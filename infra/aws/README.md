# ffinn on AWS

ffinn.ca runs on the shared Northforged Labs Lightsail server in AWS account `northforged-labs`,
region `ca-central-1` (Montreal). The server, Caddy (`/opt/edge`), the shared Postgres (`/opt/postgres`), the deploy
role and the ECR registry belong to the `northforged-labs` repository (`infra/aws/README.md` there). This repository
only adds its own project, `ffinn`.

Status: **moved from Azure on 2026-10-26.** The Azure resources had already been removed, so there was no data to
copy; ffinn started with an empty database.

## What runs where

| Piece | AWS |
|---|---|
| ffinn.ca | `web` container (Next.js, 256 MB). `www.ffinn.ca` is redirected to it by Caddy in one permanent hop. |
| api.ffinn.ca | `api` container (FastAPI, 512 MB). Runs `alembic upgrade head` on start, then seeds the admin, roles and plans. |
| Database | Database `ffinn`, login `ffinn_app`, on the shared Postgres. Connection string in `/opt/postgres/apps/ffinn.url`. Backed up nightly with the rest. |
| Uploads and chat attachments | `/opt/ffinn/data/uploads` and `/opt/ffinn/data/agent_uploads`, owned by uid 10001. **Not** in the Postgres backup. |
| Images | ECR `ffinn-api`, `ffinn-web` (last 5 kept) |
| Scheduled jobs | None on the server. The API runs its own scheduler in-process, so keep exactly one `api` container. |
| TLS | Caddy issues certificates itself once DNS points at the server. |
| Staging | Project `ffinn-staging` (see [Staging](#staging-for-the-build-agent)): staging.ffinn.ca and staging-api.ffinn.ca. |

Caddy also sets HSTS and the usual security headers for the site and the API (`site.caddy`). Certificates are Let's Encrypt, issued by Caddy. If DNS is wrong when a name is first requested, Let's Encrypt can rate-limit the retries for about an hour.

Files: `lightsail/ffinn/compose.yml` and `site.caddy`. Workflows: `aws-deploy-api.yml`, `aws-deploy-web.yml`.

## Settings on the server

`/opt/ffinn/api.env` (mode 600, never in git) is the only copy of the API's settings. It holds the JWT and
encryption keys, the callback token, the database URL and the first admin login. **Copy it to a password manager**;
the nightly backup does not include it, and losing `ENCRYPTION_KEY` makes every stored provider key and token
unreadable.

Read a value: `ssh ubuntu@<server-ip> 'grep DEFAULT_ADMIN /opt/ffinn/api.env'`.

To change a setting, edit the file, then:

```bash
docker compose -f /opt/ffinn/compose.yml up -d api
```

Email works through the Google Workspace SMTP relay, which allows this server by its fixed IP, so there is no
password. `api.env` only holds the first-start values; the live ones are in Admin > Settings > Email.

Things that are off until configured: sign-up (`ALLOW_REGISTRATION=false`), Stripe and PayPal. Turn them on by
editing `api.env`, or from the admin console where the setting lives in the database.

The frontend has no secrets: `NEXT_PUBLIC_API_URL` is baked in at build time (repository variable `PUBLIC_API_URL`,
default `https://api.ffinn.ca`).

## Deploying

`DEPLOY_TARGET=aws` is set on the repository, so a push to `main` deploys the part that changed:

- `python-backend/**` runs the tests, builds `ffinn-api`, and restarts `api`.
- `nextjs-frontend/**` type-checks, tests, builds `ffinn-web`, and restarts `web`.

Both can also be started by hand from the Actions tab. The build agent's own workflows are described under
[Staging](#staging-for-the-build-agent). Forks never deploy: every deploy workflow checks `github.repository`.

The deploy role trusts only this repository's `main` branch. Branch protection on `main` requires pull requests,
passing checks and a code-owner review for everyone except the repository admin.

## Staging for the build agent

The AI Agent's "Deploy to staging" and "Release" buttons start two workflows in this repository. On the agent's
source-control settings, set the staging workflow to `ai-agent-staging.yml` and the release workflow to
`ai-agent-production.yml`.

- **`ai-agent-staging.yml`** checks out the generation's branch, runs the backend and frontend tests, builds
  `ffinn-api-staging` and `ffinn-web-staging` (ECR, last 3 kept), and runs them as the `ffinn-staging` project
  (`lightsail/ffinn-staging`). It then seeds the demo tenant and reports the URLs back to the API. Deploys queue, since
  there is one staging environment.
- **`ai-agent-production.yml`** runs after the agent merges the pull request. The merge is a push to `main`, so the
  normal deploys above ship it; this workflow waits for those runs of the merge commit, checks production health, and
  reports back. It never deploys a second time.

The agent dispatches both on `main`, the only ref the deploy role trusts. The staging workflow checks the feature
branch out into its own folder and takes the deploy files from `main`. Neither job may declare a GitHub
`environment:`, which would change the OIDC subject and make AWS refuse the role. Callbacks use the
`FFINN_CALLBACK_TOKEN` secret, which must equal `CALLBACK_TOKEN` in both `api.env` files.

| Piece | Staging |
|---|---|
| staging.ffinn.ca / staging-api.ffinn.ca | `web` (192 MB) and `api` (384 MB) in `/opt/ffinn-staging`, sent `X-Robots-Tag: noindex`. |
| Database | `ffinn-staging`, login `ffinn_staging_app`, URL in `/opt/postgres/apps/ffinn-staging.url`. |
| Settings | `/opt/ffinn-staging/api.env`: its own JWT and encryption keys and admin password, `ENVIRONMENT=staging`, a demo tenant with one login per role (`STAGING_DEMO_PASSWORD`), no SMTP, no sign-up or billing. |

Staging runs unreviewed, AI-generated branches next to the other apps on the shared server, with access only to its
own database. Look at the pull request before deploying a branch you did not expect.

## DNS (Namecheap)

Namecheap has no ALIAS record for the bare domain, so every name is an `A` record to the server's static IP (the
repository variable `LIGHTSAIL_HOST`; `<server-ip>` below). Set the TTL to 300 seconds.

| Type | Host | Points to |
|---|---|---|
| A | @ | <server-ip> |
| A | www | <server-ip> |
| A | api | <server-ip> |
| A | staging | <server-ip> |
| A | staging-api | <server-ip> |

Leave MX, TXT and any other email records alone. Before changing DNS, check the server directly:

```bash
curl --resolve ffinn.ca:443:<server-ip> https://ffinn.ca/
curl --resolve api.ffinn.ca:443:<server-ip> https://api.ffinn.ca/api/monitoring/health
```

(Certificates only issue after DNS points here, so use `-k` until then, or check from inside the Caddy container.)

## Cost

Nothing extra: ffinn runs on the server the other projects already pay for, about 770 MB of its memory. Image storage is
about $1 a month. Check `free -m` before adding more.

## Rolling back and recovery

- **Bad deploy:** redeploy the previous image with
  `ssh ubuntu@<server-ip> 'cd /opt/ffinn && sed -i "s|^API_TAG=.*|API_TAG=<old sha>|" .env && docker compose up -d api'`
  (same for `WEB_TAG`). The last 5 images are kept in ECR.
- **Restart:** `docker compose -f /opt/ffinn/compose.yml restart api web`
- **Logs:** `docker logs ffinn-api-1 --tail 100`, `docker logs ffinn-web-1 --tail 100`
- **Restore the database:** from `/opt/postgres/backups` (restore steps are at the top of `backup.sh` in the
  `northforged-labs` repository).
- **Reset the admin password:** change `DEFAULT_ADMIN_PASSWORD` in `api.env` only affects a *new* database. To reset on
  a live one, use the "forgot password" flow once SMTP is set, or update the user's hash from a shell in the `api`
  container.

## Azure leftovers

Nothing of ffinn remains on Azure. The build agent's staging and release workflows moved to AWS on 2026-10-26 as
well. The old Azure deploy workflows and their GitHub secrets, variables and environments were removed on 2026-10-26.
