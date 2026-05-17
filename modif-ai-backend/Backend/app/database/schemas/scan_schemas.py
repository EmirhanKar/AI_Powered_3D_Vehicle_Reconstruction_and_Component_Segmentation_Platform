from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from typing import Optional, List


class ScanBase(BaseModel):
    method: str
    status: Optional[str] = Field(default="pending")


class ScanCreate(ScanBase):
    user_id: int


class ScanImageBrief(BaseModel):
    image_url: str
    class Config:
        from_attributes = True


class JantBrief(BaseModel):
    model_name: str
    image_url: Optional[str] = None  # 3D servis bunu RIM_PATH olarak kullanır
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
    is_shared: bool = False
    thumbnail_url: Optional[str] = None
    model_url: Optional[str] = None

    processed_3d: Optional[Processed3DInfo] = Field(default=None, exclude=True)
    processed_2d: Optional[Processed2DInfo] = Field(default=None, exclude=True)

    modifications: List[ModificationBrief] = Field(default=[])
    images: List[ScanImageBrief] = Field(default=[])  # Fotoğraf URL'leri

    # Kolay erişim için düzleştirilmiş alanlar
    jant_image_url: Optional[str] = None    # 3D servis bunu RIM_PATH olarak kullanır
    renk_kodu: Optional[str] = None         # 3D servis bunu renk olarak kullanır

    class Config:
        from_attributes = True

    @model_validator(mode='after')
    def set_fields(self) -> 'ScanResponse':
        # Thumbnail ve model URL
        if self.processed_3d:
            self.thumbnail_url = self.processed_3d.thumbnail_url
            self.model_url = self.processed_3d.model_url
        elif self.processed_2d:
            self.thumbnail_url = self.processed_2d.thumbnail_url

        # Jant ve renk bilgisi — 3D servis için
        if self.modifications:
            mod = self.modifications[0]
            if mod.jant:
                self.jant_image_url = mod.jant.image_url
            if mod.colors:
                self.renk_kodu = mod.colors.color_code

        return self