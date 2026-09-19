# services/scene_change_detector.py surviving-mutant record (STRICT census 2026-09-19, wave-66)

203 mutants; 169 killed pre-WP4.4 (score 83.3%). Wave-66 batch (7 classes,
`TestWp44SceneChangeGaps*`, test_scene_change_detector.py): **16 newly killed**.
STRICT census: all 34 open keys re-probed with synced tests, kill = rc in (1,3),
-n 0, 0 no-verdicts.

Coverage map: threshold boundary `<=` (change_detected False at ssim==threshold),
bool contract `is False` + to_dict false (C13 — killed the change_detected
False→None pair 19/81), win_size spy on 4×4 frames (C10: skimage gets 3,
kills even/oversized-window mutants), `data_range=255`+`win_size=7` call spy
(C11), resize_width=1 (C5), LANCZOS spy on PIL resize (C7), ndim-only duck
object → ValueError (C6).

Module total: (169+16)/203 = **185 = 91.1%** (was 83.3% pre-WP4.4).
18 survivors remain — dossier C1 message-padding (4, EQUIVALENT: match= substrings
survive), C2 type-name interpolation (2, EQUIVALENT), C3 `mode=` neutralized —
Pillow typemap inference byte-identical (6, EQUIVALENT), C4 `shape[:3]` of 2-D
(2, EQUIVALENT), C8 `w <=`→`<` same-size fast path (1, EQUIVALENT), C9 win 7→8
re-pulled by odd-adjust (1, EQUIVALENT), C12 clamp 1.0→2.0 unreachable (>1.0
impossible with uint8+data_range=255) (1, LOW-VALUE), plus **detect_changes__84**
(EQUIVALENT, post-census addendum): drops the `is_first_frame=False` kwarg and
the dataclass default IS False (scene_change_detector.py:32) — byte-identical
result, structurally unkillable. They ARE the surviving-mutant record.

```
backend.services.scene_change_detector.xǁSceneChangeDetectorǁ__init____mutmut_15
backend.services.scene_change_detector.xǁSceneChangeDetectorǁ__init____mutmut_7
backend.services.scene_change_detector.xǁSceneChangeDetectorǁ_resize_frame__mutmut_18
backend.services.scene_change_detector.xǁSceneChangeDetectorǁ_resize_frame__mutmut_2
backend.services.scene_change_detector.xǁSceneChangeDetectorǁ_resize_frame__mutmut_7
backend.services.scene_change_detector.xǁSceneChangeDetectorǁ_resize_frame__mutmut_9
backend.services.scene_change_detector.xǁSceneChangeDetectorǁ_to_grayscale__mutmut_22
backend.services.scene_change_detector.xǁSceneChangeDetectorǁ_to_grayscale__mutmut_3
backend.services.scene_change_detector.xǁSceneChangeDetectorǁ_to_grayscale__mutmut_32
backend.services.scene_change_detector.xǁSceneChangeDetectorǁ_to_grayscale__mutmut_34
backend.services.scene_change_detector.xǁSceneChangeDetectorǁ_to_grayscale__mutmut_47
backend.services.scene_change_detector.xǁSceneChangeDetectorǁ_to_grayscale__mutmut_49
backend.services.scene_change_detector.xǁSceneChangeDetectorǁdetect_changes__mutmut_14
backend.services.scene_change_detector.xǁSceneChangeDetectorǁdetect_changes__mutmut_3
backend.services.scene_change_detector.xǁSceneChangeDetectorǁdetect_changes__mutmut_30
backend.services.scene_change_detector.xǁSceneChangeDetectorǁdetect_changes__mutmut_46
backend.services.scene_change_detector.xǁSceneChangeDetectorǁdetect_changes__mutmut_77
backend.services.scene_change_detector.xǁSceneChangeDetectorǁdetect_changes__mutmut_84
```
