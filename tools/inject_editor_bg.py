#!/usr/bin/env python3
"""Inject an editor-authored background over the generated zone BG.

Reads the act's override file ({"layout": [2048 words, blob-local tile
indices], "tiles": [[64 px]...]}) and rewrites that act's
data/generated/<zone>/<act>/zone_bg.bin + bg_tiles.bin in the engine's
conventions (VRAM-absolute indices at BG_TILE_BASE_SLOT, 2-byte BE
byte-length tile blob header).

THE ACT IS A PARAMETER, NOT A CONSTANT (2026-08-27). Every act-dependent name
and path — the output directory, the override file, the emitted module name,
the `embed(...)` path — is derived by `BgActNames` from the zone/act ids in
project.json. `--zone`/`--act` are INDICES into project.json, exactly the
signature tools/effects_gen.py already uses, so an act that is not declared
there is a refusal rather than a silently-empty bake. Defaults are zone 0 /
act 0, which is what the no-argument call site in tools/regenerate-level.sh
gets, so its output is unchanged.

Run by tools/regenerate-level.sh after ojz_strip_gen.py when the act's
override file exists.
"""
import argparse, json, struct, os, sys

# LOCKSTEP: the per-band record layout this tool emits (6 dc.w fields + 8
# bank pointers = 44 bytes) is mirrored by the `bganim_band` struct in
# engine/level/bg_anim.emp (`struct bganim_band`, read field-by-field by
# BgAnim_Update). A record-format change edits BOTH together.
# BG_TILE_BASE_SLOT / BG_TILE_CAPACITY are imported from the generated registry
# mirror — ONE authority (tools/vram_map.py <- games/sonic4/vram.toml), not
# restated literals (the four-copies-of-448 incident). The capacity is 400 since
# EFFECTS-W1 item 9d (the top 48 of the physical 448-slot run became the
# `waterline_strips` region), and was never constants.asm's old 512 nominal:
# the sprite table ($B800) and HScroll table ($BC00) live in the top of the
# $8000-$BFFF region. Do not restate the number here — read it from the import.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vram_map import GAME as _VRAM_MAP_GAME, BG_TILE_BASE_SLOT, BG_TILE_CAPACITY
#: The bank-placement floor, DERIVED from the tool that owns it rather than restated.
#: A literal `16 KiB` sat in the refusal below for two days after the 2026-09-04 raise
#: to 0xC000, invisible to a line-based prose sweep because the figure and its bound
#: word sit on different physical lines of the same message.
from bganim_room import DATA_GROWTH_RESERVE as _BANK_PLACEMENT_FLOOR
assert _VRAM_MAP_GAME == 'sonic4', (
    f"tools/vram_map.py was generated for {_VRAM_MAP_GAME!r}, not sonic4 — "
    "regenerate: python3 tools/gen_vram_map.py --game sonic4 "
    "--toml games/sonic4/vram.toml --py tools/vram_map.py")
# BGANIM_MAX_BANDS — the band ceiling this emitter enforces, and the RELEASE defense
# for BgAnim_Update's walk over BgAnim_LastStep (bg_anim.emp's `assert.w d7, ls,
# #BGANIM_MAX_BANDS` is a DEBUG-only backstop; asserts are zero bytes in the plain
# shape). It was a bare `4` inside the assert message until 2026-08-18.
#
# THREE INDEPENDENT AUTHORITIES HOLD THIS NUMBER, and they must agree:
#   engine/system/constants.emp   pub const BGANIM_MAX_BANDS — sizes engine/ram.emp's
#                                 BgAnim_LastStep array (ram.emp names it, so the array
#                                 cannot drift from THIS one on its own)
#   engine/level/bg_anim.emp      a DELIBERATE module-local mirror — that file is lowered
#                                 STANDALONE by `bg_anim_port` against an empty symbol
#                                 table, so it may not import engine.constants (see the
#                                 note at its own const); it bounds the runtime assert
#   this file                     the emitter's cap, which is what actually keeps a
#                                 too-wide table out of the ROM
#
# They are NOT collapsible: the standalone-port constraint is real and the ram-harvest
# pass cannot reach a CODE module's consts. So this follows RASTER_MAX_PATCH's ruling
# instead — KEEP THE MIRRORS, GATE THE DRIFT. The gate is
# tools/test_bg_emit.py::TestBgAnimBandCeiling, which reads all three and fails on any
# disagreement; before it existed, raising the ceiling HERE alone would have let
# BgAnim_Update walk off the end of BgAnim_LastStep in the release shape with nothing
# to catch it. Named rather than left inline so the gate can import it instead of
# regex-scraping an assert message.
BGANIM_MAX_BANDS = 4

# ── THE SECTION-SIZE CEILING (decision d-9) ────────────────────────────────────
#
# `ojz_bg_anim` is ONE section holding the band table and the bank blob for EVERY
# band in the act. It sits between `OJZ_Palette` and `test_mappings` in the declared
# order (games/sonic4/map.toml), and everything from `Map_TestObj` through
# `Art_Sonic` shifts downstream when it grows — into the room before the `dac_banks`
# anchor. Until the ROM re-layout (2026-08-26) that anchor was $48000 and read as a
# hardware-fixed latch that could not move, which made the room whatever Sonic's art
# left; since the re-layout the anchor is DERIVED from the packed-data end by the
# BANK PLACEMENT RULE in map.toml and re-ruled at every freeze (see the block below).
#
#   BGANIM_SECTION_CEILING — the ROM-room limit, i.e. the owner's ruled authoring
#       budget. Derived (2026-08-24, instrument = the sigil `.lst` + the art blob on
#       disk + map.toml's anchor; NOT the frozen boundary table, whose gaps are
#       allotments and not free space):
#           s4       Art_Sonic 0x2CE60 + 97,472 = 0x44B20 -> $48000 leaves 13,536 B
#           s4.debug Art_Sonic 0x2D6A0 + 97,472 = 0x45360 -> $48000 leaves 11,424 B
#           demo / demo.debug -- no `ojz_bg_anim` section at all (their BgAnim_Table
#                                is games/demo/data/demo_data.emp's own stub)
#       MINIMUM 11,424 B free, + the 2 B the stub already holds = 11,426 B reachable.
#       *** RE-DERIVED 2026-08-26 after the roomy-BG regeneration (aeon 94b384a2). The
#       static background dropped 448 -> 320 unique tiles, freeing 128 x 32 = 4,096 B in
#       exactly this run, so the room GREW: s4 17,264 B free, s4.debug 15,152 B free
#       (the debug shape is the binding one, as always). The 9,394 figure below was
#       derived against the OLD 11,424 and was left stale-low by ~5.7 KB. Owner ruled
#       (2026-08-26, via the hub): raise it, but not to the physical edge -- keep a
#       margin so other content in this run can grow without forcing the re-layout.
#       12,288 B (12 KiB) is that number: 2,864 B of margin under the debug room, and
#       still short of two 8 KB bands (16,384 > 15,152), which remains the re-layout's
#       job. ***
#       Both spans were confirmed to be pure $00 fill in the built image, so spending
#       them does NOT grow the ROM file -- it spends what `Art_Sonic` may grow into.
#       tools/bganim_room.py re-derives this on every build and fails if it stops
#       fitting (which is the revisit d-9 named, and which is what re-derived it).
#       ~15.1 KB of room is ONE band of up to 12 KB per act under the ruled ceiling;
#       a second 8 KB band needs the "banks late, data unbounded" re-layout booked in
#       docs/DEFERRED_WORK.md, not a bigger number here.
#
#   BGANIM_PLACER_CEILING — RETIRED 2026-08-25. Until sigil b0363140 (merge of
#       feat/derived-layout) the chainer measured every section at its FROZEN
#       provisional base and could absorb one 0x400 spread step before `colliding
#       pins`, which capped this section at ~1 KB regardless of ROM room. sigil now
#       re-measures a grown pure-data section at a scratch slot and packs its
#       neighbours downstream (`[layout.provisional-drift]` is a warning, not a
#       stop), so placement no longer bounds a data section. Deleted, not disabled.
#
# THE CHECK TOTALS ALL BANDS, NEVER EACH BAND. `BgAnim_Banks` is one blob for the
# whole act, so a per-band cap is unsound: this zone's own shipped content (32x4 +
# 16x4, recoverable at b0e5a661) passes any generous per-band limit while its SUM is
# 49,242 B. Decision d-6 made that error and this repo's deleted content refuted it.
# Total slots are bounded above by BG_TILE_CAPACITY (400) because bands pack
# contiguously from slot 0 as a prefix of `tiles` -- `validate_band_coherence` is the
# authority -- so the provable worst case is BGANIM_WORST_CASE_BYTES below.
#
# RAISING THIS NUMBER IS NOT A ONE-LINE EDIT: it is bounded by tools/bganim_room.py's
# live derivation, which fails the build if the ceiling exceeds the room. Raised
# 9,394 -> 12,288 on 2026-08-26 under the owner's ruling; the derivation above is what
# licenses it, and bganim_room.py is what keeps it honest if the room ever shrinks.
#
# ── ONE RULED NUMBER AGAIN, PER-SHAPE TABLE KEPT (ROM re-layout, 2026-08-26) ──
#
# Decision d-28-answered (2026-08-26) split the ceiling per shape for one day: the
# showcase parcel widened `band_record` on every band in the tree, `Art_Sonic` landed
# at 0x2F430 in the DEBUG shape, 3,856 B were left before the $48000 anchor, and the
# DEBUG row dropped to the 12,094 B that room held (194 B under d-9's 12,288). The
# owner booked the ROM re-layout (option 2) as the follow-up and it landed the same
# day: the Z80 banks now sit AFTER the data region at LMAs the BANK PLACEMENT RULE in
# games/sonic4/map.toml derives from the packed-data end —
#
#     dac_banks = align_up(max over sound-on shapes of packed_data_end
#                          + DATA_GROWTH_RESERVE + DATA_GROWTH_GRACE, 0x8000)
#
# — so every sound-on shape has at least DATA_GROWTH_RESERVE of room at every freeze,
# and the ceiling no longer depends on Sonic's art size. The reserve was 0x4000
# (16,384 B, two 8 KB bands) from 08-26 until the SECOND re-layout on 2026-09-04,
# which raised it to 0xC000 (49,152 B) and added the 0x8000 GRACE term; see the BANK
# PLACEMENT RULE block in games/sonic4/map.toml for both derivations. Measured at each
# re-layout (both canonical listings; the parcel reports
# docs/superpowers/2026-08-26-rom-relayout-report.md and
# docs/superpowers/2026-09-04-rom-relayout-more-room-report.md carry the full tables):
#
#     date      shape     Art_Sonic  + art blob    = packed end  anchor    room
#     08-26     s4        0x72210    + 97,472      = 0x89ED0     0x90000    24,880 B
#     08-26     s4.debug  0x72A60    + 97,472      = 0x8A720     0x90000    22,752 B
#     09-04     s4        0x72BFC    + 101,056     = 0x8B6BC     0xA8000   115,524 B
#     09-04     s4.debug  0x7355E    + 101,056     = 0x8C01E     0xA8000   114,658 B
#
# Both rows are d-9's 12,288 throughout. The TABLE stays on purpose: the gate is per
# shape and the listing IS the instrument — a third shape, or a renamed listing, must
# be UNMEASURABLE in tools/bganim_room.py, never defaulted to another shape's number.
# That gate also enforces the placement rule itself (`--gate` fails naming the new
# anchor pair the moment a shape's room drops under the reserve), which is the
# re-ruling trigger: move BOTH anchors per the rule.
#
#   BGANIM_SECTION_CEILING_RULED   d-9's budget, RAISED to 20,480 on 2026-09-04 (see
#                                  the block at the constant) — the owner's authoring budget.
#   BGANIM_SECTION_CEILINGS        the per-shape table tools/bganim_room.py gates
#                                  against, keyed by the sigil listing that IS the
#                                  shape's instrument.
#   BGANIM_SECTION_CEILING         what the GENERATOR accepts from the editor: the
#                                  MINIMUM across shapes (== the ruled number while the
#                                  rows agree; it must stay the minimum so a section can
#                                  never pass this emitter and fail one shape's gate).
# ── RAISED 12,288 -> 20,480 (owner "Agrree", 2026-09-04, amending d-9) ────────
#
# THE ASK: a SECOND full-size band alongside the shipped canopy. What that costs is
# derived from this file's own layout constants, never estimated:
#
#     canopy band = 8 cols x 4 rows = 32 slots; a slot is BGANIM_PHASES (8) x
#     BGANIM_TILE_BYTES (32) = 256 B. Two of them = 64 slots = 16,384 B of blob,
#     + BGANIM_COUNT_BYTES (2) + 2 x BGANIM_RECORD_BYTES (44)   = 16,474 B.
#     With the two DEBUG view twins still emitted (2 x (2 + 44)) = 16,654 B.
#
# 20,480 (20 KiB) covers the larger of those with 3,826 B of margin — the SAME shape
# of choice d-9 made at 12,288, which is why it is not sized to 16,654 exactly: the
# margin is what lets the other band grow a row without re-ruling this number.
#
# WHY THIS IS NOW A FREE CHOICE, AND WAS NOT ON 2026-08-26. The block above still
# says a second 8 KB band "needs the re-layout, not a bigger number here" — that was
# TRUE WHEN WRITTEN and is spent: the re-layout landed (483b3e12) and moved the Z80
# banks to 0xA8000. Re-measured live on this tree with tools/bganim_room.py rather
# than trusting that sentence: room is 125,872 B (s4.lst) and 123,430 B
# (s4.debug.lst), and the tool's own verdict is now "binding limit: the ruled
# ceiling — it sits 111,142 B inside the ROM room". The room stopped being the
# constraint; this number is the only thing in the way, which is exactly why it took
# an owner ruling and not a measurement.
#
# STILL BOUNDED, in both directions: bganim_room.py fails the build if the ceiling
# ever exceeds the room again, and test_bg_emit.py holds it <= the provable worst
# case any legal authoring can produce (BGANIM_WORST_CASE_BYTES, 114,866 B).
BGANIM_SECTION_CEILING_RULED = 20480
BGANIM_SECTION_CEILINGS = {
    "s4.lst": BGANIM_SECTION_CEILING_RULED,
    "s4.debug.lst": BGANIM_SECTION_CEILING_RULED,
}
BGANIM_SECTION_CEILING = min(BGANIM_SECTION_CEILINGS.values())

#: Section layout, stated once so every size in this file derives from ONE place:
#: a u16 band count, then a 44-byte record per band (6 u16 header fields + an
#: 8-entry `[*u8; 8]` pointer array), then the concatenated bank blob at 32 bytes
#: per 4bpp tile x 8 phases per slot. Mirrors engine/level/bg_anim.emp's
#: `struct bganim_band` (the LOCKSTEP contract at the head of this file).
BGANIM_COUNT_BYTES = 2
BGANIM_RECORD_BYTES = 44
BGANIM_PHASES = 8
BGANIM_TILE_BYTES = 32
BGANIM_BYTES_PER_SLOT = BGANIM_PHASES * BGANIM_TILE_BYTES     # 256

#: The largest section any legal authoring can produce: every band record present and
#: every BG slot animated. Derived, not asserted -- it bounds the ceilings above.
BGANIM_WORST_CASE_BYTES = (BGANIM_COUNT_BYTES
                           + BGANIM_RECORD_BYTES * BGANIM_MAX_BANDS
                           + BG_TILE_CAPACITY * BGANIM_BYTES_PER_SLOT)


# ── `default_off` AND THE DEBUG VIEW TWINS (owner ask, 2026-09-03) ────────────
#
# THE ASK, in the owner's words: "can we please just get rid of the animated tiles for
# now, they're so distracting? Maybe have one view for horizontal and one for vertical?"
# — and, separately, "it would be nice to see them perspective related instead of just
# timer right now".
#
# THE MECHANISM, and why it is here rather than in the engine. A band's driver and rate
# are BAKED into its 44-byte record, so "run this band off Camera_X" and "run it off
# Camera_Y" are two different TABLES, not two states of one. This emitter therefore
# writes three tables into the same section, sharing one bank blob:
#
#   BgAnim_Table    the act's own. A band marked `"default_off": true` is NOT counted
#                   in it, so an act whose only band is default-off emits `count = 0`
#                   and the whole system is off at boot in EVERY shape -- no runtime
#                   flag, no engine gate, no cost. That is the "get rid of them" half,
#                   and it is off in the RELEASE ROM too.
#   BgAnim_View_H   the authored band verbatim -- "H" for the HORIZONTAL camera axis it
#                   is driven by (Camera_X), not for the band's own art axis.
#   BgAnim_View_V   the same band re-driven off Camera_Y at its own rate (below).
#   BgAnim_View_T   the same band re-driven off Logic_Tick -- the TIMER view, restored
#                   2026-09-04 (EFFECTS-W1 F6) so "perspective vs timer" is a comparison
#                   a reviewer can actually make. See BGANIM_VIEW_T_RATE_SHIFT.
#
# `engine/level/bg_anim.emp`'s DEBUG-only `BgAnim_SetTable` points the walk at one of the
# four; the plain shape has no selector and permanently walks `BgAnim_Table`.
#
# THE V VIEW'S RATE IS DERIVED, NOT COPIED. A camera-driven step at a tick-tuned rate is
# wrong by construction, because the two drivers have different units (frames vs pixels).
# Both rungs below are derived from the band's own pattern period P (px) and the display:
#
#   H view (Camera_X), authored in the override as `rate_shift`. The rung matches the
#     TIMER view's apparent speed at running speed, so the change of driver is not also a
#     change of tempo. Old view: driver Logic_Tick, rate_shift 2 = 1 px / 4 frames =
#     0.25 px/frame. New view: 1 px per 2^s px of camera travel, and the camera at
#     PHYS_TOP_SPEED ($600 = 6.0 px/frame, engine/system/constants.emp) gives
#     6 / 2^s px/frame. s = 4 -> 0.375 px/frame; s = 5 -> 0.1875. Four is the nearer rung
#     and errs toward VISIBLE, which is the right way to err on a review view. It also
#     reads well as depth: a full P = 64 px cycle costs 64 * 16 = 1024 px of camera
#     travel, 3.2 screen widths.
#   V view (Camera_Y), BGANIM_VIEW_V_RATE_SHIFT below.
BGANIM_VIEW_V_DRIVER = 'camera_y'

#: The V view's rate, derived: one full pattern cycle should cost about one SCREEN HEIGHT
#: of vertical camera travel, because that is the scale of a normal vertical excursion --
#: a rung tuned to horizontal running distance would leave the band visually frozen when
#: the player moves up and down. P * 2^s ~= 224 (the active display height) with P = 64
#: gives 2^s ~= 3.5; s = 2 (256 px, 1.14 screen heights) is the rung, and s = 1 (128 px,
#: 0.57) cycles twice per screen and reads as a flicker rather than as motion.
#:
#: STATED AS A SHIFT AND NOT A FORMULA ON PURPOSE: `P` is the band's own `pattern_px` and
#: could differ per act, but `rate_shift` is a hardware shift count -- there are only
#: whole rungs, and picking the nearest one to a computed real number would silently
#: change with a band's geometry while claiming to be derived. This number is derived FOR
#: the 64 px band this tree ships; `views_emitted` refuses any other period rather than
#: extrapolating (see its own refusal).
BGANIM_VIEW_V_RATE_SHIFT = 2

#: The pattern period this V rate was derived against, in px. Any other period makes the
#: derivation above a claim about a band it was not computed for.
BGANIM_VIEW_DERIVED_PERIOD_PX = 64

# ── THE TIMER VIEW (owner ask, 2026-09-04, EFFECTS-W1 F6) ─────────────────────
#
# THE ASK, in the owner's words: "I just ddidn't want the experimental animation bands
# right now for this, they showed we can do horizontal and vertical movement on a timer,
# but it was on for every test and distracting. It should be its own scene with start +
# button and should be tested for perspective vs timer, that's all"
#
# "Tested for perspective vs timer" is a COMPARISON, and yesterday's parcel removed one
# of its two arms: the H and V views are both camera-driven, so there was nothing left in
# the ROM to compare them against. This third twin puts the timer arm back.
BGANIM_VIEW_T_DRIVER = 'timer'

#: The T view's rate. NOT re-derived from the display: it is the rate the RETIRED TIMER
#: VIEW ACTUALLY RAN AT, and that is the whole point of restoring it.
#:
#: THE DERIVATION IS BY IDENTITY, and it is stronger here than a fresh computation would
#: be. The H rung above was derived by MATCHING this number ("Old view: driver Logic_Tick,
#: rate_shift 2 = 1 px / 4 frames = 0.25 px/frame [...] s = 4 -> 0.375 px/frame [...]
#: errs toward VISIBLE"). Pick any other rung for the timer arm and the H view's own
#: derivation comment stops naming a band that exists in the ROM, and the owner's A/B
#: silently becomes "perspective vs a DIFFERENT-TEMPO timer" -- two variables, one press.
#:
#: WHAT THE TWO ARMS ACTUALLY DIFFER BY, stated so the reviewer knows what to look for:
#:   moving at PHYS_TOP_SPEED   H = 0.375 px/frame   T = 0.25 px/frame   (1.5x, same order)
#:   standing still             H = 0     px/frame   T = 0.25 px/frame   (the whole point)
#: The camera arm STOPS when the player stops; the timer arm does not. That difference,
#: not the tempo, is what "perspective vs timer" is asking a reviewer to judge.
#:
#: PERIOD-INDEPENDENT, unlike the V rung: a tick-driven rate is px per FRAME and does not
#: reference the band's geometry or the display at all, so `views_emitted`'s period
#: refusal is not protecting this number. It is protecting the V one, as it always was.
BGANIM_VIEW_T_RATE_SHIFT = 2

#: How many DEBUG view twins a `default_off` act's table gets.
BGANIM_VIEW_COUNT = 3


def views_emitted(anims):
    """How many DEBUG view twins this act's `anims` produce (0 or BGANIM_VIEW_COUNT).

    NARROW BY DESIGN. The twins exist for the effects lab, which drives ONE band, so
    they are emitted only for the shape the lab can actually show: exactly one band,
    marked `default_off`, whose pattern period is the one BGANIM_VIEW_V_RATE_SHIFT was
    derived against. Anything else emits no twins and behaves exactly as before -- an
    act that never sets `default_off` cannot notice this feature exists.

    THE PERIOD CHECK IS A REFUSAL AND NOT A SILENT ZERO for the reason the rate constant
    states: a 32 px band would take the same shift and get a different cadence while the
    comment above still claimed the number was derived. Better to say so.
    """
    off = [a for a in anims if a.get('default_off', False)]
    if not off:
        return 0
    if len(anims) != 1:
        raise AssertionError(
            f'`default_off` is set on {len(off)} of {len(anims)} bands. The debug view '
            'twins are emitted only for a single-band act (the effects lab drives one '
            'band), and a multi-band act would need a view table per band and a selector '
            'that names both. Drop `default_off`, or extend BGANIM_VIEWS to a per-band '
            'shape deliberately.')
    period = anims[0]['pattern_px']
    if period != BGANIM_VIEW_DERIVED_PERIOD_PX:
        raise AssertionError(
            f"band 0 is `default_off` with pattern_px {period}, but "
            f"BGANIM_VIEW_V_RATE_SHIFT ({BGANIM_VIEW_V_RATE_SHIFT}) was DERIVED against a "
            f"{BGANIM_VIEW_DERIVED_PERIOD_PX} px period (one full cycle ~= one screen "
            f"height of vertical camera travel). At {period} px that shift gives a "
            f"different cadence while the derivation comment still claims the number was "
            f"computed for it. Re-derive the rung for this period and move "
            f"BGANIM_VIEW_DERIVED_PERIOD_PX with it.")
    return BGANIM_VIEW_COUNT


def bganim_section_bytes(n_bands, total_slots, n_views=0):
    """Emitted `ojz_bg_anim` size for `n_bands` bands covering `total_slots` slots.

    The one authority for the section's size. `n_bands == 0` is the disabled stub
    (`BgAnim_Table: u16 = 0` plus `BgAnim_Banks = Data.empty`) = 2 bytes.

    `n_views` is the number of DEBUG view twins emitted beside the act's own table
    (`default_off` acts; see BGANIM_VIEWS). Each is its own count word plus its own
    44-byte record -- the records differ from the authored one only in `driver` and
    `rate_shift`, but a record is a contiguous image the engine walks with `(a3)+`,
    so it cannot be shared and is written out again. The BANK BLOB is shared: every
    view's pointer array names the same `extern("BgAnim_Banks")` offsets, which is
    why the expensive half of the section does not multiply.
    """
    return (BGANIM_COUNT_BYTES
            + BGANIM_RECORD_BYTES * n_bands
            + n_views * (BGANIM_COUNT_BYTES + BGANIM_RECORD_BYTES * n_bands)
            + total_slots * BGANIM_BYTES_PER_SLOT)


def check_bganim_section_fits(anims, section=None):
    """Refuse an over-ceiling act BEFORE the build, naming the limit.

    `section` is the section name the refusal must name (`BgActNames.section`);
    it defaults to the default act's, which is what every existing caller gets.

    Replaces the diagnostic an author used to get instead:
        sections `test_mappings` [...] and `ojz_bg_anim` [...] overlap (colliding pins)
    which names neither the band, nor its size, nor any limit, nor a remedy.

    Raises SystemExit (the emitter runs as a build step, so this is a build failure
    with a message, not a traceback).
    """
    section = section or ACT.section
    n_bands = len(anims)
    total_slots = sum(a['cols'] * a['rows'] for a in anims)
    size = bganim_section_bytes(n_bands, total_slots, n_views=views_emitted(anims))
    ceiling = BGANIM_SECTION_CEILING
    if size <= ceiling:
        return size
    per_band = ', '.join(f"band {i}: {a['cols']}x{a['rows']} = {a['cols'] * a['rows']} slots"
                         for i, a in enumerate(anims))
    over = size - ceiling
    fits = max(0, (ceiling - BGANIM_COUNT_BYTES - BGANIM_RECORD_BYTES * n_bands)
               // BGANIM_BYTES_PER_SLOT)
    why = (
        f"  The limit is the owner's ruled authoring budget (decision d-9, raised\n"
        f"  2026-09-04): {ceiling} B. DERIVED from BGANIM_SECTION_CEILING, never typed --\n"
        f"  a literal here said '12 KiB' for two days after the 2026-09-04 raise,\n"
        f"  telling the author a bound this gate was not enforcing.\n"
        f"  `{section}` grows into the room before the `dac_banks` anchor, which the\n"
        f"  BANK PLACEMENT RULE in games/sonic4/map.toml keeps at >= "
        f"{_BANK_PLACEMENT_FLOOR:,} B\n"
        f"  (DATA_GROWTH_RESERVE) in every shape; the ceiling is the budget INSIDE that\n"
        f"  room, and raising it is an\n"
        f"  owner ruling, not an edit. Run `python3 tools/bganim_room.py --lst\n"
        f"  s4.debug.lst` for the live room derivation.")
    raise SystemExit(
        f"[inject_editor_bg] REFUSED: this act's BG animation does not fit its section.\n"
        f"  {n_bands} band(s), {total_slots} slots total ({per_band})\n"
        f"  -> {section} would be {size} B "
        f"({BGANIM_COUNT_BYTES} + {BGANIM_RECORD_BYTES}x{n_bands} + "
        f"{total_slots}x{BGANIM_BYTES_PER_SLOT})\n"
        f"  -> the ceiling is {ceiling} B (BGANIM_SECTION_CEILING, the ruled authoring\n"
        f"     budget inside the ROM room), so this is {over} B over.\n"
        f"{why}\n"
        f"  THE LIMIT IS ON THE TOTAL, NOT PER BAND -- BgAnim_Banks is one blob for the\n"
        f"  whole act. At {n_bands} band(s) the ceiling allows {fits} slots in total.\n"
        f"  To fit: shrink or drop bands until the total is {fits} slots or fewer.")


def live_section_bytes(aeon=None, act=None):
    """Size of the bg-anim section this tree's override file currently produces.

    Reads the same override the emitter reads, so the gate in tools/bganim_room.py
    measures the shipping content rather than assuming the stub.

    `aeon` is a repo ROOT to resolve the path against; `act` is a `BgActNames`.
    With neither, the module-level `OVERRIDE` is used, which is what lets
    tools/test_bg_emit.py redirect this the same way it redirects `main()`.

    `aeon` RE-ROOTS A PATH, IT DOES NOT SELECT AN ACT. The ids still come from this
    tree's project.json (via `ACT`), because tools/bganim_room.py's own tests call
    this with a synthetic room directory that holds a listing and an art blob and no
    project.json at all — reading ids from `aeon` turned eight of those into
    FileNotFoundError. Which act's background this measures is a property of the
    project; `aeon` only says where on disk to look for it.
    """
    if act is None:
        act = ACT
    path = act.override_path(aeon) if aeon is not None else (
        OVERRIDE if act is ACT else act.override_path())
    if not os.path.exists(path):
        return bganim_section_bytes(0, 0)          # no override -> the disabled stub
    with open(path) as f:
        data = json.load(f)
    anims = data.get('anims')
    if anims is None and data.get('anim'):
        anims = [data['anim']]
    if not anims:
        return bganim_section_bytes(0, 0)
    return bganim_section_bytes(len(anims),
                                sum(a['cols'] * a['rows'] for a in anims),
                                n_views=views_emitted(anims))


REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

#: The one act whose override file predates this tool taking an act, and which
#: therefore keeps the un-suffixed spelling `games/sonic4/data/editor_bg_override.json`.
#: NOT a fallback and NOT probed on disk: the mapping is act -> path, decided before
#: any I/O, so a second act can never silently read act 1's background.
#:
#: WHY IT IS GRANDFATHERED RATHER THAN RENAMED. That filename is spelled in eight
#: other places — tools/bg_override_io.py, tools/png_to_bg_override.py,
#: tools/forest_bg_gen.py, tools/level_staleness.py (the staleness scan list),
#: tools/test_bg_tile_budget.py, tools/test_bg_emit.py, the fixture
#: test/fixtures/bg-override/editor_bg_override.b0e5a661.json, and
#: tools/EFFECTS_CONSUMER_CONTRACT.md §"Input file", which calls the path FIXED.
#: Renaming it is a contract amendment plus a sweep of those readers; it is booked in
#: docs/DEFERRED_WORK.md instead of being smuggled into this parcel.
LEGACY_OVERRIDE_ACT = ('ojz', 'act1')
LEGACY_OVERRIDE_REL = ('games', 'sonic4', 'data', 'editor_bg_override.json')


class BgActNames:
    """Every act-dependent name and path this emitter needs, derived from the ids.

    Constructed from project.json's zone/act ids by `act_names()` below, which
    reuses tools/effects_gen.py's reader so the ids have ONE authority and ONE
    symbol-safety check (they become `.emp` module-name components here too).

    THE SECTION NAME CARRIES NO ACT AND THAT IS DELIBERATE. `ojz_bg_anim` is one
    section holding the band table and bank blob for the whole act (the d-9 block at
    the head of this file), placed by the `BgAnim_Table` row in games/sonic4/map.toml.
    So `section` is derived from the ZONE only, and two acts of the same zone name
    the same section and the same `pub` symbols. Making several acts resident at once
    is a ROM-PLACEMENT change (a per-act section and a re-derived d-9 ceiling, or an
    act-selected pointer) and needs an owner ruling; it is booked in
    docs/DEFERRED_WORK.md, "A SECOND ACT'S BG ANIMATION HAS NOWHERE TO LIVE". It is
    NOT decision d-31 — d-31 asks about background height versus act height, and no
    decision in docs/decisions.jsonl asks about multi-act residency. This class does
    the plumbing and does not pre-empt the ruling. effects_gen.py's own `ActNames`
    docstring flagged the hazard here ("a latent hazard in the `bg_anim.emp`
    precedent, whose section name carries no act suffix — noted, not fixed here");
    it is now named at the site rather than only next door.
    """

    def __init__(self, zone_id, act_id, repo=None):
        #: The repo root this act's on-disk paths hang off. Defaults to REPO; the
        #: unit tests pass a tmpdir so a second act can be baked end-to-end without
        #: writing into games/sonic4/data/generated/.
        self.repo = repo or REPO
        self.zone_id, self.act_id = zone_id, act_id
        self.label = f'{zone_id}/{act_id}'                       # ojz/act1
        self.module = f'games.sonic4.{zone_id}_bg_anim_{act_id}'  # ..ojz_bg_anim_act1
        self.section = f'{zone_id}_bg_anim'                      # zone-scoped: see above
        #: repo-relative, forward-slashed — it goes into an `embed(...)` in the
        #: emitted `.emp`, which sigil resolves against the repo root, NOT against
        #: `out_dir` (which the unit tests redirect to a tmpdir).
        self.banks_embed = (f'games/sonic4/data/generated/'
                            f'{zone_id}/{act_id}/bg_anim_banks.bin')

    def out_dir(self, repo=None):
        return os.path.join(repo or self.repo, 'games', 'sonic4', 'data', 'generated',
                            self.zone_id, self.act_id)

    def override_path(self, repo=None):
        if (self.zone_id, self.act_id) == LEGACY_OVERRIDE_ACT:
            return os.path.join(repo or self.repo, *LEGACY_OVERRIDE_REL)
        return os.path.join(repo or self.repo, 'games', 'sonic4', 'data',
                            f'editor_bg_override_{self.zone_id}_{self.act_id}.json')

    def __repr__(self):
        return f'BgActNames({self.zone_id!r}, {self.act_id!r})'


def act_names(repo=REPO, zone=0, act=0, paths_repo=None):
    """`BgActNames` for project.json's zone/act INDICES (effects_gen's signature).

    Delegates the project.json read AND the symbol-safety check to
    tools/effects_gen.py: the ids become `.emp` symbol components in both tools, so
    a second reader here would be a second place for `ojz-1` to be accepted. An
    index that names no act raises straight out of that reader (IndexError/KeyError)
    rather than resolving to a plausible-looking empty act.
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from effects_gen import act_names as _effects_act_names
    n = _effects_act_names(repo, zone, act)
    return BgActNames(n.zone_id, n.act_id, paths_repo or repo)


#: The default act — project.json's first act of its first zone. DERIVED, so this
#: module has no `act1` literal outside LEGACY_OVERRIDE_ACT above. `OUT_DIR` and
#: `OVERRIDE` stay module-level names because tools/test_bg_emit.py rebinds them
#: around `main()` to redirect a run into a tmpdir; `main()` reads them at call time
#: for exactly that reason.
ACT = act_names()
OUT_DIR = ACT.out_dir()
OVERRIDE = ACT.override_path()

# ── THE MOTION AXIS (EFFECTS-W1 DoD item 8) ────────────────────────────────────
#
# THE ENGINE IS AXIS-AGNOSTIC AND ALWAYS WAS. This is the finding the item turned on,
# so it is written down here rather than left to be re-derived: `BgAnim_Update` does
# not know which way a band moves. It reads `step` off a scalar, picks bank `step & 7`,
# and rotates the band's byte image by `(step >> 3) << col_shift`. Both fields are
# UNITS, not axes:
#
#   col_shift  log2 of the ROTATION UNIT in bytes — the byte distance one whole-tile
#              step of motion moves the image. The name says "column" because the
#              horizontal arm shipped first; the engine only ever shifts by it.
#   step_mask  the pattern PERIOD in px, minus 1 — the ring the step wraps on.
#
# The axis is therefore a property of two things the engine never sees: how the eight
# phase banks were shifted, and what order the band's slots are placed in on the plane.
# The engine's own legality condition is the same on both axes — `units * unit_bytes`
# must equal `tile_count * 32`, which is what keeps its piece-1 length positive:
#
#   horizontal   cols units x (rows * 32) B  = cols * rows * 32   ✓
#   vertical     rows units x (cols * 32) B  = cols * rows * 32   ✓
#
# So aurora ROADMAP row 55's open question — *"whether a vertical shift can reuse the
# column rotate at all or needs a different DMA shape"* — is answered REUSE, EXACTLY,
# with no engine byte moved. What forbade vertical until 2026-09-02 was not the DMA:
# it was the two asserts this table replaces, which spelled the horizontal reading of
# both fields as if it were the only one.
#
#   axis          unit_bytes   period_px   slot order within the band
#   horizontal    rows * 32    cols * 8    column-major: slot base + c*rows + r
#   vertical      cols * 32    rows * 8    ROW-major:    slot base + r*cols + c
#
# THE SLOT ORDER IS THE AUTHOR'S OBLIGATION, NOT SOMETHING THIS TOOL CAN CHECK. A
# band's slot order lives in `layout` — which cell references which slot — and the
# same 32 slots read as a scroll under one order and as a shimmer under the other.
# Nothing here can tell them apart, because a band's slots are also deduped against
# the static blob and appear at many cells. It is stated in
# tools/EFFECTS_CONSUMER_CONTRACT.md §1.2 as a writer obligation.
#
# DIRECTION IS FIXED, and it is fixed by the mechanism rather than by choice. Bank k
# is phase 0 translated k px toward DECREASING coordinate (this is measured, not
# assumed: the live act's eight phases are exactly `phase0[y][(x + k) % W]`), and the
# coarse rotate carries the same sign — slot i takes the content of slot i + one unit.
# So an increasing driver scrolls a horizontal band LEFT and a vertical band UP. A
# `direction` key (the engine would need to reverse the step on the ring) is booked in
# docs/DEFERRED_WORK.md, not built.
BAND_AXES = ('horizontal', 'vertical')

#: Which band dimension supplies the rotation unit on each axis. The OTHER dimension
#: supplies the period. Named so the refusals below can say which key an author must
#: change, instead of "column bytes must be a power of 2" on a band that has no
#: columns in the relevant sense.
_AXIS_UNIT_TILES = {'horizontal': 'rows', 'vertical': 'cols'}
_AXIS_PERIOD_TILES = {'horizontal': 'cols', 'vertical': 'rows'}


def band_axis_geometry(a, where='band'):
    """`(axis, unit_bytes, unit_shift, period_px)` for one authored band.

    The single derivation of both axis-dependent record fields. `where` is a caller
    label so a refusal names the band rather than only the rule.
    """
    axis = a.get('axis', 'horizontal')
    if axis not in BAND_AXES:
        raise AssertionError(
            f"{where}: axis {axis!r} is not one of {' / '.join(map(repr, BAND_AXES))}. "
            "The axis names which way the band's pattern translates; it is NOT the "
            "`driver`, which names the scalar the step is read from and never an axis.")
    unit_tiles = a[_AXIS_UNIT_TILES[axis]]
    period_tiles = a[_AXIS_PERIOD_TILES[axis]]
    unit_bytes = unit_tiles * 32
    unit_shift = unit_bytes.bit_length() - 1
    if (1 << unit_shift) != unit_bytes:
        raise AssertionError(
            f"{where}: a {axis} band rotates by whole "
            f"{'columns' if axis == 'horizontal' else 'rows'} of "
            f"{_AXIS_UNIT_TILES[axis]}*32 = {unit_bytes} B, and BgAnim_Update shifts by "
            f"that distance with `lsl`, so it must be a power of two — "
            f"{_AXIS_UNIT_TILES[axis]}={unit_tiles} is not. (The power-of-two key is "
            f"`rows` on a horizontal band and `cols` on a vertical one; this band is "
            f"{axis}.)")
    return axis, unit_bytes, unit_shift, period_tiles * 8


def validate_band_phase_axis(anims):
    """Refuse a VERTICAL band whose phases were regenerated by a HORIZONTAL writer.

    NARROW ON PURPOSE, AND ITS POPULATION IS EMPTY TODAY. No act in this tree
    authors a vertical band, so this runs over nothing on a real build; it is a guard
    for the first one, placed now because the failure it catches is silent.

    THE FAILURE. `axis` is a declaration about art this tool did not make. Aurora is
    the author of `anims` (owner decision d-14) and its shift-fill regenerates bank k
    as phase 0 scrolled k px within the pattern WIDTH — horizontal by construction,
    with the column-wise twin costed but NOT BUILT (aurora ROADMAP row 55). So the
    reachable accident is precise: someone opens a vertical band in the editor, touches
    it, and the phases come back HORIZONTAL while `axis: vertical` stays in the file.
    The bake is clean, every other assert passes, and the band ships as a shimmer.
    That is docs/BUGS.md TOOL-01's shape exactly, one axis over.

    WHAT IS CHECKED, and it is deliberately not "phase k is a vertical roll". The
    horizontal arm's shipped bands are NOT pure rolls — measured 2026-09-02: the
    historical two-band act's colonnade and firefly banks are composites (the firefly
    band is a brightness triangle, `forest_bg_gen.py` FF_TRI), and the engine's own
    header comment celebrates layers that stay glued under the rotation. Demanding an
    exact roll would outlaw the same trick on the vertical arm before anyone has used
    it. So the check is the CONVERSE: a vertical band whose phases are exactly
    horizontal translations, and are not also vertical ones, has been written by a
    horizontal-only writer. Anything else is admitted.

    READ IN THE DECLARED AXIS'S SLOT ORDER (widened 2026-09-03). `_band_pixels` used
    to decode column-major unconditionally, so on a row-major band — which is what
    `axis: "vertical"` requires — it assembled a PERMUTATION of the real picture, a
    true x-roll stopped looking like an x-roll, and the guard fell through its own
    `continue`. Measured with a control before the fix, on one 2x2 band whose eight
    phases are exact x-rolls of `(x*7 + y*13) % 15 + 1`, the two arms differing ONLY
    in slot order:

        column-major slots + x-rolled phases  ->  REFUSED   (control: guard reachable)
        row-major    slots + x-rolled phases  ->  ADMITTED  (the shimmer ships)

    The old docstring's defence — "a consistent relabelling of the slots cannot turn a
    non-translation into one" — is TRUE and rules out FALSE POSITIVES. The exposure was
    a FALSE NEGATIVE, the other direction: a relabelling turns a translation INTO a
    non-translation. Certifying the half nobody was worried about.

    THE PREDICATE IS UNCHANGED — only the decode is. Still "horizontal AND NOT
    vertical", still admitting composites; nothing newly refused beyond the obligation
    above. See §1.2 of the consumer contract for why composites stay legal.

    NOT PROVEN BY THIS: that a vertical band's art is right, or that `layout` places
    its slots row-major. Both are the writer's, and §1.2 of the consumer contract says
    so. Note the second one is what this decode now ASSUMES rather than checks: a band
    that declares `vertical` and emits column-major slots is read as the picture its
    declaration says it is, which is garbage — the refusal that lands on it, if any,
    is incidental. Obligation 1 is discharged by asserting the order at named cells,
    not here.
    """
    for i, a in enumerate(anims):
        axis = a.get('axis', 'horizontal')
        if axis != 'vertical':
            continue
        cols, rows, phases = a['cols'], a['rows'], a['phases']
        if len(phases) < 2:
            continue
        w, h = cols * 8, rows * 8
        base = _band_pixels(phases[0], cols, rows, axis)
        h_rolls = all(_band_pixels(phases[k], cols, rows, axis)
                      == [[base[y][(x + k) % w] for x in range(w)] for y in range(h)]
                      for k in range(len(phases)))
        if not h_rolls:
            continue
        v_rolls = all(_band_pixels(phases[k], cols, rows, axis)
                      == [[base[(y + k) % h][x] for x in range(w)] for y in range(h)]
                      for k in range(len(phases)))
        if v_rolls:
            continue                        # ambiguous art (uniform along one axis) — admit
        raise AssertionError(
            f'band {i} declares axis "vertical" but every phase is an exact HORIZONTAL '
            f'translation of phase 0 ({w}px pattern) and none is a vertical one. Its '
            'banks were regenerated by a horizontal-only writer (aurora\'s shift-fill; '
            'the column-wise twin is aurora ROADMAP row 55 and is not built). Baking '
            'this would ship a clean build whose band shimmers instead of scrolling. '
            'Regenerate the phases along the declared axis, or change `axis` back to '
            '"horizontal" if horizontal is what the band is meant to do.')


def _band_pixels(bank, cols, rows, axis):
    """One phase bank as a `rows*8` x `cols*8` grid of palette indices.

    DECODED IN `axis`'S OWN SLOT ORDER, which is the whole point: column-major
    (slot `c*rows + r` is band cell `(c, r)`) on a horizontal band, ROW-major
    (slot `r*cols + c`) on a vertical one — the two orders §1.2 obligation 1 assigns
    to the two axes. `axis` is required rather than defaulted so no future caller can
    inherit the unconditional column-major read this replaces.

    WHY IT HAS TO BE CONDITIONAL, stated in the direction that actually bit us. Reading
    a row-major band column-major yields a consistent RELABELLING of its cells. Such a
    relabelling cannot turn a non-translation into a translation — that argument is
    sound, and it is why the old code was safe against FALSE POSITIVES. But it says
    nothing about the converse, and the converse is the live risk: a relabelling turns
    a translation INTO a non-translation, `h_rolls` comes out False on art that really
    is an x-roll, and the caller's `continue` swallows exactly the case the guard
    exists to refuse. Measured with a control 2026-09-03; see the caller's docstring
    and tools/EFFECTS_CONSUMER_CONTRACT.md §1.2 obligation 2.
    """
    g = [[0] * (cols * 8) for _ in range(rows * 8)]
    for i, t in enumerate(bank):
        if axis == 'vertical':
            r, c = divmod(i, cols)          # row-major
        else:
            c, r = divmod(i, rows)          # column-major
        for y in range(8):
            for x in range(8):
                g[r * 8 + y][c * 8 + x] = t[y * 8 + x] & 0xF
    return g


def validate_band_coherence(anims, tiles):
    """Assert each band's slots really are the front of the static tile blob.

    Bands pack contiguously from slot 0 and DMA over the FRONT of `tiles`, so a
    band's phase-0 art IS those slots' rest state:

        phases[0] == tiles[slot_base : slot_base + cols*rows]

    Verified exactly on the two real bands the file carried at b0e5a661. This
    is the invariant that makes `anims`/`tiles`/`layout` inseparable, and it is
    asserted here because a violation bakes CLEANLY and ships silently corrupt
    art: retained bands would DMA stale phase art over whatever a newer dedup
    put in those slots. Every other assert in this file would still pass.

    Booked as docs/BUGS.md TOOL-01.
    """
    cursor = 0
    for i, a in enumerate(anims):
        n = a['cols'] * a['rows']
        base = a.get('slot_base', cursor)
        assert base == cursor, (
            f'band {i}: slot_base {base} does not pack contiguously (expected {cursor}); '
            'bands must tile the front of the blob from slot 0')
        assert base + n <= len(tiles), (
            f'band {i}: slots {base}..{base + n} exceed the {len(tiles)}-tile static blob')
        phase0 = a['phases'][0]
        assert phase0 == tiles[base:base + n], (
            f"band {i}: phases[0] != tiles[{base}:{base + n}]. The band's rest state must BE "
            'the static tiles it covers. This means anims and tiles came from different '
            'generator runs — regenerating layout/tiles while retaining anims produces a '
            'clean bake that ships CORRUPT art. Regenerate both together (tools/forest_bg_gen.py).')
        cursor += n


def main(act=None):
    """Bake one act's editor background. `act` is a `BgActNames`.

    `act=None` means the module-level defaults (`ACT`/`OUT_DIR`/`OVERRIDE`), read
    HERE and not captured at import, because tools/test_bg_emit.py rebinds those two
    globals around this call to redirect a run into a tmpdir. Passing an `act`
    bypasses them entirely and takes every path from the act.
    """
    if act is None:
        act, out_dir, override = ACT, OUT_DIR, OVERRIDE
    else:
        out_dir, override = act.out_dir(), act.override_path()
    with open(override) as f:
        data = json.load(f)
    layout, tiles = data['layout'], data['tiles']

    # ---- HCZ-pillar tile-band animation, table-driven (up to 4 bands).
    # Each band's phase-0 tiles occupy a contiguous slot range starting at
    # slot_base (bands packed from slot 0, in list order), column-major so
    # whole-column rotation is two wrapped DMAs. Emit one concatenated banks
    # bin + a pure-data band table (engine reads it at runtime — act data
    # assembles after engine code, so no assemble-time conditionals).
    DRIVERS = {'camera_x': 0, 'camera_y': 1, 'timer': 2}
    anims = data.get('anims')
    if anims is None and data.get('anim'):
        anims = [data['anim']]                  # legacy single-band shape
    if anims:
        validate_band_coherence(anims, tiles)
        validate_band_phase_axis(anims)
        assert len(anims) <= BGANIM_MAX_BANDS, (
            f'{len(anims)} animated bands authored but the engine sizes BgAnim_LastStep '
            f'for at most BGANIM_MAX_BANDS={BGANIM_MAX_BANDS}. Raising it here is NOT '
            f'enough: engine/system/constants.emp (which sizes the array) and '
            f'engine/level/bg_anim.emp (which bounds the runtime assert) hold the same '
            f'number and must be raised together, or BgAnim_Update walks past the array '
            f'in the release shape. See BGANIM_MAX_BANDS at the head of this file.')
        # The SECTION-SIZE ceiling, checked on the TOTAL across every band (see the
        # BGANIM_SECTION_CEILING block at the head of this file). Deliberately ahead of
        # any emission: an over-ceiling act must fail with a sentence naming the limit,
        # not by writing artifacts that make sigil report a section collision.
        section_bytes = check_bganim_section_fits(anims, act.section)
        n_views = views_emitted(anims)
        banks = bytearray()
        bands = []
        slot_cursor = 0
        for a in anims:
            cols, rows = a['cols'], a['rows']
            n = cols * rows
            pattern_px = a['pattern_px']
            # Both record fields are axis-derived; see the BAND_AXES block above for
            # why the engine needs no change to read either one.
            axis, _unit_bytes, col_shift, period_px = band_axis_geometry(
                a, f'band {len(bands)}')
            assert pattern_px == period_px, (
                f'band {len(bands)}: a {axis} band\'s pattern period is '
                f'{_AXIS_PERIOD_TILES[axis]}*8 = {period_px} px, but `pattern_px` says '
                f'{pattern_px}. (`pattern_px` is the period ALONG THE AXIS — it is the '
                f"band's width when horizontal and its HEIGHT when vertical.)")
            slot_base = a.get('slot_base', slot_cursor)
            assert slot_base == slot_cursor, 'bands must pack contiguously from slot 0'
            slot_cursor += n
            strip_off = len(banks)
            for bank in a['phases']:
                assert len(bank) == n
                for t in bank:
                    for row in range(8):
                        for col in range(4):
                            hi = t[row*8 + col*2] & 0xF
                            lo = t[row*8 + col*2 + 1] & 0xF
                            banks.append((hi << 4) | lo)
            bands.append({
                'axis': axis,
                'default_off': bool(a.get('default_off', False)),
                'driver': DRIVERS[a.get('driver', 'camera_x')],
                'driver_name': a.get('driver', 'camera_x'),
                'rate_shift': a.get('rate_shift', 2),
                'step_mask': pattern_px - 1,
                'col_shift': col_shift,
                'tile_count': n,
                'slot_base': slot_base,
                'bank_offsets': [strip_off + ph * n * 32 for ph in range(len(a['phases']))],
            })
        with open(os.path.join(out_dir, 'bg_anim_banks.bin'), 'wb') as f:
            f.write(banks)
        # Parcel K3 run B: BgAnim_Table is a natively-placed `.emp` section
        # (ojz_bg_anim). Per band, a 44-byte record contiguous in the section:
        # 6 u16 header words (baked constants; BG_TILE_BASE_VRAM = $8000) then an
        # 8-entry pointer array `extern("BgAnim_Banks") + off` (link-relative,
        # resolved at link). Mirrors engine/level/bg_anim.emp `struct bganim_band`
        # field-for-field (the LOCKSTEP contract).
        #
        # THE `extern(...)` IS LOAD-BEARING AND WAS WRONG UNTIL 2026-08-24. This arm
        # shipped booked as "FORMAT-FAITHFUL BUT NOT BYTE-PROVEN" — no act in the tree
        # authored BG animation, so the six-target gate only ever exercised the stub
        # below, and the array went out as a bare `BgAnim_Banks + off`. The first real
        # band discharged the booking: sigil resolves bare names against the compiler's
        # name table, which these generated act modules are not in, and answered
        # `[Error] unknown name \`BgAnim_Banks\`` once per entry (16 on the two-band
        # b0e5a661 fixture). extern("Name") is the accepted spelling for a link-time
        # symbol inside an emitted data image; sec_local_maps.emp in the same generated
        # directory is the precedent. THE ADDEND FORM WORKS — `extern("X") + N` links
        # (measured here, not inherited); docs/EMP_PITFALLS.md §5's warning about
        # extern() poisoning comptime-ness applies to images a comptime pin then
        # COMPARES, and nothing pins this one.
        #
        # The arm now has a test that runs it: tools/test_bg_emit.py::TestBgAnimEmission
        # drives this emitter over the real two-band fixture and rejects any bare
        # link-time symbol in an emitted array initializer.
        # (docs/superpowers/notes/2026-08-01-k3-run-b.md §animated-arm;
        #  docs/DEFERRED_WORK.md "the first real authored band does not assemble".)
        BG_TILE_BASE_VRAM = 0x8000
        for b in bands:
            assert len(b['bank_offsets']) == 8, \
                'bganim_band.banks is [*u8; 8]: each band needs exactly 8 phases'
        with open(os.path.join(out_dir, 'bg_anim.emp'), 'w') as f:
            f.write('// AUTO-GENERATED by tools/inject_editor_bg.py — DO NOT EDIT.\n')
            f.write(f'// {act.label} BG tile-band animation table (HCZ-pillar technique).\n')
            f.write('// Mirrors engine/level/bg_anim.emp `struct bganim_band` (LOCKSTEP).\n')
            f.write(f'// Natively placed at the {act.section} section.\n')
            f.write(f'module {act.module} in {act.section}\n\n')
            # A `default_off` band is NOT counted in the act's own table — the whole
            # system is off at boot, in every shape. See the `default_off` block at the
            # head of this file. The records still follow the count word, so they are
            # reachable through the view labels below and through nothing else.
            live_bands = [b for b in bands if not b['default_off']]
            assert all(b['default_off'] for b in bands[len(live_bands):]), (
                'default_off bands must be the TAIL of the band list: the count word '
                'says how many of the records that FOLLOW IT the engine walks, so a '
                'default-off band ahead of a live one would silently disable the live '
                'one instead of itself.')
            f.write(f'pub data BgAnim_Table: u16 = {len(live_bands)}   // band count'
                    + ('  (default_off: the act boots with BG animation OFF)\n'
                       if len(live_bands) != len(bands) else '\n'))

            def _emit_record(tag, b, i, driver, rate_shift, gated=False):
                vram_dest = BG_TILE_BASE_VRAM + b['slot_base'] * 32
                # The axis and its direction are named here because the record cannot
                # carry them: `col_shift` and `step_mask` are units, and a reader of
                # the emitted table has no other way to tell a leftward band from an
                # upward one. See the BAND_AXES block for why direction is fixed.
                f.write(f'// band {i}: {b["tile_count"]} tiles at BG slot {b["slot_base"]}, '
                        f'driver {driver}, {b["axis"]} '
                        f'(scrolls {"left" if b["axis"] == "horizontal" else "up"}), '
                        f'1px per {1 << rate_shift} units\n')
                hdr = (f'[{DRIVERS[driver]}, {rate_shift}, {b["step_mask"]}, '
                       f'{b["col_shift"]}, {b["tile_count"]}, ${vram_dest:X}]')
                if gated:
                    f.write(f'data _BgAnim_{tag}{i}_hdr: [u16; BGANIM_VIEW_EMIT * 6] = '
                            f'if DEBUG == 1 {{ {hdr} }} else {{ [] }}\n')
                else:
                    f.write(f'data _BgAnim_{tag}{i}_hdr: [u16; 6] = {hdr}\n')
                # extern("BgAnim_Banks"), NOT a bare `BgAnim_Banks` — see the
                # spelling note at :151. tools/test_bg_emit.py::TestBgAnimEmission
                # is the gate on this line.
                banks_list = ', '.join(f'extern("BgAnim_Banks") + {off}'
                                       for off in b['bank_offsets'])
                if gated:
                    f.write(f'data _BgAnim_{tag}{i}_banks: [*u8; BGANIM_VIEW_EMIT * 8] = '
                            f'if DEBUG == 1 {{ [{banks_list}] }} else {{ [] }}\n')
                else:
                    f.write(f'data _BgAnim_{tag}{i}_banks: [*u8; 8] = [{banks_list}]\n')

            for i, b in enumerate(bands):
                _emit_record('Band', b, i, b['driver_name'], b['rate_shift'])

            # ---- the DEBUG view twins (see the `default_off` block above) ----
            #
            # EVERY DECLARATION IS SHAPE-GATED, and that is not tidiness. The only
            # installer is `Debug_BgAnimViewHotkey`, whose whole body is inside
            # `if DEBUG == 1 {}`; an unconditional emission would put 92 bytes of band
            # table in the SHIPPED ROM that nothing in that shape can point the walk at
            # -- the dormant scaffold this tree deletes rather than keeps "for later",
            # and the same ruling `OJZ_BaseSwap`'s own emission gate records. It also
            # moved every release symbol after it by 92 bytes on the first draft, which
            # turned three committed gate cuts stale for data the release cannot reach.
            #
            # THE IDIOM IS THE TREE'S OWN: a conditional ARRAY LENGTH plus an empty
            # literal (`games/sonic4/data/effects/ojz_effects.emp`, OJZ_BandDemo and
            # OJZ_BaseSwap). It has to be spelled per declaration because a band table is
            # three declarations -- a count word, a `[u16; 6]` header and a `[*u8; 8]`
            # pointer array -- and the pointer array cannot be folded into the others:
            # its entries are LINK-TIME `extern()` relocations, not values this tool can
            # split into words.
            #
            # WHAT IS **NOT** GATED, deliberately, and it is the bigger number: the act's
            # own band records and the 8 KB `BgAnim_Banks` blob below stay unconditional.
            # They are ACT DATA that predates this parcel -- all this parcel did to them
            # is turn one count word from 1 to 0 -- and making them shape-divergent would
            # shrink the release `ojz_bg_anim` section from ~8.3 KB to 2 B, i.e. an 8 KB
            # release re-layout with the frozen placement tables to re-rule. That is a
            # separate parcel and is booked in docs/DEFERRED_WORK.md rather than done
            # here on the way past.
            if n_views:
                b = bands[0]
                f.write("\n// The effects lab's three BG-animation views. Same band, same\n"
                        '// bank blob, same slots — they differ ONLY in which scalar the\n'
                        '// step is read from and how fast. Reached through\n'
                        '// BgAnim_SetTable (engine/level/bg_anim.emp), DEBUG shape only:\n'
                        '// every declaration below emits ZERO bytes in the plain shape,\n'
                        '// where nothing can point the walk at them.\n')
                f.write('const BGANIM_VIEW_EMIT = if DEBUG == 1 { 1 } else { 0 }\n')
                f.write('pub data BgAnim_View_H: [u16; BGANIM_VIEW_EMIT] = '
                        'if DEBUG == 1 { [1] } else { [] }   // horizontal camera motion\n')
                _emit_record('ViewH', b, 0, b['driver_name'], b['rate_shift'], gated=True)
                f.write('pub data BgAnim_View_V: [u16; BGANIM_VIEW_EMIT] = '
                        'if DEBUG == 1 { [1] } else { [] }   // vertical camera motion\n')
                _emit_record('ViewV', b, 0, BGANIM_VIEW_V_DRIVER,
                             BGANIM_VIEW_V_RATE_SHIFT, gated=True)
                f.write('pub data BgAnim_View_T: [u16; BGANIM_VIEW_EMIT] = '
                        'if DEBUG == 1 { [1] } else { [] }   // the TIMER arm of the A/B\n')
                _emit_record('ViewT', b, 0, BGANIM_VIEW_T_DRIVER,
                             BGANIM_VIEW_T_RATE_SHIFT, gated=True)
            f.write(f'pub data BgAnim_Banks = embed("{act.banks_embed}")\n')
        assert section_bytes == bganim_section_bytes(
                len(bands), sum(b['tile_count'] for b in bands), n_views=n_views), (
            f'bganim_section_bytes predicted {section_bytes} B but the emitted artifacts are '
            f'{BGANIM_COUNT_BYTES + BGANIM_RECORD_BYTES * len(bands) + n_views * (BGANIM_COUNT_BYTES + BGANIM_RECORD_BYTES * len(bands)) + len(banks)} B — the '
            f'size formula and the emitter have diverged, so the ceiling gates nothing')
        live = sum(0 if b['default_off'] else 1 for b in bands)
        print(f'[inject_editor_bg] anim: {len(bands)} band(s), {live} live at boot, '
              f'{n_views} debug view twin(s), {len(banks)} bytes of banks; '
              f'ojz_bg_anim {section_bytes}/{BGANIM_SECTION_CEILING} B (ROM-room ceiling)')
    else:
        # no animation: emit the disabled stub as a natively-placed `.emp` section
        # (Parcel K3 run B). band_count = 0 disables the whole system.
        with open(os.path.join(out_dir, 'bg_anim.emp'), 'w') as f:
            f.write('// AUTO-GENERATED by tools/inject_editor_bg.py — DO NOT EDIT.\n')
            f.write(f'// {act.label} BG tile-band animation table (HCZ-pillar technique).\n')
            f.write('// The engine contract (engine/level/bg_anim.emp, BgAnim_Update):\n')
            f.write('// every act supplies BgAnim_Table; band_count = 0 disables the whole\n')
            f.write('// system. This act has no BG animation, so it is the disabled stub.\n')
            f.write(f'// Natively placed at the {act.section} section.\n')
            f.write(f'module {act.module} in {act.section}\n\n')
            f.write('pub data BgAnim_Table: u16 = 0              // band_count = 0 (disabled)\n')
            f.write('pub data BgAnim_Banks = Data.empty         // bank-blob base (empty in the stub)\n')
        print('[inject_editor_bg] anim: disabled stub (band_count = 0)')
    if len(layout) == 2048:
        layout = layout + [0]*2048          # legacy 32-row layout: pad to 64 rows
    assert len(layout) == 4096, f'layout must be 64x32 or 64x64 words, got {len(layout)}'
    assert len(tiles) <= BG_TILE_CAPACITY, f'{len(tiles)} tiles exceeds BG capacity {BG_TILE_CAPACITY}'

    # nametable: local -> VRAM-absolute indices, preserving pal/pri/flip bits.
    # This is the editor->engine boundary: the editor layout is ROW-MAJOR
    # (idx = row*64 + col), the engine reads COLUMN-MAJOR (blob[col*128 + row*2]
    # — column-contiguous, 64 rows per column). Transpose here so every engine
    # consumer (BG_Init, Section_RedrawPlanes' Plane B blit, Draw_BG_TileColumn)
    # gathers a column with sequential reads. See engine/level/bg.emp header.
    COLS, ROWS = 64, 64
    nt = bytearray(COLS * ROWS * 2)
    for col in range(COLS):
        for row in range(ROWS):
            word = layout[row * COLS + col]
            if word != 0:
                idx = word & 0x7FF
                word = (word & ~0x7FF) | ((idx + BG_TILE_BASE_SLOT) & 0x7FF)
            struct.pack_into('>H', nt, (col * ROWS + row) * 2, word)
    with open(os.path.join(out_dir, 'zone_bg.bin'), 'wb') as f:
        f.write(nt)

    # tile blob: BE byte-length header + raw 4bpp tiles
    blob = bytearray()
    for t in tiles:
        for row in range(8):
            for col in range(4):
                hi = t[row*8 + col*2] & 0xF
                lo = t[row*8 + col*2 + 1] & 0xF
                blob.append((hi << 4) | lo)
    # Tier-1 move.l blit contract (BG_Init .tile_copy): the runtime copies the
    # tile body a longword at a time, so the byte length must be a multiple of 4.
    # Tiles are 32 bytes each, so this holds by construction; assert it anyway so
    # a format change can never feed the move.l loop a sub-longword remainder.
    assert len(blob) % 4 == 0, f'BG tile blob must be 4-byte granular for move.l, got {len(blob)}'
    with open(os.path.join(out_dir, 'bg_tiles.bin'), 'wb') as f:
        f.write(struct.pack('>H', len(blob)))
        f.write(blob)
    print(f'[inject_editor_bg] wrote zone_bg.bin ({len(nt)}B) + bg_tiles.bin ({len(tiles)} tiles)')

    # optional: stamp a BG palette line. strip_gen copies ojz_palette.bin from
    # sonic_hack every build, so a palette that matches the injected art must be
    # written HERE (inject runs after strip_gen) or the colours revert.
    if 'palette' in data:
        cram_line = int(data.get('palette_line', 2)) & 3
        words = data['palette']
        assert len(words) == 16, f'palette must be 16 CRAM words, got {len(words)}'
        # ojz_palette.bin's 3 source lines load starting at CRAM line 1 (the
        # scroll test / act loader put OJZ_Palette at Palette_Buffer+$20), so
        # source line = cram_line - 1. The BG nametable references CRAM line 2.
        file_line = cram_line - 1
        assert file_line >= 0, 'BG palette maps to CRAM line >=1'
        pal_path = os.path.join(out_dir, 'ojz_palette.bin')
        pal = bytearray(open(pal_path, 'rb').read())
        for i, w in enumerate(words):
            struct.pack_into('>H', pal, file_line * 32 + i * 2, w & 0xFFFF)
        with open(pal_path, 'wb') as f:
            f.write(pal)
        print(f'[inject_editor_bg] stamped CRAM line {cram_line} (file line {file_line}, {len(words)} colours)')

def parse_args(argv=None):
    """`--zone`/`--act` as project.json INDICES — tools/effects_gen.py's signature.

    Indices rather than free-text ids on purpose: an id typed at the command line
    that names no declared act would resolve to a plausible directory and an
    override file that does not exist, i.e. a confusing FileNotFoundError instead of
    "project.json has no such act". The index goes through the same reader that
    validates the ids, so the failure names project.json.
    """
    p = argparse.ArgumentParser(
        description='Bake one act\'s editor-authored background over its generated '
                    'zone BG. Defaults to project.json\'s first act of its first zone.')
    p.add_argument('--zone', type=int, default=0,
                   help='zone INDEX in project.json (default: 0)')
    p.add_argument('--act', type=int, default=0,
                   help='act INDEX within that zone (default: 0)')
    return p.parse_args(argv)


if __name__ == '__main__':
    _args = parse_args()
    main(act_names(REPO, _args.zone, _args.act))
