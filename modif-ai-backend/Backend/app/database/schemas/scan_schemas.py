from pydantic import BaseModel , Field, model_validator
from datetime import datetime
from typing import Any, List, Optional

class ScanBase(BaseModel):
    method: str
    status: Optional[str] = Field(default = "pending")
    
class ScanCreate(ScanBase):
    user_id: int
    
class Processed3DInfo(BaseModel):
    thumbnail_url: Optional[str] = None
    model_url: Optional[str] = None
 
    class Config:
        from_attributes = True
 
 
class Processed2DInfo(BaseModel):
    thumbnail_url: Optional[str] = None
    image_url: Optional[str] = None
 
    class Config:
        from_attributes = True
    
class ScanResponse(BaseModel):
    scan_id: int
    method: str
    status: str
    created_at: datetime
    car_name: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    
    # Bunlar veritabanından gelen ham veriler, 
    # 'exclude=True' diyerek Flutter'a gitmesini engelliyoruz (kalabalık yapmasın)
    processed_3d: Optional[Processed3DInfo] = Field(default=None, exclude=True)
    processed_2d: Optional[Processed2DInfo] = Field(default=None, exclude=True)

    class Config:
        from_attributes = True 
        
    @model_validator(mode='after')
    def set_thumbnail(self) -> 'ScanResponse':
        # Hangisinde thumbnail varsa onu ana alana kopyala
        if self.processed_3d and len(self.processed_3d) > 0:
            self.thumbnail_url = self.processed_3d[0].thumbnail_url
        elif self.processed_2d and len(self.processed_2d) > 0:
            self.thumbnail_url = self.processed_2d[0].thumbnail_url
        return self
        

