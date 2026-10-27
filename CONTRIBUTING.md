# Contributing to ffinn

Thanks for your interest in ffinn! Contributions of all kinds are welcome: bug reports, docs, tests, features, and AI-agent improvements.

By participating you agree to follow our [Code of Conduct](CODE_OF_CONDUCT.md). Contributions are licensed under the project's [MIT License](LICENSE).

## Ground rules

- **Never commit secrets.** No API keys, tokens, passwords, connection strings, `.env` files, or customer data. Use `.env.example` for documenting configuration. CI runs a secret scan on every PR.
- **Security issues are not public issues.** See [SECURITY.md](SECURITY.md).
- For anything larger than a small fix, **open an issue first** so we can agree on the approach before you invest time.

## Development setup

To just run ffinn, follow the [Quick Start](README.md#quick-start). To work on the code with hot reload you need Python 3.12, Node.js 20+, and Docker for the database.

```bash
# Database (from the repo root)
docker compose up -d db
```

```bash
# Backend
cd python-backend
python -m venv .venv && source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cp .env.example .env          # defaults already match the Docker database
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

```bash
# Frontend
cd nextjs-frontend
npm install
cp .env.example .env.local
npm run dev
```

## Before you open a pull request

Run the same checks CI runs:

```bash
# Backend (from python-backend/)
ruff check app/ --select E,W,F --ignore E501
pytest tests/ -q

# Frontend (from nextjs-frontend/)
npx tsc --noEmit
npm test
npm run build
```

Please also:

- Add or update tests for behavior changes. Backend tests use SQLite and need no external services.
- If you change database models, add an Alembic migration (`alembic revision --autogenerate -m "describe change"`) and review it by hand.
- If you add configuration, document it in `python-backend/.env.example` and the README.
- Keep PRs focused. One logical change per PR makes review faster.

## Project layout

```
python-backend/app/
  api/             HTTP routes (thin; delegate to services)
  services/        Business logic
  domain/models/   SQLAlchemy models
  schemas/         Pydantic request/response models
  core/            Config, security, dependencies
  infrastructure/  Email, SMS, storage, websockets, background tasks
  ai_agent/        AI agent: providers, source control, repo setup, pattern enforcement
nextjs-frontend/src/
  app/             Next.js routes (App Router)
  components/      UI components
  lib/             API client and helpers
```

## How a pull request gets merged

1. Fork the repository, create a branch, and open a pull request against `main`.
2. CI on pull requests from forks waits until a maintainer approves the run. It never has access to secrets or
   deployments.
3. Every pull request needs passing checks (backend, frontend, secret scan), resolved review conversations, and an
   approving review from a code owner (see `.github/CODEOWNERS`).
4. A maintainer merges it. Pushes to `main` deploy ffinn.ca, so changes to `.github/workflows/` and `infra/` get
   especially careful review.

## Commit and PR style

- Write commit messages in the imperative mood ("Add X", "Fix Y") with a short summary line.
- Fill in the PR template and link any related issue.
- Be responsive to review feedback; maintainers may ask for changes before merging.

## Adding an AI provider or cloud provider

AI providers live in `python-backend/app/ai_agent/providers.py`; cloud providers are registered in `python-backend/app/services/cloud_provider_registry.py` (with matching UI metadata in `nextjs-frontend/src/lib/aiProviderFormMeta.ts` and `cloudProviderConfig.ts`). Include tests that mock the provider's HTTP client so they never need real credentials.

Thank you for helping make ffinn better!
