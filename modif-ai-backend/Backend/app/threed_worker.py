"""
threed_worker.py
────────────────
Bağımsız çalışan AI worker.
1. Backend'den pending_3d scan'leri çeker
2. Fotoğrafları indirir, TripoSR ile 3D model üretir
3. GLB'yi complete/3d/{scan_id} endpoint'ine yükler

Çalıştırmak için:
    pip install httpx Pillow gradio_client
    python threed_worker.py
"""

import asyncio
import httpx
import os
import time
import tempfile
from pathlib import Path

# ─── AYARLAR ──────────────────────────────────────────────────────────────────
BACKEND_URL = "http://192.168.1.33:8000"   # Kendi backend URL'in
POLL_INTERVAL = 30                          # Kaç saniyede bir kontrol (sn)
HF_TOKEN = os.getenv("HF_TOKEN", "")       # HuggingFace token (opsiyonel)
# ──────────────────────────────────────────────────────────────────────────────


async def fetch_pending_scans(client: httpx.AsyncClient) -> list:
    """Backend'den işlenmeyi bekleyen 3D scan'leri çeker."""
    try:
        r = await client.get(f"{BACKEND_URL}/scans/pending_3d", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[HATA] pending_3d çekilemedi: {e}")
        return []


async def download_image(client: httpx.AsyncClient, url: str, dest: Path) -> bool:
    """Tek bir fotoğrafı indirir."""
    try:
        if url.startswith("uploads/") or url.startswith("uploads\\"):
            url = f"{BACKEND_URL}/{url.replace(chr(92), '/')}"
        r = await client.get(url, timeout=30)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return True
    except Exception as e:
        print(f"  [HATA] Fotoğraf indirilemedi {url}: {e}")
        return False


def generate_3d_model(image_path: Path) -> bytes | None:
    """
    TripoSR Gradio API ile 3D model üretir.
    Adımlar: preprocess → generate → GLB bytes döner.
    """
    print(f"  → TripoSR API'ye gönderiliyor: {image_path.name}")
    try:
        from gradio_client import Client, handle_file

        kwargs = {}
        if HF_TOKEN:
            kwargs["hf_token"] = HF_TOKEN

        client = Client("stabilityai/TripoSR", **kwargs)

        # Adım 1: Arka plan kaldır / ön plan hazırla
        processed = client.predict(
            str(image_path),
            True,
            0.85,
            api_name="/preprocess"
        )
        print(f"  → Preprocess tamamlandı, 3D üretiliyor...")

        # Adım 2: 3D model üret
        result = client.predict(
            processed,
            256,
            api_name="/generate"
        )

        # result = (obj_path, glb_path)
        glb_path = result[1]
        glb_bytes = Path(glb_path).read_bytes()
        print(f"  ✓ 3D model üretildi ({len(glb_bytes) / 1024:.1f} KB)")
        return glb_bytes

    except Exception as e:
        print(f"  [HATA] 3D üretim başarısız: {e}")
        return None


async def upload_glb(client: httpx.AsyncClient, scan_id: int, glb_bytes: bytes) -> bool:
    """Üretilen GLB'yi backend'e yükler."""
    try:
        files = {"model_file": (f"model_{scan_id}.glb", glb_bytes, "model/gltf-binary")}
        r = await client.post(
            f"{BACKEND_URL}/scans/complete/3d/{scan_id}",
            files=files,
            timeout=60,
        )
        r.raise_for_status()
        print(f"  ✓ GLB yüklendi → scan_id={scan_id}")
        return True
    except Exception as e:
        print(f"  [HATA] GLB yüklenemedi scan_id={scan_id}: {e}")
        return False


async def process_scan(client: httpx.AsyncClient, scan: dict) -> None:
    """Tek bir scan'i işler."""
    scan_id = scan["scan_id"]
    images = scan.get("images", [])

    print(f"\n── Scan #{scan_id} işleniyor ({len(images)} fotoğraf) ──")

    if not images:
        print(f"  [ATLA] Fotoğraf yok.")
        return

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)

        # Fotoğrafları indir
        image_paths = []
        for i, img in enumerate(images):
            url = img.get("image_url", "")
            if not url:
                continue
            dest = tmp / f"photo_{i:02d}.jpg"
            success = await download_image(client, url, dest)
            if success:
                image_paths.append(dest)

        print(f"  {len(image_paths)}/{len(images)} fotoğraf indirildi")

        if not image_paths:
            print(f"  [ATLA] Hiç fotoğraf indirilemedi.")
            return

        # İlk fotoğrafla 3D üret (TripoSR tek görsel alıyor)
        glb_bytes = generate_3d_model(image_paths[0])

        if not glb_bytes:
            return

        await upload_glb(client, scan_id, glb_bytes)


async def worker_loop():
    """Ana döngü — sürekli pending_3d kontrol eder."""
    print("=" * 50)
    print("  MODIF-AI 3D Worker başladı")
    print(f"  Backend : {BACKEND_URL}")
    print(f"  Model   : TripoSR (stabilityai/TripoSR)")
    print(f"  Kontrol : {POLL_INTERVAL}sn")
    print(f"  HF Token: {'var ✓' if HF_TOKEN else 'yok'}")
    print("=" * 50)

    async with httpx.AsyncClient() as client:
        while True:
            print(f"\n[{time.strftime('%H:%M:%S')}] Pending scan'ler kontrol ediliyor...")
            scans = await fetch_pending_scans(client)

            if not scans:
                print("  Bekleyen scan yok.")
            else:
                print(f"  {len(scans)} scan bulundu, işleniyor...")
                for scan in scans:
                    await process_scan(client, scan)

            await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(worker_loop())
