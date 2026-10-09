"""F1.3: nginx must explicitly forward the session credential to /api and /ws.

B1.5's gate reads exactly two client credentials on the proxied path: the
``session_id`` cookie and the ``api-key.<key>`` WebSocket subprotocol
(``backend/api/middleware/auth.py`` at origin/main e9ec74ef). The SPA is
same-origin behind nginx (``docker-compose.prod.yml`` documents the relative-URL
topology), so every browser credential reaches the backend only if nginx
proxies it.

Until F1.3 the Cookie header rode through by nginx's *default* behavior
(``proxy_pass_request_headers`` is on and no block hides Cookie) — true, but
unenforced: a future ``proxy_set_header`` rework or a ``proxy_hide_header``
would silently lock every UI session out, and the three existing nginx-config
test files asserted nothing about it. F1.3 makes the invariant explicit in
every rendered ``/api`` and ``/ws`` block and pins it here.

Sibling precedent for testing frontend/ nginx config from this directory:
``test_nginx_rate_limit_config.py``, ``test_nginx_connection_limit_config.py``,
``test_nginx_security_headers.py``.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent


def _location_blocks(text: str) -> list[tuple[str, str]]:
    """Return (location_path, block_body) for every nginx location block.

    Brace-matching scan; handles the entrypoint's heredoc-rendered variants and
    the static nginx.conf alike. Nested braces (none today in these blocks) are
    tracked so a stray one cannot truncate a body.
    """
    blocks: list[tuple[str, str]] = []
    for match in re.finditer(r"location\s+(\^[~~]|~\*|~|=)?\s*(\S+)\s*\{", text):
        path = match.group(2)
        depth = 1
        pos = match.end()
        start = pos
        while pos < len(text) and depth > 0:
            if text[pos] == "{":
                depth += 1
            elif text[pos] == "}":
                depth -= 1
            pos += 1
        blocks.append((path, text[start : pos - 1]))
    return blocks


@pytest.fixture(scope="module")
def entrypoint_text() -> str:
    path = REPO_ROOT / "frontend" / "docker-entrypoint.sh"
    assert path.exists(), f"missing {path}"
    return path.read_text()


@pytest.fixture(scope="module")
def nginx_conf_text() -> str:
    path = REPO_ROOT / "frontend" / "nginx.conf"
    assert path.exists(), f"missing {path}"
    return path.read_text()


def _proxied_credential_blocks(text: str) -> list[tuple[str, str]]:
    """Location blocks that proxy to the backend: paths under /api or /ws."""
    return [
        (path, body)
        for path, body in _location_blocks(text)
        if (path.startswith("/api") or path.startswith("/ws")) and "proxy_pass" in body
    ]


class TestCredentialForwardingApi:
    """Every rendered /api proxy block carries the credential explicitly."""

    def test_entrypoint_api_blocks_set_cookie_header(self, entrypoint_text: str) -> None:
        blocks = [
            (p, b) for p, b in _proxied_credential_blocks(entrypoint_text) if p.startswith("/api")
        ]
        assert blocks, "no /api proxy blocks found in docker-entrypoint.sh"
        missing = [p for p, b in _named(blocks) if "proxy_set_header Cookie" not in b]
        assert not missing, (
            f"/api blocks without an explicit Cookie forward: {missing}. "
            "B1.5's gate reads only the session_id cookie and the API key; "
            "Cookie must be forwarded by directive, not by nginx default."
        )

    def test_ssl_8443_blocks_set_cookie_header(self, entrypoint_text: str) -> None:
        # The SSL server block is the third rendered variant. The whole-file
        # scans above already SEE its blocks (escaped \$ heredoc form), but an
        # existence-only check here would let a rework keep the section and
        # lose the directive, so assert the directive by name: a dropped SSL
        # Cookie line fails HERE, not only in the aggregate scan.
        at = entrypoint_text.find("listen 8443")
        assert at != -1, "SSL (8443) server section missing from docker-entrypoint.sh"
        blocks = _named(_proxied_credential_blocks(entrypoint_text[at:]))
        paths = {path.rsplit(" #", 1)[0] for path, _ in blocks}
        assert {"/api/ai-audit", "/api", "/ws"} <= paths, (
            f"SSL section proxies only {sorted(paths)}"
        )
        missing = [path for path, body in blocks if "proxy_set_header Cookie" not in body]
        assert not missing, f"SSL blocks without an explicit Cookie forward: {missing}"


class TestCredentialForwardingWebSocket:
    """/ws handshake credential paths: Cookie rides the upgrade request too."""

    def test_entrypoint_ws_blocks_set_cookie_header(self, entrypoint_text: str) -> None:
        blocks = [
            (p, b) for p, b in _proxied_credential_blocks(entrypoint_text) if p.startswith("/ws")
        ]
        assert blocks, "no /ws proxy blocks found in docker-entrypoint.sh"
        missing = [p for p, b in _named(blocks) if "proxy_set_header Cookie" not in b]
        assert not missing, f"/ws blocks without an explicit Cookie forward: {missing}"

    def test_ws_blocks_keep_the_upgrade_pair(self, entrypoint_text: str) -> None:
        # The F1.3 edit must not disturb the smuggling-hardened upgrade wiring.
        for path, body in _proxied_credential_blocks(entrypoint_text):
            if path.startswith("/ws"):
                assert "$websocket_upgrade" in body, f"{path} lost the validated Upgrade map"
                assert "$connection_upgrade" in body, f"{path} lost the validated Connection map"


def _named(blocks: list[tuple[str, str]]) -> list[tuple[str, str]]:
    # location paths repeat across variants; index them for readable failures.
    return [(f"{path} #{i}", body) for i, (path, body) in enumerate(blocks)]


class TestNoCredentialSuppression:
    """Nothing anywhere hides or drops the credential headers."""

    def test_no_hide_or_disable_directives(
        self, entrypoint_text: str, nginx_conf_text: str
    ) -> None:
        combined = entrypoint_text + nginx_conf_text
        for directive in ("proxy_hide_header Cookie", "proxy_pass_request_headers off"):
            assert directive not in combined, f"{directive} would lock the UI out of B1.5's gate"
