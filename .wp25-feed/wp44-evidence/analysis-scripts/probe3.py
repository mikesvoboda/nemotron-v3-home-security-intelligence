"""Probe 3: who has main.init_redis mocked when debug_client enters?"""
import sys
from unittest.mock import patch

import pytest

@pytest.fixture
def spy_init():
    import backend.main as m
    print(f"SPY entry: main.init_redis={type(m.init_redis)} name={getattr(m.init_redis, '_mock_name', None)}", file=sys.stderr)
    yield
    print(f"SPY exit: main.init_redis={type(m.init_redis)} name={getattr(m.init_redis, '_mock_name', None)}", file=sys.stderr)
