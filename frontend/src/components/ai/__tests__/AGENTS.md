# AI Component Tests Directory

## Purpose

The `frontend/src/components/ai/__tests__/` directory contains unit tests for the AI-related components in the frontend, specifically the `PromptPlayground` component. These tests verify the functionality of the A/B testing interface for AI prompt configuration.

## Directory Structure

```
frontend/src/components/ai/__tests__/
├── AGENTS.md                                    # This file
├── PromptPlayground.actions.test.tsx            # 6,570 bytes - Action button tests
├── PromptPlayground.diffPreview.test.tsx        # 13,425 bytes - Diff preview modal tests
├── PromptPlayground.modelEditors.test.tsx       # 5,368 bytes - Model editor tests
├── PromptPlayground.promoteB.test.tsx           # 15,710 bytes - Promote-to-primary tests
└── PromptPlayground.rendering.test.tsx          # 7,013 bytes - Basic rendering tests
```

## Test Files Overview

### `PromptPlayground.rendering.test.tsx` (7,013 bytes)

**Purpose:** Tests basic rendering and visibility of the PromptPlayground component.

**Coverage:**
- Component visibility (open/closed state)
- Title and description rendering
- Model accordions rendering (Nemotron, Florence2, YOLO-World)
- Nemotron configuration fields (system prompt, temperature, max tokens)
- Recommendation context display
- Close button functionality
- Export/import buttons

**Key Test Cases:**
- Renders when open, hidden when closed
- Displays correct title and description
- Shows all model configuration sections
- Renders form controls for each model

**Related:** `PromptPlayground.tsx` component

### `PromptPlayground.actions.test.tsx` (6,570 bytes)

**Purpose:** Tests action buttons (Export, Import, Save, Reset, etc.).

**Coverage:**
- Export button functionality
- Import button functionality
- Save button behavior (creates or updates prompts)
- Reset button behavior (reverts to original configuration)
- Button states (enabled/disabled)
- Loading states during API calls

**Key Test Cases:**
- Export downloads JSON configuration
- Import loads JSON and updates UI
- Save calls API with correct payload
- Reset reverts unsaved changes

**Related:** API client methods in `services/api.ts`

### `PromptPlayground.diffPreview.test.tsx` (13,425 bytes)

**Purpose:** Tests the diff preview modal that shows configuration changes before saving.

**Coverage:**
- Diff preview modal rendering
- Side-by-side comparison display
- "Primary → Secondary" workflow
- "Secondary → Primary" workflow
- Change highlighting
- Modal close and cancel functionality

**Key Test Cases:**
- Modal shows differences between configurations
- Highlights added, removed, and modified fields
- Correctly labels "Primary" and "Secondary" configurations
- Close button dismisses modal without saving

**Related:** Diff algorithm for comparing JSON configurations

### `PromptPlayground.modelEditors.test.tsx` (5,368 bytes)

**Purpose:** Tests individual model editor sections (Nemotron, Florence2, YOLO-World).

**Coverage:**
- Nemotron editor: system prompt, temperature, max_tokens
- Florence2 editor: VQA queries array
- YOLO-World editor: object classes and confidence threshold
- Form validation
- Real-time state updates

**Key Test Cases:**
- Each model's editor renders with correct fields
- Input changes update component state
- Validation errors display for invalid inputs
- Array fields (VQA queries, object classes) can be added/removed

**Related:** Model-specific configuration schemas

### `PromptPlayground.promoteB.test.tsx` (15,710 bytes)

**Purpose:** Tests the "Promote to Primary" workflow (B-to-A promotion).

**Coverage:**
- Promote button visibility and behavior
- Confirmation dialog
- API call to update primary configuration
- Success/error handling
- State synchronization after promotion
- Post-promotion cleanup (secondary becomes copy of primary)

**Key Test Cases:**
- Promote button only visible when secondary differs from primary
- Confirmation dialog shows before promotion
- API call includes correct payload
- Success updates both primary and secondary configurations
- Error handling displays appropriate messages

**Related:** A/B testing workflow in Phase 8 (NEM-1751)

## Testing Technology Stack

### Testing Libraries

- **Vitest:** Test runner (Jest-compatible API)
- **React Testing Library:** Component testing utilities
- **@testing-library/user-event:** User interaction simulation
- **@testing-library/jest-dom:** DOM matchers

### Mocking Strategy

All test files mock the API client:

```tsx
// Mock the API functions
vi.mock('../../../services/api', () => ({
  fetchAllPrompts: vi.fn(() => Promise.resolve({ /* mock data */ })),
  updatePrompt: vi.fn(() => Promise.resolve({ success: true })),
  createPrompt: vi.fn(() => Promise.resolve({ success: true })),
}));
```

This isolates component logic from backend dependencies.

## Test Organization

### File Naming Convention

All test files follow the pattern:

```
PromptPlayground.<test-suite>.test.tsx
```

**Benefits:**
- Grouped together when sorted alphabetically
- Clear indication of parent component
- Specific test suite purpose in filename

### Test Suite Structure

Each test file uses:

```tsx
describe('PromptPlayground - <Suite Name>', () => {
  beforeEach(() => {
    // Setup: Reset mocks, clear state
  });

  it('should <behavior>', () => {
    // Arrange: Render component
    // Act: Trigger user actions
    // Assert: Verify expected outcome
  });
});
```

## Running Tests

### Run All AI Component Tests

```bash
cd frontend
npm test -- src/components/ai/__tests__/
```

### Run Specific Test File

```bash
npm test -- PromptPlayground.rendering.test.tsx
```

### Run with Coverage

```bash
npm test -- --coverage src/components/ai/__tests__/
```

### Watch Mode

```bash
npm test -- --watch src/components/ai/__tests__/
```

## Test Coverage Requirements

As defined in `vite.config.ts`:

- **Statements:** 83%
- **Branches:** 77%
- **Functions:** 81%
- **Lines:** 84%

These thresholds are enforced in CI.

## NEM-1320 Refactoring

**Context:** These test files were refactored from a single large `PromptPlayground.test.tsx` file as part of NEM-1320.

**Benefits of split structure:**
- Faster test execution (parallel test runners)
- Easier to locate specific test failures
- Better code organization and maintainability
- Reduced cognitive load when adding new tests

**Original file:** Previously ~20,000+ lines, now split into 5 focused files.

## Key Testing Patterns

### Async API Calls

```tsx
it('saves configuration on save button click', async () => {
  const user = userEvent.setup();
  render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

  const saveButton = screen.getByText('Save');
  await user.click(saveButton);

  await waitFor(() => {
    expect(updatePrompt).toHaveBeenCalledWith(expect.objectContaining({ /* ... */ }));
  });
});
```

### User Interactions

```tsx
it('updates temperature when slider changes', async () => {
  const user = userEvent.setup();
  render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

  const slider = screen.getByLabelText('Temperature');
  await user.clear(slider);
  await user.type(slider, '0.9');

  expect(slider).toHaveValue(0.9);
});
```

### Modal Visibility

```tsx
it('opens diff preview when compare button clicked', async () => {
  const user = userEvent.setup();
  render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

  await user.click(screen.getByText('Compare'));

  expect(screen.getByRole('dialog')).toBeInTheDocument();
  expect(screen.getByText('Configuration Diff')).toBeVisible();
});
```

## Related Documentation

- `/frontend/src/components/ai/AGENTS.md` - AI component directory overview
- `/frontend/src/components/ai/PromptPlayground.tsx` - Component under test
- `/frontend/src/services/api.ts` - API client (mocked in tests)
- `/docs/plans/PHASE-8-INTEGRATION-TESTING.md` - Integration testing strategy
- `/docs/ROADMAP.md` - Post-MVP A/B testing features

## Maintenance Guidelines

### Adding New Tests

When adding tests for new PromptPlayground features:

1. **Choose the right file:**
   - Rendering/visibility → `PromptPlayground.rendering.test.tsx`
   - Actions/buttons → `PromptPlayground.actions.test.tsx`
   - Diff preview → `PromptPlayground.diffPreview.test.tsx`
   - Model editors → `PromptPlayground.modelEditors.test.tsx`
   - Promote workflow → `PromptPlayground.promoteB.test.tsx`

2. **Create a new file if needed:**
   - Follow naming convention: `PromptPlayground.<suite>.test.tsx`
   - Add comprehensive description header
   - Update this AGENTS.md with new file details

3. **Follow existing patterns:**
   - Use `describe` blocks to group related tests
   - Use descriptive `it` test names
   - Mock API calls consistently
   - Use `userEvent` for interactions (not `fireEvent`)

### Debugging Test Failures

If tests fail:

1. **Run in watch mode:** `npm test -- --watch <filename>`
2. **Check mock data:** Ensure mocked API responses match expected schema
3. **Use `screen.debug()`:** Print component DOM to console
4. **Check async timing:** Add `waitFor` for async state updates
5. **Verify selectors:** Use Testing Library Playground browser extension

### Refactoring Tests

When refactoring these tests:

- **Maintain coverage:** Don't reduce coverage below thresholds
- **Update documentation:** Keep this AGENTS.md in sync
- **Run full suite:** Ensure no regressions in other test files
- **Preserve intent:** Test behavior, not implementation details

## CI Integration

These tests run in CI as part of the frontend test suite:

```yaml
# .github/workflows/ci.yml
- name: Run frontend tests
  run: |
    cd frontend
    npm test -- --coverage
```

**CI Requirements:**
- All tests must pass
- Coverage thresholds must be met
- No console errors or warnings
- Tests must complete within timeout (5 minutes)

## Performance Metrics

Current test execution times (approximate):

| Test File                              | Duration | Tests |
| -------------------------------------- | -------- | ----- |
| `PromptPlayground.rendering.test.tsx`  | ~0.8s    | 12    |
| `PromptPlayground.actions.test.tsx`    | ~1.2s    | 15    |
| `PromptPlayground.diffPreview.test.tsx`| ~1.5s    | 18    |
| `PromptPlayground.modelEditors.test.tsx`| ~0.9s    | 10    |
| `PromptPlayground.promoteB.test.tsx`   | ~1.8s    | 20    |
| **Total**                              | **~6.2s**| **75**|

These tests run in parallel during CI, reducing total wall-clock time.
