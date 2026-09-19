# services/clip_loader.py surviving-mutant record (STRICT census 2026-09-19, wave-67)

48 mutants; 24 killed pre-WP4.4 (score 50.0%). Wave-67 batch (4 tests in
TestClipLoaderDiagnostics, caplog-based): **19 newly killed**. STRICT census:
all 24 open keys re-probed with synced tests, kill = rc in (1,3), -n 0,
0 no-verdicts. First census read 14/24 vs dossier 19/24; the line-diff audit
below fixed 3 draft under-shoots + 1 dossier mis-cluster, and the clip-only
re-census (w67-clip2.jsonl, recounted from disk) terminated at 19/24 with the
survivor set predicted exactly.

Line-level diff audit of the first census's 10 survivors against
`__mutmut_orig` in the mutants tree resolved every deviation:

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
  error-message XX/case clobbers); confirmed dead-on-arrival by the re-census.

Module total: (24+19)/48 = **43 = 89.6%** (was 50.0% pre-WP4.4).
5 survivors remain — dossier-predicted exactly (C7 raise-suffix, C8
error-message clobbers under prefix/substring convention). They ARE the
surviving-mutant record.

```
backend.services.clip_loader.x_load_clip_model__mutmut_31
backend.services.clip_loader.x_load_clip_model__mutmut_32
backend.services.clip_loader.x_load_clip_model__mutmut_40
backend.services.clip_loader.x_load_clip_model__mutmut_41
backend.services.clip_loader.x_load_clip_model__mutmut_42
```
