import sys
from unittest.mock import patch
which = sys.argv[1]
try:
    if which == "A":
        with patch("opentelemetry.sdk.resources.Resource", autospec=True), \
             patch("opentelemetry.sdk.trace.TracerProvider", autospec=True): pass
    elif which == "B":
        with patch("opentelemetry.sdk.trace.TracerProvider", autospec=True), \
             patch("opentelemetry.sdk.resources.Resource", autospec=True): pass
    elif which == "C":
        with patch("opentelemetry.sdk.resources.Resource", autospec=True), \
             patch("opentelemetry.sdk.resources.get_aggregated_resources", autospec=True): pass
    elif which == "D":
        with patch("opentelemetry.sdk.resources.get_aggregated_resources", autospec=True), \
             patch("opentelemetry.sdk.resources.Resource", autospec=True): pass
    elif which == "E":
        with patch("opentelemetry.sdk.resources.Resource", autospec=True): pass
    print(which, "OK")
except Exception as e:
    print(which, type(e).__name__, str(e)[:60])
