#!/usr/bin/env python3
"""Interactive setup script for Home Security Intelligence.

Generates .env and docker-compose.override.yml files for user environment.
Supports two modes:
- Quick mode (default): Accept defaults with Enter
- Guided mode (--guided): Step-by-step with explanations
"""

import secrets
import socket

# Service definitions with default ports
SERVICES = {
    "backend": {"port": 8000, "category": "Core", "desc": "Backend API"},
    "frontend": {"port": 5173, "category": "Core", "desc": "Frontend web UI"},
    "postgres": {"port": 5432, "category": "Core", "desc": "PostgreSQL database"},
    "redis": {"port": 6379, "category": "Core", "desc": "Redis cache/queue"},
    "rtdetr": {"port": 8090, "category": "AI", "desc": "RT-DETRv2 object detection"},
    "nemotron": {"port": 8091, "category": "AI", "desc": "Nemotron LLM reasoning"},
    "florence": {"port": 8092, "category": "AI", "desc": "Florence-2 vision-language"},
    "clip": {"port": 8093, "category": "AI", "desc": "CLIP embeddings"},
    "enrichment": {"port": 8094, "category": "AI", "desc": "Entity enrichment"},
    "grafana": {"port": 3002, "category": "Monitoring", "desc": "Grafana dashboards"},
    "prometheus": {"port": 9090, "category": "Monitoring", "desc": "Prometheus metrics"},
    "alertmanager": {"port": 3000, "category": "Monitoring", "desc": "Alert manager"},
    "redis_exporter": {"port": 9121, "category": "Monitoring", "desc": "Redis exporter"},
    "json_exporter": {"port": 7979, "category": "Monitoring", "desc": "JSON exporter"},
}


def check_port_available(port: int) -> bool:
    """Check if a port is available for binding.

    Args:
        port: Port number to check

    Returns:
        True if port is available, False if in use
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) != 0


def find_available_port(start: int) -> int:
    """Find the next available port starting from a given port.

    Args:
        start: Starting port number

    Returns:
        First available port >= start
    """
    port = start
    while not check_port_available(port):
        port += 1
        if port > 65535:
            raise RuntimeError(f"No available ports found starting from {start}")
    return port


def generate_password(length: int = 16) -> str:
    """Generate a secure random password.

    Args:
        length: Desired password length

    Returns:
        URL-safe random string of specified length
    """
    return secrets.token_urlsafe(length)[:length]


if __name__ == "__main__":
    print("Setup script placeholder - full implementation in next task")
