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

| Script | Model | Input | Output | Engine Path |
|--------|-------|-------|--------|-------------|
| `export_clip.py` | CLIP ViT-L/14 | (B, 3, 224, 224) | (B, 768) | `/models/cache/clip/1/model.plan` |
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

| Flag | Default | Description |
|------|---------|-------------|
| `--model-path` | Model-specific | HuggingFace model directory or model ID |
| `--output-path` | Model-specific | Destination for the TensorRT .plan file |
| `--precision` | `fp16` | `fp16` or `fp32` |
| `--max-batch` | `8` | Maximum dynamic batch size |
| `--workspace-gb` | `1` | TensorRT builder workspace (GB) |
| `--opset` | `17` | ONNX opset version |
| `--onnx-only` | false | Export ONNX only, skip TRT conversion |
| `--skip-validation` | false | Skip ONNX vs PyTorch validation |

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
