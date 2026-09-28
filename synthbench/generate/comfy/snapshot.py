"""Capture /object_info filtered to the node types our builders use (for offline validation).

python -m synthbench.generate.comfy.snapshot   # renderer must be up (serve up)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from synthbench.generate.comfy.client import ComfyClient
from synthbench.generate.comfy.graphs import sample_graphs
from synthbench.generate.comfy.serve import ServeConfig

OUT = Path(__file__).resolve().parent / "object_info.v0.37.0.json"


def filtered(object_info: dict[str, Any]) -> dict[str, Any]:
    used = {node["class_type"] for graph in sample_graphs().values() for node in graph.values()}
    kept = {name: object_info[name] for name in sorted(used) if name in object_info}
    if "LoadImage" in kept:  # uploaded file names are only known at run time
        kept["LoadImage"]["input"]["required"]["image"] = ["STRING", {}]
    return kept


def main() -> int:
    client = ComfyClient(ServeConfig.from_env().base_url)
    try:
        OUT.write_text(json.dumps(filtered(client.object_info()), indent=1, sort_keys=True) + "\n")
    finally:
        client.close()
    sys.stdout.write(f"wrote {OUT}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
