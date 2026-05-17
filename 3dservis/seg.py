import os
import cv2
from ultralytics import YOLO
from config import IMAGES_DIR, JANT_DIR, YOLO_MODEL_PATH

# --- Model ve görsel yolları ---
model_path = YOLO_MODEL_PATH
image_path = os.path.join(IMAGES_DIR, "araba.jpeg")
output_path = os.path.join(JANT_DIR, "sonuc.jpeg")

# --- Modeli yükle ---
model = YOLO(model_path)
print(model.names)

# --- Tahmin yap ---
results = model.predict(source=image_path, conf=0.25, imgsz=1024)  # daha küçük parçaları yakalamak için

# --- Sonuçları işle ve eksik parçaları tespit et ---
for idx, result in enumerate(results):
    print(f"--- Result {idx} ---")

    # Maskeleri kontrol et
    if result.masks:
        masks = result.masks.data
        print(f"Maskelenen obje sayısı: {masks.shape[0]}")
    else:
        print("Mask yok")

    # Bounding boxları ve sınıfları kontrol et
    if result.boxes:
        boxes = result.boxes.xyxy
        classes = result.boxes.cls
        print(f"Box sayısı: {len(boxes)}")
        print(f"Sınıflar (class indexleri): {classes}")
    else:
        print("Box yok")

    # Annotated image oluştur ve kaydet
    annotated_img = result.plot()
    cv2.imwrite(output_path, annotated_img)

print(f"Tahmin tamamlandı. Annotated image kaydedildi: {output_path}")
