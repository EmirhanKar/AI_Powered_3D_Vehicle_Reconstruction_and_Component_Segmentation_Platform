from pydantic import BaseModel , Field
from datetime import datetime
from typing import Optional

class ScanBase(BaseModel):
    method: str
    status: Optional[str] = Field(default = "pending")
    
class ScanCreate(ScanBase):
    user_id: int
    
    
class ScanResponse(ScanBase):
    scan_id: int
    created_at: datetime

    class Config:
        from_attributes = True

