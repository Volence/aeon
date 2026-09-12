#!/usr/bin/env python3
"""anim_frame_bound — bound the animation frame BYTE against the mappings table
it indexes, for EVERY animation table the ROM ships.

WHY THIS EXISTS (LS-9a)
-----------------------
`AnimateSprite` (engine/objects/animate.emp) classifies a script byte with one
test — `cmpi.b #AF_SET_FIELD, d0 / bhs` — so every byte 0..$F6 is taken as a
mapping frame index and written into `Sst.mapping_frame`. Nothing anywhere
compares that byte against the number of frames the SST's mappings table
actually has. `refresh_piece_count` (engine/objects/frames.emp) then reads an
offset word from past the end of the offset table — i.e. out of piece data — and
follows it as a frame pointer, taking an arbitrary byte as the piece count.

LS-9 bound each mappings table to its DPLC partner (`offset_table_frames(map) ==
offset_table_frames(dplc)`), which is a DIFFERENT claim: two tables that agree
with each other are still both overrun by a script byte at or above their common
frame count. That is this gate.

THE COMPARISON IS STRICT, AND THAT IS THE WHOLE POINT
-----------------------------------------------------
A table of N frames has valid indices 0..N-1, so the bound is

    max reachable mapping_frame  <  offset_table_frames(mappings)

Six of the ten tables shipped today sit at margin ZERO because their last frame
is legitimately used (dust charge 6/7, dust puff 3/4, particle 2/3, sparkle 3/4,
spring 2/3, insta-shield 7/8). Written `<=` this gate would be green on a real
overrun; written `<` on a wrongly-derived maximum it would be red on correct
assets. `--selftest` proves BOTH directions per table: the shipped last frame
stays green, and that frame plus one goes red.

WHY IT READS THE BUILT ROM AND NOT THE SOURCE
---------------------------------------------
This is the design decision LS-9a was booked to make, and the source route was
tried first and rejected. The animation scripts live in `offsets` bodies whose
byte arrays a comptime fn cannot index, so an `.emp` `ensure` reaches only the
three tables whose bodies name a `const: [u8; N]` (insta-shield, ring sparkle,
spring) — three of ten, and a guard that pins three siblings while seven go
unpinned is the exact defect LS-9 was written to remove. A Python parser over
the `.emp` sources hits the same wall from the other side: it has to understand
`offsets` bodies, `const` indirection, `rep()` splices, `centered()` mapping
frames and `equ ... = extern(...)` aliases, and the prototype LS-9 built went
silently blind on four of eleven tables.

The EMITTED ROM erases every one of those distinctions. An `offsets` table and
an `embed()`ed blob have the same shape once linked: a word-offset table whose
first word is twice the entry count, bodies behind it. So the walk below is
uniform over all ten tables, and its population comes from the LISTING — the
labels that actually reached the image — not from a source scan that can go
blind. A scan that goes blind here produces an UNCLAIMED table and a non-zero
exit, never a quiet zero.

WHAT "EVERY TABLE" MEANS, AND HOW THE POPULATION IS BUILT
---------------------------------------------------------
1. Population: every `Ani_*` label in the sigil listing. Not a list typed here.
2. Pairing: each is bound to a mappings label by DERIVATION from the tree —
   a `CharacterDef` literal's `cd_mappings`/`cd_animtable`, a routine that
   writes both `#Map_X, ...mappings(aN)` and `#Ani_Y, ...anim_table(aN)`, or an
   `objdef(map:, anim_table:)` literal. `equ NAME = extern("Sym")` aliases are
   resolved. EVERY derived pair is checked, so a routine that animated one
   character's scripts against another's mappings is checked as the pair it
   really forms, not as the pair someone meant.
3. A table no derivation reaches must appear in DECLARED_PAIRS with a reason and
   live evidence, and it is reported as DECLARED, never folded in with the
   derived ones. One table is in that state today (Ani_Particle — its mappings
   are INHERITED at spawn by CreateEffect_Normal, so no co-located pair exists);
   the tool prints the limitation rather than implying coverage it lacks.
4. A listing label that is neither derived nor declared FAILS the gate.
5. THE POPULATION IS PER SHAPE, and the two canonical shapes differ. s4.debug
   ships all ten tables; s4 (release) ships NINE — `Ani_Particle` is absent
   because the whole TestParticle / TestEmitter / TestStressEmitter /
   TestChurnObj / TestAnimated family is absent from the release image (measured
   2026-09-07: `grep -c TestEmitter` is 0 in s4.lst against 6 in s4.debug.lst,
   with 50 `Ani_Sonic` hits in s4.lst as the positive control). A pairing whose
   table is not in THIS image is reported and skipped — there is no frame byte
   here to bound. The staleness question that gives up ("does this declaration
   still speak for a real table?") is answered in the SOURCE by
   tools/test_anim_frame_bound.py, which runs where no shape is involved.

THE FRAME SET IS NOT JUST THE SCRIPT — THE SECOND AND THIRD MOUTHS
------------------------------------------------------------------
`AnimateSprite` is not the only writer of `Sst.mapping_frame`, and a bound that
ignores the others is wrong for the assets that have them:

  * `TailsAppendage_Main` ADDS a roll-direction bank of 0/4/8/$C to the script's
    byte after the animation step (gated on ANIM_ROLL), so the appendage's
    reachable maximum is above any byte in its table.
  * `Player_ApplyTilt` ADDS a ground-angle block (`block << TILT_*_SHIFT`, four
    blocks) to the WALK and RUN rows for all three player characters — a THIRD
    mouth, and the one LS-9a's card did not name.
  * `Climb_Animate` and the ledge bodies write frames DIRECTLY, bypassing the
    script entirely (Knuckles only, and that ownership is checked against the
    roster rather than assumed).

Those three expansions, the opcode widths, and the writer census are IMPORTED
from tools/dplc_straddle.py rather than restated: it already derives each of
them from the defining constants and re-checks the instruction spellings, and a
second copy would be a second thing to drift. This tool adds the bound they were
missing — dplc_straddle computes an `out_of_range` set from exactly this model
and, until the parcel that added this file, PRINTED it without failing on it.

FAIL-SAFE DIRECTION. dplc_straddle widens an undetermined reachable set to every
frame so its cost model overstates. Widening is not available to a BOUND — "all
frames" is not a bound — so any unclaimed `Sst.mapping_frame` write site, any
claimed routine whose write count drifted, and any stale evidence line FAILS
this gate outright instead of narrowing or widening.

WHAT THIS DOES NOT COVER, STATED SO A GREEN RUN IS NOT OVER-READ
-----------------------------------------------------------------
  * `Ani_Particle`'s pairing is DECLARED, not derived (see 3 above): its mappings
    are inherited from whichever object spawns the particle. The bound proved
    here is against Map_TestObj; a future emitter carrying a different mappings
    set would be an unchecked combination, and the run says so by name.
  * It bounds `mapping_frame` against the MAPPINGS table only. The DPLC table is
    LS-9's `offset_table_frames(map) == offset_table_frames(dplc)` ensure, and
    the two together are what make the DPLC safe.
  * It runs post-link, so it fails at the build, not at the edited line.

Usage:
    anim_frame_bound.py --lst s4.debug.lst [--rom s4.debug.bin] [--gate]
    anim_frame_bound.py --lst s4.debug.lst --selftest
    anim_frame_bound.py --lst demo.debug.lst --game demo --gate

Exit: 0 green, 1 a bound breached or a population gap, 2 UNMEASURABLE.
"""

import argparse
import os
import re
import struct
import sys
from pathlib import Path

# Run as a script, sys.path[0] is tools/ already; imported by pytest it is not.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import artifact_provenance                                                   # noqa: E402

from dplc_straddle import (                                          # noqa: E402
    AEON,
    WRITER_SCAN_ROOTS,
    WRITER_SCAN_SUFFIXES,
    WRITERS,
    Unmeasurable,
    _read,
    _strip_comment,
    anim_opcodes,
    appendage_bank,
    check_anim_dplc_pairings,
    climb_frames,
    lst_labels,
    scan_write_sites,
    sole_ability_owner,
    sst_offsets,
    subject_bindings,
    tilt_expansion,
    unshipped_scan_paths,
)


#: Tables no derivation in the tree can reach, each with the reason and the
#: evidence that keeps the reason true. These are reported SEPARATELY from the
#: derived pairs — a declared pair is a claim this tool makes, not one it read.
DECLARED_PAIRS = {
    "Ani_Particle": dict(
        map="Map_TestObj",
        why="TestParticle sets only its anim_table; its mappings are INHERITED from "
            "the spawning object by CreateEffect_Normal, so no routine binds the pair "
            "and none can be derived. Every emitter in the tree spawns it from a slot "
            "carrying the test object's own mappings set",
        evidence=[
            (r'^\s*move\.l\s+Sst\.mappings\(a0\),\s*Sst\.mappings\(a2\)',
             "CreateEffect_Normal still inherits the parent's mappings — the reason this "
             "pair cannot be derived",
             "engine/objects/children.emp"),
            (r'^\s*move\.l\s+#ANI_PARTICLE,\s*anim_table\(a0\)',
             "TestParticle still binds Ani_Particle and only Ani_Particle",
             "games/sonic4/objects/test_particle.emp"),
            (r'^\s*move\.l\s+#Map_TestObj,\s*Sst\.mappings\(a0\)',
             "Map_TestObj is still the mappings set the test scene installs",
             "games/sonic4/test/ojz_scroll_test.emp"),
        ]),
}


def be16(buf, pos):
    if pos + 2 > len(buf):
        raise Unmeasurable(f"read past the end of the image at 0x{pos:X}")
    return struct.unpack_from(">H", buf, pos)[0]


def offset_table_frames(rom, base, who):
    """Frames in a word-offset table, read out of the ROM.

    The engine's own `offset_table_frames` (engine/objects/dplc.emp) computes
    exactly this from the embedded blob at comptime; the point of re-reading it
    from the image is that a source-declared `offsets` mappings table has no
    blob to parse and is indistinguishable here from one that does.
    """
    first = be16(rom, base)
    if first == 0 or first % 2:
        raise Unmeasurable(
            f"{who}: the first offset word at 0x{base:X} is {first} — an offset table's "
            f"first word IS twice its entry count, so this is not one (or the label moved)")
    return first // 2


def walk_anim_table(rom, base, who, af, events, mapframe_off):
    """Every frame byte a script in this table can name -> {anim_id: {frames}}.

    The same walk `dplc_straddle.parse_anim_table` performs, minus its
    ANIM_COUNT cross-check: that constant belongs to the player id space, and
    six of the tables here are single-animation object scripts that have nothing
    to do with it. The entry count comes from the table's own first word.

    Terminators (AF_END, AF_ROUTINE, AF_DELETE) end the walk; AF_BACK and
    AF_CHANGE end it too, because the rewind lands on bytes already covered and
    the target body is enumerated in its own right. Inline events are read
    THROUGH at the widths anim_opcodes() derived from AnimateSprite's own
    `addq.b #N, Sst.anim_frame(a0)` cursor advances.
    """
    count = offset_table_frames(rom, base, who)
    offs = [be16(rom, base + 2 * i) for i in range(count)]
    starts = sorted(set(offs))
    by_id = {}
    for i, off in enumerate(offs):
        limit = min([s for s in starts if s > off], default=max(starts) + 4096)
        p, frames = off + 1, set()
        while p < limit:
            b = rom[base + p]
            if b < af["AF_SET_FIELD"]:
                frames.add(b)
                p += 1
                continue
            if b == af["AF_BACK"]:
                cursor, n = p - off - 1, rom[base + p + 1]
                if n > cursor:
                    raise Unmeasurable(
                        f"{who}: animation {i} rewinds {n} from cursor {cursor} — the byte "
                        f"`sub.b` in .cc_back underflows and the interpreter reads outside "
                        f"the body, so no bound can be established from this script")
                break
            if b in events:
                if b == af["AF_SET_FIELD"] and rom[base + p + 1] == mapframe_off:
                    # A script writing mapping_frame through AF_SET_FIELD bypasses
                    # the frame walk. DEBUG asserts against it, release does not,
                    # so the value counts toward the bound.
                    frames.add(rom[base + p + 2])
                p += events[b]
                continue
            break                                        # a terminator
        else:
            raise Unmeasurable(
                f"{who}: animation {i} runs past its body end (offset {off}, limit {limit}) "
                f"with no terminator — the script format or the table changed")
        by_id[i] = frames
    return by_id


# ------------------------------------------------------------ pairing, derived

def equ_aliases():
    """`equ NAME = extern("Sym")` across the scanned tree -> {NAME: Sym}.

    The object modules bind their cross-seam data by alias (`equ
    MAP_DUST_PUFF = extern("Map_DustPuff")`), so a scan that only matched the
    linker labels would miss four of the seven co-located pairs.
    """
    rx = re.compile(r'^\s*equ\s+([A-Za-z_]\w*)\s*=\s*extern\("(\w+)"\)', re.M)
    out = {}
    for rel, text in scanned_files():
        for m in rx.finditer(text):
            out[m.group(1)] = m.group(2)
    return out


def scanned_files():
    """(relative path, text) for every file the writer census covers.

    Same roots, suffixes and unshipped exclusion as dplc_straddle's writer scan,
    imported rather than restated so the two populations cannot drift apart.
    """
    unshipped = unshipped_scan_paths()
    for root in WRITER_SCAN_ROOTS:
        base = AEON / root
        if not base.is_dir():
            raise Unmeasurable(f"{root} is not a directory — the pairing scan cannot run")
        for p in sorted(base.rglob("*")):
            if p.suffix not in WRITER_SCAN_SUFFIXES or not p.is_file():
                continue
            rel = p.relative_to(AEON).as_posix()
            if rel in unshipped:
                continue
            yield rel, p.read_text(errors="replace")


def derived_pairs(alias):
    """[(anim label, map label, source)] — every (Ani_*, Map_*) binding in the tree.

    Three shapes, because the tree uses three:

      * a CharacterDef literal, which is the one place a character's mappings
        and animation table are declared together;
      * a routine that writes BOTH `#<map>, ...mappings(aN)` and
        `#<anim>, ...anim_table(aN)` — the object spawn idiom;
      * an `objdef(map: "...", anim_table: extern("..."))` literal.

    Nothing here is a pairing typed into this tool. A routine that bound the
    wrong two is reported as the pair it actually forms and checked as such.
    """
    pairs = []

    charrec = re.compile(r'pub\s+data\s+(CharDef_\w+)\s*:\s*CharacterDef\s*=\s*'
                         r'CharacterDef\{(.*?)\n\}', re.S)
    symbol = re.compile(r'^\s*(?:pub\s+)?(?:proc|comptime\s+fn|fn)\s+([A-Za-z_]\w*)')
    write = re.compile(r'move\.l\s+#([A-Za-z_]\w*),\s*(?:Sst\.)?(mappings|anim_table)\(a[0-7]\)')
    objdef = re.compile(r'pub\s+data\s+(\w+)\s*:\s*ObjDef\s*=\s*objdef\((.*?)\)\s*$', re.S | re.M)

    for rel, text in scanned_files():
        for m in charrec.finditer(text):
            body = m.group(2)
            mp = re.search(r'cd_mappings:\s*extern\("(\w+)"\)', body)
            an = re.search(r'cd_animtable:\s*extern\("(\w+)"\)', body)
            if mp and an:
                pairs.append((an.group(1), mp.group(1), f"{rel} {m.group(1)}"))

        cur, seen = "<file>", {}
        for n, raw in enumerate(text.splitlines(), 1):
            s = symbol.match(raw)
            if s:
                cur, seen = s.group(1), {}
            w = write.search(_strip_comment(raw))
            if w:
                seen[w.group(2)] = w.group(1)
            if "mappings" in seen and "anim_table" in seen:
                pairs.append((alias.get(seen["anim_table"], seen["anim_table"]),
                              alias.get(seen["mappings"], seen["mappings"]),
                              f"{rel}:{n} ({cur})"))
                # Cleared on every completed pair: a routine binding two sets in
                # turn must be judged pair by pair, not against whatever it named
                # first. Same rule as check_anim_dplc_pairings().
                seen = {}

        for m in objdef.finditer(text):
            body = _strip_comment_block(m.group(2))
            mp = re.search(r'\bmap:\s*"(\w+)"', body)
            an = re.search(r'\banim_table:\s*extern\("(\w+)"\)', body)
            if mp and an:
                pairs.append((an.group(1), mp.group(1), f"{rel} {m.group(1)}"))

    if not pairs:
        raise Unmeasurable("the pairing scan found NO (Ani_*, Map_*) binding at all — "
                           "the scan roots or the binding idioms changed")
    return pairs


def _strip_comment_block(text):
    return "\n".join(_strip_comment(line) for line in text.splitlines())


# ------------------------------------------------------- the reachable set

def writer_census_faults():
    """Every reason the reachable set cannot be trusted, as strings.

    Straight from dplc_straddle's own census rules, run here for their own sake:
    a write site no WRITERS entry claims, a claimed routine whose write count
    drifted, and a stale evidence line each mean some path writes mapping_frame
    in a way this tool has not modelled. A cost model can widen and overstate;
    a BOUND cannot, so each of these fails.
    """
    faults = []
    by_routine = {}
    for rel, n, sym, _text in scan_write_sites():
        by_routine.setdefault((rel, sym), []).append(n)

    for key in sorted(set(by_routine) | set(WRITERS)):
        spec, found = WRITERS.get(key), by_routine.get(key, [])
        if spec is None:
            faults.append(f"UNCLAIMED Sst.mapping_frame writer {key[0]} ({key[1]}) at line(s) "
                          f"{', '.join(str(n) for n in found)} — no WRITERS entry in "
                          f"tools/dplc_straddle.py says what it writes, so the reachable set "
                          f"is incomplete and no bound follows from it")
            continue
        if not found:
            faults.append(f"WRITERS claims {key[0]} ({key[1]}) but the scan found no write "
                          f"there — the claim is stale")
            continue
        if len(found) != spec["sites"]:
            faults.append(f"{key[0]} ({key[1]}) holds {len(found)} mapping_frame writes, not "
                          f"the {spec['sites']} its WRITERS entry claims")
            continue
        for ev in spec.get("evidence", ()):
            rx, why = ev[0], ev[1]
            where = ev[2] if len(ev) > 2 else key[0]
            if not re.search(rx, _read(where), re.M):
                faults.append(f"{key[0]} ({key[1]}): {where} no longer matches `{rx}` ({why})")

    faults.extend(f"MISMATCHED anim/DPLC binding — {line}"
                  for line in check_anim_dplc_pairings())
    return faults


def expansions_for(anim_label, by_id, bind):
    """(extra frames, notes) contributed by the non-script mapping_frame writers.

    Which expansion applies is DERIVED, never attached by name: tilt applies to
    an animation table a CharacterDef names (that is what makes its SST a
    player); the roll bank applies to the table the appendage's own equ block
    names; the climb frames apply to the CharacterDef that is the SOLE owner of
    the climb ability hook, checked against the roster so a second character
    with the same hook widens instead of quietly staying Knuckles'.
    """
    extra, notes = set(), []
    players = {b["anim"] for b in bind.values() if b["kind"] == "player"}
    appendages = {b["anim"] for b in bind.values() if b["kind"] == "appendage"}

    if anim_label in players:
        got, note = tilt_expansion(by_id)
        extra |= got
        notes.append(f"Player_ApplyTilt {note}")
    if anim_label in appendages:
        got, note = appendage_bank(by_id)
        extra |= got
        notes.append(f"TailsAppendage_Main {note}")

    climb_spec = next((s for s in WRITERS.values() if s.get("ability")), None)
    if climb_spec is not None:
        owner = sole_ability_owner(bind, climb_spec["ability"])
        if owner is None:
            raise Unmeasurable(
                f"{climb_spec['ability']} is owned by zero or several CharacterDefs — the "
                f"climb/ledge frames are reachable for an undetermined set of sheets, so "
                f"no per-table bound follows")
        if bind[owner]["anim"] == anim_label:
            climb = climb_frames()
            for part in climb.values():
                extra |= part
            notes.append("climb/ledge direct writes: "
                         + ", ".join(f"{k}={len(v)}" for k, v in sorted(climb.items())))
    return extra, notes


# ---------------------------------------------------------------------- report

def build_rows(lst_path, rom_path):
    """One row per (anim table, mappings table) pair, plus the population faults."""
    labels = lst_labels(lst_path)
    rom = (AEON / rom_path).read_bytes() if not str(rom_path).startswith("/") \
        else open(rom_path, "rb").read()
    af, events, _thresh = anim_opcodes()
    mapframe_off = sst_offsets()["mapping_frame"]
    bind = subject_bindings()
    alias = equ_aliases()

    population = sorted(n for n in labels if n.startswith("Ani_"))
    pairs = {}
    for anim, mapl, src in derived_pairs(alias):
        if not anim.startswith("Ani_"):
            continue
        pairs.setdefault((anim, mapl), []).append(src)

    faults = list(writer_census_faults())

    if not population:
        faults.append(f"{lst_path} carries NO Ani_* label at all for game `sonic4` — this gate "
                      f"would then be green over an empty population, which is the one result "
                      f"it must never report as OK")

    # A PAIRING WHOSE TABLE IS NOT IN *THIS* IMAGE IS NOT APPLICABLE, NOT STALE,
    # and getting that wrong turned the release shape red on the first run. The
    # two canonical shapes do not ship the same set: s4.debug carries all ten
    # animation tables, s4 (release) carries NINE — `Ani_Particle` is absent
    # because the whole TestParticle / TestEmitter / TestStressEmitter /
    # TestChurnObj / TestAnimated family is absent from the release image
    # (measured 2026-09-07: `grep -c TestEmitter` is 0 in s4.lst and 6 in
    # s4.debug.lst, against a positive control of 50 Ani_Sonic hits in s4.lst).
    #
    # Absence is therefore reported and skipped, never faulted: there is no frame
    # byte in this image to bound. What that costs is the ability to notice a
    # declaration that outlived its table — so THAT check lives in the source,
    # not here: tools/test_anim_frame_bound.py holds every DECLARED_PAIRS
    # evidence line against the file that defines the binding, and runs in the
    # pre-build lane where no shape is involved.
    not_in_shape = []

    declared = {}
    for anim, spec in DECLARED_PAIRS.items():
        if anim not in population:
            not_in_shape.append(f"{anim} (DECLARED) is not in this image — nothing to bound "
                                f"for this shape")
            continue
        if any(a == anim for a, _m in pairs):
            faults.append(f"{anim} is DECLARED in this tool but the tree now binds it too — "
                          f"delete the declaration and let the derivation stand")
            continue
        stale = [f"{where} no longer matches `{rx}` ({why})"
                 for rx, why, where in spec["evidence"]
                 if not re.search(rx, _read(where), re.M)]
        if stale:
            faults.extend(f"{anim} DECLARED pairing: {s}" for s in stale)
            continue
        declared[(anim, spec["map"])] = [f"DECLARED: {spec['why']}"]

    covered = {a for a, _m in pairs} | {a for a, _m in declared}
    for anim in population:
        if anim not in covered:
            faults.append(
                f"{anim} is in {lst_path} but NO CharacterDef, spawn routine or objdef binds "
                f"it to a mappings table, and DECLARED_PAIRS does not claim it — its frame "
                f"bytes are bounded by nothing. Add the binding, or declare the pairing here "
                f"with the reason it cannot be derived")

    rows = []
    for (anim, mapl), sources in sorted({**pairs, **declared}.items()):
        kind = "declared" if (anim, mapl) in declared else "derived"
        if anim not in labels:
            not_in_shape.append(f"{anim} (bound by {sources[0]}) is not in this image")
            continue
        if mapl not in labels:
            # The other direction IS a fault: the animation table shipped and the
            # mappings table it indexes did not, so there is a live frame byte
            # with nothing to bound it against.
            faults.append(f"{mapl} is not a label in {lst_path}, but {anim} — which "
                          f"{sources[0]} pairs it with — IS in this image, so that table's "
                          f"frame bytes are bounded by a mappings table this shape does not "
                          f"ship")
            continue
        by_id = walk_anim_table(rom, labels[anim], anim, af, events, mapframe_off)
        script = set().union(*by_id.values()) if by_id else set()
        extra, notes = expansions_for(anim, by_id, bind)
        reach = script | extra
        bound = offset_table_frames(rom, labels[mapl], mapl)
        rows.append(dict(anim=anim, map=mapl, kind=kind, sources=sources, anims=len(by_id),
                         script_max=max(script) if script else -1,
                         reach_max=max(reach) if reach else -1,
                         bound=bound, notes=notes,
                         over=sorted(f for f in reach if f >= bound)))
    return rows, faults, population, not_in_shape


def report(lst_path, rom_path, game, gate, out=sys.stdout):
    if game != "sonic4":
        # NOT a skip. The claim is positive and checkable: a game with no
        # animation tables has nothing for this gate to bound, and if one
        # appears the gate must start covering it rather than stay quiet.
        labels = lst_labels(lst_path)
        stray = sorted(n for n in labels if n.startswith("Ani_"))
        print(f"anim_frame_bound [{lst_path}]: game `{game}` — the pairing scan covers "
              f"{'/'.join(WRITER_SCAN_ROOTS)} only.", file=out)
        if stray:
            print(f"anim_frame_bound: FAIL — {game} ships {len(stray)} animation table(s) "
                  f"({', '.join(stray)}) that this gate's scan roots do not cover. Widen "
                  f"WRITER_SCAN_ROOTS or this gate is blind to them.", file=out)
            return 1
        print("anim_frame_bound: OK — no Ani_* label in the image, so there is no frame "
              "byte to bound (asserted, not skipped).", file=out)
        return 0

    rows, faults, population, not_in_shape = build_rows(lst_path, rom_path)

    print(f"anim_frame_bound [{lst_path}]: {len(population)} animation table(s) in the "
          f"listing, {len(rows)} (table, mappings) pair(s) checked", file=out)
    print(f"  {'anim table':22s} {'mappings':20s} {'anims':>5s} {'script':>7s} "
          f"{'reach':>6s} {'frames':>6s} {'margin':>6s}  pairing", file=out)
    for r in rows:
        margin = r["bound"] - 1 - r["reach_max"]
        print(f"  {r['anim']:22s} {r['map']:20s} {r['anims']:5d} "
              f"{'$%02X' % r['script_max']:>7s} {'$%02X' % r['reach_max']:>6s} "
              f"{r['bound']:6d} {margin:6d}  {r['kind']}", file=out)
        for s in r["sources"]:
            print(f"      <- {s}", file=out)
        for n in r["notes"]:
            print(f"      + {n}", file=out)

    for n in dict.fromkeys(not_in_shape):
        print(f"  - {n}", file=out)

    failed = False
    for f in dict.fromkeys(faults):
        print(f"  ! {f}", file=out)
        failed = True
    for r in rows:
        if r["over"]:
            print(f"\nanim_frame_bound: FAIL — {r['anim']} can reach mapping frame(s) "
                  f"{', '.join('$%02X' % i for i in r['over'][:12])}, but {r['map']} declares "
                  f"{r['bound']} frames (valid indices 0..{r['bound'] - 1}). AnimateSprite "
                  f"writes the byte unchecked and refresh_piece_count would read an offset "
                  f"word from past the end of {r['map']}'s offset table and follow it as a "
                  f"frame pointer.", file=out)
            failed = True

    if failed:
        return 1
    worst = min((r["bound"] - 1 - r["reach_max"], r["anim"]) for r in rows) if rows else (0, "-")
    print(f"\nanim_frame_bound: OK — every reachable mapping_frame is strictly below its "
          f"mappings table's frame count across all {len(rows)} pair(s); tightest margin "
          f"{worst[0]} ({worst[1]}). DOES NOT COVER: the DPLC table (that is LS-9's "
          f"offset_table_frames(map) == offset_table_frames(dplc) ensure), and "
          f"{sum(1 for r in rows if r['kind'] == 'declared')} pairing(s) are DECLARED rather "
          f"than derived, and {len(not_in_shape)} table(s) this tree binds are not in "
          f"THIS shape's image (listed above) — those are bounded where they ship, not "
          f"here.", file=out)
    return 0 if not gate else 0


# -------------------------------------------------------------------- selftest

def script_positions(rom, base, who, af, events):
    """[(anim_id, absolute ROM address, value)] for every byte the walk TAKES AS
    A FRAME. Operand bytes (a rewind count, an sfx id, an AF_SET_FIELD value) are
    stepped over, so a mutation placed here can only ever move a real frame
    index — which is what makes a red result attributable to the bound and not
    to a corrupted script."""
    count = offset_table_frames(rom, base, who)
    offs = [be16(rom, base + 2 * i) for i in range(count)]
    starts = sorted(set(offs))
    out = []
    for i, off in enumerate(offs):
        limit = min([s for s in starts if s > off], default=max(starts) + 4096)
        p = off + 1
        while p < limit:
            b = rom[base + p]
            if b < af["AF_SET_FIELD"]:
                out.append((i, base + p, b))
                p += 1
                continue
            if b == af["AF_BACK"]:
                break
            if b in events:
                p += events[b]
                continue
            break
    return out


def _verdict(lst_path, image, td, name):
    """Run the gate over a patched image copy -> (exit code, output text)."""
    path = Path(td) / name
    path.write_bytes(bytes(image))
    sink = _Sink()
    rc = report(lst_path, str(path), "sonic4", True, out=sink)
    return rc, sink.text


def selftest(lst_path, rom_path, out=sys.stdout):
    """Prove the STRICT compare per table, in BOTH directions.

    The direction matters more than the redness here. Six of the ten tables
    shipped today sit at margin ZERO — their script's last frame IS the mappings
    table's last frame — so a `<=` compare would be green on a real overrun,
    while a `<` compare over a mis-derived maximum would be red on a correct
    asset. Neither error is visible from one case, so each table gets three:

      A. CONTROL — the shipped image, unpatched, is green for this pair.
      B. LAST VALID — a frame byte set to `frames - 1`, the highest index the
         table really has, must stay GREEN. This is the case that catches a
         comparison written the wrong way round.
      C. FIRST INVALID — the SAME byte set to `frames`, one past the end, must
         go RED and name this table.

    B and C differ by one in a single byte, so nothing but the comparison
    direction separates them.

    B and C need `frames` to be a value a script byte can hold. Two tables
    (Map_Tails and Map_Knuckles, 251 frames each) declare more frames than the
    $F7 frame/command threshold lets a script byte name at all, so for those the
    first invalid index is UNREACHABLE FROM A SCRIPT BYTE and B/C are replaced
    by:

      D. EXPANSION — the largest expressible frame byte ($F6) placed at each
         frame position in turn until one goes red THROUGH an expansion
         (Player_ApplyTilt's tilt blocks add up to 3 << TILT_WALK_SHIFT). If no
         position can breach the bound, the table is reported as one this gate
         cannot fail, with the arithmetic that says why — a vacuity finding, not
         a pass.

    The mutation is a byte patch on an IMAGE COPY: nothing in the tree is edited,
    so there is nothing to restore, and every patched byte is read back off disk
    and asserted changed before its case counts.
    """
    import tempfile

    labels = lst_labels(lst_path)
    rom_p = Path(rom_path) if str(rom_path).startswith("/") else AEON / rom_path
    base = rom_p.read_bytes()
    af, events, _t = anim_opcodes()

    rows, faults, _pop, _nis = build_rows(lst_path, rom_path)
    if faults:
        print("anim_frame_bound selftest: the shipped build is not green — cannot prove "
              "anything red-first against it:", file=out)
        for f in faults:
            print(f"  ! {f}", file=out)
        return 2
    if any(r["over"] for r in rows):
        print("anim_frame_bound selftest: the shipped build already breaches a bound — "
              "fix that first", file=out)
        return 2

    threshold = af["AF_SET_FIELD"]
    print(f"anim_frame_bound selftest [{lst_path}]: {len(rows)} pair(s); frame bytes are "
          f"0..${threshold - 1:02X} (AnimateSprite takes ${threshold:02X}+ as a command)",
          file=out)

    proved = weak = broken = 0
    with tempfile.TemporaryDirectory() as td:
        for r in rows:
            anim, bound = r["anim"], r["bound"]
            pos = script_positions(base, labels[anim], anim, af, events)
            if not pos:
                print(f"  {anim:22s} BROKEN — the walk found no frame byte to mutate", file=out)
                broken += 1
                continue

            # A. CONTROL. Established by build_rows above for every pair at once;
            # restated per table so a green line is not read as covering a pair
            # it never mentioned.
            print(f"  {anim:22s} A control: shipped reach ${r['reach_max']:02X} < {bound} "
                  f"frames — GREEN (margin {bound - 1 - r['reach_max']})", file=out)

            if bound <= threshold - 1:
                # B / C — the boundary pair, at a position whose row carries no
                # expansion. A position IN an expanded row would take `frames-1`
                # over the bound through the expansion and make B red for a
                # reason that is not the comparison direction, so such positions
                # are skipped — and the skip is itself measured, not assumed.
                chosen, b_how = None, ""
                for _id, addr, v in pos:
                    if v == bound - 1:
                        # The byte ALREADY holds the last valid index, so patching
                        # it to that value would change nothing and a green run
                        # would prove nothing. The unpatched image IS case B at
                        # this byte — said out loud, because an unchanged image
                        # reported as a passing mutation is the failure mode this
                        # branch exists to avoid.
                        chosen, b_how = addr, "already in the shipped image, no patch needed"
                        break
                    img = bytearray(base)
                    img[addr] = bound - 1
                    rc, _txt = _verdict(lst_path, img, td, f"{anim}.b.bin")
                    if rc == 0:
                        chosen, b_how = addr, "patched"
                        break
                if chosen is None:
                    print(f"  {anim:22s} B/C BROKEN — no frame position holds "
                          f"${bound - 1:02X} without an expansion carrying it over the "
                          f"bound; the boundary pair cannot be placed", file=out)
                    broken += 1
                    continue
                print(f"  {anim:22s} B last valid: ${bound - 1:02X} at ROM 0x{chosen:X} "
                      f"({b_how}) -> GREEN (a `<=` compare would agree; a "
                      f"wrong-direction one would not)", file=out)

                img = bytearray(base)
                img[chosen] = bound
                path = Path(td) / f"{anim}.c.bin"
                path.write_bytes(bytes(img))
                if path.read_bytes()[chosen] != bound or bytes(img) == base:
                    print(f"  {anim:22s} C BROKEN — the patched byte did not read back "
                          f"changed", file=out)
                    broken += 1
                    continue
                sink = _Sink()
                rc = report(lst_path, str(path), "sonic4", True, out=sink)
                named = anim in sink.text and "FAIL" in sink.text
                if rc == 1 and named:
                    print(f"  {anim:22s} C first invalid: ${bound:02X} at the SAME byte "
                          f"-> RED, names {anim}", file=out)
                    proved += 1
                else:
                    print(f"  {anim:22s} C NOT PROVED — rc={rc} named={named}; the "
                          f"mutation is weak or the runner is dead", file=out)
                    weak += 1
                continue

            # D — the first invalid index is not expressible as a frame byte.
            hit = None
            for _id, addr, v in pos:
                if v == threshold - 1:
                    continue
                img = bytearray(base)
                img[addr] = threshold - 1
                rc, txt = _verdict(lst_path, img, td, f"{anim}.d.bin")
                if rc == 1 and anim in txt:
                    hit = addr
                    break
            if hit is None:
                print(f"  {anim:22s} D VACUOUS — {r['map']} declares {bound} frames, more "
                      f"than the largest frame byte ${threshold - 1:02X} ({threshold - 1}) "
                      f"plus every expansion this tool models can reach, so NO script byte "
                      f"can breach this bound. The gate cannot fail for this pair; it is "
                      f"reported, not counted as proved.", file=out)
                weak += 1
                continue
            print(f"  {anim:22s} D expansion: ${threshold - 1:02X} at ROM 0x{hit:X} -> RED "
                  f"THROUGH an expansion (the first invalid index {bound} is not a "
                  f"frame byte, so B/C cannot be placed for this pair)", file=out)
            proved += 1

    total = proved + weak + broken
    print(f"\nanim_frame_bound selftest: {proved} of {total} pair(s) proved red-first; "
          f"{weak} could not be made red by any frame byte, {broken} broken", file=out)
    return 0 if broken == 0 else 1


class _Sink:
    def __init__(self):
        self.text = ""

    def write(self, s):
        self.text += s

    def flush(self):
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--rom", help="the ROM the listing came from (default: --lst .lst -> .bin)")
    ap.add_argument("--game", default="sonic4")
    ap.add_argument("--built-after", type=float, default=None,
                    help="epoch seconds; the listing and ROM must both post-date it, so a "
                         "PREVIOUS invocation's artifact is UNMEASURABLE rather than measured")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--selftest", action="store_true",
                    help="prove the gate red per table, both directions of the strict compare")
    a = ap.parse_args(argv)
    rom = a.rom or re.sub(r'\.lst$', '.bin', a.lst)
    try:
        if a.built_after is not None:
            # LS-1a (2026-09-12): the ONE freshness verdict (tools/artifact_provenance.py):
            # written after this build began AND the listing's Source Digest reproduces.
            rc = artifact_provenance.gate_check("anim_frame_bound", rom, a.lst, a.built_after,
                                                expect_game=a.game)
            if rc:
                return rc
        if a.selftest:
            return selftest(a.lst, rom)
        return report(a.lst, rom, a.game, a.gate)
    except Unmeasurable as e:
        print(f"anim_frame_bound: UNMEASURABLE — {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
