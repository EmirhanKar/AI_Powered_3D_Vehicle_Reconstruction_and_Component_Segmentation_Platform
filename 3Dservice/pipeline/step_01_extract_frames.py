"""
Adım 01: Kare Çıkarma, Bulanıklık Elemesi ve Paralaks Anahtar Kare Seçimi (`step_01_extract_frames.py`).

Amaç:
    Doğrulanmış videodan aday kareleri çıkarır, hareket bulanıklığı (motion blur)
    içeren kareleri Laplacian varyansı ile eler ve ardışık kareler arasında
    yeterli kamera hareketi (paralaks / baseline) bulunan en net kareleri
    `TARGET_FRAME_COUNT` sınırına kadar seçer.

Girdiler (requires):
    - `validated_video`: Adım 00 tarafından doğrulanmış video dosyası.
    - `video_metadata`: Video üstveri JSON dosyası (`duration_seconds`, `fps`, `is_360`).

Çıktılar (produces):
    - `raw_frames_dir`: Seçilen net anahtar karelerin (`frame_0000.jpg` ...) bulunduğu klasör.
    - `extraction_report`: Aday sayısı, elenen bulanık kare sayısı, ortalama keskinlik ve
      paralaks skorlarını içeren JSON raporu.

Tipik Hata Durumları ve Kodları:
    - `FFMPEG_EXTRACTION_FAILED`: Videodan kare çıkarma işlemi başarısız oldu.
    - `ALL_FRAMES_BLURRY`: Çıkarılan tüm kareler `BLUR_THRESHOLD` değerinin altında kaldı.
    - `TOO_FEW_FRAMES`: Seçilen net kare sayısı `MIN_FRAME_COUNT` sınırının altında kaldı.
    - `INSUFFICIENT_PARALLAX`: Kamera neredeyse hiç hareket etmemiş (sabit açı çekimi).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import shutil
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np

from pipeline.base import PipelineContext, Step, StepResult
from pipeline.errors import StepError
from pipeline.utils.subprocess_runner import run_subprocess


def compute_sharpness_laplacian(image_bgr: np.ndarray) -> float:
    """
    Görüntünün keskinliğini (sharpness) gri tonlamalı Laplacian operatörünün
    varyansı ile hesaplar.

    Neden Laplacian Varyansı?
    Hareket bulanıklığı (motion blur) yüksek frekanslı kenar geçişlerini yok eder.
    COLMAP SIFT çıkarıcısı bulanık karelerde yanlış eşleşmeler (outliers) üretir ve
    Gaussian Splatting eğitiminde "hayalet/sis" (floaters) artefaktlarına yol açar.
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    # Farklı çözünürlüklerde tutarlı bir eşik elde etmek için standart genişliğe (640px) ölçekle
    h, w = gray.shape[:2]
    if w > 640:
        scale = 640.0 / float(w)
        gray = cv2.resize(gray, (640, max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    return float(lap.var())


def compute_parallax_score(prev_gray_small: np.ndarray, curr_gray_small: np.ndarray) -> float:
    """
    İki küçük gri kare arasındaki ortalama piksel farkı / yer değiştirme skorunu hesaplar.
    Kullanıcı videoda yürümeden aynı noktada durursa ardışık kareler neredeyse aynı olur;
    bu durumda üçgenleme (triangulation) açısı sıfıra yaklaşır ve derinlik belirsizleşir.
    """
    diff = cv2.absdiff(prev_gray_small, curr_gray_small)
    return float(np.mean(diff))


def _generate_synthetic_car_frames(output_dir: Path, count: int, width: int, height: int) -> List[Path]:
    """
    `DEV_MOCK_MODE=true` olduğunda veya sentetik testlerde, aracın etrafında
    dönen bir kamerayı simüle eden zengin dokulu (Laplacian keskinliği yüksek
    ve kareler arası paralaksı belirgin) JPEG kareler üretir.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: List[Path] = []
    rng = np.random.default_rng(seed=42)

    # Sabit bir dama tahtası + doku zemini oluştur (COLMAP ve Laplacian için yüksek frekanslı kenarlar)
    checker = np.zeros((height, width, 3), dtype=np.uint8)
    tile = 32
    for y in range(0, height, tile):
        for x in range(0, width, tile):
            color = 190 if ((x // tile) + (y // tile)) % 2 == 0 else 65
            checker[y : y + tile, x : x + tile] = (color, color, color)

    noise = rng.integers(0, 25, size=(height, width, 3), dtype=np.uint8)
    base_bg = cv2.add(checker, noise)

    for idx in range(count):
        angle = (2.0 * math.pi * idx) / float(max(count, 1))
        frame = base_bg.copy()

        # Kamera dönüşünü simüle etmek için arka planı yatay kaydır (paralaks)
        shift_x = int((idx * 17) % width)
        frame = np.roll(frame, shift=shift_x, axis=1)

        # Merkezde dönen bir araç gövdesi ve tekerlekleri çiz
        cx = int(width * 0.5 + 35.0 * math.cos(angle))
        cy = int(height * 0.55 + 15.0 * math.sin(angle))
        body_w = int(width * 0.36)
        body_h = int(height * 0.22)

        x1 = max(10, cx - body_w // 2)
        y1 = max(10, cy - body_h // 2)
        x2 = min(width - 10, cx + body_w // 2)
        y2 = min(height - 10, cy + body_h // 2)

        # Araç gövdesi (mavi-kırmızı tonlu + keskin kenar çizgileri)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (35, 70, 210), thickness=-1)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (245, 245, 245), thickness=3)

        # Tavan / cam kabini
        roof_x1 = x1 + int(body_w * 0.2)
        roof_x2 = x2 - int(body_w * 0.2)
        roof_y1 = max(5, y1 - int(body_h * 0.45))
        cv2.rectangle(frame, (roof_x1, roof_y1), (roof_x2, y1), (180, 210, 230), thickness=-1)
        cv2.rectangle(frame, (roof_x1, roof_y1), (roof_x2, y1), (20, 20, 20), thickness=2)

        # Tekerlekler
        wheel_r = max(12, int(body_h * 0.28))
        cv2.circle(frame, (x1 + int(body_w * 0.22), y2), wheel_r, (25, 25, 25), thickness=-1)
        cv2.circle(frame, (x2 - int(body_w * 0.22), y2), wheel_r, (25, 25, 25), thickness=-1)
        cv2.circle(frame, (x1 + int(body_w * 0.22), y2), wheel_r // 2, (200, 200, 200), thickness=2)
        cv2.circle(frame, (x2 - int(body_w * 0.22), y2), wheel_r // 2, (200, 200, 200), thickness=2)

        out_file = output_dir / f"cand_{idx:04d}.jpg"
        cv2.imwrite(str(out_file), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        generated.append(out_file)

    return generated


class Step01ExtractFrames(Step):
    """Videodan aday kareleri çıkaran, bulanıkları eleyen ve anahtar kareleri seçen adım."""

    name = "extract_frames"
    order = 1
    requires = ("validated_video", "video_metadata")
    produces = ("raw_frames_dir", "extraction_report")

    def _extract_candidates(
        self,
        video_path: Path,
        candidates_dir: Path,
        duration_seconds: float,
        ctx: PipelineContext,
    ) -> List[Path]:
        """
        FFmpeg (veya yedek olarak OpenCV) kullanarak hedef kare sayısının ~2 katı
        kadar aday kare çıkarır ki bulanık olanlar elendikten sonra bile yeterli
        sayıda net kare kalsın.
        """
        candidates_dir.mkdir(parents=True, exist_ok=True)
        desired_candidates = max(ctx.config.target_frame_count * 2, ctx.config.min_frame_count * 2)
        sample_fps = max(1.0, min(15.0, desired_candidates / max(duration_seconds, 1.0)))

        ffmpeg_bin = ctx.config.ffmpeg_bin
        ffmpeg_available = shutil.which(ffmpeg_bin) is not None or Path(ffmpeg_bin).exists()

        if ffmpeg_available and not ctx.config.dev_mock_mode:
            out_pattern = candidates_dir / "cand_%04d.jpg"
            cmd = [
                ffmpeg_bin,
                "-y",
                "-i",
                str(video_path),
                "-vf",
                f"fps={sample_fps:.3f}",
                "-qscale:v",
                "2",
                str(out_pattern),
            ]
            run_subprocess(
                command=cmd,
                step_name=self.step_id,
                error_code="FFMPEG_EXTRACTION_FAILED",
                error_message="FFmpeg ile videodan kare çıkarma işlemi başarısız oldu",
                hint="Videonun bozuk olmadığından ve FFmpeg kurulumunun sağlam olduğundan emin olun.",
                timeout_seconds=ctx.config.step_timeout_seconds,
                logger=ctx.logger,
            )
            extracted = sorted(candidates_dir.glob("cand_*.jpg"))
            if extracted:
                return extracted

        # OpenCV ile doğrudan okuma (FFmpeg yoksa veya mock modda gerçek bir video verilmişse)
        cap = cv2.VideoCapture(str(video_path))
        extracted_cv: List[Path] = []
        if cap.isOpened():
            try:
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                stride = max(1, total_frames // desired_candidates) if total_frames > desired_candidates else 1
                frame_idx = 0
                saved_idx = 0
                while True:
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        break
                    if frame_idx % stride == 0:
                        out_file = candidates_dir / f"cand_{saved_idx:04d}.jpg"
                        cv2.imwrite(str(out_file), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
                        extracted_cv.append(out_file)
                        saved_idx += 1
                    frame_idx += 1
            finally:
                cap.release()

        if extracted_cv:
            return extracted_cv

        # Eğer mock modundaysak ve girdi dosyası sahte/boş bir test dosyasıysa sentetik kareler üret
        if ctx.config.dev_mock_mode:
            ctx.logger.info("DEV_MOCK_MODE aktif: Sentetik araç kareleri üretiliyor.")
            return _generate_synthetic_car_frames(
                output_dir=candidates_dir,
                count=max(ctx.config.target_frame_count, ctx.config.min_frame_count + 6),
                width=640,
                height=480,
            )

        raise StepError(
            step=self.step_id,
            code="FFMPEG_EXTRACTION_FAILED",
            message="Videodan hiçbir kare çıkarılamadı.",
            hint="Lütfen standart H.264/MP4 kodekli bir video yükleyin.",
        )

    def run(self, ctx: PipelineContext) -> StepResult:
        step_dir = self.prepare_step_dir(ctx)
        video_path = ctx.get_artifact_path("validated_video")
        meta_path = ctx.get_artifact_path("video_metadata")
        meta: Dict[str, Any] = json.loads(meta_path.read_text(encoding="utf-8"))

        candidates_dir = step_dir / "_candidates"
        raw_frames_dir = step_dir / "frames"
        raw_frames_dir.mkdir(parents=True, exist_ok=True)

        candidate_files = self._extract_candidates(
            video_path=video_path,
            candidates_dir=candidates_dir,
            duration_seconds=float(meta.get("duration_seconds", 10.0)),
            ctx=ctx,
        )

        total_candidates = len(candidate_files)
        ctx.logger.info("Toplam %d aday kare çıkarıldı; bulanıklık ve paralaks analizi başlıyor.", total_candidates)

        # 1. Her karenin keskinlik (Laplacian variance) skorunu ölç ve eşik altındakileri ele
        sharp_frames: List[Tuple[Path, float, np.ndarray]] = []
        blur_rejected_count = 0

        for cand_path in candidate_files:
            img = cv2.imread(str(cand_path))
            if img is None:
                continue
            sharpness = compute_sharpness_laplacian(img)
            if sharpness < ctx.config.blur_threshold:
                blur_rejected_count += 1
                continue
            small_gray = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (160, 120))
            sharp_frames.append((cand_path, sharpness, small_gray))

        # Aday klasörünü temizlemeden önce keskin kare sayısını kontrol et
        if not sharp_frames:
            shutil.rmtree(candidates_dir, ignore_errors=True)
            raise StepError(
                step=self.step_id,
                code="ALL_FRAMES_BLURRY",
                message=(
                    f"Çıkarılan {total_candidates} karenin tamamı bulanıklık eşiğinin "
                    f"(BLUR_THRESHOLD={ctx.config.blur_threshold}) altında kaldı."
                ),
                hint="Telefonu sabit tutarak, yavaş adımlarla ve iyi ışık altında tekrar video çekin.",
                details={
                    "total_candidates": total_candidates,
                    "blur_threshold": ctx.config.blur_threshold,
                },
            )

        # 2. Paralaks (hareket) filtrelemesi: Kamera sabit dururken çekilmiş kopya kareleri atla
        parallax_filtered: List[Tuple[Path, float]] = [
            (sharp_frames[0][0], sharp_frames[0][1])
        ]
        last_gray = sharp_frames[0][2]
        parallax_scores: List[float] = []

        for cand_path, sharpness, small_gray in sharp_frames[1:]:
            p_score = compute_parallax_score(last_gray, small_gray)
            parallax_scores.append(p_score)
            if p_score >= ctx.config.min_parallax_score:
                parallax_filtered.append((cand_path, sharpness))
                last_gray = small_gray

        mean_parallax = float(np.mean(parallax_scores)) if parallax_scores else 0.0
        if len(sharp_frames) > 1 and mean_parallax < (ctx.config.min_parallax_score * 0.5):
            shutil.rmtree(candidates_dir, ignore_errors=True)
            raise StepError(
                step=self.step_id,
                code="INSUFFICIENT_PARALLAX",
                message=(
                    f"Kareler arasında yeterli kamera hareketi (paralaks={mean_parallax:.2f}) tespit edilemedi."
                ),
                hint="Olduğunuz yerde durarak çekim yapmayın; aracın etrafında 360 derece tam bir daire çizerek yürüyün.",
                details={
                    "mean_parallax": round(mean_parallax, 3),
                    "min_parallax_score": ctx.config.min_parallax_score,
                },
            )

        # Eğer paralaks filtresi çok agresif davranıp sayıyı MIN_FRAME_COUNT altına düşürdüyse,
        # ancak elimizde yeterince keskin kare varsa keskin kare havuzundan homojen örnekleme yap.
        usable_pool = parallax_filtered if len(parallax_filtered) >= ctx.config.min_frame_count else [
            (p, s) for p, s, _ in sharp_frames
        ]

        if len(usable_pool) < ctx.config.min_frame_count:
            shutil.rmtree(candidates_dir, ignore_errors=True)
            raise StepError(
                step=self.step_id,
                code="TOO_FEW_FRAMES",
                message=(
                    f"Bulanıklık elemesi sonrasında yalnızca {len(usable_pool)} net kare kaldı "
                    f"(minimum {ctx.config.min_frame_count} gerekli)."
                ),
                hint="Aracın etrafında daha yavaş yürüyerek ve kamerayı titretmeden daha uzun bir video çekin.",
                details={
                    "usable_frames": len(usable_pool),
                    "min_frame_count": ctx.config.min_frame_count,
                    "blur_rejected_count": blur_rejected_count,
                },
            )

        # 3. TARGET_FRAME_COUNT sınırına kadar zaman ekseninde eşit aralıklı (uniform stride) seçim yap
        target_n = min(len(usable_pool), ctx.config.target_frame_count)
        indices = np.linspace(0, len(usable_pool) - 1, num=target_n, dtype=int)
        selected_entries = [usable_pool[idx] for idx in dict.fromkeys(indices)]

        selected_records: List[Dict[str, Any]] = []
        for out_idx, (src_path, sharpness_val) in enumerate(selected_entries):
            dest_name = f"frame_{out_idx:04d}.jpg"
            dest_path = raw_frames_dir / dest_name
            shutil.copy2(src_path, dest_path)
            selected_records.append(
                {
                    "frame_index": out_idx,
                    "file_name": dest_name,
                    "sharpness": round(sharpness_val, 2),
                }
            )

        # Geçici aday klasörünü sil (disk tasarrufu)
        shutil.rmtree(candidates_dir, ignore_errors=True)

        mean_sharpness = float(np.mean([r["sharpness"] for r in selected_records]))
        report_data = {
            "total_candidates": total_candidates,
            "blur_rejected_count": blur_rejected_count,
            "selected_frame_count": len(selected_records),
            "mean_sharpness": round(mean_sharpness, 2),
            "mean_parallax_score": round(mean_parallax, 3),
            "frames": selected_records,
        }
        report_path = step_dir / "extraction_report.json"
        report_path.write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")

        ctx.logger.info(
            "Kare çıkarma tamamlandı: %d aday -> %d bulanık elendi -> %d net anahtar kare seçildi (ort. keskinlik=%.1f).",
            total_candidates,
            blur_rejected_count,
            len(selected_records),
            mean_sharpness,
        )

        return StepResult(
            status="done",
            artifacts={
                "raw_frames_dir": str(raw_frames_dir),
                "extraction_report": str(report_path),
            },
            metrics={
                "total_candidates": total_candidates,
                "blur_rejected_count": blur_rejected_count,
                "selected_frame_count": len(selected_records),
                "mean_sharpness": round(mean_sharpness, 2),
                "mean_parallax_score": round(mean_parallax, 3),
            },
            summary=f"{len(selected_records)} net anahtar kare çıkarıldı ({blur_rejected_count} bulanık kare elendi).",
        )
