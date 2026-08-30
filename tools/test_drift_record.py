"""Gates over the drift record and its reader (tools/drift_record.py).

WHAT IS UNDER TEST AND WHY IT NEEDS A GATE. sigil's nightly drift job asks this repo
what the ROM bytes should have been. It maps the reader's exit 3 to "no entry" and every
other non-zero to "could not answer"; the first is quiet, the second is NOTHING MEASURED.
A reader that answered 3 when it could not reach its data would turn a broken record into
a clean miss, and the job's own report cannot tell the difference. So the exit codes are
the subject here, not a detail of it.

AND THE SECOND SUBJECT IS THE BIAS DIRECTION. The record feeds a decision about retiring
a byte-identity gate, and every error in it errs toward "the gate is spent". These rows
pin the property that makes that structurally hard: an entry cannot spell "the drift job
observed this", because `origin` has a closed domain in which no member means it and the
names someone would reach for are refused BY NAME.

Every rule below was proven red-first — the guard broken alone in drift_record.py, this
file run, the named row observed failing, the guard restored. Run under
PYTHONDONTWRITEBYTECODE=1; a stale __pycache__ is a measured false-green source in this
tree.
"""

import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
READER = os.path.join(HERE, "drift_record.py")
RECORD = os.path.join(HERE, "drift_record.jsonl")

sys.path.insert(0, HERE)
import drift_record  # noqa: E402

A_KNOWN = "a" * 40
A_OTHER = "b" * 40
S_CLOSURE = "c" * 40
S_LINKED = "d" * 40

EXIT_OK, EXIT_CANNOT, EXIT_MISS = 0, 2, 3


def _entry(**over):
    e = {
        "schema": 1,
        "aeon_rev": A_KNOWN,
        "sigil_linked_rev": S_LINKED,
        "sigil_closure_rev": S_CLOSURE,
        "sigil_tree_state": "clean",
        "origin": "aeon-hand-measurement",
        "measured_on": "2026-08-30",
        "build": "./build.sh",
        "shapes": {"s4": {"crc": "0123abcd", "size": 100}},
        "note": "a fixture",
    }
    e.update(over)
    return e


def _write(tmp_path, *entries, raw=None):
    p = tmp_path / "rec.jsonl"
    p.write_text(raw if raw is not None
                 else "".join(json.dumps(e) + "\n" for e in entries))
    return str(p)


def _run(record, *argv):
    """Invoke the reader exactly as sigil's `_reader()` does: argv appended, stdout
    read, exit code interpreted. cwd is deliberately NOT the repo — the job's cwd is
    its own, so a reader that resolved its record relatively would answer nothing."""
    p = subprocess.run([sys.executable, READER, "--record", record, *argv],
                       capture_output=True, text=True, cwd=os.sep, timeout=120)
    return p.returncode, p.stdout, p.stderr


# ── the closed origin domain: what makes an unobserved chain uncountable ────────────

def test_no_origin_the_record_can_express_is_a_job_observation():
    # The structural claim in one line. If a member of this map is ever True, this
    # record has become able to assert that the drift job observed something — which
    # only sigil's ledger can assert, and which nothing in this repository can write.
    assert drift_record.ORIGIN_IS_JOB_OBSERVATION, "the origin domain must not be empty"
    assert not any(drift_record.ORIGIN_IS_JOB_OBSERVATION.values()), (
        "an origin claiming a drift-job observation is expressible: "
        + repr({k: v for k, v in drift_record.ORIGIN_IS_JOB_OBSERVATION.items() if v}))


def test_the_refused_origin_names_are_disjoint_from_the_allowed_ones():
    assert not (set(drift_record.REFUSED_ORIGINS) & drift_record.ORIGINS)


def test_the_chain_188_credit_is_refused_by_name_and_says_why(tmp_path):
    rec = _write(tmp_path, _entry(origin="chain-188"))
    rc, out, err = _run(rec, "lookup-aeon", A_KNOWN)
    assert rc == EXIT_CANNOT, f"expected 2 (could not answer), got {rc}"
    assert out == "", "a refused record must serve nothing"
    assert "REFUSED" in err and "chain 188" in err


@pytest.mark.parametrize("name", sorted(drift_record.REFUSED_ORIGINS))
def test_every_refused_origin_makes_the_record_unloadable(tmp_path, name):
    rec = _write(tmp_path, _entry(origin=name))
    rc, out, _ = _run(rec, "lookup-aeon", A_KNOWN)
    assert (rc, out) == (EXIT_CANNOT, ""), f"origin {name!r} was served, rc={rc}"


def test_an_unknown_origin_is_refused_rather_than_ignored(tmp_path):
    rec = _write(tmp_path, _entry(origin="whatever-seems-fine"))
    rc, _, err = _run(rec, "lookup-aeon", A_KNOWN)
    assert rc == EXIT_CANNOT and "origin" in err


def test_a_missing_origin_is_refused(tmp_path):
    e = _entry()
    del e["origin"]
    rec = _write(tmp_path, e)
    rc, _, err = _run(rec, "lookup-aeon", A_KNOWN)
    assert rc == EXIT_CANNOT and "origin" in err


def test_the_reader_has_no_verb_that_counts_chains_or_observations():
    # N is sigil's to count, over its own ledger. A verb here that returned a count
    # would be a number this record cannot support, offered where one is wanted.
    assert set(drift_record.VERBS) == set(drift_record.PROTOCOL_VERBS) \
        | set(drift_record.LOCAL_VERBS)
    banned = ("count", "chains", "n", "observations", "observed", "credit")
    assert not [v for v in drift_record.VERBS if v in banned]


def test_the_reader_is_directly_executable_with_a_shebang():
    # sigil's own harness — crates/sigil-cli/tests/drift_nightly_harness.rs,
    # `the_record_seam_is_empty_and_absence_is_not_a_pass` — asserts of the configured
    # value: `reader.is_empty() || Path::new(&reader).exists() || reader.starts_with('/')`.
    # So `DRIFT_RECORD_READER` must be a bare absolute path, not "python3 <path>", and
    # this file must therefore run as argv[0]. Losing the mode bit would break their
    # side with an error naming their config rather than this file.
    assert open(READER, encoding="utf-8").readline().startswith("#!"), "no shebang"
    assert os.access(READER, os.X_OK), (
        "the reader is not executable; sigil's config must name it as a bare absolute "
        "path, so it runs as argv[0] rather than as an argument to an interpreter")
    p = subprocess.run([READER, "--record", RECORD, "shapes"],
                       capture_output=True, text=True, cwd=os.sep, timeout=120)
    assert p.returncode == EXIT_OK and p.stdout.strip(), p.stderr


def test_the_reader_never_opens_the_record_for_writing():
    src = open(READER, encoding="utf-8").read()
    for bad in ('"w"', "'w'", '"a"', "'a'", '"w+"', "'a+'"):
        assert f"open(a.record, {bad}" not in src and f"open(path, {bad}" not in src, (
            f"the reader appears to open its record for writing ({bad}); nothing "
            f"automated may mint an entry")


# ── the three exits, which must never collapse into each other ─────────────────────

def test_a_missing_record_could_not_answer_it_is_not_a_clean_miss(tmp_path):
    rc, out, err = _run(str(tmp_path / "nope.jsonl"), "lookup-aeon", A_KNOWN)
    assert rc == EXIT_CANNOT, (
        f"a reader that cannot reach its data returned {rc}; 3 would read to the job "
        f"as a clean miss and a clean miss is quiet")
    assert out == "" and "does not exist" in err


def test_a_malformed_line_could_not_answer(tmp_path):
    rec = _write(tmp_path, raw=json.dumps(_entry()) + "\n{ not json\n")
    rc, out, err = _run(rec, "lookup-aeon", A_KNOWN)
    assert (rc, out) == (EXIT_CANNOT, "") and "not valid JSON" in err


def test_an_empty_record_could_not_answer_rather_than_missing(tmp_path):
    rec = _write(tmp_path, raw="# only a comment\n\n")
    for verb, args in (("shapes", ()), ("lookup-aeon", (A_KNOWN,)),
                       ("has-sigil", (S_CLOSURE,)), ("lookup", (A_KNOWN, S_CLOSURE))):
        rc, out, _ = _run(rec, verb, *args)
        assert (rc, out) == (EXIT_CANNOT, ""), (
            f"`{verb}` over an empty record returned {rc}; an empty deployment must not "
            f"pass for a clean one")


def test_shapes_never_returns_the_miss_code(tmp_path):
    # sigil's record_shapes() DISCARDS the hit flag, so an exit 3 there becomes "the
    # record covers no shapes" — coverage read out of an absence.
    for rec in (_write(tmp_path, _entry()), str(tmp_path / "gone.jsonl")):
        rc, _, _ = _run(rec, "shapes")
        assert rc != EXIT_MISS, "`shapes` returned 3, which the caller cannot see"


def test_a_genuine_miss_is_three_and_says_nothing(tmp_path):
    rec = _write(tmp_path, _entry())
    rc, out, _ = _run(rec, "lookup-aeon", A_OTHER)
    assert (rc, out) == (EXIT_MISS, "")
    rc, out, _ = _run(rec, "lookup", A_OTHER, S_CLOSURE)
    assert (rc, out) == (EXIT_MISS, "")
    rc, out, _ = _run(rec, "has-sigil", "e" * 40)
    assert (rc, out) == (EXIT_MISS, "")


def test_a_short_revision_could_not_answer_rather_than_missing(tmp_path):
    rec = _write(tmp_path, _entry())
    rc, _, err = _run(rec, "lookup-aeon", A_KNOWN[:8])
    assert rc == EXIT_CANNOT and "40-character" in err


def test_an_unknown_verb_could_not_answer(tmp_path):
    rec = _write(tmp_path, _entry())
    rc, _, err = _run(rec, "lookup-everything", A_KNOWN)
    assert rc == EXIT_CANNOT and "unknown verb" in err


# ── the row shapes the caller parses ───────────────────────────────────────────────

def test_lookup_aeon_emits_four_whitespace_fields_the_caller_can_unpack(tmp_path):
    rec = _write(tmp_path, _entry())
    rc, out, _ = _run(rec, "lookup-aeon", A_KNOWN)
    assert rc == EXIT_OK
    for line in out.splitlines():
        srev, shape, crc, size = line.split()   # exactly the caller's unpack
        assert len(srev) == 40 and shape == "s4" and crc == "0123abcd" and size == "100"


def test_lookup_emits_three_whitespace_fields(tmp_path):
    rec = _write(tmp_path, _entry())
    rc, out, _ = _run(rec, "lookup", A_KNOWN, S_CLOSURE)
    assert rc == EXIT_OK
    for line in out.splitlines():
        shape, crc, size = line.split()
        assert (shape, crc, size) == ("s4", "0123abcd", "100")


def test_lookup_and_has_sigil_key_on_the_closure_revision_only(tmp_path):
    # The job passes `--sigil-closure-rev`. Matching a LINKED revision against it would
    # answer a different question: `revision` moves on docs-only commits no compilation
    # can see, so two byte-identical assemblers key as two.
    rec = _write(tmp_path, _entry())
    assert _run(rec, "lookup", A_KNOWN, S_LINKED)[0] == EXIT_MISS
    assert _run(rec, "has-sigil", S_LINKED)[0] == EXIT_MISS
    assert _run(rec, "has-sigil", S_CLOSURE)[0] == EXIT_OK


def test_an_unknown_closure_revision_is_never_matched_by_key_but_is_still_served(tmp_path):
    rec = _write(tmp_path, _entry(sigil_closure_rev=None))
    assert _run(rec, "has-sigil", S_LINKED)[0] == EXIT_MISS
    assert _run(rec, "lookup", A_KNOWN, S_LINKED)[0] == EXIT_MISS
    rc, out, _ = _run(rec, "lookup-aeon", A_KNOWN)
    assert rc == EXIT_OK and out.split()[0] == S_LINKED


def test_shapes_is_the_union_over_entries(tmp_path):
    rec = _write(tmp_path,
                 _entry(shapes={"s4": {"crc": "00000000", "size": 1}}),
                 _entry(sigil_linked_rev="e" * 40, sigil_closure_rev="f" * 40,
                        shapes={"demo": {"crc": "00000001", "size": 2}}))
    rc, out, _ = _run(rec, "shapes")
    assert (rc, out.split()) == (EXIT_OK, ["demo", "s4"])


# ── schema rules, each refusing rather than degrading ──────────────────────────────

@pytest.mark.parametrize("over,fragment", [
    ({"schema": 2}, "schema"),
    ({"aeon_rev": "ec6a4791"}, "aeon_rev"),
    ({"aeon_rev": "A" * 40}, "aeon_rev"),
    ({"sigil_linked_rev": "zz"}, "sigil_linked_rev"),
    ({"sigil_closure_rev": "short"}, "sigil_closure_rev"),
    ({"sigil_tree_state": "probably-clean"}, "sigil_tree_state"),
    ({"measured_on": "yesterday"}, "measured_on"),
    ({"build": "  "}, "build"),
    ({"note": ""}, "note"),
    ({"shapes": {}}, "shapes"),
    ({"shapes": {"s4": {"crc": "6516FC68", "size": 1}}}, "lowercase hex"),
    ({"shapes": {"s4": {"crc": "651", "size": 1}}}, "lowercase hex"),
    ({"shapes": {"s4": {"crc": "6516fc68", "size": 0}}}, "positive integer"),
    ({"shapes": {"s4": {"crc": "6516fc68", "size": "736315"}}}, "positive integer"),
])
def test_each_schema_rule_refuses_and_names_itself(tmp_path, over, fragment):
    rec = _write(tmp_path, _entry(**over))
    rc, out, err = _run(rec, "lookup-aeon", A_KNOWN)
    assert (rc, out) == (EXIT_CANNOT, ""), f"{over} was accepted, rc={rc}"
    assert fragment in err, f"the refusal does not name {fragment!r}: {err.strip()}"


def test_an_unknown_key_is_refused_so_a_typo_cannot_pass_as_data(tmp_path):
    e = _entry()
    e["orgin"] = "aeon-hand-measurement"
    rec = _write(tmp_path, e)
    rc, _, err = _run(rec, "lookup-aeon", A_KNOWN)
    assert rc == EXIT_CANNOT and "unknown key" in err


def test_two_entries_for_one_build_are_refused_rather_than_picked(tmp_path):
    rec = _write(tmp_path, _entry(), _entry(shapes={"s4": {"crc": "ffffffff",
                                                           "size": 999}}))
    rc, out, err = _run(rec, "lookup-aeon", A_KNOWN)
    assert (rc, out) == (EXIT_CANNOT, "") and "ambiguous" in err


# ── the committed record itself ────────────────────────────────────────────────────

def test_the_committed_record_loads_and_validates():
    rc, out, err = _run(RECORD, "validate")
    assert rc == EXIT_OK, f"the committed record does not load: {err.strip()}"
    assert "record OK" in out


def test_every_committed_entry_declares_an_allowed_non_observation_origin():
    entries = drift_record.load(RECORD)
    assert entries, "the committed record is empty"
    for e in entries:
        assert e["origin"] in drift_record.ORIGINS
        assert drift_record.ORIGIN_IS_JOB_OBSERVATION[e["origin"]] is False


def test_the_committed_record_covers_every_shape_the_job_builds_or_is_short_by_name():
    # sigil's DRIFT_SHAPES (scripts/drift-nightly.conf at 8acee94a). A shape the record
    # covers and the job never builds reads as coverage; a shape the job builds and the
    # record does not cover is NOT a failure here, but it must be visible, because the
    # job renders it as `unmeasured` and unmeasured must never look like quiet.
    job_shapes = {"s4", "s4_debug", "demo", "demo_debug"}
    covered = {s for e in drift_record.load(RECORD) for s in e["shapes"]}
    assert not (covered - job_shapes), (
        "the record covers shapes the nightly job never builds: "
        + repr(sorted(covered - job_shapes)))
    # Reported, not asserted-away: this is the honest partial, and naming it here is
    # what stops it becoming invisible.
    if covered != job_shapes:
        print("NOTE: shapes the job builds and the record does not cover: "
              + repr(sorted(job_shapes - covered)))
