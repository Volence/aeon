#!/usr/bin/env python3
"""
sound_api bus-hold mask lint — every `with z80_stopped` in engine/sound/sound_api.emp
must be entered with 68k interrupts masked.

WHAT THE INVARIANT IS, and it is the FILE'S OWN, quoted from its header:

    "So every transaction holds the bus, with interrupts masked so a VBlank
     stopZ80/startZ80 pair ... can't release the bus mid-write."

WHY IT IS A CORRECTNESS RULE AND NOT A STYLE ONE. `z80_stopped` (engine/z80_bus.emp)
splices `move.w #$0100, Z80_BUS_REQUEST` ONCE, ABOVE its `.wait_z80` poll, and the hold is
a LATCH, not a counter — z80_bus.emp says so in as many words: "an inner release frees the
outer hold". So an IRQ6 landing anywhere in that spliced spin runs VInt_Level / VInt_Lag,
whose own `with z80_stopped` brackets (engine/system/vblank.emp, sound-ON) and
`Read_Controllers`' unconditional one (engine/system/controllers.emp) each RELEASE the bus
on the way out; `rte` returns into `.wait_z80`, bit 0 reads 1 again, and NOTHING below that
label re-issues the request. Either the spin never exits, or it exits on a stale grant and
the body then writes Z80 RAM with the Z80 live. An IRQ6 landing in the BODY instead is the
milder half of the same fault (the writes are silently dropped) and is what
engine/level/parallax.emp's masked reg-$0B bracket documents.

`Sound_PlayMusic`'s `.await_slot` was the one site in this file that did not mask, from the
repost gate's introduction until 2026-09-07 (lens sweep item LS-11). The DEBUG
`SPIN_WATCHDOG_LIMIT` counter did not cover it: the counter decrements on the OUTER
`.await_slot` iteration, one level ABOVE the spliced inner spin, so the shape that exists
to make a wedge loud stayed silent through exactly this one.

WHAT THIS LINT CHECKS, all of it derived from the file it reads:
  * every `with z80_stopped` in sound_api.emp is masked at entry, by EITHER an enclosing
    `with ints_off { … }` (the Sound_PostByte / Sound_ReadStat / Sound_PlayMusic shape) OR
    a hand-spelled `move.w #$2700, sr` earlier in the same proc with no intervening
    `move.w (sp)+, sr` (the Sound_Init / Sound_DrainSfxRing shape, named in
    engine/irq.emp:58-63 as the deliberate hand-spelled class);
  * the file's HEADER (everything above the `module` line, and only that — a control
    proved the whole-file search was satisfiable by the fix's own restatement of the rule)
    still STATES the rule the check enforces. If the header sentence is deleted or reworded
    past recognition, this lint has lost its premise and fails loudly rather than guarding a
    rule the file no longer claims;
  * a population FLOOR of six bracket sites. That is a floor and NOT a census: it catches a
    site being deleted out from under the check, it does NOT catch the file being split so
    that new brackets live somewhere else.

WHAT IT DOES NOT COVER, and each of these is a real hole:
  * ANY OTHER FILE. Counted 2026-09-07: SIXTEEN more `with z80_stopped` brackets across
    eight files — vblank.emp 6, section.emp 3, bg.emp 2, boot.emp 1, controllers.emp 1,
    parallax.emp 1, sound_debug.emp 1, ojz_scroll_test.emp 1. (Derived by
    `grep -rn "with z80_stopped" engine games`, 18 hits, less the two that are prose:
    section.emp:300 and controllers.emp:12.) Several are correct only because of a mask
    established many lines above them, or because they run in interrupt context where the
    68000's own IPL is the mask — neither of which this file-scoped text rule models. Do
    not read a green run here as a statement about them.
    RE-DERIVED 2026-09-07 (LS-13 parcel) and the sixteen HOLD, by a differently-shaped
    grep: 27 hits for "with z80_stopped" across engine+games, less 5 prose lines, = 22
    code sites, of which sound_api's 6 are this lint's subject. The full census, with
    each site's masking mechanism and shape gate, now lives in engine/z80_bus.emp's
    header — that is the file to update, not this docstring.
  * THE ONE HOLD THAT IS NOT A BRACKET AT ALL, and so is invisible to any grep for
    `with z80_stopped`: engine/system/boot.emp:132-156 spells its own bus
    request/spin/release by hand around the Z80 driver-blob copy. Found by grepping for
    `Z80_BUS_REQUEST|Z80_RESET|A11100|A11200` instead — the search shape that enumerates
    by what TOUCHES the register rather than by what names the context. It is masked (the
    reset SR is still standing; boot's first `sr` write is at :266), but nothing checks
    that, here or in sigil.
  * A MASK ESTABLISHED BY A CALLER. A proc in this file that is only ever reached with SR
    already at $2700 would be flagged, and correctly so — the rule is that the transaction
    masks — but the converse hole is real for the other files above.
  * RUNTIME. Nothing here executes a ROM. It cannot show that the deadlock is gone, only
    that the instruction that closes the window is emitted. Reproducing the original hang
    needs an IRQ6 to land inside a ~5-instruction window during a `config_a` hotkey press.
  * The inner `.wait_z80` spin remains OUTSIDE `SPIN_WATCHDOG_LIMIT`'s reach in every shape.
    The mask is what bounds it; the watchdog is not a net for it and this lint does not make
    it one.

IT IS A TEXT LINT, deliberately, and in the same family as
tools/test_parallax_publish_order_lint.py for the same reason build.sh's own header gives:
the pytest lane runs BEFORE sigil, so a test that opened s4.bin would grade the PREVIOUS
build's artifact. A byte-level twin would have to be wired below sigil as its own step.

Runner: build.sh's tool-suite pytest sweep (`python3 -m pytest "${TOOLS}"`, build-fatal),
which collects `tools/test_*.py` by directory glob. Also runnable standalone:
`python3 tools/test_sound_bus_hold_mask_lint.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SUBJECT = REPO / "engine" / "sound" / "sound_api.emp"

# The header sentence the whole check is derived from. Matched loosely (whitespace-
# and line-break-insensitive) so reflowing the comment does not fail the build, but
# strictly enough that deleting the claim does.
RULE_SENTENCE = re.compile(
    r"every transaction holds the bus,\s*(?://\s*)?with interrupts masked",
    re.IGNORECASE,
)

# Six is the count on this file today, enumerated by hand and re-derived by this lint on
# every run (the test prints it). A FLOOR, not a census — see the docstring.
MIN_BRACKETS = 6

RE_PROC = re.compile(r"^\s*(?:pub\s+)?proc\s+(\w+)")
RE_Z80 = re.compile(r"\bwith\s+z80_stopped\b")
RE_INTS_OFF = re.compile(r"\bwith\s+ints_off\b")
RE_MASK_SET = re.compile(r"move\.w\s+#\$2700\s*,\s*sr")
RE_MASK_RESTORE = re.compile(r"move\.w\s+\(sp\)\+\s*,\s*sr")


def _strip_comment(line: str) -> str:
    """Drop a trailing `//` comment. No string literals carry `//` in this file."""
    idx = line.find("//")
    return line if idx < 0 else line[:idx]


def scan(text: str) -> list[dict]:
    """Return one record per `with z80_stopped` bracket: line, proc, how it is masked."""
    sites: list[dict] = []
    proc = None
    # Depth of the innermost open `with ints_off {` blocks, as brace depths at which they
    # were opened. A bracket is inside one while the running depth is greater.
    ints_off_depths: list[int] = []
    hand_masked = False
    depth = 0

    for n, raw in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw)

        m = RE_PROC.match(line)
        if m:
            proc = m.group(1)
            ints_off_depths = []
            hand_masked = False
            depth = 0

        opens = line.count("{")
        closes = line.count("}")

        if RE_MASK_SET.search(line):
            hand_masked = True
        if RE_MASK_RESTORE.search(line):
            hand_masked = False

        if RE_Z80.search(line):
            sites.append(
                {
                    "line": n,
                    "proc": proc,
                    "text": raw.strip(),
                    "ints_off": bool(ints_off_depths),
                    "hand_masked": hand_masked,
                }
            )

        if RE_INTS_OFF.search(line):
            # The `{` on this line opens the ints_off body.
            ints_off_depths.append(depth)

        depth += opens - closes
        while ints_off_depths and depth <= ints_off_depths[-1]:
            ints_off_depths.pop()

    return sites


def header_block(text: str) -> str:
    """The file header — everything ABOVE the `module` declaration.

    Scoped deliberately, and the scoping was forced by a control: with the whole file
    searched, deleting the header sentence still passed, because the fix at `.await_slot`
    QUOTES the rule in its own comment and the search found the restatement. A premise
    check that a restatement can satisfy is not a premise check.
    """
    m = re.search(r"^\s*module\s+engine\.sound_api\b", text, re.MULTILINE)
    assert m, (
        f"{SUBJECT.relative_to(REPO)} has no `module engine.sound_api` declaration — the "
        f"file this lint reads is not the file it was written for."
    )
    return text[: m.start()]


def test_header_still_states_the_rule():
    text = header_block(SUBJECT.read_text())
    assert RULE_SENTENCE.search(text), (
        f"{SUBJECT.relative_to(REPO)} no longer states the mask rule this lint enforces "
        f"(looked for 'every transaction holds the bus, with interrupts masked' in the "
        f"header). Either the rule changed — in which case re-derive this lint — or the "
        f"sentence was lost in an edit. This test is NOT a check on the code."
    )


def test_bracket_population_has_not_shrunk():
    sites = scan(SUBJECT.read_text())
    print(f"`with z80_stopped` brackets in {SUBJECT.relative_to(REPO)}: {len(sites)}")
    for s in sites:
        how = "ints_off" if s["ints_off"] else ("#$2700,sr" if s["hand_masked"] else "UNMASKED")
        print(f"  :{s['line']:<4} {s['proc']:<20} {how}")
    assert len(sites) >= MIN_BRACKETS, (
        f"only {len(sites)} `with z80_stopped` bracket(s) found, floor is {MIN_BRACKETS}. "
        f"A site was deleted or the file was split. This is a FLOOR, not a census: it "
        f"cannot see brackets that moved to another file, which this lint does not read."
    )


def test_every_bus_hold_is_masked():
    sites = scan(SUBJECT.read_text())
    unmasked = [s for s in sites if not (s["ints_off"] or s["hand_masked"])]
    assert not unmasked, (
        "unmasked `with z80_stopped` bracket(s) in "
        f"{SUBJECT.relative_to(REPO)} — an IRQ6 landing in the spliced `.wait_z80` spin "
        "releases the bus latch and nothing re-issues the request (see this file's "
        "docstring and engine/z80_bus.emp:8-10):\n"
        + "\n".join(f"  :{s['line']} in {s['proc']}: {s['text']}" for s in unmasked)
        + "\nMask it with `with ints_off { … }`, or with a hand-spelled "
        "`move.w #$2700, sr` earlier in the proc if the site is one of the loop shapes "
        "engine/irq.emp:58-63 names. NOTE: this check reads sound_api.emp ONLY — the "
        "sixteen brackets in the tree's other eight files are not covered."
    )


if __name__ == "__main__":
    test_header_still_states_the_rule()
    test_bracket_population_has_not_shrunk()
    test_every_bus_hold_is_masked()
    print("OK")
