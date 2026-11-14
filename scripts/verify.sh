#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
relay_python="${RELAY_TEST_PYTHON:-.venv/bin/python}"
if [[ ! -x "$relay_python" ]]; then relay_python=python; fi
env -u ANTHROPIC_API_KEY -u OPENAI_API_KEY "$relay_python" -m unittest discover -s tests -v
npm --prefix frontend test
npm --prefix frontend run build
RELAY_TEST_PYTHON="$relay_python" node scripts/browser-smoke.mjs
RELAY_TEST_PYTHON="$relay_python" node scripts/project-recovery-smoke.mjs
