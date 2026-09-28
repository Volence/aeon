#!/bin/bash
# redfirst_ensures.sh <out> : each ARM ensure mutated on disk, FAST DEBUG built (must REFUSE with
#   its own message), then engine/system/constants.emp restored from the COMMITTED file and the
#   restored tree built (must be rc 0). The mutated line is printed into <out>.
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
cd "$(dirname "$0")/../../.." || exit 2
OUT=$1; : > "$OUT"
F=engine/system/constants.emp
n=0
mut() {  # name sed-expression expected-message-fragment
  git show HEAD:$F > $F
  sed -i "$2" $F
  echo "== $1: $(grep -n "^pub const [HV]_PFX_ARM" $F | tr '\n' ' ')" >> "$OUT"
  FAST=1 DEBUG=1 ./build.sh > /tmp/redfirst_$$.log 2>&1
  local rc=$?
  local hit; hit=$(grep -c "$3" /tmp/redfirst_$$.log)
  echo "   rc=$rc own-message-lines=$hit" >> "$OUT"
  n=$((n+1))
}
mut H_ARM_16  's/^pub const H_PFX_ARM .*/pub const H_PFX_ARM = 16/' 'H_PFX_ARM (16 px) must exceed'
mut H_ARM_168 's/^pub const H_PFX_ARM .*/pub const H_PFX_ARM = 168/' 'H_PFX_ARM (168 px) must exceed'
mut V_ARM_2   's/^pub const V_PFX_ARM .*/pub const V_PFX_ARM = 2/' 'V_PFX_ARM (2 rows) must exceed'
mut V_ARM_17  's/^pub const V_PFX_ARM .*/pub const V_PFX_ARM = 17/' 'V_PFX_ARM (17 rows) must exceed'
git show HEAD:$F > $F
FAST=1 DEBUG=1 ./build.sh > /tmp/redfirst_$$.log 2>&1
echo "== restored from HEAD: rc=$? diff-lines=$(git diff --stat -- $F | wc -l)" >> "$OUT"
rm -f /tmp/redfirst_$$.log
echo "finished=$n" >> "$OUT"
