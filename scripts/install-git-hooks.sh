#!/usr/bin/env bash
# Install the repository's git hooks (run once per clone).
set -euo pipefail
cd "$(dirname "$0")/.."
git config core.hooksPath scripts/git-hooks
chmod +x scripts/git-hooks/*
echo "git hooks installed (core.hooksPath = scripts/git-hooks)"
