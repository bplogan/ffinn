# =============================================================================
# ffinn — Azure Infrastructure Setup
# =============================================================================
# Run this ONCE to provision all Azure resources.
# Prerequisites:
#   1. Azure CLI installed: https://learn.microsoft.com/en-us/cli/azure/install-azure-cli
#   2. Logged in: az login
#   3. gh CLI installed and authenticated: gh auth login
# =============================================================================

[CmdletBinding()]
Param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$GitHubRepo,                # owner/repo, e.g. "yourorg/ffinn"

    [ValidateNotNullOrEmpty()]
    [string]$ResourceGroup    = "ffinn-rg",

    [ValidateNotNullOrEmpty()]
    [string]$Location         = "eastus",

    [ValidateNotNullOrEmpty()]
    [string]$RegistryName     = "ffinnregistry",

    [ValidateNotNullOrEmpty()]
    [string]$EnvironmentName  = "ffinn-env",

    [ValidateNotNullOrEmpty()]
    [string]$ProdAppName      = "ffinn-api",

    [ValidateNotNullOrEmpty()]
    [string]$StagingAppName   = "ffinn-api-staging",

    [ValidateNotNullOrEmpty()]
    [string]$SwaName          = "ffinn-web",

    [ValidateNotNullOrEmpty()]
    [string]$PostgresServer   = "ffinn-postgres",

    [ValidateNotNullOrEmpty()]
    [string]$PostgresDb       = "ffinn",

    [ValidateNotNullOrEmpty()]
    [string]$PostgresUser     = "ffinnadmin"
)

$ErrorActionPreference = "Stop"

# Map parameters to the variables used throughout the script (kept for diff
# stability with the historical script body).
$RESOURCE_GROUP    = $ResourceGroup
$LOCATION          = $Location
$REGISTRY_NAME     = $RegistryName
$ENVIRONMENT_NAME  = $EnvironmentName
$PROD_APP_NAME     = $ProdAppName
$STAGING_APP_NAME  = $StagingAppName
$SWA_NAME          = $SwaName
$POSTGRES_SERVER   = $PostgresServer
$POSTGRES_DB       = $PostgresDb
$POSTGRES_USER     = $PostgresUser
$POSTGRES_PASSWORD = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 24 | ForEach-Object {[char]$_})
$GITHUB_REPO       = $GitHubRepo
# ── END CONFIGURATION ────────────────────────────────────────────────────────

Write-Host "`n=== ffinn Azure Setup ===" -ForegroundColor Cyan
Write-Host "Resource Group : $RESOURCE_GROUP"
Write-Host "Location       : $LOCATION"
Write-Host "Registry       : $REGISTRY_NAME"
Write-Host ""

# 1. Resource Group
Write-Host "[1/10] Creating resource group..." -ForegroundColor Yellow
az group create --name $RESOURCE_GROUP --location $LOCATION

# 2. Azure Container Registry
Write-Host "[2/10] Creating Container Registry..." -ForegroundColor Yellow
az acr create `
    --resource-group $RESOURCE_GROUP `
    --name $REGISTRY_NAME `
    --sku Basic `
    --admin-enabled true

# 3. PostgreSQL Flexible Server
Write-Host "[3/10] Creating PostgreSQL Flexible Server (this takes ~3 min)..." -ForegroundColor Yellow
az postgres flexible-server create `
    --resource-group $RESOURCE_GROUP `
    --name $POSTGRES_SERVER `
    --location $LOCATION `
    --admin-user $POSTGRES_USER `
    --admin-password $POSTGRES_PASSWORD `
    --sku-name Standard_B1ms `
    --tier Burstable `
    --storage-size 32 `
    --version 16 `
    --public-access 0.0.0.0  # allow Azure services; tighten in production

az postgres flexible-server db create `
    --resource-group $RESOURCE_GROUP `
    --server-name $POSTGRES_SERVER `
    --database-name $POSTGRES_DB

$PROD_DB_URL  = "postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_SERVER}.postgres.database.azure.com/${POSTGRES_DB}"
$STAGING_DB_URL = $PROD_DB_URL  # point at same DB for now; swap for a separate staging server later

# 4. Generate JWT + Encryption keys
Write-Host "[4/10] Generating secrets..." -ForegroundColor Yellow
$JWT_SECRET      = [System.Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
$ENCRYPT_KEY     = [System.Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
$STAGING_JWT     = [System.Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
$STAGING_ENCRYPT = [System.Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))

# 5. Container Apps Environment
Write-Host "[5/10] Creating Container Apps environment..." -ForegroundColor Yellow
az containerapp env create `
    --name $ENVIRONMENT_NAME `
    --resource-group $RESOURCE_GROUP `
    --location $LOCATION

# 6. Do an initial Docker build & push so Container Apps has an image to reference
Write-Host "[6/10] Building initial Docker image..." -ForegroundColor Yellow
az acr build `
    --registry $REGISTRY_NAME `
    --image "ffinn-api:initial" `
    --file python-backend/Dockerfile `
    python-backend/

$REGISTRY_SERVER   = "${REGISTRY_NAME}.azurecr.io"
$REGISTRY_USERNAME = (az acr credential show --name $REGISTRY_NAME --query username -o tsv)
$REGISTRY_PASSWORD_ACR = (az acr credential show --name $REGISTRY_NAME --query "passwords[0].value" -o tsv)

# 7. Production Container App
Write-Host "[7/10] Creating production Container App..." -ForegroundColor Yellow
az containerapp create `
    --name $PROD_APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --environment $ENVIRONMENT_NAME `
    --image "${REGISTRY_SERVER}/ffinn-api:initial" `
    --registry-server $REGISTRY_SERVER `
    --registry-username $REGISTRY_USERNAME `
    --registry-password $REGISTRY_PASSWORD_ACR `
    --target-port 8000 `
    --ingress external `
    --min-replicas 1 `
    --max-replicas 5 `
    --cpu 0.5 `
    --memory 1Gi `
    --env-vars `
        "ENVIRONMENT=production" `
        "DATABASE_URL=secretref:database-url" `
        "JWT_SECRET_KEY=secretref:jwt-secret" `
        "ENCRYPTION_KEY=secretref:encryption-key" `
    --secrets `
        "database-url=$PROD_DB_URL" `
        "jwt-secret=$JWT_SECRET" `
        "encryption-key=$ENCRYPT_KEY"

# 8. Staging Container App
Write-Host "[8/10] Creating staging Container App..." -ForegroundColor Yellow
az containerapp create `
    --name $STAGING_APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --environment $ENVIRONMENT_NAME `
    --image "${REGISTRY_SERVER}/ffinn-api:initial" `
    --registry-server $REGISTRY_SERVER `
    --registry-username $REGISTRY_USERNAME `
    --registry-password $REGISTRY_PASSWORD_ACR `
    --target-port 8000 `
    --ingress external `
    --min-replicas 0 `
    --max-replicas 2 `
    --cpu 0.5 `
    --memory 1Gi `
    --env-vars `
        "ENVIRONMENT=staging" `
        "DATABASE_URL=secretref:database-url" `
        "JWT_SECRET_KEY=secretref:jwt-secret" `
        "ENCRYPTION_KEY=secretref:encryption-key" `
    --secrets `
        "database-url=$STAGING_DB_URL" `
        "jwt-secret=$STAGING_JWT" `
        "encryption-key=$STAGING_ENCRYPT"

# Get the URLs
$PROD_URL    = (az containerapp show --name $PROD_APP_NAME --resource-group $RESOURCE_GROUP --query "properties.configuration.ingress.fqdn" -o tsv)
$STAGING_URL = (az containerapp show --name $STAGING_APP_NAME --resource-group $RESOURCE_GROUP --query "properties.configuration.ingress.fqdn" -o tsv)

# 9. Azure Static Web Apps (frontend)
Write-Host "[9/10] Creating Azure Static Web App for frontend..." -ForegroundColor Yellow
az staticwebapp create `
    --name $SWA_NAME `
    --resource-group $RESOURCE_GROUP `
    --location "eastus2" `
    --sku Free

$SWA_TOKEN    = (az staticwebapp secrets list --name $SWA_NAME --resource-group $RESOURCE_GROUP --query "properties.apiKey" -o tsv)
$SWA_HOSTNAME = (az staticwebapp show --name $SWA_NAME --resource-group $RESOURCE_GROUP --query "defaultHostname" -o tsv)

# Bake the backend URL into the SWA as an app setting (used by Next.js SSR + build)
az staticwebapp appsettings set `
    --name $SWA_NAME `
    --resource-group $RESOURCE_GROUP `
    --setting-names "NEXT_PUBLIC_API_URL=https://$PROD_URL" | Out-Null

# 10. Create a service principal for GitHub Actions
Write-Host "[10/10] Creating GitHub Actions service principal..." -ForegroundColor Yellow
$SUBSCRIPTION_ID = (az account show --query id -o tsv)
$TENANT_ID       = (az account show --query tenantId -o tsv)

# Create SP (without --sdk-auth which is deprecated and produces incompatible creds for azure/login@v2)
$SP_INFO = az ad sp create-for-rbac --name "ffinn-github-actions" | ConvertFrom-Json
$SP_APP_ID    = $SP_INFO.appId
$SP_SECRET    = $SP_INFO.password

# Explicitly assign Contributor on the resource group (required for az acr build + az containerapp update)
az role assignment create `
    --assignee $SP_APP_ID `
    --role Contributor `
    --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP"

# Also grant AcrPush (belt-and-suspenders; Contributor already covers ACR but this is explicit)
az role assignment create `
    --assignee $SP_APP_ID `
    --role AcrPush `
    --scope (az acr show --name $REGISTRY_NAME --query id -o tsv)

# Build credentials JSON in the exact format expected by azure/login@v2 with creds: input
$SP_JSON = [PSCustomObject]@{
    clientId       = $SP_APP_ID
    clientSecret   = $SP_SECRET
    subscriptionId = $SUBSCRIPTION_ID
    tenantId       = $TENANT_ID
} | ConvertTo-Json -Compress

# ── Set GitHub Secrets & Variables ───────────────────────────────────────────
Write-Host "`nSetting GitHub secrets..." -ForegroundColor Yellow
$SP_JSON          | gh secret set AZURE_CREDENTIALS         --repo $GITHUB_REPO
$PROD_DB_URL      | gh secret set PRODUCTION_DATABASE_URL   --repo $GITHUB_REPO
$JWT_SECRET       | gh secret set PRODUCTION_JWT_SECRET_KEY --repo $GITHUB_REPO
$ENCRYPT_KEY      | gh secret set PRODUCTION_ENCRYPTION_KEY --repo $GITHUB_REPO
$STAGING_DB_URL   | gh secret set STAGING_DATABASE_URL      --repo $GITHUB_REPO
$STAGING_JWT      | gh secret set STAGING_JWT_SECRET_KEY    --repo $GITHUB_REPO
$STAGING_ENCRYPT  | gh secret set STAGING_ENCRYPTION_KEY    --repo $GITHUB_REPO

Write-Host "Setting GitHub variables..." -ForegroundColor Yellow
gh variable set AZURE_REGISTRY                   --body $REGISTRY_NAME             --repo $GITHUB_REPO
gh variable set AZURE_RESOURCE_GROUP             --body $RESOURCE_GROUP            --repo $GITHUB_REPO
gh variable set AZURE_CONTAINER_APP_NAME         --body $PROD_APP_NAME             --repo $GITHUB_REPO
gh variable set AZURE_CONTAINER_APP_STAGING_NAME --body $STAGING_APP_NAME          --repo $GITHUB_REPO
gh variable set PRODUCTION_API_URL               --body "https://$PROD_URL"         --repo $GITHUB_REPO
gh variable set STAGING_URL                      --body "https://$STAGING_URL"      --repo $GITHUB_REPO
gh variable set API_BASE_URL                     --body "https://$PROD_URL"         --repo $GITHUB_REPO
gh variable set SWA_HOSTNAME                     --body $SWA_HOSTNAME               --repo $GITHUB_REPO
$SWA_TOKEN | gh secret set SWA_DEPLOYMENT_TOKEN  --repo $GITHUB_REPO

# ── Summary ──────────────────────────────────────────────────────────────────
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  Azure setup complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Production API  : https://$PROD_URL"
Write-Host "Staging API     : https://$STAGING_URL"
Write-Host "Frontend (SWA)  : https://$SWA_HOSTNAME"
Write-Host ""
Write-Host "All GitHub secrets + variables are set. Push to main to deploy."
Write-Host ""
Write-Host "Postgres password saved — store this somewhere safe:"
Write-Host "  $POSTGRES_PASSWORD" -ForegroundColor DarkYellow
