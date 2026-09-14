"""Monitoring Stack Validator Service.

This service validates the health of the monitoring stack (Prometheus, Grafana,
exporters) and provides health check endpoints for observability verification.

Features:
    - Validates Prometheus is running and scraping metrics
    - Checks Grafana connectivity and dashboard availability
    - Verifies alerting rules are loaded
    - Provides combined health check for the entire monitoring stack

Usage:
    from backend.services.monitoring_stack_validator import MonitoringStackValidator

    validator = MonitoringStackValidator()

    # Check overall health
    health = await validator.check_health()
    if not health.healthy:
        logger.warning(f"Monitoring stack unhealthy: {health.warnings}")

    # Check individual components
    prom_status = await validator.check_prometheus()
    grafana_status = await validator.check_grafana()
    rules_status = await validator.check_alerting_rules()

    # Get scrape targets
    targets = await validator.get_scrape_targets()
    for target in targets:
        if target.health == ScrapeTargetHealth.DOWN:
            logger.warning(f"Target {target.job} is down: {target.last_error}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import httpx

from backend.core.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


class ScrapeTargetHealth(Enum):
    """Health status of a Prometheus scrape target."""

    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass
class ScrapeTarget:
    """Represents a Prometheus scrape target.

    Attributes:
        job: The job name for this target.
        instance: The instance label (usually host:port).
        scrape_url: The URL being scraped.
        health: Current health status (up/down/unknown).
        last_scrape: ISO timestamp of last scrape attempt.
        last_scrape_duration: Duration of last scrape in seconds.
        last_error: Error message from last failed scrape, if any.
    """

    job: str
    instance: str
    scrape_url: str
    health: ScrapeTargetHealth
    last_scrape: str | None = None
    last_scrape_duration: float = 0.0
    last_error: str | None = None


@dataclass
class PrometheusStatus:
    """Status of the Prometheus server.

    Attributes:
        healthy: Whether Prometheus is healthy overall.
        reachable: Whether Prometheus API is reachable.
        total_targets: Total number of configured scrape targets.
        targets_up: Number of targets with health=up.
        targets_down: Number of targets with health=down.
        error: Error message if unhealthy.
        version: Prometheus version if available.
    """

    healthy: bool
    reachable: bool
    total_targets: int = 0
    targets_up: int = 0
    targets_down: int = 0
    error: str | None = None
    version: str | None = None


@dataclass
class GrafanaStatus:
    """Status of the Grafana server.

    Attributes:
        healthy: Whether Grafana is healthy overall.
        reachable: Whether Grafana API is reachable.
        version: Grafana version.
        database_status: Status of Grafana's database.
        dashboard_count: Number of available dashboards.
        error: Error message if unhealthy.
    """

    healthy: bool
    reachable: bool
    version: str | None = None
    database_status: str | None = None
    dashboard_count: int = 0
    error: str | None = None


@dataclass
class AlertingRulesStatus:
    """Status of Prometheus alerting rules.

    Attributes:
        loaded: Whether alerting rules are loaded.
        total_rules: Total number of alerting rules.
        healthy_rules: Number of rules with health=ok.
        unhealthy_rules: Number of rules with health!=ok.
        rule_groups: List of rule group names.
        error: Error message if unable to check rules.
    """

    loaded: bool
    total_rules: int = 0
    healthy_rules: int = 0
    unhealthy_rules: int = 0
    rule_groups: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class MonitoringStackHealth:
    """Combined health status of the monitoring stack.

    Attributes:
        healthy: Whether the entire monitoring stack is healthy.
        prometheus: Prometheus status details.
        grafana: Grafana status details.
        alerting_rules: Alerting rules status details.
        checked_at: Timestamp when health was checked.
        warnings: List of warning messages for degraded components.
    """

    healthy: bool
    prometheus: PrometheusStatus
    grafana: GrafanaStatus
    alerting_rules: AlertingRulesStatus
    checked_at: datetime
    warnings: list[str] = field(default_factory=list)


class MonitoringStackValidator:
    """Validates monitoring stack health (Prometheus, Grafana, exporters).

    This service periodically checks that the monitoring stack is functional:
    - Prometheus is reachable and scraping targets successfully
    - Grafana is reachable and has a healthy database
    - Alerting rules are loaded and healthy

    The validator can be used for:
    - Health check endpoints
    - Auto-recovery triggers
    - Monitoring dashboards
    """

    def __init__(
        self,
        prometheus_url: str | None = None,
        grafana_url: str | None = None,
        http_timeout: float = 10.0,
    ) -> None:
        """Initialize the MonitoringStackValidator.

        Args:
            prometheus_url: Prometheus server URL. If None, uses settings.
            grafana_url: Grafana server URL. If None, uses settings.
            http_timeout: Timeout for HTTP requests in seconds.
        """
        settings = get_settings()

        # Use provided URLs or fall back to settings
        self._prometheus_url = prometheus_url or getattr(
            settings, "prometheus_url", "http://localhost:9090"
        )
        self._grafana_url = grafana_url or settings.grafana_url

        self._http_timeout = http_timeout
        self._http_client: httpx.AsyncClient | None = None

        logger.info(
            f"MonitoringStackValidator initialized: "
            f"prometheus={self._prometheus_url}, grafana={self._grafana_url}"
        )

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client.

        Returns:
            Async HTTP client for making requests.
        """
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=self._http_timeout)
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client and release resources."""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def check_prometheus(self) -> PrometheusStatus:
        """Check Prometheus health and scrape target status.

        Queries the Prometheus /api/v1/targets endpoint to verify:
        - Prometheus is reachable
        - Scrape targets are configured
        - Targets are being scraped successfully

        Returns:
            PrometheusStatus with health details.
        """
        try:
            client = await self._get_http_client()
            url = f"{self._prometheus_url}/api/v1/targets"

            response = await client.get(url)

            if response.status_code != 200:
                logger.warning(f"Prometheus returned status {response.status_code}")
                return PrometheusStatus(
                    healthy=False,
                    reachable=False,
                    error=f"HTTP {response.status_code}",
                )

            data = response.json()
            if data.get("status") != "success":
                return PrometheusStatus(
                    healthy=False,
                    reachable=True,
                    error=f"API error: {data.get('error', 'unknown')}",
                )

            # Parse target data
            active_targets = data.get("data", {}).get("activeTargets", [])
            total = len(active_targets)
            up_count = sum(1 for t in active_targets if t.get("health") == "up")
            down_count = sum(1 for t in active_targets if t.get("health") == "down")

            logger.debug(f"Prometheus targets: {up_count}/{total} up, {down_count} down")

            return PrometheusStatus(
                healthy=True,
                reachable=True,
                total_targets=total,
                targets_up=up_count,
                targets_down=down_count,
            )

        except httpx.TimeoutException as e:
            logger.warning(f"Prometheus check timed out: {e}")
            return PrometheusStatus(
                healthy=False,
                reachable=False,
                error=f"Request timed out: {e}",
            )
        except Exception as e:
            logger.warning(f"Prometheus check failed: {e}")
            return PrometheusStatus(
                healthy=False,
                reachable=False,
                error=str(e),
            )

    async def get_scrape_targets(self) -> list[ScrapeTarget]:
        """Get list of Prometheus scrape targets with their health status.

        Returns:
            List of ScrapeTarget objects with current status.
        """
        try:
            client = await self._get_http_client()
            url = f"{self._prometheus_url}/api/v1/targets"

            response = await client.get(url)

            if response.status_code != 200:
                logger.warning(f"Failed to get targets: HTTP {response.status_code}")
                return []

            data = response.json()
            if data.get("status") != "success":
                logger.warning(f"Failed to get targets: {data.get('error')}")
                return []

            targets: list[ScrapeTarget] = []
            active_targets = data.get("data", {}).get("activeTargets", [])

            for t in active_targets:
                health_str = t.get("health", "unknown")
                if health_str == "up":
                    health = ScrapeTargetHealth.UP
                elif health_str == "down":
                    health = ScrapeTargetHealth.DOWN
                else:
                    health = ScrapeTargetHealth.UNKNOWN

                target = ScrapeTarget(
                    job=t.get("labels", {}).get("job", "unknown"),
                    instance=t.get("labels", {}).get("instance", "unknown"),
                    scrape_url=t.get("scrapeUrl", ""),
                    health=health,
                    last_scrape=t.get("lastScrape"),
                    last_scrape_duration=t.get("lastScrapeDuration", 0.0),
                    last_error=t.get("lastError") or None,
                )
                targets.append(target)

            return targets

        except Exception as e:
            logger.warning(f"Failed to get scrape targets: {e}")
            return []

    async def check_alerting_rules(self) -> AlertingRulesStatus:
        """Check Prometheus alerting rules status.

        Queries the Prometheus /api/v1/rules endpoint to verify:
        - Rules are loaded
        - Rules are healthy

        Returns:
            AlertingRulesStatus with rule details.
        """
        try:
            client = await self._get_http_client()
            url = f"{self._prometheus_url}/api/v1/rules"

            response = await client.get(url)

            if response.status_code != 200:
                logger.warning(f"Rules endpoint returned {response.status_code}")
                return AlertingRulesStatus(
                    loaded=False,
                    error=f"HTTP {response.status_code}",
                )

            data = response.json()
            if data.get("status") != "success":
                return AlertingRulesStatus(
                    loaded=False,
                    error=f"API error: {data.get('error', 'unknown')}",
                )

            # Parse rule groups
            groups = data.get("data", {}).get("groups", [])
            rule_groups: list[str] = []
            total_rules = 0
            healthy_rules = 0
            unhealthy_rules = 0

            for group in groups:
                group_name = group.get("name", "unknown")
                rule_groups.append(group_name)

                rules = group.get("rules", [])
                for rule in rules:
                    if rule.get("type") == "alerting":
                        total_rules += 1
                        if rule.get("health") == "ok":
                            healthy_rules += 1
                        else:
                            unhealthy_rules += 1

            logger.debug(
                f"Alerting rules: {healthy_rules}/{total_rules} healthy, {len(rule_groups)} groups"
            )

            return AlertingRulesStatus(
                loaded=True,
                total_rules=total_rules,
                healthy_rules=healthy_rules,
                unhealthy_rules=unhealthy_rules,
                rule_groups=rule_groups,
            )

        except httpx.TimeoutException as e:
            logger.warning(f"Rules check timed out: {e}")
            return AlertingRulesStatus(
                loaded=False,
                error=f"Request timed out: {e}",
            )
        except Exception as e:
            logger.warning(f"Rules check failed: {e}")
            return AlertingRulesStatus(
                loaded=False,
                error=str(e),
            )

    async def check_grafana(self) -> GrafanaStatus:
        """Check Grafana health and dashboard availability.

        Queries the Grafana /api/health endpoint and dashboard API to verify:
        - Grafana is reachable
        - Database is healthy
        - Dashboards are available

        Returns:
            GrafanaStatus with health details.
        """
        try:
            client = await self._get_http_client()

            # Check health endpoint
            health_url = f"{self._grafana_url}/api/health"
            health_response = await client.get(health_url)

            if health_response.status_code != 200:
                logger.warning(f"Grafana health returned {health_response.status_code}")
                return GrafanaStatus(
                    healthy=False,
                    reachable=False,
                    error=f"HTTP {health_response.status_code}",
                )

            health_data = health_response.json()
            version = health_data.get("version")
            database_status = health_data.get("database", "unknown")

            # Check dashboard availability
            dashboard_count = 0
            try:
                dashboards = await self.get_dashboards()
                dashboard_count = len(dashboards)
            except Exception as e:
                logger.debug(f"Failed to get dashboard count: {e}")

            # Determine health based on database status
            is_healthy = database_status == "ok"

            if not is_healthy:
                logger.warning(f"Grafana database status: {database_status}")

            return GrafanaStatus(
                healthy=is_healthy,
                reachable=True,
                version=version,
                database_status=database_status,
                dashboard_count=dashboard_count,
            )

        except httpx.TimeoutException as e:
            logger.warning(f"Grafana check timed out: {e}")
            return GrafanaStatus(
                healthy=False,
                reachable=False,
                error=f"Request timed out: {e}",
            )
        except Exception as e:
            logger.warning(f"Grafana check failed: {e}")
            return GrafanaStatus(
                healthy=False,
                reachable=False,
                error=str(e),
            )

    async def get_dashboards(self) -> list[dict[str, Any]]:
        """Get list of available Grafana dashboards.

        Returns:
            List of dashboard metadata dictionaries.
        """
        try:
            client = await self._get_http_client()
            url = f"{self._grafana_url}/api/search?type=dash-db"

            response = await client.get(url)

            if response.status_code != 200:
                logger.warning(f"Dashboard search returned {response.status_code}")
                return []

            dashboards = response.json()
            return dashboards if isinstance(dashboards, list) else []

        except Exception as e:
            logger.warning(f"Failed to get dashboards: {e}")
            return []

    async def check_health(self) -> MonitoringStackHealth:
        """Check overall health of the monitoring stack.

        Performs checks on all monitoring components and aggregates results.

        Returns:
            MonitoringStackHealth with combined status and any warnings.
        """
        # Check all components
        prometheus_status = await self.check_prometheus()
        grafana_status = await self.check_grafana()
        alerting_status = await self.check_alerting_rules()

        # Collect warnings
        warnings: list[str] = []

        if not prometheus_status.reachable:
            warnings.append("Prometheus is unreachable")
        elif prometheus_status.targets_down > 0:
            warnings.append(f"{prometheus_status.targets_down} Prometheus target(s) are down")

        if not grafana_status.reachable:
            warnings.append("Grafana is unreachable")
        elif not grafana_status.healthy:
            warnings.append(f"Grafana database status: {grafana_status.database_status}")

        if not alerting_status.loaded:
            warnings.append("Alerting rules are not loaded")
        elif alerting_status.unhealthy_rules > 0:
            warnings.append(f"{alerting_status.unhealthy_rules} alerting rule(s) are unhealthy")

        # Determine overall health
        # Stack is healthy if Prometheus and Grafana are reachable and healthy
        is_healthy = (
            prometheus_status.healthy
            and prometheus_status.reachable
            and grafana_status.healthy
            and grafana_status.reachable
        )

        if warnings:
            logger.warning(f"Monitoring stack warnings: {warnings}")

        return MonitoringStackHealth(
            healthy=is_healthy,
            prometheus=prometheus_status,
            grafana=grafana_status,
            alerting_rules=alerting_status,
            checked_at=datetime.now(UTC),
            warnings=warnings,
        )
