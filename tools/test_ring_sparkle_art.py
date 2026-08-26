"""Ring art provenance — the spin blob and the collect-sparkle blob both come out of
games/sonic4/test/compose_ring.py run over the sonic_hack Ring.bin donor, and the
committed bytes must be exactly what that pipeline produces today.

Two tiers, so the always-on half never depends on a machine having the donor:

  * property tests over the COMMITTED blobs (always run): sizes, and the pixel-index
    census the sparkle's comptime ensure also pins — {0,5,6,C,D}, CRAM line 1, the
    ring's own set. A stray index here means the art was regenerated from the wrong
    donor (skdisasm's Ring.bin uses {1,5,6,F} and would need a lossy remap).
  * regeneration (needs the donor + nemdec): decompress the donor into tmp, run the
    composer into tmp, compare BOTH outputs byte-for-byte against the committed files.
    Skips LOUDLY, naming the missing piece, when the donor tree or the decompressor is
    absent — a skip is visible in the totals; it is never a silent pass.

NEVER write into the repo from here (tools/test_import_sk_collision.py:14 records why).
"""
import os
import shutil
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
AEON = os.path.normpath(os.path.join(HERE, ".."))
COMPOSER = os.path.join(AEON, "games", "sonic4", "test", "compose_ring.py")
RING_ART = os.path.join(AEON, "games", "sonic4", "test", "ring_art.bin")
SPARKLE_ART = os.path.join(AEON, "games", "sonic4", "test", "ring_sparkle_art.bin")

SONIC_HACK = os.environ.get(
    "AEON_SONIC_HACK_DIR",
    os.path.normpath(os.path.join(AEON, "..", "sonic_hack")))
DONOR = os.path.join(SONIC_HACK, "art", "nemesis", "Ring.bin")
NEMDEC = os.path.join(SONIC_HACK, "tools", "nemdec")

TILE = 32
# The ring's line-1 vocabulary: 0 transparent, 5 outline, 6 white, $C bright gold,
# $D dark gold — see compose_ring.py's docstring and rings.emp RING_ART_ATTR.
RING_INDICES = {0, 5, 6, 0xC, 0xD}


def _indices(blob: bytes) -> set[int]:
    out: set[int] = set()
    for b in blob:
        out.add(b >> 4)
        out.add(b & 0xF)
    return out


def test_spin_blob_is_four_2x2_frames():
    assert os.path.getsize(RING_ART) == 4 * 4 * TILE


def test_sparkle_blob_is_one_2x2_piece():
    assert os.path.getsize(SPARKLE_ART) == 4 * TILE


def test_sparkle_uses_only_the_ring_line_indices():
    blob = open(SPARKLE_ART, "rb").read()
    used = _indices(blob)
    assert used <= RING_INDICES, f"sparkle art uses indices {sorted(used - RING_INDICES)} outside the ring's line-1 set"
    # Not just a subset — it must actually be drawn with the ring's colours, or a
    # blank/zeroed blob would pass.
    assert used & {5, 6, 0xC, 0xD} == {5, 6, 0xC, 0xD}


def test_sparkle_and_spin_share_the_same_index_set():
    assert _indices(open(SPARKLE_ART, "rb").read()) == _indices(open(RING_ART, "rb").read())


def _need_donor():
    if not os.path.isfile(DONOR):
        pytest.skip(f"SKIPPED (donor absent): {DONOR} — set AEON_SONIC_HACK_DIR")
    if not (os.path.isfile(NEMDEC) and os.access(NEMDEC, os.X_OK)):
        pytest.skip(f"SKIPPED (decompressor absent): {NEMDEC}")


def test_committed_blobs_reproduce_from_the_donor(tmp_path):
    _need_donor()
    donor_raw = tmp_path / "ring_donor.bin"
    subprocess.run([NEMDEC, "-d", DONOR, str(donor_raw)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert donor_raw.stat().st_size == 14 * TILE, "sonic_hack Ring.bin should decompress to 14 tiles"
    spin = tmp_path / "ring_art.bin"
    sparkle = tmp_path / "ring_sparkle_art.bin"
    subprocess.run([sys.executable, COMPOSER, str(donor_raw), str(spin), str(sparkle)],
                   check=True, stdout=subprocess.DEVNULL)
    assert spin.read_bytes() == open(RING_ART, "rb").read(), "committed ring_art.bin drifted from the composer's output"
    assert sparkle.read_bytes() == open(SPARKLE_ART, "rb").read(), "committed ring_sparkle_art.bin drifted from the composer's output"
    # The sparkle is donor tiles 10..13 verbatim (compose_ring.SPARKLE_DONOR_TILES).
    raw = donor_raw.read_bytes()
    assert sparkle.read_bytes() == raw[10 * TILE:14 * TILE]


def test_composer_is_deterministic(tmp_path):
    _need_donor()
    donor_raw = tmp_path / "ring_donor.bin"
    subprocess.run([NEMDEC, "-d", DONOR, str(donor_raw)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    outs = []
    for i in range(2):
        spin = tmp_path / f"spin{i}.bin"
        sparkle = tmp_path / f"sparkle{i}.bin"
        subprocess.run([sys.executable, COMPOSER, str(donor_raw), str(spin), str(sparkle)],
                       check=True, stdout=subprocess.DEVNULL)
        outs.append((spin.read_bytes(), sparkle.read_bytes()))
    assert outs[0] == outs[1]
