"""
Adım 00: Girdi Doğrulama ve 360° Video Tespiti (`step_00_validate_input.py`).

Amaç:
    Kullanıcı veya Backend tarafından gönderilen araç videosunun boyutu, formatı,
    süresi ve çözünürlüğünün `.env` içerisindeki sınırlar dahilinde olduğunu
    doğrular. Ayrıca videonun 2:1 en-boy oranına veya küresel (spherical)
    üstverisine bakarak 360° equirectangular video olup olmadığını (`is_360`)
    tespit eder.

Girdiler (requires):
    - `input_video`: Ham girdi video dosyasının yolu (`Path` veya `str`).

Çıktılar (produces):
    - `validated_video`: Doğrulanmış videonun `00_validate_input/` içindeki yolu.
    - `video_metadata`: Çözünürlük, süre, FPS ve `is_360` bilgisini içeren JSON dosyası yolu.

Tipik Hata Durumları ve Kodları:
    - `VIDEO_NOT_FOUND`: Girdi video dosyası diskte mevcut değil.
    - `UNSUPPORTED_FORMAT`: Dosya uzantısı desteklenen video formatlarından (.mp4, .mov vb.) değil.
    - `VIDEO_TOO_LARGE`: Dosya boyutu `MAX_VIDEO_MB` sınırını aşıyor.
    - `VIDEO_TOO_SHORT` / `VIDEO_TOO_LONG`: Video süresi izin verilen aralık dışında.
    - `RESOLUTION_TOO_LOW`: Çözünürlük `MIN_VIDEO_WIDTH` x `MIN_VIDEO_HEIGHT` altında.
    - `FFPROBE_FAILED`: Video akışı bozuk veya okunamıyor.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Set

from pipeline.base import PipelineContext, Step, StepResult
from pipeline.errors import StepError
from pipeline.utils.ffmpeg_utils import probe_video_metadata

SUPPORTED_VIDEO_EXTENSIONS: Set[str] = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}


class Step00ValidateInput(Step):
    """Girdi videosunun teknik uygunluğunu ve 360° olup olmadığını denetleyen ilk adım."""

    name = "validate_input"
    order = 0
    requires = ("input_video",)
    produces = ("validated_video", "video_metadata")

    def run(self, ctx: PipelineContext) -> StepResult:
        step_dir = self.prepare_step_dir(ctx)
        input_video_path = ctx.get_artifact_path("input_video")

        # 1. Dosya varlık kontrolü
        if not input_video_path.exists() or not input_video_path.is_file():
            raise StepError(
                step=self.step_id,
                code="VIDEO_NOT_FOUND",
                message=f"Girdi video dosyası bulunamadı: '{input_video_path}'.",
                hint="Lütfen geçerli bir video dosyası yüklediğinizden emin olun.",
                details={"input_video": str(input_video_path)},
            )

        # 2. Uzantı kontrolü
        ext = input_video_path.suffix.lower()
        if ext not in SUPPORTED_VIDEO_EXTENSIONS:
            raise StepError(
                step=self.step_id,
                code="UNSUPPORTED_FORMAT",
                message=f"Desteklenmeyen video formatı: '{ext}'.",
                hint=f"Lütfen desteklenen formatlardan birini kullanın: {sorted(SUPPORTED_VIDEO_EXTENSIONS)}",
                details={"extension": ext, "supported": sorted(SUPPORTED_VIDEO_EXTENSIONS)},
            )

        # 3. Dosya boyutu kontrolü (disk ve bellek taşmalarını önlemek için)
        file_size_bytes = input_video_path.stat().st_size
        if file_size_bytes == 0:
            raise StepError(
                step=self.step_id,
                code="VIDEO_EMPTY",
                message="Yüklenen video dosyası tamamen boş (0 byte).",
                hint="Dosya aktarımının tamamlandığından emin olup tekrar yükleyin.",
            )

        file_size_mb = file_size_bytes / (1024.0 * 1024.0)
        if file_size_mb > ctx.config.max_video_mb:
            raise StepError(
                step=self.step_id,
                code="VIDEO_TOO_LARGE",
                message=(
                    f"Video boyutu ({file_size_mb:.1f} MB), izin verilen maksimum sınırı "
                    f"({ctx.config.max_video_mb:.1f} MB) aşıyor."
                ),
                hint="Videoyu 1080p veya 4K H.264 formatında sıkıştırarak veya süresini kısaltarak tekrar yükleyin.",
                details={"file_size_mb": round(file_size_mb, 2), "max_video_mb": ctx.config.max_video_mb},
            )

        # 4. Üstveri (metadata) okuma
        if ctx.config.dev_mock_mode:
            # Mock modunda dosya adı veya boyutu üzerinden deterministik üstveri üret,
            # ancak gerçek bir video dosyası verilmişse yine de ffprobe/opencv dene.
            try:
                meta = probe_video_metadata(
                    video_path=input_video_path,
                    ffprobe_bin=ctx.config.ffprobe_bin,
                    step_name=self.step_id,
                    logger=ctx.logger,
                )
            except StepError:
                is_360_hint = "360" in input_video_path.stem.lower() or "equirect" in input_video_path.stem.lower()
                width = 1920 if not is_360_hint else 2880
                height = 1080 if not is_360_hint else 1440
                meta = {
                    "file_name": input_video_path.name,
                    "file_size_mb": round(file_size_mb, 3),
                    "width": width,
                    "height": height,
                    "aspect_ratio": round(width / height, 4),
                    "duration_seconds": 12.0,
                    "fps": 30.0,
                    "codec_name": "mock_h264",
                    "spherical_metadata": is_360_hint,
                    "is_aspect_2_to_1": is_360_hint,
                    "is_360": is_360_hint,
                }
        else:
            meta = probe_video_metadata(
                video_path=input_video_path,
                ffprobe_bin=ctx.config.ffprobe_bin,
                step_name=self.step_id,
                logger=ctx.logger,
            )

        # 5. Süre kalite kapıları (çok kısa videoda 360° tur tamamlanamaz, çok uzun videoda COLMAP şişer)
        duration = float(meta["duration_seconds"])
        if duration < ctx.config.min_video_seconds:
            raise StepError(
                step=self.step_id,
                code="VIDEO_TOO_SHORT",
                message=(
                    f"Video süresi çok kısa ({duration:.1f} sn). En az "
                    f"{ctx.config.min_video_seconds:.1f} saniye olmalıdır."
                ),
                hint="Aracın etrafında tam bir tur atacak şekilde en az 15-30 saniyelik bir video çekin.",
                details={"duration_seconds": duration, "min_video_seconds": ctx.config.min_video_seconds},
            )

        if duration > ctx.config.max_video_seconds:
            raise StepError(
                step=self.step_id,
                code="VIDEO_TOO_LONG",
                message=(
                    f"Video süresi ({duration:.1f} sn), maksimum sınırı "
                    f"({ctx.config.max_video_seconds:.1f} sn) aşıyor."
                ),
                hint="Lütfen yalnızca aracın etrafında döndüğünüz 30-90 saniyelik bölümü kırparak yükleyin.",
                details={"duration_seconds": duration, "max_video_seconds": ctx.config.max_video_seconds},
            )

        # 6. Çözünürlük kalite kapısı (düşük çözünürlükte SIFT/SuperPoint yeterli anahtar nokta bulamaz)
        width = int(meta["width"])
        height = int(meta["height"])
        short_side = min(width, height)
        long_side = max(width, height)
        req_short = min(ctx.config.min_video_width, ctx.config.min_video_height)
        req_long = max(ctx.config.min_video_width, ctx.config.min_video_height)

        if short_side < req_short or long_side < req_long:
            raise StepError(
                step=self.step_id,
                code="RESOLUTION_TOO_LOW",
                message=(
                    f"Video çözünürlüğü ({width}x{height}) çok düşük. "
                    f"Minimum {ctx.config.min_video_width}x{ctx.config.min_video_height} gereklidir."
                ),
                hint="Telefon veya kamera ayarlarından en az 1080p (1920x1080) çözünürlük seçerek tekrar çekim yapın.",
                details={
                    "width": width,
                    "height": height,
                    "min_width": ctx.config.min_video_width,
                    "min_height": ctx.config.min_video_height,
                },
            )

        # Doğrulanmış videoyu adımın kendi klasörüne kopyala (veya sabit bağ oluştur)
        validated_video_path = step_dir / f"validated_input{ext}"
        shutil.copy2(input_video_path, validated_video_path)

        metadata_path = step_dir / "video_metadata.json"
        metadata_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

        # Bağlam üstverisine `is_360` bilgisini de kaydet
        ctx.metadata["is_360"] = bool(meta["is_360"])

        ctx.logger.info(
            "Video doğrulandı: %dx%d, %.1f sn, %.2f MB, is_360=%s",
            width,
            height,
            duration,
            file_size_mb,
            meta["is_360"],
        )

        return StepResult(
            status="done",
            artifacts={
                "validated_video": str(validated_video_path),
                "video_metadata": str(metadata_path),
            },
            metrics={
                "width": width,
                "height": height,
                "duration_seconds": duration,
                "file_size_mb": round(file_size_mb, 3),
                "is_360": bool(meta["is_360"]),
            },
            summary=f"Video doğrulandı ({width}x{height}, {duration:.1f}s, 360°={meta['is_360']}).",
        )
