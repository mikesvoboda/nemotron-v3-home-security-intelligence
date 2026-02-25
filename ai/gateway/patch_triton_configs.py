#!/usr/bin/env python3
"""Patch Triton config.pbtxt instance_group based on models.yml triton_kind settings.

Called by entrypoint.sh before Triton starts.  models.yml is the single source of
truth for whether each Triton model runs on GPU or CPU — change models.yml, not
individual config.pbtxt files.

Behaviour per triton_kind:
  KIND_GPU  — count→1, kind→KIND_GPU, inserts gpus:[index] after kind line, removes
              CPU-threading `parameters {}` blocks.
  KIND_CPU  — kind→KIND_CPU, removes gpus line (count left unchanged).

Writes config.pbtxt only when content actually changes so Triton's inotify
watches are not triggered unnecessarily.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("[patch_triton_configs] PyYAML not available — skipping", file=sys.stderr)
    sys.exit(0)

REPO = Path(os.environ.get("TRITON_MODEL_REPOSITORY", "/models/repository"))
MODELS_YAML = Path(os.environ.get("MODELS_YAML_PATH", "/app/models.yml"))


def set_instance_group(text: str, triton_kind: str, gpu_index: int = 0) -> str:
    """Rewrite kind/count/gpus lines inside the instance_group of a config.pbtxt.

    All other content (comments, dynamic_batching, version_policy, etc.) is
    preserved verbatim so the diff is minimal and auditable.
    """
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    skip_params = False
    params_depth = 0

    for line in lines:
        stripped = line.strip()

        # Remove CPU-only `parameters {}` blocks when promoting to KIND_GPU.
        # These blocks (intra_op_thread_count, execution_mode) are no-ops on GPU
        # and confuse ONNX Runtime's CUDA EP session-options parsing.
        if triton_kind == "KIND_GPU" and stripped == "parameters {":
            skip_params = True
            params_depth = 1
            continue
        if skip_params:
            params_depth += stripped.count("{") - stripped.count("}")
            if params_depth <= 0:
                skip_params = False
            continue

        # Drop any existing `gpus: [...]` line; will be re-added below for KIND_GPU.
        if re.match(r"\s+gpus:\s*\[", line):
            continue

        # Patch `  count: N` — set to 1 for GPU, leave unchanged for CPU.
        m = re.match(r"(\s+count:\s*)(\d+)([ \t]*(?:#[^\n]*)?)", line.rstrip("\n"))
        if m:
            nl = "\n" if line.endswith("\n") else ""
            new_count = "1" if triton_kind == "KIND_GPU" else m.group(2)
            out.append(f"{m.group(1)}{new_count}{m.group(3)}{nl}")
            continue

        # Patch `  kind: KIND_XXX` and inject `gpus:` line right after for GPU.
        # Inline comments (e.g. `# 14MB model runs efficiently on CPU`) are preserved.
        m = re.match(r"(\s+)(kind:\s*KIND_\w+)([ \t]*(?:#[^\n]*)?)", line.rstrip("\n"))
        if m:
            nl = "\n" if line.endswith("\n") else ""
            indent = m.group(1)
            comment = m.group(3)
            out.append(f"{indent}kind: {triton_kind}{comment}{nl}")
            if triton_kind == "KIND_GPU":
                out.append(f"{indent}gpus: [ {gpu_index} ]\n")
            continue

        out.append(line)

    return "".join(out)


def collect_triton_configs(models: list[dict]) -> list[tuple[str, str]]:
    """Yield (triton_name, triton_kind) pairs from models.yml model entries.

    Handles both forms:
      Simple:  triton_name: clip       triton_kind: KIND_GPU
      List:    triton_models: [{triton_name: clip, triton_kind: KIND_GPU}, ...]
    """
    results: list[tuple[str, str]] = []
    for m in models:
        for tm in m.get("triton_models", []):
            if "triton_name" in tm and "triton_kind" in tm:
                results.append((str(tm["triton_name"]), str(tm["triton_kind"])))
        if "triton_name" in m and "triton_kind" in m:
            results.append((str(m["triton_name"]), str(m["triton_kind"])))
    return results


def main() -> None:
    if not MODELS_YAML.exists():
        print(f"[patch_triton_configs] {MODELS_YAML} not found — skipping", file=sys.stderr)
        return

    with MODELS_YAML.open() as f:
        config = yaml.safe_load(f)

    triton_configs = collect_triton_configs(config.get("models", []))
    if not triton_configs:
        print("[patch_triton_configs] No triton_name/triton_kind entries in models.yml")
        return

    patched = 0
    for triton_name, triton_kind in triton_configs:
        cfg_path = REPO / triton_name / "config.pbtxt"
        if not cfg_path.exists():
            print(f"[patch_triton_configs] WARN: {cfg_path} not found — skipping", file=sys.stderr)
            continue

        original = cfg_path.read_text()
        updated = set_instance_group(original, triton_kind)
        if updated != original:
            cfg_path.write_text(updated)
            print(f"[patch_triton_configs]   patched  {triton_name}: → {triton_kind}")
            patched += 1
        else:
            print(f"[patch_triton_configs]   verified {triton_name}: {triton_kind}")

    print(f"[patch_triton_configs] {patched}/{len(triton_configs)} config(s) patched")


if __name__ == "__main__":
    main()
