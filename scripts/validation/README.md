# Validation Scripts

This directory contains local validation and regression scripts for HumaSkill.

Keep `scripts/` for runnable user-facing entrypoints, such as:

- `run_harness_sequence.py`
- `run_single_gmt_motion.py`
- inspection utilities

Put scoped checks and milestone regressions here as `validate_*.py`.

Run from the repository root, for example:

```bash
python scripts/validation/validate_hermite.py
python scripts/validation/validate_transition_planner.py
```
