# Security Policy

## Supported versions

ffinn is released from `main`. Security fixes land on `main` and are deployed to ffinn.ca; there are no separately
maintained release branches. If you self-host, update to the latest `main` to pick up fixes.

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues, discussions or pull requests.**

Report them privately through [GitHub Security Advisories](https://github.com/bplogan/ffinn/security/advisories/new)
(preferred), or by email to **info@ffinn.ca**.

Please include:

- The type of issue and its impact (what an attacker could do)
- The affected file(s), endpoint(s) or page(s), and the commit or URL where you saw it
- Step-by-step instructions to reproduce, with a proof of concept if you have one

### What to expect

- We acknowledge reports within 48 hours.
- We keep you updated while we investigate and fix the issue.
- We credit you in the published advisory, unless you prefer to remain anonymous.

Please give us a reasonable time to ship a fix before disclosing publicly, and only test against your own
installation, not ffinn.ca or other people's data.

## Self-hosting checklist

`docker-compose.yml` and the `.env.example` files contain well-known development values. Never expose that stack to the
internet. For any real deployment:

1. **Generate your own secrets** and keep them out of git (`.env` files are ignored):
   - `JWT_SECRET_KEY`: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   - `ENCRYPTION_KEY` (encrypts stored provider keys and tokens):
     `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   - `CALLBACK_TOKEN` (authenticates the build agent's workflow callbacks): a long random string.
   - Back up `ENCRYPTION_KEY` somewhere safe. Losing it makes every stored key and token unreadable.
2. **Set `ENVIRONMENT=production`.** The backend then refuses to start if `JWT_SECRET_KEY` or `ENCRYPTION_KEY` is
   missing or shorter than 32 characters, or if `JWT_SECRET_KEY`, `ENCRYPTION_KEY`, `CALLBACK_TOKEN` or
   `DEFAULT_ADMIN_PASSWORD` is a value published in this repository (`docker-compose.yml`, the `.env.example` files,
   the CI workflows, or anything starting with `CHANGE-THIS`). `STAGING_DEMO_PASSWORD` is checked too when
   `SEED_STAGING_DEMO=true`. The list is `KNOWN_PLACEHOLDER_SECRETS` in `python-backend/app/core/config.py`. It only
   catches those known values: it does not check the database password or whether your own secrets are strong.
3. **Set `DEFAULT_ADMIN_EMAIL` / `DEFAULT_ADMIN_PASSWORD`** to your own values before the first start, then sign in and
   enable two-factor authentication for admin accounts.
4. **Restrict CORS** with `CORS_ORIGINS_RAW` to your own frontend origin(s). Don't use `*`.
5. **Serve everything over HTTPS** and send HSTS (`FORCE_HTTPS=true`, or set it in your reverse proxy).
6. **Leave `ALLOW_REGISTRATION=false`** unless you want public sign-up.
7. **Payments:** set `STRIPE_WEBHOOK_SECRET` (and `PAYPAL_WEBHOOK_ID`) so webhook signatures are verified.
   Card details are handled by Stripe and PayPal and never stored by ffinn.
8. **Build agent:** generated branches are unreviewed, AI-written code. Read the pull request before deploying it to
   staging, keep staging isolated from production data, and give the agent's source-control token the narrowest
   scopes your provider allows.
9. **Keep dependencies current.** This repository uses Dependabot and CodeQL; if you run a fork, enable them there too.

## How this repository is protected

- Secret scanning with push protection is enabled, and CI runs gitleaks over the full history on every pull request.
- Pull requests from forks need a maintainer's approval before their workflows run, and fork workflows never receive
  secrets or cloud credentials.
- `main` is protected: changes go through pull requests with passing checks and a code-owner review.
- Deployments authenticate to AWS through OIDC with a role that trusts only this repository's `main` branch; there are
  no long-lived cloud keys in GitHub.
