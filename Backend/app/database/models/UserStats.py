from sqlalchemy import Column, ForeignKey, Integer, String 
from app.database.db import Base
from sqlalchemy.orm import relationship

class UserStats(Base):
    __tablename__ = "user_stats"
    id = Column(Integer, primary_key=True)
    user_id = ForeignKey("users.id")
    user_credi = Column(Integer, default=0)
    create_image = Column(Integer, default=0)
    render_image = Column(Integer, default=0)
    

    user = relationship("User", back_populates="UserStats")     

