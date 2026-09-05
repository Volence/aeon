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
PROJECT_JSON = os.path.join(ROOT, "project.json")
STRIP_GEN_SRC = os.path.join(ROOT, "tools", "ojz_strip_gen.py")
NAMETABLE_TILE_MASK = 0x07FF   # bits 0-10 of a VDP nametable word
NAMETABLE_ATTR_MASK = 0xE000   # priority + palette line (flip bits are NOT here)

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


# Generated files that are legitimately unreferenced. Each needs a REASON, because
# the whole point of the orphan check is that "nothing references it" is normally a
# defect. Do not add a line here to silence a real orphan.
_ORPHAN_ALLOWLIST = {
    # The only embedder sits inside `if anims:` and the committed bg_anim.emp is the
    # else-branch stub, so this is referenced by a code path that is not currently
    # taken (tools lens sweep D10). Real input, not detritus — keep it.
    "bg_anim_banks.bin",
}


def verify_no_orphans():
    """Every committed generated artifact should be referenced by something.

    THE GAP THIS CLOSES. verify_level_bin checks embed -> file (does every embedded
    path exist?) and never file -> embed (does every file have an embedder?). So
    18 orphans totalling 240 KB — sec{0..8}_tiles.{bin,zx0}, whose writer had been
    removed from ojz_strip_gen.py — sat committed for 45 days with zero references
    anywhere in the tree, having been swept in as untracked build detritus by a
    commit that meant to track the real generated tree (tools lens sweep D10).

    That is the cleanest available proof that "review git status before committing"
    is not a gate. This is the gate.

    WARN, not fail: an orphan is a housekeeping defect, not a broken ROM, and a
    build that refuses to produce a working image over dead weight would get
    switched off. It is loud, in the output people read, and it names each file.
    """
    gen_root = os.path.join(ROOT, "games", "sonic4", "data", "generated")
    if not os.path.isdir(gen_root):
        return
    # Everything that could name a generated file.
    haystack = []
    for sub in ("engine", "games", "tools"):
        for dirpath, _d, filenames in os.walk(os.path.join(ROOT, sub)):
            # Do NOT skip generated/ — the generated manifests (.emp) are the very
            # things that embed the generated blobs, so excluding them reported 74
            # false orphans on the first run, act_pool_page*.bin among them.
            if os.sep + ".git" in dirpath:
                continue
            for fn in filenames:
                if fn.endswith((".emp", ".asm", ".toml", ".py", ".sh", ".json")):
                    try:
                        with open(os.path.join(dirpath, fn), "r",
                                  encoding="utf-8", errors="ignore") as fh:
                            haystack.append(fh.read())
                    except OSError:
                        pass
    blob = "\n".join(haystack)

    orphans = []
    for dirpath, _d, filenames in os.walk(gen_root):
        for fn in filenames:
            if fn in _ORPHAN_ALLOWLIST:
                continue
            stem = os.path.splitext(fn)[0]
            # A file is "referenced" if its NAME, its stem, or its DIGIT-STRIPPED
            # skeleton appears. The skeleton matters because tools build these names
            # with f-strings -- `f"sec{sec}_strips_a.bin"` -- so the literal
            # "sec0_strips_a.bin" appears nowhere. Without it this reported 19 false
            # orphans on its first run, which is the failure mode that makes a
            # warning get ignored.
            # The tail AFTER the leading index is what survives an f-string:
            # `f"sec{sec}_strips_a.bin"` contains "_strips_a.bin" but neither
            # "sec0_strips_a.bin" nor the digit-stripped "sec_strips_a.bin".
            tail = re.sub(r"^[A-Za-z]*\d+", "", fn)
            cands = [fn, stem]
            if tail and tail != fn and len(tail) > 4:
                cands.append(tail)
            if not any(c in blob for c in cands):
                orphans.append(os.path.relpath(os.path.join(dirpath, fn), ROOT))

    if orphans:
        print(f"verify_level_bin: WARNING — {len(orphans)} generated artifact(s) "
              f"referenced by NOTHING (no embed, no BINCLUDE, no tool). Either wire "
              f"them up, delete them, or add them to _ORPHAN_ALLOWLIST with a reason:",
              file=sys.stderr)
        for o in sorted(orphans):
            print(f"  - {o}", file=sys.stderr)


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


def _strip_gen_int(name):
    """Read a plain-integer constant out of tools/ojz_strip_gen.py's SOURCE.

    Derived from the generator rather than re-declared here: the strip layout is
    the generator's to define, and a second literal 776 in this file is exactly
    the pin that goes stale with nothing noticing. Parsed rather than imported
    because verify_level_bin is deliberately donor-free and dependency-free,
    while ojz_strip_gen pulls in collision_pipeline / vram_map / donor_provenance
    at import time. A constant that has moved or gone non-literal returns None
    and records a failure -- loud, never green.
    """
    if not os.path.isfile(STRIP_GEN_SRC):
        check(False, f"editor bake: {STRIP_GEN_SRC} missing -- cannot derive the "
                     f"strip layout, so the bake-fidelity check cannot run")
        return None
    m = re.search(rf"^{name}\s*=\s*(\d+)\b", open(STRIP_GEN_SRC).read(), re.M)
    if not m:
        check(False, f"editor bake: ojz_strip_gen.py no longer defines {name} as a "
                     f"plain integer -- the strip layout moved and this check is "
                     f"reading a shape that no longer exists; re-derive it")
        return None
    return int(m.group(1))


def _tile_pixels(blob, idx, hflip, vflip):
    """The 32 bytes of tile `idx` in `blob`, with the VDP flips applied.

    Out-of-range indices resolve to the zero tile, matching what the generator's
    collect_referenced_tiles substitutes -- so an out-of-range source reference
    is still CHECKED (against blank) rather than skipped.
    """
    base = idx * TILE_SIZE
    if base + TILE_SIZE > len(blob):
        return bytes(TILE_SIZE)
    rows = [blob[base + i * 4: base + i * 4 + 4] for i in range(8)]
    if hflip:
        rows = [bytes((((b & 0x0F) << 4) | (b >> 4)) for b in reversed(r))
                for r in rows]
    if vflip:
        rows = rows[::-1]
    return b"".join(rows)


def verify_editor_bake_fidelity():
    """The committed generated tree must carry the EDITOR's authored nametable,
    pixel for pixel, into the artifacts the ROM consumes. Donor-free.

    Three claims, checked per section over every one of its 65536 words:
      1. sec{N}_strips_source.bin's nametable equals section_{N}.tiles.bin word
         for word (the generator's column-major strip vs the editor's row-major
         grid).
      2. sec{N}_strips_a.bin preserves each source word's priority and
         palette-line bits. Only the tile index and the flip bits are the
         remapper's to rewrite; an attribute that moved is a palette bug that
         renders as a recoloured region.
      3. Resolving a strips_a word through sec{N}_local_map.bin into the act art
         pool pages yields the SAME 8x8 pixels as the source word resolves to in
         the editor tileset, flips applied on both sides.

    WHY IT EXISTS. The OJZ section-7 vertical-seam probe (2026-09-05) asked "is
    the FG loading wrong?" and nothing in the tree could answer it offline.
    verify_act_pool and verify_local_maps check that the generated tree is
    internally CONSISTENT -- sizes line up, indices are in range, the .zx0 pages
    round-trip. None of them compares it against what the editor authored, so a
    dedupe / spatial-order / paging regression that is merely self-consistent
    (wrong tile, right shape) passes every existing gate and is first seen as
    garbage on a screen. This is the check that distinguishes "the bake is
    wrong" from "the level data says that".
    """
    fails_before = len(_fail)
    strip_rows = _strip_gen_int("STRIP_TILE_HEIGHT")
    pad = _strip_gen_int("STRIP_COLLISION_PAD")
    if strip_rows is None or pad is None:
        return
    # ojz_strip_gen's own formula (its module docstring):
    #   WIDE_STRIP_SIZE = STRIP_TILE_HEIGHT*2 + 2*COLLISION_ROWS_PER_STRIP + PAD
    #   COLLISION_ROWS_PER_STRIP = STRIP_TILE_HEIGHT // 2
    stride = strip_rows * 2 + 2 * (strip_rows // 2) + pad
    grid = strip_rows            # editor grid is square, one strip per tile column

    if not os.path.isfile(PROJECT_JSON):
        check(False, "editor bake: project.json missing -- cannot locate the editor tree")
        return
    with open(PROJECT_JSON) as f:
        proj = json.load(f)
    zone = proj["zones"][0]
    act = zone["acts"][0]
    tileset_path = os.path.join(ROOT, zone["tileset"])
    data_path = os.path.join(ROOT, act["dataPath"])
    declared = act["gridWidth"] * act["gridHeight"]
    check(declared == NUM_SECTIONS,
          f"editor bake: project.json declares {declared} sections but this file "
          f"is written against {NUM_SECTIONS} -- update NUM_SECTIONS")

    if not os.path.isfile(tileset_path):
        check(False, f"editor bake: editor tileset {tileset_path} missing")
        return
    art = read(tileset_path)
    check(len(art) > 0 and len(art) % TILE_SIZE == 0,
          f"editor bake: editor tileset is {len(art)} bytes -- not a whole number "
          f"of {TILE_SIZE}-byte tiles (a 0-byte tileset bakes a blank level and "
          f"passes every other gate)")
    if not art:
        return

    pages = []
    idx = 0
    while os.path.isfile(os.path.join(GEN, f"act_pool_page{idx}.bin")):
        pages.append(read(os.path.join(GEN, f"act_pool_page{idx}.bin")))
        idx += 1
    check(bool(pages), "editor bake: no act_pool_page*.bin -- nothing to resolve "
                       "remapped tiles against")
    if not pages:
        return
    pool = b"".join(pages)

    sections_checked = 0
    words_checked = 0
    for n in range(min(declared, NUM_SECTIONS)):
        ed_path = os.path.join(data_path, f"section_{n}.tiles.bin")
        src_path = os.path.join(GEN, f"sec{n}_strips_source.bin")
        rem_path = os.path.join(GEN, f"sec{n}_strips_a.bin")
        map_path = os.path.join(GEN, f"sec{n}_local_map.bin")
        if not os.path.isfile(ed_path):
            continue         # generate() skips sections with no editor tiles
        missing = [p for p in (src_path, rem_path, map_path) if not os.path.isfile(p)]
        if missing:
            check(False, f"editor bake: sec{n} has editor tiles but is missing "
                         f"{', '.join(os.path.basename(p) for p in missing)}")
            continue

        ed = read(ed_path)
        if len(ed) != grid * grid * 2:
            check(False, f"editor bake: {os.path.basename(ed_path)} is {len(ed)} "
                         f"bytes, expected {grid * grid * 2} for a {grid}x{grid} grid")
            continue
        ed_words = struct.unpack(f">{grid * grid}H", ed)
        src = read(src_path)
        rem = read(rem_path)
        for label, blob, path in (("source", src, src_path), ("a", rem, rem_path)):
            check(len(blob) == grid * stride,
                  f"editor bake: sec{n}_strips_{label}.bin is {len(blob)} bytes, "
                  f"expected {grid} columns x {stride} (derived from "
                  f"ojz_strip_gen's STRIP_TILE_HEIGHT/STRIP_COLLISION_PAD)")
        if len(src) != grid * stride or len(rem) != grid * stride:
            continue
        lm_raw = read(map_path)
        local_map = struct.unpack(f">{len(lm_raw) // 2}H", lm_raw)

        nt_bad = attr_bad = art_bad = range_bad = 0
        first = None
        seen = set()
        for c in range(grid):
            off = c * stride
            col_src = struct.unpack(f">{grid}H", src[off: off + grid * 2])
            col_rem = struct.unpack(f">{grid}H", rem[off: off + grid * 2])
            ed_col = ed_words[c::grid]
            if col_src != ed_col:
                for r in range(grid):
                    if col_src[r] != ed_col[r]:
                        nt_bad += 1
                        if first is None:
                            first = (r, c, ed_col[r], col_src[r])
            for r in range(grid):
                pair = (col_src[r], col_rem[r])
                if pair in seen:
                    continue
                seen.add(pair)
                sw, rw = pair
                if (sw & NAMETABLE_ATTR_MASK) != (rw & NAMETABLE_ATTR_MASK):
                    attr_bad += 1
                    continue
                li = rw & NAMETABLE_TILE_MASK
                if li >= len(local_map):
                    range_bad += 1
                    continue
                g = local_map[li]
                if (g + 1) * TILE_SIZE > len(pool):
                    range_bad += 1
                    continue
                want = _tile_pixels(art, sw & NAMETABLE_TILE_MASK,
                                    (sw >> 11) & 1, (sw >> 12) & 1)
                got = _tile_pixels(pool, g, (rw >> 11) & 1, (rw >> 12) & 1)
                if want != got:
                    art_bad += 1
            words_checked += grid

        check(nt_bad == 0,
              f"editor bake: sec{n} strips_source disagrees with the editor "
              f"nametable in {nt_bad} word(s) -- the generated tree does NOT carry "
              f"what the editor authored (first: row {first[0]} col {first[1]}, "
              f"editor ${first[2]:04X} vs strips ${first[3]:04X})"
              if first else f"editor bake: sec{n} nametable mismatch")
        check(attr_bad == 0,
              f"editor bake: sec{n} strips_a changed the priority/palette bits on "
              f"{attr_bad} distinct word shape(s) -- the remapper may rewrite the "
              f"tile index and the flips, nothing else")
        check(range_bad == 0,
              f"editor bake: sec{n} has {range_bad} distinct word shape(s) whose "
              f"local index or resolved global slot falls outside the committed "
              f"local map / art pool")
        check(art_bad == 0,
              f"editor bake: sec{n} resolves {art_bad} distinct word shape(s) to "
              f"DIFFERENT pixels than the editor authored -- same layout, wrong "
              f"art (dedupe / spatial-order / paging drift)")
        sections_checked += 1

    check(sections_checked > 0,
          "editor bake: zero sections had editor tiles to check -- this gate "
          "measured nothing, which is not a pass")
    if sections_checked and len(_fail) == fails_before:
        print(f"verify_level_bin: editor bake fidelity OK "
              f"({sections_checked} section(s), {words_checked} nametable words)")


def main():
    verify_act_pool()
    verify_local_maps()
    verify_block_blobs()
    verify_bininclude_targets()
    verify_collision_is_interned()
    verify_editor_bake_fidelity()
    verify_no_orphans()
    checks_run = ("act-pool+content+sidecar / local-maps / block-blobs / "
                  "bininclude-targets / collision-interned / editor-bake / orphans")
    if _fail:
        print(f"verify_level_bin: FAIL ({len(_fail)} issue(s)) [{checks_run}]", file=sys.stderr)
        for m in _fail:
            print(f"  - {m}", file=sys.stderr)
        return 1
    print(f"verify_level_bin: OK [{checks_run}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
