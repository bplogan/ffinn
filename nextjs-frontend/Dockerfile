# ── Next.js Frontend — ffinn Web ───────────────────────────────────────────
# Multi-stage build using Next.js standalone output mode.

# Stage 1: Install all dependencies
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# Stage 2: Build the application
FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NEXT_PUBLIC_API_URL is baked into the client bundle at build time.
# Pass the real backend URL via --build-arg (`docker build --build-arg NEXT_PUBLIC_API_URL=...`).
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

# Stage 3: Minimal production runtime (standalone output)
FROM node:22-alpine AS runner
WORKDIR /app

# wget is included in alpine base; used for the HEALTHCHECK
RUN addgroup -S -g 1001 nodejs \
    && adduser -S -G nodejs -u 1001 nextjs

ENV NODE_ENV=production
# Let the Next.js server bind on all interfaces so the reverse proxy can reach it
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

COPY --from=builder --chown=nextjs:nodejs /app/public ./public
# Standalone bundle (includes node_modules subset)
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
# Static assets must be copied separately for standalone mode
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD wget -qO- http://127.0.0.1:3000/ >/dev/null 2>&1 || exit 1

CMD ["node", "server.js"]
