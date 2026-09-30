# Synthbench clips: the H3 probe beside the flagship (plan Task 1)

- **Date:** 2026-09-30, about 04:58–05:22 UTC, on the GB300 (sm_103, 249.81 GiB visible to
  PyTorch). The flagship was resident throughout (`VLLM::EngineCore`, 191,548 MiB).
- **Plan:** `docs/superpowers/plans/2026-09-30-synthbench-h3-clips.md`.
- **Spec:** `docs/superpowers/specs/2026-09-30-synthbench-h3-clips-design.md`.
- **The owner's go-ahead:** the owner approved starting the renderer for the probe. It was
  stopped afterwards.

## Weights

All five H3 turbo files resolve through `/export/models/comfyui` and match their pinned sha256
(`p1-slate.json`, `Comfy-Org/MiniMax-H3@4cc1d817`):

- the int8 diffusion model;
- the NVFP4 Qwen3-VL-32B text encoder;
- the video and audio VAEs;
- the 4-step 768p turbo LoRA.

## The renderer and ComfyUI's shapes

- **Start.** `systemctl --user start synthbench-renderer` rendered its FLUX.2 warm-up image in
  47.1 s. The journal carried one `aimdo ... funchook_prepare(cuMemAllocAsync_ptsz) failed`
  ERROR line; the warm-up was unaffected.
- **Memory with FLUX.2 resident:** 52,058 MiB for the renderer, with 11.85 GiB free on the
  device.
- **`GET /history?max_items=1`** returns one entry. Its `prompt` is a list of 5, and item 2 is
  the graph; the `UNETLoader.unet_name` was `flux2_dev_fp8mixed.safetensors`.
- **`GET /system_stats`** has the keys `system` and `devices`. `devices[0]` has `index`, `name`,
  `type`, `vram_total`, `vram_free`, `torch_vram_total` and `torch_vram_free`.

## `/free` is asynchronous

`POST /free {"unload_models": true, "free_memory": true}` answered 200 at once:

| Time after the call | Renderer memory |
| ------------------- | --------------- |
| t+2 s               | 52,058 MiB      |
| t+5 s               | 892 MiB         |
| t+10 s              | 892 MiB         |

After it, `vram_free` was 61.81 GiB. The history still names FLUX.2, since `/free` does not
touch it.

**Consequence (plan ruling H3-R16, amended):** both render commands poll `/system_stats` after
`/free`, every second for up to 30 s, before judging the free memory.

## Clips

Each input was the source render fitted to 1344×768 (`ImageOps.fit`, LANCZOS). The graph was
the committed `minimax_h3_turbo_i2v`: 4 steps, LoRA 1.0, shift 6/3, euler. Every run used seed 1,
except the warm-up (seed 0).

| Clip                     | Source        | Frames | Seconds | Renderer peak | Output                         |
| ------------------------ | ------------- | -----: | ------: | ------------: | ------------------------------ |
| warm-up (H3 load + clip) | smoke image   |     22 |    61.2 |      42.0 GiB | 1344×768 h264, 22 frames, aac  |
| r0 firearm_visible, day  | B-batch-1-015 |    243 |   327.0 |      42.4 GiB | 1344×768 h264, 243 frames, aac |
| r1 pool_service, day     | B-batch-1-000 |    243 |   328.7 |      43.3 GiB | 1344×768 h264, 243 frames, aac |
| r2 tailgating, IR night  | B-batch-1-014 |    243 |   327.6 |      43.3 GiB | 1344×768 h264, 243 frames, aac |
| r0 reference             | B-batch-1-015 |    124 |   133.2 |      48.3 GiB | 1344×768 h264, 124 frames, aac |

- **Peak memory:** 48.3 GiB, sampled every 0.5 s across the run. That is under the 59.9 GiB
  ceiling that keeps the flagship's util-0.76 boot gate passable. The 124-frame clip's peak was
  the highest.
- **Frames:** H3 returned exactly the frames requested (243 in, 243 out). 243 is on its 17k+5
  grid, 10.1 s at 24 fps.
- **Time against length:** twice the frames (124 to 243) took 2.46× as long, roughly
  frames^1.34.
- **P1 comparison:** P1 measured 67.7 s for 124 frames in an owner GPU window. Beside the
  flagship it took 133.2 s.
- **The GPU** was at 100% utilization during the clips.
- **The flagship** answered 236 of 236 health checks (HTTP 200, every 5 s), and the guard
  journal had no entries.

The clips and their inputs are in `/synthbench/probes/clips/`, outside the corpus.

## The owner's verdict

The owner watched the three 243-frame clips: "clips look good". The owner then asked to generate
clips for the whole corpus.

## Constants chosen (plan ruling H3-R7, amended)

| Constant           | Value | Why                                                                                                   |
| ------------------ | ----: | ----------------------------------------------------------------------------------------------------- |
| `CLIP_FRAMES`      |   243 | the owner's ~10 s                                                                                     |
| `H3_PEAK_GIB`      |    49 | 48.3 GiB measured, rounded up                                                                         |
| `CLIP_TIMEOUT_S`   |   500 | 1.5 × 328.7 s; the plan's 2× (≈660 s) exceeds the agent's 600 s call, and three clips varied by 1.7 s |
| `WARMUP_TIMEOUT_S` |   240 | 61.2 s with a warm page cache; room for a cold weight load                                            |

With `CALL_LIMIT_S = 570`, a clip starts only in the first 70 s of a `clip render` call. So one
call renders one clip. A call that switches models may render none: the warm-up takes about
61 s before the first clip could start.
