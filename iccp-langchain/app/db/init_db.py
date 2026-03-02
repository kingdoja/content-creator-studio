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
