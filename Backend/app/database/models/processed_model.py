from app.database.base import Base
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

class ProcessedModel(Base):
    __tablename__ = "processed_models"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id"), index=True, unique=True)
    model_url = Column(String, index=True)
    thumbnail_url = Column(String, index=True)
    file_size = Column(Integer, index=True)
    
    scan = relationship("Scans", back_populates="processed_models")
    