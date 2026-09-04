"""The boot read is bounded — gate it here, because the ruling had no gate anywhere.

WHY THIS FILE EXISTS. The suite ruled on 2026-09-02 that `docs/OVERSEER.md` — the file
every overseer session reads whole at boot — stays under the boot-read bound, and that
each lane copies the check into its own gate. empyrean, sigil, oracle and aurora split
their files; **aeon never wired the check**. The rule was therefore in force and
unenforced, which is exactly why this repo's copy sat over the bound for days (114,357 B
on 2026-09-03, 118,205 B on 2026-09-04) with nothing saying so. A rule that lives only in
a ruling is not in force for your successor — this repo's own standing ruling, arriving
on the ruling that stated it.

THE RULING, read at a committed revision and never through the sibling path:

    git -C ../empyrean fetch -q origin && \
      git -C ../empyrean show origin/main:docs/OVERSEER-PROTOCOL.md

    Section "The boot read is bounded" (owner, 2026-09-02):
      "docs/OVERSEER.md is the boot read, and it stays under about 900 lines / 100 KB."
      "Judge by bytes. Unwrapping a multi-kilobyte one-line bullet into prose RAISES the
       line count while cutting bytes ... so the line half of the bound can move the wrong
       way under a correct fix."

BYTES ONLY. Per that warning the line half is reported as a RESIDUAL and is never
asserted: a correct fix can raise it. Anything that gates on lines punishes the fix.

The bound is stated in the protocol as prose, so it cannot be computed from an artifact.
It is written ONCE below, with its citation, and every expectation in this file —
the failure text, the fixtures, both directions of the two-directional test — is derived
from that name. Nothing in this file re-types the number. That is bar 1 ("derived, never
copied") pointed at a bound whose only source is a sentence.
"""

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# THE RULED BOUND. empyrean docs/OVERSEER-PROTOCOL.md, "The boot read is bounded",
# read at origin/main on 2026-09-04: "it stays under about 900 lines / 100 KB".
# 100 KB is taken as 100,000 bytes (the decimal reading, the stricter of the two;
# the KiB reading would be 102,400). If the suite ever restates the bound, change
# it HERE and nowhere else — every expectation below is computed from this name.
BOOT_READ_BOUND_BYTES = 100_000

# Reported beside the bytes, never asserted. The protocol's "about 900 lines".
BOOT_READ_LINES_GUIDE = 900

REPO_ROOT = Path(__file__).resolve().parent.parent
BOOT_READ = REPO_ROOT / "docs" / "OVERSEER.md"


def measure(path: Path) -> tuple[int, int]:
    """(bytes, lines) of `path`. Raises if it cannot be read — never returns a guess."""
    data = path.read_bytes()
    return len(data), data.count(b"\n")


def over_bound(size_bytes: int) -> bool:
    """The whole predicate, in one place, so both directions test the same thing."""
    return size_bytes > BOOT_READ_BOUND_BYTES


def _verdict(path: Path, size_bytes: int, lines: int) -> str:
    over = size_bytes - BOOT_READ_BOUND_BYTES
    return (
        f"{path} is {size_bytes:,} bytes against the suite's boot-read bound of "
        f"{BOOT_READ_BOUND_BYTES:,} bytes — {over:,} OVER.\n"
        f"  residual (NOT gated): {lines:,} lines against the protocol's guide of "
        f"about {BOOT_READ_LINES_GUIDE:,}.\n"
        f"  The bound is empyrean docs/OVERSEER-PROTOCOL.md, section 'The boot read is "
        f"bounded'. Read it at a committed revision:\n"
        f"    git -C ../empyrean show origin/main:docs/OVERSEER-PROTOCOL.md\n"
        f"  The fix is that section's split procedure, in its order: move the dated tail\n"
        f"  whole to docs/OVERSEER-LOG.md; MEASURE before pointer-ising any bar (only\n"
        f"  lines a grep finds verbatim in the protocol qualify); move closed history\n"
        f"  around a live rule verbatim, keeping the rule. Live repo-specific rulings\n"
        f"  interleaved with narrative are the OWNER'S parcel — report the residual\n"
        f"  rather than trimming a ruling to hit this number.\n"
        f"  Prove any split lossless by set-difference against the committed file before\n"
        f"  committing. JUDGE BY BYTES: unwrapping a one-line bullet raises the line\n"
        f"  count while cutting bytes, so the line figure above can move the wrong way\n"
        f"  under a correct fix and is reported, never asserted."
    )


def test_the_boot_read_exists_and_is_measurable():
    """Loud on unmeasurable. A missing boot read FAILS; it never skips or passes.

    The failure this guards is the one the whole suite keeps re-finding: an absent
    instrument reported as a green result. A gate that cannot see its subject has not
    passed, it has not run.
    """
    assert BOOT_READ.is_file(), (
        f"{BOOT_READ} does not exist (or is not a regular file). The boot read is the "
        f"file every overseer session reads first; its absence is a failure, not a skip. "
        f"If it moved, this gate moves with it."
    )
    size_bytes, _ = measure(BOOT_READ)
    assert size_bytes > 0, f"{BOOT_READ} is empty — that is a broken boot read, not a small one."


# THE RATCHET, in force until the owner answers the suite-wide card 7 (split the rules
# into a second boot file, or raise the bound — one call for all six lanes).
#
# WHY THIS IS NOT THE RULED BOUND YET, and why it is NOT report-only either. The file is
# over the ruled 100,000 B and the residual is 14,320 B of LIVE RULINGS interleaved with
# narrative, which the protocol names as the owner's parcel: the bound exists to make the
# boot read cheap, not to make rulings disappear. So this gate cannot assert the ruled
# bound today without failing the build for every lane on a question only he can answer.
#
# The hub's first ruling was to merge it REPORT-ONLY. That was declined and the deviation
# ratified, on this ground: a check that cannot fail is green by construction, so its
# presence and its absence read the same — which is exactly the property that let the
# MISSING gate go unnoticed here for days. Replacing an absent gate with an unfailable one
# changes what a reader sees and not what is true.
#
# So the ratchet pins the MEASURED residual. It is failable today, by growth, which is the
# live risk while the question is open: fifteen lines were added to this file on 2026-09-04
# by someone who did not know it was over, and nothing stopped them. The distance to the
# ruled bound prints beside the verdict on every run, pass or fail.
#
# THE DAY CARD 7 IS ANSWERED: delete RATCHET_BYTES and point this at
# BOOT_READ_BOUND_BYTES. One constant. The ratchet's whole job is to guarantee the file has
# not drifted further in the meantime.
RATCHET_BYTES = 114_320


def test_overseer_md_does_not_grow_while_the_bound_question_is_open():
    """THE GATE, in its ratchet form. The boot read may not GROW past the measured
    residual, and the distance to the ruled bound is reported either way."""
    size_bytes, lines = measure(BOOT_READ)
    residual = size_bytes - BOOT_READ_BOUND_BYTES
    report = (
        f"\n{BOOT_READ} is {size_bytes:,} bytes ({lines:,} lines, reported not gated).\n"
        f"  ruled bound   {BOOT_READ_BOUND_BYTES:,} — residual {residual:,} OVER, "
        f"owner's card 7.\n"
        f"  ratchet       {RATCHET_BYTES:,} — this gate fails only on GROWTH past it.\n"
    )
    print(report)
    assert size_bytes <= RATCHET_BYTES, (
        report
        + f"\nGREW by {size_bytes - RATCHET_BYTES:,} bytes past the ratchet.\n"
        "The boot read is already over the suite-ruled bound and is waiting on the owner. "
        "Do not add to it: move the content to docs/OVERSEER-LOG.md, or lower RATCHET_BYTES "
        "if you SHRANK the file and want the new floor held."
    )


def test_the_ratchet_is_never_looser_than_the_ruled_bound_once_it_is_met():
    """The ratchet must not outlive its purpose. If the file ever reaches the ruled bound,
    a ratchet ABOVE that bound would silently permit regrowth back into breach — so this
    fails the moment the ratchet becomes the weaker of the two, which is the day someone
    should be deleting it."""
    size_bytes, _ = measure(BOOT_READ)
    if size_bytes <= BOOT_READ_BOUND_BYTES:
        assert RATCHET_BYTES <= BOOT_READ_BOUND_BYTES, (
            f"{BOOT_READ} is now {size_bytes:,} bytes, within the ruled "
            f"{BOOT_READ_BOUND_BYTES:,} — but RATCHET_BYTES is {RATCHET_BYTES:,}, which is "
            "LOOSER than the bound and would permit regrowth into breach. The residual is "
            "settled: delete RATCHET_BYTES and assert BOOT_READ_BOUND_BYTES directly."
        )


def test_the_bound_check_is_two_directional(tmp_path):
    """A bound test that fixes its input is one-directional, and the direction it cannot
    see is the one that leaves it GREEN (this repo's own bar, added 2026-08-27).

    So the fixtures are derived from BOOT_READ_BOUND_BYTES rather than authored: the
    over-long case is BOUND+1, not a literal. Move the constant either way and this test
    tracks it; re-author a fixture and it tracks neither.
    """
    at_bound = tmp_path / "at_bound.md"
    at_bound.write_bytes(b"x" * BOOT_READ_BOUND_BYTES)
    assert measure(at_bound) == (BOOT_READ_BOUND_BYTES, 0)
    assert not over_bound(BOOT_READ_BOUND_BYTES), "the bound itself must PASS — 'under' is inclusive here"

    under = tmp_path / "under.md"
    under.write_bytes(b"x" * (BOOT_READ_BOUND_BYTES - 1))
    assert not over_bound(measure(under)[0])

    over = tmp_path / "over.md"
    over.write_bytes(b"x" * (BOOT_READ_BOUND_BYTES + 1))
    assert over_bound(measure(over)[0]), (
        "one byte over the bound must FAIL — a bound test that only ever sees compliant "
        "input cannot tell you the gate works"
    )

    # And the verdict text must name the file and both numbers, or a reader cannot act on it.
    text = _verdict(over, BOOT_READ_BOUND_BYTES + 1, 0)
    assert str(over) in text
    assert f"{BOOT_READ_BOUND_BYTES + 1:,}" in text, "the verdict must report the ACTUAL size"
    assert f"{BOOT_READ_BOUND_BYTES:,}" in text, "the verdict must report the BOUND"
    assert "residual (NOT gated)" in text, "the line count must be reported as a residual"


def test_the_gate_never_asserts_the_line_count():
    """The protocol warns the line half can move the wrong way under a correct fix, so
    the guide is REPORTED and never gated. This test is what stops a later hand from
    'tightening' the gate by adding a line assertion.

    A file well over the line guide but under the byte bound must PASS.
    """
    many_short_lines = BOOT_READ_LINES_GUIDE * 3
    body = b"a\n" * many_short_lines
    assert len(body) < BOOT_READ_BOUND_BYTES
    assert not over_bound(len(body)), (
        "a file with three times the line guide but comfortably under the byte bound must "
        "PASS — the gate is bytes only"
    )


def test_reading_a_missing_file_raises_rather_than_returning_a_number(tmp_path):
    """measure() must never manufacture a measurement for a file that is not there."""
    with pytest.raises(OSError):
        measure(tmp_path / "no-such-file.md")
