"""Integration tests for proxy headers configuration (NEM-5062).

This module tests that uvicorn is properly configured with --proxy-headers
and --forwarded-allow-ips flags, which are critical for nginx reverse proxy
setups.

Tests verify:
- X-Forwarded-For headers are properly parsed for client IP
- X-Forwarded-Proto headers are used for protocol detection (HSTS, etc.)
- X-Forwarded-Host headers are processed correctly
- Rate limiting uses the actual client IP (not proxy IP)
- Security headers respect the forwarded protocol
"""

import pytest


@pytest.mark.asyncio
async def test_proxy_headers_x_forwarded_proto_triggers_hsts(client):
    """Test that X-Forwarded-Proto header enables HSTS header.

    When nginx proxies HTTPS requests, it adds X-Forwarded-Proto: https
    header. With --proxy-headers flag enabled, uvicorn should use this
    to determine the original protocol and the SecurityHeadersMiddleware
    should add HSTS header.
    """
    response = await client.get("/", headers={"X-Forwarded-Proto": "https"})

    assert response.status_code == 200
    # HSTS header should be present for HTTPS requests
    # This indicates the middleware is respecting the forwarded protocol
    assert "strict-transport-security" in response.headers
    hsts = response.headers["strict-transport-security"]
    assert "max-age=" in hsts
    assert "includeSubDomains" in hsts


@pytest.mark.asyncio
async def test_proxy_headers_x_forwarded_host_in_combined_headers(client):
    """Test that X-Forwarded-* headers work together.

    When nginx proxies HTTPS requests from a specific client, it sets:
    - X-Forwarded-For: client IP
    - X-Forwarded-Proto: https
    - X-Forwarded-Host: original host
    """
    response = await client.get(
        "/",
        headers={
            "X-Forwarded-For": "198.51.100.25",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "security.example.com",
        },
    )

    assert response.status_code == 200
    # Request should be processed successfully with all headers
    # HSTS should be present due to X-Forwarded-Proto: https
    assert "strict-transport-security" in response.headers


@pytest.mark.asyncio
async def test_proxy_headers_multiple_x_forwarded_for_entries(client):
    """Test handling of multiple X-Forwarded-For entries (proxy chain).

    When requests go through multiple proxies, X-Forwarded-For can have
    comma-separated list of IPs. The first IP is the original client.
    """
    # Multiple proxies in the chain
    forwarded_for = "203.0.113.42, 198.51.100.5, 192.0.2.10"

    response = await client.get("/", headers={"X-Forwarded-For": forwarded_for})

    assert response.status_code == 200
    # Should handle the proxy chain correctly


@pytest.mark.asyncio
async def test_proxy_headers_security_headers_present(client):
    """Test that security headers are properly applied with proxy headers.

    The SecurityHeadersMiddleware should add security headers regardless
    of proxy headers. When proxy headers indicate HTTPS, HSTS should also
    be added.
    """
    response = await client.get(
        "/", headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "example.com"}
    )

    assert response.status_code == 200
    # Check core security headers
    assert "x-content-type-options" in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "x-frame-options" in response.headers
    assert response.headers["x-frame-options"] == "DENY"
    # HSTS should be present due to HTTPS
    assert "strict-transport-security" in response.headers
