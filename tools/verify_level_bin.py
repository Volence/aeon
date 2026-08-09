#!/usr/bin/env python3
"""Level-tree drift check — the committed OJZ generated tree must be internally
consistent, with NO donor project required.

The OJZ level tree (games/sonic4/data/generated/) ships as committed artifacts
the build consumes directly; its generators read out-of-repo donors so the build
cannot re-derive it (see tools/regenerate-level.sh, the level-gen parcel). It
fails the build LOUDLY if a
committed head was hand-edited, or a referenced blob went missing, or a .zx0 page
drifted from its .bin — the drift a whole-ROM byte gate only catches once the ROM
already moved. It does NOT re-run the generators (those need the donor); it checks
referential integrity + the .zx0 wrapper roundtrip, which need only the tree.

Run from the repo root:  python3 tools/verify_level_bin.py
"""
import os
import re
import struct
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
GEN = os.path.join(ROOT, "games", "sonic4", "data", "generated", "ojz", "act1")
NUM_SECTIONS = 9            # 3x3 grid (project.json); sections 0..8
ART_POOL_PAGE_BYTES = 2048  # ART_POOL_PAGE_TILES (64) * 32
TILE_SIZE = 32
BLOCK_INDEX_BYTES = 1024   # 256 * 4-byte block index table (ojz_block_gen)
BLOCK_RAW_SIZE = 768       # one raw 16x16 block (dict region is a multiple)

_fail = []


def check(cond, msg):
    if not cond:
        _fail.append(msg)


def read(path):
    with open(path, "rb") as f:
        return f.read()


def verify_act_pool():
    """Manifest v2 (P2b): the const manifest page count == the pool's page embeds
    == the [PageManifest;N] table entries == the per-page blob files present. Each
    page's manifest form matches its blob extension; pm_tiles*32 == the .bin size;
    a ZX0 page's wrapper round-trips (size header == .bin, flags/version 0,2)."""
    manifest = os.path.join(GEN, "ojz_act_pool_manifest.emp")
    pool = os.path.join(GEN, "ojz_act_pool.emp")
    if not (os.path.isfile(manifest) and os.path.isfile(pool)):
        check(False, "act pool: ojz_act_pool_manifest.emp / ojz_act_pool.emp missing")
        return
    m = re.search(r"^(?:pub\s+const\s+)?OJZ_ACT_POOL_PAGES\s*=\s*(\d+)$",
                  open(manifest).read(), re.M)
    check(m is not None, "act pool: OJZ_ACT_POOL_PAGES not found in manifest")
    if not m:
        return
    pages = int(m.group(1))
    pool_txt = open(pool).read()
    # page blob embeds — .zx0 or .raw, symbol index must equal file index
    binc = re.findall(
        r'OJZ_Act_Pool_Page(\d+)\s*=\s*embed\("[^"]*/act_pool_page(\d+)\.(zx0|raw)"\)',
        pool_txt)
    embed_ext = {int(sym): ext for sym, fidx, ext in binc if sym == fidx}
    check([int(sym) for sym, fidx, ext in binc if sym == fidx] == list(range(pages)),
          f"act pool: ojz_act_pool.emp embeds {[b[0] for b in binc]}, expected pages 0..{pages-1}")
    # manifest v2 table entries: {source page idx, tiles, form, flags}
    tbl = re.search(r'OJZ_Act_Pool_PageTable[^\[]*\[(.*)\]', pool_txt, re.S)
    entries = re.findall(
        r'pm_source:\s*extern\("OJZ_Act_Pool_Page(\d+)"\)\s*,\s*'
        r'pm_tiles:\s*(\d+)\s*,\s*pm_form:\s*(\d+)\s*,\s*pm_flags:\s*(\d+)',
        tbl.group(1) if tbl else "")
    check([int(e[0]) for e in entries] == list(range(pages)),
          f"act pool: PageManifest table indices {[e[0] for e in entries]}, expected 0..{pages-1}")
    for e in entries:
        k, tiles, form, _flags = int(e[0]), int(e[1]), int(e[2]), int(e[3])
        pbin = os.path.join(GEN, f"act_pool_page{k}.bin")
        if not os.path.isfile(pbin):
            check(False, f"act pool: act_pool_page{k}.bin missing")
            continue
        raw = read(pbin)
        check(len(raw) <= ART_POOL_PAGE_BYTES,
              f"act pool: page{k}.bin is {len(raw)}B > one page ({ART_POOL_PAGE_BYTES})")
        check(tiles * TILE_SIZE == len(raw),
              f"act pool: page{k} manifest tiles {tiles} (*32={tiles*32}) != .bin size {len(raw)}")
        ext = embed_ext.get(k)
        if form == 0:   # ZX0
            check(ext == "zx0", f"act pool: page{k} form 0 (ZX0) but embeds .{ext}")
            pzx0 = os.path.join(GEN, f"act_pool_page{k}.zx0")
            if not os.path.isfile(pzx0):
                check(False, f"act pool: act_pool_page{k}.zx0 missing")
                continue
            w = read(pzx0)
            check(len(w) >= 4, f"act pool: page{k}.zx0 shorter than its 4-byte wrapper")
            if len(w) >= 4:
                usize = struct.unpack(">H", w[0:2])[0]
                check(usize == len(raw),
                      f"act pool: page{k}.zx0 wrapper size {usize} != page{k}.bin size {len(raw)}")
                check(w[2] == 0 and w[3] == 2,
                      f"act pool: page{k}.zx0 wrapper flags/version {w[2]},{w[3]} != 0,2")
        elif form == 1:   # raw-direct
            check(ext == "raw", f"act pool: page{k} form 1 (raw) but embeds .{ext}")
            praw = os.path.join(GEN, f"act_pool_page{k}.raw")
            if not os.path.isfile(praw):
                check(False, f"act pool: act_pool_page{k}.raw missing")
                continue
            check(len(read(praw)) == len(raw),
                  f"act pool: page{k}.raw size != page{k}.bin size {len(raw)}")
        else:
            check(False, f"act pool: page{k} unknown form {form}")


def verify_block_blobs():
    """Every OJZ_Sec{N}_Blocks resolves (BINCLUDE'd blob present, or equ-aliased
    to a present one); sec_block_dicts declares a dict length for every section,
    and the length fits inside the blob (index table + dict region)."""
    # Both the block-blob embeds and the dict-length table are generated `.emp`
    # modules (Parcel K3): sec_block_blobs.emp (natively-placed section) +
    # sec_block_dicts.emp (const module).
    blobs = os.path.join(GEN, "sec_block_blobs.emp")
    dicts = os.path.join(GEN, "sec_block_dicts.emp")
    if not (os.path.isfile(blobs) and os.path.isfile(dicts)):
        check(False, "block blobs: sec_block_blobs.emp / sec_block_dicts.emp missing")
        return
    btxt = open(blobs).read()
    binc = dict(re.findall(r'OJZ_Sec(\d+)_Blocks\s*=\s*embed\("[^"]*/(sec\d+_blocks\.bin)"\)', btxt))
    alias = dict(re.findall(r'OJZ_Sec(\d+)_Blocks\s*=\s*extern\("OJZ_Sec(\d+)_Blocks"\)', btxt))
    dtxt = open(dicts).read()
    dlen = {int(n): int(v) for n, v in
            re.findall(r"OJZ_SEC(\d+)_BLOCK_DICT_LEN\s*=\s*(\d+)", dtxt)}
    for n in range(NUM_SECTIONS):
        s = str(n)
        check(s in binc or s in alias,
              f"block blobs: OJZ_Sec{n}_Blocks neither BINCLUDE'd nor aliased")
        check(n in dlen, f"block dicts: OJZ_SEC{n}_BLOCK_DICT_LEN missing")
        if s in alias:
            check(alias[s] in binc or alias[s] in alias,
                  f"block blobs: OJZ_Sec{n}_Blocks aliases undefined OJZ_Sec{alias[s]}_Blocks")
            continue
        if s in binc:
            bpath = os.path.join(GEN, binc[s])
            check(os.path.isfile(bpath), f"block blobs: {binc[s]} referenced but missing")
            if os.path.isfile(bpath) and n in dlen:
                sz = os.path.getsize(bpath)
                check(dlen[n] % BLOCK_RAW_SIZE == 0,
                      f"block dicts: sec{n} dict len {dlen[n]} not a multiple of {BLOCK_RAW_SIZE}")
                check(sz >= BLOCK_INDEX_BYTES + dlen[n],
                      f"block blobs: sec{n}_blocks.bin is {sz}B < index({BLOCK_INDEX_BYTES}) + dict({dlen[n]})")


def verify_bininclude_targets():
    """Every BINCLUDE / embed() in the committed generated heads resolves to a
    present file (catches a renamed/removed blob a hand-edit left dangling)."""
    for head in ("ojz_act_pool.emp", "sec_block_blobs.emp", "sec_local_maps.emp", "bg_anim.emp"):
        hp = os.path.join(GEN, head)
        if not os.path.isfile(hp):
            continue
        for tgt in re.findall(r'(?:BINCLUDE\s+|embed\()"([^"]+)"', open(hp).read()):
            tp = os.path.join(ROOT, tgt) if not os.path.isabs(tgt) else tgt
            check(os.path.isfile(tp), f"{head}: BINCLUDE/embed target missing: {tgt}")


def main():
    verify_act_pool()
    verify_block_blobs()
    verify_bininclude_targets()
    checks_run = "act-pool / block-blobs / bininclude-targets"
    if _fail:
        print(f"verify_level_bin: FAIL ({len(_fail)} issue(s)) [{checks_run}]", file=sys.stderr)
        for m in _fail:
            print(f"  - {m}", file=sys.stderr)
        return 1
    print(f"verify_level_bin: OK [{checks_run}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
