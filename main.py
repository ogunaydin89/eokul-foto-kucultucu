import os
import sys
import json
import base64
import cv2
import numpy as np
from PIL import Image, ExifTags
import bottle
import webview
import threading

# Handle PyInstaller paths
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    STATIC_DIR = os.path.join(getattr(sys, '_MEIPASS', BASE_DIR), 'static')
    CASCADE_PATH = os.path.join(getattr(sys, '_MEIPASS', BASE_DIR), 'haarcascade_frontalface_default.xml')
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    STATIC_DIR = os.path.join(BASE_DIR, 'static')
    CASCADE_PATH = os.path.join(BASE_DIR, 'haarcascade_frontalface_default.xml')

app = bottle.Bottle()

# Load OpenCV cascade - Handle non-ASCII path issue in cv2 on Windows
import tempfile
import shutil

temp_dir = tempfile.gettempdir()
safe_cascade_path = os.path.join(temp_dir, 'haarcascade_frontalface_default.xml')
if not os.path.exists(safe_cascade_path):
    shutil.copy2(CASCADE_PATH, safe_cascade_path)

face_cascade = cv2.CascadeClassifier(safe_cascade_path)

TARGET_WIDTH = 133
TARGET_HEIGHT = 171
TARGET_RATIO = TARGET_WIDTH / TARGET_HEIGHT

@app.route('/')
def serve_index():
    return bottle.static_file('index.html', root=STATIC_DIR)

@app.route('/<filepath:path>')
def serve_static(filepath):
    return bottle.static_file(filepath, root=STATIC_DIR)

def auto_crop_face(image_bytes):
    # Convert bytes to cv2 image
    np_arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img is None:
        return None, "Geçersiz resim formatı"

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

    img_h, img_w = img.shape[:2]

    # If no face found, default to center crop with target ratio
    if len(faces) == 0:
        crop_w = img_w
        crop_h = int(crop_w / TARGET_RATIO)
        if crop_h > img_h:
            crop_h = img_h
            crop_w = int(crop_h * TARGET_RATIO)
        
        x = (img_w - crop_w) // 2
        y = (img_h - crop_h) // 2
        return {"x": x, "y": y, "width": crop_w, "height": crop_h, "face_found": False}, None

    # Use the largest face
    faces = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)
    fx, fy, fw, fh = faces[0]

    desired_crop_h = int(fh * 2.5)
    desired_crop_w = int(desired_crop_h * TARGET_RATIO)

    cx = fx + fw // 2
    cy = fy + fh // 2

    crop_x = cx - (desired_crop_w // 2)
    crop_y = cy - int(desired_crop_h * 0.45)

    if crop_x < 0: crop_x = 0
    if crop_y < 0: crop_y = 0
    if crop_x + desired_crop_w > img_w:
        desired_crop_w = img_w - crop_x
        desired_crop_h = int(desired_crop_w / TARGET_RATIO)
    if crop_y + desired_crop_h > img_h:
        desired_crop_h = img_h - crop_y
        desired_crop_w = int(desired_crop_h * TARGET_RATIO)

    return {"x": int(crop_x), "y": int(crop_y), "width": int(desired_crop_w), "height": int(desired_crop_h), "face_found": True}, None

@app.post('/api/detect')
def api_detect():
    upload = bottle.request.files.get('image')
    if not upload:
        return {"error": "Resim yüklenmedi"}
    
    file_bytes = upload.file.read()
    crop_box, err = auto_crop_face(file_bytes)
    
    if err:
        return {"error": err}
        
    b64_img = base64.b64encode(file_bytes).decode('utf-8')
    mime = "image/jpeg"
    if upload.filename.lower().endswith(".png"): mime = "image/png"
    
    return {
        "image_data": f"data:{mime};base64,{b64_img}",
        "crop_box": crop_box,
        "filename": upload.filename
    }

def ensure_file_size(img, filepath):
    # e-Okul explicitly requires size to be strictly > 20 KB! ("20 Kb' dan küçük olamaz")
    # We will aim for exactly 25 KB to be safe, while staying under 50 KB.
    target_min = 25 * 1024
    target_max = 50 * 1024
    
    quality = 100
    img.save(filepath, "JPEG", quality=quality, optimize=False)
    
    while os.path.getsize(filepath) > target_max and quality > 10:
        quality -= 5
        img.save(filepath, "JPEG", quality=quality, optimize=True)
        
    # If it's too small (below 25KB), we add padding via EXIF data
    size = os.path.getsize(filepath)
    if size < target_min:
        padding_needed = target_min - size + 1024 # Add 1KB extra buffer
        dummy_exif = b"Exif\x00\x00" + (b"A" * padding_needed)
        img.save(filepath, "JPEG", quality=quality, exif=dummy_exif)

# Increase Bottle's default request size limit to 50MB for large images
bottle.BaseRequest.MEMFILE_MAX = 1024 * 1024 * 50

@app.post('/api/save')
def api_save():
    try:
        data = bottle.request.json
        if not data:
            return {"error": "Veri alınamadı veya çok büyük."}
        
        b64_data = data['image'].split(',')[1]
        filename = data['filename']
        
        base_name = os.path.splitext(filename)[0]
        new_filename = base_name + "_eOkul.jpg"
        
        desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
        output_dir = os.path.join(desktop, "eOkul_Hazir_Fotograflar")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        output_path = os.path.join(output_dir, new_filename)
        
        img_bytes = base64.b64decode(b64_data)
        import io
        img = Image.open(io.BytesIO(img_bytes))
        
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        img = img.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)
        
        ensure_file_size(img, output_path)
        
        return {"status": "success", "path": output_path, "size": os.path.getsize(output_path)}
    except Exception as e:
        # DO NOT use traceback.print_exc() as it writes to sys.stderr and crashes pythonw.exe
        return {"error": str(e)}

def run_server():
    bottle.run(app, host='127.0.0.1', port=8090, quiet=True)

if __name__ == '__main__':
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    import time
    time.sleep(1)
    
    webview.create_window('e-Okul Fotoğraf Küçültücü', 'http://127.0.0.1:8090', width=1200, height=800)
    webview.start()
