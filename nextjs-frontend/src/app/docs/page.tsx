'use client'
import { useEffect, useState } from 'react'
import DOMPurify from 'isomorphic-dompurify'
import {
  ChevronRight, Search, Book, Code, Shield, Bot, CreditCard,
  Globe, Rocket, Heart, PanelLeft, X } from 'lucide-react'
import SiteShell from '@/components/marketing/SiteShell'

type Topic = { id: string; title: string; content: string }
type Section = { id: string; title: string; icon: React.ReactNode; topics: Topic[] }

const sections: Section[] = [
  {
    id: 'getting-started', title: 'Getting Started', icon: <Book size={16} />,
    topics: [
      {
        id: 'quickstart', title: 'Quick Start',
        content: `# Quick Start

You only need **Git** and **Docker Desktop** (open it once so it's running). No Python, Node or database setup.

## 1. Get the code and start it

\`\`\`bash
git clone https://github.com/bplogan/ffinn.git
cd ffinn
docker compose up -d --build --wait
\`\`\`

The first run downloads and builds everything, so give it a few minutes. The command finishes once the app is ready.

## 2. Sign in

Open \`http://localhost:3000/auth/login\` and sign in with \`admin@localhost\` / \`ChangeMe123!\`.

## 3. Try it

1. Go to **AI Agent → Agents → Create an agent**.
2. Give it a name, pick an instructions template, choose a provider and paste your API key. Click **Test connection**, then **Create agent**.
3. Open the agent and start chatting.

Using **Ollama** on your own machine? With Docker, set its URL to \`http://host.docker.internal:11434\`, not \`localhost\`.

## Stop, restart or start over

| To | Run |
|---|---|
| Stop ffinn | \`docker compose down\` |
| Start it again | \`docker compose up -d --wait\` |
| Wipe all data and start fresh | \`docker compose down -v\` |
| See what went wrong | \`docker compose logs api\` |

## If something goes wrong

| Problem | Fix |
|---|---|
| \`Cannot connect to the Docker daemon\` | Docker Desktop isn't running. Open it and try again. |
| \`port is already allocated\` | Something else is using port 3000 or 8000. Stop it, or change the left-hand port in \`docker-compose.yml\`. |
| Sign-in says the password is wrong | Run \`docker compose down -v\` to reset, then start again. |

> This setup uses public development passwords and keys, so keep it on your own machine. For any real deployment, generate your own secrets and set \`ENVIRONMENT=production\`, which rejects the placeholder defaults.

## Developing without Docker

Only needed if you want to change the code with hot reload. You need **Python 3.12**, **Node.js 20 or newer**, and Docker for the database.

\`\`\`bash
docker compose up -d db
\`\`\`

**Backend** (one terminal):

\`\`\`bash
cd python-backend
python -m venv .venv
source .venv/bin/activate   # Windows: .\\.venv\\Scripts\\Activate.ps1
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
\`\`\`

The defaults in \`.env.example\` already match the Docker database. API docs are at \`http://localhost:8000/docs\`.

**Frontend** (second terminal):

\`\`\`bash
cd nextjs-frontend
npm install
cp .env.example .env.local
npm run dev
\`\`\`

Open \`http://localhost:3000\` and sign in with the same admin account.`
      },
      {
        id: 'configuration', title: 'Configuration',
        content: `# Configuration

All backend settings are in \`python-backend/.env\` and typed in \`app/core/config.py\`. \`.env.example\` lists every option.

## Required Settings

| Variable | Description |
|---|---|
| \`DATABASE_URL\` | asyncpg connection string |
| \`JWT_SECRET_KEY\` | Min 32-char random string (rejected if left at the default when \`ENVIRONMENT=production\`) |
| \`ENCRYPTION_KEY\` | Fernet key that encrypts AI provider keys and repository tokens (required in production) |

## Optional Settings

\`\`\`env
# App
APP_URL=https://your-frontend-domain.com
API_BASE_URL=https://your-api-domain.com     # used for CI callbacks
ENVIRONMENT=production
DEBUG=false

# CORS - comma-separated list (a JSON array also works)
CORS_ORIGINS_RAW=https://your-app.com,http://localhost:3000

# Sign-up and first admin
ALLOW_REGISTRATION=true
REQUIRE_EMAIL_CONFIRMATION=true
DEFAULT_ADMIN_EMAIL=admin@your-app.com
DEFAULT_ADMIN_PASSWORD=choose-a-strong-password

# Email (also editable later in Admin > Settings > Email)
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=apikey
SMTP_PASSWORD=your-sendgrid-api-key
SMTP_FROM_ADDRESS=noreply@your-app.com

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Build agent CI callbacks (must equal the FFINN_CALLBACK_TOKEN repository secret)
CALLBACK_TOKEN=a-long-random-string

# Storage
FILE_STORAGE_BACKEND=local    # or: s3, azure
S3_BUCKET_NAME=your-bucket
AWS_REGION=us-east-1
\`\`\`

Many settings can also be changed at runtime in **Admin → Settings**, where they are stored in the database.

## Generating Secrets

\`\`\`bash
# JWT secret
python -c "import secrets; print(secrets.token_hex(32))"

# Fernet encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
\`\`\``
      },
      {
        id: 'first-admin', title: 'First Admin User',
        content: `# First Admin User

The API seeds its starting data every time it starts, so there is nothing extra to run after \`alembic upgrade head\`.

## What gets seeded

- The **Admin** and **User** system roles and their default permissions
- A host administrator, created from \`DEFAULT_ADMIN_EMAIL\` and \`DEFAULT_ADMIN_PASSWORD\`. If either is empty the admin is skipped, and an existing admin is never overwritten
- Placeholder subscription plans (Free, Starter, Pro, Enterprise) with no pricing. Set your own in **Admin → Subscription Plans**
- Feature flags and default host settings

You can also run the seeder by hand:

\`\`\`bash
cd python-backend
python -m app.data_seeder
\`\`\`

Credentials are never printed. Sign in with the values you set, then **change the password immediately** via Profile → Change password.

## Creating more users

Sign-up is controlled by \`ALLOW_REGISTRATION\`. When it is on, people can register from the sign-in screen, or you can call the API:

\`\`\`http
POST /api/auth/register
Content-Type: application/json

{
  "email": "admin@yourapp.com",
  "password": "StrongP@ss1",
  "firstName": "Admin",
  "lastName": "User",
  "tenantName": "Acme Corp"
}
\`\`\`

Passwords need at least 8 characters with a digit, an uppercase letter and a special character. Admins can also invite people from **Team Invites**.`
      },
    ]
  },
  {
    id: 'architecture', title: 'Architecture', icon: <Code size={16} />,
    topics: [
      {
        id: 'overview', title: 'Overview',
        content: `# Architecture Overview

ffinn is a full-stack application framework with a clean separation between the Python API backend and the Next.js frontend.

## Project Layout

\`\`\`
ffinn/
├── python-backend/
│   ├── app/
│   │   ├── api/          ← FastAPI routers (HTTP only)
│   │   ├── core/         ← Config, security, middleware, permissions
│   │   ├── domain/       ← SQLAlchemy ORM models
│   │   ├── schemas/      ← Pydantic request/response models
│   │   ├── services/     ← Business logic layer
│   │   ├── infrastructure/ ← DB, email, SMS, push, storage, websockets
│   │   └── ai_agent/     ← Build agent, chat assistants, AI providers
│   └── alembic/          ← Database migrations
├── nextjs-frontend/
│   └── src/
│       ├── app/          ← Next.js App Router: public site, /auth, /app portal
│       ├── components/   ← Shared UI components
│       ├── contexts/     ← React context (Auth)
│       ├── lib/          ← API client (axios) and helpers
│       └── types/        ← TypeScript type definitions
├── infra/aws/            ← Reference AWS deployment
└── .github/workflows/    ← CI and deploy workflows
\`\`\`

## Backend Stack

- **FastAPI** - async Python API framework
- **SQLAlchemy 2 (async)** - ORM with async sessions
- **Alembic** - schema migrations
- **Pydantic v2** - validation and serialization
- **python-jose** - JWT tokens, with **bcrypt** password hashing
- **cryptography** - Fernet encryption for AI keys and repository tokens
- **PostgreSQL** via asyncpg

## Frontend Stack

- **Next.js 16** (App Router) and **React 19**
- **TypeScript**
- **Tailwind CSS**
- **TanStack Query** for server state
- **axios** for API calls`
      },
      {
        id: 'multi-tenancy', title: 'Multi-Tenancy',
        content: `# Multi-Tenancy

Every customer-facing resource in ffinn is scoped to a **tenant** (shown as an *organization* in the portal). Isolation is enforced in the service layer: services always filter by \`tenant_id\`, and the build agent's validator requires it on every generated model.

## Tenant Resolution

The current tenant comes from the authenticated user's JWT:

\`\`\`python
# Access token payload (abridged)
{
  "sub": "user-uuid",
  "email": "user@example.com",
  "tenant_id": "tenant-uuid",   # null for host users
  "roles": ["Admin"],
  "permissions": ["Users.View", "..."]
}
\`\`\`

A person can belong to several organizations. If their email matches more than one, sign-in asks which to open, and the portal sidebar shows the current one.

## Tenant Data Isolation

Domain models carry a \`tenant_id\` column, and every service query filters on it:

\`\`\`python
stmt = select(Entity).where(Entity.tenant_id == tenant_id)
\`\`\`

## Creating Tenants

Host admins create tenants in **Tenants** in the portal, or through the API:

\`\`\`http
POST /api/tenants
Authorization: Bearer <host-admin-token>

{
  "name": "Acme Corp",
  "adminEmail": "owner@acme.com",
  "adminPassword": "StrongP@ss1",
  "editionId": "optional-edition-uuid"
}
\`\`\`

Tenants can also be created by self-service sign-up when \`MULTI_TENANCY_ENABLED\` and \`ALLOW_REGISTRATION\` are on.

## Host and tenant users

The **host** is the platform owner with no tenant context: host users see every tenant plus the Platform Setup menus (plans, editions, feature flags, SSO, settings). Tenant admins only see their own organization's users, roles, audit logs and settings.`
      },
      {
        id: 'domain-models', title: 'Domain Models',
        content: `# Domain Models

Domain models are SQLAlchemy ORM classes in \`app/domain/models/\`.

## Base Pattern

Tenant-scoped models follow this shape (see \`projects.py\` for a working example):

\`\`\`python
class MyEntity(Base):
    __tablename__ = "my_entities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
\`\`\`

Every \`relationship()\` must set \`lazy="selectin"\` (and queries should use \`selectinload\`), because the async session cannot lazy-load.

## Migrations

Add a new model, then generate and run a migration:

\`\`\`bash
alembic revision --autogenerate -m "add my_entity"
alembic upgrade head
\`\`\``
      },
    ]
  },
  {
    id: 'authentication', title: 'Authentication', icon: <Shield size={16} />,
    topics: [
      {
        id: 'jwt', title: 'JWT Authentication',
        content: `# JWT Authentication

ffinn uses short-lived access tokens + long-lived refresh tokens.

## Login

\`\`\`http
POST /api/auth/login
Content-Type: application/json

{
  "username_or_email": "admin@example.com",
  "password": "your-password",
  "tenant_name": "Acme Corp"
}
\`\`\`

\`tenant_name\` is optional. Login is rate limited (10 attempts a minute per IP).

Response:

\`\`\`json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 3600
}
\`\`\`

The refresh token is also set as an httpOnly cookie. Two other response shapes exist: \`{ "requires_two_factor": true, "user_id": "..." }\` when the account has 2FA (see Two-Factor Auth), and \`{ "tenants": [...] }\` when the email belongs to several organizations and you must pick one with \`tenant_name\`.

## Using the Token

Include in every authenticated request:

\`\`\`
Authorization: Bearer <access_token>
\`\`\`

## Refreshing

\`\`\`http
POST /api/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ..."
}
\`\`\`

## Token Expiry

| Token | Default TTL |
|---|---|
| Access token | 60 minutes |
| Refresh token | 30 days |

Configure via \`JWT_ACCESS_TOKEN_EXPIRE_MINUTES\` and \`JWT_REFRESH_TOKEN_EXPIRE_DAYS\` in \`.env\`.`
      },
      {
        id: 'sso', title: 'SSO / OAuth2',
        content: `# SSO / OAuth2

ffinn supports single sign-on over **OIDC** and **SAML 2.0**. Configurations are per organization, under **Administration → SSO** in the portal.
## Supported Providers

Pick a protocol, then a preset:

- **OIDC**: Google, Microsoft, Okta, Auth0, or a custom OIDC issuer
- **SAML 2.0**: Okta, AD FS, Azure AD (Entra ID), or any SAML 2.0 identity provider

## Configuration

For **OIDC**, provide the issuer or metadata URL, a client ID and a client secret from your identity provider. For **SAML**, provide the identity provider's metadata URL or XML, and give the identity provider ffinn's service-provider metadata from \`GET /api/sso/sp/{configId}\`.

Register this callback URL with the identity provider:

\`\`\`
https://your-api-domain.com/api/sso/callback/{configId}
\`\`\`

A **Test** button on each configuration returns the identity provider's sign-in URL. Optionally turn on *auto-provision users* to create accounts on first sign-in.

## Sign-in flow

The sign-in page lists the enabled providers for an organization (\`GET /api/sso/tenant/{tenantName}\`). Choosing one starts \`GET /api/sso/login/{configId}\`, which redirects to the identity provider. After the callback, ffinn redirects the browser back to the app, which exchanges the result for normal access and refresh tokens.`
      },
      {
        id: '2fa', title: 'Two-Factor Auth',
        content: `# Two-Factor Authentication

ffinn supports TOTP-based 2FA compatible with Google Authenticator, Authy, and any RFC 6238 app. It is off by default: a host admin turns it on under **Admin → Settings → Security** (\`security.two_factor_enabled\`), after which users can enrol.

## Enabling 2FA

Users enable 2FA from **Profile → Security**. Behind the scenes:

\`\`\`http
POST /api/2fa/setup
Authorization: Bearer <token>
\`\`\`

Returns the shared key and a QR code. The user scans it, then confirms with a first code:

\`\`\`http
POST /api/2fa/verify
Authorization: Bearer <token>

{ "code": "123456" }
\`\`\`

The response contains the one-time recovery codes. They are stored hashed and cannot be shown again.

## Verifying on Login

When 2FA is enabled, \`POST /api/auth/login\` returns \`requires_two_factor: true\` and a \`user_id\` instead of tokens. Finish signing in with:

\`\`\`http
POST /api/2fa/verify-login
Content-Type: application/json

{
  "user_id": "uuid-from-login",
  "code": "123456",
  "is_recovery": false
}
\`\`\`

Returns full access/refresh tokens on success. Set \`is_recovery\` to \`true\` to use a recovery code. Attempts are limited to 5 a minute.

## Recovery Codes

Eight single-use recovery codes are generated on setup. Users can regenerate them (with a current TOTP code) from Profile → Security, which invalidates the old ones. \`POST /api/2fa/disable\` turns 2FA off with a code or the account password.`
      },
    ]
  },
  {
    id: 'ai-agents', title: 'AI Agents', icon: <Bot size={16} />,
    topics: [
      {
        id: 'overview', title: 'Overview',
        content: `# AI Agent Overview

ffinn's build agent generates full-stack code extensions - domain models, services, API endpoints, and React pages - from natural language prompts. Open it under **AI Agent** in the portal.

## How It Works

1. You describe a feature in **Generate Code**: *"Add a booking system with date ranges and availability"*
2. The agent reads your existing codebase structure
3. It generates code that follows ffinn's architecture patterns and validates it
4. The change is committed to a new branch and opened as a pull request
5. You deploy the branch to **staging** and try it
6. You **release to production**, or **revert** it. Every generation is kept in **History**

Production deploys always wait for you.

## Supported Providers

| Provider | Models |
|---|---|
| OpenAI | Any chat model your key can use |
| Anthropic | Any Claude model your key can use |
| Google | Any Gemini model your key can use |
| GitHub Models | Models available to your GitHub token |
| Azure OpenAI | Any deployment on your resource |
| Ollama | Any model installed on your Ollama server |
| OpenAI-compatible | LM Studio, vLLM, OpenRouter, or any server exposing \`/v1\` |

The model list is loaded live from the provider, so new models appear without a ffinn update.

## Key Features

- **Pattern enforcement** - generated code is validated against ffinn's architecture rules before writing
- **Retry loop** - if code has violations or format errors, the agent self-corrects up to 3 times
- **Source control** - GitHub today (and GitHub Actions for staging and release), so every change is a reviewable pull request
- **Live progress** - generation status streams to the page, with plain-language help for each stage
- **Tenant-aware** - generated entities are tenant-scoped`
      },
      {
        id: 'providers', title: 'Setting up Providers',
        content: `# Setting up AI Providers

The quickest way is **AI Agent → Setup Wizard**. To manage providers on their own, open **AI Agent → Providers**.

## Adding a Provider

1. Pick your provider
2. Paste your API key - it is encrypted before storage
3. Choose a model from the list that loads from the provider (or type one)
4. Click **Test connection** - you get the provider's real error message if something is wrong
5. Save

You can keep several providers of the same type (for example a dev and a production key).

## Agents link to providers

An agent stores a *link* to a provider, not a copy of its key. Rotate a key on the Providers page and every agent that uses it picks up the change. On the Generate page, *Advanced options → Provider override* lets you run one generation against a different saved provider.

## Provider-Specific Notes

**OpenAI**

\`\`\`
API Key: sk-...
Model: gpt-4o (recommended)
\`\`\`

**Anthropic**

\`\`\`
API Key: sk-ant-...
Model: pick from the list loaded for your key
\`\`\`

**Azure OpenAI**

\`\`\`
API Key: your-azure-key
Endpoint: https://your-resource.openai.azure.com
Deployment: your-deployment-name
\`\`\`

**Ollama (local)**

\`\`\`
Base URL: http://localhost:11434
Model: codestral (recommended for code)
\`\`\`

No API key needed for Ollama.`
      },
      {
        id: 'assistant-agents', title: 'Chat Assistants',
        content: `# Chat Assistants

Besides the **build agent** (which writes code), you can create any number of **assistant agents**: chat agents with their own job, instructions and AI key. They work like the web versions of Claude or ChatGPT, except everything runs on your ffinn install with your own provider accounts.

## Creating one

1. Open **AI Agent → Agents** and click **New agent**
2. Give it a name and a one-line description of what it is responsible for
3. Write its instructions (or start from a template: support, code review, writing, analysis)
4. Pick a saved provider, or add one with your own API key right there
5. Optionally choose a model and a creativity level

## Using it

- Replies **stream** as they are generated; press the stop button to cut one short
- **Attach files** with the paperclip, by dragging them in, or by pasting. PDF, Word, text, code and data files are read as text; images are sent to the model when it supports vision
- Every chat is saved per user. Rename or delete threads from the sidebar
- Code in replies is highlighted and has a copy button

## The build agent

The build agent is part of the framework. It is always present, cannot be removed, and keeps its own flow: **Generate Code**, review the pull request, deploy to staging, release. Its repository and provider settings live under **Agents → Build agent → Settings**.

## Where things are stored

Conversations and messages are in the \`ai_conversations\` and \`ai_messages\` tables. Attachments are written to \`AGENT_ATTACHMENTS_PATH\` (default \`./agent_uploads\`), which is **not** served publicly: downloads go through an authenticated endpoint.`
      },
      {
        id: 'pattern-enforcement', title: 'Pattern Enforcement',
        content: `# Pattern Enforcement

The build agent includes a built-in validator that checks generated code against ffinn's architectural rules before anything is committed.

## What Gets Validated

- **Domain models** must be tenant-scoped (\`tenant_id\`), and every \`relationship()\` must set \`lazy="selectin"\`
- **Services** must not depend on web-layer types
- **API routes** must not query the database or open sessions directly: they call services
- **Async SQLAlchemy and Pydantic v2** patterns are checked (no \`db.query()\`, no \`from_orm()\`)
- **New files** must be placed in the correct module directory

## Protected Files

The agent can read the whole project but cannot write to protected core files, and any it produces are stripped before the commit:

- backend \`app/core/\`, \`app/infrastructure/\`, \`main.py\`, \`alembic/\` and files such as \`database.py\`, \`security.py\` and \`config.py\`
- frontend \`components/\`, \`contexts/\`, \`lib/\`, \`types/\`, \`public/\`, and the app shell outside \`app/features/\`

A short list of bounded files (the sidebar navigation, permissions, the API router, model imports and the data seeders) can only be changed through controlled merge points, so a new feature is wired in without rewriting them.

## Auto-fix and Retries

Common mistakes, such as a missing \`selectinload\` or \`lazy="selectin"\`, are repaired automatically. If violations remain, the agent retries with a focused correction prompt explaining each one. Up to 3 attempts are made before the request fails with an explanation. Generated branches use the \`ai-agent/\` prefix by default.`
      },
    ]
  },
  {
    id: 'billing', title: 'Billing', icon: <CreditCard size={16} />,
    topics: [
      {
        id: 'stripe-setup', title: 'Stripe Setup',
        content: `# Stripe Setup

ffinn integrates with Stripe for subscriptions and Stripe Checkout, and with PayPal as an alternative. Both are off until configured. Keys can be set in \`.env\` or in **Admin → Settings → Payments**.

## Configuration

\`\`\`env
STRIPE_ENABLED=true
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Optional PayPal
PAYPAL_ENABLED=true
PAYPAL_MODE=live          # or: sandbox
PAYPAL_CLIENT_ID=...
PAYPAL_CLIENT_SECRET=...
PAYPAL_WEBHOOK_ID=...
\`\`\`

## Webhook

Register a webhook endpoint in your Stripe dashboard pointing to:

\`\`\`
https://your-api-domain.com/api/subscriptions/webhook
\`\`\`

(\`/api/webhooks/stripe\` is accepted as an alias.) Events are de-duplicated, so Stripe retries are safe. Subscribe to:
- \`checkout.session.completed\`
- \`customer.subscription.updated\`
- \`customer.subscription.deleted\`
- \`invoice.payment_succeeded\`
- \`invoice.payment_failed\`

The PayPal webhook is \`/api/subscriptions/paypal/webhook\`.

## Plan Configuration

Subscription plans (name, monthly and annual price, user and storage limits, Stripe price IDs) are managed in **Platform Setup → Subscr. Plans**. **Editions** group the features offered to a tenant and are assigned when a tenant is created or when someone signs up. Tenants see and change their plan under **Subscription**.`
      },
      {
        id: 'paywall', title: 'Feature Paywall',
        content: `# Feature Paywall

ffinn has two related tools for deciding who gets what.

## Feature flags

Host admins turn platform features on or off in **Platform Setup → Feature Flags**. A set of flags (AI agent, team invitations, two-factor, SSO, Stripe billing, SMS and push notifications) is seeded on first start, and you can add your own. Flag values are available to your code through the API:

\`\`\`http
GET /api/features
GET /api/features/{name}/enabled
\`\`\`

Tenant users get a read-only view of their own organization's values. Enforcement is up to each feature, so check the flag where you want to gate behaviour.

## Editions

**Platform Setup → Editions** defines the plans you offer and which features each includes (\`/api/editions/{id}/features\`). A tenant is assigned an edition when it is created or when someone signs up.

## Registration paywall

Turn on **Require edition selection during tenant registration** in **Admin → Settings → Registration** and new sign-ups must choose an edition before they can register. The plan-selection screen (\`/select-plan\`) reads the public editions from \`GET /api/paywall/editions\`. The paywall copy and prices (\`/api/paywall/configuration\`) can only be changed by host administrators.`
      },
    ]
  },
  {
    id: 'deployment', title: 'Deployment', icon: <Rocket size={16} />,
    topics: [
      {
        id: 'docker', title: 'Docker',
        content: `# Docker

Both services ship with production-ready Dockerfiles. ffinn runs anywhere Docker runs.

## Backend

The image is \`python:3.12-slim\`, runs as an unprivileged user, includes a health check at \`/api/monitoring/health\`, and applies database migrations on start:

\`\`\`dockerfile
# python-backend/Dockerfile (abridged)
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
\`\`\`

## Frontend

The frontend is a multi-stage Node 22 build that uses Next.js standalone output. The API URL must be baked in at build time:

\`\`\`bash
docker build \\
  --build-arg NEXT_PUBLIC_API_URL=https://your-api.com \\
  -t ffinn-frontend ./nextjs-frontend
\`\`\`

## Docker Compose (local)

\`docker-compose.yml\` at the repository root runs PostgreSQL 16, the API and the web app. It uses development-only secrets, so never expose it publicly:

\`\`\`bash
docker compose up --build
\`\`\`

## Production checklist

- Set \`ENVIRONMENT=production\`: placeholder secrets are then rejected, and Swagger (\`/docs\`) is turned off
- Generate your own \`JWT_SECRET_KEY\`, \`ENCRYPTION_KEY\` and \`CALLBACK_TOKEN\`, and back up \`ENCRYPTION_KEY\`: losing it makes every stored provider key and token unreadable
- Put TLS in front of both services, and set \`APP_URL\`, \`API_BASE_URL\` and \`CORS_ORIGINS_RAW\` to your real domains
- Run exactly one API container: scheduled jobs run inside the API process
- Back up the database and the uploads folders (\`LOCAL_STORAGE_PATH\`, \`AGENT_ATTACHMENTS_PATH\`)`
      },
      {
        id: 'aws', title: 'AWS and Other Clouds',
        content: `# AWS and Other Clouds

ffinn.ca itself runs on AWS, and the repository includes that setup as a reference in \`infra/aws/\`.

## The reference setup

- A single AWS Lightsail server (region \`ca-central-1\`) running Docker Compose with a \`web\` container (Next.js) and an \`api\` container (FastAPI)
- Caddy in front for automatic TLS (Let's Encrypt), HSTS and security headers
- PostgreSQL on the same server, backed up nightly
- Images built in GitHub Actions and stored in Amazon ECR (the last five are kept)
- The deploy role trusts only the repository's \`main\` branch through GitHub OIDC, so there are no long-lived AWS keys in GitHub

A push to \`main\` deploys whichever part changed: backend changes run the tests and restart \`api\`, frontend changes type-check, test and restart \`web\`.

## Staging for the build agent

The build agent's **Deploy to staging** and **Release** buttons run \`ai-agent-staging.yml\` and \`ai-agent-production.yml\`. Staging runs as a separate project on the same server, with its own database, keys and a demo tenant with one login per role. Both workflows report back to the API with a shared callback token (\`CALLBACK_TOKEN\` on the API, \`FFINN_CALLBACK_TOKEN\` in GitHub).

## Settings and DNS

The API reads one \`api.env\` file on the server. Keep a copy in a password manager, because losing \`ENCRYPTION_KEY\` makes stored provider keys and tokens unreadable. The frontend has no secrets: \`NEXT_PUBLIC_API_URL\` is baked in at build time. Point \`A\` records for the site, \`www\`, \`api\` and the staging names at the server.

## Forks

The deploy workflows only run in \`bplogan/ffinn\`. If you fork ffinn, change the \`github.repository\` guards and configure your own secrets and variables. See [infra/aws/README.md](https://github.com/bplogan/ffinn/blob/main/infra/aws/README.md) for the full runbook, including rollback and recovery.

## Other clouds

Any host that runs the two containers works. The portal's **Cloud Setup** page offers provisioning helpers for Azure, AWS, GCP, Oracle Cloud and a local option, and the build agent's workflow templates (\`python-backend/app/ai_agent/templates/workflows/\`) can be adapted to your own deploy steps.`
      },
    ]
  },
  {
    id: 'contributing', title: 'Contributing', icon: <Heart size={16} />,
    topics: [
      {
        id: 'overview', title: 'How to Contribute',
        content: `# Contributing to ffinn

ffinn is **free and open source** under the MIT license. The code lives at [github.com/bplogan/ffinn](https://github.com/bplogan/ffinn) and every kind of contribution is welcome: bug reports, documentation, tests, features, new AI providers, and improvements to the agents.

## Ground rules

- **Never commit secrets.** API keys, tokens, passwords, connection strings and \`.env\` files stay out of the repo. CI runs a secret scan on every pull request.
- **Security issues are not public issues.** Follow [SECURITY.md](https://github.com/bplogan/ffinn/blob/main/SECURITY.md) for private disclosure.
- For anything bigger than a small fix, **open an issue first** so we can agree on the approach before you invest time.
- Be kind. The [Code of Conduct](https://github.com/bplogan/ffinn/blob/main/CODE_OF_CONDUCT.md) applies everywhere the project happens.

## Development setup

\`\`\`bash
git clone https://github.com/bplogan/ffinn.git
cd ffinn
docker compose up --build
\`\`\`

Or run the backend (\`python-backend\`, FastAPI) and frontend (\`nextjs-frontend\`, Next.js) separately — see [CONTRIBUTING.md](https://github.com/bplogan/ffinn/blob/main/CONTRIBUTING.md) for the full steps.

## Before you open a pull request

\`\`\`bash
# Backend
cd python-backend && ruff check app/ --select E,W,F --ignore E501 && pytest tests/ -q

# Frontend
cd nextjs-frontend && npx tsc --noEmit && npm test && npm run build
\`\`\`

Keep pull requests focused, describe **why** as well as what, and add or update tests for behaviour you change.

## Good first contributions

- A new AI provider in \`python-backend/app/ai_agent/providers.py\` (implement \`generate_code\`, \`_ping\` and \`stream_chat\`)
- Better text extraction for chat attachments (\`chat_service.py\`)
- Translations, docs fixes, accessibility improvements
- Anything labelled **good first issue** on GitHub`
      },
    ]
  },
  {
    id: 'api-reference', title: 'API Reference', icon: <Globe size={16} />,
    topics: [
      {
        id: 'conventions', title: 'Conventions',
        content: `# API Conventions

The ffinn API is a JSON REST API served by FastAPI.

## Base URL

\`\`\`
https://your-api-domain.com/api
\`\`\`

Interactive Swagger UI is at \`/docs\` and ReDoc at \`/redoc\` (both are turned off when \`ENVIRONMENT=production\`). Routes live under \`/api/<feature>\`, for example \`/api/auth\`, \`/api/users\`, \`/api/tenants\`, \`/api/aiagent\` and \`/api/2fa\`.

## Authentication

All protected endpoints require a Bearer token:

\`\`\`
Authorization: Bearer <access_token>
\`\`\`

## Response Format

Success responses return the resource as JSON. Some feature routes use camelCase field names and others snake_case, so check the Swagger schema for the route you call.

Errors raised by ffinn share one shape:

\`\`\`json
{
  "error": "NOT_FOUND",
  "message": "Tenant not found"
}
\`\`\`

Request validation failures add a \`details\` array (it is left out when \`ENVIRONMENT=production\`, so field-level errors are not leaked):

\`\`\`json
{
  "error": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "details": [{ "loc": ["body", "email"], "msg": "value is not a valid email address", "type": "value_error" }]
}
\`\`\`

Some routes return FastAPI's plain \`{ "detail": "..." }\` form instead.

## Common Error Codes

| Code | HTTP Status | Meaning |
|---|---|---|
| \`BUSINESS_ERROR\` | 400 | A business rule was broken (the default for other codes) |
| \`UNAUTHORIZED\` | 401 | Missing or invalid credentials |
| \`INVALID_TOKEN\` | 401 | Token is invalid or expired |
| \`PAYMENT_ERROR\` | 402 | Payment processing failed |
| \`FORBIDDEN\` | 403 | Insufficient permissions |
| \`NOT_FOUND\` | 404 | Resource doesn't exist in this tenant |
| \`CONFLICT\` | 409 | Duplicate resource (e.g. email already in use) |
| \`VALIDATION_ERROR\` | 422 | Request body failed validation |
| \`INTERNAL_SERVER_ERROR\` | 500 | Unexpected error (details are logged, not returned) |

Login, registration and other sensitive routes are rate limited and return 429 when you exceed the limit.`
      },
      {
        id: 'pagination', title: 'Pagination',
        content: `# Pagination

List endpoints return a page of results wrapped in an envelope. Page size is capped at 100.

## Query Parameters

Most lists use offset paging, but the parameter names differ by route:

| Route | Parameters |
|---|---|
| \`/api/users\` | \`maxResultCount\` (default 20, max 100), \`skipCount\`, \`filter\`, \`role\` |
| \`/api/tenants\` | \`page\` (default 1), \`page_size\` (default 20, max 100), \`search\` |

Check the Swagger schema for the route you are calling.

## Example Request

\`\`\`http
GET /api/users?maxResultCount=25&skipCount=25&filter=smith
Authorization: Bearer <token>
\`\`\`

## Response Envelope

\`\`\`json
{
  "items": [ ... ],
  "total_count": 142,
  "page": 2,
  "page_size": 25,
  "total_pages": 6
}
\`\`\``
      },
    ]
  },
]

// ─── Markdown renderer ──────────────────────────────────────────────────────

const slug = (h: string) => h.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')

/** Tiny renderer for the in-page docs. Styling lives in `.docs-prose` (globals.css) so it follows the theme. */
function renderContent(md: string): string {
  // Set code blocks aside first so the rules below can't touch them: no headings
  // from `# comments`, and their newlines survive the final newline collapse.
  const blocks: string[] = []
  const escape = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return md
    .replace(/```(\w+)?\n?([\s\S]+?)```/g, (_, _lang, code: string) => {
      blocks.push(`<pre><code>${escape(code.replace(/\n$/, ''))}</code></pre>`)
      return `\u0000${blocks.length - 1}\u0000`
    })
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/^## (.+)$/gm, (_, h: string) => `<h2 id="${slug(h)}">${h}</h2>`)
    .replace(/\|([^\n]+)\|\n\|[-| :]+\|\n((?:\|[^\n]+\|\n?)*)/g, (_, head: string, body: string) => {
      const th = head.split('|').filter(Boolean).map(c => `<th>${c.trim()}</th>`).join('')
      const rows = body.trim().split('\n').map(r => `<tr>${r.split('|').filter(Boolean).map(c => `<td>${c.trim()}</td>`).join('')}</tr>`).join('')
      return `<div class="docs-table"><table><thead><tr>${th}</tr></thead><tbody>${rows}</tbody></table></div>`
    })
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/^(\d+)\. (.+)$/gm, '<div class="docs-li"><span>$1.</span><span>$2</span></div>')
    .replace(/^- (.+)$/gm, '<div class="docs-li"><span>–</span><span>$1</span></div>')
    .replace(/\n\n/g, '<div class="docs-gap"></div>')
    .replace(/\n/g, ' ')
    .replace(/\u0000(\d+)\u0000/g, (_, i: string) => blocks[Number(i)])
}

// ─── Page ────────────────────────────────────────────────────────────────────

const DEFAULT = { section: 'getting-started', topic: 'quickstart' }

function topicExists(section: string, topic: string) {
  return sections.some(s => s.id === section && s.topics.some(t => t.id === topic))
}

export default function DocsPage() {
  const [active, setActive] = useState(DEFAULT)
  const [search, setSearch] = useState('')
  const [mobileOpen, setMobileOpen] = useState(false)

  // Deep links: /docs#section/topic
  useEffect(() => {
    const [section, topic] = window.location.hash.replace(/^#/, '').split('/')
    if (section && topic && topicExists(section, topic)) setActive({ section, topic })
  }, [])

  const activeSection = sections.find(s => s.id === active.section)
  const activeTopic = activeSection?.topics.find(t => t.id === active.topic)

  const allTopics = sections.flatMap(s =>
    s.topics.map(t => ({ ...t, section: s.id, sectionTitle: s.title }))
  )
  const q = search.trim().toLowerCase()
  const filtered = q
    ? allTopics.filter(t => t.title.toLowerCase().includes(q) || t.content.toLowerCase().includes(q))
    : []

  function navigate(section: string, topic: string) {
    setActive({ section, topic })
    setSearch('')
    setMobileOpen(false)
    window.history.replaceState(null, '', `#${section}/${topic}`)
    window.scrollTo({ top: 0 })
  }

  const idx = allTopics.findIndex(t => t.section === active.section && t.id === active.topic)
  const prev = idx > 0 ? allTopics[idx - 1] : null
  const next = idx < allTopics.length - 1 ? allTopics[idx + 1] : null
  const headings = activeTopic ? [...activeTopic.content.matchAll(/^## (.+)$/gm)].map(m => m[1]) : []

  return (
    <SiteShell active="docs">
      {/* Docs sub-bar: mobile menu toggle + where you are */}
      <div className="sticky top-16 z-30 border-b bg-canvas/85 backdrop-blur-xl md:hidden">
        <div className="flex items-center gap-3 px-5 py-2.5">
          <button
            type="button"
            onClick={() => setMobileOpen(v => !v)}
            aria-expanded={mobileOpen}
            aria-controls="docs-nav"
            className="inline-flex shrink-0 items-center gap-2 rounded-full px-3 py-1.5 text-[13px] ring-1 ring-ink/15"
          >
            {mobileOpen ? <X size={14} /> : <PanelLeft size={14} />} Menu
          </button>
          <span className="truncate text-[13px] text-ink-mute">{activeSection?.title} / <span className="text-ink">{activeTopic?.title}</span></span>
        </div>
      </div>

      <div className="mx-auto flex w-full max-w-[1400px]">
        {/* Sidebar */}
        <aside
          id="docs-nav"
          aria-label="Documentation"
          className={`${mobileOpen ? 'flex' : 'hidden'} fixed inset-x-0 bottom-0 top-[117px] z-20 flex-col overflow-y-auto bg-canvas md:sticky md:top-16 md:flex md:h-[calc(100vh-4rem)] md:w-72 md:shrink-0 md:border-r`}
        >
          <div className="p-4 pb-2">
            <label className="relative block">
              <span className="sr-only">Search documentation</span>
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-mute" aria-hidden />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search docs…"
                className="w-full rounded-xl bg-surface py-2.5 pl-9 pr-3 text-[14px] text-ink outline-none ring-1 ring-ink/10 placeholder:text-ink-mute focus:ring-2 focus:ring-accent"
              />
            </label>
          </div>

          {q ? (
            <div className="px-2 pb-4" aria-live="polite">
              {filtered.length === 0 ? (
                <p className="px-3 py-3 text-[13px] text-ink-mute">No results for &ldquo;{search}&rdquo;</p>
              ) : (
                filtered.map(t => (
                  <button
                    key={`${t.section}-${t.id}`}
                    onClick={() => navigate(t.section, t.id)}
                    className="w-full rounded-lg px-3 py-2 text-left transition-colors hover:bg-ink/[0.05]"
                  >
                    <div className="font-mono text-[11px] uppercase tracking-[0.1em] text-ink-mute">{t.sectionTitle}</div>
                    <div className="text-[14px] text-ink">{t.title}</div>
                  </button>
                ))
              )}
            </div>
          ) : (
            <nav className="flex-1 px-2 pb-8">
              {sections.map(s => (
                <div key={s.id} className="mt-4">
                  <div className="flex items-center gap-2 px-3 py-1 font-mono text-[11px] uppercase tracking-[0.12em] text-ink-mute">
                    <span aria-hidden>{s.icon}</span>{s.title}
                  </div>
                  <ul className="mt-1">
                    {s.topics.map(t => {
                      const isActive = active.section === s.id && active.topic === t.id
                      return (
                        <li key={t.id}>
                          <button
                            onClick={() => navigate(s.id, t.id)}
                            aria-current={isActive ? 'page' : undefined}
                            className={`relative w-full rounded-lg px-3 py-1.5 text-left text-[14px] transition-colors ${
                              isActive ? 'bg-ink/[0.06] font-medium text-ink' : 'text-ink-soft hover:bg-ink/[0.03] hover:text-ink'
                            }`}
                          >
                            {isActive && <span className="absolute inset-y-1.5 left-0 w-[2px] rounded-full bg-accent" aria-hidden />}
                            {t.title}
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                </div>
              ))}
            </nav>
          )}
        </aside>

        {/* Content */}
        <div className="min-w-0 flex-1 px-5 py-10 sm:px-10 md:py-14 lg:px-16">
          {activeTopic && (
            <>
              <nav aria-label="Breadcrumb" className="mb-8 flex items-center gap-1.5 text-[13px] text-ink-mute">
                <span>Docs</span><ChevronRight size={12} aria-hidden />
                <span>{activeSection?.title}</span><ChevronRight size={12} aria-hidden />
                <span className="text-ink">{activeTopic.title}</span>
              </nav>
              <article
                className="docs-prose max-w-[72ch]"
                dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(renderContent(activeTopic.content)) }}
              />
              <div className="mt-16 grid max-w-[72ch] gap-3 border-t pt-8 sm:grid-cols-2">
                {prev ? (
                  <button onClick={() => navigate(prev.section, prev.id)} className="group rounded-2xl p-4 text-left ring-1 ring-ink/10 transition hover:ring-ink/25">
                    <div className="text-[12px] text-ink-mute">Previous</div>
                    <div className="mt-1 flex items-center gap-1.5 text-[15px] font-medium"><ChevronRight size={14} className="rotate-180 transition-transform group-hover:-translate-x-0.5" />{prev.title}</div>
                  </button>
                ) : <div />}
                {next ? (
                  <button onClick={() => navigate(next.section, next.id)} className="group rounded-2xl p-4 text-right ring-1 ring-ink/10 transition hover:ring-ink/25">
                    <div className="text-[12px] text-ink-mute">Next</div>
                    <div className="mt-1 flex items-center justify-end gap-1.5 text-[15px] font-medium">{next.title}<ChevronRight size={14} className="transition-transform group-hover:translate-x-0.5" /></div>
                  </button>
                ) : <div />}
              </div>
            </>
          )}
        </div>

        {/* On this page */}
        <aside className="sticky top-16 hidden h-[calc(100vh-4rem)] w-56 shrink-0 overflow-y-auto px-6 py-14 xl:block">
          {headings.length > 0 && (
            <nav aria-label="On this page">
              <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-ink-mute">On this page</p>
              <ul className="mt-4 space-y-2 border-l">
                {headings.map(h => (
                  <li key={h}>
                    <a
                      href={`#${slug(h)}`}
                      onClick={e => { e.preventDefault(); document.getElementById(slug(h))?.scrollIntoView({ behavior: 'smooth' }) }}
                      className="-ml-px block border-l border-transparent pl-3 text-[13px] leading-relaxed text-ink-mute transition-colors hover:border-ink hover:text-ink"
                    >
                      {h}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          )}
        </aside>
      </div>
    </SiteShell>
  )
}
