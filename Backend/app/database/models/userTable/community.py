#bu tabloda kullanıcıların beğenileri ve yorumları tutulacak. Bir kullanıcı bir tarama için sadece bir kez beğeni yapabilir. Yorumlar ise ayrı bir tabloda tutulacak. Bu tabloda sadece beğeni sayısı ve kullanıcı ile tarama ilişkisi olacak. Yorumlar ise yorum tablosunda tutulacak. 

from app.database.base import Base
from sqlalchemy import Column, Boolean , ForeignKey, Integer, String
from sqlalchemy.orm import relationship

class Community(Base):
    __tablename__ = "community"
    
    community_id = Column(Integer, primary_key=True, index=True)
    likes = Column(Integer, default=0)
    comment = Column(String, default="")
    user_id = Column(Integer, ForeignKey("users.user_id"), index=True)
    scan_id = Column(Integer, ForeignKey("scans.scan_id"), index=True)
    
    user = relationship("User", back_populates="community")
    scan = relationship("Scans", back_populates="community")