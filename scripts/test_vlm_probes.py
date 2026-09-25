"""Unit tests for the S-3 salience harness's judge() parsing.

G0 close-out audit #2: a served reply whose content was `null` (or `[1,2]`,
or a bare string) raised AttributeError inside judge() and killed the whole
run - rows were only written after the loop, so the crash lost every frame
judged so far. That is precisely the violation class the probe hunts: an
unparseable verdict must be a DATA POINT (parse_ok False), never a crash.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_MOD = Path(__file__).resolve().parent / "vlm_probes" / "s3_salience_stock.py"
_spec = importlib.util.spec_from_file_location("s3_salience_stock_uu", _MOD)
assert _spec and _spec.loader
s3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s3)


class _Resp:
    def __init__(self, content, status: int = 200):
        self._c, self.status_code = content, status

    def json(self):
        return {"choices": [{"message": {"content": self._c}}]}


class _Client:
    """httpx.Client stand-in: returns one canned completion per call."""

    def __init__(self, content):
        self._c = content

    def post(self, url, json=None):
        return _Resp(self._c)


def _judge(content):
    frame = Path(__file__)  # any readable file; bytes go into the data URI
    return s3.judge(_Client(content), "http://x", frame, "nonce123")


class TestJudgeNeverCrashes:
    def test_null_content_is_a_datapoint_not_a_crash(self) -> None:
        row = _judge("null")
        assert row["parse_ok"] is False

    def test_list_content_is_a_datapoint(self) -> None:
        row = _judge("[1, 2]")
        assert row["parse_ok"] is False

    def test_scalar_content_is_a_datapoint(self) -> None:
        row = _judge('"just a string"')
        assert row["parse_ok"] is False

    def test_wrong_shape_object_scores_invalid(self) -> None:
        row = _judge(json.dumps({"verdict": "confirmed"}))  # no nonce, no score
        assert row["parse_ok"] is False

    def test_out_of_range_score_scores_invalid(self) -> None:
        row = _judge(
            json.dumps(
                {"probe_const": "nonce123", "verdict": "confirmed", "risk_score": 140, "summary": "s"}
            )
        )
        assert row["parse_ok"] is False

    def test_good_verdict_parses(self) -> None:
        row = _judge(
            json.dumps(
                {"probe_const": "nonce123", "verdict": "rejected", "risk_score": 5, "summary": "s"}
            )
        )
        assert row["parse_ok"] is True and row["verdict"] == "rejected"
