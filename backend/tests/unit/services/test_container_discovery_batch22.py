"""Batch-22 mutation-kill battery: container_discovery compose-fallback
warning texts + fallback-return arg forwards.

Target: the 5 NEW true gaps found by the FULL 883-key cdfull run
(/tmp/redcheck-cdfull.log, rc=0 09:22:25Z, 844 KILLED / 39 SURVIVED —
these 5 are cdfull survivors outside the cd52 dossier's 27):
- x_build_configs_from_compose__mutmut_16 (FileNotFoundError warning -> None)
- __mutmut_21 (generic-Exception parse-warning -> None)
- __mutmut_22/23/25 (fallback return build_service_configs(settings,
  include_monitoring) args -> None / settings->None / removal)

cdfull ALSO killed the prior-run anomalies (359/467/488 grace/backoff and
compose__9) and reproduced all 27 cd52 survivors — the 7 info-family extras
(7, 10-15) are batch-20's kill set, not scope here.

Root cause: no test ever drove the two EXCEPTION fallback legs of
build_configs_from_compose with logger capture or with a settings object
whose ports/flag differ from the defaults — the WP44 test drives the
FileNotFoundError leg through the SERVICE constructor and only checks
flags, and batch-20 pins the SUCCESS info and the service-level port leg.

MEASURED against shipped production this session (workspace-tree probe;
production NOT bent):
- FileNotFoundError leg: warning 'Compose file not found: <path>, falling
  back to hardcoded configs' EXACT (no kwargs, exactly 1 call); shipped
  fallback pg port 15432 + prometheus PRESENT with flag=True settings.
- Generic leg (parse_file raises ValueError('badyaml')): warning 'Failed to
  parse compose file: badyaml, falling back to hardcoded configs' EXACT
  (no kwargs, exactly 1 call); flag=True -> prom present, flag=False ->
  prom ABSENT, pg 15432 in both — the two flag legs plus the pg-port pin
  kill settings->None (5432 default), include_monitoring->None (falsy:
  prom wrongly absent on the flag=True drive) and removal (default True:
  prom wrongly present on the flag=False drive).
Both legs are driven because keys 22/23/25 sit on the fallback returns of
BOTH legs (source L81/L84, identical text — occurrence mapping decides
which); driving both makes either assignment fatal.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.services import container_discovery as CD
from backend.services.compose_parser import ComposeParser
from backend.tests.unit.services.test_container_discovery import ALL_PORTS


class TestFallbackLegWarningTexts:
    """Both exception legs log their own message; ->None mutants died
    silently because no test captured warnings on these legs."""

    def test_missing_file_warns_with_exact_message(self, tmp_path):
        missing = tmp_path / "gone-b22.yml"
        settings = SimpleNamespace(monitoring_enabled=True, **ALL_PORTS)
        with (
            patch.object(CD.logger, "warning", autospec=True) as lw,
            patch.object(CD.logger, "info", autospec=True),
        ):
            CD.build_configs_from_compose(missing, settings, True)
        assert len(lw.call_args_list) == 1
        # MEASURED EXACT: message tuple only, no kwargs
        assert lw.call_args_list[0].args == (
            f"Compose file not found: {missing}, falling back to hardcoded configs",
        )
        assert lw.call_args_list[0].kwargs == {}

    def test_parse_failure_warns_with_exact_message(self, tmp_path, monkeypatch):
        def boom(_self, _path):
            raise ValueError("badyaml")

        monkeypatch.setattr(ComposeParser, "parse_file", boom)
        settings = SimpleNamespace(monitoring_enabled=True, **ALL_PORTS)
        with (
            patch.object(CD.logger, "warning", autospec=True) as lw,
            patch.object(CD.logger, "info", autospec=True),
        ):
            CD.build_configs_from_compose(tmp_path / "broken-b22.yml", settings, True)
        assert len(lw.call_args_list) == 1
        assert lw.call_args_list[0].args == (
            "Failed to parse compose file: badyaml, falling back to hardcoded configs",
        )
        assert lw.call_args_list[0].kwargs == {}


class TestFallbackReturnForwardsBothArgs:
    """Every fallback return must forward settings AND include_monitoring;
    both legs driven because the mutants sit on either return line."""

    @pytest.mark.parametrize("flag", [True, False])
    @pytest.mark.parametrize("leg", ["missing", "parse_error"])
    def test_fallback_forwards_settings_ports_and_flag(self, tmp_path, monkeypatch, leg, flag):
        settings = SimpleNamespace(monitoring_enabled=True, **ALL_PORTS)
        if leg == "parse_error":

            def boom(_self, _path):
                raise ValueError("badyaml")

            monkeypatch.setattr(ComposeParser, "parse_file", boom)
            path = tmp_path / "broken-b22.yml"
        else:
            path = tmp_path / "gone-b22.yml"
        with (
            patch.object(CD.logger, "warning", autospec=True),
            patch.object(CD.logger, "info", autospec=True),
        ):
            cfgs = CD.build_configs_from_compose(path, settings, flag)
        # settings->None mutant: pg port 5432 (env default) not 15432
        assert cfgs["postgres"].port == 15432
        # include_monitoring->None: prom absent on flag=True; removal
        # (default True): prom present on flag=False. Both drive legs kill.
        assert ("prometheus" in cfgs) is flag
