# Performance Documentation

This directory contains documentation for performance testing, monitoring, and optimization.

## Contents

| File               | Purpose                                                   |
| ------------------ | --------------------------------------------------------- |
| `LOAD_PROFILES.md` | Realistic load profiles for k6 and pytest-benchmark tests |

## Key Topics

### Load Testing

- **k6 Load Tests:** `tests/load/*.js`
- **Load Profiles:** Smoke, Average, Stress, Spike, Soak
- **Thresholds:** Response time, error rate, throughput limits

### Performance Benchmarking

- **pytest-benchmark:** `backend/tests/benchmarks/*.py`
- **Memory Profiling:** pytest-memray (Linux only)
- **Slow Query Detection:** Automatic slow query logging

### CI/CD Integration

- **Nightly + manual (report-only, owner ruling 100):** benchmarks and load
  tests have no push or PR trigger; they run nightly and on demand, report
  through summaries/artifacts/Linear, and gate nothing. (The former "block
  PRs" / "block main" rows described triggers that never existed in these
  files and a required-context set that only ever held
  `CI Gate (Required Checks)`.)
- **Thresholds:** 20% regression, 500MB memory, 50ms queries

## Related Files

- `.github/workflows/benchmarks.yml` - Performance benchmark CI
- `.github/workflows/load-tests.yml` - k6 load test CI
- `tests/load/config.js` - k6 configuration and thresholds
- `backend/tests/benchmarks/` - Python benchmark tests

## Quick Reference

```bash
# Run benchmarks locally
uv run pytest backend/tests/benchmarks/ --benchmark-only -v

# Run load tests locally
./scripts/load-test.sh all smoke

# Run memory profiling (Linux only)
uv run pytest backend/tests/benchmarks/test_memory.py --memray -v
```
