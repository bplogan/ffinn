"""
Comprehensive tests for AI providers module.
Covers: parse_generated_files, create_ai_provider factory, AIGenerationResult, cost estimation.
All external API calls are mocked — no real tokens required.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai_agent.providers import (
    AIGenerationResult,
    parse_generated_files,
    create_ai_provider,
    OpenAIClient,
    AnthropicClient,
    GoogleGeminiClient,
    OllamaClient,
    AzureOpenAIClient,
    GITHUB_MODELS_ENDPOINT,
)


# ═══════════════════════════════════════════════════════════════════════
# parse_generated_files — JSON format
# ═══════════════════════════════════════════════════════════════════════

class TestParseGeneratedFilesJSON:
    def test_parses_files_array_format(self):
        data = {"files": [
            {"path": "app/api/blog.py", "content": "router = APIRouter()"},
            {"path": "app/schemas/blog.py", "content": "class BlogSchema(BaseModel): pass"},
        ]}
        result = parse_generated_files(json.dumps(data))
        assert len(result) == 2
        assert "app/api/blog.py" in result
        assert "router = APIRouter()" in result["app/api/blog.py"]

    def test_parses_list_format(self):
        data = [
            {"path": "app/api/orders.py", "content": "# orders"},
            {"path": "app/schemas/orders.py", "content": "# schemas"},
        ]
        result = parse_generated_files(json.dumps(data))
        assert "app/api/orders.py" in result
        assert "app/schemas/orders.py" in result

    def test_json_missing_content_field_skipped(self):
        data = {"files": [
            {"path": "app/api/blog.py"},                         # no content
            {"path": "app/other.py", "content": "good"},
        ]}
        result = parse_generated_files(json.dumps(data))
        assert "app/api/blog.py" not in result
        assert "app/other.py" in result

    def test_json_missing_path_field_skipped(self):
        data = {"files": [
            {"content": "orphan content"},                        # no path
            {"path": "app/good.py", "content": "good"},
        ]}
        result = parse_generated_files(json.dumps(data))
        assert len(result) == 1
        assert "app/good.py" in result

    def test_empty_files_array_returns_empty(self):
        result = parse_generated_files(json.dumps({"files": []}))
        assert result == {}

    def test_json_with_unicode_content(self):
        data = {"files": [{"path": "app/api/unicode.py", "content": "# こんにちは世界"}]}
        result = parse_generated_files(json.dumps(data))
        assert "こんにちは世界" in result["app/api/unicode.py"]


# ═══════════════════════════════════════════════════════════════════════
# parse_generated_files — Markdown code block format
# ═══════════════════════════════════════════════════════════════════════

class TestParseGeneratedFilesMarkdown:
    def test_parses_markdown_header_with_python_block(self):
        text = (
            "## python-backend/app/api/blog.py\n"
            "```python\n"
            "from fastapi import APIRouter\n"
            "router = APIRouter()\n"
            "```\n"
        )
        result = parse_generated_files(text)
        assert "python-backend/app/api/blog.py" in result
        assert "router = APIRouter()" in result["python-backend/app/api/blog.py"]

    def test_parses_multiple_markdown_blocks(self):
        text = (
            "## app/api/products.py\n"
            "```python\n"
            "# products router\n"
            "```\n"
            "## app/schemas/products.py\n"
            "```python\n"
            "# products schema\n"
            "```\n"
            "## nextjs-frontend/src/app/app/features/products/page.tsx\n"
            "```tsx\n"
            "// products page\n"
            "```\n"
        )
        result = parse_generated_files(text)
        assert "app/api/products.py" in result
        assert "app/schemas/products.py" in result
        assert "nextjs-frontend/src/app/app/features/products/page.tsx" in result

    def test_parses_triple_hash_header(self):
        text = (
            "### app/services/blog_service.py\n"
            "```python\n"
            "class BlogService: pass\n"
            "```\n"
        )
        result = parse_generated_files(text)
        assert "app/services/blog_service.py" in result

    def test_parses_typescript_block(self):
        text = (
            "## nextjs-frontend/src/app/app/features/blog/page.tsx\n"
            "```tsx\n"
            "export default function BlogPage() { return null }\n"
            "```\n"
        )
        result = parse_generated_files(text)
        assert "nextjs-frontend/src/app/app/features/blog/page.tsx" in result
        assert "BlogPage" in result["nextjs-frontend/src/app/app/features/blog/page.tsx"]

    def test_parses_tsx_block(self):
        text = (
            "## nextjs-frontend/src/app/app/features/blog/layout.tsx\n"
            "```tsx\n"
            "<div>Hello</div>\n"
            "```\n"
        )
        result = parse_generated_files(text)
        assert "nextjs-frontend/src/app/app/features/blog/layout.tsx" in result


# ═══════════════════════════════════════════════════════════════════════
# parse_generated_files — Edge cases
# ═══════════════════════════════════════════════════════════════════════

class TestParseGeneratedFilesEdgeCases:
    def test_empty_string_returns_empty(self):
        assert parse_generated_files("") == {}

    def test_none_handled_gracefully(self):
        # Function signature says str; verify it handles empty gracefully
        assert parse_generated_files("") == {}

    def test_invalid_json_falls_back_to_markdown(self):
        text = (
            "Here is your file:\n"
            "## app/api/test.py\n"
            "```python\n"
            "# fallback\n"
            "```\n"
        )
        result = parse_generated_files(text)
        assert "app/api/test.py" in result

    def test_plain_text_no_blocks_returns_empty(self):
        result = parse_generated_files("This is just some plain explanation text with no code.")
        assert result == {}

    def test_json_without_files_key_falls_back_to_markdown(self):
        text = '{"description": "no files here"}\n## app/foo.py\n```python\n# hi\n```\n'
        result = parse_generated_files(text)
        assert "app/foo.py" in result

    def test_whitespace_in_json_content_preserved(self):
        data = {"files": [{"path": "app/main.py", "content": "    indented = True\n"}]}
        result = parse_generated_files(json.dumps(data))
        assert "    indented = True" in result["app/main.py"]


# ═══════════════════════════════════════════════════════════════════════
# AIGenerationResult
# ═══════════════════════════════════════════════════════════════════════

class TestAIGenerationResult:
    def test_success_result(self):
        r = AIGenerationResult(
            success=True,
            generated_files={"app/api/test.py": "# test"},
            tokens_used=500,
            estimated_cost=0.0025,
        )
        assert r.success is True
        assert "app/api/test.py" in r.generated_files
        assert r.tokens_used == 500
        assert r.error is None

    def test_failure_result(self):
        r = AIGenerationResult(success=False, error="Rate limit exceeded")
        assert r.success is False
        assert r.error == "Rate limit exceeded"
        assert r.generated_files == {}

    def test_default_generated_files_is_empty_dict(self):
        r = AIGenerationResult(success=True)
        assert r.generated_files == {}

    def test_raw_response_stored(self):
        raw = '{"files": []}'
        r = AIGenerationResult(success=True, raw_response=raw)
        assert r.raw_response == raw


# ═══════════════════════════════════════════════════════════════════════
# create_ai_provider factory
# ═══════════════════════════════════════════════════════════════════════

class TestCreateAIProvider:
    def _patch_import(self, module_path: str, mock_obj=None):
        return patch(module_path, mock_obj or MagicMock())

    def test_creates_openai_client(self):
        with patch("openai.AsyncOpenAI"):
            provider = create_ai_provider("openai", "sk-test", "gpt-4o")
        assert isinstance(provider, OpenAIClient)
        assert provider.provider_name == "OpenAI"

    def test_creates_openai_client_case_insensitive(self):
        with patch("openai.AsyncOpenAI"):
            provider = create_ai_provider("OpenAI", "sk-test", "gpt-4o")
        assert isinstance(provider, OpenAIClient)

    def test_creates_anthropic_client(self):
        with patch("anthropic.AsyncAnthropic"):
            provider = create_ai_provider("anthropic", "sk-ant-test", "claude-3-5-sonnet-20241022")
        assert isinstance(provider, AnthropicClient)
        assert provider.provider_name == "Anthropic"

    def test_creates_anthropic_client_alias(self):
        with patch("anthropic.AsyncAnthropic"):
            provider = create_ai_provider("claude", "sk-ant-test", "claude-3-5-sonnet-20241022")
        assert isinstance(provider, AnthropicClient)

    def test_creates_ollama_client(self):
        provider = create_ai_provider("ollama", "", "codellama")
        assert isinstance(provider, OllamaClient)
        assert provider.provider_name == "Ollama"

    def test_creates_ollama_with_custom_endpoint(self):
        provider = create_ai_provider("ollama", "", "llama2", endpoint="http://my-server:11434")
        assert isinstance(provider, OllamaClient)

    def test_creates_azure_openai_client(self):
        with patch("openai.AsyncAzureOpenAI"):
            provider = create_ai_provider(
                "azureopenai", "azure-key", "gpt-4o",
                endpoint="https://my-resource.openai.azure.com"
            )
        assert isinstance(provider, AzureOpenAIClient)
        assert provider.provider_name == "AzureOpenAI"

    def test_creates_azure_client_alias(self):
        with patch("openai.AsyncAzureOpenAI"):
            provider = create_ai_provider(
                "azure", "azure-key", "gpt-4o",
                endpoint="https://my-resource.openai.azure.com"
            )
        assert isinstance(provider, AzureOpenAIClient)

    def test_unknown_provider_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown AI provider"):
            create_ai_provider("unknown-llm", "key", "model")

    def test_creates_github_models_client(self):
        """github-models uses the OpenAI-compatible Azure inference endpoint."""
        with patch("openai.AsyncOpenAI"):
            provider = create_ai_provider("github-models", "ghp_token", "gpt-4o")
        assert isinstance(provider, OpenAIClient)
        assert provider.provider_name == "OpenAI"

    def test_creates_github_models_client_aliases(self):
        for alias in ("github_models", "githubmodels"):
            with patch("openai.AsyncOpenAI"):
                provider = create_ai_provider(alias, "ghp_token", "gpt-4o")
            assert isinstance(provider, OpenAIClient)

    def test_github_models_uses_inference_endpoint_by_default(self):
        """When no endpoint is provided, the GitHub Models inference URL is used."""
        with patch("openai.AsyncOpenAI") as mock_openai:
            create_ai_provider("github-models", "ghp_token", "gpt-4o")
            _, kwargs = mock_openai.call_args
            assert GITHUB_MODELS_ENDPOINT in (kwargs.get("base_url") or "")

    def test_google_gemini_client_created(self):
        import sys
        mock_genai = MagicMock()
        mock_genai.configure = MagicMock()
        with patch.dict(sys.modules, {"google.generativeai": mock_genai}):
            provider = create_ai_provider("google", "gcp-key", "gemini-1.5-pro")
        assert isinstance(provider, GoogleGeminiClient)
        assert provider.provider_name == "Google"

    def test_gemini_alias(self):
        import sys
        mock_genai = MagicMock()
        mock_genai.configure = MagicMock()
        with patch.dict(sys.modules, {"google.generativeai": mock_genai}):
            provider = create_ai_provider("gemini", "gcp-key", "gemini-1.5-pro")
        assert isinstance(provider, GoogleGeminiClient)


# ═══════════════════════════════════════════════════════════════════════
# OpenAI client — generate_code mock
# ═══════════════════════════════════════════════════════════════════════

class TestOpenAIClientGenerateCode:
    def _make_client(self):
        with patch("openai.AsyncOpenAI"):
            return OpenAIClient(api_key="sk-test", model="gpt-4o")

    @pytest.mark.asyncio
    async def test_successful_generation(self):
        client = self._make_client()
        mock_response = MagicMock()
        good_json = json.dumps({"files": [{"path": "app/api/test.py", "content": "# test"}]})
        mock_response.choices[0].message.content = good_json
        mock_response.usage.total_tokens = 500
        client._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await client.generate_code("sys prompt", "user prompt")
        assert result.success is True
        assert "app/api/test.py" in result.generated_files
        assert result.tokens_used == 500

    @pytest.mark.asyncio
    async def test_api_error_returns_failure(self):
        client = self._make_client()
        client._client.chat.completions.create = AsyncMock(side_effect=Exception("connection timeout"))

        result = await client.generate_code("sys", "user")
        assert result.success is False
        assert "connection timeout" in result.error

    @pytest.mark.asyncio
    async def test_empty_response_returns_success_with_no_files(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = ""
        mock_response.usage.total_tokens = 10
        client._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await client.generate_code("sys", "user")
        assert result.success is True
        assert result.generated_files == {}

    def test_cost_estimation_gpt4o(self):
        client = self._make_client()
        cost = client._estimate_cost(1000, "gpt-4o")
        assert cost == pytest.approx(0.005, rel=1e-3)

    def test_cost_estimation_unknown_model_uses_default(self):
        client = self._make_client()
        cost = client._estimate_cost(1000, "unknown-model")
        assert cost > 0

    def test_cost_estimation_none_tokens_returns_zero(self):
        client = self._make_client()
        cost = client._estimate_cost(None, "gpt-4o")
        assert cost == 0.0


# ═══════════════════════════════════════════════════════════════════════
# Anthropic client — generate_code mock
# ═══════════════════════════════════════════════════════════════════════

class TestAnthropicClientGenerateCode:
    def _make_client(self):
        with patch("anthropic.AsyncAnthropic"):
            return AnthropicClient(api_key="sk-ant-test")

    @pytest.mark.asyncio
    async def test_successful_generation(self):
        client = self._make_client()
        good_json = json.dumps({"files": [{"path": "app/api/blog.py", "content": "# blog"}]})
        mock_response = MagicMock()
        mock_response.content[0].text = good_json
        mock_response.usage.input_tokens = 200
        mock_response.usage.output_tokens = 300
        client._client.messages.create = AsyncMock(return_value=mock_response)

        result = await client.generate_code("sys", "user")
        assert result.success is True
        assert "app/api/blog.py" in result.generated_files
        assert result.tokens_used == 500

    @pytest.mark.asyncio
    async def test_api_error_returns_failure(self):
        client = self._make_client()
        client._client.messages.create = AsyncMock(side_effect=Exception("overloaded"))

        result = await client.generate_code("sys", "user")
        assert result.success is False
        assert "overloaded" in result.error

    def test_cost_estimation_claude_3_5_sonnet(self):
        client = self._make_client()
        mock_usage = MagicMock()
        mock_usage.input_tokens = 1000
        mock_usage.output_tokens = 500
        cost = client._estimate_cost(mock_usage, "claude-3-5-sonnet-20241022")
        expected = (1000 * 3.0 + 500 * 15.0) / 1_000_000
        assert cost == pytest.approx(expected, rel=1e-3)

    def test_cost_estimation_claude_opus_4_exact(self):
        client = self._make_client()
        mock_usage = MagicMock()
        mock_usage.input_tokens = 1000
        mock_usage.output_tokens = 500
        cost = client._estimate_cost(mock_usage, "claude-opus-4")
        expected = (1000 * 15.0 + 500 * 75.0) / 1_000_000
        assert cost == pytest.approx(expected, rel=1e-3)

    def test_cost_estimation_claude_sonnet_4_dated_variant(self):
        """Date-suffixed variants like claude-sonnet-4-20250514 match by prefix."""
        client = self._make_client()
        mock_usage = MagicMock()
        mock_usage.input_tokens = 1000
        mock_usage.output_tokens = 500
        cost = client._estimate_cost(mock_usage, "claude-sonnet-4-20250514")
        # Should match the "claude-sonnet-4" prefix rate
        expected = (1000 * 3.0 + 500 * 15.0) / 1_000_000
        assert cost == pytest.approx(expected, rel=1e-3)

    def test_cost_estimation_claude_3_7_sonnet(self):
        client = self._make_client()
        mock_usage = MagicMock()
        mock_usage.input_tokens = 1000
        mock_usage.output_tokens = 500
        cost = client._estimate_cost(mock_usage, "claude-3-7-sonnet-20250219")
        # Matches "claude-3-7-sonnet" prefix
        expected = (1000 * 3.0 + 500 * 15.0) / 1_000_000
        assert cost == pytest.approx(expected, rel=1e-3)

    def test_cost_estimation_unknown_model_returns_nonzero(self):
        """Completely unknown models fall back to a conservative non-zero default."""
        client = self._make_client()
        mock_usage = MagicMock()
        mock_usage.input_tokens = 1000
        mock_usage.output_tokens = 1000
        cost = client._estimate_cost(mock_usage, "totally-unknown-model-xyz")
        assert cost > 0


# ═══════════════════════════════════════════════════════════════════════
# Ollama client — generate_code mock
# ═══════════════════════════════════════════════════════════════════════

class TestOllamaClientGenerateCode:
    @pytest.mark.asyncio
    async def test_successful_generation_from_response_field(self):
        import httpx
        client = OllamaClient(model="codellama")
        good_json = json.dumps({"files": [{"path": "app/api/test.py", "content": "# ok"}]})

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": good_json}

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_ctx = AsyncMock()
            mock_ctx.post = AsyncMock(return_value=mock_response)
            mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_async_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await client.generate_code("sys", "user")

        assert result.success is True
        assert "app/api/test.py" in result.generated_files

    @pytest.mark.asyncio
    async def test_connection_error_returns_failure(self):
        client = OllamaClient(model="codellama")

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_ctx = AsyncMock()
            mock_ctx.post = AsyncMock(side_effect=Exception("connection refused"))
            mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_async_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await client.generate_code("sys", "user")

        assert result.success is False
        assert "connection refused" in result.error


# ═══════════════════════════════════════════════════════════════════════
# Provider setup helpers: custom/OpenAI-compatible, model lists, error text
# ═══════════════════════════════════════════════════════════════════════

class TestProviderSetupHelpers:
    def test_custom_provider_uses_openai_client_with_endpoint(self):
        with patch("openai.AsyncOpenAI") as mock_openai:
            provider = create_ai_provider("custom", "", "my-model", endpoint="http://localhost:1234/v1")
        assert provider.provider_name == "OpenAI"
        assert mock_openai.call_args.kwargs["base_url"] == "http://localhost:1234/v1"

    def test_custom_provider_requires_endpoint(self):
        with pytest.raises(ValueError, match="base URL"):
            create_ai_provider("custom", "k", "m")

    def test_canonical_provider_aliases(self):
        from app.ai_agent.providers import canonical_provider
        assert canonical_provider("Azure_OpenAI") == "azure"
        assert canonical_provider("claude") == "anthropic"
        assert canonical_provider("google-gemini") == "google"
        assert canonical_provider("GitHub_Models") == "github-models"

    def test_openai_reasoning_models_use_completion_tokens(self):
        from app.ai_agent.providers import _openai_chat_kwargs
        assert "max_completion_tokens" in _openai_chat_kwargs("o3-mini", max_tokens=100, temperature=0.1)
        assert "temperature" not in _openai_chat_kwargs("gpt-5", max_tokens=100, temperature=0.1)
        assert _openai_chat_kwargs("gpt-4o", max_tokens=100, temperature=0.1)["max_tokens"] == 100

    def test_parse_openai_models_filters_non_chat_and_sorts(self):
        from app.ai_agent.providers import parse_model_list
        payload = {"data": [{"id": "text-embedding-3-small"}, {"id": "gpt-4o"}, {"id": "whisper-1"}, {"id": "o3-mini"}]}
        assert parse_model_list("openai", payload) == ["o3-mini", "gpt-4o"]

    def test_parse_anthropic_models_keeps_order(self):
        from app.ai_agent.providers import parse_model_list
        payload = {"data": [{"id": "claude-b"}, {"id": "claude-a"}]}
        assert parse_model_list("anthropic", payload) == ["claude-b", "claude-a"]

    def test_parse_google_models_requires_generate_content(self):
        from app.ai_agent.providers import parse_model_list
        payload = {"models": [
            {"name": "models/gemini-2.0-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/embedding-001", "supportedGenerationMethods": ["embedContent"]},
        ]}
        assert parse_model_list("google", payload) == ["gemini-2.0-flash"]

    def test_parse_ollama_and_github_models(self):
        from app.ai_agent.providers import parse_model_list
        assert parse_model_list("ollama", {"models": [{"name": "llama3.2:latest"}]}) == ["llama3.2:latest"]
        gh = [{"name": "gpt-4o", "task": "chat-completion"}, {"name": "embed-x", "task": "embeddings"}]
        assert parse_model_list("github-models", gh) == ["gpt-4o"]

    def test_friendly_error_explains_bad_key(self):
        from app.ai_agent.providers import friendly_error

        class E(Exception):
            status_code = 401
        assert "rejected the API key" in friendly_error(E("nope"))

    @pytest.mark.asyncio
    async def test_verify_returns_readable_error_instead_of_false(self):
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_openai.return_value.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))
            provider = create_ai_provider("openai", "sk", "gpt-4o")
            ok, error = await provider.verify()
        assert ok is False
        assert error == "boom"
        assert await provider.test_connection() is False
