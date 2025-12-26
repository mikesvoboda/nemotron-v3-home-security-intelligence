# Use specific Node.js LTS Alpine version for latest security patches
# Node.js 20.19.6 with Alpine 3.23 (December 2025 security release)
FROM node:20.19.6-alpine3.23

WORKDIR /app

# Install wget for healthcheck
RUN apk add --no-cache wget

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy application code
COPY . .

# Change ownership of app directory to non-root user
RUN chown -R node:node /app

# Switch to non-root user (node user exists in official Node images)
USER node

# Expose Vite dev server port
EXPOSE 3000

# Run Vite dev server (accessible from host)
CMD ["npm", "run", "dev", "--", "--host"]
