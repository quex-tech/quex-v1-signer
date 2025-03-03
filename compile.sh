#!/bin/bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <requirements.txt path>"
    exit 1
fi

requirements=$(realpath "$1")

temp_dir=$(mktemp -d)
function finish {
  rm -rf "$temp_dir"
}
trap finish EXIT

cd "$temp_dir"
pip download -r "$requirements" --quiet
hash_pattern=$(pip hash * | grep -oP "(?<=--hash=).*" | paste -sd "|")

uv pip compile \
  --generate-hashes \
  --refresh \
  --quiet \
  "$requirements" \
  | grep -P "==|$hash_pattern" \
  | sed '/--hash=/ s/ \\$//'
