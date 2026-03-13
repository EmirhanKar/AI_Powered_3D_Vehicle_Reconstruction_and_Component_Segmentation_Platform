from app.database.db import Base
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

class processed_model(Base):
    __tablename__ = "processed_models"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id"), index=True)
    model_url = Column(String, index=True)
    thumbnail_url = Column(String, index=True)
    file_size = Column(Integer, index=True)
    
    scan = relationship("scan", back_populates="processed_models")
    