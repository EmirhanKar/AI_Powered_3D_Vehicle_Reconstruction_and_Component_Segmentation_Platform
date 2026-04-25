# app/api/routers/modification_router.py — YENİ DOSYA

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.database.db import get_session
from app.database.models import Scans, User, Modification
from app.database.models.pluginsTable.jant import Jant
from app.database.models.pluginsTable.colors import Colors
from app.api import get_current_user

router = APIRouter(prefix="/modifications")


# ─────────────────────────────────────────
# ŞEMALAR
# ─────────────────────────────────────────

class ModificationCreate(BaseModel):
    scan_id: int
    jant_id: Optional[int] = None
    color_id: Optional[int] = None


class ModificationUpdate(BaseModel):
    jant_id: Optional[int] = None
    color_id: Optional[int] = None


class ModificationResponse(BaseModel):
    modification_id: int
    scan_id: int
    user_id: int
    jant_id: Optional[int] = None
    color_id: Optional[int] = None
    last_step: str

    class Config:
        from_attributes = True


class DraftResponse(BaseModel):
    scan_id: int
    car_name: str
    last_step: str           # Ne kadar ilerledi
    step_label: str          # Flutter'a gösterilecek yazı: "Jant Seçimi Yarım Kaldı"
    created_at: datetime
    method: str

    class Config:
        from_attributes = True


# ─────────────────────────────────────────
# YARDIMCI FONKSİYON
# ─────────────────────────────────────────

def get_step_label(last_step: str) -> str:
    labels = {
        "method_selected": "Yöntem Seçildi, Fotoğraf Bekleniyor",
        "photo_uploaded": "Fotoğraf Yüklendi, Eklenti Bekleniyor",
        "plugin_selected": "Eklenti Seçildi, Render Bekleniyor",
        "completed": "Tamamlandı",
    }
    return labels.get(last_step, "Devam Et")


# ─────────────────────────────────────────
# ENDPOINTler
# ─────────────────────────────────────────

@router.post("", response_model=ModificationResponse, status_code=status.HTTP_201_CREATED, tags=["Modifications"])
async def create_modification(
    mod_in: ModificationCreate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Adım 3: Kullanıcı eklenti seçti (jant, renk veya ikisi).
    Scan'e bağlı modifikasyon kaydı oluşturur.
    """
    # Scan var mı ve bu kullanıcıya mı ait?
    scan = await db.get(Scans, mod_in.scan_id)
    if not scan or scan.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Tarama bulunamadı.")

    # Jant geçerli mi?
    if mod_in.jant_id:
        jant = await db.get(Jant, mod_in.jant_id)
        if not jant:
            raise HTTPException(status_code=404, detail="Jant bulunamadı.")

    # Renk geçerli mi?
    if mod_in.color_id:
        color = await db.get(Colors, mod_in.color_id)
        if not color:
            raise HTTPException(status_code=404, detail="Renk bulunamadı.")

    new_mod = Modification(
        scan_id=mod_in.scan_id,
        user_id=current_user.user_id,
        jant_id=mod_in.jant_id,
        color_id=mod_in.color_id,
        last_step="plugin_selected"
    )
    db.add(new_mod)

    # Scan'in last_step'ini de güncelle
    scan.status = "plugin_selected"
    await db.commit()
    await db.refresh(new_mod)
    return new_mod


@router.patch("/{modification_id}", response_model=ModificationResponse, tags=["Modifications"])
async def update_modification(
    modification_id: int,
    mod_in: ModificationUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Mevcut modifikasyonu güncelle (jant veya renk değiştir)."""
    result = await db.execute(
        select(Modification).where(
            Modification.modification_id == modification_id,
            Modification.user_id == current_user.user_id
        )
    )
    mod = result.scalar_one_or_none()
    if not mod:
        raise HTTPException(status_code=404, detail="Modifikasyon bulunamadı.")

    if mod_in.jant_id is not None:
        jant = await db.get(Jant, mod_in.jant_id)
        if not jant:
            raise HTTPException(status_code=404, detail="Jant bulunamadı.")
        mod.jant_id = mod_in.jant_id

    if mod_in.color_id is not None:
        color = await db.get(Colors, mod_in.color_id)
        if not color:
            raise HTTPException(status_code=404, detail="Renk bulunamadı.")
        mod.color_id = mod_in.color_id

    await db.commit()
    await db.refresh(mod)
    return mod


@router.get("/drafts", response_model=List[DraftResponse], tags=["Modifications"])
async def get_drafts(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Kullanıcının taslak araçlarını getirir.
    status 'completed' olmayanlar taslak sayılır.
    """
    result = await db.execute(
        select(Scans)
        .where(
            Scans.user_id == current_user.user_id,
            Scans.status != "completed"
        )
        .order_by(Scans.created_at.desc())
    )
    scans = result.scalars().all()

    drafts = []
    for scan in scans:
        # Bu scan'e ait modifikasyon var mı?
        mod_result = await db.execute(
            select(Modification).where(Modification.scan_id == scan.scan_id)
        )
        mod = mod_result.scalar_one_or_none()

        last_step = mod.last_step if mod else scan.status
        drafts.append(DraftResponse(
            scan_id=scan.scan_id,
            car_name=scan.car_name,
            last_step=last_step,
            step_label=get_step_label(last_step),
            created_at=scan.created_at,
            method=scan.method
        ))

    return drafts


@router.get("/{scan_id}", response_model=ModificationResponse, tags=["Modifications"])
async def get_modification(
    scan_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Bir scan'e ait modifikasyonu getirir."""
    result = await db.execute(
        select(Modification).where(
            Modification.scan_id == scan_id,
            Modification.user_id == current_user.user_id
        )
    )
    mod = result.scalar_one_or_none()
    if not mod:
        raise HTTPException(status_code=404, detail="Modifikasyon bulunamadı.")
    return mod


@router.delete("/{modification_id}", tags=["Modifications"])
async def delete_modification(
    modification_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Modifikasyonu siler."""
    result = await db.execute(
        select(Modification).where(
            Modification.modification_id == modification_id,
            Modification.user_id == current_user.user_id
        )
    )
    mod = result.scalar_one_or_none()
    if not mod:
        raise HTTPException(status_code=404, detail="Modifikasyon bulunamadı.")

    await db.delete(mod)
    await db.commit()
    return {"message": "Modifikasyon silindi."}