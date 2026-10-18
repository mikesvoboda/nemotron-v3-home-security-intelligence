"""B3.3: the ordered, checked schema-upgrade path for databases that already exist.

`backend/core/database.py`'s `init_db()` calls `create_all`, which creates missing TABLES and
never alters an existing one. A database deployed last month therefore keeps whatever columns
and types it was created with, forever, no matter what `backend/models/` says today. This
package is the other half: recorded upgrades that bring an existing database forward.

The upgrade text lives in `docs/api/migrations/*.sql` and the ORDER lives in `registry.py`
(`UPGRADES`) -- the file set is not self-ordering, so a new upgrade is *listed* as well as
added, and an unlisted file is reported as drift by `python -m backend.migrations --status`.
Read `backend/migrations/AGENTS.md` before adding an upgrade.
"""

from backend.migrations.errors import UpgradeDriftError, UpgradeError
from backend.migrations.registry import UPGRADES, Upgrade
from backend.migrations.runner import (
    SCHEMA_TABLE,
    Record,
    UpgradeResult,
    apply_all,
    plan,
    upgrade_database,
)

__all__ = [
    "SCHEMA_TABLE",
    "UPGRADES",
    "Record",
    "Upgrade",
    "UpgradeDriftError",
    "UpgradeError",
    "UpgradeResult",
    "apply_all",
    "plan",
    "upgrade_database",
]
