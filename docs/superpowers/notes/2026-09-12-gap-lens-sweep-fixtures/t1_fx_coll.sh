#!/bin/bash
# FIXTURE D (T1 seat): apply_editor_collision_overlay() treats a wrong-sized
# section_N.collattr.bin as "no editor collision" (prints WARNING, returns the AIR baseline)
# and a wrong-sized collattrb.bin as "absent" (plane B silently MIRRORS plane A).
# D1: truncate sec0 collattr.bin by 2 bytes (the only section with authored collision).
# D2 (separate copy): truncate sec0 collattrb.bin by 2 bytes.
# Question: does the re-bake or its drift gate refuse, or does it ship?
S=$(cat /tmp/claude-1000/-home-volence-sonic-hacks-aeon/0f66baa9-0a26-4066-a435-9516186c96f8/scratchpad/t1_S_path)
for CASE in D1 D2; do
  F="$S/fx_coll_$CASE"
  rm -rf "$F"; cp -a "$S/pristine" "$F"
  python3 - "$F/tools/regenerate-level.sh" <<'EOF'
import sys
p = sys.argv[1]; s = open(p).read()
old = 'cd "$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"'
assert s.count(old) == 1
open(p, "w").write(s.replace(old, 'cd "$(dirname "${BASH_SOURCE[0]}")/.."'))
EOF
  cd "$F"
  E=games/sonic4/data/editor/ojz/act1
  if [ "$CASE" = D1 ]; then T="$E/section_0.collattr.bin"; else T="$E/section_0.collattrb.bin"; fi
  truncate -s 131070 "$T"
  echo "== $CASE: $(basename "$T") now $(stat -c%s "$T") bytes (expected 131072)"
  export EMPYREAN_SUITE_ROOT=/home/volence/sonic_hacks
  export AEON_SONIC_HACK_DIR=/home/volence/sonic_hacks/sonic_hack
  export AEON_SKDISASM_DIR=/home/volence/sonic_hacks/skdisasm
  PYC=$(mktemp -d "$S/pyc.XXXXXX"); export PYTHONPYCACHEPREFIX="$PYC"
  echo "start_utc=$(date -u +%FT%TZ)"
  bash tools/regenerate-level.sh > "$S/fx_coll_$CASE.log" 2>&1
  rc=$?
  echo "regenerate-level.sh finished=$rc end_utc=$(date -u +%FT%TZ)"
  grep -n "sec 0:\|WARNING: .*collattr\|NOTICE: sec 0\|Collision: 9\|verify_level_bin\|Traceback\|Error\|Re-bake complete" "$S/fx_coll_$CASE.log"
  python3 - "$F" "$S/pristine" <<'EOF'
import sys, os
F, P = sys.argv[1], sys.argv[2]
G = "games/sonic4/data/generated/ojz/act1"
def coll(root, plane):
    raw = open(os.path.join(root, G, "sec0_strips_a.bin"), "rb").read()
    off = 512 if plane == "A" else 640
    return [raw[c*776+off:c*776+off+128] for c in range(256)]
for plane in "AB":
    a, b = coll(P, plane), coll(F, plane)
    nz_p = sum(1 for col in a for x in col if x)
    nz_f = sum(1 for col in b for x in col if x)
    print(f"  sec0 plane {plane}: non-air collision cells committed={nz_p}  fixture={nz_f}")
cd = [f for f in ("heightmaps.bin","heightmaps_rot.bin","angles.bin","solidity.bin","crossover.bin")
      if os.path.exists(os.path.join(P,"games/sonic4/data/collision",f)) and
      open(os.path.join(P,"games/sonic4/data/collision",f),"rb").read() != open(os.path.join(F,"games/sonic4/data/collision",f),"rb").read()]
print("  ROM collision tables that changed:", cd)
EOF
done
