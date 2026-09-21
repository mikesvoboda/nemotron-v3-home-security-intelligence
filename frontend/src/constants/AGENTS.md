# Constants

## Purpose

Centralized, framework-free app constants. Currently: the single source of truth for chart colors used by Recharts and Tremor.

## Key Files

| File                | Purpose                                                        |
| ------------------- | -------------------------------------------------------------- |
| `index.ts`          | `export * from './chartColors'` — import from `src/constants`   |
| `chartColors.ts`    | All hex/Tremor color tokens and their derived union types       |

## chartColors.ts Groups

| Export                                      | Use                                                    |
| ------------------------------------------- | ------------------------------------------------------ |
| `SEVERITY_COLORS` / `SEVERITY_COLORS_ALT`   | Risk-level hex values (critical/high/medium/low/info)  |
| `SEVERITY_TREMOR_COLORS`, `RISK_TREMOR_COLORS`, `RISK_HEX_COLORS` | Severity mapped to Tremor color names |
| `CHART_COLORS`, `CHART_PALETTE`, `TREMOR_PALETTE` | General chart palette (hex + ordered arrays)    |
| `DETECTION_OBJECT_COLORS`, `DETECTION_TREMOR_COLORS`, `DETECTION_HEX_COLORS` | Colors per detected object class |
| `PERFORMANCE_COLORS`, `PERFORMANCE_TREMOR_COLORS` | Latency/throughput charts                        |
| `BODY_PART_COLORS`                          | Pose estimation overlays                                 |
| `SeverityLevel`, `ChartColorKey`, `TremorColorName` | Derived union types                          |

## Gotchas

- **No Tailwind classes here** — values are hex strings (for SVG/inline styles) or Tremor color *names*; mixing the two families in one chart is the usual source of mismatched legends.
- `medium` severity is `#EAB308` (yellow-500) here, but some older components still hardcode `#F59E0B` (amber-500) — normalize to this file rather than adding a third value.
