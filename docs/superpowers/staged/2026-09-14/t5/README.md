# T5 execution staging (ruling-gated — do NOT touch pyproject.toml pre-approval)
Order per packet §5:
1. conftest _apply_timeout_marker honors CLI --timeout (pure honesty fix) + retire /tmp/timeout_stamp_plugin.py
2. pyproject swap (signal, func_only=false, timeout=5 per decision rule: runA2 setup p99 1.332s ≪ 2s)
3. smoke: /tmp/t5/test_setup_hang_smoke.py serial with BOTH --rerun=1 and plain — expect clean failure, no node-down
4. gate x2 green zero node-downs
