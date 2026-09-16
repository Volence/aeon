#!/usr/bin/env python3
"""A STREAMED region may not also name a per-column vertical deform table.

THE HAZARD, in the engine's own terms. `CAP_PER_COL_VSRAM` and Step 4a's band
rotation read Plane-B lines through `and.w #PLANE_B_SPAN-1`
(`engine/level/parallax.emp`): they assume ANY plane line holds valid art,
because today the whole plane is resident and every line does. A region that
streams its background — one that names its own `rg_bg_layout`, or a
`rg_bg_span` taller than the plane — turns Plane B into a vertical ring in which
only the window plus its lead is valid; a per-column read of the rest samples
whatever the streamer has not reached yet. Regions part 2 spec §4.2 names the
combination and asks for a build-time refusal.

WHY THIS IS A PYTEST AND NOT THE `ensure` THE SPEC ASKS FOR. MEASURED
2026-09-15 (regions part 2, step 2), against the sigil release binary that
builds this tree:

  * `Region.rg_parallax` reaches `ojz_region()` as a `Label`, and `.emp` has no
    comptime dereference of one. The half of the fact that lives in the parallax
    config — `pcfg_v_deform_table_bg` — is therefore invisible at the only call
    site where the other half (`bg_layout` / `bg_span`) is known.
  * WORSE THAN UNAVAILABLE: a spelling that LOOKS like it reads it is silently
    vacuous. `ensure(parallax_config.pcfg_v_deform_table_bg(parallax) == 12345,
    ...)` and its exact negation `!= 12345` BOTH built GREEN from act 1's real
    region rows, in a tree where a plain `ensure(1 == 0, ...)` at the same line
    went red 55 times (the control, run first). So the condition is not being
    decided at all, and an author who wrote the spec's guard in the obvious
    spelling would have shipped a permanently vacuous one with no diagnostic.

So the refusal is made where both halves are readable at once: the built ROM,
where a region row is bytes and the config it points at is bytes.

WHAT IT EXAMINES, AND HOW IT COULD FAIL. Every region row of the act, and for
each one the vertical-deform word of the parallax config it actually resolves to
— real bytes, read per row, through Effects_ResolveParallax's own rungs. A row
whose config could not be resolved is a SETUP failure here, not a quiet skip, so
"I read nothing" can never come out the same colour as "I read ten rows and none
offended". The predicate fires the day a row gains `bg_layout` or `bg_span` while
its config carries a table — which is exactly what regions part 2 step 6 is about
to author, and what this was proven red against (a mutated row, rebuilt, then
restored).

WHAT A GREEN DOES NOT SAY: that the combination has ever been exercised. At the
pin no act declares a streamed region and no REGION-bound config names a table
(the tables that ship are on lab scenes; tools/left_col_mask_probe.py already
asserts the act-installed configs carry none). Both populations are printed in
the failure text so a reader can see which side moved.
"""

import os
import re
import unittest

import pytest

import region_table

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM = os.path.join(AEON, "s4.bin")
LST = os.path.join(AEON, "s4.lst")
ACT_SYMBOL = "OJZ_Act1_Descriptor"

# The field this refuses, by NAME in the source's own struct, so a rename or a
# reordering is a setup error here rather than a four-byte slide that reads a
# neighbouring word and reports "clean".
VDEFORM_FIELD = "pcfg_v_deform_table_bg"
PRESET = os.path.join(AEON, "engine", "effects", "preset.emp")
PRESET_PARALLAX_FIELD = "ep_parallax"
ACT_PARALLAX_FIELD = "act_parallax_config"


def preset_field_offset(name):
    """One EffectsPreset field's offset, read off its own `@ $HH` annotation.

    `struct EffectsPreset` states every offset EXPLICITLY (engine/effects/preset.emp),
    which region_table.struct_layout — an accumulator over field types — does not parse.
    Reading the stated offset is the better reader for this declaration anyway: it is the
    number the assembler uses, not a reconstruction of it.
    """
    text = open(PRESET, errors="replace").read()
    m = re.search(rf"^\s*{re.escape(name)}\s*:[^@\n]*@\s*\$([0-9A-Fa-f]+)", text, re.M)
    if not m:
        raise region_table.LayoutError(
            f"`struct EffectsPreset` in engine/effects/preset.emp does not declare "
            f"`{name}` with an `@ $HH` offset — the rung this follows has changed shape")
    return int(m.group(1), 16)


def lst_symbols(path):
    """Symbol -> 24-bit address out of a sigil listing (`(0) <idx>/<hex> :  Name:`).

    A local re-derivation, matching tools/effects_gates.py's, for its reason: the
    shared copies live in modules that drag an Aether client import behind them.
    """
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


class BgStreamVDeformExclusion(unittest.TestCase):

    @pytest.mark.needs_build("s4.bin", "s4.lst")
    def test_no_streamed_region_names_a_per_column_v_deform_table(self):
        for p in (ROM, LST):
            self.assertTrue(os.path.isfile(p),
                            f"{p} is missing — this arm grades the built image and would "
                            "otherwise pass by not running")
        rom = open(ROM, "rb").read()
        syms = lst_symbols(LST)
        self.assertIn(ACT_SYMBOL, syms,
                      f"{ACT_SYMBOL} is not in s4.lst — the act descriptor this reads through "
                      "has been renamed, so the measurement could not be made")

        # Offsets come from engine/structs.emp's own declarations (region_table parses
        # them and cross-checks every trailing `// $HH` against the accumulation), never
        # from a number written here.
        pcfg_off, _ = region_table.struct_layout("parallax_config")
        self.assertIn(VDEFORM_FIELD, pcfg_off,
                      f"`struct parallax_config` no longer declares {VDEFORM_FIELD} — the "
                      "field this refuses has been renamed")
        ep_parallax = preset_field_offset(PRESET_PARALLAX_FIELD)
        act_off, _ = region_table.struct_layout("Act")
        self.assertIn(ACT_PARALLAX_FIELD, act_off,
                      f"`struct Act` no longer declares {ACT_PARALLAX_FIELD} — the last rung "
                      "of the parallax resolve has been renamed")

        rows = region_table.read_regions(rom, syms[ACT_SYMBOL])

        def u32(at):
            return int.from_bytes(rom[at:at + 4], "big")

        # Per row: does it stream, and does its RESOLVED parallax config name a
        # per-column vertical deform table? Both halves are read from the image.
        def config_for(r):
            """Effects_ResolveParallax's rungs, restated: the row's own config outranks
            the preset's, and the act default is the last rung. A row that defers still
            HAS a config, so this must follow the rungs rather than call 0 "no config"."""
            if r["parallax"]:
                return r["parallax"], "rg_parallax"
            if r["effects"]:
                cfg = u32(r["effects"] + ep_parallax)
                if cfg:
                    return cfg, "the preset's ep_parallax"
            cfg = u32(syms[ACT_SYMBOL] + act_off[ACT_PARALLAX_FIELD])
            return cfg, "the act default"

        streamed, vdeform, offenders, unresolved = [], [], [], []
        for r in rows:
            streams = r["bg_layout"] != 0 or r["bg_span"] != 0
            cfg, source = config_for(r)
            if not cfg:
                unresolved.append(r["index"])
                continue
            tbl = u32(cfg + pcfg_off[VDEFORM_FIELD])
            if streams:
                streamed.append(r["index"])
            if tbl:
                vdeform.append(r["index"])
            if streams and tbl:
                offenders.append(
                    "region %d [x %d..%d, y %d..%d] streams (bg_layout $%X, bg_span %d) "
                    "and its parallax config $%X (via %s) names %s = $%X"
                    % (r["index"], r["x0"], r["x1"], r["y0"], r["y1"],
                       r["bg_layout"], r["bg_span"], cfg, source, VDEFORM_FIELD, tbl))

        self.assertEqual(
            unresolved, [],
            "%d of %s's %d region rows resolve to NO parallax config at all (rows %s). "
            "Effects_ResolveParallax's last rung is Act.act_parallax_config, which the act "
            "constructor requires, so a zero there means the resolve restated above has "
            "drifted from the engine's — and an unread row cannot offend, which would make "
            "the assertion below quieter than it looks."
            % (len(unresolved), ACT_SYMBOL, len(rows), unresolved))

        self.assertEqual(
            offenders, [],
            "a region both STREAMS its background and names a per-column vertical deform "
            "table (%d of %d rows stream; %d carry a table). On a streamed plane only the "
            "window plus its lead holds valid art, and CAP_PER_COL_VSRAM / the band "
            "rotation read ANY plane line through `and.w #PLANE_B_SPAN-1` "
            "(engine/level/parallax.emp). Give the region the act-default layout and a span "
            "equal to the plane, or give it a parallax config with %s = 0:\n  "
            % (len(streamed), len(rows), len(vdeform), VDEFORM_FIELD)
            + "\n  ".join(offenders))


if __name__ == "__main__":
    unittest.main()
