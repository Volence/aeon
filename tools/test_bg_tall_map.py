#!/usr/bin/env python3
"""GATE BG-TALL, ROM-SIDE HALF — a background map taller than the plane, and a streamer with work.

REGIONS PART 2, STEP 5 (the empyrean OVERSEER sequence: "steps 1 to 6 in order ... steady-state
streaming"). NOT the v1 regions design's step 5, which is a different piece of work and is done.

WHAT THIS EXISTS TO STOP, stated as the failure it is aimed at rather than as a feature.

Steps 1 to 4 built the whole machine — the two record fields, the row-major blob, the row
producer, the region-aware blits, the region-derived position clamp and the rate clamp — and
NONE of it could be told apart from the code it replaced, because every shipped region row leaves
`rg_bg_span` at 0. Step 4's own ledger states the trap precisely: authoring the honest value does
not help either, because the background map IS the plane, so an honest span is PLANE_B_SPAN = 512,
whose ceiling is 512 - 224 = 288 — *exactly* the `VSCROLL_BG_MAX` the new clamp replaced. There is
no authored value that separates the two clamps until a map is a different height from the plane.

So the subject of this gate is not "does the streamer work" (that needs a running machine and is
TAGGED in the step-5 ledger). It is the prior question, the one that has silently been answered
NO for four steps: **is there anything on this tree that the new code behaves differently on than
the old code would?** Leg 1 is that question and nothing else.

THE FIVE LEGS, and what fraction of the outcome space each accepts.

  1. THE DISCRIMINATOR. Some region row in the DEBUG act declares `rg_bg_span` strictly greater
     than PLANE_B_SPAN, so the step-4 clamp's ceiling (span - SCREEN_HEIGHT) is a value the
     pre-step-4 code could not produce. ACCEPTS: spans in (512, inf). REFUSES: the entire space
     every tree before this parcel occupied — all-zero spans, and any span <= 512 (which includes
     the "honest" 512 the trap is made of). This leg is RED on aeon master and on the step-1
     through step-4 trees; that is checked by running it against them, not asserted.

  2. THE MAP IS REAL. That row's `rg_bg_layout` points at a blob in the ROM byte-identical to the
     committed 12288-byte file, and the blob's 96 rows are PAIRWISE DISTINCT. The second half is
     not pedantry: the plane is a 64-row ring, so map row m is shown by plane row m mod 64, and
     a nametable reader can only say WHICH map row a plane row holds if rows p and p+64 differ.
     Without it a streamer that never ran and one that ran correctly could read identical.

  3. THE STREAMER HAS WORK TO DO, DERIVED. From the region's own rectangle, the parallax config
     it actually resolves to (v_factor / v_center / v_offset read out of the ROM, through
     Effects_ResolveParallax's own precedence), and the engine's own constants, this computes how
     many DISTINCT window-top rows the tracker must visit as the camera crosses the region — and
     asserts it is greater than ZERO. The same arithmetic is then run with the OLD ceiling
     substituted, and the two must DIFFER: that is the old-vs-new comparison done on numbers this
     ROM supplies rather than on a claim. ACCEPTS: nothing on any earlier tree, where both
     computations give 0 and are therefore equal.

  4. RELEASE IS UNTOUCHED. No release region row names a non-zero span, and the 12 KB test blob
     is absent from `s4.bin` — the "nothing visible changes before step 6" half, checked on bytes.

  5. THE TRACKER IS WIRED. `BG_Stream_Update` is in the listing AND is the target of a real call
     instruction in the ROM image. A proc nothing calls is the exact shape `Draw_BG_TileRow` had
     for three steps; naming it in a source file is not evidence it runs.

WHAT A GREEN HERE DOES NOT SAY, and this is the important sentence. It says nothing about the
picture. Every leg reads ROM bytes and arithmetic over them; not one observes the VDP. A build
that computes the right window and writes it to the wrong VRAM address passes all five. The
nametable half of BG-TALL is TAGGED for the foreground in the step-5 ledger, with its sampled
scroll values and expected row contents derived by tools/bg_tall_map_witness.py.
"""

import hashlib
import os
import unittest

import pytest

import region_table

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DBG_ROM = os.path.join(AEON, "s4.debug.bin")
DBG_LST = os.path.join(AEON, "s4.debug.lst")
REL_ROM = os.path.join(AEON, "s4.bin")
REL_LST = os.path.join(AEON, "s4.lst")
TALL_BLOB = os.path.join(AEON, "games/sonic4/data/generated/ojz/act1/zone_bg_tall_debug.bin")
ACT_SYMBOL = "OJZ_Act1_Descriptor"
TRACKER_SYMBOL = "BG_Stream_Update"

# Engine constants, each re-derived from its own source file rather than typed here, because a
# gate that copies a number from a nearby pin measures the copy. See _engine_consts().
CONST_SOURCES = {
    "PLANE_H_CELLS": ("engine/system/constants.emp", "PLANE_H_CELLS"),
    "PLANE_V_CELLS": ("engine/system/constants.emp", "PLANE_V_CELLS"),
    "SCREEN_HEIGHT": ("engine/system/constants.emp", "SCREEN_HEIGHT"),
}

# parallax_config's vertical mapping fields, by their own `@ $HH` annotations in the struct.
PCFG_FIELDS = ("pcfg_v_factor_bg", "pcfg_v_center_y", "pcfg_v_offset")


def _read(path):
    with open(path, "rb") as fh:
        return fh.read()


def _engine_consts():
    """The three plane/screen constants, read out of engine/system/constants.emp by name."""
    import re
    text = open(os.path.join(AEON, "engine/system/constants.emp"), errors="replace").read()
    out = {}
    for key, (_rel, name) in CONST_SOURCES.items():
        m = re.search(rf"^\s*pub\s+const\s+{re.escape(name)}\s*=\s*(\d+)", text, re.M)
        if not m:
            raise region_table.LayoutError(
                f"engine/system/constants.emp no longer declares `pub const {name} = <int>`. "
                f"Every expectation in tools/test_bg_tall_map.py is derived from it, so this is "
                f"a setup failure and MUST NOT be defaulted to a remembered value.")
        out[key] = int(m.group(1))
    return out


def _pcfg_offsets():
    """parallax_config field offsets, read off the struct's own `@ $HH` annotations."""
    import re
    text = open(os.path.join(AEON, "engine/structs.emp"), errors="replace").read()
    out = {}
    for name in PCFG_FIELDS:
        m = re.search(rf"^\s*{re.escape(name)}\s*:[^/\n]*//\s*\$([0-9A-Fa-f]+)", text, re.M)
        if not m:
            raise region_table.LayoutError(
                f"`struct parallax_config` (engine/structs.emp) no longer annotates `{name}` "
                f"with its `$HH` offset — leg 3's vertical mapping is read through it")
        out[name] = int(m.group(1), 16)
    return out


def lst_symbols(path):
    """Symbol -> 24-bit address out of a sigil listing. A local re-derivation, matching
    tools/test_bg_stream_vdeform_exclusion.py's, for its stated reason."""
    out = {}
    with open(path, errors="replace") as fh:
        for line in fh:
            if not line.startswith("(0) "):
                continue
            try:
                addrpart, namepart = line[4:].split(" :", 1)
                addr = int(addrpart.split("/", 1)[1], 16)
            except (ValueError, IndexError):
                continue
            nm = namepart.strip().rstrip(":")
            if nm and "$" not in nm and nm not in out:
                out[nm] = addr & 0xFFFFFF
    return out


def _resolve_parallax(rom, row, act_base, aeon=AEON):
    """The parallax config a region row actually gets, through Effects_ResolveParallax's ladder:
    Region.rg_parallax > EffectsPreset.ep_parallax > Act.act_parallax_config (engine/effects/
    preset.emp). Returns the config's ROM address; raises rather than returning 0, because a row
    whose config cannot be resolved is a setup failure and must not read as 'nothing offended'."""
    import re
    if row["parallax"]:
        return row["parallax"]
    preset = open(os.path.join(aeon, "engine/effects/preset.emp"), errors="replace").read()
    m = re.search(r"^\s*ep_parallax\s*:[^@\n]*@\s*\$([0-9A-Fa-f]+)", preset, re.M)
    if not m:
        raise region_table.LayoutError(
            "`struct EffectsPreset` no longer declares ep_parallax with an `@ $HH` offset")
    ep = int.from_bytes(rom[row["effects"] + int(m.group(1), 16):][:4], "big")
    if ep:
        return ep
    # region_table's own AEON (a Path) — not this module's string one.
    acts, _ = region_table.struct_layout("Act")
    act_cfg = int.from_bytes(rom[act_base + acts["act_parallax_config"]:][:4], "big")
    if not act_cfg:
        raise region_table.LayoutError(
            f"region row {row['index']} binds no parallax, its preset binds none, and "
            f"Act.act_parallax_config is 0 — the resolution ladder has no bottom rung, so "
            f"leg 3 cannot compute a vertical mapping and MUST NOT report 0 work")
    return act_cfg


def _tops_visited(rom, row, cfg, k, ceiling):
    """The set of distinct window-top rows BG_Stream_Update visits as the camera crosses this
    region vertically, under a given position-clamp CEILING.

    This is `engine/level/bg.emp`'s own arithmetic restated in Python, against
    `Parallax_Step5_Vscroll`'s vertical mapping read out of the ROM:

        vscroll  = clamp(((camY - v_center) >> v_factor) + v_offset, 0, ceiling)
        want_top = clamp((vscroll >> 3) - LEAD, 0, map_rows - PLANE_V_CELLS)

    The camera CENTRE is what the crossing resolves on (Parallax_CheckBoundary), and the centre's
    reachable Y inside this rectangle is what the walk can actually produce.
    """
    po = _pcfg_offsets()
    v_factor = rom[cfg + po["pcfg_v_factor_bg"]]
    v_center = int.from_bytes(rom[cfg + po["pcfg_v_center_y"]:][:2], "big")
    v_offset = int.from_bytes(rom[cfg + po["pcfg_v_offset"]:][:2], "big")

    plane_rows = k["PLANE_V_CELLS"]
    screen_rows = k["SCREEN_HEIGHT"] // 8 + 1
    lead = (plane_rows - screen_rows) // 2
    map_rows = row["bg_span"] // 8 if row["bg_span"] else plane_rows
    max_top = max(0, map_rows - plane_rows)

    tops = set()
    bound_at = None          # the first camera Y at which the ceiling is what STOPS the scroll
    raw_hi = None
    for cam_y in range(row["y0"], row["y1"] + 1):
        raw = ((cam_y - v_center) >> v_factor) + v_offset
        raw_hi = raw if raw_hi is None else max(raw_hi, raw)
        if raw > ceiling and bound_at is None:
            bound_at = cam_y
        v = 0 if raw < 0 else (ceiling if raw > ceiling else raw)
        want = (v >> 3) - lead
        want = 0 if want < 0 else (max_top if want > max_top else want)
        tops.add(want)
    return tops, dict(v_factor=v_factor, v_center=v_center, v_offset=v_offset,
                      lead=lead, map_rows=map_rows, max_top=max_top,
                      raw_vscroll_max=raw_hi, ceiling=ceiling, ceiling_binds_at=bound_at)


def _calls_to(rom, target):
    """Count real 68000 call instructions in `rom` whose target is `target`: `jsr abs.l`
    ($4EB9 + 32-bit address) and `bsr.w` ($6100 + signed 16-bit displacement from PC+2).

    Both forms are counted because sigil relaxes transfers by reach — `jbsr` is spelled at
    every call site in `.emp` and which encoding it becomes is the linker's choice, so a
    checker that knew only one encoding would report 'never called' on a perfectly wired
    tracker the day a section moved.
    """
    n = 0
    for at in range(0, len(rom) - 6, 2):
        w = int.from_bytes(rom[at:at + 2], "big")
        if w == 0x4EB9:
            if int.from_bytes(rom[at + 2:at + 6], "big") == target:
                n += 1
        elif w == 0x6100:
            disp = int.from_bytes(rom[at + 2:at + 4], "big")
            if disp >= 0x8000:
                disp -= 0x10000
            if at + 2 + disp == target:
                n += 1
    return n


class BgTallMap(unittest.TestCase):

    def _setup(self, rom_path, lst_path):
        for p in (rom_path, lst_path):
            self.assertTrue(os.path.isfile(p),
                            f"{p} is missing — this arm grades the built image and would "
                            f"otherwise pass by not running")
        rom = _read(rom_path)
        syms = lst_symbols(lst_path)
        self.assertIn(ACT_SYMBOL, syms,
                      f"{lst_path} has no `{ACT_SYMBOL}` — this is not the listing that pairs "
                      f"with {rom_path}, and every row below would be read from the wrong place")
        base = syms[ACT_SYMBOL]
        return rom, syms, base, region_table.read_regions(rom, base)

    # ---- LEG 1 + LEG 2 + LEG 3: the DEBUG shape, where the tall map lives ----
    @pytest.mark.needs_build("s4.debug.bin", "s4.debug.lst")
    def test_a_region_declares_a_map_taller_than_the_plane(self):
        k = _engine_consts()
        plane_span = k["PLANE_V_CELLS"] * 8
        old_ceiling = plane_span - k["SCREEN_HEIGHT"]        # VSCROLL_BG_MAX, the pre-step-4 one
        rom, syms, base, rows = self._setup(DBG_ROM, DBG_LST)

        # ---- LEG 1: the discriminator ----
        tall = [r for r in rows if r["bg_span"] > plane_span]
        spans = sorted({r["bg_span"] for r in rows})
        self.assertTrue(
            tall,
            f"NO region row in the DEBUG act declares a background map taller than the plane. "
            f"{len(rows)} rows read, spans present: {spans} (0 = the act default). "
            f"PLANE_B_SPAN is {plane_span}.\n"
            f"This is the state every tree through regions part 2 step 4 was in, and it is the "
            f"reason those steps were unmeasurable: with no span above {plane_span} the step-4 "
            f"clamp's ceiling is always {old_ceiling}, which is exactly the VSCROLL_BG_MAX it "
            f"replaced, and BG_Stream_Update's max_top is always 0 so it never moves the window. "
            f"A span of exactly {plane_span} does NOT fix this — it computes the same {old_ceiling}.")
        self.assertEqual(
            len(tall), 1,
            f"expected exactly one tall-map region row in the DEBUG act, found {len(tall)}: "
            f"{[(r['index'], r['bg_span']) for r in tall]}. More than one is not wrong in itself, "
            f"but leg 3 below derives its expectations from THE tall row and would be silently "
            f"reporting about only the first.")
        row = tall[0]

        # NO SEPARATE `ceiling != VSCROLL_BG_MAX` ASSERTION HERE, DELIBERATELY, AND THE REASON IS
        # WORTH THE SENTENCE. One was written and DELETED before this file landed: with
        # old_ceiling = PLANE_V_CELLS*8 - SCREEN_HEIGHT and the predicate above already requiring
        # bg_span > PLANE_V_CELLS*8, `bg_span - SCREEN_HEIGHT > old_ceiling` follows by
        # subtraction and the assertion could never fire. A check that cannot fail is the vacuity
        # this file is about, and shipping one inside the gate against vacuity would have been
        # the joke version of it. The implication IS the coverage; the predicate above is where
        # it is enforced.
        new_ceiling = row["bg_span"] - k["SCREEN_HEIGHT"]

        # ---- LEG 2: the map is real, and its rows are distinguishable ----
        self.assertTrue(os.path.isfile(TALL_BLOB), f"{TALL_BLOB} is missing")
        blob = _read(TALL_BLOB)
        row_bytes = k["PLANE_H_CELLS"] * 2
        self.assertEqual(
            len(blob), (row["bg_span"] // 8) * row_bytes,
            f"the committed blob is {len(blob)} B but row {row['index']} declares span "
            f"{row['bg_span']} px = {row['bg_span'] // 8} rows x {row_bytes} B = "
            f"{(row['bg_span'] // 8) * row_bytes} B. A span that disagrees with its blob makes "
            f"the streamer read past the end of the map.")
        self.assertTrue(row["bg_layout"],
                        f"region row {row['index']} declares a span of {row['bg_span']} but NO "
                        f"bg_layout, so it would stream rows out of the act default — an 8192-byte "
                        f"blob — for {row['bg_span'] // 8} rows' worth of map")
        at = row["bg_layout"]
        seg = rom[at:at + len(blob)]
        self.assertEqual(
            hashlib.md5(seg).hexdigest(), hashlib.md5(blob).hexdigest(),
            f"the {len(blob)} ROM bytes at rg_bg_layout ({at:#x}) are not the committed blob. "
            f"A stale ROM and a stale blob are indistinguishable from this message alone: rebuild "
            f"before reading it as a defect.")
        nrows = row["bg_span"] // 8
        seen = {}
        dupes = []
        for r in range(nrows):
            key = blob[r * row_bytes:(r + 1) * row_bytes]
            if key in seen:
                dupes.append((seen[key], r))
            seen[key] = r
        self.assertFalse(
            dupes,
            f"map rows {dupes[:4]} are byte-identical. The plane is a {k['PLANE_V_CELLS']}-row "
            f"ring, so map row m is shown by plane row m mod {k['PLANE_V_CELLS']}; with duplicate "
            f"rows a nametable reader cannot say which map row a plane row holds, and 'the "
            f"streamer never ran' reads the same as 'the streamer ran correctly'. "
            f"tools/gen_tall_bg_test.py's marker cell is what prevents this — check it still runs.")

        # ---- LEG 3: the streamer has work, and the two ceilings disagree ----
        cfg = _resolve_parallax(rom, row, base)
        new_tops, info = _tops_visited(rom, row, cfg, k, new_ceiling)
        old_tops, _ = _tops_visited(rom, row, cfg, k, old_ceiling)
        self.assertGreater(
            len(new_tops), 1,
            f"region row {row['index']} never moves the window: over camera Y "
            f"{row['y0']}..{row['y1']} the tracker visits window tops {sorted(new_tops)}. "
            f"Mapping read from the ROM: {info}. A tall map under a config that does not move "
            f"the BG vertically (v_factor 15 is the LOCKED plane, and 18 of the 20 OJZ scenes "
            f"author it) streams nothing ever — the instrument cannot produce the answer it "
            f"claims to look for.")
        self.assertNotEqual(
            new_tops, old_tops,
            f"the new ceiling ({new_ceiling}) and the old one ({old_ceiling}) send the tracker "
            f"to the SAME set of window tops, {sorted(new_tops)}. The clamp change is then "
            f"unobservable here too, and this gate would be measuring nothing. "
            f"Mapping: {info}.")
        # ---- LEG 3b: THE NEW CEILING IS EXERCISED AS A CONSTRAINT, not merely as a number ----
        # Added after the first cut of this fixture was found to be half a test. A rectangle
        # that only makes the two ceilings DISAGREE proves the clamp changed; it does not prove
        # the NEW ceiling ever stops anything. Testing a clamp only where it does not clamp
        # leaves the one line that does the clamping ungraded — and that line is step 4's whole
        # subject. The region has to reach a raw scroll ABOVE the new ceiling.
        self.assertIsNotNone(
            info["ceiling_binds_at"],
            f"the new ceiling {new_ceiling} is never REACHED inside region {row['index']}: the "
            f"largest raw scroll the camera can produce over camera Y {row['y0']}..{row['y1']} "
            f"is {info['raw_vscroll_max']}. The two clamps may still disagree (the old one binds "
            f"and the new one does not), which is why this is a SEPARATE leg — but no camera "
            f"path then puts the new ceiling on the deciding side of a compare, so "
            f"Parallax_Step5_Vscroll's `cmp.w d3,d2 / move.w d3,d2` arm is never taken with the "
            f"region-derived value and step 4's BG-RATE gate stays vacuous. Mapping: {info}. "
            f"Extend the region's Y range (the fixture reaches the new ceiling only above "
            f"camera Y {(new_ceiling << info['v_factor']) + info['v_center']}).")
        print(f"\nBG-TALL leg 3: row {row['index']} [x {row['x0']}..{row['x1']}, "
              f"y {row['y0']}..{row['y1']}] span {row['bg_span']} ({info['map_rows']} rows), "
              f"cfg {cfg:#x} v_factor {info['v_factor']} v_center {info['v_center']} "
              f"v_offset {info['v_offset']}, lead {info['lead']}, max_top {info['max_top']}\n"
              f"  window tops NEW ceiling {new_ceiling}: {min(new_tops)}..{max(new_tops)} "
              f"({len(new_tops)} distinct)\n"
              f"  window tops OLD ceiling {old_ceiling}: {min(old_tops)}..{max(old_tops)} "
              f"({len(old_tops)} distinct)\n"
              f"  raw vscroll reaches {info['raw_vscroll_max']}; the NEW ceiling {new_ceiling} "
              f"BINDS from camera Y {info['ceiling_binds_at']} (leg 3b)")

    # ---- LEG 5: the tracker is CALLED ----
    @pytest.mark.needs_build("s4.debug.bin", "s4.debug.lst")
    def test_the_tracker_is_called(self):
        rom, syms, _base, _rows = self._setup(DBG_ROM, DBG_LST)
        self.assertIn(
            TRACKER_SYMBOL, syms,
            f"`{TRACKER_SYMBOL}` is not in {DBG_LST}. The steady-state streamer was not emitted, "
            f"so every other leg here is describing data nothing reads.")
        n = _calls_to(rom, syms[TRACKER_SYMBOL])
        self.assertGreaterEqual(
            n, 1,
            f"`{TRACKER_SYMBOL}` is at {syms[TRACKER_SYMBOL]:#x} and NOTHING in the ROM calls it "
            f"(no `jsr abs.l` and no `bsr.w` resolves there). That is exactly the state "
            f"`Draw_BG_TileRow` was in for three steps: present, correct, and never run. "
            f"The wiring is three `jbsr BG_Stream_Update` in "
            f"games/sonic4/test/ojz_scroll_test.emp (boot, per-frame, warp).")
        print(f"\nBG-TALL leg 5: {TRACKER_SYMBOL} at {syms[TRACKER_SYMBOL]:#x}, {n} call site(s)")

    # ---- LEG 4: release is untouched ----
    @pytest.mark.needs_build("s4.bin", "s4.lst")
    def test_release_carries_no_tall_map(self):
        k = _engine_consts()
        rom, _syms, _base, rows = self._setup(REL_ROM, REL_LST)
        offenders = [(r["index"], r["bg_span"]) for r in rows if r["bg_span"]]
        self.assertFalse(
            offenders,
            f"release region rows declare non-zero spans {offenders}. The owner's sequence says "
            f"NOTHING VISIBLE CHANGES BEFORE STEP 6, and a span above "
            f"{k['PLANE_V_CELLS'] * 8} changes where the background sits on screen. The step-5 "
            f"test map is DEBUG-only by construction (act_assets.emp / act_descriptor.emp both "
            f"gate on `if DEBUG == 1`) — a span here means one of those gates was lost.")
        self.assertTrue(os.path.isfile(TALL_BLOB))
        blob = _read(TALL_BLOB)
        self.assertNotIn(
            blob, rom,
            f"the {len(blob)}-byte DEBUG test map is present in the RELEASE ROM. The embed's "
            f"`if DEBUG == 1 {{ embed(..) }} else {{ [] }}` gate in act_assets.emp is what keeps "
            f"12 KB of test data out of the shipped image.")
        # A probe rather than only the whole blob: a blob that landed in PIECES, or with one byte
        # changed, would slip past the `assertNotIn` above while still being 12 KB of dead weight.
        row_bytes = k["PLANE_H_CELLS"] * 2
        probe = blob[64 * row_bytes:64 * row_bytes + 64]
        self.assertNotIn(
            probe, rom,
            f"a 64-byte slice of the DEBUG test map's row 64 is present in the RELEASE ROM at "
            f"offset {rom.find(probe):#x}, even though the whole blob is not. Part of the test "
            f"map reached the shipped image.")


if __name__ == "__main__":
    unittest.main()
