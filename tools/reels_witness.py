#!/usr/bin/env python3
"""reels_witness — does the ACTIVE reel rate table actually drive the column buffer?

The claim is NOT "the table and the routine reach the ROM" (tools/reels_gate.py proves
that, byte for byte, without an emulator). It is that `OJZ_Reels_Fill`, once active,
genuinely writes REEL_BAND_COUNT DIFFERENT, INDEPENDENTLY-ADVANCING values into
`Parallax_Vscroll_Column_Buf`'s BG words — i.e. that two adjacent 16-px strips on
screen are showing genuinely different vertical offsets of the background, changing at
genuinely different rates, rather than the smooth ripple every OTHER per-column
mechanism in this tree already produces (SceneVDeform.Columns / Rocking / Perspective) —
AND that the table those rates come from is the one the running engine SELECTED, not the
one this file happens to know about.

    ⚠ WHAT THIS FILE USED TO DO, AND WHY IT WAS THE WORST AVAILABLE FAILURE. Until
    2026-09-04 it carried `SPEEDS = [3, -5, 2, -4, 6]` — a hand copy of `OJZ_REEL_SPEEDS`,
    the FALLBACK demo table — and compared every band against it unconditionally. Since
    aeon 09d964c7 a scene document can author its own rates, and `OJZ_Reels_Fill` selects
    a per-scene table by walking `EditorReelBindings_<CAP>` against
    `Parallax_Current_Config`. Pointed at a ROM whose active table is an AUTHORED one
    carrying different rates, the old file went RED — it accused the feature of failing at
    the exact moment the authoring worked. A witness that fails in that direction is worse
    than no witness: a red instrument is read as a broken feature, and the feature gets
    "fixed" until it matches the instrument's stale copy.

    THE RULE THAT REPLACES IT: DERIVE THE EXPECTED RATES FROM THE BOUND SCENE, NEVER TYPE
    THEM. Nothing in this file is a rate. Every number below is read out of
    `games/sonic4/config/constants.emp`, out of the listing, out of the ROM image, or out
    of the running machine's RAM.

HOW THE ACTIVE TABLE IS RESOLVED, and this is the whole widening. `OJZ_Reels_Fill`'s
`.bind` walk (games/sonic4/data/effects/ojz_effects.emp) reads
`EditorReelBindings_<CAP>` as (config, rates) longs until a ZERO config long, comparing
each config against `Parallax_Current_Config` — the pointer the engine holds to the
ACTIVE parallax config — and keeps `OJZ_Reel_Speed` on a miss. This file mirrors that
loop in Python over the ROM IMAGE, against the config it reads out of live RAM, and
then requires the ENGINE to have reached the same answer (register `a2` at the `.bound`
label). Two independent resolutions of one question.

⚠⚠ THE TRAP, and it is the single most important paragraph here. In the MISS pass `d2`
ALSO holds the authored table's address: `.bind` loads the candidate rates pointer
BEFORE it compares the config, so it holds a bound table's address whether or not that
binding matched. MEASURED IN THIS TREE, 2026-09-04, s4.debug.bin — natural (unbound)
config $013DD4: `a2 = $01476C` (OJZ_Reel_Speed, the fallback) while `d2 = $013FCE` (the
authored table). So "the authored table's address appears in a register" is satisfied by
BOTH outcomes and proves NOTHING. Only `a2` separates them. Never assert on `d2`, and
never assert on a signal you have not run the unbound control against.

    THE CONTROL IS PART OF THE INSTRUMENT, not a one-off:

        tools/reels_witness.py <rom> <lst>                      # bound   -> PASS
        tools/reels_witness.py <rom> <lst> --config natural     # unbound -> must FAIL

    The two differ in ONE value, `Parallax_Current_Config`. If the second passes, the
    `--expect authored` assertion is not measuring the binding and this file is decorative.

⚠ AND THE OTHER HALF OF THE SAME TRAP, live in this tree TODAY. The one authored scene
(`games/sonic4/data/editor/effects/ojz_act1_depth.json`) authors `[3, -5, 2, -4, 6]` —
BYTE-IDENTICAL to the fallback demo table. So the per-band DELTA arm below cannot tell
the two tables apart at all: it goes green either way. This file detects that collision
and says so loudly, because a green delta row read as evidence of selection would be
exactly the "true and worthless" reading the `d2` trap produces. When the images
collide, the RESOLUTION arm (Python walk + `a2`) is carrying the entire discrimination.

THE EXPECTATION IS DERIVED FROM `Lag_Frame_Count`, NOT FROM N ITSELF (measured
2026-09-03). `OJZ_Reels_Fill` is called once from `GameState_OJZScroll_Update`'s frame
body (games/sonic4/test/ojz_scroll_test.emp) — that proc has exactly one `rts`, so it
never skips the call on its own. But the LEVEL frame body only ever runs once per
COMPLETE VBlank (`VInt_Level`, `VBlank_Ready=1`); whenever a physical VBlank fires while
the main loop is still mid-frame (`VBlank_Ready=0`), `VInt_Lag` (engine/system/vblank.emp)
runs instead — critical DMA and controller reads only, no level update, hence no
`OJZ_Reels_Fill` call — and still ticks `Frame_Counter` (so `run_frames(N)` genuinely
advances N physical VBlanks every time; nothing is wrong with the harness's frame count).
`VInt_Lag` also ticks `Lag_Frame_Count` (u32, DEBUG-only, engine/ram.emp), which is
therefore the exact count of frames in the just-elapsed window where the fill did NOT
run. So this witness brackets `Lag_Frame_Count` tightly around the same `run_frames` call
it measures across, and multiplies each band's rate by `N - lag_delta` (the MEASURED
execution count), never by N and never by a hardcoded `N - 2`.

THE BG BASE IS SUBTRACTED, not assumed zero. `OJZ_Reels_Fill` stores
`Parallax_Current_Vscroll_BG + phase` into each BG word, so a camera whose BG base moved
between the two samples shifts every band's delta by the same amount. Poking
`Parallax_Current_Config` can start a band lerp, so this is not hypothetical once the
config is forced. The base is read at both sample points and its delta removed; it is
also PRINTED, so a nonzero one is visible rather than silently absorbed.

THERE IS NO HOTKEY. `OJZ_Reel_Speed`/`OJZ_Reels_Fill`'s own header
(games/sonic4/data/effects/ojz_effects.emp) records why: `Debug_BandDemoHotkey`'s header
enumerates every remaining pad chord against this shape and finds none free. So this
witness pokes `OJZ_Reel_Active` directly — `Debug_BandDemoHotkey`'s own header names
this as the alternative to a chord, and `band_witness.py` uses the identical pattern for
`Raster_Pending`/OJZ_BandDemo. `Parallax_Current_Config` is poked the same way and for
the same reason: `Parallax_StartTransition` writes it only on a SECTION CROSSING, and the
scroll test's camera does not cross one (Camera_X is static at $0060 through 300 frames,
measured). The poke is verified to have STUCK at both sample points; a config that moved
under us is UNMEASURABLE, not a result.

    DOES NOT ESTABLISH that a player reaches this state by playing. Both `OJZ_Reel_Active`
    and `Parallax_Current_Config` are poked. Whether a poke-driven witness meets item 10's
    done-test is the owner's and the hub's reading, recorded here rather than assumed.

VACUITY CHECK, mandatory, band_witness.py's own discipline: if every band's delta between
the two samples is the SAME value, either the fill never took effect (the whole buffer is
still Parallax_Update's shared-phase fill) or every rate in the active table collapsed to
one — either way UNMEASURABLE, not a pass.

TWO THINGS THIS DOES NOT ESTABLISH:
  * It reads Work RAM, not the VDP's VSRAM registers. `Vscroll_Write`'s existing,
    unmodified per-frame DMA (engine/level/parallax.emp) is what actually carries this
    buffer to hardware every VBlank; that leg is already exercised by every other scene
    this engine ships (Rocking/Perspective/etc.) and is not re-proven here.
  * It samples ONE representative column per band (the band's first of REEL_COLS_PER_BAND),
    not all VSCROLL_COL_PAIRS. A per-column bug that only hit columns 1-3 of a band would
    pass.

Usage:
    tools/reels_witness.py <rom> <lst> [--expect authored|fallback|auto]
                                       [--config natural|<symbol>|<hex addr>]

    (DEBUG shape only — OJZ_Reel_Active does not exist in a release build's RAM layout.)

    --expect auto (the default) reads the ROM's association table: `authored` if any
    scene bound rates, `fallback` if none. A tree that authors no reels is therefore
    still gradable, against `OJZ_Reel_Speed`, with no flag.

Exit 0 = pass. 1 = a real failure. 2 = UNMEASURABLE.
"""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import add_client_path  # noqa: E402
add_client_path()  # the Aether client, resolved from the suite root; loud if absent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aether import BusClient
from aether_instance import aether_emulator, read_bytes, write_bytes, run_to_addr
from raster_cost_probe import parse_lst
# THE SAME derivations tools/reels_gate.py grades the ROM with, imported rather than
# re-implemented: two copies of "what does the source declare" is two places to drift
# from the source. `Unmeasurable` travels with them so this file's refusals read alike.
import reels_gate as G

SETTLE_FRAMES = 180                          # into real gameplay before poking anything
WARMUP_FRAMES = 8                            # let the poked config + fill settle
SAMPLE_GAP_FRAMES = 30                       # frames between the two samples
BOUND_LABEL_SUFFIX = "$OJZ_Reels_Fill$bound"  # the local label a2 is read at


class Unmeasurable(G.Unmeasurable):
    pass


def local_label(lst, suffix):
    """A sigil LOCAL label (`$<module>$<Proc>$<local>`) out of the listing.

    `parse_lst` deliberately drops every name containing `$`, so a proc-local label is
    invisible to it. Matched by SUFFIX rather than by full name so a module rename does
    not silently stop finding it; ambiguity is refused rather than resolved by picking.
    """
    hits = {}
    for line in Path(lst).read_text(errors="replace").splitlines():
        if not line.startswith("(0) "):
            continue
        try:
            addrpart, namepart = line[4:].split(" :", 1)
            addr = int(addrpart.split("/", 1)[1], 16)
        except (ValueError, IndexError):
            continue
        name = namepart.strip().rstrip(":")
        if name.endswith(suffix):
            hits[name] = addr & 0xFFFFFF
    if not hits:
        raise Unmeasurable(
            f"no label ending in {suffix!r} in {lst}. This witness reads register a2 AT "
            f"that label — it is the only signal that separates a binding HIT from a MISS "
            f"(d2 holds the candidate either way) — so without it there is nothing to "
            f"measure, and grading the deltas alone would be the vacuous half")
    if len(hits) > 1:
        raise Unmeasurable(
            f"{len(hits)} labels end in {suffix!r} ({sorted(hits)}) — refusing to pick one, "
            f"since the wrong one would report a2 from a different point in the routine")
    return next(iter(hits.values()))


def parse_bindings(rom, addr, limit_longs=256):
    """`OJZ_Reels_Fill`'s `.bind` loop, in Python, over the ROM image.

    Deliberately the SAME shape as the assembly: read a config long, stop on zero, else
    read the rates long that follows and keep walking. A parser that read the table as a
    fixed-length array would disagree with the engine the day the table's declared length
    and its terminator disagree, which is exactly the case worth catching.
    """
    out = []
    i = 0
    while i < limit_longs:
        off = addr + i * 4
        if off + 8 > len(rom):
            raise Unmeasurable(
                f"the association table at ${addr:06X} runs past the end of the "
                f"{len(rom)}-byte ROM without a zero terminator")
        cfg = int.from_bytes(rom[off:off + 4], "big")
        if cfg == 0:
            return out
        out.append((cfg, int.from_bytes(rom[off + 4:off + 8], "big")))
        i += 2
    raise Unmeasurable(
        f"the association table at ${addr:06X} has no zero terminator within "
        f"{limit_longs} longs")


def resolve(bindings, config, fallback_addr):
    """The engine's own selection rule: first matching config wins, else the fallback."""
    for cfg, rates in bindings:
        if cfg == config:
            return rates, True
    return fallback_addr, False


def signed_rates(rom, addr, count):
    """`count` signed bytes out of the ROM at `addr` — the ACTIVE table's rates.

    This is the only place expected rates come from, and it is downstream of the
    resolution above. Nothing here knows what the numbers are supposed to be.
    """
    if addr + count > len(rom):
        raise Unmeasurable(
            f"rate table at ${addr:06X} + {count} bytes runs past the end of the "
            f"{len(rom)}-byte ROM")
    return [b - 256 if b >= 128 else b for b in rom[addr:addr + count]]


def bg_word(buf, column):
    """The BG word for one 16-px column-pair. Format: 4 bytes per pair, [FG hi, FG lo,
    BG hi, BG lo] — Parallax_Vscroll_Column_Buf's own layout (parallax.emp Step 5b)."""
    off = column * 4 + 2
    return (buf[off] << 8) | buf[off + 1]


async def run(sock, lst, rom_image, expect, config_arg):
    bands = G.emp_const(G.GAME_CONSTANTS, "REEL_BAND_COUNT")
    cols_per_band = G.emp_const(G.GAME_CONSTANTS, "REEL_COLS_PER_BAND")
    # VSCROLL_COL_PAIRS is `SCREEN_WIDTH / 16` (engine/level/parallax.emp), not a literal
    # this file's `.emp` const reader can parse — but ojz_effects.emp carries a build-time
    # ensure that REEL_BAND_COUNT * REEL_COLS_PER_BAND == VSCROLL_COL_PAIRS, so the
    # product IS the pair count, guaranteed by the build rather than assumed here.
    col_pairs = bands * cols_per_band
    buf_len = col_pairs * 4

    sym = parse_lst(lst)
    bound_pc = local_label(lst, BOUND_LABEL_SUFFIX)
    for need in ("OJZ_Reel_Active", "OJZ_Reel_Speed", "Parallax_Current_Config",
                 "Parallax_Current_Vscroll_BG", "Parallax_Vscroll_Column_Buf",
                 "Lag_Frame_Count"):
        if need not in sym:
            raise Unmeasurable(f"`{need}` is not in {lst}")
    # the association table's symbol name is act-qualified; take it from the listing
    binds = sorted(n for n in sym if n.startswith("EditorReelBindings_"))
    if len(binds) != 1:
        raise Unmeasurable(
            f"expected exactly one `EditorReelBindings_*` symbol in the listing, found "
            f"{binds!r}. OJZ_Reels_Fill names ONE by hand (act 1's); with a second act's "
            f"table present this witness cannot tell which one the routine walks")
    bind_sym = binds[0]
    bind_addr, fallback_addr = sym[bind_sym], sym["OJZ_Reel_Speed"]
    bindings = parse_bindings(rom_image, bind_addr)

    if expect == "auto":
        expect = "authored" if bindings else "fallback"
    print(f"`{bind_sym}` at ${bind_addr:06X}: {len(bindings)} binding(s) "
          + ", ".join(f"cfg ${c:06X} -> rates ${r:06X}" for c, r in bindings)
          + f"; fallback `OJZ_Reel_Speed` at ${fallback_addr:06X}")
    print(f"expecting the ACTIVE table to be the {expect.upper()} one")

    # what to force Parallax_Current_Config to. `natural` leaves whatever the scene
    # resolved on its own — which is the UNBOUND control, and the only difference between
    # the control and the test run.
    if config_arg == "auto":
        config_arg = "natural" if expect == "fallback" else None
    if config_arg is None:
        if not bindings:
            raise Unmeasurable(
                "no scene binds reel rates in this ROM, so there is no bound config to "
                "force — run with --expect fallback (or --config natural) to grade the "
                "fallback path this bake actually exercises")
        poke_config = bindings[0][0]
    elif config_arg == "natural":
        poke_config = None
    elif config_arg in sym:
        poke_config = sym[config_arg]
    else:
        try:
            poke_config = int(config_arg, 16)
        except ValueError:
            raise Unmeasurable(
                f"--config {config_arg!r} is neither `natural`, a symbol in the listing, "
                f"nor a hex address")

    b = BusClient(socket_path=sock, client_id="reelsw", client_name="reels_witness")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})
    await b.call("emulator/reset", {})
    await b.call("emulator/run_frames", {"frames": SETTLE_FRAMES})

    async def read_u32(addr):
        return int(await read_bytes(b, addr, 4), 16)

    async def read_u16(addr):
        return int(await read_bytes(b, addr, 2), 16)

    if poke_config is not None:
        await write_bytes(b, sym["Parallax_Current_Config"], f"{poke_config:08X}")
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["OJZ_Reel_Active"]), "value": 1, "width": 1})
    await b.call("emulator/run_frames", {"frames": WARMUP_FRAMES})

    active = await read_bytes(b, sym["OJZ_Reel_Active"], 1)
    if int(active, 16) == 0:
        return 1, ["OJZ_Reel_Active reads 0 after the write — the poke did not take"]

    config = await read_u32(sym["Parallax_Current_Config"])
    if poke_config is not None and config != poke_config:
        raise Unmeasurable(
            f"Parallax_Current_Config was poked to ${poke_config:06X} but reads "
            f"${config:06X} after {WARMUP_FRAMES} frames — something (a section crossing, "
            f"a staged transition promoting) rewrote it, so this run is not measuring the "
            f"config it set out to")
    want_rates_addr, hit = resolve(bindings, config, fallback_addr)
    rates = signed_rates(rom_image, want_rates_addr, bands)
    fallback_rates = signed_rates(rom_image, fallback_addr, bands)
    print(f"Parallax_Current_Config = ${config:06X} ({'poked' if poke_config is not None else 'natural'})"
          f" -> walk {'HIT' if hit else 'MISS'} -> rates at ${want_rates_addr:06X} = {rates}")

    fails = []

    # ---- ASSERTION 1: the outcome the caller expects. THIS is the one that differs
    # between the bound and unbound runs; everything else below is satisfied by both.
    if expect == "authored" and not hit:
        fails.append(
            f"expected the AUTHORED path but Parallax_Current_Config ${config:06X} matches "
            f"no binding in `{bind_sym}` — OJZ_Reels_Fill keeps the fallback "
            f"`OJZ_Reel_Speed` (${fallback_addr:06X}). This is the UNBOUND outcome")
    if expect == "fallback" and hit:
        fails.append(
            f"expected the FALLBACK path but Parallax_Current_Config ${config:06X} matched "
            f"a binding in `{bind_sym}`, selecting the authored table at "
            f"${want_rates_addr:06X}")

    # ---- ASSERTION 2: the ENGINE resolved it the same way. a2 at `.bound`, never d2:
    # d2 holds a candidate rates pointer on the MISS path too (see the header).
    await run_to_addr(b, bound_pc, f"{BOUND_LABEL_SUFFIX} (a2 = the selected rate table)",
                      max_frames=600)
    regs = await b.call("emulator/registers", {})
    pc = int(regs["pc"].lstrip("$").removeprefix("0x"), 16) & 0xFFFFFF
    if pc != bound_pc:
        raise Unmeasurable(
            f"run_to reported reaching ${bound_pc:06X} but the machine is at ${pc:06X}; a2 "
            f"is only the SELECTED table at that exact instruction")
    a2 = int(regs["a2"].lstrip("$").removeprefix("0x"), 16) & 0xFFFFFF
    d2 = int(regs["d2"].lstrip("$").removeprefix("0x"), 16) & 0xFFFFFF
    print(f"at {BOUND_LABEL_SUFFIX} (${bound_pc:06X}): a2 = ${a2:06X}, d2 = ${d2:06X} "
          f"(d2 is NOT evidence — .bind loads a candidate before comparing, so it holds a "
          f"bound table's address on the MISS path too)")
    if a2 != want_rates_addr:
        fails.append(
            f"the engine selected ${a2:06X} but resolving `{bind_sym}` against "
            f"Parallax_Current_Config ${config:06X} in Python gives ${want_rates_addr:06X}. "
            f"Two independent walks of one table disagree — suspect the SceneCfgN "
            f"`offsetof(hdr) == 0` identity the comparison rests on")

    # ---- ASSERTION 3: those rates actually drive the buffer.
    if rates == fallback_rates and hit:
        print(f"\n  ⚠ NOTE: the authored table at ${want_rates_addr:06X} and the fallback "
              f"at ${fallback_addr:06X} hold THE SAME rates {rates}. The per-band delta "
              f"rows below therefore CANNOT tell the two tables apart — they go green on "
              f"either. Assertions 1 and 2 are carrying the whole discrimination in this "
              f"bake; author different rates into the bound scene to make the deltas "
              f"discriminating too.")

    async def sample():
        raw = bytes.fromhex(await read_bytes(b, sym["Parallax_Vscroll_Column_Buf"], buf_len))
        if len(raw) != buf_len:
            raise Unmeasurable(f"read {len(raw)} bytes, wanted {buf_len}")
        return raw

    lag1, bg1, buf1 = (await read_u32(sym["Lag_Frame_Count"]),
                       await read_u16(sym["Parallax_Current_Vscroll_BG"]), await sample())
    await b.call("emulator/run_frames", {"frames": SAMPLE_GAP_FRAMES})
    lag2, bg2, buf2 = (await read_u32(sym["Lag_Frame_Count"]),
                       await read_u16(sym["Parallax_Current_Vscroll_BG"]), await sample())

    config_after = await read_u32(sym["Parallax_Current_Config"])
    if config_after != config:
        raise Unmeasurable(
            f"Parallax_Current_Config moved from ${config:06X} to ${config_after:06X} "
            f"INSIDE the sample window — the two samples were taken under two different "
            f"rate tables and their delta is not a rate")

    lag_delta = lag2 - lag1
    if lag_delta < 0:
        return 1, [f"Lag_Frame_Count went BACKWARDS ({lag1} -> {lag2}) — u32 wrap or a "
                   "reset landed inside the sample window; the measurement is invalid"]
    fill_executions = SAMPLE_GAP_FRAMES - lag_delta
    if fill_executions <= 0:
        return 1, [f"Lag_Frame_Count says {lag_delta} lag frames out of "
                   f"{SAMPLE_GAP_FRAMES} requested — OJZ_Reels_Fill would have run "
                   f"{fill_executions} times, which cannot be measured"]

    bg_delta = (bg2 - bg1) & 0xFFFF
    print(f"\nLag_Frame_Count: {lag1} -> {lag2} (delta {lag_delta}) over "
          f"{SAMPLE_GAP_FRAMES} requested frames -> OJZ_Reels_Fill actually ran "
          f"{fill_executions} times (this, not the requested frame count, is what "
          f"each band's expectation is multiplied by)")
    print(f"Parallax_Current_Vscroll_BG: {bg1:#06x} -> {bg2:#06x} (delta {bg_delta % 256} "
          f"mod 256) — OJZ_Reels_Fill composes this into every BG word, so it is "
          f"SUBTRACTED from each observed delta rather than assumed zero")
    print(f"sampled {SAMPLE_GAP_FRAMES} frames apart, one representative column per band "
          f"(column = band * {cols_per_band}):")
    deltas = []
    for band in range(bands):
        col = band * cols_per_band
        v1, v2 = bg_word(buf1, col), bg_word(buf2, col)
        # the phase accumulator is a BYTE (wraps mod 256); the word delta modulo 256 is
        # the comparable quantity regardless of how many times it wrapped
        delta = (v2 - v1 - bg_delta) % 256
        want = (rates[band] * fill_executions) % 256
        deltas.append(delta)
        ok = delta == want
        print(f"  band {band} (col {col}): BG {v1:#06x} -> {v2:#06x}, phase delta {delta} "
              f"(mod 256), rate {rates[band]:+d} x {fill_executions} actual runs = "
              f"{want}  {'OK' if ok else 'MISMATCH'}")
        if not ok:
            fails.append(f"band {band}: phase delta {delta}, the active table's rate "
                         f"{rates[band]:+d} x {fill_executions} runs wants {want}")

    if len(set(deltas)) == 1:
        raise Unmeasurable(
            "VACUOUS: every band's delta is identical — either OJZ_Reel_Active never took "
            "effect (Parallax_Update's shared-phase fill is still running unopposed) or "
            "the ACTIVE table's rates collapsed to one. This is exactly the property "
            "tools/reels_gate.py's ROM-level distinctness check exists to rule out before "
            "an emulator is ever involved; if this fires while that gate is green, the "
            "divergence is between the ROM and this build's listing, not the mechanism.")
    print(f"\nvacuity check: {len(set(deltas))} distinct band deltas — the instrument "
          f"sees independently-advancing strips")
    return (1, fails) if fails else (0, [])


def main():
    args = sys.argv[1:]
    pos = [a for a in args if not a.startswith("--")]

    def opt(flag, default=None):
        return args[args.index(flag) + 1] if flag in args else default

    if len(pos) < 2:
        print(__doc__.split("Usage:", 1)[1].split("Exit 0", 1)[0].strip())
        return 2
    rom, lst = pos[0], pos[1]
    expect = opt("--expect", "auto")
    if expect not in ("authored", "fallback", "auto"):
        print(f"reels_witness: UNMEASURABLE — --expect must be authored|fallback|auto "
              f"(got {expect!r})")
        return 2
    config_arg = opt("--config", "auto")

    rom_image = Path(rom).read_bytes()
    try:
        with aether_emulator(rom) as sock:
            rc, fails = asyncio.run(run(sock, lst, rom_image, expect, config_arg))
    except G.Unmeasurable as e:
        print(f"\nRESULT: UNMEASURABLE — {e}")
        return 2
    print("\nRESULT:", "PASS — the reel bands advance at the rates of the table the "
          "engine actually selected" if rc == 0 else f"FAIL — {fails}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
