#!/bin/bash
key="$1"
out="/tmp/wp25/wp44-triage/diffs/$key.diff"
if [ ! -s "$out" ]; then
  timeout 60 uv run mutmut show "$key" > "$out" 2>&1 || echo "FAILED $key" > "$out"
fi
