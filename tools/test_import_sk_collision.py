import os, subprocess, sys

HERE = os.path.dirname(__file__)
SK = os.path.normpath(os.path.join(HERE, "..", "..", "skdisasm", "Levels", "Misc"))
OUT = os.path.normpath(os.path.join(HERE, "..", "data", "collision"))


def run():
    subprocess.run([sys.executable, os.path.join(HERE, "import_sk_collision.py")], check=True)


def test_tables_byte_match_sk_inputs():
    run()
    assert open(os.path.join(OUT, "heightmaps.bin"), "rb").read() == open(os.path.join(SK, "Height Maps.bin"), "rb").read()
    assert open(os.path.join(OUT, "heightmaps_rot.bin"), "rb").read() == open(os.path.join(SK, "Height Maps Rotated.bin"), "rb").read()
    assert open(os.path.join(OUT, "angles.bin"), "rb").read() == open(os.path.join(SK, "angles.bin"), "rb").read()


def test_solidity_all_except_air():
    run()
    hm = open(os.path.join(OUT, "heightmaps.bin"), "rb").read()
    sol = open(os.path.join(OUT, "solidity.bin"), "rb").read()
    assert len(sol) == 256
    for i in range(256):
        shape = hm[i * 16:(i + 1) * 16]
        air = (i == 0) or not any(shape)
        assert sol[i] == (0 if air else 3), f"shape {i}: solidity {sol[i]}"
