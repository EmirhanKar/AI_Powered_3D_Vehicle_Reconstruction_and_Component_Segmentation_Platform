#eklenecek eklentilerin bilgilerini tutmak için oluşturulan tablo

from app.database.base import Base
from sqlalchemy import Column,ForeignKey, Integer, String
from sqlalchemy.orm import relationship

class Modification(Base):
    __tablename__ = "modifications"

    modification_id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.scan_id"), index=True , nullable=True)
    color_id = Column(Integer, ForeignKey("colors.color_id"), index=True , nullable=True)
    jant_id = Column(Integer,ForeignKey("jant.jant_id"), index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), index=True)

    
    scan = relationship("Scans", back_populates="modifications")
    user = relationship("User", back_populates="modifications")
    jant = relationship("Jant", back_populates="modifications")
    scan_images = relationship("ScanImage", back_populates="modifications")
    colors = relationship("Colors", back_populates="modifications")