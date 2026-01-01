#!/bin/sh
# Inject the container's DNS resolver into nginx config at runtime
# This makes the config portable across Docker (127.0.0.11) and Podman (10.89.0.x)

set -e

# Get the nameserver from /etc/resolv.conf
RESOLVER=$(grep -m1 '^nameserver' /etc/resolv.conf | awk '{print $2}')

if [ -n "$RESOLVER" ]; then
    echo "Configuring nginx with DNS resolver: $RESOLVER"
    # Replace the placeholder with the actual resolver
    sed -i "s/__DNS_RESOLVER__/$RESOLVER/g" /etc/nginx/conf.d/default.conf
else
    echo "Warning: Could not determine DNS resolver, using default"
    sed -i "s/__DNS_RESOLVER__/127.0.0.11/g" /etc/nginx/conf.d/default.conf
fi

# Execute the original command (nginx)
exec "$@"
