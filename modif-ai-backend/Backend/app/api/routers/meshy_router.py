# app/api/routers/meshy_router.py
# ────────────────────────────────
# Meshy AI 3D üretim API endpoint'leri.
# Bu router, Meshy AI API'yi backend üzerinden proxy'ler
# ve sonuçları mevcut scan/modification akışına entegre eder.

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from typing import Optional, List
from pydantic import BaseModel
import os
import uuid
import logging

from app.database.db import get_session
from app.database.models import Scans, User, Processed3D, UserStats
from app.api import get_current_user
from app.services.meshy_service import meshy_client, MeshyModel, OutputFormat, MeshyAPIError

log = logging.getLogger("meshy_router")

router = APIRouter(prefix="/meshy", tags=["Meshy AI"])


# ─── KREDİ MALİYETLERİ ──────────────────────────────────────────

MESHY_CREDIT_COSTS = {
    "image_to_3d": 50,        # Kullanıcı kredi maliyeti
    "multi_image_to_3d": 70,
    "text_to_3d": 60,
    "retexture": 30,
    "remesh": 20,
}


# ─── ŞEMALAR ─────────────────────────────────────────────────────

class ImageTo3DRequest(BaseModel):
    """Tek görsel → 3D model üretim isteği."""
    scan_id: int
    ai_model: str = "meshy-6"           # "meshy-6" (onerilen)
    topology: str = "quad"              # "quad" | "triangle"
    target_polycount: int = 30000


class MultiImageTo3DRequest(BaseModel):
    """Çoklu görsel → 3D model üretim isteği."""
    scan_id: int
    ai_model: str = "meshy-6"
    topology: str = "quad"
    target_polycount: int = 30000


class TextTo3DRequest(BaseModel):
    """Metin → 3D model üretim isteği."""
    prompt: str
    art_style: str = "realistic"        # "realistic" | "cartoon" | "low-poly" | "sculpture"
    negative_prompt: str = ""
    ai_model: str = "meshy-6"
    target_polycount: int = 30000


class RetextureRequest(BaseModel):
    """Mevcut 3D modele yeni texture uygulama isteği."""
    scan_id: int
    prompt: str                         # "metallic red car paint", "matte black"
    art_style: str = "realistic"
    resolution: str = "2048"            # "1024" | "2048" | "4096"


class RemeshRequest(BaseModel):
    """3D model mesh optimizasyonu isteği."""
    scan_id: int
    target_polycount: int = 10000
    topology: str = "quad"


class TaskStatusRequest(BaseModel):
    """Task durumu sorgulama isteği."""
    task_id: str
    task_type: str = "image-to-3d"


class MeshyTaskResponse(BaseModel):
    """Meshy task yanıt şeması."""
    task_id: str
    status: str
    progress: int = 0
    message: str = ""
    model_urls: dict = {}
    thumbnail_url: Optional[str] = None

    class Config:
        from_attributes = True


class MeshyHealthResponse(BaseModel):
    """Meshy sağlık kontrolü yanıtı."""
    status: str
    mode: str
    api_key_valid: bool
    message: str
    balance: Optional[dict] = None


# ─── YARDIMCI FONKSİYONLAR ──────────────────────────────────────

async def _check_credits(db: AsyncSession, user_id: int, operation: str) -> UserStats:
    """Kullanıcı kredisini kontrol eder, yetersizse HTTPException fırlatır."""
    cost = MESHY_CREDIT_COSTS.get(operation, 50)

    result = await db.execute(select(UserStats).where(UserStats.user_id == user_id))
    stats = result.scalar_one_or_none()

    if not stats or stats.user_credi < cost:
        raise HTTPException(
            status_code=402,
            detail=f"Yetersiz kredi. Bu işlem {cost} kredi gerektiriyor. "
                   f"Mevcut: {stats.user_credi if stats else 0}"
        )
    return stats


async def _deduct_credits(db: AsyncSession, stats: UserStats, operation: str):
    """Krediyi düşer."""
    cost = MESHY_CREDIT_COSTS.get(operation, 50)
    stats.user_credi -= cost
    await db.commit()


def _get_meshy_model(ai_model: str) -> MeshyModel:
    """String model adını MeshyModel enum'ına çevirir."""
    model_map = {
        "meshy-6": MeshyModel.MESHY_6,
        "meshy-4": MeshyModel.MESHY_6,  # meshy-4 deprecated, meshy-6'ya yonlendir
        "default": MeshyModel.DEFAULT,
    }
    return model_map.get(ai_model, MeshyModel.MESHY_6)


async def _get_scan_image_urls(db: AsyncSession, scan_id: int, user_id: int, backend_url: str) -> List[str]:
    """
    Scan'e ait fotoğrafların public URL'lerini döndürür.
    Meshy API public erişilebilir URL'ler gerektirir.
    """
    result = await db.execute(
        select(Scans)
        .where(Scans.scan_id == scan_id, Scans.user_id == user_id)
        .options(selectinload(Scans.images))
    )
    scan = result.scalar_one_or_none()

    if not scan:
        raise HTTPException(status_code=404, detail="Tarama bulunamadı.")

    if not scan.images:
        raise HTTPException(status_code=400, detail="Bu taramada fotoğraf bulunamadı.")

    # Backend URL'i ile tam URL oluştur
    urls = []
    for img in scan.images:
        img_url = img.image_url
        if img_url and not img_url.startswith("http"):
            img_url = f"{backend_url}/{img_url.replace(chr(92), '/')}"
        urls.append(img_url)

    return urls


async def _process_meshy_3d(
    scan_id: int,
    task_id: str,
    task_type: str,
    db_url: str,
):
    """
    Arka planda Meshy task'ını takip eder ve tamamlanınca
    GLB dosyasını indirir, backend DB'sine kaydeder.
    """
    from app.database.db import AsyncSessionLocal

    try:
        # Task tamamlanmasını bekle
        result = await meshy_client.wait_for_task(
            task_id=task_id,
            task_type=task_type,
            poll_interval=5.0,
            max_wait=600.0,
        )

        if result.status.value != "SUCCEEDED":
            log.error(f"Scan {scan_id}: Meshy task başarısız — {result.error}")
            return

        # GLB dosyasını indir
        glb_url = result.model_urls.get("glb", "")
        if not glb_url:
            # Herhangi bir format al
            for fmt, url in result.model_urls.items():
                glb_url = url
                break

        if not glb_url:
            log.error(f"Scan {scan_id}: Model URL'i bulunamadı!")
            return

        # Kayıt dizini
        upload_dir = os.path.join("uploads", "images_3d", f"scan_{scan_id}")
        os.makedirs(upload_dir, exist_ok=True)

        model_filename = f"model_{uuid.uuid4()}.glb"
        model_path = os.path.join(upload_dir, model_filename).replace("\\", "/")

        await meshy_client.download_model(glb_url, model_path)

        # Thumbnail indir
        thumb_path = None
        if result.thumbnail_url:
            thumb_filename = f"thumb_{scan_id}.png"
            thumb_dir = os.path.join("uploads", "thumbnails")
            os.makedirs(thumb_dir, exist_ok=True)
            thumb_path = os.path.join(thumb_dir, thumb_filename).replace("\\", "/")
            await meshy_client.download_thumbnail(result.thumbnail_url, thumb_path)

        # DB güncelle
        async with AsyncSessionLocal() as db:
            # Processed3D güncelle
            proc_result = await db.execute(
                select(Processed3D).where(Processed3D.scan_id == scan_id)
            )
            proc = proc_result.scalar_one_or_none()

            if proc:
                proc.model_url = model_path
                if thumb_path:
                    proc.thumbnail_url = thumb_path
            else:
                new_proc = Processed3D(
                    scan_id=scan_id,
                    model_url=model_path,
                    thumbnail_url=thumb_path or "",
                )
                db.add(new_proc)

            # Scan durumunu güncelle
            await db.execute(
                update(Scans)
                .where(Scans.scan_id == scan_id)
                .values(status="completed")
            )

            await db.commit()

        log.info(f"✅ Scan {scan_id}: Meshy 3D model başarıyla kaydedildi → {model_path}")

    except MeshyAPIError as e:
        log.error(f"❌ Scan {scan_id}: Meshy API hatası — {e}")
    except Exception as e:
        log.error(f"❌ Scan {scan_id}: Beklenmeyen hata — {e}", exc_info=True)


# ═══════════════════════════════════════════════════════════════════
#  ENDPOINT'LER
# ═══════════════════════════════════════════════════════════════════

@router.get("/health", response_model=MeshyHealthResponse)
async def meshy_health_check():
    """
    Meshy AI API bağlantı durumunu kontrol eder.
    API key geçerliliğini ve modu (test/live) gösterir.
    """
    result = await meshy_client.health_check()
    return result


@router.post("/image-to-3d", response_model=MeshyTaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_image_to_3d(
    req: ImageTo3DRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Scan'e ait ilk fotoğraftan Meshy AI ile 3D model üretir.
    İşlem arka planda çalışır, task_id ile takip edilebilir.
    """
    # Kredi kontrolü
    stats = await _check_credits(db, current_user.user_id, "image_to_3d")

    # Scan'in fotoğraflarını al
    # NOT: Meshy API, public erişilebilir URL gerektirir
    # Geliştirme ortamında bu çalışmayabilir — production'da domain gerekli
    backend_url = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
    image_urls = await _get_scan_image_urls(db, req.scan_id, current_user.user_id, backend_url)

    try:
        # Meshy API'ye gönder (ilk fotoğraf)
        task_id = await meshy_client.image_to_3d(
            image_url=image_urls[0],
            model=_get_meshy_model(req.ai_model),
            topology=req.topology,
            target_polycount=req.target_polycount,
        )

        # Krediyi düş
        await _deduct_credits(db, stats, "image_to_3d")

        # Arka planda task takibi başlat
        db_url = os.getenv("DB_URL", "")
        background_tasks.add_task(
            _process_meshy_3d,
            scan_id=req.scan_id,
            task_id=task_id,
            task_type="image-to-3d",
            db_url=db_url,
        )

        return MeshyTaskResponse(
            task_id=task_id,
            status="PENDING",
            progress=0,
            message="3D model üretimi başlatıldı. Task ID ile durumu takip edebilirsiniz.",
        )

    except MeshyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/multi-image-to-3d", response_model=MeshyTaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_multi_image_to_3d(
    req: MultiImageTo3DRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Scan'e ait tüm fotoğraflardan (8 açı) Meshy AI ile 3D model üretir.
    Birden fazla açıyla daha doğru 3D yapı elde edilir.
    """
    stats = await _check_credits(db, current_user.user_id, "multi_image_to_3d")

    backend_url = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
    image_urls = await _get_scan_image_urls(db, req.scan_id, current_user.user_id, backend_url)

    try:
        task_id = await meshy_client.multi_image_to_3d(
            image_urls=image_urls,
            model=_get_meshy_model(req.ai_model),
            topology=req.topology,
            target_polycount=req.target_polycount,
        )

        await _deduct_credits(db, stats, "multi_image_to_3d")

        db_url = os.getenv("DB_URL", "")
        background_tasks.add_task(
            _process_meshy_3d,
            scan_id=req.scan_id,
            task_id=task_id,
            task_type="multi-image-to-3d",
            db_url=db_url,
        )

        return MeshyTaskResponse(
            task_id=task_id,
            status="PENDING",
            progress=0,
            message=f"{len(image_urls)} fotoğrafla 3D model üretimi başlatıldı.",
        )

    except MeshyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/text-to-3d", response_model=MeshyTaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_text_to_3d(
    req: TextTo3DRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Metin açıklamasından 3D aksesuar/parça üretir.
    Örnek: "carbon fiber rear spoiler", "aggressive body kit"
    """
    stats = await _check_credits(db, current_user.user_id, "text_to_3d")

    try:
        task_id = await meshy_client.text_to_3d(
            prompt=req.prompt,
            model=_get_meshy_model(req.ai_model),
            art_style=req.art_style,
            negative_prompt=req.negative_prompt,
            target_polycount=req.target_polycount,
        )

        await _deduct_credits(db, stats, "text_to_3d")

        return MeshyTaskResponse(
            task_id=task_id,
            status="PENDING",
            progress=0,
            message=f"Text-to-3D üretimi başlatıldı: \"{req.prompt[:80]}\"",
        )

    except MeshyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/retexture", response_model=MeshyTaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def retexture_model(
    req: RetextureRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Mevcut bir 3D modele yeni AI texture uygular.
    Örnek prompt: "glossy metallic red car paint", "matte black with carbon fiber accents"
    """
    stats = await _check_credits(db, current_user.user_id, "retexture")

    # Scan'in 3D modelini bul
    result = await db.execute(
        select(Processed3D).where(Processed3D.scan_id == req.scan_id)
    )
    proc = result.scalar_one_or_none()

    if not proc or not proc.model_url:
        raise HTTPException(
            status_code=404,
            detail="Bu taramada 3D model bulunamadı. Önce 3D model oluşturun."
        )

    # Model URL'ini public URL'e çevir
    backend_url = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
    model_url = proc.model_url
    if not model_url.startswith("http"):
        model_url = f"{backend_url}/{model_url.replace(chr(92), '/')}"

    try:
        task_id = await meshy_client.texture_3d(
            model_url=model_url,
            prompt=req.prompt,
            art_style=req.art_style,
            resolution=req.resolution,
        )

        await _deduct_credits(db, stats, "retexture")

        return MeshyTaskResponse(
            task_id=task_id,
            status="PENDING",
            progress=0,
            message=f"Retexture başlatıldı: \"{req.prompt[:80]}\"",
        )

    except MeshyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/remesh", response_model=MeshyTaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def remesh_model(
    req: RemeshRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Mevcut 3D modelin mesh topolojisini optimize eder.
    Daha temiz geometri ve daha düşük polygon sayısı sağlar.
    """
    stats = await _check_credits(db, current_user.user_id, "remesh")

    result = await db.execute(
        select(Processed3D).where(Processed3D.scan_id == req.scan_id)
    )
    proc = result.scalar_one_or_none()

    if not proc or not proc.model_url:
        raise HTTPException(
            status_code=404,
            detail="Bu taramada 3D model bulunamadı."
        )

    backend_url = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
    model_url = proc.model_url
    if not model_url.startswith("http"):
        model_url = f"{backend_url}/{model_url.replace(chr(92), '/')}"

    try:
        task_id = await meshy_client.remesh(
            model_url=model_url,
            target_polycount=req.target_polycount,
            topology=req.topology,
        )

        await _deduct_credits(db, stats, "remesh")

        return MeshyTaskResponse(
            task_id=task_id,
            status="PENDING",
            progress=0,
            message=f"Remesh başlatıldı: polycount={req.target_polycount}",
        )

    except MeshyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/task/{task_id}", response_model=MeshyTaskResponse)
async def get_task_status(
    task_id: str,
    task_type: str = "image-to-3d",
    current_user: User = Depends(get_current_user),
):
    """
    Meshy AI görevinin durumunu sorgular.

    Task türleri: image-to-3d, multi-image-to-3d, text-to-3d, text-to-texture, remesh
    """
    try:
        result = await meshy_client.get_task_status(task_id, task_type)

        return MeshyTaskResponse(
            task_id=result.task_id,
            status=result.status.value,
            progress=result.progress,
            message=result.error or "",
            model_urls=result.model_urls,
            thumbnail_url=result.thumbnail_url,
        )

    except MeshyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/balance")
async def get_meshy_balance(
    current_user: User = Depends(get_current_user),
):
    """
    Meshy AI hesap bakiyesini ve kalan krediyi gösterir.
    Sadece admin/geliştirici kullanımı için.
    """
    balance = await meshy_client.get_balance()
    return balance


@router.get("/credits/costs")
async def get_credit_costs(
    current_user: User = Depends(get_current_user),
):
    """Her Meshy işlemi için kullanıcı kredi maliyetlerini döndürür."""
    return {
        "costs": MESHY_CREDIT_COSTS,
        "currency": "user_credits",
        "note": "Bu maliyetler kullanıcı kredileridir, Meshy API kredileri değildir.",
    }
