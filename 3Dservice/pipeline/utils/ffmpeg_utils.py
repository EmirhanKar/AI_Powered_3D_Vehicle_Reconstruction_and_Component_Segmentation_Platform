"""
ModifAI 3D Servisi — FFmpeg ve FFprobe Yardımcı Fonksiyonları.

Bu modül, video üstverisini (çözünürlük, süre, FPS, codec, 360° küresel etiketler)
okumak ve videodan kare (frame) çıkarmak için kullanılan yardımcı işlevleri barındırır.
`DEV_MOCK_MODE=true` olduğunda veya test ortamında `ffprobe` kurulu değilse
OpenCV (`cv2.VideoCapture`) üzerinden güvenli bir geri dönüş (fallback) sağlar.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import shutil
from typing import Any, Dict, Optional

import cv2

from pipeline.errors import StepError
from pipeline.utils.subprocess_runner import run_subprocess


def probe_video_metadata(
    video_path: Path,
    ffprobe_bin: str,
    step_name: str,
    logger: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    """
    Video dosyasının teknik özelliklerini (`width`, `height`, `duration`, `fps`,
    `codec_name`, `is_360`) analiz eder.

    360° (Equirectangular) Tespiti Neden Önemlidir?
    Kullanıcı Insta360 / GoPro Max gibi bir kamerayla çekim yaptığında görüntü
    2:1 en-boy oranında küresel (equirectangular) projeksiyona sahiptir. Standart
    iğne deliği (pinhole) kamera varsayımıyla COLMAP'e verilirse poz tahmini
    tamamen çöker. Bu yüzden hem `side_data_list` / `spherical` üstverisine hem de
    2:1 en-boy oranına (`abs(width / height - 2.0) < 0.05`) bakılarak `is_360`
    bayrağı belirlenir.
    """
    file_size_mb = video_path.stat().st_size / (1024.0 * 1024.0)
    ffprobe_available = shutil.which(ffprobe_bin) is not None or Path(ffprobe_bin).exists()

    width = 0
    height = 0
    duration = 0.0
    fps = 30.0
    codec_name = "unknown"
    spherical_tagged = False

    if ffprobe_available:
        cmd = [
            ffprobe_bin,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ]
        res = run_subprocess(
            command=cmd,
            step_name=step_name,
            error_code="FFPROBE_FAILED",
            error_message="Video üstverisi (metadata) ffprobe ile okunamadı",
            hint="Video dosyasının bozuk olmadığından ve desteklenen bir formatta (MP4/MOV) olduğundan emin olun.",
            timeout_seconds=60,
            logger=logger,
        )
        try:
            probe_data = json.loads(res.stdout)
        except json.JSONDecodeError as exc:
            raise StepError(
                step=step_name,
                code="FFPROBE_INVALID_JSON",
                message="ffprobe çıktısı geçerli bir JSON formatında değil.",
                details={"stdout": res.stdout[:500]},
            ) from exc

        streams = probe_data.get("streams", [])
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        if not video_stream:
            raise StepError(
                step=step_name,
                code="NO_VIDEO_STREAM",
                message="Dosya içinde geçerli bir video akışı (stream) bulunamadı.",
                hint="Yalnızca ses içeren veya bozuk bir dosya yüklemediğinizden emin olun.",
            )

        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        codec_name = str(video_stream.get("codec_name", "unknown"))

        # Kare hızı (r_frame_rate örn. "30000/1001" veya "30/1")
        fps_raw = str(video_stream.get("r_frame_rate", "30/1"))
        if "/" in fps_raw:
            num, den = fps_raw.split("/", 1)
            fps = float(num) / max(float(den), 1.0)
        else:
            fps = float(fps_raw or 30.0)

        fmt = probe_data.get("format", {})
        duration = float(video_stream.get("duration") or fmt.get("duration") or 0.0)

        # Küresel (360) metadata kontrolü (side_data_list veya tags)
        side_data = video_stream.get("side_data_list", [])
        for sd in side_data:
            sd_type = str(sd.get("side_data_type", "")).lower()
            proj = str(sd.get("projection", "")).lower()
            if "spherical" in sd_type or "equirectangular" in proj:
                spherical_tagged = True

        tags = {k.lower(): str(v).lower() for k, v in {**fmt.get("tags", {}), **video_stream.get("tags", {})}.items()}
        if any("spherical" in k or "equirectangular" in v or "360" in v for k, v in tags.items()):
            spherical_tagged = True
    else:
        # Sistemde ffprobe yoksa OpenCV VideoCapture ile yedek okuma yap
        if logger:
            logger.warning("Sistemde '%s' bulunamadı; video üstverisi OpenCV ile okunuyor.", ffprobe_bin)
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise StepError(
                step=step_name,
                code="FFPROBE_FAILED",
                message="Video dosyası ne ffprobe ne de OpenCV ile açılabildi.",
                hint="Lütfen standart H.264 MP4 veya MOV formatında geçerli bir video yükleyin.",
            )
        try:
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
            if fps <= 0:
                fps = 30.0
            frame_count = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
            duration = frame_count / fps if frame_count > 0 else 5.0
            codec_name = "opencv_fallback"
        finally:
            cap.release()

    #Dosya adında "360" veya "equirect" geçmesi ya da 2:1 en-boy oranı (ör. 3840x1920, 2880x1440)
    aspect_ratio = (float(width) / float(height)) if height > 0 else 0.0
    is_aspect_2_to_1 = abs(aspect_ratio - 2.0) <= 0.06
    filename_hint_360 = "360" in video_path.stem.lower() or "equirect" in video_path.stem.lower()
    is_360 = bool(spherical_tagged or is_aspect_2_to_1 or filename_hint_360)

    return {
        "file_name": video_path.name,
        "file_size_mb": round(file_size_mb, 3),
        "width": width,
        "height": height,
        "aspect_ratio": round(aspect_ratio, 4),
        "duration_seconds": round(duration, 3),
        "fps": round(fps, 3),
        "codec_name": codec_name,
        "spherical_metadata": spherical_tagged,
        "is_aspect_2_to_1": is_aspect_2_to_1,
        "is_360": is_360,
    }
