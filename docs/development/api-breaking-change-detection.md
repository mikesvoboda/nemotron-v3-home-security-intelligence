# API Breaking Change Detection

This document describes the API breaking change detection system integrated into the CI pipeline.

## Overview

The API breaking change detection system automatically detects and reports breaking changes in the OpenAPI specification between a PR branch and the main branch. This prevents unintentional breaking changes from being merged without review and approval.

## How It Works

### CI Workflow

The `api-compatibility.yml` workflow runs on all PRs that modify:

- `backend/api/**`
- `backend/models/**`
- `backend/main.py`

The workflow:

1. Generates OpenAPI spec from the main branch
2. Generates OpenAPI spec from the PR branch
3. Compares the specs using `oasdiff` to detect breaking changes
4. Posts a comment on the PR with details of any breaking changes
5. **Blocks the PR** if breaking changes are detected (unless approved)
6. Allows the PR to proceed if the `breaking-change-approved` label is added

### Breaking Changes Detected

The system detects the following breaking changes:

#### Endpoint Changes

- ❌ **Removed endpoints**: Entire API paths removed
- ❌ **Removed HTTP methods**: Specific methods removed from an endpoint

#### Parameter Changes

- ❌ **Removed required parameters**: Required parameters removed
- ⚠️ **Removed optional parameters**: Optional parameters removed (potentially breaking)
- ❌ **Parameter made required**: Optional parameter changed to required
- ❌ **Parameter type changed**: Parameter data type changed

#### Request Body Changes

- ❌ **Request body removed**: Required request body removed
- ❌ **Request body made required**: Optional request body changed to required
- ❌ **Content type removed**: Supported content type removed

#### Response Changes

- ❌ **Success response removed**: 2xx response removed
- ❌ **Response content type removed**: Supported response content type removed

## Usage

### For Developers

#### When Your PR Triggers Breaking Change Detection

If your PR introduces breaking changes, the workflow will:

1. **Post a comment** on the PR with details of all breaking changes
2. **Fail the CI check** (blocking merge)
3. **Require approval** via the `breaking-change-approved` label

**Example PR comment:**

```markdown
## 🚨 Breaking API Changes Detected

❌ **Not Approved**: Add the `breaking-change-approved` label to merge despite breaking changes.

### Breaking Changes

- **Method Removed**: `POST /api/users`
  - HTTP method POST was removed
- **Parameter Made Required**: `GET /api/users`
  - Parameter 'limit' is now required
  - Location: query

### Required Actions

1. **Review** all breaking changes above
2. **Update** frontend API clients if needed
3. **Update** API documentation
4. **Consider** API versioning for major changes
5. **Add label** `breaking-change-approved` to proceed with merge
```

#### Approving Breaking Changes

To approve a PR with breaking changes:

1. **Review the breaking changes** thoroughly
2. **Ensure all necessary updates** are made:
   - Frontend API clients updated
   - API documentation updated
   - Changelog updated
   - Migration guide provided (if needed)
3. **Add the `breaking-change-approved` label** to the PR
4. **CI will re-run** and allow the PR to proceed

### For Reviewers

When reviewing a PR with breaking changes:

1. **Verify intentionality**: Are the breaking changes intentional or accidental?
2. **Check completeness**: Are all necessary updates included in the PR?
3. **Consider versioning**: Should this use API versioning instead?
4. **Approve the label**: Add `breaking-change-approved` only if all requirements are met

### Local Testing

You can run breaking change detection locally before pushing:

#### Using the Shell Script (Recommended)

```bash
# Compare against main branch
./scripts/check-api-compatibility.sh

# Compare against a specific branch or commit
./scripts/check-api-compatibility.sh origin/develop
./scripts/check-api-compatibility.sh HEAD~5
```

#### Using the Python Script

```bash
# Generate specs
uv run python scripts/generate-openapi.py

# Compare specs (assuming you have base spec from main)
uv run python scripts/check-api-breaking-changes.py \
  --base openapi-main.json \
  --current docs/openapi.json

# Different output formats
uv run python scripts/check-api-breaking-changes.py \
  --base openapi-main.json \
  --current docs/openapi.json \
  --format markdown

uv run python scripts/check-api-breaking-changes.py \
  --base openapi-main.json \
  --current docs/openapi.json \
  --format json
```

## Scripts

### `check-api-compatibility.sh`

Bash script that:

- Installs `oasdiff` if needed
- Generates OpenAPI specs from both branches
- Compares them using `oasdiff`
- Reports breaking changes and full diff

**Location:** `scripts/check-api-compatibility.sh`

**Usage:**

```bash
./scripts/check-api-compatibility.sh [BASE_REF]
```

**Exit codes:**

- `0`: No breaking changes
- `1`: Breaking changes detected

### `check-api-breaking-changes.py`

Python script that:

- Parses OpenAPI specifications
- Implements custom breaking change detection logic
- Supports multiple output formats (text, markdown, JSON)
- Provides detailed categorization of changes

**Location:** `scripts/check-api-breaking-changes.py`

**Usage:**

```bash
python scripts/check-api-breaking-changes.py --base <base-spec> --current <current-spec>
```

**Options:**

- `--base`: Base OpenAPI spec (e.g., from main branch)
- `--current`: Current OpenAPI spec (e.g., from PR branch)
- `--format`: Output format (`text`, `markdown`, `json`)
- `--verbose`: Enable verbose output
- `--allow-potentially-breaking`: Don't fail on potentially breaking changes

**Exit codes:**

- `0`: No breaking changes
- `1`: Breaking changes detected
- `2`: Error (invalid files, parsing failure, etc.)

## Architecture

### Workflow Flow

```
PR Created/Updated
    ↓
Workflow Triggered
    ↓
Generate Main Spec ────────┐
    ↓                      │
Generate PR Spec           │
    ↓                      │
Compare Specs ←────────────┘
    ↓
Breaking Changes? ──→ No ──→ ✅ Pass
    ↓
   Yes
    ↓
Post PR Comment
    ↓
Has 'breaking-change-approved' label? ──→ Yes ──→ ✅ Pass
    ↓
   No
    ↓
❌ Fail (Block PR)
```

### Change Detection Logic

The Python script (`check-api-breaking-changes.py`) implements:

1. **Path comparison**: Detect removed endpoints
2. **Method comparison**: Detect removed HTTP methods
3. **Parameter comparison**: Detect parameter changes (type, required status, removal)
4. **Request body comparison**: Detect request body changes
5. **Response comparison**: Detect response schema changes
6. **Severity classification**: Categorize changes as breaking or potentially breaking

## Testing

### Unit Tests

The breaking change detection logic is tested in:

- `backend/tests/unit/test_check_api_breaking_changes.py`

Run tests:

```bash
uv run pytest backend/tests/unit/test_check_api_breaking_changes.py -v
```

### Test Cases

The test suite covers:

- ✅ No breaking changes
- ✅ Removed endpoints
- ✅ Removed HTTP methods
- ✅ Parameter made required
- ✅ Parameter type changed
- ✅ Removed required parameters
- ✅ Request body removed
- ✅ Multiple breaking changes
- ✅ Markdown output format
- ✅ JSON output format
- ✅ Invalid spec handling

## Best Practices

### For API Developers

1. **Run locally first**: Check for breaking changes before pushing
2. **Document intentional breaks**: If a breaking change is necessary, document it thoroughly
3. **Consider alternatives**:
   - Can you add a new endpoint instead of modifying an existing one?
   - Can you support both old and new parameters during a transition period?
   - Should you introduce API versioning?
4. **Update clients**: Ensure all API clients are updated before merging
5. **Communication**: Inform stakeholders about breaking changes

### For Reviewers

1. **Verify necessity**: Are the breaking changes truly necessary?
2. **Check completeness**: Are all updates included?
3. **Require documentation**: Ensure breaking changes are documented
4. **Consider impact**: Who will be affected by these changes?
5. **Approve thoughtfully**: Only add the approval label when confident

### For Maintainers

1. **Monitor failures**: Review any breaking changes merged to main
2. **Track trends**: Are breaking changes becoming too frequent?
3. **Enforce standards**: Ensure the approval process is followed
4. **Update tooling**: Keep `oasdiff` and detection scripts updated

## Troubleshooting

### False Positives

If the detection reports a breaking change that isn't actually breaking:

1. **Review the change**: Understand why it's flagged
2. **Check the spec**: Ensure the OpenAPI spec is accurate
3. **Update detection logic**: If needed, improve the detection script
4. **Document exception**: Add to known limitations

### Missing Detections

If a breaking change isn't detected:

1. **Report the issue**: Create a Linear issue with details
2. **Add test case**: Add a test for the missed case
3. **Update detection logic**: Improve the script to catch it
4. **Run tests**: Verify the fix works

### Workflow Failures

If the workflow fails unexpectedly:

1. **Check logs**: Review the GitHub Actions logs
2. **Verify specs**: Ensure both specs were generated correctly
3. **Check oasdiff**: Ensure `oasdiff` installed successfully
4. **Retry**: Sometimes transient failures occur

## Integration with Other Systems

### Linear

On main branch failures, the workflow:

- Creates a Linear issue with details
- Links to the failing workflow run
- Avoids duplicate issues

### GitHub

The workflow:

- Posts detailed comments on PRs
- Uses GitHub Actions artifacts to store specs
- Integrates with required status checks

### CI/CD

The breaking change check:

- Runs alongside other API checks
- Must pass for PR to be mergeable
- Can be overridden with approval label

## Future Enhancements

Potential improvements:

1. **Semantic versioning**: Automatically suggest version bumps based on changes
2. **Migration guides**: Auto-generate migration guides for breaking changes
3. **Client SDKs**: Auto-update client SDK versions when breaking changes are approved
4. **Deprecation tracking**: Track deprecated endpoints and warn before removal
5. **Change impact analysis**: Estimate how many clients will be affected
6. **Notification system**: Alert teams when breaking changes are introduced

## References

- [OpenAPI Specification](https://swagger.io/specification/)
- [oasdiff Documentation](https://github.com/Tufin/oasdiff)
- [API Versioning Best Practices](https://www.troyhunt.com/your-api-versioning-is-wrong-which-is/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
