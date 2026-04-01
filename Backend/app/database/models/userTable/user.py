#kullanıcı bilgilerini tutmak için oluşturulan tablo

from sqlalchemy import Column, Integer, String 
from sqlalchemy.orm import relationship

from app.database.base import Base

class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True)
    name = Column(String)
    surname = Column(String)
    profil_image_url = Column(String, default="")
    email = Column(String, unique=True)
    password = Column(String)

    
    community = relationship("Community", back_populates="user")
    userstats = relationship("UserStats", back_populates="user", uselist=False) 
    subscriptions = relationship("Subscription", back_populates="user")
    modifications = relationship("Modification", back_populates="user")