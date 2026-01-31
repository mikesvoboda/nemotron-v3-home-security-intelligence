"""Database operations (migrations, seeding)."""

import random

from scripts.redeploy.core import output
from scripts.redeploy.core.process import ProcessRunner
from scripts.redeploy.models import DeployConfig


class DatabaseManager:
    """Manage database operations."""

    def __init__(self, process: ProcessRunner, config: DeployConfig):
        """Initialize database manager.

        Args:
            process: Process runner instance
            config: Deployment configuration
        """
        self.process = process
        self.config = config

    def run_migrations(self) -> bool:
        """Initialize database schema.

        Note: We use a flat schema without Alembic migrations.
        The backend creates tables on startup via SQLAlchemy metadata.create_all().
        This simplifies deployment - no migration history to maintain.

        Returns:
            True always (schema created by backend on startup)
        """
        output.step("Database schema will be created by backend on startup...")
        output.success("Using flat schema (no migrations)")
        return True

    def stamp_head(self) -> bool:
        """No-op: migrations disabled.

        Returns:
            True always
        """
        # No-op: using flat schema without Alembic
        return True

    def seed_database(self) -> bool:
        """Seed database with initial data.

        Returns:
            True if seeding successful
        """
        output.step("Seeding database...")

        if self.config.dry_run:
            output.dry_run("Would run seed script")
            return True

        seed_script = self.config.project_root / "scripts" / "seed-events.py"
        if not seed_script.exists():
            output.warn("Seed script not found")
            return True

        result = self.process.run(
            ["uv", "run", "python", str(seed_script)],
            check=False,
            cwd=self.config.project_root,
        )

        if result.success:
            output.success("Database seeded")
            return True
        else:
            output.warn("Seeding had errors (may be non-fatal)")
            return True

    def seed_files(self, count: int) -> bool:
        """Touch random files to trigger AI pipeline.

        Args:
            count: Number of files to touch

        Returns:
            True if files touched successfully
        """
        if count <= 0:
            return True

        output.step(f"Seeding {count} files to trigger AI pipeline...")

        if self.config.dry_run:
            output.dry_run(f"Would touch {count} random image files")
            return True

        foscam_path = self.config.foscam_base_path
        if not foscam_path.exists():
            output.warn(f"Foscam path not found: {foscam_path}")
            return False

        # Find image files
        image_extensions = {".jpg", ".jpeg", ".png"}
        image_files = [
            f
            for f in foscam_path.rglob("*")
            if f.is_file() and f.suffix.lower() in image_extensions
        ]

        if not image_files:
            output.warn("No image files found to seed")
            return False

        # Select random files
        files_to_touch = random.sample(image_files, min(count, len(image_files)))

        touched = 0
        for file_path in files_to_touch:
            try:
                file_path.touch()
                touched += 1
            except PermissionError:
                pass

        output.success(f"Touched {touched} files")
        return True
