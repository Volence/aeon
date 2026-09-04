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

  ⚠ THE "PAIRED aeon+sigil LANDING" THIS TEXT USED TO DEMAND IS RETIRED. The owner
  ended the paired freeze on 2026-09-02 ("CUT THE CEREMONY", empyrean
  docs/OVERSEER.md 2026-09-02T18:20:19Z): aeon freezes and certifies alone with its
  own gates, and sigil's nightly drift observer is the safety net — drift is a sigil
  finding after the fact, never a gate on an aeon landing. Sigil's frozen tables
  DO hold resolved addresses that an anchor move staled, so an anchor move is still
  something to HAND to the sigil lane; it is no longer something to block on.

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
_ART_SONIC_EMBED = re.compile(r'const\s+_art_sonic\s*=\s*embed\(\s*"([^"]*)"')
COLLISION_DATA_EMP = "games/sonic4/data/collision/collision_data.emp"

#: The label that ends the packed run, and the bank anchor it runs into.
LAST_PACKED_LABEL = "Art_Sonic"
ANCHOR_NAME = "dac_banks"

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


def report(lst_path, aeon=AEON, gate=False, out=sys.stdout, rom_path=None,
           built_after=None, fixture_path=None):
    """Print the ROM-room derivation and this SHAPE's ruled ceiling; with `gate`, fail
    on a breach. Returns the exit code. The verdict line names which of the two binds."""
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
    r = rom_room(lst_path, aeon)
    live = live_section_bytes(aeon)
    headroom = r["room"] + live
    print(f"  Art_Sonic 0x{r['art_sonic_lma']:X} + {r['art_blob_len']} "
          f"= 0x{r['packed_end']:X}; anchor 0x{r['anchor']:X}", file=out)
    print(f"  ROM room {r['room']} B free + {live} B the section already holds "
          f"= {headroom} B for ojz_bg_anim", file=out)
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
                f"  Move BOTH anchors there. Do NOT shrink the reserve. Hand the new "
                f"anchors to the sigil lane afterwards — their frozen tables hold "
                f"resolved addresses this stales — but do NOT block on it: the paired "
                f"aeon+sigil freeze ended 2026-09-02 (CUT THE CEREMONY).",
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
    if not lst or (rom is None) != (built_after is None):
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
