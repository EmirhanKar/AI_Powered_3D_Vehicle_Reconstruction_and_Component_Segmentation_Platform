"""
multiview_expander.py
─────────────────────
Her fotoğraf için InstantMesh ile 6 açıdan görüntü üretir.
8 fotoğraf → 48 görüntü → DA3METRIC ile çok daha kaliteli 3D model.

Kullanım:
    from multiview_expander import expand_images
    all_images = expand_images(image_paths, output_dir)
"""

import os
import cv2
import numpy as np
from pathlib import Path
from gradio_client import Client, handle_file
from PIL import Image as PILImage
import rembg


INSTANTMESH_SPACE = "TencentARC/InstantMesh"
_rembg_session = None

def get_rembg_session():
    """rembg session'ı lazy load et."""
    global _rembg_session
    if _rembg_session is None:
        print("  rembg modeli yükleniyor...")
        _rembg_session = rembg.new_session("u2net")
        print("  rembg hazır.")
    return _rembg_session


def remove_background(image_path: str, output_path: str) -> str:
    """
    Fotoğrafın arka planını kaldırır, beyaz arka planlı PNG kaydeder.
    InstantMesh temiz arka planlı görselde çok daha iyi çalışır.
    """
    session = get_rembg_session()
    with open(image_path, "rb") as f:
        input_data = f.read()
    output_data = rembg.remove(input_data, session=session)

    # PNG olarak kaydet (şeffaf arka plan)
    png_path = output_path.replace(".jpg", "_nobg.png")
    with open(png_path, "wb") as f:
        f.write(output_data)

    # Beyaz arka plan ekle (InstantMesh beyaz arka plan sever)
    img = PILImage.open(png_path).convert("RGBA")
    bg = PILImage.new("RGBA", img.size, (255, 255, 255, 255))
    bg.paste(img, mask=img.split()[3])
    white_path = output_path.replace(".jpg", "_white.jpg")
    bg.convert("RGB").save(white_path, "JPEG", quality=95)

    return white_path


def split_multiview_grid(grid_path: str, output_dir: str, prefix: str) -> list[str]:
    """
    InstantMesh 3x2 grid görüntüsünü 6 ayrı fotoğrafa böler.
    Grid düzeni: 3 sütun x 2 satır = 6 görüntü
    """
    # Pillow ile oku (webp dahil tüm formatlar desteklenir)
    try:
        from PIL import Image as PILImage
        pil_img = PILImage.open(grid_path).convert("RGB")
        grid = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"  [HATA] Grid okunamadı: {grid_path} → {e}")
        return []

    h, w = grid.shape[:2]
    rows, cols = 2, 3
    cell_h = h // rows
    cell_w = w // cols

    saved = []
    idx = 0
    for r in range(rows):
        for c in range(cols):
            cell = grid[r*cell_h:(r+1)*cell_h, c*cell_w:(c+1)*cell_w]
            out_path = os.path.join(output_dir, f"{prefix}_view{idx:02d}.jpg")
            cv2.imwrite(out_path, cell)
            saved.append(out_path)
            idx += 1

    print(f"  ✓ {len(saved)} görüntüye bölündü")
    return saved


def expand_single_image(image_path: str, output_dir: str, client: Client,
                         sample_steps: int = 75, seed: int = 42) -> list[str]:
    """
    Tek bir fotoğrafı InstantMesh ile 6 açıya genişletir.
    Döner: 6 görüntü yolunun listesi
    """
    prefix = Path(image_path).stem
    print(f"  → {prefix} için multi-view üretiliyor...")

    try:
        # Adım 1: rembg ile arka planı yerel olarak temizle
        nobg_dir = os.path.join(os.path.dirname(image_path), "nobg")
        os.makedirs(nobg_dir, exist_ok=True)
        nobg_path = os.path.join(nobg_dir, Path(image_path).stem + "_white.jpg")
        clean_image = remove_background(image_path, nobg_path)
        print(f"    Arka plan kaldırıldı → {os.path.basename(clean_image)}")

        # Adım 2: Temiz görseli InstantMesh'e gönder (arka plan kaldırma kapalı)
        processed = client.predict(
            input_image=handle_file(clean_image),
            do_remove_background=False,
            api_name="/preprocess",
            result_callbacks=None
        )
        processed_path = processed["path"] if isinstance(processed, dict) else processed
        print(f"    Preprocess tamamlandı")

        # Adım 3: 6 açıdan görüntü üret
        multiview = client.predict(
            input_image=handle_file(processed_path),
            sample_steps=sample_steps,
            sample_seed=seed,
            api_name="/generate_mvs",
            result_callbacks=None
        )
        grid_path = multiview["path"] if isinstance(multiview, dict) else multiview
        print(f"    Multi-view grid üretildi")

        # Adım 3: Grid'i 6 ayrı görüntüye böl
        views = split_multiview_grid(grid_path, output_dir, prefix)
        return views

    except Exception as e:
        print(f"  [HATA] {prefix} genişletilemedi: {e}")
        # Hata durumunda orijinal fotoğrafı döndür
        return [image_path]


def expand_images(image_paths: list[str], output_dir: str,
                  sample_steps: int = 75) -> list[str]:
    """
    Ana fonksiyon: tüm fotoğrafları genişletir.
    8 fotoğraf → ~48 görüntü (bazıları hata verirse daha az)

    Döner: tüm genişletilmiş görüntü yolları
    """
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n=== InstantMesh Multi-View Genişletme ===")
    print(f"  {len(image_paths)} fotoğraf → ~{len(image_paths) * 6} görüntü")
    print(f"  Space: {INSTANTMESH_SPACE}")

    try:
        client = Client(INSTANTMESH_SPACE, httpx_kwargs={"timeout": 300})
    except Exception as e:
        print(f"  [HATA] InstantMesh bağlanamadı: {e}")
        print(f"  Orijinal fotoğraflarla devam ediliyor...")
        return image_paths

    all_views = []

    for i, img_path in enumerate(image_paths):
        print(f"\n  [{i+1}/{len(image_paths)}] {os.path.basename(img_path)}")
        views = expand_single_image(img_path, output_dir, client, sample_steps)
        all_views.extend(views)

    print(f"\n✓ Toplam {len(all_views)} görüntü üretildi")
    return all_views


if __name__ == "__main__":
    # Test
    import glob
    test_images = glob.glob("temp_scans/88/*.jpg")[:2]  # Test için 2 fotoğraf
    if test_images:
        results = expand_images(test_images, "temp_multiview/test")
        print(f"\nSonuç: {len(results)} görüntü")
        for r in results:
            print(f"  {r}")
    else:
        print("Test fotoğrafı bulunamadı")
