"""
Scans tablosuna is_shared kolonu ekler (PostgreSQL).
Bu script, mevcut veritabanını güncellemek için bir kez çalıştırılmalıdır.
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv
import os

load_dotenv()

DB_URL = os.getenv("DB_URL", "postgresql+asyncpg://postgres:1234@localhost:5432/modifai")

async def migrate():
    engine = create_async_engine(DB_URL)
    async with engine.begin() as conn:
        # Kolon var mı kontrol et
        result = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'scans' AND column_name = 'is_shared'"
        ))
        exists = result.fetchone()
        
        if not exists:
            await conn.execute(text(
                "ALTER TABLE scans ADD COLUMN is_shared BOOLEAN NOT NULL DEFAULT FALSE"
            ))
            print("[OK] 'is_shared' kolonu scans tablosuna eklendi.")
        else:
            print("[INFO] 'is_shared' kolonu zaten mevcut.")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
