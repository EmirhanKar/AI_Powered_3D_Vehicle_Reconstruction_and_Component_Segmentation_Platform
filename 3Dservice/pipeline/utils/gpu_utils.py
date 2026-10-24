"""
ModifAI 3D Servisi — GPU, Sistem Bağımlılıkları ve Model Ağırlık Kontrolü.

Bu modül, `GET /health` uç noktası ve başlangıç denetimleri için FFmpeg,
FFprobe, COLMAP, CUDA/GPU erişilebilirliği ve SAM 2 model ağırlık dosyasının
durumunu sorgular.
"""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any, Dict

from config import ServiceConfig


def _check_binary(bin_name_or_path: str) -> Dict[str, Any]:
    """Verilen ikili (binary) dosyanın sistem PATH'inde veya belirtilen yolda olup olmadığını denetler."""
    p = Path(bin_name_or_path)
    if p.exists() and p.is_file():
        return {"available": True, "path": str(p.resolve())}
    resolved = shutil.which(bin_name_or_path)
    if resolved:
        return {"available": True, "path": resolved}
    return {"available": False, "path": None}


def check_gpu_status() -> Dict[str, Any]:
    """PyTorch üzerinden CUDA ve GPU belleği (VRAM) durumunu sorgular."""
    try:
        import torch  # type: ignore

        cuda_available = bool(torch.cuda.is_available())
        if cuda_available:
            device_count = int(torch.cuda.device_count())
            device_name = str(torch.cuda.get_device_name(0))
            props = torch.cuda.get_device_properties(0)
            total_vram_gb = round(props.total_memory / (1024**3), 2)
            return {
                "cuda_available": True,
                "device_count": device_count,
                "device_name": device_name,
                "total_vram_gb": total_vram_gb,
            }
        return {
            "cuda_available": False,
            "device_count": 0,
            "device_name": None,
            "total_vram_gb": 0.0,
        }
    except Exception as exc:
        return {
            "cuda_available": False,
            "device_count": 0,
            "device_name": None,
            "error": str(exc),
        }


def collect_health_report(cfg: ServiceConfig) -> Dict[str, Any]:
    """
    Tüm alt bileşenlerin (ffmpeg, ffprobe, colmap, GPU, SAM checkpoint)
    sağlık durumunu tek bir sözlükte toplar.

    `DEV_MOCK_MODE=true` olduğunda eksik ikili dosyalar servisi 'unhealthy'
    yapmaz, ancak raporda şeffaf bir şekilde 'mock_mode' olarak belirtilir.
    """
    ffmpeg_info = _check_binary(cfg.ffmpeg_bin)
    ffprobe_info = _check_binary(cfg.ffprobe_bin)
    colmap_info = _check_binary(cfg.colmap_bin)
    gpu_info = check_gpu_status()
    sam_exists = cfg.sam_checkpoint_path.exists() and cfg.sam_checkpoint_path.is_file()

    all_real_deps_ready = (
        ffmpeg_info["available"]
        and ffprobe_info["available"]
        and colmap_info["available"]
        and (gpu_info["cuda_available"] or cfg.device == "cpu")
        and sam_exists
    )

    status = "healthy" if (all_real_deps_ready or cfg.dev_mock_mode) else "degraded"

    return {
        "status": status,
        "dev_mock_mode": cfg.dev_mock_mode,
        "storage_backend": cfg.storage_backend,
        "recon_method": cfg.recon_method,
        "dependencies": {
            "ffmpeg": ffmpeg_info,
            "ffprobe": ffprobe_info,
            "colmap": colmap_info,
            "gpu": gpu_info,
            "sam_checkpoint": {
                "available": sam_exists,
                "path": str(cfg.sam_checkpoint_path),
            },
        },
    }
