import datetime

from app.database.db import Base
from sqlalchemy import Date, DateTime ,ForeignKey ,Column, Integer, String


class Subscription(Base):
    __tablename__ = 'subscriptions'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), index=True)  
    tier = Column(String, index=True)
    start_date = Column(DateTime, default = datetime.utcnow)
    end_date = Column(DateTime, default=datetime.utcnow)