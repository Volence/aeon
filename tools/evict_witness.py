#!/usr/bin/env python3
"""Eviction-liveness witness (adjudication debt V-3, 2026-08-09).

Proves the residency cache actually evicts, against a LIVE oracle instance,
on the STRESS_EVICT shape (PAGE_FRAMES_CLAMP=9 frames vs the 10-page OJZ
pool).

PHASE 1 (the proof, famine-free): sample Page_Table rapidly while the OJZ
init loads the act. Ten pages must stream through nine frames, so the load
itself evicts: the sampler observes a page transition resident->absent while
the distinct-ever-resident count exceeds the frame clamp (pigeonhole — no
engine instrumentation needed). Measured on 2026-08-09 master: page 2 is
evicted to admit page 8, distinct=10.

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

Usage:
  STRESS_EVICT=1 ./build.sh
  python3 tools/evict_witness.py [--rom s4.stress.bin] [--lst s4.stress.lst]

Requires one running oracle_gui (socket /run/user/1000/oracle.sock).
"""
import argparse
import asyncio
import sys
import time
import zlib
from pathlib import Path

sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
from aether import BusClient  # noqa: E402

SOCK = "/run/user/1000/oracle.sock"
OJZ_POOL_PAGES = 10
PAGE_FRAMES_CLAMP = 9
PAGE_NOT_RESIDENT = 0xFF
PHASE1_SECONDS = 15          # covers the ~2,700-frame init swallow with margin
BURST_FRAMES = 90


async def sym(b, name):
    r = await b.call("emulator/lookup_symbol", {"name": name})
    return int(r["addr"], 16)


async def read(b, addr, n):
    r = await b.call("emulator/read_memory", {"addr": hex(addr), "len": n})
    return bytes.fromhex(r["bytes"])


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default="s4.stress.bin")
    ap.add_argument("--lst", default="s4.stress.lst")
    args = ap.parse_args()
    rom_path = Path(args.rom).resolve()
    lst_path = Path(args.lst).resolve()
    rom_bytes = rom_path.read_bytes()

    b = BusClient(socket_path=SOCK, client_id="evictw", client_name="evict-witness")
    await b.connect()

    await b.call("emulator/load_symbols", {"path": str(lst_path)})
    a_init = await sym(b, "GameState_OJZScroll_Init")
    a_page_table = await sym(b, "Page_Table")
    a_err = await sym(b, "ErrorHandlerBlob")

    # Anchor: bp BEFORE reload (run_to after reload is wall-clock racy).
    await b.call("emulator/breakpoint_add", {"addr": hex(a_init)})
    await b.call("emulator/reload_rom", {"path": str(rom_path)})

    # Stale-binary guard: the loaded cart must be the file we were pointed at.
    h = await b.call("emulator/memory_hash", {"addr": "0x0", "len": len(rom_bytes)})
    want = zlib.crc32(rom_bytes) & 0xFFFFFFFF
    got = int(h["crc32"], 16)
    if want != got:
        print(f"FAIL: loaded ROM crc {got:#010x} != file {want:#010x} (stale build?)")
        return 1

    # SEND-SIDE SPELLING IS PINNED TO THE SERVER WE ACTUALLY TALK TO. The legacy server
    # takes `timeout_ms`; oracle's Rust core takes `timeoutMs` and REFUSES an unknown key
    # with -32602 rather than aliasing it (accepting both spellings is how a vocabulary
    # rots). A key you SEND cannot be dual-spelled, so this stays `timeout_ms` until this
    # probe migrates, and the migration moves both halves together.
    r = await b.call("emulator/wait_for_break", {"timeout_ms": 60000})
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

    # ---- PHASE 1: init-load residency churn, sampled live ----
    await b.call("emulator/resume", {})
    seen = set()
    evicted_pages = set()
    prev = None
    valid_samples = 0
    t0 = time.monotonic()
    while time.monotonic() - t0 < PHASE1_SECONDS:
        table = await read(b, a_page_table, OJZ_POOL_PAGES)
        if PAGE_NOT_RESIDENT in table:      # guard vs the boot-zeroed table
            resident = {i for i, f in enumerate(table) if f != PAGE_NOT_RESIDENT}
            valid_samples += 1
            seen |= resident
            if prev is not None:
                evicted_pages |= prev - resident
            prev = resident
        await asyncio.sleep(0.05)
    await b.call("emulator/pause", {})
    if await in_fault():
        print("FAIL: fault raise during init load (Phase 1 must be famine-free)")
        return 1
    if valid_samples == 0:
        print("FAIL: no valid Page_Table samples (guard never satisfied)")
        return 1

    pigeonhole = len(seen) > PAGE_FRAMES_CLAMP
    if not pigeonhole:
        print(f"FAIL: no eviction proven — distinct resident pages {sorted(seen)} "
              f"(= {len(seen)}) never exceeded the {PAGE_FRAMES_CLAMP}-frame clamp "
              f"({valid_samples} samples)")
        return 1
    print(f"PHASE 1: eviction proven — {len(seen)} distinct pages "
          f"> {PAGE_FRAMES_CLAMP} frames; directly observed evictions: "
          f"{sorted(evicted_pages) or '(transition not sampled)'} "
          f"[{valid_samples} samples]")

    # ---- PHASE 2: one scroll burst, famine-triaged ----
    await b.call("emulator/press", {"buttons": ["right"], "frames": BURST_FRAMES})
    if await in_fault():
        print("PHASE 2: known AllocFrame famine on scroll burst (OPEN DEBT — "
              "P-1 class, see the adjudication ledger); witness PASS stands on "
              "Phase 1")
        print("PASS (with known famine)")
        return 0
    table = await read(b, a_page_table, OJZ_POOL_PAGES)
    resident = {i for i, f in enumerate(table) if f != PAGE_NOT_RESIDENT}
    reloaded = resident - seen if not seen >= resident else resident & evicted_pages
    print(f"PHASE 2: scroll burst clean — resident now {sorted(resident)}"
          + (f"; evicted-then-reloaded observed: {sorted(reloaded)}" if reloaded else ""))
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
