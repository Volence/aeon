#!/usr/bin/env python3
"""Eviction witness (adjudication debt V-3, 2026-08-09; re-aimed 2026-09-28).

THE PROMISE IT KEEPS: when an act needs more pages than the frames it has, the page cache
really evicts and re-loads, correctly, and the picture's art stays right. It grades that on
the STRESS_EVICT shape (the act's page pool is larger than `PAGE_FRAMES_CLAMP`), against a
headless `oracle-aether` IT SPAWNS ITSELF, stepping ONE EMULATED FRAME per sample.

WHY IT WAS RE-AIMED (EVICT-WITNESS-PHASE1-PREMISE, 2026-09-28). Until then Phase 1 proved
eviction by watching the INIT bulk load: the whole pool streamed into fewer frames, so the
load itself evicted (page 2 out for page 8). `787a9980` (2026-09-25) removed that on purpose:
a streaming act now bulk-loads only pages [0, PAGE_FRAMES_CLAMP) at identity, so the load
cannot evict, and the old witness FAILED honestly ("distinct resident pages [0..8] (= 9)
never exceeded the 9-frame clamp"). The eviction now has to come from GAMEPLAY, so the
witness flies the camera to a window that needs a page the init load did not bring.

THE STIMULUS IS DERIVED, NEVER TYPED. From the build:
  * the page FIELD: every cell of the act decoded to its pool page from the section block
    blobs and local maps (tools/fg_working_set.load_page_grid, the one decoder the FG
    working-set measurements use), after checking byte-for-byte that those files are what
    the ROM's act descriptor points at (grid dims, each section's block blob, dict length
    and local map). A field read from files the cart does not carry is refused (exit 2);
  * the window a camera holds: tools/fg_page_order.window_for_camera, Tile_Cache_Fill's
    steady-state window from engine constants (80x60 tile cache);
  * the INITIAL set: the pages resident when the boot settles, read off Page_Table;
  * the PINNED set: each page's pm_flags in the act's manifest, read out of ROM.
From those it picks, along the camera's own row after the settle:
  OUT    the first camera x to the right whose window names a page OUTSIDE the initial set;
  BACK   after the out leg, the first x back to the left whose window names a page the out
         leg EVICTED, such that every window between is SERVICEABLE (below).
No such window is a loud exit 2, never a pass.

SERVICEABLE. A pinned page is never evicted, so once resident it holds its frame for the rest
of the act. A window is serviceable iff |pages(window) ∪ pinned pages resident by then| <=
clamp. The BACK leg only flies through serviceable windows, because a window that is not is
the P-1 capacity famine (below): flying into it is a measurement of that famine, not of
eviction. The famine is PREDICTED from the same field and printed; `--famine-probe` flies
into it and dumps the evidence.

WHAT IS GRADED (exit 1 on any of these):
  * a HALT: `Logic_Tick` unchanged for HALT_FRAMES frames (a raise_error, e.g. the DEBUG
    PageCache_Audit or AllocFrame's thrash, or a hang). Printed with the recovered
    raise_error text and the page-cache state;
  * OUT: no eviction (pigeonhole: distinct pages seen resident must exceed the clamp, and a
    resident->absent transition must be observed); no admission of a page outside the
    initial set INTO A FRAME AN EVICTED PAGE HELD (frame re-use); the settled window's pages
    not all resident;
  * BACK: no evicted page re-loaded (absent after its eviction, resident again); the settled
    window's pages not all resident;
  * ART, after every settle: for every resident page p in frame f, VRAM[f * page_bytes ..]
    must equal p's tiles, decoded from the ROM's own page blob (raw, or ZX0 via
    tools/bin/salvador) and Page_Frames[f].pf_page must be p. The same check runs on the
    initial set before anything moves, as the CONTROL on the reference (a mismatch there is
    reported as the init load's, not the eviction path's).
WHAT IT DOES NOT GRADE: the nametable half of the picture (which frame each cache word
names) is the DEBUG PageCache_Audit's, which halts the run on a violation (a HALT above).

Outcomes (exit code):
  0 PASS
  1 FAIL — a halt, or a graded property above did not hold
  2 UNMEASURABLE — the ROM is not a forced-eviction shape (the pool fits the clamp), the
    derivation has no route (no window needs a page outside the initial set; no serviceable
    way back to an evicted page), the camera did not fly, or the field / cart is not the
    one on disk. "Could not ask" is never "the answer is no".

THE P-1 CAPACITY FAMINE, measured 2026-09-28 on s4.stress.bin crc32 7e677683 (origin/master
bb2d11a1): the act pins pages {0,1,7,8,9} (pm_flags, the >=75%-of-sections rule), so once page
9 is resident only 4 of the 9 frames are evictable, and section 0's windows at camera x
~768..1344 (y 144) need all 5 unpinned pages {2..6}. Flying right to page 9 and back left
halts there: "PageCache_AllocFrame: no free/evictable frame (thrash bug)", demand for page 5,
every evictable frame named by the cache. See EVICT-WITNESS-PHASE1-PREMISE in
docs/DEFERRED_WORK.md. The witness keeps its BACK leg short of it by derivation.

Usage (it spawns its OWN emulator; nothing needs to be running first):
  STRESS_EVICT=1 ./build.sh
  python3 tools/evict_witness.py [--rom s4.stress.bin] [--lst s4.stress.lst] [--famine-probe]

HISTORY KEPT BECAUSE THE SHAPES OF THE DEFECTS ARE THE POINT.
  * Until 2026-09-19 it dialled an ambient legacy socket (`/run/user/1000/oracle.sock`) and
    died with FileNotFoundError when none ran; nothing in the tree ran it, so nothing noticed.
  * Until 2026-09-25 it sampled a free-running machine every 50 ms of wall time and missed a
    12-frame residency window in 11 of 16 runs. Every sample is now one stepped frame.
  * Transcribed constants (clamp, PAGE_NOT_RESIDENT, pool pages) are read from the artifacts.
    PAGE_FRAMES_CLAMP is read off the EMITTED `cmpi.w #imm,d6` in Level_LoadArt's
    fully-resident latch (located by local labels, EVICT-WITNESS-SITE 2026-09-28), not its
    EQU: on the 2026-09-17 sigil the STRESS listing published 12 while the ROM compared 9.
"""
import argparse
import asyncio
import os
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import add_client_path  # noqa: E402
add_client_path()  # the Aether client, resolved from the suite root; loud if absent
from aether import BusClient  # noqa: E402
from aether_instance import AetherInstance, SpawnError  # noqa: E402
from cart_identity import CartMismatch  # noqa: E402
from stressart_legs_witness import (Unmeasurable, sym, rd, listing_labels,  # noqa: E402
                                    nearest_label, raise_message)
import re  # noqa: E402

# ---- run shape (emulated frames) ----
# Boot settle before any direction goes down (stressart_legs_witness's 300: the act is loaded
# and the level ticking well before it). Sampled every frame from frame 1, so a page that
# comes and goes during the settle is still seen.
BOOT_FRAMES = 300
# A leg flies until the camera reaches its derived x, within this budget (DEBUG free flight
# is 16 px a tick; the measured OUT leg is ~120 frames, BACK ~30).
LEG_FRAMES = 1500
# After a leg the directions are released and the machine runs until Page_Table has been
# unchanged for SETTLE_STABLE frames (at most SETTLE_MAX), so every published page's landing
# DMA has drained before VRAM is read.
SETTLE_STABLE = 16
SETTLE_MAX = 240
# One second of video with no completed logic tick (stressart_legs_witness's definition).
HALT_FRAMES = 60

# ---- struct layouts read by this tool (engine/structs.emp) ----
ACT_ART_POOL_TABLE_OFF = 0x1A   # Act.act_art_pool_table (*u8)
ACT_ART_POOL_PAGES_OFF = 0x1E   # Act.act_art_pool_pages (u16)
ACT_GRID_PTR_OFF = 0x00         # Act.sec_grid_ptr
ACT_GRID_W_OFF, ACT_GRID_H_OFF = 0x04, 0x06
ACT_SEC_LOCAL_MAPS_OFF = 0x22   # Act.act_sec_local_maps ([*u8; grid_w*grid_h])
SEC_SIZE = 22                   # sizeof(Sec), ensure'd in structs.emp
SEC_BLOCK_INDEX_OFF, SEC_DICT_LEN_OFF = 0x00, 0x14
PM_SIZE = 8                     # sizeof(PageManifest): source.l, tiles.w, form.b, flags.b
PF_SIZE, PF_PAGE_OFF, PF_STAMP_OFF, PF_FLAGS_OFF = 8, 0, 4, 7   # PageFrame

CMPI_W_D6 = b"\x0c\x46"        # cmpi.w #imm,d6 — the residency-clamp compare's opcode
MOVEQ_D6 = 0x7C                 # moveq #imm,d6 — the bulk-load cap's clamp (high byte)
# THE CLAMP SITE IS LOCATED BY LOCAL LABELS (EVICT-WITNESS-SITE, 2026-09-28): the listing
# publishes `$<module>$Level_LoadArt$<label> : <addr> C |`, so the spans are
#   LATCH [Level_LoadArt, .streaming_pool)  the fully-resident latch; the clamp is read here
#   CAP   [.streaming_pool, .bulk_count_ok) the bulk-load cap's cmpi + moveq, cross-checked
# Exactly one site per span or a loud SETUP refusal. Never widen, never pick.
LATCH_END_LABEL = "streaming_pool"
CAP_END_LABEL = "bulk_count_ok"
SALVADOR = os.path.join(AEON, "tools", "bin", "salvador")


def lst_equ(lst_path: Path, name: str) -> int:
    """One `EQU <name> = $HHHHHHHH` out of a sigil listing, or a loud refusal (never a default:
    the listing is the only place a comptime constant is published to a tool)."""
    pat = re.compile(r"^EQU\s+" + re.escape(name) + r"\s*=\s*\$([0-9A-Fa-f]+)\s*$")
    for line in lst_path.read_text(errors="replace").splitlines():
        m = pat.match(line.strip())
        if m:
            return int(m.group(1), 16)
    raise Unmeasurable(f"SETUP — the listing {lst_path.name} publishes no `EQU {name}`; "
                       f"refusing to substitute a transcribed value")


def lst_local_label(lst_path: Path, routine: str, label: str) -> int:
    """Address of `.label` inside `routine`; exactly one or a loud SETUP refusal."""
    pat = re.compile(r"^\$[^$\s]+\$" + re.escape(routine) + r"\$" + re.escape(label)
                     + r"\s*:\s*([0-9A-Fa-f]+)\s+C\s*\|")
    hits = {int(m.group(1), 16) for line in lst_path.read_text(errors="replace").splitlines()
            if (m := pat.match(line.strip()))}
    if len(hits) != 1:
        raise Unmeasurable(
            f"SETUP — the listing {lst_path.name} publishes {len(hits)} address(es) for local "
            f"label `.{label}` in {routine} (want exactly one); re-derive the site from "
            f"engine/level/load_art.emp")
    return hits.pop()


def span_sites(rom_image: bytes, lo: int, hi: int, opword_ok) -> list:
    """Even addresses in [lo, hi) whose opword satisfies `opword_ok`."""
    return [a for a in range(lo, hi - 1, 2) if opword_ok(rom_image[a:a + 2])]


def emitted_clamp(rom_image: bytes, lst_path: Path, a_loadart: int) -> int:
    """PAGE_FRAMES_CLAMP as the 68000 compares it (see EVICT-WITNESS-SITE)."""
    a_latch_end = lst_local_label(lst_path, "Level_LoadArt", LATCH_END_LABEL)
    a_cap_end = lst_local_label(lst_path, "Level_LoadArt", CAP_END_LABEL)
    if not a_loadart < a_latch_end < a_cap_end <= len(rom_image):
        raise Unmeasurable(f"SETUP — Level_LoadArt ${a_loadart:06X}, .{LATCH_END_LABEL} "
                           f"${a_latch_end:06X}, .{CAP_END_LABEL} ${a_cap_end:06X} are not in "
                           f"routine order; re-derive the site from engine/level/load_art.emp")
    latch = span_sites(rom_image, a_loadart, a_latch_end, lambda w: w == CMPI_W_D6)
    cap = span_sites(rom_image, a_latch_end, a_cap_end, lambda w: w == CMPI_W_D6)
    cap_mq = span_sites(rom_image, a_latch_end, a_cap_end, lambda w: w[0] == MOVEQ_D6)
    for what, sites, insn in (("fully-resident latch", latch, "cmpi.w #imm,d6"),
                              ("bulk-load cap", cap, "cmpi.w #imm,d6"),
                              ("bulk-load cap", cap_mq, "moveq #imm,d6")):
        if len(sites) != 1:
            raise Unmeasurable(f"SETUP — {len(sites)} `{insn}` site(s) in Level_LoadArt's {what} "
                               f"span; this witness reads the clamp off exactly one")
    clamp = int.from_bytes(rom_image[latch[0] + 2:latch[0] + 4], "big")
    c2 = int.from_bytes(rom_image[cap[0] + 2:cap[0] + 4], "big")
    c3 = rom_image[cap_mq[0] + 1]
    if not clamp == c2 == c3:
        raise Unmeasurable(f"SETUP — Level_LoadArt's three PAGE_FRAMES_CLAMP immediates disagree "
                           f"({clamp}, {c2}, {c3}); refusing to pick one")
    print(f"PAGE_FRAMES_CLAMP(emitted) = {clamp}, read off `cmpi.w #${clamp:04X},d6` at "
          f"${latch[0]:06X}; the bulk-load cap's cmpi ${cap[0]:06X} and moveq ${cap_mq[0]:06X} "
          f"agree")
    return clamp


# ---------------------------------------------------------------------------
# The derivation: page field, pinned set, page art — all tied to the cart
# ---------------------------------------------------------------------------

def be(img, off, n):
    return int.from_bytes(img[off:off + n], "big")


def derive_field(rom_image: bytes, act_ptr: int):
    """(PageField, window constants, model) for the act at `act_ptr`, after proving the baked
    files the field is decoded from are the bytes this cart's descriptor points at."""
    import fg_working_set as fws
    import fg_page_order as fpo
    model = fws.Model()
    wc = fpo.load_budget_constants()
    gw, gh = be(rom_image, act_ptr + ACT_GRID_W_OFF, 2), be(rom_image, act_ptr + ACT_GRID_H_OFF, 2)
    if (gw, gh) != (model.grid_w, model.grid_h):
        raise Unmeasurable(f"the cart's act grid is {gw}x{gh}, the baked tree's is "
                           f"{model.grid_w}x{model.grid_h}: the field would describe another act")
    grid = be(rom_image, act_ptr + ACT_GRID_PTR_OFF, 4)
    lmaps = be(rom_image, act_ptr + ACT_SEC_LOCAL_MAPS_OFF, 4)
    dict_lens = fws.load_dict_lens()
    for i in range(gw * gh):
        sec = grid + SEC_SIZE * i
        blocks_at, dict_len = be(rom_image, sec + SEC_BLOCK_INDEX_OFF, 4), be(rom_image, sec + SEC_DICT_LEN_OFF, 2)
        lmap_at = be(rom_image, lmaps + 4 * i, 4)
        for what, at, name in (("block blob", blocks_at, f"sec{i}_blocks.bin"),
                               ("local map", lmap_at, f"sec{i}_local_map.bin")):
            want = Path(fws.GEN_DIR, name).read_bytes()
            if rom_image[at:at + len(want)] != want:
                raise Unmeasurable(f"section {i}'s {what} at ${at:06X} in the cart is not "
                                   f"{name}: the page field would be decoded from bytes the "
                                   f"ROM does not carry")
        if dict_len != dict_lens.get(i):
            raise Unmeasurable(f"section {i}: the cart's dict length {dict_len} != the baked "
                               f"{dict_lens.get(i)}")
    page_grid, _per_sec, _air = fws.load_page_grid(model)
    return fws.PageField(page_grid), wc, model


def page_manifest(rom_image: bytes, act_ptr: int, pool_pages: int):
    """[(source, tiles, form, flags)] for every pool page, out of the cart."""
    tbl = be(rom_image, act_ptr + ACT_ART_POOL_TABLE_OFF, 4)
    return [(be(rom_image, tbl + PM_SIZE * p, 4), be(rom_image, tbl + PM_SIZE * p + 4, 2),
             rom_image[tbl + PM_SIZE * p + 6], rom_image[tbl + PM_SIZE * p + 7])
            for p in range(pool_pages)]


def page_art(rom_image: bytes, manifest, form_raw: int, form_zx0: int, hdr: int) -> list:
    """Each page's tiles as the ROM carries them: raw bytes, or its ZX0 stream decoded by
    salvador (the packer's own decoder; it stops at the stream's end marker, so reading past
    the stream is harmless). The decoded length must be exactly pm_tiles*32."""
    out = []
    for p, (src, tiles, form, _flags) in enumerate(manifest):
        n = tiles * 32
        if form == form_raw:
            art = rom_image[src:src + n]
        elif form == form_zx0:
            if not os.access(SALVADOR, os.X_OK):
                raise Unmeasurable(f"no salvador at {SALVADOR} to decode ZX0 page {p} "
                                   f"(build.sh builds it)")
            with tempfile.TemporaryDirectory() as td:
                a, b = os.path.join(td, "in.zx0"), os.path.join(td, "out.bin")
                Path(a).write_bytes(rom_image[src + hdr:src + hdr + 2 * n + 64])
                r = subprocess.run([SALVADOR, "-d", a, b], capture_output=True)
                art = Path(b).read_bytes() if r.returncode == 0 and os.path.isfile(b) else b""
        else:
            raise Unmeasurable(f"page {p}: pm_form {form} is neither RAW nor ZX0")
        if len(art) != n:
            raise Unmeasurable(f"page {p}: decoded {len(art)} bytes, pm_tiles says {n}")
        out.append(art)
    return out


class Route:
    """Camera x -> the window's page set, along one camera row."""

    def __init__(self, field, wc, cam_y, max_x):
        self.field, self.wc, self.cam_y, self.max_x = field, wc, cam_y, max_x

    def window(self, x):
        from fg_page_order import window_for_camera
        return window_for_camera(self.wc, x, self.cam_y)

    def pages(self, x):
        l, r, t, b = self.window(x)
        return self.field.page_set(t, l, b - t + 1, r - l + 1)


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------

class Run:
    def __init__(self, b, s, pool, not_resident, clamp, page_frames, rom_image, labels):
        self.b, self.s, self.pool, self.nr = b, s, pool, not_resident
        self.clamp, self.page_frames = clamp, page_frames
        self.rom_image, self.labels = rom_image, labels
        self.frame = 0
        self.prev_tick, self.still = None, 0
        self.prev_table = None
        self.seen = set()
        self.owner = {}           # frame -> page last seen resident in it
        self.events = []          # (frame, "evict"/"admit", page, vram frame, previous occupant)
        self.evicted_at = {}      # page -> emulated frame of its latest eviction
        self.reloads = []         # (frame, page, vram frame) — resident again after an eviction

    async def table(self):
        return await rd(self.b, self.s["Page_Table"], self.pool)

    async def cam(self):
        return (int.from_bytes(await rd(self.b, self.s["Camera_X"], 4), "big") >> 16,
                int.from_bytes(await rd(self.b, self.s["Camera_Y"], 4), "big") >> 16)

    async def step(self):
        """One emulated frame; records residency transitions; True when HALTED."""
        await self.b.call("emulator/run_frames", {"frames": 1})
        self.frame += 1
        t = int.from_bytes(await rd(self.b, self.s["Logic_Tick"], 4), "big")
        self.still = self.still + 1 if t == self.prev_tick else 0
        self.prev_tick = t
        tab = await self.table() if self.pool else b""
        if self.nr in tab:               # guard vs the boot-zeroed table
            res = {p: f for p, f in enumerate(tab) if f != self.nr}
            prev = self.prev_table or {}
            for p in sorted(set(prev) - set(res)):
                self.events.append((self.frame, "evict", p, prev[p], None))
                self.evicted_at[p] = self.frame
            for p in sorted(set(res) - set(prev)):
                f = res[p]
                self.events.append((self.frame, "admit", p, f, self.owner.get(f)))
                if p in self.evicted_at:
                    self.reloads.append((self.frame, p, f))
                self.owner[f] = p
            self.seen |= set(res)
            self.prev_table = res
        return self.still >= HALT_FRAMES

    def resident(self):
        return dict(self.prev_table or {})

    async def fly(self, buttons, reached):
        """Hold `buttons` until reached(cam_x) or the budget; returns (halted, reached_at)."""
        await self.b.call("emulator/hold", {"buttons": buttons, "down": True})
        try:
            for _ in range(LEG_FRAMES):
                if await self.step():
                    return True, None
                cx, _cy = await self.cam()
                if reached(cx):
                    return False, cx
            return False, None
        finally:
            await self.b.call("emulator/hold", {"buttons": buttons, "down": False})

    async def settle(self):
        """Run until Page_Table is stable for SETTLE_STABLE frames WHILE THE LOOP TICKS; True
        when HALTED. A faulted machine also holds a stable Page_Table, so stability alone
        would call a raise_error settled: measured on the first draft of this function, whose
        famine probe printed "NOT reproduced" over a machine sitting in the fault island. The
        exit therefore also needs the last frame to have ticked, and a machine that stops
        ticking runs on to HALT_FRAMES and is reported as the halt it is."""
        stable, last = 0, None
        for _ in range(SETTLE_MAX + HALT_FRAMES):
            if await self.step():
                return True
            cur = self.resident()
            stable = stable + 1 if cur == last else 0
            last = cur
            if stable >= SETTLE_STABLE and self.still == 0:
                return False
        raise Unmeasurable(f"Page_Table never held still for {SETTLE_STABLE} ticking frames in "
                           f"{SETTLE_MAX + HALT_FRAMES}; nothing settled to be graded")

    async def check_art(self, art, what):
        """Every resident page's frame holds its tiles and names it back. [] = clean."""
        bad = []
        frames = await rd(self.b, self.s["Page_Frames"], PF_SIZE * self.page_frames)
        for p, f in sorted(self.resident().items()):
            pf_page = be(frames, PF_SIZE * f + PF_PAGE_OFF, 2)
            if pf_page != p:
                bad.append(f"page {p} -> frame {f}, but Page_Frames[{f}].pf_page = ${pf_page:04X}")
            want = art[p]
            got = b""
            for off in range(0, len(want), 2048):
                n = min(2048, len(want) - off)
                r = await self.b.call("emulator/read_vram",
                                      {"addr": hex(f * self.page_bytes + off), "len": n})
                got += bytes.fromhex(str(r["bytes"]).removeprefix("0x").removeprefix("0X"))
            if got != want:
                diff = next(i for i in range(len(want)) if got[i:i + 1] != want[i:i + 1])
                bad.append(f"page {p} in frame {f}: VRAM ${f * self.page_bytes + diff:04X} "
                           f"(tile {diff // 32}) differs from the page's art")
        print(f"  ART {what}: {len(self.resident())} resident page(s) checked against their "
              f"ROM art in VRAM — " + ("clean" if not bad else f"{len(bad)} MISMATCH(ES)"))
        for line in bad:
            print(f"    {line}")
        return bad

    async def dump_halt(self, where):
        """The famine / fault evidence: the raise text, the frames, what the cache names."""
        st = await self.b.call("emulator/status", {})
        pc = int(str(st.get("pc", "0")), 16) & 0xFFFFFF
        cx, cy = await self.cam()
        print(f"  HALT during {where} at emulated frame {self.frame - HALT_FRAMES}: Logic_Tick "
              f"unchanged for {HALT_FRAMES} frames, camera ({cx},{cy}), pc ${pc:06X} "
              f"({'in' if pc >= self.s['ErrorHandlerBlob'] else 'NOT in'} the fault island)")
        msgs = await raise_message(self.b, self.rom_image)
        for site, m in msgs:
            print(f"    raise_error at ${site:06X} ({nearest_label(self.labels, site)}): {m!r}")
        if not msgs:
            print("    raise_error message: none recovered from RAM")
        frames = await rd(self.b, self.s["Page_Frames"], PF_SIZE * self.page_frames)
        for f in range(self.page_frames):
            rec = frames[PF_SIZE * f:PF_SIZE * (f + 1)]
            pg = be(rec, PF_PAGE_OFF, 2)
            fl = rec[PF_FLAGS_OFF]
            print(f"    frame {f:2}: page {'-' if pg == 0xFFFF else pg}, flags ${fl:02X}"
                  f"{' PINNED' if fl & self.pf_pinned else ''}"
                  f"{' DEMAND-HELD' if fl & self.pf_held else ''}, stamp {be(rec, PF_STAMP_OFF, 2)}")
        nt = b""
        for off in range(0, self.nt_size, 2400):
            nt += await rd(self.b, self.s["Tile_Cache_Nametable"] + off, min(2400, self.nt_size - off))
        named = sorted({(be(nt, i, 2) & self.nt_mask) >> self.frame_shift
                        for i in range(0, len(nt), 2) if be(nt, i, 2) & self.nt_mask})
        cur = int.from_bytes(await rd(self.b, self.s["PageIn_Cur_Page"], 2), "big")
        flags = (await rd(self.b, self.s["PageIn_Cur_Flags"], 1))[0]
        print(f"    Tile_Cache_Nametable names frames {named}; the request being served: page "
              f"{cur}, flags ${flags:02X}")


async def main(sock, rom_path: Path, lst_path: Path, famine_probe: bool) -> int:
    rom_image = rom_path.read_bytes()
    labels = listing_labels(lst_path)
    not_resident = lst_equ(lst_path, "PAGE_NOT_RESIDENT")
    page_table_max = lst_equ(lst_path, "PAGE_TABLE_MAX")
    page_frames = lst_equ(lst_path, "PAGE_FRAMES")
    clamp_equ = lst_equ(lst_path, "PAGE_FRAMES_CLAMP")
    print(f"evict_witness: {rom_path.name} crc32 {zlib.crc32(rom_image):08x}; derived from "
          f"{lst_path.name}: PAGE_FRAMES_CLAMP(EQU)={clamp_equ} PAGE_FRAMES={page_frames} "
          f"PAGE_NOT_RESIDENT=${not_resident:02X}")

    b = BusClient(socket_path=sock, client_id="evictw", client_name="evict-witness")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": str(lst_path)})
    s = {n: await sym(b, n) for n in (
        "Logic_Tick", "Camera_X", "Camera_Y", "Page_Table", "Page_Frames", "Current_Act_Ptr",
        "Tile_Cache_Nametable", "PageIn_Cur_Page", "PageIn_Cur_Flags", "ErrorHandlerBlob",
        "Level_LoadArt")}
    clamp = emitted_clamp(rom_image, lst_path, s["Level_LoadArt"])
    if clamp != clamp_equ:
        print(f"  !! DISAGREEMENT: the listing publishes PAGE_FRAMES_CLAMP = {clamp_equ}, the ROM "
              f"compares against {clamp}. Going with the ROM (STRESS-CLAMP-EQU-WRONG).")

    run = Run(b, s, None, not_resident, clamp, page_frames, rom_image, labels)
    run.page_bytes = lst_equ(lst_path, "ART_POOL_PAGE_BYTES")
    run.pf_pinned = lst_equ(lst_path, "PF_PINNED")
    run.pf_held = 1 << lst_equ(lst_path, "PF_DEMAND_HELD_BIT")
    run.nt_size = lst_equ(lst_path, "TILE_CACHE_NT_SIZE")
    run.nt_mask = lst_equ(lst_path, "NT_TILE_MASK")
    run.frame_shift = lst_equ(lst_path, "PAGE_FRAME_TILE_SHIFT")

    # ---- boot settle, sampled every frame; the pool size comes off the loaded act ----
    act_ptr, pool = 0, None
    for _ in range(BOOT_FRAMES):
        if pool is None:
            act_ptr = int.from_bytes(await rd(b, s["Current_Act_Ptr"], 4), "big") & 0xFFFFFF
            if 0 < act_ptr < len(rom_image) - 0x30:
                n = be(rom_image, act_ptr + ACT_ART_POOL_PAGES_OFF, 2)
                if 0 < n <= page_table_max:
                    pool, run.pool = n, n
        if await run.step():
            await run.dump_halt("the boot settle")
            return 1
    if pool is None:
        raise Unmeasurable(f"Current_Act_Ptr never resolved to an act in {BOOT_FRAMES} frames "
                           f"(last ${act_ptr:06X})")
    print(f"act descriptor ${act_ptr:06X}: act_art_pool_pages={pool} vs PAGE_FRAMES_CLAMP={clamp}")
    if pool <= clamp:
        print(f"UNMEASURABLE: this shape cannot force an eviction — the act's {pool}-page pool "
              f"fits the {clamp}-frame residency clamp, so the cache is fully resident by design. "
              f"Build the fixture shape: `STRESS_EVICT=1 ./build.sh` (writes s4.stress.bin / "
              f"s4.stress.lst).")
        return 2

    manifest = page_manifest(rom_image, act_ptr, pool)
    pinned = {p for p, m in enumerate(manifest) if m[3] & lst_equ(lst_path, "ART_PAGE_FLAG_PINNED")}
    art = page_art(rom_image, manifest, lst_equ(lst_path, "ART_PAGE_FORM_RAW"),
                   lst_equ(lst_path, "ART_PAGE_FORM_ZX0"), lst_equ(lst_path, "ART_HDR_SIZE"))
    field, wc, model = derive_field(rom_image, act_ptr)

    initial = run.resident()
    identity = all(f == p for p, f in initial.items())
    print(f"INITIAL (after the {BOOT_FRAMES}-frame settle): resident {sorted(initial)}"
          f"{' at identity' if identity else ' (NOT at identity: ' + str(initial) + ')'}; "
          f"evictions during the settle: {sum(1 for e in run.events if e[1] == 'evict')}; "
          f"pinned pages (pm_flags) {sorted(pinned)}")
    if await run.check_art(art, "CONTROL, the initial set as the init load landed it"):
        print("FAIL: the init load's pages do not match their ROM art (the reference is decoded "
              "independently, from the cart's own page blobs); nothing has been evicted yet, so "
              "this is the init path's defect, not the eviction path's")
        return 1

    # ---- derive the route ----
    cam_x0, cam_y = await run.cam()
    max_x = max(0, model.act_cols * 8 - wc["SCREEN_WIDTH"])
    route = Route(field, wc, cam_y, max_x)
    outside = lambda x: route.pages(x) - set(initial)  # noqa: E731
    x_out = next((x for x in range(cam_x0, max_x + 1, 8) if outside(x)), None)
    if x_out is None:
        anywhere = any(m >> clamp for row in field.mask_field(wc["TILE_CACHE_COLS"],
                                                              wc["TILE_CACHE_ROWS"]) for m in row)
        print(f"UNMEASURABLE: no window to the right of camera ({cam_x0},{cam_y}) along row y "
              f"{cam_y} names a page outside the initial set {sorted(initial)}"
              + ("" if anywhere else f"; NO window anywhere in the act names a page >= {clamp}")
              + ", so no flight on this row can demand an eviction")
        return 2
    print(f"OUT target (derived): camera x {x_out} at y {cam_y}, window {route.window(x_out)} "
          f"names {sorted(route.pages(x_out))}, of which {sorted(outside(x_out))} are outside the "
          f"initial set; start camera ({cam_x0},{cam_y})")

    # ---- OUT leg ----
    ev0 = len(run.events)
    halted, at = await run.fly(["right"], lambda cx: cx >= x_out)
    if halted:
        await run.dump_halt("the OUT leg")
        print("FAIL: the OUT leg halted")
        return 1
    if at is None:
        cx, _ = await run.cam()
        raise Unmeasurable(f"the OUT leg did not fly: camera x {cx} < {x_out} after "
                           f"{LEG_FRAMES} frames")
    if await run.settle():
        await run.dump_halt("the OUT settle")
        print("FAIL: the OUT leg halted while settling")
        return 1
    x_out_end, _ = await run.cam()
    out_events = run.events[ev0:]
    for fr, kind, p, f, prev_owner in out_events:
        print(f"  +{fr}: {kind} page {p} {'from' if kind == 'evict' else 'into'} frame {f}"
              + (f" (previously page {prev_owner}'s)" if kind == "admit" and prev_owner is not None
                 else ""))
    evicted_out = sorted({p for _fr, k, p, _f, _o in out_events if k == "evict"})
    reuse = [(fr, p, f, o) for fr, k, p, f, o in out_events
             if k == "admit" and p not in initial and o is not None and o in evicted_out]
    res = run.resident()
    need = route.pages(x_out_end)
    fails = []
    if len(run.seen) <= clamp or not evicted_out:
        fails.append(f"no eviction proven: {len(run.seen)} distinct page(s) seen resident against "
                     f"a {clamp}-frame clamp, evicted {evicted_out}")
    if not reuse:
        fails.append("no page outside the initial set was admitted into a frame an evicted page "
                     "had held (frame re-use not observed)")
    if not need <= set(res):
        fails.append(f"settled at camera x {x_out_end}: the window names {sorted(need)} but "
                     f"{sorted(need - set(res))} is not resident")
    print(f"OUT: settled at camera x {x_out_end}; {len(run.seen)} distinct pages > {clamp} frames; "
          f"evicted {evicted_out}; re-used frames "
          f"{[f'page {p} into frame {f} (was page {o}) at +{fr}' for fr, p, f, o in reuse]}")
    fails += await run.check_art(art, "after the OUT leg")
    if fails:
        for line in fails:
            print(f"FAIL: {line}")
        return 1

    # ---- derive the BACK target: a serviceable route to a window naming an evicted page ----
    # Pinned pages resident by then hold their frames for good; a pinned page the route admits
    # joins them. A window is serviceable iff its pages plus those fit the clamp.
    held = {p for p in res if p in pinned}
    x_back, famine_at, path_max = None, None, 0
    for x in range(x_out_end, -1, -8):
        pg = route.pages(x)
        held |= pg & pinned
        n = len(pg | held)
        if n > clamp:
            famine_at = (x, sorted(pg), sorted(held), n)
            break
        path_max = max(path_max, n)
        if pg & (set(evicted_out) - set(res)):
            x_back = x
            break
    if x_back is None:
        why = (f"the first window back to the left that is not serviceable is at camera x "
               f"{famine_at[0]}: it names {famine_at[1]}, and with the pinned pages "
               f"{famine_at[2]} resident that is {famine_at[3]} > {clamp} frames"
               if famine_at else "no window back to camera x 0 names an evicted page")
        print(f"UNMEASURABLE: no serviceable way back to a window that names an evicted page "
              f"({evicted_out}); {why}")
        return 2
    want_back = sorted(route.pages(x_back) & set(evicted_out))
    print(f"BACK target (derived): camera x {x_back}, window {route.window(x_back)} names "
          f"{sorted(route.pages(x_back))}, including evicted {want_back}; every window on the way "
          f"needs <= {path_max} of {clamp} frames")

    # ---- the famine, predicted beyond the BACK target ----
    fam = None
    for x in range(x_back, -1, -8):
        pg = route.pages(x)
        held |= pg & pinned
        if len(pg | held) > clamp:
            fam = (x, sorted(pg), sorted(held), len(pg | held))
            break
    if fam:
        print(f"P-1 FAMINE (predicted, not flown): at camera x {fam[0]} the window names {fam[1]}; "
              f"with the pinned pages {fam[2]} resident that is {fam[3]} pages for {clamp} frames, "
              f"so no frame is evictable there (EVICT-WITNESS-PHASE1-PREMISE)")

    # ---- BACK leg ----
    ev1, back_start = len(run.events), run.frame
    halted, at = await run.fly(["left"], lambda cx: cx <= x_back)
    if halted:
        await run.dump_halt("the BACK leg")
        print("FAIL: the BACK leg halted on a route derived serviceable")
        return 1
    if at is None:
        cx, _ = await run.cam()
        raise Unmeasurable(f"the BACK leg did not fly: camera x {cx} > {x_back}")
    if await run.settle():
        await run.dump_halt("the BACK settle")
        print("FAIL: the BACK leg halted while settling")
        return 1
    x_back_end, _ = await run.cam()
    for fr, kind, p, f, prev_owner in run.events[ev1:]:
        print(f"  +{fr}: {kind} page {p} {'from' if kind == 'evict' else 'into'} frame {f}"
              + (f" (previously page {prev_owner}'s)" if kind == "admit" and prev_owner is not None
                 else ""))
    reloaded = [(fr, p, f) for fr, p, f in run.reloads if p in evicted_out and fr > back_start]
    res = run.resident()
    need = route.pages(x_back_end)
    fails = []
    if not any(p in res for p in want_back):
        fails.append(f"none of the evicted pages {want_back} the BACK window names is resident")
    if not reloaded:
        fails.append(f"no evicted page ({evicted_out}) was re-loaded")
    if not need <= set(res):
        fails.append(f"settled at camera x {x_back_end}: the window names {sorted(need)} but "
                     f"{sorted(need - set(res))} is not resident")
    print(f"BACK: settled at camera x {x_back_end}; re-loaded "
          f"{[f'page {p} into frame {f} at +{fr}' for fr, p, f in reloaded]}")
    fails += await run.check_art(art, "after the BACK leg")
    if fails:
        for line in fails:
            print(f"FAIL: {line}")
        return 1

    if famine_probe:
        if not fam:
            print("FAMINE PROBE: nothing predicted to the left; not flown")
        else:
            print(f"FAMINE PROBE: flying left to camera x {fam[0]} (predicted over capacity)")
            halted, _at = await run.fly(["left"], lambda cx: cx <= fam[0])
            if not halted:
                halted = await run.settle()
            if halted:
                await run.dump_halt("the famine probe")
                print("FAMINE PROBE: reproduced (the verdict below is the eviction proof's)")
            else:
                print("FAMINE PROBE: NOT reproduced — the camera reached the predicted window and "
                      "the machine kept ticking")
    print(f"PASS: evicted {evicted_out} for a page outside the initial set, re-used the frame, "
          f"re-loaded {sorted({p for _fr, p, _f in reloaded})}; every resident page's art checked "
          f"in VRAM after each leg")
    return 0


def _cli() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=os.path.join(AEON, "s4.stress.bin"))
    ap.add_argument("--lst", default=os.path.join(AEON, "s4.stress.lst"))
    ap.add_argument("--famine-probe", action="store_true",
                    help="after the proof, fly into the predicted P-1 famine and dump it")
    args = ap.parse_args()
    rom_path, lst_path = Path(args.rom).resolve(), Path(args.lst).resolve()
    for label, q in (("ROM", rom_path), ("listing", lst_path)):
        if not q.is_file():
            print(f"UNMEASURABLE: no {label} at {q}. This witness grades the forced-eviction "
                  f"fixture shape; build it with `STRESS_EVICT=1 ./build.sh` (writes "
                  f"s4.stress.bin / s4.stress.lst), or point --rom/--lst at one.")
            return 2
    inst = AetherInstance(str(rom_path), symbols=str(lst_path))
    try:
        sock = inst.start()
        if inst.cart_note:
            print(inst.cart_note)
        return asyncio.run(main(sock, rom_path, lst_path, args.famine_probe))
    except (Unmeasurable, SpawnError, CartMismatch) as e:
        print(f"UNMEASURABLE: {e}")
        return 2
    finally:
        inst.reap()


if __name__ == "__main__":
    raise SystemExit(_cli())
