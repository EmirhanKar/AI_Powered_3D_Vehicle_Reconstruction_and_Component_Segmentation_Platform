import os
import glob
import cv2
from ultralytics import YOLO


# ----------------------------
# PATHS
# ----------------------------
model_path = r"C:\Users\Turkuaz\Desktop\segmentasyon\runs\segment\train4\weights\best.pt"
images_dir = r"C:\Users\Turkuaz\Desktop\segmentasyon\images"
output_dir = r"C:\Users\Turkuaz\Desktop\segmentasyon\output\yolo_results"

os.makedirs(output_dir, exist_ok=True)


# ----------------------------
# LOAD MODEL
# ----------------------------
model = YOLO(model_path)


# ----------------------------
# GET ALL IMAGES
# ----------------------------
image_files = []
extensions = ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG"]

for ext in extensions:
    image_files.extend(glob.glob(os.path.join(images_dir, ext)))

print(f"📂 Total images found: {len(image_files)}")


# ----------------------------
# PROCESS EACH IMAGE
# ----------------------------
for img_path in image_files:

    print("\n====================================")
    print("📸 IMAGE:", img_path)

    img = cv2.imread(img_path)

    if img is None:
        print("❌ Cannot read image")
        continue

    h, w = img.shape[:2]

    # ----------------------------
    # PREDICT
    # ----------------------------
    results = model.predict(
        source=img,
        conf=0.25,
        imgsz=1024
    )

    for r in results:

        # ----------------------------
        # BOX INFO
        # ----------------------------
        if r.boxes is not None:

            classes = r.boxes.cls.cpu().numpy().astype(int)
            confs = r.boxes.conf.cpu().numpy()

            print(f"📦 Objects detected: {len(classes)}")
            print(f"📊 Classes: {classes}")
            print(f"📊 Confidences: {confs.round(3)}")

        else:
            print("❌ No boxes detected")

        # ----------------------------
        # MASK INFO
        # ----------------------------
        if r.masks is not None:

            masks = r.masks.data.cpu().numpy()

            print(f"🎭 Masks found: {masks.shape[0]}")

            total_area = 0

            for i, m in enumerate(masks):

                m = cv2.resize(m, (w, h))
                m = (m > 0.5).astype("uint8")

                area = m.sum()
                total_area += area

                print(f"   - Mask {i}: area = {area}")

            coverage = total_area / (h * w)

            print(f"📏 Coverage ratio: {coverage:.3f}")

        else:
            print("❌ No masks found")

        # ----------------------------
        # SAVE VISUAL OUTPUT
        # ----------------------------
        annotated = r.plot()

        name = os.path.splitext(os.path.basename(img_path))[0]

        save_path = os.path.join(
            output_dir,
            name + "_result.jpg"
        )

        cv2.imwrite(save_path, annotated)

        print(f"💾 Saved: {save_path}")


print("\n✅ ALL DONE")