# services/session_service.py surviving-mutant record (STRICT census 2026-09-19, wave-66)

60 mutants; 25 killed pre-WP4.4 (score 41.7%). Wave-66 batch (6 tests in
`TestWp44SessionServiceGaps`, test_session_service.py): **22 newly killed**.
STRICT census: all 35 open keys re-probed with synced tests, kill = rc in (1,3),
-n 0, 0 no-verdicts.

Coverage map: stored-JSON payload contract (email/role/user_id/session_id keys —
kills C4's 8 mutants), `expire=86400/7200` kwargs (C5), `set(key, payload)`
positional pair (C6), `ttl("session:<id>")` identity (C10),
`expire("session:<id>", 7200)` full-call contract (C11).

Module total: (25+22)/60 = **47 = 78.3%** (was 41.7% pre-WP4.4).
13 survivors remain — dossier-predicted exactly: C1/C7 ValueError message text
(9, EQUIVALENT — exception type/flow identical), C2 token_urlsafe(None)≡32
(EQUIVALENT), C3 32→33-byte token (LOW-VALUE), C8 SessionExpiredError(None)
message arg (LOW-VALUE), C9 falsy-guard widening (EQUIVALENT).
They ARE the surviving-mutant record.

```
backend.services.session_service.xǁSessionServiceǁcreate_session__mutmut_2
backend.services.session_service.xǁSessionServiceǁcreate_session__mutmut_3
backend.services.session_service.xǁSessionServiceǁcreate_session__mutmut_4
backend.services.session_service.xǁSessionServiceǁcreate_session__mutmut_5
backend.services.session_service.xǁSessionServiceǁcreate_session__mutmut_6
backend.services.session_service.xǁSessionServiceǁcreate_session__mutmut_8
backend.services.session_service.xǁSessionServiceǁcreate_session__mutmut_9
backend.services.session_service.xǁSessionServiceǁget_session__mutmut_11
backend.services.session_service.xǁSessionServiceǁget_session__mutmut_13
backend.services.session_service.xǁSessionServiceǁget_session__mutmut_2
backend.services.session_service.xǁSessionServiceǁget_session__mutmut_3
backend.services.session_service.xǁSessionServiceǁget_session__mutmut_4
backend.services.session_service.xǁSessionServiceǁget_session__mutmut_5
```
