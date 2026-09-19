# services/prompt_parser.py surviving-mutant record (STRICT census 2026-09-19, wave-67)

211 mutants; 186 killed pre-WP4.4 (score 88.2%). Wave-67 batch (9 tests across
TestFindInsertionPoint / TestDetectVariableStyle / TestValidatePromptSyntax in
test_prompt_parser.py): **15 newly killed**. STRICT census: all 25 open keys
re-probed with synced tests, kill = rc in (1,3), -n 0, 0 no-verdicts.

Coverage map: fallback-warning caplog contract — exact getMessage +
record.target_section + record.prompt_length extras (kills the 11 surviving
C1/C2 clobbers of the fallback path), label_style "none" for lowercase
colon/equals labels ([A-Z]-anchored regexes, C5), duplicate-variable join
separator exact message "Duplicate variables: var_a, var_b" (C6), angle
open/close count-asymmetry warning "2 open"/"1 close" (C7).

Module total: (186+15)/211 = **201 = 95.3%** (was 88.2% pre-WP4.4).
10 survivors remain — dossier-predicted exactly: C3 curly default & comparison
constants absorbed by the identical else-fallback (6) + C4 label_style default
constants absorbed by the colon else-branch (4), both EQUIVALENT (the mutated
constant is never observable — the fallback branch produces the same output).
They ARE the surviving-mutant record; the 95.3% is the module's killable ceiling.

```
backend.services.prompt_parser.x_generate_insertion_text__mutmut_11
backend.services.prompt_parser.x_generate_insertion_text__mutmut_13
backend.services.prompt_parser.x_generate_insertion_text__mutmut_16
backend.services.prompt_parser.x_generate_insertion_text__mutmut_17
backend.services.prompt_parser.x_generate_insertion_text__mutmut_20
backend.services.prompt_parser.x_generate_insertion_text__mutmut_22
backend.services.prompt_parser.x_generate_insertion_text__mutmut_25
backend.services.prompt_parser.x_generate_insertion_text__mutmut_26
backend.services.prompt_parser.x_generate_insertion_text__mutmut_28
backend.services.prompt_parser.x_generate_insertion_text__mutmut_29
```
