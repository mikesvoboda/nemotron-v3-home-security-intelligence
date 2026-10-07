# Synthbench P5a scores: 20261006T231717Z

**Conditions.** The truth is declared by the sampler and unverified; the owner's audit below gives its error rate. Stills with an ideal detector: the VLM gets each event's declared subjects and props as detections (object type and confidence 1.0, no box) and no specialist context; a real detector misses some of them, so this is optimistic. Accuracy only: the GB300 is shared, so no latency or memory figure here stands for a deployment. Ambiguous events are not scored. Comparison models may run under different conditions from the product model (a system message, a token budget, a read timeout, thinking off, a build, server flags the operator declared): the Conditions per model table in report.md lists each model's.

Each cell reads rate [95% Wilson interval] (n); under n = 10 it reads "insufficient". S2 is benign scenes scored medium or above; S3 is incidents scored at or above their level. The clustered columns resample SCENARIOS, not items (ISS-043): items share a scenario, so the Wilson interval understates the uncertainty whenever a scenario's errors come in groups; the clustered reading is the one to read when the two disagree.

## Conditions per model

| Model       | Transport | Prompt  | Thinking | Max tokens | Read timeout | Enforcement probe | Sampling           | Build           | Server settings                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ----------- | --------- | ------- | -------- | ---------- | ------------ | ----------------- | ------------------ | --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| qwen3-vl-8b | ai-vlm    | shipped | —        | 2048       | 180 s        | on                | temp 0.0, unseeded | b7972-e06088da0 | agent-gpu container vss8-dogfood, image localhost/agent-vss8/ai-vlm:sm103 (llama.cpp build reported at /props), image CMD with compose ai-vlm defaults: --model /models/qwen3vl-8b-instruct-q4km/Qwen3VL-8B-Instruct-Q4_K_M.gguf --mmproj /models/qwen3vl-8b-instruct-q4km/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf --alias Qwen3VL-8B --sleep-idle-seconds 300 --cache-type-k q8_0 --cache-type-v q8_0 --host 0.0.0.0 --port 8098 --n-gpu-layers auto --ctx-size 32768 --parallel 2 --threads 4 --threads-batch 4 --batch-size 2048 --ubatch-size 512 --cont-batching --metrics --cache-reuse 256 --jinja --flash-attn on; weights sha256 67d1659bfe71b89d50b45a4ad1a9e5b997e5bb16ce5da66a6a6167abd569e9e2 + mmproj c6ba85508d82f42590e6eb77d5340369ab6fecf107a7561d809523d8aa5f3bfd (verified before serve) |

## Run identity

- Scored at commit `8107ee63`, scoring version 4, 2026-10-06T23:17:17+00:00.
- Corpus tierb-v0; export `tierb-v0-export (outside $SYNTHBENCH_ROOT)`: 450 sets, labels sha256 `3a9b16e3212ee799ec2faa7cefdf3becbec1f26e40f0181eb9fd81f05c2c847d`; eval store `eval/tierb-v0/eval.sqlite`.
- Audit log `audits/tierb-v0/audit.jsonl`, sha256 `none yet`.
- Split: splits.json sha256 3419d89448bf3814e2be1448f0a2acf8bb950d7e20a09bf4790b1d0fe13916da; seed vss-iss016-s3-holdout-2026-10-06; holdout 6 scenarios / 64 incident items; dev 386 (209 benign)
- vLLM models: the image is pinned by digest in the operator runbook's start command; no endpoint reports it.

| Model       | Replay                         | Transport | Endpoint                          | Build           | Weights    | Replay commit |
| ----------- | ------------------------------ | --------- | --------------------------------- | --------------- | ---------- | ------------- |
| qwen3-vl-8b | `20261006T223737Z-qwen3-vl-8b` | ai-vlm    | http://host.docker.internal:18100 | b7972-e06088da0 | unrecorded | `8107ee63`    |

## What this split can and cannot say

- The holdout is 64 incident items over 6 scenarios. That is a leak detector, not a precise estimate: items share a scenario, so the scenario-cluster interval on this many items is several times wider than the same count of independent items would be. A holdout rate here checks that tuning on dev did not collapse generalization; it is not a competing measurement of the 90% bar.
- The draw is unstratified (ISS-016 B4), so the holdout's group mix is the hash's luck rather than a design choice, and it can land suspicious-heavy — the leg where recall is worst. A holdout S3 below dev's is therefore expected for any prompt that has not fixed that leg: read the dev-versus-holdout gap, never the holdout's level as a bar attempt.
- S2 is measured on dev by design: every benign scenario stays in dev (ISS-016 B1), so the holdout says nothing at all about false alarms.
- Tuning rule: holdout stills and failures are excluded from `report.html`, the gallery tuning reads, so a prompt tuned on this run's dev material has not seen them.

## Headline: every scored item

| Model       | Items | S2                        | Clustered S2                                     | S3                        | Clustered S3                                      | S3, low floor excluded    | Refusals               | Uncertain              |
| ----------- | ----- | ------------------------- | ------------------------------------------------ | ------------------------- | ------------------------------------------------- | ------------------------- | ---------------------- | ---------------------- |
| qwen3-vl-8b | 450   | 16.3% [11.9-21.9] (n=209) | clustered 16.3% [4.2-25.3] (n=209, 31 scenarios) | 43.6% [37.5-49.9] (n=241) | clustered 43.6% [25.3-60.0] (n=241, 31 scenarios) | 43.6% [37.5-49.9] (n=241) | 0.0% [0.0-0.9] (n=450) | 3.3% [2.0-5.4] (n=450) |

## Headline: dev split (tuning may see this)

| Model       | Items | S2                        | Clustered S2                                     | S3                        | Clustered S3                                      | S3, low floor excluded    | Refusals               | Uncertain              |
| ----------- | ----- | ------------------------- | ------------------------------------------------ | ------------------------- | ------------------------------------------------- | ------------------------- | ---------------------- | ---------------------- |
| qwen3-vl-8b | 386   | 16.3% [11.9-21.9] (n=209) | clustered 16.3% [4.5-25.2] (n=209, 25 scenarios) | 47.5% [40.2-54.8] (n=177) | clustered 47.5% [24.2-68.6] (n=177, 25 scenarios) | 47.5% [40.2-54.8] (n=177) | 0.0% [0.0-1.0] (n=386) | 3.4% [2.0-5.7] (n=386) |

### Scenario slice, dev only

**qwen3-vl-8b**

| Scenario                  | S2                       | S3                       |
| ------------------------- | ------------------------ | ------------------------ |
| catalytic_converter_theft | —                        | insufficient (n=9)       |
| child_alone_at_pool       | —                        | 5.3% [0.9-24.6] (n=19)   |
| delivery_driver           | 0.0% [0.0-27.8] (n=10)   | —                        |
| fence_climbing            | —                        | insufficient (n=9)       |
| fire_or_smoke             | —                        | 78.9% [56.7-91.5] (n=19) |
| firearm_visible           | —                        | 94.7% [75.4-99.1] (n=19) |
| flashlight_neighbor       | 31.0% [17.3-49.2] (n=29) | —                        |
| forced_entry              | —                        | 84.2% [62.4-94.5] (n=19) |
| hooded_jogger             | 37.9% [22.7-56.0] (n=29) | —                        |
| landscaper_machete        | 13.8% [5.5-30.6] (n=29)  | —                        |
| loitering                 | —                        | insufficient (n=9)       |
| masked_intruder_night     | —                        | 57.9% [36.3-76.9] (n=19) |
| neighbor_passing          | insufficient (n=9)       | —                        |
| package_theft             | —                        | 5.3% [0.9-24.6] (n=19)   |
| person_down               | —                        | insufficient (n=9)       |
| pet_activity              | insufficient (n=8)       | —                        |
| pool_service              | insufficient (n=9)       | —                        |
| pool_trespass             | —                        | insufficient (n=9)       |
| power_tools_at_night      | 31.0% [17.3-49.2] (n=29) | —                        |
| resident_arrival          | 0.0% [0.0-27.8] (n=10)   | —                        |
| trying_car_doors          | —                        | insufficient (n=9)       |
| vandalism                 | —                        | insufficient (n=9)       |
| wildlife                  | insufficient (n=9)       | —                        |
| winter_face_covering      | 0.0% [0.0-11.7] (n=29)   | —                        |
| yard_maintenance          | insufficient (n=9)       | —                        |

## Headline: holdout split (tuning never saw this)

| Model       | Items | S2                 | Clustered S2 | S3                       | Clustered S3                                   | S3, low floor excluded   | Refusals              | Uncertain              |
| ----------- | ----- | ------------------ | ------------ | ------------------------ | ---------------------------------------------- | ------------------------ | --------------------- | ---------------------- |
| qwen3-vl-8b | 64    | insufficient (n=0) | —            | 32.8% [22.6-45.0] (n=64) | clustered 32.8% [7.4-56.2] (n=64, 6 scenarios) | 32.8% [22.6-45.0] (n=64) | 0.0% [0.0-5.7] (n=64) | 3.1% [0.9-10.7] (n=64) |

Footnote: no benign items in the holdout: S2 is measured on dev, which holds all 209 benign items by design (ISS-016 B1).

## Headline: audited stills whose scene the owner confirmed

| Model       | Items | S2                 | Clustered S2 | S3                 | Clustered S3 | S3, low floor excluded | Refusals           | Uncertain          |
| ----------- | ----- | ------------------ | ------------ | ------------------ | ------------ | ---------------------- | ------------------ | ------------------ |
| qwen3-vl-8b | 0     | insufficient (n=0) | —            | insufficient (n=0) | —            | insufficient (n=0)     | insufficient (n=0) | insufficient (n=0) |

## Audit

0 of 60 sampled stills have a scene answer.

| Question   | Answered | Yes | No  | Unclear | Truth error        |
| ---------- | -------- | --- | --- | ------- | ------------------ |
| scene      | 0        | 0   | 0   | 0       | insufficient (n=0) |
| prop       | 0        | 0   | 0   | 0       | insufficient (n=0) |
| people     | 0        | 0   | 0   | 0       | insufficient (n=0) |
| conditions | 0        | 0   | 0   | 0       | insufficient (n=0) |

0 event(s) whose scene the owner answered no are generation errors: they are excluded from every metric, never counted as model errors.

## Risk band

| Model       | Label    | Scored | Inside                    | Below                     | Above                     | Mean below | Mean above |
| ----------- | -------- | ------ | ------------------------- | ------------------------- | ------------------------- | ---------- | ---------- |
| qwen3-vl-8b | incident | 241    | 42.7% [36.6-49.0] (n=241) | 57.3% [50.9-63.3] (n=241) | 0.0% [0.0-1.6] (n=241)    | 34.4       | —          |
| qwen3-vl-8b | benign   | 209    | 80.9% [75.0-85.6] (n=209) | 1.9% [0.8-4.8] (n=209)    | 17.2% [12.7-22.9] (n=209) | 5.0        | 20.6       |

## Verdicts and refusals

| Model       | Verdicts                                | Unparseable | Unavailable | No cause |
| ----------- | --------------------------------------- | ----------- | ----------- | -------- |
| qwen3-vl-8b | confirmed 432, rejected 3, uncertain 15 | 0           | 0           | 0        |

## Slices

### qwen3-vl-8b

**scenario**

| scenario                  | S2                       | S3                       |
| ------------------------- | ------------------------ | ------------------------ |
| blunt_weapon              | —                        | insufficient (n=9)       |
| car_break_in              | —                        | insufficient (n=9)       |
| casing_with_phone         | —                        | insufficient (n=9)       |
| catalytic_converter_theft | —                        | insufficient (n=9)       |
| child_alone_at_pool       | —                        | 5.3% [0.9-24.6] (n=19)   |
| delivery_driver           | 0.0% [0.0-27.8] (n=10)   | —                        |
| fence_climbing            | —                        | insufficient (n=9)       |
| fire_or_smoke             | —                        | 78.9% [56.7-91.5] (n=19) |
| firearm_visible           | —                        | 94.7% [75.4-99.1] (n=19) |
| flashlight_neighbor       | 31.0% [17.3-49.2] (n=29) | —                        |
| forced_entry              | —                        | 84.2% [62.4-94.5] (n=19) |
| hooded_jogger             | 37.9% [22.7-56.0] (n=29) | —                        |
| knife_visible             | —                        | 52.6% [31.7-72.7] (n=19) |
| landscaper_machete        | 13.8% [5.5-30.6] (n=29)  | —                        |
| loitering                 | —                        | insufficient (n=9)       |
| masked_intruder_night     | —                        | 57.9% [36.3-76.9] (n=19) |
| neighbor_passing          | insufficient (n=9)       | —                        |
| package_theft             | —                        | 5.3% [0.9-24.6] (n=19)   |
| peering_into_windows      | —                        | insufficient (n=9)       |
| person_down               | —                        | insufficient (n=9)       |
| pet_activity              | insufficient (n=8)       | —                        |
| pool_service              | insufficient (n=9)       | —                        |
| pool_trespass             | —                        | insufficient (n=9)       |
| power_tools_at_night      | 31.0% [17.3-49.2] (n=29) | —                        |
| resident_arrival          | 0.0% [0.0-27.8] (n=10)   | —                        |
| tailgating                | —                        | insufficient (n=9)       |
| trying_car_doors          | —                        | insufficient (n=9)       |
| vandalism                 | —                        | insufficient (n=9)       |
| wildlife                  | insufficient (n=9)       | —                        |
| winter_face_covering      | 0.0% [0.0-11.7] (n=29)   | —                        |
| yard_maintenance          | insufficient (n=9)       | —                        |

**group**

| group         | S2                        | S3                        |
| ------------- | ------------------------- | ------------------------- |
| benign        | 1.6% [0.3-8.3] (n=64)     | —                         |
| hard_negative | 22.8% [16.7-30.2] (n=145) | —                         |
| suspicious    | —                         | 4.4% [1.2-14.8] (n=45)    |
| threat        | —                         | 52.6% [45.6-59.4] (n=196) |

**lighting**

| lighting        | S2                       | S3                       |
| --------------- | ------------------------ | ------------------------ |
| day             | 5.1% [2.0-12.5] (n=78)   | 47.1% [37.0-57.5] (n=87) |
| dusk            | 10.7% [3.7-27.2] (n=28)  | 37.1% [23.2-53.7] (n=35) |
| golden_hour     | 0.0% [0.0-17.6] (n=18)   | 22.7% [10.1-43.4] (n=22) |
| ir_night        | 35.4% [24.9-47.5] (n=65) | 51.5% [39.8-62.9] (n=68) |
| porch_lit_night | 20.0% [8.1-41.6] (n=20)  | 37.9% [22.7-56.0] (n=29) |

**weather**

| weather | S2                       | S3                        |
| ------- | ------------------------ | ------------------------- |
| clear   | 15.4% [9.7-23.5] (n=104) | 44.2% [36.7-52.1] (n=156) |
| fog     | 25.0% [10.2-49.5] (n=16) | 30.8% [16.5-50.0] (n=26)  |
| rain    | 26.5% [14.6-43.1] (n=34) | 47.4% [32.5-62.7] (n=38)  |
| snow    | 9.1% [4.0-19.6] (n=55)   | 47.6% [28.3-67.6] (n=21)  |

**property**

| property           | S2                       | S3                       |
| ------------------ | ------------------------ | ------------------------ |
| apartment_entrance | 5.9% [1.1-27.0] (n=17)   | 21.4% [7.6-47.6] (n=14)  |
| lake_house         | 19.5% [10.2-34.0] (n=41) | 32.7% [21.2-46.6] (n=49) |
| rural_farmhouse    | 9.4% [4.1-20.2] (n=53)   | 47.9% [34.5-61.7] (n=48) |
| small_office       | 41.7% [19.3-68.0] (n=12) | 41.7% [24.5-61.2] (n=24) |
| suburban_house     | 19.7% [11.9-30.8] (n=66) | 45.1% [34.8-55.9] (n=82) |
| urban_townhouse    | 10.0% [2.8-30.1] (n=20)  | 61.1% [38.6-79.7] (n=18) |
| warehouse          | —                        | insufficient (n=6)       |

**camera**

| camera           | S2                        | S3                        |
| ---------------- | ------------------------- | ------------------------- |
| doorbell_fisheye | 0.0% [0.0-13.8] (n=24)    | 34.8% [22.7-49.2] (n=46)  |
| eave_wide        | 15.4% [10.2-22.6] (n=130) | 41.0% [33.1-49.5] (n=134) |
| garage_mounted   | 25.0% [13.2-42.1] (n=32)  | 33.3% [16.3-56.2] (n=18)  |
| indoor_corner    | insufficient (n=4)        | 72.7% [51.8-86.9] (n=22)  |
| pole_lot         | 26.3% [11.8-48.8] (n=19)  | 57.1% [36.5-75.5] (n=21)  |

**zone**

| zone            | S2                       | S3                         |
| --------------- | ------------------------ | -------------------------- |
| backyard        | 22.6% [11.4-39.8] (n=31) | 54.5% [34.7-73.1] (n=22)   |
| driveway        | 19.7% [11.6-31.3] (n=61) | 33.3% [20.2-49.7] (n=36)   |
| front_porch     | 0.0% [0.0-11.0] (n=31)   | 45.8% [33.7-58.3] (n=59)   |
| garage_exterior | insufficient (n=6)       | insufficient (n=1)         |
| garage_interior | insufficient (n=3)       | —                          |
| hallway         | —                        | insufficient (n=3)         |
| kitchen         | insufficient (n=1)       | 100.0% [77.2-100.0] (n=13) |
| living_room     | —                        | insufficient (n=4)         |
| loading_dock    | —                        | insufficient (n=1)         |
| lobby_door      | insufficient (n=7)       | 31.2% [14.2-55.6] (n=16)   |
| mailroom        | —                        | insufficient (n=2)         |
| parking_lot     | —                        | 46.2% [23.2-70.9] (n=13)   |
| patio           | insufficient (n=2)       | 50.0% [25.4-74.6] (n=12)   |
| pool_deck       | insufficient (n=9)       | 3.6% [0.6-17.7] (n=28)     |
| shed            | —                        | insufficient (n=1)         |
| side_gate       | 5.9% [1.1-27.0] (n=17)   | 63.6% [35.4-84.8] (n=11)   |
| street_edge     | 24.4% [13.8-39.3] (n=41) | 57.9% [36.3-76.9] (n=19)   |

**artifacts**

| artifacts | S2                        | S3                        |
| --------- | ------------------------- | ------------------------- |
| drawn     | 20.5% [10.8-35.5] (n=39)  | 43.6% [29.3-59.0] (n=39)  |
| none      | 15.3% [10.7-21.5] (n=170) | 43.6% [36.9-50.5] (n=202) |

## Comparison

### Comparison: dev split (where the OD-26 rule decides)

One model scored: nothing to compare.

### Comparison: holdout split (the generalization check; the rule is not applied)

One model scored: nothing to compare.
