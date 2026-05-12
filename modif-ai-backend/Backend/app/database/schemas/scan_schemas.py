from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from typing import Optional, List


class ScanBase(BaseModel):
    method: str
    status: Optional[str] = Field(default="pending")


class ScanCreate(ScanBase):
    user_id: int

class JantBrief(BaseModel):
    model_name: str
    class Config:
        from_attributes = True

class ColorBrief(BaseModel):
    color_code: str
    class Config:
        from_attributes = True

class ModificationBrief(BaseModel):
    jant: Optional[JantBrief] = None
    colors: Optional[ColorBrief] = None
    class Config:
        from_attributes = True


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
    model_url: Optional[str] = None  # 3D model hazırsa Flutter'a gönder

    # uselist=False olduğu için List değil Optional obje
    processed_3d: Optional[Processed3DInfo] = Field(default=None, exclude=True)
    processed_2d: Optional[Processed2DInfo] = Field(default=None, exclude=True)
    modifications: List[ModificationBrief] = Field(default=[])

    class Config:
        from_attributes = True

    @model_validator(mode='after')
    def set_thumbnail_and_model(self) -> 'ScanResponse':
        if self.processed_3d:
            self.thumbnail_url = self.processed_3d.thumbnail_url
            self.model_url = self.processed_3d.model_url  # 3D hazırsa model URL'i de ver
        elif self.processed_2d:
            self.thumbnail_url = self.processed_2d.thumbnail_url
        return self