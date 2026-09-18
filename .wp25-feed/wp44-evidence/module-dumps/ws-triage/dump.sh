#!/bin/bash
out=/tmp/wp25/ws-triage/diffs.txt
: > "$out"
while read -r key; do
  echo "===KEY $key" >> "$out"
  timeout 60 uv run mutmut show "$key" >> "$out" 2>&1 || echo "!!FAILED" >> "$out"
done < /tmp/wp25/ws-triage/keys.txt
echo DONE >> "$out"
