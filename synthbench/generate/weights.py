"""Pinned, sha256-verified model weights for the ComfyUI renderer (spec §3.1).

A manifest (JSON) names every file a workflow needs: model, ComfyUI folder
category, Hugging Face repo, pinned revision, path, size and LFS sha256.
`fetch` downloads into the HF cache under HF_HOME (/export/models on the
GB300 - the root filesystem is nearly full, so never ~/.cache) and verifies
every file's sha256. `build_farm` exposes the cached files in ComfyUI's
folder layout (<farm>/<category>/<link name>) as symlinks, so nothing is
stored twice. The container mounts /export/models at the same path, so the
links resolve inside it too.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

CATEGORIES = ("diffusion_models", "latent_upscale_models", "loras", "text_encoders", "vae")
_HEX = frozenset("0123456789abcdef")


class ManifestError(ValueError):
    """The manifest is malformed."""


class ChecksumError(RuntimeError):
    """A downloaded file's sha256 does not match the manifest."""


@dataclass(frozen=True)
class WeightFile:
    model: str
    category: str
    repo: str
    revision: str
    path: str
    size: int
    sha256: str

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]


def load_manifest(path: Path) -> list[WeightFile]:
    data = json.loads(path.read_text())
    if data.get("schema_version") != 1:
        raise ManifestError(f"{path}: unsupported schema_version {data.get('schema_version')!r}")
    files = [WeightFile(**row) for row in data["files"]]
    for f in files:
        where = f"{f.repo}:{f.path}"
        if f.category not in CATEGORIES:
            raise ManifestError(f"{where}: unknown category {f.category!r}")
        if len(f.sha256) != 64 or not set(f.sha256) <= _HEX:
            raise ManifestError(f"{where}: sha256 must be 64 lowercase hex characters")
        if len(f.revision) != 40 or not set(f.revision) <= _HEX:
            raise ManifestError(f"{where}: revision must be a pinned 40-character commit")
        if f.size <= 0:
            raise ManifestError(f"{where}: size must be positive")
    return files


def link_names(files: Iterable[WeightFile]) -> dict[WeightFile, str]:
    """ComfyUI file name per manifest row: the bare file name, unless another
    row in the same category has that name with DIFFERENT content - then
    `<model>--<name>`, so a workflow can never load the wrong file."""
    rows = list(files)
    contents: dict[tuple[str, str], set[str]] = {}
    for f in rows:
        contents.setdefault((f.category, f.name), set()).add(f.sha256)
    return {
        f: f.name if len(contents[(f.category, f.name)]) == 1 else f"{f.model}--{f.name}"
        for f in rows
    }


def unique_by_sha(files: Iterable[WeightFile]) -> list[WeightFile]:
    """One row per distinct content; the first row wins."""
    seen: dict[str, WeightFile] = {}
    for f in files:
        seen.setdefault(f.sha256, f)
    return list(seen.values())


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 24), b""):
            digest.update(block)
    return digest.hexdigest()


Downloader = Callable[[WeightFile], Path]


def fetch(files: Iterable[WeightFile], download: Downloader) -> dict[str, Path]:
    """Download every distinct file once and verify it; returns sha256 -> local path."""
    local: dict[str, Path] = {}
    for f in unique_by_sha(files):
        path = download(f)
        got = sha256_of(path)
        if got != f.sha256:
            raise ChecksumError(f"{f.repo}:{f.path}: sha256 {got} != manifest {f.sha256}")
        local[f.sha256] = path
    return local


def hf_download(f: WeightFile) -> Path:
    from huggingface_hub import hf_hub_download  # heavy import, CLI path only

    return Path(hf_hub_download(f.repo, f.path, revision=f.revision))


def build_farm(
    files: Sequence[WeightFile],
    local: dict[str, Path],
    farm_root: Path,
    *,
    names: Mapping[WeightFile, str] | None = None,
) -> list[Path]:
    """Symlink every row into <farm_root>/<category>/<link name>; idempotent, repairs wrong links.

    `names` defaults to `link_names(files)`. When `files` is a subset of a manifest, pass
    the full manifest's `link_names`, so a link's name never depends on what was left out.
    """
    link_name = link_names(files) if names is None else names
    links: list[Path] = []
    for f in files:
        target = local[f.sha256]
        link = farm_root / f.category / link_name[f]
        link.parent.mkdir(parents=True, exist_ok=True)
        if not (link.is_symlink() and link.resolve() == target.resolve()):
            if link.is_symlink() or link.exists():
                link.unlink()
            link.symlink_to(target)
        links.append(link)
    return list(dict.fromkeys(links))


def extra_model_paths_yaml(farm_root: Path) -> str:
    """ComfyUI's extra_model_paths.yaml pointing every category at the farm."""
    lines = ["synthbench:", f"  base_path: {farm_root}"]
    lines += [f"  {category}: {category}/" for category in CATEGORIES]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None, *, download: Downloader = hf_download) -> int:
    parser = argparse.ArgumentParser(prog="python -m synthbench.generate.weights")
    parser.add_argument("command", choices=["sync"])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--farm-root", type=Path, default=Path("/export/models/comfyui"))
    parser.add_argument(
        "--skip-repo", action="append", default=[], help="leave a repo out (e.g. still gated)"
    )
    args = parser.parse_args(argv)
    skip = set(args.skip_repo)
    manifest = load_manifest(args.manifest)
    files = [f for f in manifest if f.repo not in skip]
    local = fetch(files, download)
    # Names come from the whole manifest: skipping a repo must not rename other models' links.
    links = build_farm(files, local, args.farm_root, names=link_names(manifest))
    sys.stdout.write(f"verified {len(local)} files; {len(links)} links under {args.farm_root}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
