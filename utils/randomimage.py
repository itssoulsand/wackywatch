import os
import random

UPLOAD_DIR = "uploads"

async def get_random_image():
    try:
        files = os.listdir(UPLOAD_DIR)
    except FileNotFoundError:
        raise "Internal Server Error: Uploads directory not found"

    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    images = [f for f in files if os.path.splitext(f)[1].lower() in image_extensions]

    if not images:
        raise "Internal Server Error: No images found in uploads directory"

    random_file = random.choice(images)
    file_path = os.path.join(UPLOAD_DIR, random_file)

    return file_path