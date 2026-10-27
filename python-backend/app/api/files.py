"""File upload routes."""
from __future__ import annotations
import uuid
from pathlib import Path
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select, delete as sa_delete
from app.core.dependencies import DBSession, get_current_user, CurrentUser
from app.infrastructure.storage import StorageService, read_upload_capped
from app.domain.models.misc import FileUpload

_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB — mirrors StorageService.MAX_FILE_SIZE_MB

router = APIRouter(prefix="/api/files", tags=["Files"])

_storage = StorageService()


@router.post("/upload")
async def upload_file(
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    file: UploadFile = File(...),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    is_public: bool = Query(False),
):
    # Guard oversized uploads while streaming so we never buffer more than
    # the cap into memory (handles missing Content-Length / chunked encoding).
    if file.size is not None and file.size > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 50 MB maximum size.")
    content = await read_upload_capped(file, _MAX_UPLOAD_BYTES)
    try:
        meta = await _storage.save_file(
            content=content,
            original_filename=file.filename or "upload",
            mime_type=file.content_type or "application/octet-stream",
            tenant_id=str(current_user.tenant_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    record = FileUpload(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        file_name=meta["filename"],
        original_file_name=meta["original_filename"],
        content_type=meta["mime_type"],
        size_bytes=meta["size_bytes"],
        storage_path=meta["filename"],
        url=meta["url"],
        entity_type=entity_type,
        entity_id=entity_id,
        is_public=is_public,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return {
        "id": str(record.id),
        "file_name": record.file_name,
        "original_file_name": record.original_file_name,
        "content_type": record.content_type,
        "size_bytes": record.size_bytes,
        "url": record.url,
        "entity_type": record.entity_type,
        "entity_id": record.entity_id,
        "is_public": record.is_public,
    }


@router.get("")
async def list_files(
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
):
    stmt = select(FileUpload).where(FileUpload.tenant_id == current_user.tenant_id)
    if entity_type:
        stmt = stmt.where(FileUpload.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(FileUpload.entity_id == entity_id)
    result = await db.execute(stmt)
    files = result.scalars().all()
    return [
        {
            "id": str(f.id),
            "file_name": f.file_name,
            "original_file_name": f.original_file_name,
            "content_type": f.content_type,
            "size_bytes": f.size_bytes,
            "url": f.url,
            "entity_type": f.entity_type,
            "entity_id": f.entity_id,
            "is_public": f.is_public,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in files
    ]


@router.post("/upload-multiple")
async def upload_multiple_files(
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    files: List[UploadFile] = File(...),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    is_public: bool = Query(False),
):
    """Upload several files in one request."""
    results = []
    for file in files:
        if file.size is not None and file.size > _MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"File '{file.filename}' exceeds the 50 MB maximum size.")
        content = await read_upload_capped(file, _MAX_UPLOAD_BYTES)
        try:
            meta = await _storage.save_file(
                content=content,
                original_filename=file.filename or "upload",
                mime_type=file.content_type or "application/octet-stream",
                tenant_id=str(current_user.tenant_id),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        record = FileUpload(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            file_name=meta["filename"],
            original_file_name=meta["original_filename"],
            content_type=meta["mime_type"],
            size_bytes=meta["size_bytes"],
            storage_path=meta["filename"],
            url=meta["url"],
            entity_type=entity_type,
            entity_id=entity_id,
            is_public=is_public,
        )
        db.add(record)
        results.append({
            "file_name": record.file_name,
            "original_file_name": record.original_file_name,
            "content_type": record.content_type,
            "size_bytes": record.size_bytes,
            "url": record.url,
        })
    await db.commit()
    return {"uploaded": len(results), "files": results}


@router.get("/entity/{entity_type}/{entity_id}")
async def get_files_by_entity(
    entity_type: str,
    entity_id: str,
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Return all files attached to a specific entity."""
    result = await db.execute(
        select(FileUpload).where(
            FileUpload.tenant_id == current_user.tenant_id,
            FileUpload.entity_type == entity_type,
            FileUpload.entity_id == entity_id,
        )
    )
    files = result.scalars().all()
    return [
        {
            "id": str(f.id),
            "file_name": f.file_name,
            "original_file_name": f.original_file_name,
            "content_type": f.content_type,
            "size_bytes": f.size_bytes,
            "url": f.url,
            "is_public": f.is_public,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in files
    ]


@router.get("/{file_id}/download")
async def download_file(
    file_id: uuid.UUID,
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Download a file — streams local files, redirects for cloud-backed storage."""
    result = await db.execute(
        select(FileUpload).where(
            FileUpload.id == file_id,
            FileUpload.tenant_id == current_user.tenant_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="File not found")

    from app.core.config import settings as _cfg
    if _cfg.file_storage_backend == "local":
        path = Path(_cfg.local_storage_path) / str(current_user.tenant_id) / record.storage_path
        if not path.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")
        return FileResponse(
            path=str(path),
            media_type=record.content_type,
            filename=record.original_file_name,
        )
    return RedirectResponse(url=record.url)


@router.get("/{file_id}")
async def get_file_metadata(
    file_id: uuid.UUID,
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    result = await db.execute(
        select(FileUpload).where(
            FileUpload.id == file_id,
            FileUpload.tenant_id == current_user.tenant_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    return {
        "id": str(record.id),
        "file_name": record.file_name,
        "original_file_name": record.original_file_name,
        "content_type": record.content_type,
        "size_bytes": record.size_bytes,
        "url": record.url,
        "entity_type": record.entity_type,
        "entity_id": record.entity_id,
        "is_public": record.is_public,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


@router.delete("/{file_id}", status_code=204)
async def delete_file(
    file_id: uuid.UUID,
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    result = await db.execute(
        select(FileUpload).where(
            FileUpload.id == file_id,
            FileUpload.tenant_id == current_user.tenant_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    await _storage.delete_file(str(current_user.tenant_id), record.storage_path)
    await db.execute(
        sa_delete(FileUpload).where(FileUpload.id == file_id)
    )
    await db.commit()
