"""[UR-48] The gateway image must be buildable where the O2.4 venue builds it.

Ruling 188 moved O2.4's real-tier gateway image to ``agent-gpu build``. That
builder's Containerfile contract is transcribed in this repo's own
``ai/vlm/Dockerfile`` header (the file that already follows it):

    "A Containerfile may not put flags on RUN (--mount= included) and may not
     use ONBUILD"

Before this pin, the pre-fix gateway Dockerfile carried
``RUN --mount=type=cache,target=/root/.cache/pip`` (blob ``6f7afa5c8``, its line 16),
so at that head the gateway image was **not buildable in the venue at all** — it
was refused before any question of VRAM, free space, or registry auth
(operator record ``6183478980`` §4, which filed this as lane work). The cure
drops the mount; this file pins the contract so the mount cannot silently come
back and re-block the venue. (The cite is to the pre-fix blob on purpose: the fix
shifts line numbers inside that file, so a bare ``Dockerfile:n`` here would point
at the wrong text the moment the file grew.)

Scope is deliberately the gateway file, not every Dockerfile: ``backend``,
``frontend`` and ``docker/base`` also carry ``RUN --mount=`` and are built by
CI's own docker/podman, which *permits* cache mounts. Only ``ai/gateway`` is
built through the flag-forbidding builder, so only it is pinned here. A
corpus-wide "no RUN flag anywhere" test would falsely fail three files that are
correct as they are.

Transparency about coverage: the transcribed contract has three clauses — (1) every
``FROM`` names an explicit registry so builds never pull, (2) no flags on ``RUN``,
(3) no ``ONBUILD``. This file pins (2) and (3). Clause (1) holds at this head
(``FROM nvcr.io/nvidia/tritonserver:...`` is explicit) but is **unpinned**: a future
``FROM tritonserver:...`` would read green here. It stays unpinned pending the digest
follow-up, which is blocked on measurement, not effort — ``nvcr.io/v2/`` returns 401
to anonymous requests, so the digest cannot be recorded from CI.

The absence assertion is paired with a positive witness (a fixture that *does*
carry ``RUN --mount=`` and ``ONBUILD`` must be detected), so an empty parse
cannot masquerade as a pass. The installed package set is pinned by its own
test so a cure that quietly dropped a dependency to dodge a build error is red.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
GATEWAY_DOCKERFILE = REPO_ROOT / "ai" / "gateway" / "Dockerfile"

# The exact set pip installs into the image today. Pinned as a set so the cure
# (dropping the cache mount, adding --no-cache-dir) cannot drop or add one.
INSTALLED_PACKAGES: frozenset[str] = frozenset(
    {
        "packaging",
        "numpy",
        "fastapi",
        "uvicorn[standard]",
        "tritonclient[grpc]",
        "pillow",
        "prometheus-client",
        "httpx",
        "python-multipart",
    }
)

# O3.1: unused export/ML dependencies stripped from the gateway runtime image.
STRIPPED_PACKAGES: frozenset[str] = frozenset(
    {
        "torch",
        "transformers",
        "ultralytics",
        "onnx",
        "onnxscript",
        "onnxruntime",
        "onnxruntime-gpu",
        "open_clip",
        "open_clip_torch",
        "timm",
        "einops",
    }
)


def logical_instructions(text: str) -> list[str]:
    """Dockerfile instructions with line-continuations joined and comments dropped.

    Comments are stripped first: a comment line that happens to mention ``--mount=``
    (as this very file's rationale does after the fix) must NOT read as a live RUN
    flag, and a continuation inside a comment must not glue two real instructions.
    A logical instruction is one physical line plus every line it continues into
    via a trailing backslash.
    """
    out: list[str] = []
    buf = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("#") or not stripped:
            # A comment or blank never participates in a continuation here; the
            # repo's Dockerfiles keep comments on their own lines, so dropping the
            # line whole cannot orphan a continuation from its parent instruction.
            continue
        if stripped.endswith("\\"):
            buf += (" " if buf else "") + stripped[:-1].strip()
            continue
        buf += (" " if buf else "") + stripped
        out.append(buf.strip())
        buf = ""
    if buf:
        out.append(buf.strip())
    return out


def run_instruction_flags(text: str) -> list[str]:
    """Instruction-level flags on RUN lines (a leading ``--...`` before the command).

    ``RUN --mount=... cmd`` is a violation; ``RUN cmd --flag`` is not, because the
    flag belongs to the program, not the instruction. So only ``--...`` tokens that
    appear between ``RUN`` and the first command word count.

    The instruction keyword is matched case-insensitively on purpose: Docker treats
    it that way, and buildkit re-prints a lowercase ``run --mount=`` as ``RUN
    --mount=`` in the step log — i.e. it really does parse the lowercase form and
    the agent-gpu venue really does refuse it. Matching only ``RUN`` would wave a
    ``run --mount=`` through this pin while the build failed, silently re-blocking
    the venue the pin exists to keep open.
    """
    flags: list[str] = []
    for ins in logical_instructions(text):
        parts = ins.split(None, 1)
        if not parts or parts[0].upper() != "RUN":
            continue
        rest = (parts[1] if len(parts) > 1 else "").split()
        for tok in rest:
            if tok.startswith("--"):
                flags.append(tok)
            else:
                break
    return flags


def onbuild_instructions(text: str) -> list[str]:
    # Case-insensitive for the same reason as run_instruction_flags: the venue
    # refuses ``onbuild RUN`` too. The returned string is the instruction verbatim
    # so the witness can pin the exact spelling it fed in.
    return [
        ins
        for ins in logical_instructions(text)
        if (ins.split(None, 1) or [""])[0].upper() == "ONBUILD"
    ]


def pip_installed_packages(text: str) -> set[str]:
    """Every package name passed to any ``pip install`` in the file.

    Flag tokens (``--no-cache-dir``, ``--force-reinstall``, ``-r``, ``--index-url``)
    are skipped so a cure that adds ``--no-cache-dir`` does not change the set.
    """
    pkgs: set[str] = set()
    for ins in logical_instructions(text):
        if "pip install" not in ins:
            continue
        for chunk in re.split(r"&&", ins):
            part = chunk.strip()
            if "pip install" not in part:
                continue
            after = part.split("pip install", 1)[1].strip()
            for tok in after.split():
                if tok.startswith("-"):
                    continue
                pkgs.add(tok.strip("\"'"))
    return pkgs


# Flags that change WHICH wheels pip resolves, not just where it looks for them
# in the layer. `--no-cache-dir` / `--force-reinstall` are deliberately absent: the
# fix itself carries both, and neither alters the resulting dependency graph.
RESOLUTION_ALTERING_FLAGS: frozenset[str] = frozenset(
    {
        "--no-deps",
        "--no-index",
        "--index-url",
        "--extra-index-url",
        "--find-links",
        "--no-build-isolation",
        "--only-binary",
        "--no-binary",
        "--require-hashes",
    }
)


def pip_resolution_flags(text: str) -> list[str]:
    """Resolution-altering pip flags on any ``pip install`` in the file.

    The package-set pin above compares names only, so ``pip install --no-deps``
    (which drops the whole transitive closure while keeping every named package)
    leaves that set untouched. This walks the same instructions and surfaces the
    flags the name comparison is blind to.
    """
    found: list[str] = []
    for ins in logical_instructions(text):
        if "pip install" not in ins:
            continue
        for chunk in re.split(r"&&", ins):
            part = chunk.strip()
            if "pip install" not in part:
                continue
            after = part.split("pip install", 1)[1].strip()
            for tok in after.split():
                name = tok.split("=", 1)[0]
                if name in RESOLUTION_ALTERING_FLAGS:
                    found.append(tok)
    return found


class TestGatewayDockerfileAgentGpuBuildable:
    def test_no_run_instruction_carries_a_flag(self) -> None:
        # RED at origin/main: line 16 is `RUN --mount=type=cache,...`.
        text = GATEWAY_DOCKERFILE.read_text()
        assert run_instruction_flags(text) == [], (
            "ai/gateway/Dockerfile has RUN flags; agent-gpu build refuses them "
            "(ruling 188 venue), so O2.4 cannot build the gateway image."
        )

    def test_no_onbuild_instruction(self) -> None:
        text = GATEWAY_DOCKERFILE.read_text()
        assert onbuild_instructions(text) == []

    def test_the_parser_detects_the_very_patterns_it_asserts_absent(self) -> None:
        # Positive witness: an empty result must be attributable to a clean file,
        # not to a parser that finds nothing. This fixture DOES carry both defects.
        violating = (
            "FROM x\n"
            "RUN --mount=type=cache,target=/root/.cache/pip pip install a\n"
            "ONBUILD RUN echo hi\n"
        )
        assert run_instruction_flags(violating) == ["--mount=type=cache,target=/root/.cache/pip"]
        assert onbuild_instructions(violating) == ["ONBUILD RUN echo hi"]

    def test_the_parser_detects_the_lowercase_instruction_forms(self) -> None:
        # The Dockerfile grammar is case-insensitive and buildkit parses (and
        # re-prints upper-cased) a lowercase `run --mount=`, so the venue refuses
        # it. Without this arm the parser could certify a grammar narrower than the
        # builder's: the uppercase witness passes and a lowercase defect survives.
        lowercase = (
            "from x\n"
            "run --mount=type=cache,target=/root/.cache/pip pip install a\n"
            "onbuild RUN echo hi\n"
        )
        assert run_instruction_flags(lowercase) == ["--mount=type=cache,target=/root/.cache/pip"]
        assert onbuild_instructions(lowercase) == ["onbuild RUN echo hi"]

    def test_a_pip_resolution_flag_is_pinned_absent(self) -> None:
        # The package-set pin compares NAMES, so a resolution-altering flag
        # (`--no-deps`, `--no-index`, an alternate `--index-url`) would change what
        # the image installs while leaving the name set identical. This pin closes
        # that gap directly rather than leaning on the set comparison.
        text = GATEWAY_DOCKERFILE.read_text()
        assert pip_resolution_flags(text) == [], (
            "ai/gateway/Dockerfile carries a pip resolution-altering flag; the "
            "18-name package-set pin cannot see it, so it would silently change "
            "what the gateway image installs."
        )

    def test_the_resolution_flag_parser_detects_what_it_asserts_absent(self) -> None:
        # Positive witness for the pin above: a fixture WITH --no-deps must be
        # detected, so the clean-file pass isn't just an empty parse.
        assert pip_resolution_flags("RUN pip install --no-deps foo\n") == ["--no-deps"]
        assert pip_resolution_flags("RUN pip install --no-cache-dir --force-reinstall foo\n") == []

    def test_a_comment_mentioning_a_mount_is_not_read_as_a_live_flag(self) -> None:
        # Guards the comment-stripping in the parser: the fix's own rationale text
        # names `--mount=`, and that must never make the real file read dirty.
        commented = "# the old RUN --mount=type=cache is gone\nRUN pip install a\n"
        assert run_instruction_flags(commented) == []

    def test_a_program_flag_after_the_command_is_not_an_instruction_flag(self) -> None:
        # The distinction the whole test rests on: RUN cmd --flag is legal.
        legal = "RUN pip install --no-cache-dir --force-reinstall pkg\n"
        assert run_instruction_flags(legal) == []

    def test_the_installed_package_set_is_pinned(self) -> None:
        # A cure that drops a dependency to dodge a build error must be red here.
        text = GATEWAY_DOCKERFILE.read_text()
        assert pip_installed_packages(text) == set(INSTALLED_PACKAGES)
        assert not (pip_installed_packages(text) & STRIPPED_PACKAGES)

    def test_gateway_runtime_imports_no_stripped_package(self) -> None:
        # O3.1: confirm by AST import trace that no gateway runtime module
        # imports any of the stripped export/ML packages.
        import ast

        gw_dir = REPO_ROOT / "ai" / "gateway"
        runtime_files = [
            p
            for p in sorted(gw_dir.rglob("*.py"))
            if "tests" not in p.parts and "export" not in p.parts
        ]
        assert runtime_files
        imported_roots: set[str] = set()
        for path in runtime_files:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_roots.add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                    imported_roots.add(node.module.split(".")[0])
        assert not (imported_roots & STRIPPED_PACKAGES), (
            f"gateway runtime imports stripped packages: {sorted(imported_roots & STRIPPED_PACKAGES)}"
        )


class TestTheCorpusScanIsHonestAboutScope:
    @pytest.mark.parametrize(
        "relpath",
        ["ai/vlm/Dockerfile", "docker/fake-ai/Dockerfile"],
    )
    def test_the_control_dockerfiles_already_comply(self, relpath: str) -> None:
        # Compliance controls, NOT a claim about who builds them: ai/vlm is the
        # agent-gpu-built file that already follows the contract (proof it is
        # satisfiable and that this test's grammar is not unique to a hand-made
        # case); docker/fake-ai is built by plain compose, so it is here only as a
        # second independent no-flag/no-ONBUILD sample.
        text = (REPO_ROOT / relpath).read_text()
        assert run_instruction_flags(text) == []
        assert onbuild_instructions(text) == []
