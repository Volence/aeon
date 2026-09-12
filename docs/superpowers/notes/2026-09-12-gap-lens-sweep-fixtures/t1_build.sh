#!/bin/bash
# Control first, then fixture C: FAST=1 DEBUG=1 ./build.sh in (a) an untouched copy of the
# pin and (b) the fx_tail copy (section_8.tiles.bin deleted + re-baked). Question: does the
# fixture tree still assemble and link, and what bytes sit where the engine will read
# OJZ_Sec_LocalMaps[8]?
S=$(cat /tmp/claude-1000/-home-volence-sonic-hacks-aeon/0f66baa9-0a26-4066-a435-9516186c96f8/scratchpad/t1_S_path)
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
[ -x "$SIGIL_BUILD" ] && [ -x "$SIGIL_EMIT" ] || { echo "BLOCKED: sigil binaries missing"; exit 2; }
export EMPYREAN_SUITE_ROOT=/home/volence/sonic_hacks
rm -rf "$S/build_ctrl"; cp -a "$S/pristine" "$S/build_ctrl"
for T in build_ctrl fx_tail; do
  cd "$S/$T" || exit 9
  PYC=$(mktemp -d "$S/pyc.XXXXXX"); export PYTHONPYCACHEPREFIX="$PYC"
  echo "== $T start_utc=$(date -u +%FT%TZ) $(TZ=UTC uptime)"
  FAST=1 DEBUG=1 ./build.sh > "$S/build_$T.log" 2>&1
  rc=$?
  echo "== $T build.sh finished=$rc end_utc=$(date -u +%FT%TZ)"
  grep -n -i "error\|refus\|STALE\|FAILED" "$S/build_$T.log" | head -15
  if [ -f s4.debug.lst ]; then
    grep -n "OJZ_Sec_LocalMaps\|OJZ_Sec[0-9]_LocalMap\b" s4.debug.lst | head -20
  else
    echo "no s4.debug.lst"
  fi
  [ -f s4.debug.bin ] && echo "rom bytes: $(stat -c%s s4.debug.bin)"
done
