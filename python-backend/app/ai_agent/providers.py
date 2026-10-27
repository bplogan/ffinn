"""
AI provider client abstraction layer.
Supports: OpenAI, Anthropic, Google Gemini, Ollama, Azure OpenAI, GitHub Models and
any OpenAI-compatible endpoint ("custom").
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Optional

import structlog

log = structlog.get_logger(__name__)

# Used only when the user has not picked a model and the provider can't be queried.
DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-5-5",
    "google": "gemini-2.0-flash",
    "ollama": "llama3.2",
    "azure": "gpt-4o",
    "github-models": "gpt-4o",
    "custom": "",
}

# GitHub Models uses the Azure-hosted OpenAI-compatible inference endpoint.
GITHUB_MODELS_ENDPOINT = "https://models.inference.ai.azure.com"
OPENAI_ENDPOINT = "https://api.openai.com/v1"
ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1"
GOOGLE_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta"
OLLAMA_ENDPOINT = "http://localhost:11434"


class AIGenerationResult:
    def __init__(
        self,
        success: bool,
        generated_files: Optional[dict[str, str]] = None,
        raw_response: Optional[str] = None,
        tokens_used: Optional[int] = None,
        estimated_cost: Optional[float] = None,
        error: Optional[str] = None,
    ):
        self.success = success
        self.generated_files = generated_files or {}
        self.raw_response = raw_response
        self.tokens_used = tokens_used
        self.estimated_cost = estimated_cost
        self.error = error


class ChatImage:
    """An image attached to a chat message, already base64-encoded."""
    def __init__(self, media_type: str, data_b64: str):
        self.media_type = media_type
        self.data_b64 = data_b64


class ChatMessage:
    """Provider-neutral chat turn. `content` is text; images ride alongside."""
    def __init__(self, role: str, content: str, images: Optional[list[ChatImage]] = None):
        self.role = role  # "user" | "assistant"
        self.content = content
        self.images = images or []


class ChatChunk:
    """One streamed piece of a reply. `text` is the delta; usage arrives on the last chunk."""
    def __init__(self, text: str = "", tokens_used: Optional[int] = None, done: bool = False):
        self.text = text
        self.tokens_used = tokens_used
        self.done = done


def _openai_messages(system_prompt: str, messages: list[ChatMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if system_prompt:
        out.append({"role": "system", "content": system_prompt})
    for m in messages:
        if m.images:
            parts: list[dict[str, Any]] = [{"type": "text", "text": m.content}] if m.content else []
            for img in m.images:
                parts.append({"type": "image_url", "image_url": {"url": f"data:{img.media_type};base64,{img.data_b64}"}})
            out.append({"role": m.role, "content": parts})
        else:
            out.append({"role": m.role, "content": m.content})
    return out


def friendly_error(exc: Exception) -> str:
    """Turn an SDK/HTTP exception into a short message a non-expert can act on."""
    status = getattr(exc, "status_code", None)
    detail = str(exc).strip() or exc.__class__.__name__
    if len(detail) > 300:
        detail = detail[:297] + "..."
    if status in (401, 403):
        return f"The provider rejected the API key ({status}). Check the key and that it has access to this model."
    if status == 404:
        return f"Model or endpoint not found (404). Check the model name and base URL. {detail}"
    if status == 429:
        return f"Rate limited or out of quota (429). {detail}"
    return detail


def canonical_provider(name: str) -> str:
    """Map every accepted spelling to one canonical provider id."""
    n = (name or "").strip().lower().replace("_", "-")
    if n in ("claude", "anthropic"):
        return "anthropic"
    if n in ("google", "gemini", "google-gemini"):
        return "google"
    if n in ("azure", "azureopenai", "azure-openai"):
        return "azure"
    if n in ("githubmodels", "github-models"):
        return "github-models"
    if n in ("custom", "openai-compatible", "openaicompatible"):
        return "custom"
    return n


def _openai_chat_kwargs(model: str, *, max_tokens: int, temperature: float) -> dict:
    """Reasoning models (o1/o3/o4/gpt-5) reject max_tokens and temperature."""
    if model.lower().startswith(("o1", "o3", "o4", "gpt-5")):
        return {"max_completion_tokens": min(max_tokens, 16000)}
    return {"max_tokens": max_tokens, "temperature": temperature}


class AIProviderClient(ABC):
    """Base interface for AI provider clients."""

    @abstractmethod
    async def generate_code(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 16000,
        temperature: float = 0.1,
    ) -> AIGenerationResult:
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @abstractmethod
    async def _ping(self) -> None:
        """Make a tiny request with the configured model. Raise on any failure."""
        ...

    async def stream_chat(
        self,
        system_prompt: str,
        messages: list["ChatMessage"],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator["ChatChunk"]:
        """Yield the reply as it is generated. Default: not supported."""
        raise NotImplementedError(f"{self.provider_name} does not support chat.")
        yield  # pragma: no cover - makes this an async generator

    async def verify(self) -> tuple[bool, Optional[str]]:
        """Check key + model/endpoint. Returns (ok, human-readable error)."""
        try:
            await self._ping()
            return True, None
        except Exception as exc:  # noqa: BLE001 - surfaced to the user as text
            return False, friendly_error(exc)

    async def test_connection(self) -> bool:
        return (await self.verify())[0]


# ── Shared response parser ────────────────────────────────────────────────────
def parse_generated_files(response_text: str) -> dict[str, str]:
    """
    Parse the AI's response and extract file path → content mappings.

    Expected format (multiple supported):
    1. JSON: {"files": [{"path": "...", "content": "..."}]}
    2. Markdown code blocks with filename headers
    3. Mixed format
    """
    if not response_text:
        return {}

    # Try JSON first
    try:
        data = json.loads(response_text.strip())
        if isinstance(data, dict) and "files" in data:
            return {f["path"]: f["content"] for f in data["files"] if "path" in f and "content" in f}
        if isinstance(data, list):
            return {f["path"]: f["content"] for f in data if "path" in f and "content" in f}
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    # Try parsing markdown code blocks with file path headers
    files: dict[str, str] = {}
    # Pattern: ## path/to/file.py\n```python\n...\n```
    pattern = re.compile(
        r'(?:^|\n)(?:##|###)\s+([^\n]+\.(?:py|ts|tsx|html|css|scss|json|sql|md|txt))\s*\n'
        r'```[^\n]*\n(.*?)```',
        re.DOTALL | re.MULTILINE,
    )
    for match in pattern.finditer(response_text):
        path = match.group(1).strip()
        content = match.group(2)
        files[path] = content

    if files:
        return files

    # Last resort: try to find any code blocks with path markers
    block_pattern = re.compile(
        r'```(?:python|typescript|tsx|html|css|json)?\s*\n'
        r'(?:#\s*([^\n]+)\n|//\s*([^\n]+)\n)?'
        r'(.*?)```',
        re.DOTALL,
    )
    for match in block_pattern.finditer(response_text):
        path = (match.group(1) or match.group(2) or "").strip()
        content = match.group(3)
        if path and content:
            files[path] = content

    return files


async def _stream_openai_chat(client, model: str, system_prompt: str, messages, kwargs: dict) -> AsyncIterator[ChatChunk]:
    """Shared by OpenAI, Azure OpenAI, GitHub Models and OpenAI-compatible servers."""
    stream = await client.chat.completions.create(
        model=model,
        messages=_openai_messages(system_prompt, messages),
        stream=True,
        stream_options={"include_usage": True},
        **kwargs,
    )
    tokens = None
    async for event in stream:
        if getattr(event, "usage", None):
            tokens = event.usage.total_tokens
        for choice in event.choices or []:
            delta = getattr(choice.delta, "content", None)
            if delta:
                yield ChatChunk(text=delta)
    yield ChatChunk(tokens_used=tokens, done=True)


# ── OpenAI Client ─────────────────────────────────────────────────────────────
class OpenAIClient(AIProviderClient):
    def __init__(self, api_key: str, model: str = "gpt-4o", endpoint: Optional[str] = None):
        import openai
        # Local OpenAI-compatible servers often need no key, but the SDK insists on one.
        self._client = openai.AsyncOpenAI(api_key=api_key or "not-needed", base_url=endpoint)
        self._model = model

    @property
    def provider_name(self) -> str:
        return "OpenAI"

    async def generate_code(self, system_prompt: str, user_prompt: str, max_tokens: int = 16000, temperature: float = 0.1) -> AIGenerationResult:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                **_openai_chat_kwargs(self._model, max_tokens=max_tokens, temperature=temperature),
            )
            content = response.choices[0].message.content or ""
            tokens = response.usage.total_tokens if response.usage else None
            cost = self._estimate_cost(tokens, self._model)
            files = parse_generated_files(content)
            return AIGenerationResult(
                success=True, generated_files=files, raw_response=content,
                tokens_used=tokens, estimated_cost=cost,
            )
        except Exception as e:
            log.error("OpenAI generation failed", error=str(e))
            return AIGenerationResult(success=False, error=str(e))

    async def _ping(self) -> None:
        await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": "ping"}],
            **_openai_chat_kwargs(self._model, max_tokens=16, temperature=0.1),
        )

    async def stream_chat(self, system_prompt, messages, *, temperature=0.7, max_tokens=4096):
        async for chunk in _stream_openai_chat(
            self._client, self._model, system_prompt, messages,
            _openai_chat_kwargs(self._model, max_tokens=max_tokens, temperature=temperature),
        ):
            yield chunk

    def _estimate_cost(self, tokens: Optional[int], model: str) -> float:
        if not tokens:
            return 0.0
        # Approximate cost per 1K tokens
        rates = {
            "gpt-4o": 0.005, "gpt-4": 0.03, "gpt-4-turbo": 0.01,
            "gpt-3.5-turbo": 0.0005,
        }
        rate = rates.get(model, 0.005)
        return round(tokens * rate / 1000, 4)


# ── Anthropic Client ─────────────────────────────────────────────────────────
class AnthropicClient(AIProviderClient):
    def __init__(self, api_key: str, model: str = DEFAULT_MODELS["anthropic"]):
        import anthropic
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    @property
    def provider_name(self) -> str:
        return "Anthropic"

    async def generate_code(self, system_prompt: str, user_prompt: str, max_tokens: int = 16000, temperature: float = 0.1) -> AIGenerationResult:
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=min(max_tokens, 8192),  # Claude max
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            content = response.content[0].text if response.content else ""
            tokens = (response.usage.input_tokens + response.usage.output_tokens) if response.usage else None
            cost = self._estimate_cost(response.usage, self._model) if response.usage else 0.0
            files = parse_generated_files(content)
            return AIGenerationResult(
                success=True, generated_files=files, raw_response=content,
                tokens_used=tokens, estimated_cost=cost,
            )
        except Exception as e:
            log.error("Anthropic generation failed", error=str(e))
            return AIGenerationResult(success=False, error=str(e))

    async def _ping(self) -> None:
        await self._client.messages.create(
            model=self._model, max_tokens=10,
            messages=[{"role": "user", "content": "hi"}],
        )

    async def stream_chat(self, system_prompt, messages, *, temperature=0.7, max_tokens=4096):
        api_messages: list[dict[str, Any]] = []
        for m in messages:
            if m.images:
                parts: list[dict[str, Any]] = [
                    {"type": "image", "source": {"type": "base64", "media_type": img.media_type, "data": img.data_b64}}
                    for img in m.images
                ]
                if m.content:
                    parts.append({"type": "text", "text": m.content})
                api_messages.append({"role": m.role, "content": parts})
            else:
                api_messages.append({"role": m.role, "content": m.content})
        kwargs: dict[str, Any] = {
            "model": self._model, "max_tokens": max_tokens, "temperature": temperature, "messages": api_messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield ChatChunk(text=text)
            final = await stream.get_final_message()
        usage = getattr(final, "usage", None)
        tokens = (usage.input_tokens + usage.output_tokens) if usage else None
        yield ChatChunk(tokens_used=tokens, done=True)

    def _estimate_cost(self, usage, model: str) -> float:
        # Claude pricing per 1M tokens (updated for 2025 model families)
        # Exact match first, then prefix-based fallback for versioned names.
        rates: dict[str, dict[str, float]] = {
            # claude-3 legacy
            "claude-3-5-sonnet-20241022": {"in": 3.0, "out": 15.0},
            "claude-3-opus-20240229":     {"in": 15.0, "out": 75.0},
            "claude-3-haiku-20240307":    {"in": 0.25, "out": 1.25},
            # claude-3-7 (hybrid reasoning)
            "claude-3-7-sonnet":          {"in": 3.0, "out": 15.0},
            # claude-4 family
            "claude-opus-4":              {"in": 15.0, "out": 75.0},
            "claude-sonnet-4":            {"in": 3.0,  "out": 15.0},
            "claude-haiku-4":             {"in": 0.80, "out": 4.0},
        }
        # Exact match
        rate = rates.get(model)
        if rate is None:
            # Prefix match (handles date-suffixed variants like claude-sonnet-4-20250514)
            for prefix, r in rates.items():
                if model.startswith(prefix):
                    rate = r
                    break
        if rate is None:
            rate = {"in": 3.0, "out": 15.0}  # conservative default
        return round(
            (usage.input_tokens * rate["in"] + usage.output_tokens * rate["out"]) / 1_000_000, 4
        )


# ── Google Gemini Client ──────────────────────────────────────────────────────
class GoogleGeminiClient(AIProviderClient):
    def __init__(self, api_key: str, model: str = "gemini-1.5-pro"):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self._genai = genai
        self._model_name = model

    @property
    def provider_name(self) -> str:
        return "Google"

    async def generate_code(self, system_prompt: str, user_prompt: str, max_tokens: int = 16000, temperature: float = 0.1) -> AIGenerationResult:
        try:
            import asyncio
            model = self._genai.GenerativeModel(
                model_name=self._model_name,
                system_instruction=system_prompt,
                generation_config=self._genai.types.GenerationConfig(
                    temperature=temperature, max_output_tokens=max_tokens,
                ),
            )
            # Gemini is sync, run in executor
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, lambda: model.generate_content(user_prompt))
            content = response.text or ""
            files = parse_generated_files(content)
            return AIGenerationResult(success=True, generated_files=files, raw_response=content)
        except Exception as e:
            log.error("Google Gemini generation failed", error=str(e))
            return AIGenerationResult(success=False, error=str(e))

    async def _ping(self) -> None:
        import asyncio
        model = self._genai.GenerativeModel(self._model_name)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: model.generate_content("hi"))

    async def stream_chat(self, system_prompt, messages, *, temperature=0.7, max_tokens=4096):
        import base64

        model = self._genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system_prompt or None,
            generation_config=self._genai.types.GenerationConfig(
                temperature=temperature, max_output_tokens=max_tokens,
            ),
        )
        contents = []
        for m in messages:
            parts: list[Any] = []
            if m.content:
                parts.append(m.content)
            for img in m.images:
                parts.append({"mime_type": img.media_type, "data": base64.b64decode(img.data_b64)})
            contents.append({"role": "user" if m.role == "user" else "model", "parts": parts})
        response = await model.generate_content_async(contents, stream=True)
        tokens = None
        async for event in response:
            text = getattr(event, "text", None)
            if text:
                yield ChatChunk(text=text)
            meta = getattr(event, "usage_metadata", None)
            if meta and getattr(meta, "total_token_count", None):
                tokens = meta.total_token_count
        yield ChatChunk(tokens_used=tokens, done=True)


# ── Ollama Client (self-hosted) ───────────────────────────────────────────────
class OllamaClient(AIProviderClient):
    def __init__(self, model: str = "codellama", endpoint: str = OLLAMA_ENDPOINT):
        self._model = model
        self._endpoint = endpoint.rstrip("/")

    @property
    def provider_name(self) -> str:
        return "Ollama"

    async def generate_code(self, system_prompt: str, user_prompt: str, max_tokens: int = 16000, temperature: float = 0.1) -> AIGenerationResult:
        try:
            import httpx
            payload = {
                "model": self._model,
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            }
            async with httpx.AsyncClient(timeout=300) as client:
                response = await client.post(f"{self._endpoint}/api/generate", json=payload)
                response.raise_for_status()
                data = response.json()
            content = data.get("response", "")
            files = parse_generated_files(content)
            return AIGenerationResult(success=True, generated_files=files, raw_response=content)
        except Exception as e:
            log.error("Ollama generation failed", error=str(e))
            return AIGenerationResult(success=False, error=str(e))

    async def stream_chat(self, system_prompt, messages, *, temperature=0.7, max_tokens=4096):
        import httpx

        api_messages: list[dict[str, Any]] = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        for m in messages:
            row: dict[str, Any] = {"role": m.role, "content": m.content}
            if m.images:
                row["images"] = [img.data_b64 for img in m.images]
            api_messages.append(row)
        payload = {
            "model": self._model, "messages": api_messages, "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        tokens = None
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream("POST", f"{self._endpoint}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    text = (data.get("message") or {}).get("content")
                    if text:
                        yield ChatChunk(text=text)
                    if data.get("done"):
                        tokens = (data.get("prompt_eval_count") or 0) + (data.get("eval_count") or 0) or None
        yield ChatChunk(tokens_used=tokens, done=True)

    async def _ping(self) -> None:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(f"{self._endpoint}/api/tags")
            except httpx.RequestError as exc:
                raise RuntimeError(
                    f"Could not reach Ollama at {self._endpoint}. "
                    "Is it running, and is the URL reachable from the server?"
                ) from exc
            resp.raise_for_status()
            installed = [m.get("name", "") for m in resp.json().get("models", [])]
        wanted = self._model if ":" in self._model else f"{self._model}:latest"
        if installed and wanted not in installed and self._model not in installed:
            raise RuntimeError(
                f"Model '{self._model}' is not installed on this Ollama server. "
                f"Run `ollama pull {self._model}` or choose one of: {', '.join(installed[:10])}."
            )


# ── Azure OpenAI Client ───────────────────────────────────────────────────────

def _azure_uses_completion_tokens(deployment: str) -> bool:
    dep = deployment.lower()
    return dep.startswith(("o1", "o3", "o4", "gpt-5"))


def _azure_chat_request_kwargs(
    deployment: str,
    *,
    max_tokens: int,
    temperature: float,
) -> dict:
    """Build Azure chat params compatible with both classic and reasoning deployments."""
    if _azure_uses_completion_tokens(deployment):
        return {"max_completion_tokens": min(max_tokens, 16000)}
    return {"max_tokens": max_tokens, "temperature": temperature}


class AzureOpenAIClient(AIProviderClient):
    def __init__(self, api_key: str, endpoint: str, model: str = "gpt-4o"):
        import openai
        self._client = openai.AsyncAzureOpenAI(api_key=api_key, azure_endpoint=endpoint, api_version="2024-02-01")
        self._deployment = model

    @property
    def provider_name(self) -> str:
        return "AzureOpenAI"

    async def generate_code(self, system_prompt: str, user_prompt: str, max_tokens: int = 16000, temperature: float = 0.1) -> AIGenerationResult:
        try:
            response = await self._client.chat.completions.create(
                model=self._deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                **_azure_chat_request_kwargs(
                    self._deployment,
                    max_tokens=max_tokens,
                    temperature=temperature,
                ),
            )
            content = response.choices[0].message.content or ""
            tokens = response.usage.total_tokens if response.usage else None
            files = parse_generated_files(content)
            return AIGenerationResult(success=True, generated_files=files, raw_response=content, tokens_used=tokens)
        except Exception as e:
            log.error("Azure OpenAI generation failed", error=str(e))
            return AIGenerationResult(success=False, error=str(e))

    async def _ping(self) -> None:
        await self._client.chat.completions.create(
            model=self._deployment,
            messages=[{"role": "user", "content": "ping"}],
            **_azure_chat_request_kwargs(
                self._deployment,
                max_tokens=16,
                temperature=0.1,
            ),
        )

    async def stream_chat(self, system_prompt, messages, *, temperature=0.7, max_tokens=4096):
        async for chunk in _stream_openai_chat(
            self._client, self._deployment, system_prompt, messages,
            _azure_chat_request_kwargs(self._deployment, max_tokens=max_tokens, temperature=temperature),
        ):
            yield chunk


# ── Provider factory ─────────────────────────────────────────────────────────

def create_ai_provider(
    provider_name: str,
    api_key: str,
    model: str,
    endpoint: Optional[str] = None,
) -> AIProviderClient:
    """Create the appropriate AI provider client.

    For Azure OpenAI, ``model`` is the deployment name used in API routing,
    not necessarily the underlying model product (e.g. gpt-5).
    """
    name = canonical_provider(provider_name)
    if name == "openai":
        return OpenAIClient(api_key=api_key, model=model, endpoint=endpoint or None)
    elif name == "anthropic":
        return AnthropicClient(api_key=api_key, model=model)
    elif name == "google":
        return GoogleGeminiClient(api_key=api_key, model=model)
    elif name == "ollama":
        return OllamaClient(model=model, endpoint=endpoint or OLLAMA_ENDPOINT)
    elif name == "azure":
        return AzureOpenAIClient(api_key=api_key, endpoint=endpoint or "", model=model)
    elif name == "github-models":
        # GitHub Models exposes an OpenAI-compatible API; authenticate with a PAT.
        return OpenAIClient(api_key=api_key, model=model, endpoint=endpoint or GITHUB_MODELS_ENDPOINT)
    elif name == "custom":
        if not (endpoint or "").strip():
            raise ValueError("A base URL is required for a custom OpenAI-compatible provider.")
        return OpenAIClient(api_key=api_key, model=model, endpoint=endpoint)
    else:
        raise ValueError(f"Unknown AI provider: {provider_name}")


# ── Live model discovery ─────────────────────────────────────────────────────

_NON_CHAT_MARKERS = (
    "embedding", "embed", "whisper", "tts", "audio", "image", "dall-e",
    "moderation", "realtime", "transcribe", "davinci", "babbage",
)


class _HttpStatusError(Exception):
    def __init__(self, status_code: int, body: str):
        super().__init__(body)
        self.status_code = status_code


async def list_provider_models(
    provider_name: str,
    api_key: str,
    endpoint: Optional[str] = None,
) -> list[str]:
    """Ask the provider which models this key can use. Also proves the key works.

    Raises ValueError with a user-readable message on failure. Azure is handled
    separately (deployments, not models) in ``azure_config.list_azure_deployments``.
    """
    import httpx

    name = canonical_provider(provider_name)
    base = (endpoint or "").strip().rstrip("/")
    headers: dict[str, str] = {}
    params: dict[str, str] = {}

    if name == "openai":
        url, headers = f"{base or OPENAI_ENDPOINT}/models", {"Authorization": f"Bearer {api_key}"}
    elif name == "github-models":
        url, headers = f"{base or GITHUB_MODELS_ENDPOINT}/models", {"Authorization": f"Bearer {api_key}"}
    elif name == "custom":
        if not base:
            raise ValueError("A base URL is required for a custom OpenAI-compatible provider.")
        url = f"{base}/models"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    elif name == "anthropic":
        url = f"{ANTHROPIC_ENDPOINT}/models"
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        params = {"limit": "100"}
    elif name == "google":
        url, headers = f"{GOOGLE_ENDPOINT}/models", {"x-goog-api-key": api_key}
        params = {"pageSize": "200"}
    elif name == "ollama":
        url = f"{base or OLLAMA_ENDPOINT}/api/tags"
    else:
        raise ValueError(f"Listing models is not supported for provider '{provider_name}'.")

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers, params=params)
    except httpx.RequestError as exc:
        raise ValueError(f"Could not reach {url} ({exc.__class__.__name__}).") from exc

    if resp.status_code != 200:
        raise ValueError(friendly_error(_HttpStatusError(resp.status_code, resp.text[:200])))

    try:
        payload = resp.json()
    except ValueError as exc:
        raise ValueError("The provider returned a response that is not JSON.") from exc
    return parse_model_list(name, payload)


def parse_model_list(name: str, payload) -> list[str]:
    """Normalize the various list-models payloads into a de-duplicated list of ids."""
    models: list[str] = []
    if name == "ollama":
        models = [m.get("name", "") for m in payload.get("models", []) if isinstance(m, dict)]
    elif name == "anthropic":
        models = [m.get("id", "") for m in payload.get("data", []) if isinstance(m, dict)]
    elif name == "google":
        for m in payload.get("models", []):
            if "generateContent" not in (m.get("supportedGenerationMethods") or []):
                continue
            models.append((m.get("name") or "").removeprefix("models/"))
    else:  # OpenAI-style {"data": [...]} or (GitHub Models) a bare list
        rows = payload.get("data", []) if isinstance(payload, dict) else payload
        for m in rows or []:
            if not isinstance(m, dict):
                continue
            if m.get("task") and m["task"] != "chat-completion":  # GitHub Models catalog
                continue
            models.append(m.get("id") or m.get("name") or "")

    models = [m for m in models if m]
    if name in ("openai", "custom", "github-models"):
        models = [m for m in models if not any(x in m.lower() for x in _NON_CHAT_MARKERS)]
        if name == "openai":
            models = [m for m in models if m.startswith(("gpt-", "o1", "o3", "o4", "chatgpt"))]
        models.sort(reverse=True)
    return list(dict.fromkeys(models))
