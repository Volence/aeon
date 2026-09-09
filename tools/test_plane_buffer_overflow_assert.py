#!/usr/bin/env python3
"""The plane-buffer overflow refusal, and the caller reserve that makes it quiet.

WHAT THIS GUARDS, and why it is a relation and not a snapshot.

`Draw_TileColumn` (`engine/level/plane_buffer.emp`) declines a column three ways,
all to the same `.done`, and only ONE of them is a defect: a column dropped
because the plane buffer is full is never redrawn (the caller records it in
`Section_Right_Col_Written` whether or not the routine wrote anything), while a
column outside the tile cache's declared window is an EXPECTED drop that
`engine/system/constants.emp`'s `TILE_CACHE_COLS` ensure names as such. The DEBUG
shape asserts on the first and stays quiet on the other two.

That assert is a DRIFT TRIPWIRE and is expected never to fire, because both call
sites reserve the callee's worst case with the exact algebraic complement of the
callee's own guard. **That agreement is the thing worth gating**: it lives in two
files, spelled two different ways, with nothing but arithmetic connecting them.
The assert's own correctness rests on it, and a snapshot of either constant would
gate neither. So every expectation below is DERIVED from the other side of the
relation — the threshold the assert compares against is read out of the release
guard, the condition it uses is computed from the release guard's branch, and the
caller's reserve is reconstructed from the callee's two operands. Nothing here is
copied from a pin, and no numeric literal for the buffer size appears in this file.

WHAT A GREEN HERE DOES NOT SAY: that the buffer never comes near full (that is a
runtime measurement — 272 B peak under horizontal motion, `docs/DEFERRED_WORK.md`),
and not that the assert fires when it should (that needs an emulator). It says the
two predicates still agree, the loud path is still gated on the window question,
and no caller has appeared without the reserve.

Hermetic: source text only, no build artifact, so this runs in build.sh's
PRE-BUILD pytest lane (`python3 -m pytest tools -m "not needs_build"`), which is
build-fatal.
"""

import os
import re
import unittest

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANE_BUFFER = os.path.join(AEON, "engine", "level", "plane_buffer.emp")
SECTION = os.path.join(AEON, "engine", "level", "section.emp")

# The 68000 conditional-branch complements, as pairs. Used to DERIVE the condition
# the assert must carry from the condition the release guard bails on: the release
# guard branches away when the buffer would overflow, so the assert — which must
# pass when it does NOT — carries the complement. Written as a table rather than a
# single hardcoded answer so that changing the release guard's branch changes what
# this test demands, instead of making it wrong.
CC_COMPLEMENT = {
    "hi": "ls", "ls": "hi",
    "hs": "lo", "lo": "hs",
    "cc": "cs", "cs": "cc",
    "ne": "eq", "eq": "ne",
    "vc": "vs", "vs": "vc",
    "pl": "mi", "mi": "pl",
    "ge": "lt", "lt": "ge",
    "gt": "le", "le": "gt",
}


def strip_comment(line):
    """Drop a trailing `//` comment. `.emp` has no string literals in these lines."""
    return line.split("//", 1)[0].rstrip()


def norm(expr):
    """Whitespace-insensitive form of an operand expression."""
    return re.sub(r"\s+", "", expr)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().split("\n")


def proc_body(lines, name):
    """Lines of `pub proc <name> (...) { ... }`, as (index_in_file, code_text) pairs.

    Brace-counted from the proc header, so a nested `if DEBUG == 1 { }` block is
    inside the body rather than ending it.
    """
    start = None
    for i, line in enumerate(lines):
        if re.match(r"\s*pub\s+proc\s+" + re.escape(name) + r"\b", line):
            start = i
            break
    if start is None:
        raise AssertionError(
            "could not locate `pub proc %s` in %s — this test cannot measure "
            "anything and is reporting that, not passing" % (name, PLANE_BUFFER)
        )
    out = []
    depth = 0
    for i in range(start, len(lines)):
        code = strip_comment(lines[i])
        depth += code.count("{") - code.count("}")
        out.append((i, code))
        if i > start and depth <= 0:
            break
    return out


class PlaneBufferOverflowAssert(unittest.TestCase):
    def setUp(self):
        self.pb_lines = read(PLANE_BUFFER)
        self.body = proc_body(self.pb_lines, "Draw_TileColumn")

    # -- the release side: unchanged behaviour, and the source of every expectation --

    def release_guard(self):
        """(cmpi_line_idx, threshold_expr, branch_cc) for the release overflow bail.

        Anchored on the pair, not on either half: a `cmpi.w #<expr>, d2` whose very
        next code line is a conditional branch to `.done`.
        """
        found = []
        code = [(i, c) for i, c in self.body if c.strip()]
        for n, (i, c) in enumerate(code[:-1]):
            m = re.match(r"\s*cmpi\.w\s+#(.+?),\s*d2\s*$", c)
            if not m:
                continue
            nxt = code[n + 1][1]
            b = re.match(r"\s*b(hi|ls|hs|lo|cc|cs|ge|gt|lt|le)(?:\.[bwl])?\s+\.done\s*$", nxt)
            if b:
                found.append((i, m.group(1), b.group(1)))
        return found

    def test_release_overflow_guard_is_present_and_unique(self):
        found = self.release_guard()
        self.assertEqual(
            len(found), 1,
            "expected exactly one `cmpi.w #<threshold>, d2` + branch-to-.done pair in "
            "Draw_TileColumn (the release overflow guard); found %d. Every other "
            "expectation in this file is derived from that pair, so 0 or 2 of them "
            "means this test measured nothing." % len(found),
        )

    def test_the_release_bail_still_drops_the_column(self):
        """The parcel's contract: release behaviour did NOT change."""
        _, _, cc = self.release_guard()[0]
        self.assertEqual(
            cc, "hi",
            "the release overflow guard no longer bails on `bhi`. That is a release "
            "behaviour change; the DEBUG assert below it is derived from this branch "
            "and would silently follow it.",
        )

    # -- the debug side: the refusal, derived from the release side ------------------

    def debug_assert(self):
        """(line_idx, width, src, cc, dest_expr) of the overflow assert."""
        out = []
        for i, c in self.body:
            m = re.match(r"\s*assert\.([bwl])\s+(\w+)\s*,\s*(\w+)\s*,\s*#(.+?)\s*$", c)
            if m:
                out.append((i, m.group(1), m.group(2), m.group(3).lower(), m.group(4)))
        return out

    def overflow_assert(self):
        """The one assert whose threshold is the release guard's, or a loud refusal.

        WHY THIS IS A HELPER AND NOT THREE INLINE INDEXES. It was three inline
        `[...][0]` lookups, and the red-first run that deleted the assert proved that
        wrong: three of the four arms went red with a bare `IndexError` and a line
        number. Red is not the bar — a gate that cannot say WHAT it failed to find
        reports "something broke" and sends the reader to the traceback instead of to
        the defect. Same family as this tree's "loud on unmeasurable" rule, one level
        in: the arm was loud, its MESSAGE was not.
        """
        _, rel_expr, _ = self.release_guard()[0]
        cands = [a for a in self.debug_assert() if norm(a[4]) == norm(rel_expr)]
        if len(cands) != 1:
            raise AssertionError(
                "found %d asserts in Draw_TileColumn testing the release guard's own "
                "threshold `#%s`, expected exactly 1. Without it there is nothing for "
                "this arm to measure, and the plane-buffer overflow drop is silent "
                "again in every shape — which is the defect, not a missing test."
                % (len(cands), rel_expr)
            )
        return cands[0]

    def test_the_overflow_assert_exists_and_matches_the_release_threshold(self):
        rel_i, rel_expr, rel_cc = self.release_guard()[0]
        cands = [a for a in self.debug_assert() if norm(a[4]) == norm(rel_expr)]
        self.assertEqual(
            len(cands), 1,
            "expected exactly one `assert.w d2, <cc>, #%s` in Draw_TileColumn — the "
            "same threshold expression the release guard compares against — found %d. "
            "A threshold that drifts from the release guard's asserts a different "
            "invariant from the one release enforces." % (rel_expr, len(cands)),
        )
        _, width, src, cc, _ = cands[0]
        self.assertEqual(width, "w", "the assert must be word-wide, like the guard it mirrors")
        self.assertEqual(
            src, "d2",
            "the assert must test d2 — the register the release guard tests, holding "
            "Plane_Buffer_Ptr plus this proc's worst-case entry size",
        )
        self.assertEqual(
            cc, CC_COMPLEMENT[rel_cc],
            "the release guard bails on `b%s`, so the assert must pass on its "
            "complement `%s`; it carries `%s`. As written the assert refuses the case "
            "release ACCEPTS." % (rel_cc, CC_COMPLEMENT[rel_cc], cc),
        )

    def test_the_overflow_assert_runs_before_the_release_guard(self):
        rel_i, _, _ = self.release_guard()[0]
        self.assertLess(
            self.overflow_assert()[0], rel_i,
            "the overflow assert sits AFTER the release guard that bails to .done on "
            "the same condition, so it can never be reached. Its whole point is to "
            "run before the bail it is about.",
        )

    def test_the_overflow_assert_is_debug_gated(self):
        ai = self.overflow_assert()[0]
        depth = 0
        opened = None
        for i, c in self.body:
            if i > ai:
                break
            if re.match(r"\s*if\s+DEBUG\s*==\s*1\s*\{", c):
                depth += 1
                opened = i
            elif c.strip() == "}" and depth > 0:
                depth -= 1
        self.assertGreater(
            depth, 0,
            "the overflow assert is not inside an `if DEBUG == 1 { }` block. `assert` "
            "self-gates to zero bytes on its own, but the window comparisons that gate "
            "it do NOT — unwrapped they would move release bytes, which is exactly "
            "what this parcel's contract forbids.",
        )
        self.assertIsNotNone(opened)

    def test_the_overflow_assert_is_window_gated(self):
        """The loud path must be reached only for a column INSIDE the cache window.

        Both operand pairs are read out of the RELEASE guards further down the proc,
        so this cannot pass by matching a hardcoded pair of variable names that the
        release path no longer uses.
        """
        rel_i, _, _ = self.release_guard()[0]
        ai = self.overflow_assert()[0]

        # The release window gates: every `cmp.w <var>, d1` + branch-to-.done pair
        # AFTER the release overflow guard.
        code = [(i, c) for i, c in self.body if c.strip()]
        release_window = []
        for n, (i, c) in enumerate(code[:-1]):
            if i <= rel_i:
                continue
            m = re.match(r"\s*cmp\.w\s+(\w+)\s*,\s*d1\s*$", c)
            if not m:
                continue
            b = re.match(r"\s*b(lt|gt|le|ge|hi|ls|lo|hs)(?:\.[bwl])?\s+\.done\s*$", code[n + 1][1])
            if b:
                release_window.append((m.group(1), b.group(1)))
        self.assertEqual(
            len(release_window), 2,
            "expected the two cache-range gates (`cmp.w <var>, d1` + branch to .done) "
            "after the release overflow guard; found %d. The DEBUG gate is derived "
            "from them, so this test measured nothing." % len(release_window),
        )

        # The same two questions, asked before the assert, branching PAST it.
        debug_window = []
        targets = set()
        for n, (i, c) in enumerate(code[:-1]):
            if not (rel_i > i and i < ai):
                continue
            m = re.match(r"\s*cmp\.w\s+(\w+)\s*,\s*d1\s*$", c)
            if not m:
                continue
            b = re.match(r"\s*b(lt|gt|le|ge|hi|ls|lo|hs)(?:\.[bwl])?\s+(\.\w+)\s*$", code[n + 1][1])
            if b:
                debug_window.append((m.group(1), b.group(1)))
                targets.add(b.group(2))
        self.assertEqual(
            debug_window, release_window,
            "the DEBUG-side window gate does not ask the same two questions, in the "
            "same sense, as the release cache-range gate. Release gates on %r; the "
            "debug path gates on %r. If they differ, the assert fires on columns the "
            "engine drops on purpose (or misses ones it does not)."
            % (release_window, debug_window),
        )

        self.assertEqual(
            len(targets), 1,
            "the two debug-side window bails branch to different labels (%r); they "
            "must both skip the same assert." % sorted(targets),
        )
        label = targets.pop()
        after = [i for i, c in self.body if i > ai and c.strip() == label[1:] + ":" or
                 (i > ai and c.strip() == label + ":")]
        self.assertTrue(
            after,
            "the debug window gate branches to %s, but no such label is defined AFTER "
            "the assert. If it is defined before, the gate skips backwards and the "
            "assert is either unreachable or unguarded." % label,
        )

    # -- the relation the assert exists to protect ----------------------------------

    def test_every_caller_reserves_the_callee_worst_case(self):
        """The reserve in `Section_UpdateColumns` must be the callee guard's complement.

        This is the invariant that makes the assert quiet. The expected reserve
        expression is RECONSTRUCTED from the callee's own two operands — the entry
        size it adds and the threshold it compares against — so a change to either
        side that is not mirrored in the other fails here, at build time, instead of
        waiting for the runtime assert to notice.
        """
        _, rel_expr, _ = self.release_guard()[0]
        entry_size = None
        for _, c in self.body:
            m = re.match(r"\s*addi\.w\s+#(.+?),\s*d2\s*$", c)
            if m:
                entry_size = m.group(1)
                break
        self.assertIsNotNone(
            entry_size,
            "could not find Draw_TileColumn's `addi.w #<worst case>, d2` — the entry "
            "size the caller must reserve. Reporting unmeasurable, not passing.",
        )
        expected = norm("%s - (%s)" % (rel_expr, entry_size))

        sec = read(SECTION)
        code = [(i, strip_comment(l)) for i, l in enumerate(sec)]
        calls = [i for i, c in code if re.match(r"\s*jbsr\s+Draw_TileColumn\s*$", c)]
        self.assertTrue(
            calls,
            "no `jbsr Draw_TileColumn` call site found in %s. The reserve invariant "
            "has no population, so this test measured nothing." % SECTION,
        )

        for call in calls:
            reserve = None
            for i in range(call - 1, max(call - 30, 0), -1):
                m = re.match(
                    r"\s*cmpi\.w\s+#(.+?),\s*Plane_Buffer_Ptr\s*$", code[i][1])
                if m:
                    reserve = (i, m.group(1))
                    break
            self.assertIsNotNone(
                reserve,
                "the `jbsr Draw_TileColumn` at %s:%d has no "
                "`cmpi.w #<reserve>, Plane_Buffer_Ptr` within the 30 lines above it. "
                "An unreserved caller CAN reach the callee's overflow drop, which is "
                "the silent-gap defect the DEBUG assert exists to catch — and it "
                "would now catch it, loudly, in the debug shape only."
                % (SECTION, call + 1),
            )
            self.assertEqual(
                norm(reserve[1]), expected,
                "the reserve at %s:%d is `%s`; Draw_TileColumn's own guard makes the "
                "complement `%s`. The two predicates have drifted: the caller now "
                "believes a different amount of room is enough than the callee does, "
                "so either columns are dropped silently in release or the reserve is "
                "needlessly tight."
                % (SECTION, reserve[0] + 1, reserve[1], expected),
            )


if __name__ == "__main__":
    unittest.main()
