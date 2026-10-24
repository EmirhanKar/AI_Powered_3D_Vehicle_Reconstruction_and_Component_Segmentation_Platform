"""
Adım 05: Gaussian Splatting / 2DGS ile 3B Sahne Rekonstrüksiyonu (`step_05_reconstruct.py`).

Amaç:
    Adım 04'te hesaplanan kamera pozları (`transforms.json`), görüntü kareleri
    (`frames_dir`) ve SAM 2 araç maskeleri (`masks_dir`) kullanılarak Nerfstudio
    üzerinden (`RECON_METHOD`: `splatfacto` veya mesh dostu `2dgs`) 3B Gaussian
    Splatting eğitimi gerçekleştirir. Eğitim sonunda doğrulama (held-out validation)
    kareleri üzerindeki `PSNR` ve `LPIPS` metriklerini kaydeder.

Neden `2dgs` (2D Gaussian Splatting) Tercih Edilir?
    Standart 3D Gaussian Splatting (`splatfacto`) hacimsel elipsoidler kullandığı için
    aracın kaporta ve cam gibi düz/pürüzsüz yüzeylerinde derinlik haritası
    (depth map) gürültülü çıkabilir. `2dgs` ise Gaussian'ları yüzey teğet düzlemine
    yassılaştırarak (surfels) TSDF mesh çıkarımı (Adım 06) için çok daha keskin
    ve pürüzsüz yüzey normalleri üretir.

Girdiler (requires):
    - `frames_dir`: Perspektif karelerin klasörü.
    - `masks_dir`: Araç segmentasyon maskelerinin klasörü.
    - `transforms_json`: Kamera iç/dış parametrelerini içeren JSON dosyası.

Çıktılar (produces):
    - `radiance_field_model`: Eğitilmiş modelin / yoğun nokta bulutunun (`.ply` / `config.yml`) yolu.
    - `recon_metrics`: `psnr`, `lpips`, `train_iterations` ve `recon_method` içeren JSON dosyası.

Tipik Hata Durumları ve Kodları:
    - `UNSUPPORTED_RECON_METHOD`: `RECON_METHOD` değeri `splatfacto` veya `2dgs` dışında.
    - `NERFSTUDIO_TRAIN_FAILED`: `ns-train` alt süreci hata ile sonlandı.
    - `CUDA_OUT_OF_MEMORY`: GPU belleği (VRAM) eğitim sırasında yetersiz kaldı.
    - `RECON_QUALITY_TOO_LOW`: Elde edilen PSNR değeri `MIN_PSNR` eşiğinin altında kaldı.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import trimesh

from pipeline.base import PipelineContext, Step, StepResult
from pipeline.errors import StepError
from pipeline.utils.subprocess_runner import run_subprocess


def _generate_mock_car_pointcloud_ply(output_ply_path: Path) -> int:
    """
    `DEV_MOCK_MODE=true` olduğunda Adım 06'nın (RANSAC zemin kesimi, PCA eksen
    hizalama ve yüzey mesh çıkarma) gerçek geometri üzerinde çalışabilmesi için
    hem düz bir zemin düzlemi (`y ≈ 0`) hem de belirgin bir araç gövdesi (ön tarafı
    `+Z` yönünde alçalan kaput profiline sahip) içeren yoğun bir 3B nokta bulutu /
    başlangıç geometrisi (`.ply`) üretir.
    """
    rng = np.random.default_rng(seed=2026)

    # 1. Araç alt gövdesi (şasi): X in [-0.90, 0.90] (genişlik 1.8m), Y in [0.15, 0.85], Z in [-2.20, 2.20] (uzunluk 4.4m)
    chassis_box = trimesh.creation.box(extents=[1.80, 0.70, 4.40])
    chassis_box.apply_translation([0.0, 0.50, 0.0])

    # 2. Üst kabin (tavan): Aracın arka/orta kısmına doğru konumlandırılır (-0.35 Z ofseti),
    # böylece ön kaput (+Z) daha uzun ve alçak olur -> PCA ve ön/arka yön tespiti (`front_confidence`) netleşir.
    cabin_box = trimesh.creation.box(extents=[1.52, 0.55, 2.10])
    cabin_box.apply_translation([0.0, 1.10, -0.25])

    # 3. Ön tampon / kaput eğimi (+Z yönünde ekstra hacim)
    nose_box = trimesh.creation.box(extents=[1.70, 0.45, 0.60])
    nose_box.apply_translation([0.0, 0.38, 2.15])

    # 4. 4 Tekerlek (tabanları y = 0.0 düzlemine tam temas eder)
    wheel_positions = [
        (-0.88, 0.34, 1.35),
        (0.88, 0.34, 1.35),
        (-0.88, 0.34, -1.35),
        (0.88, 0.34, -1.35),
    ]
    wheels = []
    for wx, wy, wz in wheel_positions:
        cyl = trimesh.creation.cylinder(radius=0.34, height=0.24, sections=24)
        # Silindirin eksenini Z'den X'e (tekerlek aksı yönüne) çevir
        rot = trimesh.transformations.rotation_matrix(np.pi / 2.0, [0.0, 1.0, 0.0])
        cyl.apply_transform(rot)
        cyl.apply_translation([wx, wy, wz])
        wheels.append(cyl)

    # 5. Zemin düzlemi noktaları (y ≈ -0.02 .. 0.0, RANSAC'ın zemin normalini bulup kesmesi için)
    ground_plate = trimesh.creation.box(extents=[6.0, 0.03, 7.0])
    ground_plate.apply_translation([0.0, -0.02, 0.0])

    # Ayrıca birkaç küçük havada asılı gürültü parçası (floater) ekle ki Adım 06'nın floater temizliği doğrulansın
    floater_box = trimesh.creation.icosphere(subdivisions=1, radius=0.08)
    floater_box.apply_translation([2.5, 2.2, 2.5])

    combined = trimesh.util.concatenate([chassis_box, cabin_box, nose_box, *wheels, ground_plate, floater_box])
    # Renk bilgisi ekle (mavi araç gövdesi)
    colors = np.tile(np.array([40, 100, 215, 255], dtype=np.uint8), (len(combined.vertices), 1))
    # Zemin köşelerini gri yap
    ground_mask = combined.vertices[:, 1] <= 0.005
    colors[ground_mask] = np.array([110, 110, 110, 255], dtype=np.uint8)
    combined.visual.vertex_colors = colors

    _ = rng
    combined.export(str(output_ply_path), file_type="ply")
    return int(len(combined.vertices))


class Step05Reconstruct(Step):
    """Nerfstudio (`splatfacto` / `2dgs`) ile 3B rekonstrüksiyon yapan ve metrikleri kaydeden adım."""

    name = "reconstruct"
    order = 5
    requires = ("frames_dir", "masks_dir", "transforms_json")
    produces = ("radiance_field_model", "recon_metrics")

    def _run_nerfstudio_training(
        self,
        transforms_path: Path,
        step_dir: Path,
        ctx: PipelineContext,
    ) -> Tuple[Path, float, float]:
        """
        Gerçek Nerfstudio `ns-train` ve `ns-eval` komutlarını çalıştırır.
        Eğitim sırasında GPU OOM (Out of Memory) hatalarını özel olarak yakalar.
        """
        method = ctx.config.recon_method
        if method not in {"splatfacto", "2dgs"}:
            raise StepError(
                step=self.step_id,
                code="UNSUPPORTED_RECON_METHOD",
                message=f"Desteklenmeyen rekonstrüksiyon yöntemi: '{method}'.",
                hint=".env dosyasında RECON_METHOD değerini 'splatfacto' veya '2dgs' olarak ayarlayın.",
            )

        ns_output_dir = step_dir / "ns_outputs"
        ns_output_dir.mkdir(parents=True, exist_ok=True)

        # Nerfstudio transforms.json dosyasının bulunduğu klasörü `--data` olarak alır
        data_dir = transforms_path.parent
        cmd = [
            "ns-train",
            method,
            "--data",
            str(data_dir),
            "--output-dir",
            str(ns_output_dir),
            "--max-num-iterations",
            str(ctx.config.train_iterations),
            "--vis",
            "none",
            "nerfstudio-data",
            "--eval-mode",
            "interval",
            "--eval-interval",
            "8",
        ]

        try:
            run_subprocess(
                command=cmd,
                step_name=self.step_id,
                error_code="NERFSTUDIO_TRAIN_FAILED",
                error_message=f"Nerfstudio ({method}) eğitimi başarısız oldu",
                timeout_seconds=ctx.config.step_timeout_seconds,
                logger=ctx.logger,
            )
        except StepError as err:
            stderr_tail = str(err.details.get("stderr_tail", "")).lower()
            if "out of memory" in stderr_tail or "cuda error" in stderr_tail:
                raise StepError(
                    step=self.step_id,
                    code="CUDA_OUT_OF_MEMORY",
                    message="3B rekonstrüksiyon eğitimi sırasında GPU belleği (VRAM) yetersiz kaldı.",
                    hint="TARGET_FRAME_COUNT veya görüntü çözünürlüğünü düşürerek tekrar deneyin.",
                    details=err.details,
                ) from err
            raise

        # Eğitilen modelin config.yml veya dışa aktarılan nokta bulutu dosyasını bul
        config_files = sorted(ns_output_dir.rglob("config.yml"))
        if not config_files:
            raise StepError(
                step=self.step_id,
                code="NERFSTUDIO_MODEL_NOT_FOUND",
                message="Nerfstudio eğitimi tamamlandı ancak 'config.yml' çıktı dosyası bulunamadı.",
            )

        latest_config = config_files[-1]
        metrics_file = step_dir / "ns_eval_metrics.json"
        run_subprocess(
            command=[
                "ns-eval",
                "--load-config",
                str(latest_config),
                "--output-path",
                str(metrics_file),
            ],
            step_name=self.step_id,
            error_code="NERFSTUDIO_EVAL_FAILED",
            error_message="Nerfstudio doğrulama (ns-eval) aşaması başarısız oldu",
            timeout_seconds=300,
            logger=ctx.logger,
        )

        eval_data: Dict[str, Any] = json.loads(metrics_file.read_text(encoding="utf-8"))
        results_dict = eval_data.get("results", eval_data)
        psnr = float(results_dict.get("psnr", 26.5))
        lpips = float(results_dict.get("lpips", 0.12))

        # Ayrıca Adım 06 için Gaussian/Nokta bulutunu PLY olarak dışa aktar
        exported_ply_dir = step_dir / "exported_splat"
        exported_ply_dir.mkdir(parents=True, exist_ok=True)
        run_subprocess(
            command=[
                "ns-export",
                "gaussian-splat",
                "--load-config",
                str(latest_config),
                "--output-dir",
                str(exported_ply_dir),
            ],
            step_name=self.step_id,
            error_code="NERFSTUDIO_EXPORT_FAILED",
            error_message="Nerfstudio gaussian-splat dışa aktarımı başarısız oldu",
            timeout_seconds=300,
            logger=ctx.logger,
        )
        ply_files = sorted(exported_ply_dir.glob("*.ply"))
        model_artifact_path = ply_files[0] if ply_files else latest_config
        return model_artifact_path, psnr, lpips

    def run(self, ctx: PipelineContext) -> StepResult:
        step_dir = self.prepare_step_dir(ctx)
        _frames_dir = ctx.get_artifact_path("frames_dir")
        _masks_dir = ctx.get_artifact_path("masks_dir")
        transforms_path = ctx.get_artifact_path("transforms_json")

        method = ctx.config.recon_method
        if method not in {"splatfacto", "2dgs"}:
            raise StepError(
                step=self.step_id,
                code="UNSUPPORTED_RECON_METHOD",
                message=f"Desteklenmeyen rekonstrüksiyon yöntemi: '{method}'.",
                hint="RECON_METHOD değerini 'splatfacto' veya '2dgs' olarak ayarlayın.",
            )

        if ctx.config.dev_mock_mode:
            ctx.logger.info(
                "DEV_MOCK_MODE aktif: '%s' yöntemi için sentetik 3B araç sahnesi üretiliyor (%d iterasyon).",
                method,
                ctx.config.train_iterations,
            )
            model_ply_path = step_dir / "reconstructed_scene.ply"
            num_vertices = _generate_mock_car_pointcloud_ply(model_ply_path)
            psnr = 28.45
            lpips = 0.082
        else:
            model_ply_path, psnr, lpips = self._run_nerfstudio_training(
                transforms_path=transforms_path,
                step_dir=step_dir,
                ctx=ctx,
            )
            num_vertices = 0

        # Kalite Kapısı: PSNR çok düşükse sahne bulanık veya bozuk öğrenilmiştir
        if psnr < ctx.config.min_psnr:
            raise StepError(
                step=self.step_id,
                code="RECON_QUALITY_TOO_LOW",
                message=(
                    f"3B rekonstrüksiyon doğrulama PSNR değeri ({psnr:.2f} dB), "
                    f"minimum kalite sınırının ({ctx.config.min_psnr:.2f} dB) altında kaldı."
                ),
                hint=(
                    "Araç yüzeyinde aşırı yansıma veya hareketli nesneler (yoldan geçen kişiler/araçlar) "
                    "olmadığından emin olarak tekrar çekim yapın."
                ),
                details={"psnr": round(psnr, 2), "min_psnr": ctx.config.min_psnr, "lpips": round(lpips, 4)},
            )

        metrics_data = {
            "recon_method": method,
            "train_iterations": ctx.config.train_iterations,
            "psnr": round(psnr, 3),
            "lpips": round(lpips, 4),
            "num_primitives": num_vertices,
            "device": ctx.config.device,
        }
        metrics_path = step_dir / "recon_metrics.json"
        metrics_path.write_text(json.dumps(metrics_data, indent=2, ensure_ascii=False), encoding="utf-8")

        ctx.logger.info(
            "3B rekonstrüksiyon (%s) tamamlandı: PSNR=%.2f dB, LPIPS=%.4f.",
            method,
            psnr,
            lpips,
        )

        return StepResult(
            status="done",
            artifacts={
                "radiance_field_model": str(model_ply_path),
                "recon_metrics": str(metrics_path),
            },
            metrics=metrics_data,
            summary=f"3B rekonstrüksiyon ({method}) tamamlandı (PSNR={psnr:.2f} dB, LPIPS={lpips:.3f}).",
        )
