#!/usr/bin/env python3
"""T1 measurements against the PINNED tree (read-only). Run with cwd = the pinned worktree."""
import json, os, struct, sys
from collections import Counter
sys.path.insert(0, "tools")
import s4lz  # noqa: E402

GEN = "games/sonic4/data/generated/ojz/act1"
ED = "games/sonic4/data/editor/ojz/act1"

print("=== 1. editor BG override")
d = json.load(open("games/sonic4/data/editor_bg_override.json"))
L, T = d["layout"], d["tiles"]
print("layout words", len(L), "tiles", len(T))
print("words == 0:", sum(1 for w in L if w == 0),
      " idx0 with nonzero attrs:", sum(1 for w in L if w and (w & 0x7FF) == 0))
print("tiles[0] all-zero pixels:", all(p == 0 for p in T[0]))
anims = d.get("anims") or ([d["anim"]] if d.get("anim") else [])
for i, a in enumerate(anims):
    print("band", i, {k: a[k] for k in a if k != "phases"}, "phases", len(a["phases"]))
print("attr histogram of nonzero words:", Counter((w & 0xF800) for w in L if w).most_common(6))

print("=== 2. collattr: 16px cell samples the TOP tile row only; does the bottom row ever differ?")
for n in range(9):
    for suffix in ("collattr", "collattrb"):
        p = f"{ED}/section_{n}.{suffix}.bin"
        if not os.path.isfile(p):
            print(f"  sec{n} {suffix}: absent"); continue
        b = open(p, "rb").read()
        if len(b) != 256 * 256 * 2:
            print(f"  sec{n} {suffix}: size {len(b)} != 131072"); continue
        w = struct.unpack(">65536H", b)
        diff = bot_only = 0
        for cr in range(128):
            top, bot = w[(2 * cr) * 256:(2 * cr + 1) * 256], w[(2 * cr + 1) * 256:(2 * cr + 2) * 256]
            for c in range(256):
                if top[c] != bot[c]:
                    diff += 1
                    if top[c] == 0 and bot[c] != 0:
                        bot_only += 1
        nz = sum(1 for x in w if x)
        print(f"  sec{n} {suffix}: nonzero words {nz}, 16px cells whose bottom row != top row: {diff} "
              f"(bottom-only painted: {bot_only})")

print("=== 3. ROM-consumed chain: decode EVERY block of secN_blocks.bin and compare with strips_a")
import importlib.util
spec = importlib.util.spec_from_file_location("ojz_block_gen", "tools/ojz_block_gen.py")
bg = importlib.util.module_from_spec(spec); spec.loader.exec_module(bg)
import re
dl = {int(a): int(b) for a, b in re.findall(r"OJZ_SEC(\d+)_BLOCK_DICT_LEN\s*=\s*(\d+)", open(f"{GEN}/sec_block_dicts.emp").read())}
tot_blocks = bad = 0
for n in range(9):
    raw = open(f"{GEN}/sec{n}_strips_a.bin", "rb").read()
    nt, ca, cb = bg.parse_strips(raw)
    blob = open(f"{GEN}/sec{n}_blocks.bin", "rb").read()
    for by in range(16):
        for bx in range(16):
            ntd, cad, cbd = bg.extract_block(nt, ca, cb, bx, by)
            exp = ntd + cad + cbd
            got = bg.decode_block(blob, dl[n], by * 16 + bx)
            if got is None:
                got = bytes(768)
            tot_blocks += 1
            if got != exp:
                bad += 1
print(f"  blocks decoded {tot_blocks}, mismatching strips_a: {bad}")

print("=== 4. baked words: tile index 0 carrying attribute bits (engine .pw_new_blank writes $0000)")
for n in range(9):
    raw = open(f"{GEN}/sec{n}_strips_a.bin", "rb").read()
    nt, _, _ = bg.parse_strips(raw)
    words = [w for row in nt for w in row]
    pri = sum(1 for w in words if (w & 0x7FF) == 0 and (w & 0x8000))
    anyattr = sum(1 for w in words if (w & 0x7FF) == 0 and (w & 0xF800))
    print(f"  sec{n}: idx0+priority {pri}, idx0+any attr {anyattr}")
