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
  * INTERPROCEDURAL CLASSIFICATION. A bracket in a helper whose caller masks is
    flagged (correctly by this rule, which is that the transaction masks). The
    direction that used to lose coverage — a `jbsr` between a mechanism-2 mask and
    its bracket lowering the mask inside the callee — is CLOSED as of 2026-09-18 by
    the spanned-call arm at the bottom of this file
    (`test_spanned_mask_calls_resolve_and_never_write_sr`): every call in such a span
    is resolved to a proc and the full transitive closure of that proc is required to
    contain no `sr` write, with anything unresolvable failing rather than skipping.
    The count of sites in that shape is DERIVED and printed by
    `test_every_bus_hold_is_masked` and by the arm on every run, not remembered here.
    What the arm still cannot see is listed in its own block comment; the largest is
    sigil's non-context splices (`assert`), a cross-repo premise.
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
    the site (the interprocedural hole — counted here, and since 2026-09-18 also
    ASSERTED by the spanned-call arm at the bottom of this file).
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



# --------------------------------------------------------------------------------
# THE SPANNED-CALL ARM (BUS-HOLD-SPANNED-CALLS, closed 2026-09-18).
#
# The hole it closes is the first bullet of "WHAT IT DOES NOT COVER" above, booked
# in docs/DEFERRED_WORK.md: mechanism 2 (HAND_2700) reads a `move.w #$2700, sr`
# earlier in the same proc, and a CALL sitting between that write and the bracket
# could lower the mask inside the callee. Until now the census COUNTED those sites
# and asserted nothing about them.
#
# WHAT THE ARM DOES. For each such site it takes every call between the mask and
# the bracket, resolves it to a proc DEFINITION in this tree, and walks the FULL
# TRANSITIVE CLOSURE of that proc's own calls, requiring that no proc in the
# closure writes `sr`. It also requires the CALLER's own span between the mask and
# the bracket to contain no `sr` write other than a re-mask — the non-call half of
# the same question, which mechanism 2 also did not check (the scanner ends
# mechanism 2 on `move.w (sp)+, sr` and on nothing else).
#
# DEPTH: UNBOUNDED — the full closure, not a bounded walk. That is sound and it
# terminates: the property is monotone reachability ("does the reachable set
# contain an `sr` write"), so a visited set loses nothing and a call CYCLE simply
# stops adding members. `WALK_VISIT_CEILING` exists only to stop a pathological
# tree hanging the build lane, and reaching it is a FAILURE ("not measured"),
# never a clean result — the one shape a bound must never take.
# `spanned_call_audit()` prints the deepest level actually reached on every run,
# so "unbounded" is a measurement rather than a claim.
#
# WHAT THE RESOLVER CAN SEE:
#   * every control transfer OUT of a reachable proc, not only `jbsr`: `jsr`, `bsr`,
#     `jbra`, `jmp`, every `b<cc>`/`jb<cc>` and every `db<cc>`. A TAIL CALL IS A CALL
#     (`jbra Other` leaves the proc exactly as `jbsr Other` does, and this tree has 383
#     of them), and an edge type the walker did not follow would be a hole of the same
#     class as the one it closes — a silent one, since a missing edge is not even an
#     unresolved call. Nearly all branch targets are `.local` labels and resolve to the
#     enclosing proc, which is already scanned in full.
#   * `jbsr Name` / `jsr Name` / `bsr(.w|.s|.b|.l) Name` where `Name` has exactly
#     one `proc Name (...) {` DEFINITION under engine/ or games/. The `{` on the
#     proc line is what separates a definition from a contract DECLARATION
#     (`proc entry: GameState`) or a binding (`proc entry = GameState_X`);
#     `test_every_proc_line_without_a_brace_is_a_declaration_or_a_binding` keeps
#     that rule honest instead of assumed.
#   * `jbsr .local_label`, resolved to the ENCLOSING proc — whose whole body, the
#     label's block included, is already scanned, so it adds nothing to the
#     closure. The label must really be DEFINED there or the call is unresolved.
#   * `with <context>` inside any reachable proc: the context must be declared in
#     this tree and its spliced acquire/release must be provably unable to LOWER
#     the mask (`context_mask_verdicts()`, read from the declaring file's text).
#
# WHAT IT CANNOT SEE — every one of these FAILS the arm rather than passing it,
# because in a green result an unresolved call and a cleared call are the same
# artifact:
#   * a register-indirect or computed target (`jsr (a0)`, `jsr (a1,d1.w)`);
#   * an absolute target outside the proc index (`jsr (MDDBG__ErrorHandler).l` —
#     the vendored MD Debugger is `.asm` and has no `proc` definition);
#   * a name with MORE THAN ONE definition in the tree (today `entry`,
#     `TestSolid_Init`, `TestSolid_Main`) — ambiguous, so undecidable here;
#   * an alias binding, a macro, or a name defined outside the scanned roots;
#   * a `with` naming a context this tree does not declare.
#
# WHAT IT STILL DOES NOT MODEL, stated because it is not measured: sigil splices
# other than the declared contexts. `assert` is the one inside today's closure
# (BG_UploadTiles' DEBUG IPL assert). Its SR-neutrality is sigil's contract — a
# CROSS-REPO premise no check in this tree can grade from source. The declared
# contexts, by contrast, ARE measured here.
# --------------------------------------------------------------------------------

RE_CALL_OPERAND = re.compile(r"\b(?:jbsr|jsr|bsr(?:\.[wsbl])?)\s+(\S+)")
# A TAIL CALL is a call. `jbra Other` / `jmp Other` / `beq Other` leave this proc for
# another one exactly as `jbsr` does, and 383 `jbra` sit in this tree — an edge type the
# walker did not follow would be a hole of the SAME class this arm exists to close, and a
# silent one, because a missing edge is not even an unresolved call. So every control
# transfer is an edge. Almost all of them target a `.local` label, which resolves to the
# enclosing proc and adds nothing; the ones that name a proc are followed.
# The condition-code list is spelled out rather than written `b\w\w` so that `btst`,
# `bset`, `bclr`, `bchg` — and the identifiers `bit`, `body`, `blue` in this tree — cannot
# match: no two-letter prefix of any of them is a 68000 condition code.
_CC_ALT = r"cc|cs|eq|ge|gt|hi|le|ls|lt|mi|ne|pl|vc|vs|hs|lo|ra"
RE_BRANCH_OPERAND = re.compile(r"\b(?:j?b(?:" + _CC_ALT + r")|jmp)(?:\.[wsbl])?\s+(\S+)")
# `dbcc` puts the target SECOND.
RE_DBCC_OPERAND = re.compile(
    r"\bdb(?:f|t|" + _CC_ALT + r")(?:\.[wsbl])?\s+\S+\s*,\s*(\S+)"
)
RE_LOCAL_LABEL_DEF = re.compile(r"^\s*(\.\w+)\s*:")
RE_WITH_NAME = re.compile(r"\bwith\s+([A-Za-z_]\w*)")
RE_CONTEXT_DECL_ANY = re.compile(r"^\s*(?:pub\s+)?context\s+(\w+)")
RE_PLAIN_NAME = re.compile(r"^[A-Za-z_]\w*$")
# A `proc` line with no body brace is legitimate in exactly two shapes.
RE_PROC_DECLARATION = re.compile(r"^\s*(?:pub\s+)?proc\s+\w+\s*:\s*\w+\s*$")
RE_PROC_BINDING = re.compile(r"^\s*(?:pub\s+)?proc\s+\w+\s*=\s*\w+\s*$")

# The only `sr` DESTINATION writes a context splice may contain and still be
# provably unable to lower an established $2700 mask:
#   `move.w #$2700, sr`  raises to the full mask (it can never lower);
#   `move.w (sp)+, sr`   restores the value the SAME bracket's acquire pushed,
#                        i.e. the mask that stood at entry.
# Anything else — `move.w d0, sr`, `andi.w #$F8FF, sr`, `move.w #$2300, sr` — is
# not provably neutral and disqualifies the context.
RE_CTX_RAISE = re.compile(r"\bmove\.w\s+#\$2700\s*,\s*sr\b")
RE_CTX_RESTORE = re.compile(r"\bmove\.w\s+\(sp\)\+\s*,\s*sr\b")
RE_CTX_SAVE = re.compile(r"\bmove\.w\s+sr\s*,\s*-\(sp\)")

# A walk needing more than this many proc visits is not measured, it is stuck.
# Today's two closures visit 1 and 3. Reaching the ceiling FAILS the arm.
WALK_VISIT_CEILING = 2000

_PROC_INDEX_CACHE: dict | None = None
_CONTEXT_CACHE: dict | None = None


def proc_definitions_in(rel: str, raw_lines: list[str]) -> list[dict]:
    """Every `proc NAME (...) {` DEFINITION in one source text, with its body.

    Brace-tracked from the proc line, so a nested `if DEBUG == 1 { ... }` does not
    end the body early and the next `proc` in the file does not have to.
    """
    out: list[dict] = []
    stripped = [_strip(l) for l in raw_lines]
    i = 0
    while i < len(stripped):
        m = RE_PROC.match(stripped[i])
        if not m or "{" not in stripped[i]:
            i += 1
            continue
        depth = 0
        j = i
        while j < len(stripped):
            depth += stripped[j].count("{") - stripped[j].count("}")
            if depth <= 0:
                break
            j += 1
        end = min(j, len(stripped) - 1)
        out.append(
            {
                "name": m.group(1),
                "file": rel,
                "start": i + 1,
                "end": end + 1,
                "lines": [(n + 1, stripped[n]) for n in range(i, end + 1)],
            }
        )
        i = end + 1
    return out


def build_proc_index(records: list[dict]) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    by_name: dict[str, list[dict]] = {}
    for rec in records:
        by_name.setdefault(rec["name"], []).append(rec)
    unique = {k: v[0] for k, v in by_name.items() if len(v) == 1}
    ambiguous = {k: v for k, v in by_name.items() if len(v) > 1}
    return unique, ambiguous


def proc_index() -> tuple[dict[str, dict], dict[str, list[dict]]]:
    """(unique name -> definition, ambiguous name -> every definition of it)."""
    global _PROC_INDEX_CACHE
    if _PROC_INDEX_CACHE is None:
        records: list[dict] = []
        for path in source_files():
            rel = path.relative_to(REPO).as_posix()
            records.extend(
                proc_definitions_in(
                    rel, path.read_text(encoding="utf-8", errors="replace").splitlines()
                )
            )
        unique, ambiguous = build_proc_index(records)
        _PROC_INDEX_CACHE = {"unique": unique, "ambiguous": ambiguous, "all": records}
    return _PROC_INDEX_CACHE["unique"], _PROC_INDEX_CACHE["ambiguous"]


def context_verdicts_in(rel: str, raw_lines: list[str]) -> dict[str, dict]:
    """Every `context NAME { ... }` in one source text, and whether its splices can
    LOWER an established $2700 mask."""
    out: dict[str, dict] = {}
    lines = [_strip(l) for l in raw_lines]
    i = 0
    while i < len(lines):
        m = RE_CONTEXT_DECL_ANY.match(lines[i])
        if not m:
            i += 1
            continue
        depth = 0
        opened = False
        j = i
        body: list[str] = []
        while j < len(lines):
            body.append(lines[j])
            depth += lines[j].count("{") - lines[j].count("}")
            if "{" in lines[j]:
                opened = True
            if opened and depth <= 0:
                break
            j += 1
        writes = [l for l in body if RE_SR_WRITE.search(l)]
        unsafe = [
            l.strip()
            for l in writes
            if not (RE_CTX_RAISE.search(l) or RE_CTX_RESTORE.search(l))
        ]
        if any(RE_CTX_RESTORE.search(l) for l in writes) and not any(
            RE_CTX_SAVE.search(l) for l in body
        ):
            unsafe.append(
                "restores `sr` from (sp)+ with no `move.w sr, -(sp)` save in the same "
                "context — the restored value is not this bracket's own"
            )
        out[m.group(1)] = {
            "file": rel,
            "line": i + 1,
            "sr_writes": [l.strip() for l in writes],
            "unsafe": unsafe,
        }
        i = j + 1
    return out


def context_mask_verdicts() -> dict[str, dict]:
    global _CONTEXT_CACHE
    if _CONTEXT_CACHE is None:
        out: dict[str, dict] = {}
        for path in source_files():
            out.update(
                context_verdicts_in(
                    path.relative_to(REPO).as_posix(),
                    path.read_text(encoding="utf-8", errors="replace").splitlines(),
                )
            )
        _CONTEXT_CACHE = out
    return _CONTEXT_CACHE


def calls_in(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Every control transfer OUT of these lines: calls AND branches/jumps.

    Branches are included because a tail call is a call (see RE_BRANCH_OPERAND). The
    overwhelming majority resolve to a `.local` label and therefore to the enclosing
    proc, which the walker has already scanned in full.
    """
    out: list[tuple[int, str]] = []
    for n, text in lines:
        for rx in (RE_CALL_OPERAND, RE_BRANCH_OPERAND, RE_DBCC_OPERAND):
            for m in rx.finditer(text):
                out.append((n, m.group(1).rstrip(",")))
    return out


def walk_from(seeds, unique, ambiguous, contexts) -> dict:
    """Transitive closure over `seeds` = [(operand, where, enclosing_proc_or_None)].

    Returns the closure, the deepest level reached, every `sr` write found inside
    it, and every call or `with` the resolver COULD NOT resolve. That last list is
    the point of the arm: an unresolved call is a hole, not a pass.
    """
    visited: dict[str, int] = {}
    sr_writes: list[str] = []
    unresolved: list[str] = []
    max_depth = 0
    visits = 0
    stack = [(op, 1, where, encl) for op, where, encl in seeds]

    seen_local: set[tuple[str, str]] = set()

    while stack:
        operand, depth, where, enclosing = stack.pop()
        visits += 1
        if visits > WALK_VISIT_CEILING:
            unresolved.append(
                f"the walk exceeded WALK_VISIT_CEILING ({WALK_VISIT_CEILING} visits) at "
                f"depth {depth} — NOT MEASURED. A ceiling that is reached is never a clean "
                f"result: raise it deliberately, or fix whatever made the graph explode."
            )
            break

        if operand.startswith("."):
            # A local label: its block lives inside the enclosing proc, whose whole
            # body is already scanned. It adds nothing to the closure and it is NOT a
            # depth level (control never left the proc), so it does not move max_depth.
            # Deduplicated per proc so a branch-heavy body cannot walk the visit ceiling.
            key = ((enclosing or {}).get("name", "?"), operand)
            if key in seen_local:
                continue
            seen_local.add(key)
            found = False
            if enclosing is not None:
                for _, t in enclosing["lines"]:
                    lm = RE_LOCAL_LABEL_DEF.match(t)
                    if lm and lm.group(1) == operand:
                        found = True
                        break
            if not found:
                unresolved.append(
                    f"{where}: local-label call `{operand}` is not defined in "
                    f"{(enclosing or {}).get('name', '<no enclosing proc>')} — cannot resolve"
                )
            continue

        max_depth = max(max_depth, depth)

        if not RE_PLAIN_NAME.match(operand):
            unresolved.append(
                f"{where}: call target `{operand}` is not a plain name (register-indirect, "
                f"absolute or computed) — this resolver cannot follow it"
            )
            continue

        if operand in ambiguous:
            sites = ", ".join(f"{r['file']}:{r['start']}" for r in ambiguous[operand])
            unresolved.append(
                f"{where}: `{operand}` has {len(ambiguous[operand])} proc definitions "
                f"({sites}) — ambiguous, so which body runs is not decidable here"
            )
            continue

        rec = unique.get(operand)
        if rec is None:
            unresolved.append(
                f"{where}: `{operand}` has no `proc {operand} (...) {{` definition under "
                f"{ROOTS} — a macro, an alias binding, an `.asm` label, or a name from "
                f"outside the scanned roots. Unresolved, therefore UNMEASURED"
            )
            continue

        if operand in visited:
            continue
        visited[operand] = depth

        for n, text in rec["lines"]:
            if RE_SR_WRITE.search(text):
                sr_writes.append(
                    f"{rec['file']}:{n} in {operand} (depth {depth}, reached via {where}): "
                    f"{text.strip()}"
                )
            for m in RE_WITH_NAME.finditer(text):
                ctx = m.group(1)
                verdict = contexts.get(ctx)
                if verdict is None:
                    unresolved.append(
                        f"{rec['file']}:{n} in {operand}: `with {ctx}` names a context not "
                        f"declared under {ROOTS} — its spliced code is UNMEASURED"
                    )
                elif verdict["unsafe"]:
                    sr_writes.append(
                        f"{rec['file']}:{n} in {operand} (depth {depth}): `with {ctx}` splices "
                        f"code that is not provably mask-raising: {verdict['unsafe']}"
                    )

        for n, call in calls_in(rec["lines"]):
            stack.append((call, depth + 1, f"{rec['file']}:{n} in {operand}", rec))

    return {
        "closure": visited,
        "max_depth": max_depth,
        "sr_writes": sr_writes,
        "unresolved": unresolved,
    }


def spanned_call_audit() -> list[dict]:
    """One record per mechanism-2 bracket with a call between its mask and the hold."""
    sites, _ = scan_tree()
    unique, ambiguous = proc_index()
    contexts = context_mask_verdicts()
    out: list[dict] = []

    for site in sites:
        if site["calls_since_mask"] <= 0:
            continue
        rec = unique.get(site["proc"])
        if rec is None:
            out.append(
                {
                    "site": f"{site['file']}:{site['line']}",
                    "proc": site["proc"],
                    "mask_line": site["mask_line"],
                    "direct": [],
                    "closure": {},
                    "max_depth": 0,
                    "sr_writes": [],
                    "unresolved": [
                        f"{site['file']}:{site['line']}: the bracket's own proc "
                        f"`{site['proc']}` has no unique definition in the proc index — the "
                        f"span between the mask and the bracket cannot even be read"
                    ],
                }
            )
            continue

        span = [(n, t) for n, t in rec["lines"] if site["mask_line"] < n < site["line"]]
        direct = calls_in(span)
        # The non-call half of the same question: nothing may write `sr` between the
        # mask and the bracket in the CALLER either. `move.w (sp)+, sr` already ends
        # mechanism 2 in the scanner; every other write did not.
        caller_writes = [
            f"{rec['file']}:{n} in {site['proc']} (caller span): {t.strip()}"
            for n, t in span
            if RE_SR_WRITE.search(t) and not RE_MASK_SET.search(t)
        ]
        walk = walk_from(
            [(op, f"{rec['file']}:{n} in {site['proc']}", rec) for n, op in direct],
            unique,
            ambiguous,
            contexts,
        )
        out.append(
            {
                "site": f"{site['file']}:{site['line']}",
                "proc": site["proc"],
                "mask_line": site["mask_line"],
                "direct": direct,
                "closure": walk["closure"],
                "max_depth": walk["max_depth"],
                "sr_writes": caller_writes + walk["sr_writes"],
                "unresolved": walk["unresolved"],
            }
        )
    return out


def test_every_proc_line_without_a_brace_is_a_declaration_or_a_binding():
    """The proc INDEX's premise, and the reason it is a premise and not a guess.

    `proc_definitions_in` indexes a proc only when the body's `{` is on the proc
    line. If a real definition ever wraps its signature, the index would miss it,
    the walker would report the callee UNRESOLVED, and the arm would go red — loud,
    which is the right failure, but this names the cause at the source instead.
    Today the only brace-less `proc` lines are the contract declaration
    `proc entry: GameState` and the two game bindings `proc entry = ...`.
    """
    odd: list[str] = []
    for path in source_files():
        rel = path.relative_to(REPO).as_posix()
        for n, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            line = _strip(raw)
            if RE_PROC.match(line) and "{" not in line:
                if RE_PROC_DECLARATION.match(line) or RE_PROC_BINDING.match(line):
                    continue
                odd.append(f"  {rel}:{n}  {line.strip()}")
    assert not odd, (
        "a `proc` line carries no body `{` and is neither a contract declaration "
        "(`proc NAME: Type`) nor a binding (`proc NAME = Target`). "
        "`proc_definitions_in` would not index it, so the spanned-call walker cannot "
        "resolve calls to it. Put the `{` on the proc line, or teach the index the new "
        "shape:\n" + "\n".join(odd)
    )


def test_declared_contexts_cannot_lower_an_established_mask():
    """The premise the walker leans on when a reachable proc brackets something.

    A `with <ctx>` splices code the source text does not show, so the walker cannot
    read it at the CALL SITE; it reads it at the DECLARATION instead. Every context
    declared in the tree must only ever raise the mask to $2700 or restore what its
    own acquire saved. This is measured from engine/irq.emp and engine/z80_bus.emp,
    not remembered.
    """
    verdicts = context_mask_verdicts()
    print(f"declared contexts: {sorted(verdicts)}")
    for name in sorted(verdicts):
        v = verdicts[name]
        print(f"  {name:<20} {v['file']}:{v['line']} sr writes={v['sr_writes']} unsafe={v['unsafe']}")
    assert verdicts, (
        "no `context` declaration found anywhere under "
        f"{ROOTS} — the sweep is not reaching engine/irq.emp and this check is vacuous."
    )
    # Non-vacuity: at least one context must actually CONTAIN `sr` writes, or this
    # check is grading a population of splices that touch nothing.
    assert any(v["sr_writes"] for v in verdicts.values()), (
        "no declared context contains an `sr` write. engine/irq.emp's `ints_off` does "
        "(save/raise/restore), so either the context bodies are not being read or the "
        "`sr` matcher has stopped matching — either way this check is vacuous."
    )
    offenders = [
        f"  {name} ({verdicts[name]['file']}:{verdicts[name]['line']}): {verdicts[name]['unsafe']}"
        for name in sorted(verdicts)
        if verdicts[name]["unsafe"]
    ]
    assert not offenders, (
        "a declared context splices an `sr` write that is not provably mask-RAISING. Any "
        "proc reachable from a mechanism-2 span could then lower the mask between the "
        "hand-spelled $2700 and the bus hold, and the spanned-call arm's closure walk "
        "would not see it (the splice is not in the caller's text):\n" + "\n".join(offenders)
    )


def test_spanned_mask_calls_resolve_and_never_write_sr():
    """THE ARM. Mechanism 2's interprocedural hole, closed.

    For every mechanism-2 bracket with a call between the mask and the hold, every
    call in that span resolves to a proc in this tree and no proc in the FULL
    transitive closure writes `sr`. Anything the resolver could not follow fails
    here rather than passing quietly — see the block comment above for exactly what
    it can and cannot see.

    NO POPULATION FLOOR IS ASSERTED. The population is a property of the tree, not
    of this check, and it has legitimately been 1 (2026-09-09) and 2 (2026-09-17,
    2026-09-18). It is PRINTED on every run instead, and the two synthetic controls
    below are what keep the mechanism non-vacuous if it ever goes to 0.
    """
    audit = spanned_call_audit()
    print(f"mechanism-2 spanned sites audited: {len(audit)}")
    for rec in audit:
        named = [c for _, c in rec["direct"] if not c.startswith(".")]
        local = [c for _, c in rec["direct"] if c.startswith(".")]
        print(
            f"  {rec['site']} in {rec['proc']} (mask at :{rec['mask_line']}): "
            f"{len(named)} transfer(s) naming a proc {named} + {len(local)} local branch(es), "
            f"closure {sorted(rec['closure'])} (max depth {rec['max_depth']}, unbounded walk)"
        )

    unresolved = [(r["site"], u) for r in audit for u in r["unresolved"]]
    assert not unresolved, (
        "the spanned-call walk could not RESOLVE part of a mechanism-2 span. That is not "
        "a pass: an unresolved call and a cleared call are indistinguishable in a green "
        "result, so this arm refuses instead of skipping. Resolve it by hand and either "
        "teach the resolver the shape or restructure the call:\n"
        + "\n".join(f"  {site}: {msg}" for site, msg in unresolved)
    )

    writes = [(r["site"], w) for r in audit for w in r["sr_writes"]]
    assert not writes, (
        "a proc reachable between a hand-spelled `move.w #$2700, sr` and its Z80 bus hold "
        "writes `sr`. Mechanism 2's whole claim is that the mask still stands AT the "
        "bracket; if the callee lowers it, an IRQ6 can land in the spliced `.wait_z80` "
        "spin, release the bus, and return to a poll that never re-issues the request "
        "(this module's header). Either the write must go, or the bracket must be masked "
        "by a mechanism that does not span it (`with ints_off { ... }` around the hold "
        "itself):\n" + "\n".join(f"  {site}: {w}" for site, w in writes)
    )


# The control seeds below say "<control seed>" rather than a `file.emp:LINE`
# coordinate on purpose: tools/ is LIVE scope for tools/test_citation_form.py, and a
# `.emp:N` literal in a SYNTHETIC fixture is a citation to a file that does not exist.
# The landing lane caught exactly that on 2026-09-18. The synthetic file NAMES are
# fine; only a name-plus-line-number reads as a citation.
def _control_index(sources: dict[str, str]):
    records: list[dict] = []
    for rel, text in sources.items():
        records.extend(proc_definitions_in(rel, text.splitlines()))
    return build_proc_index(records)


def test_the_walk_catches_an_sr_write_at_depth_two():
    """Control: TRANSITIVITY, not just the direct callee.

    An arm that only looked at direct callees would pass every direct-callee
    mutation and read as working. This drives the real `walk_from` over a synthetic
    chain A -> B -> C where only C writes `sr`, and requires it named at depth 3.
    The negative half — the same chain with the write removed — must come back
    clean, or the positive half proves nothing.
    """
    chain = {
        "engine/ctl.emp": (
            "pub proc CtlA () clobbers() {\n"
            "        jbsr    CtlB\n"
            "        rts\n"
            "}\n"
            "pub proc CtlB () clobbers() {\n"
            "        jbsr    CtlC\n"
            "        rts\n"
            "}\n"
            "pub proc CtlC () clobbers() {\n"
            "        move.w  d0, sr\n"
            "        rts\n"
            "}\n"
        )
    }
    unique, ambiguous = _control_index(chain)
    assert sorted(unique) == ["CtlA", "CtlB", "CtlC"], f"control index built {sorted(unique)}"
    got = walk_from([("CtlA", "<control seed>", None)], unique, ambiguous, {})
    assert not got["unresolved"], f"control chain should resolve cleanly: {got['unresolved']}"
    assert got["max_depth"] == 3, f"expected to reach depth 3, reached {got['max_depth']}"
    assert len(got["sr_writes"]) == 1 and "CtlC" in got["sr_writes"][0] and "depth 3" in got["sr_writes"][0], (
        "the walk did not name the depth-3 `sr` write; it is not transitive: "
        f"{got['sr_writes']}"
    )
    clean = {"engine/ctl.emp": chain["engine/ctl.emp"].replace("move.w  d0, sr", "nop")}
    u2, a2 = _control_index(clean)
    got2 = walk_from([("CtlA", "<control seed>", None)], u2, a2, {})
    assert not got2["sr_writes"] and not got2["unresolved"] and got2["max_depth"] == 3, (
        f"the negative half of the control did not come back clean: {got2}"
    )


def test_the_walk_follows_a_tail_call():
    """Control: a `jbra` to another proc is an EDGE, not a line the walker skips.

    Without this, a callee could tail-call something that lowers the mask and the arm
    would come back green having never looked — the silent form of the very hole it
    exists to close. The negative half pins the discrimination: the same chain with the
    `sr` write removed comes back clean, so the red is the write and not the `jbra`.
    """
    chain = {
        "engine/tail.emp": (
            "pub proc TailA () clobbers() {\n"
            "        beq     .skip\n"
            "        jbra    TailB\n"
            "    .skip:\n"
            "        rts\n"
            "}\n"
            "pub proc TailB () clobbers() {\n"
            "        move.w  d0, sr\n"
            "        rts\n"
            "}\n"
        )
    }
    unique, ambiguous = _control_index(chain)
    got = walk_from([("TailA", "<control seed>", None)], unique, ambiguous, {})
    assert not got["unresolved"], (
        f"the local branch `beq .skip` or the tail call did not resolve: {got['unresolved']}"
    )
    assert "TailB" in got["closure"], (
        "the walk did not follow `jbra TailB`, so a tail call is invisible to it: "
        f"closure {sorted(got['closure'])}"
    )
    assert len(got["sr_writes"]) == 1 and "TailB" in got["sr_writes"][0], got["sr_writes"]
    clean = {"engine/tail.emp": chain["engine/tail.emp"].replace("move.w  d0, sr", "nop")}
    u2, a2 = _control_index(clean)
    got2 = walk_from([("TailA", "<control seed>", None)], u2, a2, {})
    assert not got2["sr_writes"] and not got2["unresolved"] and "TailB" in got2["closure"], (
        f"the negative half of the tail-call control did not come back clean: {got2}"
    )


def test_the_walk_refuses_every_shape_it_cannot_resolve():
    """Control: LOUD ON UNMEASURABLE.

    Each shape below is something a `.emp` tree really contains and this resolver
    really cannot follow. Every one must appear in `unresolved` — never be skipped,
    and never be mistaken for a cleared call.
    """
    sources = {
        "engine/u.emp": (
            "pub proc Seed () clobbers() {\n"
            "        jsr     (a0)\n"                    # register-indirect
            "        jsr     (MDDBG__ErrorHandler).l\n" # absolute, outside the index
            "        jbsr    NotAProcAnywhere\n"        # no definition
            "        jbsr    Twice\n"                   # ambiguous
            "        jbsr    .never_defined\n"          # local label with no block
            "        with unknown_ctx {\n"
            "            nop\n"
            "        }\n"
            "        rts\n"
            "}\n"
        ),
        "engine/d1.emp": "pub proc Twice () clobbers() {\n        rts\n}\n",
        "engine/d2.emp": "pub proc Twice () clobbers() {\n        rts\n}\n",
    }
    unique, ambiguous = _control_index(sources)
    assert "Twice" in ambiguous and "Seed" in unique, f"{sorted(unique)} / {sorted(ambiguous)}"
    got = walk_from([("Seed", "<control seed>", None)], unique, ambiguous, {})
    blob = "\n".join(got["unresolved"])
    for needle, why in (
        ("(a0)", "register-indirect call"),
        ("MDDBG__ErrorHandler", "absolute call outside the proc index"),
        ("NotAProcAnywhere", "call to a name with no proc definition"),
        ("ambiguous", "call to a name with two definitions"),
        (".never_defined", "local-label call with no block in the proc"),
        ("unknown_ctx", "`with` naming an undeclared context"),
    ):
        assert needle in blob, (
            f"the walk did not refuse the {why}; it is silently skipping a shape it cannot "
            f"measure. unresolved was:\n{blob}"
        )
    assert not got["sr_writes"], f"no control source writes sr: {got['sr_writes']}"

if __name__ == "__main__":
    test_the_scan_reaches_the_tree()
    test_vblank_capability_has_exactly_one_grant_root()
    test_bracket_population_has_not_shrunk()
    test_every_bus_hold_is_masked()
    test_reset_entry_holds_precede_the_first_sr_write()
    test_no_hand_spelled_bus_hold_remains()
    test_comment_prose_cannot_satisfy_a_mechanism()
    test_every_proc_line_without_a_brace_is_a_declaration_or_a_binding()
    test_declared_contexts_cannot_lower_an_established_mask()
    test_spanned_mask_calls_resolve_and_never_write_sr()
    test_the_walk_catches_an_sr_write_at_depth_two()
    test_the_walk_follows_a_tail_call()
    test_the_walk_refuses_every_shape_it_cannot_resolve()
    print("OK")
