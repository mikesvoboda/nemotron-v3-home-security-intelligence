---
name: proxy-failfast-masks-network-tests
description: "Sandbox HTTP proxy answers fake-IP connects instantly, so non-hermetic tests look fast locally but stall ~130s on CI runners; connect-guard harness + NO_PROXY red-proves hermeticity"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 79a1f342-0c47-43c3-bc69-b513f06e89fc
  modified: 2026-09-17T09:07:40.746Z
---

A unit test that builds a real client against a fake IP (e.g. onvif-zeep's
ONVIFCamera → SOAP POST to 192.168.1.100) runs ~3s in this sandbox but
~135s on GitHub runners. The sandbox proxy ACCEPTS and fails-fast any
outbound connect; CI runners black-hole unroutable IPs until the client's
own timeout (zeep ~130s). Duration gates (WP0.5's TPA) are the detector —
the failure surface is CI-only and looks like "slow tests," not "network."

**Why:** local green + local fast proves nothing about hermeticity; the
masking is environmental, and a production fix (correct constructor args)
can unmask a latent socket with no test change at all.

**How to apply:** red-prove with a connect-guard harness —
`socket.socket.connect` patched to raise a **BaseException subclass**
(the production code's `except Exception` swallows AssertionError and the
test still passes — the trap I hit first), run with
`NO_PROXY=<fake IPs>` so requests bypasses the proxy (CI topology),
`-o addopts=` to drop xdist (workers may not inherit the patch).
Pre-fix 3 failed at `update_xaddrs` → `socket.connect(('192.168.1.100',
80))`; post-fix whole file green in 3.2s. Related:
[[pytest-quiet-traps]], [[monitor-lines-are-not-truth]].
