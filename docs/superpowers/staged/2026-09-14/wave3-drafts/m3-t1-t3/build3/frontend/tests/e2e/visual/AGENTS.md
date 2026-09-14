# Visual Regression Tests

## Purpose

Visual regression tests capture screenshots and compare them against baseline images to detect unintended UI changes. These tests catch:

- CSS regressions
- Layout shifts
- Styling bugs
- Component visual changes
- Responsive design issues

## Directory Structure

```
frontend/tests/e2e/visual/
├── AGENTS.md                    # This documentation
├── dashboard.visual.spec.ts     # Dashboard page visual tests
├── timeline.visual.spec.ts      # Timeline page visual tests
├── settings.visual.spec.ts      # Settings page visual tests
├── system.visual.spec.ts        # System page visual tests
├── components.visual.spec.ts    # Reusable component visual tests
├── responsive.visual.spec.ts    # Responsive design tests (3 viewports)
└── *.png                        # Baseline snapshot images (auto-generated)
```

## Running Visual Tests

```bash
# From frontend/ directory

# Run all visual tests
npx playwright test --project=visual-chromium

# Run specific visual test file
npx playwright test --project=visual-chromium visual/dashboard.visual.spec.ts

# Run tests matching a pattern
npx playwright test --project=visual-chromium -g "dashboard"

# Update baseline snapshots (when intentional changes are made)
npx playwright test --project=visual-chromium --update-snapshots

# View HTML report with visual diffs
npx playwright show-report
```

## Test Categories

| File                      | Description                              | Screenshots |
| ------------------------- | ---------------------------------------- | ----------- |
| `dashboard.visual.spec.ts`| Dashboard page, stats row, camera grid   | 6           |
| `timeline.visual.spec.ts` | Event timeline, cards, filters           | 6           |
| `settings.visual.spec.ts` | Settings tabs (cameras, processing, etc) | 6           |
| `system.visual.spec.ts`   | System monitoring panels and metrics     | 10          |
| `components.visual.spec.ts`| Reusable UI components                  | 15+         |
| `responsive.visual.spec.ts`| 3 viewports x 4 pages                   | 12+         |

## Viewport Sizes

Tests run at three viewport sizes for responsive testing:

| Viewport | Width  | Height | Purpose         |
| -------- | ------ | ------ | --------------- |
| Desktop  | 1920px | 1080px | Full desktop    |
| Tablet   | 1024px | 768px  | iPad/tablet     |
| Mobile   | 375px  | 667px  | iPhone SE/small |

## Screenshot Configuration

From `playwright.config.ts`:

```typescript
expect: {
  toHaveScreenshot: {
    maxDiffPixels: 100,      // Allow up to 100 pixels difference
    threshold: 0.2,          // Per-pixel color difference threshold
    animations: 'disabled',  // Disable animations for consistency
  },
}
```

## Handling Dynamic Content

Dynamic content is masked to prevent false positives:

```typescript
await expect(page).toHaveScreenshot('page.png', {
  mask: [
    page.locator('[data-testid="timestamp"]'),
    page.locator('time'),
    page.locator('[data-testid="live-metrics"]'),
    page.locator('img'),  // Camera snapshots vary
  ],
});
```

## Updating Baselines

When UI changes are intentional:

1. **Local update:**
   ```bash
   npx playwright test --project=visual-chromium --update-snapshots
   ```

2. **Review changes:**
   ```bash
   npx playwright show-report
   ```

3. **Commit updated snapshots:**
   ```bash
   git add frontend/tests/e2e/visual/*.png
   git commit -m "chore: update visual regression baselines"
   ```

4. **CI workflow (manual):**
   - Go to Actions tab in GitHub
   - Select "Visual Regression Tests" workflow
   - Click "Run workflow"
   - Check "Update baseline snapshots"
   - Download artifacts and commit

## CI Integration

Visual tests run in `.github/workflows/visual-tests.yml`:

- **Triggers:** PR and push to main (frontend changes only)
- **Browser:** Chromium only (for consistency)
- **Artifacts (generated during CI runs):**
  - HTML report (output in CI artifacts)
  - Test artifacts (output in CI artifacts)
  - Diff images on failure (output in CI artifacts)

## Best Practices

### DO

- Mask dynamic content (timestamps, live metrics, charts)
- Wait for `networkidle` before screenshots
- Add small delay after animations (`waitForTimeout(500)`)
- Use component-level screenshots for isolated testing
- Test different states (empty, loaded, error, high-alert)

### DON'T

- Screenshot real images (mask them)
- Test animation frames (disable animations)
- Rely on exact pixel matching (use `maxDiffPixels`)
- Update baselines without reviewing diffs
- Add visual tests for every minor component

## Debugging Failures

When visual tests fail:

1. **View the HTML report:**
   ```bash
   npx playwright show-report
   ```

2. **Check diff images:** The report shows:
   - Expected (baseline)
   - Actual (current)
   - Diff (highlighted differences)

3. **Common causes:**
   - Animation timing (add `waitForTimeout`)
   - Font rendering (increase `threshold`)
   - Dynamic content (add to `mask`)
   - Legitimate UI change (update baseline)

## Integration with E2E Tests

Visual tests are separate from functional E2E tests:

- **E2E tests (`../specs/`)**: Test functionality and user interactions
- **Visual tests (this directory)**: Test appearance and layout

Both use the same:
- Page objects (`../pages/`)
- Fixtures (`../fixtures/`)
- Mock configurations

## Notes for AI Agents

- Visual tests run on **Chromium only** for consistency
- Baseline images are committed to the repository
- The `visual-chromium` project is separate from functional tests
- Update baselines only after reviewing diff reports
- Keep masking rules consistent across related tests
- New pages need both functional E2E tests AND visual tests
