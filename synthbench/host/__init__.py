"""Host-only code: the guard, the renderer unit and the snapshot timer (design §1).

It runs under systemd user units from the host checkout, except `agent`, which the owner runs
from a checkout to retire and recreate the agent's sandbox. The sandbox agent never runs any of it.
"""
