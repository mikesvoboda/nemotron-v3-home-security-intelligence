# Getting Started

Welcome to Home Security Intelligence. This section guides you from zero to a running system.

---

## Quick Navigation

### Technical Setup (for operators/installers)

| Step | Guide                             | Description                                  |
| ---- | --------------------------------- | -------------------------------------------- |
| 1    | [Prerequisites](prerequisites.md) | Verify hardware and software requirements    |
| 2    | [Installation](installation.md)   | Clone, setup environment, download AI models |
| 3    | [First Run](first-run.md)         | Start the system and verify everything works |
| 4    | [Upgrading](upgrading.md)         | Update to new versions                       |

### End User Guides

| Guide                          | Description                                              |
| ------------------------------ | -------------------------------------------------------- |
| [Quick Start](quick-start.md)  | Non-technical intro - what the system does and basic use |
| [Product Tour](tour.md)        | Interactive walkthrough and first-time setup             |

---

## Recommended Path

**New users:** Follow steps 1-3 in order. The entire process takes approximately 30 minutes (plus model download time).

**Existing users:** Jump directly to [Upgrading](upgrading.md) for version updates.

---

## What You Will Need

- NVIDIA GPU with 8GB+ VRAM (RTX 3060 or better)
- Python 3.14+, Node.js 20.19+
- Docker or Podman
- Foscam cameras (or compatible FTP-uploading cameras)

See [Prerequisites](prerequisites.md) for complete requirements and verification commands.

---

## Next Steps After Setup

Once your system is running, continue to the guide that matches your role:

| Role           | Hub                              | Focus                                 |
| -------------- | -------------------------------- | ------------------------------------- |
| **End Users**  | [User Guide](../user/)           | Dashboard usage, cameras, alerts      |
| **Developers** | [Developer Guide](../developer/) | Contributing, testing, architecture   |
| **Operators**  | [Operator Guide](../operator/)   | Deployment, monitoring, configuration |
