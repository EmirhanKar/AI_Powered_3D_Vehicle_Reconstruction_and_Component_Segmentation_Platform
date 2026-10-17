import cv2
import numpy as np
import os
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image

# 1. Modeli Yükle
model = load_model('araba_modeli_guclu_v2.keras')

def kamera_simulasyonu(img_yolu):
    # Resmi oku
    original_img = cv2.imread(img_yolu)
    if original_img is None: return

    # Tahmin için ön işleme (224x224)
    img_for_model = cv2.resize(original_img, (224, 224))
    img_for_model = img_for_model / 255.0
    img_for_model = np.expand_dims(img_for_model, axis=0)

    # Tahmin yap
    predictions = model.predict(img_for_model, verbose=0)
    confidence = np.max(predictions) * 100
    
    # EKRAN TASARIMI
    h, w, _ = original_img.shape
    display_img = original_img.copy()

    # Eşik değeri: %15 (Eğitim seviyene göre şimdilik düşük tuttuk)
    if confidence > 15:
        renk = (0, 255, 0) # YEŞİL
        durum = "ARABA TESPIT EDILDI"
    else:
        renk = (0, 0, 255) # KIRMIZI
        durum = "NESNE ARANIYOR..."

    # Şablon Çerçevesini Çiz (Ekranın ortasında bir vizör)
    cv2.rectangle(display_img, (50, 50), (w-50, h-50), renk, 3)
    
    # Bilgi Paneli
    cv2.rectangle(display_img, (0, 0), (w, 60), (0, 0, 0), -1)
    cv2.putText(display_img, f"{durum} ({confidence:.1f}%)", (20, 40), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    cv2.imshow("Otonom Arac Tespit Sistemi", display_img)
    cv2.waitKey(1000) # Her resmi 1 saniye göster

# Klasördeki tüm resimleri "Kamera" gibi tara
test_folder = os.path.join(os.getcwd(), 'test_foto')
for foto in os.listdir(test_folder):
    kamera_simulasyonu(os.path.join(test_folder, foto))

cv2.destroyAllWindows()