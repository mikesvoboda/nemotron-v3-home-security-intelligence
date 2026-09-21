"""Exec the real module source with only the logging import stubbed (no pytest, /tmp only)."""
import re, sys, types

SRC = open('/agents/agent-nemo2/workspace/backend/services/trajectory_analyzer.py').read()

class _L:
    def debug(self, *a, **k): pass
    def info(self, *a, **k): pass
fake = types.ModuleType('backend.core.logging')
fake.get_logger = lambda name: _L()
sys.modules.setdefault('backend', types.ModuleType('backend'))
sys.modules.setdefault('backend.core', types.ModuleType('backend.core'))
sys.modules['backend.core.logging'] = fake

BASE = {}
exec(compile(SRC, 'trajectory_analyzer.py', 'exec'), BASE)

def fn_src(name):
    m = re.search(r'^def ' + re.escape(name) + r'\(', SRC, re.M)
    i = m.start()
    nxt = re.search(r'^(def |class |@)', SRC[i + 5:], re.M)
    j = i + 5 + nxt.start() if nxt else len(SRC)
    return SRC[i:j]
