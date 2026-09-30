# Open-Weight Image Models for Hailuo and LTX Video Seeding

> **Provenance.** A deep-research report by another agent, pasted by the owner on 2026-09-27 and
> committed verbatim below this note on 2026-09-29. Its model facts were not verified when it was
> written. It started the synthbench work: the design is
> `docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md`.
>
> **Superseded picks.** The P1 bake-off (`docs/benchmarks/synthbench/p1-bakeoff.md`, PR #6697)
> measured its candidates on this project's GPU and scenes. The owner's picks (spec rev 2, §3.2)
> are FLUX.2 [dev] for every still and MiniMax-H3 turbo (4-step 768p LoRA) for clips. This report
> did not consider local MiniMax-H3; the owner added it to the bake-off. Its licensing section is
> moot for this project (owner ruling 2026-09-25), except MiniMax-H3's territorial terms, which
> the bake-off report records (R3).

## Executive answer

For a 48–80 GB GPU and a workflow centered on photorealistic, cinematically consistent seed frames, the strongest stack is **Qwen-Image-2.1 for multi-reference continuity and storyboard editing**, **FLUX.2 [dev] for maximum photorealistic hero-frame quality**, and **Z-Image-Turbo for inexpensive, high-volume exploration**. **Ideogram 4 Quality** is also a top-tier choice when exact composition, native 2K output, typography, signage, or product layout matters, but it is less clearly differentiated for recurring-character workflows than Qwen-Image-2.1 or FLUX.2 [dev].[^1][^2][^3]

A practical production choice is therefore:

- **Primary continuity model:** [Qwen/Qwen-Image-2.1](https://huggingface.co/Qwen/Qwen-Image-2.1), especially for creating shot variants from a canonical person, wardrobe, prop, and environment reference set. It currently leads the open-weight category in Artificial Analysis’ blind-vote arena with an Elo of 1035 and accepts as many as ten reference images.[^2][^1]
- **Primary hero-frame model:** [black-forest-labs/FLUX.2-dev](https://huggingface.co/black-forest-labs/FLUX.2-dev), especially for high-end skin, materials, lighting, hands, and cinematic photographic texture. It is a 32B generation-and-editing model, supports multi-reference workflows, and is well suited to the available 48–80 GB hardware.[^4][^3][^5]
- **Primary batch ideation model:** [Tongyi-MAI/Z-Image-Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo), particularly when hundreds of visual candidates must be generated quickly before promoting a few into the continuity pipeline. It is Apache 2.0 and is among Hugging Face’s most-downloaded modern image checkpoints.[^6][^7]
- **Layout-specialist model:** [ideogram-ai/ideogram-4-nf4](https://huggingface.co/ideogram-ai/ideogram-4-nf4), when shots need tightly specified object placement, exact palettes, signs, labels, screens, or titles. Its structured JSON prompts support bounding boxes, color palettes, broad aspect ratios, and native output up to 2K.[^8][^9][^10]

The best video workflow is **not** to generate each shot independently from text. Build a canonical visual asset pack, derive every shot frame through reference-based editing, then animate those approved frames with Hailuo or LTX. Community workflows repeatedly converge on character sheets, controlled keyframes, short clips, frame extraction, low-denoise repair, and chaining rather than asking one model to solve identity, staging, motion, and long-duration continuity simultaneously.[^11][^12][^13]

## What “popular” means

Popularity and performance need separate measurements. Hugging Face’s download counter reflects the previous month and can be influenced by automated pipelines, repackaged checkpoints, quantizations, and dependency downloads; it is evidence of ecosystem activity, not a clean quality ranking. Blind human-preference arenas are better evidence for output quality, while licenses and workflow support determine whether a model is actually usable in production.[^7][^1]

As of September 27, 2026, Hugging Face’s text-to-image page sorted by downloads places SDXL Base at about 3.56 million monthly downloads, Stable Diffusion 1.5 at 1.76 million, SDXL Turbo at 981,000, FLUX.1 [dev] at 701,000, Z-Image-Turbo at 617,000, FLUX.1 [schnell] at 518,000, and Qwen-Image at 295,000. A community Qwen-Image-2.1 GGUF repository appears at 716,000, illustrating why repositories and repacks should not be added together or treated as distinct users.[^7]

| Model family        |                                                                        Current popularity signal |                                     Current quality signal | Interpretation                                                                |
| ------------------- | -----------------------------------------------------------------------------------------------: | ---------------------------------------------------------: | ----------------------------------------------------------------------------- |
| Stable Diffusion XL |                                                       3.56M monthly downloads for SDXL Base[^14] |                      Elo 677 for the original SDXL 1.0[^1] | Largest mature ecosystem; no longer frontier base quality                     |
| FLUX.1              |                                                           701K for [dev], 518K for [schnell][^7] |                   Elo 841 for [dev], 802 for [schnell][^1] | Still heavily used because of tooling, LoRAs, and familiar workflows          |
| Z-Image             |                                    617K for official Turbo plus 444K for a major GGUF repack[^7] |                                      Elo 940 for Turbo[^1] | Strong adoption-to-compute ratio and excellent batch economics                |
| Qwen Image          | 295K for original Qwen-Image; substantial activity around Lightning and new 2.1 repacks[^7][^15] |          Qwen-Image-2.1 leads open weights at Elo 1035[^1] | Current quality leader, but 2.1 is too new for long-term adoption data        |
| FLUX.2              |                                                        240K for the Klein 4B FP8 repository[^16] | Elo 1000 for [dev], 940 for Klein 9B, 864 for Klein 4B[^1] | [dev] is the quality option; Klein is the speed and permissive-license option |
| Ideogram 4          |                                   Newer, gated repositories; download counts are less comparable |             Elo 1010 for Quality and 1003 for standard[^1] | Second only to Qwen-Image-2.1 among the cited open-weight checkpoints         |

## Recommended models

### Qwen-Image-2.1

**Best role:** canonical asset creation, reference-driven shot design, character/product preservation, and local corrective editing.

Qwen-Image-2.1 is the strongest default for a storyboard-to-video pipeline because generation and editing are unified, and the official release supports up to ten reference images, localized edits, masks, fidelity preservation, and multi-subject composition. This lets each shot inherit separate references for the actor, wardrobe, prop, environment, and visual grade instead of relying on a prose description to recreate them.[^17][^2]

Its main drawback is licensing. The weights are open and downloadable, but the Qwen Research License limits the materials to non-commercial use unless a separate commercial license is obtained. It is therefore a high-confidence research, evaluation, or pre-production recommendation, but not automatically a commercial-production-safe choice.[^18]

**Recommended use:** generate or approve one hero portrait, produce front/profile/three-quarter/back views, create wardrobe and prop references, then use image editing—not fresh text-to-image generation—to place those assets into each storyboard composition. Keep each reference in a fixed slot and state what it contributes: “image 1 identity, image 2 wardrobe, image 3 environment, image 4 lighting.” This mirrors the reference-role workflow recommended in practical Qwen guides and makes continuity failures easier to diagnose.[^19]

### FLUX.2 [dev]

**Best role:** highest-quality photorealistic hero frames and final visual polish.

FLUX.2 [dev] is a 32B rectified-flow transformer that performs text-to-image generation, image editing, and image combination. ComfyUI’s implementation emphasizes up-to-4MP photorealistic output, improved skin, fabric, lighting, and hand detail, plus multi-reference consistency; Black Forest Labs documents support for combining up to ten images.[^3][^5][^4]

On the current blind-vote leaderboard, FLUX.2 [dev] scores 1000, below Qwen-Image-2.1 at 1035 and Ideogram 4 Quality at 1010, but comfortably ahead of older FLUX.1 and SDXL models. Its practical advantage for this use case is not merely one-shot Elo: it combines cinematic photographic quality, a robust ComfyUI implementation, references, and enough model capacity to benefit from a 48–80 GB GPU.[^1]

The checkpoint uses the FLUX Non-Commercial License for non-commercial and non-production use; commercial self-hosting requires a separate license. Generated outputs have broader allowances described in the model license, but the model itself cannot simply be deployed commercially under an OSI-style license.[^20][^4]

### Ideogram 4 Quality

**Best role:** composition-sensitive establishing shots, products, signage, screens, and exact art direction.

Ideogram 4 is a 9.3B open-weight model trained around structured JSON descriptions. It supports element-level descriptions, normalized bounding boxes, color palettes, resolutions from 256 to 2048 on either axis in multiples of 16, and a native quality preset for 2048-pixel output. Those controls are unusually useful when a video seed must put a subject at a precise screen position to leave room for a pan, dolly, product reveal, or title.[^9][^10]

Artificial Analysis places Ideogram 4 Quality at Elo 1010 and standard Ideogram 4 at 1003, making them the second- and third-highest named open-weight entries after Qwen-Image-2.1 in the current table. The trade-off is its gated, non-commercial model license, so it should be treated as open weights rather than unrestricted open source.[^8][^1]

### Z-Image-Turbo

**Best role:** rapid prompt exploration, contact sheets, alternate compositions, and commercial-friendly high-volume generation.

Z-Image-Turbo is a 6B checkpoint under Apache 2.0, while the undistilled Z-Image base is positioned as the higher-capacity creative and fine-tuning foundation. The Turbo checkpoint shows roughly 617,000 monthly downloads on Hugging Face and ranks well ahead of legacy open-weight models in current arena preference, although it trails Qwen-Image-2.1, Ideogram 4, and FLUX.2 [dev].[^21][^6][^1][^7]

Community experience is mixed but actionable. Users report strong photographic results when prompts specify camera type, lens, film or sensor behavior, ordinary human traits, and imperfections rather than merely saying “photorealistic”; others report residual-noise, banding, or compressed-looking detail in flat artwork and recommend a refinement or upscale pass. For video seeding, use Z-Image-Turbo to find the shot, pose, lens, and lighting quickly, then promote the selected frame through FLUX.2 or a low-denoise image-to-image pass before animation.[^22][^23]

### FLUX.2 Klein 4B

**Best role:** permissively licensed reference editing and fast local iterations.

FLUX.2 Klein 4B unifies text-to-image, editing, and multi-reference generation and is fully Apache 2.0, unlike the 9B Klein and [dev] variants. The official FP8 repository reports about 240,000 monthly downloads, demonstrating meaningful adoption despite being much newer than FLUX.1 or SDXL.[^24][^16]

Its current arena Elo of 864 is materially below the quality leaders, so it should be viewed as a production-friendly utility model rather than the best hero-frame generator. It is particularly valuable where commercial licensing simplicity matters more than extracting the last increment of realism.[^1]

### SDXL and SD3.5

**Best role:** established LoRA, IP-Adapter, ControlNet, pose, depth, and style-control pipelines.

SDXL remains the most-downloaded text-to-image model on Hugging Face at roughly 3.56 million monthly downloads, and its ecosystem includes heavily used realism checkpoints, ControlNets, IP-Adapters, and character LoRAs. Its original base model is no longer competitive with the leading 2026 models in blind preference, but it remains valuable when deterministic pose or a mature trained character LoRA matters more than base-model aesthetics.[^14][^25][^7][^1]

Stable Diffusion 3.5 Large offers a newer Stability architecture and a ComfyUI-ready FP8 package, but its arena result also trails the newer leaders. The Stability Community License permits free commercial use only below its stated $1 million annual-revenue threshold, after which an enterprise license is required.[^26][^27][^1]

### Secondary candidates

[HiDream-I1-Full](https://huggingface.co/HiDream-ai/HiDream-I1-Full) is a 17B MIT-licensed foundation model and remains attractive when a permissive license and full-weight generation matter. [Chroma1-HD](https://huggingface.co/lodestones/Chroma1-HD) is an 8.9B Apache 2.0 FLUX.1-schnell-derived base designed for fine-tuning. Neither currently displaces Qwen-Image-2.1, Ideogram 4, FLUX.2 [dev], or Z-Image-Turbo for this specific photorealistic video-keyframe workflow, but both are sensible commercial experimentation options.[^28][^29]

## Decision matrix

| Need                                | First choice    | Alternate                             | Why                                                                            |
| ----------------------------------- | --------------- | ------------------------------------- | ------------------------------------------------------------------------------ |
| Best overall open-weight quality    | Qwen-Image-2.1  | Ideogram 4 Quality                    | Highest current open-weight arena score; strong unified editing[^1][^2]        |
| Best cinematic hero frame           | FLUX.2 [dev]    | Ideogram 4 Quality                    | Strong photorealistic detail and multi-reference editing[^3][^5]               |
| Best recurring-character storyboard | Qwen-Image-2.1  | FLUX.2 [dev]                          | Up to ten references and preservation/local-edit features[^2][^30]             |
| Fastest bulk ideation               | Z-Image-Turbo   | FLUX.2 Klein 4B                       | Distilled 6B model, high adoption, permissive license[^6][^7]                  |
| Precise framing and layout          | Ideogram 4      | Qwen-Image-2.1                        | Native bounding boxes, structured JSON, palette controls[^9][^10]              |
| Commercial-friendly weights         | Z-Image-Turbo   | FLUX.2 Klein 4B                       | Both are Apache 2.0[^6][^24]                                                   |
| Custom character LoRA/control stack | SDXL            | Qwen-Image editing then LoRA training | Deep mature ecosystem; Qwen can bootstrap a multi-angle dataset[^25][^31][^32] |
| Maximum license permissiveness      | HiDream-I1 Full | Chroma1-HD                            | MIT versus Apache 2.0[^28][^29]                                                |

## Recommended asset pipeline

### Build a canonical pack

Create a single “truth set” before generating shots:

- One neutral hero portrait with clean skin detail and visible eyes.
- Front, three-quarter, profile, and back views with the same wardrobe.
- Neutral full-body and medium-shot references.
- A small expression sheet if dialogue or emotional acting is planned.
- Separate references for wardrobe, hero props, vehicles, and locations.
- A fixed look bible: lens family, depth of field, contrast curve, grain, time of day, and palette.

Hailuo’s own consistency guidance recommends a detailed character definition, a high-resolution master image, and a three-to-five-angle turnaround; it also recommends starting with short clips and simple camera movement. Community filmmakers similarly favor one canonical character sheet with neutral lighting and several angles rather than mixing unrelated “good” portraits of the same intended character.[^13][^11]

Use Qwen-Image-2.1 or FLUX.2 [dev] to derive the turnaround from the approved portrait. If the project has enough shots to justify training, use the edited multi-angle set to train a character LoRA; community workflows commonly use Qwen Edit to expand a single reference into a synthetic dataset before LoRA training.[^31][^32]

### Design each shot

For every shot, specify four layers:

1. **Identity lock:** canonical face/body reference and character LoRA if available.
2. **Continuity lock:** exact wardrobe, prop, and location references.
3. **Cinematography:** shot size, camera height, angle, lens, focus target, depth of field, lighting direction, and grade.
4. **Motion intent:** one primary subject action and one simple camera move.

Generate a contact sheet, select a composition, then edit that winner into the precise seed rather than repeatedly sampling from scratch. Community workflows report better continuity when they reuse a single anchor image, hold the identity wording stable, and change only one variable—action, camera, or atmosphere—per branch.[^33][^34]

Save approved frames as lossless PNG. Match the intended video aspect ratio at image-generation time instead of cropping after approval; MiniMax accepts JPG, JPEG, PNG, or WebP, requires a short edge over 300 pixels, limits files to under 20 MB, and accepts aspect ratios from 2:5 to 5:2.[^35]

### Create video-ready keyframes

A good still image is not automatically a good image-to-video seed. Prefer:

- Clear subject silhouette and visible joints.
- Plausible room for the intended movement.
- No motion already frozen at an anatomically extreme pose.
- Consistent light direction and shadows.
- Minimal tiny text, jewelry, fingers over faces, or occluded limbs.
- A composition that leaves space in the direction of camera or subject travel.

For Hailuo, create one excellent opening frame. For LTX, create first and last frames—and optionally middle keyframes—that share identity, wardrobe, lens, lighting, and scene geometry. Do not jump between incompatible poses, camera axes, or backgrounds and expect interpolation to conceal the discontinuity.

## Hailuo 2.3 workflow

Hailuo 2.3 supports image-to-video and text-to-video with 768p or 1080p outputs and six- or ten-second durations; 1080p is limited to six seconds. Its official image-to-video endpoint uses the supplied image as the first frame. Current third-party documentation also notes that Hailuo 2.3 does not expose last-frame control, so shots requiring a fixed visual destination should be routed to LTX or the older Hailuo 02 first/last-frame mode.[^36][^37][^33][^35]

**Recommended operating loop:**

1. Use **Hailuo 2.3 Fast** for motion auditions when available, then rerun selected prompts in standard Hailuo 2.3 for finals. The Fast variant is explicitly image-to-video focused, while standard 2.3 prioritizes visual quality.[^33][^36]
2. Feed the approved first frame and describe what happens, not what is already visible. A practical prompt order is subject/emotion, physical action, environment motion, camera, then lighting.[^33]
3. Ask for one action and one camera move per clip. Community guidance warns that complex camera instructions fail more often and recommends simple, explicit language.[^38]
4. Produce several branches from the same image and change only one motion variable at a time.[^33]
5. For extensions, extract a clean frame from just before quality starts to degrade—not automatically the literal final frame—repair it with low-denoise image-to-image if necessary, and use it as the next first frame. Hailuo users specifically report selecting a suitable internal frame rather than blindly using the last one.[^39]
6. Keep editable handles at both ends and trim unstable frames in post. This is more robust than demanding a seamless long take from repeated generations.[^40]

**Prompt template:**

```text
The same [character], feeling [emotion], [one clear physical action].
[Environmental motion]. The camera [one simple move] in a [shot size]
with a [lens] look. [Lighting direction and quality]. Natural motion,
stable facial identity, unchanged wardrobe and environment.
```

A source image already communicates appearance, so prompts should emphasize motion and camera behavior. This principle is also explicit in LTX’s official image-to-video documentation.[^41]

## LTX workflow

LTX is the better choice when exact keyframe timing, local execution, reproducibility, or first/middle/last-frame control matters. LTX-2.3 is an open-weight DiT-based audio-video model with local execution, while the official LTX stack supports images or short videos placed at selected target frames with adjustable conditioning strengths.[^42][^43]

As of September 2026, **LTX-2.5 is the current documented generation**, so a new installation should evaluate it before locking a production pipeline to 2.3. The official ComfyUI template supports image-to-video, synchronized audio, a two-stage generate/upscale/refine path, and a separate first-frame/last-frame workflow. Existing 2.3 pipelines remain relevant because Lightricks publishes full/distilled single-stage and two-stage workflows plus IC-LoRA controls for depth, pose, edges, motion tracking, HDR, and dubbing.[^44][^41]

**Recommended LTX operating loop:**

1. Begin with the official ComfyUI I2V or FLF template rather than a large third-party graph. For LTX-2.3, use the published full or distilled two-stage workflow; for a new build, test LTX-2.5’s official template first.[^41][^44]
2. Use a single start image for organic motion, first and last images for a known destination, or first/middle/last images for shots whose staging must pass through a specific beat. ComfyUI’s LTX guide supports chaining multiple `LTXVAddGuide` nodes at selected frame positions.[^45][^46]
3. Keep the source frames at the same aspect ratio and resolution. The current official template requires width and height divisible by 32, and its frame count follows `1 + a multiple of 8`.[^41]
4. Write the prompt around movement, camera, and audio. Avoid re-describing identity in ways that conflict with the frame references.[^41]
5. Break ambitious camera moves into three-to-five key stills and interpolate short segments. Community troubleshooting consistently recommends smaller segments and simple motion descriptions rather than overloading one prompt with several actions.[^47]
6. If motion timing is critical, use IC-LoRA pose or motion tracking from a guide video. A demonstrated LTX-2.3 workflow extracts pose from footage, uses it as the control signal, and conditions identity, wardrobe, location, and lighting from the first frame.[^48]
7. Use tiled VAE decoding at high resolution and crop guide-conditioning artifacts before final decode when applicable; community FLF workflows report that these choices reduce end-frame jumps and memory pressure.[^49][^50]

### Choosing LTX guides

| Shot type                   | Guides                                   | Recommended approach                                                                  |
| --------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------- |
| Portrait reaction           | First frame only                         | Let performance evolve naturally; keep the camera subtle                              |
| Product reveal              | First + last                             | Precisely define the opening and final product composition                            |
| Walk or orbit               | First + middle + last                    | Use compatible poses and camera positions across three keys                           |
| Complex choreography        | First frame + pose/motion control        | Drive timing from reference motion with IC-LoRA[^48]                                  |
| Long movement through space | Three to five stills over short segments | Render each segment, inspect boundaries, then stitch[^47]                             |
| Seamless loop               | Matching first/last composition          | Expect trimming and experimentation; FLF alone does not guarantee a perfect loop[^49] |

## End-to-end production recipe

### Fast exploration

1. Generate 32–100 visual candidates with Z-Image-Turbo using explicit camera, lens, lighting, and subject-imperfection language.[^22]
2. Select two to five compositions, not merely the prettiest faces.
3. Rebuild or polish the winners in FLUX.2 [dev], Qwen-Image-2.1, or Ideogram 4.
4. Confirm that every winning frame shares the project’s palette, lens family, wardrobe, and environment logic.

### Continuity pass

1. Use Qwen-Image-2.1 to place the canonical identity, outfit, prop, and environment into each storyboard frame through multi-reference editing.[^2]
2. Generate angle-specific references rather than forcing a frontal portrait to define a profile or rear view.
3. If consistency is still insufficient, train a character LoRA on the corrected multi-angle set and combine it with pose/depth guidance where supported.[^32][^31]
4. Compare the face, hairline, ears, wardrobe seams, jewelry, prop geometry, and environmental landmarks side by side before animation.

### Animation pass

1. Route expressive, effects-heavy, or natural one-start-frame shots to Hailuo 2.3.
2. Route exact transitions, camera destinations, multi-keyframe staging, local rendering, and pose-driven shots to LTX.
3. Generate short clips and preserve handles for editing.
4. Reject clips early if identity or geometry fails; do not spend time upscaling a bad motion sample.
5. Extract a clean bridge frame, repair it at low denoise, and continue only from the corrected image.

### Finishing pass

1. Trim unstable opening and closing frames.
2. Match cuts on action rather than attempting invisible model-to-model morphs.
3. Apply one project-wide color transform and grain layer to reduce visible variation between image models.
4. Upscale only approved clips, then interpolate frames if needed.
5. Keep seed images, prompts, references, LoRA versions, model hashes, and video-generation settings with every shot.

Creators repeatedly report that pristine keyframes save more rework than extra effort spent on text-to-video prompting, and that lossless PNG or FFV1 intermediates reduce color and compression drift during extension workflows.[^51][^12]

## Licensing guide

“Open weights” does not mean “open source” or “commercially unrestricted.” The most capable current checkpoints include non-commercial licenses, while several slightly lower-ranked models use Apache 2.0 or MIT.

| Model           | Weight availability               | License posture                                        | Commercial implication                                                              |
| --------------- | --------------------------------- | ------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| Qwen-Image-2.1  | Open, gated by license acceptance | Qwen Research License                                  | Non-commercial unless separately licensed[^18]                                      |
| FLUX.2 [dev]    | Open, gated                       | FLUX Non-Commercial License                            | Model use is non-commercial/non-production unless separately licensed[^20]          |
| Ideogram 4      | Open, gated                       | Ideogram 4 Non-Commercial                              | Treat as non-commercial unless separately authorized[^8]                            |
| Z-Image / Turbo | Open                              | Apache 2.0                                             | Permissive commercial model use, subject to law and downstream obligations[^6][^21] |
| FLUX.2 Klein 4B | Open                              | Apache 2.0                                             | Permissive commercial model use[^24]                                                |
| HiDream-I1 Full | Open                              | MIT for the transformer; component licenses also apply | Generally commercial-friendly, but review bundled VAE and encoders[^28]             |
| Chroma1-HD      | Open                              | Apache 2.0                                             | Permissive commercial use[^29]                                                      |
| SD3.5 Large     | Open/gated                        | Stability Community License                            | Free commercial use below $1M annual revenue; enterprise license above it[^26]      |

Before commercial deployment, review the exact checkpoint license, component licenses, acceptable-use terms, and the rules for derivatives and hosted services. Community “uncensored,” merged, quantized, or repackaged repositories do not automatically provide rights beyond the upstream model.

## Final recommendation

For this hardware and use case, install **Qwen-Image-2.1, FLUX.2 [dev], Z-Image-Turbo, and Ideogram 4 NF4** in one ComfyUI environment. Use Qwen for the continuity graph, FLUX.2 [dev] for premium photographic rendering, Z-Image-Turbo for breadth, and Ideogram for shots needing exact spatial art direction.

If the output will be commercial and separate licenses are not desirable, substitute **Z-Image-Turbo + FLUX.2 Klein 4B**, retain **SDXL** for its LoRA/ControlNet ecosystem, and evaluate **HiDream-I1 Full** as the permissively licensed high-capacity alternative. For animation, send open-ended performance shots to Hailuo 2.3 and controlled first/middle/last-frame shots to LTX; this division aligns each video model with the conditioning mode it handles most naturally.[^25][^6][^24][^45][^28][^35][^41]

---

## References

1. [Text to Image Leaderboard - Top AI Image Models](https://artificialanalysis.ai/image/leaderboard/text-to-image) - Find the best Text to Image models, see rankings from blind votes, and compare quality, generation s...

2. [Qwen-Image-2.1: Compact, Efficient, and Unified ...](https://qwen.ai/blog?id=qwen-image-2.1) - Qwen-Image-2.1 improves editing in four areas: multiple reference images, local editing, fidelity pr...

3. [ComfyUI Flux.2 Dev Example](https://docs.comfy.org/tutorials/flux/flux-2-dev) - This guide provides a brief introduction to the Flux.2 model and guides you through using the Flux.2...

4. [black-forest-labs/FLUX.2-dev](https://huggingface.co/black-forest-labs/FLUX.2-dev) - Generated outputs can be used for personal, scientific, and commercial purposes, as described in the...

5. [FLUX.2: Frontier Visual Intelligence](https://bfl.ai/blog/flux-2) - 2 now provides multi-reference support, with the ability to combine up to 10 images into a novel out...

6. [Tongyi-MAI/Z-Image-Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo) - License: apache-2.0 Model card Files Files and versions. Use this model Instructions to use Tongyi-M...

7. [Text-to-Image Models](https://huggingface.co/models?pipeline_tag=text-to-image&sort=downloads) - Text-to-Image • 3B • Updated Mar 14, 2024 • 343k • • 771 · nphSi/Z-Image-Lora. Text-to-Image • Updat...

8. [ideogram-ai/ideogram-4-nf4](https://huggingface.co/ideogram-ai/ideogram-4-nf4) - Ideogram 4 is Ideogram's first open weight text-to-image model. It is a state-of-the-art foundation ...

9. [ideogram-ai/ideogram-4-fp8](https://huggingface.co/ideogram-ai/ideogram-4-fp8) - Ideogram 4 is Ideogram's first open weight text-to-image model. It introduces a new structured JSON ...

10. [Ideogram 4.0 Technical Details: Open model at the ...](https://ideogram.ai/blog/ideogram-4.0/) - Ideogram 4.0 is a 9.3B parameter open-weight text-to-image model. The model is trained exclusively o...

11. [How to Create Consistent Characters in AI Videos](https://hailuoai.video/pages/blog/ai-video-character-consistency-guide) - Keep AI characters looking the same using subject reference features. Learn how to lock facial ident...

12. [Unlimited length videos with wan, comfyui, and gimp (no ...](https://www.reddit.com/r/comfyui/comments/1ou24ok/unlimited_length_videos_with_wan_comfyui_and_gimp/) - Manually process the keyframes in an image editor to make sure the backgrounds and details match. Cr...

13. [The real skill in AI video is picking the right reference TYPE ...](https://www.reddit.com/r/comfyui/comments/1ul9iei/the_real_skill_in_ai_video_is_picking_the_right/) - A plain reference image gives you almost no motion control, you steer the layout and performance mos...

14. [stabilityai/stable-diffusion-xl-base-1.0](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0) - While the capabilities of image generation models are impressive, they can also reinforce or exacerb...

15. [Models – Hugging Face](https://huggingface.co/models) - Explore machine learning models. Text-to-Image. Image-Text-to-Text

16. [black-forest-labs/FLUX.2-klein-4b-fp8](https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8) - 4B is a 4 billion parameter rectified flow transformer capable of generating images. Downloads last ...

17. [Qwen/Qwen-Image-2.1](https://huggingface.co/Qwen/Qwen-Image-2.1) - Qwen-Image-2.1, a unified text-to-image generation and image editing model. This model is licensed u...

18. [LICENSE · Qwen/Qwen-Image-2.1 at main](https://huggingface.co/Qwen/Qwen-Image-2.1/blob/main/LICENSE) - 1. Definitions · 2. Grant of Rights · 3. Redistribution · 4. Rules of use · 5. Intellectual Property...

19. [Qwen-Image 2.1 AI Image Generation & Editing Guide](https://www.weshop.ai/solutions/models/qwen-image-2-1-ai-image-generation-and-editing-guide) - Learn how Qwen-Image 2.1 handles text-to-image creation, reference-image editing, and multi-referenc...

20. [LICENSE.md · black-forest-labs/FLUX.2-dev at main](https://huggingface.co/black-forest-labs/FLUX.2-dev/blob/main/LICENSE.md) - This FLUX Model is licensed by Black Forest Labs Inc. under the FLUX Non-Commercial License. Copyrig...

21. [Tongyi-MAI/Z-Image · Hugging Face](https://huggingface.co/Tongyi-MAI/Z-Image) - License: apache-2.0 Model card Files Files and versions. Z-Image-Turbo is built for speed, Z-Image i...

22. [The Secrets of Realism, Consistency and Variety with Z ...](https://www.reddit.com/r/StableDiffusion/comments/1pcxtba/the_secrets_of_realism_consistency_and_variety/) - The key point is that out of the box, Z Image Turbo will pump out perfect digital images of beautifu...

23. [Z Image Turbo can be quite good. Except for the highly ...](https://www.reddit.com/r/StableDiffusion/comments/1pdr11d/z_image_turbo_can_be_quite_good_except_for_the/) - It's so much more noticable for artwork and anime style images. Can't get clean lines or even simple...

24. [black-forest-labs/FLUX.2-klein-4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) - The FLUX.2 [klein] model family are our fastest image models to date. FLUX.2 [klein] unifies generat...

25. [Models](https://huggingface.co/models?p=0&sort=downloads&search=controlnet) - Explore machine learning models. Featherless. Most downloads xinsir/controlnet-union-sdxl-1.0 Text-t...

26. [stabilityai/stable-diffusion-3.5-large](https://huggingface.co/stabilityai/stable-diffusion-3.5-large) - Please note: This model is released under the Stability Community License. Visit Stability AI to lea...

27. [Comfy-Org/stable-diffusion-3.5-fp8](https://huggingface.co/Comfy-Org/stable-diffusion-3.5-fp8) - Stable Diffusion 3.5 FP8. Repackaged model files for ComfyUI. Original model repository: https://hug...

28. [HiDream-ai/HiDream-I1-Full](https://huggingface.co/HiDream-ai/HiDream-I1-Full) - HiDream-I1 is a new open-source image generative foundation model with 17B parameters that achieves ...

29. [lodestones/Chroma1-HD](https://huggingface.co/lodestones/Chroma1-HD) - It is fully Apache 2.0 licensed, ensuring that anyone can use, modify, and build upon it. As a base ...

30. [FLUX.2 Image Editing](https://docs.bfl.ml/flux_2/flux2_image_editing) - Edit images with FLUX.2 using text prompts and multi-reference support for up to 10 images, with adv...

31. [Realistic character consistency in ComfyUI - looking for a ...](https://www.reddit.com/r/StableDiffusion/comments/1pn1q76/realistic_character_consistency_in_comfyui/) - Qwen Edit, at least is pretty consistent. After that to refine it, create new pictures with it, and ...

32. [FREE Face Dataset generation workflow for lora training ...](https://www.reddit.com/r/StableDiffusion/comments/1o6xjwu/free_face_dataset_generation_workflow_for_lora/) - The workflow works with a base face image. That image can be generated from whatever model you want ...

33. [Hailuo AI Prompts Guide for Consistent Characters](https://phygital.plus/blog/hailuo-ai-prompts-guide-character-consistency/) - Use Hailuo for expressive AI videos with stronger character consistency. Learn version differences, ...

34. [Qwen 2.1 story boarding : r/StableDiffusion](https://www.reddit.com/r/StableDiffusion/comments/1wm5wag/qwen_21_story_boarding/) - Use the provided image strictly as the character reference. Preserve the character's appearance and ...

35. [Image-to-Video Task - Models - MiniMax API Docs](https://platform.minimax.io/docs/api-reference/video-generation-i2v)

36. [MiniMax and VEED: Introducing Hailuo-2.3 to Bring AI ...](https://www.minimax.io/news/minimax-and-veed-hailuo-23-for-pro-level-ai-video) - MiniMax-Hailuo-2.3 Supports both text and image model inputs. Generates videos in 768p or 1080p, wit...

37. [MiniMax Hailuo 2.3 | Video Generation API](https://replicate.com/minimax/hailuo-2.3) - Input: Image only · Resolution: 768p and 1080p 1080p videos are limited to 6-second duration · Durat...

38. [Hailuo Minimax Prompts: The Ultimate Guide for Creators ...](https://blog.segmind.com/hailuo-minimax-ai-video-prompt-guide) - A clear description of the subject or character is essential for consistency throughout your video.

39. [Keyframes, Start Frame and End Frame : r/HailuoAiOfficial](https://www.reddit.com/r/HailuoAiOfficial/comments/1hxausg/keyframes_start_frame_and_end_frame/) - Have you tried a PNG image sequence? Open Shot video editor is free and you can download your video ...

40. [LTX Sequencer - output video has blurred image at end](https://www.reddit.com/r/comfyui/comments/1tse9m9/ltx_sequencer_output_video_has_blurred_image_at/) - When the video is generated, the last few frames of the video is always a blurred image of the input...

41. [Image-to-Video Workflow for Beginners | LTX Documentation](https://docs.ltx.io/open-source-model/usage-guides/image-to-video) - This tutorial shows you how to generate a video with synchronized audio from a source image and a su...

42. [Lightricks/LTX-2.3](https://huggingface.co/Lightricks/LTX-2.3) - For image-to-video, LTX-2.3 is a DiT-based audio-video foundation model designed to generate synchro...

43. [Lightricks/LTX-Video](https://huggingface.co/Lightricks/LTX-Video) - LTX-Video is the first DiT-based video generation model capable of generating high-quality videos in...

44. [Lightricks/ComfyUI-LTXVideo: LTX-Video Support for ...](https://github.com/Lightricks/ComfyUI-LTXVideo) - The ComfyUI-LTXVideo installation includes several example workflows. Workflows: Text/image to video...

45. [LTX-Video 0.9.5 Day-1 Support in ComfyUI! - by Jo Zhang](https://blog.comfy.org/p/ltx-video-095-day-1-support-in-comfyui) - This workflow can be used for image to video generation, including first frame, end frame, or other ...

46. [LTX 2 first and last frame control capability By TTPlanet](https://www.reddit.com/r/StableDiffusion/comments/1q7aukb/ttp_toolset_ltx_2_first_and_last_frame_control/) - What I'd really want is First Frame Last Frame guidance. So I add an image and it's used to guide th...

47. [LTX 2.3 IC-LoRA Union: Depth map bleeding into video, ...](https://www.reddit.com/r/StableDiffusion/comments/1twg8v8/ltx_23_iclora_union_depth_map_bleeding_into_video/) - I slightly modified the workflow to input both the first and the last frames to guide the generation...

48. [LTX 2.3 IC-LoRA: pose control + first frame conditioning](https://www.reddit.com/r/StableDiffusion/comments/1v74c4e/ltx_23_iclora_pose_control_first_frame/) - LTX 2.3 + IC-LoRA (pose control), conditioned on a single first frame. Pose extracted from the sourc...

49. [LTX 0.9.6 Distilled i2v with First and Last Frame ...](https://www.reddit.com/r/StableDiffusion/comments/1k43dft/ltx_096_distilled_i2v_with_first_and_last_frame/) - This workflow works like a charm. I'm still trying to create a seamless loop but it was insanely eas...

50. [LTX 2.3 First Last Frame | Seamless Video Generator](https://www.runcomfy.com/comfyui-workflows/ltx-2-3-first-last-frame-in-comfyui-keyframe-to-smooth-video) - LTX 2.3 First Last Frame workflow for ComfyUI creates seamless transitions between two images, produ...

51. [Sharing my Music Video project worked with my sons](https://www.reddit.com/r/comfyui/comments/1k2pil9/sharing_my_music_video_project_worked_with_my/) - It's an AI-generated music video. The visuals were created with ComfyUI, for image-to-video, charact...
