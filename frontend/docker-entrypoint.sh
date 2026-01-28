#!/bin/sh
# Inject the container's DNS resolver and SSL configuration into nginx config at runtime
# This makes the config portable across Docker (127.0.0.11) and Podman (10.89.0.x)

set -e

NGINX_CONF="/etc/nginx/conf.d/default.conf"

# =============================================================================
# DNS Resolver Configuration
# =============================================================================
RESOLVER=$(grep -m1 '^nameserver' /etc/resolv.conf | awk '{print $2}')

# Grafana upstream URL (can be overridden with GRAFANA_INTERNAL_URL env var)
GRAFANA_UPSTREAM="${GRAFANA_INTERNAL_URL:-http://grafana:3000}"

if [ -n "$RESOLVER" ]; then
    echo "Configuring nginx with DNS resolver: $RESOLVER"
else
    echo "Warning: Could not determine DNS resolver, using default"
    RESOLVER="127.0.0.11"
fi

# Replace DNS resolver placeholder in main config
sed -i "s/__DNS_RESOLVER__/$RESOLVER/g" "$NGINX_CONF"

# =============================================================================
# HTTP Location Blocks (for non-SSL mode)
# =============================================================================
# These location blocks serve the application when SSL is disabled.
# When SSL is enabled, they are replaced with a redirect to HTTPS.
HTTP_LOCATIONS='
    # Reverse proxy for AI audit evaluation endpoints (longer timeout for LLM calls)
    # AI audit evaluation makes 4 LLM calls (up to 120s each) and can take 60-480+ seconds
    # This location takes precedence over generic /api due to longer prefix match
    location ^~ /api/ai-audit {
        proxy_pass $backend_upstream;
        proxy_http_version 1.1;
        # nosemgrep: generic.nginx.security.request-host-used - using $server_name is safe
        proxy_set_header Host $server_name;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Extended timeout for LLM evaluation calls (up to 10 minutes)
        proxy_connect_timeout 60s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }

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

    # Reverse proxy for Grafana dashboards (enables remote access via /grafana/)
    # Grafana is configured with GF_SERVER_SERVE_FROM_SUB_PATH=true, so it expects /grafana/ prefix
    # This allows embedding Grafana dashboards in iframes from any host
    # Uses nginx variable for dynamic DNS re-resolution (survives container IP changes)
    location ^~ /grafana/ {
        # Dynamic DNS resolution - re-resolves hostname on each request
        # This prevents 502 errors when Grafana container is recreated with new IP
        resolver __DNS_RESOLVER__ valid=10s ipv6=off;
        set $grafana_upstream '"${GRAFANA_UPSTREAM}"';
        proxy_pass $grafana_upstream;

        proxy_http_version 1.1;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Required for Grafana live/WebSocket features
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Disable buffering for real-time dashboard updates
        proxy_buffering off;
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
# IMPORTANT: API and WebSocket proxying is preserved on HTTP to avoid breaking
# browser API calls when the page was loaded via HTTP redirect (NEM-3827).
# The health check endpoint is exempted (it has higher priority with exact match).
HTTPS_REDIRECT_PORT="${FRONTEND_HTTPS_PORT:-8443}"
HTTPS_REDIRECT='
    # Reverse proxy for AI audit evaluation endpoints (longer timeout for LLM calls)
    # AI audit evaluation makes 4 LLM calls (up to 120s each) and can take 60-480+ seconds
    # This location takes precedence over generic /api due to longer prefix match
    location ^~ /api/ai-audit {
        proxy_pass $backend_upstream;
        proxy_http_version 1.1;
        # nosemgrep: generic.nginx.security.request-host-used - using $server_name is safe
        proxy_set_header Host $server_name;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Extended timeout for LLM evaluation calls (up to 10 minutes)
        proxy_connect_timeout 60s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }

    # Reverse proxy for API requests to backend (handles /api and /api/*)
    # Preserved on HTTP even with SSL enabled to avoid "Failed to fetch" errors (NEM-3827)
    # Uses $backend_upstream variable for dynamic DNS re-resolution
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
    # Preserved on HTTP even with SSL enabled to avoid WebSocket reconnection issues (NEM-3827)
    # Uses validated upgrade header to prevent H2C smuggling attacks
    location ^~ /ws {
        proxy_pass $backend_upstream;
        proxy_http_version 1.1;

        # WebSocket upgrade headers with H2C smuggling protection
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

    # Reverse proxy for Grafana dashboards (enables remote access via /grafana/)
    # Preserved on HTTP even with SSL enabled to allow Grafana embeds (NEM-3827)
    location ^~ /grafana/ {
        resolver __DNS_RESOLVER__ valid=10s ipv6=off;
        set $grafana_upstream '"${GRAFANA_UPSTREAM}"';
        proxy_pass $grafana_upstream;

        proxy_http_version 1.1;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Required for Grafana live/WebSocket features
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Disable buffering for real-time dashboard updates
        proxy_buffering off;
    }

    # Redirect all other HTTP traffic to HTTPS
    # The health check endpoint (location = /health) has higher priority and is not affected
    # API (/api), WebSocket (/ws), and Grafana (/grafana/) are proxied directly above
    location / {
        return 301 https://$host:'"${HTTPS_REDIRECT_PORT}"'$request_uri;
    }
'

# =============================================================================
# SSL/TLS Configuration
# =============================================================================
# SSL is enabled when:
#   1. SSL_ENABLED environment variable is set to "true"
#   2. Certificate files exist at the expected paths (or are auto-generated)

SSL_CERT="${SSL_CERT_PATH:-/etc/nginx/certs/cert.pem}"
SSL_KEY="${SSL_KEY_PATH:-/etc/nginx/certs/key.pem}"
SSL_CERT_DIR="$(dirname "$SSL_CERT")"

# Function to generate self-signed certificate
generate_self_signed_cert() {
    echo "Generating self-signed SSL certificate..."

    # Get hostname/IP for SAN (Subject Alternative Name)
    # Include common local addresses and any custom SSL_SAN_EXTRA entries
    HOSTNAME=$(hostname 2>/dev/null || echo "localhost")
    SSL_SANS="DNS:localhost,DNS:*.localhost,DNS:${HOSTNAME},IP:127.0.0.1,IP:::1"

    # Add extra SANs if provided (e.g., SSL_SAN_EXTRA="IP:192.168.1.145,DNS:myhost.local")
    if [ -n "${SSL_SAN_EXTRA:-}" ]; then
        SSL_SANS="${SSL_SANS},${SSL_SAN_EXTRA}"
    fi

    # Create OpenSSL config for SANs
    cat > /tmp/openssl.cnf << EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_ca
req_extensions = v3_ca

[dn]
C = US
ST = Local
L = Development
O = Home Security Intelligence
CN = localhost

[v3_ca]
subjectAltName = ${SSL_SANS}
basicConstraints = critical,CA:TRUE
keyUsage = critical, digitalSignature, keyEncipherment, keyCertSign
extendedKeyUsage = serverAuth, clientAuth
EOF

    # Generate private key and certificate
    if ! openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$SSL_KEY" \
        -out "$SSL_CERT" \
        -config /tmp/openssl.cnf; then
        echo "ERROR: openssl command failed"
        cat /tmp/openssl.cnf
    fi

    rm -f /tmp/openssl.cnf

    if [ -f "$SSL_CERT" ] && [ -f "$SSL_KEY" ]; then
        echo "Self-signed certificate generated successfully"
        echo "  Certificate: $SSL_CERT"
        echo "  Private key: $SSL_KEY"
        echo "  SANs: $SSL_SANS"
        echo "  Valid for: 365 days"
        echo ""
        echo "NOTE: This is a self-signed certificate for development."
        echo "      Browsers will show a security warning."
        return 0
    else
        echo "ERROR: Failed to generate certificate"
        return 1
    fi
}

if [ "${SSL_ENABLED:-false}" = "true" ]; then
    # Auto-generate certificate if it doesn't exist
    if [ ! -f "$SSL_CERT" ] || [ ! -f "$SSL_KEY" ]; then
        echo "SSL_ENABLED=true but certificate files not found"
        echo "  Expected: $SSL_CERT and $SSL_KEY"
        echo ""

        # Check if we can write to the certs directory
        if [ -w "$SSL_CERT_DIR" ]; then
            generate_self_signed_cert
        else
            echo "WARNING: Cannot write to $SSL_CERT_DIR - falling back to HTTP only"
            echo "  To fix: mount a writable volume to $SSL_CERT_DIR"
            echo "  Or: provide pre-generated certificates"
        fi
    fi

    # Check if certificate files exist (either pre-existing or just generated)
    if [ -f "$SSL_CERT" ] && [ -f "$SSL_KEY" ]; then
        echo "SSL enabled: Configuring HTTPS server with HTTP-to-HTTPS redirect"

        # Replace HTTP locations with HTTPS redirect
        # Using a temp file approach for multiline replacement
        printf '%s' "$HTTPS_REDIRECT" > /tmp/https_redirect.conf
        # Replace DNS resolver placeholder in the injected content
        sed -i "s/__DNS_RESOLVER__/$RESOLVER/g" /tmp/https_redirect.conf
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
    # ssl_trusted_certificate /etc/nginx/certs/chain.pem;

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
    # Note: 'unsafe-inline' and 'unsafe-eval' for scripts required by Grafana dashboards
    # Note: 'unsafe-inline' for styles is required by Tailwind/Tremor
    # Note: frame-src 'self' allows Grafana embeds via nginx proxy at /grafana/
    add_header Content-Security-Policy \"default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' ws: wss:; frame-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'self'; upgrade-insecure-requests;\" always;

    # Permissions Policy - restrict browser features
    add_header Permissions-Policy \"accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()\" always;

    # Cross-Origin policies for additional isolation
    add_header Cross-Origin-Opener-Policy \"same-origin\" always;
    add_header Cross-Origin-Resource-Policy \"same-origin\" always;

    # ==========================================================================
    # Location Blocks
    # ==========================================================================

    # Reverse proxy for AI audit evaluation endpoints (longer timeout for LLM calls)
    # AI audit evaluation makes 4 LLM calls (up to 120s each) and can take 60-480+ seconds
    # This location takes precedence over generic /api due to longer prefix match
    location ^~ /api/ai-audit {
        proxy_pass \$backend_upstream;
        proxy_http_version 1.1;
        proxy_set_header Host \$server_name;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }

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

    # Reverse proxy for Grafana dashboards (enables remote access via /grafana/)
    # Grafana is configured with GF_SERVER_SERVE_FROM_SUB_PATH=true, so it expects /grafana/ prefix
    # Uses nginx variable for dynamic DNS re-resolution (survives container IP changes)
    location ^~ /grafana/ {
        set \$grafana_upstream ${GRAFANA_UPSTREAM};
        proxy_pass \$grafana_upstream;
        proxy_http_version 1.1;
        proxy_set_header Host \$http_host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        proxy_buffering off;
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
        # Replace DNS resolver placeholder in the injected content
        sed -i "s/__DNS_RESOLVER__/$RESOLVER/g" /tmp/http_locations.conf
        sed -i "/__HTTP_LOCATIONS__/r /tmp/http_locations.conf" "$NGINX_CONF"
        sed -i "/__HTTP_LOCATIONS__/d" "$NGINX_CONF"
        rm -f /tmp/http_locations.conf

        sed -i 's|__SSL_SERVER_BLOCK__||g' "$NGINX_CONF"
    fi
else
    echo "SSL disabled: HTTP only mode"

    # Use HTTP locations (no redirect)
    printf '%s' "$HTTP_LOCATIONS" > /tmp/http_locations.conf
    # Replace DNS resolver placeholder in the injected content
    sed -i "s/__DNS_RESOLVER__/$RESOLVER/g" /tmp/http_locations.conf
    sed -i "/__HTTP_LOCATIONS__/r /tmp/http_locations.conf" "$NGINX_CONF"
    sed -i "/__HTTP_LOCATIONS__/d" "$NGINX_CONF"
    rm -f /tmp/http_locations.conf

    # Remove SSL placeholder
    sed -i 's|__SSL_SERVER_BLOCK__||g' "$NGINX_CONF"
fi

# Execute the original command (nginx)
exec "$@"
