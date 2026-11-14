#!/usr/bin/env bash
set -euo pipefail
stable=${STABLE_BRIDGE_TAG:-}
testing=${TESTING_BRIDGE_TAG:-}
nightly=${NIGHTLY_BRIDGE_TAG:-}
has_zstd=$(jq -r 'any(.[]; any(.assets[]?; .name | endswith(".ota-zstd.json")))')
if [ -n "$stable$testing$nightly" ]; then
  if [ -z "$stable" ] || [ -z "$testing" ] || [ -z "$nightly" ]; then
    echo 'ERROR: stable, testing and nightly bridge tags must all be set' >&2
    exit 1
  fi
elif [ "$has_zstd" = true ]; then
  echo 'ERROR: zstd-only release exists but legacy bridge pins are not configured' >&2
  exit 1
fi
