#!/usr/bin/env python3
"""BG-PLANE-WINDOW, the half an emulator cannot see: the LADDER ORDER the prime depends on.

`tools/bg_window_gate.py` is the behavioural gate — it boots a headless emulator, warps
twice and reads `BG_Plane_Top` and Plane B out of the machine. It cannot grade this file's
subject, and the reason is worth stating rather than waving at:

**The boot prime's correct window is 0 on every reachable path, so a boot sample passes
whether or not the ordering is right.** `Section_RedrawPlanes` reads
`Parallax_Current_Vscroll_BG` to choose its window. That cell lives inside `Parallax_State`,
the span `Parallax_Init`'s zero loop wipes. Run the boot blit ABOVE `Parallax_Init` — as the
ladder did until BG-PLANE-WINDOW closed — and the read is STALE: the previous act's scroll,
or whatever the boot RAM clear left. On a cold boot that stale value is 0 and the prime is
accidentally right; on a warm re-entry it is not, and the prime blits the WRONG window
rather than the harmless row 0 it used to. An emulator run of the shipped boot cannot
separate those two worlds, so the ordering is pinned HERE, on the source, where it is
visible.

THE THREE LEGS.

  1. BOOT LADDER ORDER. In `GameState_OJZScroll_Init`, `jbsr Parallax_Init` stands ABOVE
     `st Section_Plane_Dirty`. This is the precondition `Section_RedrawPlanes`' windowed
     prime is written against, and nothing inside either routine can see it.

  2. THE WARP LADDER'S ORDER. `Debug_Warp_Consume` does NOT call `Parallax_Init`, and since
     WARP-VSCROLL-PRIME (2026-09-28) its blit pair stands BELOW its parallax crossing, with
     `st Parallax_BG_Snap` set immediately before that crossing's `Parallax_Update` and cleared
     immediately after it. The reorder is the fix for BG-RATE-PRIME-EXEMPTION: with the prime
     ABOVE the crossing (the order this leg pinned until then) the window was seeded from the
     PRE-warp scroll and Step 5's rate clamp ratcheted the scroll to its target 16 px a frame
     (MEASURED on s2_woven DEBUG crc 615ff7ff: Hidden Palace layouts 1 / 2 / 3 slid 15 / 31 /
     44 frames, 14 / 30 / 38 of them torn). Below, the scroll the prime reads is the post-warp
     one, stored at its target, so the window is exact and nothing slides. The snap bracket is
     pinned with it because either half alone is the bug again: the reorder without the snap
     primes from a scroll only 16 px along, and the snap without the reorder jumps the scroll
     away from a window primed for the old one. `tools/clip_bg_scroll_witness.py --warp-entry`
     grades the picture; this grades the order, which that cannot name.

  3. THE PRIME STILL DERIVES ITS SEED. `Section_RedrawPlanes` reads
     `Parallax_Current_Vscroll_BG` and writes `BG_Plane_Top` from a register — it does not
     `clr.w` it. A regression to the constant is the exact defect this item closed, and it
     is one line.

WHAT THESE LEGS DO NOT SAY: nothing about the picture, nothing about the wrap arithmetic,
nothing about VRAM. That is `tools/bg_window_gate.py`'s subject and it needs a machine.
"""

import os
import re
import unittest

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LADDER = os.path.join(AEON, "games/sonic4/test/ojz_scroll_test.emp")
SECTION = os.path.join(AEON, "engine/level/section.emp")


def _text(path):
    with open(path, errors="replace") as fh:
        return fh.read()


def _proc_body(text, name, path):
    """The source lines of one `proc NAME (...) { ... }`, brace-counted, comments and
    strings stripped so a brace or a mnemonic inside prose cannot be read as code."""
    m = re.search(rf"^\s*(?:pub\s+)?proc\s+{re.escape(name)}\b", text, re.M)
    if not m:
        raise AssertionError(
            f"{path} no longer declares `proc {name}` — every expectation in "
            f"tools/test_bg_plane_window.py is located through it, so this is a SETUP "
            f"FAILURE and must not be read as 'nothing offended'.")
    lines = text[m.start():].splitlines()
    out, depth, started = [], 0, False
    for raw in lines:
        code = raw.split("//", 1)[0]
        code = re.sub(r'"[^"]*"', '""', code)
        depth += code.count("{") - code.count("}")
        out.append(code)
        if not started and "{" in code:
            started = True
        elif started and depth <= 0:
            break
    else:
        raise AssertionError(f"{path}: `proc {name}` never closes its brace")
    return out


def _index_of(body, pattern, what, where):
    rx = re.compile(pattern)
    hits = [i for i, line in enumerate(body) if rx.search(line)]
    if not hits:
        raise AssertionError(
            f"{where}: no line matching `{pattern}` ({what}). The ladder this gate grades "
            f"has been restructured; re-derive the ordering rather than deleting the leg.")
    return hits[0], len(hits)


class BootLadderOrder(unittest.TestCase):

    def test_parallax_init_stands_above_the_boot_plane_prime(self):
        body = _proc_body(_text(LADDER), "GameState_OJZScroll_Init", LADDER)
        init_at, n_init = _index_of(body, r"\bjbsr\s+Parallax_Init\b",
                                    "the parallax boot init", "GameState_OJZScroll_Init")
        dirty_at, n_dirty = _index_of(body, r"\bst\s+Section_Plane_Dirty\b",
                                      "the synchronous plane prime trigger",
                                      "GameState_OJZScroll_Init")
        self.assertEqual((n_init, n_dirty), (1, 1),
                         f"expected exactly one `jbsr Parallax_Init` and one "
                         f"`st Section_Plane_Dirty` in GameState_OJZScroll_Init, found "
                         f"{n_init} and {n_dirty}. With more than one of either, 'above' "
                         f"is not a well-formed question and this leg would grade the "
                         f"first pair while the prime took its scroll from another.")
        self.assertLess(
            init_at, dirty_at,
            f"BOOT LADDER ORDER INVERTED: `st Section_Plane_Dirty` (line {dirty_at} of the "
            f"proc) stands ABOVE `jbsr Parallax_Init` (line {init_at}).\n"
            f"Section_RedrawPlanes' Plane B half chooses its window from "
            f"Parallax_Current_Vscroll_BG, which lives INSIDE Parallax_State — the span "
            f"Parallax_Init's zero loop wipes and its tail Parallax_Update then re-derives "
            f"from this act's camera. Triggered above the init, the prime reads the "
            f"PREVIOUS act's scroll (or whatever the boot RAM clear left) and blits the "
            f"WRONG 64 map rows, which is worse than the stale-but-harmless rows 0..63 it "
            f"blitted before BG-PLANE-WINDOW closed. A cold boot hides this because the "
            f"stale value happens to be 0 — no emulator run of the shipped boot can see it, "
            f"which is why it is pinned here.")


class WarpLadderOrder(unittest.TestCase):

    def test_the_warp_ladder_has_no_parallax_init_and_primes_after_a_snapped_update(self):
        body = _proc_body(_text(LADDER), "Debug_Warp_Consume", LADDER)
        joined = "\n".join(body)
        self.assertIsNone(
            re.search(r"\bjbsr\s+Parallax_Init\b", joined),
            "Debug_Warp_Consume now calls Parallax_Init. This ladder deliberately re-enters "
            "through Parallax_CheckBoundary so the destination region reads as a CROSSING — "
            "Parallax_Init would re-seed the region sentinel that makes that work, and zero "
            "Parallax_State (Parallax_BG_Snap included) under the snap bracket below. Re-derive "
            "the ladder before assuming the comments at both sites still hold.")
        where = "Debug_Warp_Consume"
        dirty_at, n_dirty = _index_of(body, r"\bst\s+Section_Plane_Dirty\b",
                                      "the warp's plane prime trigger", where)
        check_at, n_check = _index_of(body, r"\bjbsr\s+Parallax_CheckBoundary\b",
                                      "the warp's region crossing", where)
        upd_at, n_upd = _index_of(body, r"\bjbsr\s+Parallax_Update\b",
                                  "the warp's own Parallax_Update", where)
        set_at, n_set = _index_of(body, r"\bst\s+Parallax_BG_Snap\b",
                                  "the snap that stores the scroll at its target", where)
        clr_at, n_clr = _index_of(body, r"\bclr\.b\s+Parallax_BG_Snap\b",
                                  "the snap's clear after its one Update", where)
        stream_at, _ = _index_of(body, r"\bjbsr\s+BG_Stream_Update\b",
                                 "the tracker check after the prime", where)
        self.assertEqual((n_dirty, n_check, n_upd, n_set, n_clr), (1, 1, 1, 1, 1),
                         "expected exactly one each of `st Section_Plane_Dirty`, `jbsr "
                         "Parallax_CheckBoundary`, `jbsr Parallax_Update`, `st Parallax_BG_Snap` "
                         "and `clr.b Parallax_BG_Snap` in Debug_Warp_Consume, found "
                         f"{(n_dirty, n_check, n_upd, n_set, n_clr)}. With more than one of any, "
                         "'before' is not a well-formed question.")
        self.assertTrue(
            check_at < set_at < upd_at < clr_at < dirty_at < stream_at,
            f"THE WARP LADDER ORDER IS BROKEN (proc lines: CheckBoundary {check_at}, "
            f"st Parallax_BG_Snap {set_at}, Parallax_Update {upd_at}, clr.b Parallax_BG_Snap "
            f"{clr_at}, st Section_Plane_Dirty {dirty_at}, BG_Stream_Update {stream_at}). The "
            f"order WARP-VSCROLL-PRIME needs is crossing -> snap -> Update -> clear -> prime -> "
            f"BG_Stream_Update. Section_RedrawPlanes seeds the Plane B window from "
            f"Parallax_Current_Vscroll_BG, so the scroll must be at its post-warp TARGET before "
            f"the prime reads it; the snap is what skips Step 5's rate clamp for that one store, "
            f"and its clear keeps the same tick's body (which runs after the prime) clamped. "
            f"With the prime above the Update, the warp ratchets again: MEASURED on s2_woven "
            f"DEBUG crc 615ff7ff, 15 / 31 / 44 frames of slide into Hidden Palace layouts "
            f"1 / 2 / 3, most of them torn (BG-RATE-PRIME-EXEMPTION).")


class ThePrimeDerivesItsSeed(unittest.TestCase):

    def test_section_redrawplanes_reads_the_scroll_and_does_not_clear_the_tracker(self):
        body = _proc_body(_text(SECTION), "Section_RedrawPlanes", SECTION)
        joined = "\n".join(body)
        self.assertIsNotNone(
            re.search(r"\bmove\.w\s+Parallax_Current_Vscroll_BG\s*,", joined),
            "Section_RedrawPlanes no longer reads Parallax_Current_Vscroll_BG. Its Plane B "
            "half is the synchronous PRIME — it must write the window the scroll selects. "
            "Without that read it can only write a fixed window, which on a map taller than "
            "the plane is the wrong picture BG_Stream_Update walks back at BG_STREAM_MAX_ROWS "
            "rows a frame (BG-PLANE-WINDOW).")
        self.assertIsNone(
            re.search(r"\bclr\.w\s+BG_Plane_Top\b", joined),
            "Section_RedrawPlanes clears BG_Plane_Top to the constant 0 again. That IS the "
            "BG-PLANE-WINDOW defect: the tracker must name the window the prime actually "
            "blitted, and the prime's window is the one the scroll selects. Seed it with "
            "`move.w dN, BG_Plane_Top` from the computed top.")
        self.assertIsNotNone(
            re.search(r"\bmove\.w\s+d\d\s*,\s*BG_Plane_Top\b", joined),
            "Section_RedrawPlanes no longer seeds BG_Plane_Top from a register. The seed "
            "and the rows blitted are ONE fact — 'which 64 map rows does the plane hold' — "
            "and a seed that is not the computed top makes the tracker lie about the "
            "picture.")


if __name__ == "__main__":
    unittest.main()
