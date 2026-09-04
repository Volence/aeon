"""Tests for BG layout + shared BG tile region emission (§2 A.5 T1).

WHAT THIS FILE DOES NOT DO (2026-08-26): read the tree's own `s4*.lst`. It runs in
build.sh's PRE-build pytest lane, so any listing at the repo root is a PRIOR build's —
stale, another sigil profile's, or absent on a fresh tree — and never the subject.
Three tests that did read it were deleted after failing the sigil freeze twice with
true statements about the wrong artifact. The BG-animation ceiling against a REAL
listing is enforced exactly once: build.sh's post-sigil `tools/bganim_room.py --gate`
on the listing that invocation just emitted (`--rom/--built-after` provenance,
`--fixture` freshness). Here the derivation is tested over a committed cut of a real
listing (tools/fixtures/bganim_room_excerpt.lst, see TestBgAnimRoomOverCommittedFixture).
Nothing about the ceiling is a skip: a missing listing at the gate is a hard failure.
"""

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

import bganim_room
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
    decision d-9 refuses that act before a byte is emitted — correctly, because it
    does not FIT before the `dac_banks` anchor. Two different questions: "does the emitted module spell its
    link-time symbols in a form sigil accepts" and "does the section fit where it
    sits". Shrinking the fixture to dodge the ceiling would cost the spelling gate
    the property its docstring is built on (a real act, not a synthetic one that
    could agree with a wrong emitter by construction).

    This is NOT a general escape hatch: the ceiling's own reachability through
    `main()` is gated by
    `TestBgAnimSectionCeiling::test_main_refuses_before_writing_any_artifact`, which
    does not lift it.
    """
    saved = inject_editor_bg.BGANIM_SECTION_CEILING
    inject_editor_bg.BGANIM_SECTION_CEILING = inject_editor_bg.BGANIM_WORST_CASE_BYTES
    try:
        yield
    finally:
        inject_editor_bg.BGANIM_SECTION_CEILING = saved


def emit_over_document(data):
    """Run the REAL `inject_editor_bg.main()` over `data` into a temp dir.

    Returns `(emitted bg_anim.emp text, bg_anim_banks.bin bytes)`. One authority for
    "drive the emitter", shared by the spelling gate and the motion-axis gate so a
    change to how the emitter is invoked cannot leave one of them exercising a
    different path from the other. The size ceiling is lifted for the duration —
    neither gate is asking whether the section fits (see `ceiling_lifted`).
    """
    saved = (inject_editor_bg.OUT_DIR, inject_editor_bg.OVERRIDE)
    with tempfile.TemporaryDirectory() as tmpdir:
        override = os.path.join(tmpdir, "editor_bg_override.json")
        with open(override, "w") as f:
            json.dump(data, f)
        try:
            inject_editor_bg.OUT_DIR = tmpdir
            inject_editor_bg.OVERRIDE = override
            with ceiling_lifted():
                inject_editor_bg.main()
        finally:
            inject_editor_bg.OUT_DIR, inject_editor_bg.OVERRIDE = saved
        with open(os.path.join(tmpdir, "bg_anim.emp"), encoding="utf-8") as f:
            emp = f.read()
        with open(os.path.join(tmpdir, "bg_anim_banks.bin"), "rb") as f:
            banks = f.read()
    return emp, banks


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
    pinned section (docs/DEFERRED_WORK.md, "DEFECT 2 (BGANIM-PLACE)" — the placement
    half of that booking closed with sigil b0363140; the size ceiling stayed). That is a
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
        return emit_over_document(data)

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


class TestBgAnimMotionAxis(unittest.TestCase):
    """The band record's two axis-dependent fields, on BOTH axes (DoD item 8).

    THE CLAIM THIS GATE HOLDS UP. `BgAnim_Update` never learns which way a band
    moves: it rotates the band's byte image by `(step >> 3) << col_shift` and masks
    the step with `step_mask`. Those are a UNIT and a PERIOD, not an axis, and the
    horizontal and vertical readings of them differ only in which band dimension
    supplies which. So a vertical band is emitted by the same emitter into the same
    44-byte record and consumed by the same unchanged proc — the assertions below are
    what keep that true, because a later edit that re-hardcodes the horizontal
    reading would go unnoticed by every other test in this file (all of them predate
    the axis and every fixture they use is horizontal).

    EXPECTATIONS ARE DERIVED FROM THE GEOMETRY, never copied from the emitter. Each
    test recomputes `unit_bytes`/`period_px` from `cols`/`rows` and the documented
    rule, so an emitter that swapped the two would fail rather than agree with a
    pinned number that was itself read out of the emitter.

    THE ART IS REAL where it can be. Phase 0 of every band built here is a cut of the
    historical two-band act's own tiles (`TestBgAnimEmission.HISTORICAL`); only the
    per-phase transform is synthetic, and it has to be, because no writer in either
    repo can produce vertical phases yet (aurora ROADMAP row 55's column-wise
    shift-fill is costed and not built).
    """

    AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    @classmethod
    def setUpClass(cls):
        blob = subprocess.run(
            ["git", "cat-file", "blob", TestBgAnimEmission.HISTORICAL],
            cwd=cls.AEON, capture_output=True)
        cls.fixture = json.loads(blob.stdout) if blob.returncode == 0 else None
        cls.fixture_err = blob.stderr.decode("utf-8", "replace").strip()

    # ---- fixture construction, from the FORMAT ------------------------------

    def _doc(self, band):
        """A one-band override document carrying `band`, on the historical act's art.

        `layout`/`tiles` come from the real fixture so every check `main()` makes
        before it reaches the band (tile capacity, nametable width, coherence of the
        band against the front of the static blob) is satisfied by real data.
        """
        if self.fixture is None:
            self.fail(
                "could not read the two-band fixture blob "
                f"{TestBgAnimEmission.HISTORICAL} from git "
                f"(`git cat-file blob` said: {self.fixture_err or '<no stderr>'}). "
                "NOTHING WAS MEASURED — no band reached the emitter in this session, "
                "so every assertion in this class would pass vacuously. "
                "`git fetch --unshallow` is the likely fix; do not convert this to a "
                "skip.")
        d = copy.deepcopy(self.fixture)
        d["anims"] = [band]
        return d

    @staticmethod
    def _cell(i, cols, rows, order):
        """Slot index `i` -> band cell `(c, r)` under `order`.

        The two formulas of EFFECTS_CONSUMER_CONTRACT.md §1.2 obligation 1, spelled
        out here rather than imported so the test reads the FORMAT independently of
        the code under test: column-major `base + c*rows + r` is a horizontal band's
        order, row-major `base + r*cols + c` is a vertical band's. `order` is
        'column'/'row' rather than an axis so a fixture can deliberately pack a
        vertical band in the WRONG order — which is what the control arm below does.
        """
        if order == "row":
            r, c = divmod(i, cols)
        else:
            c, r = divmod(i, rows)
        return c, r

    @classmethod
    def _order_for(cls, axis):
        """The slot order §1.2 obligation 1 assigns to `axis`."""
        return "row" if axis == "vertical" else "column"

    @classmethod
    def _grid(cls, bank, cols, rows, order):
        """A phase bank as a `rows*8` x `cols*8` pixel grid, in slot order `order`."""
        g = [[0] * (cols * 8) for _ in range(rows * 8)]
        for i, t in enumerate(bank):
            c, r = cls._cell(i, cols, rows, order)
            for y in range(8):
                for x in range(8):
                    g[r * 8 + y][c * 8 + x] = t[y * 8 + x] & 0xF
        return g

    @classmethod
    def _bank(cls, grid, cols, rows, order):
        """The inverse of `_grid`: a pixel grid back into `cols*rows` 64-px tiles."""
        bank = []
        for i in range(cols * rows):
            c, r = cls._cell(i, cols, rows, order)
            bank.append([grid[r * 8 + y][c * 8 + x]
                         for y in range(8) for x in range(8)])
        return bank

    def _band(self, cols, rows, axis, roll, pattern_px=None, order=None, **kw):
        """One band whose 8 phases are `phase0` rolled `k` px along `roll`.

        `roll` is 'h', 'v' or None (None = a composite: a per-phase brightness step,
        which is what the shipped horizontal bands actually are — see
        `validate_band_phase_axis`'s docstring).

        `order` is the SLOT order the phases are packed in, and it defaults to the one
        §1.2 obligation 1 assigns to `axis` — so a fixture is a well-formed band of
        its declared axis unless a caller deliberately says otherwise. It has to be a
        parameter rather than always `axis`'s own order because the control arm of
        `test_the_guard_reads_a_vertical_band_in_ITS_OWN_slot_order` needs the same
        picture packed the wrong way, and because before 2026-09-03 EVERY fixture
        here was packed column-major — including the vertical ones, which is what let
        the guard's flagship test pass over a band no writer would ever emit.
        """
        n = cols * rows
        order = order or self._order_for(axis)
        base = self._grid(self.fixture["tiles"][:n], cols, rows, order)
        w, h = cols * 8, rows * 8
        phases = []
        for k in range(8):
            if roll == "h":
                g = [[base[y][(x + k) % w] for x in range(w)] for y in range(h)]
            elif roll == "v":
                g = [[base[(y + k) % h][x] for x in range(w)] for y in range(h)]
            else:
                g = [[(base[y][x] + k) & 0xF for x in range(w)] for y in range(h)]
            phases.append(self._bank(g, cols, rows, order))
        band = {"cols": cols, "rows": rows, "axis": axis,
                "pattern_px": pattern_px if pattern_px is not None
                else (cols * 8 if axis == "horizontal" else rows * 8),
                "driver": "timer", "rate_shift": 3, "slot_base": 0, "phases": phases}
        band.update(kw)
        return band

    def _record(self, band):
        """Emit `band` and return its six header words, parsed out of the module."""
        emp, _ = emit_over_document(self._doc(band))
        m = re.search(r"data _BgAnim_Band0_hdr: \[u16; 6\] = \[([^\]]+)\]", emp)
        self.assertIsNotNone(
            m, "no band-0 header row in the emitted module — the emitter took the "
               "disabled-stub branch and nothing about the axis was measured")
        words = [int(v.strip().lstrip("$"), 16 if v.strip().startswith("$") else 10)
                 for v in m.group(1).split(",")]
        keys = ("driver", "rate_shift", "step_mask", "col_shift", "tile_count",
                "vram_dest")
        return dict(zip(keys, words)), emp

    # ---- the two derivations ------------------------------------------------

    def test_the_default_axis_is_horizontal(self):
        """A band with no `axis` key keeps the pre-2026-09-02 derivation exactly.

        The anti-vacuous row for every existing document and for the shipped act: the
        axis is opt-in, so `rows` still supplies the unit and `cols` still supplies
        the period when nobody says otherwise.
        """
        band = self._band(8, 4, "horizontal", "h")
        del band["axis"]
        rec, _ = self._record(band)
        self.assertEqual(rec["col_shift"], (4 * 32).bit_length() - 1)   # rows*32 = 128
        self.assertEqual(rec["step_mask"], 8 * 8 - 1)                   # cols*8  = 64
        self.assertEqual(rec["tile_count"], 32)

    def test_a_vertical_band_takes_its_unit_from_cols_and_its_period_from_rows(self):
        """The whole item, in one record: the two fields swap which dimension feeds them."""
        cols, rows = 8, 4
        rec, _ = self._record(self._band(cols, rows, "vertical", "v"))
        self.assertEqual(
            rec["col_shift"], (cols * 32).bit_length() - 1,
            "a vertical band rotates by whole ROWS of cols*32 bytes; col_shift still "
            "reads as rows*32, so the emitter is deriving the unit from the wrong "
            "dimension")
        self.assertEqual(
            rec["step_mask"], rows * 8 - 1,
            "a vertical band's pattern period is its HEIGHT (rows*8); step_mask still "
            "reads as the width")
        self.assertEqual(rec["tile_count"], cols * rows)

    def test_the_two_axes_differ_in_the_record_on_the_same_geometry(self):
        """Guards against an emitter that ignores `axis` and happens to agree.

        8x4 is deliberately non-square: horizontal gives (unit 128, period 64) and
        vertical gives (unit 256, period 32), so a record that is the same on both
        axes proves the key was not read.
        """
        h, _ = self._record(self._band(8, 4, "horizontal", "h"))
        v, _ = self._record(self._band(8, 4, "vertical", "v"))
        self.assertNotEqual((h["col_shift"], h["step_mask"]),
                            (v["col_shift"], v["step_mask"]))

    def test_the_rotate_is_legal_on_both_axes(self):
        """The one condition `BgAnim_Update` actually needs, read off the emitted record.

        The coarse rotate walks `period_px/8` units of `1 << col_shift` bytes over an
        image of `tile_count * 32` bytes. If the product overshoots, the proc's piece-1
        length (`tile_count*32 - shift_bytes`) goes <= 0 and `QueueDMA_Deferrable` is
        handed a length that sprays 128 KB. This is the assertion that says a vertical
        band is safe for the UNCHANGED proc — it is not about the emitter's arithmetic
        but about the invariant the engine's own assert.w backstops.
        """
        for axis, roll in (("horizontal", "h"), ("vertical", "v")):
            with self.subTest(axis=axis):
                rec, _ = self._record(self._band(8, 4, axis, roll))
                units = (rec["step_mask"] + 1) // 8
                self.assertEqual(units * (1 << rec["col_shift"]),
                                 rec["tile_count"] * 32,
                                 f"{axis}: the rotation ring does not cover the band "
                                 "image exactly, so piece 1 can go non-positive")

    def test_the_emitted_comment_names_the_axis_and_its_direction(self):
        """The record cannot carry the axis; the generated module's comment must.

        A reader of `data/generated/.../bg_anim.emp` sees six numbers. Which way the
        band moves is not among them and is not recoverable from them.
        """
        _, emp = self._record(self._band(8, 4, "vertical", "v"))
        self.assertIn("vertical (scrolls up)", emp)
        _, emp = self._record(self._band(8, 4, "horizontal", "h"))
        self.assertIn("horizontal (scrolls left)", emp)

    # ---- the refusals -------------------------------------------------------

    def _refusal(self, band):
        with self.assertRaises(AssertionError) as cm:
            self._record(band)
        return str(cm.exception)

    def test_an_unknown_axis_is_refused_naming_both_legal_spellings(self):
        msg = self._refusal(self._band(8, 4, "up", "v", pattern_px=32))
        self.assertIn("'horizontal'", msg)
        self.assertIn("'vertical'", msg)

    def test_the_power_of_two_key_MOVES_with_the_axis_rather_than_doubling(self):
        """cols must be a power of two on a vertical band — and rows need not be.

        Both halves matter. The first is the new constraint; the second is what says
        the emitter MOVED the constraint instead of demanding both, which would refuse
        bands that the engine runs perfectly well.
        """
        msg = self._refusal(self._band(3, 4, "vertical", "v"))
        self.assertIn("cols", msg)
        rec, _ = self._record(self._band(4, 3, "vertical", "v"))
        self.assertEqual(rec["col_shift"], (4 * 32).bit_length() - 1)
        self.assertEqual(rec["step_mask"], 3 * 8 - 1)

    def test_rows_is_still_the_power_of_two_key_on_a_horizontal_band(self):
        """The converse control: the old constraint did not simply disappear."""
        msg = self._refusal(self._band(4, 3, "horizontal", "h"))
        self.assertIn("rows", msg)

    def test_pattern_px_is_the_period_ALONG_THE_AXIS(self):
        """A vertical band declaring its WIDTH is refused, and the message says which."""
        msg = self._refusal(self._band(8, 4, "vertical", "v", pattern_px=64))
        self.assertIn("32", msg)
        self.assertIn("HEIGHT", msg)

    # ---- the horizontal-writer guard ----------------------------------------

    def test_a_vertical_band_regenerated_by_a_horizontal_writer_is_refused(self):
        """The silent failure this guard exists for, reproduced exactly.

        Aurora's shift-fill derives bank k as phase 0 scrolled k px within the pattern
        WIDTH — measured on the live act, whose eight phases are exactly
        `phase0[y][(x + k) % W]`. Run over a band the author declared vertical, that
        produces a clean bake and a band that shimmers instead of scrolling.
        """
        msg = self._refusal(self._band(8, 4, "vertical", "h", pattern_px=32))
        self.assertIn("HORIZONTAL", msg)
        self.assertIn("row 55", msg)

    # ---- the row-major false negative, and its control ----------------------
    #
    # Both rows below run the SAME picture through the guard and differ ONLY in the
    # slot order the phases are packed in. Neither means anything alone: an admit on
    # its own could just be malformed input, and a refusal on its own says nothing
    # about whether the guard reads slot order at all. Kept as a pair permanently.
    #
    # Measured against the pre-fix code (2026-09-03), where the verdicts were the
    # other way round:
    #
    #     column-major slots + x-rolled phases  ->  REFUSED   (control)
    #     row-major    slots + x-rolled phases  ->  ADMITTED  (the hole)

    def _x_rolled_vertical_band(self, order):
        """A `axis: vertical` band whose 8 phases are exact x-rolls of phase 0.

        2x2 so `cols*32 = 64` is a legal rotation unit, and the base picture is
        `(x*7 + y*13) % 15 + 1` — period 15 against a 16 px pattern, so nothing in it
        is accidentally symmetric in x, in y, or under the column/row-major relabel.
        Synthetic rather than a cut of the historical act precisely because THIS row
        needs art whose asymmetry is derivable rather than merely observed.
        """
        cols, rows = 2, 2
        w, h = cols * 8, rows * 8
        base = [[(x * 7 + y * 13) % 15 + 1 for x in range(w)] for y in range(h)]
        phases = [self._bank([[base[y][(x + k) % w] for x in range(w)]
                              for y in range(h)], cols, rows, order)
                  for k in range(8)]
        return {"cols": cols, "rows": rows, "axis": "vertical",
                "pattern_px": rows * 8, "driver": "timer", "rate_shift": 3,
                "slot_base": 0, "phases": phases}

    def _verdict(self, band):
        """'REFUSED' or 'ADMITTED' for `band`, through the emitter that calls the guard.

        Driven end-to-end rather than by calling `validate_band_phase_axis` directly,
        so an unwired guard reads as ADMITTED here instead of passing on a function
        nothing calls.
        """
        doc = self._doc(band)
        n = len(band["phases"][0])
        doc["tiles"] = copy.deepcopy(band["phases"][0]) + doc["tiles"][n:]
        try:
            emit_over_document(doc)
        except AssertionError:
            return "REFUSED"
        return "ADMITTED"

    def test_the_guard_reads_a_vertical_band_in_ITS_OWN_slot_order(self):
        """THE REGRESSION. A row-major vertical band of x-rolled phases is refused.

        Row-major IS a vertical band's slot order (§1.2 obligation 1), so this is the
        well-formed shape of the accident the guard exists for — and it is the shape
        the guard used to miss. `_band_pixels` decoded every bank column-major, which
        on a row-major band assembles a PERMUTATION of the real picture; the x-roll
        stopped looking like an x-roll, `h_rolls` came out False, and the caller's
        `continue` swallowed it.

        Note which direction the old docstring's defence covered: "a consistent
        relabelling of the slots cannot turn a non-translation into one" is true, and
        it rules out FALSE POSITIVES. This is the false NEGATIVE — the relabelling
        turned a translation INTO a non-translation.
        """
        self.assertEqual(self._verdict(self._x_rolled_vertical_band("row")), "REFUSED")

    def test_the_column_major_control_is_what_makes_that_row_mean_anything(self):
        """THE CONTROL, and it asserts the PAIR rather than one verdict.

        Same picture, same phases, only the slot order changed. Two things are pinned:
        the two arms really are a permutation of one another (so the row above is not
        quietly testing different art), and the guard's verdict MOVES with slot order
        in the stated direction. An emitter that refused everything, or admitted
        everything, fails here even though one of the two verdicts would look right.

        Why the control ADMITS rather than also refusing: a band that declares
        `vertical` and emits column-major slots is broken in obligation 1, which is
        explicitly not checked — the guard now reads the picture the declaration says
        is there, and on such a band that picture is scrambled, so any refusal would
        be incidental rather than earned. Widening the guard to catch it would be
        widening what is refused past obligation 2, which §1.2 forbids.
        """
        col = self._x_rolled_vertical_band("column")
        row = self._x_rolled_vertical_band("row")
        self.assertEqual(
            sorted(map(tuple, col["phases"][0])), sorted(map(tuple, row["phases"][0])),
            "the two arms are not the same SET of tiles, so they differ in more than "
            "slot order and neither row proves anything about slot order")
        self.assertNotEqual(col["phases"][0], row["phases"][0],
                            "the two arms are byte-identical — the fixture did not "
                            "actually change slot order, so this control is vacuous")
        self.assertEqual(
            (self._verdict(col), self._verdict(row)), ("ADMITTED", "REFUSED"),
            "the guard's verdict does not move with slot order in the direction the "
            "declared axis requires")

    def test_the_guard_does_not_outlaw_composite_vertical_art(self):
        """Anti-vacuous, and the reason the guard is a converse rather than a roll check.

        The shipped horizontal bands are NOT pure rolls (the historical act's firefly
        band is a brightness triangle, `forest_bg_gen.py` FF_TRI). Demanding that a
        vertical band's phases BE vertical rolls would forbid the same technique on
        the new axis before anyone has used it, so the guard must admit this.
        """
        rec, _ = self._record(self._band(8, 4, "vertical", None))
        self.assertEqual(rec["step_mask"], 4 * 8 - 1)

    def test_the_guard_admits_art_that_is_a_roll_on_BOTH_axes(self):
        """Art uniform along one axis is legitimately ambiguous; refusing it would be wrong.

        A band whose phase 0 is a single colour is a horizontal roll of itself and a
        vertical one. The guard's job is to catch art that is horizontal AND NOT
        vertical, so this must pass.
        """
        band = self._band(8, 4, "vertical", "v")
        flat = [[7] * 64 for _ in range(32)]
        band["phases"] = [copy.deepcopy(flat) for _ in range(8)]
        doc = self._doc(band)
        doc["tiles"] = copy.deepcopy(flat) + doc["tiles"][32:]
        emp, _ = emit_over_document(doc)
        self.assertIn("vertical (scrolls up)", emp)

    def test_the_guard_leaves_horizontal_bands_alone(self):
        """The shipped act's own phases ARE exact horizontal rolls and must stay legal.

        Measured 2026-09-02 on games/sonic4/data/editor_bg_override.json. If the guard
        ever ran on horizontal bands it would still pass here — which is exactly why
        this row is paired with the composite row above rather than standing alone.
        """
        rec, _ = self._record(self._band(8, 4, "horizontal", "h"))
        self.assertEqual(rec["step_mask"], 8 * 8 - 1)


# ---------------------------------------------------------------------------
# The section-size ceiling (decision d-9)
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
        ceiling = inject_editor_bg.BGANIM_SECTION_CEILING
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

        Until sigil b0363140 it was refused, because sigil's placement (~1 KB) and
        not the cartridge was the binding limit; with the placer arm retired the
        check is against the ROM-room ceiling and this is an ACCEPTANCE. The test
        derives its verdict from the live ceiling rather than hardcoding one, so it
        is the refusal's actionability that is asserted when it does refuse, and the
        returned size when it does not.
        """
        band = [self._band(8, 4, 0)]
        size = inject_editor_bg.bganim_section_bytes(1, 32)
        self.assertEqual(size, 8238)
        ceiling = inject_editor_bg.BGANIM_SECTION_CEILING
        if size <= ceiling:
            self.assertEqual(inject_editor_bg.check_bganim_section_fits(band), size)
            return
        msg, facts = self._refuse(band)
        self.assertEqual(refusal_shortfalls(msg, facts), [],
                         f"the refusal is not actionable:\n{msg}")

    def test_bands_each_under_the_ceiling_but_over_in_total(self):
        """Decision d-6's error, kept executable.

        BGANIM_MAX_BANDS bands, each the LARGEST single band the ceiling admits on
        its own (derived from the live ceiling, so the fixture keeps isolating the
        per-band/total distinction whatever the ceiling is ruled to be). Every band
        passes a per-band check; their SUM is over, because `BgAnim_Banks` is one
        blob for the whole act. A per-band check passes this and ships a section
        that does not fit.
        """
        ceiling = inject_editor_bg.BGANIM_SECTION_CEILING
        per_band = ((ceiling - inject_editor_bg.BGANIM_COUNT_BYTES
                     - inject_editor_bg.BGANIM_RECORD_BYTES)
                    // inject_editor_bg.BGANIM_BYTES_PER_SLOT)
        self.assertGreaterEqual(inject_editor_bg.BGANIM_MAX_BANDS, 2)
        bands = [self._band(per_band, 1, i * per_band)
                 for i in range(inject_editor_bg.BGANIM_MAX_BANDS)]
        for i, b in enumerate(bands):
            self.assertLess(inject_editor_bg.bganim_section_bytes(1, per_band), ceiling,
                            f"band {i} alone is already over the ceiling — this fixture "
                            f"no longer isolates the per-band/total distinction")
        msg, facts = self._refuse(bands)
        self.assertEqual(refusal_shortfalls(msg, facts), [],
                         f"the refusal is not actionable:\n{msg}")

    def test_the_boundary_is_exactly_the_ceiling(self):
        """One slot below passes, one slot above is refused — derived, not literal."""
        ceiling = inject_editor_bg.BGANIM_SECTION_CEILING
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
                     "ceiling": inject_editor_bg.BGANIM_SECTION_CEILING,
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
        """The ceiling must admit the stub and must not exceed the worst case a
        legal authoring can produce (bands pack as a prefix of `tiles`, so total
        slots <= BG_TILE_CAPACITY — validate_band_coherence is the authority)."""
        stub = inject_editor_bg.bganim_section_bytes(0, 0)
        worst = inject_editor_bg.BGANIM_WORST_CASE_BYTES
        self.assertEqual(
            worst,
            inject_editor_bg.bganim_section_bytes(inject_editor_bg.BGANIM_MAX_BANDS,
                                                  inject_editor_bg.BG_TILE_CAPACITY),
            "BGANIM_WORST_CASE_BYTES is not the section size at the provable bound")
        for name in ("BGANIM_SECTION_CEILING", "BGANIM_SECTION_CEILING_RULED"):
            v = getattr(inject_editor_bg, name)
            self.assertGreaterEqual(v, stub, f"{name} refuses even the disabled stub")
            self.assertLessEqual(v, worst, f"{name} exceeds the largest section any "
                                           f"legal authoring can produce ({worst} B)")

    # ---- the per-shape table (d-28-answered, then the ROM re-layout) ------------

    def test_per_shape_table_names_exactly_the_two_sonic4_listings(self):
        """The shape IS its listing. A third shape, or a renamed listing, has no ruled
        number and must surface as a missing row here, not as a silent default."""
        self.assertEqual(sorted(inject_editor_bg.BGANIM_SECTION_CEILINGS),
                         ["s4.debug.lst", "s4.lst"])
        for lst in ("s4.lst", "s4.debug.lst"):
            self.assertEqual(inject_editor_bg.BGANIM_SECTION_CEILINGS[lst],
                             inject_editor_bg.BGANIM_SECTION_CEILING_RULED)

    def test_both_shapes_carry_the_ruled_ceiling_after_the_relayout(self):
        """d-9's 12,288 in EVERY shape (the re-layout's acceptance, 2026-08-26): the
        DEBUG row is no longer derived from what a shape's room happened to hold —
        that derivation (anchor − packed end + held) was d-28-answered's one-day
        stopgap and is retired with its `_D28_*` terms. The number is typed here on
        purpose: it is the owner's ruling, the one thing this file may not derive."""
        self.assertEqual(inject_editor_bg.BGANIM_SECTION_CEILING_RULED, 12288,
                         "d-9's guarantee moved — that is an owner ruling")
        self.assertEqual(inject_editor_bg.BGANIM_SECTION_CEILING, 12288)
        self.assertEqual(inject_editor_bg.BGANIM_SECTION_CEILING,
                         min(inject_editor_bg.BGANIM_SECTION_CEILINGS.values()))
        for stale in ("_D28_DAC_BANKS_ANCHOR", "_D28_ART_SONIC_LMA_DEBUG",
                      "BGANIM_SECTION_CEILING_DEBUG", "BGANIM_SECTION_CEILING_RELEASE"):
            self.assertFalse(hasattr(inject_editor_bg, stale),
                             f"{stale} outlived the re-layout that retired it")

    # `test_generator_accepts_the_minimum_across_shapes` was RETIRED ON PURPOSE on
    # 2026-08-26, exactly as its own failure text instructed ("the two shapes agree
    # again — the re-layout landed? Then collapse the table and retire this test on
    # purpose"): it needed a section strictly between two DIFFERENT ceilings, and
    # there is no such section once both rows are 12,288. The property it guarded —
    # the generator accepts the MINIMUM across shapes — is asserted above.

    def test_an_unlisted_shape_is_unmeasurable_not_defaulted(self):
        import bganim_room
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.ceiling_for_listing(os.path.join(self.AEON, "demo.debug.lst"))
        self.assertIn("demo.debug.lst", str(cm.exception))
        self.assertIn("BGANIM_SECTION_CEILINGS", str(cm.exception))
        for lst in ("s4.lst", "s4.debug.lst"):
            key, ceiling = bganim_room.ceiling_for_listing(os.path.join(self.AEON, lst))
            self.assertEqual((key, ceiling),
                             (lst, inject_editor_bg.BGANIM_SECTION_CEILINGS[lst]))

    # ---- the ceilings against a real listing: NOT HERE -------------------------
    #
    # This class used to end with `test_rom_ceiling_fits_the_room_every_present_shape
    # _derives`, which read whatever `s4*.lst` a PRIOR build had left at the repo
    # root. Deleted 2026-08-26: pytest runs in build.sh's PRE-build lane, so that
    # listing was never the subject — twice at the sigil freeze it was another
    # profile's (config_a, Art_Sonic 0x2F440, room 12,078, refused against the
    # 12,094 DEBUG ceiling) or absent on a fresh tree. The enforcement against a real
    # listing lives ONLY in build.sh's post-sigil `bganim_room.py --gate`, on the
    # listing the same invocation emitted, with provenance. The derivation is tested
    # below over a committed cut (TestBgAnimRoomOverCommittedFixture). Nothing about
    # the ceiling became a skip: the fresh-tree case is measured by the runner that
    # has the artifact, and a missing listing there is a hard, named failure.


class TestBgAnimRoomOverCommittedFixture(unittest.TestCase):
    """tools/bganim_room.py's derivation, gate verdict, provenance and fixture-freshness
    checks — over a COMMITTED cut of a real listing, never the tree's own `.lst`.

    THE FIXTURE. tools/fixtures/bganim_room_excerpt.lst was CUT (not written) from
    `s4.debug.lst` as built on parcel/rom-relayout at aeon 0cddcaa9 (2026-08-26, the
    ROM re-layout: `dac_banks` 0x48000 -> 0x90000; a DEBUG=1 build, crc 090c6f35,
    len 734640) by `tools/fixtures/make_listing_excerpt.py s4.debug.lst <out> --set
    bganim`. Its Art_Sonic row is `(0) 2265/72A60 : Art_Sonic:`; at that SHA
    `git cat-file -s 0cddcaa9:art/optimized/characters/sonic.bin` = 97,472 and the
    shipping override held one 8x4 band (bganim_section_bytes(1, 32) = 8,238). So:

        packed end = 0x72A60 + 97472           = 0x8A720
        rule       = align_up(0x8A720 + 0xC000 + 0x8000, 0x8000) = 0xA0000
        room       = 0xA0000 - 0x8A720         = 88,288
        headroom   = 88,288 + 8,238            = 96,526   (ceiling 12,288 sits 84,238 inside)

    — the tests below hold the tool to those four lines. The hermetic tree the tests
    build carries exactly the inputs the tool reads (map.toml anchor, the embed line,
    a blob of that length, the override) so no term leaks in from the live tree.

    ⚠ THE HERMETIC ANCHOR IS DERIVED, NOT TYPED (2026-09-04). It used to be the
    literal 0x90000 the live map declared at the 08-26 re-layout, which made every
    number below a hostage of that one constant; the 09-04 re-layout (RESERVE 0x4000
    -> 0xC000, plus the new GRACE term) moved it. `FIXTURE_ANCHOR` is now
    `bganim_room.rule_anchor(packed end)` — the anchor THE RULE demands for this
    fixture's own packed end — so these tests track the rule's constants. It is not
    and need not be the live map's anchor: the fixture's packed end is 8+ days behind
    master's, so the live anchor is legitimately higher.

    FRESHNESS. A committed cut has nothing re-deriving it. build.sh's post-sigil gate
    passes `--fixture` so every row here is re-found in the fresh listing with the
    same lexical shape; `fixture_freshness` is unit-tested here on itself and on a
    mangled copy (red-first 2026-08-26: collapsing the whitespace of the Art_Sonic
    row fails the gate naming the row and the regenerate command).
    """

    AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    FIXTURE = os.path.join(AEON, "tools", "fixtures", "bganim_room_excerpt.lst")
    FIXTURE_ART_SONIC_BYTES = 97472        # git cat-file -s 0cddcaa9:art/optimized/characters/sonic.bin
    FIXTURE_ART_SONIC_LMA = 0x72A60        # the fixture's Art_Sonic row, hand-read below too
    FIXTURE_PACKED_END = FIXTURE_ART_SONIC_LMA + FIXTURE_ART_SONIC_BYTES   # 0x8A720
    # the hermetic tree's dac_banks — DERIVED from the rule, see the docstring
    FIXTURE_ANCHOR = bganim_room.rule_anchor(FIXTURE_PACKED_END)

    def _tree(self, band=(8, 4), blob_len=FIXTURE_ART_SONIC_BYTES, lst="s4.debug.lst",
              anchor=FIXTURE_ANCHOR):
        """A hermetic aeon-shaped tree holding only what bganim_room reads."""
        import shutil
        d = tempfile.mkdtemp(prefix="bganim_room_")
        self.addCleanup(shutil.rmtree, d)
        os.makedirs(os.path.join(d, "games", "sonic4", "data", "collision"))
        os.makedirs(os.path.join(d, "art"))
        with open(os.path.join(d, "games", "sonic4", "map.toml"), "w") as f:
            f.write('[[anchor]]\nname = "dac_banks"\nat = 0x%X\nwhen = "sound_on"\n'
                    % anchor)
        with open(os.path.join(d, "games", "sonic4", "data", "collision",
                               "collision_data.emp"), "w") as f:
            f.write('const _art_sonic      = embed("art/sonic.bin")\n'
                    'pub data Art_Sonic     = _art_sonic\n')
        with open(os.path.join(d, "art", "sonic.bin"), "wb") as f:
            f.write(b"\0" * blob_len)
        if band:
            with open(os.path.join(d, "games", "sonic4", "data",
                                   "editor_bg_override.json"), "w") as f:
                json.dump({"anims": [{"cols": band[0], "rows": band[1],
                                      "slot_base": 0}]}, f)
        shutil.copy(self.FIXTURE, os.path.join(d, lst))
        return d, os.path.join(d, lst)

    def _report(self, tree, lst, **kw):
        import io
        import bganim_room
        buf = io.StringIO()
        rc = bganim_room.report(lst, tree, gate=True, out=buf, **kw)
        return rc, buf.getvalue()

    def _hand_lma(self, path=None):
        """The Art_Sonic LMA read with NONE of the tool's parsers."""
        with open(path or self.FIXTURE, encoding="utf-8") as f:
            for line in f:
                if line.startswith("(0)") and line.rstrip().endswith(" Art_Sonic:"):
                    return int(line.split("/")[1].split()[0], 16)
        self.fail("the fixture carries no Art_Sonic row")

    # ---- the fixture is a real cut ---------------------------------------------

    def test_fixture_is_a_cut_of_a_real_listing(self):
        """Every label row parses under the tool's row regex, the symbol-table half
        agrees with the row half (the cutter's own invariant), and the rows tell the
        layout story in LMA order: the section that grows, the first label it
        pushes, the last packed blob, then the anchor's alignment label."""
        import bganim_room
        rows, syms = [], []
        with open(self.FIXTURE, encoding="utf-8") as f:
            for line in f:
                m = bganim_room._LST_LABEL.match(line)
                if m:
                    rows.append((m.group(2), int(m.group(1), 16)))
                m = re.match(r"^\s*\*?([\w.$]+) : ([0-9A-F]+) [C-] \|$", line.rstrip())
                if m:
                    syms.append((m.group(1), int(m.group(2), 16)))
        self.assertEqual(rows, syms, "the two halves of the cut disagree")
        names = [n for n, _ in rows]
        self.assertEqual(names, ["Vectors", "BgAnim_Banks", "Map_TestObj", "Art_Sonic",
                                 "__align$games.sonic4.dac_banks$0"])
        lmas = [a for _, a in rows]
        self.assertEqual(lmas, sorted(lmas))
        self.assertEqual(self._hand_lma(), self.FIXTURE_ART_SONIC_LMA,
                         "the fixture is no longer the 0cddcaa9 (re-layout) cut this "
                         "class documents — update the docstring's derivation with it, "
                         "do not just re-cut")

    # ---- the derivation ---------------------------------------------------------

    def test_room_is_the_hand_computation(self):
        import bganim_room
        tree, lst = self._tree()
        lma = self._hand_lma()
        room = self.FIXTURE_ANCHOR - (lma + self.FIXTURE_ART_SONIC_BYTES)
        self.assertEqual(room, 88288, "0xA0000 - (0x72A60 + 97472), by hand")
        r = bganim_room.rom_room(lst, tree)
        self.assertEqual(
            (r["art_sonic_lma"], r["art_blob_len"], r["anchor"], r["room"]),
            (lma, self.FIXTURE_ART_SONIC_BYTES, self.FIXTURE_ANCHOR, room),
            f"tool says {r}, hand says 0x{self.FIXTURE_ANCHOR:X} - (0x{lma:X} + "
            f"{self.FIXTURE_ART_SONIC_BYTES}) = {room}")

    def test_ruled_ceiling_sits_inside_the_fixture_room_and_the_rule_holds(self):
        """The re-layout's acceptance in miniature: the DEBUG shape's room holds the
        ruled 12,288 with a POSITIVE margin, the report names the ruled ceiling as the
        binding limit, prints the bank placement rule with this shape's own numbers,
        and carries no trace of the retired placer arm."""
        import bganim_room
        tree, lst = self._tree()
        live = inject_editor_bg.bganim_section_bytes(1, 32)
        self.assertEqual(live, 8238)
        self.assertEqual(inject_editor_bg.live_section_bytes(tree), live)
        packed_end = self._hand_lma() + self.FIXTURE_ART_SONIC_BYTES
        room = self.FIXTURE_ANCHOR - packed_end
        headroom = room + live
        self.assertEqual(headroom, 96526)
        ceiling = inject_editor_bg.BGANIM_SECTION_CEILINGS["s4.debug.lst"]
        self.assertGreater(headroom - ceiling, 0, "the re-layout must leave a POSITIVE margin")
        # the rule, by hand: the first 0x8000 boundary at or above end + reserve + grace
        reserve = bganim_room.DATA_GROWTH_RESERVE
        grace = bganim_room.DATA_GROWTH_GRACE
        self.assertEqual(reserve, 0xC000, "the d-28 16,384 B band guarantee + 30 days of "
                                          "the measured 08-26..09-04 consumption, rounded "
                                          "up to the reserve's own 0x4000 quantum")
        self.assertEqual(grace, 0x8000, "one SetBank window of guaranteed growth before "
                                        "the gate can fire again")
        rule = -(-(packed_end + reserve + grace) // 0x8000) * 0x8000
        self.assertEqual(rule, 0xA0000)
        self.assertEqual(bganim_room.rule_anchor(packed_end), rule)
        rc, text = self._report(tree, lst)
        self.assertEqual(rc, 0, text)
        self.assertRegex(text, rf"(?m)^\s*ROM room {room} B free\b", text)
        self.assertRegex(text, rf"(?m)^\s*binding limit: the ruled ceiling \({ceiling} B\) — it "
                               rf"sits {headroom - ceiling} B inside the ROM room", text)
        self.assertRegex(text, rf"(?m)^\s*bank placement rule: packed end 0x{packed_end:X} \+ "
                               rf"reserve {reserve} B \+ grace {grace} B -> dac_banks >= "
                               rf"0x{rule:X}; declared 0x{self.FIXTURE_ANCHOR:X} "
                               rf"\(this shape binds exactly\)", text)
        self.assertRegex(text, rf"(?m)^\s*growth before this gate fires again: "
                               rf"{room - reserve} B ", text)
        self.assertNotIn("placer", text.lower(), text)
        self.assertNotIn("BGANIM-PLACE", text)

    def test_rule_fails_naming_the_new_anchor_pair_when_room_drops_under_the_reserve(self):
        """RED-FIRST for the rule arm: the art blob grown 40 KB. The room (47,328 B)
        still holds the 12,288 ceiling — so the CEILING arm passes and only the RULE
        arm can fail — and the failure names the anchor pair the rule now demands.

        The growth is 0xA000 and not the 0x2000 this test used before 2026-09-04
        because the reserve is now 0xC000: 8 KB of growth no longer breaches it, and a
        test that could not go red would have kept passing forever."""
        import bganim_room
        grown = self.FIXTURE_ART_SONIC_BYTES + 0xA000
        tree, lst = self._tree(blob_len=grown)
        packed_end = self._hand_lma() + grown
        room = self.FIXTURE_ANCHOR - packed_end
        self.assertEqual(room, 47328)
        self.assertGreater(room + 8238, inject_editor_bg.BGANIM_SECTION_CEILING)
        self.assertLess(room, bganim_room.DATA_GROWTH_RESERVE)
        want = -(-(packed_end + bganim_room.DATA_GROWTH_RESERVE
                   + bganim_room.DATA_GROWTH_GRACE) // 0x8000) * 0x8000
        self.assertEqual(want, 0xB0000)
        rc, text = self._report(tree, lst)
        self.assertEqual(rc, 1, text)
        self.assertNotIn("the ruled BG-animation ceiling no longer fits", text)
        self.assertIn("FAIL — the bank placement rule is broken", text)
        self.assertIn(f"leaving {room} B < DATA_GROWTH_RESERVE {bganim_room.DATA_GROWTH_RESERVE} B", text)
        self.assertIn(f"dac_banks = align_up(packed_end + reserve + grace, 0x8000) = 0x{want:X}", text)
        self.assertIn(f"sound_bank = dac_banks + 0x10000 = 0x{want + 0x10000:X}", text)
        self.assertIn("Do NOT shrink the reserve", text)
        # the remedy text names the sigil hand-off as a REQUIREMENT, because a map
        # anchor places nothing (measured 2026-09-04, both directions — see the block
        # in games/sonic4/map.toml)
        self.assertIn("hand the two addresses to the sigil lane", text)
        self.assertIn("map.undeclared-island", text)
        self.assertNotIn("a paired aeon+sigil landing)", text)
        # without --gate the same breach is reported, not enforced
        import io
        buf = io.StringIO()
        self.assertEqual(bganim_room.report(lst, tree, gate=False, out=buf), 0)
        self.assertIn("the bank placement rule is broken", buf.getvalue())

    def test_rule_reports_slack_when_another_shape_binds(self):
        """One anchor serves every sound-on shape, so an anchor ABOVE this shape's
        rule value is slack, not a breach: reported, never failed."""
        tree, lst = self._tree(anchor=self.FIXTURE_ANCHOR + 0x8000)
        rc, text = self._report(tree, lst)
        self.assertEqual(rc, 0, text)
        self.assertRegex(text, r"(?m)^\s*bank placement rule: .* declared 0xA8000 \(0x8000 of "
                               r"slack above this shape's rule value — another sound-on "
                               r"shape binds, or the rule moved\)", text)

    def test_grace_makes_the_room_above_the_reserve_a_guarantee_not_a_draw(self):
        """The 2026-09-04 GRACE term, stated as the property it exists for.

        The 08-26 rule was `align_up(end + RESERVE)` and the gate fails at
        `room < RESERVE`, so the growth absorbable before the gate re-fires was
        `align_up(end + R) - end - R` — the align_up remainder, a draw on
        `end mod 0x8000` that is 0 whenever `end + R` lands exactly on a boundary,
        and that RAISING R DOES NOT FIX (both terms move together). This test sweeps
        every residue class of the quantum and asserts the floor holds in all of them.

        RED-FIRST (2026-09-04, mutation applied on disk and reverted): dropping
        `+ DATA_GROWTH_GRACE` from `rule_anchor` fails this at the very first residue
        (`end = 0x8000`: room 0xC000, floor 0x14000), and leaves the whole rest of
        this class green — which is exactly why the defect survived 08-26."""
        import bganim_room
        floor = bganim_room.DATA_GROWTH_RESERVE + bganim_room.DATA_GROWTH_GRACE
        # every residue of the SetBank quantum, at a realistic ROM magnitude
        for end in range(0x8000, 0x8000 + 0x8000 + 1, 0x40):
            anchor = bganim_room.rule_anchor(end)
            self.assertEqual(anchor % bganim_room.BANK_ALIGN, 0,
                             f"0x{anchor:X} is not a SetBank window")
            self.assertGreaterEqual(
                anchor - end, floor,
                f"packed end 0x{end:X} -> anchor 0x{anchor:X} leaves {anchor - end} B, "
                f"under the RESERVE+GRACE floor of {floor} B: the grace term is not "
                f"guaranteeing anything and the next re-layout is a lottery again")
            # and the guarantee is TIGHT — the rule never buys a spare window it did
            # not need, so the ROM cost is the minimum that satisfies the floor
            self.assertLess(anchor - end, floor + bganim_room.BANK_ALIGN,
                            f"packed end 0x{end:X} bought a window it did not need")

    def test_rule_rejects_an_anchor_that_is_not_bank_aligned(self):
        """A Z80 SetBank window is 0x8000; an anchor off that grid is unmeasurable as
        a bank and fails by name before any room arithmetic is trusted."""
        tree, lst = self._tree(anchor=0x8C000)
        rc, text = self._report(tree, lst)
        self.assertEqual(rc, 1, text)
        self.assertIn("dac_banks 0x8C000 is not 0x8000-aligned", text)

    def test_per_shape_table_gates_the_release_row_against_the_release_listing(self):
        """The KEY is the listing's basename: the same cut renamed `s4.lst` is gated
        against the RELEASE row (it passes — both rows are 12,288 now), and poking
        ONLY the release row over the room fails it naming `s4.lst`, while the debug
        row is untouched."""
        tree, lst = self._tree(lst="s4.lst")
        rc, text = self._report(tree, lst)
        self.assertEqual(rc, 0, text)
        self.assertIn("BGANIM_SECTION_CEILINGS['s4.lst'] = 12288 B", text)
        headroom = (self.FIXTURE_ANCHOR - (self._hand_lma() + self.FIXTURE_ART_SONIC_BYTES)
                    + inject_editor_bg.bganim_section_bytes(1, 32))
        table = inject_editor_bg.BGANIM_SECTION_CEILINGS
        saved = table["s4.lst"]
        table["s4.lst"] = headroom + 1
        try:
            rc, text = self._report(tree, lst)
        finally:
            table["s4.lst"] = saved
        self.assertEqual(rc, 1, text)
        self.assertIn(f"BGANIM_SECTION_CEILINGS['s4.lst'] = {headroom + 1} B but only "
                      f"{headroom} B", text)

    def test_one_byte_over_the_room_fails_the_gate_naming_the_shape(self):
        """Red-first for the post-sigil gate, in miniature: the debug row one byte
        above what the shape holds — the headroom is read off the TOOL's own
        derivation so the test tracks the fixture, never a typed number."""
        import bganim_room
        tree, lst = self._tree()
        headroom = (bganim_room.rom_room(lst, tree)["room"]
                    + inject_editor_bg.live_section_bytes(tree))
        self.assertEqual(headroom, 96526)
        table = inject_editor_bg.BGANIM_SECTION_CEILINGS
        saved = table["s4.debug.lst"]
        table["s4.debug.lst"] = headroom + 1
        try:
            rc, text = self._report(tree, lst)
        finally:
            table["s4.debug.lst"] = saved
        self.assertEqual(rc, 1, text)
        self.assertIn("the ruled BG-animation ceiling no longer fits", text)
        self.assertIn(f"BGANIM_SECTION_CEILINGS['s4.debug.lst'] = {headroom + 1} B but only "
                      f"{headroom} B are reachable", text)
        self.assertIn("dac_banks", text)
        self.assertRegex(text, rf"(?m)^\s*binding limit: the ROM room \({headroom} B\)", text)

    # ---- loud on every unmeasurable input ---------------------------------------

    def test_absent_listing_is_loud_and_names_the_runner(self):
        """No listing is a BUILD BUG at the post-sigil gate, never a bootstrap
        condition, and never a skip; the message says who the runner is."""
        import bganim_room
        tree, _ = self._tree()
        missing = os.path.join(tree, "s4.lst")
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.rom_room(missing, tree)
        msg = str(cm.exception)
        for needle in ("NOTHING WAS MEASURED", "build.sh", "POST-sigil", "BUILD BUG",
                       "Do not convert this to a skip"):
            self.assertIn(needle, msg, msg)
        import io
        import contextlib
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = bganim_room.main(["--lst", missing, "--gate"])
        self.assertEqual(rc, 1)
        self.assertIn("FAIL (unmeasurable)", err.getvalue())

    def test_provenance_is_temporal_and_rejects_a_prior_builds_listing(self):
        """The listing carries no ROM identity, so the check the tool makes is that
        the listing AND the ROM post-date the sigil invocation."""
        import bganim_room
        tree, lst = self._tree()
        rom = os.path.join(tree, "s4.debug.bin")
        with open(rom, "wb") as f:
            f.write(b"\0")
        t = os.path.getmtime(lst)
        self.assertEqual(sorted(bganim_room.check_provenance(lst, rom, t - 1)),
                         ["ROM", "listing"])
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.check_provenance(lst, rom, t + 1)
        self.assertIn("PRIOR build's listing", str(cm.exception))
        os.utime(rom, (t - 10, t - 10))
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.check_provenance(lst, rom, t - 1)
        self.assertIn("PRIOR build's ROM", str(cm.exception))
        os.remove(rom)
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.check_provenance(lst, rom, t - 1)
        self.assertIn("does not exist", str(cm.exception))
        # The report wires it: a prior listing fails BEFORE any room is printed.
        with open(rom, "wb") as f:
            f.write(b"\0")
        with self.assertRaises(bganim_room.Unmeasurable):
            self._report(tree, lst, rom_path=rom, built_after=t + 1)
        rc, text = self._report(tree, lst, rom_path=rom, built_after=t - 1)
        self.assertEqual(rc, 0, text)
        self.assertIn("provenance: s4.debug.lst and s4.debug.bin both written after", text)
        # --built-after without --rom is a usage error, not a pass.
        import io
        import contextlib
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(bganim_room.main(["--lst", lst, "--built-after", "1"]), 2)

    def test_fixture_freshness_passes_on_itself_and_names_a_stale_row(self):
        import bganim_room
        tree, lst = self._tree()
        labels = bganim_room.fixture_freshness(lst, self.FIXTURE)
        self.assertIn("Art_Sonic", labels)
        self.assertEqual(len(labels), 5)
        rc, text = self._report(tree, lst, fixture_path=self.FIXTURE)
        self.assertEqual(rc, 0, text)
        self.assertIn("5 label rows re-found", text)
        # A mangled row: same parser fields, different lexical shape.
        rows = open(self.FIXTURE, encoding="utf-8").read().splitlines()
        i = next(i for i, r in enumerate(rows) if r.endswith(" Art_Sonic:"))
        mangled = os.path.join(tree, "mangled.lst")
        with open(mangled, "w") as f:
            f.write("\n".join(rows[:i] + [re.sub(r"\s+", " ", rows[i])] + rows[i + 1:]) + "\n")
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.fixture_freshness(lst, mangled)
        msg = str(cm.exception)
        self.assertIn("row for 'Art_Sonic' is STALE", msg)
        self.assertIn("make_listing_excerpt.py", msg)
        self.assertIn("--set bganim", msg)
        # A label the fresh listing no longer emits.
        renamed = os.path.join(tree, "renamed.lst")
        with open(renamed, "w") as f:
            f.write("\n".join(r.replace("Art_Sonic", "Art_Sonic_v2") for r in rows) + "\n")
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.fixture_freshness(lst, renamed)
        self.assertIn("carries label 'Art_Sonic_v2' but the fresh listing", str(cm.exception))
        # A fixture with no rows checks nothing, and says so.
        empty = os.path.join(tree, "empty.lst")
        open(empty, "w").close()
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.fixture_freshness(lst, empty)
        self.assertIn("no label rows", str(cm.exception))
        # And the substitution really is only the two numeric fields: a fresh
        # listing whose Art_Sonic MOVED still matches the fixture.
        moved = os.path.join(tree, "moved.lst")
        with open(moved, "w") as f:
            f.write("\n".join(r.replace("2265/72A60", "2300/72A70") for r in rows) + "\n")
        self.assertEqual(len(bganim_room.fixture_freshness(moved, self.FIXTURE)), 5)


class TestBgAnimPlacerArmRetired(unittest.TestCase):
    """The "placer room" arm of tools/bganim_room.py is GONE, and the ROM room is not.

    WHY. Until sigil b0363140 (merge of feat/derived-layout, 2026-08-25) the chainer
    measured every section at its FROZEN provisional base and could absorb only one
    0x400 spread step before `colliding pins`; `ojz_bg_anim` therefore had a ~1 KB
    "placer room" that bganim_room.py derived from a regex over sigil's source and
    reported as BINDING. Since that merge a pure-data section that outgrows its pin is
    re-measured at a scratch slot (`image_lens_pinned(.., scratch_data=true)`) and its
    neighbours pack downstream with a `[layout.provisional-drift]` WARNING, never a
    stop — the number no longer bounds anything. sigil's own design note named the
    retirement as aeon's: "a stale-but-green tool is the worse failure". These tests
    make the retirement a property, not a deletion: the output has no placer line,
    the module has no sigil-source regex, the emitter has no placer ceiling — and the
    ROM-room derivation that DOES still bind is checked against a hand computation
    done here with none of the tool's own parsers.
    """

    AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    TOOL = os.path.join(AEON, "tools", "bganim_room.py")

    # ---- (a) the arm is gone ----------------------------------------------------
    # (The report's "no placer line / names the binding limit" property and the
    # hand-computed ROM room both moved to TestBgAnimRoomOverCommittedFixture on
    # 2026-08-26 — they read the tree's own listing here, which pytest never owns.)

    def test_module_carries_no_sigil_source_regex_or_placer_derivation(self):
        """Derived from the module's CODE (its AST, docstrings excluded — the header
        is allowed to say what was retired), not from a name list someone remembered:
        no string constant may name a path under sigil's `crates/` or the SIGIL_BUILD
        env var, no regex may match the spread literal, and no name the module
        defines may say `placer` or `spread`."""
        import ast
        import bganim_room
        src = open(self.TOOL, encoding="utf-8").read()
        tree = ast.parse(src)
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)):
                body = getattr(node, "body", [])
                if (body and isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    docstrings.add(id(body[0].value))
        code_strings = [n.value for n in ast.walk(tree)
                        if isinstance(n, ast.Constant) and isinstance(n.value, str)
                        and id(n) not in docstrings]
        for needle in ("crates", "SIGIL_BUILD", "rank as u32", "spread", "placer"):
            hits = [c for c in code_strings if needle.lower() in c.lower()]
            self.assertEqual(hits, [], f"bganim_room.py code still spells {needle!r}: "
                                       f"{hits}")
        stale = sorted(n for n in dir(bganim_room)
                       if "placer" in n.lower() or "spread" in n.lower())
        self.assertEqual(stale, [], f"retired names still defined: {stale}")
        defined = {n.id for n in ast.walk(tree)
                   if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        defined |= {n.name for n in ast.walk(tree)
                    if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        self.assertEqual(sorted(n for n in defined
                                if "placer" in n.lower() or "spread" in n.lower()), [])
        self.assertIsNone(re.search(r"^\s*_SPREAD\b", src, re.M),
                          "the `_SPREAD` regex over sigil's native.rs is still defined")

    def test_emitter_has_a_single_ceiling_and_it_is_the_rom_one(self):
        stale = sorted(n for n in dir(inject_editor_bg) if "PLACER" in n.upper())
        self.assertEqual(stale, [], f"inject_editor_bg still defines {stale}")
        self.assertFalse(hasattr(inject_editor_bg, "bganim_effective_ceiling"),
                         "the two-limit chooser outlived its second limit")
        # The refusal names the ROM room, not the placer, and stays actionable.
        with self.assertRaises(SystemExit) as cm:
            inject_editor_bg.check_bganim_section_fits(
                [{"cols": 32, "rows": 4, "slot_base": 0},
                 {"cols": 16, "rows": 4, "slot_base": 128}])
        msg = str(cm.exception)
        self.assertNotIn("placer", msg.lower())
        self.assertNotIn("BGANIM-PLACE", msg)
        self.assertIn("dac_banks", msg)
        facts = {"bands": 2, "slots": 192,
                 "ceiling": inject_editor_bg.BGANIM_SECTION_CEILING, "size": 49242}
        self.assertEqual(refusal_shortfalls(msg, facts), [], msg)

    def test_an_8kb_class_band_is_accepted_under_the_section_ceiling(self):
        """aurora's 8x4 band: 2 + 44 + 32x256 = 8,238 B. It was REFUSED by the
        placer ceiling (1,026 B); under the only remaining ceiling it is accepted."""
        size = inject_editor_bg.bganim_section_bytes(1, 32)
        self.assertEqual(size, 8238)
        self.assertLessEqual(size, inject_editor_bg.BGANIM_SECTION_CEILING,
                             "the ruled ceiling no longer admits an 8 KB band — that is "
                             "an owner ruling change, not something this test hides")
        band = [{"cols": 8, "rows": 4, "slot_base": 0}]
        self.assertEqual(inject_editor_bg.check_bganim_section_fits(band), size)

    def test_over_the_section_ceiling_is_refused_naming_that_ceiling(self):
        ceiling = inject_editor_bg.BGANIM_SECTION_CEILING
        fits = ((ceiling - inject_editor_bg.BGANIM_COUNT_BYTES
                 - inject_editor_bg.BGANIM_RECORD_BYTES)
                // inject_editor_bg.BGANIM_BYTES_PER_SLOT)
        band = [{"cols": fits + 1, "rows": 1, "slot_base": 0}]
        with self.assertRaises(SystemExit) as cm:
            inject_editor_bg.check_bganim_section_fits(band)
        msg = str(cm.exception)
        self.assertIn("BGANIM_SECTION_CEILING", msg, msg)
        self.assertIn(f"the ceiling is {ceiling} B", msg, msg)
        self.assertNotIn("placer", msg.lower(), msg)

    def test_no_placer_string_survives_in_either_tools_code(self):
        """Both tools, AST-level (docstrings excluded, comments are not in the AST):
        no string constant and no defined name says `placer`."""
        import ast
        for rel in ("bganim_room.py", "inject_editor_bg.py"):
            src = open(os.path.join(self.AEON, "tools", rel), encoding="utf-8").read()
            tree = ast.parse(src)
            doc_ids = set()
            for node in ast.walk(tree):
                body = getattr(node, "body", None)
                if (isinstance(body, list) and body and isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    doc_ids.add(id(body[0].value))
            hits = [n.value for n in ast.walk(tree)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)
                    and id(n) not in doc_ids and "placer" in n.value.lower()]
            names = sorted({n.id for n in ast.walk(tree) if isinstance(n, ast.Name)
                            and "placer" in n.id.lower()}
                           | {n.name for n in ast.walk(tree)
                              if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                              and "placer" in n.name.lower()})
            self.assertEqual((hits, names), ([], []), f"tools/{rel}: {hits} {names}")


class TestActIsAParameter(unittest.TestCase):
    """`inject_editor_bg` takes an act; nothing in its emission knows act 1's name.

    WHY A FIXTURE PINNED TO `act1` WOULD BE WORTHLESS HERE. Every assertion below is
    written against a SECOND act id derived from the declared one (`_next_act_id`),
    and the load-bearing assertion is the negative: the default act's id must not
    appear ANYWHERE in the module emitted for that second act. A test that spelled
    `act1` in its own expectations would pass against the fully-hardcoded emitter
    this replaced — which is exactly the failure mode being gated.

    Red-first evidence (2026-08-27): with the module line restored to the literal
    `module games.sonic4.ojz_bg_anim_act1 in ojz_bg_anim`,
    `test_a_second_act_gets_its_own_module_and_embed_path` fails on
    `'module games.sonic4.ojz_bg_anim_act2 in ojz_bg_anim' not found`, and
    `test_no_emitted_name_is_hardcoded_to_the_default_act` fails naming the line.

    Runner: build.sh's pre-build pytest lane runs tools/ (`Running the tool-suite
    unit tests...`), which is what executes this file on every canonical build.
    """

    AEON = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         ".."))

    @staticmethod
    def _next_act_id(act_id):
        """A DIFFERENT, symbol-safe act id derived from the declared one.

        "The next act of the same zone": bump a trailing integer (`act1` -> `act2`),
        or suffix when there is no trailing integer. Derived rather than typed so
        this test keeps testing the PARAMETER if project.json's act ids are ever
        renamed, instead of testing a literal that no longer names anything.
        """
        m = re.match(r"^(.*?)(\d+)$", act_id)
        return f"{m.group(1)}{int(m.group(2)) + 1}" if m else act_id + "2"

    @staticmethod
    def _one_band_override():
        """A minimal legal override, built from the FORMAT rather than copied.

        cols x rows = 2 x 2 so column bytes (rows*32 = 64) is a power of two and
        pattern_px (cols*8 = 16) matches, which is what `main()` asserts. Band
        coherence requires phases[0] to BE the static tiles it covers, so phase 0 is
        the tile list itself.
        """
        tiles = [[(t * 7 + p) & 0xF for p in range(64)] for t in range(4)]
        return {
            "layout": [0] * 4096,
            "tiles": tiles,
            "anims": [{
                "cols": 2, "rows": 2, "pattern_px": 16,
                "driver": "timer", "rate_shift": 2,
                "phases": [tiles] + [[list(t) for t in tiles] for _ in range(7)],
            }],
        }

    def _bake(self, act):
        """Run the real `main()` for `act` and return its emitted `bg_anim.emp`."""
        os.makedirs(act.out_dir(), exist_ok=True)
        with open(act.override_path(), "w") as f:
            json.dump(self._one_band_override(), f)
        with ceiling_lifted():
            inject_editor_bg.main(act)
        with open(os.path.join(act.out_dir(), "bg_anim.emp"), encoding="utf-8") as f:
            return f.read()

    def test_a_second_act_gets_its_own_module_and_embed_path(self):
        default = inject_editor_bg.ACT
        other_id = self._next_act_id(default.act_id)
        self.assertNotEqual(other_id, default.act_id,
                            "_next_act_id produced the declared act — nothing is "
                            "being varied, so this test measures nothing")
        with tempfile.TemporaryDirectory() as tmp:
            other = inject_editor_bg.BgActNames(default.zone_id, other_id, repo=tmp)
            os.makedirs(os.path.dirname(other.override_path()), exist_ok=True)
            emp = self._bake(other)

        self.assertIn(
            f"module games.sonic4.{default.zone_id}_bg_anim_{other_id} "
            f"in {default.zone_id}_bg_anim", emp,
            "the emitted module name does not carry the act it was baked for")
        self.assertIn(
            f'embed("games/sonic4/data/generated/{default.zone_id}/{other_id}/'
            f'bg_anim_banks.bin")', emp,
            "the emitted embed() path does not point at this act's bank blob")

    def test_no_emitted_name_is_hardcoded_to_the_default_act(self):
        """The negative that a `act1`-shaped fixture could never make."""
        default = inject_editor_bg.ACT
        other_id = self._next_act_id(default.act_id)
        with tempfile.TemporaryDirectory() as tmp:
            other = inject_editor_bg.BgActNames(default.zone_id, other_id, repo=tmp)
            os.makedirs(os.path.dirname(other.override_path()), exist_ok=True)
            emp = self._bake(other)
            # Nothing may have been written for the DEFAULT act either: a leaked
            # OUT_DIR would have created its directory under this tmp repo.
            leaked = os.path.join(tmp, "games", "sonic4", "data", "generated",
                                  default.zone_id, default.act_id)
            self.assertFalse(os.path.exists(leaked),
                             f"baking {other.label} wrote into {default.label}'s "
                             f"output directory")
            for name in ("bg_anim_banks.bin", "zone_bg.bin", "bg_tiles.bin"):
                self.assertTrue(os.path.exists(os.path.join(other.out_dir(), name)),
                                f"{name} was not written under {other.label}")

        offenders = [ln for ln in emp.splitlines() if default.act_id in ln]
        self.assertEqual(
            offenders, [],
            f"the module emitted for {other.label} still names the default act "
            f"{default.act_id!r}: " + " | ".join(offenders) +
            ". Some emitted name is a constant rather than derived from the act.")

    def test_the_legacy_override_filename_belongs_to_exactly_one_act(self):
        """The grandfathered un-suffixed override name maps to ONE act, by ids.

        Two things this pins. (1) The act holding the legacy name really is the
        act the no-argument call site bakes — if project.json ever grows a zone
        ahead of this one, act 1 would otherwise silently stop finding its own
        background and bake the generated zone BG instead. (2) A different act
        never resolves to that file, so the second act's absent override is a
        missing-file failure rather than a silent bake of act 1's art.
        """
        default = inject_editor_bg.ACT
        self.assertEqual(
            (default.zone_id, default.act_id), inject_editor_bg.LEGACY_OVERRIDE_ACT,
            "project.json's first act is no longer the act that owns the legacy "
            "un-suffixed override filename (inject_editor_bg.LEGACY_OVERRIDE_ACT). "
            "Move the file to the per-act spelling, or move the constant.")
        legacy = os.path.join(self.AEON, *inject_editor_bg.LEGACY_OVERRIDE_REL)
        self.assertEqual(os.path.normpath(default.override_path()),
                         os.path.normpath(legacy))

        other_id = self._next_act_id(default.act_id)
        other = inject_editor_bg.BgActNames(default.zone_id, other_id, repo=self.AEON)
        self.assertNotEqual(os.path.normpath(other.override_path()),
                            os.path.normpath(legacy),
                            f"{other.label} resolves to {default.label}'s override "
                            f"file — a second act would bake the first act's art")
        self.assertIn(f"{default.zone_id}_{other_id}",
                      os.path.basename(other.override_path()))

    def test_the_source_carries_no_stray_default_act_literal(self):
        """`act1` may appear in exactly one place in the emitter: the legacy pair.

        AST string constants only, so prose in comments and docstrings is exempt —
        the gate is on what the tool can EMIT or RESOLVE, not on what it explains.
        """
        import ast
        default_act = inject_editor_bg.ACT.act_id
        src = open(os.path.join(self.AEON, "tools", "inject_editor_bg.py"),
                   encoding="utf-8").read()
        tree = ast.parse(src)

        doc_ids = set()
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if (isinstance(body, list) and body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                doc_ids.add(id(body[0].value))

        allowed = set()
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "LEGACY_OVERRIDE_ACT"
                            for t in node.targets)):
                allowed |= {id(c) for c in ast.walk(node.value)
                            if isinstance(c, ast.Constant)}
        self.assertTrue(allowed, "LEGACY_OVERRIDE_ACT assignment not found — this "
                                 "gate lost its subject and would pass vacuously")

        offenders = sorted(
            n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in doc_ids and id(n) not in allowed
            and default_act in n.value)
        self.assertEqual(
            offenders, [],
            f"tools/inject_editor_bg.py names the default act {default_act!r} in a "
            f"string constant at line(s) {offenders}. The act is a parameter: derive "
            f"the name from BgActNames instead. The only licensed occurrence is "
            f"LEGACY_OVERRIDE_ACT.")


if __name__ == "__main__":
    unittest.main()
