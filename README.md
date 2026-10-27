# ffinn — free, open-source AI SaaS framework

[![CI](https://github.com/bplogan/ffinn/actions/workflows/ci.yml/badge.svg)](https://github.com/bplogan/ffinn/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Website](https://img.shields.io/badge/website-ffinn.ca-6366f1)](https://ffinn.ca)

**ffinn** is a free, MIT-licensed, **multi-tenant SaaS starter kit** with built-in **AI agents**. You get a production-minded foundation (auth, roles, billing, admin) plus:

- a **build agent** that turns plain-English feature requests into code, pull requests, staging deployments and production releases, and
- **chat assistants** you create yourself, each with its own instructions, file uploads and conversation history, like the ChatGPT and Claude web apps but on your own stack.

Bring your own keys for OpenAI, Anthropic Claude, Google Gemini, Azure OpenAI, GitHub Models, Ollama or any OpenAI-compatible server. No licence fees and no vendor lock-in.

Built with a **Python/FastAPI** backend and a **Next.js** frontend. Website and docs: **[ffinn.ca](https://ffinn.ca)**.

## Features

- **Multi-tenancy**: tenant isolation, tenant management, per-tenant branding
- **Identity and access**: JWT auth, roles and fine-grained permissions, 2FA, SSO (OIDC and SAML 2.0), team invitations, delegation, audit logs
- **Billing**: subscription plans and editions, registration paywall, Stripe and PayPal
- **Notifications**: email (SMTP), SMS, push, and in-app/WebSocket channels
- **AI build agent**: describe a feature, review the generated branch/PR, deploy to staging, promote to production, or revert. Generated code is checked against the framework's patterns.
- **AI chat assistants**: create as many agents as you need, each responsible for its own job. Streaming chat, file and image upload, and per-user history.
- **Bring your own AI**: OpenAI, Anthropic Claude, Google Gemini, Azure OpenAI, GitHub Models, Ollama, or any OpenAI-compatible server. Live model lists and a connection test before you save.
- **Cloud setup**: guided provisioning helpers for Azure, AWS, GCP, Oracle Cloud and local, plus CI/CD workflows. ffinn.ca itself runs on the AWS reference setup in `infra/aws/`
- **Admin console**: users, roles, tenants, settings, feature flags, audit logs

## Contributing

ffinn is MIT licensed and contributions are very welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) to get started, and please follow our [Code of Conduct](CODE_OF_CONDUCT.md). Found a vulnerability? See [SECURITY.md](SECURITY.md).

## Repository Structure

```
ffinn/
├── python-backend/   # FastAPI backend — REST API, auth, AI agents, multi-tenancy
├── nextjs-frontend/  # Next.js frontend — public site, docs, portal, admin UI
├── infra/aws/        # Reference AWS deployment (runs ffinn.ca)
├── .github/          # CI, deploy workflows and contribution templates
└── docker-compose.yml
```

## Quick Start

### Option A — Docker Compose

```bash
docker compose up --build
```

- API: `http://localhost:8000`
- App: `http://localhost:3000`
- Default admin: `admin@localhost` / `ChangeMe123!`

> **Local development only.** `docker-compose.yml` ships well-known development secrets (JWT key, encryption key, admin password, database password). Never expose this stack to the internet or reuse these values; for any real deployment, generate your own and set `ENVIRONMENT=production`. In production the backend refuses to start if `JWT_SECRET_KEY` is shorter than 32 characters, `ENCRYPTION_KEY` is empty or shorter than 32 characters, or `JWT_SECRET_KEY`, `ENCRYPTION_KEY`, `CALLBACK_TOKEN` or `DEFAULT_ADMIN_PASSWORD` is a value published in this repo (`docker-compose.yml`, `.env.example`, the CI workflows, or anything starting with `CHANGE-THIS`); `STAGING_DEMO_PASSWORD` is checked too when `SEED_STAGING_DEMO=true`. It does not check the database password or judge the strength of other values.

### Option B — Local development

#### Backend

```bash
cd python-backend
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # fill in your values
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

API available at `http://localhost:8000`  
Swagger docs at `http://localhost:8000/docs`

#### Frontend

```bash
cd nextjs-frontend
npm install
cp .env.example .env.local   # set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

App available at `http://localhost:3000`

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic, PostgreSQL |
| Auth | JWT + bcrypt, TOTP 2FA, SSO (OIDC and SAML 2.0) |
| Payments | Stripe, PayPal |
| AI | Multi-provider (OpenAI, Anthropic, Google Gemini, Azure OpenAI, GitHub Models, Ollama, OpenAI-compatible) |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS |
| State | TanStack Query |

## Environment Variables

### Backend (`python-backend/.env`)

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `JWT_SECRET_KEY` | JWT signing key (min 32 characters) |
| `ENCRYPTION_KEY` | Fernet key for encrypting AI provider API keys |
| `APP_URL` | Frontend base URL (default `http://localhost:3000`) |
| `API_BASE_URL` | Public API URL, used for CI callbacks |
| `CORS_ORIGINS_RAW` | Comma-separated allowed CORS origins |
| `CALLBACK_TOKEN` | Shared secret for build-agent CI callbacks |
| `DEFAULT_ADMIN_EMAIL` | Seed admin email for first login |
| `DEFAULT_ADMIN_PASSWORD` | Seed admin password for first login |
| `ALLOW_REGISTRATION` | Allow self-service sign-up (default `true`) |
| `MULTI_TENANCY_ENABLED` | Enable multi-tenancy |
| `STRIPE_SECRET_KEY` | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |

Copy `python-backend/.env.example` for a full list.

### Frontend (`nextjs-frontend/.env.local`)

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | Base URL of the backend API |

## Deploying

The deploy workflows in `.github/workflows/` (`aws-deploy-*.yml`, `ai-agent-*.yml`) ship ffinn.ca itself and only run in `bplogan/ffinn`. If you fork ffinn, change the `github.repository` guards and configure your own secrets and variables (the `secrets.*` and `vars.*` the workflows reference). [`infra/aws/README.md`](infra/aws/README.md) documents the AWS setup (Lightsail, Caddy, ECR, staging for the build agent, DNS, rollback). The portal's Cloud Setup page can provision other clouds, and the build agent's workflow templates are in `python-backend/app/ai_agent/templates/workflows/`. Nothing in this repository contains credentials, and you should never commit yours.

## Security

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## License

[MIT](LICENSE)
