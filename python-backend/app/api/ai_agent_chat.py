"""Chat routes for assistant agents (conversations, attachments, streamed replies)."""
from __future__ import annotations

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.ai_agent.chat_service import (
    MAX_ATTACHMENT_BYTES,
    AgentChatService,
    conversation_to_dict,
    message_to_dict,
    sse,
)
from app.core.dependencies import DBSession, AIAgentUser
from app.core.exceptions import BusinessException
from app.infrastructure.storage import read_upload_capped

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/aiagent", tags=["AIAgentChat"])


class SendMessageRequest(BaseModel):
    content: str = Field("", max_length=50_000)
    attachment_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


class RenameConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


@router.get("/agents/{agent_id}/conversations")
async def list_conversations(agent_id: uuid.UUID, db: DBSession, current_user: AIAgentUser):
    svc = AgentChatService(db)
    rows = await svc.list_conversations(agent_id, current_user.tenant_id, current_user.id)
    return [conversation_to_dict(c) for c in rows]


@router.post("/agents/{agent_id}/conversations", status_code=201)
async def create_conversation(agent_id: uuid.UUID, db: DBSession, current_user: AIAgentUser):
    svc = AgentChatService(db)
    try:
        convo = await svc.create_conversation(agent_id, current_user.tenant_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return conversation_to_dict(convo)


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: uuid.UUID, db: DBSession, current_user: AIAgentUser):
    svc = AgentChatService(db)
    convo = await svc.get_conversation(conversation_id, current_user.tenant_id, current_user.id)
    messages = await svc.list_messages(conversation_id, current_user.tenant_id, current_user.id)
    return {**conversation_to_dict(convo), "messages": [message_to_dict(m) for m in messages]}


@router.patch("/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: uuid.UUID, body: RenameConversationRequest, db: DBSession, current_user: AIAgentUser,
):
    svc = AgentChatService(db)
    convo = await svc.rename_conversation(conversation_id, current_user.tenant_id, current_user.id, body.title)
    return conversation_to_dict(convo)


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: uuid.UUID, db: DBSession, current_user: AIAgentUser):
    await AgentChatService(db).delete_conversation(conversation_id, current_user.tenant_id, current_user.id)


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID, body: SendMessageRequest, db: DBSession, current_user: AIAgentUser,
):
    """Stream the reply as server-sent events: user_message, assistant_start, token*, done."""
    if not body.content.strip() and not body.attachment_ids:
        raise HTTPException(status_code=400, detail="Type a message or attach a file.")
    svc = AgentChatService(db)
    # Validate ownership before the stream starts so auth errors are proper HTTP errors.
    await svc.get_conversation(conversation_id, current_user.tenant_id, current_user.id)

    async def event_stream():
        # The request-scoped session is closed once the response starts streaming,
        # so the generator works in a session of its own.
        import app.infrastructure.database as database

        try:
            async with database.AsyncSessionLocal() as session:
                async for event in AgentChatService(session).send_message(
                    conversation_id, current_user.tenant_id, current_user.id, body.content, body.attachment_ids,
                ):
                    yield sse(event)
        except Exception as exc:  # noqa: BLE001
            log.warning("chat stream failed", error=str(exc))
            message = exc.message if isinstance(exc, BusinessException) and exc.message else "The reply failed."
            yield sse({"type": "error", "message": message})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/attachments", status_code=201)
async def upload_attachment(
    db: DBSession,
    current_user: AIAgentUser,
    file: UploadFile = File(...),
):
    if file.size is not None and file.size > MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 20 MB limit.")
    data = await read_upload_capped(file, MAX_ATTACHMENT_BYTES)
    svc = AgentChatService(db)
    try:
        att = await svc.save_attachment(
            current_user.tenant_id, current_user.id, file.filename or "upload",
            file.content_type or "application/octet-stream", data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": str(att.id),
        "filename": att.filename,
        "content_type": att.content_type,
        "size_bytes": att.size_bytes,
        "readable": att.extracted_text is not None or att.content_type.startswith("image/"),
    }


@router.get("/attachments/{attachment_id}")
async def download_attachment(attachment_id: uuid.UUID, db: DBSession, current_user: AIAgentUser):
    att = await AgentChatService(db).get_attachment(attachment_id, current_user.tenant_id, current_user.id)
    disposition: Optional[str] = "inline" if att.content_type.startswith("image/") else "attachment"
    return FileResponse(att.storage_path, media_type=att.content_type, filename=att.filename,
                        content_disposition_type=disposition)
