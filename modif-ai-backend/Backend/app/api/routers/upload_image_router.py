from datetime import datetime, timezone
from sqlalchemy import select, update
from fastapi import APIRouter, Depends, Form, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database.db import get_session
from app.database.schemas import ScanResponse, ScanCreate
from app.database.crud import scanCreate, scanImageCreate, get_user_scans
from app.database.crud import scan_crud
from app.database.models import Scans, Processed3D, Processed2D, User, UserStats
from typing import List
from PIL import Image
import os
import uuid

from app.api import get_current_user

router = APIRouter(prefix="/scans")

# ── KREDİ MALİYETLERİ ──────────────────────────────
# İleride değiştirilecekse buradan düzenle
CREDIT_COST_2D = 10
CREDIT_COST_3D = 25
# ───────────────────────────────────────────────────


@router.post("/upload_image", status_code=status.HTTP_201_CREATED, response_model=ScanResponse)
async def upload_image(
    files: List[UploadFile] = File(...),
    car_name: str = Form(...),
    description: str = Form(None),
    method: str = Form(...),  # "3d" veya "2d"
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    if len(files) != 8:
        raise HTTPException(status_code=400, detail="Lütfen tam olarak 8 adet fotoğraf yükleyin!")

    if method not in ["2d", "3d"]:
        raise HTTPException(status_code=400, detail="Method '2d' veya '3d' olmalıdır.")

    # ── KREDİ KONTROLÜ ──────────────────────────────
    cost = CREDIT_COST_3D if method == "3d" else CREDIT_COST_2D

    stats_result = await db.execute(select(UserStats).where(UserStats.user_id == current_user.user_id))
    user_stats = stats_result.scalar_one_or_none()

    if not user_stats or user_stats.user_credi < cost:
        raise HTTPException(
            status_code=402,
            detail=f"Yetersiz kredi. Bu işlem {cost} kredi gerektiriyor."
        )
    # ────────────────────────────────────────────────

    new_scan = await scanCreate(
        db,
        user_id=current_user.user_id,
        method=method,
        car_name=car_name,
        description=description
    )
    await db.refresh(new_scan)

    user_id_str = str(current_user.user_id)
    base_images_dir = os.path.join("uploads", "images", user_id_str)
    os.makedirs(base_images_dir, exist_ok=True)

    saved_paths = []

    for file in files:
        if file.content_type not in ["image/jpeg", "image/png"]:
            raise HTTPException(status_code=400, detail="Sadece JPEG ve PNG kabul edilir.")

        extension = file.filename.split(".")[-1]
        unique_name = f"{uuid.uuid4()}.{extension}"
        main_path = os.path.join(base_images_dir, unique_name).replace("\\", "/")

        content = await file.read()
        with open(main_path, "wb") as buffer:
            buffer.write(content)

        saved_paths.append(main_path)

        await scanImageCreate(
            db=db,
            scan_id=new_scan.scan_id,
            image_url=main_path
        )

    # Thumbnail oluştur (Pillow ile küçült)
    thumb_dir = os.path.join("uploads", "thumbnails", user_id_str)
    os.makedirs(thumb_dir, exist_ok=True)
    thumb_path = os.path.join(thumb_dir, f"thumb_{new_scan.scan_id}.jpg").replace("\\", "/")

    with Image.open(saved_paths[0]) as img:
        img.thumbnail((400, 400))
        img.convert("RGB").save(thumb_path, "JPEG")

    if method == "3d":
        new_task = Processed3D(scan_id=new_scan.scan_id, thumbnail_url=thumb_path)
    else:
        new_task = Processed2D(scan_id=new_scan.scan_id, thumbnail_url=thumb_path)

    db.add(new_task)

    # ── KREDİ DÜŞME ─────────────────────────────────
    user_stats.user_credi -= cost
    user_stats.create_image += 1  # Toplam oluşturma sayısını artır
    # ────────────────────────────────────────────────

    await db.commit()
    
    result = await db.execute(
        select(Scans)
        .where(Scans.scan_id == new_scan.scan_id)
        .options(selectinload(Scans.processed_3d), selectinload(Scans.processed_2d))
    )
    return result.scalar_one()


@router.get("/pending_3d", response_model=List[ScanResponse])
async def get_pending_3d_scans(db: AsyncSession = Depends(get_session)):
    """3D işlemi bekleyen taramaları listeler. (AI servisi için)"""
    query = (
        select(Scans)
        .join(Processed3D)
        .where(Scans.method == "3d")
        .where(Processed3D.model_url == None)
        .options(selectinload(Scans.processed_3d), selectinload(Scans.processed_2d))
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/complete/3d/{scan_id}", tags=["Admin/Modeller"])
async def complete_3d_model(
    scan_id: int,
    model_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session)
):
    """AI servisi 3D modeli tamamlayınca buraya yükler."""
    result = await db.execute(select(Processed3D).where(Processed3D.scan_id == scan_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail=f"{scan_id} ID'li tarama bulunamadı!")

    upload_path = os.path.join("uploads", "images_3d", f"scan_{scan_id}")
    os.makedirs(upload_path, exist_ok=True)

    unique_filename = f"model_{uuid.uuid4()}.glb"
    full_path = os.path.join(upload_path, unique_filename).replace("\\", "/")

    content = await model_file.read()
    with open(full_path, "wb") as f:
        f.write(content)

    task.model_url = full_path

    # render_image sayısını artır
    scan_result = await db.execute(select(Scans).where(Scans.scan_id == scan_id))
    scan = scan_result.scalar_one_or_none()
    if scan:
        stats_result = await db.execute(select(UserStats).where(UserStats.user_id == scan.user_id))
        user_stats = stats_result.scalar_one_or_none()
        if user_stats:
            user_stats.render_image += 1

    await db.execute(update(Scans).where(Scans.scan_id == scan_id).values(status="completed"))
    await db.commit()

    return {"status": "success", "message": "3D model yüklendi!", "model_url": full_path}


@router.post("/complete/2d/{scan_id}", tags=["Admin/Modeller"])
async def complete_2d_model(
    scan_id: int,
    image_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session)
):
    """AI servisi 2D sonucu tamamlayınca buraya yükler."""
    result = await db.execute(select(Processed2D).where(Processed2D.scan_id == scan_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail=f"{scan_id} ID'li 2D tarama bulunamadı!")

    if image_file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(status_code=400, detail="Sadece JPEG, PNG veya WEBP kabul edilir.")

    upload_path = os.path.join("uploads", "images_2d", f"scan_{scan_id}")
    os.makedirs(upload_path, exist_ok=True)

    extension = image_file.filename.split(".")[-1]
    unique_filename = f"result_{uuid.uuid4()}.{extension}"
    full_path = os.path.join(upload_path, unique_filename).replace("\\", "/")

    content = await image_file.read()
    with open(full_path, "wb") as f:
        f.write(content)

    task.image_url = full_path
    task.thumbnail_url = full_path

    # render_image sayısını artır
    scan_result = await db.execute(select(Scans).where(Scans.scan_id == scan_id))
    scan = scan_result.scalar_one_or_none()
    if scan:
        stats_result = await db.execute(select(UserStats).where(UserStats.user_id == scan.user_id))
        user_stats = stats_result.scalar_one_or_none()
        if user_stats:
            user_stats.render_image += 1

    await db.execute(update(Scans).where(Scans.scan_id == scan_id).values(status="completed"))
    await db.commit()

    return {"status": "success", "message": "2D görsel yüklendi!", "image_url": full_path}


@router.get("/garage", response_model=List[ScanResponse])
async def get_my_scans(
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    """Kullanıcının tamamlanmış araçlarını listeler."""
    scans = await get_user_scans(db, user_id=current_user.user_id)
    return scans


@router.get("/garage/{scan_id}", response_model=ScanResponse)
async def get_scan_details(
    scan_id: int,
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    """Garajdaki tek bir aracın detayını getirir."""
    scan = await scan_crud.get_scan_by_id(db, scan_id=scan_id, user_id=current_user.user_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Araç bulunamadı.")
    return scan


@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan_detail(
    scan_id: int,
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    """Scan ID ile tarama detayını getirir."""
    result = await db.execute(
        select(Scans)
        .where(Scans.scan_id == scan_id)
        .options(selectinload(Scans.processed_3d), selectinload(Scans.processed_2d))
    )
    scan = result.scalar_one_or_none()

    if not scan:
        raise HTTPException(status_code=404, detail="Tarama bulunamadı!")

    if scan.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Bu veriye erişim yetkiniz yok.")

    return scan


@router.delete("/{scan_id}")
async def delete_scan(
    scan_id: int,
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    """Taramayı ve tüm ilişkili verileri siler."""
    result = await db.execute(select(Scans).where(Scans.scan_id == scan_id))
    scan = result.scalar_one_or_none()

    if not scan or scan.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Silinecek kayıt bulunamadı veya yetkiniz yok.")

    await db.delete(scan)
    await db.commit()

    return {"message": f"{scan_id} numaralı tarama silindi."}