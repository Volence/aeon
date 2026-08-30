"""Insta-shield asset provenance — the mappings, the DPLC and the donor animation
reference all come out of tools/compose_instashield.py run over the sonic_hack donor,
and the committed bytes must be exactly what that pipeline produces today.

Two tiers, so the always-on half never depends on a machine having the donor:

  * property tests over the COMMITTED blobs (always run): sizes, the frame/entry
    correspondence the .emp's comptime ensure also pins (zero pieces <=> zero DPLC
    entries), the peak tile count the VRAM window is sized against, and the pixel-index
    census {0,6,7,8}. A stray index means the art was regenerated from skdisasm's
    Insta-Shield.bin, whose {0,1,$C,$D} would draw the flash in Sonic's REDS on
    art/palettes/SonicAndTails.bin.
  * regeneration (needs the donor): run the composer into tmp, compare all three
    outputs byte-for-byte against the committed files, and re-check the art identity.
    Skips LOUDLY, naming the missing piece, when the donor tree is absent — a skip is
    visible in the totals; it is never a silent pass.

NEVER write into the repo from here (tools/test_import_sk_collision.py:14 records why):
the composer is invoked with --out-root pointing at a tmp copy.
"""
import os
import shutil
import struct
import sys
from collections import Counter

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
AEON = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import compose_instashield as ci  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/, for suite_paths
from suite_paths import suite_path  # noqa: E402
# The donor sits BESIDE this checkout at the suite root. Spelled through suite_paths
# because `<checkout>/../sonic_hack` resolves to `.claude/worktrees/sonic_hack` from a worktree,
# and the rows below then SKIP for a resolution bug that reads as "donor not installed".
SONIC_HACK = os.environ.get("AEON_SONIC_HACK_DIR", str(suite_path("sonic_hack")))

MAP = os.path.join(AEON, ci.OUT_MAP)
DPLC = os.path.join(AEON, ci.OUT_DPLC)
ANIM = os.path.join(AEON, ci.OUT_ANIM)
ART = os.path.join(AEON, ci.IN_ART)

TILE = 32
# The donor's palette vocabulary, measured: 0 transparent, 6 = $0EEE white,
# 7 = $0CAA, 8 = $0866 — a white -> blue-grey ramp on CRAM line 0, Sonic's own line
# (art/palettes/SonicAndTails.bin). See the design note §2.5.
INSTA_INDICES = {0, 6, 7, 8}


def _read(path):
    with open(path, "rb") as fh:
        return fh.read()


# --------------------------------------------------------------------------
# Tier 1 — properties of the committed blobs. No donor needed.
# --------------------------------------------------------------------------
def test_art_is_52_whole_tiles():
    art = _read(ART)
    assert len(art) == 52 * TILE, f"{ci.IN_ART} is {len(art)} B, expected 52 tiles"


def test_art_palette_census():
    """Every nibble in the donor's index set. The .emp pins the same fact at comptime;
    this is the Python half, so a bad regeneration fails before the assembler runs."""
    census = Counter()
    for byte in _read(ART):
        census[byte >> 4] += 1
        census[byte & 0xF] += 1
    stray = sorted(set(census) - INSTA_INDICES)
    assert not stray, (
        f"insta_shield.bin uses palette indices {stray} outside the donor's "
        f"{sorted(INSTA_INDICES)} — regenerated from skdisasm's blob "
        f"({{0,1,0xC,0xD}}) instead of sonic_hack's?")


def test_mapping_and_dplc_frame_counts_agree():
    counts = ci.frame_piece_counts(_read(MAP))
    entries = ci.dplc_entry_counts(_read(DPLC))
    assert len(counts) == len(entries) == 8, (
        f"insta-shield has {len(counts)} mapping frames / {len(entries)} DPLC frames; "
        f"S3K's Map_InstaShield and DPLC_InstaShield both carry 8")


def test_zero_piece_frames_have_zero_entry_dplc():
    """The one deviation from the donor DPLC, checked in BOTH directions — this is
    what makes 'frames 6 and 7 draw nothing so they load nothing' a fact rather than
    a claim. The .emp carries the same ensure at comptime."""
    counts = ci.frame_piece_counts(_read(MAP))
    entries = ci.dplc_entry_counts(_read(DPLC))
    for f, (pieces, ents) in enumerate(zip(counts, entries)):
        assert (pieces == 0) == (ents == 0), (
            f"insta-shield frame {f}: {pieces} mapping pieces but {ents} DPLC entries "
            f"— a drawn frame with no art, or art loaded for a frame that draws nothing")


def test_dplc_peak_tiles_fits_its_vram_window():
    """29 tiles is what games/sonic4/vram.toml sizes the window at; the .emp checks the
    same number against VRAM_TEST_SONIC. Derived from the blob, never typed."""
    dplc = _read(DPLC)
    frames = struct.unpack_from(">H", dplc, 0)[0] // 2
    peak = 0
    for f in range(frames):
        off = struct.unpack_from(">H", dplc, f * 2)[0]
        n = struct.unpack_from(">H", dplc, off)[0]
        total = sum(((struct.unpack_from(">H", dplc, off + 2 + e * 2)[0] >> 12) + 1)
                    for e in range(n))
        peak = max(peak, total)
    assert peak == 29, f"insta-shield peak DPLC frame is {peak} tiles, window is 29"


def test_donor_anim_script_shape():
    """The reference script: duration byte, then frame bytes, then a control code.
    The .emp derives its expected total duration from exactly these bytes."""
    anim = _read(ANIM)
    assert anim[0] == 0, f"donor duration byte is {anim[0]}, expected 0 (one frame each)"
    # Stop at the terminator: $FD's ARGUMENT byte (the target anim id, 0) is itself
    # below the control floor and would otherwise count as a 15th frame.
    frames = []
    for byte in anim[1:]:
        if byte >= ci.S3K_CONTROL_FLOOR:
            break
        frames.append(byte)
    assert len(frames) == 14, f"donor attack script shows {len(frames)} frames, expected 14"
    assert frames[-1] == 7, (
        f"donor attack script's last frame is {frames[-1]}, expected 7 — S3K's "
        f"Obj_InstaShield_Main tests `cmpi.b #7,mapping_frame`")


# --------------------------------------------------------------------------
# Tier 2 — regeneration from the donor.
# --------------------------------------------------------------------------
def test_regenerates_from_donor(tmp_path):
    missing = [p for p in (ci.DONOR_MAP, ci.DONOR_DPLC, ci.DONOR_ANIM, ci.DONOR_ART)
               if not os.path.isfile(os.path.join(SONIC_HACK, p))]
    if missing:
        pytest.skip(f"donor tree absent (AEON_SONIC_HACK_DIR={SONIC_HACK}): "
                    f"missing {', '.join(missing)}")

    outputs, donor_art = ci.compose(SONIC_HACK)

    assert _read(ART) == donor_art, (
        f"{ci.IN_ART} is no longer byte-identical to {ci.DONOR_ART} in the donor tree")

    for rel, blob in outputs.items():
        committed = _read(os.path.join(AEON, rel))
        assert committed == blob, (
            f"{rel} is not what tools/compose_instashield.py produces from the donor "
            f"today ({len(committed)} B committed, {len(blob)} B composed)")


def test_composer_check_mode_is_green(tmp_path):
    """The composer's own --check path, run against a tmp copy of the outputs, so the
    CLI a human would reach for is exercised too and can never write into the repo."""
    missing = [p for p in (ci.DONOR_MAP, ci.DONOR_DPLC, ci.DONOR_ANIM, ci.DONOR_ART)
               if not os.path.isfile(os.path.join(SONIC_HACK, p))]
    if missing:
        pytest.skip(f"donor tree absent (AEON_SONIC_HACK_DIR={SONIC_HACK}): "
                    f"missing {', '.join(missing)}")

    for rel in (ci.OUT_MAP, ci.OUT_DPLC, ci.OUT_ANIM, ci.IN_ART):
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(os.path.join(AEON, rel), dst)

    argv = sys.argv
    sys.argv = ["compose_instashield.py", "--donor", SONIC_HACK,
                "--out-root", str(tmp_path), "--check"]
    try:
        assert ci.main() == 0, "compose_instashield.py --check disagrees with the tree"
    finally:
        sys.argv = argv
