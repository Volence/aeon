#!/usr/bin/env python3
"""The DMA 128 KB-straddle instrument, guarded at the four properties that make it
an instrument rather than a decoration.

WHAT IS BEING MEASURED, AND WHY IT NEEDED A GUARD
-------------------------------------------------
A transfer whose ROM source crosses the VDP's 128 KB DMA-source boundary is SPLIT
into two queue entries by `engine/system/dma_queue.emp`'s `.transfer` core, and
`.split_reject` refuses BOTH halves when only one Important slot is free. So a
straddling Important landing costs TWO slots or it is dropped whole, and
`DPLC_ENTRY_RESERVE` is what holds those two open.

That reserve was sized from total art VOLUME, which bounds how many straddling
entries EXIST IN THE ROM and says nothing about how many can want slots in ONE
FRAME (docs/DEFERRED_WORK.md, "DMA SPLIT-REJECT NEEDS TWO FREE IMPORTANT SLOTS,
AND NOTHING COUNTS PER-FRAME STRADDLES"). The instrument this file guards is what
makes that per-frame count observable.

Four ways the instrument could be present and still answer nothing, each with a
test below:

  1. COUNTED IN THE WRONG PLACE. If the bump sat after the two-slot check it would
     count SURVIVORS, not DEMAND — and the frame that matters is precisely the one
     where demand exceeded supply. `test_the_bump_is_before_the_two_slot_check`.
  2. COUNTED FOR THE WRONG QUEUE. The subject is the Important queue; the selector
     must be the constant `QueueDMA_Important` itself loads into d4, not a
     re-spelling that can drift. `test_the_important_selector_is_the_one_the_entry_point_loads`.
  3. INDISTINGUISHABLE FROM A FULL QUEUE. `.full` and `.split_reject` shared one
     `DMA_Overflow_Count`, which is why nobody could measure this. If they share it
     again the instrument is back to square one. `test_full_and_split_reject_have_separate_counters`.
  4. RESET AT THE WRONG POINT. A read and a clear that are not adjacent can lose an
     increment; a fold placed after the drain describes a different window than the
     occupancy sample. `test_the_fold_reads_and_clears_adjacently`,
     `test_the_fold_precedes_the_important_drain`.

Plus the shape guard: every cell and every instruction must be inside `if DEBUG`,
because a release ROM must not pay for diagnosis apparatus.

WHAT THIS FILE DELIBERATELY DOES NOT DO
---------------------------------------
It does not open `s4.debug.bin`. build.sh's pytest lane runs BEFORE the build
(build.sh:61-72), so a unit test reading a ROM here would be grading a PREVIOUS
build — the trap that bit two other gates and is why they use committed cuts plus a
post-build `--gate`. These are source invariants, read from the `.emp` files that
this build is about to assemble. The byte-level evidence for the instrument lives
in the parcel's commit message, taken from the listing it actually emitted.

Every expectation is DERIVED from the source, never copied: the wall is computed
from the two constants in their owning files, and the Important selector is read
out of `QueueDMA_Important`'s own body.

Runner: build.sh's pytest lane — `python3 -m pytest tools/` (build.sh:612).
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent

DMA_QUEUE = ROOT / "engine/system/dma_queue.emp"
VBLANK = ROOT / "engine/system/vblank.emp"
RAM = ROOT / "engine/ram.emp"

# The cells the instrument owns. Named once, here.
STRADDLE_ALL = "Dbg_DMA_Straddle_All"
STRADDLE_FRAME = "Dbg_DMA_Straddle_Frame"
STRADDLE_PEAK = "Dbg_DMA_Straddle_Peak"
SPLIT_REJECT = "DMA_Split_Reject_Count"
OVERFLOW = "DMA_Overflow_Count"
PEAK_IMPORTANT = "DMA_Peak_Important"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _text(path):
    assert path.is_file(), f"{path} is gone — this gate has no subject"
    return path.read_text()


def _const(rel, name):
    """A `pub const NAME = <int>` read out of its OWNING file."""
    text = (ROOT / rel).read_text()
    m = re.search(r'^\s*pub\s+const\s+' + re.escape(name) + r'\s*=\s*(\$?[0-9A-Fa-f]+)\s*(?://.*)?$',
                  text, re.M)
    assert m, f"no `pub const {name} = <int>` in {rel}"
    raw = m.group(1)
    return int(raw[1:], 16) if raw.startswith('$') else int(raw)


def _strip_comments(text):
    """Drop `//` comments so a prose mention of a symbol is never mistaken for code.

    Without this the whole file would be vacuous: every symbol it looks for is also
    named in the block comments that explain it.
    """
    return re.sub(r'//[^\n]*', '', text)


def _proc_body(text, name):
    """The source lines of `pub proc NAME (...) { ... }`, comments stripped.

    Brace-counted rather than regex-matched, because the bodies here contain nested
    `if DEBUG == 1 { }` and `with z80_stopped { }` groups.
    """
    m = re.search(r'^(?:pub\s+)?proc\s+' + re.escape(name) + r'\s*\(', text, re.M)
    assert m, f"no `proc {name}` — this gate's subject moved or was renamed"
    i = text.index('{', m.end())
    depth, j = 0, i
    while j < len(text):
        if text[j] == '{':
            depth += 1
        elif text[j] == '}':
            depth -= 1
            if depth == 0:
                break
        j += 1
    assert depth == 0, f"unbalanced braces in proc {name}"
    return _strip_comments(text[i:j])


def _split_section(body):
    """`.split`'s code, from its label up to the `.split_reject` label."""
    a = re.search(r'^\s*\.split:\s*$', body, re.M)
    b = re.search(r'^\s*\.split_reject:\s*$', body, re.M)
    assert a and b, ".split / .split_reject labels are gone — the instrument's site moved"
    assert a.start() < b.start(), ".split_reject now precedes .split; re-read this gate"
    return body[a.end():b.start()]


def _debug_blocks(section):
    """Every `if DEBUG == 1 { ... }` group in a section, as a list of bodies."""
    out = []
    for m in re.finditer(r'if\s+DEBUG\s*==\s*1[^\n{]*\{', section):
        depth, j = 0, m.end() - 1
        while j < len(section):
            if section[j] == '{':
                depth += 1
            elif section[j] == '}':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append(section[m.end():j])
    return out


# --------------------------------------------------------------------------
# 1. the count is taken where the straddle is a FACT, and before the reject
# --------------------------------------------------------------------------

def test_the_bump_is_inside_the_split_path():
    """The subject counter is bumped in `.split` and nowhere else.

    `.split` is reached only through `blo .split`, i.e. only when the core has just
    established the crossing from the real source address. A count taken anywhere
    else would be a RE-DERIVATION, free to disagree with the branch it claims to
    describe — useless in exactly the case worth measuring.
    """
    body = _proc_body(_text(DMA_QUEUE), "QueueDMA_Deferrable")
    section = _split_section(body)
    assert re.search(r'addq\.w\s+#1,\s*' + STRADDLE_FRAME, section), \
        f"{STRADDLE_FRAME} is not incremented inside .split"
    elsewhere = body.replace(section, "")
    assert STRADDLE_FRAME not in elsewhere, \
        f"{STRADDLE_FRAME} is also touched outside .split — a second, re-derived count"


def test_the_bump_is_before_the_two_slot_check():
    """DEMAND, not survivors.

    `.split` first writes the leading half's length, then does
    `cmpa.w d4, a1 / bhs .split_reject` — the two-slot check. A bump placed after
    that branch would count only the straddles that GOT their two slots, and the
    frame this whole booking is about is the one where a straddle did not. So the
    increment must precede the branch to `.split_reject`.
    """
    section = _split_section(_proc_body(_text(DMA_QUEUE), "QueueDMA_Deferrable"))
    bump = re.search(r'addq\.w\s+#1,\s*' + STRADDLE_FRAME, section)
    reject = re.search(r'b\w+\s+\.split_reject', section)
    assert bump, f"{STRADDLE_FRAME} is not incremented in .split"
    assert reject, "the branch to .split_reject is gone — re-read this gate"
    assert bump.start() < reject.start(), (
        "the straddle count is taken AFTER the two-slot check, so it counts survivors "
        "instead of demand — a frame whose demand exceeded the reserve would read as "
        "if it had not")


def test_the_important_selector_is_the_one_the_entry_point_loads():
    """The queue selector is derived from `QueueDMA_Important`, not re-spelled.

    `QueueDMA_Important` loads one constant into d4; `.split` compares d4 against a
    constant to decide whether this straddle is the subject. If those two ever
    name different things the counter silently measures a different queue, and
    nothing else in the tree would notice. Read the first out of the entry point
    and require the second to match it.
    """
    text = _text(DMA_QUEUE)
    entry = _proc_body(text, "QueueDMA_Important")
    m = re.search(r'move\.w\s+#(\w+),\s*d4', entry)
    assert m, "QueueDMA_Important no longer loads a queue-end constant into d4"
    end_const = m.group(1)

    section = _split_section(_proc_body(text, "QueueDMA_Deferrable"))
    sel = re.search(r'cmpi\.w\s+#(\w+),\s*d4', section)
    assert sel, ".split no longer selects a queue with a cmpi against d4"
    assert sel.group(1) == end_const, (
        "the straddle counter selects %r but QueueDMA_Important loads %r — the "
        "instrument is counting a different sub-queue than it claims"
        % (sel.group(1), end_const))


def test_the_all_queues_control_is_counted_unconditionally():
    """The positive control exists and is NOT behind the Important selector.

    A zero in the Important cells is only readable as "Important never straddled"
    if something proves straddles were reachable at all; otherwise it reads
    identically to a counter that was never wired. That is what the all-queues cell
    is for, so it must be bumped before the selector narrows the path.
    """
    section = _split_section(_proc_body(_text(DMA_QUEUE), "QueueDMA_Deferrable"))
    allbump = re.search(r'addq\.w\s+#1,\s*' + STRADDLE_ALL, section)
    sel = re.search(r'cmpi\.w\s+#\w+,\s*d4', section)
    assert allbump, f"{STRADDLE_ALL} — the positive control — is not counted"
    assert sel and allbump.start() < sel.start(), (
        "the all-queues control is counted after the Important selector, so it can "
        "only ever equal the Important count and proves nothing")


# --------------------------------------------------------------------------
# 2. straddles and rejects are different populations, and stay distinguishable
# --------------------------------------------------------------------------

def test_full_and_split_reject_have_separate_counters():
    """The exact confusion the booking names as the reason nobody could measure.

    `.full` (queue exhausted) and `.split_reject` (one free slot, straddle refused)
    used to share `DMA_Overflow_Count`. Sharing it again makes a straddle-reject
    indistinguishable from an ordinary full queue and puts the measurement back out
    of reach.
    """
    body = _proc_body(_text(DMA_QUEUE), "QueueDMA_Deferrable")
    full = re.search(r'^\s*\.full:\s*$', body, re.M)
    byte_capped = re.search(r'^\s*\.byte_capped:\s*$', body, re.M)
    assert full and byte_capped, ".full / .byte_capped labels moved — re-read this gate"
    full_body = body[full.end():byte_capped.start()]
    reject_body = body[re.search(r'^\s*\.split_reject:\s*$', body, re.M).end():]

    assert OVERFLOW in full_body, f".full no longer charges {OVERFLOW}"
    assert SPLIT_REJECT in reject_body, f".split_reject no longer charges {SPLIT_REJECT}"
    assert OVERFLOW not in reject_body, (
        f".split_reject charges {OVERFLOW} again — a straddle-reject is once more "
        f"indistinguishable from a full queue, which is the defect this parcel closed")
    assert SPLIT_REJECT not in full_body, (
        f".full charges {SPLIT_REJECT} — the two failure modes are crossed")


# --------------------------------------------------------------------------
# 3. the per-frame reset cannot lose an increment or fold a window twice
# --------------------------------------------------------------------------

def test_the_fold_reads_and_clears_adjacently():
    """No instruction between the read of the frame cell and its clear.

    Every Important enqueue runs under `move.w #$2700, sr` and this fold runs inside
    the VBlank handler, so the two cannot interleave — but that argument only holds
    while the read and the clear are one uninterruptible pair in the source. Any
    instruction wedged between them is a place a future edit could put a call, and
    an increment landing there is a frame's count silently lost.
    """
    body = _proc_body(_text(VBLANK), "VInt_Level")
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    idx = [i for i, ln in enumerate(lines)
           if re.match(r'move\.w\s+' + STRADDLE_FRAME + r',\s*d\d', ln)]
    assert idx, f"VInt_Level does not read {STRADDLE_FRAME}"
    assert len(idx) == 1, f"{STRADDLE_FRAME} is read more than once in VInt_Level"
    nxt = lines[idx[0] + 1]
    assert re.match(r'clr\.w\s+' + STRADDLE_FRAME + r'\b', nxt), (
        "the clear no longer immediately follows the read of %s (next line is %r) — "
        "anything between them is where a frame's count goes missing"
        % (STRADDLE_FRAME, nxt))


def test_the_fold_precedes_the_important_drain():
    """The fold and the occupancy sample describe the SAME window.

    Nothing removes an Important entry between enqueue and drain, so the instant
    before `Process_DMA_Important` is the window's maximum occupancy by
    construction. Fold after the drain and the peak sample would describe a queue
    that has just been emptied, and the two cells would no longer be comparable.
    """
    body = _proc_body(_text(VBLANK), "VInt_Level")
    drain = re.search(r'jbsr\s+Process_DMA_Important', body)
    assert drain, "VInt_Level no longer drains the Important queue"
    for cell in (STRADDLE_FRAME, STRADDLE_PEAK, PEAK_IMPORTANT):
        hit = re.search(re.escape(cell), body)
        assert hit, f"VInt_Level does not touch {cell}"
        assert hit.start() < drain.start(), (
            f"{cell} is first touched AFTER the Important drain — it now describes a "
            f"different window than the enqueues it is meant to summarise")


def test_the_frame_cell_is_cleared_exactly_once_in_the_engine():
    """One reset site. Two would double-clear; zero would make the peak monotonic
    nonsense that only ever grows."""
    hits = []
    for path in sorted((ROOT / "engine").rglob("*.emp")):
        for ln in _strip_comments(path.read_text()).splitlines():
            if re.search(r'\bclr\.\w\s+' + STRADDLE_FRAME + r'\b', ln):
                hits.append(str(path.relative_to(ROOT)))
    assert hits == ["engine/system/vblank.emp"], (
        "expected exactly one reset of %s, in vblank.emp; found %r" % (STRADDLE_FRAME, hits))


# --------------------------------------------------------------------------
# 4. shape: diagnosis apparatus must not reach a release ROM
# --------------------------------------------------------------------------

def test_every_cell_is_declared_debug_only():
    """All four cells live inside an `if DEBUG == 1 @shape_divergent` group."""
    text = _text(RAM)
    for cell in (STRADDLE_ALL, STRADDLE_FRAME, STRADDLE_PEAK, SPLIT_REJECT):
        m = re.search(r'^\s*' + cell + r':\s', text, re.M)
        assert m, f"{cell} is not declared in engine/ram.emp"
        before = text[:m.start()]
        opens = len(re.findall(r'if\s+DEBUG\s*==\s*1[^\n{]*\{', before))
        closes = before.count('}') - before.count('{') + opens
        assert opens > closes, f"{cell} is declared outside any `if DEBUG == 1` group"


def test_every_instruction_is_debug_only():
    """No cell is touched outside an `if DEBUG == 1` block, in either module.

    This is the property that keeps the release ROMs byte-identical. A bump that
    escaped its guard would cost release bytes for a diagnostic nobody can read
    there, since the cells themselves do not exist in that shape.
    """
    cells = (STRADDLE_ALL, STRADDLE_FRAME, STRADDLE_PEAK, SPLIT_REJECT, PEAK_IMPORTANT)
    for path in (DMA_QUEUE, VBLANK):
        text = _strip_comments(_text(path))
        guarded = "".join(_debug_blocks(text))
        for cell in cells:
            outside = text.count(cell) - guarded.count(cell)
            assert outside == 0, (
                "%s touches %s %d time(s) outside an `if DEBUG == 1` block — that is "
                "release bytes spent on a debug cell that does not exist in release"
                % (path.name, cell, outside))


# --------------------------------------------------------------------------
# 5. the number the reading is judged against, derived and not copied
# --------------------------------------------------------------------------

def test_the_wall_is_derivable_and_the_reserve_is_untouched():
    """`DMA_IMPORTANT_SLOTS - DPLC_ENTRY_RESERVE`, each from its owning file.

    This parcel is an INSTRUMENT and deliberately changes neither constant: the
    booking's whole point is that raising the reserve without a measurement trades a
    possible drop for a certain cost. If a later parcel does move one, it moves this
    assertion with it and has to say so.
    """
    slots = _const("engine/system/constants.emp", "DMA_IMPORTANT_SLOTS")
    reserve = _const("engine/objects/dplc.emp", "DPLC_ENTRY_RESERVE")
    assert slots == 12 and reserve == 2, (
        "DMA_IMPORTANT_SLOTS/DPLC_ENTRY_RESERVE moved (%d/%d). That is allowed, but "
        "the arming note in the parcel's commit message quotes the old pair and the "
        "reading it tells the owner to expect is derived from them — update both."
        % (slots, reserve))
    assert slots - reserve == 10
