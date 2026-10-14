#!/usr/bin/env sh
# Dependency inventory (CycloneDX) for the Python engine and the npm SDK — attached to releases.
set -eu
cd "$(dirname "$0")/.."
mkdir -p dist/sbom
.venv/bin/cyclonedx-py environment --of JSON -o dist/sbom/evalkit-python.cdx.json .venv/bin/python
if command -v npm >/dev/null 2>&1 && [ -d sdk/typescript/node_modules ]; then
  (cd sdk/typescript && npm ls --all --json > ../../dist/sbom/evalkit-sdk-npm-tree.json || true)
fi
echo "SBOM written to dist/sbom/"
