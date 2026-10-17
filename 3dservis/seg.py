"""
seg.py
──────────────────────────────────────────────────────────────────────────────
SAM (Segment Anything) ile Araç Maskeleme ve Arka Plan Temizleme Modülü
MODIF-AI 3D Servis

İşlevler:
1. Meta SAM (ViT-H) modeli yükleme ve yönetimi
2. Çoklu açı araç fotoğraflarından aracı arka plandan (zemin, binalar, gökyüzü) izole etme
3. Morfolojik temizleme ve en büyük bağlı bileşeni (araç gövdesi) çıkarma
4. 3D rekonstrüksiyon pipeline'ı için maske önbellekleme ve toplu üretim
──────────────────────────────────────────────────────────────────────────────
"""

import os
import glob
import cv2
import numpy as np
import torch
from typing import List, Optional
from segment_anything import sam_model_registry, SamPredictor
from config import SAM_CHECKPOINT, MASKS_DIR, DATA_DIR, IMAGES_DIR


def load_sam_predictor(checkpoint_path: Optional[str] = None, device: Optional[str] = None) -> SamPredictor:
    """
    SAM ViT-H modelini GPU/CPU belleğine yükler.
    """
    ckpt = checkpoint_path or SAM_CHECKPOINT
    if not os.path.exists(ckpt):
        raise FileNotFoundError(
            f"SAM ağırlık dosyası bulunamadı: {ckpt}\n"
            "Lütfen 'sam_vit_h_4b8939.pth' dosyasını SAM/ klasörüne yerleştirin."
        )

    dev = device or ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"SAM modeli yükleniyor ({dev}): {os.path.basename(ckpt)}")
    sam = sam_model_registry["vit_h"](checkpoint=ckpt)
    sam.to(dev)
    predictor = SamPredictor(sam)
    print("✓ SAM modeli başarıyla yüklendi.")
    return predictor


def get_car_mask(predictor: SamPredictor, image_rgb: np.ndarray) -> np.ndarray:
    """
    Tek bir RGB araç görselinden aracın net ikili (binary) maskesini çıkarır.
    Merkezi 5 kritik geometrik nokta referans alınarak araç arka plandan ayrılır.
    """
    h, w = image_rgb.shape[:2]

    # Araç gövdesine odaklanan 5 kritik nokta (Merkez, Üst, Alt, Sol, Sağ)
    input_points = np.array([
        [w // 2, h // 2],          # Merkez
        [w // 2, int(h * 0.35)],   # Üst tavan / kaput
        [w // 2, int(h * 0.65)],   # Alt tampon / gövde
        [int(w * 0.30), h // 2],   # Sol kapı / çamurluk
        [int(w * 0.70), h // 2],   # Sağ kapı / çamurluk
    ], dtype=np.float32)
    input_labels = np.array([1, 1, 1, 1, 1], dtype=np.int32)

    predictor.set_image(image_rgb)
    masks, scores, _ = predictor.predict(
        point_coords=input_points,
        point_labels=input_labels,
        multimask_output=True
    )

    # En yüksek güven skoruna sahip maskeyi seç
    best_mask = masks[np.argmax(scores)].astype(np.uint8)

    # Morfolojik temizleme: delikleri kapat ve kenarları pürüzsüzleştir
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    best_mask = cv2.morphologyEx(best_mask, cv2.MORPH_CLOSE, kernel, iterations=3)
    best_mask = cv2.morphologyEx(best_mask, cv2.MORPH_OPEN, kernel, iterations=2)

    # En büyük bağlı bileşeni (aracı) seç, küçük parazitleri temizle
    num_labels, labels_im = cv2.connectedComponents(best_mask)
    if num_labels > 1:
        sizes = np.bincount(labels_im.flatten())
        sizes[0] = 0  # Arka planı sıfırla
        best_mask = (labels_im == np.argmax(sizes)).astype(np.uint8)

    return best_mask


def generate_masks(
    image_files: List[str],
    masks_path: Optional[str] = None,
    sam_predictor: Optional[SamPredictor] = None
) -> List[str]:
    """
    Verilen fotoğraf listesindeki her görsel için SAM maskesi üretir veya mevcut olanı kullanır.
    3D rekonstrüksiyon pipeline'ı (test5.py) tarafından doğrudan çağrılır.
    """
    out_dir = masks_path or MASKS_DIR
    os.makedirs(out_dir, exist_ok=True)

    if sam_predictor is None:
        sam_predictor = load_sam_predictor()

    print(f"Maskeler oluşturuluyor ({len(image_files)} görsel)...")
    mask_files = []

    for img_path in image_files:
        base_name = os.path.splitext(os.path.basename(img_path))[0]
        mask_path = os.path.join(out_dir, f"{base_name}_mask.png")

        # Önbellekte varsa tekrar üretme
        if os.path.exists(mask_path):
            print(f"  Mevcut: {os.path.basename(mask_path)}")
            mask_files.append(mask_path)
            continue

        image_bgr = cv2.imread(img_path)
        if image_bgr is None:
            print(f"❌ Görsel okunamadı: {img_path}")
            continue

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        mask = get_car_mask(sam_predictor, image_rgb)

        cv2.imwrite(mask_path, mask * 255)
        print(f"  Oluşturuldu: {os.path.basename(mask_path)}")
        mask_files.append(mask_path)

    return mask_files


if __name__ == "__main__":
    # Test çalıştırması
    test_folder = DATA_DIR if os.path.exists(DATA_DIR) and len(os.listdir(DATA_DIR)) > 0 else IMAGES_DIR
    extensions = ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.PNG"]
    images = []
    for ext in extensions:
        images.extend(glob.glob(os.path.join(test_folder, ext)))

    print(f"Bulunan test görselleri: {len(images)}")
    if images:
        predictor = load_sam_predictor()
        res = generate_masks(images[:4], MASKS_DIR, predictor)
        print(f"Üretilen maske sayısı: {len(res)}")
