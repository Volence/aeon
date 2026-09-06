#!/usr/bin/env python3
"""dplc_straddle — measure the Important-queue SLOT cost of a DPLC frame, and how
it moves when character art is APPENDED to or SHIFTED in the ROM — and whether a
straddling frame is one the game can actually DISPLAY.

WHY THIS EXISTS
---------------
The d-47 budget arithmetic (13 entries against DMA_IMPORTANT_SLOTS = 12, target
10 = 12 - DPLC_ENTRY_RESERVE) is expressed in ENTRIES. The queue is charged in
SLOTS, and the two differ: `engine/system/dma_queue.emp`'s `.transfer` core
splits any transfer that crosses a 128 KB source boundary into TWO queue entries
(`.split`), and rejects the whole transfer when only one slot is free
(`.split_reject`). So

    slot_cost(frame) = sum over entries of (1 + straddles_a_128KB_boundary)

and whether an entry straddles is a function of WHERE THE ART LANDS IN ROM —
i.e. of link-time placement, not of the DPLC blob alone. `dplc_peak_entries`
(engine/objects/dplc.emp) cannot see this: it parses the blob and never learns
the base address.

That makes "appending art disturbs nothing else" a testable claim rather than an
argument, which is what this tool is for. See
docs/2026-08-30-dplc-append-disturbance.md for the falsifier and the verdict.

WHAT IT MEASURES
----------------
For each (character DPLC table, art base) pair reachable from a CharacterDef:

  * the per-frame entry count (the number d-47 reasons about),
  * the per-frame SLOT cost at the art's real linked base address,
  * the peak of each, and which frames hold it,
  * and, under `--sweep`, both peaks as a function of a byte shift applied to
    the art base — the neighbourhood an append moves through.

REACHABILITY — THE QUESTION THIS COULD NOT ASK
----------------------------------------------
The costs above are computed over EVERY frame of a character's DPLC table,
including frames no animation can reach. That overstates (Sonic's only
straddling frame, `$6A`, cannot be displayed at all), which is the mild half.
The sharp half is the other direction: without a reachable set the tool cannot
tell you when a straddle lands on a frame that IS displayable, and moving an art
base — `BLOCK-STREAM-DEDUP` is booked to move one by ~21 KB — moves which frames
straddle. That case has to be loud.

So every subject's frames are split REACHABLE / UNREACHABLE. Reachable means
"some code path can write this index into `Sst.mapping_frame` while the SST's
mappings/DPLC are THIS subject's art", and it is assembled from three sources:

  1. the animation scripts, walked OUT OF THE BUILT ROM (`--rom`) at the
     `Ani_*` table the subject's `CharacterDef` names, with the control-code
     operand widths DERIVED from `AnimateSprite`'s own handlers rather than
     transcribed — `AF_BACK`'s operand is a rewind count and `AF_CHANGE`'s an
     anim id, and neither is a frame;
  2. the per-writer expansions — `Player_ApplyTilt`'s walk/run tilt banks and
     `TailsAppendage_Main`'s roll direction banks — with the bases, shifts and
     masks read from their own defining constants and their instruction
     spellings re-checked;
  3. every OTHER writer of `Sst.mapping_frame`, found by SCANNING the tree
     (`scan_write_sites`) rather than listed from memory. Each site must be
     claimed by a `WRITERS` entry that says which subjects' art it targets and
     what it contributes — a write against a DIFFERENT mappings set (the debug
     marker's `Map_TestObj`, the test objects) contributes nothing and says so.

FAIL-SAFE, NEVER SILENT: a write site no `WRITERS` entry claims, or a claimed
site whose count drifted, WIDENS the affected subjects' reachable set to ALL
frames and prints an UNDETERMINED banner to stdout and stderr. The reachable set
is never quietly narrowed. A broken derivation (a missing constant, a changed
instruction spelling, a script that runs off its body) is `Unmeasurable` and
exits 2.

DERIVATION, NOT TRANSCRIPTION
-----------------------------
Every constant below is read out of the tree at run time and cross-checked:

  * DMA_IMPORTANT_SLOTS, DPLC_ENTRY_RESERVE, TILE_SIZE — parsed from their
    defining `.emp` lines.
  * The 128 KB boundary is DERIVED from the split code rather than typed: the
    core does `lsr.l #1, d1` (source -> words) and then a 16-bit
    `sub.w d3,d0 / sub.w d1,d0 / blo .split`, so the carry fires when
    (source_words + length_words) exceeds a 16-bit wrap, i.e. every
    2 * 0x10000 = 0x20000 source bytes. `boundary_from_source()` re-reads those
    instructions and FAILS LOUD if the spelling changes, rather than silently
    keeping a stale 0x20000.
  * The art blob lengths come from the embedded files named by the `.emp`
    `embed()` lines, and the base addresses from a fresh sigil listing.

LOUD ON UNMEASURABLE: every input this cannot establish raises `Unmeasurable`
and exits non-zero. Nothing here reports "couldn't measure" as 0 or as OK.

USAGE
    tools/dplc_straddle.py --lst s4.debug.lst
    tools/dplc_straddle.py --lst s4.debug.lst --sweep Art_Sonic --range -512:512
    tools/dplc_straddle.py --lst s4.debug.lst --gate      # non-zero if a peak
                                                          # slot cost exceeds
                                                          # the ratchet, or if a
                                                          # REACHABLE frame
                                                          # splits past the
                                                          # DPLC entry reserve
The ROM defaults to the listing with `.lst` -> `.bin`; `--rom` names it directly.
"""

import argparse
import re
import struct
import sys
from pathlib import Path

AEON = Path(__file__).resolve().parent.parent


class Unmeasurable(Exception):
    """An input could not be established. Never rendered as 0 or as green."""


# ---------------------------------------------------------------- source reads

def _read(path):
    p = AEON / path
    if not p.exists():
        raise Unmeasurable(f"{path} does not exist — cannot derive from it")
    return p.read_text()


def const_from_emp(path, name):
    """`pub const NAME = <int>` out of an .emp file. Decimal or $hex."""
    text = _read(path)
    m = re.search(r'^\s*pub\s+const\s+' + re.escape(name) + r'\s*=\s*(\$?[0-9A-Fa-f]+)\s*(?://.*)?$',
                  text, re.M)
    if not m:
        raise Unmeasurable(f"no `pub const {name} = <int>` in {path}")
    raw = m.group(1)
    return int(raw[1:], 16) if raw.startswith('$') else int(raw)


def boundary_from_source():
    """DERIVE the DMA source-boundary period from dma_queue.emp's split test.

    The core converts the source to words (`lsr.l #1, d1`) and then tests
    `0 - length_words - source_words` for borrow with 16-bit `sub.w`s. A borrow
    means the 16-bit word sum wrapped, i.e. the transfer crossed a
    (1 << 16) word == (1 << 17) byte boundary. Both instructions are re-read
    here so a change to either fails loud instead of leaving a stale constant.
    """
    src = _read("engine/system/dma_queue.emp")
    if not re.search(r'^\s*lsr\.l\s+#1,\s*d1\b', src, re.M):
        raise Unmeasurable(
            "dma_queue.emp no longer spells `lsr.l #1, d1` — the source-to-words "
            "conversion this boundary is derived from has changed; re-derive it")
    if not re.search(r'^\s*sub\.w\s+d3,\s*d0\s*$|^\s*sub\.w\s+d3,\s*d0\s*//', src, re.M) or \
       not re.search(r'^\s*sub\.w\s+d1,\s*d0\b', src, re.M):
        raise Unmeasurable(
            "dma_queue.emp no longer spells the `sub.w d3,d0 / sub.w d1,d0` "
            "boundary test — re-derive the boundary period")
    if not re.search(r'^\s*blo\s+\.split\b', src, re.M):
        raise Unmeasurable("dma_queue.emp's `blo .split` is gone — re-derive the boundary")
    word_bits = 16                     # the width of the `sub.w` the borrow comes from
    bytes_per_word = 2                 # the `lsr.l #1` above
    return (1 << word_bits) * bytes_per_word


def embed_path(emp_path, const_name):
    """The file an `.emp` `const <name> = embed("<path>")` points at."""
    text = _read(emp_path)
    m = re.search(r'^\s*const\s+' + re.escape(const_name) + r'\s*=\s*embed\("([^"]+)"\)',
                  text, re.M)
    if not m:
        raise Unmeasurable(f"no `const {const_name} = embed(...)` in {emp_path}")
    rel = m.group(1)
    p = AEON / rel
    if not p.exists():
        raise Unmeasurable(f"{emp_path} embeds {rel}, which does not exist")
    return p


def lst_labels(lst_path):
    """label -> LMA, from a sigil listing's `(0) <n>/<hex> : <label>:` rows."""
    p = Path(lst_path)
    if not p.exists():
        raise Unmeasurable(f"listing {lst_path} does not exist — build the shape first")
    out = {}
    for line in p.read_text().splitlines():
        m = re.match(r'^\(0\)\s+\d+/([0-9A-Fa-f]+)\s+:\s+([A-Za-z_][\w.]*):', line)
        if m:
            out[m.group(2)] = int(m.group(1), 16)
    if not out:
        raise Unmeasurable(f"{lst_path} yielded no label rows — wrong file or format drift")
    return out


# ------------------------------------------------------------------ DPLC parse

def parse_dplc(data, who):
    """S2-format DPLC -> [[(tile_start, tile_count), ...], ...] by frame.

    Written fresh from the format spec in engine/objects/dplc.emp's header
    (the same spec `dplc_peak_entries` walks), not shared with dplc_layout.py,
    so a bug in one does not silently agree with the other.
    """
    if len(data) < 2:
        raise Unmeasurable(f"{who}: DPLC blob is {len(data)} B — too short to hold a table")
    first = struct.unpack_from('>H', data, 0)[0]
    if first == 0 or first % 2:
        raise Unmeasurable(f"{who}: first offset word is {first} — not a frame table")
    frames = []
    for fi in range(first // 2):
        off = struct.unpack_from('>H', data, fi * 2)[0]
        if off + 2 > len(data):
            raise Unmeasurable(f"{who}: frame {fi} offset {off} is past the blob end")
        n = struct.unpack_from('>H', data, off)[0]
        pos = off + 2
        if pos + 2 * n > len(data):
            raise Unmeasurable(f"{who}: frame {fi} claims {n} entries, past the blob end")
        ents = []
        for _ in range(n):
            w = struct.unpack_from('>H', data, pos)[0]
            pos += 2
            ents.append((w & 0x0FFF, ((w >> 12) & 0xF) + 1))
        frames.append(ents)
    return frames


# ------------------------------------------------------------------- the model

def straddles(src, length, boundary):
    """Does a `length`-byte transfer from `src` cross a `boundary` multiple?

    Mirrors dma_queue.emp `.transfer`: the borrow fires when the transfer's
    bytes carry past the next boundary multiple at or above `src`. Touching a
    boundary exactly (src+length == multiple) does NOT cross.
    """
    return (src % boundary) + length > boundary


def frame_costs(frames, art_base, tile_size, boundary):
    """Per frame: (entry_count, slot_cost, straddling_entry_indices)."""
    out = []
    for ents in frames:
        n_str, idx = 0, []
        for ei, (start, count) in enumerate(ents):
            src = art_base + start * tile_size
            if straddles(src, count * tile_size, boundary):
                n_str += 1
                idx.append(ei)
        out.append((len(ents), len(ents) + n_str, idx))
    return out


# ---------------------------------------------------------------- reachability
#
# Everything below answers ONE question: which of a subject's DPLC frames can the
# game actually put in `Sst.mapping_frame` while that subject's art is the SST's
# art? See the module header's REACHABILITY section for the shape of the answer
# and for the fail-safe rule.

#: Source files scanned for `Sst.mapping_frame` writers. Derived from the
#: subjects' own game (they all live under games/sonic4), plus the engine every
#: game shares — NOT a hand-kept list of files that happen to have one today.
WRITER_SCAN_ROOTS = ("engine", "games/sonic4")
WRITER_SCAN_SUFFIXES = (".emp", ".asm")

#: 68000 mnemonics whose LAST operand is the destination. A line is a write site
#: when one of these is the mnemonic and `mapping_frame(aN)` is its last operand.
WRITE_MNEMONICS = {
    "move", "movea", "clr", "st", "sf", "add", "addq", "addi", "sub", "subq",
    "subi", "or", "ori", "and", "andi", "eor", "eori", "not", "neg", "negx",
    "bset", "bclr", "bchg", "addx", "subx", "abcd", "sbcd", "nbcd", "tas",
}


def _strip_comment(line):
    """Drop `//` (.emp) and `;` (.asm) trailing comments. Neither language has a
    string literal on an instruction line here, so this is exact enough to key a
    scanner off."""
    for mark in ("//", ";"):
        i = line.find(mark)
        if i >= 0:
            line = line[:i]
    return line


def local_const(path, name):
    """`const NAME = <int>` (with or without `pub`) out of an .emp file."""
    text = _read(path)
    m = re.search(r'^\s*(?:pub\s+)?const\s+' + re.escape(name) +
                  r'\s*=\s*(\$?[0-9A-Fa-f]+)\s*(?://.*)?$', text, re.M)
    if not m:
        raise Unmeasurable(f"no `const {name} = <int>` in {path} — re-derive it")
    raw = m.group(1)
    return int(raw[1:], 16) if raw.startswith('$') else int(raw)


def require_spelling(path, pattern, why):
    """A derivation that depends on an instruction being spelled a certain way
    re-reads that instruction, so a change to it fails loud instead of leaving a
    stale constant behind (the `boundary_from_source` discipline)."""
    if not re.search(pattern, _read(path), re.M):
        raise Unmeasurable(f"{path} no longer matches `{pattern}` — {why}")


def sst_offsets():
    """field -> byte offset, from engine/objects/sst.emp's `name: T @ $XX` rows."""
    text = _read("engine/objects/sst.emp")
    out = {}
    for m in re.finditer(r'^\s*(\w+)\s*:\s*[^@\n]+@\s*\$([0-9A-Fa-f]+)', text, re.M):
        out[m.group(1)] = int(m.group(2), 16)
    if "mapping_frame" not in out:
        raise Unmeasurable("sst.emp declares no `mapping_frame ... @ $XX` — re-derive the SST layout")
    return out


def anim_opcodes():
    """The animation control codes, and how many bytes each EVENT consumes.

    Values come from engine/system/constants.emp. The classification — which
    codes terminate a straight-line walk and which are inline events the
    interpreter reads THROUGH — is DERIVED from AnimateSprite's own handlers:
    an event handler advances the script cursor by its own width with
    `addq.b #N, Sst.anim_frame(a0)`, and a terminator does not. So a new event
    opcode, or a changed operand width, moves this rather than silently
    mis-parsing a script.

    Returns (values: name -> byte, events: byte -> width, threshold: byte).
    """
    names = ["AF_END", "AF_BACK", "AF_CHANGE", "AF_ROUTINE", "AF_DELETE",
             "AF_CALLBACK", "AF_SOUND", "AF_COLLISION", "AF_SET_FIELD"]
    values = {n: const_from_emp("engine/system/constants.emp", n) for n in names}

    src = _read("engine/objects/animate.emp")
    # The dispatch threshold: everything at or above AF_SET_FIELD is a command,
    # everything below it is a frame index. AnimateSprite spells that test five
    # times; one is enough to establish it, zero is not.
    if not re.search(r'^\s*cmpi\.b\s+#AF_SET_FIELD,\s*d0\b', src, re.M):
        raise Unmeasurable(
            "animate.emp no longer spells `cmpi.b #AF_SET_FIELD, d0` — the "
            "frame-vs-command threshold this walk depends on has moved; re-derive it")

    # The jump table names one handler label per code, highest code first
    # ($FF down to $F7) — that ORDER is what the pc-indexed `jmp` encodes.
    table = re.search(r'^\s*\.cc_table:\s*$(.*?)^\s*\.cc_end:', src, re.M | re.S)
    if not table:
        raise Unmeasurable("animate.emp has no `.cc_table:` ... `.cc_end:` block — re-derive the dispatch")
    handlers = re.findall(r'^\s*bra\.w\s+(\.\w+)', table.group(1), re.M)
    if len(handlers) != len(names):
        raise Unmeasurable(
            f"animate.emp's .cc_table has {len(handlers)} rows for {len(names)} control "
            f"codes — the dispatch changed shape; re-derive the walk")

    # A handler's body runs to the start of the NEXT handler (or to the shared
    # `.after_event` tail every event falls into). It is NOT bounded by the next
    # local label: .evt_callback carries its own `.evt_cb_done:` and its cursor
    # advance sits after it, so a next-label bound would classify the callback as
    # a terminator and silently truncate every script that carries one.
    bounds = {}
    for label in handlers + [".after_event"]:
        m = re.search(r'^\s*' + re.escape(label) + r':\s*$', src, re.M)
        if not m:
            raise Unmeasurable(f"animate.emp names handler {label} in .cc_table but "
                               f"defines no such block — re-derive the walk")
        bounds[label] = m.start()
    ordered = sorted(bounds.values())

    events = {}
    for name, label in zip(names, handlers):
        start = bounds[label]
        end = min([p for p in ordered if p > start], default=len(src))
        adv = re.search(r'^\s*addq\.b\s+#(\d+),\s*Sst\.anim_frame\(a0\)', src[start:end], re.M)
        if adv:
            events[values[name]] = int(adv.group(1))
    if not events:
        raise Unmeasurable("no animation handler advances Sst.anim_frame by a literal width — "
                           "the inline-event format changed; re-derive the walk")
    return values, events, values["AF_SET_FIELD"]


def parse_anim_table(rom, base, count_expected, who, af, events, mapframe_off):
    """Walk an `offsets` animation table OUT OF THE ROM -> {anim_id: {frames}}.

    The table is words of offsets from its own base, with the bodies packed
    inline behind it, so the first offset IS twice the entry count — the same
    self-describing shape `parse_dplc` reads. The count is cross-checked against
    ANIM_COUNT by the caller.

    Each body is byte 0 = duration, then frame bytes and control codes. The walk
    stops at a terminator: AF_END restarts at byte 1, AF_BACK rewinds by its
    operand and AF_CHANGE switches to another id — all three land on bytes this
    walk has already covered (AF_CHANGE's target body is enumerated in its own
    right), so stopping loses no frame. Inline events are read THROUGH at the
    widths anim_opcodes() derived.

    Returns (frames_by_id, notes) — notes carries anything loud the walk found.
    """
    if base + 2 > len(rom):
        raise Unmeasurable(f"{who}: anim table base 0x{base:X} is past the ROM end")
    first = struct.unpack_from('>H', rom, base)[0]
    if first == 0 or first % 2:
        raise Unmeasurable(f"{who}: first offset word is {first} — not an offsets table")
    count = first // 2
    if count != count_expected:
        raise Unmeasurable(
            f"{who}: the table holds {count} entries but ANIM_COUNT is {count_expected} — "
            f"the ROM table and the id space disagree; re-derive one of them")
    offs = [struct.unpack_from('>H', rom, base + 2 * i)[0] for i in range(count)]
    # A body ends where the next one begins. The LAST body has no successor, so
    # it is bounded by the highest offset plus a generous slack and must still
    # terminate inside it — running off the end is Unmeasurable, not a guess.
    starts = sorted(set(offs))
    slack = 4096
    notes = []
    by_id = {}
    for i, off in enumerate(offs):
        limit = min([s for s in starts if s > off], default=max(starts) + slack)
        p, frames = off + 1, set()
        while p < limit:
            b = rom[base + p]
            if b < af["AF_SET_FIELD"]:
                frames.add(b)
                p += 1
                continue
            if b == af["AF_BACK"]:
                # Stopping here is only safe because the rewind lands on bytes
                # this walk has already covered. `.cc_back` does a byte
                # `sub.b d0, anim_frame(a0)`, so a rewind larger than the cursor
                # UNDERFLOWS and the interpreter reads far outside the body —
                # frames this walk would never see. That is a script bug and a
                # hole in the reachable set at once, so it is loud, not assumed.
                cursor = p - off - 1
                n = rom[base + p + 1]
                if n > cursor:
                    raise Unmeasurable(
                        f"{who}: animation {i} rewinds {n} from cursor {cursor} — the byte "
                        f"`sub.b` underflows and the interpreter reads outside the script "
                        f"body, so the reachable set cannot be established from it")
                break
            if b in events:
                if b == af["AF_SET_FIELD"] and rom[base + p + 1] == mapframe_off:
                    # A script writing mapping_frame through AF_SET_FIELD would
                    # bypass the frame walk entirely. DEBUG asserts against it;
                    # release does not, so count the value and say so.
                    val = rom[base + p + 2]
                    frames.add(val)
                    notes.append(f"{who}[{i}]: AF_SET_FIELD writes mapping_frame = ${val:02X}")
                p += events[b]
                continue
            break                                   # a terminator
        else:
            raise Unmeasurable(
                f"{who}: animation {i} runs past its body end (offset {off}, limit {limit}) "
                f"with no terminator — the script format or the table changed")
        by_id[i] = frames
    return by_id, notes


def tilt_expansion(frames_by_id):
    """Player_ApplyTilt's contribution: the tilted walk/run art blocks.

    `mapping_frame = script_frame + (block << shift)` with block 0..TILT_SETS-1,
    gated to the WALK and RUN ids alone. Every number here is read from the
    constants that define it in player_common.emp / constants.emp, and the four
    instructions the arithmetic depends on are re-read so a re-spelled routine
    fails loud instead of leaving this formula stale.
    """
    P = "games/sonic4/player/player_common.emp"
    C = "games/sonic4/config/constants.emp"
    sets = local_const(P, "TILT_SETS")
    walk_shift = local_const(P, "TILT_WALK_SHIFT")
    run_shift = local_const(P, "TILT_RUN_SHIFT")
    anim_walk = const_from_emp(C, "ANIM_WALK")
    anim_run = const_from_emp(C, "ANIM_RUN")

    require_spelling(P, r'^\s*cmpi\.b\s+#ANIM_RUN,\s*d0\s*$',
                     "Player_ApplyTilt's `id <= ANIM_RUN` gate is the whole reason only "
                     "walk and run expand; re-derive which anims tilt")
    require_spelling(P, r'^\s*andi\.w\s+#TILT_SETS - 1,\s*d2\b',
                     "the orientation block is masked to 0..TILT_SETS-1 here; re-derive the block range")
    require_spelling(P, r'^\s*lsl\.w\s+#TILT_WALK_SHIFT,\s*d2\b',
                     "the walk block stride is this shift; re-derive it")
    require_spelling(P, r'^\s*lsl\.w\s+#TILT_RUN_SHIFT,\s*d2\b',
                     "the run block stride is this shift; re-derive it")
    require_spelling(P, r'^\s*add\.b\s+d2,\s*d0\s*$',
                     "the block offset is ADDED to the script's own frame byte; re-derive the formula")
    if anim_walk != 0:
        raise Unmeasurable(
            f"ANIM_WALK is {anim_walk}, not 0 — Player_ApplyTilt picks its stride with a bare "
            f"`tst.b anim(a0)`, so this expansion is only valid while WALK is 0")

    out = set()
    for anim_id, shift in ((anim_walk, walk_shift), (anim_run, run_shift)):
        for f in frames_by_id.get(anim_id, ()):
            for block in range(sets):
                out.add((f + (block << shift)) & 0xFF)
    return out, (f"tilt: ids {anim_walk}/{anim_run}, {sets} blocks, "
                 f"strides 1<<{walk_shift}/1<<{run_shift}")


def appendage_bank(frames_by_id):
    """TailsAppendage_Main's roll direction bank: the ball-spin cycle is stored
    four times over, and the bank (a submask of the `andi.b` mask) is added to
    the script's frame. Gated on ANIM_ROLL — every other row would index into an
    unrelated frame, which is exactly what the `cmpi.b` below says."""
    A = "games/sonic4/objects/tails_appendage.emp"
    anim_roll = const_from_emp("games/sonic4/config/constants.emp", "ANIM_ROLL")
    require_spelling(A, r'^\s*cmpi\.b\s+#ANIM_ROLL,\s*Sst\.anim\(a0\)\s*$',
                     "the direction bank is gated on ANIM_ROLL; re-derive which anims bank")
    m = re.search(r'^\s*andi\.b\s+#\$([0-9A-Fa-f]+),\s*d0\b.*?bank', _read(A), re.M)
    if not m:
        raise Unmeasurable(
            "tails_appendage.emp no longer masks the direction bank with an `andi.b #$X, d0` — "
            "re-derive the bank set")
    mask = int(m.group(1), 16)
    require_spelling(A, r'^\s*add\.b\s+1\(a1,d1\.w\),\s*d0\b',
                     "the bank is ADDED to the script's own frame byte; re-derive the formula")
    banks = [b for b in range(mask + 1) if b & ~mask == 0]
    out = {(f + b) & 0xFF for f in frames_by_id.get(anim_roll, ()) for b in banks}
    return out, f"appendage bank: id {anim_roll}, banks {'/'.join(str(b) for b in banks)}"


def climb_frames():
    """The Knuckles-only frames the climb/ledge state bodies write DIRECTLY.

    `AnimateSprite` never produces these: Climb_Animate pins anim_timer and owns
    mapping_frame itself. The cycle bounds and the two one-shot poses are their
    own constants; the clamber poses are the first byte of each 4-byte entry of
    Climb_ClamberFrames, read out of the table rather than restated.
    """
    P = "games/sonic4/player/player_climb.emp"
    lo = local_const(P, "CLIMB_FRAME_LO")
    hi = local_const(P, "CLIMB_FRAME_HI")
    if lo > hi:
        raise Unmeasurable(f"CLIMB_FRAME_LO ${lo:02X} > CLIMB_FRAME_HI ${hi:02X} — the climb cycle "
                           f"bounds are inverted; re-derive them")
    cycle = set(range(lo, hi + 1))
    catch = {local_const(P, "CLIMB_CATCH_FRAME")}
    letgo = {local_const(P, "CLIMB_LETGO_FRAME")}

    m = re.search(r'^\s*data\s+Climb_ClamberFrames\s*:[^=]*=\s*\[(.*?)\]', _read(P), re.M | re.S)
    if not m:
        raise Unmeasurable("player_climb.emp declares no `data Climb_ClamberFrames: ... = [...]` — "
                           "re-derive the ledge clamber poses")
    body = re.sub(r'//[^\n]*', '', m.group(1))
    items = [t.strip() for t in body.split(",") if t.strip()]
    if len(items) % 4:
        raise Unmeasurable(f"Climb_ClamberFrames holds {len(items)} bytes, not a whole number of "
                           f"4-byte entries — re-derive the clamber step stride")
    clamber = set()
    for i in range(0, len(items), 4):
        tok = items[i]
        if not re.fullmatch(r'\$[0-9A-Fa-f]+|\d+', tok):
            raise Unmeasurable(f"Climb_ClamberFrames entry {i // 4} starts with `{tok}`, which is "
                               f"not a literal frame byte — re-derive the table")
        clamber.add(int(tok[1:], 16) if tok.startswith('$') else int(tok))
    return {"cycle": cycle, "catch": catch, "letgo": letgo, "clamber": clamber}


def scan_write_sites():
    """Every line in the scanned tree that WRITES Sst.mapping_frame.

    Two shapes are recognised, because the tree uses both:

      * a named write — `mapping_frame(aN)` as the instruction's LAST operand
        (68000 destination), with or without the `Sst.` qualifier;
      * a sized-override OVERLAY — `move.l #..., Sst.<field>:l(aN)` whose span
        from <field>'s offset covers mapping_frame's. Load_Object initialises
        four SST bytes that way, so a scanner that only looked for the name
        would miss the one writer that runs for EVERY spawned object.

    Returns [(path, line_no, enclosing_symbol, text)].
    """
    off = sst_offsets()
    target = off["mapping_frame"]
    named = re.compile(r'(?:Sst\.)?mapping_frame(?::[bwl])?\(a[0-7][^)]*\)\s*$')
    overlay = re.compile(r'Sst\.(\w+):([bwl])\(a[0-7][^)]*\)\s*$')
    mnemonic = re.compile(r'^\s*([a-z]+)\.?([bwl]?)\s+\S')
    symbol = re.compile(r'^\s*(?:pub\s+)?(?:proc|comptime\s+fn|fn)\s+([A-Za-z_]\w*)')
    width = {"b": 1, "w": 2, "l": 4}

    sites = []
    for root in WRITER_SCAN_ROOTS:
        base = AEON / root
        if not base.is_dir():
            raise Unmeasurable(f"{root} is not a directory — the writer scan cannot run")
        for p in sorted(base.rglob("*")):
            if p.suffix not in WRITER_SCAN_SUFFIXES or not p.is_file():
                continue
            rel = p.relative_to(AEON).as_posix()
            sym = "<file>"
            for n, raw in enumerate(p.read_text(errors="replace").splitlines(), 1):
                s = symbol.match(raw)
                if s:
                    sym = s.group(1)
                line = _strip_comment(raw).rstrip()
                mn = mnemonic.match(line)
                if not mn or mn.group(1) not in WRITE_MNEMONICS:
                    continue
                if named.search(line):
                    sites.append((rel, n, sym, line.strip()))
                    continue
                ov = overlay.search(line)
                if ov and ov.group(1) in off:
                    start = off[ov.group(1)]
                    if start <= target < start + width[ov.group(2)]:
                        sites.append((rel, n, sym, line.strip()))
    if not sites:
        raise Unmeasurable("the writer scan found NO mapping_frame write sites at all — "
                           "the scan roots or the field name are wrong")
    return sites


#: What each writer contributes, keyed by (file, enclosing symbol) — the unit a
#: reader can check by opening the file at that routine. `sites` is the number of
#: write lines the routine is expected to hold, so a new write inside a claimed
#: routine is a count drift and goes loud rather than riding in unnoticed.
#:
#: `art` names WHOSE mappings the SST holds at the write:
#:    "player"      — the active CharacterDef's art (sonic / tails / knuckles)
#:    "appendage"   — the Tails appendage's own set
#:    "knuckles"    — a Knuckles-only state body
#:    "any"         — every subject (a generic object path)
#:    "other"       — a DIFFERENT mappings set, so it reaches none of this art
#: `frames` is a key into the contribution table built in reachable_sets().
WRITERS = {
    ("engine/objects/animate.emp", "AnimateSprite"): dict(
        sites=1, art="any", frames="script",
        why="the script interpreter — the frame bytes of the SST's own anim table"),
    ("engine/objects/load_object.emp", "Load_Object"): dict(
        sites=1, art="any", frames="zero",
        why="the $FF000000 overlay over prev_anim..mapping_frame zeroes the frame at spawn"),
    ("games/sonic4/player/player_common.emp", "Player_ApplyTilt"): dict(
        sites=1, art="player", frames="tilt",
        why="the ground-angle tilt banks, walk/run only"),
    ("games/sonic4/player/player_common.emp", "Player_DebugEnter"): dict(
        sites=1, art="other", frames="none",
        evidence=[(r'move\.l\s+#Map_TestObj,\s*mappings\(a0\)',
                   "debug-enter swaps the player to the marker's mappings first")],
        why="writes frame 0 against Map_TestObj, not the character sheet"),
    ("games/sonic4/player/player_common.emp", "Player_DebugExit"): dict(
        sites=1, art="player", frames="zero",
        evidence=[(r'jbsr\s+Player_InitAssets',
                   "debug-exit restores the CharacterDef's mappings before the frame write")],
        why="frame 0 against the restored character sheet"),
    # The four climb/ledge writers are Knuckles-only, and that is CHECKED, not
    # asserted: PSTATE_CLIMB is entered from exactly one place (Climb_Catch, the
    # `.hit_wall` branch of PState_Glide), the glide family is entered only from
    # the AbilityHook below, and `ability=` makes the gate verify that exactly
    # one CharacterDef owns that hook. Give a second character the same hook and
    # these subjects widen instead of quietly staying Knuckles'.
    ("games/sonic4/player/player_climb.emp", "Climb_Animate"): dict(
        sites=1, art="knuckles", frames="climb_cycle", ability="Ability_KnuxGlide",
        why="the climb cycle, owned by the state body (anim_timer is pinned)"),
    ("games/sonic4/player/player_climb.emp", "Climb_LetGo"): dict(
        sites=1, art="knuckles", frames="climb_letgo", ability="Ability_KnuxGlide",
        why="the let-go pose"),
    ("games/sonic4/player/player_climb.emp", "Climb_DoClamberStep"): dict(
        sites=1, art="knuckles", frames="climb_clamber", ability="Ability_KnuxGlide",
        why="the four ledge-clamber poses, from Climb_ClamberFrames"),
    ("games/sonic4/player/player_climb.emp", "Climb_Catch"): dict(
        sites=1, art="knuckles", frames="climb_catch", ability="Ability_KnuxGlide",
        why="the wall-catch pose"),
    ("games/sonic4/objects/tails_appendage.emp", "TailsAppendage_Main"): dict(
        sites=1, art="appendage", frames="appendage",
        why="the roll direction bank added to the appendage script's own frame"),
    ("games/sonic4/objects/test_player.emp", "TestPlayer_Main"): dict(
        sites=2, art="sonic", frames="zero",
        evidence=[(r'move\.l\s+#Map_Sonic,\s*mappings\(a0\)',
                   "the debug-exit half restores Map_Sonic before writing frame 0")],
        why="two clr.b sites, one against Map_TestObj (contributes nothing) and one "
            "against Map_Sonic; the union is frame 0"),
    ("games/sonic4/objects/test_solid.emp", "TestSolid_Init"): dict(
        sites=1, art="other", frames="none",
        evidence=[(r'code:\s*"TestSolid_Init",\s*map:\s*"Map_TestObj"',
                   "ObjDef_Solid gives the slot Map_TestObj",
                   "games/sonic4/data/objdefs/test_objects.emp")],
        why="subtype -> frame against Map_TestObj"),
    ("games/sonic4/objects/test_helpers.emp", "test_obj_prolog"): dict(
        sites=1, art="other", frames="none",
        evidence=[(r'move\.l\s+#Map_TestObj,\s*mappings\(a0\)',
                   "the prolog sets Map_TestObj in the same splice")],
        why="the shared test-object prolog frame, against Map_TestObj"),
    # RENAMED 2026-09-05, not added: the write site is the SAME `.ensure_glyph`
    # builder, which moved from the retired Debug_SceneReadout_Show into
    # Debug_PresetReadout_Show when the effects lab's three selection chords collapsed
    # into one list and the two-digit cursor readout it used to draw went with them.
    # One site, same evidence, same argument.
    ("games/sonic4/test/ojz_scroll_test.emp", "Debug_PresetReadout_Show"): dict(
        sites=1, art="other", frames="none",
        evidence=[(r'move\.l\s+#Map_TestObj,\s*Sst\.mappings\(a0\)',
                   "the glyph slot is built on Map_TestObj")],
        why="the debug preset readout glyph, against Map_TestObj"),
    # EFFECTS-W1 F4. Same class as the readout above and reached the same way (a
    # System slot the effects lab builds by hand), but its mappings are NOT
    # Map_TestObj: these tags draw a 4x1 / 3x1 letter strip, and the two frame
    # records for that are written by hand inside the proc's own DEBUG block —
    # a module-scope mapping would emit in the plain shape. So the evidence
    # pattern is the `lea` that binds that local table rather than the readout's
    # `move.l #Map_TestObj`, and it is what proves the slot never holds a
    # character sheet at the frame write.
    ("games/sonic4/test/ojz_scroll_test.emp", "Debug_TierTags_Update"): dict(
        sites=1, art="other", frames="none",
        evidence=[(r'lea\s+\.tag_mappings\(pc\),\s*a1\b',
                   "the tag slot is built on the proc's own .tag_mappings strip frames")],
        why="the effects-lab tier name tag, against .tag_mappings"),
    # EFFECTS-W1 item 9d, the waterline stamp. The same class again — a System slot the
    # effects lab builds by hand — and it carries the tier tags' argument rather than the
    # readout's: its mappings are a hand-written frame inside the proc's own DEBUG block
    # (`.wl_mappings`), not Map_TestObj, because a module-scope mapping would emit in the
    # plain shape. The art it names is the ENGINE's waterline run at VRAM_WATERLINE_STRIPS,
    # which is not a character sheet and is not DPLC'd at all: it is filled by one whole-run
    # DMA from Waterline_Art_Update (engine/level/bg_anim.emp) and never by a DPLC list. So
    # this site cannot widen any subject's reachable frame set, and the `lea` is what proves
    # the slot never holds a character sheet at the frame write.
    ("games/sonic4/test/ojz_scroll_test.emp", "Debug_WaterlineStamp_Show"): dict(
        sites=1, art="other", frames="none",
        evidence=[(r'lea\s+\.wl_mappings\(pc\),\s*a1\b',
                   "the stamp slot is built on the proc's own .wl_mappings frame")],
        why="the effects-lab waterline stamp, against .wl_mappings"),
}


def check_anim_dplc_pairings():
    """A test object that animated Sonic's SCRIPTS against Tails' DPLC would make
    the per-subject script set a lie. Every routine that hard-binds both an
    `Ani_*` table and a `DPLC_*` table must bind the MATCHING pair."""
    symbol = re.compile(r'^\s*(?:pub\s+)?(?:proc|comptime\s+fn|fn)\s+([A-Za-z_]\w*)')
    ani = re.compile(r'#Ani_(\w+)\b')
    dplc = re.compile(r'#DPLC_(\w+)\b')
    bad = []
    for root in WRITER_SCAN_ROOTS:
        for p in sorted((AEON / root).rglob("*")):
            if p.suffix not in WRITER_SCAN_SUFFIXES or not p.is_file():
                continue
            rel, sym, seen = p.relative_to(AEON).as_posix(), "<file>", {}
            for n, raw in enumerate(p.read_text(errors="replace").splitlines(), 1):
                s = symbol.match(raw)
                if s:
                    sym, seen = s.group(1), {}
                line = _strip_comment(raw)
                for rx, key in ((ani, "ani"), (dplc, "dplc")):
                    m = rx.search(line)
                    if m:
                        seen[key] = m.group(1)
                if "ani" in seen and "dplc" in seen:
                    if seen["ani"] != seen["dplc"]:
                        bad.append(f"{rel}:{n} ({sym}) binds Ani_{seen['ani']} with "
                                   f"DPLC_{seen['dplc']}")
                    # Cleared on every completed pair, matched or not: a routine
                    # that binds two sets in turn must be judged pair by pair,
                    # not against whatever it named first.
                    seen = {}
    return bad


def subject_bindings():
    """art label -> {dplc, anim, kind}, read from the records that declare them.

    The three player characters come from their `CharacterDef` literals, which
    is the ONE place the art / DPLC / anim-table triple is bound together; the
    appendage comes from the `equ ... = extern(...)` block its object uses for
    the same purpose. Nothing here is a pairing typed into this tool.
    """
    out = {}
    for p in sorted((AEON / "games/sonic4/player").glob("*.emp")):
        text = p.read_text()
        for m in re.finditer(r'pub\s+data\s+(CharDef_\w+)\s*:\s*CharacterDef\s*=\s*'
                             r'CharacterDef\{(.*?)\n\}', text, re.S):
            body = m.group(2)
            f = {k: re.search(r'cd_' + k + r':\s*extern\("(\w+)"\)', body) for k in
                 ("dplc", "artbase", "animtable")}
            if not all(f.values()):
                raise Unmeasurable(
                    f"{m.group(1)} does not name all three of cd_dplc / cd_artbase / "
                    f"cd_animtable as extern(...) — the art-to-script binding cannot be derived")
            ability = re.search(r'cd_ability:\s*extern\("(\w+)"\)', body)
            out[f["artbase"].group(1)] = {"dplc": f["dplc"].group(1),
                                          "anim": f["animtable"].group(1),
                                          "kind": "player", "record": m.group(1),
                                          "ability": ability.group(1) if ability else None}
    app = _read("games/sonic4/objects/tails_appendage.emp")
    eq = {k: re.search(r'equ\s+' + k + r'\s*=\s*extern\("(\w+)"\)', app) for k in
          ("ART_TAILS_APPENDAGE", "DPLC_TAILS_APPENDAGE", "ANI_TAILS_APPENDAGE")}
    if not all(eq.values()):
        raise Unmeasurable(
            "tails_appendage.emp no longer binds ART/DPLC/ANI_TAILS_APPENDAGE with "
            "`equ ... = extern(...)` — the appendage's art-to-script binding cannot be derived")
    out[eq["ART_TAILS_APPENDAGE"].group(1)] = {
        "dplc": eq["DPLC_TAILS_APPENDAGE"].group(1),
        "anim": eq["ANI_TAILS_APPENDAGE"].group(1),
        "kind": "appendage", "record": "tails_appendage.emp equ block", "ability": None}
    return out


def sole_ability_owner(bind, ability):
    """Which subject's CharacterDef is the ONLY one pointing at `ability`.

    A state body reached only through one character's airborne ability hook is
    that character's alone — but "Knuckles only" is a fact about the ROSTER, not
    a property of the file it lives in. Give a second record the same hook and
    those frames become reachable for a second sheet. Returns the art label, or
    None if zero or more than one record owns it (which the caller must treat as
    undetermined, never as "still just the one").
    """
    owners = [art for art, b in bind.items() if b.get("ability") == ability]
    return owners[0] if len(owners) == 1 else None


def reachable_sets(subs, rom, labels):
    """subject name -> {"frames": set, "undetermined": [reasons], "notes": [str]}.

    UNDETERMINED never narrows: any unclaimed write site, any claimed routine
    whose write count drifted, and any evidence line that stopped matching
    widens the affected subjects to EVERY frame and is reported.
    """
    off = sst_offsets()
    af, events, _ = anim_opcodes()
    anim_count = const_from_emp("games/sonic4/config/constants.emp", "ANIM_COUNT")
    bind = subject_bindings()
    climb = climb_frames()

    notes, undet_all = [], []

    # --- the scripts, out of the ROM -------------------------------------
    scripts = {}
    for s in subs:
        b = bind.get(s["art_label"])
        if b is None:
            raise Unmeasurable(
                f"{s['art_label']} is bound by no CharacterDef and by no appendage equ block — "
                f"its animation table cannot be derived")
        if b["dplc"] != s["dplc_label"]:
            raise Unmeasurable(
                f"{b['record']} pairs {s['art_label']} with {b['dplc']}, but this tool's "
                f"subject pairs it with {s['dplc_label']} — one of them is wrong")
        if b["anim"] not in labels:
            raise Unmeasurable(f"{b['anim']} (named by {b['record']}) is not in the listing")
        by_id, walk_notes = parse_anim_table(rom, labels[b["anim"]], anim_count,
                                             b["anim"], af, events, off["mapping_frame"])
        scripts[s["name"]] = by_id
        notes.extend(walk_notes)
        s["anim_label"] = b["anim"]
        s["kind"] = b["kind"]

    # --- the per-writer contributions ------------------------------------
    def contribution(key, sub):
        if key == "script":
            # EVERY row of the table, including ids this character cannot enter
            # (Sonic's Fly/Glide rows exist only to keep the ANIM id space
            # total). That is the SAFE direction — it can only overstate — and
            # it costs nothing today because every such row is a byte-for-byte
            # copy of that character's own walk cycle. Narrowing it would mean
            # deciding which ids each character's state machine can reach, which
            # is a second, drift-prone copy of Player_Animate's classifier.
            return set().union(*scripts[sub["name"]].values()) if scripts[sub["name"]] else set()
        if key == "zero":
            return {0}
        if key == "none":
            return set()
        if key == "tilt":
            got, note = tilt_expansion(scripts[sub["name"]])
            notes.append(f"{sub['name']}: {note}")
            return got
        if key == "appendage":
            got, note = appendage_bank(scripts[sub["name"]])
            notes.append(f"{sub['name']}: {note}")
            return got
        if key.startswith("climb_"):
            return climb[key[len("climb_"):]]
        raise Unmeasurable(f"WRITERS names an unknown contribution `{key}`")

    def applies(art, sub):
        if art == "any":
            return True
        if art == "player":
            return sub["kind"] == "player"
        if art == "appendage":
            return sub["kind"] == "appendage"
        if art == "other":
            return False
        return art == sub["name"]

    sites = scan_write_sites()
    by_routine = {}
    for rel, n, sym, text in sites:
        by_routine.setdefault((rel, sym), []).append((n, text))

    for key in sorted(set(by_routine) | set(WRITERS)):
        spec = WRITERS.get(key)
        found = by_routine.get(key, [])
        if spec is None:
            undet_all.append(
                f"UNCLAIMED writer {key[0]} ({key[1]}) at line(s) "
                f"{', '.join(str(n) for n, _ in found)} — no WRITERS entry says what it writes")
            continue
        if not found:
            undet_all.append(
                f"WRITERS claims {key[0]} ({key[1]}), but the scan found no write there — "
                f"the routine moved or was deleted; the claim is stale")
            continue
        if len(found) != spec["sites"]:
            undet_all.append(
                f"{key[0]} ({key[1]}) holds {len(found)} mapping_frame writes, not the "
                f"{spec['sites']} its WRITERS entry claims — a new write is unaccounted for")
            continue
        stale = []
        for ev in spec.get("evidence", ()):
            rx, why = ev[0], ev[1]
            where = ev[2] if len(ev) > 2 else key[0]
            if not re.search(rx, _read(where), re.M):
                stale.append(f"{where} no longer matches `{rx}` ({why})")
        if stale:
            undet_all.extend(f"{key[0]} ({key[1]}): {s}" for s in stale)
            continue
        if spec.get("ability"):
            owner = sole_ability_owner(bind, spec["ability"])
            expected = next((s["art_label"] for s in subs if s["name"] == spec["art"]), None)
            if owner is None or owner != expected:
                undet_all.append(
                    f"{key[0]} ({key[1]}) is routed to {spec['art']} because "
                    f"{spec['ability']} is that character's alone, but the roster now gives it "
                    f"to {owner or 'zero or several records'} — the state body is reachable for "
                    f"a different sheet than this claim says")
                continue
        for sub in subs:
            if applies(spec["art"], sub):
                sub.setdefault("_reach", set()).update(contribution(spec["frames"], sub))

    for line in check_anim_dplc_pairings():
        undet_all.append(f"MISMATCHED anim/DPLC binding — {line}")

    out = {}
    for s in subs:
        frames = s.pop("_reach", set())
        if undet_all:
            frames = set(range(len(s["frames"])))     # fail SAFE: widen, never narrow
        oob = sorted(f for f in frames if f >= len(s["frames"]))
        out[s["name"]] = {"frames": frames, "undetermined": list(undet_all),
                          "out_of_range": oob, "notes": notes}
    return out


# -------------------------------------------------------------------- subjects

#: (display name, art label, dplc label, .emp file, art const, dplc const, queue)
#  Queue is the one Perform_DPLC* variant its ONLY caller uses: the player
#  chardef path (games/sonic4/player/characters.emp:106) is Important; the
#  appendage rides the same player refresh.
SUBJECTS = [
    ("sonic",     "Art_Sonic",            "DPLC_Sonic",
     "games/sonic4/data/collision/collision_data.emp",   "_art_sonic", "_dplc_sonic",  "Important"),
    ("tails",     "Art_Tails",            "DPLC_Tails",
     "games/sonic4/data/characters/tails_data.emp",      "_art_tails", "_dplc_tails",  "Important"),
    ("tails_tail", "Art_TailsAppendage",  "DPLC_TailsAppendage",
     "games/sonic4/data/characters/tails_data.emp",      "_art_tail",  "_dplc_tail",   "Important"),
    ("knuckles",  "Art_Knuckles",         "DPLC_Knuckles",
     "games/sonic4/data/characters/knuckles_data.emp",   "_art_knux",  "_dplc_knux",   "Important"),
]


#: `pub data <Label> = <const>` in an `.emp`, with the right-hand side captured.
#: `check_subject_extents` needs the RHS: `+ art_len` is only the label's ROM
#: extent while the label binds the embed WHOLE, and a concatenation, a pad or a
#: slice all still spell `pub data <Label> = ...`.
_EMP_BINDING = re.compile(
    r'^[ \t]*pub[ \t]+data[ \t]+(?P<label>[A-Za-z_$][\w$.]*)[ \t]*'
    r'(?::[^=]*)?=[ \t]*(?P<rhs>.+?)[ \t]*(?://.*)?$', re.M)


def load_subjects(labels):
    subs = []
    for name, art_l, dplc_l, emp, art_c, dplc_c, queue in SUBJECTS:
        if art_l not in labels:
            raise Unmeasurable(f"{art_l} is not in the listing — wrong shape, or the label moved")
        if dplc_l not in labels:
            raise Unmeasurable(f"{dplc_l} is not in the listing — wrong shape, or the label moved")
        art_bytes = embed_path(emp, art_c).read_bytes()
        dplc_bytes = embed_path(emp, dplc_c).read_bytes()
        subs.append({
            "name": name, "art_label": art_l, "dplc_label": dplc_l, "queue": queue,
            "emp": emp, "art_const": art_c, "dplc_const": dplc_c,
            "art_base": labels[art_l], "art_len": len(art_bytes),
            "dplc_base": labels[dplc_l],
            "frames": parse_dplc(dplc_bytes, name), "dplc_len": len(dplc_bytes),
        })
    return subs


def check_subject_extents(subs, rom, rom_path):
    """ASSERT that each subject's ROM extent IS the file it embeds (sigil's F5).

    Every straddle verdict in this tool is a statement about ADDRESSES: an entry
    transfers `count * TILE_SIZE` bytes from `art_base + offset * TILE_SIZE`, and
    whether that crosses a 128 KB boundary is decided by where those bytes are.
    The region is `[art_base, art_base + art_len)` with `art_base` read from the
    listing and `art_len` taken as `len(<the file the .emp embeds>)` — a TERMINUS
    PROXY, the same shape as B7's F2 one layer over. Nothing checked the trade.

    WHAT GOING WRONG LOOKS LIKE, and why it is worse here than a wrong total: the
    verdict does not become obviously absurd, it moves. A pad ahead of the art
    inside its binding, a re-export that changed the blob without the label moving,
    a second thing bound into the same `data` — each shifts which frames are judged
    to cross, so frames that DO straddle are reported clean and frames that do not
    are reported dirty, and the gate's peak, its `--sweep`, and the re-cut model all
    read off the moved picture. There is no arithmetic error to notice.

    Two arms per subject, and the second is what makes `art_len` a MEASUREMENT
    rather than a restatement of `os.path.getsize`:

      (a) SOURCE SHAPE — `pub data <Art_Label> = <const>` must bind exactly the
          const the single `embed(...)` defines. Anything else (a concatenation, a
          pad, a slice) means the extent is not the file's length, in an unknown
          direction. The DPLC label is held to the same bar: `parse_dplc` walks the
          FILE and the frame offsets it yields are used against the ROM, so a DPLC
          label that is not exactly its blob desynchronises the frame table from
          the addresses it is describing.
      (b) IMAGE IDENTITY — the `art_len` bytes at `art_base` in the ROM must equal
          the embedded file byte for byte, and likewise for the DPLC. This is the
          arm that proves the LABEL POINTS AT THAT BLOB, at that address, for that
          length; without it the two halves of every straddle address come from
          two different artifacts that were never compared.

    Raises `Unmeasurable` naming the subject and the arm. Never a `--gate` verdict:
    a broken extent does not mean a frame is over budget, it means the straddle
    picture is about the wrong bytes, so no verdict should be trusted.
    """
    out = []
    for s in subs:
        text = _read(s["emp"])
        bindings = dict((m.group("label"), m.group("rhs"))
                        for m in _EMP_BINDING.finditer(text))
        if not bindings:
            raise Unmeasurable(
                f"{s['emp']} has no `pub data <Label> = ...` bindings under "
                f"{_EMP_BINDING.pattern!r} — the parser can no longer see what the "
                f"labels bind, so no extent can be established. Fix the parser.")
        for kind, label, const, base, length, blob in (
                ("art", s["art_label"], s["art_const"], s["art_base"], s["art_len"],
                 embed_path(s["emp"], s["art_const"])),
                ("DPLC", s["dplc_label"], s["dplc_const"], s["dplc_base"], s["dplc_len"],
                 embed_path(s["emp"], s["dplc_const"]))):
            # (a) source shape
            rhs = bindings.get(label)
            if rhs is None:
                raise Unmeasurable(
                    f"{s['name']}: {s['emp']} no longer carries `pub data {label} = ...`. "
                    f"The {kind} extent is derived from the embed that label binds; "
                    f"re-point this tool at whatever now defines it.")
            if rhs != const:
                raise Unmeasurable(
                    f"{s['name']}: `pub data {label} = {rhs}` no longer binds its embed "
                    f"WHOLE — expected exactly {const!r}, the const bound by the single "
                    f"`embed(...)`. A concatenation, a pad or a slice means {label}'s ROM "
                    f"extent is not {length} B, so every address this tool computes from "
                    f"it is off by an unknown amount and the straddle picture shifts. No "
                    f"verdict is reported.")
            # (b) image identity
            if base + length > len(rom):
                raise Unmeasurable(
                    f"{s['name']}: {rom_path} is {len(rom)} B and cannot hold {label}'s "
                    f"{length} B at 0x{base:X} — the image and the listing describe "
                    f"different builds.")
            want = blob.read_bytes()
            got = rom[base:base + length]
            if got != want:
                first = next(i for i in range(length) if got[i] != want[i])
                raise Unmeasurable(
                    f"{s['name']}: the {length} B at {label} 0x{base:X} in {rom_path} are "
                    f"NOT byte-identical to {blob.relative_to(AEON)} — they first differ "
                    f"{first} B in (0x{base + first:X}: ROM 0x{got[first]:02X} vs file "
                    f"0x{want[first]:02X}). `+ {length}` is then a restatement of the "
                    f"file's size and not a measurement of the ROM: the label, the length "
                    f"and the bytes come from artifacts that disagree, and every straddle "
                    f"address is computed from the pair. Rebuild, or find what moved.")
            out.append((s["name"], kind, label, base, length))
    return out


# --------------------------------------------------------------------- reports

def concurrent_demand(per_subject_split, n_players, n_appendage):
    """The worst straddle demand several RESIDENT sprite sets can make in one frame.

    A per-subject bound is not the one the reserve has to survive: two player
    slots plus Tails' appendage are drawn together, and each can land a
    straddling transfer in the same frame. Summing the N LARGEST per-subject
    splits is an upper bound over every residency combination without
    enumerating them, with N = one character per player slot plus the appendages
    that ride with them.

    Returns (n_resident, ranked_pairs, total).
    """
    n_resident = min(n_players + n_appendage, len(per_subject_split))
    ranked = sorted(per_subject_split.items(), key=lambda kv: (-kv[1], kv[0]))[:n_resident]
    return n_resident, ranked, sum(v for _, v in ranked)


# ------------------------------------------------------------------ the MARGIN
#
# THE QUANTITY THE TREE DEPENDS ON THAT NOTHING COMPUTED. Routed from sigil
# `ebd22729` (2026-09-05) §6 item 2: "the decaying dedup margin wants a monitor, not
# a note. The quantity is `packed_data_end`'s distance to the next forbidden band; it
# is computable by `dplc_straddle` today and nothing computes it."
#
# The three verdicts below all answer one question at ONE point: is the layout green
# where it stands. None of them answers HOW FAR IT CAN MOVE before it stops being
# green — and `Art_Sonic` is the terminus of the packed region, so every byte of data
# added anywhere below it moves that base. Sigil's measurement of the decay:
#
#     BLOCK-STREAM-DEDUP's slack above its safe band: 5,686 B -> 2,584 B in 7 days
#     the growth-direction margin:                   36,092 B -> 32,990 B in 7 days
#
# about 440 B/day of ordinary, unrelated data growth. A margin nobody measures is not
# a margin: the first thing that says it is gone is the build turning red, and by then
# the growth that consumed it belongs to somebody else's parcel.
#
# WHY A FULL PERIOD IS AN EXHAUSTIVE SEARCH. Whether an entry straddles depends only
# on `(art_base + shift)` relative to the multiples of `boundary`, so the verdict
# pattern is periodic in `shift` with period `boundary`. Scanning one whole period in
# each direction therefore either finds the nearest forbidden shift or proves there is
# none at any address — the second case is a real answer (three of the four subjects
# are in it: their ceiling `2 x peak_entries` cannot reach the bar), not a timeout.
#
# WHY BYTE GRANULARITY. A band can be narrower than a tile: sigil measured a 31 B
# VERDICT B band. A tile-granular scan would step over it and report a margin that is
# wrong in the flattering direction.
#
# REACHABILITY DOES NOT MOVE WITH THE BASE. Which frames the game can display is a
# property of the animation scripts and the `mapping_frame` writers, not of where the
# art landed, so the `reach` computed once at the real base is correct at every shift.
# (If that ever stops being true this is the comment that is wrong.)


def frame_split_ceiling(ents, tile_size, boundary):
    """The most entries of ONE frame that can straddle at once, over EVERY art base.

    EXACT, not a bound. Entry `(start, count)` straddles when a boundary falls strictly
    inside `(start*TS, (start+count)*TS)` measured from the art base; as the base moves,
    that interior position sweeps every offset, so the answer is the deepest overlap of
    those open intervals -- and a base can be chosen to realise it, which is what makes
    it exact rather than conservative.

    THE PLURAL-BOUNDARY TERM IS NOT AN OVERSIGHT. Boundaries recur every `boundary`
    bytes, and a subject's art is long enough that two of them can sit inside one
    frame's span at the same time, so depth is summed over `o + k*boundary` rather than
    read at a single point. Dropping that term would understate a ceiling, which is the
    flattering direction.
    """
    if not ents:
        return 0
    spans = [(s * tile_size, (s + c) * tile_size) for s, c in ents]
    hi = max(b for _a, b in spans)
    best = 0
    # Candidate offsets: every interval's open interior just past its left edge, taken
    # modulo the period. A deepest-overlap point always coincides with one of them.
    for a, _b in spans:
        o = (a + 1) % boundary
        depth = 0
        for k in range(0, hi // boundary + 2):
            x = o + k * boundary
            depth += sum(1 for lo, hiv in spans if lo < x < hiv)
        best = max(best, depth)
    return best


def subject_ceilings(sub, reach, tile_size, boundary):
    """The most this subject can EVER cost, at any art base. Derived, not swept.

        ceiling_slots  = max over ALL frames of (entries + frame_split_ceiling)
        ceiling_split  = max over REACHABLE frames of frame_split_ceiling

    This is sigil `ebd22729` §3's argument -- "three of the four subjects cannot fail
    VERDICT A at any base in the address space" -- turned from a sentence into a number
    the tool computes, which is what lets the margin scan SKIP a subject instead of
    spending a whole 0x20000-byte period proving it one shift at a time. §3 stated the
    ceiling as `2 x peak entries`, which is the bound you get by assuming every entry of
    the peak frame can straddle together; the overlap computation above is the exact
    form of the same quantity and is never larger.
    """
    rf = reach[sub["name"]]["frames"]
    slots, split = 0, 0
    for i, ents in enumerate(sub["frames"]):
        c = frame_split_ceiling(ents, tile_size, boundary)
        slots = max(slots, len(ents) + c)
        if i in rf:
            split = max(split, c)
    return slots, split


def _static_context(subs, reach, moving, tile_size, boundary):
    """Every subject EXCEPT `moving`, evaluated once at its real base.

    The margin scan moves one base at a time, so everything else is constant across
    the whole sweep; recomputing it per shift was the whole cost.
    """
    worst_all, splits = 0, {}
    for s in subs:
        if s["name"] == moving:
            continue
        costs = frame_costs(s["frames"], s["art_base"], tile_size, boundary)
        worst_all = max(worst_all, max((c[1] for c in costs), default=0))
        rf = reach[s["name"]]["frames"]
        splits[s["name"]] = max((len(costs[i][2]) for i in rf
                                 if i < len(s["frames"])), default=0)
    return worst_all, splits


def verdict_at(subs, reach, shifted, delta, tile_size, boundary,
               ratchet, reserve, n_players, n_appendage):
    """Which verdict (if any) fails when `shifted`'s art base moves by `delta`.

    Returns the failing verdict's letter ("A", "B" or "C"), or None. `shifted=None`
    evaluates the layout as linked. The reference implementation: `margin_for` hoists
    the unmoved subjects out of the loop but must agree with this, and a test pins that.
    """
    static_worst, splits = _static_context(subs, reach, shifted, tile_size, boundary)
    worst_all = static_worst
    for s in subs:
        if s["name"] != shifted:
            continue
        costs = frame_costs(s["frames"], s["art_base"] + delta, tile_size, boundary)
        worst_all = max(worst_all, max((c[1] for c in costs), default=0))
        rf = reach[s["name"]]["frames"]
        splits[s["name"]] = max((len(costs[i][2]) for i in rf
                                 if i < len(s["frames"])), default=0)
    return _verdict(worst_all, splits, ratchet, reserve, n_players, n_appendage)


def _verdict(worst_all, splits, ratchet, reserve, n_players, n_appendage):
    if worst_all > ratchet:
        return "A"
    if max(splits.values(), default=0) > reserve:
        return "B"
    if concurrent_demand(splits, n_players, n_appendage)[2] > reserve:
        return "C"
    return None


def margin_for(sub, subs, reach, tile_size, boundary, ratchet, reserve,
               n_players, n_appendage, origin=0, limit=None):
    """Distance from `origin` to the nearest forbidden art-base shift, both ways.

    {"up", "down": int|None, "up_verdict", "down_verdict": str|None,
     "structural": bool} -- `structural` is True when the subject's own ceilings prove
    no address can forbid it, in which case nothing was swept at all. A `None` distance
    with `structural` False means one whole period was searched and found nothing,
    which by the periodicity argument is the same answer arrived at the expensive way.
    """
    limit = boundary if limit is None else limit
    out = {"up": None, "down": None, "up_verdict": None, "down_verdict": None,
           "structural": False}
    ceil_slots, ceil_split = subject_ceilings(sub, reach, tile_size, boundary)
    static_worst, static_splits = _static_context(subs, reach, sub["name"],
                                                  tile_size, boundary)
    # Could a shift of THIS subject flip any verdict? A can only fire through this
    # subject's own cost (the others are constant and already green), B only through
    # its own reachable split, C only through the sum with this subject at its ceiling.
    probe = dict(static_splits)
    probe[sub["name"]] = ceil_split
    if (ceil_slots <= ratchet and ceil_split <= reserve
            and concurrent_demand(probe, n_players, n_appendage)[2] <= reserve):
        out["structural"] = True
        return out
    rf = reach[sub["name"]]["frames"]
    frames = sub["frames"]
    base = sub["art_base"]
    for sign, key in ((1, "up"), (-1, "down")):
        for d in range(1, limit + 1):
            costs = frame_costs(frames, base + origin + sign * d, tile_size, boundary)
            worst_all = max(static_worst, max((c[1] for c in costs), default=0))
            splits = dict(static_splits)
            splits[sub["name"]] = max((len(costs[i][2]) for i in rf
                                       if i < len(frames)), default=0)
            v = _verdict(worst_all, splits, ratchet, reserve, n_players, n_appendage)
            if v:
                out[key], out[key + "_verdict"] = d, v
                break
    return out


def report_margins(subs, reach, tile_size, boundary, ratchet, reserve,
                   n_players, n_appendage, origin=0, out=sys.stdout, floor=None):
    """Print each subject's margin and return the tightest finite one, or None.

    `floor` is compared against, never invented here: the caller passes the tree's
    OWN declared allowance for ordinary data growth so that "the straddle wall
    arrives before the growth the tree already budgets for" is a statement about two
    numbers the tree wrote down, not about a threshold this tool made up.
    """
    here = verdict_at(subs, reach, None, 0, tile_size, boundary, ratchet, reserve,
                      n_players, n_appendage)
    print(f"\n  MARGIN to the nearest forbidden art-base shift"
          f"{f' from {origin:+d} B' if origin else ''} "
          f"(one whole 0x{boundary:X} period each way, byte-granular; a subject whose "
          f"ceiling cannot reach the bar is answered from the ceiling and not swept)",
          file=out)
    if here:
        print(f"    ! the layout ITSELF fails VERDICT {here} at shift 0 — the margins "
              f"below are measured from a position that is already red", file=out)
    tightest = None
    for s in subs:
        m = margin_for(s, subs, reach, tile_size, boundary, ratchet, reserve,
                       n_players, n_appendage, origin=origin)
        cs, cr = subject_ceilings(s, reach, tile_size, boundary)
        # A BAR MET EXACTLY IS INDISTINGUISHABLE FROM A BAR MET WITH ROOM, right up
        # until it is not. Routed from sigil `ebd22729` §3: Knuckles' ceiling is
        # `2 x 5 = 10`, EQUAL to the bar, "and nothing in the tree states that as a
        # constraint". This line states it, on every build, from the tree's own numbers
        # rather than from a doc that would have to be remembered.
        headroom = ratchet - cs
        tag = ("  <-- CEILING EQUALS THE BAR: one more entry in this subject's worst "
               "frame makes it able to fail VERDICT A at some base" if headroom == 0
               else "")
        if m["structural"]:
            print(f"    {s['name']:<20} {s['art_label']} 0x{s['art_base']:X}   "
                  f"UNREACHABLE AT ANY BASE — slot ceiling {cs} vs bar {ratchet} "
                  f"(headroom {headroom}), reachable split ceiling {cr} vs reserve "
                  f"{reserve}{tag}", file=out)
            continue

        def fmt(k):
            d, v = m[k], m[k + "_verdict"]
            return "none in a whole period" if d is None else f"{d:,} B (VERDICT {v})"
        print(f"    {s['name']:<20} {s['art_label']} 0x{s['art_base']:X}   "
              f"grow +{fmt('up')}   shrink -{fmt('down')}   "
              f"[slot ceiling {cs} vs bar {ratchet}, headroom {headroom}; reachable "
              f"split ceiling {cr} vs reserve {reserve}]{tag}", file=out)
        for k in ("up", "down"):
            if m[k] is not None and (tightest is None or m[k] < tightest[1]):
                tightest = (s["name"], m[k], k, m[k + "_verdict"])
    if tightest is None:
        print("    tightest: NONE — no subject can be pushed into a forbidden band "
              "from here at any address", file=out)
        return None
    who, d, way, v = tightest
    print(f"    tightest: {who} can move {d:,} B "
          f"{'up (data growth below it)' if way == 'up' else 'down (a shrink below it)'} "
          f"before VERDICT {v} fires", file=out)
    if floor is not None and d < floor:
        # A WARNING AND NOT A FAILURE, deliberately: this state occurs on the shipped
        # tree today, so a refusal here would refuse a correct build. It becomes a
        # candidate for a hard gate only once the margin has demonstrably stopped
        # being under the floor.
        msg = (f"dplc_straddle: MARGIN WARNING — the nearest forbidden art-base shift is "
               f"{d:,} B away ({who}, {way}, VERDICT {v}), which is LESS than the "
               f"{floor:,} B this tree already budgets for ordinary data growth "
               f"(bganim_room.DATA_GROWTH_RESERVE). The straddle wall arrives before "
               f"the growth the bank-placement rule holds room for, so the first thing "
               f"that will say the margin is gone is a build turning red.")
        print(f"\n{msg}", file=out)
        print(msg, file=sys.stderr)
    return d


def growth_reserve():
    """The tree's declared allowance for ordinary data growth, read from its owner.

    `tools/bganim_room.py` is the module that computes the bank-placement rule and
    owns this constant; importing it is how the number stays single-sourced instead
    of becoming a second copy that drifts. Absent or unreadable -> None, and the
    floor comparison is simply not made (never a silent 0, which would compare true
    against every margin).
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import bganim_room
        return int(bganim_room.DATA_GROWTH_RESERVE)
    except Exception:
        return None


def default_rom_for(lst_path):
    """The ROM a listing came from. Not a guess the tool then trusts: rom_bytes
    fails loud if it is not there, and the caller may name it with --rom."""
    p = Path(lst_path)
    return str(p.with_suffix(".bin")) if p.suffix == ".lst" else str(p) + ".bin"


def rom_bytes(rom_path):
    p = Path(rom_path)
    if not p.exists():
        raise Unmeasurable(
            f"ROM {rom_path} does not exist — the reachable set is walked out of the BUILT "
            f"animation tables, so this gate needs the ROM its listing came from")
    return p.read_bytes()


def report(lst_path, out=sys.stdout, sweep=None, sweep_range=(-512, 512),
           recut_label=None, gate=False, rom_path=None, margin_at=None):
    tile_size = const_from_emp("engine/system/constants.emp", "TILE_SIZE")
    slots = const_from_emp("engine/system/constants.emp", "DMA_IMPORTANT_SLOTS")
    reserve = const_from_emp("engine/objects/dplc.emp", "DPLC_ENTRY_RESERVE")
    boundary = boundary_from_source()
    labels = lst_labels(lst_path)
    subs = load_subjects(labels)
    rom_path = rom_path or default_rom_for(lst_path)
    rom = rom_bytes(rom_path)
    # F5 — every straddle verdict below is a statement about ADDRESSES, and both
    # halves of every address (`art_base` from the listing, `art_len` from a file on
    # disk) were assumed to describe the same bytes. Checked before anything is
    # computed from them.
    extents = check_subject_extents(subs, rom, rom_path)
    reach = reachable_sets(subs, rom, labels)

    print(f"dplc_straddle [{lst_path}]", file=out)
    print(f"  extents: CHECKED — {len(extents)} label(s) "
          f"({', '.join(l for _n, _k, l, _b, _ln in extents)}) each bind their embed "
          f"whole and are byte-identical to it in {Path(rom_path).name}, so the "
          f"art/DPLC bases and lengths below are measured and not restated", file=out)
    print(f"  derived: TILE_SIZE={tile_size}  DMA_IMPORTANT_SLOTS={slots}  "
          f"DPLC_ENTRY_RESERVE={reserve}  DMA source boundary=0x{boundary:X}", file=out)
    print(f"  the wall the ratchet aims at: {slots} - {reserve} = {slots - reserve} slots", file=out)
    print(f"  reachability walked out of {rom_path}", file=out)
    # The derivations the reachable set rests on, said out loud: a reader who
    # doubts a frame's classification can check these before reading the code.
    for n in dict.fromkeys(reach[subs[0]["name"]]["notes"]):
        print(f"    derived: {n}", file=out)

    worst = 0
    worst_reach_slots = 0
    worst_reach_split = 0
    per_subject_split = {}
    undetermined = []
    for s in subs:
        end = s["art_base"] + s["art_len"]
        crossings = [b for b in range(boundary, end + boundary, boundary)
                     if s["art_base"] < b < end]
        costs = frame_costs(s["frames"], s["art_base"], tile_size, boundary)
        peak_e = max(c[0] for c in costs)
        peak_s = max(c[1] for c in costs)
        worst = max(worst, peak_s)
        at_e = [i for i, c in enumerate(costs) if c[0] == peak_e]
        at_s = [i for i, c in enumerate(costs) if c[1] == peak_s]
        n_str = sum(len(c[2]) for c in costs)
        f_str = [i for i, c in enumerate(costs) if c[2]]
        print(f"\n  {s['name']}: {s['art_label']} 0x{s['art_base']:X} + {s['art_len']} B "
              f"= 0x{end:X}   ({s['queue']} queue, {len(s['frames'])} frames)", file=out)
        print(f"    art spans {len(crossings)} boundary(ies): "
              f"{', '.join(f'0x{b:X}' for b in crossings) or 'none'}", file=out)
        print(f"    peak ENTRIES {peak_e} at frame(s) "
              f"{', '.join(f'${i:02X}' for i in at_e[:8])}"
              f"{' ...' if len(at_e) > 8 else ''}", file=out)
        print(f"    peak SLOTS   {peak_s} at frame(s) "
              f"{', '.join(f'${i:02X}' for i in at_s[:8])}"
              f"{' ...' if len(at_s) > 8 else ''}", file=out)
        print(f"    straddling entries: {n_str} across {len(f_str)} frame(s)"
              f"{': ' + ', '.join(f'${i:02X}' for i in f_str[:12]) if f_str else ''}", file=out)

        # --- the reachable / unreachable split ---------------------------
        r = reach[s["name"]]
        rf = r["frames"]
        if r["undetermined"]:
            undetermined.extend(r["undetermined"])
            print(f"    REACHABILITY UNDETERMINED — WIDENED to all {len(s['frames'])} frames "
                  f"(fail-safe: never narrowed). Reasons:", file=out)
            for why in dict.fromkeys(r["undetermined"]):
                print(f"      ! {why}", file=out)
        if r["out_of_range"]:
            print(f"    ! reachable frame(s) OUTSIDE this DPLC table "
                  f"({len(s['frames'])} entries): "
                  f"{', '.join(f'${i:02X}' for i in r['out_of_range'][:12])} — a writer names a "
                  f"frame this art does not have", file=out)
        in_range = sorted(f for f in rf if f < len(s["frames"]))
        r_str = [i for i in f_str if i in rf]
        u_str = [i for i in f_str if i not in rf]
        print(f"    reachable frames: {len(in_range)} of {len(s['frames'])} "
              f"(anim table {s.get('anim_label', '?')}, kind {s.get('kind', '?')})", file=out)
        print(f"    straddling REACHABLE:   {len(r_str)}"
              f"{': ' + ', '.join(f'${i:02X}' for i in r_str[:12]) if r_str else ' — none'}",
              file=out)
        print(f"    straddling unreachable: {len(u_str)}"
              f"{': ' + ', '.join(f'${i:02X}' for i in u_str[:12]) if u_str else ' — none'}",
              file=out)
        if in_range:
            r_peak = max(costs[i][1] for i in in_range)
            r_at = [i for i in in_range if costs[i][1] == r_peak]
            r_split = max(len(costs[i][2]) for i in in_range)
            worst_reach_slots = max(worst_reach_slots, r_peak)
            worst_reach_split = max(worst_reach_split, r_split)
            per_subject_split[s["name"]] = r_split
            print(f"    peak SLOTS over REACHABLE frames: {r_peak} at "
                  f"{', '.join(f'${i:02X}' for i in r_at[:8])}"
                  f"{' ...' if len(r_at) > 8 else ''}   "
                  f"(worst reachable frame splits into {r_split} extra entry(ies))", file=out)
        else:
            per_subject_split[s["name"]] = 0
            print(f"    peak SLOTS over REACHABLE frames: n/a — no frame of this art is "
                  f"reachable at all", file=out)

    # --- the CONCURRENT demand on the reserve ----------------------------
    #
    # Everything above is per-subject, and a per-subject bound is not the one
    # the reserve has to survive. Several sprite sets are resident at once — two
    # player slots plus Tails' appendage — and each can land a straddling
    # transfer in the SAME frame. The 2026-09-03 emulator reading measured a
    # per-frame straddle peak of exactly 1 and named this as the bound that
    # breaks: "it would break the moment an art-base move gives Sonic a
    # reachable straddling frame, and then two straddling landings in one frame
    # would need four slots against a reserve of two."
    #
    # So: sum the worst reachable split of the N subjects that can be resident
    # together, N = NUM_PLAYERS (one character per slot) + the appendage
    # subjects that ride with them, read from the engine constant rather than
    # typed. Summing the N LARGEST is an upper bound over every residency
    # combination without enumerating them.
    n_players = const_from_emp("engine/system/constants.emp", "NUM_PLAYERS")
    n_appendage = sum(1 for s in subs if s.get("kind") == "appendage")
    n_resident, ranked, concurrent = concurrent_demand(
        per_subject_split, n_players, n_appendage)
    print(f"\n  CONCURRENT demand on the reserve: {n_resident} sprite set(s) resident at once "
          f"(NUM_PLAYERS={n_players} + {n_appendage} appendage), worst case "
          f"{' + '.join(f'{k} {v}' for k, v in ranked)} = {concurrent} split(s) "
          f"against a {reserve}-slot reserve", file=out)

    if sweep:
        s = next((x for x in subs if x["art_label"] == sweep), None)
        if s is None:
            raise Unmeasurable(f"--sweep {sweep} names no subject; "
                               f"known: {', '.join(x['art_label'] for x in subs)}")
        lo, hi = sweep_range
        print(f"\n  SWEEP {sweep}: art base shifted over [{lo}, {hi}] B "
              f"(the neighbourhood an append/shrink moves it through)", file=out)
        srf = reach[s["name"]]["frames"]
        seen = {}
        for d in range(lo, hi + 1):
            costs = frame_costs(s["frames"], s["art_base"] + d, tile_size, boundary)
            key = (max(c[0] for c in costs), max(c[1] for c in costs),
                   sum(len(c[2]) for c in costs),
                   sum(len(c[2]) for i, c in enumerate(costs) if i in srf))
            seen.setdefault(key, []).append(d)
        for (pe, ps, ns, nr), ds in sorted(seen.items()):
            runs, start, prev = [], ds[0], ds[0]
            for d in ds[1:]:
                if d != prev + 1:
                    runs.append((start, prev))
                    start = d
                prev = d
            runs.append((start, prev))
            span = ', '.join(f"{a}" if a == b else f"{a}..{b}" for a, b in runs[:6])
            print(f"    peak entries {pe}  peak SLOTS {ps}  straddling entries {ns} "
                  f"(REACHABLE {nr})   "
                  f"at shift {span}{' ...' if len(runs) > 6 else ''}  "
                  f"({len(ds)} of {hi - lo + 1} shifts)", file=out)

    # THE MARGIN — how far the layout can move before a verdict fires. Printed on
    # EVERY run, gated or not, because the point of it is that the number exists in
    # the build log on the day the growth happens rather than being re-derived by
    # whoever is standing there when the build turns red. See the MARGIN banner.
    ratchet_for_margin, _prov = ratchet_from_source(slots, reserve)
    report_margins(subs, reach, tile_size, boundary, ratchet_for_margin, reserve,
                   n_players, n_appendage, origin=margin_at or 0, out=out,
                   floor=growth_reserve())

    if recut_label:
        s = next((x for x in subs if x["art_label"] == recut_label), None)
        if s is None:
            raise Unmeasurable(f"--recut {recut_label} names no subject; "
                               f"known: {', '.join(x['art_label'] for x in subs)}")
        report_recut(s, slots - reserve, tile_size, boundary, slots, reserve, out=out)

    ratchet, provenance = ratchet_from_source(slots, reserve)
    print(f"\n  worst peak SLOT cost over all subjects: {worst}", file=out)
    print(f"  the committed bar is {ratchet} — from {provenance}", file=out)
    print(f"  worst peak SLOT cost over REACHABLE frames: {worst_reach_slots}", file=out)
    print(f"  worst REACHABLE frame split: {worst_reach_split} extra entry(ies) against a "
          f"{reserve}-slot DPLC_ENTRY_RESERVE", file=out)
    if undetermined:
        # Loud on both streams: a widened set is a fail-safe, not an answer, and a
        # build log scrolls past stdout.
        print(f"\ndplc_straddle: REACHABILITY WIDENED — {len(set(undetermined))} writer(s) could "
              f"not be classified, so their subjects were widened to ALL frames. The reachable "
              f"columns above are an UPPER BOUND, never a narrowed set.", file=out)
        for why in dict.fromkeys(undetermined):
            print(f"  ! {why}", file=sys.stderr)
    if gate:
        failed = False
        # VERDICT A — UNCHANGED: the worst peak SLOT cost over ALL frames, with
        # the same predicate, the same message and the same exit code it has
        # always had.
        if worst > ratchet:
            print(f"\ndplc_straddle: FAIL — peak SLOT cost {worst} exceeds the committed "
                  f"entry bar {ratchet}. A frame costs more queue slots than its "
                  f"entry count, because at least one of its transfers straddles a "
                  f"0x{boundary:X} source boundary and QueueDMA splits it in two.",
                  file=out)
            failed = True
        # VERDICT B — driven by the REACHABLE set, and NOT implied by A.
        #
        # Note what is deliberately absent: there is no "a reachable frame is
        # over the bar" check, because A already forbids ANY frame being over it
        # and slot_cost already includes the splits — such a check could never
        # fire on its own and would be a gate that only looks like one.
        #
        # What A cannot see is the SHAPE of the cost. A frame can sit well under
        # the bar and still need more than the reserved slots at once: a DPLC
        # frame may name the same tile several times (Sonic's $1E lists tile 165
        # seven times), and every one of those entries straddles together when
        # the boundary falls inside that tile. QueueDMA rejects a split outright
        # when only one slot is free (dma_queue.emp `.split_reject`), so the bar
        # for a single frame's splits is DPLC_ENTRY_RESERVE — read from its own
        # defining file, never pinned here. This is the check a 21 KB art-base
        # move walks into, and it is why the reachable half exists.
        if worst_reach_split > reserve:
            print(f"\ndplc_straddle: FAIL — a REACHABLE frame splits into {worst_reach_split} "
                  f"extra queue entries at once, more than the {reserve}-slot "
                  f"DPLC_ENTRY_RESERVE held open for exactly those splits. QueueDMA rejects "
                  f"the whole transfer when only one slot is free (dma_queue.emp "
                  f".split_reject), so this frame's art would not load — and it is a frame the "
                  f"game can display.", file=out)
            failed = True
        # VERDICT C — the CONCURRENT demand, the bound the 2026-09-03 reading
        # named as the one that breaks. Also not implied by A: every resident set
        # can be comfortably under the slot bar on its own and still overrun the
        # reserve between them in one frame.
        if concurrent > reserve:
            print(f"\ndplc_straddle: FAIL — {n_resident} sprite sets are resident at once and "
                  f"their REACHABLE straddles total {concurrent} in one frame, past the "
                  f"{reserve}-slot DPLC_ENTRY_RESERVE. Each straddling landing needs two free "
                  f"slots and .split_reject drops the whole transfer when only one is free, so "
                  f"one of these sets would lose its art. Contributors: "
                  f"{', '.join(f'{k} {v}' for k, v in ranked if v)}.", file=out)
            failed = True
        if failed:
            return 1
        print(f"\ndplc_straddle: OK — no frame's SLOT cost exceeds the bar {ratchet}, no "
              f"REACHABLE frame splits past the {reserve}-slot reserve, and the concurrent "
              f"reachable demand is {concurrent} of {reserve} "
              f"(worst reachable peak {worst_reach_slots} slots, worst reachable split "
              f"{worst_reach_split})", file=out)
    return 0


def recut(sub, wall, tile_size, max_tiles_per_entry=16):
    """Model the d-47 `targeted` re-cut on a subject, from the tree's own data.

    Every frame whose entry count exceeds `wall` has its tiles APPENDED to the
    end of the art blob as one contiguous run and its DPLC frame rewritten as
    that run, split into <= 16-tile entries (the 4-bit count field's cap, as
    `tools/dplc_layout.py` splits it). Nothing else is touched.

    Returns (new_frames, art_growth_bytes, dplc_delta_bytes, rewritten_frames).
    The DPLC delta is DERIVED — two bytes per entry word removed or added, the
    frame-offset table keeping its size because the frame count does not change.
    """
    frames = [list(e) for e in sub["frames"]]
    cursor = sub["art_len"] // tile_size          # first appended tile index
    grew, entry_words, rewritten = 0, 0, []
    for fi, ents in enumerate(frames):
        if len(ents) <= wall:
            continue
        tiles = sum(c for _, c in ents)
        new = []
        start, left = cursor, tiles
        while left > 0:
            chunk = min(left, max_tiles_per_entry)
            new.append((start, chunk))
            start += chunk
            left -= chunk
        entry_words += len(new) - len(ents)
        cursor += tiles
        grew += tiles * tile_size
        frames[fi] = new
        rewritten.append(fi)
    return frames, grew, entry_words * 2, rewritten


def report_recut(sub, wall, tile_size, boundary, slots, reserve, out=sys.stdout):
    frames, grew, dplc_delta, rewritten = recut(sub, wall, tile_size)
    # The art blob's base moves by the DPLC blob's size change, because
    # DPLC_Sonic and Art_Sonic are adjacent `pub data` in one section and the
    # DPLC comes first (games/sonic4/data/collision/collision_data.emp).
    new_base = sub["art_base"] + dplc_delta
    new_len = sub["art_len"] + grew

    before = frame_costs(sub["frames"], sub["art_base"], tile_size, boundary)
    after = frame_costs(frames, new_base, tile_size, boundary)

    print(f"\n  RE-CUT MODEL for {sub['name']} (d-47 `targeted`, wall = {wall} entries)", file=out)
    print(f"    frames rewritten: {len(rewritten)} — "
          f"{', '.join(f'${i:02X}' for i in rewritten)}", file=out)
    print(f"    entries in them: {sum(len(sub['frames'][i]) for i in rewritten)} -> "
          f"{sum(len(frames[i]) for i in rewritten)}", file=out)
    print(f"    art  {sub['art_len']} B -> {new_len} B  (+{grew})", file=out)
    print(f"    dplc {sub['dplc_len']} B -> {sub['dplc_len'] + dplc_delta} B  ({dplc_delta:+})", file=out)
    print(f"    art base 0x{sub['art_base']:X} -> 0x{new_base:X}  ({dplc_delta:+} B, "
          f"the DPLC shrink ahead of it), end 0x{sub['art_base'] + sub['art_len']:X} "
          f"-> 0x{new_base + new_len:X}", file=out)

    pe_b, ps_b = max(c[0] for c in before), max(c[1] for c in before)
    pe_a, ps_a = max(c[0] for c in after), max(c[1] for c in after)
    print(f"    peak ENTRIES {pe_b} -> {pe_a}", file=out)
    print(f"    peak SLOTS   {ps_b} -> {ps_a}   (the wall is "
          f"{slots} - {reserve} = {slots - reserve})", file=out)

    str_b = {i for i, c in enumerate(before) if c[2]}
    str_a = {i for i, c in enumerate(after) if c[2]}
    print(f"    straddling frames before: "
          f"{', '.join(f'${i:02X}' for i in sorted(str_b)) or 'none'}", file=out)
    print(f"    straddling frames after:  "
          f"{', '.join(f'${i:02X}' for i in sorted(str_a)) or 'none'}", file=out)
    gained, lost = sorted(str_a - str_b), sorted(str_b - str_a)
    print(f"    DISTURBED: {len(gained)} frame(s) gained a straddle "
          f"({', '.join(f'${i:02X}' for i in gained) or 'none'}), "
          f"{len(lost)} lost one ({', '.join(f'${i:02X}' for i in lost) or 'none'})", file=out)
    worse = [(i, before[i][1], after[i][1]) for i in range(len(after))
             if after[i][1] > before[i][1]]
    print(f"    frames whose SLOT cost went UP: {len(worse)}"
          f"{'  ' + ', '.join(f'${i:02X} {b}->{a}' for i, b, a in worse[:8]) if worse else ''}",
          file=out)
    return ps_a


def ratchet_from_source(slots, reserve):
    """The bar this gate compares peak SLOT cost against, READ OUT OF THE SOURCE.

    Two spellings are legal in collision_data.emp and they mean different things,
    so this returns which one it found rather than just a number:

      * the REAL budget assert —
        `ensure(dplc_peak_entries(_dplc_sonic) + DPLC_ENTRY_RESERVE <= DMA_IMPORTANT_SLOTS)`
        — the wall is then `slots - reserve`, DERIVED from the two constants
        parsed out of their own defining files, never typed here. This is what
        ships since the d-47 re-cut.
      * a literal RATCHET `... <= N`, which is what stood while the sheet was over
        budget. Its N is the bar, because a ratchet's whole job is to pin a debt.

    Neither present is UNMEASURABLE, not a default: with no committed wall in
    source there is no number for this gate to mean anything against.

    Returns (bar, provenance_string).
    """
    text = _read("games/sonic4/data/collision/collision_data.emp")
    real = re.search(
        r'ensure\(dplc_peak_entries\(_dplc_sonic\)\s*\+\s*DPLC_ENTRY_RESERVE'
        r'\s*<=\s*DMA_IMPORTANT_SLOTS', text)
    if real:
        return (slots - reserve,
                f"the real budget assert in collision_data.emp, so the bar is "
                f"DMA_IMPORTANT_SLOTS - DPLC_ENTRY_RESERVE = {slots} - {reserve}")
    ratchet = re.search(r'ensure\(dplc_peak_entries\(_dplc_sonic\)\s*<=\s*(\d+)', text)
    if ratchet:
        n = int(ratchet.group(1))
        return (n, f"a literal ratchet `<= {n}` in collision_data.emp — the sheet is "
                   f"over budget and this pins the debt")
    raise Unmeasurable(
        "collision_data.emp carries NEITHER the real "
        "`dplc_peak_entries(_dplc_sonic) + DPLC_ENTRY_RESERVE <= DMA_IMPORTANT_SLOTS` "
        "assert NOR a literal `<= N` ratchet — the number this gate compares against "
        "is gone; re-derive it")


def selftest(lst_path, out=sys.stdout, rom_path=None):
    """RED-FIRST proof that the gate can fail, run against this build.

    A gate that has never been observed red is a gate nobody has tested. This
    drives the same `--gate` predicates through six states:

      1. the real placement                -> must be GREEN
      2. an art base shifted onto a straddle that lands on a peak frame
         -> must be RED. The failing shift is SEARCHED FOR at run time, not
         written down here, so it stays correct as the art changes; if no
         failing shift exists within the search window the self-test FAILS
         LOUD rather than passing vacuously.
      3. a corrupted derived constant      -> must be UNMEASURABLE, not 0
      4. the reachable set must be a PROPER, NON-EMPTY subset of the frames for
         at least one subject — a set that is everything, or nothing, cannot
         tell reachable from unreachable and its split is decoration.
      5. an art base shifted so a straddle lands on a REACHABLE frame -> the
         reachable straddle count must MOVE. Searched for, not written down; if
         no such shift exists the split cannot respond to a base move at all,
         which is the exact failure BLOCK-STREAM-DEDUP would walk into.
      6. an unclaimed writer must WIDEN, not narrow: a synthetic undetermined
         reason has to produce the full frame set.

    Nothing here is a hardcoded expectation copied from a previous run.
    """
    tile_size = const_from_emp("engine/system/constants.emp", "TILE_SIZE")
    slots = const_from_emp("engine/system/constants.emp", "DMA_IMPORTANT_SLOTS")
    reserve = const_from_emp("engine/objects/dplc.emp", "DPLC_ENTRY_RESERVE")
    boundary = boundary_from_source()
    ratchet, provenance = ratchet_from_source(slots, reserve)
    labels = lst_labels(lst_path)
    subs = load_subjects(labels)
    rom_path = rom_path or default_rom_for(lst_path)
    reach = reachable_sets(subs, rom_bytes(rom_path), labels)
    fails = []
    print(f"  [0] the bar is {ratchet} — from {provenance}", file=out)

    def peak_slots(sub, shift, frames=None):
        c = frame_costs(frames or sub["frames"], sub["art_base"] + shift, tile_size, boundary)
        return max(x[1] for x in c)

    # (1) green at the real placement
    worst = max(peak_slots(s, 0) for s in subs)
    print(f"  [1] real placement: worst peak SLOT cost {worst} vs ratchet {ratchet}", file=out)
    if worst > ratchet:
        fails.append(f"the real placement is already over the ratchet ({worst} > {ratchet})")

    # (2) red at a searched-for failing shift
    s = next(x for x in subs if x["name"] == "sonic")
    found = None
    for d in range(1, 1 << 17):
        for sign in (1, -1):
            if peak_slots(s, sign * d) > ratchet:
                found = sign * d
                break
        if found is not None:
            break
    if found is None:
        fails.append("no art-base shift within +/-128 KB makes the gate red — the gate "
                     "cannot be proven red on this data, so its green means nothing")
        print("  [2] RED PROOF: NONE FOUND — see failure below", file=out)
    else:
        got = peak_slots(s, found)
        print(f"  [2] red proof: shifting Art_Sonic by {found:+d} B gives peak SLOT cost "
              f"{got} > ratchet {ratchet} — the gate fires", file=out)
        if got <= ratchet:
            fails.append("the searched shift did not actually exceed the ratchet")

    # (3) loud, not zero, on a broken derivation
    try:
        const_from_emp("engine/system/constants.emp", "A_CONSTANT_THAT_DOES_NOT_EXIST")
        fails.append("a missing constant returned a value instead of raising Unmeasurable")
        print("  [3] UNMEASURABLE PROOF: did not raise — see failure below", file=out)
    except Unmeasurable:
        print("  [3] unmeasurable proof: a missing derived constant raises rather than "
              "reporting 0", file=out)

    # (4) the split has to actually split something
    discriminating = []
    for x in subs:
        rf = reach[x["name"]]["frames"]
        n, total = len(rf), len(x["frames"])
        if reach[x["name"]]["undetermined"]:
            continue
        if 0 < n < total:
            discriminating.append(f"{x['name']} {n}/{total}")
    print(f"  [4] discriminating subjects (reachable is a proper non-empty subset): "
          f"{', '.join(discriminating) or 'NONE'}", file=out)
    if not discriminating:
        fails.append("no subject has a reachable set that is both non-empty and smaller than "
                     "its whole table — the reachable/unreachable split distinguishes nothing")

    # (5) a base shift must be able to move the REACHABLE straddle count
    def reach_straddles(sub, shift):
        rf = reach[sub["name"]]["frames"]
        c = frame_costs(sub["frames"], sub["art_base"] + shift, tile_size, boundary)
        return sum(len(x[2]) for i, x in enumerate(c) if i in rf)

    moved = None
    for x in subs:
        if reach[x["name"]]["undetermined"]:
            continue
        base_n = reach_straddles(x, 0)
        for d in range(1, 1 << 17):
            for sign in (1, -1):
                if reach_straddles(x, sign * d) != base_n:
                    moved = (x["name"], sign * d, base_n, reach_straddles(x, sign * d))
                    break
            if moved:
                break
        if moved:
            break
    if moved is None:
        fails.append("no art-base shift within +/-128 KB changes any subject's REACHABLE "
                     "straddle count — the split cannot respond to a base move, which is the "
                     "one thing it exists to catch")
        print("  [5] REACHABLE-STRADDLE MOVE: NONE FOUND — see failure below", file=out)
    else:
        who, d, was, now = moved
        print(f"  [5] reachable-straddle move: shifting {who}'s art base by {d:+d} B takes its "
              f"REACHABLE straddling entries {was} -> {now}", file=out)

    # (5b) VERDICT B must be provably red on this data, or its green means
    # nothing. Searched at tile granularity over a whole boundary period, which
    # covers every distinct placement the art can have.
    def reach_split(sub, shift):
        rf = reach[sub["name"]]["frames"]
        c = frame_costs(sub["frames"], sub["art_base"] + shift, tile_size, boundary)
        return max((len(x[2]) for i, x in enumerate(c) if i in rf), default=0)

    over = None
    for x in subs:
        if reach[x["name"]]["undetermined"]:
            continue
        for d in range(0, boundary, tile_size):
            if reach_split(x, d) > reserve:
                over = (x["name"], d, reach_split(x, d))
                break
        if over:
            break
    if over is None:
        fails.append(f"no placement in a whole {boundary:#x}-byte period makes any REACHABLE "
                     f"frame split past the {reserve}-slot reserve — VERDICT B cannot be shown "
                     f"red on this data, so its green is decoration")
        print("  [5b] VERDICT B RED PROOF: NONE FOUND — see failure below", file=out)
    else:
        who, d, n = over
        print(f"  [5b] verdict B red proof: shifting {who}'s art base by {d:+d} B makes a "
              f"REACHABLE frame split into {n} entries at once, past the {reserve}-slot "
              f"reserve — the gate fires", file=out)

    # (6) an undetermined writer widens; it must never narrow
    probe = [dict(x) for x in subs]
    for x in probe:
        x["frames"] = list(x["frames"])
    saved = dict(WRITERS)
    try:
        WRITERS.pop(("engine/objects/animate.emp", "AnimateSprite"), None)
        WRITERS[("engine/objects/animate.emp", "AnimateSprite_NOT_A_ROUTINE")] = dict(
            sites=1, art="any", frames="none", why="selftest probe")
        widened = reachable_sets(probe, rom_bytes(rom_path), labels)
    finally:
        WRITERS.clear()
        WRITERS.update(saved)
    bad = [x["name"] for x in probe
           if not widened[x["name"]]["undetermined"]
           or widened[x["name"]]["frames"] != set(range(len(x["frames"])))]
    print(f"  [6] fail-safe widening: an unclaimed writer widened "
          f"{len(probe) - len(bad)}/{len(probe)} subjects to their whole table", file=out)
    if bad:
        fails.append(f"an unclaimed writer did NOT widen {', '.join(bad)} — an unclassified "
                     f"write site would silently narrow the reachable set")

    print(f"\n  derived this run: TILE_SIZE={tile_size} DMA_IMPORTANT_SLOTS={slots} "
          f"DPLC_ENTRY_RESERVE={reserve} boundary=0x{boundary:X} ratchet={ratchet}", file=out)
    if fails:
        for f in fails:
            print(f"dplc_straddle selftest: FAIL — {f}", file=out)
        return 1
    print("dplc_straddle selftest: OK — the gate is green here and provably red elsewhere",
          file=out)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--rom", help="the ROM the listing came from (default: --lst with .lst -> .bin)")
    ap.add_argument("--sweep", help="art label to sweep the base address of")
    ap.add_argument("--recut", help="art label to model the d-47 `targeted` re-cut on")
    ap.add_argument("--range", default="-512:512", help="sweep range LO:HI in bytes")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--margin-at", type=int, default=0, metavar="SHIFT",
                    help="measure the margin from this art-base shift instead of the "
                         "linked base -- e.g. --margin-at -20986 prices "
                         "BLOCK-STREAM-DEDUP's approved move before it is made")
    ap.add_argument("--selftest", action="store_true",
                    help="prove the gate red-first against this build, then restore")
    a = ap.parse_args(argv)
    lo, hi = (int(x) for x in a.range.split(":"))
    try:
        if a.selftest:
            print(f"dplc_straddle selftest [{a.lst}]")
            return selftest(a.lst, rom_path=a.rom)
        return report(a.lst, sweep=a.sweep, sweep_range=(lo, hi),
                      recut_label=a.recut, gate=a.gate, rom_path=a.rom,
                      margin_at=a.margin_at)
    except Unmeasurable as e:
        print(f"dplc_straddle: UNMEASURABLE — {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
