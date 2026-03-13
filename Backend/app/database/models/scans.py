import datetime

from app.database.db import Base
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

class Scans(Base):
    __tablename__ = 'scans'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    method = Column(String, index=True)
    status = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    images = relationship("ScanImage", back_populates="scan", cascade="all, delete-orphan")
    processed_models = relationship("processed_model", back_populates="scan", cascade="all, delete-orphan")
    