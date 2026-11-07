#!/usr/bin/env bash
# Build the plugin ZIP for the OpenAI plugin submission portal (also usable for manual installs).
# Contains only the portable plugin: plugin.json, the skill, licence and README. Tests, CI and git data are left out.
set -euo pipefail
cd "$(dirname "$0")/.."
version=$(python3 -c 'import json; print(json.load(open("plugin.json"))["version"])')
out="dist/pairwise-design-judging-${version}.zip"
mkdir -p dist
rm -f "$out"
zip -qr "$out" plugin.json skills LICENSE README.md -x '*/__pycache__/*' '*.pyc'
echo "$out"
