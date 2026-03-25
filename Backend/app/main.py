from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database.db import init_db
from app.api.routers import user_router
from app.database.models import Modification , Jant , Scans , User , UserStats , Subscription , ScanImage , processed_model


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Veritabanı tabloları oluşturuluyor...")
    await init_db()
    yield
    
    print ("Uygulama kapanıyor...")
    
app = FastAPI(
    title="MODIF-AI API",
    description="Araç Modifikasyonu Uygulaması Backend Servisi",
    version ="1.0.0",
    lifespan=lifespan
    )

app.include_router(user_router.router, prefix="/users", tags=["Kullanıcı İşlemleri"])

@app.get("/")
async def root():
    return {
        "status" : "online",
        "message" : "MODIF-AI API'ye hoş geldiniz!",
        "docs" : "/docs"
    }