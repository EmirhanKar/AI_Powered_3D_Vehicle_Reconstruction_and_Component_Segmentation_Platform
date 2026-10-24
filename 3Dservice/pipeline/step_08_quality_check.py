"""
Adım 08: Nihai Kalite Kontrolü ve Çekim İpucu Üretimi (`step_08_quality_check.py`).

Amaç:
    Önceki adımlardan gelen tüm metrikleri (`pose_report`, `recon_metrics`,
    `mesh_metrics`, `texture_metrics`) tek bir `quality_report.json` dosyasında
    toplar ve genel bir karar (`verdict`: `"pass"`, `"warn"` veya `"fail"`) ile
    kullanıcıya yönelik Türkçe yeniden çekim tavsiyesi (`retake_hint`) üretir.

Kalite Kapısı Kuralları:
    - Kayıt oranı (`registration_rate`) < `MIN_REGISTRATION_RATE` veya
      PSNR < `MIN_PSNR` veya yüz sayısı < 12 veya sınır kutusu bozuksa -> `"fail"`
      (ve `QUALITY_GATE_FAILED` hatası fırlatılır).
    - `front_confidence < 0.55` (ön/arka yön belirsizliği) veya `is_watertight == False`
      veya `lpips > 0.25` ise -> `"warn"` (işlem devam eder ancak raporda uyarı ve
      ipucu yer alır).
    - Tüm göstergeler sağlıklıysa -> `"pass"`.

Girdiler (requires):
    - `pose_report`: Adım 04 poz tahmini metrikleri.
    - `recon_metrics`: Adım 05 PSNR/LPIPS rekonstrüksiyon metrikleri.
    - `mesh_metrics`: Adım 06 mesh, sınır kutusu, ölçek ve `front_confidence` metrikleri.
    - `texture_metrics`: Adım 07 UV ve doku metrikleri.

Çıktılar (produces):
    - `quality_report`: `08_quality_check/quality_report.json` dosyasının yolu.

Tipik Hata Durumları ve Kodları:
    - `QUALITY_GATE_FAILED`: Birleştirilmiş kalite değerlendirmesi `"fail"` kararı verdi.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from pipeline.base import PipelineContext, Step, StepResult
from pipeline.errors import StepError


class Step08QualityCheck(Step):
    """Tüm metrikleri denetleyip `pass`/`warn`/`fail` kararı ve Türkçe ipucu üreten adım."""

    name = "quality_check"
    order = 8
    requires = ("pose_report", "recon_metrics", "mesh_metrics", "texture_metrics")
    produces = ("quality_report",)

    def run(self, ctx: PipelineContext) -> StepResult:
        step_dir = self.prepare_step_dir(ctx)

        pose_data: Dict[str, Any] = json.loads(ctx.get_artifact_path("pose_report").read_text(encoding="utf-8"))
        recon_data: Dict[str, Any] = json.loads(ctx.get_artifact_path("recon_metrics").read_text(encoding="utf-8"))
        mesh_data: Dict[str, Any] = json.loads(ctx.get_artifact_path("mesh_metrics").read_text(encoding="utf-8"))
        tex_data: Dict[str, Any] = json.loads(ctx.get_artifact_path("texture_metrics").read_text(encoding="utf-8"))

        registration_rate = float(pose_data.get("registration_rate", 0.0))
        psnr = float(recon_data.get("psnr", 0.0))
        lpips = float(recon_data.get("lpips", 1.0))
        face_count = int(mesh_data.get("face_count", 0))
        is_watertight = bool(mesh_data.get("is_watertight", False))
        wheel_base_y = float(mesh_data.get("wheel_base_y", 0.0))
        bbox_extents: List[float] = list(mesh_data.get("bbox_extents", [0.0, 0.0, 0.0]))
        meters_per_unit = float(mesh_data.get("meters_per_unit", 4.5))
        scale_known = bool(mesh_data.get("scale_known", False))
        front_confidence = float(mesh_data.get("front_confidence", 0.5))

        failures: List[str] = []
        warnings: List[str] = []
        hints: List[str] = []

        # 1. Kritik Başarısızlık (Fail) Denetimleri
        if registration_rate < ctx.config.min_registration_rate:
            failures.append(
                f"Kamera kayıt oranı çok düşük (%{registration_rate * 100:.1f} < %{ctx.config.min_registration_rate * 100:.0f})."
            )
            hints.append("Aracın etrafında kopukluk olmadan tam bir daire çizerek yürüyün.")

        if psnr < ctx.config.min_psnr:
            failures.append(f"PSNR görüntü kalitesi sınırın altında ({psnr:.2f} dB < {ctx.config.min_psnr:.2f} dB).")
            hints.append("Hareket bulanıklığını önlemek için daha yavaş yürüyün ve doğrudan güneş parlamasından kaçının.")

        if face_count < 12 or any(ext <= 1e-4 for ext in bbox_extents):
            failures.append(f"Üretilen 3B mesh geometrisi bozuk veya yetersiz (face_count={face_count}, extents={bbox_extents}).")
            hints.append("Aracın tamamının kadraj içinde kaldığından emin olarak tekrar çekim yapın.")

        if abs(wheel_base_y) > 0.05:
            failures.append(f"Tekerlek tabanı zemin düzlemine (y=0) tam oturmadı (wheel_base_y={wheel_base_y:.4f}).")
            hints.append("Çekim sırasında aracın alt kısmının ve tekerleklerin zemine değdiği noktaların görünmesini sağlayın.")

        # 2. Uyarı (Warn) Denetimleri (Karar 2c: Ön/arka yön belirsizliği dahil)
        if front_confidence < 0.55:
            warnings.append(
                f"Aracın ön/arka yön güven skoru düşük (front_confidence={front_confidence:.3f}). "
                "Uzun eksen +Z'ye hizalandı ancak ön/arka yönü simetrik gövde nedeniyle belirsiz olabilir."
            )
            hints.append("Aracın ön kaput ve far bölgesini çekim başında birkaç saniye daha net görüntüleyin.")

        if not is_watertight:
            warnings.append("Mesh tam su geçirmez (watertight) değil; alt şasi görünmeyen bölgelerde açık kenarlar içeriyor.")

        if lpips > 0.25:
            warnings.append(f"Algısal doku bulanıklığı (LPIPS={lpips:.3f}) ideal seviyenin üzerinde.")
            hints.append("Daha keskin dokular için 4K/1080p çözünürlükte ve iyi aydınlatmada çekim yapın.")

        if failures:
            verdict = "fail"
        elif warnings:
            verdict = "warn"
        else:
            verdict = "pass"

        retake_hint = (
            " ".join(dict.fromkeys(hints))
            if hints
            else "Çekim kalitesi ideal; yeniden çekim gerekmiyor."
        )

        quality_report = {
            "verdict": verdict,
            "retake_hint": retake_hint,
            "failures": failures,
            "warnings": warnings,
            "metrics": {
                "registration_rate": round(registration_rate, 4),
                "psnr": round(psnr, 3),
                "lpips": round(lpips, 4),
                "face_count": face_count,
                "is_watertight": is_watertight,
                "wheel_base_y": round(wheel_base_y, 6),
                "bbox_extents": bbox_extents,
                "meters_per_unit": meters_per_unit,
                "scale_known": scale_known,
                "front_confidence": front_confidence,
                "texture_size": tex_data.get("texture_size"),
            },
        }

        report_path = step_dir / "quality_report.json"
        report_path.write_text(json.dumps(quality_report, indent=2, ensure_ascii=False), encoding="utf-8")

        if verdict == "fail":
            raise StepError(
                step=self.step_id,
                code="QUALITY_GATE_FAILED",
                message="3B model kalite kontrolünden geçemedi: " + " | ".join(failures),
                hint=retake_hint,
                details=quality_report,
            )

        ctx.logger.info(
            "Kalite kontrolü tamamlandı: karar=%s, uyarı_sayısı=%d, front_confidence=%.3f.",
            verdict.upper(),
            len(warnings),
            front_confidence,
        )

        return StepResult(
            status="done",
            artifacts={"quality_report": str(report_path)},
            metrics={
                "verdict": verdict,
                "warning_count": len(warnings),
                "front_confidence": front_confidence,
                "psnr": round(psnr, 3),
                "registration_rate": round(registration_rate, 4),
            },
            summary=f"Kalite kontrolü tamamlandı (karar={verdict.upper()}, uyarı={len(warnings)}).",
        )
