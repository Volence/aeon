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

import pytest

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


def shape_aware_size(anims):
    """What `ojz_bg_anim` really comes to for `anims`, view terms included.

    ONE SPELLING for the tests, because `bganim_section_bytes`'s two view arguments
    both default to 0 and a bare call therefore answers a question no emitted module
    has ever asked: the twins are either three band tables (a qualifying act) or three
    count-0 words (every other act, since 2026-09-06 — the exported names are
    shape-invariant), and never absent. A test that models them as absent is 6 or
    138 bytes adrift from the artifact it claims to measure.
    """
    return inject_editor_bg.bganim_section_bytes(
        len(anims), sum(a["cols"] * a["rows"] for a in anims),
        n_views=inject_editor_bg.views_emitted(anims),
        n_declined_views=inject_editor_bg.declined_views(anims))


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
            "size": shape_aware_size(anims)}

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
        # The DECLINED view names are part of what the emitter writes — three count
        # words in the DEBUG shape (this fixture sets no `default_off`, so the twins
        # decline). Counting the emitted `pub data BgAnim_View_*` lines rather than
        # assuming three keeps this comparing the artifact to the formula.
        n_declined = sum(1 for line in emp.splitlines()
                         if line.startswith("pub data BgAnim_View_")
                         and "[0]" in line)
        self.assertEqual(n_declined, inject_editor_bg.BGANIM_VIEW_COUNT)
        observed = (inject_editor_bg.BGANIM_COUNT_BYTES
                    + inject_editor_bg.BGANIM_RECORD_BYTES * n_bands
                    + n_declined * inject_editor_bg.BGANIM_COUNT_BYTES + len(banks))
        self.assertEqual(
            inject_editor_bg.bganim_section_bytes(n_bands, 1,
                                                  n_declined_views=n_declined),
            observed,
            "bganim_section_bytes disagrees with the bytes the emitter actually "
            "produced — the ceiling is then measuring a section that does not exist")
        self.assertIn("pub data BgAnim_Table: u16 = 1", emp,
                      "the animated arm did not run, so nothing was measured")
        self.assertEqual(anims and True, True)   # fixture really carried bands

    # ---- the refusal ----------------------------------------------------------

    def test_the_historical_two_band_act_is_refused(self):
        """The real content this zone shipped: 32x4 + 16x4 = 192 slots.

        49,242 B of bands and blob, plus the three DECLINED view names' count words
        in the DEBUG shape (this act sets no `default_off`, so the twins decline —
        but their names are exported by every act shape since 2026-09-06).
        """
        msg, facts = self._refuse([self._band(32, 4, 0), self._band(16, 4, 128)])
        self.assertEqual(facts["slots"], 192)
        self.assertEqual(facts["size"],
                         49242 + inject_editor_bg.BGANIM_VIEW_COUNT
                         * inject_editor_bg.BGANIM_COUNT_BYTES)
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
        self.assertEqual(inject_editor_bg.bganim_section_bytes(1, 32), 8238,
                         "the bands-and-blob half of the size, which is the number "
                         "this act has always been known by")
        # What the emitter actually writes for THIS document: the band, the blob and
        # the three declined view names' count words.
        size = shape_aware_size(band)
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
                     "size": shape_aware_size(d["anims"])}
            self.assertEqual(refusal_shortfalls(str(cm.exception), facts), [],
                             f"main()'s refusal is not actionable:\n{cm.exception}")
            for name in ("bg_anim.emp", "bg_anim_banks.bin"):
                self.assertFalse(
                    os.path.exists(os.path.join(tmpdir, name)),
                    f"{name} was written before the ceiling refused — a later stage "
                    f"would consume it and the author would meet a section collision")

    def test_the_disabled_stub_is_always_admitted(self):
        """Master's shipping content. If the ceiling ever refuses this, every build
        of every act stops, animated or not.

        The stub is 2 B of `BgAnim_Table` plus the three declined view names' count
        words in the DEBUG shape — it exports them like every other act shape, which
        is what lets a consumer `use` them unconditionally.
        """
        self.assertEqual(inject_editor_bg.check_bganim_section_fits([]),
                         shape_aware_size([]))
        self.assertEqual(inject_editor_bg.bganim_section_bytes(0, 0), 2)
        self.assertEqual(shape_aware_size([]),
                         2 + inject_editor_bg.BGANIM_VIEW_COUNT
                         * inject_editor_bg.BGANIM_COUNT_BYTES)

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

    def test_the_ruled_ceiling_admits_two_full_size_canopy_bands(self):
        """WHY 20,480 and not some other number the owner might have said.

        The 2026-09-04 raise exists for exactly one ask: a second band the size of the
        shipped canopy. Derived from the emitter's own layout constants — if a record
        or a phase count ever grows, this fails and names the new figure, which is the
        whole point of not writing 16,654 down as a literal."""
        canopy_slots = 8 * 4          # the shipped band: cols x rows
        need_no_views = inject_editor_bg.bganim_section_bytes(2, canopy_slots * 2, 0)
        need_with_views = inject_editor_bg.bganim_section_bytes(
            2, canopy_slots * 2, inject_editor_bg.BGANIM_VIEW_COUNT)
        self.assertLessEqual(
            need_with_views, inject_editor_bg.BGANIM_SECTION_CEILING,
            f"two canopy-sized bands need {need_with_views} B and the ruled ceiling is "
            f"{inject_editor_bg.BGANIM_SECTION_CEILING} B — the raise no longer buys "
            f"what it was ruled for")
        self.assertLess(need_no_views, need_with_views,
                        "view twins are supposed to COST bytes; if they do not, "
                        "bganim_section_bytes has stopped counting them")

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
        """The ruled number in EVERY shape (the re-layout's acceptance, 2026-08-26): the
        DEBUG row is no longer derived from what a shape's room happened to hold —
        that derivation (anchor − packed end + held) was d-28-answered's one-day
        stopgap and is retired with its `_D28_*` terms. The number is typed here on
        purpose: it is the owner's ruling, the one thing this file may not derive.

        RAISED 12,288 -> 20,480 on 2026-09-04 (owner "Agrree", amending d-9) so a
        SECOND full-size band fits. This assertion is a tripwire for an UNRULED edit,
        so it moves with the ruling rather than being loosened to a range — a `>=`
        here would pass for any number anyone typed."""
        self.assertEqual(inject_editor_bg.BGANIM_SECTION_CEILING_RULED, 20480,
                         "d-9's guarantee moved — that is an owner ruling")
        self.assertEqual(inject_editor_bg.BGANIM_SECTION_CEILING, 20480)
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

    ⚠ THE CUT'S ANCHOR-SIDE ROWS ARE REBASED (2026-09-06). The cut's last row is
    `__align$games.sonic4.dac_banks$0` at 0x98000 — one SetBank window inside the
    0x90000 `dac_banks` of the layout it was cut from. Since FIXTURE_ANCHOR became
    derived (0xA0000, above), copying the cut verbatim produced a tree that declared
    [0x8A720, 0xA0000) free while its own listing put a row at 0x98000 inside it. The
    tree was internally inconsistent and nothing noticed, because nothing checked the
    terminus — which is the same defect as B7 itself, one level down. `_rebased_cut`
    moves rows at or above FIXTURE_CUT_ANCHOR (0x90000) with the tree's anchor, in
    both halves of the cut. It is a fix, not an exemption: `check_terminus` has no
    special case for `__align$` or any other name.

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
    # The `dac_banks` of the LAYOUT THE CUT WAS TAKEN FROM (the 08-26 re-layout,
    # 0x48000 -> 0x90000; see the class docstring). Rows at or above it are anchored
    # content, not packed data, and `_tree` rebases them onto whatever anchor the
    # tree declares — see "THE CUT'S ANCHOR-SIDE ROWS ARE REBASED" in the docstring.
    FIXTURE_CUT_ANCHOR = 0x90000
    #: `BgAnim_Banks - BgAnim_Table` for a one-band, non-DEBUG-view section: the
    #: u16 band count (2) plus one 44 B band record (a 12 B header and 32 B of bank
    #: pointers), per tools/inject_editor_bg.py's emitter. MEASURED in the live
    #: s4.lst at introduction — BgAnim_Table 0x2823C, BgAnim_Banks 0x2826A, delta
    #: 0x2E = 46. Used only to synthesize the head row the 08-26 cut predates.
    BGANIM_HEAD_DELTA = 2 + 44

    def _rebased_cut(self, anchor, head_lma=None, pads=()):
        """The committed cut with its ANCHOR-SIDE rows moved to `anchor`.

        The cut carries `__align$games.sonic4.dac_banks$0` at 0x98000 — one SetBank
        window inside the 0x90000 `dac_banks` of the layout it was cut from. The tree
        declares a DIFFERENT anchor (derived from the rule, 0xA0000), so copying the
        cut verbatim built a tree in which an anchored row sat 0x98000 — i.e. INSIDE
        the [packed end, anchor) region the tree simultaneously claimed was free.
        That inconsistency was invisible until `check_terminus` landed (2026-09-06)
        and refused the tree by name; it is fixed here rather than exempted, because
        an exemption would have deleted the check's whole point.

        Rebase = add `anchor - FIXTURE_CUT_ANCHOR` to every LMA at or above the cut's
        own anchor, in BOTH halves of the cut (label rows and symbol table), so the
        two halves still agree. Rows below it — Vectors, BgAnim_Banks, Map_TestObj,
        Art_Sonic — are packed data and never move.
        """
        delta = anchor - self.FIXTURE_CUT_ANCHOR
        out = []
        for line in open(self.FIXTURE, encoding="utf-8").read().splitlines():
            m = re.match(r"^(\(0\) \d+/)([0-9A-F]+)( .*)$", line)
            if not m:
                m = re.match(r"^( \S+ : )([0-9A-F]+)( [C-] \|)$", line)
            if m and int(m.group(2), 16) >= self.FIXTURE_CUT_ANCHOR:
                line = f"{m.group(1)}{int(m.group(2), 16) + delta:X}{m.group(3)}"
            out.append(line)
            # SYNTHESIZED, and labelled as such: `check_growth_path` (F7) asks where
            # the GROWING section starts, and the 08-26 cut carries only
            # `BgAnim_Banks`, a row INSIDE that section. The cut is not regenerated
            # for this — its addresses are the numeric basis of the whole class — so
            # the tree writes the head row itself, at `BgAnim_Banks` minus the
            # emitter's own one-band record (`inject_editor_bg`: a u16 count plus a
            # 12 B header and 32 B of bank pointers = 46 B, the delta MEASURED in
            # s4.lst at introduction: BgAnim_Table 0x2823C -> BgAnim_Banks 0x2826A).
            # Every other input this tree feeds the tool is synthesized the same way;
            # what must not be synthesized is the FIXTURE, and it is not.
            if line.startswith("(0)") and line.rstrip().endswith(" BgAnim_Banks:"):
                seq, rest = line[4:].split("/", 1)
                lma = int(rest.split()[0], 16)
                head = lma - self.BGANIM_HEAD_DELTA if head_lma is None else head_lma
                out.insert(len(out) - 1, f"(0) {int(seq) - 1}/{head:X} :"
                                         f"        BgAnim_Table:")
                for name, addr in pads:
                    out.insert(len(out) - 1,
                               f"(0) {int(seq) - 1}/{addr:X} :        {name}:")
            if re.match(r"^ BgAnim_Banks : [0-9A-F]+ C \|$", line):
                lma = int(line.split(":")[1].split()[0], 16)
                head = lma - self.BGANIM_HEAD_DELTA if head_lma is None else head_lma
                out.insert(len(out) - 1, f" BgAnim_Table : {head:X} C |")
                for name, addr in pads:
                    out.insert(len(out) - 1, f" {name} : {addr:X} C |")
        return "\n".join(out) + "\n"

    def _tree(self, band=(8, 4), blob_len=FIXTURE_ART_SONIC_BYTES, lst="s4.debug.lst",
              anchor=FIXTURE_ANCHOR, sound_gap=None, tail="", head_lma=None,
              pads=(), extra_pin=None, pad_modules=()):
        """A hermetic aeon-shaped tree holding only what bganim_room reads.

        `sound_gap` overrides the declared `sound_bank - dac_banks` distance (the F6
        relation); `tail` is appended to the hermetic collision_data.emp, which is how
        an F2 test perturbs the ARRANGEMENT of the section rather than the tool.
        `head_lma`, `pads`, `extra_pin` and `pad_modules` perturb the GROWTH PATH
        (F7): where the growing section starts, what alignment pads the path crosses,
        and whether the map pins an address inside it.
        """
        import shutil
        d = tempfile.mkdtemp(prefix="bganim_room_")
        self.addCleanup(shutil.rmtree, d)
        os.makedirs(os.path.join(d, "games", "sonic4", "data", "collision"))
        os.makedirs(os.path.join(d, "art"))
        for module_id, align_src in pad_modules:
            p = os.path.join(d, "games", "sonic4", "data", f"{module_id}.emp")
            with open(p, "w") as f:
                f.write(f"module {module_id} in {module_id.rsplit('.', 1)[-1]}\n"
                        f"{align_src}\n")
        with open(os.path.join(d, "games", "sonic4", "map.toml"), "w") as f:
            f.write('[[anchor]]\nname = "dac_banks"\nat = 0x%X\nwhen = "sound_on"\n\n'
                    '[[anchor]]\nname = "sound_bank"\nat = 0x%X\nwhen = "sound_on"\n'
                    % (anchor, anchor + (sound_gap if sound_gap is not None
                                         else bganim_room.SOUND_BANK_OFFSET)))
            if extra_pin is not None:
                kind, name, at = extra_pin
                f.write(f'\n[[{kind}]]\nname = "{name}"\nat = 0x{at:X}\n')
        with open(os.path.join(d, "games", "sonic4", "data", "collision",
                               "collision_data.emp"), "w") as f:
            f.write('module games.sonic4.collision_data in collision_data\n'
                    'const _art_sonic      = embed("art/sonic.bin")\n'
                    'pub data Art_Sonic     = _art_sonic\n' + tail)
        with open(os.path.join(d, "art", "sonic.bin"), "wb") as f:
            f.write(b"\0" * blob_len)
        if band:
            with open(os.path.join(d, "games", "sonic4", "data",
                                   "editor_bg_override.json"), "w") as f:
                json.dump({"anims": [{"cols": band[0], "rows": band[1],
                                      "slot_base": 0}]}, f)
        with open(os.path.join(d, lst), "w") as f:
            f.write(self._rebased_cut(anchor, head_lma=head_lma, pads=pads))
        return d, os.path.join(d, lst)

    def _rom(self, tree, name="s4.debug.bin", size=None, plant=None,
             anchor=FIXTURE_ANCHOR):
        """A hermetic ROM IMAGE for the terminus scan's second instrument.

        Zeros up to `size` (default one SetBank window past the anchor, so the banks
        the anchor names are actually IN the image), with `plant = (lma, bytes)`
        written in — the mutation a terminus test needs to make the image half fire.
        """
        path = os.path.join(tree, name)
        size = anchor + 0x8000 if size is None else size
        buf = bytearray(size)
        if plant:
            lma, payload = plant
            buf[lma:lma + len(payload)] = payload
        with open(path, "wb") as f:
            f.write(bytes(buf))
        return path

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
        # The number the GATE uses, which is the shape-aware one: this fixture's
        # document sets no `default_off`, so its three view twins decline and export
        # their names as count-0 words (BGANIM_VIEW_COUNT x BGANIM_COUNT_BYTES in the
        # DEBUG shape). Modelling them as absent is the 6 B this test used to be.
        live = inject_editor_bg.live_section_bytes(tree)
        self.assertEqual(live, 8238 + inject_editor_bg.BGANIM_VIEW_COUNT
                         * inject_editor_bg.BGANIM_COUNT_BYTES)
        packed_end = self._hand_lma() + self.FIXTURE_ART_SONIC_BYTES
        room = self.FIXTURE_ANCHOR - packed_end
        headroom = room + live
        self.assertEqual(headroom, 88288 + live)
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
        self.assertIn("BGANIM_SECTION_CEILINGS['s4.lst'] = 20480 B", text)
        headroom = (self.FIXTURE_ANCHOR - (self._hand_lma() + self.FIXTURE_ART_SONIC_BYTES)
                    + inject_editor_bg.live_section_bytes(tree))
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
        # 88,288 B of room + this fixture's own section (8,238 B of band and blob,
        # plus the three declined view names' count words in the DEBUG shape).
        self.assertEqual(headroom, 88288 + inject_editor_bg.live_section_bytes(tree))
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

    # ---- the terminus is a CHECKED FACT (B7, 2026-09-06) ------------------------

    def test_hermetic_tree_is_internally_consistent_about_its_own_free_region(self):
        """The scaffolding's own precondition, made a test because it was FALSE until
        `check_terminus` landed and refused it: no row of the tree's listing may sit
        in the region the tree declares free, and the rebase must have moved the
        anchor-side row rather than deleted it."""
        import bganim_room
        for anchor in (self.FIXTURE_ANCHOR, self.FIXTURE_ANCHOR + 0x8000, 0x8C000):
            tree, lst = self._tree(anchor=anchor)
            labels = bganim_room.lst_labels(lst)
            # 5 cut rows + the one SYNTHESIZED head row (`BgAnim_Table`, see
            # `_rebased_cut`), derived from the fixture's own count rather than
            # typed, so a change to either side has to be deliberate.
            self.assertEqual(
                len(labels), len(bganim_room.lst_labels(self.FIXTURE)) + 1,
                "the rebase dropped or duplicated a row")
            self.assertEqual(len(labels), 6)
            self.assertEqual(labels["BgAnim_Table"],
                             labels["BgAnim_Banks"] - self.BGANIM_HEAD_DELTA)
            packed_end = self._hand_lma() + self.FIXTURE_ART_SONIC_BYTES
            self.assertEqual(
                bganim_room.labels_in(labels, packed_end, anchor), [],
                f"the hermetic tree with anchor 0x{anchor:X} puts a row inside the "
                f"region it calls free — the tree is lying to the tool it tests")
            self.assertEqual(labels["__align$games.sonic4.dac_banks$0"],
                             anchor + 0x8000, "the anchor-side row did not track")
            for below in ("Vectors", "BgAnim_Banks", "Map_TestObj", "Art_Sonic"):
                self.assertEqual(labels[below],
                                 bganim_room.lst_labels(self.FIXTURE)[below],
                                 f"{below} is packed data and must never be rebased")

    def test_a_symbol_between_the_terminus_and_the_anchor_refuses_a_room_figure(self):
        """RED-FIRST for the symbol half. Plant one label in [packed end, anchor) —
        the exact thing B7 says nothing checked — and the tool must refuse, NAME it,
        and print no room number. Before this check the same tree reported
        88,288 B free and both gates went green over it."""
        import bganim_room
        tree, lst = self._tree()
        packed_end = self._hand_lma() + self.FIXTURE_ART_SONIC_BYTES
        intruder = packed_end + 0x1000
        rows = open(lst, encoding="utf-8").read().splitlines()
        i = next(i for i, r in enumerate(rows) if r.endswith(" Art_Sonic:"))
        rows.insert(i + 1, f"(0) 2266/{intruder:X} :        Art_LatecomerBlob:")
        with open(lst, "w") as f:
            f.write("\n".join(rows) + "\n")
        # the pre-check derivation is unchanged — the room WOULD still be 88,288
        self.assertEqual(self.FIXTURE_ANCHOR - packed_end, 88288)
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.rom_room(lst, tree)
        msg = str(cm.exception)
        self.assertIn("Art_Sonic is NOT the last packed data", msg)
        self.assertIn(f"0x{intruder:X}  Art_LatecomerBlob", msg)
        self.assertIn("+4096 B above the terminus", msg)
        self.assertIn("NO ROOM FIGURE IS REPORTED", msg)
        self.assertIn("do NOT widen the assertion", msg)
        # and the report/CLI refuse the same way, WITHOUT --gate: a broken terminus
        # is not a budget verdict, it is "the number would be wrong".
        import io
        import contextlib
        # `main()` has no tree argument and reads module-level AEON, so it must be
        # pointed at the hermetic tree or it silently derives the LENGTH term from the
        # LIVE repo while deriving the terminus from this fixture. (Measured
        # 2026-09-06: without this the CLI half reported the live tree's
        # collision_data.emp — a true statement about the wrong subject, which is the
        # exact failure mode the module header warns about for listings.)
        saved_aeon = bganim_room.AEON
        bganim_room.AEON = tree
        self.addCleanup(setattr, bganim_room, "AEON", saved_aeon)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = bganim_room.main(["--lst", lst])
        bganim_room.AEON = saved_aeon
        self.assertEqual(rc, 1)
        self.assertIn("FAIL (unmeasurable)", err.getvalue())
        self.assertIn("Art_LatecomerBlob", err.getvalue())
        self.assertNotIn("ROM room", err.getvalue())
        # a label AT the terminus is caught too, and named as such
        rows[i + 1] = f"(0) 2266/{packed_end:X} :        Art_EndMarker:"
        with open(lst, "w") as f:
            f.write("\n".join(rows) + "\n")
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.rom_room(lst, tree)
        self.assertIn("(AT the terminus)", str(cm.exception))

    def test_unlabelled_bytes_in_the_free_region_refuse_a_room_figure(self):
        """RED-FIRST for the IMAGE half — the one the symbol listing cannot do. A blob
        with no exported symbol is invisible to the `.lst`, so only the ROM scan can
        see it; without `--rom` the same tree passes, which is exactly why build.sh's
        gate passes the ROM."""
        import bganim_room
        tree, lst = self._tree()
        packed_end = self._hand_lma() + self.FIXTURE_ART_SONIC_BYTES
        at = packed_end + 0x40
        clean = self._rom(tree)
        self.assertEqual(bganim_room.rom_room(lst, tree, rom_path=clean)["room"], 88288)
        dirty = self._rom(tree, name="dirty.bin", plant=(at, b"\xDE\xAD\xBE\xEF"))
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.rom_room(lst, tree, rom_path=dirty)
        msg = str(cm.exception)
        self.assertIn("holds 4 non-zero bytes", msg)
        self.assertIn(f"the first at 0x{at:X}", msg)
        self.assertIn("exports NO label there", msg)
        self.assertIn("NO ROOM FIGURE IS REPORTED", msg)
        # THE POINT: the symbol half alone cannot see this. Same tree, no --rom, green.
        self.assertEqual(bganim_room.rom_room(lst, tree)["room"], 88288)

    def test_a_rom_that_stops_short_of_its_own_anchor_is_unmeasurable(self):
        """A truncated image cannot witness the region, and 'bytes that are not there'
        must never read as 'bytes that are free'."""
        import bganim_room
        tree, lst = self._tree()
        packed_end = self._hand_lma() + self.FIXTURE_ART_SONIC_BYTES
        short = self._rom(tree, name="short.bin", size=self.FIXTURE_ANCHOR - 0x100)
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.rom_room(lst, tree, rom_path=short)
        self.assertIn("ends 256 B before the `dac_banks` anchor", str(cm.exception))
        # An image that cannot even hold Art_Sonic is refused EARLIER, by the extent
        # check, with the more specific message — `packed_end == lma + blob_len`, so
        # through rom_room the extent arm always reaches a truncation first.
        tiny = self._rom(tree, name="tiny.bin", size=packed_end - 1)
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.rom_room(lst, tree, rom_path=tiny)
        self.assertIn("cannot hold Art_Sonic's 97472 B at 0x72A60", str(cm.exception))
        # `image_occupancy`'s own `size < lo` guard is therefore not reachable through
        # rom_room; it is a helper-level guard and is exercised as one, so it is not
        # left as an arm that cannot fire.
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.image_occupancy(tiny, packed_end, self.FIXTURE_ANCHOR)
        self.assertIn("ends BELOW the packed terminus", str(cm.exception))
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.rom_room(lst, tree, rom_path=os.path.join(tree, "absent.bin"))
        self.assertIn("extent: no ROM image at", str(cm.exception))

    def test_report_says_which_instruments_established_the_terminus(self):
        """A green must state what it PROVED. With --rom both instruments are named
        and the scanned byte count is the room; without it the report says out loud
        that unlabelled bytes were not ruled out."""
        tree, lst = self._tree()
        rom = self._rom(tree)
        rc, text = self._report(tree, lst, rom_path=rom)
        self.assertEqual(rc, 0, text)
        self.assertRegex(text, r"(?m)^\s*terminus: CHECKED by both instruments — no label "
                               r"lies between 0x8A720 and the anchor, and all 88288 B of "
                               r"that region are zero in s4\.debug\.bin$", text)
        rc, text = self._report(tree, lst)
        self.assertEqual(rc, 0, text)
        self.assertIn("terminus: CHECKED by symbols only", text)
        self.assertIn("The ROM image half did NOT run (no --rom), so unlabelled bytes "
                      "there were not ruled out.", text)

    # ---- the LENGTH term is checked too (F2, the other half of the expression) ---

    def test_a_definition_after_art_sonic_refuses_a_room_figure(self):
        """RED-FIRST for F2 (a), and the perturbation is of the ARRANGEMENT: the
        section is given a SECOND emitting definition after Art_Sonic, exactly what
        map.toml's ordering exists to prevent ("a section with several embeds has no
        such instrument"). `packed_end` then stops short of the section's real end.

        ⚠ THIS IS THE CASE NEITHER OCCUPANCY INSTRUMENT CAN SEE. The trailing
        definition here is zero-filled, so the image scan finds the region clean, and
        the hermetic listing exports no row for it, so the symbol scan finds nothing.
        The asserted-below fact is that `check_terminus` alone STAYS GREEN on this
        tree — which is why F2 needed its own assertion and not a claim that F1
        already covered it."""
        import bganim_room
        tail = ('const _pad_blob       = embed("art/pad.bin")\n'
                'pub data Art_Trailer   = _pad_blob\n')
        tree, lst = self._tree(tail=tail)
        with open(os.path.join(tree, "art", "pad.bin"), "wb") as f:
            f.write(b"\0" * 0x400)
        rom = self._rom(tree)
        # F1 alone is BLIND here: unlabelled and zero, so both its instruments pass.
        labels = bganim_room.lst_labels(lst)
        packed_end = self._hand_lma() + self.FIXTURE_ART_SONIC_BYTES
        self.assertEqual(
            bganim_room.check_terminus(lst, labels, packed_end, self.FIXTURE_ANCHOR,
                                       rom)["intruders"], [],
            "the terminus check saw the trailing definition — if it can, this test is "
            "no longer proving that F2 needs its own assertion")
        # F2 refuses, and names what trails.
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.rom_room(lst, tree, rom_path=rom)
        msg = str(cm.exception)
        self.assertIn("Art_Sonic is NOT the last thing", msg)
        self.assertIn("'Art_Trailer' is", msg)
        self.assertIn("['Art_Trailer']", msg)
        self.assertIn("too LARGE", msg)
        self.assertIn("Do NOT widen this", msg)

    def test_art_sonic_bound_other_than_whole_refuses_a_room_figure(self):
        """RED-FIRST for F2 (a), second arm: the definition still ends the section but
        no longer binds the embed WHOLE, so its ROM extent is not `blob_len`."""
        import bganim_room
        tree, lst = self._tree()
        emp = os.path.join(tree, "games", "sonic4", "data", "collision",
                           "collision_data.emp")
        src = open(emp, encoding="utf-8").read()
        with open(emp, "w") as f:
            f.write(src.replace("= _art_sonic\n", "= _art_sonic ++ [0; 64]\n"))
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.rom_room(lst, tree, rom_path=self._rom(tree))
        msg = str(cm.exception)
        self.assertIn("no longer binds the embed WHOLE", msg)
        self.assertIn("_art_sonic ++ [0; 64]", msg)

    def test_a_second_module_in_the_section_refuses_a_room_figure(self):
        """RED-FIRST for F2 (b): a sibling module placed in the same section can emit
        after Art_Sonic with no label, which is the invisible case again."""
        import bganim_room
        tree, lst = self._tree()
        extra = os.path.join(tree, "games", "sonic4", "data", "collision", "extra.emp")
        with open(extra, "w") as f:
            f.write("module games.sonic4.latecomer in collision_data\n"
                    "pub data Latecomer = [0; 256]\n")
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.rom_room(lst, tree, rom_path=self._rom(tree))
        msg = str(cm.exception)
        self.assertIn("section 'collision_data' is no longer emitted by", msg)
        self.assertIn("extra.emp", msg)
        self.assertIn("NEITHER occupancy instrument can see it", msg)

    def test_the_cancelling_pair_that_leaves_end_unchanged_is_still_caught(self):
        """THE CANCELLATION TRAP, made a test. `end = LMA + blob_len` has two
        independent ways to be wrong and they can cancel: move the label DOWN by K and
        grow the blob by K and `end` — and therefore `room`, and therefore both gates'
        verdicts — is bit-for-bit what it was. The old arithmetic could not have
        distinguished this tree from a correct one, and agreement between runs was
        never evidence about either arm.

        Each arm is varied ALONE first, so the pass below is not the sum of two
        errors: (1) LMA down by K with the blob unchanged, (2) blob up by K with the
        LMA unchanged, (3) both together. All three must be refused, and (3) must be
        refused for a reason that is about a byte, not about the total."""
        import bganim_room
        K = 0x400
        base_lma = self._hand_lma()
        base_len = self.FIXTURE_ART_SONIC_BYTES

        FILL = b"\xA5"

        def tree_with(lma, blob_len):
            """A tree whose LISTING says `lma`, whose BLOB is `blob_len` long, and
            whose ROM is the UNPERTURBED artifact: the original `base_len` bytes of
            content at `base_lma`. The ROM is the fixed point the two source terms
            are varied against, which is what keeps the arms independent — perturbing
            the ROM alongside them is how the two errors would cancel again."""
            tree, lst = self._tree(blob_len=blob_len)
            with open(os.path.join(tree, "art", "sonic.bin"), "wb") as f:
                f.write(FILL * blob_len)
            rows = open(lst, encoding="utf-8").read().splitlines()
            rows = [re.sub(r"/[0-9A-F]+ ", f"/{lma:X} ", r)
                    if r.endswith(" Art_Sonic:") else r for r in rows]
            with open(lst, "w") as f:
                f.write("\n".join(rows) + "\n")
            rom = self._rom(tree, plant=(base_lma, FILL * base_len))
            return tree, lst, rom

        # (0) THE CONTROL, established FIRST: nothing perturbed, and a room figure
        # exists. Without this the refusals below could be the tree being malformed.
        tree, lst, rom = tree_with(base_lma, base_len)
        self.assertEqual(bganim_room.rom_room(lst, tree, rom_path=rom)["room"], 88288)

        # (1) LMA ARM ALONE: the listing's label moved down K; the blob is untouched.
        # `end` moves DOWN by K, so the old arithmetic would have reported K MORE room.
        tree, lst, rom = tree_with(base_lma - K, base_len)
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.rom_room(lst, tree, rom_path=rom)
        arm1 = str(cm.exception)
        self.assertIn("are NOT art/sonic.bin", arm1)
        self.assertIn(f"they first differ 0 B in, at 0x{base_lma - K:X}", arm1)

        # (2) LENGTH ARM ALONE: the blob on disk grew by K; the label is untouched
        # (the artifact was not rebuilt). `end` moves UP by K.
        tree, lst, rom = tree_with(base_lma, base_len + K)
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.rom_room(lst, tree, rom_path=rom)
        arm2 = str(cm.exception)
        self.assertIn("are NOT art/sonic.bin", arm2)
        self.assertIn(f"they first differ {base_len} B in, at 0x{base_lma + base_len:X}",
                      arm2)

        # (3) BOTH AT ONCE: `end` — and therefore `room`, and therefore both gates'
        # verdicts — is bit-for-bit the control's. This is the tree the old derivation
        # could not have told apart from a correct one.
        tree, lst, rom = tree_with(base_lma - K, base_len + K)
        self.assertEqual((base_lma - K) + (base_len + K), base_lma + base_len,
                         "the perturbation does not actually cancel")
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.rom_room(lst, tree, rom_path=rom)
        arm3 = str(cm.exception)
        self.assertIn("are NOT art/sonic.bin", arm3)
        self.assertIn(f"at 0x{base_lma - K:X}", arm3)
        # Each arm is refused for its OWN reason, at its OWN byte — the three are not
        # one statement repeated, which is what "varied independently" has to mean.
        self.assertNotEqual(arm1, arm2)
        self.assertNotEqual(arm2, arm3)
        # And the thing the old derivation compared is IDENTICAL across (0) and (3):
        # agreement on `end` was never evidence about either arm.
        self.assertEqual(base_lma + base_len, (base_lma - K) + (base_len + K))

    def test_image_identity_is_a_measurement_not_a_restatement(self):
        """RED-FIRST for F2 (c): the blob on disk and the bytes at the label diverge
        by ONE byte, with every length and address unchanged. Nothing in the old
        derivation could see this, because it only ever read `os.path.getsize`."""
        import bganim_room
        tree, lst = self._tree()
        lma = self._hand_lma()
        with open(os.path.join(tree, "art", "sonic.bin"), "wb") as f:
            f.write(b"\x11" * self.FIXTURE_ART_SONIC_BYTES)
        good = self._rom(tree, plant=(lma, b"\x11" * self.FIXTURE_ART_SONIC_BYTES))
        self.assertEqual(bganim_room.rom_room(lst, tree, rom_path=good)["room"], 88288)
        payload = bytearray(b"\x11" * self.FIXTURE_ART_SONIC_BYTES)
        payload[500] = 0x12
        bad = self._rom(tree, name="bad.bin", plant=(lma, bytes(payload)))
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.rom_room(lst, tree, rom_path=bad)
        self.assertIn(f"first differ 500 B in, at 0x{lma + 500:X}", str(cm.exception))
        # and the SIZE-only derivation is unchanged by the mutation, which is the point
        self.assertEqual(os.path.getsize(os.path.join(tree, "art", "sonic.bin")),
                         self.FIXTURE_ART_SONIC_BYTES)

    def test_report_states_what_the_extent_check_proved(self):
        tree, lst = self._tree()
        rc, text = self._report(tree, lst, rom_path=self._rom(tree))
        self.assertEqual(rc, 0, text)
        self.assertIn("extent: CHECKED — Art_Sonic is the last of 1 definitions in "
                      "section 'collision_data' (sole module), binds its embed whole, "
                      "and its 97472 B in s4.debug.bin are byte-identical to "
                      "art/sonic.bin", text)
        rc, text = self._report(tree, lst)
        self.assertEqual(rc, 0, text)
        self.assertIn("the byte-identity half did NOT run (no --rom), so `+ 97472` is a "
                      "restatement of the file's size here, not a measurement", text)

    # ---- F6: the two bank anchors are compared, not just printed ----------------

    def test_the_two_bank_anchors_are_compared_against_the_encoded_offset(self):
        """RED-FIRST for F6: SOUND_BANK_OFFSET encoded `sound_bank == dac_banks +
        0x10000` and appeared only in its definition and in a remedy f-string, so the
        map could drift from it silently. The perturbation is of the MAP."""
        import bganim_room
        tree, lst = self._tree()
        rc, text = self._report(tree, lst)
        self.assertEqual(rc, 0, text)
        self.assertIn(f"anchor pair: `sound_bank` 0x{self.FIXTURE_ANCHOR + 0x10000:X} = "
                      f"`dac_banks` 0x{self.FIXTURE_ANCHOR:X} + SOUND_BANK_OFFSET "
                      f"0x10000, as the rule encodes", text)
        tree, lst = self._tree(sound_gap=bganim_room.SOUND_BANK_OFFSET + 0x8000)
        rc, text = self._report(tree, lst)
        self.assertEqual(rc, 1, text)
        self.assertIn("the two bank anchors have drifted apart", text)
        self.assertIn("a gap of 0x18000, but SOUND_BANK_OFFSET encodes 0x10000 "
                      "(2 SetBank windows", text)
        self.assertIn("makes the remedy wrong as well as the constant", text)
        # without --gate it is reported, not enforced — same shape as the other arms
        import io
        buf = io.StringIO()
        self.assertEqual(bganim_room.report(lst, tree, gate=False, out=buf), 0)
        self.assertIn("drifted apart", buf.getvalue())

    def test_the_live_map_satisfies_the_encoded_anchor_relation(self):
        """The live map, not a hermetic one: this is the fact F6 says was never
        compared. It is derived from the map with the tool's own parser and from the
        constant, never typed."""
        import bganim_room
        live = os.path.join(self.AEON, "games", "sonic4", "map.toml")
        dac = bganim_room.anchor_addr(live, "dac_banks")
        snd = bganim_room.anchor_addr(live, "sound_bank")
        self.assertEqual(snd, dac + bganim_room.SOUND_BANK_OFFSET,
                         f"games/sonic4/map.toml declares dac_banks 0x{dac:X} and "
                         f"sound_bank 0x{snd:X}, a gap of 0x{snd - dac:X}, but "
                         f"SOUND_BANK_OFFSET is 0x{bganim_room.SOUND_BANK_OFFSET:X}")

    # ---- F7: the ORDERING PREMISE the room figure rests on -----------------------

    def test_the_growth_path_is_reported_as_checked_on_a_sound_tree(self):
        """A green must state what it proved. The premise — the growing section is
        upstream, and nothing between it and the anchor is pinned — was asserted in
        the module header as a plain fact and checked by nothing."""
        tree, lst = self._tree()
        rc, text = self._report(tree, lst)
        self.assertEqual(rc, 0, text)
        self.assertIn("growth path: CHECKED", text)
        self.assertIn("is upstream of the terminus", text)
        self.assertIn("the map pins no address between it and the anchor", text)
        self.assertIn("crosses no alignment pad", text)

    def test_a_growing_section_at_or_above_the_terminus_refuses_a_figure(self):
        """RED-FIRST arm (1). `room = anchor - packed_end` is offered as room for
        `ojz_bg_anim`; if that section is not UPSTREAM of the terminus its growth
        does not consume this room at all, and the figure is about other ROM. The
        subtraction is unchanged and still looks healthy — which is the point.

        THE HEAD IS PUT ABOVE THE ANCHOR, and that is not an arbitrary choice: it is
        the half of arm (1) `check_terminus` structurally CANNOT reach. Terminus
        scans [packed_end, anchor), so a section landing anywhere inside that window
        is refused there first (asserted below, so the division of labour is on the
        record rather than assumed); a section placed PAST the anchor — beyond the
        Z80 banks, where the ROM tail sections live — is invisible to it and only
        this arm sees it."""
        import bganim_room
        end = self._hand_lma() + self.FIXTURE_ART_SONIC_BYTES
        tree, lst = self._tree(head_lma=self.FIXTURE_ANCHOR + 0x1000)
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.rom_room(lst, tree)
        msg = str(cm.exception)
        self.assertIn("at or ABOVE the packed-data end", msg)
        self.assertIn(f"0x{end:X}", msg)
        # The other half of the window: terminus owns it, and says so by name.
        tree, lst = self._tree(head_lma=end + 0x10)
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.rom_room(lst, tree)
        self.assertIn("is NOT the last packed data", str(cm.exception))

    def test_an_address_pinned_inside_the_growth_path_refuses_a_figure(self):
        """RED-FIRST arm (2). Everything between the growing section and the anchor
        has to FLOAT downstream for growth to turn into consumed room. A declared
        anchor inside that span pins a section: growth collides at the pin, so the
        room reported against the anchor is not the limit. The map is what changes;
        the listing, the blob and the arithmetic are untouched."""
        import bganim_room
        pin = self.FIXTURE_ANCHOR - 0x4000
        tree, lst = self._tree(extra_pin=("anchor", "some_new_island", pin))
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.rom_room(lst, tree)
        msg = str(cm.exception)
        self.assertIn("declared address(es) sit between", msg)
        self.assertIn(f"0x{pin:X} [[anchor]] some_new_island", msg)
        self.assertIn("would collide at the pin, not at the anchor", msg)

    def test_a_hole_pinned_inside_the_growth_path_is_caught_the_same_way(self):
        """`[[hole]]` fixes an address exactly as `[[anchor]]` does. A check that
        knew only about anchors would pass this and be wrong in the same direction."""
        import bganim_room
        pin = self.FIXTURE_ANCHOR - 0x2000
        tree, lst = self._tree(extra_pin=("hole", "ignored", pin))
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.rom_room(lst, tree)
        self.assertIn(f"0x{pin:X} [[hole]]", str(cm.exception))

    def test_a_pin_outside_the_path_does_not_fire(self):
        """The control. `sound_bank` sits ABOVE `dac_banks` on every real map and
        must not be read as an obstruction; a check that fired on it would be
        disabled the first week. Below the growing section is equally outside."""
        head = self._hand_lma()  # far above BgAnim_Table, but below the terminus
        tree, lst = self._tree(extra_pin=("anchor", "below_the_path", 0x1000))
        rc, text = self._report(tree, lst)
        self.assertEqual(rc, 0, text)
        self.assertIn("growth path: CHECKED", text)
        self.assertLess(0x1000, head)

    def test_alignment_slop_is_measured_from_the_module_and_shrinks_the_headroom(self):
        """Arm (3): growth of K does not shift the terminus by exactly K when the
        path crosses `align` directives — each can add up to N-1 on top. The quantum
        is READ from the module that emitted the pad, so a tree with `align 16` gets
        15 B of slop and one with `align 2` gets 1, off the same listing shape."""
        import bganim_room
        banks = bganim_room.lst_labels(self.FIXTURE)["BgAnim_Banks"]
        for quantum, want_slop in ((2, 1), (16, 15)):
            tree, lst = self._tree(
                pads=[("__align$games.sonic4.padmod$0", banks + 0x10)],
                pad_modules=[("games.sonic4.padmod", f"align {quantum}")])
            r = bganim_room.rom_room(lst, tree)
            self.assertEqual(r["growth"]["slop"], want_slop)
            self.assertEqual(r["growth"]["pads"][0][2], quantum)
            rc, text = self._report(tree, lst)
            self.assertEqual(rc, 0, text)
            self.assertIn(f"(align {quantum})", text)
            self.assertIn(f"can cost up to K+{want_slop} B", text)
            # and the headroom the ceiling is compared against is REDUCED by it
            from inject_editor_bg import live_section_bytes
            self.assertIn(f"- {want_slop} B alignment slop = "
                          f"{r['room'] + live_section_bytes(tree) - want_slop} B", text)

    def test_a_pad_whose_module_cannot_be_found_is_unmeasurable_not_zero(self):
        """Loud on unmeasurable. An unresolvable pad has an UNKNOWN quantum, so the
        headroom is unbounded above; reporting it as slop 0 would be the flattering
        answer and would restore exactly the silence this arm removes."""
        import bganim_room
        banks = bganim_room.lst_labels(self.FIXTURE)["BgAnim_Banks"]
        tree, lst = self._tree(pads=[("__align$games.sonic4.nosuch$0", banks + 0x10)])
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.rom_room(lst, tree)
        self.assertIn("no `.emp` under engine/ or games/ declares", str(cm.exception))

    def test_a_map_this_parser_cannot_read_yields_no_addresses_and_says_so(self):
        """`declared_addresses` returning an empty set would report every growth
        path clear — the vacuous-green shape. It refuses instead."""
        import bganim_room
        tree, _lst = self._tree()
        empty = os.path.join(tree, "empty.toml")
        with open(empty, "w") as f:
            f.write("# no anchors, no holes\n")
        with self.assertRaises(bganim_room.Unmeasurable) as cm:
            bganim_room.declared_addresses(empty)
        self.assertIn("ZERO declared addresses", str(cm.exception))

    @pytest.mark.needs_build("s4.lst")
    def test_the_live_tree_growth_path_is_sound_and_its_pads_are_real(self):
        """The live listing, not a hermetic one. Skipped when no build is present —
        this class is otherwise hermetic on purpose — but when s4.lst is here it is
        the only place the REAL six `align 2` pads are measured.

        MARKED needs_build (LS-1): it reads the tree's own `s4.lst`, so build.sh's
        PRE-build lane deselects it and the POST-sigil lane runs it against the
        listing that invocation emitted. Without the marker its skip-when-absent is
        invisible, and its FAIL-when-stale lands in the lane that runs before the
        build that would refresh it. Absent listing => DEFERRED, never silent."""
        import bganim_room
        lst = os.path.join(self.AEON, "s4.lst")
        if not os.path.isfile(lst):
            self.skipTest("no s4.lst in the tree (this class is otherwise hermetic)")
        r = bganim_room.rom_room(lst, self.AEON)
        g = r["growth"]
        self.assertLess(g["head"], r["packed_end"])
        self.assertTrue(g["pads"], "the live run crosses pads; zero would mean the "
                                   "parser stopped seeing them")
        self.assertEqual(g["slop"], sum(q - 1 for _n, _a, q in g["pads"]))

    def test_build_sh_post_sigil_gate_passes_the_rom_so_both_halves_run(self):
        """The runner wiring, derived from build.sh's own text rather than assumed:
        the post-sigil gate invokes this tool with --lst AND --rom, so the image half
        of the terminus check runs on every canonical build."""
        build_sh = open(os.path.join(self.AEON, "build.sh"), encoding="utf-8").read()
        m = re.search(r"python3 \"\$\{TOOLS\}/bganim_room\.py\"(.*?)--gate", build_sh,
                      re.S)
        self.assertIsNotNone(m, "build.sh no longer invokes bganim_room.py with --gate")
        invocation = m.group(1)
        self.assertIn("--lst", invocation)
        self.assertIn("--rom", invocation, "build.sh's gate stopped passing --rom: the "
                                           "terminus image half would silently stop "
                                           "running and only the symbol half would gate")

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
        # A REAL-SHAPED image, not a 1-byte stub: since 2026-09-06 `report` hands the
        # ROM to the terminus check's image half, and a stub that stops below the
        # packed terminus is (correctly) refused there before provenance is reached.
        rom = self._rom(tree)
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
        rom = self._rom(tree)
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
        bands = [{"cols": 32, "rows": 4, "slot_base": 0},
                 {"cols": 16, "rows": 4, "slot_base": 128}]
        facts = {"bands": 2, "slots": 192,
                 "ceiling": inject_editor_bg.BGANIM_SECTION_CEILING,
                 "size": shape_aware_size(bands)}
        self.assertEqual(refusal_shortfalls(msg, facts), [], msg)

    def test_an_8kb_class_band_is_accepted_under_the_section_ceiling(self):
        """aurora's 8x4 band: 2 + 44 + 32x256 = 8,238 B. It was REFUSED by the
        placer ceiling (1,026 B); under the only remaining ceiling it is accepted."""
        self.assertEqual(inject_editor_bg.bganim_section_bytes(1, 32), 8238)
        band = [{"cols": 8, "rows": 4, "slot_base": 0}]
        size = shape_aware_size(band)      # + the declined view names' count words
        self.assertLessEqual(size, inject_editor_bg.BGANIM_SECTION_CEILING,
                             "the ruled ceiling no longer admits an 8 KB band — that is "
                             "an owner ruling change, not something this test hides")
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


class TestBgAnimDefaultOffDecouple(unittest.TestCase):
    """`default_off` is a per-band SHIP decision; the DEBUG twins are a separate gate.

    THE DEFECT THIS CLASS EXISTS FOR, measured 2026-09-06 and booked in
    docs/DEFERRED_WORK.md ("AURORA'S `Promote` CAN ALREADY BREAK OUR BUILD, TODAY"):
    `views_emitted` raised an `AssertionError` whenever ANY band carried `default_off`
    and the act had more than one band. The shipped act is one band carrying
    `default_off`, and Aurora's editor ships a `Promote` control that adds a band — so
    an author did the one thing the editor invites and got a build failure about DEBUG
    view twins they had never heard of and did not touch. The refusal was correct when
    written (the only writer was a hand-edited file); Aurora's control changed the
    POPULATION of writers and nothing here noticed.

    THE RULING (hub in the owner's place, 2026-09-06, overturnable): **decouple.** The
    twins keep their own condition — exactly one band, `pattern_px` 64 — and
    `default_off` ships independently of whether that condition holds.

    WHY A NOTE AND NOT A SILENT ZERO. The rejected repair was "return 0 twins instead of
    raising", disqualified because it removes the owner's own perspective-versus-timer
    comparison from any act an author grows, unannounced. So the twins' absence is
    ANNOUNCED twice: on stdout as the build step runs, and as a comment block in the
    generated `bg_anim.emp` itself — scrollback is ephemeral, the artifact is what a
    reviewer opens when asking where the views went, and a comment costs zero ROM bytes.
    `test_the_note_matcher_rejects_a_stripped_note` keeps the matcher honest, so a green
    here cannot mean the gate stopped looking.
    """

    AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # ---- fixtures --------------------------------------------------------------

    @staticmethod
    def _doc(spec, cols=8, rows=4):
        """A COHERENT synthetic document: `spec` is [(slot_base, default_off), ...].

        Coherent matters — `validate_band_coherence` runs ahead of emission and
        demands `phases[0]` BE the static tiles the band covers, so a band built out
        of zeros gets rejected before it ever reaches the code under test (measured:
        that is exactly what a first draft of this fixture did).
        """
        n = cols * rows
        tiles = [[(i * 7 + p) % 16 for p in range(64)] for i in range(n * len(spec))]
        anims = []
        for slot_base, off in spec:
            ph0 = [tiles[slot_base + k] for k in range(n)]
            phases = [ph0] + [[[(v + ph) % 16 for v in t] for t in ph0]
                              for ph in range(1, 8)]
            band = {"cols": cols, "rows": rows, "pattern_px": cols * 8,
                    "driver": "camera_x", "rate_shift": 4,
                    "slot_base": slot_base, "phases": phases}
            if off:
                band["default_off"] = True
            anims.append(band)
        return {"layout": [0] * 4096, "tiles": tiles, "anims": anims}

    @staticmethod
    def _table_count(emp):
        """The band count word the emitter wrote, read out of the emitted text."""
        for line in emp.splitlines():
            if line.startswith("pub data BgAnim_Table:"):
                return int(line.split("=", 1)[1].split("//")[0].strip())
        raise AssertionError("emitted module has no BgAnim_Table declaration")

    #: What the twins' declined note must carry to be actionable. Derived from the
    #: ruling's own grounds: a reader must learn WHICH capability is absent, WHY
    #: (the twins' condition), what this act actually is, that `default_off` still
    #: ships, and what to do about it.
    NOTE_REQUIREMENTS = {
        "names the twins": lambda s: "BgAnim_View_H" in s,
        "names the single-band condition": lambda s: "one band" in s.lower(),
        "names the derived period": lambda s: "64" in s,
        "says default_off still ships": lambda s: "default_off" in s and "ship" in s.lower(),
        "names a remedy": lambda s: "BGANIM_VIEWS" in s or "single" in s.lower(),
    }

    def _note_shortfalls(self, note):
        return sorted(k for k, ok in self.NOTE_REQUIREMENTS.items() if not ok(note or ""))

    # ---- the matcher is itself under test --------------------------------------

    def test_the_note_matcher_rejects_a_stripped_note(self):
        """A green below must not be reachable by a note that says nothing."""
        self.assertNotEqual(
            self._note_shortfalls("no view twins for this act."), [],
            "the note matcher accepts a bare sentence — it would pass a note that "
            "tells an author nothing, which is the silence this parcel exists to avoid")

    def test_the_note_matcher_rejects_absence(self):
        self.assertNotEqual(self._note_shortfalls(None), [])

    # ---- the ruling: `default_off` no longer vetoes a multi-band act ------------

    def test_a_promoted_second_band_does_not_raise(self):
        """THE DEFECT, in its measured shape: band 0 `default_off`, band 1 promoted."""
        anims = self._doc([(0, True), (32, False)])["anims"]
        self.assertEqual(
            inject_editor_bg.views_emitted(anims), 0,
            "a multi-band act must emit no twins — the twins' condition is unmet")

    def test_every_default_off_arrangement_of_a_two_band_act_emits(self):
        """All four arrangements, enumerated rather than sampled.

        The historical refusal fired on `any(default_off) and len(anims) != 1`, so it
        caught three of these four; the fourth (no key at all) was always fine and is
        here as the control that says the fixture and the emitter agree at baseline.
        """
        for spec, expect_live in [([(0, False), (32, False)], 2),
                                  ([(0, True), (32, False)], 1),
                                  ([(0, False), (32, True)], 1),
                                  ([(0, True), (32, True)], 0)]:
            with self.subTest(spec=[o for _, o in spec]):
                emp, _ = emit_over_document(self._doc(spec))
                self.assertEqual(
                    self._table_count(emp), expect_live,
                    "BgAnim_Table must count exactly the bands NOT marked default_off")
                # The BAND, not the name. The declined note NAMES the twins on
                # purpose, so `"BgAnim_View_H" not in emp` would fail on a correct
                # emission (measured — it did); and since 2026-09-06 the three `pub
                # data` names are exported by EVERY act shape, because a consumer's
                # unconditional `use` cannot follow the document (see
                # TestBgAnimViewNamesAreShapeInvariant). What a two-band act must not
                # have is a twin RECORD — that is what the twins' condition decides.
                self.assertNotIn(
                    "_BgAnim_ViewH0_hdr", emp,
                    "a two-band act must not emit twin BANDS: their condition is one "
                    "band")
                self.assertIn(
                    "pub data BgAnim_View_H: [u16; BGANIM_VIEW_EMIT] = "
                    "if DEBUG == 1 { [0] }", emp,
                    "a declining act must still EXPORT the name, as a count-0 table — "
                    "ojz_scroll_test.emp imports it unconditionally in every shape")

    def test_the_marked_band_is_the_one_excluded_not_merely_the_count(self):
        """A correct count word reached by emitting the WRONG record is not correct.

        The count word says how many of the records FOLLOWING it the engine walks, so
        `count = 1` over a table whose first record is the default-off band silently
        disables the LIVE band instead. Read the first record's rate_shift back to
        prove which band the engine would actually walk.
        """
        doc = self._doc([(0, True), (32, False)])
        doc["anims"][1]["rate_shift"] = 5          # the live band, distinguishable
        emp, _ = emit_over_document(doc)
        self.assertEqual(self._table_count(emp), 1)
        first = next(l for l in emp.splitlines() if "_hdr:" in l)
        self.assertIn(", 5, ", first,
                      f"the first emitted record is not the live band: {first!r}")

    # ---- the twins keep their own condition, and say so when it is unmet --------

    def test_the_single_band_act_still_gets_its_three_twins(self):
        """The ruling decouples; it does not relax the twins' own condition."""
        anims = self._doc([(0, True)])["anims"]
        self.assertEqual(inject_editor_bg.views_emitted(anims),
                         inject_editor_bg.BGANIM_VIEW_COUNT)
        emp, _ = emit_over_document(self._doc([(0, True)]))
        for view in ("BgAnim_View_H", "BgAnim_View_V", "BgAnim_View_T"):
            self.assertIn(f"pub data {view}", emp)
        self.assertNotIn("NO DEBUG BG-ANIMATION VIEW TWINS", emp,
                         "an act that GETS its twins must not also be told it did not")

    def test_a_declined_multi_band_act_says_why(self):
        n_views, note = inject_editor_bg.view_emission(
            self._doc([(0, True), (32, False)])["anims"])
        self.assertEqual(n_views, 0)
        self.assertEqual(self._note_shortfalls(note), [],
                         f"the declined note is not actionable: {note!r}")

    def test_a_wrong_period_declines_rather_than_raising(self):
        """The period rung is DERIVED for 64 px; an act at 32 gets no twins, loudly.

        This used to be an `AssertionError` too, and it is the same defect: a 32 px
        single-band act carrying `default_off` is a CORRECT run under the ruling — the
        author is making a ship decision — and it would have failed the build over a
        DEBUG preview's rate derivation. Not emitting the twins protects
        BGANIM_VIEW_V_RATE_SHIFT from a period it was not computed for just as
        completely as raising did; the note supplies the loudness that raising bought.
        """
        anims = self._doc([(0, True)], cols=4, rows=4)["anims"]
        self.assertNotEqual(anims[0]["pattern_px"],
                            inject_editor_bg.BGANIM_VIEW_DERIVED_PERIOD_PX)
        n_views, note = inject_editor_bg.view_emission(anims)
        self.assertEqual(n_views, 0)
        self.assertIn("32", note or "",
                      "the note must name the period this act actually has")
        self.assertEqual(self._note_shortfalls(note), [])

    def test_an_act_with_no_default_off_is_told_nothing(self):
        """A refusal that can fire on a correct run is worse than the silence it replaces.

        An act that never sets `default_off` cannot notice this feature exists — that
        was true before the parcel and stays true. Announcing "no twins" to every such
        act would be a notice on every correct run, which is the bar this parcel is
        applying to itself.
        """
        for spec in ([(0, False)], [(0, False), (32, False)]):
            with self.subTest(spec=spec):
                self.assertEqual(
                    inject_editor_bg.view_emission(self._doc(spec)["anims"]), (0, None))

    def test_the_note_reaches_the_generated_artifact(self):
        """Scrollback is ephemeral; the emitted module is what a reviewer opens."""
        emp, _ = emit_over_document(self._doc([(0, True), (32, False)]))
        _, note = inject_editor_bg.view_emission(
            self._doc([(0, True), (32, False)])["anims"])
        first = (note or "").splitlines()[0].strip()
        self.assertIn(first, emp,
                      "the generated bg_anim.emp does not carry the declined-twins "
                      "note — its absence would be visible only in build scrollback")

    def test_the_note_costs_no_rom_bytes(self):
        """It is a comment: the section size must be the one the formula predicts."""
        spec = [(0, True), (32, False)]
        emp, banks = emit_over_document(self._doc(spec))
        anims = self._doc(spec)["anims"]
        slots = sum(a["cols"] * a["rows"] for a in anims)
        self.assertEqual(
            inject_editor_bg.bganim_section_bytes(len(anims), slots, n_views=0),
            inject_editor_bg.BGANIM_COUNT_BYTES
            + inject_editor_bg.BGANIM_RECORD_BYTES * len(anims) + len(banks))

    # ---- reordering is announced, never silent ---------------------------------

    def test_a_reordered_act_says_so(self):
        """Emitting live bands first is a real change to the table an author authored."""
        _, note = inject_editor_bg.band_emission_order(
            self._doc([(0, True), (32, False)])["anims"])
        self.assertIsNotNone(
            note, "the emitter reordered the author's bands and said nothing")
        self.assertIn("default_off", note)

    def test_an_already_ordered_act_is_not_reordered(self):
        for spec in ([(0, True)], [(0, False), (32, True)], [(0, False), (32, False)]):
            with self.subTest(spec=spec):
                anims = self._doc(spec)["anims"]
                order, note = inject_editor_bg.band_emission_order(anims)
                self.assertEqual(order, list(range(len(anims))))
                self.assertIsNone(note)


class TestBgAnimViewNamesAreShapeInvariant(unittest.TestCase):
    """The generated module's EXPORTED NAME SET must not depend on the document.

    THE DEFECT THIS CLASS EXISTS FOR, reported by the aurora lane 2026-09-06 with a
    one-key control on the pristine document and reproduced here before anything was
    changed. Delete the single key `default_off` from the shipped act's one band,
    change nothing else, re-bake, and the PLAIN build dies with:

        error: native build (sonic4 plain): build_program: 3 error(s);
          [Error] module `games.sonic4.ojz_bg_anim_act1` has no `pub` name `BgAnim_View_H`
          [Error] module `games.sonic4.ojz_bg_anim_act1` has no `pub` name `BgAnim_View_V`
          [Error] module `games.sonic4.ojz_bg_anim_act1` has no `pub` name `BgAnim_View_T`

    THE MECHANISM, and it is a two-sided one. `games/sonic4/test/ojz_scroll_test.emp`
    carries an UNCONDITIONAL `use games.sonic4.ojz_bg_anim_act1.{...}` naming all three
    twins; a `use` is resolved in EVERY shape, so the `if DEBUG == 1` guards on the
    declarations do not protect the plain shape. The emitter, meanwhile, wrote those
    three names for exactly ONE act shape (single band, `default_off`, 64 px). Measured
    over the whole population below: one shape of eight linked, and the other seven
    failed with three symbol names the author never wrote.

    NOT A REGRESSION OF THE DECOUPLE (aeon 01a45ede / 364b7bce), and the aurora lane
    checked that at 483b3e12: the pre-decouple code returned 0 twins for a
    no-`default_off` act too. The decouple removed a refusal that fired on a correct
    run; this is a DIFFERENT failure standing behind it, and it fails worse — a
    refusal at least says what happened.

    THE FIX THIS GATES: the three names are exported by every shape. A declining act
    exports them as count-0 (OFF) tables, which is structurally the same thing row 0 of
    the lab's own cycle already selects (this act's own `BgAnim_Table` when every band
    is `default_off`) and which `BgAnim_Update` walks with `move.w (a3)+, d7 / beq
    .exit`. The twins' own condition — exactly one band, `pattern_px` 64 — is UNCHANGED
    and still decides whether a twin carries a real band record; it stops deciding
    whether the module has a public interface.

    THE EXPECTATION IS DERIVED FROM THE CONSUMER, not from a list typed here: the
    subject test parses the `use` line out of `ojz_scroll_test.emp`. A fourth name
    added to that import turns this red without anyone remembering to update it.
    """

    AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    #: The module whose exported names the consumer imports. Derived, not typed:
    #: `act_names` is the one authority for the generated module's name.
    ACT = inject_editor_bg.ACT

    CONSUMER = os.path.join(AEON, "games", "sonic4", "test", "ojz_scroll_test.emp")

    # ---- the expectation, read out of the consumer ------------------------------

    def _imported_names(self):
        """Every name `ojz_scroll_test.emp` imports from the generated act module.

        Parsed from the source rather than listed here, so this gate cannot drift
        below the import it exists to protect.
        """
        with open(self.CONSUMER, encoding="utf-8") as f:
            src = f.read()
        pattern = re.compile(
            r"^\s*use\s+" + re.escape(self.ACT.module) + r"\.\{([^}]*)\}",
            re.MULTILINE)
        found = pattern.findall(src)
        self.assertTrue(
            found,
            f"no `use {self.ACT.module}.{{...}}` in {self.CONSUMER} — this gate lost "
            f"its subject and every assertion below would be vacuous")
        names = []
        for group in found:
            names += [n.strip() for n in group.split(",") if n.strip()]
        return names

    def test_the_consumer_import_is_unconditional_and_this_gate_can_see_it(self):
        """The matcher is under test: it must find a real import of real names."""
        names = self._imported_names()
        self.assertIn("BgAnim_Table", names)
        for view in ("BgAnim_View_H", "BgAnim_View_V", "BgAnim_View_T"):
            self.assertIn(view, names,
                          "the consumer no longer imports the twins by name — if that "
                          "is deliberate, this class is describing a defect that no "
                          "longer exists and should be retired, not left passing")

    # ---- fixtures: the whole population of act shapes ---------------------------

    @staticmethod
    def _band(cols, rows, slot_base, tiles, default_off):
        n = cols * rows
        ph0 = [tiles[slot_base + k] for k in range(n)]
        phases = [ph0] + [[[(v + ph) % 16 for v in t] for t in ph0]
                          for ph in range(1, 8)]
        band = {"cols": cols, "rows": rows, "pattern_px": cols * 8,
                "driver": "camera_x", "rate_shift": 4,
                "slot_base": slot_base, "phases": phases}
        if default_off:
            band["default_off"] = True
        return band

    @classmethod
    def _doc(cls, spec):
        """`spec` is [(cols, rows, default_off), ...]; [] is the no-animation act."""
        total = sum(c * r for c, r, _ in spec)
        tiles = [[(i * 7 + p) % 16 for p in range(64)] for i in range(max(total, 1))]
        anims, base = [], 0
        for cols, rows, off in spec:
            anims.append(cls._band(cols, rows, base, tiles, off))
            base += cols * rows
        return {"layout": [0] * 4096, "tiles": tiles, "anims": anims}

    #: EVERY shape an author can reach from the shipped document by editing the band
    #: list or one key of it. `(label, spec, twins_live)` — `twins_live` is what
    #: `views_emitted` says, i.e. whether the twins carry a real band record.
    #: Enumerated by what touches the emitted name set (band count, the key, the
    #: period), not sampled.
    SHAPES = [
        ("1 band, default_off, 64 px  (THE SHIPPED ACT)", [(8, 4, True)], True),
        ("1 band, NO default_off, 64 px", [(8, 4, False)], False),
        ("1 band, default_off, 32 px", [(4, 4, True)], False),
        ("1 band, NO default_off, 32 px", [(4, 4, False)], False),
        ("2 bands, band 0 default_off", [(8, 4, True), (8, 4, False)], False),
        ("2 bands, band 1 default_off", [(8, 4, False), (8, 4, True)], False),
        ("2 bands, neither default_off", [(8, 4, False), (8, 4, False)], False),
        ("no bands at all (the disabled stub)", [], False),
    ]

    @staticmethod
    def _emit(doc):
        """Emit `doc` and return the module text. Handles the no-animation stub too.

        `emit_over_document` insists on a bank blob, which the stub arm does not
        write; this is the same invocation without that requirement.
        """
        saved = (inject_editor_bg.OUT_DIR, inject_editor_bg.OVERRIDE)
        with tempfile.TemporaryDirectory() as tmpdir:
            override = os.path.join(tmpdir, "editor_bg_override.json")
            with open(override, "w") as f:
                json.dump(doc, f)
            try:
                inject_editor_bg.OUT_DIR = tmpdir
                inject_editor_bg.OVERRIDE = override
                with ceiling_lifted():
                    inject_editor_bg.main()
            finally:
                inject_editor_bg.OUT_DIR, inject_editor_bg.OVERRIDE = saved
            with open(os.path.join(tmpdir, "bg_anim.emp"), encoding="utf-8") as f:
                return f.read()

    @staticmethod
    def _declarations(emp):
        """`{name: initializer text}` for every `pub data` in the emitted module."""
        out = {}
        for line in emp.splitlines():
            m = re.match(r"pub data (\w+)\s*(?::[^=]*)?=\s*(.*)", line)
            if m:
                out[m.group(1)] = m.group(2).split("//")[0].strip()
        return out

    def test_the_fixture_reaches_both_emitter_arms(self):
        """Non-vacuity: the shapes above must exercise the animated arm AND the stub."""
        counts = {self._emit(self._doc(spec)).count("_hdr:") for _, spec, _ in self.SHAPES}
        self.assertIn(0, counts, "no shape reached the disabled-stub arm")
        self.assertTrue(any(c for c in counts), "no shape reached the animated arm")

    # ---- the subject ------------------------------------------------------------

    def test_every_act_shape_exports_every_imported_name(self):
        """THE GATE. A link error naming a symbol the author never wrote is the bug.

        Red before the fix on 7 of the 8 shapes below (measured), each missing all
        three twins; the shipped shape was the only one that linked.
        """
        wanted = self._imported_names()
        for label, spec, _live in self.SHAPES:
            with self.subTest(shape=label):
                declared = self._declarations(self._emit(self._doc(spec)))
                missing = [n for n in wanted if n not in declared]
                self.assertEqual(
                    missing, [],
                    f"the {label} act exports no `pub` name {missing} — "
                    f"{os.path.relpath(self.CONSUMER, self.AEON)} imports it "
                    f"unconditionally, so this act fails the link (in the PLAIN shape "
                    f"too: a `use` is resolved in every shape) with symbol names its "
                    f"author never wrote")

    def test_a_declining_twin_is_a_count_zero_table_and_carries_no_record(self):
        """Declining must cost an OFF row, not a wild pointer and not a band.

        Two halves, and the second is the one that keeps the twins' condition intact:
        the NAME is there, and the RECORD is not.
        """
        for label, spec, live in self.SHAPES:
            if live:
                continue
            with self.subTest(shape=label):
                emp = self._emit(self._doc(spec))
                declared = self._declarations(emp)
                for view in ("BgAnim_View_H", "BgAnim_View_V", "BgAnim_View_T"):
                    self.assertIn("[0]", declared[view],
                                  f"{view} on the {label} act is not a count-0 table: "
                                  f"{declared[view]!r}. Selecting that row in the lab "
                                  f"would hand BgAnim_Update whatever follows it.")
                self.assertNotIn(
                    "_BgAnim_ViewH0_hdr", emp,
                    f"the {label} act emitted a real twin RECORD — the twins' condition "
                    f"(exactly one band, 64 px) is what decides that and it is unmet")

    def test_the_shipped_shape_still_gets_live_twins_with_their_records(self):
        """The control: the fix must not turn the owner's A/B into three OFF rows."""
        label, spec, live = self.SHAPES[0]
        self.assertTrue(live, "the first shape is meant to be the live one")
        emp = self._emit(self._doc(spec))
        declared = self._declarations(emp)
        for view in ("BgAnim_View_H", "BgAnim_View_V", "BgAnim_View_T"):
            self.assertIn("[1]", declared[view],
                          f"{view} lost its band on the shipped act")
        for tag in ("ViewH", "ViewV", "ViewT"):
            self.assertIn(f"_BgAnim_{tag}0_hdr", emp)
            self.assertIn(f"_BgAnim_{tag}0_banks", emp)

    def test_the_declining_module_says_why_its_names_are_there(self):
        """A reader opening the artifact must not have to guess what `[0]` means."""
        emp = self._emit(self._doc([(8, 4, False)]))
        self.assertIn("count-0", emp)
        self.assertIn("ojz_scroll_test.emp", emp,
                      "the emitted explanation does not name the consumer whose "
                      "unconditional import is the reason these names exist")

    # ---- the size model must still describe the emitter -------------------------

    def test_the_size_formula_counts_the_declined_count_words(self):
        """A formula that has drifted from the emitter gates nothing.

        The declined names cost `BGANIM_VIEW_COUNT` count words in the DEBUG shape and
        zero bytes in the plain one (the `[u16; BGANIM_VIEW_EMIT]` idiom). The ceiling
        is checked against the DEBUG shape, so the formula has to carry them.
        """
        spec = [(8, 4, False)]
        anims = self._doc(spec)["anims"]
        slots = sum(a["cols"] * a["rows"] for a in anims)
        n_views = inject_editor_bg.views_emitted(anims)
        self.assertEqual(n_views, 0, "this fixture is meant to be a declining act")
        declined = inject_editor_bg.BGANIM_VIEW_COUNT - n_views
        self.assertEqual(
            inject_editor_bg.bganim_section_bytes(len(anims), slots, n_views=n_views,
                                                  n_declined_views=declined)
            - inject_editor_bg.bganim_section_bytes(len(anims), slots, n_views=n_views),
            declined * inject_editor_bg.BGANIM_COUNT_BYTES,
            "the size model does not account for the declined twins' count words")

    def test_the_live_shape_gains_no_bytes_from_this_fix(self):
        """The two terms are exclusive: 3 live twins leave 0 declined ones.

        A single 8x4 64 px `default_off` band — the shape this tree ships — must come
        to exactly what it came to before this parcel: 8,376 B, the number
        tools/EFFECTS_CONSUMER_CONTRACT.md and tools/bganim_room.py both quote. A fix
        that moved the LIVE section size would have re-opened the frozen placement
        tables for a bug about acts that do not exist yet.

        DELIBERATELY SYNTHETIC, and this is the second half of the parcel's own bar.
        A first draft asserted `live_section_bytes() == 8376`, which reads THIS TREE's
        override — so the moment an author removed `default_off` (the exact correct
        run this class exists to keep building) the build failed on a tool test
        instead of a link error. Measured: it did, on the acceptance run. A gate that
        pins the shipped document's CONTENT is the failure mode being fixed, wearing
        a different hat.
        """
        anims = self._doc([(8, 4, True)])["anims"]
        self.assertEqual(anims[0]["pattern_px"],
                         inject_editor_bg.BGANIM_VIEW_DERIVED_PERIOD_PX)
        self.assertEqual(inject_editor_bg.views_emitted(anims),
                         inject_editor_bg.BGANIM_VIEW_COUNT)
        self.assertEqual(inject_editor_bg.declined_views(anims), 0)
        self.assertEqual(shape_aware_size(anims), 8376)


if __name__ == "__main__":
    unittest.main()
