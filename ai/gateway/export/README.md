# Model Export Pipeline

Export scripts that convert HuggingFace/PyTorch models to Triton-compatible TensorRT engines.

Part of the Triton Inference Server migration (see `docs/plans/triton-migration.md`, Phase 1).

## Pipeline

```
HuggingFace PyTorch weights
        |
        v
   ONNX export (torch.onnx.export, opset 17, dynamic batch)
        |
        v
   Validation (ONNX Runtime vs PyTorch, cosine similarity > 0.999)
        |
        v
   TensorRT conversion (trtexec or tensorrt Python API, FP16)
        |
        v
   .plan engine file → Triton model repository
```

## Scripts

| Script                   | Model                 | Input            | Output   | Engine Path                               |
| ------------------------ | --------------------- | ---------------- | -------- | ----------------------------------------- |
| `export_clip.py`         | CLIP ViT-L/14         | (B, 3, 224, 224) | (B, 768) | `/models/cache/clip/1/model.plan`         |
| `export_fashion_clip.py` | FashionSigLIP (Marqo) | (B, 3, 224, 224) | (B, 768) | `/models/cache/fashion_clip/1/model.plan` |

## Usage

Each script accepts the same CLI arguments:

```bash
python export_clip.py \
    --model-path /models/zoo/clip-vit-l \
    --output-path /models/cache/clip/1/model.plan \
    --precision fp16

python export_fashion_clip.py \
    --model-path /models/zoo/fashion-clip \
    --output-path /models/cache/fashion_clip/1/model.plan \
    --precision fp16
```

### Common flags

| Flag                | Default        | Description                             |
| ------------------- | -------------- | --------------------------------------- |
| `--model-path`      | Model-specific | HuggingFace model directory or model ID |
| `--output-path`     | Model-specific | Destination for the TensorRT .plan file |
| `--precision`       | `fp16`         | `fp16` or `fp32`                        |
| `--max-batch`       | `8`            | Maximum dynamic batch size              |
| `--workspace-gb`    | `1`            | TensorRT builder workspace (GB)         |
| `--opset`           | `17`           | ONNX opset version                      |
| `--onnx-only`       | false          | Export ONNX only, skip TRT conversion   |
| `--skip-validation` | false          | Skip ONNX vs PyTorch validation         |

## TensorRT conversion strategy

Each script tries `trtexec` first (pre-installed in NVIDIA containers), then falls back to
the `tensorrt` Python API. Both paths produce identical engines.

## Validation

After export, each script compares ONNX Runtime output against PyTorch inference on 4 test
images. The cosine similarity between PyTorch and ONNX embeddings must exceed 0.999 for the
export to pass.

## Notes

- L2 normalization is NOT baked into the engine. The gateway adapter normalizes at serving time.
- The `--workspace-gb` default of 1 GB is tuned for the 4 GB RTX A400 on GPU 1.
- CLIP uses `transformers.CLIPModel`; FashionSigLIP uses `open_clip.create_model_from_pretrained`.
- FashionSigLIP local paths resolve to `hf-hub:Marqo/marqo-fashionSigLIP` (meta-tensor workaround).

## Person Re-ID: a two-step ONNX, then a per-GPU plan (O2.4)

`export_reid.py` is the one script here whose output is not decided by a flag in
one run — the gateway's `reid` model serves a TensorRT **plan** now (owner
ruling 107), and an engine is only valid on the GPU architecture that built it.
So the export splits the way `export_all.sh`'s phases already imply:

| Step                                  | Where it runs            | What it does                                                                                                     | Guard                                                                      |
| ------------------------------------- | ------------------------ | ---------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `--output-path .../reid/1/model.onnx` | any host (CPU fine)      | exports OSNet-AIN x1.0 from the `.pth`, validates the ONNX against PyTorch, then writes `provenance.json` (B2.2) | provenance only after a validated export                                   |
| `--output-path .../reid/1/model.plan` | **only the serving GPU** | compiles that `model.onnx` with `trtexec` (fp16, batch profiles 1/8/16)                                          | refuses without a provenance record whose `source_sha256` is these weights |

The plan step is a **compile, not a re-export**: it reads the sibling
`model.onnx` and never loads a checkpoint, exports, or runs inference. That is
why the numeric proof sits where it always has:

- **the graph** is proved by `validate_onnx` in the ONNX step — PyTorch against
  ONNX Runtime's **CPU** execution provider, cosine > 0.999, no GPU needed;
- **the plan** is proved by the owner's host run, `scripts/reid_parity_check.py`
  on the GB300 (ruling 107's _Done when_). Nothing in this directory
  re-validates an engine, because nothing here has a GPU to run one on; the plan
  is a deterministic compile of an already-vouched graph.
- **`provenance.json` is never rewritten by the plan step.** It stays where the
  ONNX step wrote it, because that is the record `reid_model_id()` reports in the
  running gateway, and the two must stay the same bytes.

The refusal is deliberate: `export_all.sh` skips an existing `model.onnx`, so a
stale pre-B2.2 ONNX (no record beside it) would otherwise seed a plan, and the
gateway would report a model ID its weights never earned — #6970 states that
precondition as a note; here it is a stop.

**The plan is required, not optional.** `ai/triton/model_repository/reid/config.pbtxt`
declares `backend: "tensorrt"`, so `reid` does not load without a
`model.plan`. `export_all.sh` handles the two failure shapes differently and
says which one it hit:

- **no `trtexec` on this host** (the CPU bake, and CI): the step is skipped and
  prints a warning naming `reid/config.pbtxt serves backend "tensorrt"` and
  that without a plan built ON the serving GPU, reid will not load. The bake
  still produces every ONNX, which is what those runs are for — and its summary
  says `the GPU step is pending, not passed` rather than
  `All exports succeeded`, because a skipped GPU step is not a passed one.
- **`trtexec` present and the compile fails**: counted as a failed export — the
  bake reports it and exits non-zero. A refusal from the provenance guard is the
  loud case it exists to make loud.

Two more things the bake does, both because an engine is GPU-specific:

- **It records which GPU built the plan** (`model.plan.device`, beside the plan).
  A cache copied from a different card still has a `.plan`, and Triton cannot
  load it; the bake calls that `STALE … rebuilding` instead of `CACHED`.
- **`REID_PLAN_PRECISION`** selects the compile precision (`fp16` default, like
  yolo26's shipped engine). If the owner's parity run lands just under the 0.999
  gate, `REID_PLAN_PRECISION=fp32` is the one-flag retry — the gate was proven
  against an FP32 path.

One limit of the guard, stated so nobody assumes more than it does: the record
proves the ONNX was exported from THESE weights, and `validate_onnx` proves that
ONNX matches the PyTorch model — but `--skip-validation` still writes a record,
so a record is not proof that validation ran. The plan step cannot see past the
record it is given.

Re-derive a plan after moving to different GPU hardware, or after anything
touches the ONNX (the `.device` sidecar makes this automatic on a new card):

```bash
rm -f "${CACHE_DIR}/reid/1/model.plan"
# re-export the ONNX too if the checkpoint changed — the plan refuses an ONNX
# whose provenance record does not match the checkpoint you pass
python3 export_reid.py \
    --model-path "${MODELS_ZOO}/osnet-ain-x1-0/osnet_ain_x1_0_msmt17.pth" \
    --output-path "${CACHE_DIR}/reid/1/model.onnx"
python3 export_reid.py \
    --model-path "${MODELS_ZOO}/osnet-ain-x1-0/osnet_ain_x1_0_msmt17.pth" \
    --output-path "${CACHE_DIR}/reid/1/model.plan"
```
