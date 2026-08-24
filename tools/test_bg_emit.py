"""Tests for BG layout + shared BG tile region emission (§2 A.5 T1)."""

import copy
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import inject_editor_bg

from ojz_strip_gen import (
    BLOCK_MAP_PATH,
    CHUNK_MAP_PATH,
    LAYOUT_DIR,
    OJZ_ART_PATH,
    BG_TILE_BASE_SLOT,
    PLANE_B_W,
    PLANE_B_H,
    build_bg_nametable_words,
    decompress_full_ojz_art,
    emit_bg_tile_blob,
    emit_zone_bg_layout,
    load_block_map,
    load_chunk_map,
    load_bg_layout,
)


class TestBgPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chunks = load_chunk_map(CHUNK_MAP_PATH)
        cls.blocks = load_block_map(BLOCK_MAP_PATH)
        cls.bg_layout = load_bg_layout(os.path.join(LAYOUT_DIR, "OJZ_1.bin"))
        cls.full_blob = decompress_full_ojz_art(OJZ_ART_PATH)

    def test_bg_layout_loaded(self):
        """OJZ_1.bin BG section is non-empty."""
        self.assertGreater(len(self.bg_layout), 0)
        self.assertGreater(len(self.bg_layout[0]), 0)

    def test_bg_nametable_size(self):
        """build_bg_nametable_words returns exactly 64×32 = 2048 words."""
        nt = build_bg_nametable_words(self.bg_layout, self.chunks, self.blocks)
        self.assertEqual(len(nt), PLANE_B_W * PLANE_B_H)

    def test_bg_tile_count_fits_capacity(self):
        """Deduped BG tile count must fit shared region capacity (512 slots)."""
        nt = build_bg_nametable_words(self.bg_layout, self.chunks, self.blocks)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "bg_tiles.bin")
            _, count = emit_bg_tile_blob(nt, self.full_blob, out_path)
            self.assertLessEqual(count, 512,
                                 f"BG tile count {count} exceeds shared region capacity 512")

    def test_bg_tile_blob_has_size_header(self):
        """First word of bg_tiles.bin is uncompressed body length (big-endian)."""
        nt = build_bg_nametable_words(self.bg_layout, self.chunks, self.blocks)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "bg_tiles.bin")
            _, count = emit_bg_tile_blob(nt, self.full_blob, out_path)
            with open(out_path, "rb") as f:
                data = f.read()
            header = struct.unpack(">H", data[:2])[0]
            body = data[2:]
            self.assertEqual(header, len(body))
            self.assertEqual(len(body), count * 32)

    def test_zone_bg_indices_in_shared_region(self):
        """Every emitted nametable word's tile_index ∈ [BG_TILE_BASE_SLOT, +cap)."""
        nt = build_bg_nametable_words(self.bg_layout, self.chunks, self.blocks)
        with tempfile.TemporaryDirectory() as tmpdir:
            tiles_path = os.path.join(tmpdir, "bg_tiles.bin")
            zone_path = os.path.join(tmpdir, "zone_bg.bin")
            src_to_canon, count = emit_bg_tile_blob(nt, self.full_blob, tiles_path)
            emit_zone_bg_layout(nt, src_to_canon, zone_path)
            with open(zone_path, "rb") as f:
                data = f.read()
            self.assertEqual(len(data), 64 * 32 * 2)
            for i in range(0, len(data), 2):
                word = struct.unpack(">H", data[i:i + 2])[0]
                tile_idx = word & 0x07FF
                self.assertGreaterEqual(
                    tile_idx, BG_TILE_BASE_SLOT,
                    f"BG word {i//2} tile_idx {tile_idx} below BG region base {BG_TILE_BASE_SLOT}")
                self.assertLess(
                    tile_idx, BG_TILE_BASE_SLOT + count,
                    f"BG word {i//2} tile_idx {tile_idx} above BG region top")

    def test_zone_bg_priority_bit_clear(self):
        """BG must stay low-priority — priority bit cleared on every word."""
        nt = build_bg_nametable_words(self.bg_layout, self.chunks, self.blocks)
        with tempfile.TemporaryDirectory() as tmpdir:
            tiles_path = os.path.join(tmpdir, "bg_tiles.bin")
            zone_path = os.path.join(tmpdir, "zone_bg.bin")
            src_to_canon, _ = emit_bg_tile_blob(nt, self.full_blob, tiles_path)
            emit_zone_bg_layout(nt, src_to_canon, zone_path)
            with open(zone_path, "rb") as f:
                data = f.read()
            for i in range(0, len(data), 2):
                word = struct.unpack(">H", data[i:i + 2])[0]
                self.assertEqual(word & 0x8000, 0,
                                 f"BG word {i//2} = 0x{word:04X} has priority bit set")


class TestBgAnimBandCeiling(unittest.TestCase):
    """BGANIM_MAX_BANDS is held by THREE independent authorities with no build-time
    guard until now — the gap the raster-substrate lens sweep booked (Tier 4 / B2,
    docs/superpowers/2026-08-18-raster-substrate-sweep-adjudication.md).

    The precedent is RASTER_MAX_PATCH, whose mirror in engine/ram.emp is a bare
    literal held to the real constant by a span `ensure` in raster.emp. That exact
    shape does NOT transfer here, and the difference is worth stating so nobody
    "upgrades" this gate into a vacuous one:

      * engine/ram.emp NAMES BGANIM_MAX_BANDS for BgAnim_LastStep's length rather
        than spelling a literal, so the array provably tracks constants.emp. An
        extern() span `ensure` would therefore compare constants.emp's value against
        an array sized BY constants.emp — it would measure itself and pass forever.
      * The two values that CAN drift are unreachable from any single .emp scope:
        bg_anim.emp's copy is module-local (not `pub`) and that file may not import
        engine.constants at all (it is lowered standalone by `bg_anim_port` against
        an empty symbol table), and the emitter's copy is Python.
      * The emitter's cap cannot be an .emp `ensure` even in principle: BgAnim_Table
        is a runtime-read binary blob assembled after engine code, so no comptime
        guard can see the band count it carries.

    So the guard lives where all three authorities are actually visible. What it
    preserves is the precedent's real property — compare independent restatements of
    one number and fail on disagreement — not its syntax.

    FAILURE MODE THIS CLOSES: raising the ceiling in the emitter alone let
    BgAnim_Update walk past BgAnim_LastStep. bg_anim.emp's `assert.w d7, ls,
    #BGANIM_MAX_BANDS` catches it in DEBUG only (asserts are zero bytes in the plain
    shape), so the release build had no defense at all.
    """

    AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _emp_const(self, rel_path, name):
        from effects_budget_check import emp_constants, eval_int_expr
        path = os.path.join(self.AEON, rel_path)
        consts = emp_constants(path)
        self.assertIn(name, consts, f"{rel_path} no longer declares {name}")
        return eval_int_expr(consts[name], consts)

    def test_all_three_authorities_agree(self):
        engine = self._emp_const("engine/system/constants.emp", "BGANIM_MAX_BANDS")
        local = self._emp_const("engine/level/bg_anim.emp", "BGANIM_MAX_BANDS")
        from inject_editor_bg import BGANIM_MAX_BANDS as emitter

        self.assertEqual(
            engine, local,
            f"engine/system/constants.emp says BGANIM_MAX_BANDS={engine} but "
            f"engine/level/bg_anim.emp's module-local mirror says {local}. The first "
            f"sizes engine/ram.emp's BgAnim_LastStep; the second bounds "
            f"BgAnim_Update's runtime assert. If the mirror is the LARGER, the assert "
            f"lets a table through that overruns the array.")
        self.assertEqual(
            engine, emitter,
            f"engine/system/constants.emp says BGANIM_MAX_BANDS={engine} but "
            f"tools/inject_editor_bg.py caps bands at {emitter}. The emitter's cap is "
            f"the RELEASE defense for BgAnim_Update's walk (the .emp assert is "
            f"DEBUG-only), so an emitter ceiling above the array's real width writes a "
            f"table that walks off BgAnim_LastStep with nothing to catch it.")

    def test_ram_array_still_names_the_constant(self):
        """The reasoning above depends on ram.emp NAMING BGANIM_MAX_BANDS rather than
        spelling a literal. If that ever changes, BgAnim_LastStep becomes a fourth
        independent authority this gate does not read — so fail here and make whoever
        changed it widen the gate."""
        path = os.path.join(self.AEON, "engine", "ram.emp")
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.lstrip().startswith("BgAnim_LastStep:"):
                    self.assertIn(
                        "BGANIM_MAX_BANDS", line,
                        "engine/ram.emp's BgAnim_LastStep no longer sizes itself from "
                        "BGANIM_MAX_BANDS. It is now an independent restatement of the "
                        "band ceiling, and TestBgAnimBandCeiling does not read it — "
                        "either restore the name or add the array's real width to the "
                        "comparison above (see RASTER_STATE_SIZE in "
                        "engine/effects/raster.emp for the span-guard shape that fits "
                        "a literal).")
                    return
        self.fail("engine/ram.emp declares no BgAnim_LastStep field")


class TestBgAnimBandCoherence(unittest.TestCase):
    """Bands must BE the front of the static tile blob they cover.

    Bands pack contiguously from slot 0 and DMA over the front of `tiles`, so a
    band's phase-0 art is those slots' rest state:

        phases[0] == tiles[slot_base : slot_base + cols*rows]

    Nothing asserted this before (this file had no assertion touching `anims`,
    `slot_base` or `phases` at all), which is what let a regenerate-one-key edit
    look legitimate. A violation bakes CLEANLY and ships silently corrupt art.

    The fixture is the REAL two-band data the file carried at b0e5a661, not a
    synthetic one, and every acceptance check is paired with a poison so the
    gate cannot pass by doing nothing.
    """

    HISTORICAL = "33892d82c95d61a9214cb449fa7c67f683247ad3"

    @classmethod
    def setUpClass(cls):
        cls.AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        import subprocess
        blob = subprocess.run(["git", "cat-file", "blob", cls.HISTORICAL],
                              cwd=cls.AEON, capture_output=True)
        cls.data = json.loads(blob.stdout) if blob.returncode == 0 else None

    def _historical(self):
        if self.data is None:
            self.skipTest("historical blob not present in this clone")
        return copy.deepcopy(self.data)

    def test_fixture_really_carries_two_bands(self):
        """Guards the gate itself: a fixture that lost its bands proves nothing."""
        d = self._historical()
        self.assertEqual(len(d["anims"]), 2)
        self.assertEqual([a["cols"] * a["rows"] for a in d["anims"]], [128, 64])

    def test_real_bands_are_coherent(self):
        d = self._historical()
        inject_editor_bg.validate_band_coherence(d["anims"], d["tiles"])

    def test_band_tiles_fit_inside_the_static_blob(self):
        d = self._historical()
        total = sum(a["cols"] * a["rows"] for a in d["anims"])
        self.assertLessEqual(total, len(d["tiles"]),
                             "animated slots overflow the static tile blob")

    def test_poison_desynced_phase0_is_rejected(self):
        """The exact shape of the corruption a merge-preserve would ship."""
        d = self._historical()
        d["tiles"][0] = [(v + 1) % 16 for v in d["tiles"][0]]   # regenerate art only
        with self.assertRaises(AssertionError) as cm:
            inject_editor_bg.validate_band_coherence(d["anims"], d["tiles"])
        self.assertIn("phases[0]", str(cm.exception))

    def test_poison_noncontiguous_slot_base_is_rejected(self):
        d = self._historical()
        d["anims"][1]["slot_base"] += 1
        with self.assertRaises(AssertionError):
            inject_editor_bg.validate_band_coherence(d["anims"], d["tiles"])

    def test_poison_band_overrunning_the_blob_is_rejected(self):
        d = self._historical()
        d["tiles"] = d["tiles"][:100]        # blob too small for band 0's 128 slots
        with self.assertRaises(AssertionError):
            inject_editor_bg.validate_band_coherence(d["anims"], d["tiles"])

    def test_live_override_file_is_coherent_if_it_has_bands(self):
        """Applies the invariant to the shipping file.

        NOTE: the live file currently has NO `anims` — the bands were destroyed
        at dd93a840 and BG animation is disabled in the ROM (docs/BUGS.md
        TOOL-01). This assertion is therefore latent today ON PURPOSE, and the
        assert below states that plainly rather than letting a silent zero-band
        pass read as a coherence check that ran.
        """
        with open(os.path.join(self.AEON, "games", "sonic4", "data",
                               "editor_bg_override.json")) as f:
            live = json.load(f)
        anims = live.get("anims") or ([live["anim"]] if live.get("anim") else [])
        if not anims:
            self.assertNotIn("anims", live,
                             "an empty `anims` key is neither absent nor authored")
            return
        inject_editor_bg.validate_band_coherence(anims, live["tiles"])


#: matches a generated `data`/`pub data` line whose initializer is an ARRAY literal.
#: `embed(...)` and `Data.empty` initializers are not arrays and never match.
_EMP_ARRAY_DATA = re.compile(
    r"^\s*(?:pub\s+)?data\s+\w+\s*(?::[^=]*)?=\s*\[(?P<init>.*)\]\s*(?://.*)?$")
#: `extern("Name")` — the ONLY spelling `.emp` accepts for a link-time symbol
#: reference inside an emitted data image (games/.../sec_local_maps.emp is the
#: worked precedent in the same generated directory).
_EMP_EXTERN = re.compile(r'extern\s*\(\s*"[^"]*"\s*\)')
_EMP_IDENT = re.compile(r"[A-Za-z_]\w*")


def bare_symbol_refs_in_emitted_emp(text):
    """Return every bare (non-`extern`) identifier used inside an array initializer.

    THE RULE UNDER TEST, stated so the matcher below cannot drift off it: in an
    emitted `.emp` data image, a symbol defined elsewhere at LINK time must be
    written `extern("Name")`. A bare `Name` is resolved by the compiler's name
    table, which the generated act modules are not in, and sigil rejects it with
    `unknown name \\`Name\\``.

    Scope note (deliberately narrow): this scanner is only sound over
    inject_editor_bg.py's OWN output, whose array initializers contain nothing
    but decimal literals, `$hex` literals and pointer entries. A hand-written
    `.emp` module may legally name a module-local `const` in an initializer, so
    do not lift this at other files.
    """
    offenders = []
    for lineno, line in enumerate(text.splitlines(), 1):
        m = _EMP_ARRAY_DATA.match(line)
        if not m:
            continue
        init = _EMP_EXTERN.sub(" ", m.group("init"))
        for ident in _EMP_IDENT.findall(init):
            offenders.append((lineno, ident))
    return offenders


import contextlib


@contextlib.contextmanager
def ceiling_lifted():
    """Raise the `ojz_bg_anim` size ceiling to the provable worst case, temporarily.

    NARROW AND DELIBERATE. The SPELLING gate below has to run the emitter over the
    REAL two-band historical act (49,242 B), and the size ceiling added for
    BGANIM-PLACE refuses that act before a byte is emitted — correctly, because it
    cannot be PLACED. Two different questions: "does the emitted module spell its
    link-time symbols in a form sigil accepts" and "does the section fit where it
    sits". Shrinking the fixture to dodge the ceiling would cost the spelling gate
    the property its docstring is built on (a real act, not a synthetic one that
    could agree with a wrong emitter by construction).

    This is NOT a general escape hatch: the ceiling's own reachability through
    `main()` is gated by
    `TestBgAnimSectionCeiling::test_main_refuses_before_writing_any_artifact`, which
    does not lift it.
    """
    saved = (inject_editor_bg.BGANIM_SECTION_CEILING,
             inject_editor_bg.BGANIM_PLACER_CEILING)
    worst = inject_editor_bg.BGANIM_WORST_CASE_BYTES
    inject_editor_bg.BGANIM_SECTION_CEILING = worst
    inject_editor_bg.BGANIM_PLACER_CEILING = worst
    try:
        yield
    finally:
        (inject_editor_bg.BGANIM_SECTION_CEILING,
         inject_editor_bg.BGANIM_PLACER_CEILING) = saved


class TestBgAnimEmission(unittest.TestCase):
    """Drives inject_editor_bg's ANIMATED arm and gates the symbol spelling it emits.

    WHY THIS EXISTS. The emitter's own comment at inject_editor_bg.py:152-159 booked
    this arm as "FORMAT-FAITHFUL BUT NOT BYTE-PROVEN: no act in the tree authors BG
    animation, so the six-target gate exercises only the stub — the first animated act
    proves this arm." It did, and it failed: the band pointer array was emitted as
    `[BgAnim_Banks + 0, ...]` and sigil answered with one `unknown name
    \\`BgAnim_Banks\\`` per entry (16 of them on this two-band fixture, measured
    2026-08-24 before the fix). Every pre-existing test in this file calls
    `validate_band_coherence` and stops there, so NOTHING ran the emitter itself —
    the disabled stub, which emits no pointer array at all, was the only path with
    coverage.

    WHAT IT GATES. Not "the string `extern` appears" — the RULE: no bare link-time
    symbol may appear inside an emitted array initializer. `bare_symbol_refs_in_emitted_emp`
    is that rule, and it is unit-tested against both the historical bad spelling and
    the accepted one below, so a green here cannot mean the matcher stopped looking.

    THE FIXTURE IS REAL. The two-band data the override file carried at b0e5a661
    (128 + 64 tiles, 8 phases each), read straight out of git — not a synthetic band
    that could agree with a wrong emitter by construction.

    NOT GATED HERE, on purpose: whether the emitted module LINKS. A real band grows
    the `ojz_bg_anim` section from 4 bytes to tens of KB and collides with the next
    pinned section (docs/DEFERRED_WORK.md, BGANIM-PLACE / defect 2). That is a
    frozen-table placement fix in sigil's tree, it needs a full `sigil build`, and it
    does not belong in a unit-test lane. This gate proves the SPELLING assembles as a
    name; the placement parcel proves the ROM.
    """

    HISTORICAL = "33892d82c95d61a9214cb449fa7c67f683247ad3"
    AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    @classmethod
    def setUpClass(cls):
        blob = subprocess.run(["git", "cat-file", "blob", cls.HISTORICAL],
                              cwd=cls.AEON, capture_output=True)
        cls.fixture = json.loads(blob.stdout) if blob.returncode == 0 else None
        cls.fixture_err = blob.stderr.decode("utf-8", "replace").strip()

    def _fixture(self):
        """Loud on unmeasurable: a missing fixture FAILS, it does not skip.

        The sibling coherence class skips here, and that is defensible for an
        invariant check. It is not defensible for this gate: the whole point is
        that the animated arm has never been executed, so a green produced by
        never running it is precisely the outcome this test exists to prevent.
        """
        if self.fixture is None:
            self.fail(
                f"could not read the two-band fixture blob {self.HISTORICAL} from git "
                f"(`git cat-file blob` said: {self.fixture_err or '<no stderr>'}). "
                "NOTHING WAS MEASURED — inject_editor_bg.py's animated emission arm did "
                "not run in this session. The blob is reachable from this repo's history "
                "(it is games/sonic4/data/editor_bg_override.json as of b0e5a661, before "
                "dd93a840 destroyed the bands); a shallow clone is the likely cause, and "
                "`git fetch --unshallow` is the fix. Do not convert this to a skip.")
        return copy.deepcopy(self.fixture)

    def _emit(self, data):
        """Run the real `main()` over `data` into a temp dir; return (emp_text, banks)."""
        saved = (inject_editor_bg.OUT_DIR, inject_editor_bg.OVERRIDE)
        with tempfile.TemporaryDirectory() as tmpdir:
            override = os.path.join(tmpdir, "editor_bg_override.json")
            with open(override, "w") as f:
                json.dump(data, f)
            try:
                inject_editor_bg.OUT_DIR = tmpdir
                inject_editor_bg.OVERRIDE = override
                with ceiling_lifted():          # spelling gate, not the placement one
                    inject_editor_bg.main()
            finally:
                inject_editor_bg.OUT_DIR, inject_editor_bg.OVERRIDE = saved
            with open(os.path.join(tmpdir, "bg_anim.emp"), encoding="utf-8") as f:
                emp = f.read()
            with open(os.path.join(tmpdir, "bg_anim_banks.bin"), "rb") as f:
                banks = f.read()
        return emp, banks

    def _expected_bank_offsets(self, anims):
        """Recompute the phase offsets from the FORMAT, not from the emitter's expression.

        bg_anim_banks.bin is the concatenation, in band order then phase order, of
        every phase's tiles at 32 bytes per 4bpp tile (inject_editor_bg.py's packing
        loop writes 8 rows x 4 packed bytes per tile). So band b's phase p starts at
        (bytes of every earlier band) + p * cols*rows*32.
        """
        offsets, cursor = [], 0
        for a in anims:
            n = a["cols"] * a["rows"]
            offsets.append([cursor + p * n * 32 for p in range(len(a["phases"]))])
            cursor += n * 32 * len(a["phases"])
        return offsets, cursor

    # ---- the matcher is itself under test ------------------------------------

    def test_rule_scanner_rejects_the_historical_bare_spelling(self):
        """The exact text the generator emitted before 2026-08-24."""
        bad = ('data _BgAnim_Band0_banks: [*u8; 8] = '
               '[BgAnim_Banks + 0, BgAnim_Banks + 4096]\n')
        self.assertEqual(bare_symbol_refs_in_emitted_emp(bad),
                         [(1, "BgAnim_Banks"), (1, "BgAnim_Banks")])

    def test_rule_scanner_accepts_the_extern_spelling(self):
        good = ('data _BgAnim_Band0_banks: [*u8; 8] = '
                '[extern("BgAnim_Banks") + 0, extern("BgAnim_Banks") + 4096]\n')
        self.assertEqual(bare_symbol_refs_in_emitted_emp(good), [])

    def test_rule_scanner_ignores_non_array_initializers(self):
        """`embed(...)`/`Data.empty` are not data images with symbols folded in."""
        other = ('pub data BgAnim_Banks = embed("x/y/bg_anim_banks.bin")\n'
                 'pub data BgAnim_Banks = Data.empty\n'
                 'pub data BgAnim_Table: u16 = 2\n')
        self.assertEqual(bare_symbol_refs_in_emitted_emp(other), [])

    def test_rule_scanner_sees_through_hex_and_decimal_literals(self):
        """The header row is all literals and must never be flagged."""
        hdr = "data _BgAnim_Band0_hdr: [u16; 6] = [0, 2, 255, 7, 128, $8000]\n"
        self.assertEqual(bare_symbol_refs_in_emitted_emp(hdr), [])

    # ---- the emitter ----------------------------------------------------------

    def test_the_animated_arm_actually_ran(self):
        """Guards the gate: a stub emission would pass every assertion below vacuously."""
        d = self._fixture()
        emp, banks = self._emit(d)
        self.assertIn(f"pub data BgAnim_Table: u16 = {len(d['anims'])}", emp,
                      "emitter took the disabled-stub branch — the animated arm did not run")
        for i in range(len(d["anims"])):
            self.assertIn(f"data _BgAnim_Band{i}_banks:", emp,
                          f"band {i}'s pointer array is missing from the emitted module")
        self.assertGreater(len(banks), 0, "no bank blob was written")

    def test_bank_pointers_use_the_accepted_extern_spelling(self):
        d = self._fixture()
        emp, banks = self._emit(d)
        expected, total = self._expected_bank_offsets(d["anims"])
        for i, offs in enumerate(expected):
            entries = ", ".join(f'extern("BgAnim_Banks") + {o}' for o in offs)
            self.assertIn(f"data _BgAnim_Band{i}_banks: [*u8; 8] = [{entries}]", emp,
                          f"band {i}'s pointer array is not the expected 8 "
                          f"extern-spelled entries at offsets {offs}")
        self.assertEqual(len(banks), total,
                         "bg_anim_banks.bin length disagrees with the offsets asserted "
                         "above — one of the two is describing a different blob")

    def test_no_bare_link_time_symbol_in_any_emitted_data_image(self):
        """The rule, applied to the whole emitted module.

        This is the assertion that would have caught the 2026-08-24 defect without
        anyone knowing the symbol's name in advance.
        """
        emp, _ = self._emit(self._fixture())
        offenders = bare_symbol_refs_in_emitted_emp(emp)
        self.assertEqual(
            offenders, [],
            "emitted array initializer names a link-time symbol without extern(): "
            + "; ".join(f"line {ln}: `{name}`" for ln, name in offenders)
            + ". sigil resolves bare names against the compiler's name table, which "
              "these generated act modules are not in, and answers `unknown name` per "
              "entry. Spell it extern(\"Name\") — see sec_local_maps.emp in the same "
              "generated directory.")

    def test_the_stub_arm_emits_no_pointer_array_at_all(self):
        """Byte-neutrality claim for master: with no `anims`, nothing about this
        parcel's change is reachable, so the shipping act data cannot move."""
        d = self._fixture()
        d.pop("anims")
        emp, _ = self._emit_stub(d)
        self.assertIn("pub data BgAnim_Table: u16 = 0", emp)
        self.assertNotIn("_banks:", emp)
        self.assertNotIn("extern(", emp)
        self.assertEqual(bare_symbol_refs_in_emitted_emp(emp), [])

    def _emit_stub(self, data):
        """Same as _emit but tolerates the stub branch writing no bank blob."""
        saved = (inject_editor_bg.OUT_DIR, inject_editor_bg.OVERRIDE)
        with tempfile.TemporaryDirectory() as tmpdir:
            override = os.path.join(tmpdir, "editor_bg_override.json")
            with open(override, "w") as f:
                json.dump(data, f)
            try:
                inject_editor_bg.OUT_DIR = tmpdir
                inject_editor_bg.OVERRIDE = override
                inject_editor_bg.main()
            finally:
                inject_editor_bg.OUT_DIR, inject_editor_bg.OVERRIDE = saved
            with open(os.path.join(tmpdir, "bg_anim.emp"), encoding="utf-8") as f:
                return f.read(), None


# ---------------------------------------------------------------------------
# The section-size ceiling (BGANIM-PLACE, decision d-9)
# ---------------------------------------------------------------------------

#: Everything an author needs in order to act on the refusal, as (label, predicate).
#: This is the RULE the message must satisfy — not a substring of today's wording,
#: which would let a message decay into an unactionable one while staying green.
_REFUSAL_REQUIREMENTS = (
    ("the section name", lambda m, f: "ojz_bg_anim" in m),
    ("the band count", lambda m, f: f"{f['bands']} band(s)" in m),
    ("the total slot count", lambda m, f: f"{f['slots']} slots total" in m),
    ("the section's size in bytes", lambda m, f: f"{f['size']} B" in m),
    ("the ceiling in bytes", lambda m, f: f"ceiling is {f['ceiling']} B" in m),
    ("how far over it is", lambda m, f: f"{f['size'] - f['ceiling']} B over" in m),
    ("that the limit is on the TOTAL, not per band",
     lambda m, f: "TOTAL, NOT PER BAND" in m),
    ("a remedy the author can carry out", lambda m, f: "To fit:" in m),
)


def refusal_shortfalls(message, facts):
    """Return the labels of everything an actionable refusal must carry and does not.

    THE RULE UNDER TEST: a size refusal has to tell an author what they authored, how
    big it came out, what the limit is, that the limit is on the TOTAL across bands,
    and what to change. The diagnostic this parcel replaces —
    ``sections `test_mappings` [...] and `ojz_bg_anim` [...] overlap (colliding pins)``
    — carries the section name and NOTHING else, which is why a matcher that only
    looked for "ojz_bg_anim" would accept the very failure being replaced.
    """
    return [label for label, ok in _REFUSAL_REQUIREMENTS if not ok(message, facts)]


class TestBgAnimSectionCeiling(unittest.TestCase):
    """`ojz_bg_anim` has a ceiling; exceeding it must be a sentence, not a collision.

    WHAT WAS THERE BEFORE. Nothing bounded the section's size, so the first real
    authored band (aurora's 8x4, 8,238 B) stopped the build with
    ``sections `test_mappings` [0x3B672, 0x3B6A2) and `ojz_bg_anim` [0x3B270,
    0x3D29E) overlap in the image (colliding pins)`` — which names no band, no size,
    no limit and no remedy.

    THE UNIT IS THE TOTAL, NOT THE BAND. `BgAnim_Banks` is ONE blob for every band in
    the act. Decision d-6 proposed a per-band ceiling and this project's own deleted
    content refuted it: the two bands this zone shipped (32x4 + 16x4, recoverable at
    b0e5a661) each pass a generous per-band limit while their SUM is 49,242 B. Both
    the emitter's check and the tests below are written on the total for that reason,
    and `test_bands_each_under_the_ceiling_but_over_in_total` is that refutation kept
    executable.

    THE MATCHER IS UNDER TEST. `refusal_shortfalls` states what an actionable refusal
    must carry, and it is exercised against the message the emitter really produces,
    against a stripped one, and against the collision diagnostic being replaced — so
    a green here cannot mean the matcher stopped looking. (A uniqueness grep over the
    emitter would not have shown that: two different failures can share a phrase.)
    """

    AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _band(self, cols, rows, slot_base):
        """A geometry-only band. Only cols/rows/slot_base reach the size arithmetic."""
        return {"cols": cols, "rows": rows, "slot_base": slot_base,
                "driver": "timer", "rate_shift": 3, "pattern_px": cols * 8,
                "phases": [[[0] * 64] * (cols * rows)] * 8}

    def _refuse(self, anims):
        """Run the real check; return (message, facts). Fails if it did NOT refuse."""
        with self.assertRaises(SystemExit) as cm:
            inject_editor_bg.check_bganim_section_fits(anims)
        slots = sum(a["cols"] * a["rows"] for a in anims)
        ceiling, _ = inject_editor_bg.bganim_effective_ceiling()
        return str(cm.exception), {
            "bands": len(anims), "slots": slots, "ceiling": ceiling,
            "size": inject_editor_bg.bganim_section_bytes(len(anims), slots)}

    # ---- the size formula is not a second opinion -----------------------------

    def test_size_formula_reproduces_the_emitted_artifacts(self):
        """`bganim_section_bytes` must measure what the emitter really writes.

        A ceiling checked against a formula that has drifted from the emitter gates
        nothing, so this drives the real `main()` and compares against the artifacts.
        """
        emitter = TestBgAnimEmission("test_the_animated_arm_actually_ran")
        emitter.setUpClass()
        d = emitter._fixture.__func__(emitter)
        anims = d["anims"]
        # The historical act is far over the ceiling, so shrink it to a legal one
        # while keeping the emitter's real path: one band of 1x1.
        d["anims"] = [self._band(1, 1, 0)]
        d["anims"][0]["phases"] = [d["tiles"][0:1]] * 8
        emp, banks = emitter._emit.__func__(emitter, d)
        n_bands = len(d["anims"])
        observed = (inject_editor_bg.BGANIM_COUNT_BYTES
                    + inject_editor_bg.BGANIM_RECORD_BYTES * n_bands + len(banks))
        self.assertEqual(
            inject_editor_bg.bganim_section_bytes(n_bands, 1), observed,
            "bganim_section_bytes disagrees with the bytes the emitter actually "
            "produced — the ceiling is then measuring a section that does not exist")
        self.assertIn("pub data BgAnim_Table: u16 = 1", emp,
                      "the animated arm did not run, so nothing was measured")
        self.assertEqual(anims and True, True)   # fixture really carried bands

    # ---- the refusal ----------------------------------------------------------

    def test_the_historical_two_band_act_is_refused(self):
        """The real content this zone shipped: 32x4 + 16x4 = 192 slots = 49,242 B."""
        msg, facts = self._refuse([self._band(32, 4, 0), self._band(16, 4, 128)])
        self.assertEqual(facts["slots"], 192)
        self.assertEqual(facts["size"], 49242)
        self.assertEqual(refusal_shortfalls(msg, facts), [],
                         f"the refusal is not actionable:\n{msg}")

    def test_auroras_authored_band_is_refused_with_its_own_numbers(self):
        """8x4, 8 phases = 8,238 B — the first genuinely editor-authored band.

        It is over TODAY because sigil's placement, not the cartridge, is the binding
        limit (BGANIM_PLACER_CEILING). This test asserts the REFUSAL IS ACTIONABLE,
        not that 8,238 must always be refused: when BGANIM-PLACE lifts the placer
        limit the check flips to the ROM ceiling and this becomes an acceptance —
        which is why it derives its expectation from the live ceiling rather than
        hardcoding a verdict.
        """
        band = [self._band(8, 4, 0)]
        size = inject_editor_bg.bganim_section_bytes(1, 32)
        self.assertEqual(size, 8238)
        ceiling, _ = inject_editor_bg.bganim_effective_ceiling()
        if size <= ceiling:
            self.assertEqual(inject_editor_bg.check_bganim_section_fits(band), size)
            return
        msg, facts = self._refuse(band)
        self.assertEqual(refusal_shortfalls(msg, facts), [],
                         f"the refusal is not actionable:\n{msg}")

    def test_bands_each_under_the_ceiling_but_over_in_total(self):
        """Decision d-6's error, kept executable.

        Four bands of ONE slot each. Every band is trivially under any per-band limit;
        their SUM is over, because `BgAnim_Banks` is one blob for the whole act. A
        per-band check passes this and ships a section that cannot be placed.
        """
        bands = [self._band(1, 1, i) for i in range(inject_editor_bg.BGANIM_MAX_BANDS)]
        ceiling, _ = inject_editor_bg.bganim_effective_ceiling()
        for i, b in enumerate(bands):
            self.assertLess(inject_editor_bg.bganim_section_bytes(1, 1), ceiling,
                            f"band {i} alone is already over the ceiling — this fixture "
                            f"no longer isolates the per-band/total distinction")
        msg, facts = self._refuse(bands)
        self.assertEqual(refusal_shortfalls(msg, facts), [],
                         f"the refusal is not actionable:\n{msg}")

    def test_the_boundary_is_exactly_the_ceiling(self):
        """One slot below passes, one slot above is refused — derived, not literal."""
        ceiling, _ = inject_editor_bg.bganim_effective_ceiling()
        fits = ((ceiling - inject_editor_bg.BGANIM_COUNT_BYTES
                 - inject_editor_bg.BGANIM_RECORD_BYTES)
                // inject_editor_bg.BGANIM_BYTES_PER_SLOT)
        self.assertGreaterEqual(fits, 1, "the ceiling does not admit even a 1-slot band")
        ok = inject_editor_bg.check_bganim_section_fits([self._band(fits, 1, 0)])
        self.assertLessEqual(ok, ceiling)
        self._refuse([self._band(fits + 1, 1, 0)])

    def test_main_refuses_before_writing_any_artifact(self):
        """The check must be REACHABLE through the real entry point, and must fire
        before emission — an over-ceiling act that writes artifacts first is how an
        author ends up debugging a section collision instead of reading a sentence.

        This is the one place the ceiling is NOT lifted (see `ceiling_lifted`).
        """
        emitter = TestBgAnimEmission("test_the_animated_arm_actually_ran")
        emitter.setUpClass()
        d = emitter._fixture.__func__(emitter)
        saved = (inject_editor_bg.OUT_DIR, inject_editor_bg.OVERRIDE)
        with tempfile.TemporaryDirectory() as tmpdir:
            override = os.path.join(tmpdir, "editor_bg_override.json")
            with open(override, "w") as f:
                json.dump(d, f)
            try:
                inject_editor_bg.OUT_DIR = tmpdir
                inject_editor_bg.OVERRIDE = override
                with self.assertRaises(SystemExit) as cm:
                    inject_editor_bg.main()
            finally:
                inject_editor_bg.OUT_DIR, inject_editor_bg.OVERRIDE = saved
            facts = {"bands": 2, "slots": 192,
                     "ceiling": inject_editor_bg.bganim_effective_ceiling()[0],
                     "size": 49242}
            self.assertEqual(refusal_shortfalls(str(cm.exception), facts), [],
                             f"main()'s refusal is not actionable:\n{cm.exception}")
            for name in ("bg_anim.emp", "bg_anim_banks.bin"):
                self.assertFalse(
                    os.path.exists(os.path.join(tmpdir, name)),
                    f"{name} was written before the ceiling refused — a later stage "
                    f"would consume it and the author would meet a section collision")

    def test_the_disabled_stub_is_always_admitted(self):
        """Master's shipping content. If the ceiling ever refuses this, every build
        of every act stops, animated or not."""
        self.assertEqual(inject_editor_bg.check_bganim_section_fits([]),
                         inject_editor_bg.bganim_section_bytes(0, 0))
        self.assertEqual(inject_editor_bg.bganim_section_bytes(0, 0), 2)

    # ---- the matcher is under test --------------------------------------------

    def test_matcher_rejects_the_collision_diagnostic_being_replaced(self):
        """The old failure names the section and nothing else. A matcher that
        accepted it would accept exactly the experience this parcel removes."""
        old = ("sections `test_mappings` [0x3B672, 0x3B6A2) and `ojz_bg_anim` "
               "[0x3B270, 0x3D29E) overlap in the image (colliding pins)")
        facts = {"bands": 1, "slots": 32, "ceiling": 1026, "size": 8238}
        missing = refusal_shortfalls(old, facts)
        self.assertEqual(len(missing), len(_REFUSAL_REQUIREMENTS) - 1,
                         f"the matcher accepted parts of the collision diagnostic it "
                         f"should not have; it only carries the section name. "
                         f"Reported missing: {missing}")

    def test_matcher_rejects_a_refusal_with_the_numbers_stripped(self):
        """A message that says only "too big" is not actionable."""
        facts = {"bands": 2, "slots": 192, "ceiling": 1026, "size": 49242}
        missing = refusal_shortfalls("ojz_bg_anim is too big", facts)
        self.assertNotEqual(missing, [], "the matcher passed a numberless refusal")

    def test_matcher_accepts_a_message_carrying_every_requirement(self):
        """Guards the other direction: a matcher that can never pass gates nothing."""
        facts = {"bands": 2, "slots": 192, "ceiling": 1026, "size": 49242}
        full = ("ojz_bg_anim: 2 band(s), 192 slots total -> 49242 B; "
                "the ceiling is 1026 B, so this is 48216 B over. "
                "THE LIMIT IS ON THE TOTAL, NOT PER BAND. To fit: shrink the bands.")
        self.assertEqual(refusal_shortfalls(full, facts), [])

    # ---- the ceilings themselves ------------------------------------------------

    def test_ceilings_sit_inside_the_provable_bounds(self):
        """Both ceilings must admit the stub and must not exceed the worst case a
        legal authoring can produce (bands pack as a prefix of `tiles`, so total
        slots <= BG_TILE_CAPACITY — validate_band_coherence is the authority)."""
        stub = inject_editor_bg.bganim_section_bytes(0, 0)
        worst = inject_editor_bg.BGANIM_WORST_CASE_BYTES
        self.assertEqual(
            worst,
            inject_editor_bg.bganim_section_bytes(inject_editor_bg.BGANIM_MAX_BANDS,
                                                  inject_editor_bg.BG_TILE_CAPACITY),
            "BGANIM_WORST_CASE_BYTES is not the section size at the provable bound")
        for name in ("BGANIM_SECTION_CEILING", "BGANIM_PLACER_CEILING"):
            v = getattr(inject_editor_bg, name)
            self.assertGreaterEqual(v, stub, f"{name} refuses even the disabled stub")
            self.assertLessEqual(v, worst, f"{name} exceeds the largest section any "
                                           f"legal authoring can produce ({worst} B)")

    def test_effective_ceiling_is_the_tighter_of_the_two(self):
        ceiling, which = inject_editor_bg.bganim_effective_ceiling()
        self.assertEqual(ceiling, min(inject_editor_bg.BGANIM_SECTION_CEILING,
                                      inject_editor_bg.BGANIM_PLACER_CEILING))
        self.assertIn(which, ("rom", "placer"))

    # ---- the ceilings against the live instruments ------------------------------

    def _listings(self):
        """The sonic4 listings present in this tree. LOUD if none are."""
        found = [p for p in ("s4.lst", "s4.debug.lst")
                 if os.path.exists(os.path.join(self.AEON, p))]
        if not found:
            self.fail(
                "neither s4.lst nor s4.debug.lst is present, so NOTHING WAS MEASURED: "
                "both ceilings are derived from label LMAs in the sigil listing and "
                "there is no substitute (the frozen boundary table lists a subset of "
                "labels, so a gap in it is an allotment, not free space). Build the "
                "sonic4 shapes first. Do not convert this to a skip — a ceiling that "
                "silently stops being checked is how this section outgrew its pin.")
        return found

    def test_rom_ceiling_fits_the_room_every_present_shape_derives(self):
        import bganim_room
        live = inject_editor_bg.live_section_bytes(self.AEON)
        for lst in self._listings():
            r = bganim_room.rom_room(os.path.join(self.AEON, lst), self.AEON)
            self.assertLessEqual(
                inject_editor_bg.BGANIM_SECTION_CEILING, r["room"] + live,
                f"{lst}: BGANIM_SECTION_CEILING does not fit — only "
                f"{r['room'] + live} B are reachable before the 0x{r['anchor']:X} "
                f"dac_banks anchor. See tools/bganim_room.py and decision d-9.")

    def test_placer_ceiling_is_the_minimum_across_the_present_shapes(self):
        """The recorded value must be the TIGHTEST shape's, not any one shape's.

        A per-shape gate cannot see this (tools/bganim_room.py checks only the
        safety-relevant direction), which is why it is asserted here across all of
        them at once.
        """
        import bganim_room
        rooms = {}
        for lst in self._listings():
            try:
                rooms[lst] = bganim_room.placer_room(os.path.join(self.AEON, lst))["room"]
            except bganim_room.Unmeasurable as e:
                self.fail(f"{lst}: placer room UNMEASURABLE — {e}")
        self.assertEqual(
            inject_editor_bg.BGANIM_PLACER_CEILING, min(rooms.values()),
            f"BGANIM_PLACER_CEILING = {inject_editor_bg.BGANIM_PLACER_CEILING} but the "
            f"shapes derive {rooms}. It must be the MINIMUM: above it, the emitter "
            f"accepts a band the tightest shape cannot place and the author meets "
            f"`colliding pins` instead of a sentence.")


if __name__ == "__main__":
    unittest.main()
