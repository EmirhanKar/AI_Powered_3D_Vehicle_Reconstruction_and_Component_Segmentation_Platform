import numpy as np
import os
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
from scipy.io import loadmat

# 1. Modeli ve Sınıf İsimlerini Yükle
# En son eğittiğimiz güçlü modeli kullanıyoruz
model_path = 'araba_modeli_guclu_v2.keras'
model = load_model(model_path)

# Sınıf isimlerini (Marka/Model) cars_meta'dan çekiyoruz
meta_path = os.path.join(os.getcwd(), 'car_devkit', 'devkit', 'cars_meta.mat')
meta_data = loadmat(meta_path)
class_names = [name[0] for name in meta_data['class_names'][0]]

def araba_tahmin_et(img_yolu):
    # Klasör mü yoksa dosya mı kontrolü (PermissionError'u engeller)
    if not os.path.isfile(img_yolu):
        return

    # Resmi hazırla
    img = image.load_img(img_yolu, target_size=(224, 224))
    img_array = image.img_to_array(img) / 255.0
    img_array = np.expand_dims(img_array, axis=0)

    # Tahmin yap
    predictions = model.predict(img_array, verbose=0)
    class_idx = np.argmax(predictions)
    
    predicted_name = class_names[class_idx] 
    confidence = np.max(predictions) * 100

    print("-" * 40)
    print(f"📸 Dosya: {os.path.basename(img_yolu)}")
    print(f"🚗 Tahmin: {predicted_name}")
    print(f"🎯 Güven Oranı: %{confidence:.2f}")

# ==========================================
# 2. TEST SENARYOLARI (Görseldeki Yapıya Göre)
# ==========================================

# SENARYO 1: Kendi çektiğin tüm fotoğrafları test et
kendi_foto_klasoru = os.path.join(os.getcwd(), 'test_foto')
print("\n--- KENDİ FOTOĞRAFLARIN TEST EDİLİYOR ---")
if os.path.exists(kendi_foto_klasoru):
    for foto in os.listdir(kendi_foto_klasoru):
        full_path = os.path.join(kendi_foto_klasoru, foto)
        araba_tahmin_et(full_path)

# SENARYO 2: Veri setinden (cars_train/cars_train) örnek test et
# Görseline göre resimler bu derinlikte: cars_train -> cars_train -> .jpg
train_folder = os.path.join(os.getcwd(), 'cars_train', 'cars_train')

print("\n--- VERİ SETİNDEN ÖRNEK TEST EDİLİYOR ---")
if os.path.exists(train_folder):
    files = [f for f in os.listdir(train_folder) if f.lower().endswith(('.jpg', '.jpeg'))]
    if files:
        # İlk 3 resmi test edelim
        for i in range(min(3, len(files))):
            araba_tahmin_et(os.path.join(train_folder, files[i]))