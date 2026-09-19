"""The WP8.2 deterministic FakeProvider.

FastAPI app + seeded generators implementing all 38 registry operations,
served over httpx.ASGITransport: the reference implementation of the
declared interface and the fixture source for downstream service tests.
Byte-deterministic (sha256-seeded, one sort_keys serializer), no weights,
no GPU, no network, and no ai.* imports (package rule).
"""

from backend.ai_contract.fake.app import (
    PROFILE_HEADER,
    create_fake_app,
    fake_provider_ops,
)
from backend.ai_contract.fake.generators import (
    GATEWAY_CLASSES,
    SECURITY_CLASSES,
    create_response_bytes,
    generate,
    generate_from_snapshot,
    snapshot_for,
)

__all__ = [
    "GATEWAY_CLASSES",
    "PROFILE_HEADER",
    "SECURITY_CLASSES",
    "create_fake_app",
    "create_response_bytes",
    "fake_provider_ops",
    "generate",
    "generate_from_snapshot",
    "snapshot_for",
]
