from app .database.db import Base
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

class ScanImage(Base):
    __tablename__ = 'scan_images'

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id"))
    image_url = Column(String , nullable=False)
    label = Column(String, nullable=True)
    
    scan = relationship("Scans", back_populates="images")   