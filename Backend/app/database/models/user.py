from sqlalchemy import Column, Integer, String 
from sqlalchemy.orm import relationship

from app.database.db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String, unique=True)
    password = Column(String)
    
    UserStats = relationship("UserStats", back_populates="user", uselist=False) 


