"""R8 follow-up: ai/download_models.sh must provision the VLM architecture, not the legacy zoo.

The script was the last artifact still provisioning the retired model zoo: a
14.7GB Nemotron GGUF, Florence (x2), SigLIP, vehicle/pet/depth/pose/clothing/
age/gender/weather/violence/smoke-fire/stgcn/yolo-world/fashion-clip — every
one of those serving paths died with R8 S1-S3 (github/main). The rule the
script and setup_lib share (``download_method != "skip" AND (hf_repo OR
download_method)``) now selects exactly 5 of the 10 live ``models.yml`` rows;
this tier pins that the script's DOWNLOADS (not its prose) match the rule, and
that the one gap the retirement opened — the ``${AI_MODELS_PATH}/vlm`` mount
for the ai-vlm GGUF pair — is at least documented by the script that owns
provisioning.

Verdict evidence for every retired name lives in the ledger (items 51-55) and
was re-measured per model: e.g. violence had NO reader that populates
``enrichment_data["violence_detection"]`` (detections.py:937 only consumes,
defaulting false) and no ``models.yml`` row; smoke-fire's loader module no
longer exists on disk (alert_engine's ``_check_smoke_fire`` is documented mock).

D5 ruling: model identity is config — this script (and these tests) must never
name a VLM identity; the vlm guidance is path-only.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "ai" / "download_models.sh"
MODELS_YML = REPO_ROOT / "models.yml"

# Names of retired model artifacts. The guard forbids them on CODE lines
# (uncommented) — deletion notes in comments are allowed and encouraged, so a
# future reader learns what left and why.
RETIRED_MODEL_NAMES = (
    "nemotron",
    "florence",
    "siglip",
    "vehicle-segment",
    "pet-classifier",
    "depth-anything",
    "vit-age",
    "vit-gender",
    "weather-classification",
    "violence-detection",
    "smoke-fire",
    "vitpose",
    "segformer",
    "vehicle-damage",
    "stgcn",
    "yolo-world",
    "fashion-clip",
    "yolov8n-pose",
)

# What the shared models.yml rule selects today (re-derived from models.yml in
# test_rule_selection, never hardcoded from the script's own claims).
EXPECTED_HF_ROWS = {
    "threat-detection-yolov8n",
    "yolo11-face",
    "yolo11-license-plate",
}
EXPECTED_CUSTOM_FETCHES = {"yolo26", "osnet-ain-x1-0"}


def script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def code_lines() -> list[str]:
    """Non-comment, non-blank lines of the script."""
    lines = []
    for raw in script_text().splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
    return lines


def hf_downloads_rows() -> dict[str, str]:
    """name -> repo for every row in the HF_DOWNLOADS array."""
    match = re.search(r"^HF_DOWNLOADS=\(\n(.*?)^\)", script_text(), re.M | re.S)
    assert match, "HF_DOWNLOADS array not found — the script's shape changed"
    rows = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.strip('"').split("|")
        assert len(fields) == 4, f"malformed HF_DOWNLOADS row: {line!r}"
        rows[fields[0]] = fields[1]
    return rows


def map_keys(map_name: str) -> set[str]:
    """Keys declared in a `declare -A NAME=( ... )` associative array."""
    match = re.search(rf"^declare -A {map_name}=\(\n(.*?)^\)", script_text(), re.M | re.S)
    assert match, f"declare -A {map_name} not found"
    return set(re.findall(r'\["([^"]+)"\]=', match.group(1)))


class TestScriptSyntax:
    def test_bash_syntax_check_passes(self) -> None:
        result = subprocess.run(  # noqa: S603 - fixed argv, our own script, never a shell string
            ["bash", "-n", str(SCRIPT)],  # noqa: S607 - bash from PATH, repo convention
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"bash -n failed: {result.stderr}"


class TestRetiredProvisioningGone:
    """Every retired model must be absent from every executable line.

    Checks the four provisioning surfaces plus the tree echo — the places a
    name can still cause a download or a promise: HF_DOWNLOADS rows, custom
    section variable blocks (``*_DIR=``/``wget``/``download_file`` targets),
    MODEL_CHECKSUMS keys, HF_REPO_COMMITS keys.
    """

    @pytest.mark.parametrize("name", RETIRED_MODEL_NAMES)
    def test_retired_name_absent_from_code_lines(self, name: str) -> None:
        hits = [line for line in code_lines() if name in line.lower()]
        assert not hits, f"retired model {name!r} still provisioned/echoed: {hits[:3]}"

    def test_nemotron_download_block_removed(self) -> None:
        text = script_text()
        assert "NEMOTRON_DIR=" not in text
        assert "Nemotron-3-Nano" not in "".join(code_lines())

    def test_model_checksums_are_yolo26_only(self) -> None:
        keys = map_keys("MODEL_CHECKSUMS")
        assert keys == {"yolo26n.pt", "yolo26s.pt", "yolo26m.pt"}, keys

    def test_hf_repo_commits_cover_only_kept_rows(self) -> None:
        kept_repos = set(hf_downloads_rows().values())
        keys = map_keys("HF_REPO_COMMITS")
        assert keys <= kept_repos, f"commit pins for repos no longer fetched: {keys - kept_repos}"


class TestKeepSetMatchesRule:
    def test_hf_downloads_are_exactly_the_rule_selected_hf_rows(self) -> None:
        assert set(hf_downloads_rows()) == EXPECTED_HF_ROWS

    def test_custom_fetches_are_yolo26_and_osnet_only(self) -> None:
        text = script_text()
        assert "YOLO26_DIR=" in text, "yolo26 .pt fetch must stay (gateway export needs the .pt)"
        assert "OSNET_DIR=" in text, (
            "osnet fetch must stay (re-ID runtime reads the short-name file)"
        )
        for retired in ("POSE_DIR=", "STGCN_DIR=", "YOLO_WORLD_DIR=", "MARQO_SNAPSHOTS"):
            assert retired not in text, f"retired custom-fetch section still present: {retired}"

    def test_step_arithmetic_cannot_lie(self) -> None:
        """The old script's self-check said 25 sections and quietly shipped 24.

        TOTAL must be exactly 2 custom sections + len(HF_DOWNLOADS), and the
        literal STEP increments must be 2 outside the loop + 1 inside it —
        anything else means a section was added/removed without fixing the math.
        """
        text = script_text()
        total_match = re.search(r"^TOTAL=\$\(\(([^)]*)\)\)", text, re.M)
        assert total_match, "TOTAL formula not found"
        assert re.sub(r"\s+", " ", total_match.group(1)).strip() == "2 + ${#HF_DOWNLOADS[@]}"
        assert text.count("STEP=$(( STEP + 1 ))") == 3, "2 custom sections + 1 in the HF loop"

    def test_header_counts_match_models_yml_measured(self) -> None:
        """The header must state the numbers a reader can re-measure today.

        Derives the selection count and MB sum from models.yml (the same rule
        setup_lib uses) and requires the header to carry those exact figures —
        drift between script prose and catalogue fails here, not in the field.
        """
        rows = re.split(r"\n  - name: ", MODELS_YML.read_text(encoding="utf-8"))[1:]

        def field(body: str, name: str) -> str:
            m = re.search(rf"^    {name}:\s*(\S+)", body, re.M)
            return m.group(1) if m else ""

        selected = []
        for body in rows:
            dm = field(body, "download_method")
            hf = field(body, "hf_repo")
            if dm != "skip" and ((hf and hf != "''") or dm):
                size = field(body, "size_mb")
                selected.append(int(size) if size.isdigit() else 0)
        assert len(selected) == 5, (
            "models.yml rule-selection changed — update this tier AND the script"
        )
        total_mb = sum(selected)
        assert total_mb == 763
        # Header = everything before the first executable line (`set -e`).
        text = script_text()
        match = re.search(r"^set -e$", text, re.M)
        assert match, "no `set -e` line found — script shape changed"
        header = text[: match.start()]
        assert str(len(selected)) in header and str(total_mb) in header, (
            f"header does not carry the measurable figures ({len(selected)} rows, {total_mb} MB)"
        )


class TestVlmGuidance:
    """The retirement left ${AI_MODELS_PATH}/vlm unfetched by anything; the
    provisioning script must at least tell the operator where the GGUF pair goes."""

    def test_vlm_mount_directory_documented(self) -> None:
        text = script_text()
        assert "/vlm" in text, "the ai-vlm mount dir (${AI_MODELS_PATH}/vlm) must be documented"
        assert "VLM_MODEL_PATH" in text and "VLM_MMPROJ_PATH" in text, (
            "guidance must point at the two env vars that consume the pair"
        )

    def test_no_vlm_identity_named(self) -> None:
        """D5: model identity is config. Path-only guidance, ever.

        Scoped to executable lines (echo text counts — that is what the
        operator reads as a promise). Comments may name RETIRED models as
        deletion notes; that is history, not a provisioning contract.
        """
        text = "\n".join(code_lines()).lower()
        for identity in ("qwen", "nemotron", "llama-3", "llama3", "mistral", "gemma"):
            assert identity not in text, (
                f"script names a model identity ({identity!r}) — D5 violation"
            )

    def test_gguf_pair_lands_under_ai_models_path_vlm(self) -> None:
        # The guidance is executable-truthful: echo lines naming the mount path,
        # not a fetch (the pair is operator-provisioned; compose mounts :ro).
        vlm_lines = [line for line in code_lines() if "/vlm" in line]
        assert vlm_lines, "no executable line references the vlm mount"
        assert any("echo" in line for line in vlm_lines), (
            "vlm guidance must be an operator-visible echo"
        )


class TestTreeEchoHonest:
    def test_final_tree_lists_only_provisioned_dirs(self) -> None:
        text = script_text()
        tail = text[text.index("Download Complete") :]
        for name in EXPECTED_HF_ROWS | EXPECTED_CUSTOM_FETCHES:
            assert name in tail, f"tree echo no longer lists provisioned dir {name}"
        retired_in_echo = [name for name in RETIRED_MODEL_NAMES if name in tail.lower()]
        assert not retired_in_echo, f"tree echo promises retired dirs: {retired_in_echo}"
