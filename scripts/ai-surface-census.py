#!/usr/bin/env python3
"""AI-surface reachability + swap-bucket census (plan P WP5.5).

Classifies every module under backend/services/ into exactly ONE bucket,
BEFORE any deletion, so the general reachability rule governs rather than
being retrofitted to the two known-bad records:

  HTTP-AI    talks to an AI server over HTTP — imports a gateway-facing AI
             client (detector/florence/clip/enrichment_client,
             nemotron_analyzer), or BYPASSES one: raw httpx/aiohttp POST to
             an AI-only route (/ocr-with-regions, /completion, /detect, ...)
             or reaching into a private *_url attribute (analyzer._llm_url).
             Bypasses matter most: they are what an extraction most easily
             misses (scene_ocr_service.py:526,634; nemotron_streaming.py:99).
  INPROC-AI  loads a model INTO the backend process (torch/transformers/
             ultralytics/onnx/timm/diffusers/cv2/... imported at any depth —
             a function-level lazy import still loads the lib when called).
             A second seam; an HTTP-level conformance suite leaves it open.
  DOMAIN     business logic — a provider swap cannot reach it.
  DEAD       zero non-test consumers. A services/__init__.py re-export is
             NOT a consumer (WP5.6's ruling: scene_change_service's only
             "importer" is the re-export at backend/services/__init__.py:318;
             the live path is scene_change_detector).

Precedence (exactly one bucket per module):
  DEAD > HTTP-AI > INPROC-AI > DOMAIN.
A dead module with AI evidence is DEAD — deleting it deletes the contract
surface; the contract must not grow for unreachable code.

Consumer graph: textual AST import resolution (absolute + relative imports
resolved against the importing file's package), pooled over every non-test
.py in the tree; tests/ files, test_*.py and conftest.py never count; the
services package __init__.py never counts. Self-import never counts.
Textual resolution over-imports (an over-approximated importer set only
risks calling a DEAD module LIVE — the safe direction for a census that
feeds deletions).

Run: .venv/bin/python scripts/ai-surface-census.py [--root REPO] [--json]
Test: uv run python -m pytest scripts/test_ai_surface_census.py -q
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

HEAVY_LIBS = {
    "torch",
    "torchvision",
    "transformers",
    "ultralytics",
    "onnx",
    "onnxruntime",
    "timm",
    "diffusers",
    "sentence_transformers",
    "cv2",
    "faiss",
}

# Gateway-facing AI client surfaces the conformance contract covers.
# go2rtc/mqtt clients are media/IoT plumbing — deliberately NOT here.
GATEWAY_STEMS = {
    "detector_client",
    "florence_client",
    "clip_client",
    "enrichment_client",
    "nemotron_analyzer",
}

# Routes only AI servers answer. Narrow on purpose: go2rtc also speaks httpx,
# so "makes an HTTP call" alone must never classify.
AI_ROUTE_RE = re.compile(
    r"""/(ocr(?:-with-regions)?|detect(?:ions)?|completions?|chat/completions
        |generate|classify|embeddings?|warmth|analyze|explain|describe|faces?
        |plates?|track|inference|predict)\b""",
    re.X,
)
# `analyzer._llm_url` class: reaching a hidden server url through a private
# attribute is a bypass of exactly the client the contract would cover.
PRIVATE_URL_RE = re.compile(r"\.\b_\w*(?:llm|api|model|server|infer|ocr|gpu|backend)\w*_url\b")

HTTP_LIBS = {"httpx", "aiohttp", "requests", "urllib3"}

# Scratch/vendored trees that must never count as consumers: mutants/ holds
# ~1800 mutated COPIES of backend files (a mutation census, not a consumer),
# docs/ holds sample scripts, .wp25-feed/ holds triage scratch dumps.
EXCLUDE_DIRS = {
    "mutants",
    ".wp25-feed",
    "docs",
    ".venv",
    "node_modules",
    "__pycache__",
    "build",
    "dist",
}

BUCKETS = ("HTTP-AI", "INPROC-AI", "DOMAIN", "DEAD")


def is_test_file(rel_parts: tuple[str, ...]) -> bool:
    *dirs, name = rel_parts
    if "tests" in dirs or "test" in dirs:
        return True
    return name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"


def import_targets(tree: ast.AST, pkg_parts: tuple[str, ...]) -> set[str]:
    """Every dotted name this file imports, relative imports resolved to
    absolute against the file's package."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            level = node.level or 0
            if level:
                base = pkg_parts[: max(0, len(pkg_parts) - (level - 1))]
                mod = f"{'.'.join(base)}{'.' + node.module if node.module else ''}"
                if node.module:
                    out.add(mod)
                for a in node.names:
                    out.add(f"{mod}.{a.name}" if node.module else f"{'.'.join(base)}.{a.name}")
            elif node.module:
                out.add(node.module)
                for a in node.names:
                    out.add(f"{node.module}.{a.name}")
    return out


def imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def consumed_by(targets: set[str], mod_dotted: str) -> bool:
    """Any import target that loads this module: the module itself, or
    something inside it (a.b.mod.thing needs a.b.mod loaded)."""
    pre = mod_dotted + "."
    return any(t == mod_dotted or t.startswith(pre) for t in targets)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    services = root / "backend" / "services"
    if not services.is_dir():
        print(f"no backend/services under {root}", file=sys.stderr)
        return 2

    all_py = [p for p in root.rglob("*.py") if not EXCLUDE_DIRS.intersection(p.parts)]

    trees: dict[Path, ast.AST | None] = {}
    texts: dict[Path, str] = {}
    for p in all_py:
        try:
            txt = p.read_text(encoding="utf8")
        except UnicodeDecodeError, OSError:
            txt = ""
        texts[p] = txt
        try:
            trees[p] = ast.parse(txt)
        except SyntaxError:
            trees[p] = None

    # module inventory: name (relative to services) -> dotted parts
    modules: dict[str, tuple[str, ...]] = {}
    for mpath in sorted(services.rglob("*.py")):
        if mpath.name == "__init__.py" or "__pycache__" in mpath.parts:
            continue
        modules[".".join(mpath.relative_to(services).with_suffix("").parts)] = (
            "backend",
            "services",
            *mpath.relative_to(services).with_suffix("").parts,
        )

    services_init = services / "__init__.py"

    # consumer pool -> per-module importer lists. Matching is a prefix walk,
    # not a per-module scan: an import "a.b.c.d" consumes module "a.b.c"
    # (and nothing deeper that isn't a prefix of it), so every candidate is
    # a dot-prefix of an import target. That is O(#targets * #dots) with a
    # dict probe instead of O(#targets * #modules) string work — the
    # per-module scan took >120s on the real tree (7535 py files).
    dotted_to_name = {".".join(d): name for name, d in modules.items()}
    module_files = {
        services.joinpath(*name.split(".")).with_suffix(".py"): name for name in modules
    }
    importers: dict[str, set[str]] = {name: set() for name in modules}
    for p in all_py:
        tree = trees.get(p)
        if tree is None:
            continue
        rel = p.relative_to(root)
        if is_test_file(rel.parts):
            continue
        if p == services_init:
            continue  # WP5.6 ruling: package re-exports are not consumers
        pkg_parts = p.parent.relative_to(root).parts
        own = module_files.get(p)
        for dotted in import_targets(tree, pkg_parts):
            parts = dotted.split(".")
            for i in range(1, len(parts) + 1):
                cand = ".".join(parts[:i])
                name = dotted_to_name.get(cand)
                if name is None and i == 1 and parts[0] == "services":
                    # sys.path-rooted-from-backend/ imports
                    # (`from services.model_zoo import ...` in
                    # backend/scripts/benchmark_vram.py) — same package,
                    # shorter root. Only this exact alias is resolved; a
                    # blanket stem-match would launder unrelated modules
                    # into "consumed" and hollow out the DEAD bucket.
                    name = dotted_to_name.get("backend." + cand)
                if name is None or name == own:
                    continue  # self-import never counts
                importers[name].add(str(rel))
            # (prefix walk covers `a.b.mod.thing` -> consumes a.b.mod)

    out_modules: dict[str, dict] = {}
    for name, dotted in modules.items():
        mpath = services.joinpath(*dotted[2:]).with_suffix(".py")  # strip backend.services
        text = texts.get(mpath, "")
        tree = trees.get(mpath) or ast.parse("")
        imp = sorted(importers[name])
        roots = imported_roots(tree)
        heavy = sorted(roots & HEAVY_LIBS)
        client_hit = any(
            seg in GATEWAY_STEMS for t in import_targets(tree, ("unused",)) for seg in t.split(".")
        )
        uses_http = bool(roots & HTTP_LIBS)
        route_hits = len(AI_ROUTE_RE.findall(text)) if uses_http else 0
        url_hits = len(PRIVATE_URL_RE.findall(text))
        bypass = route_hits + url_hits

        if len(imp) == 0:
            bucket = "DEAD"
        elif client_hit or bypass:
            bucket = "HTTP-AI"
        elif heavy:
            bucket = "INPROC-AI"
        else:
            bucket = "DOMAIN"

        out_modules[name] = {
            "bucket": bucket,
            "non_test_importers": len(imp),
            "importers": imp,
            "heavy_libs": heavy,
            "client_bypass_sites": bypass,
            "lines": len(text.splitlines()),
        }

    totals = {b: sum(1 for m in out_modules.values() if m["bucket"] == b) for b in BUCKETS}
    totals["dead_lines"] = sum(m["lines"] for m in out_modules.values() if m["bucket"] == "DEAD")
    totals["client_bypass_sites"] = sum(m["client_bypass_sites"] for m in out_modules.values())

    if args.json:
        json.dump({"modules": out_modules, "totals": totals}, sys.stdout, indent=1, sort_keys=True)
        print()
    else:
        for b in BUCKETS:
            names = sorted(n for n, m in out_modules.items() if m["bucket"] == b)
            print(f"{b}: {len(names)}")
            for n in names:
                print(f"    {n}  ({out_modules[n]['non_test_importers']} importers)")
        print(f"totals: {totals}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
