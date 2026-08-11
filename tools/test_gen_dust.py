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
    """S3K indices 1/12/13 must become 6/4/7; nothing else may appear."""
    run(tmp_path)
    data = open(os.path.join(tmp_path, "art_dust.bin"), "rb").read()
    seen = set()
    for b in data:
        seen.add(b >> 4)
        seen.add(b & 0xF)
    assert seen <= {0, 6, 4, 7}, f"unexpected palette indices: {sorted(seen)}"
    # and the three non-transparent ones must all be present
    assert {6, 4, 7} <= seen


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
    run(tmp_path)
    d = open(os.path.join(tmp_path, "map_dust_spindash.bin"), "rb").read()
    assert struct.unpack_from(">H", d, 0)[0] // 2 == 7


def test_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    run(a); run(b)
    for name in ("art_dust.bin", "dplc_dust.bin",
                 "map_dust_spindash.bin", "map_dust_puff.bin"):
        assert open(a / name, "rb").read() == open(b / name, "rb").read(), name
