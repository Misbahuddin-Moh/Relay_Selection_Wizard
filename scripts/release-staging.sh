#!/usr/bin/env bash
# Commit only the reviewed index after verifying its exact working tree.
set -euo pipefail
cd "$(dirname "$0")/.."
branch=$(git branch --show-current)
if [[ "$branch" != 'staging/quality-foundation' ]]; then
  echo 'Release must run on staging/quality-foundation.' >&2; exit 1
fi
if [[ $# -ne 1 || -z "$1" ]]; then echo 'Supply one commit message.' >&2; exit 1; fi
if ! git diff --quiet || [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
  echo 'Stage reviewed files and resolve unstaged/untracked files before releasing.' >&2; exit 1
fi
if git diff --cached --quiet; then echo 'No staged changes to release.' >&2; exit 1; fi
candidate_tree=$(git write-tree)
bash scripts/verify.sh
if ! git diff --quiet || [[ "$candidate_tree" != "$(git write-tree)" ]] || [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
  echo 'Files changed during verification; release stopped.' >&2; exit 1
fi
git commit -m "$1"
git push -u origin "$branch"
echo 'Staging branch pushed. Verify Render deploy status, exact revision, health and protected endpoints before calling it live.'
