from typing import TYPE_CHECKING
import inspect
if TYPE_CHECKING:
    from nonexistent_mod import MissingType

def unquoted(x: MissingType | None = None): pass
def quoted(x: "MissingType | None" = None): pass

for name, f in [("unquoted", unquoted), ("quoted", quoted)]:
    try:
        inspect.signature(f)
        print(name, "OK")
    except Exception as e:
        print(name, type(e).__name__, e)
import sys; print("py", sys.version_info[:3])
