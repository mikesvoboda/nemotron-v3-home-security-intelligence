# Addendum 1 (2026-10-07): the b7972 video answer, measured at source — and what it corrects

- **Amends:** README §5's consequence clause for Phase 1e, and §7's understanding of what
  window 1 is for. Nothing else moves: the arms, the clips (F1–F4), the statistics and the
  signature block are unchanged, and the README's frozen text is untouched — §1 names the dated
  addendum as the only amendment channel, and this is one. **Nothing here is signed; §7 stays
  unsigned and no window has been opened.**
- **What was done:** Phase 1e's CPU half only — no GPU, no container, no probe, no clip touched.
  The serving build's own source was read at its exact commit; the candidate arm-(b) build was
  read at its tag; the shipped image was grepped. Every line below is [V] as of this date unless
  marked otherwise.

## 1. The measurement

The served build string is the tag's commit: `/props` reports `b7972-e06088da0`, and tag `b7972`
_is_ commit `e06088da0` (verified via the GitHub refs API). So reading the tag's source is reading
the shipped binary's source, not an approximation of it.

| Source at `b7972`                      | What it says                                                                                                                                                       |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `tools/server/server-common.cpp`       | content parts handle `text`, `image_url` (:911) and `input_audio` (:924); anything else throws `unsupported content[].type` (:947). Zero video matches in the file |
| `tools/mtmd/mtmd.cpp`                  | one video mention, a comment: "t is omitted as we don't support video input" (:1094)                                                                               |
| `tools/mtmd/mtmd.h`, `mtmd-helper.cpp` | zero video matches                                                                                                                                                 |
| `tools/server/server.cpp`, README      | zero video matches — no video flag is even documented at this pin                                                                                                  |
| upstream ordering                      | video input arrived in PR #24269, merged 2026-06-08; b7972 is dated 2026-02-08. Four months apart — the absence is the commit, not a build flag                    |
| `ai/vlm/Dockerfile` (this repo)        | the runtime stage installs curl and libgomp1 only; zero `ffmpeg` matches in the Dockerfile and in every compose file; the CMD passes no video flags                |

**Answer to the acceptance clause** ("includes whether the llama.cpp pin supports video (tested,
not assumed)"): at the pinned commit, b7972 cannot accept video, by construction — the code does
not exist yet. §7 window 1, if signed, becomes a **confirmatory** runtime check (a 400 at the
endpoint, seconds), not the decisive unknown the README assumed.

## 2. The correction §5 needs before anyone signs §7

§5's sentence, verbatim: _"A negative kills arm (b) as a llama.cpp feature and makes it the
vLLM/second-engine question of §2 — which changes the §7 spend, so it runs first and its result
lands in the register"_. The first half is true only of the pinned build. The second half is
**wrong as written**, measured at b11376 [V]:

- `tools/server/server-common.cpp:1182` branches on `input_video` (alias `video_url`);
- README documents `--video-fps` (default 4.0), `--video-timestamp-interval`,
  `--video-ffmpeg-dir`, and accepts a video part as URL, raw base64, data URI or `file://` under
  `--media-path`;
- the decode is ffmpeg shelling out into ordinary image chunks — a frames path, not a native
  video encoder (this matches the unaudited 2026-10-04 research note, which is where the reading
  was first raised; it is now re-verified at primary source, superseding its `[A]`).

And the re-pin is already in this project's own lineage: the sweep ran on
`ai-vlm:sm103-b11376`, which the ledger records as **the same `ai/vlm/Dockerfile` with only
`LLAMA_CPP_REF` overridden** (ledger, 2026-10-03 control-arm row). So arm (b) does not have to
leave llama.cpp; it has to re-pin and pay two costs §5 never priced:

1. **The build is an outcome-variable.** ISS-087 measured b7972 versus b11376 disagreeing on 44%
   of items for identical model, weights and prompt. Arm (a) runs on the pinned b7972 because
   that is the product's serving path; arm (b) on llama.cpp _must_ run on a later build. Format
   and build then co-vary, and the S2/S3 contrast is confounded unless the design pays for a
   control: arm (a)'s burst replayed once on the arm-(b) build (~12 min of image calls at the
   dogfood median; fits the §7 row-4 arithmetic). Without it, arm (b) vs arm (a) is a combined
   "format + build" claim, readable only as such.
2. **The runtime image cannot decode.** b7972's answer aside, even a b11376 re-pin serves a
   server with no ffmpeg in the runtime stage, and b11376 shells out to ffmpeg to decode. Two
   routes: mount a static aarch64 ffmpeg/ffprobe on the models mount and point
   `--video-ffmpeg-dir` at it (zero repo change; the 2026-10-04 note's idea, untested `[A]`), or
   add ffmpeg to the runtime stage (Dockerfile change, ~30 s of apt, changes what "the pinned
   image" means for any later number quoted against the product path).

Token load is still the §7 row-4 open size: the reading that the 4 fps default puts a ~10 s clip
at ~21K tokens against a 16,384 slot (so `--video-fps` ≤ 2, with pair-merging; ~1 without) is the
2026-10-04 research note's arithmetic, `[C]` and unconfirmed here — probe (iii) above is what
turns it into a measured number before the measurement window is booked.

## 3. What window 1 is now, if the owner signs it

Same or smaller than the ≤15 min proposed: (i) confirm b7972 refuses a video part end-to-end
(seconds on the existing image recipe); (ii) confirm the runtime stage has no ffmpeg (seconds).
If the owner also rules arm (b) to be the llama.cpp re-pin, add (iii): serve `b11376` (the
image is a rebuild of this Dockerfile — ~7–10 min [V: the ledger's build rows] — the vss8 store
currently holds only `ai-vlm:sm103`, so the rebuild belongs to the window) and send one real
clip, measuring the accepted-token count and latency at an explicit `--video-fps`. That (iii)
may push the window past 15 min once, which is a §7 fact the owner signs, not a surprise.

## 4. What is unchanged, and what this addendum does not decide

Arms (a)/(b) and the acceptance shape (ISS-003 verbatim), the frozen clips (F1), the mirror and
motion stratification (F2), the freezes F3/F4, the statistics, the Phase 3 binding rule (**no
clip S2/S3 number is published before the blind audit**) — all unchanged. This addendum does not
choose arm (b)'s engine (llama.cpp re-pin vs vLLM remains the owner's), does not open or resize
any window's authority, does not rule ISS-003/OD-5/OD-2, and spends nothing: no GPU was touched,
no container ran, no corpus file was written, no number exists.
