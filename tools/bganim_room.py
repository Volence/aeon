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

WHAT LIMITS THE SECTION — AND WHAT NO LONGER DOES
--------------------------------------------------
  ROM ROOM (physical, reported here) — bytes between the end of the last packed data
  blob (`Art_Sonic`) and the `dac_banks` hardware anchor at $48000 (a Z80 `SetBank`
  latch; `map.toml`'s `[[anchor]]`, it cannot move). Growth in `ojz_bg_anim` shifts
  the whole run `Map_TestObj .. Art_Sonic` downstream into this hole. `rom_room()`
  derives it: ~11.4 KB in the debug shape, i.e. ONE 8 KB band per act. A second band
  does not fit before the anchor; that needs the "banks late, data unbounded"
  re-layout booked in docs/DEFERRED_WORK.md (the "ROM-tail character-art exile ...
  relayout pressure" entry), not a bigger ceiling.

  RULED AUTHORING CEILING (`BGANIM_SECTION_CEILING`, tools/inject_editor_bg.py) — the
  owner's budget inside that room (decision d-9). The gate here fails the moment the
  ROM room can no longer hold it, which is the revisit d-9 named.

  PLACER ROOM — RETIRED (2026-08-25). This tool used to report a second number,
  "frozen allotment + one 0x400 spread step" (~1 KB), read by regex out of sigil's
  `measure_or_spread`, and called it BINDING: sigil's chainer measured every section
  at its FROZEN provisional base and a data section that outgrew that pin stopped the
  build at `overlap in the image (colliding pins)`. Since sigil b0363140 (merge of
  feat/derived-layout) that is no longer how placement works: a pure-data section
  that collides at its pin is re-measured at a disjoint scratch slot
  (`image_lens_pinned(.., scratch_data=true)`), its neighbours pack downstream from
  real sizes, and a base that drifts past the stale frozen table is a
  `[layout.provisional-drift]` WARNING, never a stop (`packed_true_bases`,
  `GROWTH_DRIFT_TOLERANCE`). Only a run that overruns a declared HARDWARE anchor
  still fails, at the final `resolve_layout` overlap check — which is exactly the
  ROM-room limit above. The placer number therefore bounded nothing, and sigil's own
  design note named its retirement as aeon's ("a stale-but-green tool is the worse
  failure"). It is deleted, not disabled: no regex over sigil's source remains here.

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

#: The blob whose embed IS `Art_Sonic` — the last packed data before the anchor.
#: Single authority: games/sonic4/data/collision/collision_data.emp's
#: `const _art_sonic = embed(...)`, parsed rather than restated so a re-export
#: to a different path cannot leave this reading a stale file.
_ART_SONIC_EMBED = re.compile(r'const\s+_art_sonic\s*=\s*embed\(\s*"([^"]*)"')
COLLISION_DATA_EMP = "games/sonic4/data/collision/collision_data.emp"

#: The label that ends the packed run, and the hardware anchor it runs into.
LAST_PACKED_LABEL = "Art_Sonic"
ANCHOR_NAME = "dac_banks"


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


def report(lst_path, aeon=AEON, gate=False, out=sys.stdout):
    """Print the ROM-room derivation and the ruled ceiling; with `gate`, fail on a
    breach. Returns the exit code. The verdict line names which of the two binds."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from inject_editor_bg import BGANIM_SECTION_CEILING, live_section_bytes

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

    if BGANIM_SECTION_CEILING <= headroom:
        print(f"  binding limit: the ruled ceiling ({BGANIM_SECTION_CEILING} B) — it sits "
              f"{headroom - BGANIM_SECTION_CEILING} B inside the ROM room; placement no "
              f"longer bounds a data section (sigil b0363140)", file=out)
    else:
        print(f"  binding limit: the ROM room ({headroom} B) — the ruled ceiling no longer "
              f"fits before the 0x{r['anchor']:X} `{ANCHOR_NAME}` anchor", file=out)
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
