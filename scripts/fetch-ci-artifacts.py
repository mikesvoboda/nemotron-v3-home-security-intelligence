#!/usr/bin/env python3
"""Harvest a previous CI run's artifacts into a local directory (WP1.5).

Why this exists: the TPA baseline fetch (WP1.3) and the flake consumer
(WP1.5) need the SAME selection — "the newest completed main run of THIS
workflow that actually uploaded artifacts, never the current run" — and the
curl/jq transcription of that rule was already bitten twice in one day (the
generic /actions/runs?branch=main page fills with sibling workflows and
silently misses CI; selecting the current run would let a run baseline
itself). A rule with that track record belongs in a script with a test, not
in a heredoc.

Selection, in order:
  1. Resolve the workflow id by PATH (never a hardcoded id), then list THAT
     workflow's main runs. The generic endpoint mixes every workflow on the
     branch together — measured: 6 sibling rows, no CI, so CI falls off the
     page and a naive fetch silently yields nothing.
  2. Skip the current run id. A self-referential source makes every
     violation "persist against itself" (TPA) and every flake look
     single-sample (flake report).
  3. Take the newest run with >=1 matching artifact. Download+extract each.

Exit protocol (fail-loud doctrine, WP0.5/WP1.3): a failed API call or a run
with no matching artifacts exits NON-ZERO. Empty output must never be
readable as "no flakes / no baseline" when the truth is "the fetch broke" —
that class of silent lie is what the WP0.1 pre-push repair pinned.

Usage:
    fetch-ci-artifacts.py --repo OWNER/REPO --api-base URL --token-stdin \\
        --current-run-id N --out DIR [--workflow .github/workflows/ci.yml]
        [--artifact-regex '^test-results-|^playwright-test-results-']
        [--max-runs 8]
    fetch-ci-artifacts.py --self-test ...   # canned local API; see tests

--self-test skips nothing in the flow: same selection, same download, same
extract — only the API origin is a local canned server. That is deliberate;
a self-test that stubbed out the download would not be a self-test.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path


class HarvestError(RuntimeError):
    pass


# A candidate run older than this cannot have harvestable artifacts left:
# uploads in this repo set retention-days: 7, and 30 is generous to any
# longer-retention workflow. Beyond it, "no matching artifacts" is a certainty
# rather than a finding — see the Finding-4 hardening #2 comment in select_run.
MAX_CANDIDATE_AGE_DAYS = 30


def _run_age_days(created_at: str) -> float | None:
    """Days since the run was created, or None if the page gave no usable
    timestamp (None means 'unknown', never 'stale' — an unparseable page
    must not silently void the selection)."""
    if not created_at:
        return None
    try:
        created = datetime.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if created.tzinfo is None:
        created = created.replace(tzinfo=datetime.UTC)
    return (datetime.datetime.now(datetime.UTC) - created).total_seconds() / 86400


def _ssl_context() -> ssl.SSLContext | None:
    # Self-test runs against a local http:// server; urllib needs no context
    # there and https wants the default. CA bundle honored when present.
    ca = os.environ.get("WP15_CA_BUNDLE")
    if ca:
        return ssl.create_default_context(cafile=ca)
    return None


def _http_url(url: str) -> str:
    """Fail loud on anything but http(s) before it reaches urllib.

    Both URL sources are CI-controlled, not user input: the API base comes
    from this job's own --api-base flag, and archive_download_url comes from
    the GitHub API response for a run this workflow already trusts. The guard
    is the belt so a mistake (or a hostile redirect chain feeding back) is a
    HarvestError, not a file:// or gopher:// read.
    """
    scheme = urllib.parse.urlsplit(url).scheme
    if scheme not in ("https", "http"):
        raise HarvestError(
            f"refusing non-http(s) URL scheme {scheme!r} — "
            "API base and download URLs must be http(s)"
        )
    return url


def _get_json(url: str, token: str) -> object:
    # nosemgrep: ssrf-requests - scheme pinned by _http_url; CI-supplied URL
    req = urllib.request.Request(  # noqa: S310
        _http_url(url),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "wp15-fetch-ci-artifacts",
        },
    )
    try:
        # nosemgrep: ssrf-requests - scheme pinned by _http_url; CI-supplied URL
        with urllib.request.urlopen(req, timeout=60, context=_ssl_context()) as r:  # noqa: S310
            return json.loads(r.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        raise HarvestError(f"GET {url} failed: {e}") from e


class _StripAuthOnCrossHost(urllib.request.HTTPRedirectHandler):
    """Drop Authorization when a redirect changes host — curl's semantics.

    Measured live (WP1.5): the artifact download 302s to a PRE-SIGNED Azure
    blob URL (actions-results...core.windows.net/...&sig=...), and Azure
    answers 401 "Server failed to authenticate" to any request that carries
    an Authorization header ALONGSIDE the SAS signature. curl (which strips
    auth cross-host) gets 200; vanilla urllib (which KEEPS it — unlike curl)
    gets 401 on every artifact. The token is needed only for the api.github.com
    call itself; the redirect target authenticates by signature.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and req.has_header("Authorization"):
            from_host = urllib.parse.urlsplit(req.full_url).netloc
            to_host = urllib.parse.urlsplit(newurl).netloc
            if from_host != to_host:
                new.remove_header("Authorization")
        return new


def _opener() -> urllib.request.OpenerDirector:
    # built lazily: the CA bundle is read at call time, not import time
    handlers: list[object] = [_StripAuthOnCrossHost()]
    ctx = _ssl_context()
    if ctx is not None:
        handlers.append(urllib.request.HTTPSHandler(context=ctx))
    return urllib.request.build_opener(*handlers)


def _get_bytes(url: str, token: str) -> bytes:
    # nosemgrep: ssrf-requests - scheme pinned by _http_url; CI-supplied URL
    req = urllib.request.Request(  # noqa: S310
        _http_url(url),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "wp15-fetch-ci-artifacts",
        },
    )
    try:
        with _opener().open(req, timeout=180) as r:
            return r.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        raise HarvestError(f"GET {url} failed: {e}") from e


def select_run(
    api_base: str,
    repo: str,
    token: str,
    workflow_path: str,
    current_run_id: int,
    artifact_re: re.Pattern[str],
    max_runs: int,
    harvest_runs: int = 1,
) -> list[tuple[int, list[dict]]]:
    """[(run_id, artifacts)] for the newest eligible main runs, up to harvest_runs.

    harvest_runs=1 is the TPA-baseline shape (the runner's previous run IS the
    calibration); the flake consumer passes several — one run per test is one
    sample, and a pass_rate of 0 or 1 is not evidence of flakiness, history is.
    """
    wf_doc = _get_json(f"{api_base}/repos/{repo}/actions/workflows?per_page=100", token)
    wf_id = None
    for wf in wf_doc.get("workflows", []):
        if wf.get("path") == workflow_path:
            wf_id = wf.get("id")
            break
    if wf_id is None:
        raise HarvestError(f"no workflow with path {workflow_path!r} in {repo}")

    runs_doc = _get_json(
        f"{api_base}/repos/{repo}/actions/workflows/{wf_id}/runs"
        f"?branch=main&status=success&per_page={max_runs}",
        token,
    )
    candidates = [r for r in runs_doc.get("workflow_runs", []) if r.get("id") != current_run_id]
    if not candidates:
        raise HarvestError(
            f"no completed main runs of {workflow_path} other than the current one "
            f"({current_run_id}) — this is the FIRST run of this workflow; there is no history yet"
        )
    picked: list[tuple[int, list[dict]]] = []
    for run in candidates:
        if len(picked) >= harvest_runs:
            break
        rid = run.get("id")
        # Finding-4 hardening #2 (measured 2026-09-21 19:22Z, run
        # 35637776479): a stale page served EIGHT January candidates whose
        # artifacts are not merely expired-flagged but long since deleted —
        # the listing yields nothing, every candidate "skips", and the walk
        # dies vacuously while fresh main runs sat on the honest page. A run
        # older than artifact retention is unharvestable by definition
        # (repo uploads use retention-days: 7; this default is 30, generous
        # to any workflow that keeps longer), and the page itself says when
        # the run was created. Drop it BEFORE the artifact query.
        age = _run_age_days(run.get("created_at", ""))
        if age is not None and age > MAX_CANDIDATE_AGE_DAYS:
            print(
                f"run {rid}: created {age:.0f}d ago — beyond artifact retention, "
                f"unharvestable (stale runs-list page?) — skipping"
            )
            continue
        arts_doc = _get_json(
            f"{api_base}/repos/{repo}/actions/runs/{rid}/artifacts?per_page=100", token
        )
        # Finding-4 hardening (measured 2026-09-21): an expired artifact is
        # never harvestable — GitHub 410s its zip (artifact 5038838599, and
        # the 17 redirect lines that preceded this run's failure). One must
        # not make a run "selected"; on a stale runs-list page (observed: a
        # PR job got a January run as newest candidate twice) the expired
        # filter is what lets the walk reach a real baseline.
        arts = [
            a
            for a in arts_doc.get("artifacts", [])
            if artifact_re.search(a.get("name", "")) and not a.get("expired")
        ]
        if arts:
            print(f"selected run {rid}: {len(arts)} matching artifact(s)")
            picked.append((rid, arts))
        else:
            print(f"run {rid}: no artifacts matching pattern — skipping")
    if not picked:
        raise HarvestError(
            f"checked {len(candidates)} candidate main run(s) of {workflow_path}; none had "
            "artifacts matching the pattern"
        )
    return picked


def select_run_with_retries(
    api_base: str,
    repo: str,
    token: str,
    workflow_path: str,
    current_run_id: int,
    artifact_re: re.Pattern[str],
    max_runs: int,
    harvest_runs: int = 1,
    list_retries: int = 3,
    retry_sleep: float = 30.0,
) -> list[tuple[int, list[dict]]]:
    """select_run, re-requested on a VACUOUS selection (Finding-4 hardening #3,
    measured 21:00Z runs 35650649386/35650688761: both lanes red with the
    retention filter working — ONE stale candidate-list page, zero retryable,
    both died). Staleness is per-REQUEST: sibling jobs minutes apart hit
    honest pages, so a re-request usually sees truth. A dead API call is NOT
    retried here (that is not staleness, and fail-loud stands); only the
    page-served-nothing case re-reads, and persistent vacuity still exits
    non-zero — retrying is not tolerating."""
    import time

    last: HarvestError | None = None
    for attempt in range(1, list_retries + 1):
        try:
            return select_run(
                api_base,
                repo,
                token,
                workflow_path,
                current_run_id,
                artifact_re,
                max_runs,
                harvest_runs,
            )
        except HarvestError as e:
            msg = str(e)
            if "none had" not in msg and "no completed main runs" not in msg:
                raise  # transport/other failure: loud immediately
            last = e
            if attempt < list_retries:
                print(
                    f"selection attempt {attempt}/{list_retries} served nothing harvestable "
                    f"— retry after {retry_sleep:.0f}s (stale runs-list page?)"
                )
                time.sleep(retry_sleep)
    assert last is not None
    raise HarvestError(
        f"{last} (after {list_retries} selection attempts — page persistently stale?)"
    )


def harvest(
    api_base: str,
    repo: str,
    token: str,
    workflow_path: str,
    current_run_id: int,
    artifact_re: re.Pattern[str],
    out_dir: Path,
    max_runs: int,
    harvest_runs: int = 1,
    list_retries: int = 3,
    retry_sleep: float = 30.0,
) -> int:
    picked = select_run_with_retries(
        api_base,
        repo,
        token,
        workflow_path,
        current_run_id,
        artifact_re,
        max_runs,
        harvest_runs,
        list_retries,
        retry_sleep,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    files = 0
    for _rid, arts in picked:
        for art in arts:
            aid, aurl = art["id"], art["archive_download_url"]
            blob = _get_bytes(aurl, token)
            dest = out_dir / str(aid)
            dest.mkdir(parents=True, exist_ok=True)
            try:
                with zipfile.ZipFile(BytesIO(blob)) as z:
                    z.extractall(dest)
            except zipfile.BadZipFile as e:
                raise HarvestError(
                    f"artifact {aid} ({art.get('name')}) is not a valid zip: {e}"
                ) from e
            files += sum(1 for p in dest.rglob("*") if p.is_file())
            print(f"  artifact {aid} ({art.get('name')}): extracted to {dest}")
    if files == 0:
        raise HarvestError("downloaded artifacts contained zero files")
    print(f"harvested {files} file(s) from {len(picked)} run(s) into {out_dir}")
    return files


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--api-base", default="https://api.github.com")
    p.add_argument("--repo", required=True, help="OWNER/REPO")
    p.add_argument("--workflow", default=".github/workflows/ci.yml")
    p.add_argument("--current-run-id", required=True, type=int)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--artifact-regex", default=r"^test-results-|^playwright-test-results-")
    p.add_argument("--max-runs", type=int, default=8)
    p.add_argument(
        "--harvest-runs",
        type=int,
        default=1,
        help="harvest the N newest eligible runs (1 = baseline shape; flake report wants several)",
    )
    p.add_argument(
        "--list-retries",
        type=int,
        default=3,
        help="re-selection attempts when the runs-list page serves nothing harvestable "
        "(GitHub has served runner jobs stale pages repeatedly; see Finding-4)",
    )
    p.add_argument(
        "--retry-sleep",
        type=float,
        default=30.0,
        help="seconds between selection retries",
    )
    p.add_argument(
        "--token-stdin",
        action="store_true",
        help="read the API token from stdin (never argv/env — keeps it out of ps and logs)",
    )
    p.add_argument(
        "--self-test",
        action="store_true",
        help="run the real flow against a caller-supplied canned API (see tests/)",
    )
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.token_stdin:
        token = sys.stdin.readline().strip()
    else:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    if not token and args.api_base.startswith("https"):
        print("Error: no API token (stdin with --token-stdin, else GH_TOKEN)", file=sys.stderr)
        return 2
    try:
        harvest(
            api_base=args.api_base.rstrip("/"),
            repo=args.repo,
            token=token,
            workflow_path=args.workflow,
            current_run_id=args.current_run_id,
            artifact_re=re.compile(args.artifact_regex),
            out_dir=args.out,
            max_runs=args.max_runs,
            harvest_runs=args.harvest_runs,
            list_retries=args.list_retries,
            retry_sleep=args.retry_sleep,
        )
    except HarvestError as e:
        # Fail LOUD: the callers (TPA baseline, flake report) treat a
        # non-zero exit as "no history usable" and act accordingly.
        print(f"harvest failed: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
