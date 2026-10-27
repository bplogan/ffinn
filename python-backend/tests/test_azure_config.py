"""Tests for Azure OpenAI deployment listing helpers."""
from __future__ import annotations

import pytest

from app.ai_agent.azure_config import azure_agent_deployment_name, parse_azure_deployment_list


def test_parse_azure_deployment_list_data_plane_shape():
    payload = {
        "data": [
            {"id": "prod-chat", "model": "gpt-5"},
            {"id": "embeddings", "model": "text-embedding-3-large"},
        ]
    }
    rows = parse_azure_deployment_list(payload)
    assert rows == [
        {"deployment_name": "prod-chat", "model": "gpt-5"},
        {"deployment_name": "embeddings", "model": "text-embedding-3-large"},
    ]


def test_azure_agent_deployment_name_prefers_explicit_column():
    class Agent:
        azure_deployment_name = "my-deploy"
        ai_model = "gpt-4o"

    assert azure_agent_deployment_name(Agent()) == "my-deploy"


def test_azure_agent_deployment_name_falls_back_to_provider():
    class Agent:
        azure_deployment_name = ""
        ai_model = "gpt-4o"

    class Provider:
        model_name = "legacy-deploy"
        extra_config = {"deployment_name": "portal-deploy"}

    assert azure_agent_deployment_name(Agent(), provider_cfg=Provider()) == "portal-deploy"


def test_azure_agent_deployment_name_skips_ai_model_when_provider_has_deployment():
    class Agent:
        azure_deployment_name = None
        ai_model = "gpt-4o"

    class Provider:
        model_name = "gpt-5-mini"
        extra_config = {"deployment_name": "gpt-5-mini", "model": "gpt-5-mini"}

    assert azure_agent_deployment_name(Agent(), provider_cfg=Provider()) == "gpt-5-mini"


def test_parse_azure_deployment_list_management_plane_shape():
    payload = {
        "value": [
            {
                "id": "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.CognitiveServices/accounts/contoso-openai/deployments/prod-chat",
                "name": "prod-chat",
                "properties": {
                    "model": {"format": "OpenAI", "name": "gpt-5", "version": "2025-08-07"},
                },
            }
        ]
    }
    rows = parse_azure_deployment_list(payload)
    assert len(rows) == 1
    assert rows[0]["deployment_name"] == "prod-chat"
    assert rows[0]["model"] == "gpt-5-2025-08-07"


@pytest.mark.asyncio
async def test_list_azure_deployments_tries_multiple_api_versions():
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.ai_agent.azure_config import list_azure_deployments

    responses = [
        MagicMock(status_code=404, text="not found"),
        MagicMock(status_code=200, json=lambda: {"data": [{"id": "prod-chat", "model": "gpt-5"}]}),
    ]

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=responses)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.ai_agent.azure_config.httpx.AsyncClient", return_value=mock_client):
        result = await list_azure_deployments("https://contoso-openai.openai.azure.com", "test-key")

    assert result.deployments == [{"deployment_name": "prod-chat", "model": "gpt-5"}]
    assert result.error is None
