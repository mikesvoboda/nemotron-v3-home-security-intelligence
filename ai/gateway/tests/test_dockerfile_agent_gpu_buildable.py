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
        "torch",
        "transformers",
        "ultralytics",
        "onnx",
        "onnxscript",
        "onnxruntime-gpu",
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
    """
    flags: list[str] = []
    for ins in logical_instructions(text):
        m = re.match(r"^RUN\b(.*)$", ins)
        if not m:
            continue
        rest = m.group(1).strip().split()
        for tok in rest:
            if tok.startswith("--"):
                flags.append(tok)
            else:
                break
    return flags


def onbuild_instructions(text: str) -> list[str]:
    return [ins for ins in logical_instructions(text) if ins.startswith("ONBUILD")]


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


class TestTheCorpusScanIsHonestAboutScope:
    @pytest.mark.parametrize(
        "relpath",
        ["ai/vlm/Dockerfile", "docker/fake-ai/Dockerfile"],
    )
    def test_the_files_built_by_agent_gpu_already_comply(self, relpath: str) -> None:
        # ai/vlm is built by agent-gpu and already complies — proof the contract is
        # satisfiable and this test's grammar is not unique to a hand-crafted case.
        text = (REPO_ROOT / relpath).read_text()
        assert run_instruction_flags(text) == []
        assert onbuild_instructions(text) == []
