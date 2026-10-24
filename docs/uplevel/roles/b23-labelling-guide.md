# B2.3 Person-Crop Labelling Guide (Ruling 333)

> For the **owner** on the host (where `/export/foscam` and `~/o24-crops` live) and the **operator**
> (`uplevel-operator`) running `scripts/uplevel/b23_real_tier.sh`.

## Privacy and neutral pre-grouping (Ruling 333 item 1)

- **Size and source:** ~150–200 person crops across several cameras and days, including the 36 crops
  from `[r312a]` (`~/o24-crops` / `$AGENT_GPU_DIR/out/r312a-run2/crops/`).
- **Neutral pre-grouping:** `scripts/uplevel/b23_crop_tool.py sample` groups crops solely by
  `(event_id, track_id)` (one detection track inside one event is one initial identity) or camera
  snapshot burst. It **never** calls OSNet or any challenger model, so the ground-truth labels
  cannot favour any candidate.
- **Host-only storage:** Crops and `labels.json` stay on the host / `$AGENT_GPU_DIR/models/b23-work/`
  and are never committed, uploaded, or posted. PRs post only aggregate counts (`total_kept_crops`,
  `identities_count`, `multi_crop_identities_count`, `cameras_count`), `labels.json`'s SHA-256, and
  the bake-off metric table (`scripts/b23_reid_bakeoff.py`).

## Step 1: Sample and pre-group on the host

```bash
uv run python scripts/uplevel/b23_crop_tool.py sample \
  --existing-crops-dir ~/o24-crops \
  --detections-manifest ~/b23-detections.json \
  --output-dir ~/b23-work \
  --target-count 180 \
  --seed 42
```

## Step 2: Merge/split groups in the localhost review tool (`127.0.0.1` only)

```bash
uv run python scripts/uplevel/b23_crop_tool.py serve \
  --work-dir ~/b23-work \
  --host 127.0.0.1 \
  --port 8766
```

1. Open `http://127.0.0.1:8766` in a browser (via SSH local port-forward if remote).
2. Check groups belonging to the same person across events/cameras, enter a target label (e.g.
   `person_01`), and click **Merge Checked Groups**.
3. Use **Split** if a track mixed two people, or **Exclude** on non-person/unusable crops.
4. Click **Export labels.json** (or run `uv run python scripts/uplevel/b23_crop_tool.py export --work-dir ~/b23-work`).
5. Copy `~/b23-work` (`crops/` + `labels.json`) into the operator's `$AGENT_GPU_DIR/models/b23-work`
   so `uplevel-operator` can mount it read-only (`--mount models:/models`).

## Step 3: Run the bake-off (`uplevel-operator`)

```bash
scripts/uplevel/b23_real_tier.sh \
  --checkout /agents/agent-uplevel-operator/workspace \
  --gpu 0 \
  --work-dir "$AGENT_GPU_DIR/models/b23-work"
```
