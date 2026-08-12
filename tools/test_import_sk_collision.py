import os, subprocess, sys

HERE = os.path.dirname(__file__)
# Honor the same donor override the tool itself honors (worktree checkouts sit
# under .claude/worktrees/, where the ../../skdisasm default resolves wrong).
_SK_ROOT = os.environ.get(
    "AEON_SKDISASM_DIR",
    os.path.normpath(os.path.join(HERE, "..", "..", "skdisasm")))
SK = os.path.join(_SK_ROOT, "Levels", "Misc")

# NOTE: this test writes to a TMPDIR, never to games/sonic4/data/collision.
#
# It used to run the importer with no output argument, which defaults into the
# repo — and the importer's runtime tables are only DEFAULTS: gen_collision_data
# .generate() overwrites them with the per-section bake, and the COMMITTED bytes
# are the baked ones. So `pytest tools/` silently reverted the bake and left four
# tracked build inputs dirty with the raw S&K import. Because those files are
# build inputs, a build in that state produces a ROM that diverges from the frozen
# goldens and turns ~10 sigil port targets red — a trap that cost real debugging
# time on 2026-08-11 (it looked like a stray background process rewriting the
# repo). The importer now takes an output dir; the tests pass a tmp one.


def run(out_dir):
    subprocess.run(
        [sys.executable, os.path.join(HERE, "import_sk_collision.py"), str(out_dir)],
        check=True)


def test_tables_byte_match_sk_inputs(tmp_path):
    run(tmp_path)
    out = str(tmp_path)
    assert open(os.path.join(out, "heightmaps.bin"), "rb").read() == open(os.path.join(SK, "Height Maps.bin"), "rb").read()
    assert open(os.path.join(out, "heightmaps_rot.bin"), "rb").read() == open(os.path.join(SK, "Height Maps Rotated.bin"), "rb").read()
    assert open(os.path.join(out, "angles.bin"), "rb").read() == open(os.path.join(SK, "angles.bin"), "rb").read()


def test_solidity_all_except_air(tmp_path):
    run(tmp_path)
    out = str(tmp_path)
    hm = open(os.path.join(out, "heightmaps.bin"), "rb").read()
    sol = open(os.path.join(out, "solidity.bin"), "rb").read()
    assert len(sol) == 256
    for i in range(256):
        shape = hm[i * 16:(i + 1) * 16]
        air = (i == 0) or not any(shape)
        assert sol[i] == (0 if air else 3), f"shape {i}: solidity {sol[i]}"


def test_importer_does_not_write_into_the_repo(tmp_path):
    """The regression guard for the trap above: importing into a tmp dir must
    leave the in-repo collision tables untouched. Without this, the next person
    to 'simplify' the default argument away reintroduces a dirty-tree bug whose
    symptom (10 red sigil targets) points nowhere near this file."""
    repo_coll = os.path.normpath(
        os.path.join(HERE, "..", "games", "sonic4", "data", "collision"))
    names = ("heightmaps.bin", "heightmaps_rot.bin", "angles.bin", "solidity.bin")
    before = {n: open(os.path.join(repo_coll, n), "rb").read() for n in names}
    run(tmp_path)
    for n in names:
        assert open(os.path.join(repo_coll, n), "rb").read() == before[n], \
            f"the importer wrote {n} into the repo despite being given {tmp_path}"
