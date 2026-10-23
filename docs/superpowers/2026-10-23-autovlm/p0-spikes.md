# P0: Spikes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. These are operational spikes on the GB300 host, not code; each step is a command and an observation. Index: [`README.md`](README.md). Design: [`docs/auto-vlm-research/05-stack-integration.md`](../../auto-vlm-research/05-stack-integration.md) §3.

**Goal:** Prove or disprove each behaviour the design relies on before any code depends on it.

**Rules for every spike:**

- Run on the GB300 host as the owner's user unless a step says otherwise. Steps marked **owner** change the host and need the owner's go-ahead first.
- Never type an unknown word after `agent-dgx`: an unrecognised word such as `help` or `ls` starts a real session. Use `agent-dgx list --json` and `agent-dgx doctor` to inspect.
- Every throwaway session is named `autovlm-s<N>` and removed at the end with `agent-dgx session rm autovlm-s<N> --force`.
- `PROFILE` below is the governance profile the owner uses for agent sandboxes; read it from an existing session in `agent-dgx list --json`.
- Record every result in `docs/auto-vlm-research/06-spike-results.md` (created in Task 0): the date, the stack-repo commit, the exact commands, the observation, and pass or fail.

---

### Task 0: Results file

**Files:**

- Create: `docs/auto-vlm-research/06-spike-results.md`
- Modify: `docs/auto-vlm-research/README.md` (reading order gains item 6)

- [ ] **Step 1: Create the results file**

```markdown
# 06. Spike results (phase P0)

> Results of the spikes defined in [`05-stack-integration.md`](05-stack-integration.md) §3. Back to the [index](README.md).

| ID  | Date | Stack commit | Result | Decision it forces |
| --- | ---- | ------------ | ------ | ------------------ |
| S1  |      |              |        |                    |
| S2  |      |              |        |                    |
| S3  |      |              |        |                    |
| S4  |      |              |        |                    |
| S5  |      |              |        |                    |
| S6  |      |              |        |                    |
| S7  |      |              |        |                    |

## Details

One section per spike: commands run, output observed, pass or fail.
```

- [ ] **Step 2: Add it to the design README's reading order** as item 6, "`06-spike-results.md` — what the P0 spikes found."

- [ ] **Step 3: Commit**

```bash
git add docs/auto-vlm-research/06-spike-results.md docs/auto-vlm-research/README.md
git commit -m "docs(auto-vlm-research): add the P0 spike results table"
```

---

### Task 1: S1 — can a guest read host files outside its mounts?

The scorer's labels rely on this (design `01` §3.6). Guest root has full capabilities and passwordless sudo, and the virtiofs `host` tag is visible inside the guest.

- [ ] **Step 1 (owner): Create the scorer user and a canary**

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin autovlm-scorer
sudo install -d -o autovlm-scorer -g autovlm-scorer -m 700 /srv/autovlm-scorer
echo "autovlm-canary-$(date +%s)" | sudo tee /srv/autovlm-scorer/canary >/dev/null
sudo chown autovlm-scorer:autovlm-scorer /srv/autovlm-scorer/canary
sudo chmod 600 /srv/autovlm-scorer/canary
```

- [ ] **Step 2: Record which uid virtiofsd acts as**

Run: `ps -eo user,pid,args | grep -E '[v]irtiofsd'`
Record the user column. If it is `root`, file modes do not protect the canary and the spike is already a fail.

- [ ] **Step 3: Launch a throwaway shell sandbox**

```bash
agent-dgx run autovlm-s1 --agent shell --profile "$PROFILE"
```

- [ ] **Step 4: From inside the guest, try the host tag**

```bash
cat /sys/fs/virtiofs/*/tag
sudo mkdir -p /mnt/hosttag
sudo mount -t virtiofs host /mnt/hosttag && echo MOUNTED || echo MOUNT-REFUSED
sudo cat /mnt/hosttag/srv/autovlm-scorer/canary && echo READ || echo DENIED
sudo umount /mnt/hosttag 2>/dev/null; exit
```

- [ ] **Step 5: Clean up**

Run: `agent-dgx session rm autovlm-s1 --force`

- [ ] **Step 6: Check that the owner's sudo asks for a password**

Run, as the owner's user on the host: `sudo -k; sudo -n true && echo PASSWORDLESS || echo PROMPTS`
The holdout's owner-only rule (P2 Task 7) depends on `PROMPTS`: the Claude manager runs as the owner's user, so only a password separates the owner from it.

**Pass:** `MOUNT-REFUSED` or `DENIED` in Step 4, and `PROMPTS` in Step 6. **Fail on Step 6:** record "holdout confirmation moves to a host no agent runs on". **Fail on Step 4:** `READ`. On fail, the design's labels cannot live on the GB300: record "labels move to a host no sandbox runs on" as the decision, and tell the owner, because the mount itself is a sandbox escape (it is a known open item in the stack repo).

---

### Task 2: S2 — does herdr track Qwen-backed sandboxed sessions?

- [ ] **Step 1: Launch a Qwen-backed Claude session in a herdr pane**

```bash
agent-dgx run autovlm-s2 --agent claude --profile "$PROFILE" --endpoint dgx --split
```

- [ ] **Step 2: Find its herdr agent id**

Run: `herdr agent list`
Record the id of the pane running `autovlm-s2` as `S2_AGENT`.

- [ ] **Step 3: Give it a task that takes about a minute, and sample its status**

```bash
herdr agent prompt "$S2_AGENT" "Run the shell command: sleep 60; then reply DONE."
for i in $(seq 1 30); do date +%T; herdr agent get "$S2_AGENT" | grep -o '"agent_status": *"[a-z]*"'; sleep 5; done
```

- [ ] **Step 4: Clean up**

Run: `agent-dgx session rm autovlm-s2 --force`

**Pass:** the samples show `working` during the sleep and `idle` (or `done`) after the reply. **Fail:** the status stays `unknown` or never changes. On fail, P3's stall detection must use the run ledger and transcript age only; record that.

---

### Task 3: S3 — does a brief passed after `--` start a worker unattended?

- [ ] **Step 1: Launch with an opening prompt and walk away**

```bash
agent-dgx run autovlm-s3 --agent claude --profile "$PROFILE" --endpoint dgx --split -- \
  "Create the file s3-started.txt in your workspace containing the word started, then stop."
```

Do not type into the pane.

- [ ] **Step 2: Check from the host after five minutes**

Run: `cat /agents/agent-autovlm-s3/workspace/s3-started.txt`
Expected: `started`

- [ ] **Step 3: Clean up**

Run: `agent-dgx session rm autovlm-s3 --force`

**Pass:** the file exists with no human input. **Fail:** the session waits at a prompt. On fail, P3 sends the brief with `herdr agent prompt` after launch instead; record that.

---

### Task 4: S4 — do per-sandbox port denies hold?

- [ ] **Step 1: Start two dummy host services**

```bash
python3 -m http.server 18555 --bind 127.0.0.1 >/dev/null 2>&1 & echo $! > /tmp/s4-deny.pid
python3 -m http.server 18556 --bind 127.0.0.1 >/dev/null 2>&1 & echo $! > /tmp/s4-allow.pid
```

18555 stands for a port the worker must not reach (a pool port, the scorer); 18556 stands for the executor port.

- [ ] **Step 2: Launch a throwaway sandbox and deny 18555 for it alone**

```bash
agent-dgx run autovlm-s4 --agent shell --profile "$PROFILE"
# in another host shell:
sbx policy deny network --sandbox agent-autovlm-s4 '**:18555'
```

- [ ] **Step 3: Probe every name for both ports from inside the guest**

```bash
for h in host.docker.internal localhost 127.0.0.1 gateway.docker.internal; do
  for p in 18555 18556; do
    printf '%s:%s ' "$h" "$p"; curl -s -o /dev/null -m 3 -w '%{http_code}\n' "http://$h:$p/" || echo refused
  done
done
```

- [ ] **Step 4: Try a range rule, for the 100-port agent-gpu pool**

```bash
sbx policy deny network --sandbox agent-autovlm-s4 '**:18100-18199' && echo RANGE-ACCEPTED || echo RANGE-REJECTED
```

- [ ] **Step 5: Clean up**

```bash
agent-dgx session rm autovlm-s4 --force
kill "$(cat /tmp/s4-deny.pid)" "$(cat /tmp/s4-allow.pid)"; rm -f /tmp/s4-*.pid
```

Remove the two rules if `session rm` left them: `sbx policy ls` shows them.

**Pass:** every name reaches 18556 and none reaches 18555. Record whether the range form was accepted; if not, the launcher (P3) writes one rule per pool port.

---

### Task 5: S5 — does llama.cpp expose embeddings for image plus text?

Needed only for the linear-probe idea (design `03` §7).

- [ ] **Step 1: Start the pinned VLM with embeddings enabled**

Use the launch in P1 Task 12 Step 3, adding `--embeddings` to the llama-server arguments and naming the container `autovlm-s5`.

- [ ] **Step 2: Ask for an embedding of one still**

```bash
IMG=$(base64 -w0 /synthbench/exports/tierb-v0/vss/normal/B-batch-1-000/still.jpg)
curl -s "http://host.docker.internal:$S5_PORT/embeddings" -H 'Content-Type: application/json' \
  -d "{\"content\": [{\"prompt_string\": \"<__media__> describe\", \"multimodal_data\": [\"$IMG\"]}]}" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(type(d), str(d)[:300])'
```

If the request shape is refused, read the pinned build's `tools/server/README.md` for the multimodal embeddings format and retry; record the format that worked.

- [ ] **Step 3: Stop the container**: `agent-gpu stop autovlm-s5 && agent-gpu rm autovlm-s5`

**Pass:** a numeric vector comes back for an image-bearing request. **Fail:** record "linear probe needs a different engine" against design `03` §7.

---

### Task 6: S6 — does endpoint scheduling fit the global VRAM cap?

- [ ] **Step 1: Start two 8B endpoints and one 27B endpoint**

Use P1 Task 12 Step 3's launch for `autovlm-s6a` and `autovlm-s6b` (8B, `--vram 12` each), and the same launch for `autovlm-s6c` pointed at the Qwen3.8-27B Q4_K_M weights from the 2026-10-03 sweep with `--vram 20`.

- [ ] **Step 2: Observe admission and residency**

Run: `agent-gpu ps` and `nvidia-smi --query-gpu=memory.used,memory.total --format=csv`
Send one assess request to each (P1 Task 10's gpu test does this) and record latency.

- [ ] **Step 3: Stop all three** with `agent-gpu stop` and `agent-gpu rm`.

**Pass:** all three are admitted under the 40 GiB cap with the flagship resident, and each answers. **Fail:** record the largest set that fits; P2's endpoint pool uses it as its default budget.

---

### Task 7: S7 — can the production detector run for autovlm?

P1's realistic inputs need YOLO26 as the product runs it: the ai-gateway's `POST /yolo26/detect`, a multipart `file` upload returning `{"detections": [{"class", "confidence", "bbox": {"x", "y", "width", "height"}}], ...}`. The uplevel real tier keeps the detector fake, so this has not been shown on the GB300.

- [ ] **Step 1: Try the gateway image on the GB300 through agent-gpu**

Build or reuse the ai-gateway image with its Triton YOLO26 model as `docker-compose.prod.yml` defines it (re-read that file; the service names may have changed during uplevel), and start it with `agent-gpu run --name autovlm-s7 --image <gateway image> --vram 4 --port <gateway port> -- <the service's command>`.

- [ ] **Step 2: Detect one still**

```bash
curl -s -F "file=@/synthbench/exports/tierb-v0/vss/suspicious/B-batch-4-073/still.jpg" \
  "http://host.docker.internal:$S7_PORT/yolo26/detect" | python3 -m json.tool | head -30
```

- [ ] **Step 3: If the GB300 cannot run it, try the A5500 box**, where the production stack runs, with the same request.

**Pass:** a detections list comes back on either host. Record which host serves the detector for P1 Task 12. **Fail on both:** record "realistic inputs blocked"; P1 Tasks 1–11 still proceed (they test against a fake detector), and Task 12 waits.
