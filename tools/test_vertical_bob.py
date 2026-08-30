#!/usr/bin/env python3
"""test_vertical_bob — the source-side gate for the scene-level vertical bob (EFFECTS-W1
item 7).

RUNNER: `python3 -m pytest tools -q` — build.sh's tool-suite lane, which runs it
build-fatally on every canonical build (see build.sh, "Running the tool-suite unit
tests..."). It is not in `FAST=1`; nothing here writes a ROM byte.

WHAT THIS GATE IS FOR, given that the expect-fail lane
(tools/emp_expect_fail.py, rows "BOB bob_shift" / "BOB bob_period") already proves the two
authoring guards refuse an out-of-range scene. That lane can only ask questions a build
can answer. Three things it structurally cannot see, and each one is a way to ship a
background that sways wrongly with a perfectly green build:

  1. THE LADDERS ARE ONLY AS TRUE AS THE TABLE. `SINE_AMPLITUDE = $100` is a typed
     constant. If engine/data/sine.bin were ever replaced with a table of a different
     amplitude, every `ensure` in parallax.emp would keep passing — they all compare that
     constant against itself, one indirection removed — while the real peak excursion of
     every authored bob changed. So this file re-derives the amplitude and the cycle
     length FROM THE BLOB and holds the constants to it.

  2. THE EMITTED INSTRUCTIONS ARE NOT THE COMMENT. The nibble pack lives in two places
     that have to agree: `scene_bob_packed()` writes `(shift << 4) | period`, and Step 5
     reads the high nibble with `lsr.w #4` and the low one with `and.w #$0F`. Swap either
     side and you get a legal-looking byte, a green build, and a background that sways at
     the wrong amplitude and rate. The poison's own `ensure` pins the WRITE side; this
     file pins the READ side, against the source, in order.

  3. "IT MOVES NO BYTES" IS A CLAIM ABOUT A STRUCT. The whole reason `pcfg_bob` was
     claimed from `pcfg_pad_29` rather than appended is that sizeof(parallax_config) stays
     30 and no band array shifts. Nothing in the engine asserts that; the day someone
     appends a second bob byte, twenty records and their band arrays move and the only
     symptom is a repin nobody expected.

EVERY EXPECTATION HERE IS DERIVED. No test below compares against a number typed into
this file except the two structural facts the design rests on (the record is 30 bytes and
even), and those are stated as the claim they are. A source file this cannot read is a
LOUD failure, never a skip — a gate that quietly measures nothing is the failure mode this
tree keeps rediscovering.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARALLAX = os.path.join(ROOT, "engine", "level", "parallax.emp")
CONSTANTS = os.path.join(ROOT, "engine", "system", "constants.emp")
STRUCTS = os.path.join(ROOT, "engine", "structs.emp")
SCENE_DSL = os.path.join(ROOT, "engine", "level", "scene_dsl.emp")
SINE_BIN = os.path.join(ROOT, "engine", "data", "sine.bin")


def read(path):
    """The file's text, or a LOUD failure naming it.

    Not a skip. Every question this module asks is about one of five files; if one has
    moved, the honest report is that the gate cannot run, not a green tick.
    """
    if not os.path.exists(path):
        raise AssertionError(
            f"test_vertical_bob cannot read {path} — the vertical bob's gate has no "
            "subject. This is a hard failure and not a skip: a source file that moved "
            "takes this gate's whole measurement with it, and a skip here would report "
            "green about a feature nobody checked.")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def emp_const(text, name, where):
    """`const NAME = <int>` out of an .emp source, LOUD when absent."""
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|\d+)\s*$",
                  text, re.M)
    if not m:
        raise AssertionError(
            f"test_vertical_bob cannot find `const {name}` in {where}. Every bound this "
            "gate checks is derived from that constant, so a missing one makes the "
            "derivation vacuous rather than wrong — hence the failure.")
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


def sine_words(blob):
    """The table as signed 16-bit big-endian words."""
    out = []
    for i in range(0, len(blob), 2):
        w = (blob[i] << 8) | blob[i + 1]
        out.append(w - 0x10000 if w & 0x8000 else w)
    return out


# ---------------------------------------------------------------------------
# The engine's own derivation, re-implemented. Kept as three module-level fns so a
# reader can put them beside engine/level/parallax.emp's `bob_shift_min` /
# `bob_shift_max` / `bob_period_shift_max` and check them line for line.
# ---------------------------------------------------------------------------
def bob_shift_min(amp, origins):
    s = 0
    for i in range(16):
        if (amp >> i) * 2 > origins:
            s = i + 1
    return s


def bob_shift_max(amp):
    s = 0
    for i in range(16):
        if (amp >> i) >= 1:
            s = i
    return s


def bob_period_shift_max(entries, width):
    p = 0
    for i in range(32):
        if (entries << i) <= (1 << width):
            p = i
    return p


class SineTableIsTheAuthority(unittest.TestCase):
    """The amplitude ladder is derived from a constant; the constant must match the blob."""

    def setUp(self):
        self.consts = read(CONSTANTS)
        if not os.path.exists(SINE_BIN):
            raise AssertionError(
                f"test_vertical_bob cannot read {SINE_BIN} — SINE_AMPLITUDE and "
                "SINE_CYCLE_ENTRIES are declared in engine/system/constants.emp as facts "
                "ABOUT this blob, and with the blob absent nothing holds them to anything. "
                "Loud, not skipped.")
        with open(SINE_BIN, "rb") as fh:
            self.words = sine_words(fh.read())

    def test_SINE_AMPLITUDE_is_the_blob_s_actual_peak(self):
        declared = emp_const(self.consts, "SINE_AMPLITUDE", "engine/system/constants.emp")
        measured = max(abs(w) for w in self.words)
        self.assertEqual(
            measured, declared,
            f"engine/data/sine.bin's peak magnitude is {measured}, but "
            f"engine/system/constants.emp declares SINE_AMPLITUDE = {declared}. The "
            "vertical bob's amplitude ladder (BOB_SHIFT_MIN/BOB_SHIFT_MAX) is derived "
            "from the DECLARED value, and every `ensure` in parallax.emp compares that "
            "value against itself — so this is the only place the ladder is held to the "
            "table it actually shifts. A scene's authored bob_shift now means a different "
            "number of pixels than it did.")

    def test_SINE_CYCLE_ENTRIES_is_one_full_cycle_of_the_blob(self):
        declared = emp_const(self.consts, "SINE_CYCLE_ENTRIES",
                             "engine/system/constants.emp")
        # One full cycle is the sine's period: the point past 0 at which the table
        # repeats. Derived by searching for it rather than assumed, so a re-sampled table
        # is caught. The blob is one cycle plus a quarter-cycle cosine overlap, so a
        # period must exist strictly inside it.
        n = len(self.words)
        # At least 32 samples of evidence per candidate, so a p near the end of the blob
        # cannot "repeat" on one lucky comparison. The real answer is 256 and the blob is
        # 320 words, so the true period is checked against 64 samples.
        periods = [p for p in range(1, n) if n - p >= 32
                   and all(self.words[i] == self.words[i + p] for i in range(n - p))]
        self.assertTrue(
            periods,
            "engine/data/sine.bin has no repeating period inside it at all — it is no "
            "longer one full cycle plus an overlap, and SINE_CYCLE_ENTRIES describes "
            "nothing. Step 5's bob masks its phase index with this count to stay inside "
            "one cycle.")
        self.assertEqual(
            min(periods), declared,
            f"engine/data/sine.bin repeats every {min(periods)} entries, but "
            f"engine/system/constants.emp declares SINE_CYCLE_ENTRIES = {declared}. Step "
            "5's bob masks its phase index with SINE_CYCLE_ENTRIES-1, so a smaller real "
            "period makes the sway repeat mid-mask and a larger one walks the index into "
            "the quarter-cycle cosine overlap GetSineCosine reads.")


class TheLaddersAreDerivedNotTyped(unittest.TestCase):
    """parallax.emp's three literals must reproduce the derivation from its own inputs."""

    def setUp(self):
        self.plx = read(PARALLAX)
        self.amp = emp_const(self.plx, "BOB_SINE_AMP", "engine/level/parallax.emp")
        self.entries = emp_const(self.plx, "BOB_SINE_ENTRIES", "engine/level/parallax.emp")
        self.origins = emp_const(self.plx, "BOB_VSCROLL_ORIGINS",
                                 "engine/level/parallax.emp")
        self.bits = emp_const(self.plx, "BOB_TICK_BITS", "engine/level/parallax.emp")
        self.none = emp_const(self.plx, "BOB_SHIFT_NONE", "engine/level/parallax.emp")

    def test_the_inlined_sine_facts_match_engine_constants(self):
        """parallax.emp inlines them because a pub const must fold from its own file's
        names; the `ensure` pins are the engine-side check and this is the second."""
        consts = read(CONSTANTS)
        self.assertEqual(
            self.amp, emp_const(consts, "SINE_AMPLITUDE", "engine/system/constants.emp"),
            "engine/level/parallax.emp's inlined BOB_SINE_AMP has drifted from "
            "engine.constants.SINE_AMPLITUDE. The inline exists because a `pub const` "
            "calling a module-private comptime fn must fold from its own file's literal "
            "names or its importers get the raw expression — it is not licence to drift.")
        self.assertEqual(
            self.entries,
            emp_const(consts, "SINE_CYCLE_ENTRIES", "engine/system/constants.emp"),
            "engine/level/parallax.emp's inlined BOB_SINE_ENTRIES has drifted from "
            "engine.constants.SINE_CYCLE_ENTRIES.")

    def test_the_amplitude_ladder_is_non_empty_and_excludes_shift_zero(self):
        lo, hi = bob_shift_min(self.amp, self.origins), bob_shift_max(self.amp)
        self.assertLessEqual(
            lo, hi,
            f"the vertical bob's amplitude ladder is empty ({lo} .. {hi}) — no shift both "
            "fits the seam-free V-scroll span and survives the sine table, so the field "
            "is unauthorable and scene()'s guard admits nothing.")
        self.assertGreaterEqual(
            lo, 1,
            f"the amplitude ladder now admits shift {lo}. Shift 0 must stay ILLEGAL: "
            "`(0 << 4) | 0` is the byte 0, which pcfg_bob reads as NO BOB, so the largest "
            "sway the encoding can spell would be silence.")

    def test_the_sentinel_sits_outside_the_amplitude_ladder(self):
        hi = bob_shift_max(self.amp)
        self.assertGreater(
            self.none, hi,
            f"the no-bob sentinel ({self.none}) is inside the legal amplitude ladder "
            f"(up to {hi}) — a scene authoring the narrowest legal sway would lower to "
            "the packed byte 0 and not sway at all, silently.")

    def test_both_ladders_fit_their_nibbles(self):
        hi = bob_shift_max(self.amp)
        pmax = bob_period_shift_max(self.entries, self.bits)
        self.assertLessEqual(hi, 15, "the amplitude ladder overflows pcfg_bob's high nibble")
        self.assertLessEqual(pmax, 15, "the period ladder overflows pcfg_bob's low nibble")

    def test_the_period_ceiling_closes_the_cycle_on_the_tick_counter(self):
        """Stated as the property, not the number: at the ceiling the phase index returns
        to 0 exactly when the counter wraps; one past it, it does not."""
        pmax = bob_period_shift_max(self.entries, self.bits)
        span = 1 << self.bits
        self.assertEqual(
            (span >> pmax) % self.entries, 0,
            f"at period shift {pmax} the tick counter's {span} values do not divide into "
            f"whole {self.entries}-entry cycles, so the sine jumps at every counter wrap "
            "even at the declared ceiling.")
        self.assertNotEqual(
            (span >> (pmax + 1)) % self.entries, 0,
            f"period shift {pmax + 1} ALSO closes its cycle, so {pmax} is not the ceiling "
            "and scene()'s guard is refusing a legal value.")

    def test_the_scene_dsl_guards_quote_this_ladder(self):
        """The guard messages carry the ladder as literal text; the poison's fragments
        match on it. A ladder that moved without the sentences moving is a guard that
        refuses one span while telling the author about another."""
        dsl = read(SCENE_DSL)
        lo, hi = bob_shift_min(self.amp, self.origins), bob_shift_max(self.amp)
        pmax = bob_period_shift_max(self.entries, self.bits)
        self.assertIn(
            f"bob_shift {{bob_shift}} outside {lo} .. {hi}", dsl,
            f"engine/level/scene_dsl.emp's bob_shift guard does not say `outside {lo} .. "
            f"{hi}`, which is the ladder derived from this tree's own constants. Either "
            "the ladder moved and the sentence did not, or the guard was reworded and "
            "tools/emp_expect_fail.py's 'BOB bob_shift' fragment no longer matches it.")
        self.assertIn(
            f"bob_period {{bob_period}} outside 0 .. {pmax}", dsl,
            f"engine/level/scene_dsl.emp's bob_period guard does not say `outside 0 .. "
            f"{pmax}`.")


class TheEmittedReadMatchesThePack(unittest.TestCase):
    """Step 5's instruction sequence, in order, against the source."""

    def setUp(self):
        self.plx = read(PARALLAX)
        body = re.search(r"\.v_pack:(.*?)\.v_bob_none:", self.plx, re.S)
        if not body:
            raise AssertionError(
                "test_vertical_bob cannot find the bob block between `.v_pack:` and "
                "`.v_bob_none:` in engine/level/parallax.emp. The block is the subject of "
                "every assertion in this class; a rename that this gate cannot follow is "
                "a failure, not a skip.")
        # Instructions only: strip comments and blank lines.
        self.ops = [re.sub(r"//.*$", "", ln).strip()
                    for ln in body.group(1).splitlines()]
        self.ops = [o for o in self.ops if o]

    def test_the_sentinel_test_clears_the_register_first(self):
        """`move.b` into a data register leaves bits 8-31 alone, and `lsr.w #4` below
        would shift four of those dirty bits into the amplitude nibble."""
        self.assertRegex(
            self.ops[0], r"^moveq\s+#0,\s*d3$",
            "the bob block no longer opens by clearing d3. `move.b pcfg_bob(a0), d3` "
            "writes only the low byte, so without the clear `lsr.w #4, d3` brings four "
            f"dirty bits into the amplitude shift. First instruction is: {self.ops[0]}")
        self.assertRegex(
            self.ops[1], r"^move\.b\s+parallax_config\.pcfg_bob\(a0\),\s*d3$",
            f"the bob block's second instruction is not the pcfg_bob load: {self.ops[1]}")
        self.assertRegex(
            self.ops[2], r"^beq\s+\.v_bob_none$",
            "the whole-byte-0 sentinel test is gone. A scene that authors no bob must "
            f"branch past the block, not fall into it: {self.ops[2]}")

    def test_the_low_nibble_is_the_period_and_the_high_nibble_the_amplitude(self):
        """The read side of `scene_bob_packed`'s `(shift << 4) | period`. Swapping the two
        reads produces a legal byte, a green build, and the wrong sway."""
        seq = " ; ".join(self.ops)
        self.assertRegex(
            seq, r"move\.w\s+d3,\s*d0\s*;\s*and\.w\s+#\$0F,\s*d0",
            "the period shift is no longer taken from pcfg_bob's LOW nibble with "
            f"`and.w #$0F`. scene_bob_packed writes it there: {seq}")
        self.assertRegex(
            seq, r"lsr\.w\s+#4,\s*d3",
            "the amplitude shift is no longer taken from pcfg_bob's HIGH nibble with "
            f"`lsr.w #4`: {seq}")
        # Order: the period must be extracted before d3 is shifted, or the period read
        # sees the already-shifted byte.
        self.assertLess(
            seq.index("and.w   #$0F, d0"), seq.index("lsr.w   #4, d3"),
            "the amplitude shift is extracted from d3 BEFORE the period is copied out of "
            "it, so the period read sees an already-shifted byte and the sway runs at an "
            "arbitrary rate.")

    def test_the_phase_rides_the_lag_immune_tick_and_stays_in_one_cycle(self):
        seq = " ; ".join(self.ops)
        self.assertRegex(
            seq, r"move\.w\s+Logic_Tick\+2,\s*d4",
            "the bob's time source is no longer `Logic_Tick+2` — the low word of the "
            "lag-immune tick counter, the same source engine/level/bg_anim.emp:173 uses. "
            "Every derived bound in parallax.emp assumes a 16-bit counter (BOB_TICK_BITS); "
            f"a 32-bit or VBlank-paced source invalidates the period ceiling: {seq}")
        self.assertRegex(
            seq, r"and\.w\s+#BOB_SINE_ENTRIES-1,\s*d4",
            "the phase index is no longer masked to one full sine cycle. Unmasked, it "
            f"walks into the table's quarter-cycle cosine overlap: {seq}")
        self.assertRegex(
            seq, r"add\.w\s+d4,\s*d4",
            "the phase index is no longer doubled. Sine_Table's entries are WORDS, so an "
            f"unscaled index samples every other byte of the table: {seq}")

    def test_the_sample_is_shifted_arithmetically_and_added_to_the_bg_scroll(self):
        seq = " ; ".join(self.ops)
        self.assertRegex(
            seq, r"asr\.w\s+d3,\s*d4",
            "the sine sample is no longer scaled with an ARITHMETIC shift. The wave is "
            "signed; `lsr` would turn its whole negative half into a huge positive "
            f"excursion: {seq}")
        self.assertRegex(
            seq, r"add\.w\s+d4,\s*d2",
            "the bob is no longer added to d2, the BG V-scroll. d2 is what `.v_pack` "
            f"clamps and stores, and what every downstream consumer reads: {seq}")

    def test_the_table_base_is_loaded_before_it_is_indexed(self):
        """A PC-relative INDEXED read carries an 8-bit displacement on the 68000, so a
        cross-section table cannot be reached that way at all."""
        seq = " ; ".join(self.ops)
        self.assertRegex(
            seq, r"lea\s+Sine_Table,\s*a1\s*;\s*move\.w\s+\(a1,d4\.w\),\s*d4",
            "the sine sample is no longer read through an address register. "
            "`Sine_Table(pc,d4.w)` is `(d8,PC,Xn)` — an EIGHT-bit displacement — and the "
            "math section is ~20 KB from the parallax section, so that spelling is a hard "
            f"link failure rather than a slow path: {seq}")

    def test_the_bob_precedes_the_seam_clamp(self):
        """The clamp is what keeps an authored bob inside the plane's seam-free window.
        A bob added after it is unbounded."""
        v_pack = self.plx.index(".v_pack:")
        bob_none = self.plx.index(".v_bob_none:", v_pack)
        clamp = self.plx.index("tst.w   d2", bob_none)
        store = self.plx.index("move.w  d2, Parallax_Current_Vscroll_BG", bob_none)
        self.assertLess(bob_none, clamp, "the bob block no longer precedes the clamp")
        self.assertLess(
            clamp, store,
            "the Plane-B window clamp no longer sits between the bob and the store of "
            "Parallax_Current_Vscroll_BG — an authored bob can now push the BG V-scroll "
            "across the wrap seam, which is the failure PARALLAX-SCROLL-CLAMP exists to "
            "make legible.")


class ClaimingThePadMovedNoBytes(unittest.TestCase):
    """`pcfg_bob` was claimed from `pcfg_pad_29`; the point was that nothing moves."""

    def setUp(self):
        self.structs = read(STRUCTS)
        m = re.search(r"pub struct parallax_config \{(.*?)\n\}", self.structs, re.S)
        if not m:
            raise AssertionError(
                "test_vertical_bob cannot find `pub struct parallax_config` in "
                "engine/structs.emp — the record whose size this class exists to hold.")
        self.body = m.group(1)

    def test_pcfg_bob_is_the_last_field_and_the_pad_is_gone(self):
        fields = re.findall(r"^\s{4}(\w+):\s*([^,]+),\s*//\s*\$([0-9A-Fa-f]+)",
                            self.body, re.M)
        self.assertTrue(fields, "no fields parsed out of parallax_config")
        names = [f[0] for f in fields]
        self.assertNotIn(
            "pcfg_pad_29", names,
            "pcfg_pad_29 is back alongside pcfg_bob. The bob was CLAIMED from that pad "
            "precisely so the record would not grow; two bytes here take sizeof to 31, "
            "which rounds to 32, which shifts every config's band array by two and moves "
            "twenty records in the ROM.")
        self.assertEqual(
            names[-1], "pcfg_bob",
            f"pcfg_bob is no longer the last field of parallax_config (last is "
            f"{names[-1]}). It sits at the tail because it took the even-size pad's slot; "
            "a field appended after it re-parities the record.")

    def test_the_record_is_still_thirty_bytes_and_even(self):
        widths = {"u8": 1, "u16": 2, "u32": 4, "*u8": 4}
        total = 0
        for name, ty, off in re.findall(
                r"^\s{4}(\w+):\s*([^,]+?),\s*//\s*\$([0-9A-Fa-f]+)", self.body, re.M):
            ty = ty.strip()
            self.assertIn(
                ty, widths,
                f"parallax_config field {name} has type {ty}, which this gate cannot "
                "size. Add it to `widths` — a silently skipped field would let the record "
                "grow under a green sizeof check.")
            self.assertEqual(
                total, int(off, 16),
                f"parallax_config field {name} is commented ${off} but accumulates to "
                f"${total:02X}. The offset comments are a gate (see the struct's banner) "
                "and one of the two is wrong.")
            total += widths[ty]
        self.assertEqual(
            total, 30,
            f"sizeof(parallax_config) is {total}, not 30. The vertical bob's whole "
            "byte-cost argument is that it claimed an existing pad and left the record at "
            "30: at any other size every band array moves and twenty shipped records "
            "change, which is a paired sigil repin rather than a code-only parcel.")
        self.assertEqual(
            total % 2, 0,
            f"sizeof(parallax_config) is {total}, which is ODD. This size IS the band "
            "array's base offset, so copy_band_entry's `move.l` run starts on an odd "
            "address and address-errors on a 68000.")


if __name__ == "__main__":
    unittest.main()
