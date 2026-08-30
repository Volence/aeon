"""The decisions ledger, held to the shape the owner's reader accepts — at build time.

`docs/decisions.jsonl` is append-only and committed (contract/DECISIONS.md rule 8). Thirty-one
of its lines do not parse for Dominion's reader and the hub RULED they are not to be repaired
(docs/OVERSEER.md, "THIRTY-ONE LEDGER LINES DO NOT PARSE FOR THE OWNER'S READER — DO NOT
REPAIR THEM"). So the gate has two halves that pull in opposite directions and both matter:

  * nothing NEW may be rejected — the write site (tools/decisions_append.py) is how a line
    gets in, and this is the backstop for a line that bypassed it with a bare `>>`;
  * nothing OLD may be repaired, deleted or moved — a "fix" to a ruled line is the exact act
    the hub forbade, and it would look like progress (the rejected count going DOWN).

THE EXPECTATIONS ARE DERIVED, NOT TYPED. `tools/fixtures/decisions_ruled_unrepaired.json`
is emitted by `decisions_conformance.py --emit-ruled-fixture` from the tool's own measurement
and records the aeon SHA it was generated at. Regenerate it ONLY on a hub ruling that changes
the ruled set (and say so in the commit); regenerating to make a red test green is the repair
by another route.

LINES, NEVER IDS: contract 8c makes repeated ids normal, so every check here is keyed on the
1-based physical line number. An id-keyed version of this measurement once reported 28 for 31.

LOUD ON UNMEASURABLE: a missing fixture or an unreadable ledger FAILS with a sentence. A
skip here would read as green in build.sh's `-q` summary.

Runs in build.sh's tool-suite pytest lane (all four shapes, build-fatal), which collects
`tools/test_*.py` by directory sweep.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import decisions_conformance as conf  # noqa: E402

FIXTURE = TOOLS / "fixtures" / "decisions_ruled_unrepaired.json"
LEDGER = ROOT / "docs" / "decisions.jsonl"


def _fixture() -> dict:
    if not FIXTURE.is_file():
        pytest.fail(f"CANNOT MEASURE: the ruled-set fixture {FIXTURE} is missing. Regenerate it "
                    f"with `python3 tools/decisions_conformance.py --emit-ruled-fixture "
                    f"{FIXTURE.relative_to(ROOT)}` ONLY under a hub ruling; a missing fixture "
                    f"is a failure, never a skip.")
    try:
        f = json.loads(FIXTURE.read_text())
    except (OSError, json.JSONDecodeError) as ex:
        pytest.fail(f"CANNOT MEASURE: the ruled-set fixture {FIXTURE} is unreadable: {ex}")
    for key in ("generated_at_aeon_sha", "line_count", "ids_by_physical_line", "ruled_unrepaired"):
        if key not in f:
            pytest.fail(f"CANNOT MEASURE: fixture {FIXTURE} lacks `{key}`; it was not emitted by "
                        f"decisions_conformance.py --emit-ruled-fixture")
    return f


def _measure() -> list[tuple[int, object, list[str]]]:
    if not LEDGER.is_file():
        pytest.fail(f"CANNOT MEASURE: the ledger {LEDGER} is missing; refusing to report it clean")
    try:
        rows = conf.measure(str(LEDGER))
    except OSError as ex:
        pytest.fail(f"CANNOT MEASURE: the ledger {LEDGER} is unreadable: {ex}")
    if not rows:
        pytest.fail(f"CANNOT MEASURE: the ledger {LEDGER} holds no entries")
    return rows


def _fmt(n, i, e) -> str:
    return f"line {n} {i!r}: {'; '.join(e) if e else 'parses'}"


def test_every_line_after_the_ruled_set_parses():
    """Every line NOT in the ruled set has zero reject reasons. A new rejected line names
    itself here by line number; the fix is to append a conforming entry through
    tools/decisions_append.py (and, since the file is append-only, to leave the bad line
    where it is and add it to the ruled set only under a hub ruling)."""
    f = _fixture()
    ruled = {r["line"] for r in f["ruled_unrepaired"]}
    rows = _measure()
    new_bad = [(n, i, e) for n, i, e in rows if e and n not in ruled]
    assert not new_bad, (
        f"{len(new_bad)} line(s) outside the ruled set are REJECTED by the owner's reader "
        f"(the ruled set is the {len(ruled)} lines in {FIXTURE.name}, generated at aeon "
        f"{f['generated_at_aeon_sha'][:8]}); they reached the ledger without going through "
        f"tools/decisions_append.py:\n  " + "\n  ".join(_fmt(*b) for b in new_bad))


def test_the_ruled_set_is_exactly_where_it_was():
    """Each ruled line still exists, still carries that id, and is still rejected for exactly
    those reasons. A rewrite, deletion or repair of a ruled line (forbidden by the hub) fails
    here by name, and so does a NEW rejected line, since it is not in the fixture."""
    f = _fixture()
    rows = _measure()
    by_line = {n: (i, e) for n, i, e in rows}
    drift = []
    for r in f["ruled_unrepaired"]:
        n, want_id, want_reasons = r["line"], r["id"], r["reasons"]
        if n not in by_line:
            drift.append(f"line {n} ({want_id!r}) no longer exists: the ledger is shorter or the "
                         f"line is blank; the hub ruled these lines are NOT to be repaired")
            continue
        got_id, got_reasons = by_line[n]
        if got_id != want_id:
            drift.append(f"line {n} carried {want_id!r}, now carries {got_id!r}: a ruled line "
                         f"was rewritten, moved, or a line above it was inserted or deleted")
        elif got_reasons != want_reasons:
            drift.append(f"line {n} ({want_id!r}) was rejected for {want_reasons}, now "
                         f"{got_reasons or 'PARSES'}: a ruled line was REPAIRED or altered, "
                         f"which the hub forbade (rule 8: append a superseding entry instead)")
    ruled = {r["line"] for r in f["ruled_unrepaired"]}
    for n, i, e in rows:
        if e and n not in ruled:
            drift.append(f"line {n} ({i!r}) is rejected and is NOT in the ruled set: {'; '.join(e)}")
    assert not drift, (
        f"the ruled-not-to-repair set (fixture generated at aeon {f['generated_at_aeon_sha'][:8]}, "
        f"{len(f['ruled_unrepaired'])} lines) no longer matches the ledger:\n  " + "\n  ".join(drift))


def test_the_ruled_set_count_is_the_measured_one():
    """The fixture was generated from the tool's own output, so its count is the tool's count.
    Pin the number the hub ruled on so a regenerated fixture that silently shrank or grew the
    set is a named change, not a quiet one."""
    f = _fixture()
    assert len(f["ruled_unrepaired"]) == 31, (
        f"the fixture holds {len(f['ruled_unrepaired'])} ruled lines; the hub ruled on 31 "
        f"(docs/OVERSEER.md). If the ruling changed, update this pin in the same commit as the "
        f"regenerated fixture and say which ruling.")


def test_the_ledger_is_append_only():
    """Line count >= the recorded count, and the first N physical lines carry the recorded id
    sequence. A deleted, reordered or inserted line inside the recorded prefix fails by line."""
    f = _fixture()
    _measure()
    ids = conf.physical_ids(str(LEDGER))
    want = f["ids_by_physical_line"]
    n_want = f["line_count"]
    assert len(want) == n_want, (
        f"fixture is inconsistent: line_count {n_want} but {len(want)} ids recorded; it was not "
        f"emitted by decisions_conformance.py --emit-ruled-fixture")
    assert len(ids) >= n_want, (
        f"the ledger has {len(ids)} physical line(s), fewer than the {n_want} recorded at aeon "
        f"{f['generated_at_aeon_sha'][:8]}: a line was DELETED from an append-only file "
        f"(contract rule 8)")
    moved = [(n + 1, w, g) for n, (w, g) in enumerate(zip(want, ids)) if w != g]
    assert not moved, (
        f"{len(moved)} line(s) inside the recorded prefix of {n_want} changed id: the file is "
        f"append-only, so this is a rewrite, insertion or deletion, first at "
        f"line {moved[0][0]} ({moved[0][1]!r} -> {moved[0][2]!r})")


def test_the_write_site_imports_the_reader_predicate_rather_than_copying_it():
    """decisions_append.py must call decisions_conformance.reject_reasons, not carry its own
    copy: a third implementation of Dominion's parser would drift from both the reader and
    the transcription."""
    src = (TOOLS / "decisions_append.py").read_text()
    assert "import decisions_conformance as conf" in src
    assert "conf.reject_reasons(" in src
    assert "def reject_reasons(" not in src, "decisions_append.py carries its own copy of the predicate"
