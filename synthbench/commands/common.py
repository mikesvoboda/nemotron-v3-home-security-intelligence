"""What every command shares: exit codes, the two stop kinds, and corpus I/O (design §3).

A command returns EXIT_OK, raises RequestError (exit 1: the request is wrong, fix it and run
again) or raises AskOwner (exit 2: the corpus, taxonomy or host is not in the state the command
expects, so the agent stops and asks the owner). cli.main maps the exceptions to exit codes.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn, TypeVar

import yaml
from pydantic import ValidationError

from synthbench.contract.clip import ClipIndexRow, RoundRecord
from synthbench.contract.common import SLUG, ContractModel
from synthbench.contract.corpus import BatchRecord, CorpusManifest, IndexRow
from synthbench.contract.store import CorpusStore
from synthbench.taxonomy.model import Taxonomy, load_taxonomy, taxonomy_sha256

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_ASK = 2
ASK_OWNER = "Stop and ask the owner."
TAXONOMY_CHANGED = (
    "the taxonomy changed since corpus version {version} was created, so new batches would not "
    "be comparable. A changed taxonomy needs a new corpus version, which the owner sets by "
    "editing `version:` in synthbench/taxonomy/tier_b_v0.yaml."
)

M = TypeVar("M", bound=ContractModel)


class Parser(argparse.ArgumentParser):
    """argparse exits 2 on a usage error, but 2 means "ask the owner" here, so exit 1."""

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(EXIT_ERROR, f"{self.prog}: error: {message}\n")


class RequestError(Exception):
    """The request is wrong: fix it and run the command again (exit 1)."""


class AskOwner(Exception):
    """The corpus, taxonomy or host is not in the state the command expects (exit 2).

    The message is one or more sentences; cli.main appends "Stop and ask the owner."
    """


class CorpusError(AskOwner):
    """A corpus file could not be read, parsed or written."""

    def __init__(self, verb: str, path: Path, error: Exception) -> None:
        lines = str(error).splitlines()
        detail = f"{type(error).__name__}: {lines[0]}" if lines else type(error).__name__
        super().__init__(f"cannot {verb} {path} ({detail}).")


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def fail(code: int, message: str) -> int:
    sys.stderr.write(f"synthbench: {message}\n")
    return code


def batch_name(text: str) -> str:
    """argparse type for --batch: a slug, so no batch path can leave the corpus."""
    if not SLUG.fullmatch(text):
        raise argparse.ArgumentTypeError(f"batch name must match {SLUG.pattern}: {text!r}")
    return text


def round_name(text: str) -> str:
    """argparse type for --round: a slug, so no round path can leave the corpus."""
    if not SLUG.fullmatch(text):
        raise argparse.ArgumentTypeError(f"round name must match {SLUG.pattern}: {text!r}")
    return text


def taxonomy() -> Taxonomy:
    """The committed taxonomy; one that does not load is the owner's to fix (exit 2)."""
    try:
        return load_taxonomy()
    except (OSError, UnicodeDecodeError, yaml.YAMLError, ValidationError) as error:
        first = (str(error).splitlines() or [""])[0]
        raise AskOwner(
            f"the committed taxonomy does not load ({type(error).__name__}: {first})."
        ) from error


def read(store: CorpusStore, path: Path, model: type[M]) -> M:
    try:
        return store.read(path, model)
    except (OSError, UnicodeDecodeError, ValidationError) as error:
        raise CorpusError("read", path, error) from error


def read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise CorpusError("read", path, error) from error


def read_index(store: CorpusStore) -> dict[str, IndexRow]:
    try:
        return store.latest_index()
    except (OSError, UnicodeDecodeError, ValidationError) as error:
        raise CorpusError("read", store.index_file, error) from error


def write_new(store: CorpusStore, path: Path, model: ContractModel) -> None:
    try:
        store.write_new(path, model)
    except OSError as error:  # includes FileExistsError when two first runs race
        raise CorpusError("write", path, error) from error


def write_new_bytes(store: CorpusStore, path: Path, data: bytes) -> None:
    try:
        store.write_new_bytes(path, data)
    except OSError as error:
        raise CorpusError("write", path, error) from error


def replace_json(store: CorpusStore, path: Path, model: ContractModel) -> None:
    try:
        store.replace_json(path, model)
    except OSError as error:
        raise CorpusError("write", path, error) from error


def replace_text(store: CorpusStore, path: Path, text: str) -> None:
    try:
        store.replace_text(path, text)
    except OSError as error:
        raise CorpusError("write", path, error) from error


def append_index(store: CorpusStore, rows: Iterable[IndexRow]) -> None:
    try:
        store.append_index(rows)
    except OSError as error:
        raise CorpusError("write", store.index_file, error) from error


def check_manifest(store: CorpusStore) -> None:
    """Exit 2 if corpus.json records a different taxonomy than the committed one."""
    if read(store, store.manifest_file, CorpusManifest).taxonomy_sha256 != taxonomy_sha256():
        raise AskOwner(TAXONOMY_CHANGED.format(version=store.version))


def open_batch(
    tax: Taxonomy, env: Mapping[str, str], batch: str
) -> tuple[CorpusStore, BatchRecord]:
    """The store and record of a batch that `sample` created (exit 1 if there is none)."""
    store = CorpusStore.from_env(tax.version, env)
    if not store.batch_file(batch).exists():
        raise RequestError(f"no batch {batch} in corpus version {tax.version}; run sample first")
    check_manifest(store)
    return store, read(store, store.batch_file(batch), BatchRecord)


def read_clip_index(store: CorpusStore) -> dict[str, ClipIndexRow]:
    try:
        return store.latest_clip_index()
    except (OSError, UnicodeDecodeError, ValidationError) as error:
        raise CorpusError("read", store.clip_index_file, error) from error


def append_clip_index(store: CorpusStore, rows: Iterable[ClipIndexRow]) -> None:
    try:
        store.append_clip_index(rows)
    except OSError as error:
        raise CorpusError("write", store.clip_index_file, error) from error


def append_jsonl(store: CorpusStore, path: Path, rows: Iterable[ContractModel]) -> None:
    try:
        store.append_jsonl(path, rows)
    except OSError as error:
        raise CorpusError("write", path, error) from error


def open_round(tax: Taxonomy, env: Mapping[str, str], name: str) -> tuple[CorpusStore, RoundRecord]:
    """The store and record of a clip round that `clip sample` created (exit 1 if none)."""
    store = CorpusStore.from_env(tax.version, env)
    if not store.round_file(name).exists():
        raise RequestError(
            f"no clip round {name} in corpus version {tax.version}; run clip sample first"
        )
    check_manifest(store)
    return store, read(store, store.round_file(name), RoundRecord)
