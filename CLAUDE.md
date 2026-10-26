# Project rules

- specs/SPEC-1-PRODUCT.md and specs/SPEC-2-ENGINEERING.md are the source of truth.
  If something contradicts them, raise it instead of silently deviating.
- Work ONE phase at a time (SPEC-2 §8). Stop after each. Never run ahead.
- All metric computation lives in backend/app/core/metrics.py. Never in React.
- Forecast selection (SPEC-1 §3.3) must never use a publishTime after the
  cutoff. Any change to selection.py requires test_selection.py to pass.
- Missing forecasts are None, never 0, never interpolated.
- No secrets in the repo. DATABASE_URL and all config come from env.
- pytest must pass with no network access.
