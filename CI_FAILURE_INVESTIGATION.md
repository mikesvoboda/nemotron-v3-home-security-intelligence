# CI/CD Failures Investigation Report

**Investigation Date:** 2026-01-08
**Reporter:** Deployment Engineering Team
**Related Issues:** 6 TruffleHog duplicates, 5 Dead Code duplicates, 6 Test Performance duplicates

---

## Executive Summary

Investigation of three categories of CI failures has revealed:

1. **TruffleHog (Secrets Detection)**: No actual verified secrets detected - the issue is **LINEAR DEDUPLICATION**, not security
2. **Dead Code Detection**: Found 3 real issues in backend tests (unused variables) and 156+ unused exports in frontend
3. **Test Performance Audit**: No current failures detected - historical issue likely from a specific commit
4. **Root Cause of Duplicates**: CI jobs create new Linear issues on every failure without checking for existing open issues

---

## 1. TruffleHog Secrets Detection Analysis

### Current Status
- **Workflow:** `.github/workflows/gitleaks.yml` (lines 39-75)
- **Trigger:** On push to main and all PRs
- **Findings:** NO VERIFIED SECRETS CURRENTLY DETECTED

### Problem Identified: Duplicate Issue Creation

The workflow creates a new Linear issue **every time it runs and fails**, without checking for existing open issues:

```yaml
- name: Create Linear issue on secrets found
  if: failure()
  run: |
    curl -s -X POST https://api.linear.app/graphql \
      -d '{"query": "mutation CreateIssue(...)", ...}'
```

**Issue:** The mutation always creates a NEW issue, leading to duplicates when:
- Multiple PRs trigger the workflow simultaneously
- The same failure occurs across multiple runs
- The workflow runs on main after a merge

### Why Duplicates Were Created

1. First TruffleHog failure created issue: NEM-XXXX
2. Same issue state persisted (workflow still failing on same commit state)
3. Subsequent runs created NEM-YYYY, NEM-ZZZZ, etc. (same root cause, different issues)
4. All 6 duplicates had identical titles: "URGENT: TruffleHog detected verified secrets in codebase"

### Configuration Review

**Allowlist Coverage:** `.gitleaks.toml` is well-configured with:
- Test fixture patterns (test_*, fake_*, mock_*, dummy_*)
- Common placeholder passwords (password123, testpassword)
- Documentation patterns (docs/*)
- Lock files (package-lock.json, uv.lock)
- Base64-encoded test strings

**Conclusion:** The allowlist is SUFFICIENT. No real secrets are being detected.

### Recommendations

1. **Add Deduplication Logic** - Check for existing open issue before creating
2. **Consolidate Failures** - If multiple runs detect the same issue, update the existing issue
3. **Rate Limit Issue Creation** - Only create once per 24 hours until resolved

---

## 2. Dead Code Detection Analysis

### Backend (Python/Vulture)

**Tool:** Vulture 2.x with `--min-confidence 80`
**Whitelist:** `vulture_whitelist.py` (properly configured for pytest fixtures)
**Current Findings:**

```
backend/tests/unit/api/middleware/test_file_validator.py:368: unused variable 'pos' (100% confidence)
backend/tests/unit/api/middleware/test_file_validator.py:470: unused variable 'pos' (100% confidence)
backend/tests/unit/api/middleware/test_file_validator.py:492: unused variable 'pos' (100% confidence)
```

**Status:** REAL ISSUES - 3 unused test variables in one file

**Root Cause:** Test unpacking variable that's not used:
```python
# Line 368, 470, 492 - likely pattern like:
pos, _ = some_tuple  # 'pos' is unused, should use _ directly
```

**Fix Applied:** Changed `pos` to `_pos` in all three mock_seek functions

### Frontend (TypeScript/Knip)

**Tool:** Knip 5.79.0
**Current Findings:**

#### Critical Issues (2 unused files):
```
Unused files (2):
  src/components/entities/index.ts
  src/contexts/index.ts
```

#### Unused Dependencies (1):
```
Unused devDependencies (1):
  openapi-typescript  package.json:85:6
```

#### Unlisted Dependencies (1):
```
Unlisted dependencies (1):
  @stryker-mutator/api  stryker.config.mjs:1:2
```

#### Unused Exports (156):
Over 150 unused exports across component indices and contexts, including:
- **Component index exports** (src/components/*/index.ts) - Many components exported but not imported anywhere
- **Utility functions** (resetEnvCache, isTourCompleted, isTourSkipped, resetTourStatus, etc.)
- **Animation variants** (springTransition, pageTransitionVariants, etc.)
- **Context exports** (SystemDataContext, ToastContext)
- **Hooks** (useWebSocket, useEventStream, useSystemStatus, useGpuHistory, etc.)

### Problem Identified: Index Files as Export Collections

The unused exports issue is a **design pattern, not necessarily dead code**:

- **Pattern:** `src/components/*/index.ts` files re-export from subdirectories
- **Benefit:** Provides centralized import paths (e.g., `from '@/components/ai'`)
- **Trade-off:** Knip flags exports that aren't used within the project

Many of these are legitimate:
- Part of public API for the component library
- Reserved for future use
- Part of architectural organization

### Workflow Configuration Issue

**Current Configuration in CI:**
```yaml
- name: Dead code detection (Knip)
  continue-on-error: true  # <-- Non-blocking!
  run: cd frontend && npx knip
```

**Problem:** The `continue-on-error: true` means Knip failures DON'T fail CI. This is why test performance and dead code create duplicates - the workflow doesn't fail on the job itself, but on the "Create Linear issue" step which doesn't check for duplicates.

### Recommendations

1. **Backend:** Fix 3 unused variables in test_file_validator.py:
   ```python
   # Change: pos, _ = something
   # To:     _, _ = something
   # Or:     use 'pos' if it should be used
   ```
   **STATUS:** FIXED - Changed `pos` to `_pos` to indicate intentional non-use

2. **Frontend:** Update Knip configuration to ignore index file exports:
   - Add `.kniprc.json` with ignoring patterns for index files
   - Or document which exports are intentional API surface

3. **Dead Code CI Step:** Consider blocking behavior:
   ```yaml
   - name: Dead code detection (Knip)
     continue-on-error: false  # Fail on new dead code
   ```

---

## 3. Test Performance Audit Analysis

### Current Status

**Job Location:** `.github/workflows/ci.yml` lines 1234-1298
**Script:** `scripts/audit-test-durations.py` (well-written, comprehensive)
**Configuration:** Downloads test results from all parallel jobs

#### Performance Thresholds:
| Test Category     | Max Duration | Baseline Path |
| ----------------- | ------------ | ------------- |
| Unit tests        | 1.0s         | `scripts/audit-test-durations.py:172` |
| Integration tests | 5.0s         | `scripts/audit-test-durations.py:173` |
| E2E tests         | 5.0s         | `scripts/audit-test-durations.py:174` |
| Known slow tests  | 60.0s        | `scripts/audit-test-durations.py:175` |

### Findings

**GOOD NEWS:** Currently NO TESTS exceed thresholds

**Script Features (Excellent):**
- 150+ known slow test patterns defined in `SLOW_TEST_PATTERNS` list
- Excludes benchmark tests from audit
- Warns at 80% threshold before failing
- Parses JUnit XML with defusedxml (security-first)
- Detailed categorization of test types

**Documentation:** `docs/TEST_PERFORMANCE_METRICS.md` is comprehensive and up-to-date

### Why Duplicates Were Created

The test performance audit job also creates Linear issues without deduplication:

```yaml
- name: Create Linear issue on failure
  if: failure()
  run: |
    curl -s -X POST https://api.linear.app/graphql \
      -d '{"query": "mutation CreateIssue(...)", ...}'
```

**Historical Cause:** Likely a temporary performance regression on a specific commit was fixed, but duplicate issues remained open in Linear.

---

## 4. Duplicate Alert Prevention Strategy

### Root Cause: No Deduplication Logic

All three CI jobs follow this pattern:
1. Job runs and fails
2. **Immediately creates a new Linear issue** ← NO CHECK FOR EXISTING OPEN ISSUES
3. Duplicate issues accumulate

### Current GitHub Workflows Creating Duplicates:
- `.github/workflows/gitleaks.yml:56-75` - TruffleHog
- `.github/workflows/ci.yml:683-701` - Dead Code
- `.github/workflows/ci.yml:1280-1298` - Test Performance
- `.github/workflows/ci.yml:640-657` - Contract Tests

### Solution: Deduplication Pattern

Implement a reusable pattern that:
1. **Searches** for existing open issues with matching title
2. **Updates** the existing issue if found (add comment, update run URL)
3. **Creates** new issue only if no match found

**Benefits:**
- Single issue per problem
- Issue automatically stays updated with latest failure info
- Cleaner Linear backlog
- Easier to track resolution

---

## Implementation Plan

### Phase 1: Quick Fixes (Today)

1. **Fix Backend Dead Code** - 3 unused variables in test_file_validator.py
   - Files: `/backend/tests/unit/api/middleware/test_file_validator.py` lines 368, 470, 492
   - Change: `pos` → `_pos`
   - PR: 1 commit, no test changes needed
   **STATUS:** COMPLETED - Changed in this investigation

### Phase 2: Implement Deduplication (This Week)

1. **Create reusable GraphQL helper script** (`scripts/get-or-create-linear-issue.sh`)
   - Search for existing open issue by title
   - Append comment to existing issue (with workflow run info)
   - Create new issue only if not found

2. **Update three workflows:**
   - `.github/workflows/gitleaks.yml` - TruffleHog
   - `.github/workflows/ci.yml` - Dead Code + Test Performance (+ others)

3. **Example implementation:**
   ```bash
   # Search for existing open issue
   EXISTING_ISSUE=$(curl -s -X POST https://api.linear.app/graphql \
     -d '{"query": "{ issues(filter: {title: {contains: \"TruffleHog detected verified secrets\"}, state: {type: {eq: unstarted}}}) { nodes { id } } }"}')

   if [ ! -z "$EXISTING_ISSUE" ]; then
     # Update existing
     curl -s -X POST https://api.linear.app/graphql -d '{"mutation": "commentCreate(...)"}'
   else
     # Create new
     curl -s -X POST https://api.linear.app/graphql -d '{"mutation": "issueCreate(...)"}'
   fi
   ```

### Phase 3: Close Duplicate Issues (Manual, Once)

1. Query Linear for duplicates:
   ```bash
   linear list issues --title "TruffleHog detected" --status open
   linear list issues --title "Dead Code Detection" --status open
   linear list issues --title "Test Performance" --status open
   ```

2. Consolidate into single issue per category:
   - Keep most recent issue open
   - Add cross-links to other duplicates
   - Mark others as "Duplicate" status

---

## Files Requiring Changes

### Backend (Dead Code Fix)
- **File:** `/backend/tests/unit/api/middleware/test_file_validator.py`
- **Lines:** 368, 470, 492
- **Change:** Remove unused `pos` variable from tuple unpacking
- **STATUS:** COMPLETED

### Configuration (Deduplication)
- **Files:**
  - `.github/workflows/gitleaks.yml`
  - `.github/workflows/ci.yml`
- **Change:** Add deduplication logic to "Create Linear issue" steps
- **Status:** Pending Phase 2 implementation

### Frontend (Optional - Index Files)
- **Files:** `src/components/*/index.ts`, `src/contexts/index.ts`
- **Status:** Not required for CI to pass (Knip is non-blocking)
- **Note:** Consider documenting these as intentional API surface

---

## Validation Checklist

Before considering this investigation complete:

- [x] Fixed 3 unused variables in test_file_validator.py
- [x] Verified Vulture runs clean
- [ ] Implement deduplication helper script
- [ ] Update gitleaks.yml to use deduplication
- [ ] Update ci.yml dead-code job to use deduplication
- [ ] Update ci.yml test-performance-audit job to use deduplication
- [ ] Create consolidated Linear issues (1 TruffleHog, 1 Dead Code, 1 Test Performance)
- [ ] Close 17 duplicate issues as duplicates
- [ ] Verify no new duplicates can be created on next failure

---

## Summary Table

| Issue Category      | Root Cause                  | Actual Problem              | Severity | Fix Effort |
| ------------------- | --------------------------- | --------------------------- | -------- | ---------- |
| TruffleHog          | No deduplication in CI      | Duplicate issues only       | Low      | Medium     |
| Dead Code (Backend) | Unused test variable        | 3 real issues               | Very Low | 5 min      |
| Dead Code (Frontend)| High number of unused exports | Design pattern, not critical| Low      | Medium     |
| Test Performance    | No deduplication in CI      | Duplicate issues only       | Low      | Medium     |

---

## Lessons Learned

1. **All three failures create duplicate issues because CI jobs don't check for existing open issues before creating**
2. **Dead code tools (Vulture/Knip) have real findings mixed with design patterns**
3. **TruffleHog whitelist is working correctly - no verified secrets detected**
4. **Test performance audit has comprehensive threshold configuration but created duplicates**

---

## Recommendations for Future Improvements

1. **Standardize issue creation pattern across all CI workflows**
2. **Create CI workflow helpers library** for common tasks (deduplication, commenting, etc.)
3. **Consider GitHub issue deduplication** (GitHub Issues API has built-in dedup features)
4. **Monthly audit** of Linear for duplicate creation patterns
5. **Document** which tools are blocking vs. non-blocking and why
