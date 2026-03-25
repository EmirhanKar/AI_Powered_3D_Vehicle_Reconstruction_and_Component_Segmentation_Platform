from app.database.base import Base
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship 


class Jant(Base):
    __tablename__ = 'jant'

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String, index=True)
    category = Column(String, index=True)
    image_url = Column(String)
    
    modifications = relationship("Modification", back_populates="jant", cascade="all, delete-orphan")    
    
