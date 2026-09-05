#!/usr/bin/env python3
"""preset_lab_witness — do the lab's PRESET rows actually install a section's preset, and
does the readout on screen tell the truth about it?

THE SUBJECT. `Debug_LabCycleHotkey`'s PRESET arm / `Debug_PresetReadout_Show`
(games/sonic4/test/ojz_scroll_test.emp): stepping the effects lab's one list onto a
PRESET row installs that section's whole EffectsPreset onto the section the camera is
standing in, and paints a section digit plus a verdict glyph under the entry name.

⚠ THE CHORD MOVED ON 2026-09-05, and so did the walk. This tier used to have a chord of
its own (START+A) and a cursor of its own (`Debug_Preset_Index`) counting sections
0..N-1. The owner asked why there were three ways to do one thing, and the three chords
collapsed into ONE list walked by START+LEFT/RIGHT with a single cursor
(`Debug_Lab_Index`) over `.lab_index`, whose rows are {kind, sub-index, four-letter
name}. The preset entries are the LAST rows of that list, so this instrument now:

  * presses START+LEFT, not START+A;
  * walks BACKWARD from the boot cursor 0, which WRAPS straight onto the last row — the
    highest-numbered section's preset — and then steps down through every preset row to
    section 0. That is nine presses that never touch a scene or a raster row, so nothing
    this instrument installs on its way to its subject is a confound. Walking forward
    would have crossed all twenty-eight of them;
  * ends on section 0 for the reason it always did — it is the act's only PATCHED preset,
    the only entry that exercises the verdict's world-anchor arm — and reaching it by
    wrapping is now also the proof that the cursor wraps at LAB_CYCLE_COUNT;
  * derives the preset rows' POSITIONS in the list rather than assuming them: the
    `.lab_index` table is read out of the running ROM at its own listing symbol, split by
    LAB_ENTRY_SIZE, and cross-checked against the listing's own
    `lab_index`..`scene_table` span before a single press is made.

WHY AN INSTRUMENT AND NOT A LINT. The two tiers beside this one each carry a `dc.l` table
and a pytest lane that counts its rows, because a table can drift from the registry it
mirrors. THIS TIER HAS NO TABLE — the cycle list is the act's own section grid, walked by
`Act.sec_grid_ptr + cursor * sizeof(Sec)` — so there is nothing textual to lint and the
only question worth asking is a runtime one: does the press install, and does the glyph
match. That question needs a machine.

WHAT IT MEASURES.
  1. The CURSOR advances, one section per press, and wraps at the act's section count.
  2. The INSTALL is real, read off the engine's own state rather than off the hotkey:
     `Raster_Program` becomes the section's bound program (section 1 -> OJZ_TestRaster,
     section 2 -> OJZ_TestGradient, section 7 -> Raster_Program_None) and
     `Pal_Cycle_Script` becomes section 3's OJZ_ShimmerCycle. These are the cells
     `Raster_VBlank` and `Palette_LoadCycle` write, not cells the hotkey touches.
  3. The READOUT is on screen and correct, byte for byte: VRAM tile
     VRAM_DEBUG_PRESET_READOUT+0 equals the digit sheet's row for the section, and tile +1
     equals the verdict sheet's row for the state the preset is actually in. (Both cells
     moved from 1022-1023 to 957-958 with the consolidation; the four tiles they used to
     share became the entry NAME tag, which this instrument does not sample — see WHAT IT
     DOES NOT MEASURE.)

EVERY EXPECTATION IS DERIVED, NEVER TYPED — and the first draft of this file proves why
the rule is worth the trouble. It carried a hand-typed section-to-verdict table, and TWO
of its seven rows were wrong: it expected `Raster_Program` to hold `Raster_Program_None`
where the engine actually zeroes the cell on the explicit-clear path, and it expected
section 5 to be EMPTY on the strength of a source comment, when section 5's sidecar
binds a real program and the ROM says so. The readout under test was RIGHT both times
and the expectation was wrong. So nothing is typed now:

  * the section list, its length and each `Sec*` come from the LIVE act, walked exactly
    as the hotkey walks it (`Current_Act_Ptr` -> `Act.sec_grid_ptr` + cursor * 66);
  * each preset's `ep_raster` / `ep_patched` / `ep_cycle` are read out of ROM at that
    `Sec`'s own `sec_effects`, and the PARALLAX rung is resolved off the ROM's own
    records the way `Effects_ResolveParallax` resolves it (`Sec.sec_parallax_config` >
    `ep_parallax` > `Act.act_parallax_config`) — so the expected verdict is computed from
    the same four channels the proc reads, by an independent implementation of the
    documented rule. The proc CALLS the engine routine; this side reimplements it, which
    is what makes the two independent. It matters that the rung ladder is walked in full:
    OJZ act 1 sections 7 and 8 share ONE `EffectsPreset`, and differ only in
    `Sec.sec_parallax_config`, so a derivation that stopped at `ep_parallax` would give
    the floor and the control the same answer and could never fail on the defect the
    arrow verdict exists to fix;
  * both glyph sheets are read out of ROM at their own listing symbols, so a glyph edited
    in the source moves this instrument's expectation with it and cannot go stale-green;
  * `Raster_Program_None` and `Pal_Cycle_None` come from the listing, not from a literal.

WHAT IT DOES NOT MEASURE.
  * It does not sample the ENTRY NAME tag (the four-letter word above the two cells it
    does sample). That tag is painted by Debug_TierTags_Update from `Debug_Lab_Index`,
    it is armed by the same held START this instrument's chord supplies, and checking it
    would be worth doing — it is simply not this file's subject, and adding it would mean
    reading the alphabet sheet and the row's own name bytes. Booked as unmeasured here
    rather than assumed correct.
  * It does not look at pixels, and it does not read the sprite attribute table. It DOES
    check the two glyph objects' own SSTs — built (code_addr non-zero) and at the screen
    coordinates the readout declares — which closes the "the tile is right but nothing
    points at it" half; what is left unsampled is the SAT build and the pixels.
  * It does not look at the parallax config's CONTENTS. The arrow verdict is a record
    IDENTITY test on both sides — "is the config this section resolves the act's default
    or not" — so an authored scene whose numbers happen to equal the default's is
    reported (and painted) as an arrow by both. That is the glyph's stated promise, not a
    gap between the two implementations.
  * It does not reach the BLIND verdict. Section 0's water anchors are at world Y 224/314
    and a boot lands the camera above them, so the honest reading at cursor 0 is LIVE.
    Producing a BLIND requires a warp deeper into the act, which is a bigger instrument;
    the arithmetic behind the verdict IS checked, on the LIVE side of the same branch.
  * It runs the DEBUG shape only, which is the only shape any of this exists in.

IT REFUSES rather than guesses on: a served ROM that does not match the file on disk, a
cursor that does not advance, a `Raster_Pending` still staged after the settle (VBlank
never consumed the install), and a readout tile that is all zeroes (never painted).

USAGE
    python3 tools/preset_lab_witness.py --rom s4.debug.bin --lst s4.debug.lst

Exit codes: 0 measured and every check matched its derived expectation; 1 measured and at
least one did not; 2 REFUSED (unmeasurable).
"""
from __future__ import annotations

import argparse, asyncio, re, sys, zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient                      # noqa: E402
from aether_instance import aether_emulator       # noqa: E402
from raster_cost_probe import parse_lst           # noqa: E402

BOOT_FRAMES = 180        # into real gameplay before the first press
SETTLE_FRAMES = 6        # let VBlank consume Raster_Pending and the glyph DMAs land
TILE = 32                # one 8x8 4bpp tile
VRAM_DEBUG_PRESET_READOUT = 957  # games/sonic4/vram.toml, region debug_preset_readout

# The verdict glyph indices, which are also row numbers in `.verdict_font`.
V_NONE, V_BLIND, V_LIVE, V_PARALLAX = 0, 1, 2, 3
V_NAMES = {V_NONE: "bar/none", V_BLIND: "X/blind", V_LIVE: "diamond/live",
           V_PARALLAX: "arrow/parallax"}

SEC_SIZE = 34                  # sizeof(Sec) — engine/structs.emp's own stride pin
SEC_EFFECTS = 0x1C             # Sec.sec_effects
SEC_PARALLAX_CONFIG = 0x0C     # Sec.sec_parallax_config — rung 1 of the resolve
EP_RASTER, EP_PATCHED, EP_CYCLE = 0x08, 0x0C, 0x10   # EffectsPreset field offsets
EP_PARALLAX = 0x04             # EffectsPreset.ep_parallax — rung 2 of the resolve
ACT_SEC_GRID, ACT_GRID_W, ACT_GRID_H = 0x00, 0x04, 0x06
ACT_PARALLAX_CONFIG = 0x16     # Act.act_parallax_config — rung 3, and the BASELINE
ACT_HDR = 0x1A                 # enough of the Act header to reach act_parallax_config
PATCH_ANCHOR_NONE = 0x7FFF     # engine/effects/raster_dsl.emp; pinned below against ROM
RASTER_MAX_PATCH = 4
SCREEN_HEIGHT = 224            # engine/system/constants.emp
SST_SIZE = 0x50                # sizeof(Sst) — engine/objects/sst.emp's own (size:) assertion
SST_CODE_ADDR, SST_X_POS, SST_Y_POS = 0x00, 0x02, 0x06   # dispatch word + the two 16.16 Coords
NUM_SYSTEM = 8                 # engine/system/constants.emp; pinned against the listing below
PRESET_ROW_Y = 32              # DEBUG_PRESET_READOUT_Y — the second readout row
PRESET_CELL_X = (16, 24)       # DEBUG_PRESET_READOUT_X and +8


def lst_symbol(lst: str, name: str) -> int | None:
    """Find one symbol's address in the listing's own address table.

    `raster_cost_probe.parse_lst` is used for everything else, but it does not carry the
    MANGLED local-label names (`$module$proc$label`) — it returns 1035 of the listing's
    2378 names. `.verdict_font` is one of those, and EXPORTING it purely so a parser could
    see it would put a name in the release deb2 appendix for a test's convenience. So the
    one line is read here instead.
    """
    tail = f" {name} : "
    for line in open(lst, encoding="utf-8", errors="replace"):
        if line.startswith(tail):
            return int(line.split(" : ", 1)[1].split()[0], 16)
    return None


def u32(raw: bytes, off: int = 0) -> int:
    return int.from_bytes(raw[off:off + 4], "big")


async def rd(b, addr: int, n: int) -> bytes:
    r = await b.call("emulator/read_memory", {"addr": hex(addr), "len": n})
    raw = bytes.fromhex(r["bytes"].replace("0x", "").replace("$", ""))
    if len(raw) != n:
        raise RuntimeError(f"read_memory({addr:#x}, {n}) returned {len(raw)} bytes")
    return raw


async def rd_vram(b, addr: int, n: int) -> bytes:
    r = await b.call("emulator/read_vram", {"addr": hex(addr), "len": n})
    raw = bytes.fromhex(r["bytes"].replace("0x", "").replace("$", ""))
    if len(raw) != n:
        raise RuntimeError(f"read_vram({addr:#x}, {n}) returned {len(raw)} bytes")
    return raw


LAB_SOURCE = Path(__file__).resolve().parent.parent / "games/sonic4/test/ojz_scroll_test.emp"
HOLD_FRAMES = 2          # see press_chord: one VIDEO frame can be a lag frame
RELEASE_FRAMES = 2
PRESS_RETRIES = 3


async def press_chord(b) -> None:
    """Hold START+LEFT for HOLD_FRAMES video frames, then release for RELEASE_FRAMES.

    Both buttons together IS the chord: START is read from `Ctrl_1_Held` and LEFT from
    `Ctrl_1_Press`, and on the first frame of a fresh hold the press latch carries both.
    The RELEASED frames after it are what make the next press an edge again.

    LEFT and not RIGHT — see the header: backward from the boot cursor 0 wraps straight
    onto the last preset row, so the walk never crosses a scene or a raster row and
    installs nothing that could confound its own subject.

    TWO FRAMES AND NOT ONE, and this was measured rather than chosen: at one frame each
    the third press of a run was swallowed while the other nine landed. `play_input`
    covers VIDEO frames, and a LAG frame runs the main loop once across two of them — so a
    one-frame hold can be released before `Input_Tick` ever samples it. Installing
    section 2's 96-line dense ramp is exactly the kind of frame that lags. The hotkey did
    nothing wrong there; the instrument did, and holding across the lag is the fix.
    Holding two frames still steps ONCE, because the step is edge-triggered on the press
    latch and the second frame carries only the held bits.
    """
    r = await b.call("emulator/play_input",
                     {"rows": [{"start": 0, "end": HOLD_FRAMES,
                                "buttons": ["start", "left"], "port": 0}]})
    if int(r.get("frames", -1)) != HOLD_FRAMES:
        raise RuntimeError(f"play_input advanced {r.get('frames')} frames, wanted {HOLD_FRAMES}")
    await b.call("emulator/run_frames", {"frames": RELEASE_FRAMES})


async def step_cursor(b, sym, want_row: int) -> tuple[bool, int]:
    """Press START+LEFT until `Debug_Lab_Index` reads `want_row`, at most PRESS_RETRIES.

    Returns (arrived, presses_spent). A step that needs more than one press is REPORTED
    rather than hidden — a retry loop that is silent about retrying is how a systematically
    dropped press turns into a green run.
    """
    for n in range(1, PRESS_RETRIES + 1):
        await press_chord(b)
        if (await rd(b, sym["Debug_Lab_Index"], 1))[0] == want_row:
            return True, n
    return False, PRESS_RETRIES


def source_const(name: str) -> int:
    """One `const NAME = <int>` out of the lab's own source.

    The list's SHAPE — how wide a row is, which byte is the kind, what value means PRESET
    — is compile-time and reaches neither the symbol table nor the ROM as a symbol, so it
    is read from the file that declares it. Every value read this way is cross-checked
    against the running ROM below (row width x row count against the listing's own
    lab_index..scene_table span, and the preset rows' own kind bytes), so a source that
    drifted from the build under test cannot pass silently.
    """
    if not LAB_SOURCE.is_file():
        raise RuntimeError(f"{LAB_SOURCE} does not exist; the lab list's shape cannot be read")
    m = re.search(rf"^\s*const\s+{re.escape(name)}\s*=\s*(\d+)\s*(?://.*)?$",
                  LAB_SOURCE.read_text(), re.M)
    if m is None:
        raise RuntimeError(f"could not find `const {name}` in {LAB_SOURCE.name} — this "
                           f"instrument derives the lab list's shape from it and must not "
                           f"guess")
    return int(m.group(1))


async def run(sock: str, rom: str, lst: str) -> tuple[int, list[str]]:
    b = BusClient(socket_path=sock, client_id="preslab", client_name="preset_lab_witness")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})
    sym = parse_lst(lst)

    # --- the stale-shim refusal: the served ROM must be the file on disk ---
    st = await b.call("emulator/status", {})
    on_disk = Path(rom).stat().st_size
    served = st.get("romBytes")
    if served is not None and int(served) != on_disk:
        return 2, [f"the server is serving {served} ROM bytes but {rom} is {on_disk} on "
                   f"disk — a stale instance; nothing below would be about this build"]

    # --- the glyph sheets, read out of the ROM the machine is running ---
    digit_sym = "$games.sonic4.ojz_scroll_test$Debug_PresetReadout_Show$digit_font"
    verdict_sym = "$games.sonic4.ojz_scroll_test$Debug_PresetReadout_Show$verdict_font"
    digit_at = sym.get(digit_sym) or lst_symbol(lst, digit_sym)
    verdict_at = lst_symbol(lst, verdict_sym)
    for name, at in ((digit_sym, digit_at), (verdict_sym, verdict_at)):
        if at is None:
            return 2, [f"`{name}` is not in {lst} — the readout's expectations are read "
                       f"from the ROM's own sheets, so without it nothing can be derived"]
    digits = [await rd(b, digit_at + i * TILE, TILE) for i in range(10)]
    verdicts = [await rd(b, verdict_at + i * TILE, TILE) for i in range(len(V_NAMES))]
    if len({bytes(d) for d in digits}) != 10 or len({bytes(v) for v in verdicts}) != len(V_NAMES):
        return 2, ["the glyph sheets read out of ROM contain duplicate rows — either the "
                   "symbols moved or the read is wrong; a duplicate makes every tile "
                   "comparison below ambiguous rather than false"]

    if "System_Slots" not in sym:
        return 2, ["System_Slots is not in the listing — the readout's two glyph objects "
                   "are claimed by address off it, so their existence cannot be checked"]

    await b.call("emulator/reset", {})
    await b.call("emulator/run_frames", {"frames": BOOT_FRAMES})

    fails: list[str] = []
    cur = (await rd(b, sym["Debug_Lab_Index"], 1))[0]
    if cur != 0:
        return 2, [f"Debug_Lab_Index reads {cur} at boot, not 0 — boot's Work-RAM clear "
                   f"did not happen or something else writes this cell; every step below "
                   f"is indexed off it"]
    print(f"boot: Debug_Lab_Index = 0 (Work RAM cleared), {BOOT_FRAMES} frames in")

    # --- WHERE THE PRESET ROWS ARE, read off the running ROM's own table ---
    # The listing carries both ends of `.lab_index`, so its byte length is a fact about
    # THIS build; the row width and the PRESET kind value come from the source that
    # declares them, and the two are cross-checked before anything is pressed. A source
    # that drifted from the build fails here rather than sending the walk to a scene row.
    try:
        entry_size = source_const("LAB_ENTRY_SIZE")
        cycle_count = source_const("LAB_CYCLE_COUNT")
        kind_preset = source_const("LAB_KIND_PRESET")
    except RuntimeError as e:
        return 2, [str(e)]
    lab_at = sym.get("Debug_LabCycleHotkey.lab_index") or \
        lst_symbol(lst, "Debug_LabCycleHotkey.lab_index")
    scene_at = lst_symbol(lst, "$games.sonic4.ojz_scroll_test$Debug_LabCycleHotkey$scene_table")
    if lab_at is None or scene_at is None:
        return 2, ["`Debug_LabCycleHotkey.lab_index` and/or its `.scene_table` are not in "
                   f"{lst} — the preset rows' positions are derived from that span and "
                   "cannot be guessed"]
    span = scene_at - lab_at
    if span != entry_size * cycle_count:
        return 2, [f"the listing's lab_index..scene_table span is {span} B but the source "
                   f"declares LAB_ENTRY_SIZE {entry_size} x LAB_CYCLE_COUNT {cycle_count} "
                   f"= {entry_size * cycle_count} B — {LAB_SOURCE.name} is not the source "
                   f"of this build, so nothing derived from it is about the machine here"]
    table = await rd(b, lab_at, span)
    preset_rows = [i for i in range(cycle_count)
                   if table[i * entry_size] == kind_preset]
    if not preset_rows or preset_rows != list(range(preset_rows[0], cycle_count)):
        return 2, [f"the PRESET rows of `.lab_index` are {preset_rows}, which is not a "
                   f"contiguous run ending at the last row. This instrument walks BACKWARD "
                   f"from the wrap so it never crosses a scene or raster row; if the preset "
                   f"block moved, that property is gone and the walk has to be redesigned "
                   f"rather than re-pointed"]
    row_of_section = {table[i * entry_size + 1]: i for i in preset_rows}
    print(f"lab list: {cycle_count} rows of {entry_size} B at ${lab_at:06X}; "
          f"preset rows {preset_rows[0]}..{cycle_count - 1} -> sections "
          f"{sorted(row_of_section)}")

    # --- the act's own section table, read the way the hotkey walks it ---
    act = u32(await rd(b, sym["Current_Act_Ptr"], 4))
    if not act:
        return 2, ["Current_Act_Ptr is 0 after boot — no act is loaded, so there is no "
                   "cycle list to walk and nothing below means anything"]
    grid = await rd(b, act, ACT_HDR)
    sec_grid = u32(grid, ACT_SEC_GRID)
    act_parallax = u32(grid, ACT_PARALLAX_CONFIG)
    if not act_parallax:
        return 2, ["Act.act_parallax_config is 0 — the arrow verdict is decided by "
                   "comparing each section's RESOLVED parallax config against the act "
                   "default, and with no default there is nothing to compare against"]
    count = int.from_bytes(grid[ACT_GRID_W:ACT_GRID_W + 2], "big") * \
            int.from_bytes(grid[ACT_GRID_H:ACT_GRID_H + 2], "big")
    if not 1 <= count <= 10:
        return 2, [f"the act reports {count} sections; this instrument walks the whole "
                   f"cycle and the readout clamps at 10, so anything else needs the "
                   f"clamp handled explicitly rather than assumed"]
    none_prog = sym["Raster_Program_None"]
    none_cycle = sym["Pal_Cycle_None"]
    print(f"act at ${act:06X}: {count} sections, table ${sec_grid:06X}; "
          f"Raster_Program_None ${none_prog:06X}, Pal_Cycle_None ${none_cycle:06X}; "
          f"act_parallax_config ${act_parallax:06X}")

    async def preset_of(cursor: int) -> tuple[int, int, int, int, int]:
        """(EffectsPreset*, ep_raster, ep_patched, ep_cycle, RESOLVED parallax*) from ROM.

        The parallax pointer is the three-rung resolve `Effects_ResolveParallax` performs
        — Sec.sec_parallax_config > ep_parallax > Act.act_parallax_config — reimplemented
        here off the ROM's own records, which is the point: the proc under test CALLS that
        engine routine, and this side must not. Sections 7 and 8 of OJZ act 1 share ONE
        EffectsPreset, so a derivation that stopped at `ep_parallax` would give the floor
        and the control the same answer and could never fail on the defect this checks.
        """
        sec = sec_grid + cursor * SEC_SIZE
        ep = u32(await rd(b, sec + SEC_EFFECTS, 4))
        if not ep:
            raise RuntimeError(f"section {cursor} has sec_effects == 0")
        f = await rd(b, ep, 0x14)
        cfg = u32(await rd(b, sec + SEC_PARALLAX_CONFIG, 4))    # (1) the section's own
        if not cfg:
            cfg = u32(f, EP_PARALLAX)                           # (2) the preset's
        if not cfg:
            cfg = act_parallax                                  # (3) the act default
        return ep, u32(f, EP_RASTER), u32(f, EP_PATCHED), u32(f, EP_CYCLE), cfg

    async def expected_verdict(raster: int, patched: int, cycle: int,
                               parallax: int) -> tuple[int, str]:
        """The documented rule, implemented independently of the .emp that implements it.

        The patched arm reads the LIVE latched banks, which is the whole point: whether a
        world-anchored boundary is on screen is a property of where the camera is, and
        this instrument has to ask it the same way and at the same moment the proc does.
        """
        if patched:
            anchors = await rd(b, sym["Effects_World_Y"], RASTER_MAX_PATCH * 2)
            lines = await rd(b, sym["Effects_Screen_L"], RASTER_MAX_PATCH * 2)
            for i in range(RASTER_MAX_PATCH):
                a = int.from_bytes(anchors[i * 2:i * 2 + 2], "big")
                l = int.from_bytes(lines[i * 2:i * 2 + 2], "big", signed=True)
                if a != PATCH_ANCHOR_NONE and 0 <= l < SCREEN_HEIGHT:
                    return V_LIVE, f"patched channel {i} anchored at world Y {a} is on screen line {l}"
            return V_BLIND, "a patched program whose every channel latched off screen"
        if raster != none_prog:
            return V_LIVE, f"a static program at ${raster:06X}"
        if cycle != none_cycle:
            return V_LIVE, f"a palette cycle at ${cycle:06X}"
        # The PARALLAX rung, asked last for the same reason the proc asks it last: the
        # arrow refines the bar and outranks nothing. LIVE > BLIND > PARALLAX > NONE.
        if parallax != act_parallax:
            return V_PARALLAX, (f"a background scene of its own at ${parallax:06X} "
                                f"(the act default is ${act_parallax:06X})")
        return V_NONE, ("no raster, no patched program, no palette cycle, and the act's "
                        "own default background")

    if sorted(row_of_section) != list(range(count)):
        return 2, [f"the act reports {count} sections but `.lab_index`'s preset rows name "
                   f"{sorted(row_of_section)} — the list and the act disagree, so a walk "
                   f"over one of them says nothing about the other. "
                   f"tools/test_lab_index_lint.py fails the build on this too"]

    # The act's sections in DESCENDING order, which is what walking BACKWARD from the boot
    # cursor visits: press one, wrap onto the last row (the highest section), then step
    # down. Section 0 is last for the reason it always was — it is the act's only PATCHED
    # preset, so it is the only entry that exercises the verdict's world-anchor arm — and
    # the FIRST press is now also the proof that the cursor wraps at LAB_CYCLE_COUNT.
    retries = 0
    for want_cursor in sorted(row_of_section, reverse=True):
        want_row = row_of_section[want_cursor]
        ok, spent = await step_cursor(b, sym, want_row)
        retries += spent - 1
        await b.call("emulator/run_frames", {"frames": SETTLE_FRAMES})

        got = (await rd(b, sym["Debug_Lab_Index"], 1))[0]
        if not ok or got != want_row:
            fails.append(f"Debug_Lab_Index {got} after {spent} press(es), wanted row "
                         f"{want_row} (section {want_cursor}) — the cursor did not step")
            break                       # every later expectation is indexed off the cursor

        ep, raster, patched, cycle, parallax = await preset_of(want_cursor)
        want_verdict, why = await expected_verdict(raster, patched, cycle, parallax)

        pending = u32(await rd(b, sym["Raster_Pending"], 4))
        if pending != 0:
            fails.append(f"section {want_cursor}: Raster_Pending still ${pending:06X} after "
                         f"{SETTLE_FRAMES} frames — VBlank never consumed the install, so "
                         f"Raster_Program below is the PREVIOUS section's")

        # THE INSTALL IS REAL, read off a cell the hotkey never writes. On the explicit
        # -clear path Raster_VBlank ZEROES Raster_Program rather than storing the empty
        # program's address (raster.emp's own doc; the first draft of this file expected
        # the pointer and was wrong), so the expectation forks on the sentinel.
        prog = u32(await rd(b, sym["Raster_Program"], 4))
        if not patched:
            want_prog = 0 if raster == none_prog else raster
            if prog != want_prog:
                fails.append(f"section {want_cursor}: Raster_Program ${prog:06X}, wanted "
                             f"${want_prog:06X} (ep_raster ${raster:06X})")
        if cycle != none_cycle:
            cyc = u32(await rd(b, sym["Pal_Cycle_Script"], 4))
            if cyc != cycle:
                fails.append(f"section {want_cursor}: Pal_Cycle_Script ${cyc:06X}, wanted "
                             f"this preset's ep_cycle ${cycle:06X}")

        # --- the readout, on screen ---
        dig = await rd_vram(b, (VRAM_DEBUG_PRESET_READOUT + 0) * TILE, TILE)
        ver = await rd_vram(b, (VRAM_DEBUG_PRESET_READOUT + 1) * TILE, TILE)
        if dig == b"\0" * TILE or ver == b"\0" * TILE:
            fails.append(f"section {want_cursor}: a readout tile is all zeroes — the cell "
                         f"was never painted, which is not the same as painted wrong")
        else:
            if dig != digits[want_cursor]:
                shown = next((i for i, d in enumerate(digits) if d == dig), None)
                fails.append(f"section {want_cursor}: the digit cell shows "
                             f"{'digit ' + str(shown) if shown is not None else 'no digit in the sheet'}")
            if ver != verdicts[want_verdict]:
                shown = next((i for i, v in enumerate(verdicts) if v == ver), None)
                fails.append(f"section {want_cursor}: verdict shows "
                             f"{V_NAMES.get(shown, 'no glyph in the sheet')}, wanted "
                             f"{V_NAMES[want_verdict]} — {why}")
        # --- the two glyph OBJECTS: built, and where the readout says they are ---
        # Slots NUM_SYSTEM-4 and NUM_SYSTEM-3, claimed by address (the System pool has no
        # allocator). Checked once, on the first step, because they are built once.
        if want_cursor == max(row_of_section):
            for i, (slot, x) in enumerate(zip((NUM_SYSTEM - 4, NUM_SYSTEM - 3), PRESET_CELL_X)):
                sst = sym["System_Slots"] + slot * SST_SIZE
                blob = await rd(b, sst, 0x10)
                code = int.from_bytes(blob[SST_CODE_ADDR:SST_CODE_ADDR + 2], "big")
                px = int.from_bytes(blob[SST_X_POS:SST_X_POS + 2], "big")
                py = int.from_bytes(blob[SST_Y_POS:SST_Y_POS + 2], "big")
                if code == 0:
                    fails.append(f"readout cell {i}: System slot {slot} has code_addr 0 — "
                                 f"the glyph object was never built, so the VRAM tile below "
                                 f"is correct but nothing draws it")
                elif (px, py) != (x, PRESET_ROW_Y):
                    fails.append(f"readout cell {i}: System slot {slot} sits at screen "
                                 f"({px},{py}), wanted ({x},{PRESET_ROW_Y})")
            print(f"    glyph objects: System slots {NUM_SYSTEM-4}/{NUM_SYSTEM-3} built at "
                  f"screen y {PRESET_ROW_Y}")

        print(f"  cursor {want_cursor}: preset ${ep:06X} · Raster_Program ${prog:06X} · "
              f"verdict {V_NAMES[want_verdict]} ({why})")

    if retries:
        print(f"  NOTE: {retries} extra press(es) were needed across {count} steps — "
              f"a press landing entirely inside a lag frame is not sampled by Input_Tick. "
              f"This is an instrument property, not a hotkey one; a step that needed more "
              f"than {PRESS_RETRIES} would have failed above.")

    return (1 if fails else 0), fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    a = ap.parse_args()
    for p in (a.rom, a.lst):
        if not Path(p).is_file():
            print(f"preset_lab_witness: {p} does not exist", file=sys.stderr)
            return 2
    print(f"preset_lab_witness: {a.rom} "
          f"({Path(a.rom).stat().st_size} B, crc32 "
          f"{zlib.crc32(Path(a.rom).read_bytes()):08x})")
    with aether_emulator(a.rom, symbols=a.lst) as sock:
        code, fails = asyncio.run(run(sock, a.rom, a.lst))
    if code == 2:
        print("\nREFUSED — unmeasurable:")
    elif fails:
        print(f"\nFAILED — {len(fails)} check(s):")
    for f in fails:
        print(f"  - {f}")
    if code == 0:
        print("\nOK — every press stepped the cursor, installed that section's channels, "
              "and painted a digit + verdict that match the ROM's own glyph sheets and the "
              "preset's own fields.")
    return code


if __name__ == "__main__":
    sys.exit(main())
