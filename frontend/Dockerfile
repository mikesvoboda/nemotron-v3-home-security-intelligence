# Multi-stage Dockerfile for frontend (dev and production targets)
# Usage:
#   docker build --target dev -t frontend:dev .
#   docker build --target prod -t frontend:prod .

# =============================================================================
# Base stage: shared Node.js setup and dependencies
# =============================================================================
FROM node:20.19.6-alpine3.23 AS base

WORKDIR /app

# Install wget for healthcheck (needed in both dev and prod)
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
# Production target: nginx serving static assets
# =============================================================================
# nginx 1.29.4 with Alpine 3.23 (latest stable with security patches)
FROM nginx:1.29.4-alpine3.23 AS prod

# Install wget for healthcheck
RUN apk add --no-cache wget

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy entrypoint script (injects DNS resolver at runtime for Docker/Podman portability)
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Expose nginx port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:80 || exit 1

# Use entrypoint to configure DNS resolver, then run nginx
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
