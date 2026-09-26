#!/bin/bash
# runsets.sh <romdir> <legsdir> NAME [NAME...]: legs.sh over <romdir>/NAME.{bin,lst} -> <legsdir>/NAME
HERE=$(cd "$(dirname "$0")" && pwd)
RD=$1; LD=$2; shift 2
for v in "$@"; do
  "$HERE/legs.sh" "$RD/$v" "$LD/$v" > /dev/null
  echo "$v: $(grep -c 'rc=0' "$LD/$v/legs.meta") legs rc=0, $(grep finished "$LD/$v/legs.meta")"
done
