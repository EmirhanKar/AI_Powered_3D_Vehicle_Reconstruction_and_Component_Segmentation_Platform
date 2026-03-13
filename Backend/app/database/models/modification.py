from app.database.db import Base
from sqlalchemy import Column, Boolean , ForeignKey, Integer, String
from sqlalchemy.orm import relationship

class modification(Base):
    __tablename__ = "modifications"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id"), index=True)
    color_code = Column(String, index=True)
    jant_model = Column(String,ForeignKey("jant_models.model_name"), index=True)
    is_saved = Column(Boolean, default=False)
    
    scan = relationship("scan", back_populates="modifications")
    
    jant_models = relationship("jant_models", back_populates="modifications")
    
    