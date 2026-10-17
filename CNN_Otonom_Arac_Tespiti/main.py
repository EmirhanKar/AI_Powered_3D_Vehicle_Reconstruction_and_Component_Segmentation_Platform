import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image
from scipy.io import loadmat
import tensorflow as tf

# Derin Öğrenme Kütüphaneleri
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras import layers, models

# ==========================================
# 1. VERİ YÜKLEME VE HAZIRLIK
# ==========================================

# Klasör yollarını projenin yapısına göre belirliyoruz
# car_devkit/devkit içinde etiketler, cars_train içinde resimler var
path = os.path.join(os.getcwd(), 'car_devkit', 'devkit')
target_file = 'cars_train_annos.mat'
file_path = os.path.join(path, target_file)

print(f"🔍 Aranan etiket dosyası: {file_path}")

try:
    # .mat dosyasını yüklüyoruz
    annos = loadmat(file_path)
    annotations = annos['annotations'][0]

    data = []
    for ann in annotations:
        # Stanford formatı: [x1, y1, x2, y2, class, name]
        x1, y1, x2, y2 = ann[0][0][0], ann[1][0][0], ann[2][0][0], ann[3][0][0]
        class_id = ann[4][0][0]
        file_name = ann[5][0]
        data.append([file_name, x1, y1, x2, y2, class_id])

    # DataFrame oluşturma
    df = pd.DataFrame(data, columns=['file_name', 'x1', 'y1', 'x2', 'y2', 'class_id'])
    df['class_id'] = df['class_id'].astype(str) # Keras için string formatı
    
    print(f"✅ Veri başarıyla yüklendi! Toplam: {len(df)} görsel.")

except Exception as e:
    print(f"❌ Veri yükleme hatası: {e}")

# ==========================================
# 2. VERİ JENERATÖRÜ (DATA PIPELINE)
# ==========================================

# Resimlerin olduğu klasör
train_images_path = os.path.join(os.getcwd(), 'cars_train', 'cars_train')

# Normalizasyon ve %20 doğrulama ayrımı
datagen = ImageDataGenerator(rescale=1./255, validation_split=0.2)

# Eğitim Jeneratörü
train_generator = datagen.flow_from_dataframe(
    dataframe=df,
    directory=train_images_path,
    x_col="file_name",
    y_col="class_id",
    target_size=(224, 224),
    batch_size=32,
    class_mode="categorical",
    subset="training"
)

# Doğrulama Jeneratörü
val_generator = datagen.flow_from_dataframe(
    dataframe=df,
    directory=train_images_path,
    x_col="file_name",
    y_col="class_id",
    target_size=(224, 224),
    batch_size=32,
    class_mode="categorical",
    subset="validation"
)

# ==========================================
# 3. MODEL MİMARİSİ (CNN & TRANSFER LEARNING)
# ==========================================

# MobileNetV2 temelini kuruyoruz
base_model = MobileNetV2(input_shape=(224, 224, 3), include_top=False, weights='imagenet')

# Önce kaba eğitim için donduruyoruz
base_model.trainable = False

model = models.Sequential([
    base_model,
    layers.GlobalAveragePooling2D(),
    layers.Dense(256, activation='relu'),
    layers.Dropout(0.5),
    layers.Dense(196, activation='softmax')
])

# İlk derleme (Kaba eğitim için)
model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])

# ==========================================
# 4. EĞİTİM AŞAMALARI
# ==========================================

# AŞAMA 1: Kaba Eğitim (Dondurulmuş ağırlıklar ile 5 Epoch)
print("\n🚀 1. Aşama: Kaba eğitim başlıyor...")
model.fit(train_generator, validation_data=val_generator, epochs=5, verbose=1)

# AŞAMA 2: Fine-Tuning (İnce Ayar)
print("\n🔧 2. Aşama: İnce ayar (Fine-tuning) başlıyor...")
base_model.trainable = True

# İlk 100 katmanı dondurup sonrasını eğitime açıyoruz (Daha hassas öğrenme için)
for layer in base_model.layers[:100]:
    layer.trainable = False

# Çok düşük learning rate ile yeniden derliyoruz
model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.00001), 
              loss='categorical_crossentropy', 
              metrics=['accuracy'])

# Daha uzun eğitim (15 Epoch)
history = model.fit(
    train_generator,
    validation_data=val_generator,
    epochs=15,
    verbose=1
)

# ==========================================
# 5. KAYDETME
# ==========================================

model.save('araba_modeli_guclu_v2.keras')
print("\n✅ Güçlendirilmiş model başarıyla kaydedildi!")