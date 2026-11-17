#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
gh auth status
/usr/bin/python3 -m unittest discover -s tests -v

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git init -b main
fi
git add .gitignore .github README.md LICENSE ksnip-viewer ksnip_viewer scripts tests
if ! git diff --cached --quiet; then
    git commit -m "Publish Ksnip Viewer under GPLv2"
fi
gh repo create sergioelisan/ksnip_viewer --public --source . --remote origin --push \
    --description "Preview e anotação rápida de screenshots para Nautilus/GNOME"
gh repo view sergioelisan/ksnip_viewer --json url,visibility,licenseInfo
