"""AI Agent schemas."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError


GenerationTargetScope = Literal["host", "tenant"]


_SUPPORTED_SC_PROVIDERS = {"github"}


AgentKind = Literal["build", "assistant"]


class CreateConfigurationRequest(BaseModel):
    name: str
    kind: AgentKind = "build"
    description: Optional[str] = Field(None, max_length=500)
    system_prompt: Optional[str] = Field(None, max_length=20_000)
    temperature: Optional[float] = Field(None, ge=0, le=2)
    avatar: Optional[str] = Field(None, max_length=40)
    source_control_type: str = "github"
    repository_url: str = ""
    source_control_token: str = ""
    ai_provider: str = ""
    ai_model: str = ""
    ai_api_key: str = ""
    provider_config_id: Optional[UUID] = None
    azure_deployment_name: Optional[str] = None
    staging_workflow_id: Optional[str] = None
    release_workflow_id: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None

    @field_validator("source_control_type")
    @classmethod
    def validate_source_control_type(cls, v: str) -> str:
        if v.lower() not in _SUPPORTED_SC_PROVIDERS:
            raise ValueError(
                f"Unsupported source control provider '{v}'. "
                f"Currently supported: {', '.join(sorted(_SUPPORTED_SC_PROVIDERS))}."
            )
        return v.lower()

    @model_validator(mode="after")
    def validate_credentials(self) -> "CreateConfigurationRequest":
        # PydanticCustomError (not ValueError) so FastAPI can serialize the 422 body.
        if self.kind == "assistant":
            if not self.provider_config_id:
                raise PydanticCustomError("value_error", "An assistant agent must be linked to a saved AI provider.")
            return self
        if not self.provider_config_id and not (self.ai_api_key or "").strip():
            raise PydanticCustomError("value_error", "ai_api_key is required when provider_config_id is not supplied.")
        if not self.provider_config_id and not (self.ai_provider or "").strip():
            raise PydanticCustomError("value_error", "ai_provider is required when provider_config_id is not supplied.")
        return self


class UpdateConfigurationRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = Field(None, max_length=500)
    system_prompt: Optional[str] = Field(None, max_length=20_000)
    temperature: Optional[float] = Field(None, ge=0, le=2)
    avatar: Optional[str] = Field(None, max_length=40)
    repository_url: Optional[str] = None
    source_control_token: Optional[str] = None
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    ai_api_key: Optional[str] = None
    provider_id: Optional[UUID] = None
    azure_deployment_name: Optional[str] = None
    staging_workflow_id: Optional[str] = None
    release_workflow_id: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    is_active: Optional[bool] = None


class ConfigurationResponse(BaseModel):
    id: str
    name: Optional[str] = None
    kind: str = "build"
    is_default: bool = False
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: Optional[float] = None
    avatar: Optional[str] = None
    source_control_type: str = ""
    repository_url: str = ""
    ai_provider: str = ""
    ai_model: str = ""
    provider_id: Optional[str] = None
    azure_deployment_name: Optional[str] = None
    is_active: bool = True
    staging_workflow_id: Optional[str] = None
    release_workflow_id: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    created_at: Optional[datetime] = None

    @field_validator("id", "provider_id", mode="before")
    @classmethod
    def coerce_uuid_to_str(cls, v: Any) -> Optional[str]:
        return str(v) if v is not None else v

    class Config:
        from_attributes = True


class CreateGenerationRequest(BaseModel):
    config_id: UUID
    feature_name: str = Field(..., min_length=1, max_length=200)
    prompt: str = Field(..., min_length=1, max_length=10000)
    target_scope: GenerationTargetScope = "tenant"
    provider_override: Optional[str] = None  # saved provider id (preferred) or provider name
    model_override: Optional[str] = None
    scheduled_release: Optional[datetime] = None

    @field_validator("target_scope")
    @classmethod
    def normalize_target_scope(cls, v: str) -> str:
        if v not in ("host", "tenant"):
            raise ValueError("target_scope must be 'host' or 'tenant'")
        return v


class GenerationResponse(BaseModel):
    id: str
    config_id: str
    feature_name: Optional[str] = None
    user_prompt: str
    target_scope: str = "tenant"
    status: str
    branch_name: Optional[str] = None
    commit_sha: Optional[str] = None
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    staging_url: Optional[str] = None
    staging_frontend_url: Optional[str] = None
    build_url: Optional[str] = None
    error_message: Optional[str] = None
    tokens_used: Optional[int] = None
    estimated_cost: Optional[float] = None
    generated_files: Optional[Any] = None
    validation_errors: Optional[Any] = None
    code_review_passed: Optional[bool] = None
    scheduled_release_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("id", "config_id", mode="before")
    @classmethod
    def coerce_uuid_to_str(cls, v: Any) -> str:
        return str(v) if v is not None else v

    class Config:
        from_attributes = True


class BuildCallbackRequest(BaseModel):
    generation_id: UUID
    success: bool
    build_url: Optional[str] = None
    error: Optional[str] = Field(None, max_length=2000)


class DeployCallbackRequest(BaseModel):
    generation_id: UUID
    success: bool
    staging_url: Optional[str] = None
    staging_frontend_url: Optional[str] = None
    error: Optional[str] = Field(None, max_length=2000)


class ReleaseCallbackRequest(BaseModel):
    generation_id: UUID
    success: bool
    production_url: Optional[str] = None
    error: Optional[str] = Field(None, max_length=2000)


class PrValidationCallbackRequest(BaseModel):
    generation_id: UUID
    approved: bool
    reviewer_notes: Optional[str] = Field(None, max_length=2000)


class RepositorySetupRequest(BaseModel):
    api_base_url: Optional[str] = Field(None, max_length=500)
    branch: Optional[str] = Field(None, max_length=100)


class RepositorySetupStepResponse(BaseModel):
    name: str
    success: bool
    detail: str = ""


class RepositorySetupResponse(BaseModel):
    success: bool
    steps: list[RepositorySetupStepResponse]
    manual_steps: list[str]
    callback_token_configured: bool
    api_base_url: str


class ProgressEvent(BaseModel):
    generation_id: str
    status: str
    message: str
    timestamp: datetime


class ProviderConfigRequest(BaseModel):
    provider_name: str
    display_name: Optional[str] = None
    api_key: Optional[str] = None  # If None or empty, keep the existing encrypted key
    model_name: Optional[str] = None
    deployment_name: Optional[str] = None  # Azure OpenAI deployment id (API routing)
    endpoint: Optional[str] = None


class AzureDeploymentsRequest(BaseModel):
    endpoint: str
    api_key: Optional[str] = None
    provider_id: Optional[UUID] = None


class ProviderProbeRequest(BaseModel):
    """Credentials to check or to list models for, before anything is saved."""
    provider_name: str
    api_key: Optional[str] = None  # blank + provider_id => reuse the stored key
    provider_id: Optional[UUID] = None
    endpoint: Optional[str] = None
    model_name: Optional[str] = None  # model or (Azure) deployment to test
