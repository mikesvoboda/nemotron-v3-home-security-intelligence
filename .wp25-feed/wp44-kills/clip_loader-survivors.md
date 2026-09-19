# services/clip_loader.py surviving-mutant record — PROVISIONAL (wave-67, WIP at handoff 2026-09-19)

48 mutants; 24 killed pre-WP4.4 (score 50.0%). Wave-67 batch (4 drafted tests
in TestClipLoaderDiagnostics, caplog-based): first STRICT census **14/24
killed** (w67-clip.jsonl, recount from disk; 10 survivors) vs dossier
prediction 19/24.

Line-level diff audit of the 10 survivors against `__mutmut_orig` in the
mutants tree resolved every deviation:

- 14, 27, 28 — draft under-shoots: D1/D3 used SUBSTRING matching
  (`"moved to CUDA" in m`, `"transformers" in m and "pip install" in m`)
  which XX-wrap and case clobbers survive. FIXED: exact-string membership
  `assert "SigLIP 2 model moved to CUDA" in infos` / exact warning text.
- 3 — dossier mis-cluster: it clobbers the CPU-guard RAISE message
  ("SigLIP 2 requires a CUDA GPU…", line 66), not the C1 entry log; the
  covering tests only prefix-matched. FIXED: `str(exc.value) ==` the full
  SHIPPED message — note the guard RuntimeError is RE-WRAPPED by the broad
  handler, so the shipped contract is
  "Failed to load SigLIP 2 model: SigLIP 2 requires a CUDA GPU — …".
- 34 — message→None with exc_info/extra intact; D4 pinned only the kwargs.
  FIXED: `rec.getMessage() != "None"` structural guard (kills 34 WITHOUT
  pinning error-log prose, keeping C8 correctly LOW-VALUE).
- 6 — predicted survivor (C6), but D2's startswith assertions killed it.
- 31, 32, 40, 41, 42 — genuine C7/C8 LOW-VALUE survivors (raise-suffix and
  error-message XX/case clobbers), expected to persist.

Repair verified: 45 passed in-tree, ruff clean, synced into mutants/, key 35
hand-probed RED. **clip-only re-census RUNNING at handoff**: pid 2443118
(nohup, survives session), output /tmp/wp25/wp44-kills/w67-clip2.jsonl
(11 killed / 12 probed at handoff). Expected terminal: 19/24 (module
24+19 = 43/48 = 89.6%), 5 survivors = 31, 32, 40, 41, 42.

SUCCESSOR TASK: recount clip2 from disk (`python -c` json over the jsonl,
kill = rc in (1,3)); if it matches, promote this file to FINAL (drop
PROVISIONAL, list the 5 survivor keys in a fenced block) and commit the
test file with house-format message `test(wp44): clip_loader kill batch —
STRICT census 19/24 new kills (module 43/48=89.6%)`. If it deviates again,
diff surviving keys vs __mutmut_orig in mutants/backend/services/
clip_loader.py as above before touching assertions.

```
backend.services.clip_loader.x_load_clip_model__mutmut_31
backend.services.clip_loader.x_load_clip_model__mutmut_32
backend.services.clip_loader.x_load_clip_model__mutmut_40
backend.services.clip_loader.x_load_clip_model__mutmut_41
backend.services.clip_loader.x_load_clip_model__mutmut_42
```
