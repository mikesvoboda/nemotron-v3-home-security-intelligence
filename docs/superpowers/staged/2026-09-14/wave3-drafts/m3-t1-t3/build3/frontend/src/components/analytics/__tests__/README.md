# Baseline Visualization Tests (NEM-4913)

This directory contains comprehensive unit tests for Phase 2 Baseline Visualization components following TDD principles.

## Test Files

### 1. HourlyPatternChart.test.tsx
Tests for 24-hour activity pattern line chart component.

**Key Test Coverage:**
- ✅ Renders 24 data points (one per hour)
- ✅ Displays confidence band based on std_dev
- ✅ Shows tooltip on hover with hour, avg, std_dev, sample_count
- ✅ Handles empty data gracefully
- ✅ Handles missing hours in data
- ✅ Applies correct colors for data quality (opacity based on sample_count)
- ✅ Peak hour highlighting
- ✅ Accessibility (ARIA labels, keyboard navigation)

**Mock Data Structure:**
```typescript
const mockHourlyPatterns: Record<string, HourlyPattern> = {
  "0": { avg_detections: 0.5, std_dev: 0.3, sample_count: 30 },
  "12": { avg_detections: 5.2, std_dev: 1.1, sample_count: 30 },
  "17": { avg_detections: 8.0, std_dev: 2.0, sample_count: 30 },
};
```

### 2. DailyPatternChart.test.tsx
Tests for 7-day (Monday-Sunday) activity pattern bar chart component.

**Key Test Coverage:**
- ✅ Renders 7 bars (Mon-Sun)
- ✅ Shows peak hour indicator within each bar
- ✅ Displays tooltip with day, avg, peak_hour, total_samples
- ✅ Handles empty data gracefully
- ✅ Handles partial week data
- ✅ Color intensity varies with activity level
- ✅ Weekend vs weekday highlighting
- ✅ Accessibility (ARIA labels, keyboard navigation)

**Mock Data Structure:**
```typescript
const mockDailyPatterns: Record<string, DailyPattern> = {
  "monday": { avg_detections: 45.0, peak_hour: 17, total_samples: 168 },
  "tuesday": { avg_detections: 42.0, peak_hour: 18, total_samples: 168 },
};
```

### 3. BaselineDeviationCard.test.tsx
Tests for current deviation display with color-coded interpretations.

**Key Test Coverage:**
- ✅ Renders correct color for each interpretation:
  - `far_below_normal` → blue
  - `below_normal` → light blue
  - `normal` → green
  - `slightly_above_normal` → yellow
  - `above_normal` → orange
  - `far_above_normal` → red
- ✅ Displays score with correct sign (+/-)
- ✅ Shows interpretation text
- ✅ Renders contributing_factors as badges
- ✅ Handles null deviation (no data state)
- ✅ Icon selection based on interpretation
- ✅ Accessibility (ARIA labels, live regions)

**Mock Data Structure:**
```typescript
const mockDeviation: CurrentDeviation = {
  score: 1.8,
  interpretation: "slightly_above_normal",
  contributing_factors: ["person_count_elevated"],
};
```

### 4. ObjectBaselineChart.test.tsx
Tests for per-class baseline statistics grouped bar chart component.

**Key Test Coverage:**
- ✅ Renders grouped bars for each object class
- ✅ Shows metrics: avg_hourly, peak_hour, total_detections
- ✅ Displays tooltip with class name and values
- ✅ Handles empty object baselines
- ✅ Sorts by selected metric when sortable
- ✅ Color-codes by object class
- ✅ Metric selection and switching
- ✅ Accessibility (ARIA labels, keyboard navigation)

**Mock Data Structure:**
```typescript
const mockObjectBaselines: Record<string, ObjectBaseline> = {
  "person": { avg_hourly: 2.3, peak_hour: 17, total_detections: 550 },
  "vehicle": { avg_hourly: 1.1, peak_hour: 8, total_detections: 264 },
};
```

## TDD Status: RED PHASE ✅

All tests are currently **FAILING** as expected. The components do not exist yet.

### Verification

Run the tests to confirm they fail (Red phase):

```bash
cd frontend

# Test individual components
npm test -- HourlyPatternChart --run
npm test -- DailyPatternChart --run
npm test -- BaselineDeviationCard --run
npm test -- ObjectBaselineChart --run
```

**Expected Output:** All tests should fail with error:
```
Error: Failed to resolve import "./HourlyPatternChart" from "...". Does the file exist?
```

This confirms we're in the **Red phase** of TDD.

## Next Steps (Implementation Phase)

After these tests are approved, proceed to the **Green phase**:

1. Create `HourlyPatternChart.tsx` component
2. Create `DailyPatternChart.tsx` component
3. Create `BaselineDeviationCard.tsx` component
4. Create `ObjectBaselineChart.tsx` component

Each component should be implemented to make the tests pass while following:
- Tremor React chart components (`@tremor/react`)
- Existing patterns from analytics components
- Accessibility best practices
- Type safety with TypeScript

## Test Patterns Used

### React Testing Library
- `render()` - Render components
- `screen.getByText()` - Find elements by text
- `screen.getByTestId()` - Find elements by test ID
- `waitFor()` - Wait for async operations
- `userEvent` - Simulate user interactions

### Mock Data Fixtures
- Full datasets for happy path testing
- Partial datasets for edge case handling
- Empty datasets for no-data states
- Varying sample counts for data quality indicators

### Accessibility Testing
- ARIA labels and roles
- Keyboard navigation (tab, enter, space)
- Screen reader support
- Focus management

## Integration with Existing Code

These components will integrate with existing hooks:
- `useCameraBaselineQuery` - Fetch baseline summary
- `useCameraActivityBaselineQuery` - Fetch activity heatmap data
- `useCameraClassBaselineQuery` - Fetch class frequency data

API schemas are defined in:
- `backend/api/schemas/baseline.py`

Frontend types are exported from:
- `frontend/src/services/api.ts`

## Coverage Goals

Following project standards:
- **Unit test coverage:** 85% minimum
- **Combined coverage:** 95% minimum
- All edge cases handled
- All user interactions tested
- Accessibility verified
