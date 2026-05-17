# app/api/routers/community_router.py — YENİ DOSYA

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List

from app.database.db import get_session
from app.database.models import Scans, User, Like, Comment
from app.database.models.modificationTable.processed_3D import Processed3D
from app.database.models.modificationTable.processed_2D import Processed2D
from app.api import get_current_user
from app.database.schemas.community_schemas import (
    CommentCreate, CommentResponse, FeedItemResponse
)

router = APIRouter(prefix="/community")


# ─────────────────────────────────────────
# KEŞFET FEED
# ─────────────────────────────────────────

@router.get("/feed", response_model=List[FeedItemResponse], tags=["Community"])
async def get_feed(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Sadece toplulukla paylaşılmış araçları keşfet sayfası için listeler."""

    # Sadece is_shared=True olan completed scan'leri getir
    query = (
        select(Scans)
        .where(Scans.status == "completed")
        .where(Scans.is_shared == True)
        .options(
            selectinload(Scans.processed_3d),
            selectinload(Scans.processed_2d),
        )
        .order_by(Scans.created_at.desc())
    )
    result = await db.execute(query)
    scans = result.scalars().all()

    feed = []
    for scan in scans:
        # Beğeni sayısı
        like_count_result = await db.execute(
            select(func.count()).where(Like.scan_id == scan.scan_id)
        )
        like_count = like_count_result.scalar()

        # Yorum sayısı
        comment_count_result = await db.execute(
            select(func.count()).where(Comment.scan_id == scan.scan_id)
        )
        comment_count = comment_count_result.scalar()

        # Giriş yapan kullanıcı beğenmiş mi?
        liked_result = await db.execute(
            select(Like).where(
                Like.scan_id == scan.scan_id,
                Like.user_id == current_user.user_id
            )
        )
        is_liked = liked_result.scalar_one_or_none() is not None

        # Araç sahibi
        owner_result = await db.execute(select(User).where(User.user_id == scan.user_id))
        owner = owner_result.scalar_one_or_none()

        # Thumbnail
        thumbnail_url = None
        if scan.processed_3d:
            thumbnail_url = scan.processed_3d.thumbnail_url
        elif scan.processed_2d:
            thumbnail_url = scan.processed_2d.thumbnail_url

        feed.append(FeedItemResponse(
            scan_id=scan.scan_id,
            car_name=scan.car_name,
            thumbnail_url=thumbnail_url,
            like_count=like_count,
            comment_count=comment_count,
            is_liked=is_liked,
            owner_name=f"{owner.name} {owner.surname}" if owner else "Bilinmiyor"
        ))

    return feed


# ─────────────────────────────────────────
# BEĞENİ
# ─────────────────────────────────────────

@router.post("/{scan_id}/like", status_code=status.HTTP_200_OK, tags=["Community"])
async def toggle_like(
    scan_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Beğen / beğeniyi geri al. Her çağrıda toggle yapar."""

    # Scan var mı?
    scan = await db.get(Scans, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Araç bulunamadı.")

    # Daha önce beğenmiş mi?
    result = await db.execute(
        select(Like).where(Like.scan_id == scan_id, Like.user_id == current_user.user_id)
    )
    existing_like = result.scalar_one_or_none()

    if existing_like:
        # Beğeniyi geri al
        await db.delete(existing_like)
        await db.commit()
        return {"liked": False, "message": "Beğeni kaldırıldı."}
    else:
        # Beğen
        new_like = Like(user_id=current_user.user_id, scan_id=scan_id)
        db.add(new_like)
        await db.commit()
        return {"liked": True, "message": "Beğenildi."}


# ─────────────────────────────────────────
# YORUMLAR
# ─────────────────────────────────────────

@router.get("/{scan_id}/comments", response_model=List[CommentResponse], tags=["Community"])
async def get_comments(
    scan_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Bir aracın yorumlarını listeler."""
    result = await db.execute(
        select(Comment)
        .where(Comment.scan_id == scan_id)
        .order_by(Comment.created_at.desc())
    )
    return result.scalars().all()


@router.post("/{scan_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED, tags=["Community"])
async def add_comment(
    scan_id: int,
    comment_in: CommentCreate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Bir araca yorum ekler."""
    scan = await db.get(Scans, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Araç bulunamadı.")

    new_comment = Comment(
        user_id=current_user.user_id,
        scan_id=scan_id,
        content=comment_in.content
    )
    db.add(new_comment)
    await db.commit()
    await db.refresh(new_comment)
    return new_comment


@router.delete("/comments/{comment_id}", status_code=status.HTTP_200_OK, tags=["Community"])
async def delete_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Kendi yorumunu siler."""
    result = await db.execute(select(Comment).where(Comment.comment_id == comment_id))
    comment = result.scalar_one_or_none()

    if not comment:
        raise HTTPException(status_code=404, detail="Yorum bulunamadı.")

    if comment.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Bu yorumu silme yetkiniz yok.")

    await db.delete(comment)
    await db.commit()
    return {"message": "Yorum silindi."}


# ─────────────────────────────────────────
# TOPLULUKLA PAYLAŞMA
# ─────────────────────────────────────────

@router.post("/{scan_id}/share", status_code=status.HTTP_200_OK, tags=["Community"])
async def share_to_community(
    scan_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Aracı toplulukla paylaşır (keşfette görünür hale getirir)."""
    scan = await db.get(Scans, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Araç bulunamadı.")
    if scan.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Bu araca erişim yetkiniz yok.")
    if scan.status != "completed":
        raise HTTPException(status_code=400, detail="Sadece tamamlanmış araçlar paylaşılabilir.")

    scan.is_shared = True
    await db.commit()
    return {"message": "Araç toplulukla paylaşıldı!", "is_shared": True}


@router.post("/{scan_id}/unshare", status_code=status.HTTP_200_OK, tags=["Community"])
async def unshare_from_community(
    scan_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Aracı keşfetten kaldırır."""
    scan = await db.get(Scans, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Araç bulunamadı.")
    if scan.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Bu araca erişim yetkiniz yok.")

    scan.is_shared = False
    await db.commit()
    return {"message": "Araç keşfetten kaldırıldı.", "is_shared": False}