export const meta = {
  name: 'wp44-survivor-triage',
  description: 'Triage surviving mutants in the 16 most-affected modules and draft WP4.4 test skeletons (read-only while run5 owns the box)',
  phases: [{ title: 'Triage', detail: 'one agent per module: cluster survivors, classify, draft kill-tests' }],
}

const MODULES = args.modules

const SCHEMA = {
  type: 'object',
  properties: {
    module: { type: 'string' },
    survivors_total: { type: 'number' },
    clusters: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          pattern: { type: 'string', description: 'e.g. "comparison operator flipped on timestamp freshness check"' },
          count: { type: 'number' },
          classification: { type: 'string', enum: ['TEST-GAP', 'EQUIVALENT', 'LOW-VALUE'] },
          example_keys: { type: 'array', items: { type: 'string' } },
          note: { type: 'string' },
        },
        required: ['pattern', 'count', 'classification'],
      },
    },
    drafted_tests: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          test_name: { type: 'string' },
          kills_cluster: { type: 'string' },
          target_test_file: { type: 'string' },
          gist: { type: 'string' },
        },
        required: ['test_name', 'kills_cluster', 'target_test_file'],
      },
    },
    dossier_path: { type: 'string' },
    test_files_involved: { type: 'array', items: { type: 'string' } },
  },
  required: ['module', 'survivors_total', 'clusters', 'dossier_path'],
}

const results = await parallel(MODULES.map((mod) => () =>
  agent(`You are triaging SURVIVING mutants for one module of a mutation-testing baseline (WP4.3 finding feed into WP4.4). Repo root: /agents/agent-nemo2/workspace. Module: ${mod}

CRITICAL CONSTRAINTS (a live mutation run owns this machine):
- Do NOT run pytest, mutmut run, or ANY test execution. Do NOT modify any file under the repo (backend/, mutants/, tests, pyproject, etc.). You READ only.
- Your ONLY writes: the dossier file /tmp/wp25/wp44-triage/${mod.split('/').pop().replace('.py', '')}.md (create dirs as needed).
- Do NOT invoke "mutmut run" or any mutating command. "uv run mutmut show <key>" is allowed READ-ONLY for diffs; if it errors or hangs >60s (the cache is being concurrently written), fall back to manual diffing as described.

HOW THE DATA LIES:
- Verdicts: mutants/${mod}.meta is JSON {"exit_code_by_key": {mutant_key: exit_code_or_null}}. exit_code 0 == SURVIVED (that's your set). null == not yet checked (ignore). If a read fails with JSONDecodeError, retry once (concurrent write), then skip that step gracefully.
- Mutant copies: the mutated source is at mutants/${mod}. To see a specific mutant's change without mutmut show: the copy contains clobbered variants (names like x<CLOBBER>Class<CLOBBER>method__mutmut_N / __mutmut_orig); diff the relevant function region against the original ${mod}. Prefer "uv run mutmut show <key>" (prints a clean diff) and only fall back for failures.
- Which tests cover a function: /agents/agent-nemo2/workspace/mutants/mutmut-stats.json has tests_by_mangled_function_name (LARGE file - query it with a python one-liner, never Read it whole).

TASK:
1. Extract the surviving keys for ${mod} from its meta.
2. For each survivor, get its diff (one-line changes: operator flips, constant tweaks, boolean changes, return swaps). With 100-200+ survivors, DO NOT write per-mutant prose — CLUSTER by mutation pattern (same kind of change in the same function/concern = one cluster; keep example_keys <=3 per cluster).
3. Classify every cluster: EQUIVALENT (semantically identical to original — pure log/message text, dead defensive tweaks), LOW-VALUE (real change but behavior nobody should assert: debug hooks, cosmetic), or TEST-GAP (real behavior change, tests execute the line but never assert it). Read the covering test file(s) named in tests_by_mangled_function_name to judge TEST-GAP vs "test exists but asserts too weakly" (that's still TEST-GAP — note which file and what it misses).
4. For your 3-6 highest-value TEST-GAP clusters, DRAFT a real pytest test (full code, imports, follows the style of the module's existing test file) that would kill the cluster's mutants, marked "// UNVERIFIED - not yet run red/green". State the TDD procedure in one line: assert fails on mutant diff, passes on original.
5. Write the dossier: per-cluster table + drafted tests inline + the file:line of the covering test file(s).

Return the structured summary. Set module to "${mod}". cluster counts must sum to survivors_total (±0), classification on every cluster.`,
    { label: `triage:${mod.split('/').pop()}`, phase: 'Triage', schema: SCHEMA })
))

const done = results.filter(Boolean)
log(`${done.length}/${MODULES.length} modules triaged`)
return done
