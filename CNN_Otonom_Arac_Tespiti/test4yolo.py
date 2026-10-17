import cv2
from ultralytics import YOLO

# 1. Hazır eğitilmiş YOLOv8 modelini yükle (Nano versiyonu çok hızlıdır)
model = YOLO('yolov8n.pt') 

# 2. Kamerayı başlat
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret: break

    # 3. YOLO ile nesne tespiti yap
    results = model(frame, stream=True)

    for r in results:
        boxes = r.boxes
        for box in boxes:
            # Sınıf ismini al (0: person, 2: car, 3: motorcycle, 5: bus, 7: truck)
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            
            # Sadece araba türevi araçları (car, truck, bus) hedefleyelim
            if cls in [2, 5, 7] and conf > 0.5:
                # Koordinatları al
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                
                # YEŞİL ŞABLON (Araba bulundu!)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                cv2.putText(frame, f"ARABA: %{conf*100:.1f}", (x1, y1-10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            # Eğer insansa (elini salladığında) kırmızı veya istersen hiçbir şey yapma
            elif cls == 0:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(frame, "INSAN (ENGEL)", (x1, y1-10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    cv2.imshow("MODIF-AI YOLOv8 Destekli Tespit", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()