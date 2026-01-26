# Multi-stage Dockerfile for frontend (dev and production targets)
#
# Build Optimizations:
#   - BuildKit cache mounts for npm/node_modules (~5-10x faster rebuilds)
#   - Multi-stage build reduces production image size (dev and prod targets)
#
# Security Features:
#   - Non-root user execution (dev: node, prod: nginx unprivileged)
#   - Minimal production image (nginx-unprivileged)
#   - Health checks for container orchestration
#   - Security headers in nginx config
#
# Usage:
#   DOCKER_BUILDKIT=1 docker build --target dev -t frontend:dev .
#   DOCKER_BUILDKIT=1 docker build --target prod -t frontend:prod .
#   podman-compose build frontend  # Automatically enables BuildKit

# =============================================================================
# Base stage: shared Node.js setup and dependencies
# =============================================================================
FROM node:20.19.6-alpine3.23 AS base

# OCI Image Labels (org.opencontainers.image.*)
LABEL org.opencontainers.image.vendor="home-security-intelligence"
LABEL org.opencontainers.image.title="Frontend Dashboard"
LABEL org.opencontainers.image.description="React dashboard for home security monitoring with real-time WebSocket updates"
LABEL org.opencontainers.image.licenses="MPL-2.0"
LABEL org.opencontainers.image.source="https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence"
LABEL org.opencontainers.image.documentation="https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/docs"
LABEL org.opencontainers.image.authors="home-security-intelligence"
LABEL org.opencontainers.image.base.name="node:20.19.6-alpine3.23"
LABEL org.opencontainers.image.base.digest="node:20.19.6-alpine3.23"

WORKDIR /app

# Install wget for healthcheck (needed in both dev and prod)
# hadolint ignore=DL3018
RUN apk add --no-cache wget

# Copy package files and install ALL dependencies (including devDependencies)
# DevDependencies are needed for: TypeScript (tsc), Vite, testing tools
# Use --legacy-peer-deps for React 19 + Tremor (requires React 18) compatibility
# Rebuild native modules for the current platform (required for ARM64/musl)
# This ensures Rollup's platform-specific binaries are properly installed
#
# BuildKit cache mount types:
#   - /root/.npm: npm cache directory (~5-10x faster for repeated builds)
#   - /root/.bun: bun package manager cache (for future bun adoption)
#   - node_modules: persists installed packages across builds (instant installs)
#
# Cache mount persistence: "shared" mode for parallel builds, "private" for isolation
COPY package*.json ./
RUN --mount=type=cache,target=/root/.npm,sharing=shared \
    --mount=type=cache,target=/root/.bun,sharing=shared \
    npm ci --legacy-peer-deps && npm rebuild

# =============================================================================
# Development target: Vite dev server with hot reload
# =============================================================================
FROM base AS dev

# Copy application source
COPY . .

# Change ownership to non-root user
RUN chown -R node:node /app

# Switch to non-root user
USER node

# Expose Vite dev server port
EXPOSE 5173

# Health check for dev server
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:5173 || exit 1

# Run Vite dev server (accessible from host)
CMD ["npm", "run", "dev", "--", "--host", "--port", "5173"]

# =============================================================================
# Builder stage: compile TypeScript and build production assets
# =============================================================================
FROM base AS builder

# Copy source and build
# NODE_ENV is NOT set here so devDependencies (tsc, vite) are available
COPY . .

# Build with production optimizations
# This runs: tsc && vite build (needs TypeScript from devDependencies)
ENV NODE_ENV=production
RUN npm run build

# =============================================================================
# Production target: nginx unprivileged serving static assets
# =============================================================================
# Use nginx-unprivileged for better security (runs as non-root by default)
# stable-alpine-slim: smallest footprint with security patches, auto-updated weekly
FROM nginxinc/nginx-unprivileged:stable-alpine-slim AS prod

# OCI Image Labels (org.opencontainers.image.*)
LABEL org.opencontainers.image.vendor="home-security-intelligence"
LABEL org.opencontainers.image.title="Frontend Dashboard"
LABEL org.opencontainers.image.description="React dashboard for home security monitoring with real-time WebSocket updates"
LABEL org.opencontainers.image.licenses="MPL-2.0"
LABEL org.opencontainers.image.source="https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence"
LABEL org.opencontainers.image.documentation="https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/docs"
LABEL org.opencontainers.image.authors="home-security-intelligence"
LABEL org.opencontainers.image.base.name="nginxinc/nginx-unprivileged:stable-alpine-slim"
LABEL org.opencontainers.image.base.digest="nginxinc/nginx-unprivileged:stable-alpine-slim"

# Switch to root temporarily to install wget and configure files
USER root

# Install wget for healthcheck and openssl for self-signed cert generation
# Create certs directory for auto-generated SSL certificates
# hadolint ignore=DL3018
RUN apk add --no-cache wget openssl && \
    mkdir -p /etc/nginx/certs && \
    chown nginx:nginx /etc/nginx/certs

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy entrypoint script (injects DNS resolver at runtime for Docker/Podman portability)
COPY docker-entrypoint.sh /docker-entrypoint.sh

# Make entrypoint executable and ensure nginx user owns necessary directories
RUN chmod +x /docker-entrypoint.sh && \
    chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx /etc/nginx/conf.d

# Switch back to non-root nginx user
USER nginx

# Expose nginx ports (unprivileged ports: 8080 for HTTP, 8443 for HTTPS)
EXPOSE 8080 8443

# Health check (nginx-unprivileged listens on 8080)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080 || exit 1

# Use entrypoint to configure DNS resolver, then run nginx
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
