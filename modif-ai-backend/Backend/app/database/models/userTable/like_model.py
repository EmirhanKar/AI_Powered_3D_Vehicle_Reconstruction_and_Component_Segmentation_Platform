from app.database.base import Base
from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship


class Like(Base):
    __tablename__ = "likes"

    like_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    scan_id = Column(Integer, ForeignKey("scans.scan_id"), nullable=False)

    # Bir kullanıcı aynı araca sadece bir kez beğeni yapabilir
    __table_args__ = (
        UniqueConstraint("user_id", "scan_id", name="unique_user_scan_like"),
    )

    user = relationship("User", back_populates="likes")
    scan = relationship("Scans", back_populates="likes")