#!/usr/bin/env python3
"""dplc_straddle — measure the Important-queue SLOT cost of a DPLC frame, and how
it moves when character art is APPENDED to or SHIFTED in the ROM.

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
                                                          # the ratchet
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
            "art_base": labels[art_l], "art_len": len(art_bytes),
            "frames": parse_dplc(dplc_bytes, name), "dplc_len": len(dplc_bytes),
        })
    return subs


# --------------------------------------------------------------------- reports

def report(lst_path, out=sys.stdout, sweep=None, sweep_range=(-512, 512),
           recut_label=None, gate=False):
    tile_size = const_from_emp("engine/system/constants.emp", "TILE_SIZE")
    slots = const_from_emp("engine/system/constants.emp", "DMA_IMPORTANT_SLOTS")
    reserve = const_from_emp("engine/objects/dplc.emp", "DPLC_ENTRY_RESERVE")
    boundary = boundary_from_source()
    labels = lst_labels(lst_path)
    subs = load_subjects(labels)

    print(f"dplc_straddle [{lst_path}]", file=out)
    print(f"  derived: TILE_SIZE={tile_size}  DMA_IMPORTANT_SLOTS={slots}  "
          f"DPLC_ENTRY_RESERVE={reserve}  DMA source boundary=0x{boundary:X}", file=out)
    print(f"  the wall the ratchet aims at: {slots} - {reserve} = {slots - reserve} slots", file=out)

    worst = 0
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

    if sweep:
        s = next((x for x in subs if x["art_label"] == sweep), None)
        if s is None:
            raise Unmeasurable(f"--sweep {sweep} names no subject; "
                               f"known: {', '.join(x['art_label'] for x in subs)}")
        lo, hi = sweep_range
        print(f"\n  SWEEP {sweep}: art base shifted over [{lo}, {hi}] B "
              f"(the neighbourhood an append/shrink moves it through)", file=out)
        seen = {}
        for d in range(lo, hi + 1):
            costs = frame_costs(s["frames"], s["art_base"] + d, tile_size, boundary)
            key = (max(c[0] for c in costs), max(c[1] for c in costs),
                   sum(len(c[2]) for c in costs))
            seen.setdefault(key, []).append(d)
        for (pe, ps, ns), ds in sorted(seen.items()):
            runs, start, prev = [], ds[0], ds[0]
            for d in ds[1:]:
                if d != prev + 1:
                    runs.append((start, prev))
                    start = d
                prev = d
            runs.append((start, prev))
            span = ', '.join(f"{a}" if a == b else f"{a}..{b}" for a, b in runs[:6])
            print(f"    peak entries {pe}  peak SLOTS {ps}  straddling entries {ns}   "
                  f"at shift {span}{' ...' if len(runs) > 6 else ''}  "
                  f"({len(ds)} of {hi - lo + 1} shifts)", file=out)

    if recut_label:
        s = next((x for x in subs if x["art_label"] == recut_label), None)
        if s is None:
            raise Unmeasurable(f"--recut {recut_label} names no subject; "
                               f"known: {', '.join(x['art_label'] for x in subs)}")
        report_recut(s, slots - reserve, tile_size, boundary, slots, reserve, out=out)

    ratchet = ratchet_from_source()
    print(f"\n  worst peak SLOT cost over all subjects: {worst}", file=out)
    print(f"  the committed entry ratchet (collision_data.emp) is {ratchet}", file=out)
    if gate:
        if worst > ratchet:
            print(f"\ndplc_straddle: FAIL — peak SLOT cost {worst} exceeds the committed "
                  f"entry ratchet {ratchet}. A frame costs more queue slots than its "
                  f"entry count, because at least one of its transfers straddles a "
                  f"0x{boundary:X} source boundary and QueueDMA splits it in two.",
                  file=out)
            return 1
        print("\ndplc_straddle: OK — no frame's SLOT cost exceeds its entry ratchet", file=out)
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


def ratchet_from_source():
    """The committed `dplc_peak_entries(_dplc_sonic) <= N` ratchet."""
    text = _read("games/sonic4/data/collision/collision_data.emp")
    m = re.search(r'ensure\(dplc_peak_entries\(_dplc_sonic\)\s*<=\s*(\d+)', text)
    if not m:
        raise Unmeasurable(
            "collision_data.emp no longer carries the `dplc_peak_entries(_dplc_sonic) <= N` "
            "ratchet — the number this gate compares against is gone; re-derive it")
    return int(m.group(1))


def selftest(lst_path, out=sys.stdout):
    """RED-FIRST proof that the gate can fail, run against this build.

    A gate that has never been observed red is a gate nobody has tested. This
    drives the same `--gate` predicate through three states:

      1. the real placement                -> must be GREEN
      2. an art base shifted onto a straddle that lands on a peak frame
         -> must be RED. The failing shift is SEARCHED FOR at run time, not
         written down here, so it stays correct as the art changes; if no
         failing shift exists within the search window the self-test FAILS
         LOUD rather than passing vacuously.
      3. a corrupted derived constant      -> must be UNMEASURABLE, not 0

    Nothing here is a hardcoded expectation copied from a previous run.
    """
    tile_size = const_from_emp("engine/system/constants.emp", "TILE_SIZE")
    slots = const_from_emp("engine/system/constants.emp", "DMA_IMPORTANT_SLOTS")
    reserve = const_from_emp("engine/objects/dplc.emp", "DPLC_ENTRY_RESERVE")
    boundary = boundary_from_source()
    ratchet = ratchet_from_source()
    labels = lst_labels(lst_path)
    subs = load_subjects(labels)
    fails = []

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
    ap.add_argument("--sweep", help="art label to sweep the base address of")
    ap.add_argument("--recut", help="art label to model the d-47 `targeted` re-cut on")
    ap.add_argument("--range", default="-512:512", help="sweep range LO:HI in bytes")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--selftest", action="store_true",
                    help="prove the gate red-first against this build, then restore")
    a = ap.parse_args(argv)
    lo, hi = (int(x) for x in a.range.split(":"))
    try:
        if a.selftest:
            print(f"dplc_straddle selftest [{a.lst}]")
            return selftest(a.lst)
        return report(a.lst, sweep=a.sweep, sweep_range=(lo, hi),
                      recut_label=a.recut, gate=a.gate)
    except Unmeasurable as e:
        print(f"dplc_straddle: UNMEASURABLE — {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
