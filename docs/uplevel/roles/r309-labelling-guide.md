# [r309] Labelling guide (owner, ~15 minutes)

Everything runs on the host where the camera frames live. No frame, crop
or label file ever leaves the host — the repo only ever receives counts
and a SHA-256, posted in the PR.

## One-time: sample the frames

```bash
uv run python scripts/uplevel/r309_frame_sampler.py \
    --root /export/foscam \
    --out /home/OWNERHOST/frame-set/selection.json \
    --camera-tz America/New_York
```

* Stratifies the tree into day / night-IR by camera-local capture hour,
  and flags small frames (width < 720 px) as likely-distant subjects.
* Writes `selection.json` — paths and strata only, no images.
* Re-running with the same `--seed` (default 0) on an unchanged tree
  reproduces the same selection byte-for-byte.

## Two: pre-box with OWLv2 (independent detector)

```bash
uv run python scripts/uplevel/r309_prebox.py \
    --selection /home/OWNERHOST/frame-set/selection.json \
    --root /export/foscam \
    --out /home/OWNERHOST/frame-set/prebox.coco.json
```

* Runs OWLv2 (`google/owlv2-base-patch16-ensemble`, cached after first
  download; `--model-dir` for offline hosts) — a different family than
  every detector the bake-off scores, per synthbench §4.1.
* Queries `person vehicle` plus `dog cat package bicycle`; keeps
  detections scoring ≥ 0.2, at most 10 per frame, highest first.
* Writes a COCO file with every box and its score — this is a recall-
  oriented starting point; you correct it, you don't relabel from
  scratch. ~0.5–2 s per frame on CPU.
* Classes the pass finds nothing for are dropped from the file; the two
  bake-off classes are always present.

## Three: correct the boxes in your browser

```bash
uv run python scripts/uplevel/r309_label_tool.py \
    --root /export/foscam \
    --prebox /home/OWNERHOST/frame-set/prebox.coco.json \
    --state /home/OWNERHOST/frame-set/corrections.json
```

Then open **http://127.0.0.1:8765** (localhost only — the tool never
binds an external interface).

Editing, per frame:

* **Drag inside a box** to move it; **drag its bottom-right corner** to
  resize; select a box and use the class dropdown (or type an "other"
  class) to reclassify.
* **Delete selected** removes a wrong box; **No objects** marks the
  frame empty (deletes all its pre-boxes).
* **Add box**, then drag on the image, draws a new box with the current
  class.
* Prev/Next saves and steps; every action autosaves to
  `corrections.json`, so closing the tab loses nothing.
* **Export COCO** writes the corrected file (default
  `prebox.coco.corrected.json`); the pre-box file is never modified, so
  a bad export can always be re-derived.

## What the PR receives

When you've exported, hand ops-b:

* the counts per stratum and class (the export prints them, or:
  `python -c "import json;c=json.load(open('prebox.coco.corrected.json'));print(len(c['images']),'frames');print({n:sum(1 for a in c['annotations'] if a['category_id']==cat['id']) for cat in c['categories'] for n in [cat['name']]})"`),
* the labelled file's SHA-256 (`sha256sum prebox.coco.corrected.json`).

The corrected file itself stays on the host; the bake-off ([r303])
reads it from there.
