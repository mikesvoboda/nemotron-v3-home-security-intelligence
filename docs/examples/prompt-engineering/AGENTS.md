# Prompt Engineering Examples

## Purpose

This directory contains practical examples for prompt engineering with NVIDIA Nemotron models in the home security monitoring system.

## Contents

| File                     | Description                                   |
| ------------------------ | --------------------------------------------- |
| `basic-risk-analysis.md` | Minimal prompt for quick risk assessments     |
| `rubric-based-prompt.md` | Explicit rubric-based scoring for consistency |
| `chain-of-thought.md`    | Transparent reasoning with `<think>` blocks   |
| `ab-test-config.md`      | A/B experiment setup and analysis             |

## When to Use Each Example

| Scenario                           | Recommended Example    |
| ---------------------------------- | ---------------------- |
| Development/testing                | basic-risk-analysis.md |
| Production with audit requirements | rubric-based-prompt.md |
| Debugging unexpected scores        | chain-of-thought.md    |
| Comparing prompt versions          | ab-test-config.md      |

## Related Documentation

- [Nemotron Prompting Guide](../../development/nemotron-prompting.md) - Comprehensive documentation
- [AI Nemotron AGENTS.md](../../../ai/nemotron/AGENTS.md) - Model configuration

## Implementation Files

| Example          | Primary Implementation                  |
| ---------------- | --------------------------------------- |
| Basic            | `backend/services/prompts.py`           |
| Rubric-based     | `backend/services/risk_rubrics.py`      |
| Chain-of-thought | `backend/services/nemotron_analyzer.py` |
| A/B testing      | `backend/config/prompt_ab_config.py`    |
