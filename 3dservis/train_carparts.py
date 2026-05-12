from ultralytics import YOLO

if __name__ == "__main__":
    model = YOLO("yolo11n-seg.pt")

    model.train(
        data="carparts-seg.yaml",
        epochs=50,
        imgsz=640,
        batch=8
    )