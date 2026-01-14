#!/bin/sh
# Inject the container's DNS resolver and SSL configuration into nginx config at runtime
# This makes the config portable across Docker (127.0.0.11) and Podman (10.89.0.x)

set -e

NGINX_CONF="/etc/nginx/conf.d/default.conf"

# =============================================================================
# DNS Resolver Configuration
# =============================================================================
RESOLVER=$(grep -m1 '^nameserver' /etc/resolv.conf | awk '{print $2}')

if [ -n "$RESOLVER" ]; then
    echo "Configuring nginx with DNS resolver: $RESOLVER"
    sed -i "s/__DNS_RESOLVER__/$RESOLVER/g" "$NGINX_CONF"
else
    echo "Warning: Could not determine DNS resolver, using default"
    sed -i "s/__DNS_RESOLVER__/127.0.0.11/g" "$NGINX_CONF"
fi

# =============================================================================
# HTTP Location Blocks (for non-SSL mode)
# =============================================================================
# These location blocks serve the application when SSL is disabled.
# When SSL is enabled, they are replaced with a redirect to HTTPS.
HTTP_LOCATIONS='
    # Reverse proxy for API requests to backend (handles /api and /api/*)
    # Uses $backend_upstream variable for dynamic DNS re-resolution
    # The ^~ modifier ensures this prefix location takes precedence over regex locations
    # This prevents the static asset regex from accidentally matching /api/* paths
    location ^~ /api {
        proxy_pass $backend_upstream;
        proxy_http_version 1.1;
        # nosemgrep: generic.nginx.security.request-host-used - using $server_name is safe
        proxy_set_header Host $server_name;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts for long-running requests
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Reverse proxy for WebSocket connections (handles /ws and /ws/*)
    # Uses validated upgrade header to prevent H2C smuggling attacks
    # Uses $backend_upstream variable for dynamic DNS re-resolution
    # The ^~ modifier ensures this prefix location takes precedence over regex locations
    location ^~ /ws {
        proxy_pass $backend_upstream;
        proxy_http_version 1.1;

        # WebSocket upgrade headers with H2C smuggling protection
        # Only "websocket" upgrade value is allowed, all others result in connection close
        proxy_set_header Upgrade $websocket_upgrade;
        proxy_set_header Connection $connection_upgrade;

        # Standard proxy headers
        # nosemgrep: generic.nginx.security.request-host-used - using $server_name is safe
        proxy_set_header Host $server_name;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket-specific timeouts (longer for persistent connections)
        proxy_connect_timeout 60s;
        proxy_send_timeout 86400s;
        proxy_read_timeout 86400s;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Single Page Application routing
    location / {
        try_files $uri $uri/ /index.html;
    }
'

# =============================================================================
# HTTPS Redirect Location (for SSL mode)
# =============================================================================
# When SSL is enabled, HTTP traffic is redirected to HTTPS.
# The health check endpoint is exempted (it has higher priority with exact match).
HTTPS_REDIRECT='
    # Redirect all HTTP traffic to HTTPS
    # The health check endpoint (location = /health) has higher priority and is not affected
    location / {
        return 301 https://$host:8443$request_uri;
    }
'

# =============================================================================
# SSL/TLS Configuration
# =============================================================================
# SSL is enabled when:
#   1. SSL_ENABLED environment variable is set to "true"
#   2. Certificate files exist at the expected paths

SSL_CERT="${SSL_CERT_PATH:-/etc/nginx/ssl/cert.pem}"
SSL_KEY="${SSL_KEY_PATH:-/etc/nginx/ssl/key.pem}"

if [ "${SSL_ENABLED:-false}" = "true" ]; then
    # Check if certificate files exist
    if [ -f "$SSL_CERT" ] && [ -f "$SSL_KEY" ]; then
        echo "SSL enabled: Configuring HTTPS server with HTTP-to-HTTPS redirect"

        # Replace HTTP locations with HTTPS redirect
        # Using a temp file approach for multiline replacement
        printf '%s' "$HTTPS_REDIRECT" > /tmp/https_redirect.conf
        sed -i "/__HTTP_LOCATIONS__/r /tmp/https_redirect.conf" "$NGINX_CONF"
        sed -i "/__HTTP_LOCATIONS__/d" "$NGINX_CONF"
        rm -f /tmp/https_redirect.conf

        # Inject the HTTPS server block
        # Using a heredoc-style approach with sed
        SSL_SERVER_BLOCK="
server {
    # HTTPS on 8443 for nginx-unprivileged (non-root cannot bind to ports < 1024)
    listen 8443 ssl;
    http2 on;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    # ==========================================================================
    # SSL/TLS Configuration
    # ==========================================================================
    ssl_certificate ${SSL_CERT};
    ssl_certificate_key ${SSL_KEY};

    # Modern SSL configuration (TLS 1.2+ only)
    # Based on Mozilla SSL Configuration Generator (Modern profile)
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # SSL session configuration (improves performance)
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_session_tickets off;

    # OCSP Stapling (improves SSL handshake performance)
    # Note: Requires ssl_trusted_certificate for full chain validation
    # Uncomment if using certificates from a public CA
    # ssl_stapling on;
    # ssl_stapling_verify on;
    # ssl_trusted_certificate /etc/nginx/ssl/chain.pem;

    # Dynamic DNS resolution for backend
    resolver ${RESOLVER:-127.0.0.11} valid=10s ipv6=off;
    set \$backend_upstream http://backend:8000;

    # Enable gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/javascript application/xml+rss application/json;

    # ==========================================================================
    # Security Headers (defense in depth)
    # ==========================================================================

    # HTTP Strict Transport Security (HSTS)
    # max-age=31536000 = 1 year
    # includeSubDomains: applies to all subdomains
    # preload: allows submission to browser preload lists (optional, remove if not submitting)
    add_header Strict-Transport-Security \"max-age=31536000; includeSubDomains\" always;

    # Prevent clickjacking attacks
    add_header X-Frame-Options \"SAMEORIGIN\" always;

    # Prevent MIME type sniffing
    add_header X-Content-Type-Options \"nosniff\" always;

    # Enable XSS filter (legacy, but still useful for older browsers)
    add_header X-XSS-Protection \"1; mode=block\" always;

    # Control referrer information
    add_header Referrer-Policy \"strict-origin-when-cross-origin\" always;

    # Content Security Policy - restrict resource loading
    # Note: 'unsafe-inline' for styles is required by Tailwind/Tremor
    add_header Content-Security-Policy \"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' ws: wss:; frame-ancestors 'self'; base-uri 'self'; form-action 'self'; upgrade-insecure-requests;\" always;

    # Permissions Policy - restrict browser features
    add_header Permissions-Policy \"accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()\" always;

    # Cross-Origin policies for additional isolation
    add_header Cross-Origin-Opener-Policy \"same-origin\" always;
    add_header Cross-Origin-Resource-Policy \"same-origin\" always;

    # ==========================================================================
    # Location Blocks
    # ==========================================================================

    # Reverse proxy for API requests to backend
    location ^~ /api {
        proxy_pass \$backend_upstream;
        proxy_http_version 1.1;
        proxy_set_header Host \$server_name;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Reverse proxy for WebSocket connections
    location ^~ /ws {
        proxy_pass \$backend_upstream;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$websocket_upgrade;
        proxy_set_header Connection \$connection_upgrade;
        proxy_set_header Host \$server_name;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 86400s;
        proxy_read_timeout 86400s;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)\$ {
        expires 1y;
        add_header Cache-Control \"public, immutable\";
    }

    # Single Page Application routing
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # Health check endpoint
    location = /health {
        access_log off;
        add_header Content-Type text/plain always;
        return 200 \"healthy\n\";
    }
}
"
        # Replace the placeholder with the SSL server block
        # Using printf to handle the multiline string and escape characters properly
        printf '%s' "$SSL_SERVER_BLOCK" > /tmp/ssl_server_block.conf
        sed -i "/__SSL_SERVER_BLOCK__/r /tmp/ssl_server_block.conf" "$NGINX_CONF"
        sed -i "/__SSL_SERVER_BLOCK__/d" "$NGINX_CONF"
        rm -f /tmp/ssl_server_block.conf

        echo "HTTPS configured on port 8443"
        echo "HTTP requests will be redirected to HTTPS"
    else
        echo "Warning: SSL_ENABLED=true but certificate files not found"
        echo "  Expected: $SSL_CERT and $SSL_KEY"
        echo "  Falling back to HTTP only"

        # Use HTTP locations (no redirect)
        printf '%s' "$HTTP_LOCATIONS" > /tmp/http_locations.conf
        sed -i "/__HTTP_LOCATIONS__/r /tmp/http_locations.conf" "$NGINX_CONF"
        sed -i "/__HTTP_LOCATIONS__/d" "$NGINX_CONF"
        rm -f /tmp/http_locations.conf

        sed -i 's|__SSL_SERVER_BLOCK__||g' "$NGINX_CONF"
    fi
else
    echo "SSL disabled: HTTP only mode"

    # Use HTTP locations (no redirect)
    printf '%s' "$HTTP_LOCATIONS" > /tmp/http_locations.conf
    sed -i "/__HTTP_LOCATIONS__/r /tmp/http_locations.conf" "$NGINX_CONF"
    sed -i "/__HTTP_LOCATIONS__/d" "$NGINX_CONF"
    rm -f /tmp/http_locations.conf

    # Remove SSL placeholder
    sed -i 's|__SSL_SERVER_BLOCK__||g' "$NGINX_CONF"
fi

# Execute the original command (nginx)
exec "$@"
