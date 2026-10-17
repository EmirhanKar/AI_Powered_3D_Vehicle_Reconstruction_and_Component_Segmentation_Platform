"""
tripo_worker.py
───────────────
Tripo3D AI ile 3D model üretim worker'ı.

Backend'den pending_3d taramaları çeker ve Tripo3D API ile işler.

Çalıştırmak için:
    python tripo_worker.py

Ortam değişkenleri (.env veya sistem):
    TRIPO_API_KEY      = tsk_your_api_key
    TRIPO_MODE         = live | test
    BACKEND_URL        = http://localhost:8000
    BACKEND_PUBLIC_URL = http://your-domain.com:8000  (Tripo3D'nin erişebileceği URL)
"""

import os
import sys
import time
import asyncio
import logging
import requests
from pathlib import Path
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Üst dizindeki backend modüllerine erişim
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Backend"))

from app.services.tripo_service import (  # pyrefly: ignore [missing-import]
    TripoService,
    TripoAPIError,
    TaskStatus,
    TRIPO_MODE,
)

# ─── AYARLAR ──────────────────────────────────────────────────────
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
BACKEND_PUBLIC_URL = os.getenv("BACKEND_PUBLIC_URL", BACKEND_URL)
ADMIN_KEY = os.getenv("ADMIN_API_KEY", "ABCDEFGHIJKLMNOPRSTUVYZ123")
POLL_INTERVAL = int(os.getenv("TRIPO_POLL_INTERVAL", "10"))  # saniye

# ─── LOGGING ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("tripo_worker")


def get_pending_scans(endpoint: str) -> list:
    """Backend'den bekleyen taramaları çeker."""
    try:
        r = requests.get(
            f"{BACKEND_URL}/scans/{endpoint}",
            headers={"X-Admin-Key": ADMIN_KEY},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
        log.warning(f"Backend {r.status_code} döndü ({endpoint})")
        return []
    except Exception as e:
        log.error(f"Backend bağlantı hatası ({endpoint}): {e}")
        return []


def upload_glb(scan_id: int, glb_path: str) -> bool:
    """Üretilen GLB dosyasını backend'e yükler."""
    if not os.path.exists(glb_path):
        log.error(f"Scan {scan_id}: Dosya bulunamadı → {glb_path}")
        return False

    file_size_mb = os.path.getsize(glb_path) / (1024 * 1024)
    log.info(f"Scan {scan_id}: Yükleniyor ({file_size_mb:.1f} MB)")

    try:
        with open(glb_path, "rb") as f:
            r = requests.post(
                f"{BACKEND_URL}/scans/complete/3d/{scan_id}",
                data=f,
                headers={
                    "X-Admin-Key": ADMIN_KEY,
                    "Content-Type": "application/octet-stream"
                },
                timeout=300,
            )
        r.raise_for_status()
        log.info(f"Scan {scan_id}: 3D model yüklendi ✓")
        return True
    except Exception as e:
        log.error(f"Scan {scan_id}: Yükleme hatası — {e}")
        return False


def get_image_urls(scan: dict) -> list[str]:
    """Scan'den public erişilebilir fotoğraf URL'lerini çıkarır."""
    urls = []
    images = scan.get("images", [])

    for img in images:
        url = img.get("image_url", "")
        if not url:
            continue

        # Göreli yolları public URL'ye çevir
        if not url.startswith("http"):
            url = f"{BACKEND_PUBLIC_URL}/{url.replace(chr(92), '/')}"

        urls.append(url)

    return urls


async def process_scan_with_tripo(tripo: TripoService, scan: dict) -> bool:
    """
    Tek bir scan'i Tripo3D AI ile işler:
    1. Görselleri yerel yoldan Tripo'ya doğrudan yükler (Token alır)
    2. Tripo3D API'ye gönderir (image_to_model / multiview_to_model)
    3. Tamamlanmasını bekler
    4. GLB dosyasını indirir (hemen, URL expire olmadan!)
    5. Backend'e yükler
    """
    scan_id = scan.get("scan_id")
    images = scan.get("images", [])

    log.info(f"\n{'─'*50}")
    log.info(f"Scan #{scan_id} işleniyor ({len(images)} fotoğraf)")
    log.info(f"{'─'*50}")

    if not images:
        log.warning(f"Scan {scan_id}: Fotoğraf bulunamadı, atlanıyor.")
        return False

    try:
        # Görselleri Tripo'ya yükle (Yerel dosya varsa doğrudan yükle, yoksa public URL kullan)
        file_tokens = []
        image_urls = []
        
        # Tripo multiview task accepts up to 4 images
        images_to_process = images[:4] if len(images) > 1 else [images[0]]
        
        for img in images_to_process:
            img_path = img.get("image_url", "")
            local_path = ""
            
            if img_path and not img_path.startswith("http"):
                # Yol çözümlemesi
                if os.path.exists(img_path):
                    local_path = img_path
                else:
                    backend_rel_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "Backend", img_path))
                    if os.path.exists(backend_rel_path):
                        local_path = backend_rel_path
                        
            if local_path:
                log.info(f"Scan {scan_id}: Görsel Tripo'ya yükleniyor → {os.path.basename(local_path)}")
                try:
                    token = await tripo.upload_image(local_path)
                    file_tokens.append(token)
                except Exception as upload_err:
                    log.warning(f"Görsel yüklenemedi, URL kullanılacak: {upload_err}")
                    # URL fallback
                    url = img_path
                    if not url.startswith("http"):
                        url = f"{BACKEND_PUBLIC_URL}/{url.replace(chr(92), '/')}"
                    image_urls.append(url)
            else:
                # URL fallback
                url = img_path
                if url and not url.startswith("http"):
                    url = f"{BACKEND_PUBLIC_URL}/{url.replace(chr(92), '/')}"
                if url:
                    image_urls.append(url)

        # Task oluştur
        if len(images) > 1:
            log.info(f"Scan {scan_id}: Multi-Image-to-3D → {len(images_to_process)} görsel (maks 4)")
            if file_tokens:
                task_id = await tripo.multi_image_to_3d(file_tokens=file_tokens)
            else:
                task_id = await tripo.multi_image_to_3d(image_urls=image_urls)
        else:
            log.info(f"Scan {scan_id}: Image-to-3D → tek görsel")
            if file_tokens:
                task_id = await tripo.image_to_3d(file_token=file_tokens[0])
            else:
                task_id = await tripo.image_to_3d(image_url=image_urls[0])

        log.info(f"Scan {scan_id}: Task oluşturuldu → {task_id}")

        # İlerleme callback'i
        async def on_progress(tid, progress, status):
            log.info(f"Scan {scan_id}: %{progress} ({status.value})")

        # Task'ın tamamlanmasını bekle
        result = await tripo.wait_for_task(
            task_id=task_id,
            poll_interval=5.0,
            max_wait=600.0,
            progress_callback=on_progress,
        )

        if result.status != TaskStatus.SUCCESS:
            log.error(f"Scan {scan_id}: Task başarısız — {result.error}")
            return False

        # Model URL'ini al (hemen indirmek lazım, ~5dk expire!)
        model_url = result.model_url
        if not model_url:
            log.error(f"Scan {scan_id}: Model URL bulunamadı!")
            return False

        # Geçici dizine indir
        temp_dir = os.path.join("temp_tripo_output", str(scan_id))
        os.makedirs(temp_dir, exist_ok=True)
        glb_path = os.path.join(temp_dir, f"tripo_model_{scan_id}.glb")

        await tripo.download_model(model_url, glb_path)

        # Backend'e yükle
        success = upload_glb(scan_id, glb_path)

        # Geçici dosyayı temizle
        if success:
            try:
                os.remove(glb_path)
                os.rmdir(temp_dir)
            except OSError:
                pass

        return success

    except TripoAPIError as e:
        log.error(f"Scan {scan_id}: Tripo3D API hatası — {e}")
        return False
    except Exception as e:
        log.error(f"Scan {scan_id}: Beklenmeyen hata — {e}", exc_info=True)
        return False


async def worker_loop():
    """Ana worker döngüsü."""
    is_test = TRIPO_MODE == "test"

    log.info("=" * 55)
    log.info("  🚗 MODIF-AI × Tripo3D AI Worker")
    log.info(f"  Backend     : {BACKEND_URL}")
    log.info(f"  Public URL  : {BACKEND_PUBLIC_URL}")
    log.info(f"  Tripo Mode  : {'🧪 TEST' if is_test else '🔴 LIVE'}")
    log.info(f"  Poll        : {POLL_INTERVAL}sn")
    log.info("=" * 55)

    if is_test:
        log.warning(
            "⚠️  TEST modunda çalışıyorsunuz. Gerçek 3D model üretilmeyecek.\n"
            "    Production için TRIPO_MODE=live ve gerçek TRIPO_API_KEY ayarlayın."
        )

    processed_ids: set[int] = set()

    async with TripoService() as tripo:
        # Başlangıçta bağlantı kontrolü
        health = await tripo.health_check()
        log.info(f"Tripo3D AI Durum: {health['message']}")

        while True:
            try:
                # Sadece 3D pending taramaları çek
                pending = get_pending_scans("pending_3d")

                if pending:
                    log.info(f"📋 {len(pending)} bekleyen 3D tarama bulundu")

                for scan in pending:
                    scan_id = scan.get("scan_id")
                    if scan_id in processed_ids:
                        continue

                    processed_ids.add(scan_id)
                    success = await process_scan_with_tripo(tripo, scan)

                    if not success:
                        # Başarısız olanları tekrar deneme havuzuna at
                        processed_ids.discard(scan_id)
                        log.warning(f"Scan {scan_id}: Başarısız, tekrar denenecek.")

                if not pending:
                    log.debug("Bekleyen tarama yok.")

            except KeyboardInterrupt:
                log.info("🛑 Worker durduruluyor...")
                break
            except Exception as e:
                log.error(f"Beklenmeyen hata: {e}", exc_info=True)

            await asyncio.sleep(POLL_INTERVAL)


def main():
    """Worker'ı başlat."""
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        log.info("Worker sonlandırıldı.")


if __name__ == "__main__":
    main()
