#!/usr/bin/env python3
"""The vertical BgAnim probe band's LOCKSTEP gate — three authors, one geometry.

The probe band's six record fields are spelled in TWO places that cannot see each other:

  tools/bganim_vprobe_gen.py         COLS / ROWS and the derived V_COL_SHIFT,
                                     V_STEP_MASK, H_COL_SHIFT, H_STEP_MASK,
                                     VPROBE_VRAM_DEST — and it GENERATES THE ART from
                                     them, so a drift here silently produces banks
                                     rolled on the wrong axis or by the wrong period
  games/sonic4/test/ojz_scroll_test.emp   the two `_VProbe_*_hdr` records the engine
                                     actually walks

and a third, `games/sonic4/data/generated/bganim_vprobe_banks.bin`, is the art those two
have to agree ABOUT. This file reads all three and fails the build's pytest lane
(`python3 -m pytest tools`, build.sh) on any disagreement.

WHY A GATE AND NOT A COMMENT. The failure this catches is silent by construction. Change
ROWS in the generator and re-run it and the ROM still builds, the band still animates, the
witness still finds *a* band — it is just rolling on a period the record does not declare,
which is precisely the mismatch `validate_band_phase_axis` exists to refuse on the
authored side and which this band, living outside the emitter, would otherwise have no
check for at all. docs/BUGS.md TOOL-01 is the same shape one axis over.

WHY IT DOES NOT OPEN A ROM. build.sh runs the pytest lane BEFORE the sigil build, so a
test that opened `s4.bin` would be reading the PREVIOUS build's bytes and reporting them
as this one's. Everything here is source-and-generator only; the ROM-side claim is
tools/bganim_vprobe_witness.py's job, and that runs after a build with the ROM named on
its command line.
"""
import importlib.util
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EMP = REPO / "games/sonic4/test/ojz_scroll_test.emp"
BLOB = REPO / "games/sonic4/data/generated/bganim_vprobe_banks.bin"


def _gen():
    spec = importlib.util.spec_from_file_location(
        "bganim_vprobe_gen", REPO / "tools/bganim_vprobe_gen.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _record(tag):
    """The six words of one `_VProbe_<tag>_hdr` record, out of the .emp source.

    Read with a regex rather than by importing anything, because the .emp file is the
    OTHER author: a helper shared with the generator would make the two sides one side
    and the gate would pass forever.
    """
    src = EMP.read_text()
    m = re.search(rf"^data _VProbe_{tag}_hdr:.*?=.*?\[([^\]]*)\]", src, re.M | re.S)
    assert m, f"no `_VProbe_{tag}_hdr` record found in {EMP}"
    words = []
    for tok in m.group(1).split(","):
        tok = tok.strip()
        words.append(int(tok[1:], 16) if tok.startswith("$") else int(tok))
    assert len(words) == 6, f"_VProbe_{tag}_hdr has {len(words)} words, expected 6"
    return dict(zip(("driver", "rate_shift", "step_mask", "col_shift",
                     "tile_count", "vram_dest"), words))


class TestBgAnimVProbeLockstep:

    def test_vertical_record_matches_the_generator(self):
        g, r = _gen(), _record("V")
        assert r["step_mask"] == g.V_STEP_MASK
        assert r["col_shift"] == g.V_COL_SHIFT
        assert r["tile_count"] == g.TILES
        assert r["vram_dest"] == g.VPROBE_VRAM_DEST

    def test_horizontal_control_record_matches_the_generator(self):
        g, r = _gen(), _record("H")
        assert r["step_mask"] == g.H_STEP_MASK
        assert r["col_shift"] == g.H_COL_SHIFT
        assert r["tile_count"] == g.TILES
        assert r["vram_dest"] == g.VPROBE_VRAM_DEST

    def test_the_two_arms_differ_ONLY_in_the_two_axis_fields(self):
        """The control's whole value is that it isolates the axis. If the two records
        ever drift apart in driver, rate, tile count or destination, the witness's
        negative arm stops being a control and becomes a second, different experiment."""
        v, h = _record("V"), _record("H")
        for k in ("driver", "rate_shift", "tile_count", "vram_dest"):
            assert v[k] == h[k], f"the arms differ in `{k}` — the control no longer isolates the axis"
        assert (v["step_mask"], v["col_shift"]) != (h["step_mask"], h["col_shift"]), \
            "the arms carry identical axis fields — there is no control"

    def test_the_rotate_invariant_holds_on_both_arms(self):
        """`units * unit_bytes == tile_count * 32`, the condition that keeps
        BgAnim_Update's piece-1 length positive (its own `assert.w d3, gt, #0`). A record
        that broke it would send QueueDMA a length <= 0, i.e. a 128 KB spray."""
        for tag in ("V", "H"):
            r = _record(tag)
            unit = 1 << r["col_shift"]
            units = (r["tile_count"] * 32) // unit
            assert units * unit == r["tile_count"] * 32, f"_VProbe_{tag}_hdr breaks the rotate invariant"
            assert units > 1, (f"_VProbe_{tag}_hdr has {units} rotation unit(s): the coarse "
                               f"rotate can never move, so this arm is degenerate")

    def test_the_blob_on_disk_is_what_the_generator_produces(self):
        g = _gen()
        assert BLOB.exists(), f"{BLOB} is missing — run tools/bganim_vprobe_gen.py"
        assert BLOB.read_bytes() == g.blob(), (
            f"{BLOB.name} is STALE against tools/bganim_vprobe_gen.py — "
            f"run `python3 tools/bganim_vprobe_gen.py`")

    def test_the_blob_length_is_what_both_records_claim(self):
        g, v = _gen(), _record("V")
        assert len(BLOB.read_bytes()) == 8 * v["tile_count"] * 32 == g.BLOB_BYTES

    def test_every_bank_is_a_y_roll_of_bank_zero(self):
        """The art half of `axis: vertical`, checked against the BLOB rather than against
        the generator's intent: bank k must be bank 0 moved k px toward DECREASING y, in
        row-major slot order. This is the check that would catch a blob regenerated by a
        horizontal shift-fill while the record still said vertical."""
        g = _gen()
        raw = BLOB.read_bytes()
        n = g.TILES * 32
        pic = [g_decode(raw[k * n:(k + 1) * n], g.COLS, g.ROWS) for k in range(8)]
        h = g.ROWS * 8
        for k in range(1, 8):
            want = [pic[0][(y + k) % h] for y in range(h)]
            assert pic[k] == want, f"bank {k} is not bank 0 rolled up {k} px"

    def test_the_art_makes_both_arms_discriminating(self):
        """The generator's own art contract, re-asserted against the blob on disk: all
        pixel rows distinct (else some vertical roll is a no-op) and all pixel columns
        distinct (else the horizontal control is a no-op on the pixels and its failure
        would be about the art, not the axis)."""
        g = _gen()
        p = g_decode(BLOB.read_bytes()[:g.TILES * 32], g.COLS, g.ROWS)
        rows = {tuple(r) for r in p}
        cols = {tuple(p[y][x] for y in range(len(p))) for x in range(len(p[0]))}
        assert len(rows) == len(p), f"only {len(rows)} of {len(p)} pixel rows are distinct"
        assert len(cols) == len(p[0]), f"only {len(cols)} of {len(p[0])} pixel columns are distinct"


def g_decode(buf, cols, rows):
    """Row-major slot decode — the order a vertical band's slots must be in."""
    img = [[0] * (cols * 8) for _ in range(rows * 8)]
    for j in range(cols * rows):
        tr, tc = j // cols, j % cols
        t = buf[j * 32:(j + 1) * 32]
        for dy in range(8):
            for k in range(4):
                b = t[dy * 4 + k]
                img[tr * 8 + dy][tc * 8 + k * 2] = b >> 4
                img[tr * 8 + dy][tc * 8 + k * 2 + 1] = b & 0xF
    return img
