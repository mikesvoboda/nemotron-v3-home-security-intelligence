"""Docker Compose file parser for dynamic service discovery.

This module parses docker-compose.yml files to dynamically build ServiceConfig
objects for the container orchestrator. This eliminates the need to maintain
a separate hardcoded list of services.

Key Features:
- Parses healthcheck definitions to extract health endpoints/commands
- Uses labels for orchestrator-specific configuration
- Infers service category from name prefixes (ai-*, etc.)
- Provides sensible defaults for missing configuration

Label Schema (optional - all have defaults):
    orchestrator.enabled: "true" | "false" (default: "true")
    orchestrator.category: "INFRASTRUCTURE" | "AI" | "MONITORING" (default: inferred)
    orchestrator.display_name: "Human Readable Name" (default: service name)
    orchestrator.backoff_base: "5.0" (default: category-specific)
    orchestrator.backoff_max: "300.0" (default: category-specific)
    orchestrator.startup_grace_period: "60" (default: from healthcheck or category)
    orchestrator.max_failures: "5" (default: from healthcheck retries or category)

Usage:
    from backend.services.compose_parser import ComposeParser

    parser = ComposeParser()
    configs = parser.parse_file("docker-compose.prod.yml")
    # Returns: dict[str, ServiceConfig]
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from backend.core.logging import get_logger
from backend.services.orchestrator import ServiceCategory, ServiceConfig

logger = get_logger(__name__)

# Category defaults for backoff settings
CATEGORY_DEFAULTS: dict[ServiceCategory, dict[str, Any]] = {
    ServiceCategory.INFRASTRUCTURE: {
        "startup_grace_period": 15,
        "max_failures": 10,
        "restart_backoff_base": 2.0,
        "restart_backoff_max": 60.0,
    },
    ServiceCategory.AI: {
        "startup_grace_period": 60,
        "max_failures": 5,
        "restart_backoff_base": 5.0,
        "restart_backoff_max": 300.0,
    },
    ServiceCategory.MONITORING: {
        "startup_grace_period": 30,
        "max_failures": 5,
        "restart_backoff_base": 10.0,
        "restart_backoff_max": 120.0,
    },
}

# Service name prefixes for category inference
CATEGORY_PREFIXES: dict[str, ServiceCategory] = {
    "ai-": ServiceCategory.AI,
    "prometheus": ServiceCategory.MONITORING,
    "grafana": ServiceCategory.MONITORING,
    "loki": ServiceCategory.MONITORING,
    "jaeger": ServiceCategory.MONITORING,
    "alertmanager": ServiceCategory.MONITORING,
    "pyroscope": ServiceCategory.MONITORING,
    "alloy": ServiceCategory.MONITORING,
    "elasticsearch": ServiceCategory.MONITORING,
    "node-exporter": ServiceCategory.MONITORING,
    "cadvisor": ServiceCategory.MONITORING,
    "dcgm-exporter": ServiceCategory.MONITORING,
    "redis-exporter": ServiceCategory.MONITORING,
    "json-exporter": ServiceCategory.MONITORING,
    "blackbox-exporter": ServiceCategory.MONITORING,
}

# Infrastructure services (explicit list since they don't have a prefix)
INFRASTRUCTURE_SERVICES: set[str] = {
    "postgres",
    "redis",
    "backend",
    "frontend",
    "go2rtc",
}


class ComposeParser:
    """Parser for docker-compose.yml files.

    Extracts service configurations for the container orchestrator,
    including health checks, ports, and orchestrator-specific labels.
    """

    def __init__(self) -> None:
        """Initialize the compose parser."""
        # Regex patterns for extracting health endpoints from healthcheck commands
        # Patterns match: curl, wget, or generic http://localhost URLs
        self._http_patterns = [
            re.compile(r"curl\s+.*http://localhost:(\d+)(/[^\s'\"]+)?"),
            re.compile(r"wget\s+.*http://localhost:(\d+)(/[^\s'\"]+)?"),
            re.compile(r"http://localhost:(\d+)(/[^\s'\"]+)?"),
        ]

    def parse_file(
        self,
        compose_file: str | Path,
        include_disabled: bool = False,
    ) -> dict[str, ServiceConfig]:
        """Parse a docker-compose file and return ServiceConfig objects.

        Args:
            compose_file: Path to the docker-compose.yml file.
            include_disabled: If True, include services with orchestrator.enabled=false.

        Returns:
            Dictionary mapping service names to ServiceConfig objects.

        Raises:
            FileNotFoundError: If the compose file doesn't exist.
            yaml.YAMLError: If the compose file is invalid YAML.
        """
        compose_path = Path(compose_file).resolve()
        if not compose_path.exists():
            raise FileNotFoundError(f"Compose file not found: {compose_file}")

        # Security: Verify the file has a safe extension
        if compose_path.suffix not in (".yml", ".yaml"):
            raise ValueError(f"Invalid compose file extension: {compose_path.suffix}")

        with compose_path.open() as f:
            compose_data = yaml.safe_load(f)

        if not compose_data or "services" not in compose_data:
            logger.warning(f"No services found in {compose_file}")
            return {}

        configs: dict[str, ServiceConfig] = {}
        services = compose_data.get("services", {})

        for name, service_def in services.items():
            if service_def is None:
                continue

            # Check if service is enabled (default: true)
            labels = service_def.get("labels", {})
            # Labels can be a list or dict
            if isinstance(labels, list):
                labels = self._labels_list_to_dict(labels)

            enabled = labels.get("orchestrator.enabled", "true").lower() == "true"
            if not enabled and not include_disabled:
                logger.debug(f"Skipping disabled service: {name}")
                continue

            try:
                config = self._parse_service(name, service_def)
                if config:
                    configs[name] = config
                    logger.debug(f"Parsed service config: {name}")
            except Exception as e:
                logger.warning(f"Failed to parse service {name}: {e}")

        logger.info(f"Parsed {len(configs)} service configs from {compose_file}")
        return configs

    def _labels_list_to_dict(self, labels: list[str]) -> dict[str, str]:
        """Convert labels list format to dict.

        Docker compose supports both:
            labels:
              - "key=value"
            labels:
              key: value

        Args:
            labels: List of "key=value" strings.

        Returns:
            Dictionary of label key-value pairs.
        """
        result: dict[str, str] = {}
        for label in labels:
            if "=" in label:
                key, value = label.split("=", 1)
                result[key] = value
        return result

    def _parse_service(
        self,
        name: str,
        service_def: dict[str, Any],
    ) -> ServiceConfig | None:
        """Parse a single service definition into a ServiceConfig.

        Args:
            name: Service name.
            service_def: Service definition from docker-compose.

        Returns:
            ServiceConfig if parseable, None otherwise.
        """
        labels = service_def.get("labels", {})
        if isinstance(labels, list):
            labels = self._labels_list_to_dict(labels)

        # Determine category
        category = self._get_category(name, labels)

        # Get category defaults
        defaults = CATEGORY_DEFAULTS.get(category, CATEGORY_DEFAULTS[ServiceCategory.AI])

        # Parse healthcheck
        healthcheck = service_def.get("healthcheck", {})
        health_endpoint, health_cmd, health_port = self._parse_healthcheck(healthcheck)

        # Parse port from ports section or healthcheck
        port = self._parse_port(service_def, health_port)

        # Get display name
        display_name = labels.get("orchestrator.display_name", self._format_display_name(name))

        # Get startup grace period (from label, healthcheck start_period, or default)
        startup_grace = self._parse_duration(
            labels.get("orchestrator.startup_grace_period")
            or healthcheck.get("start_period")
            or str(defaults["startup_grace_period"])
        )

        # Get max failures (from label, healthcheck retries, or default)
        max_failures = int(
            labels.get("orchestrator.max_failures")
            or healthcheck.get("retries")
            or defaults["max_failures"]
        )

        # Get backoff settings
        backoff_base = float(
            labels.get("orchestrator.backoff_base", defaults["restart_backoff_base"])
        )
        backoff_max = float(labels.get("orchestrator.backoff_max", defaults["restart_backoff_max"]))

        return ServiceConfig(
            display_name=display_name,
            category=category,
            port=port,
            health_endpoint=health_endpoint,
            health_cmd=health_cmd,
            startup_grace_period=startup_grace,
            max_failures=max_failures,
            restart_backoff_base=backoff_base,
            restart_backoff_max=backoff_max,
        )

    def _get_category(
        self,
        name: str,
        labels: dict[str, str],
    ) -> ServiceCategory:
        """Determine service category from labels or name.

        Args:
            name: Service name.
            labels: Service labels.

        Returns:
            ServiceCategory enum value.
        """
        # Check label first
        category_label = labels.get("orchestrator.category", "").upper()
        if category_label:
            try:
                return ServiceCategory[category_label]
            except KeyError:
                logger.warning(f"Unknown category label '{category_label}' for {name}")

        # Check infrastructure services
        if name in INFRASTRUCTURE_SERVICES:
            return ServiceCategory.INFRASTRUCTURE

        # Check prefixes
        for prefix, category in CATEGORY_PREFIXES.items():
            if name.startswith(prefix) or name == prefix:
                return category

        # Default to infrastructure
        return ServiceCategory.INFRASTRUCTURE

    def _parse_healthcheck(
        self,
        healthcheck: dict[str, Any],
    ) -> tuple[str | None, str | None, int | None]:
        """Parse healthcheck definition to extract health endpoint or command.

        Args:
            healthcheck: Healthcheck definition from docker-compose.

        Returns:
            Tuple of (health_endpoint, health_cmd, port).
            Only one of health_endpoint or health_cmd will be set.
        """
        if healthcheck.get("disable"):
            return None, None, None

        test = healthcheck.get("test")
        if not test:
            return None, None, None

        # Convert test to string for parsing
        if isinstance(test, list):
            # Skip CMD or CMD-SHELL prefix
            if test and test[0] in ("CMD", "CMD-SHELL"):
                test = test[1:]
            test_str = " ".join(str(t) for t in test)
        else:
            test_str = str(test)

        # Try to extract HTTP endpoint
        for pattern in self._http_patterns:
            match = pattern.search(test_str)
            if match:
                port = int(match.group(1))
                # Group 2 is the endpoint path, default to /health if not captured
                endpoint = match.group(2) if match.lastindex and match.lastindex >= 2 else "/health"
                return endpoint, None, port

        # If no HTTP endpoint found, use the command as health_cmd
        # Clean up common prefixes
        health_cmd = test_str.strip()
        if health_cmd.startswith("sh -c"):
            health_cmd = health_cmd[6:].strip().strip("'\"")

        # Extract port from common command patterns
        cmd_port: int | None = None
        port_match = re.search(r"-p\s+(\d+)|:(\d+)", health_cmd)
        if port_match:
            cmd_port = int(port_match.group(1) or port_match.group(2))

        return None, health_cmd, cmd_port

    def _parse_port(
        self,
        service_def: dict[str, Any],
        health_port: int | None,
    ) -> int:
        """Extract service port from ports definition or healthcheck.

        Args:
            service_def: Service definition from docker-compose.
            health_port: Port extracted from healthcheck (if any).

        Returns:
            Service port number.
        """
        # Try healthcheck port first (most accurate for internal port)
        if health_port:
            return health_port

        # Parse ports section
        ports = service_def.get("ports", [])
        for port_def in ports:
            port_str = str(port_def)
            # Handle formats: "8080:8080", "127.0.0.1:8080:8080", "8080"
            parts = port_str.split(":")
            if len(parts) >= 2:
                # Last part is container port
                container_port = parts[-1].split("/")[0]  # Remove /tcp, /udp
                try:
                    return int(container_port)
                except ValueError:
                    continue
            elif len(parts) == 1:
                try:
                    return int(parts[0].split("/")[0])
                except ValueError:
                    continue

        # Default port
        return 8080

    def _parse_duration(self, duration: str | None) -> int:
        """Parse duration string to seconds.

        Args:
            duration: Duration string like "30s", "2m", "120".

        Returns:
            Duration in seconds.
        """
        if not duration:
            return 30

        duration = str(duration).strip()

        # Already an integer
        if duration.isdigit():
            return int(duration)

        # Parse with suffix
        match = re.match(r"(\d+)([smh])?", duration)
        if match:
            value = int(match.group(1))
            unit = match.group(2) or "s"
            if unit == "m":
                return value * 60
            elif unit == "h":
                return value * 3600
            else:
                return value

        return 30

    def _format_display_name(self, name: str) -> str:
        """Format service name as display name.

        Args:
            name: Service name (e.g., "ai-yolo26").

        Returns:
            Display name (e.g., "AI YOLO26").
        """
        # Remove common prefixes
        display = name
        if display.startswith("ai-"):
            display = display[3:]

        # Replace hyphens with spaces and title case
        display = display.replace("-", " ").replace("_", " ")

        # Handle special cases
        special_cases = {
            "yolo26": "YOLO26",
            "llm": "LLM (Nemotron)",
            "clip": "CLIP",
            "florence": "Florence-2",
            "postgres": "PostgreSQL",
            "redis": "Redis",
            "go2rtc": "go2rtc",
            "grafana": "Grafana",
            "prometheus": "Prometheus",
            "loki": "Loki",
            "jaeger": "Jaeger",
            "alertmanager": "Alertmanager",
            "pyroscope": "Pyroscope",
            "alloy": "Grafana Alloy",
            "elasticsearch": "Elasticsearch",
            "dcgm exporter": "DCGM Exporter",
            "node exporter": "Node Exporter",
            "cadvisor": "cAdvisor",
        }

        for key, value in special_cases.items():
            if display.lower() == key:
                return value

        return display.title()


def parse_compose_configs(
    compose_file: str | Path = "docker-compose.prod.yml",
    _settings: Any = None,
) -> dict[str, ServiceConfig]:
    """Convenience function to parse compose file and return configs.

    Args:
        compose_file: Path to docker-compose file.
        _settings: Optional OrchestratorSettings (unused, for API compatibility).

    Returns:
        Dictionary mapping service names to ServiceConfig objects.
    """
    parser = ComposeParser()
    return parser.parse_file(compose_file)
