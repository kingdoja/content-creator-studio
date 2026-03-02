from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, resolve_user_role
from app.auth.security import create_access_token, hash_password, verify_password
from app.db.session import get_db_session
from app.models.user import User


router = APIRouter()


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


@router.post("/register")
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db_session)):
    existing = await db.execute(
        select(User).where(or_(User.email == request.email, User.username == request.username))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="邮箱或用户名已存在")

    user = User(
        username=request.username.strip(),
        email=request.email.lower(),
        hashed_password=hash_password(request.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token({"sub": user.id, "email": user.email})
    role = resolve_user_role(user)
    return {
        "success": True,
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "username": user.username, "email": user.email, "role": role},
    }


@router.post("/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(User).where(User.email == request.email.lower()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    token = create_access_token({"sub": user.id, "email": user.email})
    role = resolve_user_role(user)
    return {
        "success": True,
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "username": user.username, "email": user.email, "role": role},
    }


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    role = resolve_user_role(current_user)
    return {
        "success": True,
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "is_active": current_user.is_active,
            "role": role,
        },
    }
