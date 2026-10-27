"""Helpers for Azure OpenAI deployment vs model separation."""

from __future__ import annotations



from dataclasses import dataclass

from typing import Any, Optional
from urllib.parse import urlparse



import httpx



_AZURE_ALIASES = frozenset({"azure", "azure-openai", "azure_openai", "azureopenai"})



# Data-plane list endpoint versions to try (varies by resource age/region).

_DEPLOYMENT_LIST_API_VERSIONS = (

    "2024-06-01",

    "2023-05-15",

    "2023-03-15-preview",

    "2022-12-01",

)





def is_azure_provider(provider: Optional[str]) -> bool:

    return (provider or "").lower() in _AZURE_ALIASES





def _extra(cfg: Any) -> dict:

    raw = getattr(cfg, "extra_config", None)

    return raw if isinstance(raw, dict) else {}





def azure_deployment_name(cfg: Any) -> str:

    """Azure API routing id (Portal → Model deployments → Deployment name)."""

    extra = _extra(cfg)

    explicit = (extra.get("deployment_name") or "").strip()

    if explicit:

        return explicit

    # Legacy rows stored the deployment id in model_name.

    return (getattr(cfg, "model_name", None) or "").strip()





def azure_agent_deployment_name(
    config: Any,
    *,
    model_override: Optional[str] = None,
    provider_cfg: Optional[Any] = None,
) -> str:
    """Resolve Azure deployment id for an agent configuration row."""
    if (model_override or "").strip():
        return model_override.strip()
    explicit = (getattr(config, "azure_deployment_name", None) or "").strip()
    if explicit:
        return explicit
    if provider_cfg is not None:
        from_provider = azure_deployment_name(provider_cfg)
        if from_provider:
            return from_provider
    return (getattr(config, "ai_model", None) or "").strip()





def azure_model_name(cfg: Any) -> str:

    """Underlying model product (e.g. gpt-5), used for display and capabilities."""

    extra = _extra(cfg)

    explicit = (extra.get("model") or "").strip()

    if explicit:

        return explicit

    return (getattr(cfg, "model_name", None) or "").strip()





def apply_azure_provider_fields(

    cfg: Any,

    *,

    deployment_name: Optional[str],

    model_name: Optional[str],

) -> None:

    extra = dict(_extra(cfg))

    if deployment_name is not None:

        extra["deployment_name"] = deployment_name.strip()

    if model_name is not None:

        cleaned = model_name.strip()

        cfg.model_name = cleaned or None

        extra["model"] = cleaned

    cfg.extra_config = extra or None





@dataclass

class AzureDeploymentsListResult:

    deployments: list[dict[str, str]]

    error: Optional[str] = None





def _short_http_body(response: httpx.Response, limit: int = 240) -> str:

    try:

        text = response.text.strip()

    except Exception:

        return ""

    if not text:

        return ""

    return text if len(text) <= limit else text[: limit - 3] + "..."





def _deployment_id_from_item(item: dict[str, Any]) -> str:

    raw = (item.get("id") or item.get("name") or "").strip()

    if "/" in raw:

        raw = raw.rsplit("/", 1)[-1]

    return raw





def _model_from_item(item: dict[str, Any], fallback: str) -> str:

    model = item.get("model")

    if isinstance(model, dict):

        name = (model.get("name") or "").strip()

        version = (model.get("version") or "").strip()

        if name and version:

            return f"{name}-{version}" if version not in name else name

        return name or version or fallback

    if isinstance(model, str) and model.strip():

        return model.strip()



    props = item.get("properties")

    if isinstance(props, dict):

        nested = props.get("model")

        if isinstance(nested, dict):

            name = (nested.get("name") or "").strip()

            version = (nested.get("version") or "").strip()

            if name and version:

                return f"{name}-{version}" if version not in name else name

            return name or version or fallback

    return fallback





def parse_azure_deployment_list(payload: Any) -> list[dict[str, str]]:

    """Normalize Azure deployment list payloads (data/value/management-plane shapes)."""

    if not isinstance(payload, dict):

        return []



    items = payload.get("data") or payload.get("value") or []

    if not isinstance(items, list):

        return []



    rows: list[dict[str, str]] = []

    seen: set[str] = set()

    for item in items:

        if not isinstance(item, dict):

            continue

        dep_id = _deployment_id_from_item(item)

        if not dep_id or dep_id in seen:

            continue

        seen.add(dep_id)

        model = _model_from_item(item, dep_id)

        rows.append({"deployment_name": dep_id, "model": model})

    return rows





async def _fetch_deployments_from_base(

    client: httpx.AsyncClient,

    base: str,

    api_key: str,

) -> AzureDeploymentsListResult:

    last_error: Optional[str] = None

    for version in _DEPLOYMENT_LIST_API_VERSIONS:

        url = f"{base.rstrip('/')}/openai/deployments?api-version={version}"

        try:

            response = await client.get(url, headers={"api-key": api_key})

        except httpx.RequestError as exc:

            last_error = f"Network error contacting Azure ({exc})."

            continue



        if response.status_code == 200:

            rows = parse_azure_deployment_list(response.json())

            if rows:

                return AzureDeploymentsListResult(deployments=rows)

            last_error = "Azure returned an empty deployment list for this resource."

            continue



        body = _short_http_body(response)

        last_error = f"Azure HTTP {response.status_code} (api-version={version})"

        if body:

            last_error += f": {body}"



    return AzureDeploymentsListResult(deployments=[], error=last_error)





async def list_azure_deployments(endpoint: str, api_key: str) -> AzureDeploymentsListResult:

    """Return deployment id + underlying model from the Azure OpenAI resource."""

    bases = [endpoint.rstrip("/")]

    host = (urlparse(endpoint).hostname or "").lower()

    if host.endswith(".openai.azure.com"):

        alt = endpoint.replace(".openai.azure.com", ".cognitiveservices.azure.com").rstrip("/")

        if alt not in bases:

            bases.append(alt)



    last_error: Optional[str] = None

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:

        for base in bases:

            result = await _fetch_deployments_from_base(client, base, api_key)

            if result.deployments:

                return result

            last_error = result.error



    hint = (

        " Azure may not expose deployment listing for this resource via API key. "

        "Open Azure Portal → your resource → Model deployments and copy the Deployment name manually."

    )

    return AzureDeploymentsListResult(

        deployments=[],

        error=(last_error or "Could not list deployments from Azure.") + hint,

    )


