"""Unit tests for orchestrator enums module.

Tests that enums are properly re-exported from the API schemas.
"""


class TestServiceCategoryEnum:
    """Tests for ServiceCategory enum re-export."""

    def test_import_from_orchestrator(self) -> None:
        """ServiceCategory can be imported from orchestrator module."""
        from backend.services.orchestrator import ServiceCategory

        assert ServiceCategory is not None

    def test_import_from_enums(self) -> None:
        """ServiceCategory can be imported from orchestrator.enums."""
        from backend.services.orchestrator.enums import ServiceCategory

        assert ServiceCategory is not None

    def test_has_infrastructure_value(self) -> None:
        """ServiceCategory has INFRASTRUCTURE value."""
        from backend.services.orchestrator import ServiceCategory

        assert hasattr(ServiceCategory, "INFRASTRUCTURE")

    def test_has_ai_value(self) -> None:
        """ServiceCategory has AI value."""
        from backend.services.orchestrator import ServiceCategory

        assert hasattr(ServiceCategory, "AI")

    def test_has_monitoring_value(self) -> None:
        """ServiceCategory has MONITORING value."""
        from backend.services.orchestrator import ServiceCategory

        assert hasattr(ServiceCategory, "MONITORING")

    def test_same_as_api_schemas(self) -> None:
        """ServiceCategory is the same class as in api.schemas.services."""
        from backend.api.schemas.services import ServiceCategory as APIServiceCategory
        from backend.services.orchestrator import ServiceCategory

        assert ServiceCategory is APIServiceCategory


class TestContainerServiceStatusEnum:
    """Tests for ContainerServiceStatus enum re-export."""

    def test_import_from_orchestrator(self) -> None:
        """ContainerServiceStatus can be imported from orchestrator module."""
        from backend.services.orchestrator import ContainerServiceStatus

        assert ContainerServiceStatus is not None

    def test_import_from_enums(self) -> None:
        """ContainerServiceStatus can be imported from orchestrator.enums."""
        from backend.services.orchestrator.enums import ContainerServiceStatus

        assert ContainerServiceStatus is not None

    def test_has_running_value(self) -> None:
        """ContainerServiceStatus has RUNNING value."""
        from backend.services.orchestrator import ContainerServiceStatus

        assert hasattr(ContainerServiceStatus, "RUNNING")

    def test_has_stopped_value(self) -> None:
        """ContainerServiceStatus has STOPPED value."""
        from backend.services.orchestrator import ContainerServiceStatus

        assert hasattr(ContainerServiceStatus, "STOPPED")

    def test_has_unhealthy_value(self) -> None:
        """ContainerServiceStatus has UNHEALTHY value."""
        from backend.services.orchestrator import ContainerServiceStatus

        assert hasattr(ContainerServiceStatus, "UNHEALTHY")

    def test_has_disabled_value(self) -> None:
        """ContainerServiceStatus has DISABLED value."""
        from backend.services.orchestrator import ContainerServiceStatus

        assert hasattr(ContainerServiceStatus, "DISABLED")

    def test_has_not_found_value(self) -> None:
        """ContainerServiceStatus has NOT_FOUND value."""
        from backend.services.orchestrator import ContainerServiceStatus

        assert hasattr(ContainerServiceStatus, "NOT_FOUND")

    def test_same_as_api_schemas(self) -> None:
        """ContainerServiceStatus is the same class as in api.schemas.services."""
        from backend.api.schemas.services import (
            ContainerServiceStatus as APIContainerServiceStatus,
        )
        from backend.services.orchestrator import ContainerServiceStatus

        assert ContainerServiceStatus is APIContainerServiceStatus
