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
  blob (`Art_Sonic`) and the `dac_banks` anchor (`map.toml`'s `[[anchor]]`). Growth
  in `ojz_bg_anim` shifts the whole run `Map_TestObj .. Art_Sonic` downstream into
  this room. `rom_room()` derives it. Until the ROM re-layout (2026-08-26) the anchor
  was $48000 and read as a hardware latch that could not move, so the room was
  whatever Sonic's art left (~3.9 KB in the debug shape at d-28); since the re-layout
  the Z80 banks sit AFTER the data region and the anchor is DERIVED — see the rule.

  THAT `Art_Sonic` IS LAST IS NOW CHECKED, AND USED NOT TO BE (2026-09-06, from the
  sigil lane's e5b47915 item B7). This paragraph used to assert "the last packed data
  blob" as a plain fact while the code's only guard was that the LABEL EXISTS. It was
  true at the time and nothing held it true: anything landing between
  `LMA(Art_Sonic) + blob` and the anchor makes the terminus too LOW, so `room` comes
  out LARGER than the space that exists and BOTH consumers — the build-fatal reserve
  gate and the ceiling gate — stay green through a real breach. `check_terminus()`
  now asserts it from the two occupancy instruments this header already named as the
  only ones that can answer occupancy: no label LMA in [packed_end, anchor), and (with
  `--rom`, which build.sh's gate always passes) every byte of that region zero in the
  ROM image — the half that can see UNLABELLED content the listing cannot. A broken
  terminus is Unmeasurable, not a `--gate` verdict: it does not mean a budget was
  breached, it means the room number is WRONG, so no figure is reported at all.
  Measured at introduction on both canonical shapes: zero labels and zero non-zero
  bytes in the region (s4 115,724 B, s4.debug 113,122 B) — the assumption held, and
  now it is held.

  AND SO IS THE LENGTH TERM (2026-09-06, sigil's F2 — the other half of the same
  line). `end = LMA(Art_Sonic) + blob_len` can be wrong in TWO independent ways, and
  they CANCEL: a label that moved down by K with a blob that grew by K leaves `end`,
  `room` and both gates' verdicts bit-for-bit unchanged. So the terminus check above
  does NOT imply this one and neither may be inferred from the other. `check_extent()`
  asserts the length term from the source and the image: `Art_Sonic` is the LAST
  emitting `data` in its module, it binds its embed WHOLE, its section has no second
  module, and (with `--rom`) the `blob_len` bytes at its LMA in the ROM are
  byte-identical to the embedded file. The last of those is what turns `+ blob_len`
  from a restatement of `os.path.getsize` into a measurement of the ROM.
  ⚠ The case that motivates the SOURCE half specifically: trailing content that is
  unlabelled AND zero-filled is byte-identical to free space, so NEITHER occupancy
  instrument can see it. map.toml concedes this in its own words — "a section with
  several embeds has no such instrument" — and records that the character-data
  sections were ordered before `collision_data` so the assumption would hold.
  Arranged-so-it-holds is not checked; this is the check.

  THE TWO BANK ANCHORS ARE COMPARED (2026-09-06, sigil's F6). `SOUND_BANK_OFFSET`
  encodes `sound_bank == dac_banks + 0x10000` and used to appear only in its own
  definition and inside the remedy f-string below — never compared against the map,
  so the two `[[anchor]]` addresses could drift apart with nothing noticing and the
  gate's own remedy line would then name a `sound_bank` the map disagrees with.
  `report()` now reads both anchors with the same parser and fails the pair by name.
  Measured at introduction: 0xA8000 + 0x10000 == 0xB8000, as declared.

  BANK PLACEMENT RULE (games/sonic4/map.toml, enforced here since 2026-08-26;
  the GRACE term added 2026-09-04) —
      dac_banks = align_up(packed_end + DATA_GROWTH_RESERVE + DATA_GROWTH_GRACE, 0x8000)
      sound_bank = dac_banks + 0x10000
  with DATA_GROWTH_RESERVE = 0xC000 (49,152 B: the d-28 two-8 KB-bands-per-act
  guarantee of 16,384 B plus 30 days of the measured 08-26..09-04 consumption,
  rounded up to the reserve's own 0x4000 quantum) and DATA_GROWTH_GRACE = 0x8000
  (32,768 B, one SetBank window: the growth this layout is GUARANTEED to absorb
  before the gate fires again — see the constant's own note for why the 08-26
  single-term rule could not guarantee that at any reserve).
  One anchor serves every sound-on shape, so the binding shape is the
  one with the largest packed end; for the others the anchor sits ABOVE their rule
  value and that slack is reported, never failed. What DOES fail (with `--gate`): a
  shape whose room drops under the reserve — the report names the anchor pair the
  rule now demands, and the remedy is to move BOTH anchors, never to shrink the
  reserve. An anchor off the 0x8000 grid fails by name before any room arithmetic
  is trusted.

  ⚠ MOVING THE ANCHORS IS NOT SOMETHING AEON CAN DO ALONE, and that is a mechanism
  rather than the retired ceremony. The owner ended the paired aeon+sigil freeze on
  2026-09-02 ("CUT THE CEREMONY", empyrean docs/OVERSEER.md 2026-09-02T18:20:19Z),
  so a sigil refreeze no longer GATES an ordinary aeon landing. But a `[[anchor]]`
  in map.toml places nothing: sigil derives every section's provisional base from
  its frozen table (`load_frozen_table` -> `true_bases_by_index`) and uses the map's
  anchors only as an address set that AUTHORIZES a section to stay where the table
  already puts it. Measured both ways on 2026-09-04 — moving the anchors alone gives
  `[map.undeclared-island] ROM section at 0x90000`, and declaring a spare anchor at
  0xA8000 with the tables unchanged gives `[map.anchor-absent] ... at 0xA8000 is not
  an inferred island`. So an anchor move must be HANDED to the sigil lane with the
  new addresses; see the same block in games/sonic4/map.toml.

  RULED AUTHORING CEILING (`BGANIM_SECTION_CEILINGS`, tools/inject_editor_bg.py) — the
  owner's budget inside that room, per shape since decision d-28-answered
  (2026-08-26) and 12,288 (d-9) in both rows again since the re-layout the same day.
  The shape is the listing: `s4.lst` is the release instrument, `s4.debug.lst` the
  debug one, and a listing the table does not name is UNMEASURABLE here — never
  silently the release number. The gate fails the moment a shape's ROM room can no
  longer hold that shape's ceiling (the rule above should fire first, since the
  reserve exceeds the ceiling; if the ceiling arm fires alone, the rule was edited).

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

WHO RUNS THE GATE, AND ON WHICH LISTING (2026-08-26)
---------------------------------------------------
  The ONLY enforcement of `BGANIM_SECTION_CEILINGS` against a real listing is
  build.sh's POST-sigil gate, on the listing the same invocation just emitted:

      bganim_room.py --lst s4.debug.lst --rom s4.debug.bin --built-after <epoch> \\
                     --fixture tools/fixtures/bganim_room_excerpt.lst --gate

  It used to also run in the PRE-build pytest lane, reading whatever `s4*.lst` a
  PRIOR build had left on disk — and that listing was twice not the subject: once it
  was another sigil profile's (config_a, Art_Sonic 0x2F440, room 12,078, refused
  against a 12,094 ceiling — a true statement about the wrong artifact), and once it
  was absent on a fresh tree, so the first canonical build could not pass its own
  pre-build lane. A listing from a prior build is never a valid subject.

  PROVENANCE (`--rom`, `--built-after`): the sigil listing carries no ROM identity
  or CRC of its own (it is label rows and a symbol table), so the check the listing
  actually supports is TEMPORAL: both the listing and the ROM must have been written
  at or after the moment build.sh started the sigil invocation. A stale listing, a
  listing another profile left behind, or a listing that outlived its ROM all fail
  this by construction — nothing else wrote either file after that instant.

  FIXTURE FRESHNESS (`--fixture`): the pytest half of this tool tests the derivation
  over a COMMITTED cut of a real listing (tools/fixtures/bganim_room_excerpt.lst).
  A committed cut has nothing re-deriving it, so the gate re-checks every label row
  it carries against the fresh listing: same parser, same lexical shape once the
  two numeric fields (sequence, LMA) are substituted. If the listing emitter changes
  shape, this is a named "fixture is stale" failure here, not a unit test that keeps
  passing against the old format.

USAGE
    python3 tools/bganim_room.py --lst s4.debug.lst            # report
    python3 tools/bganim_room.py --lst s4.debug.lst --gate     # report + fail on breach
    ... --rom s4.debug.bin                                      # + terminus image scan
    ... --rom s4.debug.bin --built-after 1756236899             # + provenance
    ... --fixture tools/fixtures/bganim_room_excerpt.lst        # + fixture freshness

LOUD ON UNMEASURABLE: every input this module cannot read is a hard error naming the
input. It never renders "could not measure" as 0, and it never returns a room figure
it did not derive. A MISSING listing is a build bug (sigil was asked for
`--emit-lst`), never a bootstrap condition — it exits non-zero naming the runner.
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
_ART_SONIC_EMBED = re.compile(
    r'const\s+(?P<const>_art_sonic)\s*=\s*embed\(\s*"(?P<path>[^"]*)"')
COLLISION_DATA_EMP = "games/sonic4/data/collision/collision_data.emp"

#: The label that ends the packed run, and the bank anchor it runs into.
LAST_PACKED_LABEL = "Art_Sonic"
ANCHOR_NAME = "dac_banks"

#: The head label of the section the room is FOR. `tools/inject_editor_bg.py`
#: emits `pub data BgAnim_Table` first into section `<zone>_bg_anim`, and
#: games/sonic4/map.toml places that section by this row. `check_growth_path`
#: needs it because the room figure is a claim about THIS section's growth, and
#: until 2026-09-06 nothing in this file mentioned the growing section at all —
#: only the run it displaces.
GROWTH_SECTION_HEAD = "BgAnim_Table"

#: An `.emp` `align N` directive. Used to size the pads the growth path crosses;
#: the quantum is read from the module that emitted the pad, never assumed.
_EMP_ALIGN = re.compile(r"^[ \t]*align[ \t]+(\$?[0-9A-Fa-fx]+)", re.M)

#: The second anchor the bank placement rule fixes relative to the first. Checked
#: against `ANCHOR_NAME + SOUND_BANK_OFFSET` so the relation the constant encodes is
#: compared with the map instead of only being printed in a remedy line.
SOUND_ANCHOR_NAME = "sound_bank"

#: The module head (`module <path> in <section>`) and the emitting `data` definitions
#: of a `.emp`. Used by `check_extent` to establish that `Art_Sonic` is the LAST thing
#: its section emits and that it binds its embed WHOLE.
_EMP_MODULE = re.compile(r"^\s*module\s+([\w.]+)\s+in\s+([\w.]+)", re.M)
_EMP_DATA_DEF = re.compile(
    r"^[ \t]*(?:pub[ \t]+)?data[ \t]+([A-Za-z_$][\w$.]*)[ \t]*=[ \t]*(.+?)[ \t]*(?://.*)?$",
    re.M)

#: The BANK PLACEMENT RULE's terms (games/sonic4/map.toml, "BANK PLACEMENT RULE").
#:
#: RESERVE is the floor this gate DEMANDS stays free under `dac_banks`. It holds the
#: d-28 BG-animation guarantee (16,384 B = two 8 KB bands per act) and, since the
#: 2026-09-04 re-layout, a measured runway on top of it — see the rule block in
#: map.toml for the derivation from the 08-26..09-04 consumption.
#:
#: GRACE is the term the 2026-09-04 re-layout ADDED, and it exists because of a
#: structural defect the 08-26 rule had: with `dac_banks = align_up(end + RESERVE)`
#: the free room ABOVE the reserve — the growth the tree may absorb before this gate
#: fires again — is the align_up remainder. That is a lottery on `end mod 0x8000`,
#: uniform on [0, 0x8000), and RAISING RESERVE DOES NOT RAISE IT (the demand and the
#: anchor move together). 08-26 drew 6,368 B and content ate it in 8 days; the gate
#: re-fired 30 B under. Adding GRACE inside the align_up makes the room the anchor
#: buys `>= RESERVE + GRACE`, so the growth absorbed before the next re-layout is
#: bounded BELOW by GRACE instead of by the draw. GRACE = one full SetBank window.
#:
#: The alignment is a Z80 SetBank window; the sound bank follows the blip + shared
#: DAC banks (two windows).
DATA_GROWTH_RESERVE = 0xC000
DATA_GROWTH_GRACE = 0x8000
BANK_ALIGN = 0x8000
SOUND_BANK_OFFSET = 2 * BANK_ALIGN


def rule_anchor(packed_end):
    """The rule's `dac_banks` for a shape whose packed data ends at `packed_end`: the
    first BANK_ALIGN boundary at or above `packed_end + DATA_GROWTH_RESERVE +
    DATA_GROWTH_GRACE`. The gate below fails on RESERVE alone, so the GRACE term is
    exactly the growth this layout is guaranteed to absorb before it fires again."""
    return (-(-(packed_end + DATA_GROWTH_RESERVE + DATA_GROWTH_GRACE) // BANK_ALIGN)
            * BANK_ALIGN)


class Unmeasurable(Exception):
    """An instrument could not be read. NEVER caught to produce a zero or a green."""


def lst_labels(lst_path):
    """label -> ROM LMA, from a sigil `.lst`. The instrument, not the frozen table."""
    if not os.path.exists(lst_path):
        raise Unmeasurable(
            f"no listing at {lst_path}. NOTHING WAS MEASURED: the room derivation reads "
            f"label LMAs out of the sigil `.lst`, and there is no substitute — the frozen "
            f"boundary table lists a SUBSET of labels, so a gap in it is an allotment and "
            f"not free space (docs/OVERSEER.md). The runner is build.sh's POST-sigil gate, "
            f"on the listing `sigil build --emit-lst` just wrote in the same invocation — "
            f"a missing listing there is a BUILD BUG (the emit failed or the path moved), "
            f"not a fresh-tree condition. Do not convert this to a skip.")
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


def declared_addresses(map_toml):
    """Every declared FIXED address in the placement map: `[[anchor]] at` and
    `[[hole]] at`, as a sorted list of (address, what).

    `anchor_addr` answers "where is THIS anchor"; this answers "what in the map is
    pinned at all", which is the question `check_growth_path` needs — an address
    the map fixes anywhere inside the growth path is a section that CANNOT float
    downstream, and the room arithmetic assumes every byte between the growing
    section and `dac_banks` does exactly that.

    Parsed with the same two line regexes `anchor_addr` uses, so a map shape this
    cannot read fails there first rather than silently yielding an empty set.
    """
    if not os.path.exists(map_toml):
        raise Unmeasurable(f"no placement map at {map_toml}")
    out, cur, kind = [], None, None
    with open(map_toml, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s == "[[anchor]]":
                kind, cur = "anchor", None
                continue
            if s == "[[hole]]":
                kind, cur = "hole", None
                continue
            if s.startswith("[["):
                kind, cur = None, None
                continue
            m = _TOML_NAME.match(line)
            if m:
                cur = m.group(1)
                continue
            m = _TOML_AT.match(line)
            if m and kind is not None:
                out.append((int(m.group(1), 0), f"[[{kind}]] {cur or '(unnamed)'}"))
    if not out:
        raise Unmeasurable(
            f"{map_toml} yielded ZERO declared addresses under "
            f"{_TOML_AT.pattern!r} — the map format changed under this parser. Fix "
            f"the parser; an empty answer here would report every growth path clear.")
    return sorted(out)


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
        f"That anchor is the end of the data region this section grows into; without "
        f"it there is no room figure to report.")


def art_sonic_bytes(aeon=None):
    """Size of the blob `Art_Sonic` embeds, resolved through the .emp that embeds it."""
    aeon = AEON if aeon is None else aeon
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
    blob = os.path.join(aeon, m.group("path"))
    if not os.path.exists(blob):
        raise Unmeasurable(f"Art_Sonic embeds {m.group('path')}, which does not exist")
    return blob, os.path.getsize(blob), m.group("const")


def emp_modules(aeon):
    """(section -> [.emp paths]) over the game and engine trees. Only `engine/` and
    `games/` are walked: those are the two trees whose modules a game's map places."""
    out = {}
    for root_name in ("engine", "games"):
        root = os.path.join(aeon, root_name)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for fn in filenames:
                if not fn.endswith(".emp"):
                    continue
                p = os.path.join(dirpath, fn)
                with open(p, encoding="utf-8", errors="replace") as f:
                    m = _EMP_MODULE.search(f.read())
                if m:
                    out.setdefault(m.group(2), []).append(p)
    return out


def emp_module_files(aeon):
    """(module id -> .emp path), the other index of the same walk `emp_modules`
    does. `check_growth_path` needs it to resolve a `__align$<module id>$<n>`
    label back to the source whose `align` directive produced it."""
    out = {}
    for root_name in ("engine", "games"):
        root = os.path.join(aeon, root_name)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for fn in filenames:
                if not fn.endswith(".emp"):
                    continue
                p = os.path.join(dirpath, fn)
                with open(p, encoding="utf-8", errors="replace") as f:
                    m = _EMP_MODULE.search(f.read())
                if m:
                    out.setdefault(m.group(1), p)
    return out


def check_extent(aeon, lma, blob, blob_len, const_name, rom_path=None):
    """ASSERT the OTHER half of `packed_end = LMA(Art_Sonic) + blob_len` (sigil's F2).

    F1 (`check_terminus`) asks whether anything lives ABOVE the terminus. F2 asks
    whether the terminus is where the arithmetic says at all: `+ blob_len` assumes
    `Art_Sonic`'s ROM extent is EXACTLY the embedded file — one embed, bound whole,
    with nothing emitted after it inside its section. It fails in the same direction
    as F1: it UNDERSTATES `packed_end`, which OVERSTATES room, which makes the
    build-fatal reserve gate and the ceiling gate green over a breach.

    ⚠ `check_terminus` DOES NOT ALREADY CLOSE THIS, and the reason is worth stating
    because a check that cannot fail is what this parcel exists to delete. Trailing
    content after the embed comes in three kinds:
      · LABELLED  — a `pub data` after `Art_Sonic` gets a label, which lands in
        [packed_end, anchor) and the SYMBOL half catches it. Already closed.
      · UNLABELLED and NON-ZERO — no label, real bytes; the IMAGE half catches it.
        Already closed.
      · UNLABELLED and ZERO — alignment padding, a zero-filled reservation, an
        embed of zeros. It is byte-identical to free space, so NEITHER instrument
        can see it, and it is precisely what map.toml concedes when it says "a
        section with several embeds has no such instrument". Only the SOURCE can
        testify, which is what this function reads.

    map.toml's own note records that the tree is ARRANGED so the assumption holds
    (the character-data sections were ordered BEFORE `collision_data` for exactly
    this reason). Arranged-so-it-holds is not checked, and this is the check.

    Three assertions, each able to fail on its own:
      (a) SOURCE SHAPE — in the module that defines it, `Art_Sonic` must be the LAST
          emitting `data` definition, and its right-hand side must be exactly the
          const bound by the single `embed(...)`: bound WHOLE, not concatenated,
          padded or sliced.
      (b) SECTION EXCLUSIVITY — that module must be the only one placed in its
          section, or a sibling module could emit after it with no label.
      (c) IMAGE IDENTITY (with `--rom`) — the `blob_len` bytes at `LMA(Art_Sonic)`
          in the ROM must equal the embedded file byte-for-byte. This is what makes
          `+ blob_len` a measurement instead of a restatement: it proves the label
          points AT that blob, at that address, for that length.
    """
    src = os.path.join(aeon, COLLISION_DATA_EMP)
    with open(src, encoding="utf-8") as f:
        text = f.read()

    # (a) source shape
    defs = _EMP_DATA_DEF.findall(text)
    if not defs:
        raise Unmeasurable(
            f"extent: {COLLISION_DATA_EMP} has no `data <Name> = ...` definitions under "
            f"{_EMP_DATA_DEF.pattern!r} — the parser can no longer see what the section "
            f"emits, so it cannot establish that {LAST_PACKED_LABEL} is last. Fix the "
            f"parser; do not report a room figure.")
    names = [n for n, _ in defs]
    last_name, last_rhs = defs[-1]
    if last_name != LAST_PACKED_LABEL:
        trailing = (names[names.index(LAST_PACKED_LABEL) + 1:]
                    if LAST_PACKED_LABEL in names else names)
        raise Unmeasurable(
            f"extent: {LAST_PACKED_LABEL} is NOT the last thing {COLLISION_DATA_EMP} "
            f"emits — {last_name!r} is. The section emits {names!r} in that order, so "
            f"{len(trailing)} definition(s) land AFTER the terminus: {trailing!r}. "
            f"`packed_end = LMA({LAST_PACKED_LABEL}) + {blob_len}` therefore stops SHORT "
            f"of the section's real end, the room figure is too LARGE by whatever those "
            f"emit, and both gates pass over the difference. Either move "
            f"{LAST_PACKED_LABEL} back to the tail (map.toml orders the sections so that "
            f"it IS the packed-data end) or re-point LAST_PACKED_LABEL at whatever now "
            f"ends the run. Do NOT widen this.")
    if last_rhs != const_name:
        raise Unmeasurable(
            f"extent: `data {LAST_PACKED_LABEL} = {last_rhs}` no longer binds the embed "
            f"WHOLE — it was expected to be exactly {const_name!r}, the const bound by "
            f"the single `embed(...)` in {COLLISION_DATA_EMP}. Anything else (a "
            f"concatenation, a pad, a slice) means the label's ROM extent is not "
            f"{blob_len} B, so `packed_end` is wrong in an unknown direction and no room "
            f"figure is reported.")

    # (b) section exclusivity
    mm = _EMP_MODULE.search(text)
    if not mm:
        raise Unmeasurable(
            f"extent: {COLLISION_DATA_EMP} has no `module <path> in <section>` head, so "
            f"the section {LAST_PACKED_LABEL} lands in cannot be named, and whether any "
            f"OTHER module emits into it cannot be answered.")
    section = mm.group(2)
    siblings = sorted(p for p in emp_modules(aeon).get(section, [])
                      if os.path.abspath(p) != os.path.abspath(src))
    if siblings:
        rel = [os.path.relpath(p, aeon) for p in siblings]
        raise Unmeasurable(
            f"extent: section {section!r} is no longer emitted by "
            f"{COLLISION_DATA_EMP} alone — {len(rel)} other module(s) are placed in it: "
            f"{rel}. Whatever they emit may land AFTER {LAST_PACKED_LABEL}, and if it "
            f"carries no label and is zero-filled NEITHER occupancy instrument can see "
            f"it, so `packed_end` would understate the section's end and the room figure "
            f"would be too large. Re-derive the terminus across every module in the "
            f"section, or move the newcomer to a section of its own.")

    # (c) image identity
    identical = None
    if rom_path:
        if not os.path.exists(rom_path):
            raise Unmeasurable(
                f"extent: no ROM image at {rom_path}, so `+ {blob_len}` cannot be "
                f"checked against the bytes at {LAST_PACKED_LABEL}. Not a room figure.")
        size = os.path.getsize(rom_path)
        if size < lma + blob_len:
            raise Unmeasurable(
                f"extent: {rom_path} is {size} B and cannot hold {LAST_PACKED_LABEL}'s "
                f"{blob_len} B at 0x{lma:X} — the image and the listing describe "
                f"different artifacts, so `+ {blob_len}` cannot be verified.")
        with open(rom_path, "rb") as f:
            f.seek(lma)
            in_rom = f.read(blob_len)
        with open(blob, "rb") as f:
            on_disk = f.read()
        if in_rom != on_disk:
            first = next(i for i, (a, b) in enumerate(zip(in_rom, on_disk)) if a != b) \
                if any(a != b for a, b in zip(in_rom, on_disk)) else min(len(in_rom),
                                                                        len(on_disk))
            raise Unmeasurable(
                f"extent: the {blob_len} B at {LAST_PACKED_LABEL} (0x{lma:X}) in "
                f"{rom_path} are NOT {os.path.relpath(blob, aeon)} — they first differ "
                f"{first} B in, at 0x{lma + first:X}. `packed_end = 0x{lma:X} + "
                f"{blob_len}` assumes that label names exactly that file's bytes; it "
                f"does not, so the length term is not measured and no room figure is "
                f"reported. Either the label moved, the listing is not this ROM's, or "
                f"the section emits something else at that address.")
        identical = blob_len
    return {"section": section, "emits": [n for n, _ in defs], "image_identical": identical}


def check_growth_path(labels, aeon, map_toml, packed_end, anchor):
    """ASSERT THE ORDERING PREMISE the room figure rests on (sigil's F7).

    `room = anchor - packed_end` is offered as room for `ojz_bg_anim`, and that
    sentence contains a step nothing checked: it is room for THAT section only if
    growth in THAT section pushes `packed_end` toward the anchor. The module header
    states the premise as a plain fact — "growth in `ojz_bg_anim` shifts the whole
    run `Map_TestObj .. Art_Sonic` downstream into this room" — and it is the
    premise, not the subtraction, that makes the number mean anything. Two ways for
    it to be false, both of which leave the arithmetic looking perfectly healthy:

      (1) THE SECTION IS NOT UPSTREAM. If `ojz_bg_anim` ever landed at or above
          `packed_end`, its growth would not consume this room at all (or would
          consume it twice over), and the gate would keep reporting a figure about
          a different piece of ROM.
      (2) SOMETHING IN THE PATH CANNOT MOVE. Every section between the growing one
          and the anchor has to float downstream. A declared `[[anchor]]` or
          `[[hole]]` inside that span pins a section at an address: growth then
          does not flow into the room, it collides — and it collides at the pin,
          not at `dac_banks`, so the number this gate reports is not the limit.

    And a third thing, which is not a failure but an OVERSTATEMENT the figure
    carried silently:

      (3) ALIGNMENT IS NOT FREE. Growth of K bytes does not shift `packed_end` by
          exactly K when the path crosses `align` directives: each re-aligns, and
          each can add up to N-1 bytes on top of K. The run holds 6 such points in
          `s4.lst` (sonic_anims, tails_anims ×2, knuckles_anims, dust_anims ×2),
          every one `align 2`, so the overstatement is small — but it is real, it
          was never named, and its size is a property of the tree rather than a
          constant. The slop is MEASURED here and subtracted from the headroom the
          gate compares the ruled ceiling against, so the figure is conservative
          rather than plausible.

    Returns a dict; raises `Unmeasurable` for (1) and (2), naming the pin or the
    address. Like `check_terminus` and `check_extent`, a broken premise is NOT a
    `--gate` breach verdict: it does not mean the ceiling was exceeded, it means
    the room number describes something else, so no figure should be trusted.
    """
    if GROWTH_SECTION_HEAD not in labels:
        raise Unmeasurable(
            f"growth path: this listing defines no {GROWTH_SECTION_HEAD} — the room "
            f"figure is offered as room for the `ojz_bg_anim` section, and the section "
            f"is not in this shape. (demo/demo.debug place no such section; they are "
            f"not gated here.) A sonic4 listing without it is a placement change, not a "
            f"zero-room answer.")
    head = labels[GROWTH_SECTION_HEAD]

    # (1) upstream of the terminus
    if head >= packed_end:
        raise Unmeasurable(
            f"growth path: {GROWTH_SECTION_HEAD} is at 0x{head:X}, at or ABOVE the "
            f"packed-data end 0x{packed_end:X}. `room = anchor - packed_end` is offered "
            f"as room for the section that label heads, which is only true while that "
            f"section sits UPSTREAM of the terminus and its growth pushes the terminus "
            f"toward the anchor. It does not, so the figure is about a different piece "
            f"of ROM. Re-derive the room against wherever the section now sits.")

    # (2) nothing pinned inside the path
    pinned = [(a, what) for a, what in declared_addresses(map_toml)
              if head < a < anchor]
    if pinned:
        listed = ", ".join(f"0x{a:X} {what}" for a, what in pinned)
        raise Unmeasurable(
            f"growth path: {len(pinned)} declared address(es) sit between "
            f"{GROWTH_SECTION_HEAD} (0x{head:X}) and the `{ANCHOR_NAME}` anchor "
            f"(0x{anchor:X}): {listed}. Everything in that span has to float downstream "
            f"for growth to turn into consumed room; a section the map PINS cannot. "
            f"Growth would collide at the pin, not at the anchor, so `room` "
            f"({anchor - packed_end} B) is not the limit it is reported as. Either the "
            f"new pin belongs outside the path, or the room must be re-derived against "
            f"the pin instead of the anchor.")

    # (3) alignment slop, MEASURED from the modules that produced the pads
    pads = [(a, n) for a, n in labels_in(labels, head, packed_end)
            if n.startswith("__align$")]
    module_files = emp_module_files(aeon) if pads else {}
    slop, detail = 0, []
    for addr, name in pads:
        body = name[len("__align$"):]
        module_id = body.rsplit("$", 1)[0]
        path = module_files.get(module_id)
        if path is None:
            raise Unmeasurable(
                f"growth path: pad label {name!r} at 0x{addr:X} names module "
                f"{module_id!r}, and no `.emp` under engine/ or games/ declares "
                f"`module {module_id} in ...`. Its alignment quantum is what bounds how "
                f"much MORE than K bytes a K-byte growth can cost, so an unresolvable "
                f"pad makes the headroom figure unbounded above. Not a room figure.")
        with open(path, encoding="utf-8") as f:
            quanta = [int(q[1:], 16) if q.startswith("$") else int(q, 0)
                      for q in _EMP_ALIGN.findall(f.read())]
        if not quanta:
            raise Unmeasurable(
                f"growth path: {os.path.relpath(path, aeon)} emitted the pad {name!r} "
                f"but declares no `align` directive this parser can read "
                f"({_EMP_ALIGN.pattern!r}). Fix the parser rather than assuming the "
                f"quantum — an assumed one is exactly the class of thing this file "
                f"exists to stop.")
        # The MAXIMUM quantum in the module, not the i-th directive: the pad index
        # and the source order are not guaranteed to correspond, and a maximum is
        # wrong only in the conservative direction (it can overstate the slop, which
        # tightens the gate; understating it would loosen one).
        q = max(quanta)
        slop += q - 1
        detail.append((name, addr, q))

    return {"head": head, "pads": detail, "slop": slop,
            "pinned_checked": (head, anchor)}


def labels_in(labels, lo, hi):
    """Every label whose LMA lies in [lo, hi), lowest address first, as (LMA, name)."""
    return sorted((a, n) for n, a in labels.items() if lo <= a < hi)


def image_occupancy(rom_path, lo, hi):
    """What the ROM IMAGE holds over [lo, hi): the second occupancy instrument.

    Returns `(examined, nonzero, first_nonzero, beyond_eof)` — bytes actually read,
    how many of them are non-zero, the LMA of the first such byte (or None), and how
    many of the requested bytes lie past the end of the image (bytes that do not
    exist cannot be occupied, but the count is reported rather than absorbed).

    A ROM that stops BELOW `lo` cannot answer the question at all and is Unmeasurable
    — the region the caller is asking about is not in the file it was handed.
    """
    if not os.path.exists(rom_path):
        raise Unmeasurable(f"terminus: no ROM image at {rom_path} to scan for occupancy")
    size = os.path.getsize(rom_path)
    if size < lo:
        raise Unmeasurable(
            f"terminus: {rom_path} is {size} B (0x{size:X}) and ends BELOW the packed "
            f"terminus 0x{lo:X}, so the image cannot say what occupies the region under "
            f"the anchor. Either this is not the ROM the listing describes, or the "
            f"terminus derivation is wrong. Not a free-room answer.")
    beyond_eof = max(0, hi - size)
    with open(rom_path, "rb") as f:
        f.seek(lo)
        seg = f.read(max(0, min(hi, size) - lo))
    nonzero = [i for i, b in enumerate(seg) if b]
    return (len(seg), len(nonzero), (lo + nonzero[0]) if nonzero else None, beyond_eof)


def check_terminus(lst_path, labels, packed_end, anchor, rom_path=None):
    """ASSERT the precondition every room figure below rests on: `packed_end` really
    IS the end of the data, i.e. NOTHING lives between it and the anchor.

    WHY THIS IS A CHECK AND NOT A COMMENT (2026-09-06, sigil's e5b47915 item B7).
    `packed_end = LMA(Art_Sonic) + blob` was an ASSUMPTION dressed as a fact: the
    header called Art_Sonic "the last packed data before the anchor" and the only
    guard was that the label EXISTS. Anything landing above it and below `dac_banks`
    makes `packed_end` too LOW, so `room` comes out LARGER than the space that
    exists, and both consumers — the reserve gate (build.sh, build-fatal) and the
    ceiling gate — stay GREEN through a real breach. A green that certifies a false
    condition is the worst direction for a gate to fail, and nothing about it looks
    wrong from the outside.

    THE TWO INSTRUMENTS, exactly the two the module header names as able to answer
    occupancy (a gap in the frozen boundary table is an allotment, never free space):

      SYMBOLS (always, the `.lst` is already required) — no label LMA in
      [packed_end, anchor). A label AT `packed_end` counts: a zero-size end marker
      and a real intruder are indistinguishable from the symbol alone, so both fail
      here and the image scan below is what tells them apart.

      THE IMAGE (whenever `--rom` is given, and build.sh's gate always gives it) —
      every byte of [packed_end, anchor) in the ROM file must be zero. This is the
      half that sees UNLABELLED data: a blob placed there with no exported symbol is
      invisible to the listing and would otherwise be counted as free room.

    Raises Unmeasurable naming the intruder and its address. It is Unmeasurable and
    not a `--gate` verdict on purpose: a broken terminus does not mean the budget was
    breached, it means the room NUMBER is wrong, so the tool must refuse to report
    one rather than report one that is too large.
    """
    intruders = labels_in(labels, packed_end, anchor)
    scan = image_occupancy(rom_path, packed_end, anchor) if rom_path else None

    if intruders:
        listed = "\n".join(f"      0x{a:X}  {n}" + (f"   (+{a - packed_end} B above the "
                                                    f"terminus)" if a > packed_end else
                                                    "   (AT the terminus)")
                           for a, n in intruders[:12])
        more = (f"\n      ... and {len(intruders) - 12} more" if len(intruders) > 12 else "")
        if scan is not None:
            _, nonzero, first, _ = scan
            witness = (f"The ROM image AGREES: {nonzero} non-zero bytes in that region, the "
                       f"first at 0x{first:X}. This is real content, not a marker."
                       if nonzero else
                       "The ROM image is all zeros over that region, so this may be a "
                       "zero-size end marker rather than content — but the terminus is "
                       "still not established: re-derive it from whatever the listing now "
                       "says ends the packed run.")
        else:
            witness = ("No --rom was given, so the image half could not run and a zero-size "
                       "marker cannot be told apart from content here. Re-run with --rom.")
        raise Unmeasurable(
            f"terminus: {LAST_PACKED_LABEL} is NOT the last packed data before "
            f"`{ANCHOR_NAME}` in {lst_path}. The packed run was derived to end at "
            f"0x{packed_end:X}, but {len(intruders)} label(s) lie between there and the "
            f"anchor 0x{anchor:X}:\n{listed}{more}\n"
            f"  {witness}\n"
            f"  NO ROOM FIGURE IS REPORTED. Every number this tool prints — the reserve "
            f"gate's and the ceiling gate's alike — is `anchor - packed_end`, so a "
            f"terminus that is too low makes BOTH gates green over a region that is not "
            f"free. Fix the derivation (point {LAST_PACKED_LABEL} at whatever now ends "
            f"the run, or extend it past the new island); do NOT widen the assertion.")

    if scan is not None:
        _, nonzero, first, beyond = scan
        if nonzero:
            raise Unmeasurable(
                f"terminus: the ROM image {rom_path} holds {nonzero} non-zero bytes "
                f"between the packed terminus 0x{packed_end:X} and the `{ANCHOR_NAME}` "
                f"anchor 0x{anchor:X} — the first at 0x{first:X} — and the listing "
                f"exports NO label there. That is UNLABELLED content in the region both "
                f"gates count as free: the symbol half cannot see it, and the room figure "
                f"would be {anchor - packed_end} B when the true free tail is smaller.\n"
                f"  NO ROOM FIGURE IS REPORTED. Find what emits those bytes (a raw embed "
                f"with no exported symbol, or padding that is no longer zero) and either "
                f"give it a label or move it; do NOT widen the assertion.")
        if beyond:
            raise Unmeasurable(
                f"terminus: {rom_path} ends {beyond} B before the `{ANCHOR_NAME}` anchor "
                f"0x{anchor:X}, so the image cannot witness the last {beyond} B of the "
                f"region. The anchored banks are supposed to be IN this ROM; a shape "
                f"whose image stops short of its own anchor is not the shape the room "
                f"figure describes.")
    return {"intruders": intruders, "image_scan": scan}


def rom_room(lst_path, aeon=None, map_toml=None, rom_path=None):
    """Physical bytes between the end of the packed data run and the hardware anchor.

    DERIVATION (every term from an instrument, none from the frozen table):
        end   = LMA(Art_Sonic)            <- the `.lst`
              + len(art blob on disk)     <- the file the .emp embeds
        room  = anchor                    <- map.toml's [[anchor]] dac_banks
              - end

    CHECKED, NOT ASSUMED: `end` is only the end of the data if nothing sits between it
    and the anchor. `check_terminus` asserts that from the two occupancy instruments
    (symbols always, the ROM image when `rom_path` is given) and raises Unmeasurable
    naming the intruder rather than letting a too-low `end` inflate `room`.
    """
    # LATE-BOUND (2026-09-06). These used to default to `aeon=AEON` in the signature,
    # which Python binds ONCE at definition — so `main()`, which has no tree argument,
    # could not be pointed at another tree and would derive the LENGTH term from the
    # live repo while deriving the terminus from whatever listing it was handed. That
    # is the module header's own "a true statement about the wrong artifact" failure,
    # one level down; measured when a hermetic test's CLI half reported the live
    # tree's collision_data.emp.
    aeon = AEON if aeon is None else aeon
    map_toml = map_toml or os.path.join(aeon, "games", "sonic4", "map.toml")
    labels = lst_labels(lst_path)
    if LAST_PACKED_LABEL not in labels:
        raise Unmeasurable(
            f"{lst_path} defines no {LAST_PACKED_LABEL} — either this shape does not place "
            f"the character data island, or the label was renamed. Not a zero-room answer.")
    blob, blob_len, const_name = art_sonic_bytes(aeon)
    anchor = anchor_addr(map_toml)
    lma = labels[LAST_PACKED_LABEL]
    # BOTH halves of `end`, checked independently and in this order: the LENGTH term
    # (F2, check_extent) before the TERMINUS (F1, check_terminus). They are separate
    # ways for the same expression to be wrong and they can CANCEL — an LMA that
    # moved down by K with a blob that grew by K leaves `end` identical — so neither
    # may be inferred from the other, and `end` agreeing with a previous run is not
    # evidence that either arm is sound.
    extent = check_extent(aeon, lma, blob, blob_len, const_name, rom_path)
    end = lma + blob_len
    terminus = check_terminus(lst_path, labels, end, anchor, rom_path)
    # F7 — the ORDERING PREMISE. `room` is only room FOR `ojz_bg_anim` while that
    # section is upstream of the terminus and everything between it and the anchor
    # can float. Checked after the two halves of `end` because it is stated in terms
    # of `end`, and independent of both: a correct terminus with a correct length
    # still says nothing about whether growth reaches this room.
    growth = check_growth_path(labels, aeon, map_toml, end, anchor)
    return {
        "art_sonic_lma": lma,
        "art_blob": blob,
        "art_blob_len": blob_len,
        "packed_end": end,
        "anchor": anchor,
        "room": anchor - end,
        "growth": growth,
        "labels_below_terminus": len(labels_in(labels, 0, end)),
        "image_scan": terminus["image_scan"],
        "extent": extent,
        "map_toml": map_toml,
    }


def ceiling_for_listing(lst_path):
    """(shape key, ruled ceiling) for the shape whose instrument `lst_path` is.

    Per-shape since d-28-answered. The key is the listing's basename — `s4.lst` /
    `s4.debug.lst` — because the listing IS the shape's instrument; anything else is
    Unmeasurable, never the release number by default (a debug listing renamed, or a
    third shape added without a ruling, must fail loudly here rather than be gated
    against a ceiling nobody ruled for it).
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from inject_editor_bg import BGANIM_SECTION_CEILINGS
    key = os.path.basename(lst_path)
    if key not in BGANIM_SECTION_CEILINGS:
        raise Unmeasurable(
            f"{lst_path}: no ruled BG-animation ceiling for a shape whose listing is "
            f"{key!r}. BGANIM_SECTION_CEILINGS (tools/inject_editor_bg.py) names "
            f"{sorted(BGANIM_SECTION_CEILINGS)}; the ceiling is per shape (d-28-answered) "
            f"and an unlisted shape has no number to gate against — add a ruled row, do "
            f"not fall back to another shape's.")
    return key, BGANIM_SECTION_CEILINGS[key]


def check_provenance(lst_path, rom_path, built_after):
    """The listing and the ROM must both post-date the sigil invocation's start.

    This is the provenance check the sigil listing SUPPORTS: it carries no ROM name,
    no CRC, no build id — only label rows and a symbol table — so identity cannot be
    read out of it. What CAN be asserted is that nothing but the invocation that
    started at `built_after` wrote either file after that instant. Returns the two
    mtimes; raises Unmeasurable naming the stale file.
    """
    built_after = float(built_after)
    out = {}
    for what, path in (("listing", lst_path), ("ROM", rom_path)):
        if not os.path.exists(path):
            raise Unmeasurable(
                f"provenance: the {what} {path} does not exist, so the listing cannot be "
                f"tied to a ROM built by this invocation. The runner is build.sh's "
                f"post-sigil gate; this is a build bug, not a bootstrap condition.")
        mtime = os.path.getmtime(path)
        if mtime < built_after:
            raise Unmeasurable(
                f"provenance: {path} (mtime {mtime:.3f}) predates this build's sigil "
                f"invocation (started {built_after:.3f}) — it is a PRIOR build's {what}, "
                f"possibly another profile's, and is not the subject under test. The "
                f"gate reads only the listing the current invocation emitted.")
        out[what] = mtime
    return out


#: The label row, in GROUPS, for the fixture-freshness check: everything that is not
#: one of the two numeric fields must match the committed cut byte-for-byte.
_LST_LABEL_SHAPE = re.compile(r"^(\(0\)\s+)(\d+)(/)([0-9A-Fa-f]+)(\s+:\s+)([A-Za-z_$][\w$.]*)(:.*)$")


def fixture_freshness(lst_path, fixture_path):
    """Every label row the committed fixture carries must still be emitted, under the
    same parser, with the same lexical shape, in the FRESH listing.

    For each fixture row: find the fresh row for that label; substitute the fixture's
    two numeric fields (sequence number, LMA) into the fresh row; the result must equal
    the fixture row exactly. Returns the list of labels checked; raises Unmeasurable
    naming the first stale row and the regeneration command. A fixture with no label
    rows is itself a failure (nothing would be checked).
    """
    if not os.path.exists(fixture_path):
        raise Unmeasurable(f"fixture: no committed listing cut at {fixture_path}")
    fresh = {}
    with open(lst_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = _LST_LABEL_SHAPE.match(line.rstrip("\n"))
            if m:
                fresh.setdefault(m.group(6), (line.rstrip("\n"), m))
    checked = []
    with open(fixture_path, encoding="utf-8") as f:
        for raw in f:
            row = raw.rstrip("\n")
            if not row.startswith("(0)"):
                continue
            m = _LST_LABEL_SHAPE.match(row)
            if not m:
                raise Unmeasurable(
                    f"fixture: {fixture_path} row {row!r} no longer parses as a label row "
                    f"under {_LST_LABEL_SHAPE.pattern!r} — the fixture is STALE against "
                    f"the parser. Regenerate: python3 tools/fixtures/make_listing_excerpt.py "
                    f"{os.path.basename(lst_path)} {fixture_path} --set bganim")
            label = m.group(6)
            if label not in fresh:
                raise Unmeasurable(
                    f"fixture: {fixture_path} carries label {label!r} but the fresh "
                    f"listing {lst_path} emits no such row — the fixture is STALE (label "
                    f"renamed, section removed, or the row format changed so the parser "
                    f"no longer sees it). Regenerate: python3 "
                    f"tools/fixtures/make_listing_excerpt.py {os.path.basename(lst_path)} "
                    f"{fixture_path} --set bganim")
            fresh_row, fm = fresh[label]
            rebuilt = (fm.group(1) + m.group(2) + fm.group(3) + m.group(4)
                       + fm.group(5) + fm.group(6) + fm.group(7))
            if rebuilt != row:
                raise Unmeasurable(
                    f"fixture: {fixture_path} row for {label!r} is STALE against the fresh "
                    f"listing's shape:\n    fixture: {row!r}\n    fresh:   {fresh_row!r}\n"
                    f"  (compared with the sequence and LMA fields substituted). The unit "
                    f"tests exercise this fixture; regenerate it: python3 "
                    f"tools/fixtures/make_listing_excerpt.py {os.path.basename(lst_path)} "
                    f"{fixture_path} --set bganim")
            checked.append(label)
    if not checked:
        raise Unmeasurable(f"fixture: {fixture_path} carries no label rows — nothing checked")
    return checked


def report(lst_path, aeon=None, gate=False, out=sys.stdout, rom_path=None,
           built_after=None, fixture_path=None):
    """Print the ROM-room derivation and this SHAPE's ruled ceiling; with `gate`, fail
    on a breach. Returns the exit code. The verdict line names which of the two binds."""
    aeon = AEON if aeon is None else aeon    # late-bound; see rom_room
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from inject_editor_bg import BGANIM_SECTION_CEILING, live_section_bytes

    shape, ceiling = ceiling_for_listing(lst_path)
    print(f"bganim_room [{shape}]:", file=out)
    if built_after is not None:
        if rom_path is None:
            raise Unmeasurable("--built-after needs --rom: provenance ties the listing "
                               "to the ROM the same invocation wrote")
        times = check_provenance(lst_path, rom_path, built_after)
        print(f"  provenance: {os.path.basename(lst_path)} and "
              f"{os.path.basename(rom_path)} both written after this build started "
              f"(+{times['listing'] - float(built_after):.1f} s / "
              f"+{times['ROM'] - float(built_after):.1f} s)", file=out)
    if fixture_path is not None:
        labels = fixture_freshness(lst_path, fixture_path)
        print(f"  fixture: {os.path.relpath(fixture_path, aeon)} — {len(labels)} label "
              f"rows re-found in the fresh listing with the same shape", file=out)
    r = rom_room(lst_path, aeon, rom_path=rom_path)
    live = live_section_bytes(aeon)
    # The ALIGNMENT SLOP is subtracted (F7 arm 3): growth of K shifts the terminus
    # by up to K + slop, so the largest the section can be and still fit under the
    # anchor is `live + room - slop`, not `live + room`. Measured, not assumed —
    # `check_growth_path` reads each pad's quantum from the module that emitted it.
    headroom = r["room"] + live - r["growth"]["slop"]
    print(f"  Art_Sonic 0x{r['art_sonic_lma']:X} + {r['art_blob_len']} "
          f"= 0x{r['packed_end']:X}; anchor 0x{r['anchor']:X}", file=out)
    # The terminus is now a CHECKED FACT (see check_terminus): say which instruments
    # established it, so a green states what it proved rather than what it assumed.
    if r["image_scan"] is None:
        print(f"  terminus: CHECKED by symbols only — of the "
              f"{r['labels_below_terminus']} labels at or below 0x{r['packed_end']:X}, "
              f"none lies above it, and the region up to the anchor exports no label. "
              f"The ROM image half did NOT run (no --rom), so unlabelled bytes there "
              f"were not ruled out.", file=out)
    else:
        examined, _, _, _ = r["image_scan"]
        print(f"  terminus: CHECKED by both instruments — no label lies between "
              f"0x{r['packed_end']:X} and the anchor, and all {examined} B of that "
              f"region are zero in {os.path.basename(rom_path)}", file=out)
    ex = r["extent"]
    print(f"  extent: CHECKED — {LAST_PACKED_LABEL} is the last of "
          f"{len(ex['emits'])} definitions in section {ex['section']!r} (sole module), "
          f"binds its embed whole"
          + (f", and its {ex['image_identical']} B in "
             f"{os.path.basename(rom_path)} are byte-identical to "
             f"{os.path.relpath(r['art_blob'], aeon)}"
             if ex["image_identical"] is not None else
             "; the byte-identity half did NOT run (no --rom), so `+ "
             f"{r['art_blob_len']}` is a restatement of the file's size here, not a "
             f"measurement of the ROM"), file=out)
    g = r["growth"]
    print(f"  growth path: CHECKED — {GROWTH_SECTION_HEAD} 0x{g['head']:X} is upstream "
          f"of the terminus, and the map pins no address between it and the anchor, so "
          f"growth here consumes the room below", file=out)
    if g["pads"]:
        print(f"    crosses {len(g['pads'])} alignment pad(s) — "
              + ", ".join(f"{n[len('__align$'):]} (align {q})" for n, _a, q in g["pads"])
              + f" — so a K-byte growth can cost up to K+{g['slop']} B; the headroom "
                f"below is reduced by that slop", file=out)
    else:
        print(f"    crosses no alignment pad, so growth costs exactly what it adds",
              file=out)
    print(f"  ROM room {r['room']} B free + {live} B the section already holds "
          f"- {g['slop']} B alignment slop = {headroom} B for ojz_bg_anim", file=out)
    print(f"  ruled authoring ceiling BGANIM_SECTION_CEILINGS[{shape!r}] = {ceiling} B "
          f"(the generator accepts the minimum across shapes, "
          f"BGANIM_SECTION_CEILING = {BGANIM_SECTION_CEILING} B)", file=out)

    rc = 0
    # The BANK PLACEMENT RULE, this shape's own numbers. Alignment first: an anchor
    # off the SetBank grid is not a bank, and no room figure against it is trusted.
    anchor, packed_end = r["anchor"], r["packed_end"]
    if anchor % BANK_ALIGN:
        print(f"bganim_room: FAIL — {ANCHOR_NAME} 0x{anchor:X} is not 0x{BANK_ALIGN:X}-aligned "
              f"(a Z80 SetBank window); the map's anchor is not a bank.", file=out)
        rc = 1 if gate else rc
    else:
        # F6: SOUND_BANK_OFFSET encodes `sound_bank == dac_banks + 0x10000`, and until
        # 2026-09-06 it appeared only in its own definition and in the remedy f-string
        # below — never compared with the map. The two anchors could drift apart with
        # nothing noticing, and the remedy line would then hand the sigil lane a
        # sound_bank address the map disagrees with. Derived from the same parser as
        # dac_banks, never a literal.
        declared_sound = anchor_addr(r["map_toml"], SOUND_ANCHOR_NAME)
        if declared_sound != anchor + SOUND_BANK_OFFSET:
            print(
                f"bganim_room: FAIL — the two bank anchors have drifted apart.\n"
                f"  {r['map_toml']} declares `{ANCHOR_NAME}` at 0x{anchor:X} and "
                f"`{SOUND_ANCHOR_NAME}` at 0x{declared_sound:X}, a gap of "
                f"0x{declared_sound - anchor:X}, but SOUND_BANK_OFFSET encodes "
                f"0x{SOUND_BANK_OFFSET:X} ({SOUND_BANK_OFFSET // BANK_ALIGN} SetBank "
                f"windows: the blip plus the shared DAC banks).\n"
                f"  That relation is what this gate's remedy line tells the sigil lane "
                f"to move BOTH anchors to, so a drift makes the remedy wrong as well as "
                f"the constant. Fix whichever is stale — the map or SOUND_BANK_OFFSET — "
                f"before trusting any anchor arithmetic here.", file=out)
            rc = 1 if gate else rc
        else:
            print(f"  anchor pair: `{SOUND_ANCHOR_NAME}` 0x{declared_sound:X} = "
                  f"`{ANCHOR_NAME}` 0x{anchor:X} + SOUND_BANK_OFFSET "
                  f"0x{SOUND_BANK_OFFSET:X}, as the rule encodes", file=out)
        want = rule_anchor(packed_end)
        if anchor < want:
            print(
                f"bganim_room: FAIL — the bank placement rule is broken in this shape.\n"
                f"  `{ANCHOR_NAME}` is declared at 0x{anchor:X} but packed data ends at "
                f"0x{packed_end:X}, leaving {r['room']} B < DATA_GROWTH_RESERVE "
                f"{DATA_GROWTH_RESERVE} B.\n"
                f"  The rule (games/sonic4/map.toml, BANK PLACEMENT RULE): "
                f"dac_banks = align_up(packed_end + reserve + grace, 0x{BANK_ALIGN:X}) "
                f"= 0x{want:X}, sound_bank = dac_banks + 0x{SOUND_BANK_OFFSET:X} "
                f"= 0x{want + SOUND_BANK_OFFSET:X}.\n"
                f"  Move BOTH anchors there AND hand the two addresses to the sigil "
                f"lane: a map anchor VALIDATES placement, sigil's frozen tables PERFORM "
                f"it, and until the matching rows move in every sound-on table the "
                f"build stops at `[map.undeclared-island]`. Do NOT shrink the reserve.",
                file=out)
            rc = 1 if gate else rc
        else:
            slack = ("this shape binds exactly" if anchor == want else
                     f"0x{anchor - want:X} of slack above this shape's rule value — another "
                     f"sound-on shape binds, or the rule moved")
            print(f"  bank placement rule: packed end 0x{packed_end:X} + reserve "
                  f"{DATA_GROWTH_RESERVE} B + grace {DATA_GROWTH_GRACE} B -> "
                  f"{ANCHOR_NAME} >= 0x{want:X}; declared 0x{anchor:X} ({slack})", file=out)
            print(f"  growth before this gate fires again: {r['room'] - DATA_GROWTH_RESERVE} B "
                  f"(the room above the reserve; guaranteed >= grace "
                  f"{DATA_GROWTH_GRACE} B by the rule)", file=out)

    if gate and ceiling > headroom:
        print(
            f"bganim_room: FAIL — the ruled BG-animation ceiling no longer fits.\n"
            f"  BGANIM_SECTION_CEILINGS[{shape!r}] = {ceiling} B but only {headroom} B "
            f"are reachable in this shape ({r['room']} B free before the 0x{r['anchor']:X} "
            f"`{ANCHOR_NAME}` anchor, plus the {live} B ojz_bg_anim already holds).\n"
            f"  The likely cause is that {os.path.relpath(r['art_blob'], aeon)} grew: it is "
            f"{r['art_blob_len']} B and it is the last packed blob before the anchor.\n"
            f"  Since the ROM re-layout (2026-08-26) the anchor is DERIVED by the bank "
            f"placement rule and the reserve exceeds this ceiling, so the rule arm above "
            f"should have fired first: apply the rule (move both anchors) rather "
            f"than shrinking the ceiling, which is an owner ruling (d-9).",
            file=out)
        rc = 1

    if ceiling <= headroom:
        print(f"  binding limit: the ruled ceiling ({ceiling} B) — it sits "
              f"{headroom - ceiling} B inside the ROM room; placement no "
              f"longer bounds a data section (sigil b0363140)", file=out)
    else:
        print(f"  binding limit: the ROM room ({headroom} B) — the ruled ceiling no longer "
              f"fits before the 0x{r['anchor']:X} `{ANCHOR_NAME}` anchor", file=out)
    return rc


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    usage = (f"usage: {sys.argv[0]} --lst <rom.lst> [--gate] [--rom <rom.bin> "
             f"--built-after <epoch>] [--fixture <cut.lst>]")
    lst, gate, rom, built_after, fixture = None, False, None, None, None
    try:
        while argv:
            a = argv.pop(0)
            if a == "--lst":
                lst = argv.pop(0)
            elif a == "--gate":
                gate = True
            elif a == "--rom":
                rom = argv.pop(0)
            elif a == "--built-after":
                built_after = float(argv.pop(0))
            elif a == "--fixture":
                fixture = argv.pop(0)
            else:
                raise IndexError
    except (IndexError, ValueError):
        print(usage, file=sys.stderr)
        return 2
    # `--rom` ALONE is valid since 2026-09-06: it is the terminus check's image half,
    # useful on its own. `--built-after` without `--rom` remains a usage error — the
    # provenance check ties the listing TO a ROM and has nothing to tie it to.
    if not lst or (built_after is not None and rom is None):
        print(usage, file=sys.stderr)
        return 2
    try:
        return report(lst, gate=gate, rom_path=rom, built_after=built_after,
                      fixture_path=fixture)
    except Unmeasurable as e:
        print(f"bganim_room: FAIL (unmeasurable) — {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
