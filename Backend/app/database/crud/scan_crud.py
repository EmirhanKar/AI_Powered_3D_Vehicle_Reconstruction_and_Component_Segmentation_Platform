from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import Scans
from app.database.schemas import ScanCreate

async def scanCreate(db: AsyncSession, user_id: int, method: str):
    db_scan = Scans(
        user_id=user_id,
        method=method,
        status="pending"
    )
    
    db.add(db_scan)
    await db.commit()
    await db.refresh(db_scan)
    return db_scan


async def scanUpdate(db: AsyncSession, scan_id: int, status: str):
    result = await db.execute(select(Scans).where(Scans.scan_id == scan_id))
    
    db_scan = result.scalars().first() 
    
    if not db_scan:
        return None
        
    db_scan.status = status
    
    await db.commit()
    await db.refresh(db_scan)
    return db_scan 


async def scanRead(db: AsyncSession, scan_id: int):
    result = await db.execute(select(Scans).where(Scans.scan_id == scan_id))
    return result.scalars().first()