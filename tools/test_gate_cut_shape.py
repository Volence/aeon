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
CUT_FILES = ("sprite_tilt_cut.json", "instashield_cut.json", "tailsflight_cut.json")


def test_canonical_listings_come_from_the_provenance_table():
    """Derived, not typed: one .lst per CANONICAL_SHAPES .bin."""
    want = {b[:-4] + ".lst" for b in artifact_provenance.CANONICAL_SHAPES}
    assert gcs.canonical_listings() == want
    assert {"s4.lst", "s4.debug.lst"} <= want        # positive control on the mapping


def test_off_canonical_listings_are_build_sh_stress_shapes():
    got = gcs.off_canonical_listings()
    assert got == {"s4.stress.lst", "s4.stressart.lst",
                   "s4.s2clip.lst", "s4.s2clip.debug.lst",
                   "s4.stressobj.lst", "s4.stressobj.debug.lst",
                   "s4.sidekick.lst", "s4.sidekick.debug.lst",
                   "s4.configa.lst", "s4.configb.lst"}, got
    assert not (got & gcs.canonical_listings())


def test_every_non_canonical_outputs_stem_is_off_canonical():
    """G0b Task 10: build.sh writes a description row's `[outputs]` stem (SHAPE=config-a ->
    s4.configa), computed, not a literal. Expectations from source: every stem a
    games/*/game.toml `[outputs]` row names that is not a CANONICAL_SHAPES artifact is
    off-canonical; the canonical ones are not."""
    import tomllib
    canonical = {b[:-4] for b in artifact_provenance.CANONICAL_SHAPES}
    got = gcs.off_canonical_listings()
    stems = set()
    for desc in sorted((gcs.AEON / "games").glob("*/game.toml")):
        stems |= set(tomllib.loads(desc.read_text()).get("outputs", {}).values())
    assert {"s4.configa", "s4.configb"} <= stems     # positive control: the rows exist
    for stem in stems:
        assert ((stem + ".lst") in got) == (stem not in canonical), (stem, sorted(got))


def test_an_outputs_stem_that_is_canonical_elsewhere_is_refused(tmp_path):
    """A description naming a canonical artifact under a non-canonical row is two sources
    disagreeing: refused, not classified."""
    (tmp_path / "games" / "sonic4").mkdir(parents=True)
    (tmp_path / "games" / "sonic4" / "game.toml").write_text(
        '[outputs]\nrelease = "s4"\ndebug = "s4.debug"\nconfig-a = "demo"\n')
    (tmp_path / "build.sh").write_text("")
    with pytest.raises(gcs.ShapeClassError, match="demo"):
        gcs.off_canonical_listings(tmp_path / "build.sh")


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


def _listing(tmp_path, target, rom_path="s4.stress.bin", name="s4.stress.lst", game="sonic4"):
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
        "DIGEST-SHAPE target=%s game=%s debug=1 extra-entries=none" % (target, game),
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
    lst = _listing(tmp_path, "release", rom_path="s4.bin")
    assert "CANONICAL build target" in gcs.digest_target_problem(lst)
    fixture = tmp_path / "toy_cut.json"
    fixture.write_text('{"shapes": {}}')
    produced = []
    rc = gcs.derive_for_offcanonical("toy_gate", str(lst), str(fixture),
                                     lambda f: [], produced.append, lambda p: [])
    assert rc == 2 and not produced
    assert "COULD NOT RUN" in capsys.readouterr().out


def test_a_canonical_artifact_no_outputs_row_names_is_refused(tmp_path, monkeypatch):
    """Loud on unmeasurable: a canonical artifact whose game description names no row for
    it cannot be keyed in the new spelling, and that is refused, not skipped. With the
    profile-driven `(game, game)` spelling gone (G0b Task 10) this is the only way the key
    can fail, so it is held for both counts the rule refuses: no row, and two rows."""
    games = tmp_path / "games"
    for g, outputs in (("sonic4", 'release = "s4"\ndebug = "s4.debug"\n'), ("demo", 'release = "demo"\n')):
        (games / g).mkdir(parents=True)
        (games / g / "game.toml").write_text("[outputs]\n" + outputs)
    monkeypatch.setattr(gcs, "AEON", tmp_path)
    with pytest.raises(gcs.ShapeClassError, match=r"0 row\(s\) naming 'demo.debug'"):
        gcs.canonical_build_ids()
    (games / "demo" / "game.toml").write_text(
        '[outputs]\nrelease = "demo"\ndebug = "demo.debug"\nalias = "demo.debug"\n')
    with pytest.raises(gcs.ShapeClassError, match=r"2 row\(s\) naming 'demo.debug'"):
        gcs.canonical_build_ids()


@REAL_DIGEST
def test_digest_of_a_canonical_target_built_as_an_off_canonical_artifact_is_accepted(tmp_path):
    """The S2CLIP clip-act shapes: off-canonical in their ACT DATA, built through the
    canonical sonic4 target (`--project games/sonic4 --shape release|debug`), and sigil was
    asked for THIS artifact.

    This is the case the target proxy could not express. The discriminating pair is this
    row and the rename row above: same target, different DIGEST-ROM path, opposite verdict.
    """
    lst = _listing(tmp_path, "release", rom_path="s4.s2clip.bin", name="s4.s2clip.lst")
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
        "DIGEST-SHAPE target=release game=sonic4 debug=0 extra-entries=none",
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


# ── G0b: the game-as-data driver names a build by its `[shapes.*]` row ──
#
# sigil's game-as-data driver (`sigil build --project games/<g> --shape <row>`) writes
# `DIGEST-SHAPE target=<row> game=<g>`, where the profile-driven driver wrote
# `target=<g>` (sigil docs/QUEUE.md G0B-COMPARE-IDENTITY-NAMES). Keyed on the target word
# alone, a canonical demo build under the new name reads as NOT canonical, so a renamed
# canonical artifact silently earns a derived cut. The key is (game, target). Task 8 took
# both spellings; since Task 10 (the sonic4 cutover) build.sh builds every shape through
# `--project`, so only (game, <the [outputs] row>) is canonical.


@REAL_DIGEST
@pytest.mark.parametrize("game,row,stem", [("demo", "release", "demo"), ("demo", "debug", "demo.debug"),
                                           ("sonic4", "release", "s4"), ("sonic4", "debug", "s4.debug")])
def test_a_canonical_build_under_its_shape_row_name_renamed_is_refused(tmp_path, capsys, game, row, stem):
    """A canonical build written by the game-as-data driver (target=<row>), renamed to an
    off-canonical listing name: the rename guard must still fire."""
    lst = _listing(tmp_path, row, rom_path=stem + ".bin", game=game)
    problem = gcs.digest_target_problem(lst)
    assert problem is not None and "CANONICAL build target" in problem, problem
    fixture = tmp_path / "toy_cut.json"
    fixture.write_text('{"shapes": {}}')
    produced = []
    rc = gcs.derive_for_offcanonical("toy_gate", str(lst), str(fixture),
                                     lambda f: [], produced.append, lambda p: [])
    assert rc == 2 and not produced
    assert "COULD NOT RUN" in capsys.readouterr().out


@REAL_DIGEST
def test_an_off_canonical_row_spelled_the_new_way_is_accepted(tmp_path):
    """sonic4's `stress-evict` row (target=stress-evict, game=sonic4) is off-canonical in
    both spellings."""
    assert gcs.digest_target_problem(_listing(tmp_path, "stress-evict", game="sonic4")) is None


def test_canonical_build_ids_are_the_outputs_rows_only():
    """Expectations from source: each CANONICAL_SHAPES artifact is canonical as exactly
    (game, the games/<game>/game.toml [outputs] row naming its stem), and as nothing else:
    the profile-driven spelling (game, game) was retired with the sonic4 cutover."""
    import tomllib
    ids = gcs.canonical_build_ids()
    want = set()
    for rom, (game, _debug) in artifact_provenance.CANONICAL_SHAPES.items():
        outputs = tomllib.loads((gcs.AEON / "games" / game / "game.toml").read_text())["outputs"]
        rows = [r for r, stem in outputs.items() if stem == rom[:-len(".bin")]]
        assert len(rows) == 1, (rom, outputs)
        want.add((game, rows[0]))
        assert (game, game) not in ids, (rom, sorted(ids))
    assert ids == want, sorted(ids)
    # A row naming no canonical artifact (the stress and config shapes) is not canonical.
    assert ("sonic4", "stress-evict") not in ids and ("sonic4", "config-a") not in ids


@REAL_DIGEST
@pytest.mark.parametrize("game", ["sonic4", "demo"])
def test_the_profile_driven_spelling_is_not_a_canonical_build(tmp_path, game):
    """`target=<game>` is what the retired build.sh path wrote; no build.sh build writes it
    since the cutover, so it is not a canonical build id (a --legacy listing from sigil's
    comparison job is not a canonical build either). The rename guard keys on the new
    spelling alone, which the rows above prove still fires."""
    lst = _listing(tmp_path, game, rom_path="s4.bin", game=game)
    assert gcs.digest_target_problem(lst) is None


@REAL_DIGEST
def test_a_digest_shape_without_a_game_is_refused_by_the_READER(tmp_path):
    """The key is (game, target): a DIGEST-SHAPE without `game=` cannot be keyed, and must
    not read as "not canonical" (which would earn a derived cut).

    MEASURED (G0b Task 10, the "listing without game=" path the brief named): the reader
    refuses it first (artifact_provenance requires `target game debug extra-entries` on the
    SHAPE line), so `digest_target_problem`'s own missing-game branch is belt and braces,
    as the ROM-line row above records for DIGEST-ROM. A reader relaxing the grammar makes
    that branch live, and this row will say so by changing which message it gets."""
    lst = _listing(tmp_path, "release", rom_path="s4.bin")
    lst.write_text(lst.read_text().replace(" game=sonic4 ", " "))
    problem = gcs.digest_target_problem(lst)
    assert problem is not None
    assert "cannot be read" in problem and "['game']" in problem, problem
