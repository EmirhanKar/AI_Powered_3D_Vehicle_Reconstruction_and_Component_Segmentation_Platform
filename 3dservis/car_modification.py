import os
import cv2
import glob
import numpy as np
import torch
from ultralytics import YOLO
from scipy.ndimage import binary_fill_holes

# ----------------------------
# YOLLAR
# ----------------------------

IMAGES_DIR = r"C:\Users\Turkuaz\Desktop\segmentasyon\images"

OUTPUT_DIR = r"C:\Users\Turkuaz\Desktop\segmentasyon\output\wheel_pro_final"

RIM_PATH = r"C:\Users\Turkuaz\Desktop\segmentasyon\jant_foto\jant.png"

YOLO_MODEL_PATH = r"C:\Users\Turkuaz\Desktop\segmentasyon\runs\segment\train4\weights\best.pt"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ----------------------------
# MODEL
# ----------------------------

device = "cuda" if torch.cuda.is_available() else "cpu"

yolo = YOLO(YOLO_MODEL_PATH)

print(f"Cihaz: {device} | Sınıflar: {yolo.names}")

# ----------------------------
# IMAGE LOADER
# ----------------------------

def get_images():

    exts = [
        "*.jpg",
        "*.jpeg",
        "*.png",
        "*.webp",
        "*.JPG",
        "*.JPEG",
        "*.PNG"
    ]

    files = []

    for e in exts:
        files.extend(glob.glob(os.path.join(IMAGES_DIR, e)))

    return files

# ----------------------------
# LOAD RIM
# ----------------------------

def load_rim(path):

    rim = cv2.imread(path, cv2.IMREAD_UNCHANGED)

    if rim is None:
        raise FileNotFoundError(f"Jant bulunamadı: {path}")

    # grayscale fix
    if rim.ndim == 2:
        rim = cv2.cvtColor(rim, cv2.COLOR_GRAY2BGR)

    # alpha
    if rim.shape[2] == 4:

        rim_bgr = rim[:, :, :3]

        rim_alpha = rim[:, :, 3].astype(np.float32) / 255.0

    else:

        rim_bgr = rim

        gray = cv2.cvtColor(rim_bgr, cv2.COLOR_BGR2GRAY)

        _, bg = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)

        rim_alpha = (255 - bg).astype(np.float32) / 255.0

        filled = binary_fill_holes(rim_alpha > 0.1).astype(np.float32)

        rim_alpha = cv2.GaussianBlur(filled, (5, 5), 0)

    # ------------------------
    # canlı görünüm
    # ------------------------

    hsv = cv2.cvtColor(rim_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)

    hsv[:, :, 1] *= 1.15
    hsv[:, :, 2] *= 1.08

    hsv = np.clip(hsv, 0, 255)

    rim_bgr = cv2.cvtColor(
        hsv.astype(np.uint8),
        cv2.COLOR_HSV2BGR
    )

    rim_bgr = cv2.convertScaleAbs(
        rim_bgr,
        alpha=1.05,
        beta=5
    )

    return rim_bgr, rim_alpha

# ----------------------------
# WHEEL INSTANCES
# ----------------------------

def get_wheel_instances(img):

    h, w = img.shape[:2]

    results = yolo.predict(
        img,
        conf=0.25,
        imgsz=1024,
        verbose=False
    )

    instances = []

    for r in results:

        if r.masks is None:
            continue

        for i, m in enumerate(r.masks.data.cpu().numpy()):

            cls_id = int(r.boxes.cls[i])

            cls_name = yolo.names[cls_id].lower()

            if "wheel" not in cls_name:
                continue

            m = (m > 0.5).astype(np.uint8)

            m = cv2.resize(
                m,
                (w, h),
                interpolation=cv2.INTER_NEAREST
            )

            # temizle
            kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (7, 7)
            )

            m = cv2.morphologyEx(
                m,
                cv2.MORPH_CLOSE,
                kernel
            )

            m = binary_fill_holes(m).astype(np.uint8)

            cnts, _ = cv2.findContours(
                m,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )

            if not cnts:
                continue

            c = max(cnts, key=cv2.contourArea)

            if cv2.contourArea(c) < 500:
                continue

            if len(c) < 5:
                continue

            ellipse = cv2.fitEllipse(c)

            instances.append({
                "mask": m,
                "ellipse": ellipse
            })

    return instances

# ----------------------------
# WARP RIM TO ELLIPSE
# ----------------------------
def warp_rim_to_ellipse(rim_bgr, rim_alpha, ellipse, canvas_shape):
    h_canvas, w_canvas = canvas_shape[:2]
    (cx, cy), (ma, mb), angle = ellipse
    h_rim, w_rim = rim_bgr.shape[:2]

    # --- 1. PERSPEKTİF DÜZELTME (4 NOKTA SİSTEMİ) ---
    # Jantın kare köşeleri
    src_pts = np.array([
        [0, 0], [w_rim, 0], 
        [w_rim, h_rim], [0, h_rim]
    ], dtype=np.float32)

    # Tekerleğin elipsine göre 4 köşe noktası hesapla (Rotated Rect)
    # Bu aşama, jantın elipsin içine perspektifli girmesini sağlar
    box = cv2.boxPoints(((cx, cy), (ma, mb), angle)).astype(np.float32)
    
    # Perspektif matrisi (Affine yerine Homografi mantığı)
    M_persp = cv2.getPerspectiveTransform(src_pts, box)
    
    warp_rim = cv2.warpPerspective(rim_bgr, M_persp, (w_canvas, h_canvas), flags=cv2.INTER_LANCZOS4)
    warp_alp = cv2.warpPerspective(rim_alpha, M_persp, (w_canvas, h_canvas), flags=cv2.INTER_LANCZOS4)

    # --- 2. MERKEZ KAYMASINI ÖNLEYEN GELİŞMİŞ REMAP ---
    y, x = np.mgrid[0:h_canvas, 0:w_canvas]
    dx, dy = x - cx, y - cy

    # Elipsin açısına göre koordinatları döndür
    rad = np.deg2rad(-angle)
    x_rot = dx * np.cos(rad) - dy * np.sin(rad)
    y_rot = dx * np.sin(rad) + dy * np.cos(rad)

    # Normalize edilmiş mesafe (Elipsin içine yayılım kontrolü)
    # Burada 0.95 çarpanı, jantın lastik yanağına aşırı taşmasını önler
    norm_dist = np.sqrt((x_rot / (ma / 2 * 0.95))**2 + (y_rot / (mb / 2 * 0.95))**2)
    
    # Jant tellerinin içe doğru bükülmesini (derinlik etkisi) sağlar
    # Eğer norm_dist 1'den büyükse (dışarıdaysa) daraltır
    scale = np.where(norm_dist > 1.0, 1.0 / (norm_dist**1.1), 1.0)

    final_x = (cx + dx * scale).astype(np.float32)
    final_y = (cy + dy * scale).astype(np.float32)

    # Nihai Remap
    final_rim = cv2.remap(warp_rim, final_x, final_y, interpolation=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT)
    final_alp = cv2.remap(warp_alp, final_x, final_y, interpolation=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT)

    return final_rim, final_alp
# ----------------------------
# MATCH COLOR
# ----------------------------

def match_color(src, ref, mask):

    src_f = src.astype(np.float32)

    ref_f = ref.astype(np.float32)

    m = (mask > 0.1).astype(bool)

    if np.sum(m) < 10:
        return src

    out = src_f.copy()

    influence = 0.15

    for c in range(3):

        s_ch = src_f[:, :, c][m]

        r_ch = ref_f[:, :, c][m]

        if s_ch.std() < 1e-3:
            continue

        if r_ch.std() < 1e-3:
            continue

        matched = (
            (s_ch - s_ch.mean()) /
            s_ch.std()
        ) * r_ch.std() + r_ch.mean()

        out[:, :, c][m] = (
            s_ch * (1 - influence) +
            matched * influence
        )

    return np.clip(out, 0, 255).astype(np.uint8)

# ----------------------------
# LIGHTING
# ----------------------------

def apply_lighting(rim_bgr, rim_alpha):

    h, w = rim_bgr.shape[:2]

    y, x = np.mgrid[-1:1:h*1j, -1:1:w*1j]

    shading = np.clip(
        1.0 - (x * 0.4 - y * 0.6) * 0.3,
        0.7,
        1.2
    )

    dist = np.sqrt(x**2 + y**2)

    vignette = np.clip(
        1.1 - dist * 0.2,
        0.7,
        1.1
    )

    final_shading = (
        shading * vignette
    ).astype(np.float32)

    out = rim_bgr.astype(np.float32)

    for c in range(3):

        out[:, :, c] *= (
            final_shading * rim_alpha +
            (1 - rim_alpha)
        )

    return np.clip(out, 0, 255).astype(np.uint8)

# ----------------------------
# COMPOSITE
# ----------------------------

def composite(
    canvas,
    rim_bgr,
    rim_alpha,
    mask
):

    combined_alpha = np.clip(
        rim_alpha * mask.astype(np.float32),
        0,
        1
    )

    combined_alpha = cv2.GaussianBlur(
        combined_alpha,
        (7, 7),
        0
    )[:, :, None]

    out = (
        canvas.astype(np.float32) *
        (1 - combined_alpha)
        +
        rim_bgr.astype(np.float32) *
        combined_alpha
    )

    return np.clip(out, 0, 255).astype(np.uint8)

# ----------------------------
# MAIN LOOP
# ----------------------------

def process_all():

    rim_bgr, rim_alpha = load_rim(RIM_PATH)

    files = get_images()

    print(f"{len(files)} adet görüntü işleniyor...")

    for f in files:

        img = cv2.imread(f)

        if img is None:
            continue

        instances = get_wheel_instances(img)

        result = img.copy()

        for inst in instances:

            mask = inst["mask"]

            ellipse = inst["ellipse"]

            # mask büyüt
            kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (11, 11)
            )

            dilated_mask = cv2.dilate(
                mask,
                kernel
            )

            # warp
            rim_w, alp_w = warp_rim_to_ellipse(
                rim_bgr,
                rim_alpha,
                ellipse,
                img.shape
            )

            # roi
            roi = cv2.bitwise_and(
                result,
                result,
                mask=(dilated_mask * 255).astype(np.uint8)
            )

            # color
            rim_c = match_color(
                rim_w,
                roi,
                dilated_mask
            )

            # light
            rim_l = apply_lighting(
                rim_c,
                alp_w
            )

            # composite
            result = composite(
                result,
                rim_l,
                alp_w,
                dilated_mask
            )

        save_path = os.path.join(
            OUTPUT_DIR,
            "final_" + os.path.basename(f)
        )

        cv2.imwrite(save_path, result)

        print("Bitti:", os.path.basename(f))

# ----------------------------
# RUN
# ----------------------------

if __name__ == "__main__":

    process_all()