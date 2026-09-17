"""tools/gate_cut_shape.py: which listings earn a DERIVED cut (STRESS-SHAPES-GATE-CUTS).

Donor-free and build-free: these run in the pre-build pytest lane. The end-to-end half
(each gate deriving a cut on a real stress ROM and executing its sweeps) is evidenced by
`STRESS_EVICT=1 ./build.sh` / `STRESS_ART=1 ./build.sh`, which no canonical lane runs.
"""

import json
import pathlib
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import artifact_provenance  # noqa: E402
import gate_cut_shape as gcs  # noqa: E402

FIXTURES = TOOLS / "fixtures"
CUT_FILES = ("sprite_tilt_cut.json", "instashield_cut.json", "tailsflight_cut.json",
             "loop_crossover_cut.json")


def test_canonical_listings_come_from_the_provenance_table():
    """Derived, not typed: one .lst per CANONICAL_SHAPES .bin."""
    want = {b[:-4] + ".lst" for b in artifact_provenance.CANONICAL_SHAPES}
    assert gcs.canonical_listings() == want
    assert {"s4.lst", "s4.debug.lst"} <= want        # positive control on the mapping


def test_off_canonical_listings_are_build_sh_stress_shapes():
    got = gcs.off_canonical_listings()
    assert got == {"s4.stress.lst", "s4.stressart.lst",
                   "s4.s2clip.lst", "s4.s2clip.debug.lst"}, got
    assert not (got & gcs.canonical_listings())


@pytest.mark.parametrize("lst", ["s4.lst", "s4.debug.lst", "demo.lst", "demo.debug.lst",
                                 "/abs/path/s4.debug.lst"])
def test_canonical_shapes_classify_canonical(lst):
    assert gcs.classify(lst) == gcs.CANONICAL


@pytest.mark.parametrize("lst", ["s4.stress.lst", "some/dir/s4.stressart.lst"])
def test_stress_shapes_classify_off_canonical(lst):
    assert gcs.classify(lst) == gcs.OFF_CANONICAL


@pytest.mark.parametrize("lst", ["s4.debg.lst", "s4.stress.debug.lst", "foo.lst", ""])
def test_an_unrecognised_name_never_earns_a_derived_cut(lst):
    assert gcs.classify(lst) == gcs.CANONICAL


def test_a_computed_rom_name_is_not_read_as_a_fixture_shape(tmp_path):
    """Only a STANDALONE literal assignment declares a fixture shape: the canonical
    names are computed, and one sits inside an if/else line."""
    b = tmp_path / "build.sh"
    b.write_text('if [[ x ]]; then ROM_NAME="s4"; else ROM_NAME="$GAME"; fi\n'
                 'ROM_NAME="${ROM_NAME}.debug"\n'
                 '    ROM_NAME="s4.newfixture"\n')
    assert gcs.off_canonical_listings(b) == {"s4.newfixture.lst"}


def test_sources_that_disagree_are_refused_not_guessed(tmp_path):
    b = tmp_path / "build.sh"
    b.write_text('    ROM_NAME="s4.debug"\n')
    with pytest.raises(gcs.ShapeClassError):
        gcs.off_canonical_listings(b)
    with pytest.raises(gcs.ShapeClassError):
        gcs.classify("s4.stress.lst", b)


@pytest.mark.parametrize("cut", CUT_FILES)
def test_no_off_canonical_cut_is_committed(cut):
    """Off-canonical cuts are derived at gate time, never committed."""
    shapes = set(json.loads((FIXTURES / cut).read_text())["shapes"])
    assert shapes, "%s has no shapes; this row would be vacuous" % cut
    assert not (shapes & gcs.off_canonical_listings()), (cut, sorted(shapes))


# ---- the derive-and-self-check wrapper, on a toy producer/checker ----------------------

#: Rows that want the REAL digest-target corroboration rather than the stub below.
REAL_DIGEST = pytest.mark.real_digest


@pytest.fixture(autouse=True)
def _stress_digest(monkeypatch, request):
    """The toy runs name s4.stress.lst, which does not exist here, so the digest-target
    corroboration is stubbed out for them; the rows that are ABOUT it opt back in.

    ⚠ THE OPT-OUT USED TO BE A NAME PREFIX (`name.startswith("test_digest")`) AND IT
    SILENTLY DISARMED A ROW (2026-09-17). A new row exercising `digest_target_problem`
    was called `test_a_digest_without_a_rom_line_...`, did not match the prefix, got the
    `lambda lst: None` stub, and asserted against the stub's answer instead of the
    function's — a rule keyed to a checkable surface (the name) being blind to what is
    true but off it (the subject). It is a MARKER now: a row says what it wants, and a row
    that forgets loses the subject LOUDLY (it asserts against None) instead of being
    quietly renamed out of its own coverage.
    """
    if request.node.get_closest_marker("real_digest"):
        return
    monkeypatch.setattr(gcs, "digest_target_problem", lambda lst: None)


def _run(tmp_path, capsys, *, committed=(), produce=None, check=None):
    fixture = tmp_path / "toy_cut.json"
    fixture.write_text(json.dumps({"shapes": {k: {} for k in committed}}))
    produce = produce or (lambda p: p.write_text('{"shapes": {"s4.stress.lst": {}}}'))
    check = check or (lambda p: [])
    rc = gcs.derive_for_offcanonical(
        "toy_gate", "s4.stress.lst", str(fixture),
        lambda f: sorted(json.loads(pathlib.Path(f).read_text())["shapes"]),
        produce, check)
    return rc, capsys.readouterr().out


def test_clean_derivation_returns_none_and_is_loud(tmp_path, capsys):
    rc, out = _run(tmp_path, capsys, committed=("s4.lst", "s4.debug.lst"))
    assert rc is None
    assert "OFF-CANONICAL SHAPE 's4.stress.lst'" in out and "DERIVED" in out


def test_a_failed_derivation_is_could_not_run(tmp_path, capsys):
    def boom(p):
        raise KeyError("Player_ApplyTilt")
    rc, out = _run(tmp_path, capsys, produce=boom)
    assert rc == 2 and "COULD NOT RUN" in out


def test_a_derived_cut_that_does_not_check_is_could_not_run(tmp_path, capsys):
    rc, out = _run(tmp_path, capsys, check=lambda p: ["routine differs"])
    assert rc == 2 and "routine differs" in out
    rc, out = _run(tmp_path, capsys, check=lambda p: (_ for _ in ()).throw(SystemExit("x")))
    assert rc == 2


def test_a_committed_off_canonical_cut_is_refused(tmp_path, capsys):
    rc, out = _run(tmp_path, capsys, committed=("s4.lst", "s4.stress.lst"))
    assert rc == 1 and "COMMITTED cut for off-canonical" in out


def _listing(tmp_path, target, rom_path="s4.stress.bin", name="s4.stress.lst"):
    """A minimal listing whose Source Digest parses (the reader's own grammar).

    `rom_path` is the artifact sigil was ASKED to write (DIGEST-ROM path=), which is what
    separates a RENAMED canonical build from a deliberately-built off-canonical one since
    2026-09-17. Defaulting it to the listing's own .bin keeps every pre-existing caller
    modelling a real off-canonical build; a rename is modelled by naming s4.bin here.
    """
    import zlib
    read = "DIGEST-READ crc=00000000 size=0 origin=source path=x.emp"
    agg = "%08x" % (zlib.crc32((read + "\n").encode()) & 0xFFFFFFFF)
    lst = tmp_path / name
    lst.write_text("\n".join([
        "DIGEST-FORMAT 1",
        "DIGEST-ASSEMBLER sigil version=0 revision=0 tree=clean",
        "DIGEST-SHAPE target=%s game=sonic4 debug=1 extra-entries=none" % target,
        "DIGEST-SCAN pattern=*.emp files=1 crc=00000000",
        read,
        "DIGEST-AGGREGATE crc=%s reads=1" % agg,
        "DIGEST-ROM crc=00000000 size=0 path=%s" % rom_path,
        "DIGEST-END", ""]))
    return lst


@REAL_DIGEST
def test_digest_target_of_a_stress_build_is_accepted(tmp_path):
    assert gcs.digest_target_problem(_listing(tmp_path, "stress-evict")) is None


@REAL_DIGEST
def test_digest_canonical_build_under_a_stress_name_is_refused(tmp_path, capsys):
    """A canonical build RENAMED to s4.stress.lst must not earn a derived cut.

    The rename is now modelled properly: sigil was asked for `s4.bin` and the pair was
    renamed afterwards, so the digest still says so. This fixture used to set only
    `target=sonic4` and leave `path=s4.stress.bin`, which does not describe a rename at
    all — it describes an off-canonical build — and it passed only because the rule was
    reading the target as a proxy. It could not tell the two rules apart; it can now.
    """
    lst = _listing(tmp_path, "sonic4", rom_path="s4.bin")
    assert "CANONICAL build target" in gcs.digest_target_problem(lst)
    fixture = tmp_path / "toy_cut.json"
    fixture.write_text('{"shapes": {}}')
    produced = []
    rc = gcs.derive_for_offcanonical("toy_gate", str(lst), str(fixture),
                                     lambda f: [], produced.append, lambda p: [])
    assert rc == 2 and not produced
    assert "COULD NOT RUN" in capsys.readouterr().out


@REAL_DIGEST
def test_digest_of_a_canonical_target_built_as_an_off_canonical_artifact_is_accepted(tmp_path):
    """The S2CLIP clip-act shapes: off-canonical in their ACT DATA, built through the
    canonical `--game sonic4` target, and sigil was asked for THIS artifact.

    This is the case the target proxy could not express. The discriminating pair is this
    row and the rename row above: same target, different DIGEST-ROM path, opposite verdict.
    """
    lst = _listing(tmp_path, "sonic4", rom_path="s4.s2clip.bin", name="s4.s2clip.lst")
    assert gcs.digest_target_problem(lst) is None


@REAL_DIGEST
def test_a_digest_without_a_rom_line_is_refused_by_the_READER(tmp_path):
    """The discriminator cannot go missing: DIGEST-ROM is required by the grammar.

    MEASURED rather than assumed while widening the rule above — the guess was that a
    digest could arrive without a ROM line and that `digest_target_problem` owned that
    case. It does not: the reader's grammar (FORMAT ASSEMBLER SHAPE DEFINE* SCAN READ+
    AGGREGATE ROM END) refuses it first, so the branch in that function is belt and
    braces and this row records WHERE the refusal actually comes from. A future reader
    relaxing the grammar makes that branch live, and this row will say so by changing
    which message it gets.
    """
    import zlib
    read = "DIGEST-READ crc=00000000 size=0 origin=source path=x.emp"
    agg = "%08x" % (zlib.crc32((read + "\n").encode()) & 0xFFFFFFFF)
    lst = tmp_path / "s4.s2clip.lst"
    lst.write_text("\n".join([
        "DIGEST-FORMAT 1",
        "DIGEST-ASSEMBLER sigil version=0 revision=0 tree=clean",
        "DIGEST-SHAPE target=sonic4 game=sonic4 debug=0 extra-entries=none",
        "DIGEST-SCAN pattern=*.emp files=1 crc=00000000",
        read,
        "DIGEST-AGGREGATE crc=%s reads=1" % agg,
        "DIGEST-END", ""]))
    problem = gcs.digest_target_problem(lst)
    assert problem is not None
    assert "cannot be read" in problem and "ROM END" in problem, problem


@REAL_DIGEST
def test_digest_missing_is_refused(tmp_path):
    lst = tmp_path / "s4.stress.lst"
    lst.write_text("no digest here\n")
    assert "cannot be read" in gcs.digest_target_problem(lst)
