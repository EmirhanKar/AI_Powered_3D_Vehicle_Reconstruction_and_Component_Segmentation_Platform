from fastapi import APIRouter, Depends, HTTPException ,status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.db import get_session
from app.database.schemas.user_schemas import UserCreate , UserResponse
from app.database.crud import user_crud

router = APIRouter()

@router.post("/register", response_model=UserResponse , status_code = status.HTTP_201_CREATED)
async def register_user(user_in: UserCreate, db: AsyncSession = Depends(get_session)):
    db_user = await user_crud.get_user_by_email(db, email=user_in.email)
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bu e-posta zaten kayıtlı")


    new_user = await user_crud.user_create(db, user_in)
    
    return new_user

@router.get("/me",response_model = UserResponse)
async def get_current_user_info():
    return {"message": "Bu endpoint henüz tamamlanmadı."}