from fastapi import FastAPI, Depends,HTTPException
from pydantic import BaseModel
from typing import List , Annotated
from Backend.app.database.models.user import User
from database.db import SessionLocal, engine
from sqlalchemy.orm import Session
from database import models

app = FastAPI()
models.Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
db_dependency = Annotated[Session, Depends(get_db)]
    
@app.post("/users/")
async def create_user(user: User , db: db_dependency):
    db_user = models.User(name=user.name, email=user.email, password=user.password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
        