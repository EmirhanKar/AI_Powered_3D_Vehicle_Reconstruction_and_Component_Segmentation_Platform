from ultralytics import YOLO

if __name__ == "__main__":
    # YOLOv8m-seg modeli: 6GB GPU için güvenli ve küçük parçaları iyi öğrenir
    model = YOLO(r"C:\Users\Turkuaz\Desktop\segmentasyon\yolov8m-seg.pt")

    # Eğitim
    results = model.train(
        data="data.yaml",   # dataset
        epochs=200,         # küçük parçalar için yeterli tekrar
        device=0,           # GPU
        imgsz=1024,         # küçük objeler için yüksek çözünürlük
        batch=2,            # 6GB GPU için güvenli
        optimizer="AdamW",  # default optimizer
        augment=True        # veri augmentasyonu
        # class_weights ve accumulate artık direkt kullanılmaz
    )

    print("Training tamamlandı. Sonuçlar:")
    print(results)