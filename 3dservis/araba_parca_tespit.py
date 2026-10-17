"""
araba_parca_tespit.py
──────────────────────────────────────────────────────────────────────────────
YOLO Araç Parça Tespiti ve Segmentasyon Modülü
MODIF-AI 3D Servis

İşlevler:
1. Eğitilmiş YOLOv8/v11 parça segmentasyon modelini yükleme (YOLO_MODEL_PATH)
2. Araç parçalarını (tekerlek, tampon, kapı, kaput, far vb.) tespit etme ve maskeleme
3. Jant ve modifikasyon pipeline'ları için parça maskeleri sağlama
4. Bağımsız olarak çalıştırıldığında test görselleri üzerinde analiz yapma
──────────────────────────────────────────────────────────────────────────────
"""

import os
import glob
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
from ultralytics import YOLO
from config import IMAGES_DIR, OUTPUT_DIR, YOLO_MODEL_PATH


def load_yolo_model(model_path: Optional[str] = None) -> YOLO:
    """YOLO parça segmentasyon modelini yükler."""
    path = model_path or YOLO_MODEL_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(f"YOLO modeli bulunamadı: {path}")
    print(f"YOLO modeli yükleniyor: {path}")
    model = YOLO(path)
    return model


def detect_car_parts(
    image: np.ndarray,
    model: Optional[YOLO] = None,
    conf: float = 0.25,
    imgsz: int = 1024
) -> Tuple[List[Dict], Optional[np.ndarray]]:
    """
    Tek bir görsel üzerinde araç parçalarını tespit eder.
    Döner: (parça_listesi, görselleştirilmiş_kare)
    """
    if model is None:
        model = load_yolo_model()

    h, w = image.shape[:2]
    results = model.predict(source=image, conf=conf, imgsz=imgsz, verbose=False)

    parts = []
    annotated_image = None

    for r in results:
        annotated_image = r.plot()
        if r.boxes is not None and r.masks is not None:
            boxes = r.boxes.xyxy.cpu().numpy()
            classes = r.boxes.cls.cpu().numpy().astype(int)
            confs = r.boxes.conf.cpu().numpy()
            masks = r.masks.data.cpu().numpy()

            for i in range(len(classes)):
                cls_id = int(classes[i])
                cls_name = model.names.get(cls_id, f"class_{cls_id}")
                mask_raw = cv2.resize(masks[i], (w, h))
                mask_binary = (mask_raw > 0.5).astype(np.uint8)

                parts.append({
                    "class_id": cls_id,
                    "class_name": cls_name,
                    "confidence": float(confs[i]),
                    "bbox": boxes[i].tolist(),
                    "mask": mask_binary,
                    "area": int(mask_binary.sum())
                })

    return parts, annotated_image


def process_images_folder(
    input_folder: Optional[str] = None,
    output_folder: Optional[str] = None,
    model_path: Optional[str] = None
):
    """Belirtilen klasördeki tüm görselleri işler ve görsel çıktıları kaydeder."""
    images_dir = input_folder or IMAGES_DIR
    out_dir = output_folder or os.path.join(OUTPUT_DIR, "yolo_results")
    os.makedirs(out_dir, exist_ok=True)

    model = load_yolo_model(model_path)
    extensions = ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]

    image_files = []
    for ext in extensions:
        image_files.extend(glob.glob(os.path.join(images_dir, ext)))

    print(f"📂 Toplam görsel bulundu: {len(image_files)}")

    for img_path in image_files:
        print(f"\n📸 İşleniyor: {os.path.basename(img_path)}")
        img = cv2.imread(img_path)
        if img is None:
            print(f"❌ Görsel okunamadı: {img_path}")
            continue

        parts, annotated = detect_car_parts(img, model=model)
        print(f"📦 Tespit edilen parça sayısı: {len(parts)}")
        for p in parts:
            print(f"   - {p['class_name']}: Güven={p['confidence']:.2f}, Alan={p['area']}")

        if annotated is not None:
            name = os.path.splitext(os.path.basename(img_path))[0]
            save_path = os.path.join(out_dir, f"{name}_result.jpg")
            cv2.imwrite(save_path, annotated)
            print(f"💾 Kaydedildi: {save_path}")

    print("\n✅ Tüm parçalar başarıyla tespit edildi.")


if __name__ == "__main__":
    process_images_folder()