"""
ModifAI 3D Servisi — Ana API Sunucusu ve Birleştirilmiş İş Koşturucusu (JobRunner).

Bu modül, `3Dservice/` dizini içerisinden doğrudan çalıştırılan giriş noktasıdır:
    uvicorn service:app --host 0.0.0.0 --port 8001

Mimari Özellikler:
1. Tekil İş Koşturucusu (`JobRunner`): Hem doğrudan HTTP `POST /jobs` çağrıları
   hem de `backend_poller.py` üzerinden gelen işler aynı `asyncio.Queue` ve
   `Semaphore(MAX_CONCURRENT_JOBS)` kontrollü GPU işçisini (worker) kullanır.
2. Mevcut Backend Uyumu:
   - Kimlik doğrulama: `X-Admin-Key` (veya `X-API-Key`) başlığı ile `.env`
     içindeki `API_KEY` doğrulanır; yetkisiz isteklerde Backend ile aynı formatta
     `HTTP 403 {"detail": "Geçersiz veya eksik Admin API Key."}` döner.
   - Hata formatı: Hem FastAPI `detail` alanını hem de `failed_step`, `error_code`,
     `hint` ve `details` alanlarını içerir.
   - Statik dosyalar: GLB için `model/gltf-binary` MIME tipi tanımlıdır ve yerel
     çıktılar `/outputs` altından sunulur.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
import logging
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Security, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
import httpx
from pydantic import BaseModel, Field

from backend_poller import BackendPoller
from config import ServiceConfig, settings
from pipeline.errors import StepError
from pipeline.orchestrator import PipelineOrchestrator
from pipeline.utils.gpu_utils import collect_health_report

# Mevcut Backend (`Backend/app/main.py`) ile birebir aynı GLB/GLTF MIME tanımları
mimetypes.add_type("model/gltf-binary", ".glb")
mimetypes.add_type("model/gltf+json", ".gltf")

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("3dservice.api")

# ── Kimlik Doğrulama (Mevcut Backend `app/api/deps.py` ile uyumlu) ──
admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    x_admin_key: Optional[str] = Security(admin_key_header),
    x_api_key: Optional[str] = Security(api_key_header),
) -> str:
    """
    İstek başlığındaki `X-Admin-Key` veya `X-API-Key` anahtarını doğrular.
    Mevcut Backend `X-Admin-Key` kullandığı için öncelikli olarak onu kontrol eder.
    """
    provided = x_admin_key or x_api_key
    if not provided or provided != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Geçersiz veya eksik Admin API Key.",
        )
    return provided


# ── İstek / Yanıt Pydantic Şemaları ──


class JobCreateRequest(BaseModel):
    """JSON gövdesiyle iş oluşturma şeması (yerel video yolu veya URL ile)."""

    video_path: Optional[str] = Field(default=None, description="Sunucu üzerindeki yerel video dosyasının yolu")
    scan_id: Optional[int] = Field(default=None, description="Mevcut Backend'deki ilişkili tarama (scan) kimliği")
    car_name: Optional[str] = Field(default=None, description="Araç adı veya etiketi")
    callback_url: Optional[str] = Field(default=None, description="İş bittiğinde bildirim gönderilecek özel URL")
    from_step: Optional[int] = Field(default=None, description="Başlangıç adım numarası (opsiyonel)")
    to_step: Optional[int] = Field(default=None, description="Bitiş adım numarası (opsiyonel)")
    resume: bool = Field(default=False, description="Daha önce tamamlanmış adımları atlayarak devam et")


class JobCreateResponse(BaseModel):
    """İş kabul edildiğinde dönen yanıt şeması."""

    job_id: str
    status: str
    message: str
    scan_id: Optional[int] = None


class JobStatusResponse(BaseModel):
    """`GET /jobs/{job_id}` uç noktasının döndürdüğü ayrıntılı durum şeması."""

    job_id: str
    status: str
    progress: int = 0
    current_step: Optional[str] = None
    failed_step: Optional[str] = None
    error_code: Optional[str] = None
    detail: Optional[str] = None
    hint: Optional[str] = None
    error: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    steps: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


# ── Tekil Arka Plan İş Koşturucusu (Unified Job Runner) ──


class JobRunner:
    """
    Hem HTTP API'den hem de `BackendPoller`'dan gelen işleri tek bir kuyrukta
    toplayan ve `MAX_CONCURRENT_JOBS` sınırına göre GPU'da sırayla çalıştıran sınıf.
    """

    def __init__(self, config: ServiceConfig) -> None:
        self.config = config
        self.orchestrator = PipelineOrchestrator(config=config)
        self.queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(config.max_concurrent_jobs)
        self.workers: List[asyncio.Task[Any]] = []
        self.poller: Optional[BackendPoller] = None
        self.poller_task: Optional[asyncio.Task[Any]] = None

    async def start(self) -> None:
        """Arka plan işçi görevlerini ve etkinse Backend Poller'ı başlatır."""
        for idx in range(self.config.max_concurrent_jobs):
            task = asyncio.create_task(self._worker_loop(worker_id=idx))
            self.workers.append(task)

        if self.config.enable_backend_poller:
            self.poller = BackendPoller(config=self.config, enqueue_fn=self.enqueue_from_poller)
            self.poller_task = asyncio.create_task(self.poller.poll_forever())

    async def stop(self) -> None:
        """Tüm arka plan görevlerini güvenli bir şekilde durdurur."""
        if self.poller:
            self.poller.stop()
        if self.poller_task:
            self.poller_task.cancel()
        for w in self.workers:
            w.cancel()

    async def enqueue_from_poller(
        self,
        job_id: str,
        video_path: Path,
        metadata: Dict[str, Any],
    ) -> None:
        """`BackendPoller` tarafından bulunan yeni bir işi ortak kuyruğa ekler."""
        self.orchestrator.initialize_job(
            job_id=job_id,
            initial_artifacts={"input_video": str(video_path.resolve())},
            metadata=metadata,
        )
        await self.queue.put(
            {
                "job_id": job_id,
                "from_step": None,
                "to_step": None,
                "resume": False,
            }
        )

    async def enqueue_job(
        self,
        job_id: str,
        video_path: Path,
        metadata: Optional[Dict[str, Any]] = None,
        from_step: Optional[int] = None,
        to_step: Optional[int] = None,
        resume: bool = False,
    ) -> Dict[str, Any]:
        """HTTP API üzerinden gelen bir işi başlatır ve kuyruğa ekler."""
        state = self.orchestrator.initialize_job(
            job_id=job_id,
            initial_artifacts={"input_video": str(video_path.resolve())},
            metadata=metadata or {"source": "http_api"},
        )
        await self.queue.put(
            {
                "job_id": job_id,
                "from_step": from_step,
                "to_step": to_step,
                "resume": resume,
            }
        )
        return state

    async def _send_webhook_callback(self, callback_url: str, payload: Dict[str, Any]) -> None:
        """Yapılandırılmışsa iş bitiminde veya hatada `BACKEND_CALLBACK_URL` adresine POST gönderir."""
        if not callback_url:
            return
        headers = {"X-Admin-Key": self.config.api_key, "Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            for attempt in range(1, self.config.backend_max_retries + 1):
                try:
                    resp = await client.post(callback_url, json=payload, headers=headers, timeout=15.0)
                    if resp.status_code < 500:
                        return
                except Exception as exc:
                    logger.warning("Webhook callback hatası (%s, deneme %d): %s", callback_url, attempt, exc)
                await asyncio.sleep(min(2**attempt, 10))

    async def _worker_loop(self, worker_id: int) -> None:
        """Kuyruktan işleri çekip CPU/GPU iş parçacığında (`asyncio.to_thread`) çalıştıran döngü."""
        logger.info("GPU İşçi #%d hazır.", worker_id)
        loop = asyncio.get_running_loop()

        while True:
            try:
                item = await self.queue.get()
            except asyncio.CancelledError:
                break

            job_id: str = item["job_id"]
            from_step: Optional[int] = item.get("from_step")
            to_step: Optional[int] = item.get("to_step")
            resume: bool = bool(item.get("resume", False))

            async with self.semaphore:
                state = self.orchestrator.load_state(job_id)
                metadata = state.get("metadata", {})
                scan_id: Optional[int] = metadata.get("scan_id")
                callback_url: str = metadata.get("callback_url") or self.config.backend_callback_url

                def _progress_hook(step_id: str, msg: str, pct: int) -> None:
                    if scan_id is not None and self.poller is not None:
                        asyncio.run_coroutine_threadsafe(
                            self.poller.report_scan_progress(int(scan_id), step_id, msg, pct),
                            loop,
                        )

                try:
                    final_state = await asyncio.to_thread(
                        self.orchestrator.run_pipeline,
                        job_id,
                        from_step,
                        to_step,
                        resume,
                        _progress_hook,
                    )

                    # Eğer iş bir `scan_id` ile ilişkiliyse tamamlanan GLB dosyasını Backend'e yükle
                    if scan_id is not None and self.poller is not None:
                        glb_str = final_state.get("artifacts", {}).get("exported_glb")
                        if glb_str:
                            uploaded = await self.poller.upload_completed_glb(int(scan_id), Path(glb_str))
                            if not uploaded:
                                await self.poller.report_scan_failure(
                                    int(scan_id),
                                    failed_step="step_09_export",
                                    error_code="BACKEND_GLB_UPLOAD_FAILED",
                                    message="3D model üretildi ancak Backend'e yüklenemedi.",
                                    hint="Backend sunucusunun erişilebilir olduğundan emin olun.",
                                )

                    if callback_url:
                        await self._send_webhook_callback(
                            callback_url,
                            {
                                "job_id": job_id,
                                "scan_id": scan_id,
                                "status": "done",
                                "progress": 100,
                                "artifacts": final_state.get("artifacts", {}),
                            },
                        )

                except StepError as step_err:
                    logger.error("İş başarısız oldu (job_id=%s, step=%s, code=%s)", job_id, step_err.step, step_err.code)
                    if scan_id is not None and self.poller is not None:
                        await self.poller.report_scan_failure(
                            int(scan_id),
                            failed_step=step_err.step,
                            error_code=step_err.code,
                            message=step_err.message,
                            hint=step_err.hint,
                            details=step_err.details,
                        )
                    if callback_url:
                        await self._send_webhook_callback(
                            callback_url,
                            {
                                "job_id": job_id,
                                "scan_id": scan_id,
                                "status": "failed",
                                **step_err.to_dict(),
                            },
                        )
                except Exception as exc:
                    logger.exception("İş çalıştırılırken beklenmeyen hata (job_id=%s): %s", job_id, exc)
                finally:
                    self.queue.task_done()


job_runner = JobRunner(config=settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama başlangıcında iş kuyruğunu ve poller'ı başlatır, kapanışta durdurur."""
    await job_runner.start()
    yield
    await job_runner.stop()


app = FastAPI(
    title="MODIF-AI 3D Rekonstrüksiyon Servisi",
    description="Araç videosundan (normal veya 360°) temiz ve dokulu 3B GLB model üreten bağımsız mikroservis.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Yerel depolama çıktılarını `/outputs` altında statik olarak sun
settings.outputs_dir.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(settings.outputs_dir)), name="outputs")


# ── API Uç Noktaları (Endpoints) ──


@app.get("/health", tags=["Sistem"])
async def health_check() -> Dict[str, Any]:
    """
    FFmpeg, FFprobe, COLMAP, CUDA/GPU ve SAM 2 model ağırlıklarının sağlık
    durumunu kontrol eder.
    """
    report = collect_health_report(settings)
    report["queue_size"] = job_runner.queue.qsize()
    report["poller_enabled"] = settings.enable_backend_poller
    return report


@app.post(
    "/jobs",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Jobs"],
)
async def create_job(
    request: Request,
    video: Optional[UploadFile] = File(default=None),
    scan_id: Optional[int] = Form(default=None),
    car_name: Optional[str] = Form(default=None),
    callback_url: Optional[str] = Form(default=None),
    job_id: Optional[str] = Form(default=None),
    _api_key: str = Depends(verify_api_key),
) -> JobCreateResponse:
    """
    Yeni bir 3B rekonstrüksiyon işi başlatır ve hemen `job_id` döndürür.

    İki farklı çağrı biçimini destekler:
    1. `multipart/form-data`: `video` dosyası doğrudan yüklenir.
    2. `application/json`: `{"video_path": "...", "scan_id": 123, ...}` gövdesi gönderilir.
    """
    content_type = request.headers.get("content-type", "").lower()

    if "application/json" in content_type:
        body_data = await request.json()
        req_obj = JobCreateRequest.model_validate(body_data)
        assigned_job_id = body_data.get("job_id") or (
            f"scan_{req_obj.scan_id}" if req_obj.scan_id else f"job_{uuid.uuid4().hex[:10]}"
        )
        if not req_obj.video_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="JSON isteğinde 'video_path' alanı zorunludur.",
            )
        src_video = Path(req_obj.video_path).resolve()
        if not src_video.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Belirtilen video dosyası bulunamadı: {src_video}",
            )
        metadata = {
            "source": "http_json",
            "scan_id": req_obj.scan_id,
            "car_name": req_obj.car_name or "",
            "callback_url": req_obj.callback_url or "",
        }
        await job_runner.enqueue_job(
            job_id=assigned_job_id,
            video_path=src_video,
            metadata=metadata,
            from_step=req_obj.from_step,
            to_step=req_obj.to_step,
            resume=req_obj.resume,
        )
        return JobCreateResponse(
            job_id=assigned_job_id,
            status="pending",
            message="3D rekonstrüksiyon işi kuyruğa alındı.",
            scan_id=req_obj.scan_id,
        )

    # Multipart dosya yükleme akışı
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bir video dosyası ('video') yüklemeli veya JSON ile 'video_path' göndermelisiniz.",
        )

    assigned_job_id = job_id or (f"scan_{scan_id}" if scan_id else f"job_{uuid.uuid4().hex[:10]}")
    job_dir = settings.jobs_dir / assigned_job_id
    raw_input_dir = job_dir / "raw_input"
    raw_input_dir.mkdir(parents=True, exist_ok=True)

    original_name = Path(video.filename or "input_video.mp4").name
    saved_video_path = raw_input_dir / original_name
    content = await video.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Yüklenen video dosyası boş!")
    saved_video_path.write_bytes(content)

    metadata = {
        "source": "http_multipart",
        "scan_id": scan_id,
        "car_name": car_name or "",
        "callback_url": callback_url or "",
    }
    await job_runner.enqueue_job(
        job_id=assigned_job_id,
        video_path=saved_video_path,
        metadata=metadata,
    )
    return JobCreateResponse(
        job_id=assigned_job_id,
        status="pending",
        message="Video yüklendi ve 3D rekonstrüksiyon işi kuyruğa alındı.",
        scan_id=scan_id,
    )


@app.get("/jobs/{job_id}", response_model=JobStatusResponse, tags=["Jobs"])
async def get_job_status(
    job_id: str,
    _api_key: str = Depends(verify_api_key),
) -> JobStatusResponse:
    """
    Bir işin güncel durumunu, çalışan adımını, ilerleme yüzdesini (`progress`),
    başarısız olduysa hangi adımda (`failed_step`) ve hangi hata koduyla (`error_code`)
    durduğunu döndürür.
    """
    try:
        state = job_runner.orchestrator.load_state(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"'{job_id}' kimlikli iş bulunamadı.",
        ) from exc

    err = state.get("error") or {}
    return JobStatusResponse(
        job_id=state["job_id"],
        status=state["status"],
        progress=state.get("progress", 0),
        current_step=state.get("current_step"),
        failed_step=state.get("failed_step"),
        error_code=err.get("error_code"),
        detail=err.get("detail"),
        hint=err.get("hint"),
        error=state.get("error"),
        created_at=state.get("created_at"),
        updated_at=state.get("updated_at"),
        metadata=state.get("metadata", {}),
        steps=state.get("steps", {}),
    )


@app.get("/jobs/{job_id}/result", tags=["Jobs"])
async def get_job_result(
    job_id: str,
    download: bool = False,
    _api_key: str = Depends(verify_api_key),
):
    """
    Tamamlanan bir işin kalite raporunu, ölçek/koordinat üstverisini (`extras`) ve
    dışa aktarılan `.glb` / `.usdz` dosya bağlantılarını döndürür.
    `?download=true` parametresi verilirse doğrudan `.glb` ikili dosyasını indirir.
    """
    try:
        state = job_runner.orchestrator.load_state(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"'{job_id}' kimlikli iş bulunamadı.",
        ) from exc

    if state["status"] == "failed":
        err = state.get("error") or {}
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "job_id": job_id,
                "status": "failed",
                "failed_step": state.get("failed_step"),
                "error_code": err.get("error_code", "STEP_FAILED"),
                "detail": err.get("detail", "İşlem sırasında adım hatası oluştu."),
                "hint": err.get("hint"),
                "details": err.get("details", {}),
            },
        )

    if state["status"] != "done":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"İş henüz tamamlanmadı (mevcut durum: {state['status']}, adım: {state.get('current_step')}).",
        )

    artifacts = state.get("artifacts", {})
    glb_path_str = artifacts.get("exported_glb")
    manifest_path_str = artifacts.get("export_manifest")
    quality_path_str = artifacts.get("quality_report")

    if download and glb_path_str and Path(glb_path_str).exists():
        return FileResponse(
            path=str(glb_path_str),
            media_type="model/gltf-binary",
            filename=f"{job_id}.glb",
        )

    manifest_data: Dict[str, Any] = {}
    if manifest_path_str and Path(manifest_path_str).exists():
        manifest_data = json.loads(Path(manifest_path_str).read_text(encoding="utf-8"))

    quality_data: Dict[str, Any] = {}
    if quality_path_str and Path(quality_path_str).exists():
        quality_data = json.loads(Path(quality_path_str).read_text(encoding="utf-8"))

    return {
        "status": "success",
        "job_id": job_id,
        "model_url": manifest_data.get("glb", {}).get("uri"),
        "export_manifest": manifest_data,
        "quality_report": quality_data,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "service:app",
        host=settings.service_host,
        port=settings.service_port,
        reload=False,
    )
