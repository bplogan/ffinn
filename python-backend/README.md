# ffinn Python Backend

A full-featured Python/FastAPI backend for the ffinn application framework — the backend for the ffinn application framework.

## Tech Stack

- **Framework**: FastAPI (async, OpenAPI/Swagger built-in)
- **ORM**: SQLAlchemy 2.0 (async) + Alembic migrations
- **Database**: PostgreSQL (via asyncpg)
- **Auth**: JWT (python-jose) + bcrypt password hashing
- **Payments**: Stripe + PayPal
- **Real-time**: WebSockets (AI generation progress)
- **Background Jobs**: asyncio task queue + APScheduler
- **Email**: SMTP via aiosmtplib
- **Encryption**: Fernet (cryptography library) — AES-256
- **Validation**: Pydantic v2

## Architecture

Follows **Clean Architecture** with clearly separated layers:

```
app/
├── api/          ← Routes/controllers (HTTP only, delegates to services)
├── services/     ← Business logic, orchestration
├── domain/       ← Domain models (SQLAlchemy)
├── schemas/      ← Pydantic DTOs (request/response models)
├── core/         ← Config, security, DI, exceptions
├── infrastructure/ ← Email, storage, external integrations
└── ai_agent/     ← AI agent system (AI-powered code generation)
    ├── pattern_enforcement.py  ← Protects framework files
    ├── prompt_optimization.py  ← Pre-processes user prompts
    ├── providers.py            ← OpenAI, Anthropic, Google, Azure OpenAI, GitHub Models, Ollama
    ├── chat_service.py         ← Chat assistants
    └── source_control.py       ← GitHub
```

## Quick Start

```bash
cd python-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your settings

# Run database migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload --port 8000
```

API available at: `http://localhost:8000`  
Swagger UI: `http://localhost:8000/docs`  
ReDoc: `http://localhost:8000/redoc`

## Frontend Integration

The Next.js frontend connects to this backend via the `NEXT_PUBLIC_API_URL` environment variable.

In `nextjs-frontend/.env.local`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

The frontend uses an API rewrite in `next.config.ts` to proxy `/api/*` requests to the backend, avoiding CORS issues during local development.

## Environment Variables

See `.env.example` for all configuration options.

## Deployment

See [GitHub Actions workflows](../.github/workflows/) for CI/CD pipelines and [`infra/aws/README.md`](../infra/aws/README.md) for the AWS deployment that runs ffinn.ca.
The image runs `alembic upgrade head` on start, then the app seeds roles, the admin, plans, feature flags and settings.

## AI Agent Safety System

The AI agent enforces strict architectural rules to prevent generated code from breaking the framework:

- **Protected paths**: Core framework files can never be overwritten
- **Bounded update files**: Only specific files (routes, layout, permissions) can be updated in a controlled way
- **Pattern validation**: Generated code is validated against architectural rules before committing (async SQLAlchemy relationships, Pydantic v2, route/service separation, etc.)
- **Auto-fix**: Common mistakes are fixed automatically; fixable validation issues are repaired in a loop before triggering an AI retry
- **Retry logic**: Up to 3 retry attempts with increasingly specific prompts

See `app/ai_agent/pattern_enforcement.py` for the full rule set.
