"""Cloud provider registry — shared metadata for the setup wizard."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CredentialField:
    key: str
    label: str
    required: bool = True
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProvisionField:
    key: str
    label: str
    required: bool = False
    placeholder: str = ""


@dataclass(frozen=True)
class CloudProviderDef:
    id: str
    label: str
    default_region: str
    credential_fields: tuple[CredentialField, ...] = ()
    provision_fields: tuple[ProvisionField, ...] = ()


COMMON_PROVISION_FIELDS = (
    ProvisionField("region", "Region", required=True),
    ProvisionField("environment_name", "Environment name", placeholder="ffinn"),
)

CLOUD_PROVIDERS: dict[str, CloudProviderDef] = {
    "azure": CloudProviderDef(
        id="azure",
        label="Azure",
        default_region="eastus",
        credential_fields=(
            CredentialField("tenant_id", "Tenant ID", aliases=("tenantId",)),
            CredentialField("client_id", "Client ID", aliases=("clientId",)),
            CredentialField("client_secret", "Client secret", aliases=("clientSecret",)),
            CredentialField("subscription_id", "Subscription ID", aliases=("subscriptionId",)),
        ),
        provision_fields=(
            ProvisionField("region", "Region", required=True),
            ProvisionField("resource_group", "Resource group", placeholder="rg-ffinn"),
            ProvisionField("environment_name", "Environment name", placeholder="ffinn"),
        ),
    ),
    "aws": CloudProviderDef(
        id="aws",
        label="AWS",
        default_region="us-east-1",
        credential_fields=(
            CredentialField("access_key_id", "Access key ID", aliases=("accessKeyId",)),
            CredentialField("secret_access_key", "Secret access key", aliases=("secretAccessKey",)),
            CredentialField("region", "Region", required=False),
        ),
        provision_fields=COMMON_PROVISION_FIELDS,
    ),
    "gcp": CloudProviderDef(
        id="gcp",
        label="Google Cloud",
        default_region="us-central1",
        credential_fields=(
            CredentialField("project_id", "Project ID", aliases=("projectId",)),
            CredentialField("service_account_json", "Service account JSON", aliases=("serviceAccountJson",)),
        ),
        provision_fields=COMMON_PROVISION_FIELDS,
    ),
    "oci": CloudProviderDef(
        id="oci",
        label="Oracle Cloud",
        default_region="us-ashburn-1",
        credential_fields=(
            CredentialField("tenancy_ocid", "Tenancy OCID", aliases=("tenancyOcid",)),
            CredentialField("user_ocid", "User OCID", aliases=("userOcid",)),
            CredentialField("fingerprint", "API key fingerprint"),
            CredentialField("private_key", "Private key (PEM)", aliases=("privateKey",)),
            CredentialField("region", "Region", required=False),
        ),
        provision_fields=(
            ProvisionField("region", "Region", required=True),
            ProvisionField("compartment_ocid", "Compartment OCID", placeholder="ocid1.compartment.oc1.."),
            ProvisionField("environment_name", "Environment name", placeholder="ffinn"),
        ),
    ),
    "local": CloudProviderDef(
        id="local",
        label="Local",
        default_region="local",
        credential_fields=(),
        provision_fields=(
            ProvisionField("environment_name", "Environment name", placeholder="ffinn"),
        ),
    ),
}


def get_provider(provider: str) -> CloudProviderDef:
    key = provider.lower()
    if key not in CLOUD_PROVIDERS:
        raise KeyError(f"Unsupported cloud provider: {provider}")
    return CLOUD_PROVIDERS[key]


def resolve_credential(creds: dict[str, Any], cred_field: CredentialField) -> Any:
    """Return a credential value accepting camelCase aliases."""
    if cred_field.key in creds and creds[cred_field.key] not in (None, ""):
        return creds[cred_field.key]
    for alias in cred_field.aliases:
        if alias in creds and creds[alias] not in (None, ""):
            return creds[alias]
    return None


def require_credentials(provider: str, creds: dict[str, Any]) -> dict[str, Any]:
    """Validate required credential fields and return normalized snake_case dict."""
    defn = get_provider(provider)
    normalized: dict[str, Any] = {}
    for fld in defn.credential_fields:
        value = resolve_credential(creds, fld)
        if fld.required and not value:
            raise ValueError(f"{defn.label} requires {fld.label.lower()} ({fld.key}).")
        if value is not None:
            normalized[fld.key] = value
    return normalized
