import traceback
from unittest.mock import patch
try:
    with patch("opentelemetry.sdk.trace.TracerProvider", autospec=True), \
         patch("opentelemetry.sdk.resources.Resource", autospec=True):
        pass
except Exception:
    traceback.print_exc(limit=6)
