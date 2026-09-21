#!/usr/bin/env python3
"""WP9.1: static cross-provider parity checker (AST-only; never imports the AI tier).

Plan: docs/superpowers/plans/2026-09-19-swap-readiness-72h.md §WP9.1. Thesis:
every Tier-A defect in the plan would have been caught automatically by this
script — and it is how provider #4 is prevented from drifting silently.

WHAT IT READS — ast.parse ONLY. Nothing is imported: native servers pull torch
(forbidden under .venv), gateway adapters pull triton plumbing, and even the
registry is parsed as literals rather than imported.

  backend/ai_contract/operations.py     the WP7.3 availability matrix — the
                                        DECLARATION (gateway /
                                        enrichment_light_adapter /
                                        per_model_server / fake slots)
  ai/gateway/adapters/*.py              gateway provider surface: routes,
                                        pydantic request/response schemas,
                                        field validators, model_config
                                        aliases, handler field reads
  ai/gateway/main.py                    include_router mount prefixes
  ai/*/model.py                         per-model-server native surface
                                        (ai/nemotron ships model_hf.py — out of
                                        the model.py glob by design)
  the six backend caller modules: detector_client.py, clip_client.py,
  florence_client.py, enrichment_client.py, nemotron_analyzer.py,
  api/routes/model_management.py — which URLs they build, from which base
  (gateway branch / settings / hardcoded host), with which JSON payload keys
  docker-compose.prod.yml                  the DEPLOYED topology: which service
                                        hostnames exist and which AI URL
                                        settings the deployment rewrites to
                                        gateway-prefixed URLs (compose's
                                        backend env ENRICHMENT_URL=http://
                                        ai-gateway:8090/enrichment — the
                                        rewrite that makes D1/D2 live). Read as
                                        data; absent compose (fixture trees)
                                        means "no rewrites, all hosts exist".

DETECTION RULES. Each fires only on a disagreement the matrix does NOT declare
(matrix-declared availability splits — e.g. yolo26_segment gateway:True /
per_model_server:False = D4 — are reported under "declared" and stay green):

  SHAPE-<op>-<key>          same op served by gateway and native; a shared
                            request key's value type at the gateway can REJECT
                            what the native provider accepts — heavy adapter's
                            bbox: dict[str,float] vs native list[float] while
                            the client sends a list                         D1
  CLAIM-AVAILABILITY-<op>   a surface SERVES a route the matrix says it must
                            not. ABSENCE is never a violation — absence is
                            exactly what a False slot declares.
  CLAIM-PATH-<op>           a backend caller builds a URL that is not the op's
                            registered path — POST /models/{name}/unload vs the
                            registry's POST /models/unload?model_name=         D3
  CLAIM-GW404-<op>          an op declared gateway:False has a caller whose
                            base, AS DEPLOYED (client use_ai_gateway branch, a
                            compose rewrite of the settings URL to a
                            gateway-prefixed URL, or a backend module's
                            hardcoded host that no compose service provides),
                            resolves to a surface where nothing registered
                            serves the op                                      D2
  TYPE-UNUSED-<op>-<key>    gateway widens a field to a primitive relative to
                            the native Enum/model type AND its handler never
                            reads the field — a flag the deployed provider
                            silently ignores                                  D5
  GUARD-<op>-<key>          native enforces a field_validator on a LIST-typed
                            (batch-size/DoS-shaped) key that the gateway schema
                            lacks — the guard vanishes on the deployed surface D6
  KEY-<op>-<key>            a payload key a mapped client method sends is not
                            accepted by a DEPLOYED provider schema serving the
                            op (a provider renamed/dropped a key); or gateway
                            vs native response key sets differ. model_config
                            aliases (image_base64 <-> image) resolve;
                            extra="ignore" schemas accept anything declared.

Known Tier-A list (WP8.4 dossier /tmp/wp25/wp84-draft/tier-a.md — ground
truth: if this checker finds FEWER, it is wrong, not the tree):
  D1 heavy-gateway bbox shape 422 (client list vs gateway dict vs native list)
  D2 four ops gateway:False yet callers hit gateway-prefixed/undeployed URLs
     (model_status, model_preload, model_unload, object_distance)
  D3 /models/{name}/unload vs registered POST /models/unload?model_name=
  D4 /segment gateway:True per_model_server:False — DECLARED, must stay green
  D5 camera_type widened to str, never read by gateway classify
  D6 MAX_BATCH_TEXTS_SIZE field_validator native-only, absent at the gateway

Exit codes (WP1.3 ratchet family; same shape as scripts/ratchet-check.py):
  0  parity — no divergences, or (with --expect) detected set == golden set
  1  undeclared divergence (or, with --expect, the golden list drifted: a lost
     golden id means a fix landed without --update; a new id means drift)
  2  checker error (registry missing/unparseable, unexpected exception)

Usage:
    .venv/bin/python scripts/check-ai-provider-parity.py                 # summary
    .venv/bin/python scripts/check-ai-provider-parity.py --json          # machine report
    .venv/bin/python scripts/check-ai-provider-parity.py --expect FILE   # golden gate (CI)
    .venv/bin/python scripts/check-ai-provider-parity.py --update        # rewrite golden list
    .venv/bin/python scripts/check-ai-provider-parity.py --root DIR      # fixture tree (tests)

CI wiring (LANDED, collection-sanity job) following WP1.3's ratchet shape,
mirroring the "Suppression ratchet (counts may only fall)" step in ci.yml:

    # WP9.1: cross-provider AI parity. The golden list pins the adjudicated
    # Tier-A defect set (D1-D6); the gate FAILS on any divergence not in the
    # list — provider #4 cannot drift silently, and fixing a defect means
    # removing its id from .github/ai-parity-baseline.json in the same commit.
    - name: AI provider parity (golden divergence list)
      run: >-
        uv run python scripts/check-ai-provider-parity.py
        --expect .github/ai-parity-baseline.json

and appending `scripts/test_check_ai_provider_parity.py` to the "Run the
anti-rot gates' own tests" pytest list in the same job.

Tests: uv run pytest scripts/test_check_ai_provider_parity.py -q
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT_DEFAULT = Path(__file__).resolve().parent.parent
GOLDEN_DEFAULT_NAME = ".github/ai-parity-baseline.json"
OPERATIONS_REL = "backend/ai_contract/operations.py"
COMPOSE_REL = "docker-compose.prod.yml"
ADAPTER_PREFIXES_FALLBACK = {
    "yolo26": "/yolo26",
    "clip": "/clip",
    "florence": "/florence",
    "enrichment": "/enrichment",
    "enrichment_light": "/enrich-lt",
}
NATIVE_FAMILY_PREFIX = {
    "yolo26": "/yolo26",
    "clip": "/clip",
    "florence": "/florence",
    "enrichment": "/enrichment",
    "enrichment-light": "/enrich-lt",
    "nemotron": "",
}
MOUNT_PREFIXES = {p for p in NATIVE_FAMILY_PREFIX.values() if p}
# settings attribute -> compose/env var that can rewrite it to a
# gateway-prefixed URL in the deployed topology (compose backend env;
# .env.example mirrors it)
SETTING_ENV = {
    "yolo26_url": "YOLO26_URL",
    "clip_url": "CLIP_URL",
    "florence_url": "FLORENCE_URL",
    "enrichment_url": "ENRICHMENT_URL",
    "enrichment_light_url": "ENRICHMENT_LIGHT_URL",
}
INFRA_ROUTES = {"/health", "/metrics", "/readiness", "/models/registry"}
PRIMITIVES = {"str", "int", "float", "bool", "bytes"}
CLIENT_MODULE_RELS = (
    "backend/services/detector_client.py",
    "backend/services/clip_client.py",
    "backend/services/florence_client.py",
    "backend/services/enrichment_client.py",
    "backend/services/nemotron_analyzer.py",
    "backend/api/routes/model_management.py",
)


class CheckerError(Exception):
    pass


# --------------------------------------------------------------------------
# AST primitives
# --------------------------------------------------------------------------


def parse_file(root: Path, rel: str) -> ast.Module | None:
    try:
        src = (root / rel).read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return ast.parse(src, filename=rel)
    except SyntaxError as e:
        raise CheckerError(f"cannot parse {rel}: {e}") from e


def ann_members(type_str: str) -> frozenset[str]:
    """Base type names of an annotation: unions flattened, Optional expanded,
    subscripts reduced to their origin name (dict[str, float] -> 'dict')."""
    try:
        node = ast.parse(type_str or "None", mode="eval").body
    except SyntaxError:
        return frozenset({type_str})

    def walk(n: ast.expr, out: set[str]) -> None:
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr):
            walk(n.left, out)
            walk(n.right, out)
            return
        if isinstance(n, ast.Subscript):
            base = n.value.id if isinstance(n.value, ast.Name) else ast.unparse(n.value)
            if base == "Optional":
                walk(n.slice, out)
            else:
                out.add(base)
            return
        if isinstance(n, ast.Constant) and n.value is None:
            out.add("None")
            return
        if isinstance(n, ast.Name):
            out.add(n.id)
            return
        out.add(ast.unparse(n))

    out: set[str] = set()
    walk(node, out)
    return frozenset(out)


@dataclass
class Schema:
    name: str
    module: str
    types: dict[str, str] = field(default_factory=dict)
    list_keys: set[str] = field(default_factory=set)
    validators: set[str] = field(default_factory=set)
    bounded: set[str] = field(default_factory=set)  # Field(max_length=...) — constant cap
    aliases: dict[str, str] = field(default_factory=dict)
    extra_ignores: bool = False

    @property
    def keys(self) -> set[str]:
        return set(self.types)

    def accepts(self, key: str) -> bool:
        return key in self.types or key in self.aliases


def extract_schemas(tree: ast.Module, module: str) -> dict[str, Schema]:
    out: dict[str, Schema] = {}
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        bases = {(b.id if isinstance(b, ast.Name) else getattr(b, "attr", "?")) for b in cls.bases}
        if "BaseModel" not in bases:
            continue
        sch = Schema(name=cls.name, module=module)
        for stmt in cls.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                tstr = ast.unparse(stmt.annotation) if stmt.annotation else ""
                sch.types[stmt.target.id] = tstr
                members = ann_members(tstr)
                if members & {"list", "dict", "set", "tuple", "Sequence", "Mapping"}:
                    sch.list_keys.add(stmt.target.id)
                if (
                    isinstance(stmt.value, ast.Call)
                    and getattr(stmt.value.func, "id", "") == "Field"
                ):
                    for kw in stmt.value.keywords:
                        if kw.arg == "alias" and isinstance(kw.value, ast.Constant):
                            sch.aliases[str(kw.value)] = stmt.target.id
                        if kw.arg in ("max_length", "maxItems", "max_items"):
                            sch.bounded.add(stmt.target.id)
            elif isinstance(stmt, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "model_config" for t in stmt.targets
            ):
                if isinstance(stmt.value, ast.Dict):
                    for k, v in zip(stmt.value.keys, stmt.value.values, strict=True):
                        if (
                            isinstance(k, ast.Constant)
                            and k.value == "extra"
                            and isinstance(v, ast.Constant)
                        ):
                            sch.extra_ignores = v.value == "ignore"
            elif isinstance(stmt, ast.FunctionDef):
                for dec in stmt.decorator_list:
                    dn = dec.func if isinstance(dec, ast.Call) else dec
                    dname = dn.attr if isinstance(dn, ast.Attribute) else getattr(dn, "id", "")
                    if dname in ("field_validator", "validator") and isinstance(dec, ast.Call):
                        keys = {
                            a.value
                            for a in dec.args
                            if isinstance(a, ast.Constant) and isinstance(a.value, str)
                        }
                        sch.validators |= keys
                        # A validator whose cap is a LITERAL (if len(v) > 30) is
                        # a constant rule both providers could re-implement
                        # statically; the drifted-but-equal case is invisible to
                        # this checker BY DESIGN. A validator reading a module
                        # CONSTANT (MAX_BATCH_TEXTS_SIZE from env) is a
                        # deployment-tunable contract guard that must survive at
                        # the gateway — only that kind is GUARD-worthy.
                        body_consts = {
                            n.id
                            for n in ast.walk(stmt)
                            if isinstance(n, ast.Name)
                            and isinstance(n.ctx, ast.Load)
                            and n.id.isupper()
                            and len(n.id) > 1
                        }
                        if not body_consts:
                            sch.bounded |= keys  # literal-only cap = constant rule
        out[cls.name] = sch
    return out


ROUTE_METHODS = {"get": "GET", "post": "POST", "put": "PUT", "delete": "DELETE", "patch": "PATCH"}


@dataclass
class Route:
    module: str = ""
    kind: str = ""
    raw_path: str = ""
    method: str = ""
    param_type: str | None = None
    response_type: str | None = None
    handler: ast.FunctionDef | ast.AsyncFunctionDef | None = None


def extract_routes(tree: ast.Module) -> list[Route]:
    routes: list[Route] = []
    for fn in (n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
        for dec in fn.decorator_list:
            if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                continue
            holder = dec.func.value
            if not (isinstance(holder, ast.Name) and holder.id in ("router", "app")):
                continue
            method = ROUTE_METHODS.get(dec.func.attr)
            if not method or not dec.args or not isinstance(dec.args[0], ast.Constant):
                continue
            raw_path = dec.args[0].value
            if not isinstance(raw_path, str):  # mypy narrowing: route paths are str constants
                continue
            param = None
            if (
                fn.args.args
                and fn.args.args[-1].arg != "self"
                and isinstance(fn.args.args[-1].annotation, ast.Name)
            ):
                param = fn.args.args[-1].annotation.id
            resp = None
            for kw in dec.keywords:
                if kw.arg == "response_model" and isinstance(kw.value, ast.Name):
                    resp = kw.value.id
            routes.append(
                Route(
                    raw_path=raw_path,
                    method=method,
                    param_type=param,
                    response_type=resp,
                    handler=fn,
                )
            )
    return routes


def handler_reads(handler: ast.AST | None, key: str) -> bool:
    if handler is None:
        return False
    return any(
        isinstance(n, ast.Attribute)
        and isinstance(n.value, ast.Name)
        and n.value.id.endswith("request")
        and n.attr == key
        for n in ast.walk(handler)
    )


# --------------------------------------------------------------------------
# Registry (the DECLARATION)
# --------------------------------------------------------------------------


@dataclass
class Op:
    id: str
    method: str
    path: str
    availability: dict[str, bool]
    client_methods: list[str]


def load_registry(root: Path) -> dict[str, Op]:
    tree = parse_file(root, OPERATIONS_REL)
    if tree is None:
        raise CheckerError(f"registry not found: {root / OPERATIONS_REL}")
    ops: dict[str, Op] = {}
    for node in ast.walk(tree):
        targets = (
            [node.target]
            if isinstance(node, ast.AnnAssign)
            else (node.targets if isinstance(node, ast.Assign) else [])
        )
        if not any(getattr(t, "id", None) == "OPERATIONS" for t in targets):
            continue
        d = getattr(node, "value", None)  # mypy: Assign/AnnAssign carry .value, AST does not
        if not isinstance(d, ast.Dict):
            raise CheckerError("OPERATIONS is not a dict literal")
        for k, v in zip(d.keys, d.values, strict=True):
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                continue
            if not isinstance(v, ast.Call):
                continue
            kw = {f.arg: f.value for f in v.keywords}
            try:
                ops[k.value] = Op(
                    id=k.value,
                    method=ast.literal_eval(kw["method"]),
                    path=ast.literal_eval(kw["path"]),
                    availability=ast.literal_eval(kw["availability"]),
                    client_methods=ast.literal_eval(kw["client_methods"]),
                )
            except (ValueError, TypeError, KeyError, SyntaxError) as e:
                raise CheckerError(f"op {k.value!r} unreadable: {e}") from e
        break
    if not ops:
        raise CheckerError("registry parsed 0 operations")
    return ops


def op_family(o: Op) -> str:
    for fam, p in NATIVE_FAMILY_PREFIX.items():
        if p and o.path.startswith(p + "/"):
            return fam
    return ""


# --------------------------------------------------------------------------
# Deployed topology
# --------------------------------------------------------------------------


@dataclass
class Deploy:
    services: set[str] = field(default_factory=set)
    setting_prefix: dict[str, str] = field(default_factory=dict)
    compose_found: bool = False


def load_deploy(root: Path) -> Deploy:
    d = Deploy()
    p = root / COMPOSE_REL
    if not p.exists():
        return d
    try:
        import yaml  # optional: fixture trees carry no compose
    except ImportError:
        return d
    try:
        data = yaml.safe_load(p.read_text()) or {}
    except Exception:  # an unreadable compose must not crash the checker
        return d
    d.compose_found = True
    services = data.get("services") or {}
    d.services = set(services)
    env = services.get("backend", {}).get("environment") or {}
    if isinstance(env, list):
        env = {
            s.split("=", 1)[0]: s.split("=", 1)[1] for s in env if isinstance(s, str) and "=" in s
        }
    for attr, var in SETTING_ENV.items():
        val = env.get(var)
        if not isinstance(val, str) or "://" not in val:
            continue
        rest = val.split("://", 1)[1]
        path = ("/" + rest.split("/", 1)[1]) if "/" in rest else ""
        if path.rstrip("/") in MOUNT_PREFIXES:
            d.setting_prefix[attr] = path.rstrip("/")
    return d


# --------------------------------------------------------------------------
# Provider surfaces
# --------------------------------------------------------------------------


@dataclass
class Served:
    op: Op
    kind: str  # gateway | light | native
    location: str
    req: Schema | None
    resp: Schema | None
    handler: ast.FunctionDef | ast.AsyncFunctionDef | None = None


def gateway_prefixes(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    tree = parse_file(root, "ai/gateway/main.py")
    if tree is None:
        return dict(ADAPTER_PREFIXES_FALLBACK)
    for n in ast.walk(tree):
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "include_router"
            and n.args
            and isinstance(n.args[0], ast.Name)
        ):
            stem = n.args[0].id.removesuffix("_router")
            for kw in n.keywords:
                if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                    out[stem] = str(kw.value.value)
    return out or dict(ADAPTER_PREFIXES_FALLBACK)


def match_op(ops: dict[str, Op], full: str, raw: str, family: str | None) -> Op | None:
    for op in ops.values():
        if op.path == full:
            return op
    for op in ops.values():
        if op.path == raw:
            return op
    if family:
        pfx = NATIVE_FAMILY_PREFIX.get(family, "")
        if pfx:
            for op in ops.values():
                if (
                    op.path.startswith(pfx + "/")
                    and op.path.rsplit("/", 1)[-1] == raw.rsplit("/", 1)[-1]
                ):
                    return op
    return None


def collect_gateway(root: Path, ops: dict[str, Op]) -> tuple[list[Served], list[str]]:
    served: list[Served] = []
    unclaimed: list[str] = []
    try:
        files = sorted(
            p for p in (root / "ai/gateway/adapters").glob("*.py") if p.name != "__init__.py"
        )
    except OSError:
        files = []
    if not files:
        raise CheckerError(f"no gateway adapters under {root / 'ai/gateway/adapters'}")
    prefixes = gateway_prefixes(root)
    for f in files:
        rel = str(f.relative_to(root))
        tree = parse_file(root, rel)
        if tree is None:
            continue
        schemas = extract_schemas(tree, f.stem)
        kind = "light" if f.stem == "enrichment_light" else "gateway"
        prefix = prefixes.get(f.stem, ADAPTER_PREFIXES_FALLBACK.get(f.stem, ""))
        for r in extract_routes(tree):
            r.module, r.kind = f.stem, kind
            full = prefix + r.raw_path
            op = match_op(ops, full, r.raw_path, None)
            if op is None:
                if r.raw_path not in INFRA_ROUTES:
                    unclaimed.append(f"{rel} [{r.method} {full}]")
                continue
            # built after the None-narrow (Served.op is non-Optional; the
            # old pre-continue construction fed mypy an Op | None)
            served.append(
                Served(
                    op,
                    kind,
                    f"{rel} [{r.method} {full}]",
                    schemas.get(r.param_type or ""),
                    schemas.get(r.response_type or ""),
                    r.handler,
                )
            )
    return served, unclaimed


def collect_native(root: Path, ops: dict[str, Op]) -> tuple[list[Served], list[str], set[str]]:
    """(matched, unclaimed route locations, native BaseModel class names)."""
    served: list[Served] = []
    unclaimed: list[str] = []
    model_classes: set[str] = set()
    try:
        families = sorted(d.name for d in (root / "ai").iterdir() if (d / "model.py").exists())
    except OSError:
        raise CheckerError(f"no ai/ tree under {root}") from None
    for fam in families:
        rel = f"ai/{fam}/model.py"
        tree = parse_file(root, rel)
        if tree is None:
            continue
        schemas = extract_schemas(tree, fam)
        model_classes |= set(schemas)
        pfx = NATIVE_FAMILY_PREFIX.get(fam, "")
        for r in extract_routes(tree):
            r.module, r.kind = fam, "native"
            full = pfx + r.raw_path
            op = match_op(ops, full, r.raw_path, fam)
            if op is None:
                if r.raw_path not in INFRA_ROUTES:
                    unclaimed.append(f"{rel} [{r.method} {full}]")
                continue
            served.append(
                Served(
                    op,
                    "native",
                    f"{rel} [{r.method} {full}]",
                    schemas.get(r.param_type or ""),
                    schemas.get(r.response_type or ""),
                    r.handler,
                )
            )
    return served, unclaimed, model_classes


# --------------------------------------------------------------------------
# Backend caller surface
# --------------------------------------------------------------------------


@dataclass
class Base:
    """One possible base URL a caller's request hangs off, AS DEPLOYED."""

    kind: str  # gateway | settings | hardcoded
    label: str
    family: str = ""
    null: bool = False  # resolves to a surface where nothing serves bare registry ops


@dataclass
class Caller:
    module: str
    cls: str
    method: str
    lineno: int
    suffix: str
    http: str
    payload_keys: set[str]
    multipart: bool
    bases: list[Base] = field(default_factory=list)


def _url_parts(node: ast.expr) -> tuple[str, dict[str, ast.expr]] | None:
    """url expression -> (template, {placeholder: expr}). A leading base is
    kept as a placeholder; constants become literals."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, {}
    if not isinstance(node, ast.JoinedStr):
        return None
    parts: list[str] = []
    vars_: dict[str, ast.expr] = {}
    for v in node.values:
        if isinstance(v, ast.Constant):
            parts.append(str(v.value))
        elif isinstance(v, ast.FormattedValue):
            e = v.value
            name = ""
            while isinstance(e, ast.Attribute):
                name = e.attr
                e = e.value
            if isinstance(e, ast.Name) and not name:
                name = e.id
            key = name or "expr"
            parts.append("{" + key + "}")
            vars_[key] = v.value
    return "".join(parts), vars_


def _unwrap(value: ast.expr) -> ast.expr:
    while (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Attribute)
        and value.func.attr in ("rstrip", "strip")
    ):
        value = value.func.value
    return value


def module_bases(tree: ast.Module, deploy: Deploy) -> dict[str, list[Base]]:
    """base attribute/constant name -> deployed Base list.

    * gateway branch: `self.<attr> = f"{gw}/<mount-prefix>"` (evidence-based —
      the constant tail IS a gateway mount prefix, so the indirect
      `_use_gw = ...; if _use_gw:` form is caught as well as the direct test)
    * settings branch: settings.<attr> / getattr(settings, "<attr>", ...) whose
      env var compose rewrote to a gateway-prefixed URL -> that base is a
      gateway-prefixed base IN PRODUCTION (the D2 mechanism)
    * module constants http://host:port whose host is no compose service ->
      null everywhere (model_management.py's hardcoded ai-* hosts)
    """
    out: dict[str, list[Base]] = {}

    def compose_base(setting: str) -> Base | None:
        if setting in deploy.setting_prefix:
            pfx = deploy.setting_prefix[setting]
            fam = next((f for f, p in NATIVE_FAMILY_PREFIX.items() if p == pfx), "")
            return Base(
                "settings", f"settings:{setting} -> {pfx} (compose rewrite)", fam, null=True
            )
        return None

    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        init = next(
            (
                f
                for f in cls.body
                if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and f.name == "__init__"
            ),
            None,
        )
        if init is None:
            continue
        for n in ast.walk(init):
            stmts = [n] if isinstance(n, (ast.Assign, ast.AnnAssign)) else []
            for s in stmts:
                targets = s.targets if isinstance(s, ast.Assign) else [s.target]
                for t in targets:
                    if not (
                        isinstance(t, ast.Attribute)
                        and isinstance(t.value, ast.Name)
                        and t.value.id == "self"
                    ):
                        continue
                    if s.value is None:
                        continue
                    v = _unwrap(s.value)
                    if isinstance(v, ast.JoinedStr):
                        tail = ""  # trailing literal segment of the f-string base
                        for x in v.values:
                            if isinstance(x, ast.Constant):
                                tail = str(x.value)
                        if tail in MOUNT_PREFIXES:
                            fam = next(
                                (f for f, p in NATIVE_FAMILY_PREFIX.items() if p == tail), ""
                            )
                            out.setdefault(t.attr, []).append(
                                Base("gateway", f"use_ai_gateway -> {tail}", fam, null=True)
                            )
                    elif (
                        isinstance(v, ast.Call)
                        and getattr(v.func, "id", "") == "getattr"
                        and len(v.args) >= 2
                        and isinstance(v.args[1], ast.Constant)
                    ):
                        b = compose_base(str(v.args[1].value))
                        if b:
                            out.setdefault(t.attr, []).append(b)
                    elif isinstance(v, ast.Attribute) and v.attr in SETTING_ENV:
                        b = compose_base(v.attr)
                        if b:
                            out.setdefault(t.attr, []).append(b)
    consts = {
        t.id: n.value.value
        for n in ast.walk(tree)
        if isinstance(n, (ast.Assign, ast.AnnAssign))
        for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
        if isinstance(t, ast.Name)
        and isinstance(n.value, ast.Constant)
        and isinstance(n.value.value, str)
        and "://" in n.value.value
    }
    for name, url in consts.items():
        host = url.split("://", 1)[1].split("/", 1)[0].split(":", 1)[0]
        exists = host in deploy.services if deploy.compose_found else True
        fam = (
            "enrichment-light"
            if "light" in host
            else ("enrichment" if host.startswith("ai-enrichment") else "")
        )
        out.setdefault(name, []).append(Base("hardcoded", url, fam, null=not exists))
    # module-level routing helpers (get_service_for_model) alias their constants
    for fn in (
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")
    ):
        returned = {
            (e.id if isinstance(e, ast.Name) else getattr(e, "attr", ""))
            for n in ast.walk(fn)
            if isinstance(n, ast.Return) and n.value is not None
            for e in (n.value.elts if isinstance(n.value, ast.Tuple) else [n.value])
        }
        merged = [b for c in returned if c in consts for b in out.get(c, [])]
        if merged:
            out.setdefault(fn.name, []).extend(merged)
    return out


def _local_bases(fn: ast.AST, name: str, mbases: dict[str, list[Base]]) -> list[Base]:
    """`x = self._get_service_for_model("depth")` / `x =
    settings.get_enrichment_url_for_model(m)`: the client's own contract is
    that its service_url is one of its service bases — union them."""
    for n in ast.walk(fn):
        if not isinstance(n, ast.Assign):
            continue
        names: list[str] = []
        for t in n.targets:
            if isinstance(t, ast.Name):
                names.append(t.id)
            elif isinstance(t, ast.Tuple):
                names += [e.id for e in t.elts if isinstance(e, ast.Name)]
        if name not in names:
            continue
        call_name = ""
        if isinstance(n.value, ast.Call):
            call_name = (
                n.value.func.attr
                if isinstance(n.value.func, ast.Attribute)
                else getattr(n.value.func, "id", "")
            )
        if (
            "service_for_model" in call_name
            or "url_for_model" in call_name
            or ("url" in call_name and call_name.startswith("get"))
        ):
            return [b for bases in mbases.values() for b in bases]
    return []


def _endpoint_table(fn: ast.AST) -> dict[str, str]:
    counts: dict[str, int] = {}
    vals: dict[str, str] = {}
    for n in ast.walk(fn):
        if (
            isinstance(n, ast.Assign)
            and len(n.targets) == 1
            and isinstance(n.targets[0], ast.Name)
            and isinstance(n.value, ast.Constant)
            and isinstance(n.value.value, str)
        ):
            k = n.targets[0].id
            counts[k] = counts.get(k, 0) + 1
            vals[k] = n.value.value
    return {k: v for k, v in vals.items() if counts.get(k) == 1}


def _payload_of(fn: ast.AST, call: ast.Call) -> tuple[set[str], bool]:
    keys: set[str] = set()
    multipart = False
    for kw in call.keywords:
        if kw.arg == "files":
            multipart = True
        if kw.arg != "json":
            continue
        v = kw.value
        if isinstance(v, ast.Dict):
            keys |= {
                k.value for k in v.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)
            }
        elif isinstance(v, ast.Name):
            for m in ast.walk(fn):
                if isinstance(m, ast.Assign):
                    for t in m.targets:
                        if (
                            isinstance(t, ast.Name)
                            and t.id == v.id
                            and isinstance(m.value, ast.Dict)
                        ):
                            keys |= {
                                k.value
                                for k in m.value.keys
                                if isinstance(k, ast.Constant) and isinstance(k.value, str)
                            }
                        if (
                            isinstance(t, ast.Subscript)
                            and isinstance(t.value, ast.Name)
                            and t.value.id == v.id
                            and isinstance(t.slice, ast.Constant)
                            and isinstance(t.slice.value, str)
                        ):
                            keys.add(t.slice.value)
                elif (
                    isinstance(m, ast.AnnAssign)
                    and isinstance(m.target, ast.Name)
                    and m.target.id == v.id
                    and isinstance(m.value, ast.Dict)
                ):
                    keys |= {
                        k.value
                        for k in m.value.keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)
                    }
                elif (
                    isinstance(m, ast.Call)
                    and isinstance(m.func, ast.Attribute)
                    and m.func.attr == "update"
                    and isinstance(m.func.value, ast.Name)
                    and m.func.value.id == v.id
                    and m.args
                    and isinstance(m.args[0], ast.Dict)
                ):
                    keys |= {
                        k.value
                        for k in m.args[0].keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)
                    }
    return keys, multipart


def collect_callers(root: Path, deploy: Deploy) -> tuple[list[Caller], list[str]]:
    callers: list[Caller] = []
    unanchored: list[str] = []
    for rel in CLIENT_MODULE_RELS:
        tree = parse_file(root, rel)
        if tree is None:
            continue
        mbases = module_bases(tree, deploy)
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        # scan every function EXACTLY once (class methods via their class,
        # everything else via the module) — ast.walk on the module would also
        # descend into classes and double-count every client method
        module_fns = [
            n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        in_class = set()
        for c in classes:
            for sub in c.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    in_class.add(id(sub))
        scopes: list[tuple[str, list]] = [("", [n for n in module_fns if id(n) not in in_class])]
        scopes += [
            (c.name, [f for f in c.body if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))])
            for c in classes
        ]
        for cls_name, fns in scopes:
            # helpers that RECEIVE the http client as a parameter
            # (_fetch_service_status(client, url)) build their URL from a
            # callsite constant; the callsite scan below resolves their bases.
            # They are scanned exactly once here (single-scan scheme).
            for fn in fns:
                if fn.name == "__init__":
                    continue
                for n in ast.walk(fn):
                    if not (
                        isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Attribute)
                        and n.func.attr in ("get", "post", "put", "delete")
                        and (
                            (
                                isinstance(n.func.value, ast.Attribute)
                                and "http_client" in n.func.value.attr
                            )
                            or (
                                isinstance(n.func.value, ast.Name)
                                and (
                                    "http_client" in n.func.value.id or n.func.value.id == "client"
                                )
                            )
                        )
                    ):
                        continue
                    if not n.args:
                        continue
                    parts = _url_parts(n.args[0])
                    if parts is None:
                        continue
                    template, vars_ = parts
                    base_name = ""
                    url_node = n.args[0]
                    if isinstance(url_node, ast.JoinedStr):
                        for v in url_node.values:
                            if isinstance(v, ast.FormattedValue):
                                e = v.value
                                attr = ""
                                while isinstance(e, ast.Attribute):
                                    attr = e.attr
                                    e = e.value
                                nm = attr or (e.id if isinstance(e, ast.Name) else "")
                                if nm and "url" in nm.lower():
                                    base_name = nm
                                    break
                    suffix = template
                    if base_name:
                        suffix = suffix.replace("{" + base_name + "}", "", 1)
                    ep = _endpoint_table(fn)
                    for var, expr in vars_.items():
                        if var == base_name:
                            continue
                        if var in ep:
                            suffix = suffix.replace("{" + var + "}", ep[var])
                        elif isinstance(expr, ast.Name) and (
                            expr.id.startswith("ENRICHMENT") or expr.id.endswith("URL")
                        ):
                            # a SECOND constant base used mid-url: url space to
                            # its right is the bare registry space
                            suffix = suffix.split("{" + var + "}")[-1]
                            base_name = base_name or expr.id
                        # else: keep the {var} placeholder — a path parameter
                        # like /models/{model_name}/unload can never match a
                        # registered path, and that IS the D3 evidence.
                    if not suffix.startswith("/"):
                        suffix = "/" + suffix
                    bases = list(mbases.get(base_name, []))
                    if not bases and base_name and base_name not in mbases:
                        bases = _local_bases(fn, base_name, mbases)
                    if not bases and base_name:
                        # helper called with a constant base (_fetch_service_status(http, ENRICHMENT_URL))
                        for cf in (
                            m
                            for m in ast.walk(tree)
                            if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                        ):
                            for call in (
                                c
                                for c in ast.walk(cf)
                                if isinstance(c, ast.Call)
                                and isinstance(c.func, ast.Name)
                                and c.func.id == (fn.name or "")
                            ):
                                for a in call.args:
                                    if isinstance(a, ast.Name):
                                        bases += mbases.get(a.id, [])
                    payload, multipart = _payload_of(fn, n)
                    callers.append(
                        Caller(
                            rel,
                            cls_name,
                            fn.name,
                            fn.lineno,
                            suffix,
                            n.func.attr.upper(),
                            payload,
                            multipart,
                            bases,
                        )
                    )
    return callers, unanchored


# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    id: str
    kind: str
    op: str | None
    detail: str

    def to_json(self) -> dict:
        return {"id": self.id, "kind": self.kind, "op": self.op, "detail": self.detail}


SCHEMAS_DIR_REL = "backend/ai_contract/schemas"


def schema_artifact_ops(root: Path) -> set[str]:
    """Op ids carried by the generated schema artifacts, via the FILESYSTEM.

    WP4.2's second, independent read for the registry count: operations.py is
    an AST literal the checker parses (load_registry); the schemas/ directory
    is generator output counted by name (each op contributes
    `<op>.response.json`, some a `.request.json` too). A legitimate contract
    change regenerates both together, so the pair agrees without any hand
    pin; a checker parse that goes blind to ops (registry renamed, literal
    restructured, entry silently skipped by the AST walk) desynchronizes the
    two counts and the derived assertion in test_check_ai_provider_parity.py
    fails LOUD — which is the guard the retired `== 38` pin used to fake.
    """
    d = root / SCHEMAS_DIR_REL
    if not d.is_dir():
        return set()
    names = set()
    for p in d.glob("*.json"):
        stem = p.stem
        for suffix in (".response", ".request"):
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
                break
        names.add(stem)
    return names


def analyze(root: Path) -> dict:
    ops = load_registry(root)
    deploy = load_deploy(root)
    gw_served, gw_unclaimed = collect_gateway(root, ops)
    nat_served, nat_unclaimed, nat_model_classes = collect_native(root, ops)

    findings: dict[str, Finding] = {}
    declared: list[dict] = []

    def add(kind: str, op_id: str | None, key: str, detail: str) -> None:
        suffix = f"-{op_id}-{key}" if (op_id and key) else (f"-{op_id}" if op_id else key)
        f = Finding(f"AI-PARITY-{kind}{suffix}", kind, op_id, detail)
        findings.setdefault(f.id, f)

    # ---- availability claims from PRESENCE
    for s in gw_served:
        slot = "enrichment_light_adapter" if s.kind == "light" else "gateway"
        if not s.op.availability.get(slot, False):
            add(
                "CLAIM-AVAILABILITY",
                s.op.id,
                "",
                f"{s.kind} surface serves {s.location} but matrix says {slot}:False",
            )
    for s in nat_served:
        if not s.op.availability.get("per_model_server", False):
            add(
                "CLAIM-AVAILABILITY",
                s.op.id,
                "",
                f"native server serves {s.location} but matrix says per_model_server:False",
            )

    # ---- declared availability disagreements (informational, green) — D4 lives here
    for op in ops.values():
        g, p = op.availability.get("gateway", False), op.availability.get("per_model_server", False)
        if g != p:
            declared.append(
                {
                    "op": op.id,
                    "reason": f"matrix declares gateway:{int(g)} per_model_server:{int(p)}",
                    "served_gateway": any(s.op.id == op.id for s in gw_served),
                    "served_native": any(s.op.id == op.id for s in nat_served),
                }
            )

    # ---- provider-vs-provider (gateway/light vs native): shape/unused/guard/response-keys
    by_op: dict[str, dict[str, list[Served]]] = {}
    for s in gw_served + nat_served:
        by_op.setdefault(s.op.id, {}).setdefault(s.kind, []).append(s)
    for op_id, kinds in sorted(by_op.items()):
        non_native = [s for k in ("gateway", "light") for s in kinds.get(k, [])]
        natives = kinds.get("native", [])
        for gw in non_native:
            for nat in natives:
                if gw.req is None or nat.req is None:
                    continue
                for key in sorted(gw.req.keys & nat.req.keys):
                    gm = set(ann_members(gw.req.types.get(key, "")))
                    nm = set(ann_members(nat.req.types.get(key, "")))
                    if gm == nm:
                        continue
                    if "dict" in gm and nm & nat_model_classes:
                        continue  # dict payload validates as the native model (BoundingBox)
                    if gm & PRIMITIVES and not nm & (PRIMITIVES | {"None"}):
                        # gateway widened an Enum/model-typed field to a primitive
                        if handler_reads(gw.handler, key) or key in gw.req.validators:
                            continue  # declared: the gateway honours it in its own way
                        add(
                            "TYPE-UNUSED",
                            op_id,
                            key,
                            f"{op_id}: gateway {gw.location} widens {key}: {nat.req.types[key]} -> {gw.req.types[key]} and "
                            f"the gateway handler never reads request.{key} — the deployed provider accepts values whose "
                            f"semantics it silently ignores (native validates/enumerates {key})",
                        )
                        continue
                    if key in gw.req.validators or gw.req.extra_ignores:
                        continue
                    if not nm <= gm:
                        add(
                            "SHAPE",
                            op_id,
                            key,
                            f"{op_id}: request key {key!r} is {gw.req.types[key]} at {gw.location} but {nat.req.types[key]} at "
                            f"{nat.location} — the two providers accept different value types for payloads both are "
                            f"supposed to serve (clients sending the native shape get 422 at the gateway)",
                        )
                for key in sorted(nat.req.validators - gw.req.validators):
                    if key not in nat.req.list_keys or key in nat.req.bounded:
                        continue  # scalar content-validation is re-implemented in gateway
                    # handlers, and literal-capped validators are constant rules both
                    # providers could re-implement statically; an env/constant-capped
                    # LIST field is a deployment-tunable DoS guard that must survive at
                    # the gateway (D6: MAX_BATCH_TEXTS_SIZE)
                    add(
                        "GUARD",
                        op_id,
                        key,
                        f"{op_id}: native {nat.location} enforces field_validator({key!r}) capped by a module "
                        f"constant on a list-typed field (deployment-tunable batch/DoS guard); gateway "
                        f"{gw.location} schema has no validator for it — the guard exists only on the "
                        f"(in prod: undeployed) native provider",
                    )
                if gw.resp is not None and nat.resp is not None and gw.resp.keys != nat.resp.keys:
                    add(
                        "KEY",
                        op_id,
                        "response",
                        f"{op_id}: response key sets differ — gateway-only {sorted(gw.resp.keys - nat.resp.keys)} / "
                        f"native-only {sorted(nat.resp.keys - gw.resp.keys)} ({gw.location} vs {nat.location})",
                    )

    # ---- deployed providers per op (compose decides whether native is deployed)
    def deployed(s: Served) -> bool:
        if s.kind != "native":
            return True
        if not deploy.compose_found:
            return True  # fixture trees: all surfaces deployed
        fam_service = {
            "yolo26": "ai-yolo26",
            "clip": "ai-clip",
            "florence": "ai-florence",
            "enrichment": "ai-enrichment",
            "enrichment-light": "ai-enrichment-light",
        }.get(op_family(s.op), "")
        return bool(fam_service) and fam_service in deploy.services

    # ---- client payload keys vs DEPLOYED provider schemas (KEY)
    callers, caller_unanchored = collect_callers(root, deploy)
    callers_by_method: dict[str, list[Caller]] = {}
    for c in callers:
        callers_by_method.setdefault(c.method, []).append(c)
    for op in ops.values():
        svs = [s for s in gw_served + nat_served if s.op.id == op.id and deployed(s)]
        if not svs:
            continue
        for cm in op.client_methods:
            for c in callers_by_method.get(cm.split(".")[-1], []):
                if not c.payload_keys or c.multipart:
                    continue
                for s in svs:
                    if s.req is None:
                        continue
                    missing = {k for k in c.payload_keys if not s.req.accepts(k)}
                    if missing and not s.req.extra_ignores:
                        add(
                            "KEY",
                            op.id,
                            ",".join(sorted(missing)),
                            f"{op.id}: {c.module} {c.cls + '.' if c.cls else ''}{c.method} sends {sorted(missing)} that "
                            f"{s.location} schema does not define (a provider renamed/dropped the key)",
                        )

    # ---- caller URL claims (D2 / D3)
    d2: dict[str, list[str]] = {}
    d3: dict[str, list[str]] = {}
    for c in callers:
        if (
            c.suffix.split("*")[0].rstrip("/") in INFRA_ROUTES
            or c.suffix.rstrip("/") in INFRA_ROUTES
        ):
            continue  # /health probes are infrastructure, not contract ops
        seg_suffix = c.suffix
        if "*" in seg_suffix:
            seg_suffix = seg_suffix.split("*")[0] if seg_suffix.split("*")[0] else seg_suffix
        plain_segs = {p for p in seg_suffix.split("/") if p and "{" not in p and p != "*"}
        for b in c.bases:
            pfx = NATIVE_FAMILY_PREFIX.get(b.family)
            url = (
                ((pfx or "") + seg_suffix)
                if (b.kind in ("gateway", "settings") and pfx is not None)
                else seg_suffix
            )
            if "*" in url:
                continue
            cop = match_op(ops, url, seg_suffix, b.family or None)
            ev = f"{c.module}:{c.lineno} {c.cls + '.' if c.cls else ''}{c.method} builds {url}"
            if cop is None:
                # phantom path — anchor ONLY when the op's family matches the
                # caller's base family (or the op is a bare registry path);
                # segment-subset alone would anchor junk
                cands = [
                    o
                    for o in ops.values()
                    if {p for p in o.path.split("/") if p} <= plain_segs
                    and (op_family(o) == "" or op_family(o) == b.family)
                    and o.path != NATIVE_FAMILY_PREFIX.get(b.family, "") + seg_suffix
                ]
                if cands:
                    best = sorted(
                        cands, key=lambda o: len(plain_segs - {p for p in o.path.split("/") if p})
                    )[0]
                    d3.setdefault(best.id, []).append(
                        f"{ev}; registered is {best.method} {best.path} [{b.label}]"
                    )
                    if not best.availability.get("gateway", False):
                        d2.setdefault(best.id, []).append(f"{ev} via {b.label}")
                elif not any(
                    o.path.endswith(seg_suffix) and op_family(o) and op_family(o) != b.family
                    for o in ops.values()
                ):
                    caller_unanchored.append(f"{ev} [{b.label}]")
                continue
            if not cop.availability.get("gateway", False) and b.null:
                d2.setdefault(cop.id, []).append(f"{ev} — {b.label}")
    # events (not ev): the caller loop above binds ev to a str — reusing the
    # name here made mypy see str | list[str] (a rename is behavior-neutral)
    for op_id, events in sorted(d2.items()):
        op = ops[op_id]
        add(
            "CLAIM-GW404",
            op_id,
            "",
            f"op {op_id} declares gateway:False (per_model_server:True) but backend callers build URLs that resolve, "
            f"as deployed, to a surface where nothing serves it: {'; '.join(sorted(set(events)))} — grep over "
            f"ai/gateway/adapters returns 0 route hits for {op.path}",
        )
    for op_id, events in sorted(d3.items()):
        add(
            "CLAIM-PATH",
            op_id,
            "",
            f"op {op_id}: {'; '.join(sorted(set(events)))} — the caller path is not a registered surface (phantom; "
            f"the registry's canonical path is the contract)",
        )

    return {
        "tool": "check-ai-provider-parity",
        "root": str(root),
        "registry_ops": len(ops),
        # WP4.2: cross-source count — see schema_artifact_ops(). Two
        # independent reads of the SAME generator run; the parity suite
        # asserts they agree (no hand-pinned contract size anywhere).
        "schema_artifact_ops": len(schema_artifact_ops(root)),
        "deploy": {
            "compose_found": deploy.compose_found,
            "compose_rewritten_settings": sorted(deploy.setting_prefix.items()),
            "native_services": sorted(s for s in deploy.services if s.startswith("ai-")),
        },
        "surfaces": {
            "gateway_routes_matched": len(gw_served),
            "native_routes_matched": len(nat_served),
            "gateway_routes_unclaimed": sorted(gw_unclaimed),
            "native_routes_unclaimed": sorted(nat_unclaimed),
            "caller_urls": len(callers),
            "caller_urls_unanchored": sorted(caller_unanchored),
        },
        "divergences": [f.to_json() for f in sorted(findings.values(), key=lambda f: f.id)],
        "declared": declared,
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def load_expect(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise CheckerError(f"--expect file unreadable: {e}") from e
    if isinstance(data, dict):
        data = data.get("divergences", [])
    if not isinstance(data, list):
        raise CheckerError("--expect file must be a JSON list of ids or {divergences: [...]}.")
    ids = []
    for item in data:
        if isinstance(item, str):
            ids.append(item)
        elif isinstance(item, dict) and isinstance(item.get("id"), str):
            ids.append(item["id"])
        else:
            raise CheckerError("--expect entries must be id strings or {id: ...} objects")
    return ids


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="WP9.1 static cross-provider AI parity checker")
    ap.add_argument(
        "--root", default=str(REPO_ROOT_DEFAULT), help="tree to check (fixture trees in tests)"
    )
    ap.add_argument("--json", action="store_true", help="machine-readable report on stdout")
    ap.add_argument(
        "--expect", metavar="FILE", help="golden divergence-id list (check-ratchet --expect shape)"
    )
    ap.add_argument(
        "--allow-superset", action="store_true", help="with --expect: new ids warn, do not fail"
    )
    ap.add_argument("--update", action="store_true", help="write the golden file (--expect target)")
    args = ap.parse_args(argv)

    root = Path(args.root)
    try:
        report = analyze(root)
    except CheckerError as e:
        print(f"checker error: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # exit-2 contract: loud, with cause
        import traceback

        traceback.print_exc()
        print(f"checker error: unexpected {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    detected = [d["id"] for d in report["divergences"]]

    if args.update:
        target = Path(args.expect) if args.expect else root / GOLDEN_DEFAULT_NAME
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {"tool": "check-ai-provider-parity", "divergences": report["divergences"]}, indent=2
            )
            + "\n"
        )
        print(f"wrote {len(detected)} golden divergences to {target}")
        return 0

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"registry ops: {report['registry_ops']}  divergences detected: {len(detected)}")
        for d in report["divergences"]:
            print(f"  {d['id']}\n      {d['detail']}")
        for d in report["declared"]:
            print(
                f"  DECLARED {d['op']}: {d['reason']} (served gw={int(d['served_gateway'])} native={int(d['served_native'])})"
            )

    if args.expect:
        expected = load_expect(Path(args.expect))
        missing = sorted(set(expected) - set(detected))
        extra = sorted(set(detected) - set(expected))
        for m in missing:
            print(
                f"GOLDEN-LOST: {m} no longer detected — a fix landed; re-ratchet with --update",
                file=sys.stderr,
            )
        for x in extra:
            print(f"NEW-DIVERGENCE: {x}", file=sys.stderr)
        if missing:
            return 1
        if extra and not args.allow_superset:
            return 1
        return 0
    return 1 if detected else 0


if __name__ == "__main__":
    sys.exit(main())
