#!/bin/bash
# FIXTURE A (T1 seat): a SHORT (non-empty) editor tileset. editor_data_available() refuses
# only a ZERO-byte tileset (lens D3). Truncate the tileset in a scratch copy to 700 of its
# 919 tiles while the editor sections still reference indices up to 732, then run the real
# re-bake and the real drift gate. Question: does anything refuse, or does it bake blanks?
S=$(cat /tmp/claude-1000/-home-volence-sonic-hacks-aeon/0f66baa9-0a26-4066-a435-9516186c96f8/scratchpad/t1_S_path)
F="$S/fx_trunc"
rm -rf "$F"; cp -a "$S/pristine" "$F"
python3 - "$F/tools/regenerate-level.sh" <<'EOF'
import sys
p = sys.argv[1]; s = open(p).read()
old = 'cd "$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"'
assert s.count(old) == 1
open(p, "w").write(s.replace(old, 'cd "$(dirname "${BASH_SOURCE[0]}")/.."'))
EOF
TS="$F/games/sonic4/data/editor/ojz_tiles.bin"
echo "tileset before: $(stat -c%s "$TS") bytes"
truncate -s $((700*32)) "$TS"
echo "tileset after:  $(stat -c%s "$TS") bytes ($((700)) tiles; editor references up to index 732)"
cd "$F"
export EMPYREAN_SUITE_ROOT=/home/volence/sonic_hacks
export AEON_SONIC_HACK_DIR=/home/volence/sonic_hacks/sonic_hack
export AEON_SKDISASM_DIR=/home/volence/sonic_hacks/skdisasm
PYC=$(mktemp -d "$S/pyc.XXXXXX"); export PYTHONPYCACHEPREFIX="$PYC"
echo "start_utc=$(date -u +%FT%TZ)"
bash tools/regenerate-level.sh > "$S/fx_trunc.log" 2>&1
rc=$?
echo "regenerate-level.sh finished=$rc end_utc=$(date -u +%FT%TZ)"
grep -n "Tile art:\|Source tile indices\|Deduped\|Act art pool:\|Pages:\|verify_level_bin\|ERROR\|Traceback\|REFUS\|Re-bake complete" "$S/fx_trunc.log"
python3 - "$F" <<'EOF'
import sys, os, struct
F = sys.argv[1]
G = os.path.join(F, "games/sonic4/data/generated/ojz/act1")
P = os.path.join(os.path.dirname(F), "pristine/games/sonic4/data/generated/ojz/act1")
diff = []
for fn in sorted(os.listdir(P)):
    a = open(os.path.join(P, fn), "rb").read()
    b = open(os.path.join(G, fn), "rb").read() if os.path.exists(os.path.join(G, fn)) else None
    if a != b: diff.append(fn)
print("generated files differing from the committed tree:", len(diff), diff[:14], "..." if len(diff) > 14 else "")
# which editor references fell off the end, and what did they bake to?
pool = b"".join(open(os.path.join(G, f"act_pool_page{k}.bin"), "rb").read() for k in range(64)
                if os.path.exists(os.path.join(G, f"act_pool_page{k}.bin")))
ed = os.path.join(F, "games/sonic4/data/editor/ojz/act1")
oob_words = oob_idx = 0; idxs = set()
for n in range(9):
    w = struct.unpack(">65536H", open(os.path.join(ed, f"section_{n}.tiles.bin"), "rb").read())
    for x in w:
        if (x & 0x7FF) >= 700:
            oob_words += 1; idxs.add(x & 0x7FF)
print(f"editor nametable words referencing tiles 700..: {oob_words} ({len(idxs)} distinct tile indices) -- each baked as a BLANK tile with no diagnostic")
EOF
