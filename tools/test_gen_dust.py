import os, subprocess, sys, struct

HERE = os.path.dirname(__file__)
GEN = os.path.join(HERE, "..", "games", "sonic4", "data", "dust_staging", "gen_dust.py")
_SK_ROOT = os.environ.get(
    "AEON_SKDISASM_DIR",
    os.path.normpath(os.path.join(HERE, "..", "..", "skdisasm")))

# NOTE: every test here writes to tmp_path. NEVER default the importer's output
# into the repo — see tools/test_import_sk_collision.py:14 for the incident that
# rule comes from (a test silently reverted a committed bake and turned ~10
# sigil port targets red).


def run(out_dir):
    subprocess.run([sys.executable, GEN, "--out", str(out_dir),
                    "--skdisasm", _SK_ROOT], check=True)


def _tiles(path):
    return os.path.getsize(path) // 32


def test_art_is_88_tiles(tmp_path):
    run(tmp_path)
    assert _tiles(os.path.join(tmp_path, "art_dust.bin")) == 88


def test_art_uses_only_remapped_indices(tmp_path):
    """S3K indices 1/12/13 must become 6/4/7; nothing else may appear.

    Asserts the exact per-index pixel histogram, not just the output set: a
    transposition (e.g. swapping which source index maps to 4 vs 7) leaves the
    set {0,4,6,7} unchanged but shows up immediately here. The four counts are
    independently confirmed (see games/sonic4/data/dust_staging/README.md).
    """
    run(tmp_path)
    data = open(os.path.join(tmp_path, "art_dust.bin"), "rb").read()
    hist = {}
    for b in data:
        for nib in (b >> 4, b & 0xF):
            hist[nib] = hist.get(nib, 0) + 1
    seen = set(hist)
    assert seen <= {0, 6, 4, 7}, f"unexpected palette indices: {sorted(seen)}"
    assert {6, 4, 7} <= seen
    assert hist == {0: 4286, 6: 1244, 4: 81, 7: 21}, hist


def test_charge_dplc_frames_and_peak(tmp_path):
    run(tmp_path)
    d = open(os.path.join(tmp_path, "dplc_dust.bin"), "rb").read()
    n_frames = struct.unpack_from(">H", d, 0)[0] // 2
    assert n_frames == 7
    counts = []
    for f in range(n_frames):
        off = struct.unpack_from(">H", d, f * 2)[0]
        n_entries = struct.unpack_from(">H", d, off)[0]
        total = 0
        for e in range(n_entries):
            word = struct.unpack_from(">H", d, off + 2 + e * 2)[0]
            tile_count = ((word >> 12) & 0xF) + 1
            assert tile_count <= 16
            assert (word & 0x0FFF) + tile_count <= 72, "charge DPLC ran past its 72 tiles"
            total += tile_count
        counts.append(total)
    assert counts == [8, 8, 8, 12, 12, 12, 12]
    assert max(counts) == 12, "charge DPLC peak must fit the 12-tile window"


def test_puff_mappings_are_four_2x2_frames(tmp_path):
    run(tmp_path)
    d = open(os.path.join(tmp_path, "map_dust_puff.bin"), "rb").read()
    assert struct.unpack_from(">H", d, 0)[0] // 2 == 4
    for f in range(4):
        off = struct.unpack_from(">H", d, f * 2)[0]
        assert struct.unpack_from(">H", d, off + 4)[0] == 1, "puff frame must be one piece"
        size = d[off + 6 + 2]
        assert size == 0b0101, "puff piece must be 2x2 tiles"
        tile = struct.unpack_from(">H", d, off + 6 + 4)[0] & 0x07FF
        assert tile == f * 4, f"puff frame {f} must address tile {f * 4}"


def test_spindash_mappings_are_seven_frames(tmp_path):
    """Every charge frame's mapping must exactly cover its own DPLC's tiles.

    Expected per-frame footprints are derived from the sibling dplc_dust.bin
    artifact rather than hardcoded, so a build_mappings regression that
    corrupts charge frames (while leaving the already-checked puff frames
    correct) is caught: it would either drop below the DPLC's tile count, spill
    a piece past the 12-tile charge window, or leave a frame with no pieces.
    """
    run(tmp_path)
    dm = open(os.path.join(tmp_path, "map_dust_spindash.bin"), "rb").read()
    dd = open(os.path.join(tmp_path, "dplc_dust.bin"), "rb").read()

    n_frames = struct.unpack_from(">H", dm, 0)[0] // 2
    assert n_frames == 7
    assert struct.unpack_from(">H", dd, 0)[0] // 2 == n_frames

    for f in range(n_frames):
        dplc_off = struct.unpack_from(">H", dd, f * 2)[0]
        n_entries = struct.unpack_from(">H", dd, dplc_off)[0]
        expected_tiles = sum(
            ((struct.unpack_from(">H", dd, dplc_off + 2 + e * 2)[0] >> 12) & 0xF) + 1
            for e in range(n_entries))

        map_off = struct.unpack_from(">H", dm, f * 2)[0]
        n_pieces = struct.unpack_from(">H", dm, map_off + 4)[0]
        assert n_pieces >= 1, f"charge frame {f} has no pieces"

        footprint = 0
        for p in range(n_pieces):
            piece_off = map_off + 6 + p * 8
            size = dm[piece_off + 2]
            w = ((size >> 2) & 3) + 1
            h = (size & 3) + 1
            tile = struct.unpack_from(">H", dm, piece_off + 4)[0] & 0x07FF
            assert tile + w * h <= 12, (
                f"charge frame {f} piece {p}: tile {tile} + {w}x{h} footprint "
                "exceeds the 12-tile charge DPLC window (VRAM_DUST_SPINDASH)")
            footprint += w * h

        assert footprint == expected_tiles, (
            f"charge frame {f}: mapping covers {footprint} tiles but the "
            f"frame's own DPLC streams {expected_tiles}")


def test_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    run(a); run(b)
    for name in ("art_dust.bin", "dplc_dust.bin",
                 "map_dust_spindash.bin", "map_dust_puff.bin"):
        assert open(a / name, "rb").read() == open(b / name, "rb").read(), name
