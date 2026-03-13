from app.database.db import Base
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship 

class Jant(Base):
    __tablename__ = 'jant'

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String, index=True)
    category = Column(String, index=True)
    image_url = Column(String)
    
    modifications = relationship("modification", back_populates="jant_models", cascade="all, delete-orphan")    
    
