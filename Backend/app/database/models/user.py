from sqlalchemy import Column, Integer, String 
from sqlalchemy.orm import relationship

from app.database.base import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String, unique=True)
    password = Column(String)
    
    userstats = relationship("UserStats", back_populates="user", uselist=False) 
    subscriptions = relationship("Subscription", back_populates="user")

