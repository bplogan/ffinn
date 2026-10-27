"""Assistant agents: hub rules, conversations, attachments and streamed replies (provider mocked)."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from tests.test_ai_agent_api import _get_token


async def _headers(client: AsyncClient) -> dict:
    return {"Authorization": f"Bearer {await _get_token(client)}"}


async def _provider(client: AsyncClient, headers: dict) -> str:
    resp = await client.post("/api/aiagent/providers", json={
        "provider_name": "openai", "api_key": "sk-chat", "model_name": "gpt-4o", "display_name": "Chat key",
    }, headers=headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


async def _assistant(client: AsyncClient, headers: dict, provider_id: str, name: "str" = "Support Helper") -> dict:
    resp = await client.post("/api/aiagent/configurations", json={
        "name": name, "kind": "assistant", "provider_config_id": provider_id,
        "description": "Answers support questions", "system_prompt": "You are terse.", "temperature": 0.3,
    }, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _parse_sse(text: str) -> list[dict]:
    return [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]


class _FakeChunk:
    def __init__(self, text="", tokens_used=None, done=False):
        self.text, self.tokens_used, self.done = text, tokens_used, done


def _fake_client(pieces=("Hello", ", ", "world"), tokens=42):
    client = MagicMock()

    async def stream_chat(system_prompt, messages, **kw):
        client.calls.append({"system": system_prompt, "messages": messages, **kw})
        for p in pieces:
            yield _FakeChunk(text=p)
        yield _FakeChunk(tokens_used=tokens, done=True)

    client.calls = []
    client.stream_chat = stream_chat
    return client


# ── Agent hub rules ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_build_agent_is_created_on_first_list_and_cannot_be_deleted(client: AsyncClient):
    headers = await _headers(client)
    listed = (await client.get("/api/aiagent/configurations", headers=headers)).json()
    builds = [a for a in listed["items"] if a["kind"] == "build" and a["is_default"]]
    assert len(builds) == 1
    build = builds[0]

    # Listing again does not create a second one.
    again = (await client.get("/api/aiagent/configurations", headers=headers)).json()
    assert len([a for a in again["items"] if a["is_default"]]) == 1

    resp = await client.delete(f"/api/aiagent/configurations/{build['id']}", headers=headers)
    assert resp.status_code == 409
    assert "cannot be removed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_assistant_agent_requires_a_provider(client: AsyncClient):
    headers = await _headers(client)
    resp = await client.post("/api/aiagent/configurations", json={"name": "No provider", "kind": "assistant"}, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_assistant_agent_round_trips_its_fields_and_can_be_deleted(client: AsyncClient):
    headers = await _headers(client)
    pid = await _provider(client, headers)
    agent = await _assistant(client, headers, pid)
    assert agent["kind"] == "assistant"
    assert agent["system_prompt"] == "You are terse."
    assert agent["temperature"] == 0.3
    assert agent["provider_id"] == pid
    assert agent["is_default"] is False

    upd = await client.put(f"/api/aiagent/configurations/{agent['id']}", json={
        "system_prompt": "Be friendly.", "name": "Helper 2"}, headers=headers)
    assert upd.status_code == 200 and upd.json()["system_prompt"] == "Be friendly."
    assert (await client.delete(f"/api/aiagent/configurations/{agent['id']}", headers=headers)).status_code == 204


# ── Conversations + chat ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_is_refused_for_the_build_agent(client: AsyncClient):
    headers = await _headers(client)
    build = next(a for a in (await client.get("/api/aiagent/configurations", headers=headers)).json()["items"] if a["is_default"])
    resp = await client.post(f"/api/aiagent/agents/{build['id']}/conversations", headers=headers)
    assert resp.status_code == 400
    assert "build agent" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_send_message_streams_tokens_and_persists_both_turns(client: AsyncClient):
    headers = await _headers(client)
    pid = await _provider(client, headers)
    agent = await _assistant(client, headers, pid)
    convo = (await client.post(f"/api/aiagent/agents/{agent['id']}/conversations", headers=headers)).json()
    assert convo["title"] == "New chat"

    fake = _fake_client()
    with patch("app.ai_agent.chat_service.create_ai_provider", return_value=fake):
        resp = await client.post(f"/api/aiagent/conversations/{convo['id']}/messages",
                                 json={"content": "Say hello to the world please"}, headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(resp.text)
    types = [e["type"] for e in events]
    assert types[0] == "user_message" and types[1] == "assistant_start" and types[-1] == "done"
    assert "".join(e["text"] for e in events if e["type"] == "token") == "Hello, world"
    done = events[-1]["message"]
    assert done["content"] == "Hello, world" and done["tokens_used"] == 42 and done["model"] == "gpt-4o"

    # The agent's instructions and temperature reached the provider.
    assert fake.calls[0]["system"] == "You are terse."
    assert fake.calls[0]["temperature"] == 0.3
    assert [m.role for m in fake.calls[0]["messages"]] == ["user"]

    # Both turns are stored, and the thread was titled from the first message.
    full = (await client.get(f"/api/aiagent/conversations/{convo['id']}", headers=headers)).json()
    assert [m["role"] for m in full["messages"]] == ["user", "assistant"]
    assert full["title"] == "Say hello to the world please"
    listed = (await client.get(f"/api/aiagent/agents/{agent['id']}/conversations", headers=headers)).json()
    assert listed[0]["id"] == convo["id"]


@pytest.mark.asyncio
async def test_history_is_replayed_to_the_model(client: AsyncClient):
    headers = await _headers(client)
    pid = await _provider(client, headers)
    agent = await _assistant(client, headers, pid)
    convo = (await client.post(f"/api/aiagent/agents/{agent['id']}/conversations", headers=headers)).json()
    fake = _fake_client(pieces=("ok",))
    with patch("app.ai_agent.chat_service.create_ai_provider", return_value=fake):
        for text in ("first", "second"):
            await client.post(f"/api/aiagent/conversations/{convo['id']}/messages", json={"content": text}, headers=headers)
    roles = [(m.role, m.content) for m in fake.calls[1]["messages"]]
    assert roles == [("user", "first"), ("assistant", "ok"), ("user", "second")]


@pytest.mark.asyncio
async def test_provider_failure_becomes_a_readable_error_message(client: AsyncClient):
    headers = await _headers(client)
    pid = await _provider(client, headers)
    agent = await _assistant(client, headers, pid)
    convo = (await client.post(f"/api/aiagent/agents/{agent['id']}/conversations", headers=headers)).json()

    class Boom(Exception):
        status_code = 401

    async def failing(*a, **k):
        raise Boom("bad key")
        yield  # pragma: no cover

    fake = MagicMock()
    fake.stream_chat = failing
    with patch("app.ai_agent.chat_service.create_ai_provider", return_value=fake):
        resp = await client.post(f"/api/aiagent/conversations/{convo['id']}/messages", json={"content": "hi"}, headers=headers)
    done = _parse_sse(resp.text)[-1]
    assert done["type"] == "done"
    assert "rejected the API key" in done["message"]["error"]


@pytest.mark.asyncio
async def test_attachment_upload_extracts_text_and_is_sent_to_the_model(client: AsyncClient, tmp_path):
    headers = await _headers(client)
    pid = await _provider(client, headers)
    agent = await _assistant(client, headers, pid)
    convo = (await client.post(f"/api/aiagent/agents/{agent['id']}/conversations", headers=headers)).json()

    with patch("app.ai_agent.chat_service.settings.agent_attachments_path", str(tmp_path)):
        up = await client.post("/api/aiagent/attachments",
                               files={"file": ("notes.md", b"# Plan\nShip it", "text/markdown")}, headers=headers)
        assert up.status_code == 201, up.text
        att = up.json()
        assert att["readable"] is True

        fake = _fake_client(pieces=("got it",))
        with patch("app.ai_agent.chat_service.create_ai_provider", return_value=fake):
            resp = await client.post(f"/api/aiagent/conversations/{convo['id']}/messages", json={
                "content": "Summarize this", "attachment_ids": [att["id"]]}, headers=headers)
        sent = fake.calls[0]["messages"][-1].content
        assert 'attached_file name="notes.md"' in sent and "Ship it" in sent and "Summarize this" in sent

        user_msg = _parse_sse(resp.text)[0]["message"]
        assert user_msg["attachments"][0]["filename"] == "notes.md"

        dl = await client.get(f"/api/aiagent/attachments/{att['id']}", headers=headers)
        assert dl.status_code == 200 and dl.content == b"# Plan\nShip it"


@pytest.mark.asyncio
async def test_conversations_are_private_to_their_owner(client: AsyncClient):
    """Another tenant's user cannot read a conversation by id."""
    headers = await _headers(client)
    pid = await _provider(client, headers)
    agent = await _assistant(client, headers, pid)
    convo = (await client.post(f"/api/aiagent/agents/{agent['id']}/conversations", headers=headers)).json()
    bad = await client.get(f"/api/aiagent/conversations/{convo['id']}")
    assert bad.status_code == 401


def test_extract_text_handles_pdf_docx_and_binary():
    import io
    import zipfile
    from app.ai_agent.chat_service import extract_text

    assert extract_text("a.py", "text/x-python", b"print(1)") == "print(1)"
    assert extract_text("pic.png", "image/png", b"\x89PNG") is None
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", "<w:document><w:p><w:r><w:t>Hello docx</w:t></w:r></w:p></w:document>")
    docx = extract_text("a.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", buf.getvalue())
    assert docx == "Hello docx"
    assert extract_text("x.bin", "application/octet-stream", b"\x00\x01") is None
