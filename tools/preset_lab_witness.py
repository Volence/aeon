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
name}. The preset entries are the last BLOCK of that list, so this instrument now:

  * presses START+LEFT, not START+A;
  * walks BACKWARD from the boot cursor 0, which WRAPS onto the LAST row of the list, and
    then steps down through every preset row to section 0. Walking forward would have
    crossed all twenty-eight scene and raster rows.

    THE PRESET BLOCK IS NO LONGER THE TAIL. It was when this file was written; e3e40a4a
    (2026-09-05) appended row 37, a WLINE entry, one row past it. So the crossed rows are
    now DERIVED (`crossed`, below) and stepped as a named preamble, and they are held to
    the property that mattered rather than to the position that used to imply it: SCENE
    and WLINE share one dispatch arm which only blanks the readout and installs a
    parallax config, and the `.preset` arm unconditionally re-does both on every press, so
    a crossed row of either kind cannot survive into a measurement. A crossed RASTER row
    is REFUSED, not tolerated;
  * ends on section 0, and the WRAP half of that is unchanged: the last press is the proof
    that the cursor wraps at LAB_CYCLE_COUNT.

    ⚠ CORRECTED 2026-09-09 (parcel/section-effects-record-fix). The rest of this bullet used
    to read "for the reason it always did — it is the act's only PATCHED preset, the only
    entry that exercises the verdict's world-anchor arm". THAT REASON EXPIRED. It is quoted
    rather than deleted so a reader who remembers it meets the correction. Section 7 is the
    act's SECOND patched preset: `OJZ_Preset_Sec7` binds `patched: OJZ_WorldWater`
    (games/sonic4/data/effects/ojz_effects.emp, at `OJZ_Preset_Sec7`) with world anchors on
    channels 2 and 3,
    landed 2026-09-05 — the same change that made claim 2 in the paragraph below stale, and
    it was corrected there but not here. So section 0 is no longer the ONLY entry exercising
    the world-anchor arm; ending on it is now a wrap proof plus a habit, not a coverage
    argument. What still IS unique to section 0: it is the only patched section whose two
    channels are 0 and 1 (section 7 uses 2 and 3), which is what the ch0/ch1 band-map arm of
    tools/effects_gates.py measures there;
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
     `Raster_Program` becomes the section's bound program and `Pal_Cycle_Script` becomes
     the section's `ep_cycle`. These are the cells `Raster_VBlank` and `Palette_LoadCycle`
     write, not cells the hotkey touches. (The parenthesis here used to name four
     bindings by hand. THREE OF THE FOUR ARE STILL RIGHT, checked against this build's
     listing rather than assumed: section 1 -> OJZ_TestRaster $14684, section 2 ->
     OJZ_TestGradient $14A0C, section 3's cycle -> OJZ_ShimmerCycle $147A2, all three
     matching what the first successful run measured. The FOURTH, "section 7 ->
     Raster_Program_None", is stale: section 7's preset is PATCHED now, and that is what
     puts a BLIND on the readout below. The list is gone anyway — every binding is derived
     at runtime, so hand-copying them could only ever go wrong, and one of four did.)
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
    as the hotkey walks it (`Current_Act_Ptr` -> `Act.sec_grid_ptr` + cursor * 34, the
    `SEC_SIZE` this file pins below — the "* 66" this line used to say was a stale stride
    contradicted by this file's own code, booked as LS-20 by the 2026-09-06 lens sweep);
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
  * ⚠ THIS BULLET USED TO SAY "it does not reach the BLIND verdict", on the reasoning
    that section 0's water anchors are at world Y 224/314 and a boot lands the camera
    above them. That is still true OF SECTION 0 — cursor 0 reads LIVE, patched channel 0
    anchored at world Y 224 on screen line 88 — but the claim was written before this
    file had ever completed a run, and the first one that did (2026-09-06) reaches BLIND
    at CURSOR 7, whose preset is patched and whose every channel latches off screen. All
    four verdict glyphs are therefore exercised in one walk: arrow/parallax at 8, X/blind
    at 7, diamond/live via a static program at 6/5/4/2/1, via a palette cycle at 3, and
    via a patched world anchor at 0. Nothing was added to reach BLIND; the act's content
    moved under a claim nothing was running to contradict.
  * It runs the DEBUG shape only, which is the only shape any of this exists in.

IT REFUSES rather than guesses on: a served ROM that does not match the file on disk, a
cursor that does not advance, a `Raster_Pending` still staged after the settle (VBlank
never consumed the install), and a readout tile that is all zeroes (never painted).

AND IT NO LONGER MANUFACTURES AN ABSENCE (2026-09-06). This file's FIRST run in its
intended runner — `tools/nightly_effects_gates.sh`, lane two — refused with
"`$games.sonic4.ojz_scroll_test$Debug_PresetReadout_Show$verdict_font` is not in
s4.debug.lst". The symbol was in the listing, twice, spelled
`Debug_PresetReadout_Show.verdict_font`: 625fdc74 had EXPORTED the label two days after
this file was written, which moves a local from the `$`-mangled spelling to the dotted
one, and the hard-coded query went stale. A `None` from a lookup had been rendered as a
fact about the ROM. Every listing name is now resolved through `resolve_local`, which
accepts EITHER spelling, and no absence is believed until `lookup_control` has proven the
reader works on a symbol known to be present. A future spelling change therefore fails
saying "`verdict_font` IS in the listing — as `X` — but under neither spelling this
instrument knows", not "the symbol is missing".

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


LAB_MODULE = "games.sonic4.ojz_scroll_test"   # this file's own module path, for the mangle

_LST_TABLE: dict[str, dict[str, int]] = {}


def lst_symbols(lst: str) -> dict[str, int]:
    """Every name in the listing's own address table, MANGLED locals included.

    `raster_cost_probe.parse_lst` is used for everything else, but it reads the listing's
    BODY lines (`(0) <idx>/<hex> :  Name:`) and drops any name containing `$` — it returns
    1094 of this listing's 2375 names. The `$module$proc$label` locals are the missing
    half, so the address table at the foot of the listing is read here instead. Two
    readers over two different sections of one file is also what makes the control below
    possible.
    """
    cached = _LST_TABLE.get(lst)
    if cached is not None:
        return cached
    out: dict[str, int] = {}
    for line in open(lst, encoding="utf-8", errors="replace"):
        # ` <name> : <hex> <class> |` — names never contain a space.
        if not line.startswith(" ") or " : " not in line:
            continue
        name, rest = line[1:].split(" : ", 1)
        if not name or " " in name:
            continue
        try:
            addr = int(rest.split()[0], 16)
        except (ValueError, IndexError):
            continue
        out.setdefault(name, addr & 0xFFFFFF)
    _LST_TABLE[lst] = out
    return out


class SymbolSpelling(RuntimeError):
    """A symbol lookup that failed, carrying WHY rather than only THAT."""


def lookup_control(lst: str) -> None:
    """POSITIVE CONTROL on the listing reader, asked BEFORE any absence is believed.

    ---- WHY THIS EXISTS, STATED AS IT WAS FOUND (2026-09-06) ----
    The first run of this instrument in its intended runner refused with
    "`$games.sonic4.ojz_scroll_test$Debug_PresetReadout_Show$verdict_font` is not in
    s4.debug.lst". The symbol WAS in the listing, twice, spelled
    `Debug_PresetReadout_Show.verdict_font`. A lookup that returned None had been rendered
    as an absence, and the instrument manufactured the very fact it was refusing over.

    So the mechanism is now tested on something known present before any name is called
    missing, and the two controls fail for reasons no single label can cause:

      1. `Debug_PresetReadout_Show` — the proc under test. Resolved TWICE, by two readers
         over two different sections of the same file (`lst_symbols` over the address
         table, `parse_lst` over the body). If either comes up empty, or they disagree on
         the address, the reader is broken and every absence below would be manufactured.
      2. The mangled population. Locals reach the table as `${LAB_MODULE}$proc$label`; if
         the table holds ZERO such names, the mangling convention itself moved and every
         mangled candidate this file builds is wrong for a reason that has nothing to do
         with any one label.

    Raises SymbolSpelling — never returns a "couldn't check" that could read as green.
    """
    table = lst_symbols(lst)
    if not table:
        raise SymbolSpelling(
            f"the address table of {lst} parsed to ZERO names — the listing's format "
            f"moved under this reader. Nothing below could tell a missing symbol from a "
            f"missing parser, so no absence is reported")
    probe = "Debug_PresetReadout_Show"           # the proc under test; must be emitted
    body = parse_lst(lst)
    a, b_ = table.get(probe), body.get(probe)
    if a is None or b_ is None or a != b_:
        raise SymbolSpelling(
            f"the listing reader failed its own control: `{probe}` (the proc under test, "
            f"which must be in any build carrying this instrument's subject) reads "
            f"{'absent' if a is None else f'${a:06X}'} from the address table and "
            f"{'absent' if b_ is None else f'${b_:06X}'} from the listing body. Two "
            f"readers over one file disagree, so this run cannot distinguish a symbol "
            f"that moved from a parser that broke")
    mangled = sum(1 for n in table if n.startswith(f"${LAB_MODULE}$"))
    if mangled == 0:
        raise SymbolSpelling(
            f"the address table of {lst} holds {len(table)} names and NOT ONE of them "
            f"starts with `${LAB_MODULE}$` — the local-label mangling convention moved. "
            f"Every mangled candidate this instrument builds is stale for that reason "
            f"alone, so a per-label absence below would name the wrong cause")
    print(f"lookup control: {len(table)} names in the address table "
          f"({mangled} mangled under ${LAB_MODULE}$), `{probe}` agrees at ${a:06X} "
          f"across both readers")


def resolve_local(lst: str, proc: str, label: str) -> tuple[int, str]:
    """A proc-local label's address under EITHER spelling the toolchain may emit.

    ---- WHICH SPELLING, AND WHY BOTH ----
    A `.local` inside a proc reaches the listing under one of two names, and WHICH ONE is
    a property of whether the label is EXPORTED — which is in turn a property of whether
    some OTHER proc references it, i.e. of the code's shape and not of the label:

        not exported ->  `$games.sonic4.ojz_scroll_test$Debug_PresetReadout_Show$digit_font`
        exported     ->  `Debug_PresetReadout_Show.verdict_font`

    `.verdict_font` was the first form until 625fdc74 (2026-09-05) exported it — not for a
    parser's convenience, but because that refactor gave `Debug_PresetReadout_Blank` two
    cross-proc `lea Debug_PresetReadout_Show.verdict_font(pc)`, and a cross-proc reference
    to a local REQUIRES the export. The dotted form is therefore the current truth AND it
    is anchored by a real code dependency rather than by taste. The same commit is why
    `.lab_index` is dotted (three procs walk it) while `.scene_table`, used only inside
    its own proc, is still mangled.

    So neither spelling is hard-coded. Pinning the dotted one alone would have re-broken
    the instant anyone deleted `Debug_PresetReadout_Blank`; pinning the mangled one is the
    defect this parcel is repairing. Accepting both costs one dict lookup and survives the
    change in either direction with no edit here. (Deriving the address from the ROM's own
    `lea` displacement instead would survive a RENAME too, and was rejected: it trades a
    legible name for an instruction-encoding dependency that fails by silently pointing at
    the wrong bytes rather than by refusing.)

    ---- THE RELEASE-LEAK WORRY THIS REPLACES, RE-MEASURED 2026-09-06 ----
    The deleted `lst_symbol` justified reading the mangled line by saying that exporting a
    label "purely so a parser could see it would put a name in the release deb2 appendix
    for a test's convenience". THE WORRY IS REAL — build.sh's own corrected note (2026-09-04)
    records that the RELEASE ROM carries the appendix too, and that adding a symbol to a
    DEBUG-gated block moves `s4.bin`'s bytes because the NAMES land there. It simply did
    not materialise for this label: `verdict_font` occurs 0 times in `s4.lst` and 2 times
    in `s4.debug.lst`, because the sheet lives inside `if DEBUG == 1` and so emits no
    label at all in the release shape. (The proc labels themselves DO survive — both
    `Debug_PresetReadout_Show` and `Debug_PresetReadout_Blank` are in `s4.lst`, at one
    shared address, as zero-byte procs.)

    ⚠ AND DO NOT RE-CHECK THIS BY GREPPING THE ROM. `strings s4.bin | grep verdict_font`
    returns 0 — and so does the same grep for `Debug_PresetReadout_Show`, `Raster_Program`
    and `Sonic`, in BOTH ROMs, because deb2 does not store names as raw ASCII. A ROM-side
    grep for a symbol name cannot fail, so it is not evidence. The LISTING is the sound
    check: it is what convsym consumes, so a name absent from `s4.lst` cannot be in
    `s4.bin`'s appendix.

    Returns (address, the spelling that resolved). Raises SymbolSpelling naming the REAL
    cause — never "the symbol is missing" when it is merely spelled differently.
    """
    table = lst_symbols(lst)
    cands = [f"{proc}.{label}", f"${LAB_MODULE}${proc}${label}"]
    for c in cands:
        if c in table:
            return table[c], c

    # NOT an absence until it is proven to be one. `lookup_control` has already shown the
    # reader works, so the question left is only "under what name".
    elsewhere = sorted(n for n in table if label in n)
    siblings = sorted(n for n in table
                      if n.startswith(f"{proc}.") or n.startswith(f"${LAB_MODULE}${proc}$"))
    tried = " nor ".join(f"`{c}`" for c in cands)
    if elsewhere:
        raise SymbolSpelling(
            f"`{label}` IS in {lst} — as {', '.join('`' + n + '`' for n in elsewhere)} — "
            f"but under neither spelling this instrument knows ({tried}). The label's "
            f"SPELLING changed, the symbol did not go away: adding or removing "
            f"`export .{label}:` in {LAB_SOURCE.name} moves a local between the dotted "
            f"and the $-mangled form, and renaming its proc or module moves it again. "
            f"Re-point `resolve_local`; do not conclude the readout lost its sheet")
    if siblings:
        raise SymbolSpelling(
            f"no name containing `{label}` is in {lst}, but its proc `{proc}` IS emitted "
            f"and carries {len(siblings)} other local(s) — "
            f"{', '.join('`' + n + '`' for n in siblings[:8])}"
            f"{' ...' if len(siblings) > 8 else ''}. So the proc is alive and the LABEL "
            f"was renamed or deleted; tried {tried}")
    raise SymbolSpelling(
        f"neither `{label}` nor any local of `{proc}` is in {lst} (tried {tried}, and the "
        f"reader passed its control above, so this is a real absence). The proc's whole "
        f"`if DEBUG == 1` block is gone, or this is not the DEBUG shape")


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

    # --- the listing reader is proven working before any name is called missing ---
    try:
        lookup_control(lst)
    except SymbolSpelling as e:
        return 2, [str(e)]

    # --- the glyph sheets, read out of the ROM the machine is running ---
    # Both under whichever spelling THIS build emitted — see `resolve_local`. The two
    # sheets currently sit on opposite sides of that fork (`.verdict_font` is exported,
    # `.digit_font` is not), which is exactly why neither is hard-coded.
    try:
        digit_at, digit_sym = resolve_local(lst, "Debug_PresetReadout_Show", "digit_font")
        verdict_at, verdict_sym = resolve_local(lst, "Debug_PresetReadout_Show", "verdict_font")
    except SymbolSpelling as e:
        return 2, [f"{e} — the readout's expectations are read from the ROM's own sheets, "
                   f"so without it nothing can be derived"]
    print(f"glyph sheets: `{digit_sym}` ${digit_at:06X}, `{verdict_sym}` ${verdict_at:06X}")
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
        kind_scene = source_const("LAB_KIND_SCENE")
        kind_wline = source_const("LAB_KIND_WLINE")
    except RuntimeError as e:
        return 2, [str(e)]
    # The same either-spelling resolve, for the same reason: `.lab_index` is exported
    # (three procs walk it) and `.scene_table` is not, and which side of that fork a
    # label sits on is not this instrument's business to remember.
    try:
        lab_at, lab_sym = resolve_local(lst, "Debug_LabCycleHotkey", "lab_index")
        scene_at, scene_sym = resolve_local(lst, "Debug_LabCycleHotkey", "scene_table")
    except SymbolSpelling as e:
        return 2, [f"{e} — the preset rows' positions are derived from the "
                   f"lab_index..scene_table span and cannot be guessed"]
    span = scene_at - lab_at
    if span != entry_size * cycle_count:
        return 2, [f"the listing's lab_index..scene_table span is {span} B but the source "
                   f"declares LAB_ENTRY_SIZE {entry_size} x LAB_CYCLE_COUNT {cycle_count} "
                   f"= {entry_size * cycle_count} B — {LAB_SOURCE.name} is not the source "
                   f"of this build, so nothing derived from it is about the machine here"]
    table = await rd(b, lab_at, span)
    preset_rows = [i for i in range(cycle_count)
                   if table[i * entry_size] == kind_preset]
    if not preset_rows or preset_rows != list(range(preset_rows[0], preset_rows[-1] + 1)):
        return 2, [f"the PRESET rows of `.lab_index` are {preset_rows}, which is not one "
                   f"contiguous run. This instrument steps DOWN through the block one row "
                   f"per press; a split block means the walk visits a non-preset row in the "
                   f"middle of its own subject and has to be redesigned rather than "
                   f"re-pointed"]

    # ---- THE ROWS THE BACKWARD WALK CROSSES BEFORE IT REACHES ITS SUBJECT ----
    # The header's original claim was that the preset block is the LAST of the list, so
    # pressing LEFT from cursor 0 wraps straight onto it and the walk installs nothing.
    # THAT STOPPED BEING TRUE ON 2026-09-05: e3e40a4a appended row 37, a WLINE entry, one
    # row past the presets — two days after this file was written, into a nightly lane
    # that had been jammed since 08-28, so nothing could notice. The claim is not repaired
    # by re-pointing it at "the last row"; it is repaired by deriving the crossed rows and
    # holding them to the property that actually mattered.
    #
    # WHAT ACTUALLY MATTERED is that nothing crossed on the way can survive into a preset
    # measurement. SCENE and WLINE share ONE dispatch arm in Debug_LabCycleHotkey, and
    # that arm does exactly two things: `Debug_PresetReadout_Blank` and
    # `Parallax_StartTransition`. The `.preset` arm then unconditionally re-does both —
    # `Effects_InstallPreset` (which re-resolves and re-installs the parallax config and
    # re-latches the world lines) followed by `Parallax_StartTransition` and
    # `Debug_PresetReadout_Show` — on EVERY preset press. So a crossed SCENE/WLINE row is
    # overwritten by the very next press and cannot reach any expectation below.
    #
    # A crossed RASTER row would NOT qualify and is refused rather than reasoned about:
    # it stages `Raster_Pending` for a program of its own, and this instrument's
    # `Raster_Program` check forks on whether the preset is patched — a case that has
    # never been measured with a foreign program staged into it. If the list grows one,
    # that is a walk to redesign, not a tolerance to widen here.
    crossed = list(range(preset_rows[-1] + 1, cycle_count))
    kind_names = {kind_scene: "SCENE", kind_wline: "WLINE",
                  kind_preset: "PRESET", source_const("LAB_KIND_RASTER"): "RASTER"}
    bad = [(i, table[i * entry_size]) for i in crossed
           if table[i * entry_size] not in (kind_scene, kind_wline)]
    if bad:
        return 2, [f"the backward walk crosses rows {crossed} on its way from the wrap to "
                   f"the preset block, and "
                   + ", ".join(f"row {i} is kind {k} "
                               f"({kind_names.get(k, 'UNKNOWN')})" for i, k in bad)
                   + f". Only SCENE and WLINE are crossable — they share one arm that "
                     f"installs a parallax config and blanks the readout, both of which "
                     f"the next preset press unconditionally re-does. Anything else "
                     f"leaves state this instrument then measures as if the preset had "
                     f"put it there"]
    row_of_section = {table[i * entry_size + 1]: i for i in preset_rows}
    print(f"lab list: `{lab_sym}` / `{scene_sym}`; "
          f"{cycle_count} rows of {entry_size} B at ${lab_at:06X}; "
          f"preset rows {preset_rows[0]}..{preset_rows[-1]} -> sections "
          f"{sorted(row_of_section)}; "
          + (f"crossing {len(crossed)} row(s) to reach them: "
             + ", ".join(f"{i}={kind_names.get(table[i * entry_size], '?')}" for i in crossed)
             if crossed else "the block is the tail of the list, nothing crossed"))

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

    # ---- THE PREAMBLE: the crossed rows, stepped ON PURPOSE ----
    # The first press wraps cursor 0 onto row LAB_CYCLE_COUNT-1, which is the proof that
    # the cursor wraps. If the preset block is no longer the tail (it is not — see
    # `crossed` above), the rows between the wrap and the block are stepped here, one
    # press each, and CHECKED. Letting `step_cursor`'s retry loop absorb them instead
    # would have worked by accident and then printed the lag-frame note below as the
    # explanation for presses that were never dropped — an instrument telling a false
    # causal story about itself, which is the same class of defect as the one this parcel
    # is repairing.
    retries = 0
    for want_row in crossed[::-1]:
        ok, spent = await step_cursor(b, sym, want_row)
        retries += spent - 1
        if not ok:
            got = (await rd(b, sym["Debug_Lab_Index"], 1))[0]
            return 2, [f"the wrap/preamble step to row {want_row} "
                       f"({kind_names.get(table[want_row * entry_size], '?')}) left "
                       f"Debug_Lab_Index at {got} after {spent} press(es) — the walk never "
                       f"reached the preset block, so nothing below was measured"]
        print(f"  crossed row {want_row} "
              f"({kind_names.get(table[want_row * entry_size], '?')})"
              + (f" — the wrap, cursor 0 -> {want_row}" if want_row == cycle_count - 1 else ""))
    await b.call("emulator/run_frames", {"frames": SETTLE_FRAMES})

    # The act's sections in DESCENDING order, which is what stepping DOWN from the preset
    # block's last row visits. Section 0 is last for the reason it always was — it is the
    # act's only PATCHED preset, so it is the only entry that exercises the verdict's
    # world-anchor arm.
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
