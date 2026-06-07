"""
color_change.py — LAB tabanlı araba boyama
Kullanım: python color_change.py --image araba.jpg --color #0000FF --output sonuc.jpg
"""

import cv2
import numpy as np
import torch
import argparse
import os
from segment_anything import sam_model_registry, SamPredictor
from ultralytics import YOLO

# ─── AYARLAR ──────────────────────────────────────────────────────────────────
SAM_CHECKPOINT  = r"D:\MODIFIAI\3dservis\SAM\sam_vit_h_4b8939.pth"
YOLO_MODEL_PATH = r"D:\MODIFIAI\3dservis\runs\segment\train4\weights\best.pt"
# ──────────────────────────────────────────────────────────────────────────────


def hex_to_lab(hex_color: str) -> tuple:
    """#RRGGBB → (L, A, B) OpenCV LAB formatı"""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    pixel = np.uint8([[[b, g, r]]])
    lab = cv2.cvtColor(pixel, cv2.COLOR_BGR2Lab)
    return int(lab[0, 0, 0]), int(lab[0, 0, 1]), int(lab[0, 0, 2])


def get_body_mask(image_rgb, sam_predictor, yolo_model=None) -> np.ndarray:
    """SAM ile araç maskesi, tekerlekler çıkarılmış kaporta maskesi döner."""
    h, w = image_rgb.shape[:2]

    input_points = np.array([
        [w // 2, h // 2],
        [w // 2, h // 3],
        [w // 3, h // 2],
        [2 * w // 3, h // 2],
        [w // 2, int(h * 0.4)],
    ])
    input_labels = np.array([1, 1, 1, 1, 1])

    sam_predictor.set_image(image_rgb)
    masks, scores, _ = sam_predictor.predict(
        point_coords=input_points,
        point_labels=input_labels,
        multimask_output=True
    )
    car_mask = masks[np.argmax(scores)].astype(np.uint8)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    car_mask = cv2.morphologyEx(car_mask, cv2.MORPH_CLOSE, kernel, iterations=3)
    car_mask = cv2.morphologyEx(car_mask, cv2.MORPH_OPEN,  kernel, iterations=2)

    # YOLO ile tekerlekleri çıkar
    if yolo_model is not None:
        image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        results = yolo_model.predict(image_bgr, conf=0.25, imgsz=1024, verbose=False)
        for r in results:
            if r.masks is None:
                continue
            for i, m in enumerate(r.masks.data.cpu().numpy()):
                cls_name = yolo_model.names[int(r.boxes.cls[i])].lower()
                if "wheel" not in cls_name:
                    continue
                wheel_mask = (m > 0.5).astype(np.uint8)
                wheel_mask = cv2.resize(wheel_mask, (w, h), interpolation=cv2.INTER_NEAREST)
                wheel_dilated = cv2.dilate(wheel_mask, kernel, iterations=5)
                car_mask = np.where(wheel_dilated > 0, 0, car_mask).astype(np.uint8)

    # Alt %15 sil (zemin/gölge)
    car_mask[int(h * 0.85):, :] = 0

    return car_mask


def apply_color(image_bgr: np.ndarray, mask: np.ndarray, hex_color: str, strength: float = 0.88) -> np.ndarray:
    """
    Gerçek renk değiştirme:
    1. Gövdeyi önce griye çevir (mevcut rengi sıfırla)
    2. Hedef rengi LAB A/B kanallarıyla uygula
    3. L (parlaklık) her zaman korunur → yansıma/gölge gerçekçi
    4. Siyah plastik, cam, yansıma korunur
    """
    target_l, target_a, target_b = hex_to_lab(hex_color)

    # BGR → LAB
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2Lab).astype(np.float32)
    l_ch = lab[:, :, 0]
    a_ch = lab[:, :, 1]
    b_ch = lab[:, :, 2]

    # BGR → HSV (filtre için)
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    s_ch = hsv[:, :, 1]
    v_ch = hsv[:, :, 2]

    body      = mask > 0
    dark      = v_ch < 45
    glass     = (s_ch < 30) & (v_ch > 160)
    highlight = (v_ch > 215) & body
    normal    = body & ~dark & ~glass & ~highlight

    # Strength haritası
    strength_map = np.zeros_like(l_ch, dtype=np.float32)
    strength_map[normal]    = strength
    strength_map[highlight] = strength * 0.2

    soft = cv2.GaussianBlur(strength_map, (31, 31), 0)

    # Mevcut A/B'yi önce nötre (128) çek → mevcut rengi sil
    # Sonra hedef rengi uygula
    # Bu iki adımı tek formüle indirge:
    # new = 128 * soft + target * soft + original * (1 - soft)
    # = original * (1 - soft) + target * soft
    # Ama önce orijinal rengi nötre çekiyoruz:
    neutralized_a = a_ch * (1 - soft) + 128.0 * soft
    neutralized_b = b_ch * (1 - soft) + 128.0 * soft

    # Sonra hedef rengi uygula
    final_a = neutralized_a * (1 - soft) + target_a * soft
    final_b = neutralized_b * (1 - soft) + target_b * soft

    new_lab = np.stack([l_ch, final_a, final_b], axis=-1)
    new_lab = np.clip(new_lab, 0, 255).astype(np.uint8)

    result = cv2.cvtColor(new_lab, cv2.COLOR_Lab2BGR)
    return result


def process_image(image_path: str, hex_color: str, output_path: str,
                  sam_predictor, yolo_model=None, strength: float = 0.88):
    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        raise FileNotFoundError(f"Fotoğraf bulunamadı: {image_path}")

    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    print(f"  Maske oluşturuluyor...")
    mask = get_body_mask(image_rgb, sam_predictor, yolo_model)

    print(f"  Renk uygulanıyor: {hex_color} (LAB)")
    result = apply_color(image_bgr, mask, hex_color, strength)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    cv2.imwrite(output_path, result)
    print(f"  ✓ Kaydedildi: {output_path}")

    debug_path = output_path.rsplit(".", 1)[0] + "_mask.jpg"
    cv2.imwrite(debug_path, mask * 255)
    return result, mask


def load_models():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Cihaz: {device}")

    sam = sam_model_registry["vit_h"](checkpoint=SAM_CHECKPOINT)
    sam.to(device)
    sam_predictor = SamPredictor(sam)
    print("SAM yüklendi.")

    yolo_model = None
    if os.path.exists(YOLO_MODEL_PATH):
        yolo_model = YOLO(YOLO_MODEL_PATH)
        print("YOLO yüklendi.")
    else:
        print("YOLO bulunamadı.")

    return sam_predictor, yolo_model


def change_color_for_scan(image_path, hex_color, output_path, sam_predictor, yolo_model=None):
    try:
        process_image(image_path, hex_color, output_path, sam_predictor, yolo_model)
        return output_path
    except Exception as e:
        print(f"[HATA] {e}")
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image",    required=True)
    parser.add_argument("--color",    required=True)
    parser.add_argument("--output",   required=True)
    parser.add_argument("--strength", type=float, default=0.88)
    args = parser.parse_args()

    sam_predictor, yolo_model = load_models()
    process_image(args.image, args.color, args.output, sam_predictor, yolo_model, args.strength)
