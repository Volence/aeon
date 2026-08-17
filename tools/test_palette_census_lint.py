#!/usr/bin/env python3
"""
palette census lint — the TEXT-LEVEL half of the frame-top palette committer census.

THE CENSUS ITSELF lives in `engine/system/buffers.emp`, above `Enqueue_Dirty_Buffers`:
a comment table of every site that touches `Palette_Buffer` / `Palette_Ship_Snap`, plus a
comptime `ensure` pinning its length. That census exists because `Palette_Ship_Snap`'s
invariant (spec §2.2 of docs/superpowers/specs/2026-08-16-parcel-r1-palette-bands-v6.md)
— "the snapshot equals THIS FRAME'S base-DMA payload for that line" — holds only while
every writer of `Palette_Buffer` runs in the MAIN LOOP, upstream of the VBlank splices.
There is no single frame-top commit seam enforcing that.

WHY THIS FILE EXISTS. The .emp `ensure` is a length pin: it fires when somebody edits the
census, and does nothing when somebody adds a writer WITHOUT editing it — which is the
actual failure mode (spec §8, CLAIM 7). sigil cannot close that hole today: its proc
contracts are REGISTER write-sets (`clobbers`/`out`/`preserves`) and call-graph contexts
(`requires`/`grants`); there is no memory write-set declaration to check, and no contract
that keys on the destination symbol of a store outside the VDP-port check in
sigil's z80_bus.rs. So the enforcement available tonight is textual: pin the SET of files
that name these symbols and each file's reference COUNT, and fail the build on drift.

WHAT IT CATCHES: a new file that names `Palette_Buffer`/`Palette_Ship_Snap`; a new
reference added inside an already-listed file; a reference deleted without updating the
census. WHAT IT CANNOT CATCH: a write that reaches CRAM without naming either symbol
(a raw address literal, a pointer handed in from elsewhere, a direct VDP-port write).
Label it for what it is — lint-enforced at the text level; comptime enforcement remains
UNVERIFIED (spec §8, CLAIM 7).

Runs in every build: build.sh's tool-suite pytest step (same `--no-lint` hatch as the
other source gates). Also runnable standalone: `python3 tools/test_palette_census_lint.py`
prints the live scan and exits nonzero on drift.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The two symbols the invariant is made of. Palette_Buffer is the frame-top accumulator
# the base DMA ships; Palette_Ship_Snap is the per-line copy the band restore streams from.
SYMBOL_RE = re.compile(r"\bPalette_(?:Buffer|Ship_Snap)\b")

# Only these two trees hold engine/game source. tools/ and docs/ mention the symbols in
# prose and gates; they cannot write them.
SCAN_ROOTS = ("engine", "games")
SCAN_SUFFIXES = (".emp", ".asm")

# THE PINS — one row per file that references the symbols, with its CODE reference count
# (comments and string literals excluded; see strip_noncode). Measured 2026-08-17, R1
# Task 14. Each row maps onto the census comment table in engine/system/buffers.emp:
#
#   engine/ram.emp                          the two declarations themselves
#   engine/effects/palette.emp              census 0-3 (the writers) + 13 (DeriveVariant reads)
#   engine/effects/raster.emp               census 12 — the HBlank restore, only runtime reader
#                                           of Palette_Ship_Snap
#   engine/system/buffers.emp               census 10 (SRC_PAL_LINE0..3, the ship's DMA source)
#                                           + 11 (the four snapshot splices: 4 lea + 4 lea)
#   games/sonic4/player/player_common.emp   census 4  — Player_RefreshPhysics line-0 copy
#   games/sonic4/test/ojz_scroll_test.emp   census 5-6 — init copy + the T15 sky-marker
#   games/sonic4/test/object_test_state.emp census 7-8 — two init copies
#   games/demo/demo_state.emp               census 9  — the demo game's init copy
CENSUS_PINS = {
    "engine/effects/palette.emp": 8,
    "engine/effects/raster.emp": 1,
    "engine/ram.emp": 2,
    "engine/system/buffers.emp": 12,
    "games/demo/demo_state.emp": 1,
    "games/sonic4/player/player_common.emp": 1,
    "games/sonic4/test/object_test_state.emp": 2,
    "games/sonic4/test/ojz_scroll_test.emp": 3,
}

FIX_INSTRUCTIONS = (
    "The frame-top palette committer census has drifted.\n"
    "  1. Update the census comment table AND its length `ensure` in engine/system/buffers.emp.\n"
    "  2. Update CENSUS_PINS in tools/test_palette_census_lint.py to the counts printed above.\n"
    "  3. RE-DERIVE the Palette_Ship_Snap invariant (spec §2.2 of\n"
    "     docs/superpowers/specs/2026-08-16-parcel-r1-palette-bands-v6.md) for the new site:\n"
    "     if it can run in VBlank context, or in any frame-top phase downstream of\n"
    "     Enqueue_Dirty_Buffers' splices, the snapshot no longer matches the shipped\n"
    "     base-DMA payload and the band restore op streams the wrong colours."
)


def strip_noncode(line: str) -> str:
    """Drop `//` comments and double-quoted string literals.

    Both carry the symbol names in prose (the census table, the ensure messages) and a
    prose edit must not be able to trip a gate about writes. Crude on purpose: no escape
    handling, no block comments — .emp has no block comment form, and a `"` inside an
    .emp string is not spelled in this tree.

    ONE string form survives, and it is not an exception so much as the rule applied
    correctly: `extern("Palette_Buffer")` is a link-time ADDRESS reference that happens to
    be spelled with quotes (buffers.emp's SRC_PAL_LINE0..3 — census entry 10, the ship's
    own DMA source). Dropping it with the prose would have silently un-pinned the four
    references that matter most, and did on the first run of this lint.
    """
    line = line.split("//", 1)[0]
    line = re.sub(r'extern\(\s*"([^"]*)"\s*\)', r"extern(\1)", line)
    return re.sub(r'"[^"]*"', "", line)


def scan(root: Path) -> dict[str, int]:
    """{repo-relative path: code references to the palette symbols}, non-zero rows only."""
    found: dict[str, int] = {}
    for sub in SCAN_ROOTS:
        base = root / sub
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in SCAN_SUFFIXES or not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            count = sum(len(SYMBOL_RE.findall(strip_noncode(ln))) for ln in text.splitlines())
            if count:
                found[path.relative_to(root).as_posix()] = count
    return found


def _report(found: dict[str, int]) -> str:
    rows = "\n".join(f"    {v:>3}  {k}" for k, v in sorted(found.items()))
    return f"live scan:\n{rows}"


# --------------------------------------------------------------------------- tests


def test_census_matches_the_pins():
    """The real tree's palette-symbol reference set equals the census."""
    found = scan(REPO_ROOT)
    added = sorted(set(found) - set(CENSUS_PINS))
    removed = sorted(set(CENSUS_PINS) - set(found))
    changed = sorted(
        f"{f}: pinned {CENSUS_PINS[f]}, found {found[f]}"
        for f in set(found) & set(CENSUS_PINS)
        if found[f] != CENSUS_PINS[f]
    )
    assert not (added or removed or changed), (
        f"UNREGISTERED palette committer.\n"
        f"  new files referencing Palette_Buffer/Palette_Ship_Snap: {added or 'none'}\n"
        f"  files that stopped referencing them:                    {removed or 'none'}\n"
        f"  reference-count drift:                                  {changed or 'none'}\n"
        f"{_report(found)}\n{FIX_INSTRUCTIONS}"
    )


def test_the_emp_census_is_still_there():
    """The lint is one half of the mechanism; fail loudly if the .emp half is deleted.

    Pins the comptime fn's name and its length `ensure` — the pair the census comment
    table hangs off. Without this, someone could delete the census and only this file's
    pins would remain, which is the advisory tripwire minus the thing it points at.
    """
    text = (REPO_ROOT / "engine" / "system" / "buffers.emp").read_text(encoding="utf-8")
    assert "comptime fn pal_committer_census(" in text, (
        "the frame-top palette committer census disappeared from engine/system/buffers.emp "
        "— it is the authority this lint's pins mirror (spec §8, CLAIM 7)"
    )
    assert "ensure(pal_committer_census() == 14," in text, (
        "the census length pin in engine/system/buffers.emp is gone or its count moved "
        "without this lint being updated — see spec §2.2 before changing either"
    )


# The RED-FIRST proof, run every build. It cannot live in the real tree: a poison .emp
# carrying a Palette_Buffer write would trip this lint IN the real build (and would have
# to be pinned, making the pin meaningless). So the poison is a synthetic mini-tree.


def _mini_tree(tmp_path: Path, extra: dict[str, str] | None = None) -> Path:
    files = {
        "engine/effects/palette.emp": "        lea     Palette_Buffer, a1\n",
        "games/demo/demo_state.emp": "        lea     Palette_Buffer, a1  // (Palette_Buffer).w\n",
    }
    files.update(extra or {})
    for rel, body in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return tmp_path


def test_poison_a_new_writer_in_a_new_file_is_seen(tmp_path):
    """A brand-new frame-top writer in an unregistered file shows up in the scan."""
    clean = scan(_mini_tree(tmp_path / "clean"))
    assert clean == {"engine/effects/palette.emp": 1, "games/demo/demo_state.emp": 1}

    poisoned = scan(
        _mini_tree(
            tmp_path / "poisoned",
            {"engine/system/vblank.emp": "        move.w  d0, Palette_Buffer\n"},
        )
    )
    assert set(poisoned) - set(clean) == {"engine/system/vblank.emp"}


def test_poison_an_added_reference_in_a_listed_file_is_seen(tmp_path):
    """A new write inside an ALREADY-listed file moves that file's count."""
    poisoned = scan(
        _mini_tree(
            tmp_path,
            {
                "engine/effects/palette.emp": (
                    "        lea     Palette_Buffer, a1\n"
                    "        lea     Palette_Buffer + $20, a2\n"
                )
            },
        )
    )
    assert poisoned["engine/effects/palette.emp"] == 2


def test_prose_edits_do_not_trip_the_gate(tmp_path):
    """Comments and ensure-message text name the symbols; only code counts."""
    quiet = scan(
        _mini_tree(
            tmp_path,
            {
                "engine/effects/palette.emp": (
                    "// Palette_Buffer is composed once per frame; Palette_Ship_Snap copies it.\n"
                    '        ensure(1 == 1, "Palette_Buffer / Palette_Ship_Snap census")\n'
                    "        lea     Palette_Buffer, a1\n"
                )
            },
        )
    )
    assert quiet["engine/effects/palette.emp"] == 1


def test_extern_string_references_still_count(tmp_path):
    """`extern("Palette_Buffer")` is an address reference, not prose — it must count."""
    seen = scan(
        _mini_tree(
            tmp_path,
            {
                "engine/system/buffers.emp": (
                    'equ SRC_PAL_LINE0 = (extern("Palette_Buffer") >> 1) & $7FFFFF\n'
                    'equ SRC_PAL_LINE1 = ((extern("Palette_Buffer") + $20) >> 1) & $7FFFFF\n'
                )
            },
        )
    )
    assert seen["engine/system/buffers.emp"] == 2


if __name__ == "__main__":
    live = scan(REPO_ROOT)
    print(_report(live))
    if live != CENSUS_PINS:
        print(FIX_INSTRUCTIONS, file=sys.stderr)
        sys.exit(1)
    print("palette census lint: OK — 8 files, 30 references, census intact")
