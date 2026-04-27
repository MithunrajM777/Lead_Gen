from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from .. import models
from ..services import auth
from ..database import get_db

router = APIRouter()

@router.post("/signup")
def signup(user_data: dict, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.username == user_data["username"]).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    new_user = models.User(
        username=user_data["username"],
        email=user_data.get("email"),
        hashed_password=auth.get_password_hash(user_data["password"]),
        credits=100,
        role=models.UserRole.USER.value,
        plan="free",
        is_approved=0
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User created. Awaiting admin approval.", "username": new_user.username}

@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect username or password")
    
    if user.role != models.UserRole.ADMIN.value and not user.is_approved:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your account is pending admin approval")
    
    access_token = auth.create_access_token(data={"sub": user.username, "role": user.role})
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user": {"username": user.username, "role": user.role}
    }

@router.get("/me")
async def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "credits": current_user.credits,
        "role": current_user.role,
        "plan": current_user.plan,
        "is_approved": bool(current_user.is_approved),
        "is_admin": auth.is_admin(current_user),
    }
