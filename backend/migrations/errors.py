"""B3.3: the exception types the upgrade path raises.

Their own module so `sql.py`, `checks.py` and `runner.py` can all use them without any of them
importing another (the cycle would be: registry needs the SQL lexer, the lexer needs to fail,
failing needs the type).

None of these is an `AppException` subclass on purpose: `backend/core/error_handler.py` maps
those to HTTP responses, and this code runs at startup and from a CLI, where a traceback is the
point and an HTTP status is nonsense.
"""


class UpgradeError(RuntimeError):
    """The upgrade path cannot proceed: missing file, or a failing statement."""


class UpgradeDriftError(UpgradeError):
    """The registry and a database's records disagree about history.

    Two distinct drifts, both fatal: a recorded id the registry no longer lists (an applied
    upgrade was deleted or renamed, so the sequence that database was built from is no longer
    expressible), or a recorded checksum that differs from the file (a shipped upgrade was
    edited after some database applied it). Both mean the history is no longer reproducible, so
    the runner refuses to guess. This is the failure that justifies recording a checksum at all:
    without it, editing a shipped upgrade is invisible until someone upgrades a database that
    never had the original.
    """


class UpgradeNotRegisteredError(RuntimeError):
    """A CHECK was written for an id the registry does not list (import-time config error).

    Not an `UpgradeError`: no database is involved. It fires at import, before any connection,
    and its whole job is to turn a rename in the registry into a red import instead of a
    silently unchecked upgrade.
    """
