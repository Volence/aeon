#!/usr/bin/env python3
"""Derive how much room the `ojz_bg_anim` section actually has — from INSTRUMENTS.

WHY THIS FILE EXISTS, AND THE BAR IT ENFORCES
---------------------------------------------
Three parties in one afternoon (2026-08-24) read a gap between two rows of sigil's
frozen boundary table (`crates/sigil-harness/golden/offcanonical_sizes/s4*.txt`) as
free space, and re-derived arithmetic on top of it — which looked like corroboration
and was propagation. The gap held `AngleTable`, `SolidityTable`, `Map_Sonic`,
`DPLC_Sonic` and `Art_Sonic`.

**A gap between two rows of that table is an ALLOTMENT, never proven free space.**
The table lists a SUBSET of labels, so content between two listed labels is invisible
in it by construction. The only instruments that can answer occupancy are the sigil
`.lst` symbol listing and a scan of the ROM image. This module reads exactly those,
plus `games/sonic4/map.toml` for the hardware anchor, and NOTHING else. See
`docs/OVERSEER.md` (the repo bar) and decisions d-8 / d-9.

THE TWO INDEPENDENT LIMITS ON THE SECTION'S SIZE
------------------------------------------------
They are different questions with different answers, and conflating them is what
produced the retracted numbers:

  1. ROM ROOM — physical bytes between the end of the last packed data blob
     (`Art_Sonic`) and the `dac_banks` hardware anchor at $48000 (a Z80 `SetBank`
     latch; `map.toml`'s `[[anchor]]`, it cannot move). Growth in `ojz_bg_anim`
     shifts the whole run `Map_TestObj .. Art_Sonic` downstream into this hole.
     `rom_room()` derives it.

  2. PLACER ROOM — what sigil's frozen-pin MEASURING pass can even resolve. The
     chainer measures every section's image length at its frozen provisional base;
     when a grown section collides there it retries with a cumulative
     `0x400`-per-rank spread (`sigil crates/sigil-harness/src/native.rs`,
     `measure_or_spread`). `ojz_bg_anim` and `test_mappings` are ADJACENT in the map
     order, so the retry buys exactly ONE spread step. A section that outgrows
     (its frozen allotment + one step) cannot be MEASURED, and the build stops with
     `... overlap in the image (colliding pins)`. `placer_room()` derives it.

  ROM room is ~11 KB. Placer room is ~1 KB. **The placer is the binding limit
  today, and it is not raisable from this repo** — see docs/DEFERRED_WORK.md,
  "BGANIM-PLACE".

USAGE
    python3 tools/bganim_room.py --lst s4.debug.lst            # report
    python3 tools/bganim_room.py --lst s4.debug.lst --gate     # report + fail on breach

LOUD ON UNMEASURABLE: every input this module cannot read is a hard error naming the
input. It never renders "could not measure" as 0, and it never returns a room figure
it did not derive.
"""
import os
import re
import sys

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The `.lst` label rows sigil emits: `(0) <n>/<HEXLMA> :        <Name>:`
_LST_LABEL = re.compile(r"^\(0\)\s+\d+/([0-9A-Fa-f]+)\s+:\s+([A-Za-z_$][\w$.]*):")

#: `[[anchor]]` blocks in a game's placement map: `name = "..."` then `at = 0x...`.
_TOML_NAME = re.compile(r'^\s*name\s*=\s*"([^"]*)"')
_TOML_AT = re.compile(r"^\s*at\s*=\s*(0x[0-9A-Fa-f]+|\d+)")

#: The measuring spread step, read out of sigil's own source (see `sigil_spread_step`).
_SPREAD = re.compile(r"\*p \+= (0x[0-9A-Fa-f]+) \* rank as u32")

#: The blob whose embed IS `Art_Sonic` — the last packed data before the anchor.
#: Single authority: games/sonic4/data/collision/collision_data.emp's
#: `const _art_sonic = embed(...)`, parsed rather than restated so a re-export
#: to a different path cannot leave this reading a stale file.
_ART_SONIC_EMBED = re.compile(r'const\s+_art_sonic\s*=\s*embed\(\s*"([^"]*)"')
COLLISION_DATA_EMP = "games/sonic4/data/collision/collision_data.emp"

#: The label that ends the packed run, and the hardware anchor it runs into.
LAST_PACKED_LABEL = "Art_Sonic"
ANCHOR_NAME = "dac_banks"
#: The two labels whose spacing IS the section's current frozen allotment.
SECTION_HEAD = "BgAnim_Table"
SECTION_NEXT = "Map_TestObj"


class Unmeasurable(Exception):
    """An instrument could not be read. NEVER caught to produce a zero or a green."""


def lst_labels(lst_path):
    """label -> ROM LMA, from a sigil `.lst`. The instrument, not the frozen table."""
    if not os.path.exists(lst_path):
        raise Unmeasurable(
            f"no listing at {lst_path}. NOTHING WAS MEASURED: the room derivation reads "
            f"label LMAs out of the sigil `.lst`, and there is no substitute — the frozen "
            f"boundary table lists a SUBSET of labels, so a gap in it is an allotment and "
            f"not free space (docs/OVERSEER.md). Build the shape first (`./build.sh` / "
            f"`DEBUG=1 ./build.sh`), then re-run.")
    out = {}
    with open(lst_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = _LST_LABEL.match(line)
            if m:
                out.setdefault(m.group(2), int(m.group(1), 16))
    if not out:
        raise Unmeasurable(f"{lst_path} parsed to ZERO labels — the listing format changed "
                           f"under {_LST_LABEL.pattern!r}; fix the parser, do not report 0")
    return out


def anchor_addr(map_toml, name=ANCHOR_NAME):
    """The declared `[[anchor]]` address, from the game's placement map."""
    if not os.path.exists(map_toml):
        raise Unmeasurable(f"no placement map at {map_toml}")
    cur = None
    with open(map_toml, encoding="utf-8") as f:
        for line in f:
            m = _TOML_NAME.match(line)
            if m:
                cur = m.group(1)
                continue
            m = _TOML_AT.match(line)
            if m and cur == name:
                return int(m.group(1), 0)
    raise Unmeasurable(
        f"{map_toml} declares no `[[anchor]]` named {name!r} with an `at =` address. "
        f"That anchor is the fixed end of the data region (a Z80 SetBank latch); without "
        f"it there is no room figure to report.")


def art_sonic_bytes(aeon=AEON):
    """Size of the blob `Art_Sonic` embeds, resolved through the .emp that embeds it."""
    src = os.path.join(aeon, COLLISION_DATA_EMP)
    if not os.path.exists(src):
        raise Unmeasurable(f"no {COLLISION_DATA_EMP} — cannot resolve Art_Sonic's blob path")
    with open(src, encoding="utf-8") as f:
        m = _ART_SONIC_EMBED.search(f.read())
    if not m:
        raise Unmeasurable(
            f"{COLLISION_DATA_EMP} no longer spells `const _art_sonic = embed(\"...\")`. "
            f"Art_Sonic's length is derived from that embed; re-point this parser at "
            f"whatever now defines it rather than hardcoding a size.")
    blob = os.path.join(aeon, m.group(1))
    if not os.path.exists(blob):
        raise Unmeasurable(f"Art_Sonic embeds {m.group(1)}, which does not exist")
    return blob, os.path.getsize(blob)


def rom_room(lst_path, aeon=AEON, map_toml=None):
    """Physical bytes between the end of the packed data run and the hardware anchor.

    DERIVATION (every term from an instrument, none from the frozen table):
        end   = LMA(Art_Sonic)            <- the `.lst`
              + len(art blob on disk)     <- the file the .emp embeds
        room  = anchor                    <- map.toml's [[anchor]] dac_banks
              - end
    """
    map_toml = map_toml or os.path.join(aeon, "games", "sonic4", "map.toml")
    labels = lst_labels(lst_path)
    if LAST_PACKED_LABEL not in labels:
        raise Unmeasurable(
            f"{lst_path} defines no {LAST_PACKED_LABEL} — either this shape does not place "
            f"the character data island, or the label was renamed. Not a zero-room answer.")
    blob, blob_len = art_sonic_bytes(aeon)
    anchor = anchor_addr(map_toml)
    end = labels[LAST_PACKED_LABEL] + blob_len
    return {
        "art_sonic_lma": labels[LAST_PACKED_LABEL],
        "art_blob": blob,
        "art_blob_len": blob_len,
        "packed_end": end,
        "anchor": anchor,
        "room": anchor - end,
    }


def sigil_spread_step(sigil_build=None):
    """The measuring spread step, READ OUT OF SIGIL'S SOURCE — not restated here.

    `measure_or_spread` in `crates/sigil-harness/src/native.rs` retries a collided
    measuring resolve with `*p += 0x400 * rank as u32`. That literal is the whole of
    the placer's slack, so it is parsed rather than copied: if sigil widens it, the
    placer ceiling this repo reports widens with it instead of going stale.

    `sigil_build` is the path to the `sigil` binary (`$SIGIL_BUILD`); the repo root is
    its `target/release/..` grandparent. Returns (step, source_path).
    """
    sigil_build = sigil_build or os.environ.get("SIGIL_BUILD", "")
    if not sigil_build:
        raise Unmeasurable(
            "SIGIL_BUILD is unset, so sigil's source tree cannot be located and the "
            "measuring spread step cannot be read. The placer ceiling is NOT derivable "
            "in this environment — say so; do not fall back to a number.")
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(sigil_build))))
    src = os.path.join(root, "crates", "sigil-harness", "src", "native.rs")
    if not os.path.exists(src):
        raise Unmeasurable(f"no sigil harness source at {src} (derived from SIGIL_BUILD)")
    with open(src, encoding="utf-8", errors="replace") as f:
        m = _SPREAD.search(f.read())
    if not m:
        raise Unmeasurable(
            f"{src} no longer spells the measuring spread as {_SPREAD.pattern!r}. The "
            f"placer ceiling is a function of that step; re-point this parser rather "
            f"than pinning the old value.")
    return int(m.group(1), 0), src


def placer_room(lst_path, sigil_build=None):
    """What sigil's frozen-pin measuring pass can resolve for `ojz_bg_anim`.

    DERIVATION:
        allotment = LMA(Map_TestObj) - LMA(BgAnim_Table)      <- the `.lst`
        room      = allotment + one spread step               <- sigil's own source

    Validated against two independent measurements on 2026-08-24: a 814-byte section
    builds in both sonic4 shapes; a 1,070-byte one fails in both, and sigil's own
    diagnostic reported the available spans as 0x40E (plain) and 0x402 (debug) —
    exactly `allotment + 0x400` for allotments of 14 and 2.
    """
    labels = lst_labels(lst_path)
    for name in (SECTION_HEAD, SECTION_NEXT):
        if name not in labels:
            raise Unmeasurable(
                f"{lst_path} defines no {name} — this shape does not place the "
                f"`ojz_bg_anim` seam (the `demo` game does not), so it has no placer "
                f"room to report. Not a zero.")
    allot = labels[SECTION_NEXT] - labels[SECTION_HEAD]
    step, src = sigil_spread_step(sigil_build)
    return {
        "allotment": allot,
        "spread_step": step,
        "spread_source": src,
        "room": allot + step,
    }


def report(lst_path, aeon=AEON, sigil_build=None, gate=False, out=sys.stdout):
    """Print both derivations; with `gate`, fail on a breach. Returns the exit code."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from inject_editor_bg import (BGANIM_SECTION_CEILING, BGANIM_PLACER_CEILING,
                                  live_section_bytes)

    r = rom_room(lst_path, aeon)
    live = live_section_bytes(aeon)
    headroom = r["room"] + live
    print(f"bganim_room [{os.path.basename(lst_path)}]:", file=out)
    print(f"  Art_Sonic 0x{r['art_sonic_lma']:X} + {r['art_blob_len']} "
          f"= 0x{r['packed_end']:X}; anchor 0x{r['anchor']:X}", file=out)
    print(f"  ROM room {r['room']} B free + {live} B the section already holds "
          f"= {headroom} B for ojz_bg_anim", file=out)
    print(f"  ruled authoring ceiling BGANIM_SECTION_CEILING = "
          f"{BGANIM_SECTION_CEILING} B", file=out)

    rc = 0
    if gate and BGANIM_SECTION_CEILING > headroom:
        print(
            f"bganim_room: FAIL — the ruled BG-animation ceiling no longer fits.\n"
            f"  BGANIM_SECTION_CEILING = {BGANIM_SECTION_CEILING} B but only {headroom} B "
            f"are reachable in this shape ({r['room']} B free before the 0x{r['anchor']:X} "
            f"`{ANCHOR_NAME}` anchor, plus the {live} B ojz_bg_anim already holds).\n"
            f"  The likely cause is that {os.path.relpath(r['art_blob'], aeon)} grew: it is "
            f"{r['art_blob_len']} B and it is the last packed blob before a HARDWARE anchor "
            f"that cannot move (a Z80 SetBank latch).\n"
            f"  This is the revisit decision d-9 named. Either shrink the ceiling in "
            f"tools/inject_editor_bg.py (authors lose band size) or take the relocation "
            f"option d-9 kept open. Do NOT raise the anchor.",
            file=out)
        rc = 1

    # The placer half is reported separately because it answers a different question
    # and is the BINDING one today. Unmeasurable here is loud, not silent.
    try:
        p = placer_room(lst_path, sigil_build)
    except Unmeasurable as e:
        # LOUD ON UNMEASURABLE. Printing "UNMEASURED" and returning green would make
        # the gate stop asking the question without anyone noticing — the placer limit
        # is the BINDING one, so an unanswerable question here is a failure, not a
        # pass. (This exact hole was found by poisoning the parser and watching the
        # gate exit 0.)
        print(f"  placer room: UNMEASURED — {e}", file=out)
        if gate:
            print("bganim_room: FAIL — the placer ceiling could not be derived, so the "
                  "BINDING limit on ojz_bg_anim went unchecked. That is a failure, not "
                  "a pass.", file=out)
            rc = 1
        return rc
    print(f"  placer room {p['room']} B "
          f"(frozen allotment {p['allotment']} + spread step {p['spread_step']}) "
          f"-- BINDING, see docs/DEFERRED_WORK.md BGANIM-PLACE", file=out)
    # BGANIM_PLACER_CEILING must be the MINIMUM across the sonic4 shapes, which no
    # single shape can confirm. What a single shape CAN prove is the safety-relevant
    # direction: a recorded ceiling ABOVE this shape's room would let the emitter pass
    # a band that then dies at `colliding pins` — the exact experience this parcel
    # replaces. (The other direction only costs an author a few bytes, and the
    # equals-the-minimum half is gated by
    # tools/test_bg_emit.py::TestBgAnimSectionCeiling.)
    if BGANIM_PLACER_CEILING > p["room"]:
        print(
            f"bganim_room: FAIL — tools/inject_editor_bg.py records "
            f"BGANIM_PLACER_CEILING = {BGANIM_PLACER_CEILING} B but this shape can only "
            f"place {p['room']} B ({p['allotment']} B frozen allotment + one "
            f"{p['spread_step']} B spread step). The emitter would accept a band this "
            f"shape cannot place, and the author would meet `overlap in the image "
            f"(colliding pins)` instead of a sentence. Re-derive the recorded value as "
            f"the MINIMUM over every sonic4 shape's listing.",
            file=out)
        rc = 1
    elif BGANIM_PLACER_CEILING < p["room"]:
        print(f"  (this shape has {p['room'] - BGANIM_PLACER_CEILING} B more placer room "
              f"than the recorded minimum — the recorded value is the tighter shape's)",
              file=out)
    return rc


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    lst, gate = None, False
    while argv:
        a = argv.pop(0)
        if a == "--lst":
            lst = argv.pop(0)
        elif a == "--gate":
            gate = True
        else:
            print(f"usage: {sys.argv[0]} --lst <rom.lst> [--gate]", file=sys.stderr)
            return 2
    if not lst:
        print(f"usage: {sys.argv[0]} --lst <rom.lst> [--gate]", file=sys.stderr)
        return 2
    try:
        return report(lst, gate=gate)
    except Unmeasurable as e:
        print(f"bganim_room: FAIL (unmeasurable) — {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
