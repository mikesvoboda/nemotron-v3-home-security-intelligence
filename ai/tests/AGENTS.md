# AI Tests Directory

## Test Files

| File                     | Purpose                                                                         |
| ------------------------ | ------------------------------------------------------------------------------- |
| `test_module_hygiene.py` | Collection-hygiene guards for the `ai/` tier (import-time poisoning and shadow) |

## Running Tests

```bash
uv run pytest ai/tests/test_module_hygiene.py -q
```
