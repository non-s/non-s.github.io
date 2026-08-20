#!/usr/bin/env bash
set -euo pipefail

evidence_root="${RUNNER_TEMP}/liquid-wire-publication-ledger"
rm -rf "${evidence_root}"
mkdir -p "${evidence_root}"

gh api "/repos/${GITHUB_REPOSITORY}/actions/artifacts?per_page=100" \
  --jq '.artifacts[] | select(.expired == false and (.name | startswith("liquid-wire-evidence-"))) | .id' \
  | while read -r artifact_id; do
      target="${evidence_root}/${artifact_id}"
      mkdir -p "${target}"
      gh api "/repos/${GITHUB_REPOSITORY}/actions/artifacts/${artifact_id}/zip" > "${target}.zip"
      unzip -q "${target}.zip" -d "${target}"
    done

python scripts/rebuild_publication_ledger.py "${evidence_root}"
