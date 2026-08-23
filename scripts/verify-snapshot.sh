#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

sha256sum -c SHA256SUMS

# Bounded, high-confidence credential patterns. This supplements—not replaces—review.
pattern='BEGIN ([A-Z ]+ )?PRIVATE KEY|github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|sk-[A-Za-z0-9]{32,}'
if grep -RInE --exclude='SHA256SUMS' --exclude='verify-snapshot.sh' "$pattern" dotfiles manifests README.md AI_AGENT_INTEGRATION.md; then
  echo "Potential credential material detected." >&2
  exit 1
fi

echo "Integrity and bounded secret-pattern checks passed."
