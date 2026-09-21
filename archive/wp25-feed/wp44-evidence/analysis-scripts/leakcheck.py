from unittest.mock import patch, MagicMock
from opentelemetry.sdk.trace import TracerProvider
try:
    MagicMock(spec=TracerProvider)
    print("fresh spec OK")
except Exception as e:
    print("fresh spec:", type(e).__name__, str(e)[:70])
with patch("opentelemetry.sdk.resources.Resource", autospec=True):
    pass
try:
    MagicMock(spec=TracerProvider)
    print("after Resource-patch spec OK")
except Exception as e:
    print("after Resource-patch spec:", type(e).__name__, str(e)[:70])
with patch("opentelemetry.trace", autospec=True):
    pass
try:
    MagicMock(spec=TracerProvider)
    print("after trace-module-patch spec OK")
except Exception as e:
    print("after trace-module-patch spec:", type(e).__name__, str(e)[:70])
