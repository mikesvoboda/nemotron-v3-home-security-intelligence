# Multi-stage Dockerfile for frontend (dev and production targets)
#
# Security Features:
#   - Non-root user execution (dev: node, prod: nginx unprivileged)
#   - Minimal production image (nginx-unprivileged)
#   - Health checks for container orchestration
#   - Security headers in nginx config
#
# Usage:
#   docker build --target dev -t frontend:dev .
#   docker build --target prod -t frontend:prod .

# =============================================================================
# Base stage: shared Node.js setup and dependencies
# =============================================================================
FROM node:20.19.6-alpine3.23 AS base

# Security labels
LABEL org.opencontainers.image.vendor="home-security-intelligence"
LABEL org.opencontainers.image.title="Frontend Dashboard"
LABEL org.opencontainers.image.description="React dashboard for home security monitoring"
LABEL org.opencontainers.image.licenses="MPL-2.0"
LABEL org.opencontainers.image.source="https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence"

WORKDIR /app

# Install wget for healthcheck (needed in both dev and prod)
# hadolint ignore=DL3018
RUN apk add --no-cache wget

# Copy package files and install ALL dependencies (including devDependencies)
# DevDependencies are needed for: TypeScript (tsc), Vite, testing tools
# Use --legacy-peer-deps for React 19 + Tremor (requires React 18) compatibility
COPY package*.json ./
RUN npm ci --legacy-peer-deps

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

# Security labels
LABEL org.opencontainers.image.vendor="home-security-intelligence"
LABEL org.opencontainers.image.title="Frontend Dashboard"
LABEL org.opencontainers.image.description="React dashboard for home security monitoring"
LABEL org.opencontainers.image.licenses="MPL-2.0"
LABEL org.opencontainers.image.source="https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence"

# Switch to root temporarily to install wget and configure files
USER root

# Install wget for healthcheck
# hadolint ignore=DL3018
RUN apk add --no-cache wget

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy entrypoint script (injects DNS resolver at runtime for Docker/Podman portability)
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Ensure nginx user owns the necessary directories
RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx /etc/nginx/conf.d

# Switch back to non-root nginx user
USER nginx

# Expose nginx ports (unprivileged ports for HTTP and HTTPS)
EXPOSE 8080
EXPOSE 8443

# Health check (nginx-unprivileged listens on 8080 for HTTP)
# Note: Health check uses HTTP even when SSL is enabled for simplicity
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080 || exit 1

# Use entrypoint to configure DNS resolver, then run nginx
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
