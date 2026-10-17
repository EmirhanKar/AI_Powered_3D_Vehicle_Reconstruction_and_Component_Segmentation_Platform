# MODIF-AI — Yapay Zekâ Destekli Araç Modifikasyon Platformu

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi&logoColor=white)
![Flutter](https://img.shields.io/badge/Flutter-3.x-02569B?logo=flutter&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-2.x-EE4C2C?logo=pytorch&logoColor=white)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-00FFFF?logo=yolo)
![Open3D](https://img.shields.io/badge/Open3D-3D%20Vision-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14%2B-336791?logo=postgresql&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

**Araç sahiplerinin fiziksel modifikasyon yapmadan önce görsel değişiklikleri (jant giydirme, kaporta boyama ve 3B modelleme) simüle edebilecekleri uçtan uca dijital stüdyo.**

</div>

---

## 📌 İçindekiler
- [Öne Çıkan Özellikler](#-öne-çıkan-özellikler)
- [Sistem Mimarisi](#-sistem-mimarisi)
- [Proje Yapısı](#-proje-yapısı)
- [Gereksinimler ve Model Dosyaları](#-gereksinimler-ve-model-dosyaları)
- [Kurulum ve Çalıştırma](#-kurulum-ve-çalıştırma)
  - [1. Backend Servisi (FastAPI)](#1-backend-servisi-fastapi)
  - [2. AI Worker Servisi (3dservis)](#2-ai-worker-servisi-3dservis)
  - [3. Mobil Uygulama (Flutter)](#3-mobil-uygulama-flutter)
  - [4. CNN Araç Tespiti (Opsiyonel)](#4-cnn-araç-tespiti-opsiyonel)
- [Ortam Değişkenleri (.env)](#-ortam-değişkenleri-env)
- [API Dokümantasyonu ve Endpointler](#-api-dokümantasyonu-ve-endpointler)
- [Sıkça Karşılaşılan Sorunlar (Troubleshooting)](#-sıkça-karşılaşılan-sorunlar-troubleshooting)
- [Lisans](#-lisans)

---

## 🚀 Öne Çıkan Özellikler

- 📸 **Şablonlu Akıllı Kamera**: Kamera açıkken arka planda çalışan CNN (MobileNetV2) modeli ile aracın doğru açıda ve kadrajda olduğunu canlı olarak doğrular.
- 🛞 **2B Jant Giydirme**: Özel eğitilmiş YOLOv8-seg modeli ile tekerleklerin bulunması, elips tespiti, perspektif homografi (warp perspective), renk eşleme ve aydınlatma uyarlaması ile gerçekçi jant montajı.
- 🎨 **2B Kaporta Boyama**: Segment Anything Model (SAM) ile tekerlekler, camlar ve plastik aksamlar hariç tutularak araç kaportasının LAB renk uzayında doğal yansımalar korunarak boyanması.
- 🧊 **Lokal 3B Rekonstrüksiyon**: Meta SAM + Depth Anything 3 ile çoklu açılardan derinlik çıkarımı, Open3D ile point cloud filtreleme ve Poisson yüzey örme pipeline'ı ile `.glb` 3D model üretimi.
- ☁️ **Tripo3D Bulut Entegrasyonu**: Metinden/görselden 3D üretim ve tamamlanmış modellere yapay zekâ tekstürleme giydirme yeteneği.
- 📱 **Etkileşimli 3D Mobil Stüdyo**: Flutter `model_viewer_plus` ile 360° döndürülebilir, yakınlaştırılabilir 3D GLB inceleme, topluluk keşfet akışı, garaj ve taslak yönetimi.

---

## 🏗 Sistem Mimarisi

```mermaid
flowchart TD
    subgraph Client["Mobil Uygulama (Flutter)"]
        UI["Arayüz & Şablonlu Kamera"]
        Viewer["3D GLB Görüntüleyici"]
        Store["Kredi & Mağaza"]
    end

    subgraph Backend["Backend API (FastAPI + SQLAlchemy)"]
        Auth["JWT & Kullanıcı Yönetimi"]
        Scans["Tarama & Upload Kuyruğu"]
        Mods["Modifikasyon Router"]
        TripoService["Tripo3D API Servisi"]
        CarDetAPI["Canlı Araç Tespit API"]
        DB[(PostgreSQL)]
    end

    subgraph AIWorkers["Yapay Zeka Servisleri (Worker)"]
        WorkerLocal["3dservis/servis.py\n(Depth Anything 3 + SAM + YOLOv8)"]
        WorkerCloud["3dservis/tripo_worker.py\n(Tripo3D Cloud AI)"]
        CNN["CNN_Otonom_Arac_Tespiti\n(MobileNetV2 Model)"]
    end

    UI -->|"Kamera Doğrulama (1.8s)"| CarDetAPI
    CarDetAPI --> CNN
    UI -->|"Fotoğraf Yükleme (2D / 3D)"| Scans
    UI -->|"Modifikasyon Seçimi (Jant / Renk)"| Mods
    Scans --> DB
    Mods --> DB

    WorkerLocal -->|"Kuyruk Dinleme (pending_2d / pending_3d)"| Scans
    WorkerLocal -->|"Sonuç Yükleme (GLB / Görsel)"| Scans
    TripoService -.->|"Bulut Texturing"| WorkerCloud
    Viewer -->|"GLB Modeli İndir & Oynat"| Scans
```

---

## 📂 Proje Yapısı

```
MODIFIAI/
├── Backend/                    # Backend API Sunucusu (FastAPI)
│   ├── app/
│   │   ├── main.py                 # FastAPI ana uygulama & CORS
│   │   ├── core/                   # JWT & bcrypt güvenlik ayarları
│   │   ├── api/routers/            # API uç noktaları (scans, modifications, plugins, user...)
│   │   ├── database/models/        # SQLAlchemy veritabanı modelleri
│   │   ├── database/schemas/       # Pydantic istek & yanıt şemaları
│   │   └── services/               # CNN araç tespit & Tripo3D servisleri
│   ├── alembic/                    # DB migration versiyonları
│   ├── requirements.txt            # Backend bağımlılıkları
│   └── .env                        # Backend ortam değişkenleri
│
├── Frontend/                   # Mobil Uygulama (Flutter)
│   └── lib/
│       ├── main.dart                   # Uygulama giriş noktası
│       ├── config.dart                 # Merkezi Backend URL ve timeout konfigürasyonu
│       ├── render_state.dart           # Global render takip & polling yöneticisi
│       ├── sayfalar/                   # Şablonlu kamera & 3D model görüntüleyici
│       ├── sayfalar_islem.dart         # Proje tipi, upload ve jant/renk seçim sayfaları
│       ├── sekme_*.dart                # Anasayfa, Keşfet, Garaj, Mağaza, Profil sekmeleri
│       ├── servisler/                  # HTTP API ve Auth servisleri
│       └── modeller/                   # Scan, Plugin, User veri modelleri
│
├── 3dservis/                   # AI Servisleri (Görüntü İşleme & 3D)
│   ├── servis.py                       # Ana lokal worker servisi (2D & 3D kuyruk dinleyici)
│   ├── car_modification.py             # YOLOv8 jant giydirme & renk entegrasyonu
│   ├── color_change.py                 # SAM + LAB kaporta boyama motoru
│   ├── test5.py                        # Depth Anything 3 + SAM + Open3D pipeline'ı
│   ├── tripo_worker.py                 # Alternatif bulut Tripo3D worker'ı
│   ├── config.py                       # Dinamik model ve klasör yol yapılandırması
│   ├── SAM/                            # Meta SAM vit-h ağırlık dosyası
│   └── Depth-Anything-3/               # DA3 derinlik modeli kaynak kodları
│
├── CNN_Otonom_Arac_Tespiti/     # Canlı Araç Tespiti
│   ├── araba_modeli_guclu_v2.keras     # Eğitilmiş MobileNetV2 modeli
│   └── main.py                         # Stanford Cars eğitim scripti
│
├── requirements.txt             # Kapsamlı Python bağımlılıkları
└── README.md                    # Proje dokümantasyonu
```

---

## ⚙️ Gereksinimler ve Model Dosyaları

- **İşletim Sistemi**: Windows 10/11, Linux veya macOS
- **Python**: 3.10 – 3.12 (3.12 önerilir)
- **Flutter**: 3.x (Dart SDK 3.11+)
- **PostgreSQL**: 14+
- **GPU**: CUDA destekli NVIDIA ekran kartı (AI worker için önerilir, CPU desteklenir)

### Model Dosyaları Tablosu

| Model | Konum | Boyut | İndirme / Kaynak |
|---|---|---|---|
| **SAM (ViT-H)** | `3dservis/SAM/sam_vit_h_4b8939.pth` | ~2.5 GB | [Meta Segment Anything](https://github.com/facebookresearch/segment-anything) |
| **YOLOv8 Car Parts** | `3dservis/runs/segment/train4/weights/best.pt` | ~55 MB | Proje reposunda eğitilmiş hazır model |
| **Depth Anything V3** | Otomatik İndirilir (`hf_cache/`) | ~1.4 GB | HuggingFace `depth-anything/DA3-LARGE` |
| **MobileNetV2 Araç Tespit** | `CNN_Otonom_Arac_Tespiti/araba_modeli_guclu_v2.keras` | ~29 MB | Stanford Cars ile eğitilmiş hazır model |

---

## 🛠 Kurulum ve Çalıştırma

Projeyi çalıştırmak için 3 ayrı terminal penceresi açın:

### 1. Backend Servisi (FastAPI)

1. PostgreSQL servisini başlatın ve bir veritabanı oluşturun:
   ```sql
   CREATE DATABASE modifai;
   ```
2. Backend dizinine girin:
   ```bash
   cd Backend
   ```
3. Sanal ortam oluşturup aktifleştirin:
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate
   ```
4. Bağımlılıkları kurun:
   ```bash
   pip install -r requirements.txt
   ```
5. `.env` dosyanızı yapılandırın (`.env.example` dosyasını kopyalayabilirsiniz):
   ```env
   DB_URL="postgresql+asyncpg://postgres:SIFRE@localhost:5432/modifai"
   MY_TOKEN="super_secret_jwt_key_123"
   ADMIN_API_KEY="ABCDEFGHIJKLMNOPRSTUVYZ123"
   ENVIRONMENT="development"
   BACKEND_PUBLIC_URL="http://localhost:8000"
   TRIPO_API_KEY="tsk_..."
   TRIPO_MODE="test"
   ```
6. Veritabanı tablolarını migrate edin:
   ```bash
   alembic upgrade head
   ```
7. Sunucuyu başlatın:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   > 🌐 Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### 2. AI Worker Servisi (3dservis)

Worker servisi backend kuyruklarını dinler, 2B/3B işlemleri sırayla işleyip sonucu backend'e aktarır.

1. Yeni bir terminal açıp `3dservis` dizinine girin:
   ```bash
   cd 3dservis
   ```
2. Sanal ortamı aktifleştirin ve paketleri yükleyin:
   ```bash
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. `3dservis/.env` dosyasını kontrol edin:
   ```env
   BACKEND_URL="http://localhost:8000"
   ADMIN_API_KEY="ABCDEFGHIJKLMNOPRSTUVYZ123"
   TRIPO_POLL_INTERVAL="5"
   ```
4. **Lokal AI Servisini Başlatın**:
   ```bash
   python servis.py
   ```
   *(Opsiyonel: Eğer yerel ekran kartı yerine Tripo3D bulut motorunu kullanmak isterseniz `python tripo_worker.py` çalıştırabilirsiniz).*

---

### 3. Mobil Uygulama (Flutter)

1. `Frontend/lib/config.dart` dosyasını açıp IP adresini ayarlayın:
   - **Android Emülatör**: `static const String baseUrl = "http://10.0.2.2:8000";`
   - **iOS Simülatör**: `static const String baseUrl = "http://localhost:8000";`
   - **Fiziksel Cihaz**: Bilgisayarınızın yerel Wi-Fi IP adresi (örn: `http://192.168.1.50:8000`)
2. Yeni bir terminal açıp Flutter dizinine girin:
   ```bash
   cd Frontend
   ```
3. Paketleri çekin ve çalıştırın:
   ```bash
   flutter pub get
   flutter run
   ```

---

### 4. CNN Araç Tespiti (Opsiyonel)

Eğer araç tespit modelini Stanford Cars veri setiyle sıfırdan yeniden eğitmek isterseniz:
```bash
cd CNN_Otonom_Arac_Tespiti
python -m venv venv
.\venv\Scripts\activate
pip install tensorflow pandas matplotlib scipy Pillow
python main.py
```

---

## 🔒 Ortam Değişkenleri (.env)

### `Backend/.env`
| Değişken | Açıklama | Örnek Değer |
|---|---|---|
| `DB_URL` | PostgreSQL async bağlantı dizesi | `postgresql+asyncpg://postgres:SIFRE@localhost:5432/modifai` |
| `MY_TOKEN` | JWT imzalama anahtarı | `super_secret_jwt_key` |
| `ADMIN_API_KEY` | Worker servisleri için güvenlik anahtarı | `ABCDEFGHIJKLMNOPRSTUVYZ123` |
| `ENVIRONMENT` | Çalışma modu | `development` / `production` |
| `BACKEND_PUBLIC_URL` | Dışarıya açık backend adresi | `http://localhost:8000` |
| `TRIPO_API_KEY` | Tripo3D AI API Anahtarı | `tsk_...` |
| `TRIPO_MODE` | Tripo çalışma modu | `test` / `live` |

### `3dservis/.env`
| Değişken | Açıklama | Örnek Değer |
|---|---|---|
| `BACKEND_URL` | Worker'ın erişeceği backend URL'i | `http://localhost:8000` |
| `ADMIN_API_KEY` | Backend ile eşleşen admin anahtarı | `ABCDEFGHIJKLMNOPRSTUVYZ123` |
| `TRIPO_POLL_INTERVAL` | Kuyruk tarama sıklığı (saniye) | `5` |

---

## 📡 API Dokümantasyonu ve Endpointler

Tüm endpoint'ler `/docs` adresinde Swagger UI ile interaktif olarak test edilebilir:

- **Kullanıcı İşlemleri (`/users`)**:
  - `POST /users/register`: Yeni kullanıcı kaydı (Otomatik 100 Hoş Geldin Kredisi hediye edilir).
  - `POST /users/login`: OAuth2 şifre akışı ile JWT Bearer token alma.
  - `GET /users/me`: Profil ve kullanıcı istatistikleri.
- **Taramalar ve Kuyruk (`/scans`)**:
  - `POST /scans/upload_image`: Fotoğraf yükleme (2D için 1 adet, 3D için 4 adet).
  - `POST /scans/detect_car`: Canlı kamera karelerinde araç varlık doğrulaması.
  - `GET /scans/garage`: Kullanıcının tamamlanmış veya taslak projeleri.
  - `GET /scans/pending_2d` & `GET /scans/pending_3d`: AI worker için bekleyen işler kuyruğu.
  - `POST /scans/complete/2d/{id}` & `PUT /scans/complete/3d/{id}`: İşlenen sonucun yüklenmesi.
- **Modifikasyonlar (`/modifications`)**:
  - `GET /modifications/costs`: Jant ve renk işlem kredi maliyetleri.
  - `POST /modifications`: Araca jant/boya modifikasyonu uygulama.
  - `GET /modifications/drafts`: Kullanıcının devam eden taslak projeleri.
- **Eklentiler (`/plugins`)**:
  - `GET /plugins/jants`: Kategorilerine göre jant kataloğu (sport, classic, suv).
  - `GET /plugins/colors`: Boya renk kataloğu ve HEX kodları.
- **Topluluk (`/community`)**:
  - `GET /community/feed`: Paylaşılan araçlar, beğeni ve yorum akışı.
- **Mağaza (`/store`)**:
  - `GET /store/packages`: Kredi ve haftalık sınırsız paketleri.
  - `POST /store/purchase/{package_id}`: Kredi yükleme.

---

## ❓ Sıkça Karşılaşılan Sorunlar (Troubleshooting)

1. **Flutter'da "Sunucuya ulaşılamadı" veya "Connection refused" Hatası**:
   - `config.dart` dosyasındaki `baseUrl` adresini kontrol edin. Android emülatörde `localhost` çalışmaz, mutlaka `http://10.0.2.2:8000` kullanmalısınız.
2. **CUDA / Ekran Kartı Bellek Hatası (Out of Memory - OOM)**:
   - SAM ViT-H modeli ~2.5 GB bellek kullanır. Yetersiz VRAM durumunda `car_modification.py` ve `test5.py` dosyalarında `device = "cpu"` olarak ayarlayabilirsiniz.
3. **Kredi Yetersiz Hatası (HTTP 402)**:
   - Yeni kaydolan kullanıcılara otomatik 100 kredi verilir. Krediniz biterse Mağaza (`/store`) sekmesinden paket seçerek bakiye yükleyebilirsiniz.
4. **3D Model Mobilde Görünmüyor**:
   - Backend `main.py` içinde GLB MIME tipi (`model/gltf-binary`) ve CORS ayarlarının açık olduğundan emin olun. Dosya yolu `/uploads/images_3d/scan_X/model_Y.glb` formatında erişilebilir olmalıdır.

---

## 📄 Lisans

Bu proje **MIT Lisansı** altında lisanslanmıştır. Detaylar için [LICENSE](file:///d:/MODIFIAI/LICENSE) dosyasına göz atabilirsiniz.

Copyright (c) 2026 **Emirhan Kar & Furkan Genç & Tevfik Üner**

---

<div align="center">
  <sub>MODIF-AI Ekibi tarafından geliştirilmiştir.</sub>
</div>
