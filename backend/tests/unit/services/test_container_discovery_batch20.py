"""Batch-20 mutation-kill battery: container_discovery INFO-payload + settings legs.

Target: the TRUE-GAP survivors of the 52-key dossier-residual cd52 lane run
(/tmp/redcheck-cd52.log, rc=0, 25 KILLED / 27 SURVIVED; feed /tmp/cd52-feed.tsv).
Originally triaged 7 gaps + 20 equivalents; on authoring, init__5 flipped from
"dead else-branch" to a REACHABLE true gap (settings=None compose fallback —
see correction below), so 8 keys here and 19 per-mutant-measured EQUIVALENTs
(BSD-J grace=60 x4, BSD-M max_failures=5 x14 via rebuild-minus-kwarg
bit-identity with a postgres grace=10 discriminator; cms__13 []-vs-None
falsiness) justified in the ledger — NOT in scope here.

Root cause of the gap class: no test ever CAPTURED the two observability
INFO sites (compose-success in build_configs_from_compose, discovery-summary
in discover_all), the WP44 fallback test checks the monitoring FLAG leg
only (so the __init__ compose-branch `settings=None` mutant keeps the flag
and reverts ports invisibly), and NOTHING drives the __init__ ternary's
settings=None else-leg (WP44 always passes settings).

Correction logged during authoring: init__5 (else-leg True->False) was
first triaged "flag-dead equivalent" — WRONG. MEASURED this session:
ContainerDiscoveryService(cli, compose_file=missing) with settings omitted
is shipped-reachable: include_monitoring=True -> fallback INCLUDES
prometheus; the mutant's False excludes it. It is a true gap and killed by
test_settingsless_compose_fallback_keeps_monitoring below. The cd20
red-check below therefore covers 8 keys, not 7.

Every expected value MEASURED against shipped production this session
(probe drives below; production NOT bent):
- x_build_configs_from_compose__mutmut_8 (extra=None): parse-success info
  message 'Loaded 3 service configs from <path>' AND extra EXACT
  {'compose_file': str(path), 'count': 3} — renames/None/'COUNT' all die.
- xǁContainerDiscoveryServiceǁ__init____mutmut_8 (settings->None in the
  compose branch): MEASURED shipped fallback port 15432 from ALL_PORTS; the
  mutant's settings=None returns the 5432 .env default. The flag leg cannot
  see this — ports are the only discriminator.
- xǁContainerDiscoveryServiceǁdiscover_all__mutmut_30/31/33/34/35 (message
  ->None, extra ->None/removal/'XXcountXX'/'COUNT'): summary info message
  'Discovered 2 containers' (the shipped unpluralised grammar is pinned AS
  SHIPPED, production never bends) + extra EXACT {'count': 2} with a
  two-container drive so a hardcoded-count mutant dies too.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.schemas.services import ServiceCategory
from backend.services import container_discovery as CD
from backend.services.compose_parser import ComposeParser
from backend.services.container_discovery import (
    ContainerDiscoveryService,
    ServiceConfig,
)
from backend.tests.unit.services.test_container_discovery import ALL_PORTS


class TestComposeSuccessInfoPayload:
    """build_configs_from_compose logs the successful parse; nothing pinned
    that log before, so extra=None and text mutants were invisible."""

    def test_parse_success_logs_message_and_exact_extra(self, tmp_path, monkeypatch):
        path = tmp_path / "fake-b20.yml"
        configs = {
            key: ServiceConfig(display_name=key, category=ServiceCategory.INFRASTRUCTURE, port=1)
            for key in ("postgres", "redis", "backend")
        }
        monkeypatch.setattr(ComposeParser, "parse_file", lambda _self, _path: configs)
        with patch.object(CD.logger, "info", autospec=True) as li:
            out = CD.build_configs_from_compose(path)

        assert out == configs  # success path, not the fallback
        assert len(li.call_args_list) == 1
        m = li.call_args_list[0]
        # MEASURED: literal message + extra dict EXACT (compose_file str + count)
        assert m.args == (f"Loaded 3 service configs from {path}",)
        assert dict(m.kwargs["extra"]) == {"compose_file": str(path), "count": 3}


class TestInitComposeBranchForwardsSettings:
    """The compose branch of __init__ forwards settings into the fallback;
    the WP44 flag-leg test cannot see a settings=None mutant — only ports."""

    def test_missing_compose_file_falls_back_with_settings_ports(self, tmp_path):
        missing = tmp_path / "nope-compose-b20.yml"
        settings = SimpleNamespace(monitoring_enabled=True, **ALL_PORTS)
        svc = ContainerDiscoveryService(MagicMock(), settings=settings, compose_file=missing)

        # MEASURED shipped 15432; settings=None mutant -> 5432 .env default
        assert svc.get_config("postgres").port == 15432

    def test_settingsless_compose_fallback_keeps_monitoring(self, tmp_path):
        """__init__'s settings=None default must stay True (monitoring kept).

        MEASURED shipped: compose_file=missing + NO settings -> fallback
        INCLUDES prometheus. The else-leg True->False mutant drops it — WP44
        always passes settings, so nothing drove this leg before.
        """
        missing = tmp_path / "nope-compose-init5.yml"
        svc = ContainerDiscoveryService(MagicMock(), compose_file=missing)
        assert "prometheus" in svc._configs


class TestDiscoverySummaryInfoPayload:
    """discover_all's summary info: message and extra={'count': N} were
    unpinned, so message->None, extra->None/removal and key renames all
    survived."""

    @pytest.mark.asyncio
    async def test_summary_info_message_and_extra_exact(self):
        containers = [
            SimpleNamespace(
                name="security-postgres-1",
                id="pg-abcdef123456",
                image=SimpleNamespace(tags=["pg:17"]),
            ),
            SimpleNamespace(
                name="security-redis-1",
                id="rd-123456789012",
                image=SimpleNamespace(tags=["redis:7"]),
            ),
        ]
        client = MagicMock()
        client.list_containers = AsyncMock(return_value=containers)
        svc = ContainerDiscoveryService(client)

        with patch.object(CD.logger, "info", autospec=True) as li:
            discovered = await svc.discover_all()

        assert len(discovered) == 2
        summary = [m for m in li.call_args_list if "Discovered" in str(m.args)]
        assert len(summary) == 1
        # MEASURED shipped grammar: 'Discovered 2 containers' — pin as shipped.
        assert summary[0].args == ("Discovered 2 containers",)
        assert dict(summary[0].kwargs["extra"]) == {"count": 2}
