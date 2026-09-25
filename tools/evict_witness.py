#!/usr/bin/env python3
"""Eviction-liveness witness (adjudication debt V-3, 2026-08-09).

Proves the residency cache actually evicts, on the STRESS_EVICT shape, against a
headless `oracle-aether` IT SPAWNS ITSELF (PAGE_FRAMES_CLAMP frames vs the act's larger
page pool; both numbers are derived at run time, see the banner below).

PHASE 1 (the proof, famine-free): sample Page_Table ONCE PER EMULATED FRAME
(stepped, not wall-clock timed; see PHASE1_FRAMES) while the OJZ init loads the act. More pages must stream through than there are frames to
hold them, so the load itself evicts: the sampler observes a page transition
resident->absent while the distinct-ever-resident count exceeds the frame
clamp (pigeonhole — no engine instrumentation needed). Both sides of that
inequality are derived per run and the run REFUSES when it does not hold.
Measured 2026-08-09: page 2 evicted to admit page 8, distinct 10 over a
9-frame clamp. Re-measured 2026-09-19 on s4.stress.bin crc32 cd308561:
same shape — 10 distinct pages, clamp 9, eviction of page 2 observed.

PHASE 2 (best-effort scroll churn): one 90-frame camera-scroll burst, then a
residency re-sample. This leg exercises the reload-after-evict path — but the
STRESS shape has a KNOWN reachable AllocFrame famine on sustained scroll
(P-1 class + the 2026-08-09 sustained-right recipes, ledgered in
2026-08-09-art-streaming-p2-lens-adjudication.md), and the famine is a
knife-edge race that can fire on the very first burst. A Phase-2 famine is
therefore reported as the OPEN DEBT it is, without failing the witness —
Phase 1 already carries the liveness proof.

Sampling guard: a boot-cleared Page_Table is all zeroes, which decodes as
"every page resident in frame 0". Samples are ignored until the table
contains at least one PAGE_NOT_RESIDENT ($FF) sentinel (every legitimate
post-PageCache_Init state has one).

Outcomes (exit code):
  0 PASS — eviction proven in Phase 1; Phase 2 clean or known-famine
  1 FAIL — no eviction observed / fault during Phase 1 / setup error
  2 UNMEASURABLE — the ROM handed to it is not a forced-eviction shape (its act's page
    pool fits the residency clamp, so nothing CAN evict and the pigeonhole is vacuous),
    or the cart the server loaded is not the file on disk. Never rendered as a zero and
    never as a FAIL of the eviction subject: "could not ask" is not "the answer is no".

Usage (it spawns its OWN emulator; nothing needs to be running first):
  STRESS_EVICT=1 ./build.sh
  python3 tools/evict_witness.py [--rom s4.stress.bin] [--lst s4.stress.lst]

⚠ WHAT THIS FILE WAS UNTIL 2026-09-19, because the shape of the defect is the point.
It hard-coded `SOCK = "/run/user/1000/oracle.sock"` and connected to whatever legacy
`oracle_gui` the owner happened to be running. MEASURED on this tree, crc32 62238a15:
`python3 tools/evict_witness.py --rom s4.debug.bin --lst s4.debug.lst` died in 0 s with an
unhandled `FileNotFoundError` out of `sock.connect`, exit 1. Nothing in the tree ran it, so
nothing noticed — the only code reference to its name anywhere was a string in
`cart_coverage_census.py`'s table of tool classifications. It now spawns a private headless
`oracle-aether` through `tools/aether_instance.py`, like every other witness here, which is
also what makes it gradeable by a lane instead of by a person with a GUI open.

THREE COPIED CONSTANTS ARE NOW DERIVED, for the same reason. `PAGE_FRAMES_CLAMP = 9`,
`PAGE_NOT_RESIDENT = 0xFF` and `OJZ_POOL_PAGES = 10` were transcribed from the engine, and
a transcribed number is one that nothing notices when the source moves: the pool page count
in particular comes out of a GENERATED manifest (`ojz_act_pool_manifest.emp`) that any
level re-bake can change. Each is read from the authority that governs it:

  PAGE_NOT_RESIDENT, PAGE_TABLE_MAX   the listing's own `EQU` lines
  act_art_pool_pages                  the act descriptor on the running machine
  PAGE_FRAMES_CLAMP                   the EMITTED `cmpi.w #imm,d6` in `Level_LoadArt`,
                                      NOT its `EQU` — on the STRESS shape those two
                                      DISAGREE (12 published, 9 compared). The `EQU` is
                                      read anyway and printed beside it, loudly, because
                                      an instrument that silently prefers one of two
                                      disagreeing authorities is how a disagreement
                                      stays invisible. See the block at that read.

If the pool and the clamp
ever stop satisfying `pool_pages > clamp` the fixture cannot force an eviction at all, and
that is now a loud refusal rather than a pigeonhole that quietly always holds.
"""
import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import add_client_path  # noqa: E402
add_client_path()  # the Aether client, resolved from the suite root; loud if absent
from aether import BusClient  # noqa: E402
from aether_instance import AetherInstance  # noqa: E402

# PHASE 1 IS SAMPLED ONCE PER EMULATED FRAME, NOT ON A WALL-CLOCK TIMER (2026-09-25,
# EVICT-WITNESS-WIRING). Until then it was `PHASE1_SECONDS = 15` of free-running emulation
# read every 50 ms of WALL time, and that is a race the witness loses most of the time.
# MEASURED on s4.stress.bin crc32 cd308561, stepped one frame at a time from the
# GameState_OJZScroll_Init breakpoint (frame +N = N frames past it, the numbering the PHASE 1
# line prints): pages 0..8 stream in every 2 frames from +35, page 2 is resident for exactly
# 12 FRAMES (+39..+50) and is evicted at +51 to admit page 8, and the table is settled by +52. The old sampler read a free-running machine every 50 ms of
# wall time, so whether a 12-frame window fell between two reads was up to the host: the
# wall-clock witness exited 1 ("no eviction proven", distinct pages [0,1,3..9] = 9, page 2
# never seen) in 11 of 16 back-to-back runs on the same ROM on 2026-09-25 (runs 1-3, 10 and
# 16 passed; load average 16-35 throughout). How the miss rate depends on host speed was NOT
# measured and is not claimed. A verdict that changes between identical runs of one ROM is
# not a verdict about the engine. Frame-stepped, the sample sequence is the ROM's.
# The budget is emulated frames: 900 (15 s at 60 Hz, the window the old constant nominally
# bought) against a measured settle at +52, so ~17x margin for a slower load; ~5 ms of wall
# per frame over the bus, so ~4.5 s.
PHASE1_FRAMES = 900
BURST_FRAMES = 90
ACT_ART_POOL_PAGES_OFF = 0x1E   # engine/structs.emp, Act.act_art_pool_pages (u16)
CMPI_W_D6 = b"\x0c\x46"        # cmpi.w #imm,d6 — the residency-clamp compare's opcode
CLAMP_SCAN_BYTES = 64           # window from Level_LoadArt; must contain exactly one
PAGE_TABLE_MAX_NAME = "PAGE_TABLE_MAX"


def lst_equ(lst_path: Path, name: str) -> int:
    """One `EQU <name> = $HHHHHHHH` value out of a sigil listing, or a loud refusal.

    The listing is the only place a comptime constant is published to a tool: it is not a
    symbol, so `emulator/lookup_symbol` cannot see it (two namespaces, one interface). A
    missing name is an ERROR and never a default — a default here would be a copied
    constant wearing a fallback, which is the thing this function exists to replace.
    """
    pat = re.compile(r"^EQU\s+" + re.escape(name) + r"\s*=\s*\$([0-9A-Fa-f]+)\s*$")
    for line in lst_path.read_text(errors="replace").splitlines():
        m = pat.match(line.strip())
        if m:
            return int(m.group(1), 16)
    raise SystemExit(
        f"evict_witness: SETUP — the listing {lst_path} publishes no `EQU {name}`. "
        f"Refusing to substitute a transcribed value: the whole point of reading it here "
        f"is that nothing notices when a transcribed one goes stale.")


async def sym(b, name):
    r = await b.call("emulator/lookup_symbol", {"name": name})
    return int(r["addr"], 16)


async def read(b, addr, n):
    """`n` bytes at `addr`, or a loud refusal — never a short or padded answer.

    THE `0x` PREFIX IS A SEAM DIFFERENCE, found while migrating this file to the Rust core
    on 2026-09-19: oracle-aether returns `bytes` as `0x....` where the legacy C++ server
    returned bare hex, so the old one-line `bytes.fromhex(r["bytes"])` raised
    `non-hexadecimal number found ... at position 1` on the very first read. A short reply
    is NEVER left-padded here: padding would shift every field of a decoded block and the
    numbers would still look like numbers.
    """
    r = await b.call("emulator/read_memory", {"addr": hex(addr & 0xFFFFFF), "len": n})
    h = str(r["bytes"]).removeprefix("0x").removeprefix("0X")
    if len(h) != n * 2:
        raise SystemExit(f"evict_witness: read_memory at ${addr:06X} len {n} returned "
                         f"{len(h) // 2} byte(s) ({h!r}) — refusing to pad")
    return bytes.fromhex(h)


async def main(sock, rom_path: Path, lst_path: Path):
    # THE FIXTURE'S OWN TWO NUMBERS, READ OFF THE ARTIFACTS BEING GRADED. Neither is a
    # literal here any more; see the banner. `PAGE_NOT_RESIDENT` doubles as the sampling
    # guard's sentinel, so a drift there would have silently disabled the guard.
    clamp_equ = lst_equ(lst_path, "PAGE_FRAMES_CLAMP")
    not_resident = lst_equ(lst_path, "PAGE_NOT_RESIDENT")
    page_table_max = lst_equ(lst_path, PAGE_TABLE_MAX_NAME)
    print(f"derived from {lst_path.name}: PAGE_FRAMES_CLAMP(EQU)={clamp_equ} "
          f"PAGE_NOT_RESIDENT=${not_resident:02X} PAGE_TABLE_MAX={page_table_max}")

    b = BusClient(socket_path=sock, client_id="evictw", client_name="evict-witness")
    await b.connect()

    await b.call("emulator/load_symbols", {"path": str(lst_path)})
    a_init = await sym(b, "GameState_OJZScroll_Init")
    a_page_table = await sym(b, "Page_Table")
    a_err = await sym(b, "ErrorHandlerBlob")
    a_act = await sym(b, "Current_Act_Ptr")
    a_loadart = await sym(b, "Level_LoadArt")

    # ---- THE CLAMP IS READ OFF THE INSTRUCTION THAT ENFORCES IT ----
    # AND THAT IS NOT PEDANTRY, IT IS A MEASURED DISAGREEMENT. On 2026-09-19, on the very
    # shape this witness exists for, `s4.stress.lst` publishes `EQU PAGE_FRAMES_CLAMP =
    # $0000000C` (12) while `s4.stress.bin` emits `cmpi.w #$0009,d6` at the one site in
    # `Level_LoadArt` that uses that name (engine/level/load_art.emp:88), i.e. the fixture IS
    # clamped to 9 and the listing says it is not. The listing's other three constants are
    # consistent with 9 (`PAGE_FRAMES` 12, `STRESS_EVICT` 1, `STRESS_EVICT_FRAMES` 9, and
    # constants.emp folds those to 12 - 1*(12-9) = 9), so it is the FOLDED publication that
    # is wrong, not the shape. Booked in docs/DEFERRED_WORK.md.
    #
    # So the authority here is the emitted immediate: the number the 68000 actually compares
    # against. The EQU is read anyway and printed beside it, because an instrument that
    # silently prefers one of two disagreeing authorities is how a disagreement stays
    # invisible. The scan is bounded and requires EXACTLY ONE `cmpi.w #imm,d6` in the window
    # — zero or two is a refusal, never a guess, because a routine that grew a second one
    # would otherwise hand back whichever came first.
    rom_image = rom_path.read_bytes()
    win = rom_image[a_loadart:a_loadart + CLAMP_SCAN_BYTES]
    hits = [i for i in range(0, len(win) - 3, 2) if win[i:i + 2] == CMPI_W_D6]
    if len(hits) != 1:
        print(f"FAIL: SETUP — {len(hits)} `cmpi.w #imm,d6` site(s) in the "
              f"{CLAMP_SCAN_BYTES} bytes at Level_LoadArt (${a_loadart:06X}); this witness "
              f"reads the residency clamp off exactly one and refuses to pick. Re-derive "
              f"the site from engine/level/load_art.emp before widening the window.")
        return 1
    clamp = int.from_bytes(win[hits[0] + 2:hits[0] + 4], "big")
    print(f"PAGE_FRAMES_CLAMP(emitted) = {clamp}, read off `cmpi.w #${clamp:04X},d6` at "
          f"${a_loadart + hits[0]:06X} in Level_LoadArt")
    if clamp != clamp_equ:
        print(f"  !! DISAGREEMENT: the listing publishes PAGE_FRAMES_CLAMP = {clamp_equ}, the "
              f"ROM compares against {clamp}. Going with the ROM — it is the one that runs — "
              f"and the publication is a defect in its own right. See docs/DEFERRED_WORK.md, "
              f"STRESS-CLAMP-EQU-WRONG.")

    # THE RELOAD-ORDERING HAZARD THAT USED TO LIVE HERE IS GONE WITH THE RELOAD, and it is
    # recorded rather than deleted because the hazard is still real for any tool that reloads:
    # `emulator/reload_rom` re-binds the symbol table it already holds instead of re-reading
    # the `.lst`, and REPORTS `symbolsDropped: false`, which reads as reassurance — so a
    # symbol resolved AFTER a reload comes back "no such symbol" while sitting in the listing
    # you just grepped (oracle's finding, 2026-09-04). This file resolved every symbol before
    # its reload and was safe by a decision taken for an unrelated reason. It no longer
    # reloads at all: a private spawn is handed the ROM on its command line.
    await b.call("emulator/breakpoint_add", {"addr": hex(a_init)})

    # THE CART IS ALREADY PROVEN. `AetherInstance.start()` asserts the Rust server and then
    # compares the loaded cart against the file on disk while the machine is still stopped at
    # frame 0, and raises `CartMismatch` (UNMEASURABLE, never a zero) if they differ. The
    # RELOAD this function used to perform is gone with the ambient socket that made it
    # necessary: reloading existed to make somebody ELSE's running emulator hold our ROM.
    # A private spawn is given the ROM on its command line, so there is nothing to reload
    # and no `symbolsDropped: false` reassurance to misread.
    await b.call("emulator/resume", {})
    await b.call("emulator/pause", {})

    # SEND-SIDE SPELLING IS PINNED TO THE SERVER WE ACTUALLY TALK TO. The legacy server
    # takes `timeout_ms`; oracle's Rust core takes `timeoutMs` and REFUSES an unknown key
    # with -32602 rather than aliasing it (accepting both spellings is how a vocabulary
    # rots). This probe MIGRATED to the Rust core on 2026-09-19 (it used to dial an ambient
    # legacy socket), and per the owner ruling of 2026-08-26 the spelling flips in the same
    # commit as the migration and never before — `tools/test_wait_for_break_spelling.py`
    # and `tools/test_legacy_seam_keys.py` both read this file's seam off its imports and
    # grade this key against it, so the two halves cannot land apart.
    r = await b.call("emulator/wait_for_break", {"timeoutMs": 60000})
    # READ SIDE, AND THIS IS THE HALF THAT USED TO FAIL SILENTLY. It was
    # `r.get("timeout_reached")`: after a migration that key is spelled `timeoutReached`,
    # `.get` returns None, None is falsy, and A SURRENDER READS AS A SUCCESS — the probe
    # would announce the breakpoint was reached when the server had just told it the
    # opposite. The parameter error above announces itself; this one never would.
    # Dual-accept is legitimate on the RECEIVE side, and the absence of BOTH spellings is
    # now a loud error rather than a default.
    for key in ("timeout_reached", "timeoutReached"):
        if key in r:
            timed_out = bool(r[key])
            break
    else:
        raise RuntimeError(
            "wait_for_break replied with neither `timeout_reached` nor `timeoutReached` "
            f"(keys: {sorted(r)}). Refusing to guess: reading a missing key as False would "
            "report a timeout as a reached breakpoint.")
    if timed_out:
        print("FAIL: never reached GameState_OJZScroll_Init")
        return 1
    await b.call("emulator/breakpoint_clear", {"all": True})

    async def in_fault():
        s = await b.call("emulator/status", {})
        return int(s["pc"], 16) >= a_err  # fault island = last emission

    # ---- THE POOL PAGE COUNT, READ OFF THE ACT THE MACHINE ACTUALLY LOADED ----
    # It used to be `OJZ_POOL_PAGES = 10`, transcribed from
    # `games/sonic4/data/generated/ojz/act1/ojz_act_pool_manifest.emp` — a GENERATED file
    # that `tools/regenerate-level.sh` rewrites.
    #
    # IT IS RESOLVED INSIDE THE SAMPLE LOOP, NOT AT THE BREAKPOINT, and that was MEASURED
    # rather than chosen for elegance: read immediately at `GameState_OJZScroll_Init` the
    # pointer is not yet installed and comes back $001814FC, which the bus rejects as past
    # the end of an 848,075-byte cart. `Level_Load` installs it a little way INTO the state
    # this breakpoint anchors. So the loop below asks every iteration until the answer is a
    # plausible ROM address, and ignores samples until then — which costs nothing, because
    # the $FF sampling guard already ignores everything before `PageCache_Init` anyway.
    rom_bytes = rom_path.stat().st_size

    async def try_pool_pages():
        ptr = int.from_bytes(await read(b, a_act, 4), "big") & 0xFFFFFF
        if not 0 < ptr < rom_bytes - ACT_ART_POOL_PAGES_OFF - 2:
            return None, ptr
        n = int.from_bytes(await read(b, ptr + ACT_ART_POOL_PAGES_OFF, 2), "big")
        return (n if 0 < n <= page_table_max else None), ptr

    # ---- PHASE 1: init-load residency churn, sampled EVERY EMULATED FRAME ----
    # The machine stays stopped at the breakpoint and is advanced one frame per sample, so
    # the sample sequence is a property of the ROM, not of the host's load. See the block at
    # PHASE1_FRAMES for the measured 12-frame residency window the wall-clock sampler missed.
    seen = set()
    evicted_pages = set()
    first_eviction = None
    prev = None
    valid_samples = 0
    pool_pages = None
    act_ptr = 0
    for frame in range(1, PHASE1_FRAMES + 1):
        await b.call("emulator/run_frames", {"frames": 1})
        if pool_pages is None:
            pool_pages, act_ptr = await try_pool_pages()
            if pool_pages is None:
                continue
            print(f"act descriptor ${act_ptr:06X} (frame +{frame}): "
                  f"act_art_pool_pages={pool_pages} vs PAGE_FRAMES_CLAMP={clamp}")
        table = await read(b, a_page_table, pool_pages)
        if not_resident in table:      # guard vs the boot-zeroed table
            resident = {i for i, f in enumerate(table) if f != not_resident}
            valid_samples += 1
            seen |= resident
            if prev is not None:
                gone = prev - resident
                if gone and first_eviction is None:
                    first_eviction = (frame, sorted(gone), sorted(resident - prev))
                evicted_pages |= gone
            prev = resident
    if await in_fault():
        print("FAIL: fault raise during init load (Phase 1 must be famine-free)")
        return 1
    if pool_pages is None:
        print(f"FAIL: Current_Act_Ptr never resolved to a usable act descriptor in "
              f"{PHASE1_FRAMES} frames (last value ${act_ptr:06X}). act_art_pool_pages could "
              f"not be derived, and a transcribed one is what this tool just stopped using.")
        return 1

    # ---- IS THIS SHAPE EVEN A FORCED-EVICTION FIXTURE? ----
    # The proof below is a pigeonhole: more distinct pages stream through than there are
    # frames to hold them. That argument is only available while pool_pages > clamp. On a
    # CANONICAL shape the clamp equals PAGE_FRAMES and the pool fits it, the cache
    # degenerates to fully-resident by design (§9.7), and nothing evicts — so running this
    # witness there and reporting FAIL would be reporting the engine working as designed.
    # It is UNMEASURABLE (exit 2), named, with the build line that produces the right shape.
    # CHECKED BEFORE `valid_samples`, deliberately: on a fully-resident shape the sampler
    # can legitimately see nothing to report, and "no samples" is the wrong sentence for it.
    if pool_pages <= clamp:
        print(f"UNMEASURABLE: this shape cannot force an eviction — the act's {pool_pages}-page "
              f"pool fits the {clamp}-frame residency clamp, so the cache is fully resident by "
              f"design and the pigeonhole below would be vacuous ({len(seen)} distinct pages "
              f"over {valid_samples} samples). Build the fixture shape: "
              f"`STRESS_EVICT=1 ./build.sh` (writes s4.stress.bin / s4.stress.lst).")
        return 2
    if valid_samples == 0:
        print("FAIL: no valid Page_Table samples (guard never satisfied)")
        return 1

    pigeonhole = len(seen) > clamp
    if not pigeonhole:
        print(f"FAIL: no eviction proven — distinct resident pages {sorted(seen)} "
              f"(= {len(seen)}) never exceeded the {clamp}-frame clamp "
              f"({valid_samples} samples)")
        return 1
    first = (f"; first at frame +{first_eviction[0]}: evicted {first_eviction[1]} admitting "
             f"{first_eviction[2]}" if first_eviction else "")
    print(f"PHASE 1: eviction proven — {len(seen)} distinct pages "
          f"> {clamp} frames; directly observed evictions: "
          f"{sorted(evicted_pages) or '(transition not sampled)'}{first} "
          f"[{valid_samples} per-frame samples over {PHASE1_FRAMES} frames]")

    # ---- PHASE 2: one scroll burst, famine-triaged ----
    await b.call("emulator/press", {"buttons": ["right"], "frames": BURST_FRAMES})
    if await in_fault():
        print("PHASE 2: known AllocFrame famine on scroll burst (OPEN DEBT — "
              "P-1 class, see the adjudication ledger); witness PASS stands on "
              "Phase 1")
        print("PASS (with known famine)")
        return 0
    table = await read(b, a_page_table, pool_pages)
    resident = {i for i, f in enumerate(table) if f != not_resident}
    reloaded = resident - seen if not seen >= resident else resident & evicted_pages
    print(f"PHASE 2: scroll burst clean — resident now {sorted(resident)}"
          + (f"; evicted-then-reloaded observed: {sorted(reloaded)}" if reloaded else ""))
    print("PASS")
    return 0


def _cli() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=os.path.join(AEON, "s4.stress.bin"))
    ap.add_argument("--lst", default=os.path.join(AEON, "s4.stress.lst"))
    args = ap.parse_args()
    rom_path, lst_path = Path(args.rom).resolve(), Path(args.lst).resolve()
    # A MISSING FIXTURE IS A NAMED REFUSAL, NOT A TRACEBACK. The defaults are the STRESS
    # shape on purpose — that is the shape this witness is ABOUT — and that shape is
    # off-canonical, so an ordinary checkout does not have it lying around.
    for label, q in (("ROM", rom_path), ("listing", lst_path)):
        if not q.is_file():
            print(f"evict_witness: SETUP — no {label} at {q}. This witness grades the "
                  f"forced-eviction fixture shape; build it with `STRESS_EVICT=1 ./build.sh` "
                  f"(writes s4.stress.bin / s4.stress.lst), or point --rom/--lst at one.",
                  file=sys.stderr)
            return 2
    inst = AetherInstance(str(rom_path), symbols=str(lst_path))
    try:
        sock = inst.start()
        if inst.cart_note:
            print(inst.cart_note)
        return asyncio.run(main(sock, rom_path, lst_path))
    finally:
        inst.reap()


if __name__ == "__main__":
    raise SystemExit(_cli())
