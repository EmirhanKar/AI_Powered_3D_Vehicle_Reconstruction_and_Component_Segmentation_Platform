# ModifAI 3D Rekonstrüksiyon Servisi (`3Dservice/`)

Bu servis, normal perspektif bir araç videosunu veya **360° equirectangular** (Insta360 / GoPro Max vb.) bir araç videosunu alıp 10 izole adımda temizlenmiş, zemin düzlemine (`y=0`) oturtulmuş, `+Z` eksenine hizalanmış ve çoklu açıdan dokusu fırınlanmış (baked) **glTF 2.0 Binary (`.glb`)** modeline dönüştürür.

---

## 1. Mimari ve Klasör Yapısı

Her adım kendi dosyasındadır (`step_00` .. `step_09`), yalnızca önceki adımların ürettiği beyan edilmiş (`requires`) artefaktları okur ve yalnızca kendi iş klasörüne (`jobs/<job_id>/<NN_stepname>/`) yazar.

```text
3Dservice/
  service.py                  # FastAPI sunucusu + tekil GPU iş kuyruğu (JobRunner)
  backend_poller.py           # Mevcut Backend (/scans/pending_3d) için opsiyonel kuyruk tarayıcısı
  config.py                   # .env yükleyici ve başlangıç doğrulayıcısı (startup validation)
  requirements.txt            # Sabitlenmiş (pinned) Python paket sürümleri
  .env.example                # Örnek yapılandırma şablonu
  README.md                   # Kurulum ve kullanım kılavuzu
  ASSUMPTIONS.md              # Backend entegrasyonu ve mimari varsayımlar
  pipeline/
    base.py                   # Step soyut sınıfı, StepResult, PipelineContext
    errors.py                 # StepError(step, code, message, hint, details)
    orchestrator.py           # Adım yürütücüsü, state.json yönetimi, resume/rerun
    cli.py                    # Tekil adım veya aralık çalıştırma CLI aracı
    utils/                    # FFmpeg, subprocess (timeout + stderr tail), GPU kontrolü, S3/Local depolama
    step_00_validate_input.py # Video boyut/süre/çözünürlük ve 360° tespiti
    step_01_extract_frames.py # Kare çıkarma, Laplacian bulanıklık elemesi, paralaks seçimi
    step_02_reproject_360.py  # 360° ise sanal perspektif kameralara bölme; değilse skipped
    step_03_segment_car.py    # SAM 2 video araç maskeleme + hata ayıklama önizlemesi
    step_04_estimate_poses.py # COLMAP poz tahmini + kayıt oranı kalite kapısı
    step_05_reconstruct.py    # Nerfstudio (splatfacto / 2dgs) eğitimi ve PSNR/LPIPS hesabı
    step_06_extract_mesh.py   # TSDF/Poisson mesh, RANSAC zemin kesimi, PCA hizalama, y=0 tekerlek tabanı
    step_07_texture.py        # xatlas UV açma ve çoklu açıdan doku fırınlama (baking)
    step_08_quality_check.py  # Kalite raporu (pass/warn/fail) ve Türkçe yeniden çekim ipucu
    step_09_export.py         # GLB (extras: meters_per_unit, scale_known, front_confidence) + USDZ dışa aktarım
```

---

## 2. Sistem Bağımlılıkları (FFmpeg, COLMAP, CUDA)

Üretim ortamında (`DEV_MOCK_MODE=false`) aşağıdaki sistem araçlarının kurulu ve `PATH` üzerinde (veya `.env` içinde tam yoluyla belirtilmiş) olması gerekir:

1. **NVIDIA GPU & CUDA Toolkit (11.8 veya 12.1+):**
   ```bash
   nvidia-smi
   nvcc --version
   ```
2. **FFmpeg & FFprobe:**
   - **Ubuntu/Debian:** `sudo apt-get update && sudo apt-get install -y ffmpeg`
   - **Windows (Winget):** `winget install Gyan.FFmpeg`
3. **COLMAP (CUDA destekli derleme önerilir):**
   - **Ubuntu/Debian:** `sudo apt-get install -y colmap`
   - **Windows:** [COLMAP Releases](https://github.com/colmap/colmap/releases) sayfasından `COLMAP-windows-cuda.zip` indirilip `.env` içindeki `COLMAP_BIN` değişkenine `colmap.bat` veya `colmap.exe` yolu verilir.
4. **SAM 2 ve Nerfstudio Kurulumu:**
   ```bash
   cd 3Dservice
   python -m venv .venv
   # Windows: .venv\Scripts\activate | Linux: source .venv/bin/activate
   pip install -r requirements.txt
   pip install git+https://github.com/facebookresearch/sam2.git
   pip install nerfstudio==1.1.4
   ```

---

## 3. Model Ağırlıklarının (Checkpoints) İndirilmesi

SAM 2 video segmentasyonu için ağırlık dosyasını `3Dservice/checkpoints/` dizinine indirin:

```bash
mkdir -p checkpoints
curl -L https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_large.pt -o checkpoints/sam2_hiera_large.pt
```

`.env` dosyanızda `SAM_CHECKPOINT_PATH=./checkpoints/sam2_hiera_large.pt` ve `SAM_MODEL_CFG=sam2_hiera_l.yaml` ayarlarının bulunduğundan emin olun.

---

## 4. Yapılandırma ve Sunucuyu Başlatma

`3Dservice` klasör adı rakamla başladığı için hiçbir zaman dışarıdan bir Python paketi olarak import edilmez; tüm komutlar **`3Dservice/` dizini içerisinden** çalıştırılır:

```bash
cd 3Dservice
cp .env.example .env
# Geliştirme/test ortamında GPU olmadan uçtan uca test için .env içinde DEV_MOCK_MODE=true yapabilirsiniz.
python service.py
# veya:
uvicorn service:app --host 0.0.0.0 --port 8001
```

### API Uç Noktaları (`X-Admin-Key: <API_KEY>` başlığı gerektirir):
- `GET /health`: FFmpeg, COLMAP, GPU/VRAM ve SAM 2 model ağırlıklarının durumunu döndürür.
- `POST /jobs`: Multipart `video` dosyası veya JSON `{"video_path": "..."}` ile yeni iş başlatır, hemen `job_id` döndürür.
- `GET /jobs/{job_id}`: İşin durumunu (`pending`, `running`, `done`, `failed`), çalışan adımı, başarısız olduysa `failed_step`, `error_code`, Türkçe `detail` ve `hint` alanlarını döndürür.
- `GET /jobs/{job_id}/result`: Kalite raporunu, GLB `extras` üstverisini ve model indirme bağlantısını döndürür (`?download=true` ile doğrudan `.glb` dosyasını indirir).

---

## 5. CLI ile Tek Bir Adımı veya Adım Aralığını Çalıştırma / Hata Ayıklama

Herhangi bir adım başarısız olduğunda önceki adımları tekrarlamadan yalnızca ilgili adımı tek başına çalıştırabilir ve `jobs/<job_id>/logs/step_NN.log` dosyasından çıktısını inceleyebilirsiniz:

```bash
cd 3Dservice

# 1. Yeni bir iş başlat ve tüm adımları (00 -> 09) çalıştır:
python -m pipeline.cli --job ornek_is_01 --video /path/to/arac_video.mp4

# 2. Yalnızca Adım 04'ü (estimate_poses) tek başına yeniden çalıştır:
#    (Sadece jobs/ornek_is_01/04_estimate_poses/ klasörü silinip yeniden oluşturulur)
python -m pipeline.cli --job ornek_is_01 --step 4

# 3. Adım 04'ten Adım 06'ya kadar (04, 05, 06) çalıştır:
python -m pipeline.cli --job ornek_is_01 --from 4 --to 6

# 4. Başarısız olmuş bir işi kaldığı adımdan devam ettir (tamamlanan adımları atlar):
python -m pipeline.cli --job ornek_is_01 --resume

# 5. GPU olmadan tüm boru hattını mock modunda uçtan uca test et:
python -m pipeline.cli --job mock_test_01 --video ./ornek.mp4 --mock
```
