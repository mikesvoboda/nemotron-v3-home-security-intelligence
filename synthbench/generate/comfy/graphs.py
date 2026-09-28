"""One ComfyUI API-graph builder per model (spec §3.2 slots), derived from the
official v0.37.0 workflow templates. File names are the farm's link names
(synthbench.generate.weights.link_names over manifests/p1-slate.json).

Each builder keeps its template's sampler, scheduler, steps, cfg/guidance and
shift; it replaces the seed, prompt, size (and frame count) with its arguments.
Subgraphs are flattened, switches resolve to the branch named in the comment,
and preview, note and prompt-enhancer nodes are dropped.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from synthbench.generate.comfy.client import Graph

T2IBuilder = Callable[..., Graph]
EditBuilder = Callable[..., Graph]
I2VBuilder = Callable[..., Graph]


def _prefix(model: str) -> str:
    return f"synthbench/{model}"


def _reference_ids(images: Sequence[str], per_image: int) -> list[list[str]]:
    """Node ids for each reference image's chain: image 0 gets "100", "101", ...; image 1 "110"..."""
    if not images:
        raise ValueError("an edit graph needs at least one reference image (the identity)")
    return [[str(100 + 10 * i + k) for k in range(per_image)] for i in range(len(images))]


# From template image_z_image_turbo.json
def z_image_turbo_t2i(prompt: str, *, seed: int, width: int, height: int) -> Graph:
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "z_image_turbo_bf16.safetensors", "weight_dtype": "default"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen_3_4b.safetensors",
                "type": "lumina2",
                "device": "default",
            },
        },
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "4": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 3.0}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "6": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}},
        "7": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "8": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["4", 0],
                "positive": ["5", 0],
                "negative": ["6", 0],
                "latent_image": ["7", 0],
                "seed": seed,
                "steps": 8,
                "cfg": 1.0,
                "sampler_name": "res_multistep",
                "scheduler": "simple",
                "denoise": 1.0,
            },
        },
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {
            "class_type": "SaveImage",
            "inputs": {"images": ["9", 0], "filename_prefix": _prefix("z-image-turbo")},
        },
    }


# From template image_flux2_fp8.json (text-to-image path; Turbo LoRA off)
def flux2_dev_t2i(prompt: str, *, seed: int, width: int, height: int) -> Graph:
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "flux2_dev_fp8mixed.safetensors", "weight_dtype": "default"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "mistral_3_small_flux2_fp8.safetensors",
                "type": "flux2",
                "device": "default",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "flux2-dev--flux2-vae.safetensors"},
        },
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "5": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["4", 0], "guidance": 4.0}},
        "6": {"class_type": "BasicGuider", "inputs": {"model": ["1", 0], "conditioning": ["5", 0]}},
        "7": {
            "class_type": "EmptyFlux2LatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "8": {
            "class_type": "Flux2Scheduler",
            "inputs": {"steps": 20, "width": width, "height": height},
        },
        "9": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "10": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "11": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["10", 0],
                "guider": ["6", 0],
                "sampler": ["9", 0],
                "sigmas": ["8", 0],
                "latent_image": ["7", 0],
            },
        },
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
        "13": {
            "class_type": "SaveImage",
            "inputs": {"images": ["12", 0], "filename_prefix": _prefix("flux2-dev")},
        },
    }


# From template image_flux2_klein_text_to_image.json (its "4B Distilled" subgraph)
def flux2_klein_4b_t2i(prompt: str, *, seed: int, width: int, height: int) -> Graph:
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "flux-2-klein-4b.safetensors", "weight_dtype": "default"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "flux2", "device": "default"},
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "flux2-klein-4b--flux2-vae.safetensors"},
        },
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "5": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
        "6": {
            "class_type": "CFGGuider",
            "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0], "cfg": 1.0},
        },
        "7": {
            "class_type": "EmptyFlux2LatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "8": {
            "class_type": "Flux2Scheduler",
            "inputs": {"steps": 4, "width": width, "height": height},
        },
        "9": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "10": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "11": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["10", 0],
                "guider": ["6", 0],
                "sampler": ["9", 0],
                "sigmas": ["8", 0],
                "latent_image": ["7", 0],
            },
        },
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
        "13": {
            "class_type": "SaveImage",
            "inputs": {"images": ["12", 0], "filename_prefix": _prefix("flux2-klein-4b")},
        },
    }


# From template image_qwen_image_2_1_t2i.json
def qwen_image_21_t2i(prompt: str, *, seed: int, width: int, height: int) -> Graph:
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "qwen_image_2.1_bf16.safetensors", "weight_dtype": "default"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen3vl_8b_bf16.safetensors",
                "type": "qwen_image",
                "device": "default",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "qwen_image_2.1_vae_bf16.safetensors"},
        },
        "4": {
            "class_type": "TextEncodeQwenImage21",
            "inputs": {
                "clip": ["2", 0],
                "prompt": prompt,
                "negative_prompt": "",
                "resolution": 1024,
            },
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "6": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["4", 0],
                "negative": ["4", 1],
                "latent_image": ["5", 0],
                "seed": seed,
                "steps": 25,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
            },
        },
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
        "8": {
            "class_type": "SaveImage",
            "inputs": {"images": ["7", 0], "filename_prefix": _prefix("qwen-image-2.1")},
        },
    }


# From template hidream_i1_full.json
def hidream_i1_full_t2i(prompt: str, *, seed: int, width: int, height: int) -> Graph:
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "hidream_i1_full_fp8.safetensors", "weight_dtype": "default"},
        },
        "2": {
            "class_type": "QuadrupleCLIPLoader",
            "inputs": {
                "clip_name1": "clip_l_hidream.safetensors",
                "clip_name2": "clip_g_hidream.safetensors",
                "clip_name3": "t5xxl_fp8_e4m3fn_scaled.safetensors",
                "clip_name4": "llama_3.1_8b_instruct_fp8_scaled.safetensors",
            },
        },
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "4": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": 3.0}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["2", 0], "text": "bad ugly jpeg artifacts"},
        },
        "7": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "8": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["4", 0],
                "positive": ["5", 0],
                "negative": ["6", 0],
                "latent_image": ["7", 0],
                "seed": seed,
                "steps": 50,
                "cfg": 5.0,
                "sampler_name": "uni_pc",
                "scheduler": "simple",
                "denoise": 1.0,
            },
        },
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {
            "class_type": "SaveImage",
            "inputs": {"images": ["9", 0], "filename_prefix": _prefix("hidream-i1-full")},
        },
    }


def _ideogram_side(pixels: int) -> int:
    """The template's size rule: max(((a + 15) // 16) * 16, 256)."""
    return max((pixels + 15) // 16 * 16, 256)


# From template image_ideogram4_t2i.json (plain-text prompt; the "Default" preset)
def ideogram_4_t2i(prompt: str, *, seed: int, width: int, height: int) -> Graph:
    w, h = _ideogram_side(width), _ideogram_side(height)
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "ideogram4_fp8_scaled.safetensors", "weight_dtype": "default"},
        },
        "2": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "ideogram4_unconditional_fp8_scaled.safetensors",
                "weight_dtype": "default",
            },
        },
        "3": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen3vl_8b_fp8_scaled.safetensors",
                "type": "ideogram4",
                "device": "default",
            },
        },
        "4": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "ideogram-4--flux2-vae.safetensors"},
        },
        "5": {
            "class_type": "CFGOverride",
            "inputs": {"model": ["1", 0], "cfg": 3.0, "start_percent": 0.7, "end_percent": 1.0},
        },
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": prompt}},
        "7": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["6", 0]}},
        "8": {
            "class_type": "DualModelGuider",
            "inputs": {
                "model": ["5", 0],
                "positive": ["6", 0],
                "cfg": 7.0,
                "model_negative": ["2", 0],
                "negative": ["7", 0],
            },
        },
        "9": {
            "class_type": "EmptyFlux2LatentImage",
            "inputs": {"width": w, "height": h, "batch_size": 1},
        },
        "10": {
            "class_type": "Ideogram4Scheduler",
            "inputs": {"steps": 20, "width": w, "height": h, "mu": 0.0, "std": 1.75},
        },
        "11": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "12": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "13": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["12", 0],
                "guider": ["8", 0],
                "sampler": ["11", 0],
                "sigmas": ["10", 0],
                "latent_image": ["9", 0],
            },
        },
        "14": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["4", 0]}},
        "15": {
            "class_type": "SaveImage",
            "inputs": {"images": ["14", 0], "filename_prefix": _prefix("ideogram-4")},
        },
    }


# From template image_qwen_image_2_1_image_edit.json (custom size on: the canvas is width x height)
def qwen_image_21_edit(
    prompt: str, *, images: Sequence[str], seed: int, width: int, height: int
) -> Graph:
    encode: dict[str, Any] = {
        "clip": ["3", 0],
        "vae": ["4", 0],
        "prompt": prompt,
        "negative_prompt": "",
        "resolution": 0,
    }
    graph: Graph = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "qwen_image_2.1_bf16.safetensors", "weight_dtype": "default"},
        },
        "2": {
            "class_type": "QwenImage21Cache",
            "inputs": {"model": ["1", 0], "device": "auto", "dtype": "default"},
        },
        "3": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen3vl_8b_bf16.safetensors",
                "type": "qwen_image",
                "device": "default",
            },
        },
        "4": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "qwen_image_2.1_vae_bf16.safetensors"},
        },
        "5": {"class_type": "TextEncodeQwenImage21", "inputs": encode},
        "6": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["2", 0],
                "positive": ["5", 0],
                "negative": ["5", 1],
                "latent_image": ["6", 0],
                "seed": seed,
                "steps": 25,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
            },
        },
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["4", 0]}},
        "9": {
            "class_type": "SaveImage",
            "inputs": {"images": ["8", 0], "filename_prefix": _prefix("qwen-image-2.1")},
        },
    }
    for i, ((load,), name) in enumerate(zip(_reference_ids(images, 1), images, strict=True)):
        graph[load] = {"class_type": "LoadImage", "inputs": {"image": name}}
        encode[f"images.image_{i + 1}"] = [load, 0]
    return graph


# From template image_flux2_fp8.json (reference path; Turbo LoRA off)
def flux2_dev_edit(
    prompt: str, *, images: Sequence[str], seed: int, width: int, height: int
) -> Graph:
    chains = _reference_ids(images, 4)
    graph = flux2_dev_t2i(prompt, seed=seed, width=width, height=height)
    conditioning: list[Any] = ["5", 0]  # FluxGuidance, then one ReferenceLatent per image
    for (load, scale, encode, reference), name in zip(chains, images, strict=True):
        graph[load] = {"class_type": "LoadImage", "inputs": {"image": name}}
        graph[scale] = {
            "class_type": "ImageScaleToTotalPixels",
            "inputs": {
                "image": [load, 0],
                "upscale_method": "area",
                "megapixels": 1.0,
                "resolution_steps": 1,
            },
        }
        graph[encode] = {
            "class_type": "VAEEncode",
            "inputs": {"pixels": [scale, 0], "vae": ["3", 0]},
        }
        graph[reference] = {
            "class_type": "ReferenceLatent",
            "inputs": {"conditioning": conditioning, "latent": [encode, 0]},
        }
        conditioning = [reference, 0]
    graph["6"]["inputs"]["conditioning"] = conditioning
    return graph


# From template image_flux2_klein_image_edit_4b_distilled.json
def flux2_klein_4b_edit(
    prompt: str, *, images: Sequence[str], seed: int, width: int, height: int
) -> Graph:
    chains = _reference_ids(images, 5)
    graph = flux2_klein_4b_t2i(prompt, seed=seed, width=width, height=height)
    positive: list[Any] = ["4", 0]  # CLIPTextEncode
    negative: list[Any] = ["5", 0]  # ConditioningZeroOut
    for (load, scale, encode, ref_pos, ref_neg), name in zip(chains, images, strict=True):
        graph[load] = {"class_type": "LoadImage", "inputs": {"image": name}}
        graph[scale] = {
            "class_type": "ImageScaleToTotalPixels",
            "inputs": {
                "image": [load, 0],
                "upscale_method": "nearest-exact",
                "megapixels": 1.0,
                "resolution_steps": 1,
            },
        }
        graph[encode] = {
            "class_type": "VAEEncode",
            "inputs": {"pixels": [scale, 0], "vae": ["3", 0]},
        }
        graph[ref_pos] = {
            "class_type": "ReferenceLatent",
            "inputs": {"conditioning": positive, "latent": [encode, 0]},
        }
        graph[ref_neg] = {
            "class_type": "ReferenceLatent",
            "inputs": {"conditioning": negative, "latent": [encode, 0]},
        }
        positive, negative = [ref_pos, 0], [ref_neg, 0]
    graph["6"]["inputs"] |= {"positive": positive, "negative": negative}
    return graph


# The template's negative prompt, verbatim (Wan's standard Chinese negative).
_WAN_NEGATIVE = "\uff0c".join(
    (
        "色调艳丽",
        "过曝",
        "静态",
        "细节模糊不清",
        "字幕",
        "风格",
        "作品",
        "画作",
        "画面",
        "静止",
        "整体发灰",
        "最差质量",
        "低质量",
        "JPEG压缩残留",
        "丑陋的",
        "残缺的",
        "多余的手指",
        "画得不好的手部",
        "画得不好的脸部",
        "畸形的",
        "毁容的",
        "形态畸形的肢体",
        "手指融合",
        "静止不动的画面",
        "杂乱的背景",
        "三条腿",
        "背景人很多",
        "倒着走",
    )
)


def _save_video(video: list[Any], model: str) -> dict[str, Any]:
    return {
        "class_type": "SaveVideo",
        "inputs": {
            "video": video,
            "filename_prefix": _prefix(model),
            "format": "auto",
            "format.codec": "auto",
        },
    }


# From template video_ltx2_5_i2v.json (prompt enhancer off; two-stage: half size, then x2)
def ltx_25_i2v(
    prompt: str, *, image: str, seed: int, width: int, height: int, frames: int
) -> Graph:
    fps = 24

    def guider() -> dict[str, Any]:  # one per stage, as in the template
        return {
            "class_type": "LTXVDualCFGGuider",
            "inputs": {
                "model": ["1", 0],
                "positive": ["11", 0],
                "negative": ["11", 1],
                "video_cfg": 1.0,
                "audio_cfg": 1.0,
            },
        }

    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "ltx-2.5-22b-distilled-transformer-bf16.safetensors",
                "weight_dtype": "default",
            },
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "gemma4-12b-with-proj-ltx-2.5-bf16.safetensors",
                "type": "ltxv",
                "device": "default",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "ltx-2.5-video-vae-bf16.safetensors"},
        },
        "4": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "ltx-2.5-audio-vae-bf16.safetensors"},
        },
        "5": {
            "class_type": "LatentUpscaleModelLoader",
            "inputs": {"model_name": "ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors"},
        },
        "6": {"class_type": "LoadImage", "inputs": {"image": image}},
        "7": {
            "class_type": "ResizeImageMaskNode",
            "inputs": {
                "input": ["6", 0],
                "resize_type": "scale longer dimension",
                "resize_type.longer_size": 1536,
                "scale_method": "lanczos",
            },
        },
        "8": {"class_type": "LTXVPreprocess", "inputs": {"image": ["7", 0], "img_compression": 18}},
        "9": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "10": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["2", 0],
                "text": "pc game, console game, video game, cartoon, childish, ugly",
            },
        },
        "11": {
            "class_type": "LTXVConditioning",
            "inputs": {"positive": ["9", 0], "negative": ["10", 0], "frame_rate": float(fps)},
        },
        "12": {
            "class_type": "EmptyLTXVLatentVideo",
            "inputs": {
                "width": width // 2,
                "height": height // 2,
                "length": frames,
                "batch_size": 1,
            },
        },
        "13": {
            "class_type": "LTXVImgToVideoInplace",
            "inputs": {
                "vae": ["3", 0],
                "image": ["8", 0],
                "latent": ["12", 0],
                "strength": 0.7,
                "bypass": False,
            },
        },
        "14": {
            "class_type": "LTXVEmptyLatentAudio",
            "inputs": {
                "frames_number": frames,
                "frame_rate": fps,
                "batch_size": 1,
                "audio_vae": ["4", 0],
            },
        },
        "15": {
            "class_type": "LTXVConcatAVLatent",
            "inputs": {"video_latent": ["13", 0], "audio_latent": ["14", 0]},
        },
        "16": guider(),
        "17": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler_ancestral"}},
        "18": {
            "class_type": "ManualSigmas",
            "inputs": {
                "sigmas": "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"
            },
        },
        "19": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "20": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["19", 0],
                "guider": ["16", 0],
                "sampler": ["17", 0],
                "sigmas": ["18", 0],
                "latent_image": ["15", 0],
            },
        },
        "21": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["20", 0]}},
        "22": {
            "class_type": "LTXVLatentUpsampler",
            "inputs": {"samples": ["21", 0], "upscale_model": ["5", 0], "vae": ["3", 0]},
        },
        "23": {
            "class_type": "LTXVImgToVideoInplace",
            "inputs": {
                "vae": ["3", 0],
                "image": ["8", 0],
                "latent": ["22", 0],
                "strength": 1.0,
                "bypass": False,
            },
        },
        "24": {
            "class_type": "LTXVConcatAVLatent",
            "inputs": {"video_latent": ["23", 0], "audio_latent": ["21", 1]},
        },
        "25": guider(),
        "26": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler_ancestral"}},
        "27": {"class_type": "ManualSigmas", "inputs": {"sigmas": "0.85, 0.7250, 0.4219, 0.0"}},
        "28": {"class_type": "RandomNoise", "inputs": {"noise_seed": 42}},  # fixed in the template
        "29": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["28", 0],
                "guider": ["25", 0],
                "sampler": ["26", 0],
                "sigmas": ["27", 0],
                "latent_image": ["24", 0],
            },
        },
        "30": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["29", 0]}},
        "31": {
            "class_type": "VAEDecodeTiled",
            "inputs": {
                "samples": ["30", 0],
                "vae": ["3", 0],
                "tile_size": 512,
                "overlap": 64,
                "temporal_size": 64,
                "temporal_overlap": 16,
            },
        },
        "32": {
            "class_type": "LTXVAudioVAEDecode",
            "inputs": {"samples": ["30", 1], "audio_vae": ["4", 0]},
        },
        "33": {
            "class_type": "CreateVideo",
            "inputs": {"images": ["31", 0], "audio": ["32", 0], "fps": float(fps), "bit_depth": 8},
        },
        "34": _save_video(["33", 0], "ltx-2.5"),
    }


# From template video_wan2_2_14B_i2v.json (the 4-step lightx2v LoRA path)
def wan22_i2v(prompt: str, *, image: str, seed: int, width: int, height: int, frames: int) -> Graph:
    def sampler(model: str, latent: list[Any], **stage: Any) -> dict[str, Any]:
        return {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": [model, 0],
                "positive": ["12", 0],
                "negative": ["12", 1],
                "latent_image": latent,
                "steps": 4,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                **stage,
            },
        }

    def lora(model: str, name: str) -> dict[str, Any]:
        return {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {"model": [model, 0], "lora_name": name, "strength_model": 1.0},
        }

    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
                "weight_dtype": "default",
            },
        },
        "2": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
                "weight_dtype": "default",
            },
        },
        "3": lora("1", "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors"),
        "4": lora("2", "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors"),
        "5": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["3", 0], "shift": 5.0}},
        "6": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["4", 0], "shift": 5.0}},
        "7": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "umt5_xxl_fp16.safetensors",
                "type": "wan",
                "device": "default",
            },
        },
        "8": {"class_type": "VAELoader", "inputs": {"vae_name": "wan_2.1_vae.safetensors"}},
        "9": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["7", 0], "text": prompt}},
        "10": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["7", 0], "text": _WAN_NEGATIVE}},
        "11": {"class_type": "LoadImage", "inputs": {"image": image}},
        "12": {
            "class_type": "WanImageToVideo",
            "inputs": {
                "positive": ["9", 0],
                "negative": ["10", 0],
                "vae": ["8", 0],
                "start_image": ["11", 0],
                "width": width,
                "height": height,
                "length": frames,
                "batch_size": 1,
            },
        },
        "13": sampler(
            "5",
            ["12", 2],
            add_noise="enable",
            noise_seed=seed,
            start_at_step=0,
            end_at_step=2,
            return_with_leftover_noise="enable",
        ),
        "14": sampler(
            "6",
            ["13", 0],
            add_noise="disable",
            noise_seed=0,
            start_at_step=2,
            end_at_step=4,
            return_with_leftover_noise="disable",
        ),
        "15": {"class_type": "VAEDecode", "inputs": {"samples": ["14", 0], "vae": ["8", 0]}},
        "16": {
            "class_type": "CreateVideo",
            "inputs": {"images": ["15", 0], "fps": 16.0, "bit_depth": 8},
        },
        "17": _save_video(["16", 0], "wan2.2-i2v"),
    }


# From template video_minimax_h3_i2v.json @ 98fd32c (Lightning LoRA off: 20 steps; fp16 video VAE)
def minimax_h3_i2v(
    prompt: str, *, image: str, seed: int, width: int, height: int, frames: int
) -> Graph:
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
                "weight_dtype": "default",
            },
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
                "type": "minimax",
                "device": "default",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"},
        },
        "4": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"},
        },
        "5": {"class_type": "LoadImage", "inputs": {"image": image}},
        "6": {  # encodes the prompt itself; returns the conditioning and the AV latent
            "class_type": "MiniMaxH3ImageToVideo",
            "inputs": {
                "clip": ["2", 0],
                "vae": ["3", 0],
                "first_frame": ["5", 0],
                "prompt": prompt,
                "width": width,
                "height": height,
                "length": frames,
            },
        },
        "7": {"class_type": "BasicGuider", "inputs": {"model": ["1", 0], "conditioning": ["6", 0]}},
        "8": {
            "class_type": "BasicScheduler",
            "inputs": {"model": ["1", 0], "scheduler": "simple", "steps": 20, "denoise": 1.0},
        },
        "9": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "10": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "11": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["10", 0],
                "guider": ["7", 0],
                "sampler": ["9", 0],
                "sigmas": ["8", 0],
                "latent_image": ["6", 1],
            },
        },
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
        "13": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["11", 0], "vae": ["4", 0]}},
        "14": {
            "class_type": "CreateVideo",
            "inputs": {"images": ["12", 0], "audio": ["13", 0], "fps": 24.0, "bit_depth": 8},
        },
        "15": _save_video(["14", 0], "minimax-h3"),
    }


T2I_BUILDERS: dict[str, T2IBuilder] = {
    "flux2-dev": flux2_dev_t2i,
    "flux2-klein-4b": flux2_klein_4b_t2i,
    "qwen-image-2.1": qwen_image_21_t2i,
    "z-image-turbo": z_image_turbo_t2i,
    "hidream-i1-full": hidream_i1_full_t2i,
    "ideogram-4": ideogram_4_t2i,
}
EDIT_BUILDERS: dict[str, EditBuilder] = {
    "qwen-image-2.1": qwen_image_21_edit,
    "flux2-dev": flux2_dev_edit,
    "flux2-klein-4b": flux2_klein_4b_edit,
}
I2V_BUILDERS: dict[str, I2VBuilder] = {
    "ltx-2.5": ltx_25_i2v,
    "wan2.2-i2v": wan22_i2v,
    "minimax-h3": minimax_h3_i2v,
}

_SAMPLE: dict[str, Any] = {"seed": 11, "width": 1024, "height": 576}


def sample_graphs() -> dict[str, Graph]:
    graphs: dict[str, Graph] = {}
    for model, t2i in T2I_BUILDERS.items():
        graphs[f"t2i:{model}"] = t2i("a front porch", **_SAMPLE)
    for model, edit in EDIT_BUILDERS.items():
        graphs[f"edit:{model}"] = edit("the same man", images=["ref.png"], **_SAMPLE)
    for model, i2v in I2V_BUILDERS.items():
        graphs[f"i2v:{model}"] = i2v("he walks", image="key.png", frames=33, **_SAMPLE)
    return graphs
