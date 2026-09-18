#!/bin/bash
cd /agents/agent-nemo2/workspace
OUT=/tmp/wp25/wp44-triage/diffs.txt
: > "$OUT"
n=0
while IFS= read -r key; do
  n=$((n+1))
  d=$(timeout 60 uv run mutmut show "$key" 2>&1)
  rc=$?
  {
    echo "=== KEY $key (rc=$rc)"
    echo "$d"
  } >> "$OUT"
done < /tmp/wp25/wp44-triage/keys_exact.txt
echo "DONE processed=$n"
