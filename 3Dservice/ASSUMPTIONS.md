# ModifAI 3D Servisi (`3Dservice/`) — Mimari Varsayımlar ve Entegrasyon Kararları (`ASSUMPTIONS.md`)

Bu belge, mevcut `Backend/` kod tabanının incelenmesi sonucunda alınan mimari kararları, varsayımları ve ileride kolayca değiştirilebilmesi için izole edilen bileşenleri açıklar.

---

## 1. Mevcut Backend İletişim ve İş/Durum (Job & Status) Modeli

### Tespitler:
- Mevcut `Backend/` (`Backend/app/api/routers/upload_image_router.py`), dış bir 3D mikroservisine doğrudan senkron veya asenkron HTTP `POST` isteği **atmamaktadır**.
- Bunun yerine `Backend`, iş kuyruğunu veritabanında (`Scans` ve `Processed3D` tabloları) tutmakta ve şu uç noktaları sunmaktadır:
  - `GET /scans/pending_3d`: `Processed3D.model_url == None` olan bekleyen 3B taramaları listeler.
  - `PUT /scans/complete/3d/{scan_id}` (veya `POST`): Üretilen `.glb` dosyasını `multipart/form-data` yerine **raw binary (`application/octet-stream`)** gövde olarak kabul eder, `uploads/images_3d/scan_{scan_id}/model_{uuid}.glb` dizinine kaydeder ve tarama durumunu `completed` yapar.
- Ayrıca eski servis (`3dservis/servis.py`) incelendiğinde, ilerleme ve hata durumlarının `POST /scans/progress/{scan_id}` ve `POST /scans/fail/{scan_id}` uç noktalarına bildirildiği görülmüştür.

### Alınan Karar ve İzolasyon:
1. **Birleştirilmiş İş Koşturucusu (`JobRunner`):**
   - `3Dservice/service.py` içinde hem doğrudan REST API (`POST /jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/result`, `GET /health`) hem de `3Dservice/backend_poller.py` içindeki `BackendPoller` **tek bir `JobRunner` kuyruğunu** paylaşır. İki ayrı çalıştırma yolu yoktur.
2. **`ENABLE_BACKEND_POLLER` Varsayılan Değeri (`true`):**
   - Mevcut `Backend` kodunda hiçbir değişiklik yapılmaması (Hard Requirement #2) istendiği ve `Backend` halihazırda `pending_3d` kuyruğunun tüketilmesini beklediği için `.env.example` ve `config.py` içinde `ENABLE_BACKEND_POLLER=true` varsayılan olarak seçilmiştir.
   - Eğer ileride `Backend` doğrudan `POST /jobs` çağrısı yapacak şekilde güncellenirse, yalnızca `.env` içerisindeki `ENABLE_BACKEND_POLLER=false` yapılarak poller devre dışı bırakılabilir.
3. **Çift İşlemeyi Önleme ve Hata Bildirimi:**
   - `BackendPoller` bir işi aldığında hem bellekteki `claimed_scan_ids` kümesine ekler hem de hemen `POST /scans/progress/{scan_id}` ile `status="processing"` bildirir.
   - Herhangi bir adım başarısız olduğunda `POST /scans/fail/{scan_id}` uç noktasına `failed_step`, `error_code`, `detail` ve Türkçe `hint` gönderilir.
   - Bağlantı hatalarında ve GLB yüklemelerinde üssel geri çekilme (**exponential backoff**) uygulanır.

---

## 2. Kimlik Doğrulama (Authentication)

- Mevcut `Backend/app/api/deps.py` dosyasında dış servisler için `APIKeyHeader(name="X-Admin-Key")` ve `ADMIN_API_KEY` ortam değişkeni kullanılmaktadır.
- `3Dservice/service.py` bu standardı birebir yansıtır:
  - İsteklerde `X-Admin-Key: <API_KEY>` (veya geriye dönük uyumluluk için `X-API-Key: <API_KEY>`) başlığını arar.
  - Anahtar eksik veya hatalıysa Backend ile aynı HTTP kodu ve mesaj formatını (`HTTP 403 Forbidden`, `{"detail": "Geçersiz veya eksik Admin API Key."}`) döndürür.

---

## 3. 3B Koordinat Sistemi, Zemin Hizalama ve Ölçek (`extras`) Kararları

1. **glTF 2.0 Sağ-El Koordinat Sistemi:**
   - **+Y:** Yukarı (Up) — RANSAC ile bulunan zemin düzleminin normali.
   - **+Z:** Araç Önü (Forward) — X-Z düzleminde PCA ile bulunan ana uzun eksen.
   - **+X:** Araç Solu (Right-handed sistemde `X = Y × Z`).
2. **Zemin Referanslı Merkezleme (`y = 0.0`):**
   - Model kütle merkezine `(0, 0, 0)` **taşınmaz**. Yatayda `X=0` ve `Z=0` ortalanır, dikeyde ise tekerleklerin bastığı en alt nokta tam olarak **`y = 0.0`** düzlemine oturtulur. Böylece Flutter (`model_viewer_plus`) veya Three.js sahnesine eklendiğinde araç zeminin içine gömülmez veya havada asılı kalmaz.
3. **Ön/Arka Yönü Belirsizliği (`front_confidence`):**
   - PCA aracın boyuna eksenini yüksek doğrulukla bulur ancak 180° yön belirsizliği (ön mü `+Z`, arka mı `+Z`?) içerir.
   - `step_06_extract_mesh.py`, kaput ve kabin/tavan yükseklik profili asimetrisinden ön yönü tahmin eder ve `[0.15, 0.99]` aralığında bir `front_confidence` hesaplar.
   - Eğer araç simetrik bir profile sahipse ve `front_confidence < 0.55` çıkarsa, bu durum `step_06.log` içinde uyarılır ve `step_08_quality_check.py` tarafından `quality_report.json` içine `warn` olarak işlenir.
4. **Gerçek Ölçeğin Korunması (`GLB extras`):**
   - `.env` içinde `KNOWN_METERS_PER_UNIT > 0` verilmişse model birim küpe küçültülmez, doğrudan metre cinsinden dışa aktarılır (`scale_known = true`, `meters_per_unit = 1.0`).
   - Ölçek referansı bilinmiyorsa (`KNOWN_METERS_PER_UNIT = 0.0`), model birim boyuta normalize edilirken sahnenin tahmini metre karşılığı `meters_per_unit` olarak kaydedilir (`scale_known = false`).
   - `step_09_export.py`, üretilen `.glb` dosyasının JSON yığınına (`asset.extras` ve `scenes[0].extras`) `meters_per_unit`, `scale_known` ve `front_confidence` alanlarını ikili (binary) düzeyde gömer.

---

## 4. Girdi Bağımsızlığı (Input-Agnostic Steps 03..09)

- İleride tekli veya çoklu fotoğraf girdisi ekleneceği için video doğrulama (`step_00`), kare çıkarma (`step_01`) ve 360° yeniden izdüşüm (`step_02`) adımları tamamen ayrıştırılmıştır.
- `step_03_segment_car` ve sonraki hiçbir adım `input_video` veya `validated_video` artefaktına erişemez; yalnızca `frames_dir` ve `camera_info` tüketir. `PipelineContext.get_artifact()` metodu, bir adımın `requires` listesinde olmayan bir artefakta erişmesini çalışma zamanında (`UNDECLARED_ARTIFACT_ACCESS`) engeller.
