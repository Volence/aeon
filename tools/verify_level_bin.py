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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import act_grid  # noqa: E402  stdlib-only: the ONE reader of the act's section count

ROOT =os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
GEN = os.path.join(ROOT, "games", "sonic4", "data", "generated", "ojz", "act1")
SALVADOR = os.path.join(ROOT, "tools", "bin", "salvador")
CONSTANTS_EMP = os.path.join(ROOT, "engine", "system", "constants.emp")
TILE_SIZE = 32


def load_page_geometry(path=CONSTANTS_EMP):
    """(ART_POOL_PAGE_TILES, ART_POOL_PAGE_BYTES), read from the ENGINE, not restated.

    This file used to type `ART_POOL_PAGE_BYTES = 2048` (PAGE-SIZE-CONSTANT-ONLY,
    2026-09-17): the page size is a parameter of the owner's open card FG-CACHE-10-HOW
    (64 -> 32 tiles), and the generator, the page order and the budget check already
    read it from constants.emp through fg_working_set.ConstantSource (stdlib-only at
    import, so this gate stays donor-free). Same reader here, so a page-size change is
    a constant change. An unreadable or incoherent constant raises: loud, never green.
    """
    from fg_working_set import ConstantSource
    src = ConstantSource()
    src.load_file(path)
    tiles = src.get("ART_POOL_PAGE_TILES")
    page_bytes = src.get("ART_POOL_PAGE_BYTES")
    if tiles * TILE_SIZE != page_bytes:
        raise ValueError(f"{path}: ART_POOL_PAGE_BYTES {page_bytes} != ART_POOL_PAGE_TILES "
                         f"{tiles} * TILE_SIZE {TILE_SIZE}")
    return tiles, page_bytes


ART_POOL_PAGE_TILES, ART_POOL_PAGE_BYTES = load_page_geometry()
BLOCK_INDEX_BYTES = 1024   # 256 * 4-byte block index table (ojz_block_gen)
BLOCK_RAW_SIZE = 768       # one raw 16x16 block (dict region is a multiple)
PROJECT_JSON = os.path.join(ROOT, "project.json")
_DEFAULT_PROJECT_JSON = PROJECT_JSON
# The base collision shape bank the editor cell words index; None = the S&K
# vocabulary under collision/base/. Set by --bank. See verify_editor_collision_fidelity.
BASE_BANK_DIR = None
STRIP_GEN_SRC = os.path.join(ROOT, "tools", "ojz_strip_gen.py")
NAMETABLE_TILE_MASK = 0x07FF   # bits 0-10 of a VDP nametable word
NAMETABLE_ATTR_MASK = 0xE000   # priority + palette line (flip bits are NOT here)
# The ROM-consumed collision tables and the S&K base bank the bake resolves against.
COLLISION_DIR = os.path.join(ROOT, "games", "sonic4", "data", "collision")
PROFILE_LEN = 16               # one height byte per 16-px column of a collision cell

# The stress bake's clone declaration (ojz_strip_gen.STRESS_CLONES_SIDECAR, mirrored by
# name; the generator is not importable here, this gate is donor-free). Read ONLY under
# --stress; a canonical run refuses a tree that carries it. See _stress_clone_scratch.
STRESS_CLONES_SIDECAR = "stress_clones.json"
STRESS_MODE = False            # set by main() from --stress (regenerate-level.sh / build.sh
                               # pass it exactly when STRESS_UNIQUIFY / STRESS_ART is set)

_fail = []


def check(cond, msg):
    if not cond:
        _fail.append(msg)


def read(path):
    with open(path, "rb") as f:
        return f.read()


def _section_count():
    """The act's section count, from tools/act_grid.py (project.json, required to
    agree with the engine's act descriptor), or None with a recorded failure.

    This file used to carry its own literal `NUM_SECTIONS = 9` (2026-09-12 gap lens
    sweep F2): a count the gate checks itself against cannot notice the section set
    shrinking under it.
    """
    try:
        return act_grid.section_count(PROJECT_JSON)
    except (OSError, ValueError, KeyError) as exc:
        check(False, f"act grid: cannot derive the section count -- {exc}")
        return None


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
              f"act pool: page{k} manifest tiles {tiles} (*{TILE_SIZE}={tiles*TILE_SIZE}) != .bin size {len(raw)}")
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
                # byte-compare against the .bin. Every full page is exactly
                # ART_POOL_PAGE_BYTES, so the size checks above have zero discriminating power
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
            # BYTE equality, not just size: full raw pages are all exactly ART_POOL_PAGE_BYTES.
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


def verify_local_map_table(n_sec):
    """OJZ_Sec_LocalMaps must hold exactly one entry per grid section, in flat-id order.

    THE GAP THIS CLOSES (2026-09-12 gap lens sweep F2). With section_8.tiles.bin
    missing, the strip baker emitted `OJZ_Sec_LocalMaps: [*u8; 8]` for a 3x3 act and
    this gate passed it: it checked each per-section map FILE, and the stale
    sec8_local_map.bin was still on disk. The engine indexes the table by flat id over
    the act's grid, so entry 8 was the first long of whatever the linker placed next.
    """
    path = os.path.join(GEN, "sec_local_maps.emp")
    if not os.path.isfile(path):
        check(False, "local maps: sec_local_maps.emp missing")
        return
    txt = open(path).read()
    m = re.search(r"OJZ_Sec_LocalMaps:\s*\[\*u8;\s*(\d+)\]\s*=\s*\[([^\]]*)\]", txt)
    if not m:
        check(False, "local maps: no `OJZ_Sec_LocalMaps: [*u8; N] = [...]` table in "
                     "sec_local_maps.emp -- the emitter's shape moved; re-derive this check")
        return
    length = int(m.group(1))
    ptrs = [int(i) for i in re.findall(r'extern\("OJZ_Sec(\d+)_LocalMap"\)', m.group(2))]
    check(length == n_sec and ptrs == list(range(n_sec)),
          f"local maps: OJZ_Sec_LocalMaps is [*u8; {length}] pointing at sections {ptrs}, "
          f"but the act grid has {n_sec} sections. The engine indexes this table by flat "
          f"id over the grid, so a short table hands it the NEXT table's first long as a "
          f"section's local map")
    defined = {int(i) for i in
               re.findall(r"OJZ_Sec(\d+)_LocalMap\s*=\s*(?:embed|extern)\(", txt)}
    undefined = [i for i in range(n_sec) if i not in defined]
    check(not undefined,
          f"local maps: sec_local_maps.emp defines no OJZ_Sec{{N}}_LocalMap for sections "
          f"{undefined}")


def verify_section_set():
    """No per-section artifact for a section OUTSIDE the act grid.

    Why a failure and not a deletion (2026-09-12 gap lens sweep F2). After that fix no
    baker reads a section outside the grid, so a leftover secN_* is inert -- but the
    only way to get one is a grid that SHRANK, and a shrink is exactly when a person
    should look: a mistyped grid would otherwise have the bakers quietly delete the
    sections it dropped. So the bakers never delete committed files by glob, and this
    names what is left over. verify_no_orphans cannot see these: it matches a file's
    name with its leading index stripped, and "_strips_a.bin" is referenced for every
    section.
    """
    n_sec = _section_count()
    if n_sec is None or not os.path.isdir(GEN):
        return
    extra = sorted(fn for fn in os.listdir(GEN)
                   if (m := re.match(r"sec(\d+)_", fn)) and int(m.group(1)) >= n_sec)
    check(not extra,
          f"section set: {len(extra)} per-section artifact(s) for sections outside the "
          f"{n_sec}-section act grid: {', '.join(extra)}. Nothing reads them; they are a "
          f"larger grid's leftovers, or project.json's grid shrank by mistake. If the "
          f"shrink was intended, delete them (the bakers deliberately never delete "
          f"committed files).")


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
    # global>>PAGE_FRAME_TILE_SHIFT with only a DEBUG assert, so out-of-pool values in a committed
    # map must die HERE. Bound PER PAGE: global g lives in page g // page_tiles at
    # index g % page_tiles, which must be under that page's pm_tiles. Since
    # STITCHED-ACT-PAGE-ORDER (2026-09-17) a page need not be full (per-zone pages
    # end a zone's run short, and global slots keep the gap, because the engine
    # finds the page as global>>shift), so the old bound "g < sum of pm_tiles" would
    # refuse a legal gapped slot and admit a slot in a short page's gap. For
    # contiguous full pages the two bounds are the same set.
    pool_tiles = 0
    page_tiles_list = []
    page_tiles = ART_POOL_PAGE_TILES
    pool = os.path.join(GEN, "ojz_act_pool.emp")
    if os.path.isfile(pool):
        page_tiles_list = [int(t) for t in
                           re.findall(r"pm_tiles:\s*(\d+)", open(pool).read())]
        pool_tiles = sum(page_tiles_list)
    n_sec = _section_count()
    if n_sec is None:
        return
    verify_local_map_table(n_sec)
    for n in range(n_sec):
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
            bad = [v for v in vals
                   if v // page_tiles >= len(page_tiles_list)
                   or v % page_tiles >= page_tiles_list[v // page_tiles]]
            check(not bad,
                  f"local maps: sec{n}_local_map.bin has {len(bad)} entries outside the pool's "
                  f"pages ({len(page_tiles_list)} pages, {pool_tiles} tiles, {page_tiles} slots "
                  f"per page) — out-of-pool globals (max {max(bad) if bad else 0})")
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


def _nt_form_flag():
    """OJZ_ACT_NT_PHYSICAL as the generated sec_local_maps.emp declares it, or None."""
    path = os.path.join(GEN, "sec_local_maps.emp")
    if not os.path.isfile(path):
        return None
    m = re.search(r"^pub const OJZ_ACT_NT_PHYSICAL\s*=\s*(\d+)\s*$", open(path).read(), re.M)
    return int(m.group(1)) if m else None


def verify_nt_form():
    """The block nametable word FORM (resident plain copy, 2026-09-26).

    The engine copies a PHYSICAL-form act's words verbatim (PAGECACHE_DIRECT_PLAIN) with
    no map read and no per-word check, so everything that makes that copy exact is held
    HERE, on the committed tree, where it is cheap. Three facts, each derived from source
    rather than restated:

      1. The form is the one the bake rule gives: PHYSICAL iff the pool's page count
         (ojz_act_pool.emp's pm_tiles rows) fits PAGE_FRAMES (engine/system/constants.emp).
         A flag the tree carries against that rule is a hand edit or a partial commit.
      2. Under PHYSICAL, every section map is the POOL-SLOT IDENTITY (map[i] = i for a real
         slot, 0 for a short page's gap, length = last slot + 1). That is what keeps every
         TRANSLATING loop exact on physical words, i.e. what makes the form safe on a shape
         that turns out not to be resident at runtime (STRESS_EVICT).
      3. Under PHYSICAL, every strips_a word (the blocks carry exactly these words;
         verify_block_decode ties the two) either is $0000 or names a real pool slot. A
         blank word with attribute bits would be copied with them, where every translating
         loop stores $0000 — measured 39,443 such words in OJZ's local-form tree.
    """
    flag = _nt_form_flag()
    if flag is None:
        check(False, "word form: sec_local_maps.emp declares no `pub const OJZ_ACT_NT_PHYSICAL = 0|1` "
                     "-- the emitter's shape moved or the tree predates the resident plain copy")
        return
    check(flag in (0, 1), f"word form: OJZ_ACT_NT_PHYSICAL = {flag}, not 0 or 1")
    pool = os.path.join(GEN, "ojz_act_pool.emp")
    if not os.path.isfile(pool):
        check(False, "word form: ojz_act_pool.emp missing -- cannot derive the expected form")
        return
    page_tiles_list = [int(t) for t in re.findall(r"pm_tiles:\s*(\d+)", open(pool).read())]
    from fg_working_set import ConstantSource
    src = ConstantSource()
    src.load_file(CONSTANTS_EMP)
    page_frames = src.get("PAGE_FRAMES")
    expected = 1 if 0 < len(page_tiles_list) <= page_frames else 0
    check(flag == expected,
          f"word form: OJZ_ACT_NT_PHYSICAL = {flag}, but the pool has {len(page_tiles_list)} "
          f"pages against PAGE_FRAMES = {page_frames}, so the bake rule gives {expected}. "
          f"Re-bake (tools/regenerate-level.sh); never hand-edit the flag: a PHYSICAL flag on "
          f"LOCAL words puts section-local indices on screen as tile numbers")
    if flag != 1:
        return
    slots = {p * ART_POOL_PAGE_TILES + i
             for p, n in enumerate(page_tiles_list) for i in range(n)}
    last = max(slots)
    want = [i if i in slots else 0 for i in range(last + 1)]
    n_sec = _section_count()
    if n_sec is None:
        return
    for n in range(n_sec):
        mpath = os.path.join(GEN, f"sec{n}_local_map.bin")
        if not os.path.isfile(mpath):
            check(False, f"word form: sec{n}_local_map.bin missing")
            continue
        m = read(mpath)
        got = list(struct.unpack(f">{len(m) // 2}H", m))
        bad = [i for i in range(max(len(got), len(want)))
               if i >= len(got) or i >= len(want) or got[i] != want[i]]
        check(not bad,
              f"word form: PHYSICAL, but sec{n}_local_map.bin is not the pool-slot identity "
              f"({len(got)} entries against {len(want)}; first differing index "
              f"{bad[0] if bad else '-'}). Every translating loop then disagrees with the "
              f"plain copy on those words")
        spath = os.path.join(GEN, f"sec{n}_strips_a.bin")
        if not os.path.isfile(spath):
            check(False, f"word form: sec{n}_strips_a.bin missing")
            continue
        strip_rows = _strip_gen_int("STRIP_TILE_HEIGHT")
        pad = _strip_gen_int("STRIP_COLLISION_PAD")
        if strip_rows is None or pad is None:
            return
        stride = strip_rows * 2 + 2 * (strip_rows // 2) + pad
        blob = read(spath)
        blank_attr = off_pool = 0
        first = None
        for c in range(len(blob) // stride):
            col = struct.unpack(f">{strip_rows}H", blob[c * stride: c * stride + strip_rows * 2])
            for r, w in enumerate(col):
                idx = w & NAMETABLE_TILE_MASK
                if idx == 0 and w != 0:
                    blank_attr += 1
                elif idx != 0 and idx not in slots:
                    off_pool += 1
                else:
                    continue
                if first is None:
                    first = (c, r, w)
        check(blank_attr == 0 and off_pool == 0,
              f"word form: PHYSICAL, but sec{n}_strips_a.bin has {blank_attr} blank word(s) "
              f"carrying attribute bits and {off_pool} word(s) naming no pool slot (first: "
              f"col {first[0]} row {first[1]} ${first[2]:04X}). The plain copy stores these "
              f"verbatim; every translating loop would not"
              if first else "word form: strips mismatch")


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
    n_sec = _section_count()
    if n_sec is None:
        return
    for n in range(n_sec):
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


def verify_block_decode():
    """Every block of every section's ROM-consumed block blob must DECODE to the block
    its strips define.

    THE GAP THIS CLOSES (2026-09-12 gap lens sweep F6). Nothing in the ROM embeds
    sec{N}_strips_a.bin; the ROM embeds sec{N}_blocks.bin, and verify_local_maps read
    only its raw dictionary region. The seat copied sec5_blocks.bin over sec0_blocks.bin
    (both with a 768-byte dictionary): this gate said OK while 67 of section 0's 256
    blocks decoded to the wrong content. Every content check above certifies the strips;
    this is the link from the strips to the bytes the engine actually decompresses.

    A block, as ojz_block_gen.extract_block defines it: 16x16 nametable words row-major,
    then collision plane A (16 columns x 8 rows, row-major), then plane B -- 768 bytes.
    The blob's index entry is 0 for an all-zero block, bit 31 set for a raw block inside
    the dictionary region, else the offset of an S4LZ stream decoded against that region.
    Decoded with tools/s4lz.py, the format's reference decoder (the engine's agreement
    with it is compression_selftest's question, not this file's). A section whose blob
    is content-deduplicated is decoded through the blob the ROM gives it.
    """
    import s4lz
    n_sec = _section_count()
    strip_rows = _strip_gen_int("STRIP_TILE_HEIGHT")
    pad = _strip_gen_int("STRIP_COLLISION_PAD")
    if n_sec is None or strip_rows is None or pad is None:
        return
    blobs_emp = os.path.join(GEN, "sec_block_blobs.emp")
    dicts_emp = os.path.join(GEN, "sec_block_dicts.emp")
    if not (os.path.isfile(blobs_emp) and os.path.isfile(dicts_emp)):
        check(False, "block decode: sec_block_blobs.emp / sec_block_dicts.emp missing")
        return
    btxt = open(blobs_emp).read()
    embed = dict(re.findall(r'OJZ_Sec(\d+)_Blocks\s*=\s*embed\("[^"]*/(sec\d+_blocks\.bin)"\)', btxt))
    alias = dict(re.findall(r'OJZ_Sec(\d+)_Blocks\s*=\s*extern\("OJZ_Sec(\d+)_Blocks"\)', btxt))
    dlen = {int(k): int(v) for k, v in re.findall(
        r"OJZ_SEC(\d+)_BLOCK_DICT_LEN\s*=\s*(\d+)", open(dicts_emp).read())}

    coll_rows = strip_rows // 2
    stride = strip_rows * 2 + 2 * coll_rows + pad
    off_a, off_b = strip_rows * 2, strip_rows * 2 + coll_rows
    bsz = 16                                   # a block is 16x16 tiles
    blocks_per_axis = strip_rows // bsz
    brows = bsz // 2                           # 16-px collision rows per block
    raw_size = bsz * bsz * 2 + 2 * bsz * brows
    index_bytes = blocks_per_axis * blocks_per_axis * 4

    blocks_checked = 0
    for n in range(n_sec):
        owner, seen = str(n), set()
        while owner in alias and owner not in seen:   # the blob the ROM hands section n
            seen.add(owner)
            owner = alias[owner]
        rem_path = os.path.join(GEN, f"sec{n}_strips_a.bin")
        if owner not in embed or n not in dlen or not os.path.isfile(rem_path):
            check(False, f"block decode: sec{n} has no resolvable blob, dict length or "
                         f"strips -- cannot decode what the ROM carries for it")
            continue
        blob_path = os.path.join(GEN, embed[owner])
        if not os.path.isfile(blob_path):
            check(False, f"block decode: {embed[owner]} (the blob sec{n} uses) is missing")
            continue
        blob = read(blob_path)
        rem = read(rem_path)
        if len(rem) != strip_rows * stride or len(blob) < index_bytes + dlen[n]:
            check(False, f"block decode: sec{n} strips {len(rem)} B / blob {len(blob)} B "
                         f"are the wrong shape to decode")
            continue
        cols = [rem[c * stride:(c + 1) * stride] for c in range(strip_rows)]
        dictionary = blob[index_bytes:index_bytes + dlen[n]]
        bad = []
        for by in range(blocks_per_axis):
            for bx in range(blocks_per_axis):
                cs = cols[bx * bsz:(bx + 1) * bsz]
                t0 = by * bsz * 2
                want = (b"".join(col[t0 + 2 * r:t0 + 2 * r + 2] for r in range(bsz) for col in cs)
                        + bytes(col[off_a + by * brows + r] for r in range(brows) for col in cs)
                        + bytes(col[off_b + by * brows + r] for r in range(brows) for col in cs))
                i = by * blocks_per_axis + bx
                entry = struct.unpack_from(">I", blob, i * 4)[0]
                if entry == 0:
                    got = bytes(raw_size)
                elif entry & 0x80000000:
                    off = entry & 0x7FFFFFFF
                    ok_range = index_bytes <= off and off + raw_size <= index_bytes + dlen[n]
                    got = blob[off:off + raw_size] if ok_range else None
                else:
                    try:
                        got = s4lz.decompress(blob[entry:], dictionary=dictionary)
                    except Exception:           # a malformed stream is a wrong block
                        got = None
                if got != want:
                    bad.append(i)
                blocks_checked += 1
        check(not bad,
              f"block decode: sec{n}: {len(bad)} of {blocks_per_axis ** 2} blocks in "
              f"{embed[owner]} do NOT decode to the block its strips define (first: block "
              f"{bad[0] if bad else '-'}) -- the ROM would stream different level data "
              f"than every other check certified")
    check(blocks_checked > 0, "block decode: zero blocks decoded -- measured nothing")


DESCRIPTOR = os.path.join(ROOT, "games", "sonic4", "data", "levels", "ojz", "act1",
                          "act_descriptor.emp")


def verify_descriptor_wiring():
    """Row N of the act descriptor streams section N's blob (GATE-PREDICATE-VS-PROMISE,
    2026-09-26).

    `verify_block_decode` certifies that `secN_blocks.bin` decodes to `secN_strips`, which is
    "the link from the strips to the bytes the engine actually decompresses" only if the
    section-N row HANDS the engine `OJZ_SecN_Blocks`. That binding is hand-written in the
    descriptor and nothing read it. Measured: row 1 rewired to `OJZ_Sec5_Blocks` (with its
    dict and dict_len) and every lane here stayed green, while the ROM would stream section
    5's blocks through section 1's local map.

    Read from comment-stripped source: the Nth `ojz_sec(...)` row names `OJZ_SecN_Blocks` as
    `blocks:`, `extern("OJZ_SecN_Blocks")` in `dict:`, and `OJZ_SECN_BLOCK_DICT_LEN` as
    `dict_len:`, and there is one row per section of the act grid."""
    try:
        src = open(DESCRIPTOR, encoding="utf-8").read()
    except OSError as exc:
        check(False, f"descriptor wiring: cannot read {os.path.relpath(DESCRIPTOR, ROOT)} -- {exc}")
        return
    code = re.sub(r"//[^\n]*", "", src)
    # Call sites only: `comptime fn ojz_sec(blocks: Label, ...)` is the declaration.
    starts = [m.start() for m in re.finditer(r"(?<!fn )(?<![\w])ojz_sec\(\s*blocks:", code)]
    rel = os.path.relpath(DESCRIPTOR, ROOT)
    # The row COUNT is compared only for the shipped project: a clip bake (--project)
    # regenerates the act grid while these hand-written rows stay as they are, and what
    # the engine does with that difference is the clip lanes' question, not this one's.
    # The per-row identity below holds in both.
    n_sec = _section_count() if PROJECT_JSON == _DEFAULT_PROJECT_JSON else None
    if n_sec is not None:
        check(len(starts) == n_sec,
              f"descriptor wiring: {rel} carries {len(starts)} `ojz_sec(blocks: ...)` rows, "
              f"the act grid declares {n_sec} sections")
    for k, s in enumerate(starts):
        row = code[s:starts[k + 1] if k + 1 < len(starts) else len(code)]
        blocks = re.match(r"ojz_sec\(\s*blocks:\s*(\w+)", row).group(1)
        dict_m = re.search(r'\bdict:\s*extern\("(\w+)"\)', row)
        len_m = re.search(r"\bdict_len:\s*(\w+)", row)
        want = (f"OJZ_Sec{k}_Blocks", f"OJZ_Sec{k}_Blocks", f"OJZ_SEC{k}_BLOCK_DICT_LEN")
        got = (blocks, dict_m.group(1) if dict_m else None, len_m.group(1) if len_m else None)
        check(got == want,
              f"descriptor wiring: {rel} row {k} names blocks={got[0]} dict={got[1]} "
              f"dict_len={got[2]}; section {k} must stream {want[0]} (dict {want[1]}, "
              f"dict_len {want[2]}). Anything else streams another section's blocks through "
              f"this section's local map, and every decode lane above still passes")


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
    """The 32 bytes of tile `idx` in `blob`, with the VDP flips applied, or None when
    the blob does not reach that tile.

    None, NOT the zero tile (2026-09-12 gap lens sweep F3). This used to return
    bytes(TILE_SIZE) "matching what the generator's collect_referenced_tiles
    substitutes", which made the fidelity proof reproduce the generator's fallback:
    a tileset cut to 700 tiles baked 12,164 words blank, and this check compared the
    blank it expected against the blank the bake held, and passed. The 09-06 tools
    packet's T1-2 shape. A tile that does not exist is a failure the caller counts.
    """
    base = idx * TILE_SIZE
    if base + TILE_SIZE > len(blob):
        return None
    rows = [blob[base + i * 4: base + i * 4 + 4] for i in range(8)]
    if hflip:
        rows = [bytes((((b & 0x0F) << 4) | (b >> 4)) for b in reversed(r))
                for r in rows]
    if vflip:
        rows = rows[::-1]
    return b"".join(rows)


def _stress_clone_scratch(pool, stress=None, gen=None):
    """None on a canonical run; on a --stress run, {clone_slot: (byte_offset, xor)} for
    every clone whose declaration checks out against the pool bytes.

    WHY (STRESS-UNIQUIFY-REBAKE, 2026-09-17). The STRESS_ART fixture
    (ojz_strip_gen --stress-uniquify, P2c Task 11) re-points a spread of nametable words
    at CLONES of their own tile, each with one byte XORed so the clone is a distinct
    tile the page cache has to stream. That is a deliberate one-byte pixel difference
    from what the editor authored, so verify_editor_bake_fidelity (8706d8f2, 2026-09-05)
    refused every stress re-bake: MEASURED 1988 mismatched word shapes, 1988 distinct
    clone slots (612..2599), every one differing from the editor in exactly 1 byte, and
    zero mismatches on a real pool slot.

    THE RULE, which is not an exemption. The generator declares each clone as
    [slot, parent_slot, byte_offset, xor]. Here: the declaration must be complete
    (exactly the slots past the real pool, each once), each parent a real non-blank
    pool tile, and the clone's pool bytes must equal its parent's with that one byte
    XORed. The fidelity comparison then UNDOES the declared byte on the clone and still
    demands the editor's pixels. So a wrong tile anywhere is still refused: in a real
    slot nothing is undone; in a clone slot the undone tile is not the editor's tile
    (and fails the parent check). A clone slot whose raw bytes already match the editor
    also fails, since undoing a nonzero XOR then breaks it. The most a declaration can
    account for is one XOR byte per clone, and only on a tile that otherwise matches.

    TWO KEYS. Honoured only with --stress AND the sidecar. --stress without it is a
    failure (the stress bake did not declare its clones); the sidecar on a canonical
    run is a failure too (a stress tree is being verified as a real one, or a stress
    re-bake's leftover is in the tree), and it is not read.
    """
    stress = STRESS_MODE if stress is None else stress
    path = os.path.join(GEN if gen is None else gen, STRESS_CLONES_SIDECAR)
    present = os.path.isfile(path)
    if not stress:
        check(not present,
              f"editor bake: {os.path.relpath(path, ROOT)} is present on a CANONICAL verify "
              f"-- that is the STRESS_ART fixture's clone declaration, so this tree is a "
              f"stress bake (or a stress re-bake's leftover). Restore the committed tree "
              f"from git, or verify it as a stress bake with --stress")
        return None
    if not present:
        check(False, f"editor bake: --stress but no {STRESS_CLONES_SIDECAR} in "
                     f"{os.path.relpath(GEN if gen is None else gen, ROOT)} -- the stress "
                     f"bake did not declare its clones, so nothing may be undone and every "
                     f"clone is held to the editor's pixels as-is")
        return {}
    try:
        with open(path) as f:
            decl = json.load(f)
        version = decl["version"]
        base = int(decl["base_pool_tiles"])
        declared_pool = int(decl["pool_tiles"])
        clones = [tuple(int(x) for x in c) for c in decl["clones"]]
    except (OSError, ValueError, KeyError, TypeError) as e:
        check(False, f"editor bake: {STRESS_CLONES_SIDECAR} is unreadable ({e!r})")
        return {}
    pool_tiles = len(pool) // TILE_SIZE
    shape_ok = (version == 1 and 0 < base < declared_pool == pool_tiles
                and all(len(c) == 4 for c in clones)
                and [c[0] for c in clones] == list(range(base, declared_pool)))
    check(shape_ok,
          f"editor bake: {STRESS_CLONES_SIDECAR} does not declare exactly the clone slots "
          f"past the real pool (version {version}, base_pool_tiles {base}, pool_tiles "
          f"{declared_pool} vs {pool_tiles} in the pages, {len(clones)} clone rows) -- "
          f"no clone is honoured")
    if not shape_ok:
        return {}
    scratch = {}
    bad = []
    for slot, parent, off, xor in clones:
        if not (0 < parent < base and 0 <= off < TILE_SIZE and 0 < xor <= 0xFF):
            bad.append((slot, parent, off, xor))
            continue
        undone = bytearray(pool[slot * TILE_SIZE:(slot + 1) * TILE_SIZE])
        undone[off] ^= xor
        if bytes(undone) != pool[parent * TILE_SIZE:(parent + 1) * TILE_SIZE]:
            bad.append((slot, parent, off, xor))
            continue
        scratch[slot] = (off, xor)
    check(not bad,
          f"editor bake: {len(bad)} declared stress clone(s) are NOT their parent with the "
          f"declared byte XORed (first [slot, parent, byte, xor]: {list(bad[0]) if bad else ''}) "
          f"-- those clones are not honoured, so every word on them is held to the editor "
          f"as-is")
    return scratch


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
    # Claim 2's one exception (resident plain copy, 2026-09-26): a PHYSICAL-form tree
    # stores a blank cell as $0000, dropping the editor's attribute bits on it, because
    # that is the word every patch loop writes for a blank. verify_nt_form holds the rest.
    physical_form = _nt_form_flag() == 1
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
    # Relative to the PROJECT FILE, not to ROOT — identical for the shipped
    # project.json, which sits at the repo root, and the only spelling that works
    # for the second project file a clip act is baked from (--project).
    tileset_path = os.path.join(os.path.dirname(PROJECT_JSON), zone["tileset"])
    data_path = os.path.join(os.path.dirname(PROJECT_JSON), act["dataPath"])
    declared = _section_count()
    if declared is None:
        return

    # A KEYED act (S2-COMPRESSED-ACT row 7: `zones[0].tilesets` + a section_N.zonekey.bin
    # per section — tools/ojz_strip_gen._project_tilesets) names a tileset PER CELL, and
    # claim 3 below must resolve each source word against the sheet ITS cell names. Held
    # to the one-tileset reading, every Chemical Plant cell of a two-zone act would be
    # compared against Emerald Hill's art and fail — or, worse, a bake that LOST the key
    # would compare EHZ-against-EHZ and pass. So the key is read here from the same files
    # the bake read, and a missing one is a failure, never a fallback to one tileset.
    sheet_paths = zone.get("tilesets")
    if sheet_paths is not None:
        sheet_paths = [os.path.join(os.path.dirname(PROJECT_JSON), p) for p in sheet_paths]
        tileset_path = sheet_paths[0]
    arts = []
    for p in (sheet_paths if sheet_paths is not None else [tileset_path]):
        if not os.path.isfile(p):
            check(False, f"editor bake: editor tileset {p} missing")
            return
        a = read(p)
        check(len(a) > 0 and len(a) % TILE_SIZE == 0,
              f"editor bake: editor tileset {os.path.basename(p)} is {len(a)} bytes -- not "
              f"a whole number of {TILE_SIZE}-byte tiles (a 0-byte tileset bakes a blank "
              f"level and passes every other gate)")
        if not a:
            return
        arts.append(a)
    art = arts[0]

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
    # None on a canonical run (the comparison below is then exactly the pre-stress-rule
    # one); on --stress, the verified clone declarations (see _stress_clone_scratch).
    scratch = _stress_clone_scratch(pool)
    clone_shapes = 0
    clones_seen = set()

    sections_checked = 0
    words_checked = 0
    for n in range(declared):
        ed_path = os.path.join(data_path, f"section_{n}.tiles.bin")
        src_path = os.path.join(GEN, f"sec{n}_strips_source.bin")
        rem_path = os.path.join(GEN, f"sec{n}_strips_a.bin")
        map_path = os.path.join(GEN, f"sec{n}_local_map.bin")
        if not os.path.isfile(ed_path):
            # This used to be a silent `continue` ("generate() skips sections with no
            # editor tiles"), so a missing section was checked by nothing (gap lens
            # sweep F2). ojz_strip_gen now refuses to bake without one.
            check(False, f"editor bake: section_{n}.tiles.bin is missing -- every one of "
                         f"the act grid's {declared} sections needs editor tiles")
            continue
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
        ed_keys = None
        if sheet_paths is not None:
            kp = os.path.join(data_path, f"section_{n}.zonekey.bin")
            if not os.path.isfile(kp) or os.path.getsize(kp) != grid * grid:
                check(False, f"editor bake: keyed act, but section_{n}.zonekey.bin is "
                             f"missing or not {grid * grid} bytes -- without the key a "
                             f"cell's art cannot be named, and falling back to one tileset "
                             f"is how a lost key would pass")
                continue
            ed_keys = struct.unpack(f">{grid * grid}b", read(kp))
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

        nt_bad = attr_bad = art_bad = range_bad = src_oob = 0
        src_oob_max = -1
        first = None
        seen = set()
        for c in range(grid):
            off = c * stride
            col_src = struct.unpack(f">{grid}H", src[off: off + grid * 2])
            col_rem = struct.unpack(f">{grid}H", rem[off: off + grid * 2])
            ed_col = ed_words[c::grid]
            key_col = ed_keys[c::grid] if ed_keys is not None else None
            if col_src != ed_col:
                for r in range(grid):
                    if col_src[r] != ed_col[r]:
                        nt_bad += 1
                        if first is None:
                            first = (r, c, ed_col[r], col_src[r])
            for r in range(grid):
                key = 0 if key_col is None else key_col[r]
                pair = (col_src[r], col_rem[r], key)
                if pair in seen:
                    continue
                seen.add(pair)
                sw, rw = col_src[r], col_rem[r]
                if physical_form and (rw & NAMETABLE_TILE_MASK) == 0:
                    # Physical form stores a blank as $0000 — the word every patch loop
                    # writes for it — so the editor's attribute bits on a blank cell are
                    # dropped BY DESIGN, not changed. Anything else on a blank is not.
                    if rw != 0:
                        attr_bad += 1
                        continue
                elif (sw & NAMETABLE_ATTR_MASK) != (rw & NAMETABLE_ATTR_MASK):
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
                if key < 0:
                    # VOID in a keyed act: no clip or corridor covers the cell, the bake
                    # renders the blank tile, and the editor word must be 0 (the bake's
                    # own input check refuses a non-zero one).
                    want = bytes(TILE_SIZE) if sw == 0 else None
                else:
                    if key >= len(arts):
                        range_bad += 1
                        continue
                    want = _tile_pixels(arts[key], sw & NAMETABLE_TILE_MASK,
                                        (sw >> 11) & 1, (sw >> 12) & 1)
                if want is None:
                    src_oob += 1
                    src_oob_max = max(src_oob_max, sw & NAMETABLE_TILE_MASK)
                    continue
                if scratch and g in scratch:
                    # A declared stress clone: undo its ONE declared byte, then hold it
                    # to the editor like any other tile.
                    off, xor = scratch[g]
                    tile = bytearray(pool[g * TILE_SIZE:(g + 1) * TILE_SIZE])
                    tile[off] ^= xor
                    got = _tile_pixels(bytes(tile), 0, (rw >> 11) & 1, (rw >> 12) & 1)
                    clone_shapes += 1
                    clones_seen.add(g)
                else:
                    got = _tile_pixels(pool, g, (rw >> 11) & 1, (rw >> 12) & 1)
                if got is None:
                    range_bad += 1
                    continue
                if want != got:
                    art_bad += 1
            words_checked += grid

        check(src_oob == 0,
              f"editor bake: sec{n} has {src_oob} distinct word shape(s) naming a tile "
              f"past the end of the {len(art) // TILE_SIZE}-tile editor tileset (highest "
              f"index {src_oob_max}) -- that art does not exist, so no bake can have "
              f"carried it (this check used to resolve both sides to a blank tile and pass)")
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
    if scratch is not None and sections_checked:
        # Stress: a declared clone no word renders is a declaration nothing tested, and
        # a stress bake with no clone words is not the fixture it claims to be.
        unseen = sorted(set(scratch) - clones_seen)
        check(not unseen,
              f"editor bake: {len(unseen)} declared stress clone(s) are rendered by no "
              f"nametable word (first slot {unseen[0] if unseen else ''}) -- the "
              f"declaration covers art the check never compared")
        check(clone_shapes > 0,
              "editor bake: --stress run compared zero clone word shapes -- the stress "
              "rule measured nothing, which is not a pass")
    if sections_checked and len(_fail) == fails_before:
        stress_note = ("" if scratch is None else
                       f"; STRESS: {clone_shapes} word shape(s) on {len(clones_seen)} "
                       f"declared clone(s) matched the editor after undoing their one "
                       f"declared scratch byte")
        print(f"verify_level_bin: editor bake fidelity OK "
              f"({sections_checked} section(s), {words_checked} nametable words{stress_note})")


def _expected_collision_entry(word, base_hm, base_an):
    """What one editor collision cell word must bake to, derived from the word itself
    and the committed base bank. Returns:
      None                               -- AIR: the baked attr byte must be 0
      (heights, angle, solidity, xover)  -- the ROM tables' entry at the baked byte
      str                                -- the word cannot be baked at all (why)

    RE-DERIVED FROM THE ENCODING, NOT IMPORTED FROM THE BAKER. The per-plane cell word
    is Aurora's (bits 9:0 base-bank shape, bit 10 xflip, bit 11 yflip, 13:12 this
    plane's solidity, 15:14 the loop crossover mark), resolved xflip-then-yflip
    against the base bank as collision_pipeline.bake_plane_cell documents. Importing
    that function would make this gate agree with the baker by construction, which is
    the T1-2 shape (a proof that reproduces the generator instead of checking it).
    A second statement of five bit fields is the price of a check that can disagree.
    """
    xover = (word >> 14) & 3
    if xover == 3:
        return f"XOVER == 3, which docs/LOOP_CROSSOVER_ENCODING.md reserves as illegal"
    shape = word & 0x03FF
    solidity = (word >> 12) & 3
    if solidity == 0 or shape == 0:
        # No geometry. Unmarked is plain air; a marked cell still interns a non-zero
        # attr whose entry is all-zero heights, angle 0, solidity 0, and the mark.
        return None if xover == 0 else (bytes(PROFILE_LEN), 0, 0, xover)
    if (shape + 1) * PROFILE_LEN > len(base_hm) or shape >= len(base_an):
        return (f"shape {shape} lies outside the {len(base_hm) // PROFILE_LEN}-shape "
                f"base bank")
    heights = base_hm[shape * PROFILE_LEN:(shape + 1) * PROFILE_LEN]
    angle = base_an[shape]
    if word & 0x0400:                       # xflip: mirror columns, negate the angle
        heights = heights[::-1]
        angle = (-angle) & 0xFF
    if word & 0x0800:                       # yflip: hang from the top, reflect the angle
        heights = bytes(h if h in (0, 16) else (256 - h) & 0xFF for h in heights)
        angle = (-angle - 0x80) & 0xFF
    return (bytes(heights), angle, solidity, xover)


def verify_editor_collision_fidelity():
    """The baked collision must carry the EDITOR's authored collision, cell for cell,
    through the attr bytes in sec{N}_strips_a.bin into the ROM-consumed tables.

    THE GAP THIS CLOSES (2026-09-12 gap lens sweep, F1). A section_0.collattr.bin cut
    by two bytes made ojz_strip_gen's overlay warn and return the all-air baseline:
    section 0's plane A went from 1038 non-air cells to 0, all five ROM tables changed,
    and this gate said OK. Nothing in it compared collision to what the editor
    authored, and verify_collision_is_interned only asks "not the raw base bank",
    which an all-air table also satisfies.

    WHAT "FIDELITY" MEANS, derived from ojz_strip_gen.apply_editor_collision_overlay:
      * a section WITH section_N.collattr.bin: every 16-px cell (tile column `col`,
        collision row `cr`) bakes from the word at tile row 2*cr, column col (the
        cell's top tile row). Plane A reads collattr.bin; plane B reads collattrb.bin,
        or plane A's word when collattrb.bin is ABSENT (a wrong-sized file is a failure
        here, not a mirror). The baked byte is an index into the ROM tables, and the
        entry it names must equal what the word resolves to against the base bank --
        or the byte must be 0 when the word is air.
      * a section with NO collattr.bin: the overlay keeps the air baseline, so every
        collision byte in its strips must be 0.
    heightmaps_rot.bin is not compared: it is a pure function of heightmaps.bin
    (rotate_profile), not of anything the editor authored.
    """
    fails_before = len(_fail)
    strip_rows = _strip_gen_int("STRIP_TILE_HEIGHT")
    pad = _strip_gen_int("STRIP_COLLISION_PAD")
    if strip_rows is None or pad is None:
        return
    W = strip_rows                       # the editor grid: W x W tiles per section
    coll_rows = strip_rows // 2          # 16-px collision rows per strip column
    stride = strip_rows * 2 + 2 * coll_rows + pad
    off_a = strip_rows * 2               # plane A follows the nametable words
    off_b = off_a + coll_rows            # plane B follows plane A
    cell_file_bytes = W * W * 2

    if not os.path.isfile(PROJECT_JSON):
        check(False, "editor collision: project.json missing -- cannot locate the editor tree")
        return
    with open(PROJECT_JSON) as f:
        act = json.load(f)["zones"][0]["acts"][0]
    # Relative to the PROJECT FILE (see the same note in the bake-fidelity lane).
    data_path = os.path.join(os.path.dirname(PROJECT_JSON), act["dataPath"])
    declared = _section_count()
    if declared is None:
        return

    names = ("heightmaps.bin", "angles.bin", "solidity.bin", "crossover.bin")
    # --bank names the BASE SHAPE BANK the editor cell words index. Default: the
    # S&K vocabulary under collision/base/, which the shipped act is authored
    # against. A Sonic 2 clip act is authored against collision/base_s2/ (staged
    # plan row 4) and a shape index means a DIFFERENT shape in the other bank, so
    # running this lane with the wrong bank reports every authored cell as a
    # mismatch — which is how a shape ends up skipping the lane instead of
    # pointing it at the right bank.
    bank = BASE_BANK_DIR or os.path.join(COLLISION_DIR, "base")
    need = [os.path.join(bank, "heightmaps.bin"),
            os.path.join(bank, "angles.bin")]
    need += [os.path.join(COLLISION_DIR, n) for n in names]
    missing = [p for p in need if not os.path.isfile(p)]
    if missing:
        check(False, f"editor collision: cannot check -- missing "
                     f"{', '.join(os.path.relpath(p, ROOT) for p in missing)}")
        return
    base_hm = read(need[0])
    base_an = read(need[1])
    hm, an, sol, xo = (read(os.path.join(COLLISION_DIR, n)) for n in names)
    entries = len(hm) // PROFILE_LEN
    if not (len(hm) % PROFILE_LEN == 0 and entries and len(an) == len(sol) == len(xo) == entries):
        check(False, f"editor collision: ROM table sizes disagree (heightmaps {len(hm)} B, "
                     f"angles {len(an)}, solidity {len(sol)}, crossover {len(xo)}) -- "
                     f"they are one table indexed by the same attr byte")
        return
    check(not any(hm[:PROFILE_LEN]) and sol[0] == 0 and xo[0] == 0,
          "editor collision: ROM attr index 0 is not air -- every air cell bakes to "
          "byte 0, so a non-air entry 0 makes the whole act solid where it is empty")

    def rom_entry(idx):
        return (hm[idx * PROFILE_LEN:(idx + 1) * PROFILE_LEN], an[idx], sol[idx], xo[idx])

    cells_checked = 0
    authored_nonair = 0
    for n in range(declared):
        rem_path = os.path.join(GEN, f"sec{n}_strips_a.bin")
        if not os.path.isfile(rem_path):
            check(False, f"editor collision: sec{n}_strips_a.bin missing")
            continue
        rem = read(rem_path)
        if len(rem) != W * stride:
            check(False, f"editor collision: sec{n}_strips_a.bin is {len(rem)} bytes, "
                         f"expected {W} columns x {stride}")
            continue
        path_a = os.path.join(data_path, f"section_{n}.collattr.bin")
        path_b = os.path.join(data_path, f"section_{n}.collattrb.bin")
        if not os.path.isfile(path_a):
            solid = sum(1 for c in range(W) for o in (off_a, off_b)
                        for x in rem[c * stride + o: c * stride + o + coll_rows] if x)
            check(solid == 0,
                  f"editor collision: sec{n} has no section_{n}.collattr.bin (the bake keeps "
                  f"the air baseline) but its strips carry {solid} non-air collision bytes")
            cells_checked += W * coll_rows * 2
            continue
        planes = {}
        bad_size = False
        for label, p in (("A", path_a), ("B", path_b)):
            if not os.path.isfile(p):
                continue
            blob = read(p)
            if len(blob) != cell_file_bytes:
                check(False, f"editor collision: {os.path.relpath(p, ROOT)} is {len(blob)} "
                             f"bytes, expected {cell_file_bytes} ({W}x{W} 16-bit cell "
                             f"words) -- the bake cannot have carried it faithfully")
                bad_size = True
                continue
            planes[label] = struct.unpack(f">{W * W}H", blob)
        if bad_size:
            continue
        planes.setdefault("B", planes["A"])     # absent collattrb.bin: plane B mirrors A

        for label, off in (("A", off_a), ("B", off_b)):
            words = planes[label]
            pairs = {}
            baked_nonair = 0
            for c in range(W):
                col_bytes = rem[c * stride + off: c * stride + off + coll_rows]
                baked_nonair += sum(1 for x in col_bytes if x)
                # words[c::2W] = rows 0, 2, 4 ... of column c: each cell's top tile row
                for pair in zip(words[c::2 * W], col_bytes):
                    pairs[pair] = pairs.get(pair, 0) + 1
            want_nonair = 0
            bad = 0
            first = None
            for (word, idx), count in pairs.items():
                exp = _expected_collision_entry(word, base_hm, base_an)
                if exp is not None and not isinstance(exp, str):
                    want_nonair += count
                if isinstance(exp, str):
                    ok, why = False, exp
                elif exp is None:
                    ok, why = idx == 0, "air (attr byte 0)"
                else:
                    ok = 0 < idx < entries and rom_entry(idx) == exp
                    why = (f"heights {list(exp[0])} angle ${exp[1]:02X} solidity "
                           f"{exp[2]} xover {exp[3]}")
                if not ok:
                    bad += count
                    if first is None:
                        first = (word, idx, why)
            authored_nonair += want_nonair
            cells_checked += W * coll_rows
            check(bad == 0,
                  f"editor collision: sec{n} plane {label}: {bad} of {W * coll_rows} "
                  f"cells do NOT carry what the editor authored (editor has "
                  f"{want_nonair} non-air cells, the bake has {baked_nonair}; first: "
                  f"editor word ${first[0]:04X} baked to attr {first[1]}, expected "
                  f"{first[2]})" if first else f"editor collision: sec{n} plane {label}")

    check(cells_checked > 0,
          "editor collision: zero cells checked -- this gate measured nothing, which is "
          "not a pass")
    if cells_checked and len(_fail) == fails_before:
        print(f"verify_level_bin: editor collision fidelity OK ({declared} section(s), "
              f"{cells_checked} cells, {authored_nonair} authored non-air)")


def main(argv=None):
    global STRESS_MODE, PROJECT_JSON, BASE_BANK_DIR
    args = sys.argv[1:] if argv is None else list(argv)
    # --project PATH names the project file whose act this tree was baked from. The
    # DEFAULT is the shipped project.json at the repo root and nothing about a
    # canonical run changes. A clip act (S2-COMPRESSED-ACT row 6) bakes a SECOND act
    # into the same output directory, and without this every lane below still ran but
    # the two editor-fidelity lanes compared the clip's bake against the SHIPPED act's
    # editor tree — a guaranteed, uninformative failure, which is how a shape ends up
    # skipping the gate entirely instead of pointing it at the right tree.
    project = None
    bank = None
    rest = []
    i = 0
    while i < len(args):
        if args[i] == "--project" and i + 1 < len(args):
            project = args[i + 1]
            i += 2
            continue
        if args[i] == "--bank" and i + 1 < len(args):
            bank = args[i + 1]
            i += 2
            continue
        rest.append(args[i])
        i += 1
    unknown = [a for a in rest if a != "--stress"]
    if unknown:
        print(f"usage: verify_level_bin.py [--stress] [--project PATH] [--bank DIR]  "
              f"(unknown: {' '.join(unknown)})", file=sys.stderr)
        return 2
    if project is not None:
        if not os.path.isfile(project):
            print(f"verify_level_bin: --project {project} does not exist", file=sys.stderr)
            return 2
        PROJECT_JSON = os.path.abspath(project)
    if bank is not None:
        if not os.path.isdir(bank):
            print(f"verify_level_bin: --bank {bank} is not a directory", file=sys.stderr)
            return 2
        BASE_BANK_DIR = os.path.abspath(bank)
    STRESS_MODE = "--stress" in rest
    if STRESS_MODE:
        print("verify_level_bin: --stress: verifying a STRESS_ART throwaway bake "
              f"(declared clones in {STRESS_CLONES_SIDECAR} are held to the editor after "
              f"undoing their one declared byte)")
    verify_act_pool()
    verify_local_maps()
    verify_nt_form()
    verify_block_blobs()
    verify_block_decode()
    verify_descriptor_wiring()
    verify_bininclude_targets()
    verify_collision_is_interned()
    verify_editor_bake_fidelity()
    verify_editor_collision_fidelity()
    verify_section_set()
    verify_no_orphans()
    checks_run = ("act-pool+content+sidecar / local-maps+table / word-form / block-blobs / "
                  "block-decode / descriptor-wiring / bininclude-targets / "
                  "collision-interned / editor-bake / "
                  "editor-collision / section-set / orphans")
    if _fail:
        print(f"verify_level_bin: FAIL ({len(_fail)} issue(s)) [{checks_run}]", file=sys.stderr)
        for m in _fail:
            print(f"  - {m}", file=sys.stderr)
        return 1
    print(f"verify_level_bin: OK [{checks_run}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
