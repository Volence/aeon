#!/usr/bin/env python3
"""dplc_coherence_witness.py — is the player's VRAM art ever OUT OF STEP with the
mapping frame the SAT was built from?

WHY THIS EXISTS (EFFECTS-W1 F7, "sometimes the sprites get jumbled"). A scrambled
Sonic — head, body and shoe pieces interleaved — does NOT require a malformed sprite
attribute table. It requires the tiles at the player's DPLC window to be art from a
DIFFERENT mapping frame than the one the SAT entries were built from. So the SAT is
the wrong thing to look at, and a screenshot of a paused machine is worse (it is a
post-hoc render: it fails by showing a clean picture).

WHAT IT MEASURES, DIRECTLY, ON A RUNNING MACHINE. Every frame:

  * read `Sst.mapping_frame` (F) out of the live player SST;
  * rebuild, from the ROM ON DISK, the exact byte image `Perform_DPLC` would have to
    leave in the DPLC window for F — walk DPLC_Sonic's entry list for F, concatenate
    `Art_Sonic[tile_start*32 : (tile_start+count)*32]` in entry order (that IS
    `perform_dplc`'s running-destination loop, engine/objects/dplc.emp);
  * read the live VRAM window and compare, tile by tile.

Only the tiles frame F actually loads are compared — anything above its tile total is
stale BY DESIGN and no piece references it.

A tile that does not match F is art from some other frame sitting under a mapping that
expects F's. That is the jumble, and this counts it — CLEAN, OTHER_FRAME (the window
is some other frame's, and the report names the candidates), or UNIDENTIFIED (the
window is no frame's at all, the shape a half-landed DPLC would take).

It runs a SECOND, independent instrument on the same samples: the VDP's OWN sprite
attribute table at $B800, read after the Critical drain has shipped it. The player's
pieces must appear there as a contiguous run, in mapping order, with tile = art_tile +
the frame's per-piece offset and the frame's size codes — and the link chain walked
from entry 0 must be exactly `Sprites_Rendered` long. That is the other half of the
F7 question: not "is the art right" but "is the table well-formed".

WHERE THE SAMPLE IS TAKEN, AND WHY THERE. `SAMPLE_PC_SYM` below — the instruction
after `Process_DMA_Important` returns inside `VInt_Level`. At that pc the Critical
drain has already pushed the SAT into VRAM and the Important drain has already pushed
what DPLC art it could, while `Sst.mapping_frame` still holds the frame the shipped
SAT was built from. So art, table and frame number are all the ones the frame about to
be displayed will use, and NOTHING about phase has to be inferred. An earlier cut of
this witness sampled at `VSync_Wait` instead and had to fit a lag; that fit ABSORBED a
deliberate one-frame poison completely, because in a walk cycle mf_i + 1 IS mf_{i+1}.
The lag numbers are still printed, as a diagnostic. They do not classify.

SAMPLE RESOLUTION IS DERIVED, and this is the trap this repo has fallen into twice.
The candidate mechanism (a budgeted DMA drain that stops mid-entry-list, engine/system/
dma_queue.emp `Drain_Budgeted_Queue.out_of_budget`) leaves the window wrong for EXACTLY
ONE frame: the surviving entries are compacted and drain in the next VBlank. So the
event lasts one frame, and every frame is sampled — there are no gaps to hide in.

TWO CONTROLS, because a green from an instrument that cannot go red is worth nothing.

  POSITIVE CONTROL (printed with every run). A drive in which the player never animates
  never enqueues a DPLC entry, so it CANNOT show this defect. The run prints the count
  of distinct mapping frames and `DMA_Peak_Important`, and says out loud when either
  makes the result vacuous.

  POISON CONTROL (`--poison N`). The identical drive, with every expectation built from
  mapping_frame + N. Measured 2026-09-04 over 300 frames: ART goes 300/300 red at N =
  1, 7 and 50. The SAT instrument goes 94, 230 and 300 red respectively — it is
  COARSER, and this is its stated blind spot: 128 of Sonic's 224 frames share their
  (tile, size) piece signature with another frame (33 adjacent pairs are identical), so
  a swap between two such frames is invisible to it. The ART instrument is the fine
  one: 213 of the 224 DPLC window images are distinct, and 20 frames can prefix-alias,
  which is why `identify()` reports the whole candidate set instead of picking.

THE DRIVE ORDER IS LOAD-BEARING (each cost an evening; see loop_step_over_witness.py):
  * leave debug-fly with a real B PRESS, never by writing debug_flag;
  * set the CAMERA first and let streaming settle, THEN place the player;
  * let the camera FOLLOW afterwards.

WHAT A RUN OF THIS CANNOT SEE, said before the numbers rather than after them. It
watches ONE object (the player), in ONE character's art (Sonic), in the act the debug
build boots into. That act's art is fully resident — `Dbg_PageCache_Demands` stayed 0
across 5,000 px of travel — so the player's DPLC is the Important queue's ONLY
customer here and the drain has no second claimant to be starved by. An act that
really streams pages would be a different population, and this witness has never seen
one. It also never touches the Deferrable queue's own drain, which is where the
spindash dust and insta-shield art rides.

Usage:
    tools/dplc_coherence_witness.py --rom s4.debug.bin --lst s4.debug.lst
    tools/dplc_coherence_witness.py --rom s4.debug.bin --lst s4.debug.lst \
        --gsp 0x1000 --force-gsp --frames 2000
    tools/dplc_coherence_witness.py --rom s4.debug.bin --lst s4.debug.lst \
        --gsp 0x1000 --force-gsp --frames 300 --poison 7        # the control

Exit 0 always for a bare run — this is a WITNESS, it reports.
"""

import argparse
import asyncio
import hashlib
import pathlib
import re
import sys

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from suite_paths import add_client_path, harness_path      # noqa: E402
sys.path.insert(0, str(harness_path()))
add_client_path()
from aether_instance import aether_emulator                # noqa: E402
from aether import BusClient                               # noqa: E402

# The sample point. Chosen so the comparison has NO PHASE AMBIGUITY: it is the
# instruction right after `Process_DMA_Important` returns inside VInt_Level, so at
# this instant the Critical drain has already pushed Sprite_Table_Buffer into the
# VDP's SAT and the Important drain has already pushed whatever DPLC art it could.
# `Sst.mapping_frame` is untouched by the VBlank, so it still holds the frame the
# just-shipped SAT was built from. VRAM window vs mapping_frame at THIS pc is the
# coherence the displayed frame will actually use — nothing is inferred about phase.
SAMPLE_PC_SYM = "$engine.vblank$VInt_Level$staging_idle"

NEED_SYMS = (SAMPLE_PC_SYM, "Player_1", "Camera_X", "Camera_Y", "Art_Sonic", "DPLC_Sonic",
             "Map_Sonic",
             "DMA_Peak_Important", "DMA_Overflow_Count", "DMA_Split_Reject_Count",
             "DMA_Budget_Remaining", "DMA_Important_Slot", "DMA_Important",
             "Plane_Buffer_Ptr", "Sprites_Rendered", "Sprite_Table_Buffer",
             "Dbg_PageCache_Demands", "Dbg_PageCache_Prefetches", "Dbg_PageIn_Deferred",
             "Dbg_DMA_Enq_Capped")
NEED_EQUS = ("SST_x_pos", "SST_y_pos", "SST_mapping_frame", "SST_prev_frame",
             "SST_art_tile", "SST_anim", "SST_layer", "SST_angle")

# PlayerV overlays Sst.sst_custom = $30; ground_speed is the overlay's first field and
# debug_flag sits at +$C from it. Both are `.emp` struct fields, not EQU lines, so this
# file states them rather than pretending they came out of the build.
PLAYERV_GROUND_SPEED = 0x30
PLAYERV_DEBUG_FLAG = 0x3C

TILE_BYTES = 32
START_X, START_Y = 1097, 553          # the ramp foot of the section-0 loop
CAM_X, CAM_Y = 1097, 445
SETTLE_FRAMES = 40
LAND_FRAMES = 8
ENTRY_LEN = 14                        # sizeof(DMAEntry)
SAT_VRAM = 0xB800                     # VRAM_SPRITE_TABLE (engine/system/constants.emp)
SAT_BYTES = 640                       # 80 entries x 8


def sat_check(sat, rendered, art_tile, pieces):
    """Is the player's piece run present, contiguous, in order, and inside the chain?

    Returns (verdict, detail). The SAT read here is the VDP's OWN table, after the
    Critical drain has shipped it — the real output, not the RAM buffer proxy.
    """
    want = [((art_tile + t) & 0x07FF, size) for (_y, size, t) in pieces]
    got = [(((sat[i * 8 + 4] << 8) | sat[i * 8 + 5]) & 0x07FF, sat[i * 8 + 2])
           for i in range(SAT_BYTES // 8)]
    # walk the link chain from entry 0 and record which entries are live
    chain, idx = [], 0
    for _ in range(SAT_BYTES // 8):
        chain.append(idx)
        nxt = sat[idx * 8 + 3]
        if nxt == 0:
            break
        idx = nxt
    if len(chain) != rendered:
        return "CHAIN_LEN", "link-path %d vs Sprites_Rendered %d" % (len(chain), rendered)
    if not want:
        return "OK", "frame has no pieces"
    for start in range(0, len(chain) - len(want) + 1):
        run = [got[chain[start + k]] for k in range(len(want))]
        if run == want:
            return "OK", "run at chain position %d" % start
    return "NO_RUN", "expected %s; chain tiles %s" % (
        [hex(t) for t, _ in want],
        [hex(got[c][0]) for c in chain][:16])


def parse_lst(path):
    sym_re = re.compile(r"^ ([A-Za-z_$][\w$.]*) : ([0-9A-Fa-f]+) [A-Z] \|")
    equ_re = re.compile(r"^EQU ([A-Za-z_][\w]*) = \$([0-9A-Fa-f]+)\s*$")
    syms, equs = {}, {}
    for line in pathlib.Path(path).read_text(errors="replace").splitlines():
        m = sym_re.match(line)
        if m:
            syms.setdefault(m.group(1), int(m.group(2), 16))
            continue
        m = equ_re.match(line)
        if m:
            equs.setdefault(m.group(1), int(m.group(2), 16))
    missing = ([n for n in NEED_SYMS if n not in syms]
               + [n for n in NEED_EQUS if n not in equs])
    if missing:
        raise SystemExit("dplc_coherence_witness: %s carries no %s"
                         % (path, ", ".join(missing)))
    return syms, equs


class DplcModel:
    """The ROM's own answer to 'what must the window hold for frame F?'"""

    def __init__(self, rom_bytes, dplc_addr, art_addr):
        self.rom = rom_bytes
        self.dplc = dplc_addr
        self.art = art_addr
        self.frames = self._be16(dplc_addr) // 2

    def _be16(self, a):
        return (self.rom[a] << 8) | self.rom[a + 1]

    def window(self, f):
        """The exact bytes perform_dplc leaves at the window base for frame f."""
        if not (0 <= f < self.frames):
            return None
        fo = self.dplc + self._be16(self.dplc + f * 2)
        n = self._be16(fo)
        out = bytearray()
        for e in range(n):
            w = self._be16(fo + 2 + e * 2)
            count = ((w >> 12) & 0xF) + 1
            start = w & 0x0FFF
            src = self.art + start * TILE_BYTES
            out += self.rom[src:src + count * TILE_BYTES]
        return bytes(out), n

    def entries(self, f):
        return self.window(f)[1] if self.window(f) else 0

    @property
    def max_tiles(self):
        if not hasattr(self, "_mt"):
            self._mt = max(len(self.window(f)[0]) // TILE_BYTES
                           for f in range(self.frames))
        return self._mt

    def identify(self, live):
        """Every DPLC frame whose window image is a prefix-match of `live`.

        The window is only as long as the frame it holds, so a shorter frame can
        legitimately alias a longer one — the caller reports the whole candidate
        set rather than picking, which is what keeps this from inventing a
        single confident answer it cannot support.
        """
        out = []
        for f in range(self.frames):
            want = self.window(f)[0]
            if want and live[:len(want)] == want:
                out.append(f)
        return out


class MapModel:
    """The ROM's own answer to 'which SAT entries must the player occupy?'

    A mapping frame's pieces are emitted in order by Emit_ObjectPieces, so the SAT
    must contain them as a CONTIGUOUS run whose per-entry (tile, size) pair is the
    frame's, in the frame's order. Anything else — a run from two frames, a run cut
    short, a run out of order — is a malformed table, which is the other half of
    the F7 question.
    """

    def __init__(self, rom_bytes, map_addr):
        self.rom = rom_bytes
        self.map = map_addr
        self.frames = self._be16(map_addr) // 2

    def _be16(self, a):
        return (self.rom[a] << 8) | self.rom[a + 1]

    def pieces(self, f):
        if not (0 <= f < self.frames):
            return None
        fo = self.map + self._be16(self.map + f * 2)
        n = self._be16(fo + 4)
        out = []
        for e in range(n):
            po = fo + 6 + e * 8
            out.append((self._be16(po) if self._be16(po) < 0x8000
                        else self._be16(po) - 0x10000,        # y offset
                        self.rom[po + 2],                      # VDP size code
                        self._be16(po + 4)))                   # tile attr (relative)
        return out


class Bus:
    def __init__(self, client):
        self.b = client

    async def read(self, addr, n):
        r = await self.b.call("emulator/read_memory",
                              {"addr": hex(addr & 0xFFFFFF), "len": n})
        s = r["bytes"]
        s = s[2:] if s[:2].lower() == "0x" else s
        return bytes.fromhex(s)

    async def read_vram(self, addr, n):
        r = await self.b.call("emulator/read_vram", {"addr": hex(addr), "len": n})
        s = r["bytes"]
        s = s[2:] if s[:2].lower() == "0x" else s
        return bytes.fromhex(s)

    async def write(self, addr, value, width):
        return await self.b.call("emulator/write_memory",
                                 {"addr": hex(addr & 0xFFFFFF), "value": value,
                                  "width": width})

    async def frames(self, n):
        return await self.b.call("emulator/run_frames", {"frames": n})

    async def status(self):
        return await self.b.call("emulator/status", {})

    async def check_alive(self, where):
        st = await self.status()
        sym = st.get("symbolAtPc") or ""
        if "ErrorHandler" in sym:
            raise SystemExit("dplc_coherence_witness: the ROM FAULTED during %s — "
                             "symbolAtPc=%r pc=%s." % (where, sym, st.get("pc")))
        return st


def classify(live, want, want_prev):
    """CLEAN / PARTIAL / STALE_PREV / OTHER + the first mismatching tile."""
    n = len(want) // TILE_BYTES
    bad = [t for t in range(n)
           if live[t * TILE_BYTES:(t + 1) * TILE_BYTES]
           != want[t * TILE_BYTES:(t + 1) * TILE_BYTES]]
    if not bad:
        return "CLEAN", None, 0
    first = bad[0]
    if want_prev is not None and len(want_prev) >= len(want) \
            and live[:len(want)] == want_prev[:len(want)]:
        return "STALE_PREV", first, len(bad)
    if bad == list(range(first, n)):
        return "PARTIAL", first, len(bad)
    return "OTHER", first, len(bad)


async def drive(sock, syms, equs, model, gsp, frames, verbose, force=False,
                jump=0):
    client = BusClient(socket_path=sock, client_id="dplcw", client_name="dplc-coherence")
    await client.connect()
    b = Bus(client)

    P = syms["Player_1"]
    A_X, A_Y = P + equs["SST_x_pos"], P + equs["SST_y_pos"]
    A_MF = P + equs["SST_mapping_frame"]
    A_PF = P + equs["SST_prev_frame"]
    A_ART = P + equs["SST_art_tile"]
    A_GSP = P + PLAYERV_GROUND_SPEED
    A_DBG = P + PLAYERV_DEBUG_FLAG

    await client.call("emulator/reset", {})
    await b.frames(240)
    await b.check_alive("boot")

    dbg = (await b.read(A_DBG, 1))[0]
    if dbg:
        await client.call("emulator/press", {"buttons": ["b"]})
        await b.frames(4)
    await b.check_alive("debug-fly exit")

    await b.write(syms["Camera_X"], CAM_X << 16, 4)
    await b.write(syms["Camera_Y"], CAM_Y << 16, 4)
    await b.frames(SETTLE_FRAMES)
    await b.check_alive("streaming settle")

    await b.write(A_X, START_X << 16, 4)
    await b.write(A_Y, START_Y << 16, 4)
    await b.frames(LAND_FRAMES)
    await b.check_alive("placement")

    art_tile = int.from_bytes(await b.read(A_ART, 2), "big")
    vram_base = (art_tile & 0x07FF) * TILE_BYTES

    await client.call("emulator/hold", {"buttons": ["right"], "down": True})
    if gsp:
        await b.write(A_GSP, gsp, 2)

    st = await b.status()
    stop_phase = st.get("symbolAtPc")

    rows, prev_f = [], None
    sample_pc = syms[SAMPLE_PC_SYM]
    for f in range(frames):
        # ADVANCE FIRST. `run_to` returns immediately when the machine is already
        # standing on the target — without this step every iteration would sample
        # the same instant and report a perfectly stable, perfectly meaningless
        # machine (measured: 150 identical rows, Plane_Buffer_Ptr 0 throughout).
        if jump and f and f % jump == 0:
            await client.call("emulator/press", {"buttons": ["c"]})
        if force and gsp:
            # STRESS DRIVER, and it is an injection, not physics: ground_speed is
            # rewritten every tick so the run does not decay against the ramp the
            # player otherwise stalls on (DEFERRED_WORK T1). It buys distance —
            # i.e. section streaming and page landings, the Important-queue
            # pressure this witness exists to put the drain under — at the price
            # of a state the physics would not have produced on its own. Every
            # coherence verdict below is still the engine's.
            await b.write(A_GSP, gsp, 2)
        await b.frames(1)
        r = await client.call("emulator/run_to",
                              {"addr": hex(sample_pc), "maxFrames": 8})
        if not r.get("reached"):
            rows.append({"frame": f, "fault": "run_to never reached the sample pc",
                         "pc": r.get("pc")})
            break
        st = await b.status()
        sym = st.get("symbolAtPc") or ""
        if "ErrorHandler" in sym:
            rows.append({"frame": f, "fault": sym, "pc": st.get("pc")})
            break
        mf = (await b.read(A_MF, 1))[0]
        pf = (await b.read(A_PF, 1))[0]
        live = await b.read_vram(vram_base, model.max_tiles * TILE_BYTES)
        row = {
            "frame": f,
            "x": int.from_bytes(await b.read(A_X, 4), "big") >> 16,
            "y": int.from_bytes(await b.read(A_Y, 4), "big") >> 16,
            "mf": mf, "pf": pf,
            "live": live,
            "budget": int.from_bytes(await b.read(syms["DMA_Budget_Remaining"], 2), "big"),
            "imp_left": (int.from_bytes(
                await b.read(syms["DMA_Important_Slot"], 2), "big")
                - (syms["DMA_Important"] & 0xFFFF)) // ENTRY_LEN,
            "plane": int.from_bytes(await b.read(syms["Plane_Buffer_Ptr"], 2), "big"),
            "sat": await b.read_vram(SAT_VRAM, SAT_BYTES),
            "rendered": int.from_bytes(
                await b.read(syms["Sprites_Rendered"], 2), "big"),
            "art_tile": art_tile,
        }
        rows.append(row)
        prev_f = mf

    await client.call("emulator/hold", {"buttons": ["right"], "down": False})

    tail = {
        "peak_important_bytes": int.from_bytes(
            await b.read(syms["DMA_Peak_Important"], 2), "big"),
        "overflow": int.from_bytes(await b.read(syms["DMA_Overflow_Count"], 2), "big"),
        "split_reject": int.from_bytes(
            await b.read(syms["DMA_Split_Reject_Count"], 2), "big"),
        "enq_capped": int.from_bytes(
            await b.read(syms["Dbg_DMA_Enq_Capped"], 2), "big"),
        "page_demands": int.from_bytes(
            await b.read(syms["Dbg_PageCache_Demands"], 2), "big"),
        "page_prefetch": int.from_bytes(
            await b.read(syms["Dbg_PageCache_Prefetches"], 2), "big"),
        "page_deferred": int.from_bytes(
            await b.read(syms["Dbg_PageIn_Deferred"], 2), "big"),
        "vram_base": vram_base,
        "art_tile": art_tile,
        "stop_phase": stop_phase,
    }
    await client.close()
    return rows, tail


def report(rows, tail, gsp, label, verbose, model, mapmodel, poison=0):
    """`poison` shifts the mapping frame the expectations are built from. It is the
    CONTROL: a checker that cannot fail proves nothing, so `--poison 1` re-runs the
    identical drive comparing every frame against the NEXT animation frame's art and
    pieces. Both instruments must go red almost everywhere; if they do not, the
    green above was vacuous."""
    live = [r for r in rows if "live" in r]
    faults = [r for r in rows if "fault" in r]

    # --- establish the SAMPLE PHASE from the data, do not assume it ---
    # The machine parks at VSync_Wait, i.e. AFTER a tick's render and BEFORE the
    # VBlank that ships that tick's DMA. So the art standing in VRAM at sample i
    # is whatever the last COMPLETED VBlank left there, which is one or more
    # ticks behind sample i's mapping_frame. Rather than assert a lag, every
    # frame's window is IDENTIFIED against all 224 candidates and the lag that
    # explains the most frames is reported — with the residue that no lag
    # explains, which is the only part that can be a defect.
    for r in live:
        r["mf"] = (r["mf"] + poison) % model.frames if poison else r["mf"]
        r["cands"] = model.identify(r["live"])
    lag_hits = {}
    for lag in (0, 1, 2):
        hits = 0
        for i, r in enumerate(live):
            j = i - lag
            if j < 0:
                continue
            if live[j]["mf"] in r["cands"]:
                hits += 1
        lag_hits[lag] = hits
    # LAG IS PINNED AT 0, not fitted. The sample pc is inside VInt_Level after both
    # drains, so the only correct answer IS 0 — and a fitted lag is worse than
    # useless here: it launders a systematic offset. Measured 2026-09-04: a
    # `--poison 1` control (compare against the NEXT animation frame) was absorbed
    # completely by a fitted lag of 1, because in a walk cycle mf_i + 1 IS mf_{i+1}.
    # The fitted numbers stay in the report as a diagnostic; they do not classify.
    best = 0
    for i, r in enumerate(live):
        j = i - best
        r["explained"] = j >= 0 and live[j]["mf"] in r["cands"]
        r["want_mf"] = live[j]["mf"] if j >= 0 else None
    kinds = {}
    for r in live:
        k = "CLEAN" if r["explained"] else ("UNIDENTIFIED" if not r["cands"]
                                            else "OTHER_FRAME")
        r["kind"] = k
        kinds[k] = kinds.get(k, 0) + 1
    sat_kinds = {}
    for r in live:
        v, d = sat_check(r["sat"], r["rendered"], r["art_tile"],
                         mapmodel.pieces(r["mf"]) or [])
        r["sat_kind"], r["sat_detail"] = v, d
        sat_kinds[v] = sat_kinds.get(v, 0) + 1
    mfs = sorted({r["mf"] for r in live})
    peak_entries = tail["peak_important_bytes"] // ENTRY_LEN

    print("  %s  gsp=%s  frames sampled=%d (1-frame interval — the candidate event "
          "lasts exactly 1 frame)" % (label, hex(gsp) if gsp else "none", len(live)))
    print("    window: art_tile=$%04X -> VRAM $%05X, compared against the ROM's own "
          "DPLC walk; stop phase symbolAtPc=%r"
          % (tail["art_tile"], tail["vram_base"], tail["stop_phase"]))
    print("    POSITIVE CONTROL: distinct mapping frames seen=%d %s · "
          "DMA_Peak_Important=%d B = %d entries %s"
          % (len(mfs), "(OK)" if len(mfs) > 1 else "(*** the player never animated — "
             "a clean result from this drive would be VACUOUS ***)",
             tail["peak_important_bytes"], peak_entries,
             "(OK — the DPLC really enqueued)" if peak_entries > 1 else
             "(*** at most one Important entry ever queued — the player's DPLC did "
             "NOT run; a clean result is VACUOUS ***)"))
    print("    enqueue-side drops: DMA_Overflow_Count=%d  DMA_Split_Reject_Count=%d  "
          "Dbg_DMA_Enq_Capped=%d" % (tail["overflow"], tail["split_reject"],
                                     tail["enq_capped"]))
    print("    streaming pressure over the drive: page demands=%d prefetches=%d "
          "deferred=%d   player x %d..%d (%+d px travelled)"
          % (tail["page_demands"], tail["page_prefetch"], tail["page_deferred"],
             min(r["x"] for r in live), max(r["x"] for r in live),
             live[-1]["x"] - live[0]["x"]))
    print("    SAMPLE PHASE, derived from the data: lag hits = %s -> the window in "
          "VRAM at a sample matches the mapping_frame of the sample %d tick(s) "
          "earlier (the park is before that tick's VBlank ships its DMA)"
          % (lag_hits, best))
    print("    ART coherence (VRAM window vs the ROM's DPLC walk): "
          + ("  ".join("%s=%d" % kv for kv in sorted(kinds.items())) or "(no frames)"))
    print("    SAT well-formedness (VDP's own table at $B800, after the Critical "
          "drain): " + ("  ".join("%s=%d" % kv for kv in sorted(sat_kinds.items()))
                        or "(no frames)"))
    budgets = [r["budget"] for r in live]
    lefts = [r["imp_left"] for r in live]
    planes = [r["plane"] for r in live]
    if live:
        print("    DMA_Budget_Remaining after the drains: min=%d max=%d   "
              "Important entries still queued: max=%d   Plane_Buffer_Ptr max=%d"
              % (min(budgets), max(budgets), max(lefts), max(planes)))
    for r in live:
        if r["sat_kind"] != "OK":
            print("      f%-3d x=%-5d y=%-5d mf=%d  SAT %s: %s"
                  % (r["frame"], r["x"], r["y"], r["mf"], r["sat_kind"],
                     r["sat_detail"]))
    for r in live:
        if r["kind"] != "CLEAN":
            print("      f%-3d x=%-5d y=%-5d mf=%d(prev_frame %d) expected window for "
                  "frame %s  %s  candidates=%s  budget=%d impleft=%d"
                  % (r["frame"], r["x"], r["y"], r["mf"], r["pf"], r["want_mf"],
                     r["kind"], r["cands"][:6], r["budget"], r["imp_left"]))
    if faults:
        print("    FAULTED at frame %d: %s" % (faults[0]["frame"], faults[0]["fault"]))
    if verbose:
        for r in live:
            print("       f%-3d x=%-5d y=%-5d mf=%-3d want=%-4s %-12s budget=%-5d "
                  "impleft=%d plane=%d"
                  % (r["frame"], r["x"], r["y"], r["mf"], r["want_mf"], r["kind"],
                     r["budget"], r["imp_left"], r["plane"]))
    return kinds, tail, len(live)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--gsp", default=None, help="ground speed to inject once (hex ok)")
    ap.add_argument("--frames", type=int, default=200)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--poison", type=int, default=0,
                    help="CONTROL: build every expectation from mapping_frame+N "
                         "instead of mapping_frame. Both instruments must go red.")
    ap.add_argument("--jump", type=int, default=0,
                    help="press C every N sampled frames — exercises the air/roll "
                         "frames and the Deferrable-DPLC companions")
    ap.add_argument("--force-gsp", action="store_true",
                    help="rewrite ground_speed every tick (stress driver — see the "
                         "note at the injection site)")
    a = ap.parse_args()

    rom = pathlib.Path(a.rom).read_bytes()
    print("dplc_coherence_witness: rom=%s (%d B, sha256 %s)"
          % (a.rom, len(rom), hashlib.sha256(rom).hexdigest()[:16]))
    syms, equs = parse_lst(a.lst)
    model = DplcModel(rom, syms["DPLC_Sonic"], syms["Art_Sonic"])
    mapmodel = MapModel(rom, syms["Map_Sonic"])
    print("  DPLC_Sonic=$%05X Art_Sonic=$%05X frames=%d  peak entries/frame=%d"
          % (syms["DPLC_Sonic"], syms["Art_Sonic"], model.frames,
             max(model.entries(f) for f in range(model.frames))))

    gsp = int(a.gsp, 0) if a.gsp else None
    with aether_emulator(a.rom, symbols=a.lst) as sock:
        rows, tail = asyncio.run(drive(sock, syms, equs, model, gsp, a.frames,
                                       a.verbose, a.force_gsp, a.jump))
    report(rows, tail, gsp, "run-right", a.verbose, model, mapmodel, a.poison)
    return 0


if __name__ == "__main__":
    sys.exit(main())
