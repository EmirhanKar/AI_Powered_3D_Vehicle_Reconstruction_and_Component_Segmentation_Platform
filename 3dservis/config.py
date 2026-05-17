import os

# Tüm yollar bu dosyanın bulunduğu klasöre göre ayarlanır.
# Artık hardcoded yol yok — hangi bilgisayarda olursa olsun çalışır.

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

IMAGES_DIR = os.path.join(BASE_DIR, "images")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
JANT_DIR = os.path.join(BASE_DIR, "jant_foto")

# YOLO eğitilmiş model
YOLO_MODEL_PATH = os.path.join(BASE_DIR, "runs", "segment", "train4", "weights", "best.pt")

# YOLO base modeller
YOLO_V8M_SEG = os.path.join(BASE_DIR, "yolov8m-seg.pt")

# SAM checkpoint (indirildikten sonra buraya koyulmalı)
SAM_DIR = os.path.join(BASE_DIR, "SAM")
SAM_CHECKPOINT = os.path.join(SAM_DIR, "sam_vit_h_4b8939.pth")

# COLMAP (varsa)
COLMAP_PATH = os.path.join(BASE_DIR, "colmap", "bin", "colmap.exe")
