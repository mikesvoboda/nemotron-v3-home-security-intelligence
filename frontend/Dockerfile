FROM node:20-alpine

WORKDIR /app

# Install wget for healthcheck
RUN apk add --no-cache wget

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy application code
COPY . .

# Expose Vite dev server port
EXPOSE 3000

# Run Vite dev server (accessible from host)
CMD ["npm", "run", "dev", "--", "--host"]
