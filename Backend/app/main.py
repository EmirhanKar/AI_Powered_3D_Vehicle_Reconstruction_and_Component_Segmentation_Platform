from sys import prefix

from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.openapi.utils import get_openapi
from fastapi.security import OAuth2PasswordBearer
from app.database.db import init_db
from app.api.routers import user_router , upload_image_router
from fastapi.staticfiles import StaticFiles
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Veritabanı tabloları kontrol ediliyor...")
    await init_db()
    yield
    print("🔌 Uygulama kapanıyor...")

app = FastAPI(
    title="MODIF-AI API",
    description="Araç Modifikasyonu Uygulaması Backend Servisi",
    version="1.0.0",
    lifespan=lifespan
)

UPLOAD_DIRS = ["uploads/images", "uploads/images_2d", "uploads/images_3d"]
for directory in UPLOAD_DIRS:
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/login")

app.include_router(user_router.router, prefix="/users", tags=["Kullanıcı İşlemleri"])

app.include_router(upload_image_router.router, tags=["Scans"])

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/", tags=["Sistem"])
async def root():
    return {
        "status": "online",
        "message": "MODIF-AI API'ye hoş geldiniz!",
        "docs": "/docs"
    }

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    openapi_schema["components"]["securitySchemes"] = {
        "OAuth2PasswordBearer": {
            "type": "oauth2",
            "flows": {
                "password": {
                    "tokenUrl": "users/login",
                    "scopes": {}
                }
            }
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi