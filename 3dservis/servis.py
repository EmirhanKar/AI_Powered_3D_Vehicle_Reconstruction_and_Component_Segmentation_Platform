import os
import time
import requests
import logging

from car_modification import process_scan
import sys
sys.path.insert(0, r'D:\MODIFIAI\3dservis\Depth-Anything-3\src')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger("modifai_servis")

BACKEND_URL = "http://10.204.181.194:8000"
ADMIN_KEY   = "ABCDEFGHIJKLMNOPRSTUVYZ123"
BEKLEME_SN  = 5

# Lazy loaded 3D models
_da3_model_tuple = None   # (model, device) tuple olarak saklanır
_sam_predictor   = None

SAM_CHECKPOINT = r"D:\MODIFIAI\3dservis\SAM\sam_vit_h_4b8939.pth"

def get_3d_models():
    global _da3_model_tuple, _sam_predictor
    if _da3_model_tuple is None or _sam_predictor is None:
        log.info("3D modelleri belleğe yükleniyor, lütfen bekleyin...")
        from test5 import load_da3_model, load_sam_model
        _da3_model_tuple = load_da3_model()
        _sam_predictor   = load_sam_model(SAM_CHECKPOINT)
        log.info("3D modelleri başarıyla yüklendi.")
    return _da3_model_tuple, _sam_predictor

def bekleyen_isleri_getir(endpoint):
    try:
        r = requests.get(
            f"{BACKEND_URL}/scans/{endpoint}",
            headers={"X-Admin-Key": ADMIN_KEY},
            timeout=10
        )
        if r.status_code == 200:
            return r.json()
        log.warning(f"Backend {r.status_code} döndü ({endpoint})")
        return []
    except Exception as e:
        log.error(f"Backend bağlantı hatası ({endpoint}): {e}")
        return []

def glb_yukle(scan_id, glb_path):
    """
    GLB veya GLTF dosyasını backend'e yükler.
    İçerik tipi otomatik belirlenir.
    """
    ext = os.path.splitext(glb_path)[1].lower()
    content_type = "model/gltf-binary" if ext == ".glb" else "model/gltf+json"

    if not os.path.exists(glb_path):
        log.error(f"Scan {scan_id}: Yüklenecek dosya bulunamadı → {glb_path}")
        return False

    file_size_mb = os.path.getsize(glb_path) / (1024 * 1024)
    log.info(f"Scan {scan_id}: Yükleniyor ({file_size_mb:.1f} MB) → {glb_path}")

    try:
        with open(glb_path, "rb") as f:
            r = requests.post(
                f"{BACKEND_URL}/scans/complete/3d/{scan_id}",
                files={"model_file": (os.path.basename(glb_path), f, content_type)},
                headers={"X-Admin-Key": ADMIN_KEY},
                timeout=300   # Büyük dosyalar için 5 dk timeout
            )
        r.raise_for_status()
        log.info(f"Scan {scan_id}: 3D model backend'e yüklendi ✓ ({r.status_code})")
        return True
    except requests.exceptions.Timeout:
        log.error(f"Scan {scan_id}: Yükleme zaman aşımına uğradı (dosya çok büyük olabilir)")
        return False
    except requests.exceptions.HTTPError as e:
        log.error(f"Scan {scan_id}: HTTP hatası — {e.response.status_code}: {e.response.text[:200]}")
        return False
    except Exception as e:
        log.error(f"Scan {scan_id}: Yükleme hatası — {e}")
        return False

def main():
    log.info(f"=== ModifAI Servis Başladı === Backend: {BACKEND_URL}")
    islenen = set()

    while True:
        try:
            bekleyenler_2d = bekleyen_isleri_getir("pending_2d")
            bekleyenler_3d = bekleyen_isleri_getir("pending_3d")
            bekleyenler = bekleyenler_2d + bekleyenler_3d

            if bekleyenler:
                log.info(f"{len(bekleyenler_2d)} 2D iş, {len(bekleyenler_3d)} 3D iş bulundu.")

            for scan in bekleyenler:
                scan_id = scan["scan_id"]
                method  = scan.get("method", "2d")

                if scan_id in islenen:
                    continue

                islenen.add(scan_id)
                try:
                    out_dir = process_scan(scan)

                    if method == "3d" and out_dir:
                        log.info(f"Scan {scan_id}: 3D mesh çıkarma işlemi başlıyor...")

                        da3_model_tuple, sam_predictor = get_3d_models()
                        final_3d_dir = os.path.join("temp_3d_output", str(scan_id))
                        os.makedirs(final_3d_dir, exist_ok=True)

                        from test5 import generate_3d_model
                        # generate_3d_model artık garantili path veya None döndürüyor
                        glb_path = generate_3d_model(
                            out_dir,
                            final_3d_dir,
                            sam_predictor,
                            da3_model_tuple   # (model, device) tuple
                        )

                        if glb_path and os.path.exists(glb_path):
                            basari = glb_yukle(scan_id, glb_path)
                            if not basari:
                                log.error(f"Scan {scan_id}: Backend yükleme başarısız, scan işlenmemiş sayılacak.")
                                islenen.discard(scan_id)
                        else:
                            log.error(f"Scan {scan_id}: 3D model dosyası üretilemedi, scan yeniden denenebilir.")
                            islenen.discard(scan_id)

                except Exception as e:
                    log.error(f"Scan {scan_id} hatası: {e}", exc_info=True)
                    islenen.discard(scan_id)

        except KeyboardInterrupt:
            log.info("Servis durduruluyor...")
            break
        except Exception as e:
            log.error(f"Beklenmeyen hata: {e}", exc_info=True)

        time.sleep(BEKLEME_SN)

if __name__ == "__main__":
    main()