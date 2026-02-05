"""Tests for compose_parser module - dynamic service discovery from docker-compose."""

from pathlib import Path
from textwrap import dedent

import pytest

from backend.services.compose_parser import ComposeParser
from backend.services.orchestrator import ServiceCategory


class TestComposeParser:
    """Tests for ComposeParser class."""

    def test_parse_file_returns_configs(self, tmp_path: Path) -> None:
        """Parsing a compose file returns ServiceConfig dict."""
        compose_content = dedent("""
            version: '3.8'
            services:
              postgres:
                image: postgres:16
                ports:
                  - '5432:5432'
                healthcheck:
                  test: ['CMD', 'pg_isready']
                  interval: 10s
                  timeout: 5s
                  retries: 5
        """)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        parser = ComposeParser()
        configs = parser.parse_file(compose_file)

        assert "postgres" in configs
        assert configs["postgres"].port == 5432
        assert configs["postgres"].category == ServiceCategory.INFRASTRUCTURE

    def test_parse_file_raises_for_missing_file(self) -> None:
        """Parsing a non-existent file raises FileNotFoundError."""
        parser = ComposeParser()
        with pytest.raises(FileNotFoundError):
            parser.parse_file("/nonexistent/docker-compose.yml")

    def test_parse_http_healthcheck_extracts_endpoint(self, tmp_path: Path) -> None:
        """HTTP health checks extract endpoint and port."""
        compose_content = dedent("""
            version: '3.8'
            services:
              ai-yolo26:
                image: yolo:latest
                ports:
                  - '8095:8095'
                healthcheck:
                  test: ['CMD', 'curl', '-f', 'http://localhost:8095/health']
                  interval: 10s
        """)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        parser = ComposeParser()
        configs = parser.parse_file(compose_file)

        assert configs["ai-yolo26"].health_endpoint == "/health"
        assert configs["ai-yolo26"].port == 8095

    def test_parse_wget_healthcheck_extracts_endpoint(self, tmp_path: Path) -> None:
        """Wget health checks extract endpoint and port."""
        compose_content = dedent("""
            version: '3.8'
            services:
              prometheus:
                image: prom/prometheus
                ports:
                  - '9090:9090'
                healthcheck:
                  test: ['CMD', 'wget', '--spider', 'http://localhost:9090/-/healthy']
        """)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        parser = ComposeParser()
        configs = parser.parse_file(compose_file)

        assert configs["prometheus"].health_endpoint == "/-/healthy"
        assert configs["prometheus"].category == ServiceCategory.MONITORING

    def test_parse_cmd_healthcheck_stores_command(self, tmp_path: Path) -> None:
        """CMD health checks store the command."""
        compose_content = dedent("""
            version: '3.8'
            services:
              redis:
                image: redis:7
                ports:
                  - '6379:6379'
                healthcheck:
                  test: ['CMD-SHELL', 'redis-cli ping']
        """)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        parser = ComposeParser()
        configs = parser.parse_file(compose_file)

        assert configs["redis"].health_cmd == "redis-cli ping"
        assert configs["redis"].health_endpoint is None

    def test_infer_category_from_name_prefix(self, tmp_path: Path) -> None:
        """Service category is inferred from name prefix."""
        compose_content = dedent("""
            version: '3.8'
            services:
              ai-llm:
                image: llm:latest
                ports:
                  - '8091:8091'
              grafana:
                image: grafana/grafana
                ports:
                  - '3000:3000'
              backend:
                image: backend:latest
                ports:
                  - '8000:8000'
        """)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        parser = ComposeParser()
        configs = parser.parse_file(compose_file)

        assert configs["ai-llm"].category == ServiceCategory.AI
        assert configs["grafana"].category == ServiceCategory.MONITORING
        assert configs["backend"].category == ServiceCategory.INFRASTRUCTURE

    def test_labels_override_inferred_category(self, tmp_path: Path) -> None:
        """Labels can override inferred category."""
        compose_content = dedent("""
            version: '3.8'
            services:
              custom-service:
                image: custom:latest
                ports:
                  - '9999:9999'
                labels:
                  orchestrator.category: "AI"
                  orchestrator.display_name: "Custom AI Service"
        """)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        parser = ComposeParser()
        configs = parser.parse_file(compose_file)

        assert configs["custom-service"].category == ServiceCategory.AI
        assert configs["custom-service"].display_name == "Custom AI Service"

    def test_disabled_services_excluded_by_default(self, tmp_path: Path) -> None:
        """Services with orchestrator.enabled=false are excluded."""
        compose_content = dedent("""
            version: '3.8'
            services:
              enabled-service:
                image: test:latest
                ports:
                  - '8080:8080'
              disabled-service:
                image: test:latest
                ports:
                  - '8081:8081'
                labels:
                  orchestrator.enabled: "false"
        """)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        parser = ComposeParser()
        configs = parser.parse_file(compose_file)

        assert "enabled-service" in configs
        assert "disabled-service" not in configs

    def test_disabled_services_included_when_requested(self, tmp_path: Path) -> None:
        """Disabled services can be included with include_disabled=True."""
        compose_content = dedent("""
            version: '3.8'
            services:
              disabled-service:
                image: test:latest
                ports:
                  - '8081:8081'
                labels:
                  orchestrator.enabled: "false"
        """)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        parser = ComposeParser()
        configs = parser.parse_file(compose_file, include_disabled=True)

        assert "disabled-service" in configs

    def test_parse_start_period_as_grace_period(self, tmp_path: Path) -> None:
        """Healthcheck start_period maps to startup_grace_period."""
        compose_content = dedent("""
            version: '3.8'
            services:
              slow-service:
                image: slow:latest
                ports:
                  - '8080:8080'
                healthcheck:
                  test: ['CMD', 'curl', '-f', 'http://localhost:8080/health']
                  start_period: 120s
        """)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        parser = ComposeParser()
        configs = parser.parse_file(compose_file)

        assert configs["slow-service"].startup_grace_period == 120

    def test_parse_retries_as_max_failures(self, tmp_path: Path) -> None:
        """Healthcheck retries maps to max_failures."""
        compose_content = dedent("""
            version: '3.8'
            services:
              fragile-service:
                image: fragile:latest
                ports:
                  - '8080:8080'
                healthcheck:
                  test: ['CMD', 'curl', '-f', 'http://localhost:8080/health']
                  retries: 10
        """)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        parser = ComposeParser()
        configs = parser.parse_file(compose_file)

        assert configs["fragile-service"].max_failures == 10

    def test_labels_list_format_supported(self, tmp_path: Path) -> None:
        """Labels in list format are parsed correctly."""
        compose_content = dedent("""
            version: '3.8'
            services:
              list-labels:
                image: test:latest
                ports:
                  - '8080:8080'
                labels:
                  - "orchestrator.category=AI"
                  - "orchestrator.display_name=Test Service"
        """)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        parser = ComposeParser()
        configs = parser.parse_file(compose_file)

        assert configs["list-labels"].category == ServiceCategory.AI
        assert configs["list-labels"].display_name == "Test Service"

    def test_backoff_settings_from_labels(self, tmp_path: Path) -> None:
        """Backoff settings can be configured via labels."""
        compose_content = dedent("""
            version: '3.8'
            services:
              custom-backoff:
                image: test:latest
                ports:
                  - '8080:8080'
                labels:
                  orchestrator.backoff_base: "10.0"
                  orchestrator.backoff_max: "600.0"
        """)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        parser = ComposeParser()
        configs = parser.parse_file(compose_file)

        assert configs["custom-backoff"].restart_backoff_base == 10.0
        assert configs["custom-backoff"].restart_backoff_max == 600.0

    def test_empty_compose_file_returns_empty_dict(self, tmp_path: Path) -> None:
        """Empty compose file returns empty dict."""
        compose_content = "version: '3.8'\n"
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        parser = ComposeParser()
        configs = parser.parse_file(compose_file)

        assert configs == {}

    def test_disabled_healthcheck_returns_no_health_config(self, tmp_path: Path) -> None:
        """Disabled healthcheck results in no health_endpoint or health_cmd."""
        compose_content = dedent("""
            version: '3.8'
            services:
              no-healthcheck:
                image: test:latest
                ports:
                  - '8080:8080'
                healthcheck:
                  disable: true
        """)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        parser = ComposeParser()
        configs = parser.parse_file(compose_file)

        assert configs["no-healthcheck"].health_endpoint is None
        assert configs["no-healthcheck"].health_cmd is None


class TestDisplayNameFormatting:
    """Tests for display name formatting."""

    def test_ai_prefix_removed(self, tmp_path: Path) -> None:
        """AI prefix is removed from display name."""
        compose_content = dedent("""
            version: '3.8'
            services:
              ai-yolo26:
                image: yolo:latest
                ports:
                  - '8095:8095'
        """)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        parser = ComposeParser()
        configs = parser.parse_file(compose_file)

        # Should be "YOLO26" not "AI YOLO26"
        assert configs["ai-yolo26"].display_name == "YOLO26"

    def test_special_names_formatted_correctly(self, tmp_path: Path) -> None:
        """Special service names are formatted correctly."""
        parser = ComposeParser()

        assert parser._format_display_name("postgres") == "PostgreSQL"
        assert parser._format_display_name("redis") == "Redis"
        assert parser._format_display_name("ai-llm") == "LLM (Nemotron)"
        assert parser._format_display_name("ai-clip") == "CLIP"


class TestDurationParsing:
    """Tests for duration string parsing."""

    def test_parse_seconds(self) -> None:
        """Seconds are parsed correctly."""
        parser = ComposeParser()
        assert parser._parse_duration("30s") == 30
        assert parser._parse_duration("120s") == 120

    def test_parse_minutes(self) -> None:
        """Minutes are converted to seconds."""
        parser = ComposeParser()
        assert parser._parse_duration("2m") == 120
        assert parser._parse_duration("5m") == 300

    def test_parse_bare_number(self) -> None:
        """Bare numbers are treated as seconds."""
        parser = ComposeParser()
        assert parser._parse_duration("60") == 60

    def test_parse_none_returns_default(self) -> None:
        """None returns default value."""
        parser = ComposeParser()
        assert parser._parse_duration(None) == 30
