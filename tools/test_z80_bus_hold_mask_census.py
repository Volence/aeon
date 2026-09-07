#!/usr/bin/env python3
"""
TREE-WIDE Z80 bus-hold mask census — every 68k hold of the Z80 bus must be ENTERED
with 68000 interrupts masked, and this checks the whole tree rather than one file.

WHY THE RULE EXISTS, quoted from the construct that implements it
(engine/z80_bus.emp): the hold is a LATCH, not a counter — "an inner release frees
the outer hold". `z80_stopped` splices `move.w #$0100, Z80_BUS_REQUEST` ONCE, above
its `.wait_z80` poll. An IRQ6 landing in that spin runs the VBlank handler, whose own
brackets RELEASE the bus on the way out; `rte` returns into `.wait_z80`, bit 0 reads 1
again, and NOTHING below that label re-issues the request. Either the spin never
exits, or it exits on a stale grant and the body writes Z80 RAM with the Z80 live. An
IRQ6 landing in the BODY instead is the milder half of the same fault (the writes are
dropped). That defect was real and was fixed at `Sound_PlayMusic`'s `.await_slot` on
2026-09-07 (LS-11).

WHAT THIS ADDS OVER tools/test_sound_bus_hold_mask_lint.py, which stays. That lint
reads engine/sound/sound_api.emp ONLY and additionally checks that file's header
still STATES the rule (a premise check this one does not duplicate). Its own
docstring named the hole this file closes: the brackets in the tree's OTHER files,
"neither of which this file-scoped text rule models". This file models them.

WHAT IT CHECKS. For every `with z80_stopped` bracket in engine/ and games/, the
entry mask must be established by one of FOUR mechanisms, all recognised from CODE
(comments and string literals are stripped before any matching — no mechanism here
can be satisfied by prose, and a control in this module proves that specific case):

  1. INTS_OFF   — the bracket is lexically inside `with ints_off { … }` or
                  `with ints_off_until_rte { … }` (engine/irq.emp splices
                  `move.w #$2700, sr` and the compiler proves the pairing).
  2. HAND_2700  — a hand-spelled `move.w #$2700, sr` earlier in the SAME proc with
                  no intervening `move.w (sp)+, sr`. engine/irq.emp names this class
                  deliberate for multi-exit brackets, re-masking loops, and long
                  spans whose masked region is a whole code block.
  3. VBLANK     — the proc declares `requires(vblank)` AND writes `sr` nowhere before
                  the site. `requires(vblank)` is COMPILER-CHECKED
                  (`[context.unsatisfied]`, engine/irq.emp): such a proc may only be
                  called from inside the VBlank window, where the 68000's own IPL 6
                  is the mask. The extra "no `sr` write before the site" clause is
                  what turns entry-at-IPL-6 into masked-AT-THE-BRACKET; without it a
                  `requires(vblank)` proc could lower the mask and still classify.
  4. RESET_SR   — the reset entry point, before it has written `sr` at all. The 68000
                  enters reset with SR = $2700, so the mask stands until the first
                  write. Recognised ONLY for the declared reset proc below, and only
                  for sites above that proc's FIRST `sr` write.

Mechanism 3 is the interesting one: it is the only mechanism whose premise a HUMAN
does not have to re-check, because sigil already proves it. `grants(vblank)` is
declared exactly once in the tree (engine/system/vblank.emp's `VBlank_Handler`) —
this file asserts that, because mechanism 3 is worth nothing if the capability is
handed out from a second, non-interrupt root.

THE HOLD THAT IS NOT A BRACKET. engine/system/boot.emp's `EntryPoint` spells its own
request/spin/release by hand around the Z80 driver-blob copy — `move.w d7,(a1)` with
a1 preloaded from BootData — so NO grep for `with z80_stopped` can see it, and no
`[context.*]` check treats it as a hold. Its mask argument is mechanism 4, and that
argument IS checked here: `test_boot_hand_spelled_hold_precedes_the_first_sr_write`.
Sigil cannot see this hold either — its `[bus.*]` net (sigil-frontend-emp/src/
z80_bus.rs) keys off a RESOLVED destination operand, and a register-indirect
destination is its documented soundness bailout.

WHAT IT DOES NOT COVER, each a real hole:
  * INTERPROCEDURAL ANYTHING. Classification is per-proc. A bracket in a helper whose
    caller masks would be flagged (correctly by this rule, which is that the
    transaction masks) — and, the direction that actually loses coverage, a `jbsr`
    between a mechanism-2 mask and its bracket could lower the mask inside the callee
    and this file would not see it. The count of sites in that shape is DERIVED and
    printed by `test_every_bus_hold_is_masked` on every run, not remembered here.
  * THE MASK'S *VALUE* beyond the shapes above. `move.w #$2500, sr` before a bracket
    reads as "an `sr` write" and disqualifies mechanisms 3 and 4, but a hand-spelled
    mask that is not literally `#$2700` does not SATISFY mechanism 2 either — such a
    site fails. That is deliberate: $2700 is the tree's only spelling.
  * RUNTIME. Nothing here executes a ROM. It shows the mask instruction is emitted
    before the hold, never that a particular IRQ6 was excluded.
  * SHAPE GATES. It reads source, so it sees sites in every shape at once, including
    ones no canonical build places (`Sound_DebugMirror` is placed only by
    `sigil build --native --config-a`). That is a strength here and a mismatch to
    keep in mind when comparing its population against a ROM.
  * THE Z80 SIDE. Nothing about what the Z80 does while stopped.

Runner: build.sh's PRE-BUILD tool-suite pytest lane (`python3 -m pytest "${TOOLS}"
-m "not needs_build"`, build-fatal), which collects `tools/test_*.py` by directory
glob. Also runnable standalone: `python3 tools/test_z80_bus_hold_mask_census.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOTS = ("engine", "games")
SUFFIXES = (".emp", ".asm")

# The reset entry point — mechanism 4's ONLY subject. Named as (file, proc) so the
# check cannot be satisfied by some other proc acquiring the same shape.
RESET_ENTRY = ("engine/system/boot.emp", "EntryPoint")

# The label the hand-spelled boot hold spins on. It is the only handle a source-level
# check has on that hold: the request and release write through an address register,
# so neither instruction names the bus at all.
BOOT_SPIN_LABEL = ".wait_z80"

RE_PROC = re.compile(r"^\s*(?:pub\s+)?proc\s+(\w+)")
RE_REQUIRES_VBLANK = re.compile(r"\brequires\s*\(([^)]*)\)")
RE_GRANTS = re.compile(r"\bgrants\s*\(([^)]*)\)")
RE_Z80 = re.compile(r"\bwith\s+z80_stopped\b")
RE_INTS_OFF = re.compile(r"\bwith\s+ints_off(?:_until_rte)?\b")
RE_MASK_SET = re.compile(r"\bmove\.w\s+#\$2700\s*,\s*sr\b")
RE_MASK_RESTORE = re.compile(r"\bmove\.w\s+\(sp\)\+\s*,\s*sr\b")
# Any write whose DESTINATION is sr. `move.w sr, -(sp)` and `move.w sr, d0` are reads
# and must not match, so sr is required to be the LAST operand.
RE_SR_WRITE = re.compile(
    r"\b(?:move\.w|move|andi\.w|andi|ori\.w|ori|eori\.w|eori)\s+[^,]+,\s*sr\s*(?:$|//)"
)
RE_CALL = re.compile(r"\b(?:jbsr|jsr|bsr(?:\.[wsbl])?)\b")

MECH_INTS_OFF = "INTS_OFF"
MECH_HAND_2700 = "HAND_2700"
MECH_VBLANK = "VBLANK"
MECH_RESET_SR = "RESET_SR"
UNMASKED = "UNMASKED"

# A FLOOR on the bracket population, and it is a floor and not a census: it catches
# sites being deleted out from under this check, it does not catch a site being added
# (the per-site mechanism check is what covers additions — a new bracket with no
# mechanism fails). Derived 2026-09-07 by this module's own scanner.
MIN_BRACKETS = 22


def _strip(line: str) -> str:
    """Drop string literals and then any `//` comment.

    Literals go FIRST so a `//` inside `"…"` cannot truncate the line early, and so a
    brace inside a message string cannot perturb depth tracking. Doing this before any
    matching is what makes every mechanism below a CODE test: no comment this parcel
    or any other writes can name `with ints_off`, `requires(vblank)` or
    `move.w #$2700, sr` into a classification.
    """
    line = re.sub(r'"(?:[^"\\]|\\.)*"', '""', line)
    idx = line.find("//")
    return line if idx < 0 else line[:idx]


def source_files() -> list[Path]:
    out: list[Path] = []
    for root in ROOTS:
        base = REPO / root
        if not base.is_dir():
            continue
        for suffix in SUFFIXES:
            out.extend(sorted(base.rglob(f"*{suffix}")))
    return sorted(set(out))


def scan_file(path: Path) -> tuple[list[dict], list[dict]]:
    """`scan_text` plus file IO."""
    return scan_text(
        path.read_text(encoding="utf-8", errors="replace"),
        path.relative_to(REPO).as_posix(),
    )


def scan_text(text: str, rel: str) -> tuple[list[dict], list[dict]]:
    """Return (bracket sites, proc records) for one source text.

    A site record carries the mechanism that masks it, plus the evidence the failure
    message needs: which proc, and whether a call sits between a mechanism-2 mask and
    the site (the interprocedural hole, counted rather than remembered).
    """
    sites: list[dict] = []
    procs: list[dict] = []

    proc = None
    proc_requires: set[str] = set()
    ints_off_depths: list[int] = []
    hand_masked = False
    hand_masked_line = 0
    calls_since_mask = 0
    sr_written_in_proc = False
    depth = 0
    pending_sig: str | None = None

    for n, raw in enumerate(text.splitlines(), start=1):
        line = _strip(raw)

        m = RE_PROC.match(line)
        if m:
            proc = m.group(1)
            pending_sig = line
            proc_requires = set()
            ints_off_depths = []
            hand_masked = False
            hand_masked_line = 0
            calls_since_mask = 0
            sr_written_in_proc = False
            depth = 0
            procs.append({"file": rel, "proc": proc, "line": n, "grants": set()})

        # A proc signature may wrap; accumulate until the body brace appears.
        if pending_sig is not None:
            if m is None:
                pending_sig += " " + line
            if "{" in pending_sig:
                for clause in RE_REQUIRES_VBLANK.finditer(pending_sig):
                    proc_requires |= {c.strip() for c in clause.group(1).split(",")}
                for clause in RE_GRANTS.finditer(pending_sig):
                    procs[-1]["grants"] |= {c.strip() for c in clause.group(1).split(",")}
                pending_sig = None

        opens = line.count("{")
        closes = line.count("}")

        if RE_MASK_SET.search(line):
            hand_masked = True
            hand_masked_line = n
            calls_since_mask = 0
        elif RE_MASK_RESTORE.search(line):
            hand_masked = False
        elif RE_SR_WRITE.search(line):
            sr_written_in_proc = True

        if hand_masked and RE_CALL.search(line):
            calls_since_mask += 1

        if RE_Z80.search(line):
            is_reset_entry = (rel, proc) == RESET_ENTRY
            if ints_off_depths:
                mech = MECH_INTS_OFF
            elif hand_masked:
                mech = MECH_HAND_2700
            elif "vblank" in proc_requires and not sr_written_in_proc:
                mech = MECH_VBLANK
            elif is_reset_entry and not sr_written_in_proc:
                mech = MECH_RESET_SR
            else:
                mech = UNMASKED
            sites.append(
                {
                    "file": rel,
                    "line": n,
                    "proc": proc,
                    "text": raw.strip(),
                    "mech": mech,
                    "requires": sorted(proc_requires),
                    "mask_line": hand_masked_line if mech == MECH_HAND_2700 else 0,
                    "calls_since_mask": calls_since_mask if mech == MECH_HAND_2700 else 0,
                }
            )

        if RE_INTS_OFF.search(line):
            ints_off_depths.append(depth)

        depth += opens - closes
        while ints_off_depths and depth <= ints_off_depths[-1]:
            ints_off_depths.pop()

    return sites, procs


def scan_tree() -> tuple[list[dict], list[dict]]:
    all_sites: list[dict] = []
    all_procs: list[dict] = []
    for path in source_files():
        s, p = scan_file(path)
        all_sites.extend(s)
        all_procs.extend(p)
    return all_sites, all_procs


# --------------------------------------------------------------------------------
# The checks.
# --------------------------------------------------------------------------------


def test_the_scan_reaches_the_tree():
    """Positive control for the scanner's REACH.

    An empty or near-empty population would make every other assertion below pass
    vacuously, and a directory sweep is exactly the shape that fails that way (a moved
    root, a renamed suffix). Assert the sweep found the file that DEFINES the bracket,
    and that it found source in both roots.
    """
    files = {p.relative_to(REPO).as_posix() for p in source_files()}
    assert "engine/z80_bus.emp" in files, (
        f"the sweep of {ROOTS} did not reach engine/z80_bus.emp, the module that defines "
        f"`z80_stopped` — it found {len(files)} file(s). The roots or suffixes are wrong "
        f"and every check in this module is grading an empty population."
    )
    for root in ROOTS:
        assert any(f.startswith(root + "/") for f in files), (
            f"no {root}/ source reached the sweep ({len(files)} file(s) total)."
        )


def test_vblank_capability_has_exactly_one_grant_root():
    """Mechanism 3's premise.

    `requires(vblank)` proves the caller held the capability; it proves the caller was
    an INTERRUPT only because the capability's sole root is the interrupt entry point.
    A second `grants(vblank)` on a main-loop proc would silently convert mechanism 3
    from a mask proof into nothing.
    """
    _, procs = scan_tree()
    roots = [p for p in procs if "vblank" in p["grants"]]
    names = [f"{p['file']}:{p['line']} {p['proc']}" for p in roots]
    print(f"grants(vblank) roots: {len(roots)} -> {names}")
    assert len(roots) == 1, (
        "mechanism 3 (VBLANK) assumes the `vblank` capability has exactly ONE grant "
        f"root, the hardware interrupt entry point. Found {len(roots)}: {names}. "
        "Either a second interrupt entry point was added — in which case list it here "
        "and re-derive — or a non-interrupt proc is handing out the capability, which "
        "makes `requires(vblank)` useless as a mask argument."
    )
    assert roots[0]["proc"] == "VBlank_Handler", (
        f"the sole grants(vblank) root is {roots[0]['proc']} in {roots[0]['file']}, not "
        f"VBlank_Handler. Mechanism 3's premise names the VBlank interrupt entry point."
    )


def test_bracket_population_has_not_shrunk():
    sites, _ = scan_tree()
    print(f"`with z80_stopped` brackets across {ROOTS}: {len(sites)}")
    by_mech: dict[str, int] = {}
    for s in sites:
        by_mech[s["mech"]] = by_mech.get(s["mech"], 0) + 1
        print(f"  {s['file']}:{s['line']:<5} {s['proc']:<24} {s['mech']}")
    print(f"  by mechanism: {dict(sorted(by_mech.items()))}")
    assert len(sites) >= MIN_BRACKETS, (
        f"only {len(sites)} `with z80_stopped` bracket(s) found across {ROOTS}, floor is "
        f"{MIN_BRACKETS}. Sites were deleted, or the sweep stopped reaching a directory. "
        f"This is a FLOOR, not a census."
    )


def test_every_bus_hold_is_masked():
    sites, _ = scan_tree()
    unmasked = [s for s in sites if s["mech"] == UNMASKED]

    # DERIVED, printed on every run, and the honest measure of this file's biggest
    # hole: mechanism-2 sites whose mask is separated from the bracket by at least one
    # call. A callee could lower the mask in between and nothing here would see it.
    spanned = [s for s in sites if s["calls_since_mask"] > 0]
    print(
        f"mechanism-2 sites with a call between the mask and the bracket: {len(spanned)}"
        + ("" if not spanned else " -> "
           + ", ".join(f"{s['file']}:{s['line']} ({s['calls_since_mask']} call(s))"
                       for s in spanned))
    )

    assert not unmasked, (
        "68k Z80-bus hold(s) entered with interrupts UNMASKED. The hold is a latch: an "
        "IRQ6 landing in the spliced `.wait_z80` spin releases the bus and nothing "
        "re-issues the request (engine/z80_bus.emp, and this module's docstring):\n"
        + "\n".join(
            f"  {s['file']}:{s['line']} in {s['proc']}"
            f"{' requires' + str(s['requires']) if s['requires'] else ''}: {s['text']}"
            for s in unmasked
        )
        + "\nMask it with one of the four mechanisms this file recognises: wrap it in "
        "`with ints_off { … }`; hand-spell `move.w #$2700, sr` earlier in the proc "
        "(the shapes engine/irq.emp names); declare `requires(vblank)` on the proc if "
        "it is genuinely interrupt-only, which sigil then CHECKS at every call site; "
        "or, for the reset entry point alone, keep the site above its first `sr` write."
    )


def test_boot_hand_spelled_hold_precedes_the_first_sr_write():
    """The 23rd hold — the one no `with z80_stopped` grep can see.

    engine/system/boot.emp's `EntryPoint` requests, spins on and releases the bus by
    hand, through an address register preloaded from BootData. Neither the request nor
    the release names the bus, so the only source-level handle is the spin LABEL. What
    is checked is its mask argument, which is mechanism 4: the reset SR ($2700) still
    stands because nothing has written `sr` yet.

    WHAT THIS DOES NOT PROVE: that the hold is still correctly paired, or that the
    label still belongs to a bus spin at all. Renaming the label fails this test loudly
    rather than silently dropping the hold from the population, which is the failure
    mode worth buying.
    """
    path = REPO / RESET_ENTRY[0]
    assert path.is_file(), f"{RESET_ENTRY[0]} is missing — the reset entry point moved."
    lines = [_strip(l) for l in path.read_text(encoding="utf-8").splitlines()]

    in_entry = False
    spin_lines: list[int] = []
    first_sr_write = 0
    last_bracket = 0
    for n, line in enumerate(lines, start=1):
        m = RE_PROC.match(line)
        if m:
            if in_entry:
                break
            in_entry = m.group(1) == RESET_ENTRY[1]
            continue
        if not in_entry:
            continue
        if re.match(rf"\s*{re.escape(BOOT_SPIN_LABEL)}\s*:", line):
            spin_lines.append(n)
        if RE_Z80.search(line):
            last_bracket = n
        if first_sr_write == 0 and RE_SR_WRITE.search(line):
            first_sr_write = n

    print(
        f"{RESET_ENTRY[0]} {RESET_ENTRY[1]}: hand-spelled spin at {spin_lines}, "
        f"last bracket at :{last_bracket}, first `sr` write at :{first_sr_write}"
    )
    assert len(spin_lines) == 1, (
        f"expected exactly one `{BOOT_SPIN_LABEL}:` label in {RESET_ENTRY[0]}'s "
        f"{RESET_ENTRY[1]} (the hand-spelled Z80 bus hold around the driver-blob copy); "
        f"found {len(spin_lines)} at {spin_lines}. If the hold was restructured, "
        "re-derive this check — do not delete it: this is the one hold in the tree that "
        "no `with z80_stopped` search and no `[context.*]` check can see."
    )
    assert first_sr_write > 0, (
        f"{RESET_ENTRY[1]} writes `sr` nowhere. It used to write `#$2700` after the "
        "boot Z80 work; if that moved, mechanism 4's ordering argument needs re-deriving."
    )
    for label, site in (("hand-spelled hold", spin_lines[0]), ("last bracket", last_bracket)):
        assert site < first_sr_write, (
            f"{RESET_ENTRY[0]}: the {label} at :{site} now sits AFTER {RESET_ENTRY[1]}'s "
            f"first `sr` write at :{first_sr_write}. Mechanism 4 (the reset SR still "
            "standing) no longer covers it, and nothing else does — that hold is entered "
            "with whatever mask that write left behind."
        )


def test_comment_prose_cannot_satisfy_a_mechanism():
    """The control the parcel that wrote this file owes.

    Two gates in this tree came back green with a mutation applied because the parcel's
    own new prose satisfied the search. Nothing here matches prose — `_strip` removes
    string literals and `//` comments before any regex runs — and this asserts that
    specific case rather than claiming it: a bracket whose ONLY mask is a comment
    saying `with ints_off` / `move.w #$2700, sr` / `requires(vblank)` classifies
    UNMASKED.
    """
    prose_only = (
        "pub proc Fake () clobbers() {\n"
        "        // with ints_off { and move.w #$2700, sr and requires(vblank)\n"
        '        ensure(1 == 1, "with ints_off move.w #$2700, sr requires(vblank)")\n'
        "        with z80_stopped {\n"
        "            move.b  #1, SND_DMA_ACTIVE_SLOT\n"
        "        }\n"
        "}\n"
    )
    sites, _ = scan_text(prose_only, "engine/fake.emp")
    assert len(sites) == 1, f"control fixture parsed {len(sites)} site(s), expected 1"
    assert sites[0]["mech"] == UNMASKED, (
        "prose naming a mechanism classified a bracket as masked — the comment/string "
        f"strip is not running. Got {sites[0]['mech']}."
    )

    # And the same text as CODE classifies masked, so the control above is proving that
    # comments are ignored rather than that the mechanism never matches anything.
    as_code = (
        "pub proc Fake () clobbers() {\n"
        "        with ints_off {\n"
        "            with z80_stopped {\n"
        "                move.b  #1, SND_DMA_ACTIVE_SLOT\n"
        "            }\n"
        "        }\n"
        "}\n"
    )
    sites, _ = scan_text(as_code, "engine/fake.emp")
    assert len(sites) == 1 and sites[0]["mech"] == MECH_INTS_OFF, (
        f"the positive half of the control failed: {sites}. If the code form does not "
        "classify either, the prose control above is vacuous."
    )


if __name__ == "__main__":
    test_the_scan_reaches_the_tree()
    test_vblank_capability_has_exactly_one_grant_root()
    test_bracket_population_has_not_shrunk()
    test_every_bus_hold_is_masked()
    test_boot_hand_spelled_hold_precedes_the_first_sr_write()
    test_comment_prose_cannot_satisfy_a_mechanism()
    print("OK")
