from __future__ import annotations
from typing import TYPE_CHECKING
from unittest.mock import create_autospec
if TYPE_CHECKING:
    from nonexistent_mod import MissingType

class Svc:
    async def m(self, session: MissingType) -> float | None: return None

try:
    create_autospec(Svc)
    print("future-import autospec OK")
except Exception as e:
    print("future-import autospec", type(e).__name__, e)
