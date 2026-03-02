from sqlalchemy import text

from app.db.base import Base
from app.db.session import engine
from app import models  # noqa: F401


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 轻量兼容迁移：为已有 content_records 表补充 user_id 字段。
        result = await conn.execute(text("PRAGMA table_info(content_records)"))
        columns = {row[1] for row in result.fetchall()}
        if "user_id" not in columns:
            await conn.execute(
                text(
                    "ALTER TABLE content_records "
                    "ADD COLUMN user_id VARCHAR(64) NOT NULL DEFAULT 'anonymous'"
                )
            )

        # 轻量兼容迁移：为旧版 users 表补充微信登录字段。
        users_result = await conn.execute(text("PRAGMA table_info(users)"))
        user_columns = {row[1] for row in users_result.fetchall()}
        if "wx_openid" not in user_columns:
            await conn.execute(text("ALTER TABLE users ADD COLUMN wx_openid VARCHAR(128)"))
