import os
from random import random
from PIL import Image
import io
import uuid
from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from utils.randomimage import get_random_image
import shutil

UPLOADS_DIR = "uploads"

os.makedirs(UPLOADS_DIR + "/approved", exist_ok=True)
os.makedirs(UPLOADS_DIR + "/queue", exist_ok=True)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/images", StaticFiles(directory="uploads/approved"), name="images")

@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

@app.get("/api/get_image")
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
                        })



@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.png', '.jpg', '.jpeg', '.gif', '.webp'):
        raise HTTPException(400, "Unsupported file type")

    contents = await file.read()
    img = Image.open(io.BytesIO(contents))

    max_size = 800
    if max(img.size) > max_size:
        ratio = max_size / max(img.size)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    if ext in ('.jpg', '.jpeg'):
        img.save(buffer, format='JPEG', quality=75, optimize=True)
    elif ext == '.png':
        img.save(buffer, format='PNG', optimize=True)
    elif ext == '.webp':
        img.save(buffer, format='WEBP', quality=75)
    else:
        buffer.write(contents)
        buffer.seek(0)

    new_filename = f"{x}{ext}"
    file_path = os.path.join(UPLOADS_DIR + "/queue", new_filename)

    with open(file_path, "wb") as f:
        f.write(buffer.getvalue())

    return {"message": "File uploaded and compressed", "filename": new_filename}