# app/api/routers/tripo_router.py
# ────────────────────────────────
# Tripo3D AI 3D üretim API endpoint'leri.
# Bu router, Tripo3D API'yi backend üzerinden proxy'ler
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
import httpx

from app.database.db import get_session
from app.database.models import Scans, User, Processed3D, UserStats
from app.api import get_current_user
from app.services.tripo_service import tripo_client, TripoAPIError, run_tripo_3d_pipeline

log = logging.getLogger("tripo_router")

router = APIRouter(prefix="/tripo", tags=["Tripo3D AI"])


# ─── KREDİ MALİYETLERİ ──────────────────────────────────────────

TRIPO_CREDIT_COSTS = {
    "image_to_3d": 50,        # Kullanıcı kredi maliyeti
    "multi_image_to_3d": 70,
    "text_to_3d": 60,
}


# ─── ŞEMALAR ─────────────────────────────────────────────────────

class ImageTo3DRequest(BaseModel):
    """Tek görsel → 3D model üretim isteği."""
    scan_id: int
    model_version: str = "default"


class MultiImageTo3DRequest(BaseModel):
    """Çoklu görsel → 3D model üretim isteği."""
    scan_id: int
    model_version: str = "default"


class TextTo3DRequest(BaseModel):
    """Metin → 3D model üretim isteği."""
    prompt: str
    model_version: str = "default"


class TripoTaskResponse(BaseModel):
    """Tripo3D task yanıt şeması."""
    task_id: str
    status: str
    progress: int = 0
    message: str = ""
    model_url: Optional[str] = None
    rendered_image_url: Optional[str] = None

    class Config:
        from_attributes = True


class TripoHealthResponse(BaseModel):
    """Tripo3D sağlık kontrolü yanıtı."""
    status: str
    mode: str
    api_key_valid: bool
    message: str
    balance: Optional[dict] = None


# ─── YARDIMCI FONKSİYONLAR ──────────────────────────────────────

async def _check_credits(db: AsyncSession, user_id: int, operation: str) -> UserStats:
    """Kullanıcı kredisini kontrol eder, yetersizse HTTPException fırlatır."""
    cost = TRIPO_CREDIT_COSTS.get(operation, 50)

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
    cost = TRIPO_CREDIT_COSTS.get(operation, 50)
    stats.user_credi -= cost
    await db.commit()


async def _get_scan_image_urls(db: AsyncSession, scan_id: int, user_id: int, backend_url: str) -> List[str]:
    """
    Scan'e ait fotoğrafların public URL'lerini döndürür.
    Tripo3D API public erişilebilir URL'ler gerektirir.
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


async def _process_tripo_3d(
    scan_id: int,
    task_id: str,
    db_url: str,
):
    """
    Arka planda Tripo3D task'ını takip eder ve tamamlanınca
    GLB dosyasını indirir, backend DB'sine kaydeder.

    ÖNEMLİ: Tripo3D model URL'leri ~5dk expire olur.
    Task tamamlanınca hemen indirme yapılmalıdır.
    """
    from app.database.db import AsyncSessionLocal

    try:
        # Task tamamlanmasını bekle
        result = await tripo_client.wait_for_task(
            task_id=task_id,
            poll_interval=5.0,
            max_wait=600.0,
        )

        if result.status.value != "success":
            log.error(f"Scan {scan_id}: Tripo3D task başarısız — {result.error}")
            return

        # GLB dosyasını indir (URL ~5dk expire olur, hemen indirmek lazım!)
        model_url = result.model_url
        if not model_url:
            log.error(f"Scan {scan_id}: Model URL'i bulunamadı!")
            return

        # Kayıt dizini
        upload_dir = os.path.join("uploads", "images_3d", f"scan_{scan_id}")
        os.makedirs(upload_dir, exist_ok=True)

        model_filename = f"model_{uuid.uuid4()}.glb"
        model_path = os.path.join(upload_dir, model_filename).replace("\\", "/")

        await tripo_client.download_model(model_url, model_path)

        # Rendered image indir (varsa)
        thumb_path = None
        if result.rendered_image_url:
            thumb_filename = f"thumb_{scan_id}.png"
            thumb_dir = os.path.join("uploads", "thumbnails")
            os.makedirs(thumb_dir, exist_ok=True)
            thumb_path = os.path.join(thumb_dir, thumb_filename).replace("\\", "/")

            async with httpx.AsyncClient(timeout=30.0) as dl_client:
                response = await dl_client.get(result.rendered_image_url)
                response.raise_for_status()
                with open(thumb_path, "wb") as f:
                    f.write(response.content)

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

        log.info(f"✅ Scan {scan_id}: Tripo3D model başarıyla kaydedildi → {model_path}")

    except TripoAPIError as e:
        log.error(f"❌ Scan {scan_id}: Tripo3D API hatası — {e}")
    except Exception as e:
        log.error(f"❌ Scan {scan_id}: Beklenmeyen hata — {e}", exc_info=True)


# ═══════════════════════════════════════════════════════════════════
#  ENDPOINT'LER
# ═══════════════════════════════════════════════════════════════════

@router.get("/health", response_model=TripoHealthResponse)
async def tripo_health_check():
    """
    Tripo3D AI API bağlantı durumunu kontrol eder.
    API key geçerliliğini ve modu (test/live) gösterir.
    """
    result = await tripo_client.health_check()
    return result


@router.post("/image-to-3d", response_model=TripoTaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_image_to_3d(
    req: ImageTo3DRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Scan'e ait ilk fotoğraftan Tripo3D AI ile 3D model üretir.
    İşlem arka planda çalışır, task_id ile takip edilebilir.
    """
    # Scan'in metot ve durumunu kontrol et
    scan_result = await db.execute(select(Scans).where(Scans.scan_id == req.scan_id))
    scan = scan_result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Tarama bulunamadı.")

    # Eğer bu scan 3D olarak yüklendiyse, ücreti zaten upload_image aşamasında (50 kredi) ödendi.
    # Bu yüzden tekrar ücret almıyoruz.
    is_already_paid = (scan.method in ["3d", "3d_single"])

    stats = None
    if not is_already_paid:
        stats = await _check_credits(db, current_user.user_id, "image_to_3d")

    # Scan'in fotoğraflarını al
    backend_url = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
    image_urls = await _get_scan_image_urls(db, req.scan_id, current_user.user_id, backend_url)

    try:
        # Tripo3D API'ye gönder (ilk fotoğraf)
        task_id = await tripo_client.image_to_3d(
            image_url=image_urls[0],
            model_version=req.model_version,
        )

        # Krediyi düş (eğer önceden ödenmediyse)
        if not is_already_paid and stats:
            await _deduct_credits(db, stats, "image_to_3d")

        # Arka planda task takibi başlat
        db_url = os.getenv("DB_URL", "")
        background_tasks.add_task(
            _process_tripo_3d,
            scan_id=req.scan_id,
            task_id=task_id,
            db_url=db_url,
        )

        return TripoTaskResponse(
            task_id=task_id,
            status="queued",
            progress=0,
            message="3D model üretimi başlatıldı. Task ID ile durumu takip edebilirsiniz.",
        )

    except TripoAPIError as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post("/multi-image-to-3d", response_model=TripoTaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_multi_image_to_3d(
    req: MultiImageTo3DRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Scan'e ait tüm fotoğraflardan Tripo3D AI ile 3D model üretir.
    Birden fazla açıyla daha doğru 3D yapı elde edilir.
    """
    # Scan'in metot ve durumunu kontrol et
    scan_result = await db.execute(select(Scans).where(Scans.scan_id == req.scan_id))
    scan = scan_result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Tarama bulunamadı.")

    # Eğer bu scan 3D olarak yüklendiyse, ücreti zaten upload_image aşamasında (50 kredi) ödendi.
    # Bu yüzden tekrar ücret almıyoruz.
    is_already_paid = (scan.method in ["3d", "3d_single"])

    stats = None
    if not is_already_paid:
        stats = await _check_credits(db, current_user.user_id, "multi_image_to_3d")

    backend_url = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
    image_urls = await _get_scan_image_urls(db, req.scan_id, current_user.user_id, backend_url)

    try:
        task_id = await tripo_client.multi_image_to_3d(
            image_urls=image_urls,
            model_version=req.model_version,
        )

        if not is_already_paid and stats:
            await _deduct_credits(db, stats, "multi_image_to_3d")

        db_url = os.getenv("DB_URL", "")
        background_tasks.add_task(
            _process_tripo_3d,
            scan_id=req.scan_id,
            task_id=task_id,
            db_url=db_url,
        )

        return TripoTaskResponse(
            task_id=task_id,
            status="queued",
            progress=0,
            message=f"{len(image_urls)} fotoğrafla 3D model üretimi başlatıldı.",
        )

    except TripoAPIError as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post("/text-to-3d", response_model=TripoTaskResponse, status_code=status.HTTP_202_ACCEPTED)
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
        task_id = await tripo_client.text_to_3d(
            prompt=req.prompt,
            model_version=req.model_version,
        )

        await _deduct_credits(db, stats, "text_to_3d")

        return TripoTaskResponse(
            task_id=task_id,
            status="queued",
            progress=0,
            message=f"Text-to-3D üretimi başlatıldı: \"{req.prompt[:80]}\"",
        )

    except TripoAPIError as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.get("/task/{task_id}", response_model=TripoTaskResponse)
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Tripo3D AI görevinin durumunu sorgular.
    """
    try:
        result = await tripo_client.get_task_status(task_id)

        return TripoTaskResponse(
            task_id=result.task_id,
            status=result.status.value,
            progress=result.progress,
            message=result.error or "",
            model_url=result.model_url,
            rendered_image_url=result.rendered_image_url,
        )

    except TripoAPIError as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post("/upgrade-to-premium/{scan_id}", response_model=TripoTaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def upgrade_to_premium(
    scan_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Kullanıcının taslak olan 3D modelini, 8 fotoğrafın tamamını kullanarak
    premium (high-fidelity) modele yükseltir.
    Maliyet: 70 Kredi.
    """
    # Scan kontrolü
    scan_result = await db.execute(
        select(Scans)
        .where(Scans.scan_id == scan_id)
        .options(selectinload(Scans.images))
    )
    scan = scan_result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Tarama bulunamadı.")
        
    if scan.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Bu veriye erişim yetkiniz yok.")
        
    if scan.method not in ["3d", "3d_single"]:
        raise HTTPException(status_code=400, detail="Sadece 3D taramalar premium'a yükseltilebilir.")

    # Kredi Kontrolü
    stats = await _check_credits(db, current_user.user_id, "multi_image_to_3d")
    
    # Krediyi düş
    await _deduct_credits(db, stats, "multi_image_to_3d")
    
    # Durumu pending yap
    scan.status = "pending"
    await db.commit()
    
    # Arka planda premium pipeline'ı başlat
    background_tasks.add_task(
        run_tripo_3d_pipeline,
        scan_id=scan_id,
        mode="premium"
    )
    
    return TripoTaskResponse(
        task_id="premium_pipeline_started",
        status="queued",
        progress=0,
        message="Premium 3D model üretimi arka planda başlatıldı.",
    )


@router.get("/balance")
async def get_tripo_balance(
    current_user: User = Depends(get_current_user),
):
    """
    Tripo3D AI hesap bakiyesini ve kalan krediyi gösterir.
    Sadece admin/geliştirici kullanımı için.
    """
    balance = await tripo_client.get_balance()
    return balance


@router.get("/credits/costs")
async def get_credit_costs(
    current_user: User = Depends(get_current_user),
):
    """Her Tripo3D işlemi ve modifikasyon tipi için kredi maliyetlerini döndürür."""
    return {
        "generation_costs": TRIPO_CREDIT_COSTS,
        "modification_costs": {
            "jant": 30,
            "renk": 20,
            # İleride eklenecekler:
            # "spoiler": 25,
            # "body_kit": 40,
        },
        "currency": "user_credits",
        "note": "generation_costs: 3D model üretim maliyetleri, modification_costs: modifikasyon maliyetleri (3D model tamamlandıktan sonra).",
    }
