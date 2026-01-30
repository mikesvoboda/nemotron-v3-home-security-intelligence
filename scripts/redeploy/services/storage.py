"""Container storage management (prune, reset)."""

from pathlib import Path

from scripts.redeploy.core import output
from scripts.redeploy.core.runtime import ContainerRuntime
from scripts.redeploy.models import DeployConfig


class StorageManager:
    """Manage container storage (images, volumes, build cache)."""

    def __init__(self, runtime: ContainerRuntime, config: DeployConfig):
        """Initialize storage manager.

        Args:
            runtime: Container runtime instance
            config: Deployment configuration
        """
        self.runtime = runtime
        self.config = config

    def prune_build_artifacts(self) -> None:
        """Prune dangling images and build cache.

        This is the standard post-build cleanup to prevent disk exhaustion.
        """
        output.header("Pruning Build Artifacts")

        if self.config.dry_run:
            output.dry_run("Would prune dangling images and build cache")
            return

        # Prune dangling images
        output.step("Pruning dangling images...")
        self.runtime.prune_images(all=False, force=True)
        output.success("Dangling images pruned")

        # Prune build cache
        output.step("Pruning build cache...")
        self.runtime.prune_builder(force=True)
        output.success("Build cache pruned")

        # For Podman: additional cleanup
        if self.runtime.is_podman:
            output.step("Clearing orphaned layers...")
            # Check if any containers are running
            containers = self.runtime.ps()
            if not containers:
                # Safe to do more aggressive cleanup
                self.runtime.prune_images(all=True, force=True)
                output.success("All unused images pruned")

            # Final system prune
            self.runtime.prune_system(all=False, volumes=False, force=True)

        # Verify storage health
        output.step("Verifying storage health...")
        self._verify_storage_health()

    def reset_storage(self) -> None:
        """Nuclear option: completely reset container storage.

        WARNING: This removes ALL images, containers, volumes, and cache.
        Use only when storage is severely corrupted.
        """
        output.header("Resetting Container Storage")

        if self.config.dry_run:
            output.dry_run("Would reset all container storage")
            return

        # Show warning
        output.nuclear_warning(
            items=[
                "ALL container images (will need to rebuild/re-pull)",
                "ALL stopped containers",
                "ALL build cache",
                "ALL dangling volumes",
            ],
            timeout=5,
        )

        # Stop all containers
        output.step("Stopping all containers...")
        result = self.runtime.process.run(
            [self.runtime.cmd, "stop", "-a"],
            check=False,
            capture=True,
        )
        self.runtime.process.run(
            [self.runtime.cmd, "rm", "-f", "-a"],
            check=False,
            capture=True,
        )

        # Remove all images
        output.step("Removing all images...")
        self.runtime.process.run(
            [self.runtime.cmd, "rmi", "-f", "-a"],
            check=False,
            capture=True,
        )

        # Prune everything
        output.step("Pruning all storage...")
        self.runtime.prune_system(all=True, volumes=True, force=True)

        # Podman-specific: reset storage backend
        if self.runtime.is_podman:
            output.step("Resetting Podman storage backend...")
            self._reset_podman_storage()

        output.success("Container storage reset complete")
        output.info("All images will need to be rebuilt or re-pulled")

    def _reset_podman_storage(self) -> None:
        """Reset Podman storage backend for severe corruption."""
        # Try buildah cleanup first
        self.runtime.process.run(
            ["buildah", "rm", "-a"],
            check=False,
            capture=True,
        )
        self.runtime.process.run(
            ["buildah", "prune", "-a", "-f"],
            check=False,
            capture=True,
        )

        # Try podman system reset
        result = self.runtime.process.run(
            [self.runtime.cmd, "system", "reset", "--force"],
            check=False,
            capture=True,
        )

        if not result.success:
            output.warn("podman system reset failed, trying manual cleanup...")
            self._manual_storage_cleanup()

    def _manual_storage_cleanup(self) -> None:
        """Manual cleanup of storage layers when reset fails."""
        # Get storage root
        result = self.runtime.process.run(
            [self.runtime.cmd, "info", "--format", "{{.Store.GraphRoot}}"],
            check=False,
            capture=True,
        )

        if result.success and result.stdout.strip():
            storage_root = result.stdout.strip()
        else:
            storage_root = str(Path("~/.local/share/containers/storage").expanduser())

        import shutil

        storage_path = Path(storage_root)

        # Clear overlay layers
        overlay_layers = storage_path / "overlay-layers"
        if overlay_layers.exists():
            output.step(f"Clearing overlay layers at {storage_root}...")
            try:
                shutil.rmtree(overlay_layers)
                overlay_layers.mkdir(exist_ok=True)
            except PermissionError:
                output.warn("Could not clear overlay-layers (permission denied)")

        overlay_dir = storage_path / "overlay"
        if overlay_dir.exists():
            try:
                shutil.rmtree(overlay_dir)
                overlay_dir.mkdir(exist_ok=True)
            except PermissionError:
                output.warn("Could not clear overlay dir (permission denied)")

    def _verify_storage_health(self) -> bool:
        """Verify storage is in a healthy state.

        Returns:
            True if storage is healthy
        """
        result = self.runtime.process.run(
            [self.runtime.cmd, "system", "df"],
            check=False,
            capture=True,
        )

        if result.success:
            # Try to get image size
            df_result = self.runtime.process.run(
                [self.runtime.cmd, "system", "df", "--format", "{{.ImagesSize}}"],
                check=False,
                capture=True,
            )
            if df_result.success and df_result.stdout.strip():
                output.info(f"Images: {df_result.stdout.strip().split()[0]}")

            output.success("Storage is healthy")
            return True
        else:
            output.warn("Could not verify storage health")
            return False

    def get_disk_usage(self) -> dict[str, str]:
        """Get disk usage summary.

        Returns:
            Dict with images, containers, volumes sizes
        """
        usage: dict[str, str] = {}

        result = self.runtime.process.run(
            [self.runtime.cmd, "system", "df", "--format", "json"],
            check=False,
            capture=True,
        )

        if result.success and result.stdout.strip():
            import json

            try:
                data = json.loads(result.stdout)
                if isinstance(data, list) and data:
                    for item in data:
                        type_name = item.get("Type", "")
                        size = item.get("Size", item.get("TotalSize", "0"))
                        usage[type_name] = str(size)
            except json.JSONDecodeError:
                pass

        return usage
