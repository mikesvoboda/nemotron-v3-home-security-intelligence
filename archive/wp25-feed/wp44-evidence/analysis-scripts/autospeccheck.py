from typing import TYPE_CHECKING
from unittest.mock import create_autospec
if TYPE_CHECKING:
    from nonexistent_mod import MissingType

class Svc:
    async def m(self, session: MissingType) -> float | None: return None

try:
    create_autospec(Svc)
    print("autospec OK")
except Exception as e:
    print("autospec", type(e).__name__, e)
