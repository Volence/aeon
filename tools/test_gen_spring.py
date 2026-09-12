"""Spring art provenance — the committed blob must be exactly what the pipeline makes.

The blob comes out of games/sonic4/data/spring_staging/gen_spring.py run over the
sonic_hack donor `art/nemesis/Vertical spring.bin`. Two tiers, so the always-on half
never depends on a machine having the donor tree (the shape compose_ring's own
provenance test established):

  * property tests over the COMMITTED blob (always run): its size, and the pixel-index
    census. A stray index here means the art was regenerated from the WRONG donor --
    skdisasm's Vertical Spring.bin carries {5,E,F} on top of this set, which against
    CRAM line 0 (art/palettes/SonicAndTails.bin) are blue and orange rather than the
    reds and greys this sprite is drawn in -- or WITHOUT the generator's INDEX_REMAP,
    which moves the donor's coil grey off the character-specific slot 9 onto 8 (the
    owner's ruling, SPRING-PAL-IDX9). The expected vocabulary is derived from the
    generator's own INDEX_REMAP, not restated here.
  * regeneration (needs the donor + nemdec): run the generator into tmp and compare
    byte-for-byte against the committed file. Skips LOUDLY, naming the missing piece,
    when the donor tree or the decompressor is absent -- a skip is visible in the
    totals; it is never a silent pass.

NEVER write into the repo from here (tools/test_import_sk_collision.py:14 records why).
"""
import importlib.util
import os
import subprocess
import sys
import tempfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
AEON = os.path.normpath(os.path.join(HERE, ".."))
GEN = os.path.join(AEON, "games", "sonic4", "data", "spring_staging", "gen_spring.py")
BLOB = os.path.join(AEON, "games", "sonic4", "data", "generated", "spring", "art_spring.bin")

sys.path.insert(0, HERE)
from suite_paths import suite_path  # noqa: E402
SONIC_HACK = os.environ.get("AEON_SONIC_HACK_DIR", str(suite_path("sonic_hack")))
DONOR = os.path.join(SONIC_HACK, "art", "nemesis", "Vertical spring.bin")
NEMDEC = os.path.join(SONIC_HACK, "tools", "nemdec")

TILE = 32
# 24 = the vertical sheet's 12 repacked tiles + the horizontal sheet's 12 verbatim.
# The side spring is a SEPARATE donor sheet, not a rotation (its plate is a
# vertical bar); DOWN and LEFT are renderer flips of these two.
SPRING_VERT_TILES = 12
SPRING_HORIZ_TILES = 12
SPRING_TILES = SPRING_VERT_TILES + SPRING_HORIZ_TILES
# The DONOR's line-0 vocabulary (a fact about sonic_hack's sheet): 0 transparent,
# 1 near-black outline, 6 white, 7 light grey, 8 grey-blue, 9 grey, $C bright red,
# $D dark red.
DONOR_INDICES = {0, 1, 6, 7, 8, 9, 0xC, 0xD}

# The generator's own remap, loaded from the generator (importing it runs no
# generation — main() is guarded). The committed blob's vocabulary is the donor's
# pushed through it, so changing the ruling in one place moves this expectation.
_spec = importlib.util.spec_from_file_location("gen_spring", GEN)
_gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gen)
INDEX_REMAP = _gen.INDEX_REMAP
SPRING_INDICES = {INDEX_REMAP.get(i, i) for i in DONOR_INDICES}


def _indices(blob: bytes) -> set:
    out = set()
    for b in blob:
        out.add(b >> 4)
        out.add(b & 0xF)
    return out


def test_blob_is_both_sheets():
    assert os.path.getsize(BLOB) == SPRING_TILES * TILE, (
        f"the blob must be {SPRING_VERT_TILES} vertical + {SPRING_HORIZ_TILES} "
        f"horizontal tiles")


def test_blob_uses_only_the_line_0_vocabulary():
    got = _indices(open(BLOB, "rb").read())
    assert got <= SPRING_INDICES, (
        f"the spring blob carries pixel indices {sorted(got - SPRING_INDICES)} that are "
        f"not in CRAM line 0's spring vocabulary — regenerated from the wrong donor? "
        f"skdisasm's sheet adds $5 (blue) and $E/$F (orange); or regenerated without "
        f"gen_spring.py's INDEX_REMAP {INDEX_REMAP}.")


def test_blob_draws_no_remapped_away_index():
    """The owner's SPRING-PAL-IDX9 ruling, read from the ART: no pixel on an index the
    generator moves away. Index 9 is character-specific on CRAM line 0 ($0444 as
    Sonic/Tails, $0080 as Knuckles), so any pixel left there recolours on a swap."""
    assert INDEX_REMAP, "gen_spring.INDEX_REMAP is empty — this test measures nothing"
    blob = open(BLOB, "rb").read()
    left = {src: sum((b >> 4) == src for b in blob) + sum((b & 0xF) == src for b in blob)
            for src in INDEX_REMAP}
    left = {src: n for src, n in left.items() if n}
    assert not left, (
        f"the committed spring blob still draws {left} pixel(s) on remapped-away "
        f"index(es) (index: pixels) — gen_spring.py's INDEX_REMAP {INDEX_REMAP} was not "
        f"applied. Regenerate with the generator; do not hand-edit the blob.")


def test_no_tile_is_blank():
    """The repack's whole point: 20 vertical donor tiles down to 12 by dropping the
    empty ones (the horizontal sheet has none to drop and is copied verbatim). A
    blank tile anywhere here means the re-cut silently stopped working and the map is
    paying for padding again."""
    blob = open(BLOB, "rb").read()
    blank = [t for t in range(SPRING_TILES) if blob[t * TILE:(t + 1) * TILE] == b"\0" * TILE]
    assert not blank, f"tiles {blank} are blank — the piece re-cut regressed"


def test_regenerates_byte_identically():
    for path, what in ((DONOR, "donor art"), (NEMDEC, "nemdec decompressor")):
        if not os.path.exists(path):
            pytest.skip(f"{what} not installed at {path} — regeneration not checked")
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "art_spring.bin")
        r = subprocess.run([sys.executable, GEN, "--out", out],
                           capture_output=True, text=True)
        assert r.returncode == 0, f"gen_spring failed: {r.stderr}"
        assert open(out, "rb").read() == open(BLOB, "rb").read(), (
            "the committed spring blob is NOT what gen_spring.py produces from the "
            "donor today — regenerate it, or explain the divergence")
