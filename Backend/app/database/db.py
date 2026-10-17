from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine ,AsyncSession
from sqlalchemy.orm import sessionmaker
from app.database.base import Base
from dotenv import load_dotenv
import os

load_dotenv()

DB_URL = os.getenv("DB_URL")

engine = create_async_engine(DB_URL, echo = True)

AsyncSessionLocal = async_sessionmaker(bind=engine,expire_on_commit=False)


from sqlalchemy import text

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session



