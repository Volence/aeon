#!/usr/bin/env python3
"""
parallax publish-order lint — the three-cell config record must never publish the INERT
pair to IRQ6.

WHAT THE INVARIANT IS. `Parallax_Current_Config` / `Parallax_Target_Config` /
`Parallax_Transition_Frames` (engine/ram.emp) are ONE record with THREE stores. Every
writer is main-loop; two readers are not — `Parallax_Active_Config` is called from
`Enqueue_Dirty_Buffers` (engine/system/buffers.emp, `requires(vblank)`) and from
`Vscroll_Write` (engine/level/parallax.emp, `requires(vblank)`), so an IRQ6 can land on
ANY instruction boundary between two of a writer's stores and read whatever pair is
published there.

The selector's contract is `Frames != 0 -> return Target`. So the one pair that must
never be published is `Frames != 0 && Target == 0`: the selector returns 0, which both
VBlank callers read as "no parallax active" — Enqueue_Dirty_Buffers SKIPS the 896-byte
per-line HScroll DMA (one frame of frozen HScroll table) and Vscroll_Write takes
`.whole_plane`, shipping one VSRAM longword instead of twenty while reg $0B bit 2 still
says per-column. `Parallax_StartTransition`'s `.recross_current` and `.instant` arms both
published exactly that pair until 2026-09-06 (lens sweep item LS-5), by clearing Target
before Frames.

THE RULE, per arm of `Parallax_StartTransition`, derived from the selector above:
  * staging arm  — Target BEFORE Frames. This is what makes `Frames != 0 => Target != 0`
                   an invariant of the file, and the other two arms' benign intermediates
                   rest on it.
  * `.instant`   — Current, then Frames, then Target. Current first so the `Frames == 0`
                   intermediate already selects the NEW config; Target last because it is
                   dead to every reader once Frames is 0.
  * `.recross_current` — Frames before Target. Current is untouched (a0 already equals it,
                   which is how this label was reached), so the `Frames == 0` intermediate
                   IS the settled end state.

WHAT THIS LINT CHECKS: the store order inside each of those three arms, the store COUNTS
(so a fourth arm cannot be added without landing here), and the SHAPE OF THE SELECTOR the
rule is derived from — if `Parallax_Active_Config` stops meaning `Frames != 0 -> Target`,
every order above must be re-derived and this file fails loudly rather than silently
guarding the wrong thing.

WHAT IT CANNOT CHECK: any other writer of the three cells. `Parallax_Init`'s bulk
`Parallax_State` clear zeroes all three in ascending address order and is NOT covered here
(it is a wider window of a different shape — see DEFERRED_WORK LS-5). Nor can a text lint
see a store that reaches the cells without naming them. It is a TEXT-level gate, in the
same family as tools/test_palette_census_lint.py and for the same reason: sigil's proc
contracts are register write-sets, not memory write-sets, so there is no comptime
mechanism that can key on a store's destination symbol.

IT IS DELIBERATELY NOT A ROM GATE. build.sh's pytest lane runs BEFORE the build, so a test
that opened s4.bin would read the PREVIOUS build's artifact — the stale-artifact trap
build.sh's own header calls out. A byte-level version of this check would have to be wired
below sigil in build.sh as its own step.

Runner: build.sh's tool-suite pytest sweep (`python3 -m pytest "${TOOLS}"`, build-fatal),
which collects `tools/test_*.py` by directory glob. Also runnable standalone:
`python3 tools/test_parallax_publish_order_lint.py`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "engine" / "level" / "parallax.emp"

CURRENT = "Parallax_Current_Config"
TARGET = "Parallax_Target_Config"
FRAMES = "Parallax_Transition_Frames"

# A store is `move`/`clr` whose DESTINATION operand is one of the three cells. `clr` has a
# single operand, `move` has the destination last; both are matched by "the symbol is the
# final operand on the line".
STORE_RE = re.compile(
    r"^\s*(?:move|clr)\.[bwl]\s+.*?,?\s*(Parallax_(?:Current_Config|Target_Config|Transition_Frames))\s*$"
)
LABEL_RE = re.compile(r"^\s*\.(\w+):\s*$")
PROC_RE = re.compile(r"^(?:pub\s+)?proc\s+(\w+)\s*\(")


def strip_comment(line: str) -> str:
    """Drop a trailing `// ...`. No `.emp` string literal in this file contains `//`, and
    the checked lines are instructions, so a naive split is exact here."""
    return line.split("//", 1)[0].rstrip()


def proc_body(name: str) -> list[str]:
    """The comment-stripped source lines of one top-level proc, exclusive of its header."""
    text = SOURCE.read_text().splitlines()
    start = None
    for i, line in enumerate(text):
        m = PROC_RE.match(line)
        if m and m.group(1) == name:
            start = i + 1
            break
    if start is None:
        raise AssertionError(
            f"{SOURCE}: proc `{name}` not found — this lint's whole subject is gone or "
            f"renamed. Re-derive the publish-order rule against whatever replaced it; do "
            f"not delete this file to get green."
        )
    body: list[str] = []
    for line in text[start:]:
        if PROC_RE.match(line):
            break
        body.append(strip_comment(line))
    return body


def arms(body: list[str]) -> dict[str, list[str]]:
    """Split a proc body into label-headed segments. The pre-first-label run is `<entry>`."""
    out: dict[str, list[str]] = {"<entry>": []}
    cur = "<entry>"
    for line in body:
        m = LABEL_RE.match(line)
        if m:
            cur = m.group(1)
            out.setdefault(cur, [])
            continue
        out[cur].append(line)
    return out


def stores(lines: list[str]) -> list[str]:
    """The ordered list of cell names stored to, one entry per store instruction."""
    found = []
    for line in lines:
        m = STORE_RE.match(line)
        if m:
            found.append(m.group(1))
    return found


# ---------------------------------------------------------------------------
# The rule, one row per arm: (label, required store sequence).
#
# `cap_transitions_stage_begin` is the label the staging arm actually sits under (the
# capability span's opening marker), not a label invented for this lint.
# ---------------------------------------------------------------------------
REQUIRED = {
    "cap_transitions_stage_begin": [TARGET, FRAMES],
    "instant": [CURRENT, FRAMES, TARGET],
    "recross_current": [FRAMES, TARGET],
}


def test_selector_shape_still_justifies_the_rule() -> None:
    """The order rule is DERIVED from `Frames != 0 -> Target`. Pin that shape."""
    body = proc_body("Parallax_Active_Config")
    seg = arms(body)
    entry = [ln.strip() for ln in seg.get("cap_transitions_select_begin", []) if ln.strip()]
    assert entry, (
        f"{SOURCE}: Parallax_Active_Config has no `.cap_transitions_select_begin` arm — "
        f"the selector was restructured. Re-derive every store order in "
        f"Parallax_StartTransition against the new selector before touching this lint."
    )
    joined = " | ".join(entry)
    assert re.search(rf"tst\.b\s+{FRAMES}", joined), (
        f"{SOURCE}: the selector no longer keys on `tst.b {FRAMES}` (saw: {joined}). "
        f"The publish-order rule below is derived from that test; re-derive it."
    )
    assert re.search(r"bne\s+\.use_target", joined), (
        f"{SOURCE}: the selector's nonzero-Frames branch is no longer `bne .use_target` "
        f"(saw: {joined}). The rule 'never publish Frames != 0 with Target == 0' depends "
        f"on it; re-derive."
    )
    use_target = [ln.strip() for ln in seg.get("use_target", []) if ln.strip()]
    assert any(re.search(rf"move\.l\s+{TARGET},\s*d0", ln) for ln in use_target), (
        f"{SOURCE}: `.use_target` no longer loads {TARGET} into d0 (saw: {use_target}). "
        f"Re-derive the publish-order rule."
    )


def test_start_transition_publish_order() -> None:
    body = proc_body("Parallax_StartTransition")
    seg = arms(body)
    for label, want in REQUIRED.items():
        assert label in seg, (
            f"{SOURCE}: Parallax_StartTransition has no `.{label}` arm. The arm was "
            f"renamed or removed; re-derive its publish order (see this file's header) "
            f"rather than dropping the row."
        )
        got = stores(seg[label])
        assert got == want, (
            f"{SOURCE}: Parallax_StartTransition `.{label}` publishes the config record in "
            f"the order {got}, expected {want}.\n"
            f"  Why it matters: {FRAMES} != 0 with {TARGET} == 0 is read as INERT by "
            f"Parallax_Active_Config, and an IRQ6 landing on that boundary costs one frame "
            f"of frozen HScroll (Enqueue_Dirty_Buffers skips the 896-byte DMA) plus a "
            f"whole-plane VSRAM write against a per-column reg $0B (Vscroll_Write).\n"
            f"  If you MEANT to change this arm, re-derive the order from "
            f"Parallax_Active_Config's selector and update this row with the argument."
        )


def test_no_unruled_store_to_the_record() -> None:
    """Every store to the three cells inside Parallax_StartTransition must live in a ruled
    arm. A fourth arm — or a store hoisted into the proc entry — lands here."""
    body = proc_body("Parallax_StartTransition")
    seg = arms(body)
    total = stores(body)
    ruled = sum((stores(seg[label]) for label in REQUIRED), [])
    assert len(total) == len(ruled), (
        f"{SOURCE}: Parallax_StartTransition stores to the config record "
        f"{len(total)} times but only {len(ruled)} of those sit in a ruled arm "
        f"({', '.join('.' + k for k in REQUIRED)}). A new store to "
        f"{CURRENT}/{TARGET}/{FRAMES} needs its own publish-order argument — add the arm "
        f"to REQUIRED with the derivation, do not widen this count."
    )


def _main() -> int:
    failures = []
    for fn in (
        test_selector_shape_still_justifies_the_rule,
        test_start_transition_publish_order,
        test_no_unruled_store_to_the_record,
    ):
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as exc:
            failures.append(fn.__name__)
            print(f"  FAIL {fn.__name__}\n{exc}")
    if failures:
        print(f"\nparallax publish-order lint: {len(failures)} failed — {', '.join(failures)}")
        return 1
    print("\nparallax publish-order lint: 3 passed")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
