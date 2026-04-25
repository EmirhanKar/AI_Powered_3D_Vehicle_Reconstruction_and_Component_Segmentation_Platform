from datetime import datetime, timezone

from sqlalchemy import select

from fastapi import APIRouter, Depends, HTTPException ,status , UploadFile, File 
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.db import get_session
from app.database.schemas import UserCreate , UserResponse , UserLogin , UserToken , UserUpdate , UserStatsResponse
from app.database.crud import user_crud , userstats_crud
from app.database.models import User , UserStats , Subscription
from app.core import get_password_hash, verify_password , create_access_token
from app.api import get_current_user
from fastapi.security import OAuth2PasswordRequestForm
import os , uuid

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
    
    
@router.post("/me/upload-photo", response_model=UserResponse)
async def upload_profile_photo(
    photo: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # 1. Sadece resim kabul et
    if photo.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(
            status_code=400,
            detail="Sadece JPEG, PNG veya WEBP kabul edilir."
        )
 
    # 2. Dosyayı kaydet
    upload_dir = os.path.join("uploads", "profiles")
    os.makedirs(upload_dir, exist_ok=True)
 
    extension = photo.filename.split(".")[-1]
    unique_filename = f"profile_{current_user.user_id}_{uuid.uuid4()}.{extension}"
    full_path = os.path.join(upload_dir, unique_filename).replace("\\", "/")
 
    content = await photo.read()
    with open(full_path, "wb") as f:
        f.write(content)
 
    # 3. Eski fotoğraf varsa sil
    if current_user.profil_image_url and os.path.exists(current_user.profil_image_url):
        os.remove(current_user.profil_image_url)
 
    # 4. DB'yi güncelle
    current_user.profil_image_url = full_path
    await db.commit()
    await db.refresh(current_user)
 
    # 5. UserStats'ı da çek (UserResponse için gerekli)
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
        "render_image": user_stats.render_image if user_stats else 0,
    }
    
@router.patch("/me", response_model=UserResponse)
async def update_my_profile(
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Sadece gönderilen alanları güncelle, None olanları atla
    if user_in.name is not None:
        current_user.name = user_in.name
 
    if user_in.surname is not None:
        current_user.surname = user_in.surname
 
    if user_in.email is not None:
        # Email başkası tarafından kullanılıyor mu?
        result = await db.execute(select(User).where(User.email == user_in.email))
        existing = result.scalar_one_or_none()
        if existing and existing.user_id != current_user.user_id:
            raise HTTPException(status_code=400, detail="Bu e-posta zaten kullanımda.")
        current_user.email = user_in.email
 
    if user_in.password is not None:
        current_user.password = get_password_hash(user_in.password)
 
    await db.commit()
    await db.refresh(current_user)
 
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
        "render_image": user_stats.render_image if user_stats else 0,
    }