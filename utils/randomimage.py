import os
import random
from fastapi import HTTPException

UPLOAD_DIR = "uploads/approved"

async def get_random_image():
    try:
        files = os.listdir(UPLOAD_DIR)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Internal Server Error: Uploads directory not found")

    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    images = [f for f in files if os.path.splitext(f)[1].lower() in image_extensions]

    if not images:
        raise HTTPException(status_code=500, detail="Internal Server Error: No images found in uploads directory")

    filename = random.choice(images)
    path = os.path.join(UPLOAD_DIR, filename)

    return path, filename