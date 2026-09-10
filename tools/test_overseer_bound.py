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

THE RATCHET IS RETIRED, 2026-09-10. Card 7 was answered by the owner on
2026-09-04T15:38:47Z ("7. Sounds fine") with a cut axis rather than a raised bound: the
boot read is SPLIT BY WHEN A RULE IS READ. aeon made that cut the same way the other five
lanes did — `docs/OVERSEER.md` keeps only what a fresh session needs TO ACT AT BOOT, and
everything read at a later, specific moment (the landing lane, the instruments, the
worktree quirks, the review bars) is in `docs/OVERSEER-REFERENCE.md`. 114,267 B -> 11,347 B,
proved lossless by oracle's `tools/prove_doc_split.py`. So this file now does what its own
instruction said to do on the day the card was answered: RATCHET_BYTES is deleted and the
gate asserts BOOT_READ_BOUND_BYTES directly. There is no second constant to keep in step.

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
        f"  THE AXIS IS *WHEN A RULE IS READ*, never size and never what is 'movable'\n"
        f"  (owner, 2026-09-04T15:38:47Z, card 7). This file keeps only what a fresh\n"
        f"  session needs TO ACT AT BOOT: scope, the queue, any resume brief, and the\n"
        f"  standing rulings that change what a session does FIRST. Anything read at a\n"
        f"  later, specific moment — how to land, how to dispatch, the review bars —\n"
        f"  belongs in docs/OVERSEER-REFERENCE.md, named from here by path. Dated\n"
        f"  precedent narratives belong in docs/OVERSEER-LOG.md.\n"
        f"  DO NOT TRIM A RULING TO HIT THIS NUMBER — every rule survives the cut\n"
        f"  somewhere; the only choice is which file it lives in.\n"
        f"  Prove any split lossless with oracle/tools/prove_doc_split.py, run from THIS\n"
        f"  repo by absolute path, and prove it at a unit BELOW the one you cut at.\n"
        f"  JUDGE BY BYTES: unwrapping a one-line bullet raises the line\n"
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


def test_overseer_md_is_within_the_ruled_boot_read_bound():
    """THE GATE. The boot read is held to the SUITE-RULED bound, with no second constant.

    This was a growth ratchet (RATCHET_BYTES = 114_320) from 2026-09-03 until the cut of
    2026-09-10, because the file was over the bound on a question only the owner could
    answer. He answered it on 2026-09-04 with an axis rather than a number, the cut was
    made, and this file's own instruction was then followed to the letter: the ratchet
    constant is DELETED and the assertion points at BOOT_READ_BOUND_BYTES.

    Why deleting it was right rather than merely tidy: a ratchet pinned ABOVE the bound
    silently permits regrowth back into breach, so once the file is compliant the looser
    of the two constants is the one that decides — which is a gate that reads as green
    while guarding nothing.
    """
    size_bytes, lines = measure(BOOT_READ)
    headroom = BOOT_READ_BOUND_BYTES - size_bytes
    report = (
        f"\n{BOOT_READ} is {size_bytes:,} bytes ({lines:,} lines, reported not gated).\n"
        f"  ruled bound   {BOOT_READ_BOUND_BYTES:,} — headroom {headroom:,} bytes.\n"
    )
    print(report)
    assert not over_bound(size_bytes), report + "\n" + _verdict(BOOT_READ, size_bytes, lines)


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
