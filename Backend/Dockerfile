# MODIF-AI Backend Dockerfile
FROM python:3.12-slim

# Temel ortam değişkenleri
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Çalışma dizini
WORKDIR /app

# Sistem bağımlılıkları (psycopg2, Pillow ve temel derleme araçları)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Bağımlılıkları kopyala ve kur (Docker katman önbelleği için önce sadece requirements)
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Uygulama kodlarını ve alembic migration dosyalarını kopyala
COPY alembic /app/alembic
COPY alembic.ini /app/
COPY app /app/app

# uploads klasörünü oluştur
RUN mkdir -p /app/uploads

# 8000 portunu dışa aç
EXPOSE 8000

# Başlatma komutu: uvicorn sunucusunu başlat (app lifespan içindeki init_db tabloları otomatik oluşturur)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
