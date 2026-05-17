import os
import cv2
import glob
import numpy as np
import torch
import requests
from ultralytics import YOLO
from scipy.ndimage import binary_fill_holes
from config import IMAGES_DIR, OUTPUT_DIR, JANT_DIR, YOLO_MODEL_PATH

# ----------------------------
# BACKEND AYARLARI
# ----------------------------

BACKEND_URL = "http://192.168.1.192:8000"
ADMIN_KEY   = "ABCDEFGHIJKLMNOPRSTUVYZ123"

# ----------------------------
# MODEL
# ----------------------------

device = "cuda" if torch.cuda.is_available() else "cpu"
yolo = YOLO(YOLO_MODEL_PATH)
print(f"Cihaz: {device} | Sınıflar: {yolo.names}")

# ----------------------------
# IMAGE LOADER
# ----------------------------

def get_images(images_dir=None):
    folder = images_dir or IMAGES_DIR
    exts = ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.JPG", "*.JPEG", "*.PNG"]
    files = []
    for e in exts:
        files.extend(glob.glob(os.path.join(folder, e)))
    return files

# ----------------------------
# LOAD RIM
# ----------------------------

def load_rim(path):
    rim = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if rim is None:
        raise FileNotFoundError(f"Jant bulunamadı: {path}")

    if rim.ndim == 2:
        rim = cv2.cvtColor(rim, cv2.COLOR_GRAY2BGR)

    if rim.shape[2] == 4:
        rim_bgr   = rim[:, :, :3]
        rim_alpha = rim[:, :, 3].astype(np.float32) / 255.0
    else:
        rim_bgr = rim
        gray = cv2.cvtColor(rim_bgr, cv2.COLOR_BGR2GRAY)
        _, bg = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
        rim_alpha = (255 - bg).astype(np.float32) / 255.0
        filled = binary_fill_holes(rim_alpha > 0.1).astype(np.float32)
        rim_alpha = cv2.GaussianBlur(filled, (5, 5), 0)

    hsv = cv2.cvtColor(rim_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] *= 1.15
    hsv[:, :, 2] *= 1.08
    hsv = np.clip(hsv, 0, 255)
    rim_bgr = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    rim_bgr = cv2.convertScaleAbs(rim_bgr, alpha=1.05, beta=5)

    return rim_bgr, rim_alpha

# ----------------------------
# WHEEL INSTANCES
# ----------------------------

def get_wheel_instances(img):
    h, w = img.shape[:2]
    results = yolo.predict(img, conf=0.25, imgsz=1024, verbose=False)
    instances = []

    for r in results:
        if r.masks is None:
            continue
        for i, m in enumerate(r.masks.data.cpu().numpy()):
            cls_id   = int(r.boxes.cls[i])
            cls_name = yolo.names[cls_id].lower()
            if "wheel" not in cls_name:
                continue

            m = (m > 0.5).astype(np.uint8)
            m = cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
            m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel)
            m = binary_fill_holes(m).astype(np.uint8)
            cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if not cnts:
                continue
            c = max(cnts, key=cv2.contourArea)
            if cv2.contourArea(c) < 500 or len(c) < 5:
                continue

            ellipse = cv2.fitEllipse(c)
            instances.append({"mask": m, "ellipse": ellipse})

    return instances

# ----------------------------
# WARP RIM TO ELLIPSE
# ----------------------------

def warp_rim_to_ellipse(rim_bgr, rim_alpha, ellipse, canvas_shape):
    h_canvas, w_canvas = canvas_shape[:2]
    (cx, cy), (ma, mb), angle = ellipse
    h_rim, w_rim = rim_bgr.shape[:2]

    src_pts = np.array([
        [0, 0], [w_rim, 0],
        [w_rim, h_rim], [0, h_rim]
    ], dtype=np.float32)

    box = cv2.boxPoints(((cx, cy), (ma, mb), angle)).astype(np.float32)
    M_persp = cv2.getPerspectiveTransform(src_pts, box)
    warp_rim = cv2.warpPerspective(rim_bgr, M_persp, (w_canvas, h_canvas), flags=cv2.INTER_LANCZOS4)
    warp_alp = cv2.warpPerspective(rim_alpha, M_persp, (w_canvas, h_canvas), flags=cv2.INTER_LANCZOS4)

    y, x = np.mgrid[0:h_canvas, 0:w_canvas]
    dx, dy = x - cx, y - cy
    rad   = np.deg2rad(-angle)
    x_rot = dx * np.cos(rad) - dy * np.sin(rad)
    y_rot = dx * np.sin(rad) + dy * np.cos(rad)

    norm_dist = np.sqrt((x_rot / (ma / 2 * 0.95))**2 + (y_rot / (mb / 2 * 0.95))**2)
    scale     = np.where(norm_dist > 1.0, 1.0 / (norm_dist**1.1), 1.0)

    final_x = (cx + dx * scale).astype(np.float32)
    final_y = (cy + dy * scale).astype(np.float32)

    final_rim = cv2.remap(warp_rim, final_x, final_y, interpolation=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT)
    final_alp = cv2.remap(warp_alp, final_x, final_y, interpolation=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT)

    return final_rim, final_alp

# ----------------------------
# MATCH COLOR
# ----------------------------

def match_color(src, ref, mask):
    src_f = src.astype(np.float32)
    ref_f = ref.astype(np.float32)
    m     = (mask > 0.1).astype(bool)

    if np.sum(m) < 10:
        return src

    out      = src_f.copy()
    influence = 0.15

    for c in range(3):
        s_ch = src_f[:, :, c][m]
        r_ch = ref_f[:, :, c][m]
        if s_ch.std() < 1e-3 or r_ch.std() < 1e-3:
            continue
        matched = ((s_ch - s_ch.mean()) / s_ch.std()) * r_ch.std() + r_ch.mean()
        out[:, :, c][m] = s_ch * (1 - influence) + matched * influence

    return np.clip(out, 0, 255).astype(np.uint8)

# ----------------------------
# LIGHTING
# ----------------------------

def apply_lighting(rim_bgr, rim_alpha):
    h, w = rim_bgr.shape[:2]
    y, x = np.mgrid[-1:1:h*1j, -1:1:w*1j]
    shading       = np.clip(1.0 - (x * 0.4 - y * 0.6) * 0.3, 0.7, 1.2)
    dist          = np.sqrt(x**2 + y**2)
    vignette      = np.clip(1.1 - dist * 0.2, 0.7, 1.1)
    final_shading = (shading * vignette).astype(np.float32)

    out = rim_bgr.astype(np.float32)
    for c in range(3):
        out[:, :, c] *= (final_shading * rim_alpha + (1 - rim_alpha))

    return np.clip(out, 0, 255).astype(np.uint8)

# ----------------------------
# COMPOSITE
# ----------------------------

def composite(canvas, rim_bgr, rim_alpha, mask):
    combined_alpha = np.clip(rim_alpha * mask.astype(np.float32), 0, 1)
    combined_alpha = cv2.GaussianBlur(combined_alpha, (7, 7), 0)[:, :, None]
    out = (
        canvas.astype(np.float32) * (1 - combined_alpha) +
        rim_bgr.astype(np.float32) * combined_alpha
    )
    return np.clip(out, 0, 255).astype(np.uint8)

# ----------------------------
# BACKEND'DEN İŞ ÇEK VE YÜKLE
# ----------------------------

def fotograflari_indir(scan_id, scan_images):
    """Backend'den fotoğrafları indir, klasör yolunu döndür."""
    klasor = os.path.join("temp_scans", str(scan_id))
    os.makedirs(klasor, exist_ok=True)

    for i, img in enumerate(scan_images):
        url = img.get("image_url", "")
        if not url.startswith("http"):
            url = f"{BACKEND_URL}/{url}"
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(os.path.join(klasor, f"{i:04d}.jpg"), "wb") as f:
            f.write(r.content)

    return klasor

def jant_indir(scan_id, jant_image_url):
    """Backend'den jant fotoğrafını indir, dosya yolunu döndür."""
    if not jant_image_url:
        return None

    if not jant_image_url.startswith("http"):
        jant_image_url = f"{BACKEND_URL}/{jant_image_url}"

    try:
        r = requests.get(jant_image_url, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"Jant indirilemedi ({jant_image_url}): {e}")
        return None

    rim_path = os.path.join("temp_scans", f"{scan_id}_jant.png")
    with open(rim_path, "wb") as f:
        f.write(r.content)

    return rim_path

def sonucu_yukle(scan_id, output_path):
    """İşlenmiş görseli backend'e yükle."""
    with open(output_path, "rb") as f:
        r = requests.post(
            f"{BACKEND_URL}/scans/complete/2d/{scan_id}",
            files={"image_file": (os.path.basename(output_path), f, "image/jpeg")},
            headers={"X-Admin-Key": ADMIN_KEY},
            timeout=120
        )
    r.raise_for_status()
    print(f"Scan {scan_id}: Backend'e yüklendi ✓")

# ----------------------------
# MAIN LOOP
# ----------------------------

def process_all(rim_path=None, input_folder=None, output_folder=None, color_code=None):
    """
    rim_path     : Jant PNG dosyası. None ise config'deki JANT_DIR kullanılır.
    input_folder : Araç fotoğrafları klasörü. None ise config'deki IMAGES_DIR.
    output_folder: Çıktı klasörü. None ise config'deki OUTPUT_DIR.
    color_code   : Renk kodu (ileride kullanılacak).
    """

    # Jant yükle
    rim_bgr, rim_alpha = None, None
    effective_rim = rim_path or os.path.join(JANT_DIR, "jant.png")
    try:
        rim_bgr, rim_alpha = load_rim(effective_rim)
    except Exception as e:
        print(f"Jant yükleme atlandı: {e}")

    # Klasörler
    images_dir = input_folder or IMAGES_DIR
    out_dir    = output_folder or OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    image_paths = get_images(images_dir)
    if not image_paths:
        print(f"Hiç görsel bulunamadı: {images_dir}")
        return None

    last_output = None

    for img_path in image_paths:
        img = cv2.imread(img_path)
        if img is None:
            continue

        instances = get_wheel_instances(img)
        if not instances:
            print(f"Tekerlek bulunamadı: {img_path}")
            result = img
        else:
            result = img.copy()
            for inst in instances:
                mask    = inst["mask"]
                ellipse = inst["ellipse"]

                if rim_bgr is not None and rim_alpha is not None:
                    warped_rim, warped_alp = warp_rim_to_ellipse(rim_bgr, rim_alpha, ellipse, img.shape)
                    warped_rim = apply_lighting(warped_rim, warped_alp)
                    warped_rim = match_color(warped_rim, img, warped_alp)
                    result     = composite(result, warped_rim, warped_alp, mask)

        fname       = os.path.splitext(os.path.basename(img_path))[0]
        output_path = os.path.join(out_dir, f"{fname}_modified.jpg")
        cv2.imwrite(output_path, result)
        last_output = output_path
        print(f"Kaydedildi: {output_path}")

    return last_output


def process_scan(scan: dict):
    """
    Backend'den gelen tek bir scan'i işler:
    1. Fotoğrafları indirir
    2. Jantı indirir
    3. process_all() çalıştırır
    4. Sonucu backend'e yükler
    """
    scan_id        = scan["scan_id"]
    jant_image_url = scan.get("jant_image_url")
    renk_kodu      = scan.get("renk_kodu")
    scan_images    = scan.get("images", [])

    method      = scan.get("method", "2d")

    print(f"\n=== Scan {scan_id} ({method}) işleniyor ===")

    foto_klasor = fotograflari_indir(scan_id, scan_images)
    rim_path    = jant_indir(scan_id, jant_image_url)

    out_dir     = os.path.join("temp_output", str(scan_id))
    output_path = process_all(
        rim_path=rim_path,
        input_folder=foto_klasor,
        output_folder=out_dir,
        color_code=renk_kodu
    )

    if method == "3d":
        if output_path:
            return out_dir
        else:
            print(f"Scan {scan_id}: Çıktı oluşturulamadı!")
            return None
    else:
        if output_path:
            sonucu_yukle(scan_id, output_path)
            return True
        else:
            print(f"Scan {scan_id}: Çıktı oluşturulamadı!")
            return False


if __name__ == "__main__":
    # Tek başına çalıştırınca local klasörlerle test eder
    process_all()