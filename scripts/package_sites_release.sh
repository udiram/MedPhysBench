#!/usr/bin/env bash
set -euo pipefail

repository_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
archive_path="${1:?usage: scripts/package_sites_release.sh ARCHIVE_PATH}"
web_dist="$repository_dir/web/dist"
hosting_config="$repository_dir/.openai/hosting.json"

test -f "$web_dist/server/index.js" || {
  echo "Missing web/dist/server/index.js; run npm --prefix web run build first." >&2
  exit 2
}
test -f "$hosting_config" || {
  echo "Missing .openai/hosting.json." >&2
  exit 2
}

stage_dir="$(mktemp -d)"
cleanup() {
  rm -rf -- "$stage_dir"
}
trap cleanup EXIT

mkdir -p "$stage_dir/dist/.openai" "$(dirname "$archive_path")"
cp -R "$web_dist"/. "$stage_dir/dist"/
cp "$hosting_config" "$stage_dir/dist/.openai/hosting.json"
tar -C "$stage_dir" -czf "$archive_path" dist

archive_entries="$(tar -tzf "$archive_path")"
grep -qx 'dist/server/index.js' <<<"$archive_entries"
grep -qx 'dist/.openai/hosting.json' <<<"$archive_entries"
printf '%s\n' "$archive_path"
