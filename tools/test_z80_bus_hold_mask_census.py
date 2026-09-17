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
                  for sites above that proc's FIRST `sr` write. Since LS-13b
                  (2026-09-17) it classifies TWO brackets, both in `EntryPoint`: the
                  cold-boot Z80 init hold and the YM key-off hold.

Mechanism 3 is the interesting one: it is the only mechanism whose premise a HUMAN
does not have to re-check, because sigil already proves it. `grants(vblank)` is
declared exactly once in the tree (engine/system/vblank.emp's `VBlank_Handler`) —
this file asserts that, because mechanism 3 is worth nothing if the capability is
handed out from a second, non-interrupt root.

THERE IS NO LONGER A HOLD THAT IS NOT A BRACKET (LS-13b, 2026-09-17). Until then
engine/system/boot.emp's `EntryPoint` spelled its own request/spin/release by hand
around the Z80 driver-blob copy (`move.w d7,(a1)` with a1 preloaded from BootData), so
no `with z80_stopped` grep saw it, no `[context.*]` check treated it as a hold, and
sigil's `[bus.*]` net could not recognise it (register-indirect destination AND a
non-literal source). The one statement that forced the hand spelling — releasing Z80
reset between the bus request and the grant spin — now rides in `z80_stopped`'s
`interleave` slot (sigil named slot, decision d-33), so the hold is an ordinary bracket,
counted by the population floor and classified by mechanism 4 like the key-off bracket.
Two checks keep that true rather than remembered:
  * `test_reset_entry_holds_precede_the_first_sr_write` — the ordering argument for
    BOTH `EntryPoint` brackets, and that the Z80-init one is still the bracket carrying
    the slot argument (so a regression back to a hand spelling fails here);
  * `test_no_hand_spelled_bus_hold_remains` — the bus-request register (by name or by
    raw address) appears in CODE only at its definition and inside the context that
    brackets it. A hand-spelled request, a preload of the address into a register,
    or a second context all fail it.

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

# The module that DECLARES the bus bracket, and the module that DEFINES the bus-request
# register. They are the only two files whose CODE may name that register (see
# `test_no_hand_spelled_bus_hold_remains`); both are also checked to still hold the
# declaration/definition, so renaming either fails loudly instead of widening the rule.
BUS_CONTEXT_FILE = "engine/z80_bus.emp"
BUS_REGISTER_DEF_FILE = "engine/system/constants.emp"
RE_BUS_REGISTER = re.compile(r"\bZ80_BUS_REQUEST\b|\$A11100\b|\b0xA11100\b", re.IGNORECASE)
RE_BUS_CONTEXT_DECL = re.compile(r"^\s*(?:pub\s+)?context\s+z80_stopped\b")
RE_BUS_REGISTER_DEF = re.compile(r"^\s*(?:pub\s+)?const\s+Z80_BUS_REQUEST\s*=")
# The slot argument that marks boot's Z80-init bracket (the reset release between the
# bus request and the grant spin).
RE_INTERLEAVE_ARG = re.compile(r"\bwith\s+z80_stopped\s*\(\s*interleave\s*:")

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
# mechanism fails). Derived 2026-09-07 by this module's own scanner (22); 23 since
# LS-13b (2026-09-17), when boot's hand-spelled hold became a bracket — re-derived by
# the scanner on that tree, which prints the population on every run.
MIN_BRACKETS = 23


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


def test_reset_entry_holds_precede_the_first_sr_write():
    """Mechanism 4's ordering argument, for every bus hold in the reset entry point.

    Since LS-13b both of `EntryPoint`'s holds are `with z80_stopped` brackets: the
    cold-boot Z80 init (which carries the `interleave:` slot argument, the Z80 reset
    release between the bus request and the grant spin) and the YM key-off. Both rest on
    the reset SR ($2700) still standing, i.e. on sitting ABOVE the proc's first `sr`
    write. This asserts that ordering for each, and that the slot-carrying bracket is
    still there — so boot regressing to a hand-spelled hold (which no bracket search
    would see) fails HERE, rather than silently shrinking the population by one.

    WHAT THIS DOES NOT PROVE: pairing. That is sigil's `[context.escape]` /
    `[context.entry-skip]` / `[context.reacquire]`, which cover these brackets because
    the compiler emitted them.
    """
    path = REPO / RESET_ENTRY[0]
    assert path.is_file(), f"{RESET_ENTRY[0]} is missing — the reset entry point moved."
    lines = [_strip(l) for l in path.read_text(encoding="utf-8").splitlines()]

    in_entry = False
    brackets: list[int] = []
    slot_brackets: list[int] = []
    first_sr_write = 0
    for n, line in enumerate(lines, start=1):
        m = RE_PROC.match(line)
        if m:
            if in_entry:
                break
            in_entry = m.group(1) == RESET_ENTRY[1]
            continue
        if not in_entry:
            continue
        if RE_Z80.search(line):
            brackets.append(n)
        if RE_INTERLEAVE_ARG.search(line):
            slot_brackets.append(n)
        if first_sr_write == 0 and RE_SR_WRITE.search(line):
            first_sr_write = n

    print(
        f"{RESET_ENTRY[0]} {RESET_ENTRY[1]}: z80_stopped brackets at {brackets} "
        f"(slot-carrying: {slot_brackets}), first `sr` write at :{first_sr_write}"
    )
    assert len(slot_brackets) == 1, (
        f"expected exactly one `with z80_stopped(interleave: …)` bracket in "
        f"{RESET_ENTRY[0]}'s {RESET_ENTRY[1]} (the cold-boot Z80 init hold, whose slot "
        f"releases Z80 reset between the bus request and the grant spin); found "
        f"{len(slot_brackets)} at {slot_brackets}. If boot's Z80 init went back to a "
        "hand-spelled request/spin/release, it has left every compiler pairing proof and "
        "sigil's [bus.*] tier again (LS-13b) — restore the bracket, do not re-derive this."
    )
    assert first_sr_write > 0, (
        f"{RESET_ENTRY[1]} writes `sr` nowhere. It used to write `#$2700` after the "
        "boot Z80 work; if that moved, mechanism 4's ordering argument needs re-deriving."
    )
    for site in brackets:
        assert site < first_sr_write, (
            f"{RESET_ENTRY[0]}: the z80_stopped bracket at :{site} now sits AFTER "
            f"{RESET_ENTRY[1]}'s first `sr` write at :{first_sr_write}. Mechanism 4 (the "
            "reset SR still standing) no longer covers it, and nothing else does — that "
            "hold is entered with whatever mask that write left behind."
        )


def bus_register_code_mentions() -> list[tuple[str, int, str]]:
    """Every CODE line (comments and strings stripped) naming the bus-request register."""
    out: list[tuple[str, int, str]] = []
    for path in source_files():
        rel = path.relative_to(REPO).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        for n, raw in enumerate(text.splitlines(), start=1):
            line = _strip(raw)
            if RE_BUS_REGISTER.search(line):
                out.append((rel, n, line.strip()))
    return out


def test_no_hand_spelled_bus_hold_remains():
    """The machine-checked form of "every 68k Z80-bus hold is a bracket".

    A hold has to WRITE the bus-request register, and code can only reach that
    register by naming it (`Z80_BUS_REQUEST`) or its address (`$A11100`). So: outside
    its one definition and the one context that brackets it, no CODE line anywhere in
    engine/ or games/ may name it. That rules out a hand-spelled `move.w #$0100, …`, a
    `lea`/`movea`/`dc.l` preload of the address into a register for a later
    `move.w dN,(aN)` (the exact shape boot used until LS-13b — its BootData
    `dc.l Z80_BUS_REQUEST` would have been this rule's only other hit), and a second bus
    context.

    Both allowed files are checked to still carry the definition / declaration, so a
    rename fails here rather than quietly exempting a file that no longer does the job.

    WHAT IT CANNOT SEE: an address assembled at runtime from parts, or one read from a
    table authored outside engine/ and games/. Neither exists today; this is a text rule.
    """
    mentions = bus_register_code_mentions()
    print(f"code lines naming the Z80 bus-request register: {len(mentions)}")
    for rel, n, line in mentions:
        print(f"  {rel}:{n}  {line}")

    ctx_text = [_strip(l) for l in (REPO / BUS_CONTEXT_FILE).read_text(encoding="utf-8").splitlines()]
    def_text = [_strip(l) for l in (REPO / BUS_REGISTER_DEF_FILE).read_text(encoding="utf-8").splitlines()]
    assert any(RE_BUS_CONTEXT_DECL.match(l) for l in ctx_text), (
        f"{BUS_CONTEXT_FILE} no longer declares `context z80_stopped` — the exemption "
        "below would be exempting a file that is not the bus bracket."
    )
    assert any(RE_BUS_REGISTER_DEF.match(l) for l in def_text), (
        f"{BUS_REGISTER_DEF_FILE} no longer defines `const Z80_BUS_REQUEST` — re-point "
        "BUS_REGISTER_DEF_FILE at the definition."
    )
    # Positive control: the rule must actually be SEEING the context's own writes, or
    # an empty `offenders` below would be vacuous.
    assert any(rel == BUS_CONTEXT_FILE for rel, _, _ in mentions), (
        f"no code line in {BUS_CONTEXT_FILE} names the bus-request register; the scan is "
        "not seeing the context's acquire/release, so it cannot see a hand-spelled hold."
    )

    offenders = []
    for rel, n, line in mentions:
        if rel == BUS_CONTEXT_FILE:
            continue
        if rel == BUS_REGISTER_DEF_FILE and RE_BUS_REGISTER_DEF.match(line):
            continue
        offenders.append(f"  {rel}:{n}  {line}")
    assert not offenders, (
        "CODE outside the `z80_stopped` context names the Z80 bus-request register. That "
        "is either a hand-spelled bus hold or the preload for one, and it gets none of "
        "the compiler's pairing proofs; a register-indirect or non-literal write is also "
        "invisible to sigil's [bus.*] tier (LS-13b). Use `with z80_stopped { … }` — "
        "with `z80_stopped(interleave: asm { … })` if a statement must sit between the "
        "bus request and the grant spin:\n" + "\n".join(offenders)
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
    test_reset_entry_holds_precede_the_first_sr_write()
    test_no_hand_spelled_bus_hold_remains()
    test_comment_prose_cannot_satisfy_a_mechanism()
    print("OK")
