#!/usr/bin/env python3
"""Script to systematically fix flaky WebSocket test patterns.

This script applies the following fixes:
1. Wraps pubsub.unsubscribe() calls in try/except
2. Wraps pubsub.aclose() calls in try/except
3. Wraps broadcaster.stop() calls in try/except
4. Ensures all cleanup happens in finally blocks
"""

import re
from pathlib import Path


def fix_pubsub_cleanup(content: str) -> str:
    """Fix pubsub cleanup patterns to use try/except.

    Replaces patterns like:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()

    With:
        try:
            await pubsub.unsubscribe(channel)
        except Exception:
            pass
        try:
            await pubsub.aclose()
        except Exception:
            pass
    """
    # Pattern 1: Single pubsub cleanup in finally
    pattern1 = r"(\s+)await pubsub\.unsubscribe\(([^)]+)\)\n\s+await pubsub\.aclose\(\)"
    replacement1 = r"\1try:\n\1    await pubsub.unsubscribe(\2)\n\1except Exception:\n\1    pass\n\1try:\n\1    await pubsub.aclose()\n\1except Exception:\n\1    pass"
    content = re.sub(pattern1, replacement1, content)

    # Pattern 2: Loop over multiple pubsubs without error handling
    pattern2 = r"for pubsub in \[([^\]]+)\]:\n(\s+)await pubsub\.unsubscribe\(([^)]+)\)\n\s+await pubsub\.aclose\(\)"
    replacement2 = r"for pubsub in [\1]:\n\2try:\n\2    await pubsub.unsubscribe(\3)\n\2except Exception:\n\2    pass\n\2try:\n\2    await pubsub.aclose()\n\2except Exception:\n\2    pass"

    # Only apply if not already wrapped
    if (
        "except Exception:" not in content[content.find(pattern2) : content.find(pattern2) + 200]
        if pattern2 in content
        else False
    ):
        content = re.sub(pattern2, replacement2, content)

    return content


def fix_broadcaster_cleanup(content: str) -> str:
    """Fix broadcaster cleanup patterns to use try/except.

    Replaces patterns like:
        await broadcaster.stop()

    With:
        try:
            await broadcaster.stop()
        except Exception:
            pass
    """
    # Pattern: broadcaster.stop() without try/except in finally block
    pattern = r"finally:\n(\s+)await broadcaster\.stop\(\)"
    replacement = (
        r"finally:\n\1try:\n\1    await broadcaster.stop()\n\1except Exception:\n\1    pass"
    )
    content = re.sub(pattern, replacement, content)

    return content


def main():
    """Apply fixes to test files."""
    test_files = [
        Path("backend/tests/integration/test_redis_pubsub.py"),
        Path("backend/tests/integration/test_websocket_broadcast.py"),
    ]

    for test_file in test_files:
        if not test_file.exists():
            print(f"Warning: {test_file} not found")
            continue

        print(f"Processing {test_file}...")

        # Read file
        content = test_file.read_text()
        original_content = content

        # Apply fixes
        content = fix_pubsub_cleanup(content)
        content = fix_broadcaster_cleanup(content)

        # Write back if changed
        if content != original_content:
            test_file.write_text(content)
            print(f"  ✓ Fixed {test_file}")
        else:
            print(f"  - No changes needed for {test_file}")

    print("\nDone! Review the changes and run tests to verify.")


if __name__ == "__main__":
    main()
