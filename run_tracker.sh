#!/usr/bin/env bash
set -euo pipefail

# Load environment variables if .env exists
if [ -f ".env" ]; then
  # shellcheck disable=SC1091
  source ".env"
fi

if [ -z "${VIRTUAL_ENV:-}" ] && [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

# Cleanup downloads older than 3 days (YYYY-MM-DD folders).
if [ -d "downloads" ]; then
  find downloads -mindepth 1 -maxdepth 1 -type d -name "????-??-??" -mtime +3 -print -exec rm -rf {} +
fi

DEFAULT_ARGS=(
  --last-n-days 1
  --max-results 1000
  --require-keyword-match
  --skip-gatekeeper
  --no-summary
  --translate-abstracts
  --telegram
  --log-level INFO
)

PYTHONPATH=src python -m arxiv_paper_hunter.main "${DEFAULT_ARGS[@]}" "$@"
