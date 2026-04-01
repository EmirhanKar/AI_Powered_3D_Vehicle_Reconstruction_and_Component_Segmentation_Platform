from datetime import datetime, timezone
from sqlalchemy import select
from fastapi import APIRouter, Depends, Form, HTTPException ,status , UploadFile , File
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.db import get_session
from app.database.schemas import ScanResponse , ScanCreate
from app.database.crud import scanCreate, scanImageCreate
from app.database.models import  Scans , Processed3D , Processed2D
from app.api import get_current_user
from typing import List
import os
import uuid


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
    query = select(Scans).where(Scans.method == "3d")
    result = await db.execute(query)
    scans = result.scalars().all()
    return scans