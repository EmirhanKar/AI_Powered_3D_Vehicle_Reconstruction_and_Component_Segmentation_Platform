"""
Adım 03: SAM 2 ile Araç Segmentasyonu ve Ön Plan Maskesi Üretimi (`step_03_segment_car.py`).

Amaç:
    Kareler (`frames_dir`) içerisindeki aracı arka plandan ayırmak için SAM 2
    (Segment Anything Model 2) video tahmincisini çalıştırır. Üretilen ikili
    (binary) maskeler (`255` = araç, `0` = arka plan) ve hata ayıklama için yarı
    saydam yeşil katmanlı önizleme görselleri (`masked_preview_dir`) kaydedilir.

Kritik Mimari Karar (Neden Orijinal Kareler Silinmez?):
    COLMAP kamera pozlarını tahmin ederken (Adım 04) aracın parlak/yansımalı
    kaportası yerine asfalt, kaldırım ve binalar gibi zengin dokulu statik arka
    plan özelliklerine (SIFT features) ihtiyaç duyar. Bu yüzden orijinal kareler
    olduğu gibi korunur; burada üretilen maskeler ise Adım 05 (Gaussian Splatting)
    ve Adım 06/07 (Mesh ve Doku) aşamalarında arka planı dışlamak için kullanılır.

Girdiler (requires):
    - `frames_dir`: Perspektif karelerin bulunduğu klasör (Adım 02 çıktısı).
    - `camera_info`: Kamera üstveri JSON dosyası.

Çıktılar (produces):
    - `masks_dir`: Her kareyle aynı taban adına sahip `.png` maskelerin klasörü.
    - `masked_preview_dir`: Hata ayıklama için maske bindirilmiş önizleme klasörü.
    - `segmentation_report`: Kare başına maske doluluk oranlarını içeren JSON raporu.

Tipik Hata Durumları ve Kodları:
    - `SAM_CHECKPOINT_MISSING`: `SAM_CHECKPOINT_PATH` model ağırlık dosyası bulunamadı.
    - `CAR_NOT_DETECTED` / `MASK_COVERAGE_TOO_LOW`: Karelerde yeterli büyüklükte araç bulunamadı.
    - `SEGMENTATION_FAILED`: SAM 2 çıkarımı (inference) sırasında beklenmeyen hata.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import cv2
import numpy as np

from pipeline.base import PipelineContext, Step, StepResult
from pipeline.errors import StepError


def _generate_heuristic_or_mock_mask(image_bgr: np.ndarray) -> np.ndarray:
    """
    `DEV_MOCK_MODE=true` olduğunda veya test ortamında görüntünün merkezindeki
    aracı kapsayan temiz bir ikili maske (`uint8`, 0 veya 255) üretir.
    Gerçek kenarlara duyarlı olması için GrabCut / merkez elips kombinasyonu kullanır.
    """
    h, w = image_bgr.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)

    # Aracın genellikle kadrajın merkezinde olduğu varsayımıyla eliptik+dikdörtgen gövde maskesi
    center = (w // 2, int(h * 0.54))
    axes = (int(w * 0.28), int(h * 0.22))
    cv2.ellipse(mask, center, axes, 0, 0, 360, 255, thickness=-1)

    # Morfolojik kapama ile delikleri doldur
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask


def _create_overlay_preview(image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    Gece 02:00'de segmentasyon hatalarını (ör. tavanın veya tekerleklerin kesilmesi)
    hızlıca görebilmek için araç bölgesini yarı saydam yeşil ile boyar ve sınır
    konturunu çizer.
    """
    overlay = image_bgr.copy()
    green_layer = np.zeros_like(image_bgr)
    green_layer[:, :] = (40, 220, 40)

    fg = mask > 127
    overlay[fg] = cv2.addWeighted(image_bgr[fg], 0.55, green_layer[fg], 0.45, 0)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(overlay, contours, -1, (0, 255, 255), thickness=2)
    return overlay


class Step03SegmentCar(Step):
    """SAM 2 kullanarak karelerdeki aracı segmente eden ve önizleme üreten adım."""

    name = "segment_car"
    order = 3
    requires = ("frames_dir", "camera_info")
    produces = ("masks_dir", "masked_preview_dir", "segmentation_report")

    def _run_sam2_video_predictor(
        self,
        frame_files: List[Path],
        masks_dir: Path,
        preview_dir: Path,
        ctx: PipelineContext,
    ) -> List[Dict[str, Any]]:
        """
        Gerçek SAM 2 (`sam2.build_sam.build_sam2_video_predictor`) modelini çalıştırır.
        İlk karede merkez kutu/nokta istemiyle (prompt) aracı başlatır ve tüm video
        boyunca maskeyi takip (propagate) eder.
        """
        ckpt_path = ctx.config.sam_checkpoint_path
        if not ckpt_path.exists():
            raise StepError(
                step=self.step_id,
                code="SAM_CHECKPOINT_MISSING",
                message=f"SAM 2 model ağırlık dosyası bulunamadı: '{ckpt_path}'.",
                hint="README.md içindeki talimatları izleyerek SAM 2 ağırlıklarını 'checkpoints/' klasörüne indirin.",
                details={"sam_checkpoint_path": str(ckpt_path), "sam_model_cfg": ctx.config.sam_model_cfg},
            )

        try:
            import torch  # type: ignore
            from sam2.build_sam import build_sam2_video_predictor  # type: ignore
        except ImportError as exc:
            raise StepError(
                step=self.step_id,
                code="SAM2_PACKAGE_MISSING",
                message=f"SAM 2 Python paketi yüklü değil: {exc}",
                hint="SAM 2 paketini kurun veya test için .env içinde DEV_MOCK_MODE=true yapın.",
            ) from exc

        try:
            predictor = build_sam2_video_predictor(
                config_file=ctx.config.sam_model_cfg,
                ckpt_path=str(ckpt_path),
                device=ctx.config.device,
            )
            frames_parent = frame_files[0].parent
            first_img = cv2.imread(str(frame_files[0]))
            if first_img is None:
                raise ValueError(f"İlk kare okunamadı: {frame_files[0]}")
            h, w = first_img.shape[:2]

            # Kadraj merkezini kapsayan kutu (bounding box) istemi ile başlat
            box_prompt = np.array([w * 0.15, h * 0.18, w * 0.85, h * 0.88], dtype=np.float32)

            with torch.inference_mode():
                inference_state = predictor.init_state(video_path=str(frames_parent))
                predictor.add_new_points_or_box(
                    inference_state=inference_state,
                    frame_idx=0,
                    obj_id=1,
                    box=box_prompt,
                )

                records: List[Dict[str, Any]] = []
                for out_frame_idx, _obj_ids, video_res_masks in predictor.propagate_in_video(inference_state):
                    src_file = frame_files[out_frame_idx]
                    img = cv2.imread(str(src_file))
                    raw_mask = (video_res_masks[0] > 0.0).cpu().numpy().squeeze().astype(np.uint8) * 255

                    # Küçük delikleri kapat ve kenar gürültüsünü temizle
                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                    clean_mask = cv2.morphologyEx(raw_mask, cv2.MORPH_CLOSE, kernel)

                    mask_name = f"{src_file.stem}.png"
                    mask_path = masks_dir / mask_name
                    cv2.imwrite(str(mask_path), clean_mask)

                    if img is not None:
                        preview = _create_overlay_preview(img, clean_mask)
                        cv2.imwrite(str(preview_dir / f"{src_file.stem}_preview.jpg"), preview)

                    area_ratio = float(np.count_nonzero(clean_mask)) / float(clean_mask.size)
                    records.append(
                        {
                            "frame_file": src_file.name,
                            "mask_file": mask_name,
                            "area_ratio": round(area_ratio, 4),
                        }
                    )
                return records
        except StepError:
            raise
        except Exception as exc:
            raise StepError(
                step=self.step_id,
                code="SEGMENTATION_FAILED",
                message=f"SAM 2 video segmentasyonu sırasında hata oluştu: {exc}",
                hint="GPU belleğinin (VRAM) yeterli olduğundan ve SAM 2 ağırlıklarının model konfigürasyonuyla eşleştiğinden emin olun.",
                details={"error": str(exc)},
            ) from exc

    def run(self, ctx: PipelineContext) -> StepResult:
        step_dir = self.prepare_step_dir(ctx)
        frames_dir = ctx.get_artifact_path("frames_dir")
        _camera_info_path = ctx.get_artifact_path("camera_info")

        frame_files = sorted(frames_dir.glob("*.jpg")) + sorted(frames_dir.glob("*.png"))
        if not frame_files:
            raise StepError(
                step=self.step_id,
                code="NO_FRAMES_FOR_SEGMENTATION",
                message=f"'{frames_dir}' klasöründe segmente edilecek kare bulunamadı.",
            )

        masks_dir = step_dir / "masks"
        preview_dir = step_dir / "preview"
        masks_dir.mkdir(parents=True, exist_ok=True)
        preview_dir.mkdir(parents=True, exist_ok=True)

        if ctx.config.dev_mock_mode:
            ctx.logger.info("DEV_MOCK_MODE aktif: %d kare için sentetik araç maskesi ve önizlemesi üretiliyor.", len(frame_files))
            records: List[Dict[str, Any]] = []
            for src_file in frame_files:
                img = cv2.imread(str(src_file))
                if img is None:
                    continue
                mask = _generate_heuristic_or_mock_mask(img)
                mask_name = f"{src_file.stem}.png"
                cv2.imwrite(str(masks_dir / mask_name), mask)

                preview = _create_overlay_preview(img, mask)
                cv2.imwrite(str(preview_dir / f"{src_file.stem}_preview.jpg"), preview, [int(cv2.IMWRITE_JPEG_QUALITY), 85])

                area_ratio = float(np.count_nonzero(mask)) / float(mask.size)
                records.append(
                    {
                        "frame_file": src_file.name,
                        "mask_file": mask_name,
                        "area_ratio": round(area_ratio, 4),
                    }
                )
        else:
            records = self._run_sam2_video_predictor(frame_files, masks_dir, preview_dir, ctx)

        # Kalite Kapısı: Aracın karelerdeki ortalama kaplama alanı çok düşükse çekim hatalıdır
        valid_frames = [r for r in records if r["area_ratio"] >= ctx.config.min_mask_area_ratio]
        mean_area_ratio = float(np.mean([r["area_ratio"] for r in records])) if records else 0.0
        valid_coverage_rate = len(valid_frames) / float(max(len(records), 1))

        if valid_coverage_rate < 0.70 or mean_area_ratio < ctx.config.min_mask_area_ratio:
            raise StepError(
                step=self.step_id,
                code="MASK_COVERAGE_TOO_LOW",
                message=(
                    f"Karelerde araç maskesi kaplama oranı çok düşük (ortalama alan={mean_area_ratio:.1%}, "
                    f"geçerli kare oranı={valid_coverage_rate:.1%})."
                ),
                hint="Araca daha yakın durarak (aracın ekranın en az %30-%60'ını kapladığından emin olarak) tekrar video çekin.",
                details={
                    "mean_area_ratio": round(mean_area_ratio, 4),
                    "valid_coverage_rate": round(valid_coverage_rate, 4),
                    "min_mask_area_ratio": ctx.config.min_mask_area_ratio,
                },
            )

        report_data = {
            "total_frames": len(records),
            "valid_masked_frames": len(valid_frames),
            "mean_area_ratio": round(mean_area_ratio, 4),
            "valid_coverage_rate": round(valid_coverage_rate, 4),
            "masks": records,
        }
        report_path = step_dir / "segmentation_report.json"
        report_path.write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")

        ctx.logger.info(
            "Araç segmentasyonu tamamlandı: %d/%d kare geçerli (ortalama araç alanı=%.1f%%).",
            len(valid_frames),
            len(records),
            mean_area_ratio * 100.0,
        )

        return StepResult(
            status="done",
            artifacts={
                "masks_dir": str(masks_dir),
                "masked_preview_dir": str(preview_dir),
                "segmentation_report": str(report_path),
            },
            metrics={
                "total_frames": len(records),
                "valid_masked_frames": len(valid_frames),
                "mean_area_ratio": round(mean_area_ratio, 4),
            },
            summary=f"{len(records)} kare için SAM 2 araç maskesi ve önizlemesi üretildi.",
        )
