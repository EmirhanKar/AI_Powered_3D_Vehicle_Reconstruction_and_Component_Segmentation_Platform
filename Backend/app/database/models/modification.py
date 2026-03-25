from app.database.base import Base
from sqlalchemy import Column, Boolean , ForeignKey, Integer, String
from sqlalchemy.orm import relationship

class Modification(Base):
    __tablename__ = "modifications"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id"), index=True)
    color_code = Column(String, index=True)
    jant_model = Column(Integer,ForeignKey("jant.id"), index=True)
    is_saved = Column(Boolean, default=False)
    
    scan = relationship("Scans", back_populates="modifications")
    
    jant = relationship("Jant", back_populates="modifications")
    
    