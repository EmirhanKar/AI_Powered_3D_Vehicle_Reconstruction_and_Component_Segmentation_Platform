#tarama işlemiyle ilgili bilgileri tutmak için oluşturulan tablo

from datetime import datetime , timezone
from app.database.base import Base
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

class Scans(Base):
    __tablename__ = 'scans'

    scan_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), index=True , nullable=False)
    method = Column(String, index=True , nullable=False) #bu alan, tarama işleminin hangi yöntemle yapıldığını tutmak için kullanılacak. 3d mi , 2dmi.
    status = Column(String, index=True, default="pending")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    images = relationship("ScanImage", back_populates="scan", cascade="all, delete-orphan")
    processed_3d = relationship("Processed3D", back_populates="scan", cascade="all, delete-orphan" , uselist=False)
    modifications = relationship("Modification", back_populates="scan", cascade="all, delete-orphan")
    community = relationship("Community", back_populates="scan", cascade="all, delete-orphan" , uselist=False)
    processed_2d = relationship("Processed2D", back_populates="scan", cascade="all, delete-orphan" , uselist=False)
    