from pydantic import BaseModel , EmailStr , Field
from typing import Optional

class UserBase(BaseModel):
    name: str
    email: EmailStr
    
class UserCreate(UserBase):
    password : str = Field(min_length=8)
    
class UserResponse(UserBase):
    id: int

    class Config:
        from_attributes = True