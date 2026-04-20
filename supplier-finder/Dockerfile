# syntax=docker/dockerfile:1.7
# -----------------------------------------------------------------------------
# Builder stage: TypeScript compile + prod-only install.
# -----------------------------------------------------------------------------
FROM node:20-bookworm-slim AS builder
WORKDIR /app

# System deps needed by sharp (libvips) and playwright (handled again below).
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 make g++ \
    && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json* ./
RUN npm ci

COPY tsconfig.json tsconfig.build.json vitest.config.ts ./
COPY src ./src
RUN npm run build

# Prune dev dependencies so the runtime image is lean.
RUN npm prune --omit=dev

# -----------------------------------------------------------------------------
# Runtime stage: Playwright's official base image already bundles Chromium +
# every Linux dep needed to render JS-heavy pages. Using the versioned tag
# keeps Chromium aligned with the playwright@1.48.x we install from npm.
# -----------------------------------------------------------------------------
FROM mcr.microsoft.com/playwright:v1.48.2-noble AS runtime
WORKDIR /app

ENV NODE_ENV=production \
    PORT=8787 \
    HEADLESS=true \
    TRANSFORMERS_CACHE=/app/models

# App code + its dependencies.
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY package.json ./

# HuggingFace model cache directory for @xenova/transformers. Pre-creating
# avoids the first request paying the mkdir cost.
RUN mkdir -p /app/models

EXPOSE 8787

# `dumb-init` is already present in the Playwright base image as tini.
ENTRYPOINT ["tini", "--"]
CMD ["node", "dist/server.js"]
