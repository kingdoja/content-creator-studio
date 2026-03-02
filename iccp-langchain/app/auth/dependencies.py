from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import decode_access_token
from app.config import settings
from app.db.session import get_db_session
from app.models.user import User


bearer_scheme = HTTPBearer(auto_error=True)
optional_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效或过期的 token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token 缺少用户标识")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")
    return user


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> User | None:
    if not credentials:
        return None

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效或过期的 token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token 缺少用户标识")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")
    return user


def resolve_user_role(user: User) -> str:
    admin_emails = {
        email.strip().lower()
        for email in (settings.ADMIN_EMAILS or "").split(",")
        if email.strip()
    }
    if user.email.lower() in admin_emails:
        return "admin"
    return "user"


def is_admin_user(user: User | None) -> bool:
    if not user:
        return False
    return resolve_user_role(user) == "admin"


def resolve_scoped_user_id(requested_user_id: str | None, current_user: User | None) -> str:
    requested = (requested_user_id or "").strip()
    if current_user:
        # 登录用户默认只能操作自己的数据；管理员可按需查看/操作指定 user_id。
        if requested and requested != current_user.id and is_admin_user(current_user):
            return requested
        return current_user.id
    # 未登录请求只能访问匿名域，避免通过 user_id 参数越权读写。
    return "anonymous"
