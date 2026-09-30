"""Boot environment for the gateway test tier.

R8 S3 (owner ruling 3) made ``GATEWAY_MODEL_SET`` a hard-raise: unset, unknown
and the retired ``full`` all raise inside ``resolve_active_set()``, which
``ai/gateway/main.py`` calls at import time (``ACTIVE_MODELS`` :64). That makes
the variable a *container-start* fact, so this tier cannot import the app it
tests without one — which is why the default belongs in a conftest and not in
the module.

The value mirrors the shipped deployment default rather than inventing a test
value: docker-compose.prod.yml:387 passes ``${GATEWAY_MODEL_SET:-vlm}`` and
.env.example:221 declares ``vlm``, and that pairing is pinned by
``backend/tests/unit/core/test_gateway_model_set_compose.py``. ``setdefault``
keeps an explicit operator/CI value authoritative, and a test that wants to
prove the raise uses ``monkeypatch.delenv`` (``test_residency.
TestResolveActiveSet``) — which still sees the raise it asserts because the
monkeypatch happens after this line.

Without this file the whole tier errors at collection with
``KeyError: "unknown GATEWAY_MODEL_SET: ''"``, and CI would have hit exactly
that: ci.yml does not set the variable for the backend job (grep-verified).
"""

from __future__ import annotations

import os

os.environ.setdefault("GATEWAY_MODEL_SET", "vlm")
