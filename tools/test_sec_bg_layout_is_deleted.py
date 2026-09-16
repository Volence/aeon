"""`sec_bg_layout` is gone from the .emp CODE — the readable half of step 3's guard.

Regions part 2, step 3 (2026-09-16) moved the background from the section to the region
and deleted `Sec.sec_bg_layout`. The step table asks for "build red if any `.emp` still
names `sec_bg_layout`". The build already IS red for every spelling measured — but for
one of them it is red with a message that does not mention the field, which is what this
file exists to fix.

MEASURED, against the release sigil that builds this tree, with the control run LAST so
it is the control and not the subject:

    | probe                                                  | result                     |
    |--------------------------------------------------------|----------------------------|
    | `offsetof(Sec, sec_bg_layout)`, poison via --extra-entry| [Error] offsetof: struct   |
    |                                                        | Sec has no field           |
    |                                                        | sec_bg_layout  (1 error)   |
    | `movea.l Sec.sec_bg_layout(a0), a1` in a REACHABLE      | RED — "the contract        |
    | module (engine/level/section.emp)                      | closure DROPPED 1          |
    |                                                        | instruction(s)". NO field  |
    |                                                        | diagnostic anywhere.       |
    | the same line in an UNREACHABLE module                  | RED, same message          |
    | CONTROL: the same unreachable module reading            | GREEN, exit 0, no drop     |
    | `Sec.sec_objects(a0)` instead                          |                            |

So the `Struct.field(aN)` DISPLACEMENT form does not raise a field-resolution error at
all; it survives elaboration and is stopped later, by the contract-closure analysis
noticing an instruction it cannot read. That is a red — the tree is safe — but the author
gets an instruction COUNT and has to work out which name caused it. This test is the
artifact that says the name.

WHAT EACH ARTIFACT COVERS, so no one reads one as the other:

* `games/sonic4/test/poison/poison_sec_bg_layout.emp` (registered in
  `tools/emp_expect_fail.py`) is the STRONG half: it proves the name does not resolve on
  the TYPE, on every canonical build and before every merge, and it is the only one of
  the two that would still fire if this file were deleted.
* THIS is the READABLE half. It names the file, the line and the field. It is blind to a
  rename, and it is deliberately blind to COMMENTS — a history note saying where the
  field went is exactly what a reader grepping for the old name should find, and a test
  that forbade it would delete the signpost at the junction where people take the wrong
  turn.

Not a `needs_build` test: it reads source, so it runs in the pre-build lane.
"""
import pathlib
import re

import pytest

TOOLS = pathlib.Path(__file__).resolve().parent
AEON = TOOLS.parent

NAME = "sec_bg_layout"

# Line comments only. `.emp` has no block comment, and a `//` inside a string literal is
# not something any line in this tree does with this name — the one construct that could
# (an `ensure` MESSAGE naming the field) is caught by the string-literal strip below, which
# runs first for exactly that reason.
_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')


def _code_only(line: str) -> str:
    """The instruction half of a line: string literals blanked, then the `//` tail cut.

    Strings go first. An `ensure` message is prose that happens to live inside quotes, and
    prose is allowed to name the field for the same reason a comment is.
    """
    return _STRING.sub('""', line).split("//", 1)[0]


# THE ONE FILE ALLOWED TO NAME IT IN CODE, and not as a convenience exemption: that
# module's whole job is to assert the name does not resolve, so it has to write it down.
# The first test below asserts the file is still there rather than skipping quietly — if
# it goes, the strong half of the guard went with it.
POISON = AEON / "games" / "sonic4" / "test" / "poison" / "poison_sec_bg_layout.emp"


def _emp_sources() -> list[pathlib.Path]:
    """Every .emp under engine/ and games/ — the whole .emp surface of the tree.

    Walked, not listed. A list of the files that used to carry the field cannot contain
    the file nobody thought of, which is the only kind this test is useful against.
    """
    out: list[pathlib.Path] = []
    for root in ("engine", "games"):
        out.extend(sorted((AEON / root).rglob("*.emp")))
    return out


def test_the_poison_that_proves_the_deletion_still_exists():
    """The strong half must be present for this half's exemption to be honest."""
    assert POISON.is_file(), (
        f"{POISON.relative_to(AEON)} is missing. That module is the BUILD-level guard that "
        f"`Sec.{NAME}` stays deleted (registered in tools/emp_expect_fail.py's CASES). "
        f"Without it this grep is all that is left, and a grep cannot see a rename."
    )
    assert NAME in POISON.read_text(encoding="utf-8"), (
        f"{POISON.relative_to(AEON)} no longer names `{NAME}`, so it is no longer asking "
        f"the question this test exempts it for."
    )


def test_the_comment_strip_does_not_swallow_code():
    """Anti-vacuity for the stripper itself.

    A `_code_only` that returned "" for everything would make the sweep below pass on any
    tree at all. These three lines are the two shapes it must keep and the two it must
    drop, stated as a table rather than trusted.
    """
    assert NAME in _code_only(f"        movea.l Sec.{NAME}(a0), a1        // a comment")
    assert NAME in _code_only(f"        {NAME}:        default,")
    assert NAME not in _code_only(f"        // the old {NAME} field moved to the region")
    assert NAME not in _code_only(f'ensure(false, "{NAME} was deleted in step 3")')


def test_no_emp_code_names_sec_bg_layout():
    sources = _emp_sources()
    # Anti-vacuity: a walk that found nothing would pass silently. The tree carries
    # hundreds of .emp files; a handful means the source roots moved and this test stopped
    # reading the code it names.
    assert len(sources) > 100, (
        f"only {len(sources)} .emp files found under engine/ and games/ — the source roots "
        f"moved and this test is no longer reading the tree it claims to read"
    )

    offenders = []
    for path in sources:
        if path == POISON:
            continue
        text = path.read_text(encoding="utf-8")
        if NAME not in text:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if NAME in _code_only(line):
                offenders.append(f"{path.relative_to(AEON)}:{lineno}: {line.strip()}")

    assert not offenders, (
        f"`{NAME}` is named by CODE in {len({o.split(':')[0] for o in offenders})} .emp "
        f"file(s). The field was DELETED in regions part 2 step 3 — the background belongs "
        f"to the region now: `Region.rg_bg_layout`, read by Section_RedrawPlanes "
        f"(engine/level/section.emp) and by Draw_BG_TileRow (engine/level/plane_buffer.emp), "
        f"with `Act.act_bg_layout` as the 0-means-default fallback. Note that the BUILD "
        f"already refuses this, and refuses it WITHOUT naming the field: a "
        f"`Struct.field(aN)` read of a deleted field surfaces as `the contract closure "
        f"DROPPED 1 instruction(s)`, which is why this message exists. Sites:\n  "
        + "\n  ".join(offenders)
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
