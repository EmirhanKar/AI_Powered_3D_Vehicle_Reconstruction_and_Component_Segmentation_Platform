"""
meshy_worker.py
───────────────
Meshy AI ile 3D model üretim worker'ı.

Mevcut servis.py ile paralel çalışır.
Backend'den pending_3d taramaları çeker ve Meshy AI API ile işler.

Çalıştırmak için:
    python meshy_worker.py

Ortam değişkenleri (.env veya sistem):
    MESHY_API_KEY     = msy_your_api_key
    MESHY_MODE        = live | test
    BACKEND_URL       = http://localhost:8000
    BACKEND_PUBLIC_URL = http://your-domain.com:8000  (Meshy'nin erişebileceği URL)
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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modif-ai-backend", "Backend"))

from app.services.meshy_service import (
    MeshyService,
    MeshyModel,
    MeshyAPIError,
    TaskStatus,
    MESHY_MODE,
)

# ─── AYARLAR ──────────────────────────────────────────────────────
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
BACKEND_PUBLIC_URL = os.getenv("BACKEND_PUBLIC_URL", BACKEND_URL)
ADMIN_KEY = os.getenv("ADMIN_API_KEY", "ABCDEFGHIJKLMNOPRSTUVYZ123")
POLL_INTERVAL = int(os.getenv("MESHY_POLL_INTERVAL", "10"))  # saniye
AI_MODEL = os.getenv("MESHY_AI_MODEL", "meshy-4")  # "meshy-4" veya "meshy-6"

# ─── LOGGING ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("meshy_worker")


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
                files={"model_file": (os.path.basename(glb_path), f, "model/gltf-binary")},
                headers={"X-Admin-Key": ADMIN_KEY},
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


async def process_scan_with_meshy(meshy: MeshyService, scan: dict) -> bool:
    """
    Tek bir scan'i Meshy AI ile işler:
    1. Fotoğraf URL'lerini çıkarır
    2. Meshy API'ye gönderir (single/multi image)
    3. Tamamlanmasını bekler
    4. GLB dosyasını indirir
    5. Backend'e yükler
    """
    scan_id = scan.get("scan_id")
    method = scan.get("method", "3d")
    image_urls = get_image_urls(scan)

    log.info(f"\n{'─'*50}")
    log.info(f"Scan #{scan_id} işleniyor ({len(image_urls)} fotoğraf)")
    log.info(f"{'─'*50}")

    if not image_urls:
        log.warning(f"Scan {scan_id}: Fotoğraf bulunamadı, atlanıyor.")
        return False

    try:
        model = MeshyModel.MESHY_6 if AI_MODEL == "meshy-6" else MeshyModel.MESHY_4

        # Birden fazla fotoğraf varsa multi-image, tek fotoğraf varsa single image
        if len(image_urls) > 1:
            log.info(f"Scan {scan_id}: Multi-Image-to-3D → {len(image_urls)} fotoğraf")
            task_id = await meshy.multi_image_to_3d(
                image_urls=image_urls,
                model=model,
                target_polycount=30000,
            )
            task_type = "multi-image-to-3d"
        else:
            log.info(f"Scan {scan_id}: Image-to-3D → tek fotoğraf")
            task_id = await meshy.image_to_3d(
                image_url=image_urls[0],
                model=model,
                target_polycount=30000,
            )
            task_type = "image-to-3d"

        log.info(f"Scan {scan_id}: Task oluşturuldu → {task_id}")

        # İlerleme callback'i
        async def on_progress(tid, progress, status):
            log.info(f"Scan {scan_id}: %{progress} ({status.value})")

        # Task'ın tamamlanmasını bekle
        result = await meshy.wait_for_task(
            task_id=task_id,
            task_type=task_type,
            poll_interval=5.0,
            max_wait=600.0,
            progress_callback=on_progress,
        )

        if result.status != TaskStatus.SUCCEEDED:
            log.error(f"Scan {scan_id}: Task başarısız — {result.error}")
            return False

        # GLB URL'ini al
        glb_url = result.model_urls.get("glb", "")
        if not glb_url:
            for fmt, url in result.model_urls.items():
                glb_url = url
                break

        if not glb_url:
            log.error(f"Scan {scan_id}: Model URL bulunamadı!")
            return False

        # Geçici dizine indir
        temp_dir = os.path.join("temp_meshy_output", str(scan_id))
        os.makedirs(temp_dir, exist_ok=True)
        glb_path = os.path.join(temp_dir, f"meshy_model_{scan_id}.glb")

        await meshy.download_model(glb_url, glb_path)

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

    except MeshyAPIError as e:
        log.error(f"Scan {scan_id}: Meshy API hatası — {e}")
        return False
    except Exception as e:
        log.error(f"Scan {scan_id}: Beklenmeyen hata — {e}", exc_info=True)
        return False


async def worker_loop():
    """Ana worker döngüsü."""
    is_test = MESHY_MODE == "test"

    log.info("=" * 55)
    log.info("  🚗 MODIF-AI × Meshy AI Worker")
    log.info(f"  Backend     : {BACKEND_URL}")
    log.info(f"  Public URL  : {BACKEND_PUBLIC_URL}")
    log.info(f"  Meshy Mode  : {'🧪 TEST' if is_test else '🔴 LIVE'}")
    log.info(f"  AI Model    : {AI_MODEL}")
    log.info(f"  Poll        : {POLL_INTERVAL}sn")
    log.info("=" * 55)

    if is_test:
        log.warning(
            "⚠️  TEST modunda çalışıyorsunuz. Gerçek 3D model üretilmeyecek.\n"
            "    Production için MESHY_MODE=live ve gerçek MESHY_API_KEY ayarlayın."
        )

    processed_ids: set[int] = set()

    async with MeshyService() as meshy:
        # Başlangıçta bağlantı kontrolü
        health = await meshy.health_check()
        log.info(f"Meshy AI Durum: {health['message']}")

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
                    success = await process_scan_with_meshy(meshy, scan)

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
