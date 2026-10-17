import cv2
import numpy as np
from tensorflow.keras.models import load_model

# 1. Güçlendirilmiş Modeli Yükle
model = load_model('araba_modeli_guclu_v2.keras')

# 2. Kamerayı Başlat (Genellikle 0 varsayılan kameradır)
cap = cv2.VideoCapture(0)

print("🚀 Kamera başlatıldı. Çıkmak için 'q' tuşuna basın.")

while True:
    # Kameradan bir kare oku
    ret, frame = cap.read()
    if not ret:
        break

    # Ekran boyutlarını al
    h, w, _ = frame.shape
    
    # --- MODEL İÇİN ÖN İŞLEME ---
    # Kameradan gelen kareyi modelin beklediği 224x224 boyutuna getir
    resized_frame = cv2.resize(frame, (224, 224))
    normalized_frame = resized_frame / 255.0
    input_data = np.expand_dims(normalized_frame, axis=0)

    # --- TAHMİN ---
    predictions = model.predict(input_data, verbose=0)
    confidence = np.max(predictions) * 100
    
    # --- VİZÖR TASARIMI VE MANTIK ---
    # Eşik değerini belirleyelim (Şu anki eğitim seviyene göre %15-20 makuldür)
    if confidence > 60: # %60 üzeri güven varsa araba var diyelim
        color = (0, 255, 0) # YEŞİL (Araba var)
        label = "ARABA TESPIT EDILDI"
    else:
        color = (0, 0, 255) # KIRMIZI (Araba yok/Bilinmiyor)
        label = "NESNE ARANIYOR..."

    # Ekranın ortasına bir vizör çerçevesi çiz
    # (x1, y1), (x2, y2)
    cv2.rectangle(frame, (w//4, h//4), (3*w//4, 3*h//4), color, 2)
    
    # Bilgi Paneli (Üst siyah bant)
    cv2.rectangle(frame, (0, 0), (w, 50), (0, 0, 0), -1)
    cv2.putText(frame, f"{label}: %{confidence:.1f}", (20, 35), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    # Görüntüyü göster
    cv2.imshow('Otonom Arac Tespit Sistemi - Canli', frame)

    # 'q' tuşuna basılırsa döngüden çık
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Kaynakları serbest bırak
cap.release()
cv2.destroyAllWindows()