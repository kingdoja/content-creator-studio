from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.knowledge import KnowledgeDocument
from app.models.memory import MemoryLink
from app.models.user import User
from app.rag.knowledge_service import knowledge_service


router = APIRouter()


class KnowledgeUploadRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    source_type: str = Field("text")
    source_uri: Optional[str] = Field(None, max_length=500)


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(4, ge=1, le=20)


@router.post("/upload")
async def upload_knowledge(
    request: KnowledgeUploadRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await knowledge_service.add_document(
            db,
            title=request.title,
            content=request.content,
            source_type=request.source_type,
            source_uri=request.source_uri,
        )
        return {"success": True, "document": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传知识文档失败: {e}")


@router.get("/documents")
async def list_knowledge_documents(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    docs = await knowledge_service.list_documents(db)
    return {"success": True, "documents": docs}


@router.delete("/documents/{doc_id}")
async def delete_knowledge_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    deleted = await knowledge_service.delete_document(db, doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"success": True, "deleted": True}


@router.post("/search")
async def search_knowledge(
    request: KnowledgeSearchRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    results = await knowledge_service.search(db, query=request.query, top_k=request.top_k)
    return {"success": True, "results": results}


@router.get("/stats")
async def knowledge_stats(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    result = await knowledge_service.stats(db)
    return {"success": True, "stats": result}


@router.get("/references")
async def knowledge_references(
    document_id: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(
            MemoryLink.target_id.label("document_id"),
            KnowledgeDocument.title.label("document_title"),
            func.count(MemoryLink.id).label("reference_count"),
            func.max(MemoryLink.created_at).label("last_referenced_at"),
        )
        .join(KnowledgeDocument, KnowledgeDocument.id == MemoryLink.target_id)
        .where(
            MemoryLink.target_type == "knowledge_document",
            MemoryLink.relation == "knowledge_citation",
        )
        .group_by(MemoryLink.target_id, KnowledgeDocument.title)
        .order_by(desc("reference_count"), desc("last_referenced_at"))
        .limit(max(1, min(limit, 100)))
    )
    if document_id:
        stmt = stmt.where(MemoryLink.target_id == document_id)

    rows = (await db.execute(stmt)).all()
    return {
        "success": True,
        "references": [
            {
                "document_id": row.document_id,
                "document_title": row.document_title,
                "reference_count": int(row.reference_count or 0),
                "last_referenced_at": (
                    row.last_referenced_at.isoformat() if row.last_referenced_at else ""
                ),
            }
            for row in rows
        ],
    }
