"""
ModifAI 3D Servisi — Pipeline Orkestratörü ve Durum (State) Yöneticisi.

Bu modül:
1. 00..09 adımlarını sırasıyla çalıştırır.
2. Her adımdan önce `requires` (girdi artefaktları) ve her adımdan sonra
   `produces` (çıktı artefaktları) sözleşmesini zorunlu olarak denetler.
3. Her adımın başlangıç/bitiş zamanını, süresini, durumunu (`pending`, `running`,
   `done`, `skipped`, `failed`), metriklerini ve olası `StepError` detaylarını
   `jobs/<job_id>/state.json` dosyasına atomik olarak yazar.
4. Başarısız olmuş bir işi kaldığı adımdan (`resume` veya `from_step`) önceki
   adımları tekrarlamadan devam ettirme yeteneği sunar.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Sequence

from config import ServiceConfig, settings
from pipeline.base import PipelineContext, Step, StepResult
from pipeline.errors import StepError
from pipeline.utils.logging_utils import close_logger_handlers, setup_step_logger


def _utc_now_iso() -> str:
    """UTC zaman damgasını ISO-8601 formatında döndürür."""
    return datetime.now(timezone.utc).isoformat()


def get_default_steps() -> List[Step]:
    """
    Standart 00..09 video-tabanlı 3B rekonstrüksiyon adımlarını sırasıyla yükler.
    Döngüsel (circular) import oluşmaması için fonksiyon içinde import edilir.
    """
    from pipeline.step_00_validate_input import Step00ValidateInput
    from pipeline.step_01_extract_frames import Step01ExtractFrames
    from pipeline.step_02_reproject_360 import Step02Reproject360
    from pipeline.step_03_segment_car import Step03SegmentCar
    from pipeline.step_04_estimate_poses import Step04EstimatePoses
    from pipeline.step_05_reconstruct import Step05Reconstruct
    from pipeline.step_06_extract_mesh import Step06ExtractMesh
    from pipeline.step_07_texture import Step07Texture
    from pipeline.step_08_quality_check import Step08QualityCheck
    from pipeline.step_09_export import Step09Export

    steps: List[Step] = [
        Step00ValidateInput(),
        Step01ExtractFrames(),
        Step02Reproject360(),
        Step03SegmentCar(),
        Step04EstimatePoses(),
        Step05Reconstruct(),
        Step06ExtractMesh(),
        Step07Texture(),
        Step08QualityCheck(),
        Step09Export(),
    ]
    return sorted(steps, key=lambda s: s.order)


class PipelineOrchestrator:
    """
    İş dizinini (`jobs/<job_id>/`), `state.json` kalıcılığını ve adımların
    güvenli yürütülmesini yöneten ana orkestratör sınıfı.
    """

    def __init__(
        self,
        config: Optional[ServiceConfig] = None,
        steps: Optional[Sequence[Step]] = None,
    ) -> None:
        self.config: ServiceConfig = config or settings
        self._steps: List[Step] = list(steps) if steps is not None else get_default_steps()

    @property
    def steps(self) -> List[Step]:
        return self._steps

    def get_job_dir(self, job_id: str) -> Path:
        return self.config.jobs_dir / job_id

    def get_state_path(self, job_id: str) -> Path:
        return self.get_job_dir(job_id) / "state.json"

    def load_state(self, job_id: str) -> Dict[str, Any]:
        """İşin mevcut `state.json` dosyasını okur; yoksa hata fırlatır."""
        state_path = self.get_state_path(job_id)
        if not state_path.exists():
            raise FileNotFoundError(f"İş durumu bulunamadı: {state_path}")
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_state(self, job_id: str, state: Dict[str, Any]) -> None:
        """
        `state.json` dosyasını yarım yazılmalara (torn writes) karşı önce geçici
        dosyaya yazıp ardından atomik olarak değiştirerek günceller.
        """
        job_dir = self.get_job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        state["updated_at"] = _utc_now_iso()
        state_path = self.get_state_path(job_id)
        tmp_path = state_path.with_suffix(".json.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        tmp_path.replace(state_path)

    def initialize_job(
        self,
        job_id: str,
        initial_artifacts: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Yeni bir iş (job) için çalışma klasörünü ve başlangıç `state.json`
        kaydını oluşturur. Eğer `state.json` zaten varsa mevcut durumu koruyarak
        yeni başlangıç artefaktlarını birleştirir.
        """
        job_dir = self.get_job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "logs").mkdir(parents=True, exist_ok=True)

        state_path = self.get_state_path(job_id)
        if state_path.exists():
            state = self.load_state(job_id)
            state.setdefault("artifacts", {}).update(initial_artifacts)
            if metadata:
                state.setdefault("metadata", {}).update(metadata)
            self.save_state(job_id, state)
            return state

        steps_state: Dict[str, Any] = {}
        for step in self._steps:
            steps_state[step.step_id] = {
                "step_id": step.step_id,
                "name": step.name,
                "order": step.order,
                "status": "pending",
                "started_at": None,
                "ended_at": None,
                "duration_seconds": None,
                "summary": "",
                "metrics": {},
                "error": None,
            }

        now = _utc_now_iso()
        state = {
            "job_id": job_id,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "current_step": None,
            "failed_step": None,
            "error": None,
            "progress": 0,
            "metadata": metadata or {},
            "artifacts": dict(initial_artifacts),
            "steps": steps_state,
        }
        self.save_state(job_id, state)
        return state

    def _verify_requires(self, step: Step, ctx: PipelineContext) -> None:
        """
        Adım başlamadan önce `step.requires` içindeki tüm artefakt anahtarlarının
        bağlamda (`ctx.artifacts`) bulunduğunu ve dosya/klasör yollarıysa diskte
        gerçekten var olduğunu denetler.
        """
        missing_keys: List[str] = []
        missing_files: List[str] = []

        for req_key in step.requires:
            if req_key not in ctx.artifacts or ctx.artifacts[req_key] is None:
                missing_keys.append(req_key)
                continue

            val = ctx.artifacts[req_key]
            # Eğer artefakt bir dosya veya klasör yolunu temsil ediyorsa diskte varlığını kontrol et
            if isinstance(val, (str, Path)):
                str_val = str(val)
                if ("/" in str_val or "\\" in str_val or str_val.endswith((".mp4", ".json", ".ply", ".obj", ".png", ".glb"))):
                    p = Path(str_val)
                    if not p.exists():
                        missing_files.append(f"{req_key} -> {p}")

        if missing_keys or missing_files:
            raise StepError(
                step=step.step_id,
                code="MISSING_REQUIRED_ARTIFACTS",
                message=(
                    f"'{step.step_id}' adımının çalışması için gereken girdi artefaktları eksik: "
                    f"anahtarlar={missing_keys}, bulunamayan_dosyalar={missing_files}"
                ),
                hint="Lütfen önce önceki adımları çalıştırarak gerekli girdi dosyalarının üretilmesini sağlayın.",
                details={"missing_keys": missing_keys, "missing_files": missing_files},
            )

    def _verify_produces(self, step: Step, result: StepResult, ctx: PipelineContext) -> None:
        """
        Adım tamamlandıktan sonra `step.produces` listesindeki tüm anahtarların
        üretildiğini ve karşılık gelen dosyaların diskte var olduğunu doğrular.
        Not: Eğer bir artefakt opsiyonel olarak `None` döndürülmüşse (ör. USDZ
        seçilmemişse), yalnızca seçili formatların varlığı zorunlu tutulur.
        """
        missing_keys: List[str] = []
        missing_paths: List[str] = []

        for prod_key in step.produces:
            if prod_key not in result.artifacts:
                missing_keys.append(prod_key)
                continue

            val = result.artifacts[prod_key]
            if val is None:
                # Opsiyonel çıktı (örneğin EXPORT_FORMATS içinde 'usdz' yoksa exported_usdz=None olabilir)
                continue

            if isinstance(val, (str, Path)):
                str_val = str(val)
                if ("/" in str_val or "\\" in str_val or str_val.endswith((".mp4", ".json", ".ply", ".obj", ".png", ".glb", ".usdz"))):
                    p = Path(str_val)
                    if not p.exists():
                        missing_paths.append(f"{prod_key} -> {p}")

        if missing_keys or missing_paths:
            raise StepError(
                step=step.step_id,
                code="MISSING_PRODUCED_ARTIFACTS",
                message=(
                    f"'{step.step_id}' adımı sözleşmede taahhüt ettiği çıktıları üretmedi: "
                    f"eksik_anahtarlar={missing_keys}, oluşmayan_dosyalar={missing_paths}"
                ),
                hint="Adım iç mantığında dosya yazma hatası oluştu; adım loglarını kontrol edin.",
                details={"missing_keys": missing_keys, "missing_paths": missing_paths},
            )

    def _compute_progress(self, state: Dict[str, Any]) -> int:
        """Tamamlanan veya atlanan adım sayısına göre 0-100 arası ilerleme yüzdesi hesaplar."""
        total = max(len(self._steps), 1)
        completed = sum(
            1
            for s in state.get("steps", {}).values()
            if s.get("status") in {"done", "skipped"}
        )
        return int(round((completed / total) * 100))

    def run_pipeline(
        self,
        job_id: str,
        from_step: Optional[int] = None,
        to_step: Optional[int] = None,
        resume: bool = False,
        progress_callback: Optional[Callable[[str, str, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Belirtilen aralıktaki (`from_step` .. `to_step`) adımları sırasıyla çalıştırır.

        Parametreler:
            job_id: İş kimliği (`jobs/<job_id>/`).
            from_step: Başlanacak adım numarası (dahil, ör. 4). None ise 0'dan başlar.
            to_step: Bitirilecek adım numarası (dahil, ör. 6). None ise son adıma kadar gider.
            resume: True ise, durumu zaten `done` veya `skipped` olan adımları atlar ve
                    ilk tamamlanmamış/başarısız adımdan devam eder.
            progress_callback: Her adım başında/sonunda `(step_id, message, progress_pct)` ile çağrılır.
        """
        state = self.load_state(job_id)
        job_dir = self.get_job_dir(job_id)

        state["status"] = "running"
        state["failed_step"] = None
        state["error"] = None
        self.save_state(job_id, state)

        ctx = PipelineContext(
            job_id=job_id,
            job_dir=job_dir,
            config=self.config,
            artifacts=state.setdefault("artifacts", {}),
            metadata=state.setdefault("metadata", {}),
        )

        # Çalıştırılacak adımları filtrele
        selected_steps: List[Step] = []
        for step in self._steps:
            if from_step is not None and step.order < from_step:
                continue
            if to_step is not None and step.order > to_step:
                continue
            if resume:
                existing_status = state["steps"].get(step.step_id, {}).get("status")
                if existing_status in {"done", "skipped"}:
                    continue
            selected_steps.append(step)

        for step in selected_steps:
            step_state = state["steps"].setdefault(
                step.step_id,
                {
                    "step_id": step.step_id,
                    "name": step.name,
                    "order": step.order,
                    "status": "pending",
                    "started_at": None,
                    "ended_at": None,
                    "duration_seconds": None,
                    "summary": "",
                    "metrics": {},
                    "error": None,
                },
            )

            step_logger = setup_step_logger(
                job_id=job_id,
                step_order=step.order,
                step_name=step.name,
                job_dir=job_dir,
                log_level=self.config.log_level,
            )

            ctx.logger = step_logger
            ctx.current_step_name = step.step_id
            ctx.current_allowed_requires = step.requires

            start_ts = time.perf_counter()
            step_state["status"] = "running"
            step_state["started_at"] = _utc_now_iso()
            step_state["ended_at"] = None
            step_state["duration_seconds"] = None
            step_state["error"] = None
            state["current_step"] = step.step_id
            self.save_state(job_id, state)

            if progress_callback:
                progress_callback(step.step_id, f"{step.step_id} çalışıyor...", self._compute_progress(state))

            try:
                step_logger.info("=== Adım Başladı: %s ===", step.step_id)
                step_logger.info("Beklenen girdiler (requires): %s", list(step.requires))

                # 1. Sözleşme kontrolü: Girdi artefaktları mevcut mu?
                self._verify_requires(step, ctx)

                # 2. Adımı çalıştır
                result: StepResult = step.run(ctx)

                # 3. Sözleşme kontrolü: Çıktı artefaktları üretildi mi?
                self._verify_produces(step, result, ctx)

                # 4. Üretilen artefaktları bağlama ve state.json'a kaydet
                for k, v in result.artifacts.items():
                    ctx.artifacts[k] = str(v) if isinstance(v, Path) else v

                duration = round(time.perf_counter() - start_ts, 3)
                final_step_status = result.status if result.status in {"done", "skipped"} else "done"

                step_state["status"] = final_step_status
                step_state["ended_at"] = _utc_now_iso()
                step_state["duration_seconds"] = duration
                step_state["summary"] = result.summary
                step_state["metrics"] = result.metrics
                state["progress"] = self._compute_progress(state)
                self.save_state(job_id, state)

                step_logger.info(
                    "=== Adım Tamamlandı: %s (durum=%s, süre=%.3fs) — %s ===",
                    step.step_id,
                    final_step_status,
                    duration,
                    result.summary,
                )

                if progress_callback:
                    progress_callback(step.step_id, result.summary or f"{step.step_id} tamamlandı.", state["progress"])

            except StepError as step_err:
                duration = round(time.perf_counter() - start_ts, 3)
                err_dict = step_err.to_dict()
                step_logger.error(
                    "Adım hatası [%s]: %s | İpucu: %s | Detaylar: %s",
                    step_err.code,
                    step_err.message,
                    step_err.hint,
                    json.dumps(step_err.details, ensure_ascii=False),
                )
                step_state["status"] = "failed"
                step_state["ended_at"] = _utc_now_iso()
                step_state["duration_seconds"] = duration
                step_state["error"] = err_dict

                state["status"] = "failed"
                state["failed_step"] = step.step_id
                state["error"] = err_dict
                self.save_state(job_id, state)
                raise

            except Exception as unexpected_exc:
                duration = round(time.perf_counter() - start_ts, 3)
                tb_str = traceback.format_exc()
                wrapped = StepError(
                    step=step.step_id,
                    code="UNEXPECTED_STEP_ERROR",
                    message=f"'{step.step_id}' adımında beklenmeyen çalışma zamanı hatası: {unexpected_exc}",
                    hint="Sistem yöneticisiyle iletişime geçin veya adım log dosyasını inceleyin.",
                    details={"exception_type": type(unexpected_exc).__name__, "traceback": tb_str[-1500:]},
                )
                err_dict = wrapped.to_dict()
                step_logger.error("Beklenmeyen hata:\n%s", tb_str)

                step_state["status"] = "failed"
                step_state["ended_at"] = _utc_now_iso()
                step_state["duration_seconds"] = duration
                step_state["error"] = err_dict

                state["status"] = "failed"
                state["failed_step"] = step.step_id
                state["error"] = err_dict
                self.save_state(job_id, state)
                raise wrapped from unexpected_exc

            finally:
                close_logger_handlers(step_logger)

        # Tüm adımlar tamamlandı mı kontrol et
        all_finished = all(
            s.get("status") in {"done", "skipped"}
            for s in state.get("steps", {}).values()
        )
        state["current_step"] = None
        state["progress"] = self._compute_progress(state)
        state["status"] = "done" if all_finished else "partial"
        self.save_state(job_id, state)
        return state
