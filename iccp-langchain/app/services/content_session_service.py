from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


async def persist_content_session_messages(
    *,
    db: AsyncSession,
    manager: Any,
    session_id: str | None,
    user_id: str,
    topic: str,
    content: str,
    module: str,
    metadata_extra: dict[str, Any] | None = None,
) -> None:
    if not session_id or not content:
        return
    session = await manager.get_session(db, session_id=session_id)
    if not session or session.get("user_id") != user_id:
        return

    await manager.add_message(
        db,
        session_id=session_id,
        role="user",
        content=topic,
        message_type="task",
        metadata={"module": module},
    )
    message_metadata = {"module": module}
    if metadata_extra:
        message_metadata.update(metadata_extra)
    await manager.add_message(
        db,
        session_id=session_id,
        role="assistant",
        content=content,
        message_type="result",
        metadata=message_metadata,
    )
