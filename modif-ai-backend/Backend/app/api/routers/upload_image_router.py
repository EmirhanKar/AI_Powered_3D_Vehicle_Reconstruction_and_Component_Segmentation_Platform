from datetime import datetime, timezone
from sqlalchemy import select, update
from fastapi import APIRouter, Depends, Form, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database.db import get_session
from app.database.schemas import ScanResponse, ScanCreate
from app.database.crud import scanCreate, scanImageCreate, get_user_scans, scan_crud
from app.database.models import Scans, Processed3D, Processed2D, User, UserStats, Modification
from typing import List
from PIL import Image
import os
import uuid
from app.api import get_current_user

router = APIRouter(prefix="/scans")

# ── KREDİ MALİYETLERİ ──
# İleride değiştirilecekse buradan düzenle
CREDIT_COST_2D = 30
CREDIT_COST_3D = 50

# ── KABUL EDİLEN FORMATLAR ──
# Flutter'dan gelen fotoğraflar farklı MIME type'larla gelebilir
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}

# Fotoğraf sayısı kuralları
PHOTO_COUNTS = {
    "2d": 1,
    "3d": 8,
}


@router.post("/upload_image", status_code=status.HTTP_201_CREATED, response_model=ScanResponse)
async def upload_image(
    files: List[UploadFile] = File(...),
    car_name: str = Form(...),
    description: str = Form(None),
    method: str = Form(...),  # "3d" veya "2d"
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    if method not in ["2d", "3d"]:
        raise HTTPException(status_code=400, detail="Method '2d' veya '3d' olmalıdır.")

    beklenen_sayi = PHOTO_COUNTS[method]
    if len(files) != beklenen_sayi:
        raise HTTPException(
            status_code=400,
            detail=f"{method.upper()} için tam olarak {beklenen_sayi} fotoğraf gerekli! ({len(files)} gönderildi)"
        )

    # ── KREDİ KONTROLÜ ──
    cost = CREDIT_COST_3D if method == "3d" else CREDIT_COST_2D
    stats_result = await db.execute(select(UserStats).where(UserStats.user_id == current_user.user_id))
    user_stats = stats_result.scalar_one_or_none()

    if not user_stats or user_stats.user_credi < cost:
        raise HTTPException(
            status_code=402,
            detail=f"Yetersiz kredi. Bu işlem {cost} kredi gerektiriyor."
        )

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
        # Content type kontrolü — None gelirse dosya uzantısına bak
        content_type = file.content_type or ""
        filename = file.filename or ""
        ext = filename.lower().split(".")[-1] if "." in filename else ""

        gecerli_mi = (
            content_type in ALLOWED_CONTENT_TYPES or
            ext in {"jpg", "jpeg", "png", "webp", "heic", "heif"}
        )

        if not gecerli_mi:
            raise HTTPException(
                status_code=400,
                detail=f"'{filename}' desteklenmiyor. JPEG, PNG, WEBP, HEIC kabul edilir."
            )

        unique_name = f"{uuid.uuid4()}.jpg"  # hepsini jpg olarak kaydet
        main_path = os.path.join(base_images_dir, unique_name).replace("\\", "/")

        content = await file.read()

        # Pillow ile standart JPEG'e dönüştür (HEIC dahil tüm formatlar için)
        try:
            import io
            img = Image.open(io.BytesIO(content))
            img = img.convert("RGB")
            img.save(main_path, "JPEG", quality=85)
        except Exception:
            # Pillow açamazsa direkt kaydet
            with open(main_path, "wb") as buffer:
                buffer.write(content)

        saved_paths.append(main_path)

        await scanImageCreate(db=db, scan_id=new_scan.scan_id, image_url=main_path)

    # Thumbnail oluştur
    thumb_dir = os.path.join("uploads", "thumbnails", user_id_str)
    os.makedirs(thumb_dir, exist_ok=True)
    thumb_path = os.path.join(thumb_dir, f"thumb_{new_scan.scan_id}.jpg").replace("\\", "/")
 
    try:
        with Image.open(saved_paths[0]) as img:
            img = img.convert("RGB")
            img.thumbnail((400, 400))
            img.save(thumb_path, "JPEG", quality=85)
    except Exception as e:
        # Pillow açamazsa dosyayı direkt kopyala
        import shutil
        shutil.copy2(saved_paths[0], thumb_path)
 
    # Thumbnail dosyası oluştu mu kontrol et
    if not os.path.exists(thumb_path):
        # Son çare: ilk fotoğrafın yolunu thumbnail olarak kullan
        thumb_path = saved_paths[0]
        
    # ── PROCESSED KAYDINI OLUŞTUR ──
    
    if method == "3d":
        new_task = Processed3D(
            scan_id=new_scan.scan_id,
            thumbnail_url=thumb_path,
        )
        db.add(new_task)
    else:
        new_task = Processed2D(
            scan_id=new_scan.scan_id,
            thumbnail_url=thumb_path,
        )
        db.add(new_task)

    # Kredi düş, istatistik güncelle
    user_stats.user_credi -= cost
    user_stats.create_image += 1

    await db.commit()

    result = await db.execute(
        select(Scans)
        .where(Scans.scan_id == new_scan.scan_id)
        .options(
            selectinload(Scans.processed_3d),
            selectinload(Scans.processed_2d),
            selectinload(Scans.images),
            selectinload(Scans.modifications).selectinload(Modification.jant),
            selectinload(Scans.modifications).selectinload(Modification.colors)
        )
    )
    return result.scalar_one()


# upload_image_router.py içindeki pending_3d endpoint'ini bununla değiştir

@router.get("/pending_3d", response_model=List[ScanResponse])
async def get_pending_3d_scans(db: AsyncSession = Depends(get_session)):
    """3D işlemi bekleyen taramaları listeler. (AI servisi için)"""
    query = (
        select(Scans)
        .join(Processed3D)
        .where(Scans.method == "3d")
        .where(Processed3D.model_url == None)
        .options(
            selectinload(Scans.processed_3d),
            selectinload(Scans.processed_2d),
            selectinload(Scans.images),                              # Fotoğraflar
            selectinload(Scans.modifications).selectinload(Modification.jant),
            selectinload(Scans.modifications).selectinload(Modification.colors),
        )
    )
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/complete/3d/{scan_id}", tags=["Admin/Modeller"])
async def complete_3d_model(
    scan_id: int,
    model_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session)
):
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
    await db.execute(update(Scans).where(Scans.scan_id == scan_id).values(status="completed"))
    await db.commit()

    return {"status": "success", "message": "3D model yüklendi!", "model_url": full_path}


# upload_image_router.py'ye eklenecek

@router.get("/pending_2d", response_model=List[ScanResponse])
async def get_pending_2d_scans(db: AsyncSession = Depends(get_session)):
    """2D segmentasyon bekleyen taramaları listeler. (AI servisi için)"""
    query = (
        select(Scans)
        .join(Processed2D)
        .where(Scans.method == "2d")
        .where(Scans.status.in_(["pending", "plugin_selected"]))
        .where(Processed2D.image_url == None)
        .options(
            selectinload(Scans.processed_2d),
            selectinload(Scans.processed_3d),
            selectinload(Scans.images),  # Orijinal fotoğrafları da ver
            selectinload(Scans.modifications).selectinload(Modification.jant),
            selectinload(Scans.modifications).selectinload(Modification.colors)
        )
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/complete/2d/{scan_id}", tags=["Admin/Modeller"])
async def complete_2d_model(
    scan_id: int,
    image_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session)
):
    result = await db.execute(select(Processed2D).where(Processed2D.scan_id == scan_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail=f"{scan_id} ID'li 2D tarama bulunamadı!")

    # Scan bilgilerini al (user_id için gerekli)
    scan_result = await db.execute(select(Scans).where(Scans.scan_id == scan_id))
    scan = scan_result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail=f"{scan_id} ID'li tarama bulunamadı!")

    if scan.status == "completed":
        return {"status": "skipped", "message": "Bu tarama zaten tamamlanmış."}

    # Sonuç görselini kaydet
    upload_path = os.path.join("uploads", "images_2d", f"scan_{scan_id}")
    os.makedirs(upload_path, exist_ok=True)

    extension = (image_file.filename or "result").split(".")[-1]
    unique_filename = f"result_{uuid.uuid4()}.{extension}"
    full_path = os.path.join(upload_path, unique_filename).replace("\\", "/")

    content = await image_file.read()

    with open(full_path, "wb") as buffer:
        buffer.write(content)

    # Thumbnail oluştur
    thumb_dir = os.path.join("uploads", "thumbnails", str(scan.user_id))
    os.makedirs(thumb_dir, exist_ok=True)
    thumb_path = os.path.join(thumb_dir, f"thumb_{scan_id}.jpg").replace("\\", "/")

    try:
        import io
        img = Image.open(io.BytesIO(content))
        img = img.convert("RGB")
        img.thumbnail((400, 400))
        img.save(thumb_path, "JPEG", quality=85)
    except Exception:
        import shutil
        shutil.copy2(full_path, thumb_path)

    # DB güncelle
    await db.execute(
        update(Processed2D)
        .where(Processed2D.scan_id == scan_id)
        .values(image_url=full_path, thumbnail_url=thumb_path)
    )
    await db.execute(
        update(Scans)
        .where(Scans.scan_id == scan_id)
        .values(status="completed")
    )
    await db.commit()

    return {"status": "success", "message": "2D görsel yüklendi!", "image_url": full_path}


@router.get("/garage", response_model=List[ScanResponse])
async def get_my_scans(
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    scans = await get_user_scans(db, user_id=current_user.user_id)
    return scans


@router.get("/garage/{scan_id}", response_model=ScanResponse)
async def get_scan_details(
    scan_id: int,
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    scan = await scan_crud.get_scan_by_id(db, scan_id=scan_id, user_id=current_user.user_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Araç bulunamadı.")
    return scan


#bu endpoint hem 2D hem de 3D taramalar için detayları getirir,
# sadece scan_id'ye göre sorgular. Kullanıcı doğrulaması yapılır ve tarama sahibi değilse erişim engellenir.
@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan_detail(
    scan_id: int,
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    result = await db.execute(
        select(Scans)
        .where(Scans.scan_id == scan_id)
        .options(selectinload(Scans.processed_3d), selectinload(Scans.processed_2d), selectinload(Scans.images), selectinload(Scans.modifications).selectinload(Modification.jant), selectinload(Scans.modifications).selectinload(Modification.colors))
    )
    scan = result.scalar_one_or_none()

    if not scan:
        raise HTTPException(status_code=404, detail="Tarama bulunamadı!")
    if scan.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Bu veriye erişim yetkiniz yok.")

    return scan

#bu endpoint, tarama silme işlemi için kullanılır. 
# Sadece tarama sahibi tarafından erişilebilir ve silinecek tarama bulunamazsa veya kullanıcı yetkisi yoksa hata döner. 
# Tarama başarıyla silindiğinde, silinen taramanın ID'si ile birlikte bir mesaj döner.

@router.delete("/{scan_id}")
async def delete_scan(
    scan_id: int,
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    result = await db.execute(select(Scans).where(Scans.scan_id == scan_id))
    scan = result.scalar_one_or_none()

    if not scan or scan.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Silinecek kayıt bulunamadı veya yetkiniz yok.")

    await db.delete(scan)
    await db.commit()

    return {"message": f"{scan_id} numaralı tarama silindi."}