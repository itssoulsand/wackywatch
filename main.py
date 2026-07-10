import os
import io
import uuid
import imghdr
import asyncio
from typing import Tuple
from PIL import Image
from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import aiofiles
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from utils.randomimage import get_random_image

UPLOADS_DIR = "uploads"
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 3000 * 3000

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

os.makedirs(UPLOADS_DIR + "/approved", exist_ok=True)
os.makedirs(UPLOADS_DIR + "/queue", exist_ok=True)

app = FastAPI()
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please wait a minute before uploading again."}
    )

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/images", StaticFiles(directory="uploads/approved"), name="images")

class UploadResponse(BaseModel):
    message: str
    filename: str

class ImagePathResponse(BaseModel):
    path: str

def verify_image_type(contents: bytes, ext: str) -> str:
    img_type = imghdr.what(None, h=contents)
    if not img_type:
        raise ValueError("File is not a valid image")
    
    type_map = {
        'jpeg': ('.jpg', '.jpeg'),
        'png': ('.png',),
        'gif': ('.gif',),
        'webp': ('.webp',)
    }
    
    if img_type not in type_map or ext not in type_map[img_type]:
        raise ValueError("File extension does not match its content")
    
    return img_type

def process_image(contents: bytes, ext: str) -> bytes:
    real_type = verify_image_type(contents, ext)
    
    img = Image.open(io.BytesIO(contents))

    if real_type == 'gif' and getattr(img, "is_animated", False):
        return contents

    max_size = 800
    if max(img.size) > max_size:
        ratio = max_size / max(img.size)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        if real_type == 'jpeg' and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    if real_type in ('jpeg',):
        img.save(buffer, format='JPEG', quality=75, optimize=True)
    elif real_type == 'png':
        img.save(buffer, format='PNG', optimize=True)
    elif real_type == 'webp':
        img.save(buffer, format='WEBP', quality=75)
    else:
        buffer.write(contents)

    return buffer.getvalue()


@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

@app.get("/api/get_image", response_model=ImagePathResponse | None)
async def get_image(pathonly: bool = Query(False)):
    try:
        path, filename = await get_random_image()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    image_path = f"/images/{filename}"
    
    if pathonly:
        return {"path": image_path}
        
    return FileResponse(
        path,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Image-URL": image_path
        }
    )

@app.post("/api/upload", response_model=UploadResponse)
@limiter.limit("5/minute")
async def upload_image(request: Request, file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.png', '.jpg', '.jpeg', '.gif', '.webp'):
        raise HTTPException(400, "Unsupported file extension. Supported: PNG, JPG, JPEG, GIF, WEBP")

    contents = await file.read(MAX_FILE_SIZE + 1) 
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(413, "File is too large. Maximum size is 10MB.")

    try:
        processed_bytes = await asyncio.to_thread(process_image, contents, ext)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        error_msg = str(e)
        if "pixels" in error_msg or "Image size" in error_msg or "exceeds limit" in error_msg:
            raise HTTPException(
                400, 
                "Image resolution is too high. Maximum is 3000×3000 pixels (9MP total)."
            )
        raise HTTPException(400, f"Failed to process image: {error_msg}")

    new_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOADS_DIR + "/queue", new_filename)

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(processed_bytes)

    return {"message": "File uploaded and compressed", "filename": new_filename}