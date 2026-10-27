"""
Chat for assistant agents: conversations, attachments and streamed replies.

An assistant agent is an AIAgentConfiguration with kind="assistant". It has its own
instructions (system_prompt) and is linked to a saved AIProviderConfiguration whose
key/model are used for every reply.
"""
from __future__ import annotations

import base64
import io
import json
import re
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_agent.providers import ChatImage, ChatMessage, canonical_provider, create_ai_provider, friendly_error
from app.core.config import settings
from app.core.exceptions import NotFoundException
from app.core.security import decrypt_value
from app.domain.models.ai_agent import (
    AIAgentConfiguration,
    AIAttachment,
    AIConversation,
    AIMessage,
    AIProviderConfiguration,
)

log = structlog.get_logger(__name__)

MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024
MAX_EXTRACTED_CHARS = 60_000          # per file, keeps the prompt within reason
MAX_HISTORY_MESSAGES = 40             # turns sent back to the model per reply
IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
TEXT_TYPES = {
    "text/plain", "text/markdown", "text/csv", "text/html", "text/xml", "application/json",
    "application/xml", "application/javascript", "application/x-yaml", "text/yaml",
}
TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".xml", ".html", ".css", ".js", ".ts",
    ".tsx", ".jsx", ".py", ".rb", ".go", ".rs", ".java", ".kt", ".cs", ".c", ".h", ".cpp",
    ".sql", ".sh", ".ps1", ".toml", ".ini", ".env", ".log", ".svg",
}
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


# ── Text extraction ──────────────────────────────────────────────────────────

def extract_text(filename: str, content_type: str, data: bytes) -> Optional[str]:
    """Pull readable text out of an upload so it can be given to the model.

    Returns None for images (sent as vision input) and for formats we can't read.
    """
    ext = Path(filename).suffix.lower()
    if content_type in IMAGE_TYPES:
        return None
    text: Optional[str] = None
    if content_type == "application/pdf" or ext == ".pdf":
        text = _extract_pdf(data)
    elif content_type == DOCX_TYPE or ext == ".docx":
        text = _extract_docx(data)
    elif content_type in TEXT_TYPES or content_type.startswith("text/") or ext in TEXT_EXTENSIONS:
        text = data.decode("utf-8", errors="replace")
    if text is None:
        return None
    text = text.strip()
    if len(text) > MAX_EXTRACTED_CHARS:
        text = text[:MAX_EXTRACTED_CHARS] + "\n…[truncated]"
    return text


def _extract_pdf(data: bytes) -> Optional[str]:
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover
        return None
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # noqa: BLE001
        log.warning("pdf extraction failed", error=str(exc))
        return None


def _extract_docx(data: bytes) -> Optional[str]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return None
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml)


# ── Service ──────────────────────────────────────────────────────────────────

class AgentChatService:
    def __init__(self, db: AsyncSession):
        self._db = db
        self._root = Path(settings.agent_attachments_path)

    # ── agents ──
    async def get_assistant(self, agent_id: uuid.UUID, tenant_id: Optional[uuid.UUID]) -> AIAgentConfiguration:
        agent = (await self._db.execute(
            select(AIAgentConfiguration).where(
                AIAgentConfiguration.id == agent_id,
                AIAgentConfiguration.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()
        if not agent:
            raise NotFoundException("Agent not found.")
        if agent.kind != "assistant":
            raise ValueError("Only assistant agents support chat. The build agent generates code from the Generate page.")
        return agent

    # ── conversations ──
    async def list_conversations(self, agent_id: uuid.UUID, tenant_id, user_id: uuid.UUID) -> list[AIConversation]:
        rows = (await self._db.execute(
            select(AIConversation).where(
                AIConversation.agent_id == agent_id,
                AIConversation.tenant_id == tenant_id,
                AIConversation.user_id == user_id,
            ).order_by(AIConversation.updated_at.desc().nullslast(), AIConversation.created_at.desc())
        )).scalars().all()
        return list(rows)

    async def create_conversation(self, agent_id: uuid.UUID, tenant_id, user_id: uuid.UUID) -> AIConversation:
        await self.get_assistant(agent_id, tenant_id)
        convo = AIConversation(
            id=uuid.uuid4(), tenant_id=tenant_id, agent_id=agent_id, user_id=user_id,
            title="New chat", created_at=datetime.now(timezone.utc),
        )
        self._db.add(convo)
        await self._db.commit()
        await self._db.refresh(convo)
        return convo

    async def get_conversation(self, convo_id: uuid.UUID, tenant_id, user_id: uuid.UUID) -> AIConversation:
        convo = (await self._db.execute(
            select(AIConversation).where(
                AIConversation.id == convo_id,
                AIConversation.tenant_id == tenant_id,
                AIConversation.user_id == user_id,
            )
        )).scalar_one_or_none()
        if not convo:
            raise NotFoundException("Conversation not found.")
        return convo

    async def list_messages(self, convo_id: uuid.UUID, tenant_id, user_id: uuid.UUID) -> list[AIMessage]:
        convo = await self.get_conversation(convo_id, tenant_id, user_id)
        rows = (await self._db.execute(
            select(AIMessage).where(AIMessage.conversation_id == convo.id).order_by(AIMessage.created_at)
        )).scalars().all()
        return list(rows)

    async def rename_conversation(self, convo_id, tenant_id, user_id, title: str) -> AIConversation:
        convo = await self.get_conversation(convo_id, tenant_id, user_id)
        convo.title = title.strip()[:200] or "New chat"
        await self._db.commit()
        await self._db.refresh(convo)
        return convo

    async def delete_conversation(self, convo_id, tenant_id, user_id) -> None:
        convo = await self.get_conversation(convo_id, tenant_id, user_id)
        for att in (await self._db.execute(
            select(AIAttachment).where(AIAttachment.conversation_id == convo.id)
        )).scalars():
            self._delete_file(att.storage_path)
            await self._db.delete(att)
        await self._db.delete(convo)
        await self._db.commit()

    # ── attachments ──
    async def save_attachment(
        self, tenant_id, user_id: uuid.UUID, filename: str, content_type: str, data: bytes,
    ) -> AIAttachment:
        if len(data) > MAX_ATTACHMENT_BYTES:
            raise ValueError(f"File exceeds the {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB limit.")
        safe_name = Path(filename or "upload").name[:255] or "upload"
        content_type = (content_type or "application/octet-stream").split(";")[0].strip()
        att_id = uuid.uuid4()
        folder = self._root / str(tenant_id or "host")
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{att_id}{Path(safe_name).suffix.lower()[:16]}"
        path.write_bytes(data)
        att = AIAttachment(
            id=att_id, tenant_id=tenant_id, user_id=user_id, filename=safe_name,
            content_type=content_type, size_bytes=len(data), storage_path=str(path),
            extracted_text=extract_text(safe_name, content_type, data),
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(att)
        await self._db.commit()
        await self._db.refresh(att)
        return att

    async def get_attachment(self, att_id: uuid.UUID, tenant_id, user_id: uuid.UUID) -> AIAttachment:
        att = (await self._db.execute(
            select(AIAttachment).where(
                AIAttachment.id == att_id, AIAttachment.tenant_id == tenant_id, AIAttachment.user_id == user_id,
            )
        )).scalar_one_or_none()
        if not att:
            raise NotFoundException("Attachment not found.")
        return att

    def _delete_file(self, storage_path: str) -> None:
        try:
            Path(storage_path).unlink(missing_ok=True)
        except OSError:
            pass

    # ── sending a message ──
    async def send_message(
        self,
        convo_id: uuid.UUID,
        tenant_id,
        user_id: uuid.UUID,
        text: str,
        attachment_ids: list[uuid.UUID],
    ) -> AsyncIterator[dict]:
        """Persist the user turn, stream the assistant reply, persist it. Yields SSE-ready events."""
        convo = await self.get_conversation(convo_id, tenant_id, user_id)
        agent = await self.get_assistant(convo.agent_id, tenant_id)

        attachments: list[AIAttachment] = []
        for att_id in attachment_ids:
            att = await self.get_attachment(att_id, tenant_id, user_id)
            att.conversation_id = convo.id
            attachments.append(att)

        user_msg = AIMessage(
            id=uuid.uuid4(), conversation_id=convo.id, role="user", content=text,
            attachments=[_attachment_summary(a) for a in attachments] or None,
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(user_msg)
        if convo.title == "New chat" and (text.strip() or attachments):
            convo.title = _title_from(text, attachments)
        convo.updated_at = datetime.now(timezone.utc)
        await self._db.commit()
        yield {"type": "user_message", "message": message_to_dict(user_msg), "title": convo.title}

        assistant_msg = AIMessage(
            id=uuid.uuid4(), conversation_id=convo.id, role="assistant", content="",
            created_at=datetime.now(timezone.utc),
        )
        yield {"type": "assistant_start", "message_id": str(assistant_msg.id)}

        try:
            client, model = await self._client_for(agent, tenant_id)
            assistant_msg.model = model
            history = await self._history(convo.id, attachments_for_last=attachments)
            temperature = float(agent.temperature) if agent.temperature is not None else 0.7
            parts: list[str] = []
            async for chunk in client.stream_chat(
                agent.system_prompt or "", history, temperature=temperature,
            ):
                if chunk.text:
                    parts.append(chunk.text)
                    yield {"type": "token", "text": chunk.text}
                if chunk.done:
                    assistant_msg.tokens_used = chunk.tokens_used
            assistant_msg.content = "".join(parts)
        except Exception as exc:  # noqa: BLE001 - every failure becomes a readable chat error
            assistant_msg.error = friendly_error(exc) if not isinstance(exc, ValueError) else str(exc)
            log.warning("assistant reply failed", agent_id=str(agent.id), error=assistant_msg.error)

        self._db.add(assistant_msg)
        convo.updated_at = datetime.now(timezone.utc)
        await self._db.commit()
        await self._db.refresh(assistant_msg)
        yield {"type": "done", "message": message_to_dict(assistant_msg)}

    async def _client_for(self, agent: AIAgentConfiguration, tenant_id):
        if not agent.provider_id:
            raise ValueError("This agent has no AI provider. Edit the agent and choose one.")
        provider = (await self._db.execute(
            select(AIProviderConfiguration).where(
                AIProviderConfiguration.id == agent.provider_id,
                AIProviderConfiguration.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()
        if not provider:
            raise ValueError("The provider linked to this agent was deleted. Edit the agent and choose another.")
        api_key = decrypt_value(provider.api_key_encrypted, settings.encryption_key) if provider.api_key_encrypted else ""
        name = canonical_provider(provider.provider_name)
        if name == "azure":
            from app.ai_agent.azure_config import azure_deployment_name
            model = (agent.ai_model or "").strip() or azure_deployment_name(provider)
        else:
            model = (agent.ai_model or "").strip() or (provider.model_name or "").strip()
        if not model:
            raise ValueError("No model is set for this agent or its provider.")
        client = create_ai_provider(name, api_key, model, provider.endpoint or provider.endpoint_url or None)
        return client, model

    async def _history(self, convo_id: uuid.UUID, attachments_for_last: list[AIAttachment]) -> list[ChatMessage]:
        rows = (await self._db.execute(
            select(AIMessage).where(AIMessage.conversation_id == convo_id).order_by(AIMessage.created_at)
        )).scalars().all()
        rows = [r for r in rows if not r.error][-MAX_HISTORY_MESSAGES:]
        history: list[ChatMessage] = []
        for i, row in enumerate(rows):
            content = row.content or ""
            images: list[ChatImage] = []
            if row.role == "user" and row.attachments:
                # Only the newest turn gets the full file contents; earlier turns keep a short note
                # so long chats with many files don't blow the context window.
                is_last = i == len(rows) - 1
                blocks: list[str] = []
                for summary in row.attachments:
                    att = next((a for a in attachments_for_last if str(a.id) == summary.get("id")), None) if is_last else None
                    if att is None:
                        att = await self._db.get(AIAttachment, uuid.UUID(summary["id"])) if is_last else None
                    if att and att.content_type in IMAGE_TYPES:
                        try:
                            images.append(ChatImage(att.content_type, base64.b64encode(Path(att.storage_path).read_bytes()).decode()))
                        except OSError:
                            blocks.append(f"[image {att.filename} is no longer available]")
                    elif att and att.extracted_text:
                        blocks.append(f"<attached_file name=\"{att.filename}\">\n{att.extracted_text}\n</attached_file>")
                    elif att:
                        blocks.append(f"[attached file {att.filename} ({att.content_type}) could not be read as text]")
                    else:
                        blocks.append(f"[earlier attachment: {summary.get('filename')}]")
                if blocks:
                    content = "\n\n".join(blocks + ([content] if content else []))
            if not content and not images:
                continue
            history.append(ChatMessage(row.role, content, images))
        return history


def _attachment_summary(a: AIAttachment) -> dict:
    return {"id": str(a.id), "filename": a.filename, "content_type": a.content_type, "size_bytes": a.size_bytes}


def _title_from(text: str, attachments: list[AIAttachment]) -> str:
    base = " ".join(text.split())
    if not base and attachments:
        base = attachments[0].filename
    return (base[:57] + "…") if len(base) > 60 else base or "New chat"


def _iso(dt: Optional[datetime]) -> Optional[str]:
    """ISO-8601 with an explicit offset. SQLite drops tzinfo, so naive values are taken as UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def message_to_dict(m: AIMessage) -> dict:
    return {
        "id": str(m.id),
        "conversation_id": str(m.conversation_id),
        "role": m.role,
        "content": m.content or "",
        "attachments": m.attachments or [],
        "model": m.model,
        "tokens_used": m.tokens_used,
        "error": m.error,
        "created_at": _iso(m.created_at),
    }


def conversation_to_dict(c: AIConversation) -> dict:
    return {
        "id": str(c.id),
        "agent_id": str(c.agent_id),
        "title": c.title,
        "created_at": _iso(c.created_at),
        "updated_at": _iso(c.updated_at),
    }


def sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"
