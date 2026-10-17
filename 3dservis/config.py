import os
import sys

# ── 1. Temel Dizin ve Ortam Ayarları ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# HuggingFace model önbelleğini yerel hf_cache klasörüne bağla (C sürücüsünün dolmasını önler)
HF_CACHE_DIR = os.path.join(BASE_DIR, "hf_cache")
os.environ["HF_HOME"] = HF_CACHE_DIR
os.environ["TRANSFORMERS_CACHE"] = HF_CACHE_DIR

# Depth-Anything-3 kaynak kodunu sys.path'e otomatik ekle
DA3_SRC_DIR = os.path.join(BASE_DIR, "Depth-Anything-3", "src")
if os.path.exists(DA3_SRC_DIR) and DA3_SRC_DIR not in sys.path:
    sys.path.insert(0, DA3_SRC_DIR)

# ── 2. Veri ve Çıktı Dizinleri ──
IMAGES_DIR = os.path.join(BASE_DIR, "images")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
JANT_DIR = os.path.join(BASE_DIR, "jant_foto")
DATA_DIR = os.path.join(BASE_DIR, "data")
MASKS_DIR = os.path.join(BASE_DIR, "masks")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
TEMP_3D_OUTPUT = os.path.join(BASE_DIR, "temp_3d_output")
TEMP_OUTPUT = os.path.join(BASE_DIR, "temp_output")
TEMP_SCANS = os.path.join(BASE_DIR, "temp_scans")

# Gerekli klasörlerin varlığını garanti et
for d in [HF_CACHE_DIR, OUTPUT_DIR, MASKS_DIR, RESULTS_DIR, TEMP_3D_OUTPUT, TEMP_OUTPUT, TEMP_SCANS]:
    os.makedirs(d, exist_ok=True)

# ── 3. Model Ağırlıkları ve Yolları ──
YOLO_MODEL_PATH = os.path.join(BASE_DIR, "runs", "segment", "train4", "weights", "best.pt")
YOLO_V8M_SEG = os.path.join(BASE_DIR, "yolov8m-seg.pt")
SAM_DIR = os.path.join(BASE_DIR, "SAM")
SAM_CHECKPOINT = os.path.join(SAM_DIR, "sam_vit_h_4b8939.pth")
COLMAP_PATH = os.path.join(BASE_DIR, "colmap", "bin", "colmap.exe")

# ── 4. 3D Rekonstrüksiyon Hiperparametreleri ──
POISSON_DEPTH = int(os.getenv("POISSON_DEPTH", "9"))
CONF_THRESH = float(os.getenv("CONF_THRESH", "0.65"))
OUTLIER_NB_NEIGHBORS = int(os.getenv("OUTLIER_NB_NEIGHBORS", "21"))
OUTLIER_STD_RATIO = float(os.getenv("OUTLIER_STD_RATIO", "4.0"))
DENSITY_QUANTILE = float(os.getenv("DENSITY_QUANTILE", "0.02"))
