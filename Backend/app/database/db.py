from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine ,AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.database.base import Base

db_url = "postgresql+asyncpg://postgres:1234@localhost:5432/modifai"

engine = create_async_engine(db_url, echo = True)

AsyncSessionLocal = async_sessionmaker(bind=engine,expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session



