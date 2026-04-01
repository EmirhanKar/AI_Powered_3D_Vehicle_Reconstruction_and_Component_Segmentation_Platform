from datetime import datetime, timezone

from sqlalchemy import select

from fastapi import APIRouter, Depends, HTTPException ,status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.db import get_session
from app.database.schemas import UserCreate , UserResponse , UserLogin , UserToken
from app.database.schemas import UserStatsCreate
from app.database.crud import user_crud , userstats_crud
from app.database.models import User , UserStats , Subscription
from app.core import get_password_hash, verify_password , create_access_token
from app.api import get_current_user
from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter(prefix="/users")

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserCreate, db: AsyncSession = Depends(get_session)):
    db_user = await db.execute(select(User).where(User.email == user_in.email))
    if db_user.scalars().first():
        raise HTTPException(status_code=400, detail="Bu e-posta zaten kayıtlı")

    hashed_password = get_password_hash(user_in.password)
    new_user = User(
        name=user_in.name,
        surname=user_in.surname,
        email=user_in.email,
        password=hashed_password
    )
        
    db.add(new_user)
    await db.flush() 

    #otomatik olarak userstats ve subscription tablosuna da kayıt ekleniyor.
    new_stats = UserStats(
        user_id=new_user.user_id, 
        user_credi=0,
        create_image=0,
        render_image=0
    )
        
    db.add(new_stats)
    
    new_subs = Subscription(
        user_id=new_user.user_id,
        tier="free",
        start_date= datetime.now(timezone.utc).replace(tzinfo=None),
        end_date=None
    )
    
    db.add(new_subs)
    
    await db.commit()
    await db.refresh(new_user)
        
    return new_user



@router.post("/login", response_model = UserToken , status_code = status.HTTP_200_OK)
async def login_user(form_data : OAuth2PasswordRequestForm = Depends(), db : AsyncSession = Depends(get_session)):
    result = await db.execute(select(User).where(User.email == form_data.username))    
    db_user = result.scalars().first()
    
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-posta veya şifre hatalı"
        )
    
    is_password_correct = verify_password(
        plain_password = form_data.password,
        hashed_password = db_user.password
    )
    
    if not is_password_correct:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED
        )    
    
    token_data = {"sub" : str(db_user.user_id)}
    
    access_token = create_access_token(data = token_data)
    return{
        "access_token": access_token,
        "token_type" : "bearer"
    }
    
    
@router.get("/me",response_model = UserResponse)
async def get_my_profil(db : AsyncSession = Depends(get_session),current_user: User = Depends(get_current_user)):
    
    result = await db.execute(select(UserStats).where(UserStats.user_id == current_user.user_id))
    user_stats = result.scalar()
    return {
        "user_id": current_user.user_id,
        "name": current_user.name,
        "surname": current_user.surname,
        "email": current_user.email,
        "profil_image_url": current_user.profil_image_url,
        "user_credi": user_stats.user_credi if user_stats else 0,
        "create_image": user_stats.create_image if user_stats else 0,
        "render_image": user_stats.render_image if user_stats else 0
    }