#!/usr/bin/env python3
"""
Timer-A tick banked-ROM/DMA guard lint — every Timer-A tick path in
engine/sound/z80_sound_driver.emp that reaches banked ROM must test
SND_CTRL_DMA_ACTIVE first, and must do it BEFORE the timer is re-armed.

WHAT THE RULE IS. The 2026-08-09 user ruling (commit dcc74329, "TimerA-tick
bulk-refill defers on active 68k DMA (fail-closed; user-ruled 2026-08-09)"):
banked ROM reads through the $8000 window while the 68k holds the bus for a DMA
are an address-line-glitch hazard on real hardware, so the Z80 must poll
SND_CTRL_DMA_ACTIVE and not read ROM while it is set. It is a hardware-class
rule: no emulator in this project models cartridge-bus contention, so NOTHING
here or anywhere else in the tree can observe the hazard or the fix. That is
exactly why it needs a static check — a runtime one is not available at any
price.

WHY THIS LINT EXISTS. The ruling landed on ONE of the tick's three banked-ROM
stages. Lens item LS-12 (2026-09-06): SndDrv_TimerATick's step-2
Run_SeqFrame_OnSongBank (the sequencer streams the song and its patch tables
through the window) and step-3 Snd_PollMailbox_Banked (Snd_LoadSong / SfxDispatch
read the song table and SFX blobs through it) had no check at all, and could not
acquire one by accident: the hot loop's Timer-A poll (SndDrv_Sample's
`jp nz, SndDrv_TimerATick`) is emitted ABOVE `.dma_check`, so a pass that takes
the tick never executes the flag load.

WHAT THIS LINT CHECKS, all of it from CODE lines with `//` comments stripped, so
that no comment — this file's, or the subject's — can satisfy any check:

  1. GUARD BEFORE THE BANKED WORK. In SndDrv_TimerATick, a
     `ld a,(SND_CTRL_DMA_ACTIVE)` / `or a` / conditional-transfer triple must
     appear before the first `call Run_SeqFrame_OnSongBank`. In SndDrv_Idle, the
     same triple must appear before the `call SndDrv_IdleTick` (SndDrv_IdleTick
     is the idle-context caller of the SAME Run_SeqFrame_OnSongBank).
  2. GUARD BEFORE THE RE-ARM, which is what makes it a DEFER and not a SKIP. The
     YM's Timer-A overflow status bit is cleared ONLY by $27's RST:A bit, i.e.
     only by the single `ld a, SND_TIMERA_CTRL_REARM` inside Snd_TimerA_Rearm
     (checked: that constant has exactly one code use in the file). So a guard
     that returns without having called Snd_TimerA_Rearm leaves the overflow
     LATCHED and the tick re-fires on the next pass — the frame is delayed, not
     dropped. A guard placed AFTER the re-arm would silently become a
     frame-dropping skip, which for the sequencer is an audible tempo defect, so
     the order is checked and not assumed.
  3. THE REFILL GUARD IS STILL THERE. The 2026-08-09 site itself: a flag test
     before SndDrv_TimerATick's first `ld a, (ix+0)` (the banked-window byte
     read), and specifically one BELOW the mailbox call, so that the LS-12 head
     guard cannot stand in for it. That bound is not tidiness: the first version
     of this check omitted it and came back GREEN with the refill guard deleted,
     because the head guard satisfied the search. Same family as the LS-11
     control, found the same way — by running the control.
  4. THE CALL-SITE CENSUS HAS NOT MOVED. Run_SeqFrame_OnSongBank has exactly two
     call sites and Snd_PollMailbox_Banked exactly two, derived by scanning code
     lines. A new call site anywhere fails this test, because the coverage claim
     below is enumerated against those four and a fifth would not be in it.

WHAT IT DOES NOT COVER, and the first one is a live hole, not a hypothetical:

  * SndDrv_ISR's `call Snd_PollMailbox_Banked` — ONE of the four census sites
    above (25%), and deliberately left unguarded. It is the only banked-ROM path
    that is PHASE-LOCKED to the 68k's DMA window: the Z80's own VBlank interrupt
    and the 68k's VInt_Level flag bracket are driven by the same VBlank, so the
    ISR runs, by construction, inside the window. A fail-closed skip there would
    skip every frame at the same phase forever, and a defer has nothing to defer
    to (the ISR is not re-entered until the next VBlank, at the same phase). It
    needs its own design; filed in docs/DEFERRED_WORK.md under LS-12a. A green
    run here says NOTHING about it.
  * ANY BANKED-ROM READ OUTSIDE THE TIMER-A TICK PATHS. This lint models four
    call sites in one file. The sequencer, FM, PSG and SFX modules dereference
    $8000-window pointers in many places; they are reachable only THROUGH these
    call sites today, and this lint does not prove that.
  * THE 68k SIDE. Nothing here reads engine/system/vblank.emp or
    engine/level/section.emp, which are what raise and lower the flag. A raise
    without a lower would stall the sequencer and this lint cannot see it.
  * THE HAZARD ITSELF, and its absence. See the second paragraph: unobservable
    in this project's entire verification loop. This lint checks that the
    instructions are emitted in the order the ruling requires. It is not
    evidence that any hardware behaves differently.
  * A DMA THAT BEGINS AFTER THE TEST. The guard narrows the window; it is not
    mutual exclusion, and the subject's own comment says so.

IT IS A TEXT LINT, deliberately, for the reason build.sh's header gives for the
others in this family: the pytest lane runs BEFORE sigil, so a test that opened
s4.bin would grade the PREVIOUS build's artifact.

Runner: build.sh's tool-suite pytest sweep (`python3 -m pytest "${TOOLS}"`,
build-fatal), which collects `tools/test_*.py` by directory glob. Also runnable
standalone: `python3 tools/test_timera_dma_guard_lint.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SUBJECT = REPO / "engine" / "sound" / "z80_sound_driver.emp"

FLAG = "SND_CTRL_DMA_ACTIVE"
REARM_CONST = "SND_TIMERA_CTRL_REARM"

RE_PROC = re.compile(r"^\s*(?:pub\s+)?(?:@\w+\s+)*proc\s+(\w+)")
RE_FLAG_LOAD = re.compile(r"\bld\s+a\s*,\s*\(\s*" + FLAG + r"\s*\)")
RE_OR_A = re.compile(r"\bor\s+a\b")
RE_COND_XFER = re.compile(r"\b(?:jp|jr)\s+n?z\s*,")
RE_CALL = re.compile(r"\bcall\s+(\w+)")
RE_WINDOW_READ = re.compile(r"\bld\s+a\s*,\s*\(\s*ix\s*\+\s*0\s*\)")

# Derived, not remembered: both numbers are re-counted by scan() on every run and
# asserted against these. They are the census this file's coverage clause is
# enumerated against, so a new call site must land here and in that clause together.
EXPECTED_CALL_SITES = {
    "Run_SeqFrame_OnSongBank": 2,   # SndDrv_IdleTick, SndDrv_TimerATick
    "Snd_PollMailbox_Banked": 2,    # SndDrv_ISR (UNGUARDED, phase-locked), SndDrv_TimerATick
}


def _strip_comment(line: str) -> str:
    """Drop a trailing `//` comment. No string literal in this file carries `//`."""
    idx = line.find("//")
    return line if idx < 0 else line[:idx]


def code_lines() -> list[tuple[int, str, str]]:
    """(line number, owning proc, code text) for every comment-stripped line."""
    out: list[tuple[int, str, str]] = []
    proc = "<file>"
    for n, raw in enumerate(SUBJECT.read_text().splitlines(), start=1):
        line = _strip_comment(raw)
        m = RE_PROC.match(line)
        if m:
            proc = m.group(1)
        if line.strip():
            out.append((n, proc, line))
    return out


def proc_body(name: str) -> list[tuple[int, str]]:
    """(line number, code text) for the code lines inside one proc."""
    body = [(n, t) for n, p, t in code_lines() if p == name]
    assert body, (
        f"no proc named {name} in {SUBJECT.relative_to(REPO)} — the file this lint "
        f"reads is not the file it was written for."
    )
    return body


def guard_line(body: list[tuple[int, str]], before: int, after: int = 0) -> int | None:
    """Line of the last complete flag-test triple in (`after`, `before`), or None.

    A triple is `ld a,(SND_CTRL_DMA_ACTIVE)` then `or a` then a conditional
    transfer, in that order, within the next few code lines. Anything looser
    would accept a flag load whose result is discarded.

    `after` is a LOWER bound and it is load-bearing, not decoration. Without it
    this function reports "a guard exists somewhere above", which is not the
    question any caller is asking once a proc holds more than one guard. It was
    added because a red-first control proved the point: with `after` defaulted,
    DELETING the 2026-08-09 refill guard still passed, because the tick-head
    guard added for LS-12 sits above the refill and satisfied the search. A check
    that a DIFFERENT guard can satisfy is not a check on the guard it names.
    """
    found = None
    for i, (n, text) in enumerate(body):
        if not (after < n < before) or not RE_FLAG_LOAD.search(text):
            continue
        window = body[i + 1 : i + 4]
        if any(RE_OR_A.search(t) for _, t in window) and any(
            RE_COND_XFER.search(t) for _, t in window
        ):
            found = n
    return found


def first_line_matching(body: list[tuple[int, str]], pattern: re.Pattern) -> int | None:
    for n, text in body:
        if pattern.search(text):
            return n
    return None


def test_rearm_is_the_only_overflow_clear():
    """Premise of the DEFER: nothing but Snd_TimerA_Rearm clears the overflow bit."""
    uses = [(n, p) for n, p, t in code_lines() if REARM_CONST in t]
    print(f"{REARM_CONST} code uses: {uses}")
    assert len(uses) == 1, (
        f"{REARM_CONST} has {len(uses)} code uses, expected exactly 1 "
        f"({uses}). The deferral in SndDrv_TimerATick and SndDrv_Idle depends on the "
        f"YM Timer-A overflow bit staying LATCHED when the tick returns early, and "
        f"that holds only because a single site writes the RST:A bit. A second writer "
        f"means this lint's premise must be re-derived."
    )
    assert uses[0][1] == "Snd_TimerA_Rearm", (
        f"{REARM_CONST} is written in {uses[0][1]}, not Snd_TimerA_Rearm."
    )


def test_call_site_census_is_unchanged():
    """A fifth call site would not be in this lint's coverage clause."""
    for callee, expected in EXPECTED_CALL_SITES.items():
        sites = [(n, p) for n, p, t in code_lines() if RE_CALL.search(t) and callee in t]
        print(f"call {callee}: {sites}")
        assert len(sites) == expected, (
            f"{callee} has {len(sites)} call site(s), expected {expected}: {sites}. "
            f"This lint guards a NAMED set of Timer-A tick paths and its docstring "
            f"enumerates what it does not cover against that same set. A new call site "
            f"is not covered by either until both are re-derived."
        )


def test_streaming_tick_defers_before_the_banked_work():
    body = proc_body("SndDrv_TimerATick")
    frame = first_line_matching(body, re.compile(r"\bcall\s+Run_SeqFrame_OnSongBank\b"))
    assert frame, "SndDrv_TimerATick no longer calls Run_SeqFrame_OnSongBank."
    g = guard_line(body, frame)
    print(f"SndDrv_TimerATick: guard :{g} -> Run_SeqFrame_OnSongBank :{frame}")
    assert g is not None, (
        "SndDrv_TimerATick reaches `call Run_SeqFrame_OnSongBank` with no "
        f"`ld a,({FLAG})` / `or a` / conditional-transfer triple above it. The "
        "sequencer frame streams the song and its patch tables through the $8000 "
        "window; the 2026-08-09 ruling forbids that during an active 68k DMA. The "
        "hot loop's own `.dma_check` cannot cover this — its Timer-A poll branches "
        "into this proc from ABOVE that check."
    )


def test_mailbox_poll_is_behind_the_same_guard():
    body = proc_body("SndDrv_TimerATick")
    poll = first_line_matching(body, re.compile(r"\bcall\s+Snd_PollMailbox_Banked\b"))
    assert poll, "SndDrv_TimerATick no longer calls Snd_PollMailbox_Banked."
    g = guard_line(body, poll)
    print(f"SndDrv_TimerATick: guard :{g} -> Snd_PollMailbox_Banked :{poll}")
    assert g is not None, (
        "SndDrv_TimerATick reaches `call Snd_PollMailbox_Banked` with no flag test "
        "above it. Snd_LoadSong and SfxDispatch read the song table and the SFX blobs "
        "through the $8000 window from under it."
    )


def test_guard_precedes_the_rearm_so_it_defers_rather_than_skips():
    body = proc_body("SndDrv_TimerATick")
    frame = first_line_matching(body, re.compile(r"\bcall\s+Run_SeqFrame_OnSongBank\b"))
    rearm = first_line_matching(body, re.compile(r"\bcall\s+Snd_TimerA_Rearm\b"))
    g = guard_line(body, frame)
    print(f"SndDrv_TimerATick: guard :{g} · rearm :{rearm} · frame :{frame}")
    assert rearm is not None, "SndDrv_TimerATick no longer calls Snd_TimerA_Rearm."
    assert g is not None and g < rearm, (
        f"the DMA guard (:{g}) does not precede `call Snd_TimerA_Rearm` (:{rearm}). "
        "Snd_TimerA_Rearm writes RST:A and clears the YM's Timer-A overflow bit, so a "
        "guard below it turns a DEFER into a SKIP: the tick would be DROPPED rather "
        "than retried on the next hot-loop pass, and a dropped tick is a dropped "
        "sequencer frame — an audible, gameplay-only tempo slowdown, traded for a "
        "hazard no test in this project can observe. The refill's own guard may sit "
        "below the re-arm because the ring lead absorbs a skipped refill; the "
        "sequencer frame has no such absorber."
    )


def test_idle_tick_defers_before_the_banked_work():
    body = proc_body("SndDrv_Idle")
    tick = first_line_matching(body, re.compile(r"\bcall\s+SndDrv_IdleTick\b"))
    assert tick, "SndDrv_Idle no longer calls SndDrv_IdleTick."
    g = guard_line(body, tick)
    print(f"SndDrv_Idle: guard :{g} -> SndDrv_IdleTick :{tick}")
    assert g is not None, (
        "SndDrv_Idle reaches `call SndDrv_IdleTick` with no flag test above it. "
        "SndDrv_IdleTick calls the SAME Run_SeqFrame_OnSongBank as the streaming "
        "tick, so the idle path reads the song stream through the $8000 window too. "
        "The test belongs in SndDrv_Idle rather than inside SndDrv_IdleTick: the "
        "$80 DC-center write below the call is gated on a tick having actually run."
    )


def test_the_2026_08_09_refill_guard_is_still_in_place():
    """The ORIGINAL ruled site, scoped so the LS-12 head guard cannot stand in for it."""
    body = proc_body("SndDrv_TimerATick")
    read = first_line_matching(body, RE_WINDOW_READ)
    assert read, (
        "SndDrv_TimerATick has no `ld a, (ix+0)` — the bulk refill's banked-window "
        "byte read. This lint's subject moved."
    )
    # Lower bound: the mailbox call. Everything between it and the refill read is the
    # reload block, so a triple found in that span is the refill's OWN guard and not
    # the head guard. Without this bound, deleting the refill guard passed — see
    # guard_line's docstring, and the control that proved it.
    poll = first_line_matching(body, re.compile(r"\bcall\s+Snd_PollMailbox_Banked\b"))
    assert poll, "SndDrv_TimerATick no longer calls Snd_PollMailbox_Banked."
    g = guard_line(body, read, after=poll)
    print(f"SndDrv_TimerATick: refill guard :{g} in (:{poll}, :{read})")
    assert g is not None, (
        "the 2026-08-09 refill guard is gone: SndDrv_TimerATick reaches its banked "
        f"`ld a, (ix+0)` with no `ld a,({FLAG})` triple between the mailbox call and "
        "the read. The LS-12 head guard does NOT cover it — a DMA that begins during "
        "Sequencer_Frame is exactly what the refill's own re-test is for."
    )


if __name__ == "__main__":
    test_rearm_is_the_only_overflow_clear()
    test_call_site_census_is_unchanged()
    test_streaming_tick_defers_before_the_banked_work()
    test_mailbox_poll_is_behind_the_same_guard()
    test_guard_precedes_the_rearm_so_it_defers_rather_than_skips()
    test_idle_tick_defers_before_the_banked_work()
    test_the_2026_08_09_refill_guard_is_still_in_place()
    print("OK")
