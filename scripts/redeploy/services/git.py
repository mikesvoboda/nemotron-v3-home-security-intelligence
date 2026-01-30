"""Git operations for deployment."""

from scripts.redeploy.core import output
from scripts.redeploy.core.process import ProcessRunner
from scripts.redeploy.models import DeployConfig


class GitManager:
    """Manage git operations for deployment."""

    def __init__(self, process: ProcessRunner, config: DeployConfig):
        """Initialize git manager.

        Args:
            process: Process runner instance
            config: Deployment configuration
        """
        self.process = process
        self.config = config

    def update_to_main(self) -> bool:
        """Update to latest origin/main.

        Returns:
            True if updated successfully
        """
        output.header("Updating to Latest Code")

        if self.config.dry_run:
            output.dry_run("Would fetch and merge origin/main")
            return True

        # Fetch latest
        output.step("Fetching from origin...")
        result = self.process.run(
            ["git", "fetch", "origin", "main"],
            check=False,
            cwd=self.config.project_root,
        )

        if not result.success:
            output.warn("Failed to fetch from origin")
            return False

        # Check for uncommitted changes
        status_result = self.process.run(
            ["git", "status", "--porcelain"],
            check=False,
            cwd=self.config.project_root,
        )

        if status_result.stdout.strip():
            output.step("Stashing local changes...")
            stash_result = self.process.run(
                ["git", "stash", "--include-untracked"],
                check=False,
                cwd=self.config.project_root,
            )
            if not stash_result.success:
                output.warn("Failed to stash changes")

        # Merge origin/main
        output.step("Merging origin/main...")
        merge_result = self.process.run(
            ["git", "merge", "origin/main", "--ff-only"],
            check=False,
            cwd=self.config.project_root,
        )

        if merge_result.success:
            output.success("Updated to latest origin/main")
            return True
        else:
            output.warn("Could not fast-forward merge")
            output.info("You may have local commits - continuing with current code")
            return True  # Not a fatal error

    def get_current_branch(self) -> str:
        """Get current git branch name.

        Returns:
            Branch name
        """
        result = self.process.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=False,
            cwd=self.config.project_root,
        )
        return result.stdout.strip() if result.success else "unknown"

    def get_current_commit(self) -> str:
        """Get current commit hash (short).

        Returns:
            Short commit hash
        """
        result = self.process.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=False,
            cwd=self.config.project_root,
        )
        return result.stdout.strip() if result.success else "unknown"

    def is_clean(self) -> bool:
        """Check if working directory is clean.

        Returns:
            True if no uncommitted changes
        """
        result = self.process.run(
            ["git", "status", "--porcelain"],
            check=False,
            cwd=self.config.project_root,
        )
        return not bool(result.stdout.strip())
