"""F-294 — ``External › Prometheus scrape``: the metrics endpoint really serves
a Prometheus document that the dashboard's parser can read.

Inventory row: ``docs/reference/feature-inventory.md`` §3, grep anchor
``External › Prometheus scrape``.

This is the external-artefact half of the row. The scrape is produced by
``backend/core/metrics.py`` ``get_metrics_response()`` and served by
``backend/api/routes/metrics.py``; the second consumer of the *same* bytes is
the dashboard, ``frontend/src/services/metricsParser.ts`` ``fetchAIMetrics``,
which greps for metric names by string. That pair is why the row is worth a
golden path at all: a rename inside ``metrics.py`` keeps every unit test green
and silently blanks the dashboard's cards, because nothing in the repo compares
the emitted names against the names the parser looks up. So these assertions
name the metric strings the frontend reads, at the two places it reads them.

Nothing here is mocked, and nothing here asserts a *value* — the fake-mode
verdicts are the Playwright batch's job. These paths assert the contract of the
document: content type, parseability, declared families, and label shape.
"""

from __future__ import annotations

import re

import httpx
import pytest

# ``network`` is the repo's marker for "requires network access"; these specs
# talk HTTP to a live stack. The explicit timeout is not optional: the ini
# default is 5s (pyproject.toml timeout = 5) and an empty registry scrape is
# fast but a loaded one is not, and 5s against a real stack is a coin flip.
# The conftest timeout hierarchy (backend/tests/conftest.py) puts an explicit
# marker above the ini default.
pytestmark = [pytest.mark.network, pytest.mark.timeout(120)]

METRICS_PATH = "/api/metrics"

# Names the dashboard reads as plain scalars (metricsParser.ts:364-367, via
# getGaugeValue). These four are registered without labels, so they must appear
# as a bare ``name value`` line.
UNLABELLED_METRICS = (
    "hsi_detections_processed_total",
    "hsi_events_created_total",
    "hsi_detection_queue_depth",
    "hsi_analysis_queue_depth",
)

# Names the dashboard reads by label (metricsParser.ts:368-370, via
# getCountersByLabel). The label is the whole contract: a counter renamed but
# also relabelled reads as zero on the dashboard.
LABELLED_COUNTERS = {
    "hsi_pipeline_errors_total": "error_type",
    "hsi_queue_overflow_total": "queue_name",
    "hsi_queue_items_moved_to_dlq_total": "queue_name",
}

# Histograms the dashboard reads by label (metricsParser.ts:343-354, via
# extractHistogram). Asserted only when a sample exists — an unobserved
# Histogram emits no sample lines at all (verified in-process against an idle
# registry: ``# TYPE`` present, no value lines), and which workers have observed
# a request is not this spec's contract.
LABELLED_HISTOGRAMS = {
    "hsi_stage_duration_seconds": "stage",
    "hsi_ai_request_duration_seconds": "service",
}

# A sample line is: name, optional {labels}, whitespace, a value. Prometheus's
# own text-format grammar is stricter; this is the subset the dashboard's
# line-splitting parser depends on, which is what a regression could break.
SAMPLE_LINE = re.compile(r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(?P<labels>[^}]*)\})?\s+\S+$")


def _metric_lines(body: str) -> list[str]:
    """Sample lines only — comment lines (``# HELP`` / ``# TYPE``) dropped."""
    return [line for line in body.splitlines() if line and not line.startswith("#")]


def _type_lines(body: str) -> dict[str, str]:
    """Map family name -> declared type, from the ``# TYPE`` lines."""
    declared: dict[str, str] = {}
    for line in body.splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[0] == "# TYPE":
            declared[parts[1]] = parts[3]
    return declared


@pytest.fixture(scope="module")
def scrape_response(api: httpx.Client) -> httpx.Response:
    """One scrape shared by the assertions in this module.

    Deliberately a fixture rather than a module-level call so the harness skip
    (which lives in the ``api`` fixture) fires before any socket is opened.
    """
    return api.get(METRICS_PATH)


@pytest.fixture(scope="module")
def scrape_body(scrape_response: httpx.Response) -> str:
    return scrape_response.text


def test_scrape_answers_as_plaintext_prometheus(scrape_response: httpx.Response) -> None:
    """The endpoint answers, and answers as the format Prometheus scrapes.

    ``metrics.py`` declares ``media_type="text/plain; charset=utf-8"``; a scraper
    that sees JSON or HTML refuses the sample rather than recording nothing, so
    the media type is the observable, not a detail.
    """
    assert scrape_response.status_code == 200, scrape_response.text[:500]
    content_type = scrape_response.headers.get("content-type", "")
    assert content_type.startswith("text/plain"), content_type


def test_scrape_contains_hsi_samples_and_every_one_parses(scrape_body: str) -> None:
    """The document has this project's samples, and no malformed lines.

    The parse check is the guard a rename or a label-quoting bug trips: the
    dashboard splits lines and feeds the pieces to a regex, so one line with an
    unescaped brace or a missing value drops samples on both sides silently.
    """
    samples = _metric_lines(scrape_body)
    assert samples, "scrape body had no sample lines at all"
    unparsed = [line for line in samples if not SAMPLE_LINE.match(line)]
    assert not unparsed, f"{len(unparsed)} unparsable sample lines, e.g. {unparsed[:3]!r}"
    hsi = [line for line in samples if line.split("{")[0].split(" ")[0].startswith("hsi_")]
    assert hsi, "no hsi_* sample lines in the scrape"


def test_dashboard_scalars_are_exposed_unlabelled(scrape_body: str) -> None:
    """Each name ``getGaugeValue`` reads is present as a bare scalar.

    The dashboard looks these up by exact name; if any of them gains a label,
    the lookup stops matching and the card reads 0 with no error anywhere.
    Verified against an idle registry too: prometheus_client emits the value
    line for a zero-valued Gauge/Counter, so this holds in ``--fake`` and
    ``--real`` alike.
    """
    declared = _type_lines(scrape_body)
    for name in UNLABELLED_METRICS:
        assert name in declared, (
            f"{name} has no '# TYPE' line — the family is not registered, so the "
            f"dashboard's {name} lookup can never match"
        )
        matching = [
            line
            for line in _metric_lines(scrape_body)
            if SAMPLE_LINE.match(line) and SAMPLE_LINE.match(line).group("name") == name
        ]
        assert matching, f"{name} declared as {declared[name]!r} but emitted no sample line"
        labelled = [line for line in matching if "{" in line]
        assert not labelled, (
            f"{name} gained a label ({labelled[0]!r}) — metricsParser.ts:364-367 "
            "reads it with getGaugeValue, which matches the bare name"
        )


def test_dashboard_labelled_counters_declare_their_labels(scrape_body: str) -> None:
    """Each counter ``getCountersByLabel`` reads is declared, and its samples —

    if it has any — carry the label the parser extracts. Label presence is
    asserted per sample rather than required, because a counter that has never
    incremented in this process emits nothing for its children.
    """
    declared = _type_lines(scrape_body)
    for name, label in LABELLED_COUNTERS.items():
        assert name in declared, (
            f"{name} is not declared; metricsParser.ts:368-370 reads it by label "
            f"{label!r} and would find nothing"
        )
        for line in _metric_lines(scrape_body):
            match = SAMPLE_LINE.match(line)
            if not match or match.group("name") != name:
                continue
            assert f'{label}=' in (match.group("labels") or ""), (
                f"{name} sample {line!r} lacks label {label!r}"
            )


def test_dashboard_histograms_keep_their_label_names(scrape_body: str) -> None:
    """The two histograms the dashboard extracts are declared; sampled ones
    carry the label the parser selects on.

    A histogram with no observations yet emits only its ``# TYPE`` line, which is
    why absence of samples is not a failure here — but a *relabelled* one is,
    since ``extractHistogram`` matches on ``{stage="detect"}`` /
    ``{service="detect"}`` verbatim.
    """
    declared = _type_lines(scrape_body)
    for name, label in LABELLED_HISTOGRAMS.items():
        assert name in declared, f"{name} is not declared as a metric family"
        # Every sample this family happens to have must carry the label. Zero
        # samples is legal — an unobserved Histogram emits no value lines — so
        # this iterates what exists rather than requiring a count.
        for line in _metric_lines(scrape_body):
            match = SAMPLE_LINE.match(line)
            if not match or match.group("name") != name:
                continue
            assert f'{label}=' in (match.group("labels") or ""), (
                f"{name} sample {line!r} lacks label {label!r}; "
                "metricsParser.ts:343-354 selects on it"
            )
