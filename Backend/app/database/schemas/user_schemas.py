from pydantic import BaseModel , EmailStr , Field
from typing import Optional

class UserBase(BaseModel):
    name: str
    surname : str
    email: EmailStr
    
class UserCreate(UserBase):
    password : str = Field(min_length=8)
    
class UserLogin(BaseModel):
    email: EmailStr
    password: str
    
class UserToken(BaseModel):
    access_token: str
    token_type: str

    class Config:
        from_attributes = True
    
class UserResponse(UserBase):
    user_id: int

    class Config:
        from_attributes = True