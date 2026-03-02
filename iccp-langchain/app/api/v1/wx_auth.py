"""
微信小程序登录接口
通过 wx.login() 获取的 code 换取 openid，自动注册或登录。
"""
import httpx
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import resolve_user_role
from app.auth.security import create_access_token, hash_password
from app.config import settings
from app.db.session import get_db_session
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)

WX_CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"


class WxLoginRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=128, description="wx.login 返回的 code")


async def _code2session(code: str) -> dict:
    """调用微信 code2session 接口获取 openid 和 session_key"""
    if not settings.WX_APPID or not settings.WX_SECRET:
        raise HTTPException(status_code=500, detail="服务端未配置微信小程序 appid/secret")

    params = {
        "appid": settings.WX_APPID,
        "secret": settings.WX_SECRET,
        "js_code": code,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(WX_CODE2SESSION_URL, params=params)
        data = resp.json()

    if data.get("errcode") and data["errcode"] != 0:
        logger.warning("wx code2session error: %s", data)
        raise HTTPException(status_code=400, detail=f"微信登录失败: {data.get('errmsg', '未知错误')}")

    openid = data.get("openid")
    if not openid:
        raise HTTPException(status_code=400, detail="无法获取 openid")

    return data


@router.post("/wx-login")
async def wx_login(request: WxLoginRequest, db: AsyncSession = Depends(get_db_session)):
    """微信小程序登录：code 换 openid → 自动注册/登录 → 返回 JWT"""
    wx_data = await _code2session(request.code)
    openid = wx_data["openid"]

    result = await db.execute(select(User).where(User.wx_openid == openid))
    user = result.scalar_one_or_none()

    if not user:
        short_id = uuid4().hex[:8]
        user = User(
            username=f"wx_{short_id}",
            email=f"wx_{short_id}@miniprogram.local",
            hashed_password=hash_password(uuid4().hex),
            wx_openid=openid,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("wx new user registered: %s openid=%s", user.id, openid[:8])

    token = create_access_token({"sub": user.id, "email": user.email})
    role = resolve_user_role(user)

    return {
        "success": True,
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": role,
        },
    }
