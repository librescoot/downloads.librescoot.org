#!/usr/bin/env bash
set -euo pipefail
out=${1:?output directory required}
for name in latest stable testing nightly; do
  [ -f "$out/$name.json" ] || { echo "ERROR: missing $name.json" >&2; exit 1; }
done
if [ -z "${STABLE_BRIDGE_TAG:-}${TESTING_BRIDGE_TAG:-}${NIGHTLY_BRIDGE_TAG:-}" ] && [ -e "$out/v2/bridge.json" ]; then
  echo 'ERROR: stale bridge manifest exists while bridge pins are unset' >&2
  exit 1
fi
mkdir -p "$out/v2"
for name in latest stable testing nightly; do
  cp "$out/$name.json" "$out/v2/$name.json"
done
