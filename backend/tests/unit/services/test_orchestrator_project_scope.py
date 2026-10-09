"""The orchestrator stays inside its own compose project (B1.6, D11).

The backend mounts the host's Podman socket, so its orchestrator can see, and
act on, every container on the machine. Two of its paths used to reach past
its own stack:

* discovery adopted any container whose NAME contained a configured pattern,
  whichever compose project it belonged to;
* network-isolation recovery stopped and REMOVED the container, then tried to
  recreate it with `podman-compose -f <file> up -d <service>`: no project, no env
  file, and (the shipped backend image has no `podman-compose`) a recreation that
  could not succeed, so the service stayed deleted.

These pins hold the replacement: discovery adopts only containers labelled with
the backend's own compose project (read from its own container at startup, and
nothing at all when that is unknown), and recovery restarts the service's own
container in place, never removing it, and raises an alert when it fails.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.schemas.services import ContainerServiceStatus, ServiceCategory
from backend.services.container_discovery import (
    COMPOSE_PROJECT_LABEL,
    ContainerDiscoveryService,
    resolve_own_compose_project,
)
from backend.services.container_orchestrator import ContainerOrchestrator
from backend.services.lifecycle_manager import LifecycleManager
from backend.services.service_registry import ManagedService

OWN = "hsi"
OTHER = "someone-elses-stack"


def _container(name: str, container_id: str, project: str | None) -> MagicMock:
    container = MagicMock()
    container.id = container_id
    container.name = name
    container.status = "running"
    container.image.tags = ["postgres:16-alpine"]
    container.labels = {} if project is None else {COMPOSE_PROJECT_LABEL: project}
    return container


def _docker(*containers: MagicMock) -> MagicMock:
    client = MagicMock()
    client.list_containers = AsyncMock(return_value=list(containers))
    return client


def _service(container_id: str = "own-pg") -> ManagedService:
    return ManagedService(
        name="postgres",
        display_name="PostgreSQL",
        container_id=container_id,
        image="postgres:16-alpine",
        port=5432,
        health_endpoint=None,
        health_cmd="pg_isready -U security",
        category=ServiceCategory.INFRASTRUCTURE,
        status=ContainerServiceStatus.RUNNING,
        enabled=True,
        failure_count=0,
        restart_count=0,
    )


class TestDiscoveryAdoptsOnlyItsOwnProject:
    async def test_of_two_matching_containers_only_the_own_project_one_is_adopted(self) -> None:
        """The package's first test: both names match the `postgres` pattern, one is in
        the backend's compose project and one in another; discovery adopts the first."""
        own = _container(f"{OWN}-postgres-1", "own-pg", OWN)
        other = _container(f"{OTHER}-postgres-1", "other-pg", OTHER)

        discovered = await ContainerDiscoveryService(_docker(own, other)).discover_all(project=OWN)

        assert [s.container_id for s in discovered] == ["own-pg"]

    async def test_a_container_with_no_project_label_is_not_adopted(self) -> None:
        stray = _container("postgres", "stray-pg", None)

        discovered = await ContainerDiscoveryService(_docker(stray)).discover_all(project=OWN)

        assert discovered == []

    async def test_with_no_project_known_it_adopts_nothing_and_says_why(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        own = _container(f"{OWN}-postgres-1", "own-pg", OWN)
        docker = _docker(own)

        discovered = await ContainerDiscoveryService(docker).discover_all(project=None)

        assert discovered == []
        docker.list_containers.assert_not_called()  # it never even looks across projects
        assert "compose project" in caplog.text


class TestTheBackendReadsItsOwnProject:
    async def test_the_project_is_the_label_on_the_backends_own_container(self) -> None:
        docker = MagicMock()
        docker.get_container = AsyncMock(return_value=_container("hsi-backend-1", "self", OWN))

        project = await resolve_own_compose_project(docker, hostname="self")

        assert project == OWN
        docker.get_container.assert_awaited_once_with("self")

    @pytest.mark.parametrize(
        "own_container",
        [None, _container("not-compose", "self", None)],
        ids=["own-container-not-found", "no-project-label"],
    )
    async def test_an_unknown_project_is_none_and_logged(
        self, own_container: MagicMock | None, caplog: pytest.LogCaptureFixture
    ) -> None:
        docker = MagicMock()
        docker.get_container = AsyncMock(return_value=own_container)

        assert await resolve_own_compose_project(docker, hostname="self") is None
        assert "compose project" in caplog.text


class TestTheOrchestratorScopesDiscovery:
    async def test_start_discovers_with_the_backends_own_project(self) -> None:
        docker = AsyncMock()
        docker.connect = AsyncMock(return_value=True)
        docker.get_container = AsyncMock(return_value=_container("hsi-backend-1", "self", OWN))
        settings = MagicMock(enabled=True, compose_file=None)
        orchestrator = ContainerOrchestrator(
            docker_client=docker,
            redis_client=AsyncMock(get=AsyncMock(return_value=None)),
            settings=settings,
        )

        with (
            patch(
                "backend.services.container_discovery.socket.gethostname",
                return_value="self",
                autospec=True,
            ),
            patch.object(
                orchestrator._discovery_service, "discover_all", return_value=[], autospec=True
            ) as discover,
            patch("backend.services.container_orchestrator.HealthMonitor", autospec=True),
        ):
            await orchestrator.start()

        discover.assert_awaited_once_with(project=OWN)


class TestRecoveryStaysInPlace:
    async def test_recovery_restarts_the_own_container_and_removes_nothing(self) -> None:
        """The package's second test, under the restart-in-place mechanism: recovery acts
        on the service's own container (the one scoped discovery found) and nothing else,
        keeps it (so its project and the stack's configuration stay exactly as compose made
        it), and never shells out to compose."""
        docker = MagicMock()
        docker.restart_container = AsyncMock(return_value=True)
        docker.remove_container = AsyncMock()
        docker.stop_container = AsyncMock()
        manager = LifecycleManager(
            registry=MagicMock(persist_state=AsyncMock()), docker_client=docker
        )

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=AssertionError("no compose call"),
            autospec=True,
        ):
            assert await manager.recover_in_place(_service("own-pg")) is True

        docker.restart_container.assert_awaited_once_with("own-pg", timeout=10)
        docker.remove_container.assert_not_called()
        docker.stop_container.assert_not_called()

    async def test_a_failed_recovery_removes_nothing_restores_and_alerts(self) -> None:
        """The package's third test: when the restart fails, the container is still there,
        recovery tries to bring it back, and an alert goes out."""
        docker = MagicMock()
        docker.restart_container = AsyncMock(return_value=False)
        docker.start_container = AsyncMock(return_value=True)
        docker.remove_container = AsyncMock()
        alert = AsyncMock()
        manager = LifecycleManager(
            registry=MagicMock(persist_state=AsyncMock()),
            docker_client=docker,
            on_recovery_failed=alert,
        )
        service = _service("own-pg")

        assert await manager.recover_in_place(service) is False

        docker.remove_container.assert_not_called()
        docker.start_container.assert_awaited_once_with("own-pg")  # the restore attempt
        alert.assert_awaited_once_with(service)

    async def test_the_orchestrator_broadcasts_a_failed_recovery(self) -> None:
        docker = AsyncMock()
        docker.restart_container = AsyncMock(return_value=False)
        docker.start_container = AsyncMock(return_value=False)
        broadcast = AsyncMock(return_value=1)
        orchestrator = ContainerOrchestrator(
            docker_client=docker,
            redis_client=AsyncMock(get=AsyncMock(return_value=None)),
            settings=MagicMock(enabled=True, compose_file=None),
            broadcast_fn=broadcast,
        )
        orchestrator._lifecycle_manager = LifecycleManager(
            registry=orchestrator._registry,
            docker_client=docker,
            on_recovery_failed=orchestrator._on_recovery_failed,
        )
        service = _service("own-pg")
        orchestrator._registry.register(service)

        await orchestrator._on_network_isolation(service)

        docker.remove_container.assert_not_called()
        messages = [call.args[0]["message"] for call in broadcast.await_args_list]
        assert any("Recovery failed" in m for m in messages)
