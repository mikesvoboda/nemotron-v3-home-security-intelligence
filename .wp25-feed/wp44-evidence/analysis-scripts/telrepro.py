from unittest.mock import patch

# A: resources.Resource then trace.TracerProvider (test-file order)
try:
    with patch("opentelemetry.sdk.resources.Resource", autospec=True), \
         patch("opentelemetry.sdk.trace.TracerProvider", autospec=True):
        pass
    print("A OK")
except Exception as e:
    print("A", type(e).__name__, e)

# B: reverse order
try:
    with patch("opentelemetry.sdk.trace.TracerProvider", autospec=True), \
         patch("opentelemetry.sdk.resources.Resource", autospec=True):
        pass
    print("B OK")
except Exception as e:
    print("B", type(e).__name__, e)

# C: resources.Resource then get_aggregated_resources
try:
    with patch("opentelemetry.sdk.resources.Resource", autospec=True), \
         patch("opentelemetry.sdk.resources.get_aggregated_resources", autospec=True):
        pass
    print("C OK")
except Exception as e:
    print("C", type(e).__name__, e)

# D: get_aggregated_resources then Resource
try:
    with patch("opentelemetry.sdk.resources.get_aggregated_resources", autospec=True), \
         patch("opentelemetry.sdk.resources.Resource", autospec=True):
        pass
    print("D OK")
except Exception as e:
    print("D", type(e).__name__, e)
