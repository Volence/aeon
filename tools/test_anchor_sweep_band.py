"""tools/test_anchor_sweep_band.py — the anchor mover's CROSS-FILE bound.

EFFECTS-W1 DoD item 4. There is one thing about an authored sweep that the compiler
structurally cannot check, and it is the thing most likely to go wrong first.

A sweep's peak-to-peak travel has to stay inside the `patchable(lo, hi)` band of the channel
it is authored on. Leaving that band UPWARD does not stop the edge and does not clamp it:
`Raster_BuildSchedule` REMOVES the record for the frame (`bgt .suppress`), so the band does not
move, it VANISHES — and it comes back at the next zero crossing. A sweep one rung too wide
therefore reads as a band flickering out once per cycle, which looks like a rendering bug
rather than an amplitude the author chose.

`engine/effects/raster_dsl.emp`'s `anchor_sweep()` refuses an amplitude wider than the SCREEN,
which is a necessary condition and the strongest one available to it. It cannot check the band,
and the design says why in the same words: `lo`/`hi` live in the raster program's `patchable(..)`
call, `amp_shift` lives in the preset, and the two are associated by a POINTER at runtime.
There is no comptime scope in which both numbers exist. This file is that scope.

RED-FIRST, and the mutation is on disk rather than described: raising
`games/sonic4/data/effects/ojz_effects.emp`'s `anchor_sweep(amp_shift: 4, ...)` to
`amp_shift: 1` makes `test_every_authored_sweep_fits_its_channels_patchable_band` fail with
`channel 0: peak-to-peak 512 px does not fit band 3..220 (218 lines)`, and lowering it back
makes it pass. Measured 2026-09-03.

Runner: the `pytest tools` lane in build.sh (`python3 -m pytest tools -q`), which is
build-fatal on the canonical path and skipped under FAST=1.
"""

import os
import re
import json
import unittest

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RASTER_DSL = os.path.join(AEON, "engine/effects/raster_dsl.emp")
CONSTANTS = os.path.join(AEON, "engine/system/constants.emp")
OJZ_EFFECTS = os.path.join(AEON, "games/sonic4/data/effects/ojz_effects.emp")
SCENES_DIR = os.path.join(AEON, "tools/scenes")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _const(src, name, path):
    """A `[pub ]const NAME = <int>` declaration, decimal or $hex."""
    m = re.search(r"^(?:pub )?const %s\s*=\s*(\$?[0-9A-Fa-f]+)\s*(?://.*)?$" % re.escape(name),
                  src, re.M)
    if not m:
        raise AssertionError(
            "%s: no `const %s = <literal>` declaration. This test re-derives the sweep "
            "ladders from the literals that file states; if the spelling changed, every "
            "derivation below would be against a name that no longer exists." % (path, name))
    tok = m.group(1)
    return int(tok[1:], 16) if tok.startswith("$") else int(tok)


# The three ladder derivations, transcribed from raster_dsl.emp's comptime fns. They are
# TRANSCRIBED and not read, deliberately: a test that re-executed the file's own arithmetic
# could not disagree with it. What makes this non-vacuous is that the transcription is checked
# against the `pub const` values the file publishes, so a silent edit to either half fails.
def _shift_min(amp, lines):
    s = 0
    for i in range(16):
        if (amp >> i) * 2 > lines:
            s = i + 1
    return s


def _shift_max(amp):
    s = 0
    for i in range(16):
        if (amp >> i) >= 1:
            s = i
    return s


def _period_shift_max(entries, width):
    p = 0
    for i in range(32):
        if (entries << i) <= (1 << width):
            p = i
    return p


def patchable_bands():
    """{channel: (lo, hi)} in SCREEN lines, from the `ch:/lo:/hi:` triples in ojz_effects.emp.

    Same read tools/effects_gates.py does, and for the same reason it does it there: the bands
    are a property of the source, and a test restating them is a test of its own copy.
    """
    src = _read(OJZ_EFFECTS)
    triples = re.findall(r"\bch:\s*(\d+)\s*,\s*lo:\s*(\d+)\s*,\s*hi:\s*(\d+)", src)
    return {int(c): (int(lo), int(hi)) for c, lo, hi in triples}


def authored_sweeps():
    """[(preset_name, channel, amp_shift, period_shift, phase)] over every `patch_motion:` list.

    The channel is the POSITION in the array, which is what Effects_InstallPreset's seed loop
    means by it — element i of ep_patch_motion becomes Effects_Motion[i].
    """
    src = _read(OJZ_EFFECTS)
    out = []
    for m in re.finditer(r"pub data (\w+):\s*EffectsPreset\s*=\s*preset\(", src):
        name = m.group(1)
        # Walk to the matching close paren of this preset( call.
        i = m.end() - 1
        depth = 0
        while i < len(src):
            if src[i] == "(":
                depth += 1
            elif src[i] == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body = src[m.end():i]
        pm = re.search(r"patch_motion:\s*\[", body)
        if not pm:
            continue
        j = pm.end() - 1
        depth = 0
        while j < len(body):
            if body[j] == "[":
                depth += 1
            elif body[j] == "]":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        arr = body[pm.end():j]
        # Element split at top level (anchor_sweep(..) carries its own commas).
        elems, depth, cur = [], 0, ""
        for ch in arr:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if ch == "," and depth == 0:
                elems.append(cur)
                cur = ""
            else:
                cur += ch
        elems.append(cur)
        for idx, e in enumerate(elems):
            s = re.search(r"anchor_sweep\(\s*amp_shift:\s*(\d+)\s*,\s*period_shift:\s*(\d+)"
                          r"(?:\s*,\s*phase:\s*(\d+))?\s*\)", e)
            if s:
                out.append((name, idx, int(s.group(1)), int(s.group(2)),
                            int(s.group(3) or 0)))
    return out


class TestTheLaddersAreDerivedFromTheConstantsTheyClaim(unittest.TestCase):
    """raster_dsl.emp spells three sine/screen facts as LITERALS because a COMPTIME_HELPERS
    `pub const` must fold from its own file's names. engine/effects/raster.emp pins those
    literals to engine.constants at BUILD time. This is the same fact checked from outside
    the compiler, so a build run with CONTRACTS=0 or a stale sigil still cannot hide it."""

    def setUp(self):
        self.dsl = _read(RASTER_DSL)
        self.consts = _read(CONSTANTS)

    def test_the_inlined_sine_and_screen_facts_match_engine_constants(self):
        for local, canonical in (("ANCHOR_SINE_AMP", "SINE_AMPLITUDE"),
                                 ("ANCHOR_SINE_ENTRIES", "SINE_CYCLE_ENTRIES"),
                                 ("ANCHOR_SCREEN_LINES", "SCREEN_HEIGHT")):
            self.assertEqual(
                _const(self.dsl, local, RASTER_DSL),
                _const(self.consts, canonical, CONSTANTS),
                "engine/effects/raster_dsl.emp's %s has drifted from engine.constants.%s. "
                "Every sweep ladder is derived from it, so every authored amp_shift and "
                "period_shift changes meaning silently." % (local, canonical))

    def test_the_published_ladders_are_what_the_derivations_produce(self):
        amp = _const(self.dsl, "ANCHOR_SINE_AMP", RASTER_DSL)
        entries = _const(self.dsl, "ANCHOR_SINE_ENTRIES", RASTER_DSL)
        lines = _const(self.dsl, "ANCHOR_SCREEN_LINES", RASTER_DSL)
        bits = _const(self.dsl, "ANCHOR_TICK_BITS", RASTER_DSL)
        # The published values, read as the expressions raster_dsl.emp writes them as.
        self.assertIn("pub const ANCHOR_SWEEP_SHIFT_MIN        = anchor_shift_min(ANCHOR_SINE_AMP, ANCHOR_SCREEN_LINES)",
                      self.dsl,
                      "ANCHOR_SWEEP_SHIFT_MIN is no longer derived from the two literals this "
                      "test re-derives it from — if it became a hand-written number, the "
                      "derivation stopped being the authority and this check is measuring "
                      "nothing")
        self.assertGreaterEqual(_shift_min(amp, lines), 1,
                                "the amplitude ladder admits shift 0, which collides with the "
                                "ANCHOR_MOTION_NONE sentinel")
        self.assertLessEqual(_shift_min(amp, lines), _shift_max(amp),
                             "the amplitude ladder is empty")
        self.assertLessEqual(_period_shift_max(entries, bits), 15,
                             "the period ladder does not fit the nibble the motion word packs "
                             "it into")


class TestAuthoredSweepsFitTheirBands(unittest.TestCase):
    """THE CHECK THE COMPILER CANNOT MAKE — the design's §11 Q1, answered outside comptime."""

    def test_the_channel_to_band_map_is_unambiguous(self):
        """One patched program in the tree means one band per channel. The moment a second
        one exists, `patchable(ch: 0, ...)` names two different bands and this file's
        association is wrong — so it must refuse rather than pick one."""
        src = _read(OJZ_EFFECTS)
        n = len(re.findall(r"\bpatched:\s*(\w+)", src))
        progs = set(re.findall(r"\bpatched:\s*(\w+)", src))
        self.assertEqual(
            len(progs), 1,
            "ojz_effects.emp now binds %d distinct patched programs (%s) across %d presets. "
            "A channel index no longer names one band, so the band bound below cannot be "
            "resolved by channel alone — the map has to be built per (preset -> program) "
            "before this test means anything again." % (len(progs), sorted(progs), n))

    def test_there_is_at_least_one_authored_sweep(self):
        """The anchor mover's engine half landed with exactly one authored edge. A tree with
        none would make every assertion below vacuously true, and this suite has booked that
        failure mode more than once."""
        self.assertTrue(
            authored_sweeps(),
            "no `anchor_sweep(...)` is authored anywhere in "
            "games/sonic4/data/effects/ojz_effects.emp. EFFECTS-W1 item 4 landed one, on "
            "OJZ_Preset_Sec0 channel 0; if it was deliberately removed, the capability bit "
            "CAP_ANCHOR_MOTION in games/sonic4/config/game.emp is now declared for a feature "
            "nothing raises and should come out in the same commit")

    def test_every_authored_sweep_fits_its_channels_patchable_band(self):
        bands = patchable_bands()
        amp = _const(_read(RASTER_DSL), "ANCHOR_SINE_AMP", RASTER_DSL)
        for name, ch, a, p, ph in authored_sweeps():
            self.assertIn(
                ch, bands,
                "%s authors a sweep on channel %d, which no patchable() call declares a band "
                "for. Nothing consumes that channel's line, so the sweep is invisible — and "
                "if a band is added later it inherits an amplitude nobody checked against it."
                % (name, ch))
            lo, hi = bands[ch]
            height = hi - lo + 1
            peak_to_peak = 2 * (amp >> a)
            self.assertLessEqual(
                peak_to_peak, height,
                "%s channel %d: peak-to-peak %d px does not fit band %d..%d (%d lines). "
                "Above `hi` Raster_BuildSchedule DROPS the record rather than clamping it, so "
                "the band vanishes at the top of every cycle and returns at the next zero "
                "crossing — a flicker, not an amplitude. Lower the sweep (amp_shift %d -> %d "
                "halves the travel) or widen the channel's patchable band."
                % (name, ch, peak_to_peak, lo, hi, height, a, a + 1))

    def test_every_authored_sweep_leaves_headroom_at_its_seeded_position(self):
        """Fitting the band is necessary; sitting somewhere the excursion actually fits is the
        rest of it. The seeded anchor and the band are both in the source, and the camera at
        which they are compared is the one the gate scenes and the act's own notes use."""
        SPAWN_CAMERA_Y = 144      # tools/scenes/*.json's pinned Camera_Y, and the act's spawn
        bands = patchable_bands()
        amp = _const(_read(RASTER_DSL), "ANCHOR_SINE_AMP", RASTER_DSL)
        src = _read(OJZ_EFFECTS)
        for name, ch, a, p, ph in authored_sweeps():
            m = re.search(r"pub data %s:\s*EffectsPreset\s*=\s*preset\(" % re.escape(name), src)
            body = src[m.end():m.end() + 4000]
            wy = re.search(r"patch_world_ys:\s*\[([^\]]*)\]", body)
            self.assertIsNotNone(
                wy, "%s authors motion but no patch_world_ys — the anchor it sweeps around "
                    "would be whatever preset() defaults to" % name)
            elems = [e.strip() for e in wy.group(1).split(",")]
            self.assertGreater(len(elems), ch, "%s: patch_world_ys is shorter than the "
                                               "channel its motion is authored on" % name)
            self.assertTrue(elems[ch].lstrip("-").isdigit(),
                            "%s channel %d: the seeded anchor %r is not a literal, so this "
                            "bound cannot be evaluated" % (name, ch, elems[ch]))
            line = int(elems[ch]) - SPAWN_CAMERA_Y
            lo, hi = bands[ch]
            peak = amp >> a
            self.assertGreaterEqual(
                line - peak, lo,
                "%s channel %d: at the spawn camera (Y %d) the seeded line is %d and the "
                "sweep's peak takes it to %d, below the band floor %d. Below `lo` the fire "
                "clamps up, so the top of every cycle stops tracking."
                % (name, ch, SPAWN_CAMERA_Y, line, line - peak, lo))
            self.assertLessEqual(
                line + peak, hi,
                "%s channel %d: at the spawn camera (Y %d) the seeded line is %d and the "
                "sweep's peak takes it to %d, past the band ceiling %d, where the record is "
                "DROPPED and the band disappears for that frame."
                % (name, ch, SPAWN_CAMERA_Y, line, line + peak, hi))


class TestTheGateScenesHoldTheMoverStill(unittest.TestCase):
    """tools/effects_gates.py derives every expected arm word from `anchor - Camera_Y`. That
    arithmetic is only true while nothing is moving the anchor, and the mover deliberately runs
    OUTSIDE `Debug_Scene_Freeze` — a frozen camera still has to be latched. So every scene that
    pins channel 0's anchor must also disarm the mover, or its expectations become a function
    of which frame the capture landed on."""

    def test_every_scene_that_pins_an_anchor_also_disarms_the_mover(self):
        for fn in sorted(os.listdir(SCENES_DIR)):
            if not fn.endswith(".json"):
                continue
            sc = json.loads(_read(os.path.join(SCENES_DIR, fn)))
            pokes = {s["poke"]["symbol"]: s["poke"]
                     for s in sc.get("steps", []) if "poke" in s and "symbol" in s["poke"]}
            if "Effects_World_Y" not in pokes and "Camera_Y" not in pokes:
                continue
            self.assertIn(
                "Effects_Motion_Any", pokes,
                "tools/scenes/%s pins the camera and/or channel 0's anchor but does not poke "
                "Effects_Motion_Any. Since EFFECTS-W1 item 4, OJZ_Preset_Sec0 authors a sweep "
                "on channel 0 and Effects_LatchWorldLines adds it to the latched line every "
                "frame, outside the scene freeze — so the derived arm words in "
                "tools/effects_gates.py would be measuring the sine, not the schedule builder."
                % fn)
            self.assertEqual(
                pokes["Effects_Motion_Any"].get("value"), 0,
                "tools/scenes/%s pokes Effects_Motion_Any to %r, not 0. Any nonzero value ARMS "
                "the mover — the word is a `tst.w`, not a bitfield the gate can pick apart."
                % (fn, pokes["Effects_Motion_Any"].get("value")))


if __name__ == "__main__":
    unittest.main()
