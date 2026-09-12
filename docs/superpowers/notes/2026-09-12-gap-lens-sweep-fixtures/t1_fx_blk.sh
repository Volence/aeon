#!/bin/bash
# FIXTURE B (T1 seat): verify_level_bin's content checks read strips_a (an intermediate no
# ROM module embeds) and only the DICT region of secN_blocks.bin (the artifact the ROM
# embeds). Replace sec0_blocks.bin in a scratch copy with an internally-valid blob that
# encodes a DIFFERENT section (sec5_blocks.bin, same K=1 dict length), run the real drift
# gate, then decode it the way the runtime does and count wrong blocks.
S=$(cat /tmp/claude-1000/-home-volence-sonic-hacks-aeon/0f66baa9-0a26-4066-a435-9516186c96f8/scratchpad/t1_S_path)
F="$S/fx_blk"
rm -rf "$F"; cp -a "$S/pristine" "$F"
cd "$F"
make -C tools/salvador -s >/dev/null 2>&1; mkdir -p tools/bin; cp tools/salvador/salvador tools/bin/salvador
G=games/sonic4/data/generated/ojz/act1
grep -n "OJZ_SEC0_BLOCK_DICT_LEN\|OJZ_SEC5_BLOCK_DICT_LEN" $G/sec_block_dicts.emp
cp $G/sec5_blocks.bin $G/sec0_blocks.bin
PYC=$(mktemp -d "$S/pyc.XXXXXX"); export PYTHONPYCACHEPREFIX="$PYC"
python3 tools/verify_level_bin.py; echo "verify_level_bin exit=$?"
python3 - <<'EOF'
import importlib.util, re
spec = importlib.util.spec_from_file_location("bg", "tools/ojz_block_gen.py")
bg = importlib.util.module_from_spec(spec); spec.loader.exec_module(bg)
G = "games/sonic4/data/generated/ojz/act1"
dl = {int(a): int(b) for a, b in re.findall(r"OJZ_SEC(\d+)_BLOCK_DICT_LEN\s*=\s*(\d+)", open(f"{G}/sec_block_dicts.emp").read())}
nt, ca, cb = bg.parse_strips(open(f"{G}/sec0_strips_a.bin", "rb").read())
blob = open(f"{G}/sec0_blocks.bin", "rb").read()
bad = 0
for by in range(16):
    for bx in range(16):
        e = b"".join(bg.extract_block(nt, ca, cb, bx, by))
        g = bg.decode_block(blob, dl[0], by * 16 + bx) or bytes(768)
        bad += (g != e)
print(f"sec0 blocks the runtime would decode WRONG (vs the strips the gate certified): {bad}/256")
EOF
