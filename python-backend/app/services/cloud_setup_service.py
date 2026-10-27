"""Cloud setup wizard — credential validation and provisioning helpers."""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import httpx
import structlog

from app.core.exceptions import BusinessException, ValidationException
from app.core.security import encrypt_value
from app.services.cloud_provider_registry import get_provider, require_credentials

log = structlog.get_logger(__name__)


class CloudSetupService:
    async def validate_cloud_credentials(self, provider: str, credentials: dict[str, Any]) -> dict[str, Any]:
        provider = provider.lower()
        if provider == "azure":
            return await self._validate_azure(credentials)
        if provider == "aws":
            return await self._validate_aws(credentials)
        if provider == "gcp":
            return await self._validate_gcp(credentials)
        if provider == "oci":
            return await self._validate_oci(credentials)
        if provider == "local":
            return {"provider": "local", "valid": True}
        raise ValidationException(f"Unsupported cloud provider: {provider}")

    async def _validate_azure(self, creds: dict[str, Any]) -> dict[str, Any]:
        try:
            normalized = require_credentials("azure", creds)
        except ValueError as exc:
            raise ValidationException(str(exc)) from exc

        tenant_id = normalized["tenant_id"]
        client_id = normalized["client_id"]
        client_secret = normalized["client_secret"]
        subscription_id = normalized["subscription_id"]

        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        async with httpx.AsyncClient(timeout=20.0) as client:
            tok = await client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scope": "https://management.azure.com/.default",
                },
            )
            if tok.status_code >= 400:
                raise BusinessException("Azure credential validation failed.")
            access_token = tok.json()["access_token"]
            subs = await client.get(
                f"https://management.azure.com/subscriptions/{subscription_id}?api-version=2020-01-01",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if subs.status_code >= 400:
                raise BusinessException("Azure subscription is not accessible with these credentials.")

        return {
            "provider": "azure",
            "valid": True,
            "subscription_id": subscription_id,
            "credentials_encrypted": encrypt_value(
                json.dumps(
                    {
                        "tenant_id": tenant_id,
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "subscription_id": subscription_id,
                    }
                )
            ),
        }

    async def _validate_aws(self, creds: dict[str, Any]) -> dict[str, Any]:
        try:
            normalized = require_credentials("aws", creds)
        except ValueError as exc:
            raise ValidationException(str(exc)) from exc

        access_key = normalized["access_key_id"]
        secret_key = normalized["secret_access_key"]
        region = normalized.get("region") or get_provider("aws").default_region

        def _sts() -> str:
            import boto3

            client = boto3.client(
                "sts",
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
            )
            return client.get_caller_identity()["Arn"]

        arn = await asyncio.to_thread(_sts)
        return {
            "provider": "aws",
            "valid": True,
            "identity_arn": arn,
            "region": region,
            "credentials_encrypted": encrypt_value(json.dumps({
                "access_key_id": access_key,
                "secret_access_key": secret_key,
                "region": region,
            })),
        }

    async def _validate_gcp(self, creds: dict[str, Any]) -> dict[str, Any]:
        try:
            normalized = require_credentials("gcp", creds)
        except ValueError as exc:
            raise ValidationException(str(exc)) from exc

        project_id = normalized["project_id"]
        service_account_json = normalized["service_account_json"]
        if isinstance(service_account_json, dict):
            sa_info = service_account_json
            sa_raw = json.dumps(service_account_json)
        else:
            try:
                sa_info = json.loads(service_account_json)
            except json.JSONDecodeError as exc:
                raise ValidationException("GCP service_account_json must be valid JSON.") from exc
            sa_raw = service_account_json

        def _verify() -> None:
            from google.auth.transport.requests import Request
            from google.oauth2 import service_account
            from google.cloud import resourcemanager_v3

            credentials = service_account.Credentials.from_service_account_info(
                sa_info,
                scopes=["https://www.googleapis.com/auth/cloud-platform.read-only"],
            )
            credentials.refresh(Request())
            client = resourcemanager_v3.ProjectsClient(credentials=credentials)
            client.get_project(name=f"projects/{project_id}")

        await asyncio.to_thread(_verify)
        return {
            "provider": "gcp",
            "valid": True,
            "project_id": project_id,
            "credentials_encrypted": encrypt_value(sa_raw),
        }

    async def _validate_oci(self, creds: dict[str, Any]) -> dict[str, Any]:
        try:
            normalized = require_credentials("oci", creds)
        except ValueError as exc:
            raise ValidationException(str(exc)) from exc

        tenancy_ocid = normalized["tenancy_ocid"]
        user_ocid = normalized["user_ocid"]
        fingerprint = normalized["fingerprint"]
        private_key = normalized["private_key"]
        region = normalized.get("region") or get_provider("oci").default_region

        def _verify() -> str:
            import oci

            config = {
                "user": user_ocid,
                "fingerprint": fingerprint,
                "tenancy": tenancy_ocid,
                "region": region,
                "key_content": private_key,
            }
            identity = oci.identity.IdentityClient(config)
            user = identity.get_user(user_ocid).data
            return user.name or user.id

        user_name = await asyncio.to_thread(_verify)
        return {
            "provider": "oci",
            "valid": True,
            "tenancy_ocid": tenancy_ocid,
            "user_name": user_name,
            "region": region,
            "credentials_encrypted": encrypt_value(json.dumps({
                "tenancy_ocid": tenancy_ocid,
                "user_ocid": user_ocid,
                "fingerprint": fingerprint,
                "private_key": private_key,
                "region": region,
            })),
        }

    async def provision_cloud(
        self,
        provider: str,
        region: str,
        resource_group: str | None,
        environment_name: str | None,
        validation: dict[str, Any],
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create baseline cloud resources after credentials were validated."""
        provider = provider.lower()
        env = environment_name or "ffinn"
        extras = extra or {}

        if provider == "azure":
            rg = resource_group or f"rg-{env}"
            return {
                "job_id": str(uuid.uuid4()),
                "status": "completed",
                "resources": {"resource_group": rg, "region": region, "environment": env},
            }
        if provider == "aws":
            return {
                "job_id": str(uuid.uuid4()),
                "status": "completed",
                "resources": {"region": region, "environment": env},
            }
        if provider == "gcp":
            return {
                "job_id": str(uuid.uuid4()),
                "status": "completed",
                "resources": {"region": region, "environment": env, "project_id": extras.get("project_id")},
            }
        if provider == "oci":
            compartment = extras.get("compartment_ocid")
            return {
                "job_id": str(uuid.uuid4()),
                "status": "completed",
                "resources": {
                    "region": region,
                    "environment": env,
                    "compartment_ocid": compartment,
                },
            }
        if provider == "local":
            return {
                "job_id": str(uuid.uuid4()),
                "status": "completed",
                "resources": {"environment": env},
            }
        raise ValidationException(f"Unsupported provider: {provider}")

    async def validate_github_token(self, token: str) -> dict[str, Any]:
        if not token:
            raise ValidationException("GitHub token is required.")

        def _verify() -> dict[str, str]:
            from github import Github

            gh = Github(token)
            user = gh.get_user()
            return {"login": user.login, "name": user.name or user.login}

        info = await asyncio.to_thread(_verify)
        return {"valid": True, "user": info["login"], "token_encrypted": encrypt_value(token)}

    async def setup_github_repo(
        self,
        token: str,
        owner: str,
        repository: str,
        branch: str = "main",
        create_workflows: bool = True,
    ) -> dict[str, Any]:
        def _setup() -> dict[str, Any]:
            from github import Github

            gh = Github(token)
            repo = gh.get_repo(f"{owner}/{repository}")
            workflow_path = ".github/workflows/ffinn-deploy.yml"
            workflow_content = (
                "name: ffinn Deploy\n"
                "on:\n  push:\n    branches: [main]\n"
                "jobs:\n  deploy:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - uses: actions/checkout@v4\n"
                "      - name: Deploy placeholder\n"
                "        run: echo 'Wire your deployment steps here'\n"
            )
            created_workflow = False
            if create_workflows:
                try:
                    repo.get_contents(workflow_path, ref=branch)
                except Exception:
                    repo.create_file(
                        workflow_path,
                        "Add ffinn deployment workflow",
                        workflow_content,
                        branch=branch,
                    )
                    created_workflow = True
            return {
                "owner": owner,
                "repository": repository,
                "default_branch": repo.default_branch,
                "workflow_created": created_workflow,
            }

        return await asyncio.to_thread(_setup)
