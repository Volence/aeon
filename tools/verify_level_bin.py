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
import json
import os
import re
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
GEN = os.path.join(ROOT, "games", "sonic4", "data", "generated", "ojz", "act1")
SALVADOR = os.path.join(ROOT, "tools", "bin", "salvador")
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


def zx0_decode(payload):
    """Decode a bare ZX0 stream via salvador -d (the same tool that packed it).
    Returns the plaintext bytes, or None (with a recorded failure) if salvador
    is unavailable — a missing decoder must FAIL the gate, never skip it:
    silence is also what a checker that analyzed nothing produces."""
    if not os.access(SALVADOR, os.X_OK):
        check(False, f"act pool: salvador missing at {SALVADOR} — cannot "
                     "content-verify .zx0 pages (build.sh builds it; run make -C tools/salvador)")
        return None
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "in.zx0")
        dst = os.path.join(td, "out.bin")
        with open(src, "wb") as f:
            f.write(payload)
        r = subprocess.run([SALVADOR, "-d", src, dst],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode != 0 or not os.path.isfile(dst):
            return b""          # decode failure -> caller's compare fails loudly
        return read(dst)


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
        r'OJZ_Act_Pool_Page(\d+)\s*(?:\(align:\s*\d+\)\s*)?=\s*embed\("[^"]*/act_pool_page(\d+)\.(zx0|raw)"\)',
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
                # CONTENT check, not just the wrapper: decode the stream and
                # byte-compare against the .bin. Every full page is exactly 2048
                # bytes, so the size checks above have zero discriminating power
                # against a stale .zx0 from a previous bake — which would ship
                # wrong art through every other gate (this is THE drift gate for
                # a tree the build cannot re-derive).
                dec = zx0_decode(w[4:])
                if dec is not None:
                    check(dec == raw,
                          f"act pool: page{k}.zx0 payload decodes to different bytes than page{k}.bin (stale/drifted stream)")
        elif form == 1:   # raw-direct
            check(ext == "raw", f"act pool: page{k} form 1 (raw) but embeds .{ext}")
            praw = os.path.join(GEN, f"act_pool_page{k}.raw")
            if not os.path.isfile(praw):
                check(False, f"act pool: act_pool_page{k}.raw missing")
                continue
            # BYTE equality, not just size: full raw pages are all exactly 2048 B.
            check(read(praw) == raw,
                  f"act pool: page{k}.raw content != page{k}.bin (stale/drifted copy)")
        else:
            check(False, f"act pool: page{k} unknown form {form}")

    # Sidecar cross-check: the machine-readable manifest JSON is the generator's
    # own record of page geometry + the PINNED set. pm_flags bit0 is
    # residency-safety-critical (a pin lost = evictable act-common page; a
    # spurious pin = a permanently unreclaimable frame) and was previously
    # captured and DISCARDED here — nothing tied the .emp flags to the sidecar.
    sidecar = os.path.join(GEN, "ojz_act_pool_manifest.json")
    if not os.path.isfile(sidecar):
        check(False, "act pool: ojz_act_pool_manifest.json sidecar missing")
        return
    sc = json.load(open(sidecar))
    check(sc.get("page_bytes") == ART_POOL_PAGE_BYTES,
          f"act pool: sidecar page_bytes {sc.get('page_bytes')} != {ART_POOL_PAGE_BYTES}")
    check(sc.get("page_tiles") * TILE_SIZE == ART_POOL_PAGE_BYTES,
          f"act pool: sidecar page_tiles {sc.get('page_tiles')} * {TILE_SIZE} != page_bytes")
    sc_pages = {p["index"]: p for p in sc.get("pages", [])}
    check(sorted(sc_pages) == list(range(pages)),
          f"act pool: sidecar page indices {sorted(sc_pages)} != 0..{pages-1}")
    for e in entries:
        k, tiles, _form, flags = int(e[0]), int(e[1]), int(e[2]), int(e[3])
        p = sc_pages.get(k)
        if p is None:
            continue
        check(p["tiles"] == tiles,
              f"act pool: page{k} sidecar tiles {p['tiles']} != manifest tiles {tiles}")
        check(bool(flags & 1) == bool(p["pinned"]),
              f"act pool: page{k} pm_flags pinned bit {flags & 1} != sidecar pinned {p['pinned']}")


def verify_local_maps():
    """Per-section local->global map consistency (P2b): each committed
    secN_local_map.bin must be well-formed (u16 BE entries, count <= 2048), and
    every local index used by that section's DICT-region raw blocks must fall
    inside the map. Catches the partial-commit drift where a re-baked
    secN_blocks.bin is committed without its secN_local_map.bin (or vice versa)
    — previously only the files' EXISTENCE was checked, and a mismatch renders
    garbage global slots with every gate green. (S4LZ-streamed blocks are not
    decoded here; the dict region covers the section's most-referenced blocks.)"""
    dicts = os.path.join(GEN, "sec_block_dicts.emp")
    dlen = {}
    if os.path.isfile(dicts):
        dlen = {int(n): int(v) for n, v in
                re.findall(r"OJZ_SEC(\d+)_BLOCK_DICT_LEN\s*=\s*(\d+)", open(dicts).read())}
    # Pool-tile bound for map VALUES (panel V-1b/B-3): every local->global entry
    # must name a real pool tile — the engine's PatchWord indexes Page_Table by
    # global>>6 with only a DEBUG assert, so out-of-pool values in a committed
    # map must die HERE. Bound = sum of manifest pm_tiles (the last page may be
    # partial, so pages*64 would over-admit).
    pool_tiles = 0
    pool = os.path.join(GEN, "ojz_act_pool.emp")
    if os.path.isfile(pool):
        pool_tiles = sum(int(t) for t in
                         re.findall(r"pm_tiles:\s*(\d+)", open(pool).read()))
    for n in range(NUM_SECTIONS):
        mpath = os.path.join(GEN, f"sec{n}_local_map.bin")
        bpath = os.path.join(GEN, f"sec{n}_blocks.bin")
        if not os.path.isfile(mpath):
            # sections may alias another's blocks; a missing map is only fatal
            # when the section has its own block blob
            check(not os.path.isfile(bpath),
                  f"local maps: sec{n}_blocks.bin present but sec{n}_local_map.bin missing")
            continue
        m = read(mpath)
        check(len(m) % 2 == 0, f"local maps: sec{n}_local_map.bin has odd size {len(m)}")
        count = len(m) // 2
        check(0 < count <= 2048,
              f"local maps: sec{n}_local_map.bin entry count {count} not in 1..2048")
        # Blank-first invariant (F-3 merge-translation): map[0] must be global 0
        # — the engine's shared zero staged block ($0000 words = local 0) reads
        # as blank through ANY section's map only because of this.
        check(struct.unpack(">H", m[0:2])[0] == 0,
              f"local maps: sec{n}_local_map.bin map[0] != 0 (blank-first invariant broken)")
        if pool_tiles:
            vals = struct.unpack(f">{count}H", m)
            bad = [v for v in vals if v >= pool_tiles]
            check(not bad,
                  f"local maps: sec{n}_local_map.bin has {len(bad)} entries >= pool tiles "
                  f"({pool_tiles}) — out-of-pool globals (max {max(bad) if bad else 0})")
        if not os.path.isfile(bpath) or n not in dlen:
            continue
        blob = read(bpath)
        dict_end = BLOCK_INDEX_BYTES + dlen[n]
        max_local = -1
        for off in range(BLOCK_INDEX_BYTES, min(dict_end, len(blob)), BLOCK_RAW_SIZE):
            block = blob[off:off + BLOCK_RAW_SIZE]
            # first 512 bytes of a raw block = 256 BE nametable words; local
            # index = low 11 bits
            for i in range(0, min(512, len(block)), 2):
                idx = ((block[i] << 8) | block[i + 1]) & 0x07FF
                if idx > max_local:
                    max_local = idx
        check(max_local < count,
              f"local maps: sec{n} dict blocks reference local index {max_local} "
              f">= map entry count {count} (blocks/map drift — partial commit?)")


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


def verify_collision_is_interned():
    """The ROM-consumed collision tables must NOT be the raw base S&K bank.

    THE GAP THIS CLOSES. The tools lens sweep (2026-08-13, D1) found that
    tools/regenerate-level.sh ran import_sk_collision.py FIRST -- which
    unconditionally overwrites data/collision/{heightmaps,heightmaps_rot,angles,
    solidity}.bin with the base S&K bank -- and only THEN reached a step that
    aborts on a missing donor. `set -euo pipefail` with no trap, so it exited
    having already clobbered them. The strips keep INTERNED indices, so every
    solid surface then resolves to a different height profile, angle and solidity
    class: the player falls through terrain, or is stopped by nothing.

    Nobody noticed because this file -- the level-tree drift gate -- did not
    mention collision at all. The clobber was invisible until someone played it.

    regenerate-level.sh now preflights, so the KNOWN destructive path is closed.
    This is the detector for every other path to the same state: a hand-run of
    import_sk_collision.py, a bad merge, a partial revert, a restored backup.

    The property is deliberately "differs from base/" rather than a checksum pin:
    these tables legitimately change whenever the level is re-baked, so a pin
    would demand an update on every bake and would be silenced rather than
    obeyed. "Not the raw donor bank" is drift-tolerant and is exactly the state
    the clobber produces.
    """
    live_dir = os.path.join(ROOT, "games", "sonic4", "data", "collision")
    base_dir = os.path.join(live_dir, "base")
    if not os.path.isdir(base_dir):
        return  # no base bank vendored here; nothing to compare against
    for name in ("heightmaps.bin", "heightmaps_rot.bin", "angles.bin", "solidity.bin"):
        live = os.path.join(live_dir, name)
        base = os.path.join(base_dir, name)
        if not (os.path.isfile(live) and os.path.isfile(base)):
            continue
        check(
            read(live) != read(base),
            f"collision/{name} is byte-identical to collision/base/{name} — the "
            f"ROM-consumed table is the RAW S&K BANK, not the interned one. This is "
            f"the state tools/regenerate-level.sh used to leave behind when it "
            f"aborted after import_sk_collision.py (lens D1): the strips still carry "
            f"interned indices, so every solid surface resolves to the wrong height, "
            f"angle and solidity class. Restore these four files from git "
            f"(`git checkout -- games/sonic4/data/collision/`) rather than re-baking.",
        )


def main():
    verify_act_pool()
    verify_local_maps()
    verify_block_blobs()
    verify_bininclude_targets()
    verify_collision_is_interned()
    checks_run = ("act-pool+content+sidecar / local-maps / block-blobs / "
                  "bininclude-targets / collision-interned")
    if _fail:
        print(f"verify_level_bin: FAIL ({len(_fail)} issue(s)) [{checks_run}]", file=sys.stderr)
        for m in _fail:
            print(f"  - {m}", file=sys.stderr)
        return 1
    print(f"verify_level_bin: OK [{checks_run}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
