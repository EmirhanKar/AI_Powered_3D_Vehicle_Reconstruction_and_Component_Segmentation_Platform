from datetime import datetime, timezone
from sqlalchemy import select, update
from fastapi import APIRouter, Depends, Form, HTTPException ,status , UploadFile , File
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.db import get_session
from app.database.schemas import ScanResponse , ScanCreate 
from app.database.crud import scanCreate, scanImageCreate 
from app.database.models import  Scans , Processed3D , Processed2D , User
from typing import List
import os
import uuid
from app.api import get_current_user


router = APIRouter(prefix="/scans")
#burada kullanıcıların yüklediği görselleri kaydetmek için bir endpoint oluşturulacak. Bu endpoint, 
# kullanıcıların görsellerini yüklemelerine ve bu görsellerin veritabanında saklanmasına olanak tanıyacak.
# Ayrıca, görsellerin boyutunu ve formatını kontrol etmek gibi ek doğrulamalar da yapılabilir.


@router.post("/upload_image" , status_code=status.HTTP_201_CREATED , response_model = ScanResponse)
async def upload_image(files: List[UploadFile] = File(...) , user_id: int = Form(...) , method: str = Form(...) , db: AsyncSession = Depends(get_session)):
    if len(files) != 8:
        raise HTTPException(status_code=400, detail="8 tane fotoğraf lazım!!!")

    for file in files:
        if file.content_type not in ["image/jpeg", "image/png"]:
            raise HTTPException(status_code=400, detail="Sadece JPEG ve PNG formatında dosyalar kabul edilir.")

        if file.size > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Dosya boyutu 5 MB'ı geçemez.")

    new_scan = await scanCreate(db , user_id=user_id , method=method)
    await db.refresh(new_scan)
    
    base_images_dir = os.path.join("uploads", "images", str(user_id)) # Tüm fotolar için
    os.makedirs(base_images_dir, exist_ok=True)

    for file in files:
        extension = file.filename.split(".")[-1]
        unique_name = f"{uuid.uuid4()}.{extension}"
        
        # Dosya yolları
        main_path = os.path.join(base_images_dir, unique_name)
        
        content = await file.read()

        with open(main_path, "wb") as buffer:
            buffer.write(content)

        await scanImageCreate(
            db=db, 
            scan_id=new_scan.scan_id, 
            image_url=main_path.replace("\\", "/") 
        )
        
    if method == "3d":
        new_task = Processed3D(
            scan_id=new_scan.scan_id,
            model_url= None,
            thumbnail_url= None,
        )
        db.add(new_task)
        
    elif method == "2d":
        new_task = Processed2D(
            scan_id=new_scan.scan_id,
            model_url= None,
            thumbnail_url= None,
        )
        db.add(new_task)
        
    await db.commit()

    return new_scan


@router.get("/pending_3d", response_model=List[ScanResponse])
async def get_pending_3d_scans(db: AsyncSession = Depends(get_session)):
    # Mantık: Methodu '3d' olan ve henüz işlenmemiş taramaları getir
    query = (
        select(Scans)
        .join(Processed3D)
        .where(Scans.method == "3d")
        .where(Processed3D.model_url == None)
    )
    result = await db.execute(query)
    scans = result.scalars().all()
    return scans



@router.post("/complete/3d/{scan_id}", tags=["Admin/Modeller"])
async def complete_3d_model(scan_id: int, model_file: UploadFile = File(...), db: AsyncSession = Depends(get_session)):
    
    query = select(Processed3D).filter(Processed3D.scan_id == scan_id)
    
    result = await db.execute(query)
    
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=404, 
            detail=f"Hata: {scan_id} ID'li bir tarama kaydı bulunamadı!"
        )
        
    upload_path = os.path.join("uploads", "images_3d", f"scan_{scan_id}")
    os.makedirs(upload_path, exist_ok=True)
    
    unique_filename = f"model_{uuid.uuid4()}.glb"
    full_path = os.path.join(upload_path, unique_filename)
    
    content = await model_file.read()
    with open(full_path, "wb") as f:
        f.write(content)
    
    task.model_url = full_path.replace("\\", "/")
    stmt = update(Scans).where(Scans.scan_id == scan_id).values(status="completed")
    
    await db.execute(stmt)
    await db.commit()
    
    return {"status": "success", "message": "Model yüklendi!"}


# 1. KULLANICI GALERİSİ: Giriş yapmış kullanıcının tüm taramalarını listeler
@router.get("/myscans", response_model=List[ScanResponse])
async def get_my_scans(
    db: AsyncSession = Depends(get_session), 
    current_user = Depends(get_current_user)
):
    # Mantık: Veritabanından sadece bu kullanıcıya ait olanları çek
    query = (
        select(Scans)
        .where(Scans.user_id == current_user.user_id)
        .order_by(Scans.scan_id.desc()) # En yeni tarama en üstte
    )
    result = await db.execute(query)
    scans = result.scalars().all()
    return scans


# 2. TEKİL TARAMA DETAYI: Bir taramanın tüm bilgilerini getirir (Güvenlikli)
@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan_detail(
    scan_id: int, 
    db: AsyncSession = Depends(get_session), 
    current_user = Depends(get_current_user)
):
    # Mantık: Önce ID ile taramayı bul
    query = select(Scans).where(Scans.scan_id == scan_id)
    result = await db.execute(query)
    scan = result.scalar_one_or_none()

    # Kontrol 1: Kayıt var mı?
    if not scan:
        raise HTTPException(status_code=404, detail="Tarama bulunamadı!")

    # Kontrol 2 (GÜVENLİK): Bu tarama başkasına mı ait?
    if scan.user_id != current_user.user_id:
        raise HTTPException(
            status_code=403, 
            detail="Bu veriye erişim yetkiniz yok. Başkasının aracını göremezsiniz!"
        )

    return scan


# 3. TARAMA SİLME: Kullanıcı kendi taramasını ve dosyalarını silebilir
@router.delete("/{scan_id}")
async def delete_scan(
    scan_id: int, 
    db: AsyncSession = Depends(get_session), 
    current_user = Depends(get_current_user)
):
    # Mantık: Taramayı bul ve yetkiyi kontrol et
    query = select(Scans).where(Scans.scan_id == scan_id)
    result = await db.execute(query)
    scan = result.scalar_one_or_none()

    if not scan or scan.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Silinecek kayıt bulunamadı veya yetkiniz yok.")

    # Buraya ileride os.remove() ile dosyaları fiziksel silme kodu da eklenebilir.
    await db.delete(scan)
    await db.commit()
    
    return {"message": f"{scan_id} numaralı tarama ve tüm verileri silindi."}