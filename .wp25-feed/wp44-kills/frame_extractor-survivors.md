# services/frame_extractor.py surviving-mutant record (STRICT census 2026-09-19, wave-67)

132 mutants; 105 killed pre-WP4.4 (score 79.5%). Wave-67 batch (12 tests in 3
classes in test_frame_extractor.py): **21 newly killed**. STRICT census: all 27
open keys re-probed with synced tests, kill = rc in (1,3), -n 0, 0 no-verdicts.

Coverage map: save_frame parent-chain creation + exist_ok re-save + exact
imwrite path/filename (C1-C3), detect_motion empty-guard vs size-1 inputs
(kill vectors must use SIZE-1: empty-mask mutants otherwise survive via the
nan > t == False coincidence) + strict-> threshold boundary at sensitivity 0.0
(C4-C6), (1-s)**2 threshold curve + endpoint sensitivity validation (C7, C9),
_is_mock/_MOG2Wrapper/_create_subtractor direct-call contracts (C10, C11).

Module total: (105+21)/132 = **126 = 95.5%** (was 79.5% pre-WP4.4).
6 survivors remain — dossier-predicted exactly: C8 extract_frame message text
(4, LOW-VALUE), C11 dict.get default == stored value (2, EQUIVALENT:
__init___7, _get_camera_subtractor__7).
They ARE the surviving-mutant record.

```
backend.services.frame_extractor.xǁFrameExtractorǁ__init____mutmut_7
backend.services.frame_extractor.xǁFrameExtractorǁ_get_camera_subtractor__mutmut_7
backend.services.frame_extractor.xǁFrameExtractorǁextract_frame__mutmut_2
backend.services.frame_extractor.xǁFrameExtractorǁextract_frame__mutmut_3
backend.services.frame_extractor.xǁFrameExtractorǁextract_frame__mutmut_4
backend.services.frame_extractor.xǁFrameExtractorǁextract_frame__mutmut_5
```
