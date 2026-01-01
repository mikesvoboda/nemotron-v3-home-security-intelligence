# Documentation Link Audit Report

> Generated: 2025-12-31

## Summary

| Metric                   | Count                                      |
| ------------------------ | ------------------------------------------ |
| **Total Markdown Files** | 118                                        |
| **Total Links Checked**  | 928                                        |
| **Internal Links**       | 743                                        |
| **External Links**       | 47                                         |
| **Anchor Links**         | 138                                        |
| **Remaining Issues**     | 15 (9 design doc examples, 6 orphan links) |

---

## Link Integrity: PASSED

All critical navigation links have been verified and fixed.

### Navigation Paths Validated

| Path                                                              | Status |
| ----------------------------------------------------------------- | ------ |
| README -> User Hub -> Dashboard Basics -> Back to Hub             | PASS   |
| README -> Operator Hub -> GPU Setup -> AI Services -> Back to Hub | PASS   |
| README -> Developer Hub -> Data Model -> Alerts -> Back to Hub    | PASS   |
| Any Hub -> Troubleshooting -> Back to Hub                         | PASS   |

---

## Fixes Applied

### 1. Developer Hub Navigation

- Added link to `developer/data-model.md` (detailed reference)
- Fixed link to `development/testing.md` (was pointing to wrong location)

### 2. API Reference Path Prefixes

- Fixed all `../backend/` paths to `../../backend/` in docs/api-reference/\*.md

### 3. Reference Document Back Links

- Fixed `docs/reference/config/env-reference.md` - links to Operator/Developer Hubs
- Fixed `docs/reference/config/risk-levels.md` - links to all three Hubs
- Fixed `docs/reference/glossary.md` - links to all three Hubs

### 4. Troubleshooting Back Links

- Added `docs/admin-guide/troubleshooting.md` back links to all Hubs
- Added troubleshooting link to User Hub "Need Help?" section

### 5. Image Placeholders

- Converted 16 image placeholder links to HTML comments
- Affects: `user/dashboard-basics.md`, `user/viewing-events.md`, `user/understanding-alerts.md`, `user/dashboard-settings.md`, `user-guide/*.md`

### 6. Developer Document Cross-Links

- Fixed `developer/risk-analysis.md` - error-handling.md -> batching-logic.md
- Fixed `developer/video.md` - Backend Services path prefix
- Fixed `developer/data-model.md` - AI Pipeline path
- Fixed `developer/alerts.md` - AI Pipeline path

---

## Known Issues (Non-Critical)

### Design Document Examples (9 links)

These are intentional template examples in planning documents, not navigation links:

| File                                                   | Link                           | Reason               |
| ------------------------------------------------------ | ------------------------------ | -------------------- |
| `plans/2025-12-31-documentation-overhaul-design.md`    | `path.md`, `../hub.md`         | Template examples    |
| `plans/2025-12-30-documentation-restructure-design.md` | `docs/README.md`, line numbers | Template examples    |
| `plans/2025-12-28-documentation-design.md`             | `plans/`, `decisions/`         | Directory references |

**Action:** None required - these are documentation design artifacts.

### Orphan Files (6 files)

Files not linked from any hub (design documents and standalone guides):

| File                                                        | Notes               |
| ----------------------------------------------------------- | ------------------- |
| `docs/plans/2025-12-31-system-performance-design.md`        | Recent design doc   |
| `docs/plans/2025-12-31-system-performance-plan.md`          | Recent plan doc     |
| `docs/plans/2025-12-31-documentation-overhaul-design.md`    | This audit's design |
| `docs/plans/2025-12-30-documentation-restructure-design.md` | Previous design     |
| `docs/plans/2025-12-30-ai-containerization-design.md`       | Recent design doc   |
| `docs/user-guide/logs-dashboard.md`                         | Standalone guide    |

**Action:** These are planning documents or standalone guides. They are intentionally not part of the hub navigation but are accessible via the `docs/plans/` directory.

---

## Hub Coverage: VERIFIED

### User Hub Links

- Dashboard guides: 8 documents
- Risk understanding: 4 documents
- Settings and help: 3 documents
- Total: 15+ spoke documents

### Operator Hub Links

- Installation: 3 documents
- Configuration: 4 documents
- Monitoring: 3 documents
- Total: 10+ spoke documents

### Developer Hub Links

- Architecture: 5 documents
- Development: 4 documents
- Deep dives: 6 documents
- API reference: 6 documents
- Total: 20+ spoke documents

---

## Cross-Hub References

Reference documents now link back to multiple hubs:

| Document                            | Links To                              |
| ----------------------------------- | ------------------------------------- |
| `reference/config/env-reference.md` | Operator Hub, Developer Hub           |
| `reference/config/risk-levels.md`   | User Hub, Operator Hub, Developer Hub |
| `reference/glossary.md`             | User Hub, Operator Hub, Developer Hub |
| `admin-guide/troubleshooting.md`    | User Hub, Operator Hub, Developer Hub |

---

## Maintenance Recommendations

1. **New Documents**: Always add a "Back to Hub" link at the bottom
2. **Image Placeholders**: Use HTML comments until screenshots are available
3. **Cross-References**: Link related documents in "See Also" sections
4. **Design Documents**: Keep in `docs/plans/` - these are development artifacts

---

## Validation Command

To re-run link validation:

```bash
python3 << 'EOF'
import re
from pathlib import Path

docs_dir = Path("docs")
link_pattern = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')
broken = []

for md in docs_dir.rglob("*.md"):
    content = md.read_text()
    for text, target in link_pattern.findall(content):
        if target.startswith(('http', 'mailto', '#')):
            continue
        path = target.split('#')[0].split(':')[0]
        if path and not (md.parent / path).resolve().exists():
            broken.append(f"{md}: [{text}]({target})")

print(f"Broken links: {len(broken)}")
for b in broken[:10]:
    print(f"  {b}")
EOF
```

---

Back to [Developer Hub](developer-hub.md)
