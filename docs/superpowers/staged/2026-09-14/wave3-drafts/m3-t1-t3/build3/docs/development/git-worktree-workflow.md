# Git Worktree Workflow for Parallel Development

Git worktrees allow you to work on multiple branches simultaneously in separate directories, without the need to stash changes or create multiple clones. This is particularly useful for:

- Working on a hotfix while a feature is in progress
- Running tests on one branch while developing on another
- Comparing implementations across branches
- Code review while continuing development

## Prerequisites

Git worktrees are built into Git (v2.5+). No additional installation required.

```bash
# Verify your Git version
git --version  # Should be 2.5 or higher
```

## Quick Start

### Create a Worktree for a New Feature

```bash
# From the main repository directory
git worktree add ../security-dashboard-feat-camera-api feat/camera-api

# This creates:
# - A new directory: ../security-dashboard-feat-camera-api
# - Checks out the feat/camera-api branch (creates it if it doesn't exist)
```

### Create a Worktree from an Existing Branch

```bash
# Checkout an existing branch in a new worktree
git worktree add ../security-dashboard-fix-websocket fix/websocket-reconnection

# Or create from a remote branch
git worktree add ../security-dashboard-pr-review origin/feat/alerts-api
```

### Create a Worktree for Main Branch

```bash
# Useful for running tests against main while developing
git worktree add ../security-dashboard-main main
```

## Directory Structure

We recommend organizing worktrees in a sibling directory pattern:

```
~/projects/
├── nemotron-v3-home-security/          # Main repository (usually on main)
├── security-dashboard-feat-api/         # Feature worktree
├── security-dashboard-fix-bug/          # Bugfix worktree
└── security-dashboard-review/           # PR review worktree
```

Or use a dedicated worktrees directory:

```
~/projects/nemotron-v3-home-security/
├── .git/                                # Git directory
├── .worktrees/                          # Local worktrees (gitignored)
│   ├── feat-camera-api/
│   └── fix-websocket/
└── ... (main working directory)
```

## Setting Up a New Worktree

When you create a new worktree, you'll need to set up the development environment:

```bash
# Navigate to the new worktree
cd ../security-dashboard-feat-api

# Install Python dependencies
uv sync --extra dev

# Install frontend dependencies
cd frontend && npm ci && cd ..

# Install pre-commit hooks (shared across worktrees)
pre-commit install
pre-commit install --hook-type commit-msg
pre-commit install --hook-type pre-push
```

### Helper Script

Use the provided script to create worktrees with setup:

```bash
# Create a worktree with full setup
./scripts/create-worktree.sh feat/new-feature

# The script will:
# 1. Create the worktree in ../<repo>-<branch>/
# 2. Install Python dependencies (uv sync)
# 3. Install Node dependencies (npm ci)
# 4. Install pre-commit hooks
```

## Managing Worktrees

### List All Worktrees

```bash
git worktree list
# /home/user/projects/nemotron-v3-home-security         abc1234 [main]
# /home/user/projects/security-dashboard-feat-api       def5678 [feat/camera-api]
# /home/user/projects/security-dashboard-fix-websocket  ghi9012 [fix/websocket]
```

### Remove a Worktree

```bash
# First, make sure all changes are committed/pushed
cd ../security-dashboard-feat-api
git status

# Remove the worktree (from main repo or any worktree)
git worktree remove ../security-dashboard-feat-api

# Or force remove if there are uncommitted changes
git worktree remove --force ../security-dashboard-feat-api
```

### Prune Stale Worktrees

If a worktree directory is manually deleted, clean up the Git references:

```bash
git worktree prune
```

### Move a Worktree

```bash
git worktree move ../old-path ../new-path
```

## Common Workflows

### Workflow 1: Feature Development with Hotfix

You're working on a feature when an urgent bug needs fixing:

```bash
# Currently working on feat/camera-streaming in main directory
# Create a hotfix worktree
git worktree add ../security-hotfix hotfix/critical-security-fix

# Work on the hotfix
cd ../security-hotfix
# ... make changes, test, commit ...
git push -u origin hotfix/critical-security-fix

# Return to feature work
cd ../nemotron-v3-home-security
# Continue feature development
```

### Workflow 2: Parallel Test Runs

Run tests on main while developing:

```bash
# Create a worktree on main
git worktree add ../security-main main

# In terminal 1: Run tests on main
cd ../security-main
./scripts/validate.sh

# In terminal 2: Continue development
cd ../nemotron-v3-home-security
# ... develop and commit ...
```

### Workflow 3: Code Review

Review a PR while continuing your work:

```bash
# Create a worktree for the PR branch
git fetch origin
git worktree add ../security-pr-review origin/feat/new-alerts

# Review the code
cd ../security-pr-review
# Run tests, inspect code, etc.

# When done, remove the worktree
cd ../nemotron-v3-home-security
git worktree remove ../security-pr-review
```

### Workflow 4: A/B Comparison

Compare implementations across branches:

```bash
# Create worktrees for both approaches
git worktree add ../security-approach-a feat/approach-a
git worktree add ../security-approach-b feat/approach-b

# Run benchmarks on both
cd ../security-approach-a && ./scripts/benchmark.sh
cd ../security-approach-b && ./scripts/benchmark.sh

# Compare results
```

## Worktree-Specific Considerations

### Shared Git Configuration

Git configuration is shared across all worktrees (they share the same `.git` directory). This includes:

- Git hooks (pre-commit, commit-msg, pre-push)
- Git config settings
- Remotes

### Separate Node Modules

Each worktree has its own `node_modules` directory. This means:

- You need to run `npm ci` in each worktree
- Different branches can have different dependency versions
- Disk space is used for each worktree's dependencies

### Shared Python Virtual Environment (Optional)

You can share the Python virtual environment across worktrees:

```bash
# In new worktree, link to existing venv
ln -s /path/to/main/.venv .venv

# Or create a fresh venv for isolation
uv venv .venv
uv sync --extra dev
```

### Database Considerations

If running multiple worktrees simultaneously with database access:

- Use different database names or ports per worktree
- Or ensure only one worktree runs the database at a time

```bash
# Set different database for a worktree
export DATABASE_URL="postgresql://localhost:5432/security_worktree_1"
```

## Tips and Best Practices

1. **Naming Convention**: Use descriptive worktree names that indicate the branch purpose

   ```bash
   git worktree add ../security-NEM-123-camera-api feat/NEM-123-camera-api
   ```

2. **Clean Up Regularly**: Remove worktrees when done to save disk space

   ```bash
   git worktree list  # See what's active
   git worktree prune  # Clean up stale references
   ```

3. **Don't Checkout Same Branch**: Git prevents checking out the same branch in multiple worktrees. Use different branches or detached HEAD if needed.

4. **Commit Before Switching**: Always commit or stash changes before switching focus between worktrees.

5. **Shared Secrets**: Be careful with `.env` files - each worktree may need its own configuration.

6. **IDE Configuration**: Configure your IDE to handle multiple project roots or use workspace features.

## Troubleshooting

### "fatal: '<branch>' is already checked out"

A branch can only be checked out in one worktree at a time:

```bash
# Find where the branch is checked out
git worktree list | grep <branch>

# Either switch branches in that worktree or remove it
```

### Worktree directory exists but not tracked

If you manually created a directory with the worktree name:

```bash
rm -rf ../security-worktree  # Remove the directory
git worktree add ../security-worktree <branch>  # Create properly
```

### Stale worktree references

After manually deleting a worktree directory:

```bash
git worktree prune
```

### Pre-commit hooks not working in worktree

Hooks are shared but may need reinstallation:

```bash
cd ../new-worktree
pre-commit install
pre-commit install --hook-type commit-msg
```

## Related Documentation

- [Git Worktree Documentation](https://git-scm.com/docs/git-worktree)
- [Development Setup Guide](./setup.md)
- [Contributing Guide](./contributing.md)
