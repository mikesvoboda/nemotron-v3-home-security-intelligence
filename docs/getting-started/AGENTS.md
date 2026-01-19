# Getting Started Directory - Agent Guide

## Purpose

This directory contains quick start guides for getting the Home Security Intelligence system up and running. These guides focus on installation, first-run experience, and upgrading.

## Directory Contents

```
getting-started/
  AGENTS.md          # This file
  first-run.md       # First run guide
  installation.md    # Installation guide
  prerequisites.md   # System prerequisites
  upgrading.md       # Upgrade guide
```

## Key Files

### prerequisites.md

**Purpose:** System prerequisites and requirements.

**Topics Covered:**

- Hardware requirements (CPU, RAM, GPU)
- Operating system support
- Required software (Podman, Python, Node.js)
- Network requirements
- Camera compatibility (Foscam FTP)

**When to use:** Before starting installation, verifying system compatibility.

### installation.md

**Purpose:** Step-by-step installation guide.

**Topics Covered:**

- Clone repository
- Configure environment variables
- Start services with Podman
- Verify installation
- Initial configuration

**When to use:** Installing the system for the first time.

### first-run.md

**Purpose:** Guide for the first run experience.

**Topics Covered:**

- Accessing the dashboard
- Adding cameras
- Understanding the initial state
- Demo mode and sample data
- Basic navigation
- Next steps

**When to use:** After installation, getting oriented with the system.

### upgrading.md

**Purpose:** Guide for upgrading to new versions.

**Topics Covered:**

- Backup procedures before upgrade
- Pulling latest changes
- Database migrations
- Container updates
- Rollback procedures
- Breaking changes and migration notes

**When to use:** Upgrading to a new version of the system.

## Recommended Reading Order

1. **prerequisites.md** - Verify your system meets requirements
2. **installation.md** - Install the system
3. **first-run.md** - Get oriented with the dashboard
4. Continue to **user-guide/** for detailed usage documentation

## Target Audience

| Audience           | Needs                        | Primary Documents                 |
| ------------------ | ---------------------------- | --------------------------------- |
| **New Users**      | Quick setup and orientation  | All files                         |
| **Existing Users** | Upgrading to new version     | upgrading.md                      |
| **System Admins**  | Deployment and prerequisites | prerequisites.md, installation.md |

## Related Documentation

- **docs/AGENTS.md:** Documentation directory overview
- **docs/user-guide/:** User documentation
- **docs/operator/admin/:** Administrator documentation
- **docs/operator/ai-installation.md:** AI services setup
- **docs/operator/deployment/README.md:** Docker deployment details
- **docs/reference/config/env-reference.md:** Configuration reference
