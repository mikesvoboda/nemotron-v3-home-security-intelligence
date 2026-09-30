"""Replaying served models over exported items (synthbench P5a design §3).

`models.py` imports nothing from `backend`, so commands may import it at startup; `replay.py`
imports `backend` and is imported only when a replay runs (spec §7.1 allows it here).
"""
