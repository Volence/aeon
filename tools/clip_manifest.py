#!/usr/bin/env python3
"""clip_manifest.py — `clips.json`: the file aurora writes when the author marquees a
rectangle of a converted donor zone and pastes it into an act.

S2-COMPRESSED-ACT staged plan row 3, first half
(`docs/research/2026-09-17-s2-compressed-act-design.md` §2.2, §8).

WHAT THIS FILE IS FOR. An aeon act's section files are 256x256 VDP nametable words whose
11-bit index means "tile N of the act's ONE tileset" (`project.json` zones[].tileset,
read at `tools/ojz_strip_gen.py:103-119`). Two Sonic 2 zones pasted into one act both
start their tile indices at 0, so index 5 in an Emerald Hill section and index 5 in a
Chemical Plant section are different art and nothing in the section file says so. That is
the "per-cell tileset key" of the design's §1.3 item 1 and the limitation named in
`tools/fg_page_order.py`'s header. `clips.json` is where the key comes from: a cell's
tileset is the tileset of the clip whose destination rectangle covers it.

It is also why the key cannot be dodged by concatenating the zones into one blob: the
editor word's index field is 11 bits, so ONE act-wide tileset tops out at 2048 tiles, and
the design's own measurement puts six clipped zones at 2,965 canonical tiles (§0 item 2).
Multiple tilesets are forced by the format, not chosen.

THE FORMAT (schema 1). Rectangles are in WORLD PIXELS, on both sides, because that is
what an author marquees and what `Region` rectangles already use
(`engine/structs.emp:132-156`).

    {
      "schema": 1,
      "units": "world_px",                  // the ONLY unit in this file, on both sides
      "id": "s2clip_demo",                  // the act's id; names the bake output
      "name": "two-clip fixture",           // free text, optional
      "act": { "grid_w": 2, "grid_h": 1 },  // the target act's SECTION grid, declared
      "clips": [
        { "id": "ehz_a",
          "donor": "s2disasm", "zone": "EHZ",     // -> games/sonic4/data/donors/<donor>/<zone>/
          "src_rect": { "x": 4096, "y": 0, "w": 2048, "h": 1024 },
          "dst_rect": { "x": 0,    "y": 0, "w": 2048, "h": 1024 },
          "region_id": "ehz_a",             // OPTIONAL, aurora's write-back (see below)
    //                                     ABSENT-CASE FIXTURE: games/sonic4/data/clips/s2_two_clip_pins/
    //                                     clips.json omits region_id on every clip. s2_two_clip carries it on both,
    //                                     so a reader built against that one alone will assume presence (aurora, 2026-09-17).
          "unaligned_dst_reason": null      // OPTIONAL opt-out, see R11
        }, ... ] }

WHAT THIS FILE DOES NOT DECIDE, and why — verified 2026-09-17 against the suite contract
`empyrean:contract/schema/aurora-regions.schema.json` at `0742b5ed`, read rather than taken
on report. A pasted clip becomes a `region` there, and that object is
`required: [id, rect, preset]` with `unevaluatedProperties: false`.

  * **`preset` is the region's total identity binding and a donor zone cannot supply it.**
    It names a record in the GAME's effects library (`^[A-Za-z_][A-Za-z0-9_]{0,63}$`,
    validated by `tools/effects_gen.py`), and a Sonic 2 zone has no opinion about aeon's
    effects records. So there is NO preset or palette field here. What a clip supplies is
    the donor's 96 palette bytes — `donors/<donor>/<zone>/palette.bin`, sha256 in that
    tree's `zone.json`, carried into the bake's `clipact.json` `zone_table` — and the
    preset that installs them is named by aurora at paste time. (A `"palette"` field
    existed in an earlier cut of this schema and in the design's §8 sketch; it was a
    preset name in disguise and is gone.)
  * **`region_id` is a WRITE-BACK, not a naming.** Aurora derives the region id; if it
    writes it here, this loader checks it against the schema's own pattern
    (`^[a-z][a-z0-9_]{0,31}$`) so a clips.json can never carry an id aurora could not have
    made. A clip's OWN `id` is held to that same pattern for the same reason: then the two
    documents can use one name for one rectangle instead of two.
  * **PROVENANCE LIVES HERE, NOT IN THE REGIONS DOCUMENT.** `unevaluatedProperties: false`
    means there is no extension point on a region, and the region `id` pattern cannot hold
    a donor name (`EHZ` and `s2disasm/EHZ` are both illegal). The region's `name` is free
    text (maxLength 64, never read by the engine or the generator) and may carry a
    human-readable echo such as `EHZ (s2disasm) clip ehz_a` — but it is an echo. The
    authoritative record of which donor, which zone, which source rectangle and which
    tileset sha is this file and the `clipact.json` the bake writes beside the act.
  * **A `dst_rect` is a legal region rect, but not every legal region rect is a legal
    `dst_rect`.** The schema's rect is world pixels with `x, y >= 0`, `w, h >= 1`, and its
    edges deliberately need not fall on the section grid. This file agrees about the unit
    and the floor and adds two aeon-side constraints: a multiple of 8 (R6, a hard format
    limit — the cell grid) and a section-aligned origin (R11, a default with an in-file
    opt-out). Nothing here rounds: `units` is declared in the file and every rect is an
    integer count of world pixels on both sides, so aurora converts nothing.

WHERE THIS DIFFERS FROM THE DESIGN'S §8 SKETCH, and why (each corrected in the design doc
in place):

  * `"donor": "s2/EHZ"` is gone. Parcel 2 registered TWO donor trees and five zone names
    exist in both, so donor and zone are separate, separately validated fields.
  * `dst_rect` keeps `w`/`h`, and they are REQUIRED to equal `src_rect`'s. A clip is a
    paste, never a scale; carrying both and checking them beats carrying one and hoping.
  * the act's section grid is DECLARED, not inferred from the clips' bounding box. An act
    with a trailing empty section is a different act from one without: the camera window
    sweep the art budget is counted over is a function of the grid
    (`fg_page_order.camera_windows`), so inferring it would make the budget depend on
    where the last clip happened to end.
  * there is no `tileset` field. The tileset is `donors/<donor>/<zone>/tileset.bin`, named
    by parcel 2's tree layout, and its sha256 is in that tree's `zone.json`.

THE ZONE KEY is derived, not authored: distinct `(donor, zone)` pairs in first-appearance
order, 0..n-1. Two clips of the SAME zone share a key — they share a tileset, so they must
share a key or the pool would carry the art twice.

VALIDATION RULES. Each is named in the message it raises or warns with, and every gate row
asserts that tag, so a manifest refused by an earlier rule cannot stand in for a later one.
R1-R10 are refusals with no opt-out; R11 is a refusal with a per-clip, in-file opt-out;
W1-W3 are warnings.

  R1  schema == 1, and `units` is "world_px" — declared in the file so the unit is part of
      the interface rather than a convention two tools each remember separately.
  R2  the act grid is >= 1x1 and fits MAX_ACT_SECTIONS (read from engine source).
  R3  the act id and every clip id match the suite contract's region-id pattern
      `^[a-z][a-z0-9_]{0,31}$`, and clip ids are unique. A clip id that is already a legal
      region id is one aurora can use verbatim, so one rectangle has one name in both
      documents. An optional `region_id` write-back is held to the same pattern.
  R4  donor is a registered donor and zone is one of ITS zones (tools/s2_donor.py).
  R5  rect fields are non-negative integers, w and h positive.
  R6  every rect coordinate is a multiple of 8 px. DERIVED, not a convention: an editor
      section file is a grid of 8-px cells and has no sub-tile addressing.
  R7  dst w/h == src w/h.
  R8  the dst rect lies inside the declared act grid.
  R9  the src rect lies inside the donor zone's CROP rectangle (zone.json
      extent.crop_tiles) — not merely inside its padded section grid. A rect running past
      the crop is silently truncated by the design's measurement tool
      (`s2_clip_budget.clip` slices a numpy array), which is how a clip can measure
      smaller than it reads.
  R10 no two dst rects overlap. A later clip quietly overwriting an earlier one is the
      kind of thing that is found on screen, not in a diff.
  R11 dst x and y are multiples of SECTION_SIZE (2048 px) — the design's §2.2
      recommendation. OPT-OUT: a non-empty "unaligned_dst_reason" string on the clip. The
      opt-out is a field in the file rather than a flag on the command line so the next
      reader of the manifest sees the argument that was made.
  R12 the paste SHIFT (dst origin - src origin) is a multiple of 16 px in both axes.
      DERIVED from the runtime, not from either file format: a collision cell's height
      profile is 16 bytes covering a 16-px block and `probe_core` indexes it with
      `andi.w #$F, d0` on the WORLD x (games/sonic4/player/player_sensors.emp), while
      the collision ROW is the world tile row halved (engine/level/collision_lookup.emp
      `lsr.w #1`). So the geometry a cell describes is anchored to its own world
      position mod 16, and a paste that moves it by 8 px reads the wrong half of every
      profile — silently, because the ART is one word per 8-px cell and moves correctly.
      No opt-out: unlike R11 there is no argument to be made, the data is simply wrong.

  ~~W1  src rect coordinates are not multiples of 128 px (the chunk quantum both games
      share)... upgrading W1 to a refusal is staged-plan row 5's call.~~
      **RETIRED 2026-09-17 BY ROW 5, AND ITS PREMISE WAS FALSE.** Collision is NOT
      authored per 128-px chunk in any sense a clip can cut. A chunk is 8x8 BLOCK
      PLACEMENTS and every placement carries its OWN entry word — its own block id,
      its own flips, its own two solidity nibbles — so a cut between two blocks inside
      a chunk severs nothing, and one at a chunk boundary is not special. The quantum
      that does bind is the BLOCK, 16 px, and it binds on the SHIFT rather than on the
      src origin: a 16-px-aligned src pasted to a 16-px-aligned dst is correct, and so
      is an 8-px-aligned src pasted 2048 px away. R12 above is the rule that survives.
      The tag stays reserved so a future W1 cannot quietly inherit this one's meaning.
  K1-K3 CORRIDORS (S2-COMPRESSED-ACT row 7, 2026-09-25) — see "CORRIDORS" below.
  W2  the src rect contains no painted cell.
  W3  an act section holds cells of two different ZONE KEYS. A WARNING, and the design's
      §2.2 gives two reasons for section-boundary placement of which the measurement
      supports only one (`python3 tools/clip_act_bake.py measure-alignment`, table in
      that file's header):
        * TRUE — a section's local tile map is one 11-bit space capped at 2047 entries
          (`ojz_strip_gen.build_section_local_map`), and a mixed section's map is the SUM
          of both zones'. Measured: 394 + 224 split, 617 merged.
        * NOT SUPPORTED — the camera-window page budget. Measured 9 of 12 either way once
          the control holds clip ADJACENCY fixed; the separated act's 7 is adjacency, not
          section purity. The exact refusal that does bite is downstream and precise
          (build_section_local_map raises past 2047), so this stays a warning.
      A CORRIDOR does not count as a zone here: its sheet is three tiles, so it cannot
      move a local map toward the cap, and warning on every corridor-meets-clip section
      would bury the warning that means something.

CORRIDORS (row 7, owner ruling S2ACT-SEAM-CORRIDORS 2026-09-17: "that was the plan not
butting them together"). Two Sonic 2 zones disagree about which CRAM line their ground is
(design §5.3), so they cannot share a screen; a corridor is the neutral stretch between
two clips that the palette cross-fade plays inside. Schema, beside `clips`:

    "corridors": [
      { "id": "ehz_to_cpz",                               // region-id pattern, unique
        "dst_rect": { "x": 10976, "y": 0, "w": 1312, "h": 1024 },
        "floor_y": 768 } ]                                // world px, top of the floor

WHAT A CORRIDOR PAINTS, and why each choice. It is SYNTHESISED by the bake, never taken
from a donor:
  * ART on CRAM LINE 0 — the character's line, which the engine never writes
    (engine/effects/palette.emp: a preset palette is 96 bytes = lines 1-3, never line 0).
    So the corridor is the one thing on screen a region's palette install CANNOT recolour,
    before, during or after the fade. That is the whole argument for the line; the
    colours inside it (greys of art/palettes/SonicAndTails.bin) are a plain legible
    default, and how the corridor LOOKS is the owner's call.
  * THREE TILES of its own sheet (`corridor_sheet()`): 0 blank, 1 fill, 2 the floor's top
    edge. The sheet is a zone key of its own (the LAST one), so its tiles cannot collide
    with a donor's in the keyed dedupe, and the "no camera window holds two zones" check
    (clip_act_bake Z1) can tell a corridor cell from a zone cell.
  * COLLISION: the bank's full solid block, solid on every side, on BOTH planes, from
    `floor_y` to the rectangle's bottom — a floor with nothing under it to fall into.
    The shape is FOUND in the bank (`corridor_floor_shape`), not typed.
  K1  id matches the region-id pattern, unique across clips AND corridors.
  K2  the rect obeys R5/R6/R8/R10 like a clip's dst (non-negative, 8-px grid, inside the
      act, overlapping nothing).
  K3  floor_y is a multiple of COLL_QUANTUM_PX (16) — a collision row — and lies inside
      the rect: a floor at y=770 would be a floor at y=768 that the art draws at 770.

`validate --json` (added 2026-09-25 for aurora's Sonic 2 donor page; design §8 RULED block,
row-8 work). Same checks, same exit codes (0 accepted, 1 refused), and the human mode's
output is unchanged byte for byte. Instead of the human lines it prints ONE JSON document
on stdout:

    { "schema": 1,              // VALIDATE_JSON_SCHEMA; bumped on any change a reader sees
      "ok": false,              // true iff exit code 0
      "refusals": [             // [] when ok. At most ONE entry today: load() stops at the
        {                       //   first refusal. A list so that never changes the shape.
          "rule": "R7",         // the message's leading tag (R1-R12, K1-K3), or null for
                                //   the few untagged refusals (a top level that is not an
                                //   object; an engine constant this file cannot read)
          "subjects": [         // WHICH clip(s)/corridor(s). [] = an act-level refusal
            { "kind": "clip",   // "clip" or "corridor"
              "index": 1,       // position in clips.json's `clips` / `corridors` list
              "id": "cpz_s2" }  // its id, or null when it has none (not an object, no id)
          ],                    // TWO subjects for a pair rule: R10 (overlap), a duplicate
                                //   id (R3/K1) or a duplicate region_id (R3) — first
                                //   claimant first
          "message": "R7 clip 'cpz_s2': src 2048x2048 != dst ..." } ],
                                // the human sentence, EXACTLY what the human mode prints
                                //   after "clips.json REFUSED — "
      "warnings": [             // W2/W3, same {rule, subjects, message} shape, in the
        ... ] }                 //   order raised; kept even when a later rule refuses
                                //   (W3 names every clip in the mixed section)

Only a `ClipManifestError` is a refusal, in either mode. A manifest that is not JSON at all,
or a path that does not exist, raises out of the loader as it always has (traceback, exit
code 1, NO JSON on stdout): a caller must read a non-JSON stdout with exit 1 as a crash, not
as a refusal. A usage error prints USAGE (unchanged, still human) and exits 1. `--json` goes
after the manifest path, like `--donor-root`.

Usage:
    python3 tools/clip_manifest.py validate <clips.json> [--donor-root DIR] [--json]
"""

import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(REPO, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import collision_pipeline                       # noqa: E402  (R12's quantum)
import s2_donor                                  # noqa: E402
from fg_working_set import ConstantSource        # noqa: E402  (stdlib-only at import)

SCHEMA = 1

#: Where tools/s2_zone_convert.py writes converted donor zones.
#:
#: EVERY entry point that needs it takes `donor_root` and resolves this at CALL TIME, never
#: as a default-argument value bound at import. A default bound at import cannot be replaced,
#: and a caller that forgets to pass a root then reads the author's working tree silently —
#: which is exactly how two rows of tools/test_clip_manifest.py passed here and ERRORED on a
#: checkout that had never run the converter (the trees are gitignored, so absent is the
#: NORMAL state). Late resolution lets that gate point this name at a path that cannot exist,
#: so a forgotten `donor_root` fails on every machine instead of only on a clean one.
DEFAULT_DONOR_ROOT = os.path.join(REPO, "games", "sonic4", "data", "donors")


def _root(donor_root):
    return DEFAULT_DONOR_ROOT if donor_root is None else donor_root

CONSTANTS_EMP = os.path.join(REPO, "engine", "system", "constants.emp")

#: World pixels per nametable cell. Hardware (an 8x8 tile), not a policy.
TILE_PX = 8
#: World pixels per 128x128 chunk — Sonic 2's layout byte and aeon's streaming block.
CHUNK_PX = 128
#: World pixels a collision cell's height profile spans, and therefore the quantum a
#: paste must preserve (R12). READ from the module that owns the profile, never
#: restated: PROFILE_LEN is one height byte per pixel column of a 16-px block, and
#: probe_core selects the column with `world x & 15`.
COLL_QUANTUM_PX = collision_pipeline.PROFILE_LEN

#: The suite contract's region-id pattern, transcribed from
#: `empyrean:contract/schema/aurora-regions.schema.json` `$defs/region/properties/id` at
#: 0742b5ed. Act ids, clip ids and any `region_id` write-back are all held to it, so a name
#: in this file is a name aurora can use in the regions document without translating it.
REGION_ID_PATTERN = r"^[a-z][a-z0-9_]{0,31}$"
_ID_RE = re.compile(REGION_ID_PATTERN)
#: The only unit this file speaks, on both sides, declared in the file itself.
UNITS = "world_px"
_RECT_KEYS = ("x", "y", "w", "h")


#: A refusal's or warning's rule tag is the LEADING token of its message ("R7 clip ...") —
#: the header's VALIDATION RULES contract ("each is named in the message it raises or warns
#: with"). `--json` reads it back from there, so the tag has one spelling, in one place.
#: C is `tools/clip_act_bake.py`'s family (C1-C3, the collision refusals). `bake --json`
#: reads its tags through this same reader, so the two tools agree on what a tag is.
_TAG_RE = re.compile(r"^([RKWC]\d+) ")


def rule_of(message):
    """The rule tag a message leads with (e.g. "R7"), or None for an untagged one."""
    m = _TAG_RE.match(message)
    return m.group(1) if m else None


def subject(kind, index, ident):
    """One `--json` subject: which clip or corridor a refusal/warning is about.
    `ident` is None when the entry has no usable id (a non-object, a missing `id`)."""
    return {"kind": kind, "index": index, "id": ident}


def _subject_of(obj):
    return subject("clip" if isinstance(obj, Clip) else "corridor", obj.index, obj.id)


class ClipManifestError(ValueError):
    """A clips.json this loader will not hand to a bake.

    `subjects` names the clip(s)/corridor(s) the refusal is about (`subject()` dicts; empty
    for an act-level refusal) and `rule` is the message's leading tag. Neither changes the
    message: str(exc) is exactly what it always was."""

    def __init__(self, message, subjects=()):
        super().__init__(message)
        self.subjects = [dict(s) for s in subjects]

    @property
    def rule(self):
        return rule_of(str(self))


def geometry_constants(path=CONSTANTS_EMP):
    """SECTION_SIZE and MAX_ACT_SECTIONS, READ from engine source.

    Never restated here: the section is 2048 px because `engine/system/constants.emp`
    says so, and a parcel that changes it must move this validator with it.
    """
    src = ConstantSource()
    src.load_file(path)
    try:
        return {n: src.get(n) for n in ("SECTION_SIZE", "MAX_ACT_SECTIONS")}
    except (KeyError, ValueError) as exc:
        raise ClipManifestError(f"geometry constant unreadable from {path}: {exc}")


class Clip:
    """One pasted rectangle. `zone_key` is assigned by the manifest, not the file."""

    __slots__ = ("id", "donor", "zone", "src", "dst", "region_id",
                 "unaligned_dst_reason", "severed_xover_reason", "zone_key", "index")

    def __init__(self, raw, index):
        self.index = index
        self.id = raw["id"]
        self.donor = raw["donor"]
        self.zone = raw["zone"]
        self.src = tuple(int(raw["src_rect"][k]) for k in _RECT_KEYS)
        self.dst = tuple(int(raw["dst_rect"][k]) for k in _RECT_KEYS)
        self.region_id = raw.get("region_id") or None
        self.unaligned_dst_reason = raw.get("unaligned_dst_reason") or None
        self.severed_xover_reason = raw.get("severed_xover_reason") or None
        self.zone_key = -1

    @property
    def tree_key(self):
        return (self.donor, self.zone)

    def tree_dir(self, donor_root):
        return os.path.join(donor_root, self.donor, self.zone)

    def as_json(self):
        return {
            "id": self.id, "donor": self.donor, "zone": self.zone,
            "zone_key": self.zone_key,
            "src_rect": dict(zip(_RECT_KEYS, self.src)),
            "dst_rect": dict(zip(_RECT_KEYS, self.dst)),
            "region_id": self.region_id,
            "unaligned_dst_reason": self.unaligned_dst_reason,
            "severed_xover_reason": self.severed_xover_reason,
        }

    def __repr__(self):
        return f"<Clip {self.id} {self.donor}@{self.zone} src={self.src} dst={self.dst}>"


class Corridor:
    """One synthesised neutral stretch between clips (see CORRIDORS in the header)."""

    __slots__ = ("id", "dst", "floor_y", "index")

    def __init__(self, raw, index):
        self.index = index
        self.id = raw["id"]
        self.dst = tuple(int(raw["dst_rect"][k]) for k in _RECT_KEYS)
        self.floor_y = int(raw["floor_y"])

    def as_json(self):
        return {"id": self.id, "dst_rect": dict(zip(_RECT_KEYS, self.dst)),
                "floor_y": self.floor_y}

    def __repr__(self):
        return f"<Corridor {self.id} dst={self.dst} floor_y={self.floor_y}>"


#: The corridor sheet's name in the zone table. Not a donor: `tilesets()` synthesises it.
CORRIDOR_SHEET = ("corridor", "neutral")
#: The corridor sheet's three tiles (indices into `corridor_sheet()`).
CORRIDOR_TILE_BLANK, CORRIDOR_TILE_FILL, CORRIDOR_TILE_EDGE = 0, 1, 2
#: The CRAM line corridor art is drawn on. 0, the character's line, and the reason is
#: DERIVED rather than chosen: a preset palette is 96 bytes = lines 1-3 and never line 0
#: (engine/effects/palette.emp, Palette_LoadPal's contract), so line 0 is the one line no
#: region install can recolour — the corridor looks the same under both zones' palettes
#: and through the cross-fade between them. Held against the engine by
#: tools/test_clip_two_zone.py, which reads that contract out of palette.emp.
CORRIDOR_PAL_LINE = 0
#: The colours inside the line — INDICES into art/palettes/SonicAndTails.bin, the
#: character palette the boot state loads there (games/sonic4/test/ojz_scroll_test.emp
#: `BGND_Palette`). Greys, because grey belongs to neither zone: 9 = $0444 mid grey fill,
#: 1 = $0222 dark mortar line, 6 = $0EEE white and 7 = $0CAA light grey for the top edge.
#: A LOOK, and a plain default: the owner rules how the corridor looks, not this file.
CORRIDOR_COLOURS = {"fill": 9, "mortar": 1, "edge_hi": 6, "edge": 7}


def _tile_from_rows(rows):
    """A 4bpp tile from eight rows of eight colour indices (one nibble per pixel)."""
    out = bytearray()
    for row in rows:
        assert len(row) == 8
        for i in range(0, 8, 2):
            out.append(((row[i] & 0xF) << 4) | (row[i + 1] & 0xF))
    return bytes(out)


def corridor_sheet():
    """The corridor's three-tile sheet: blank, fill (a course of stone with a mortar line
    at its foot), and the floor's top edge (a white highlight over a light-grey lip)."""
    c = CORRIDOR_COLOURS
    blank = bytes(32)
    fill = _tile_from_rows([[c["fill"]] * 8] * 7 + [[c["mortar"]] * 8])
    edge = _tile_from_rows([[c["edge_hi"]] * 8, [c["edge"]] * 8]
                           + [[c["fill"]] * 8] * 5 + [[c["mortar"]] * 8])
    return blank + fill + edge


def corridor_floor_shape(bank_dir):
    """The bank's FULL SOLID BLOCK with the odd-angle ("no usable angle") flag — found, not
    typed. A full block is one whose 16 heights are all PROFILE_LEN; the odd angle makes
    probe_core substitute the cardinal angle (games/sonic4/player/player_sensors.emp,
    `btst #0, d1`), which is what a flat floor wants. In the Sonic 2 bank that is shape
    255, angle $FF — the shape Chemical Plant's own start floor is made of."""
    with open(os.path.join(bank_dir, "heightmaps.bin"), "rb") as fh:
        hm = fh.read()
    with open(os.path.join(bank_dir, "angles.bin"), "rb") as fh:
        an = fh.read()
    n = collision_pipeline.PROFILE_LEN
    for s in range(len(hm) // n - 1, 0, -1):
        if all(v == n for v in hm[s * n:(s + 1) * n]) and (an[s] & 1):
            return s
    raise ClipManifestError(
        f"the collision bank at {bank_dir} has no full solid block with the odd-angle "
        f"flag, so a corridor floor cannot be built from it")


class ClipAct:
    """A validated clips.json: the act grid, the clips, and the derived zone-key table."""

    def __init__(self, path, raw, clips, grid_w, grid_h, constants, warnings,
                 corridors=()):
        self.path = path
        self.raw = raw
        self.id = raw["id"]
        self.name = raw.get("name") or raw["id"]
        self.clips = clips
        self.corridors = list(corridors)
        self.grid_w = grid_w
        self.grid_h = grid_h
        self.constants = constants
        self.warnings = warnings

    # -- derived geometry ---------------------------------------------------
    @property
    def section_px(self):
        return self.constants["SECTION_SIZE"]

    @property
    def section_tiles(self):
        return self.constants["SECTION_SIZE"] // TILE_PX

    @property
    def cols(self):
        return self.grid_w * self.section_tiles

    @property
    def rows(self):
        return self.grid_h * self.section_tiles

    @property
    def zone_table(self):
        """[(donor, zone)] indexed by zone key, first-appearance order. DONOR zones only:
        the corridor sheet, when there is one, is `sheet_table`'s last entry."""
        out = []
        for c in self.clips:
            if c.tree_key not in out:
                out.append(c.tree_key)
        return out

    @property
    def corridor_key(self):
        """The corridor sheet's zone key (one past the donor zones), or None."""
        return len(self.zone_table) if self.corridors else None

    @property
    def sheet_table(self):
        """Every tileset the act's cells index, by zone key: the donor zones, then the
        corridor sheet if the act has a corridor."""
        return self.zone_table + ([CORRIDOR_SHEET] if self.corridors else [])

    def summary(self):
        return (f"{self.id}: {len(self.clips)} clip(s), {len(self.zone_table)} zone(s), "
                f"{len(self.corridors)} corridor(s), "
                f"act grid {self.grid_w}x{self.grid_h} sections "
                f"({self.cols}x{self.rows} cells)")


# ---------------------------------------------------------------------------
# Loading + validation
# ---------------------------------------------------------------------------

def _rect_str(r):
    return f"x={r[0]} y={r[1]} w={r[2]} h={r[3]}"


def _require_rect(where, raw, subjects=()):
    if not isinstance(raw, dict):
        raise ClipManifestError(f"R5 {where}: not an object", subjects)
    missing = [k for k in _RECT_KEYS if k not in raw]
    if missing:
        raise ClipManifestError(f"R5 {where}: missing {missing}; a rect is x, y, w, h", subjects)
    for k in _RECT_KEYS:
        v = raw[k]
        if not isinstance(v, int) or isinstance(v, bool):
            raise ClipManifestError(f"R5 {where}.{k} = {v!r} is not an integer "
                                    f"(world pixels, never a float or a string)", subjects)
        if v < 0:
            raise ClipManifestError(f"R5 {where}.{k} = {v} is negative", subjects)
    if raw["w"] <= 0 or raw["h"] <= 0:
        raise ClipManifestError(f"R5 {where}: zero-area rect ({_rect_str([raw[k] for k in _RECT_KEYS])})",
                                subjects)


def _zone_manifest(clip, donor_root):
    p = os.path.join(clip.tree_dir(donor_root), "zone.json")
    if not os.path.isfile(p):
        raise ClipManifestError(
            f"R4 clip {clip.id!r}: no converted tree at {os.path.relpath(clip.tree_dir(donor_root), REPO)} "
            f"(looked for zone.json). Convert it first:\n"
            f"    python3 tools/s2_zone_convert.py convert {clip.donor}@{clip.zone}",
            [_subject_of(clip)])
    with open(p) as fh:
        return json.load(fh)


def load(path, donor_root=None, constants=None, warn=None, warning_records=None):
    """Read and fully validate a clips.json. Returns a ClipAct or raises ClipManifestError.

    `warn` is called with each W-rule message; the messages are also kept on the
    returned ClipAct (`.warnings`) so a caller that swallowed them can still record them.
    `warning_records`, if a list, receives one `{"rule", "subjects", "message"}` dict per
    warning AS IT IS RAISED — so a caller still has them when a later rule refuses (the
    `--json` mode's warnings list).
    """
    donor_root = _root(donor_root)
    warnings = []

    def _warn(msg, subjects=()):
        warnings.append(msg)
        if warning_records is not None:
            warning_records.append({"rule": rule_of(msg),
                                    "subjects": [dict(x) for x in subjects],
                                    "message": msg})
        if warn:
            warn(msg)

    with open(path) as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict):
        raise ClipManifestError(f"{path}: top level is not an object")

    # R1
    if raw.get("schema") != SCHEMA:
        raise ClipManifestError(
            f"R1 {path}: schema {raw.get('schema')!r}, this loader reads {SCHEMA}")
    if raw.get("units") != UNITS:
        raise ClipManifestError(
            f"R1 {path}: `units` is {raw.get('units')!r}, this loader reads {UNITS!r}. Every "
            f"rectangle in this file is an integer count of world pixels on both sides; the "
            f"unit is declared here so no consumer has to convert or round.")
    if "id" not in raw or not _ID_RE.match(str(raw.get("id", ""))):
        raise ClipManifestError(
            f"R3 {path}: `id` must match {REGION_ID_PATTERN} — the suite contract's region-id "
            f"pattern (empyrean:contract/schema/aurora-regions.schema.json)")

    c = constants or geometry_constants()
    sec_px = c["SECTION_SIZE"]

    # R2
    act = raw.get("act")
    if not isinstance(act, dict) or "grid_w" not in act or "grid_h" not in act:
        raise ClipManifestError(
            f"R2 {path}: `act` must declare grid_w and grid_h (the target act's SECTION "
            f"grid). It is declared, not inferred from the clips, because the camera-window "
            f"sweep the art budget is counted over is a function of the grid.")
    grid_w, grid_h = int(act["grid_w"]), int(act["grid_h"])
    if grid_w < 1 or grid_h < 1:
        raise ClipManifestError(f"R2 {path}: act grid {grid_w}x{grid_h} has a zero axis")
    if grid_w * grid_h > c["MAX_ACT_SECTIONS"]:
        raise ClipManifestError(
            f"R2 {path}: act grid {grid_w}x{grid_h} = {grid_w * grid_h} sections > "
            f"MAX_ACT_SECTIONS {c['MAX_ACT_SECTIONS']} (engine/system/constants.emp)")

    clips_raw = raw.get("clips")
    if not isinstance(clips_raw, list) or not clips_raw:
        raise ClipManifestError(f"R3 {path}: `clips` must be a non-empty list")

    clips, seen_ids, seen_regions = [], {}, {}
    #: id -> the --json subject that first claimed it (clips and corridors share one space)
    owner = {}
    for i, cr in enumerate(clips_raw):
        if not isinstance(cr, dict):
            raise ClipManifestError(f"R3 {path}: clips[{i}] is not an object",
                                    [subject("clip", i, None)])
        raw_id = cr.get("id")
        here = [subject("clip", i, raw_id if isinstance(raw_id, str) else None)]
        for k in ("id", "donor", "zone", "src_rect", "dst_rect"):
            if k not in cr:
                raise ClipManifestError(f"R3 {path}: clips[{i}] is missing {k!r}", here)
        cid = str(cr["id"])
        here = [subject("clip", i, cid)]
        rid = cr.get("region_id") or None
        if not _ID_RE.match(cid):
            raise ClipManifestError(
                f"R3 {path}: clip id {cid!r} does not match {REGION_ID_PATTERN}. That is the "
                f"suite contract's REGION id pattern: a pasted clip becomes a region, region "
                f"ids are validated against it, and a clip id that already satisfies it is "
                f"one aurora can use verbatim — so one rectangle keeps one name across both "
                f"documents. The donor and zone names (EHZ, s2disasm) live in their own "
                f"fields, where upper case is fine.", here)
        if cid in seen_ids:
            raise ClipManifestError(
                f"R3 {path}: clip id {cid!r} used twice (clips[{seen_ids[cid]}] and clips[{i}])",
                [owner[cid]] + here)
        seen_ids[cid] = i
        owner[cid] = here[0]
        if rid is not None:
            if rid in seen_regions:
                raise ClipManifestError(
                    f"R3 {path}: region_id {rid!r} claimed by clips {seen_regions[rid]!r} and "
                    f"{cid!r}. A region is ONE rectangle in the regions document; two clips "
                    f"cannot write back the same one.",
                    [owner[seen_regions[rid]]] + here)
            seen_regions[rid] = cid
        if rid is not None and not (isinstance(rid, str) and _ID_RE.match(rid)):
            raise ClipManifestError(
                f"R3 {path}: clip {cid!r} region_id {rid!r} does not match "
                f"{REGION_ID_PATTERN}. `region_id` is aurora's WRITE-BACK of the id it "
                f"derived, not a name this file gets to invent; an id that fails the "
                f"contract's pattern is one no regions document could have carried.", here)
        if "palette" in cr:
            raise ClipManifestError(
                f"R3 {path}: clip {cid!r} carries a `palette` field. Schema 1 has none: a "
                f"region's palette comes from its REQUIRED `preset`, which names a record in "
                f"the game's effects library, and a Sonic 2 zone cannot supply that. What the "
                f"clip supplies is donors/{cr.get('donor')}/{cr.get('zone')}/palette.bin; the "
                f"preset that installs it is named at paste time.", here)
        _require_rect(f"clips[{i}].src_rect", cr["src_rect"], here)
        _require_rect(f"clips[{i}].dst_rect", cr["dst_rect"], here)
        clips.append(Clip(cr, i))

    # R4 — donor registry, then the converted tree
    for cl in clips:
        if cl.donor not in s2_donor.DONORS:
            raise ClipManifestError(
                f"R4 clip {cl.id!r}: donor {cl.donor!r} is not registered "
                f"(tools/s2_donor.py knows {', '.join(s2_donor.DONORS)})", [_subject_of(cl)])
        names = s2_donor.zone_names(cl.donor)
        if cl.zone not in names:
            raise ClipManifestError(
                f"R4 clip {cl.id!r}: donor {cl.donor} has no zone {cl.zone!r} "
                f"(it has {', '.join(names)}). Five zone names exist in both donors and "
                f"mean different levels; the donor is not a guess.", [_subject_of(cl)])

    # zone keys: distinct (donor, zone) in first-appearance order
    keys = {}
    for cl in clips:
        cl.zone_key = keys.setdefault(cl.tree_key, len(keys))

    for cl in clips:
        zm = _zone_manifest(cl, donor_root)

        # R6 — 8-px grid
        for label, rect in (("src_rect", cl.src), ("dst_rect", cl.dst)):
            for k, v in zip(_RECT_KEYS, rect):
                if v % TILE_PX:
                    raise ClipManifestError(
                        f"R6 clip {cl.id!r}: {label}.{k} = {v} is not a multiple of "
                        f"{TILE_PX} px. An editor section file is a grid of {TILE_PX}-px "
                        f"cells (tools/ojz_strip_gen.py load_editor_section_nametable); "
                        f"there is no sub-tile addressing to round to.", [_subject_of(cl)])

        # R7 — a clip is a paste, not a scale
        if cl.src[2:] != cl.dst[2:]:
            raise ClipManifestError(
                f"R7 clip {cl.id!r}: src {cl.src[2]}x{cl.src[3]} != dst {cl.dst[2]}x{cl.dst[3]}. "
                f"A clip is a paste; nothing in this pipeline rescales nametable cells.",
                [_subject_of(cl)])

        # R8 — inside the declared act
        if cl.dst[0] + cl.dst[2] > grid_w * sec_px or cl.dst[1] + cl.dst[3] > grid_h * sec_px:
            raise ClipManifestError(
                f"R8 clip {cl.id!r}: dst_rect ({_rect_str(cl.dst)}) runs past the declared "
                f"{grid_w}x{grid_h}-section act ({grid_w * sec_px}x{grid_h * sec_px} px)",
                [_subject_of(cl)])

        # R9 — inside the donor's CROP, not merely its padded grid
        x0, x1, y0, y1 = (int(v) for v in zm["extent"]["crop_tiles"])
        cx0, cy0 = x0 * TILE_PX, y0 * TILE_PX
        cx1, cy1 = x1 * TILE_PX, y1 * TILE_PX
        if (cl.src[0] < cx0 or cl.src[1] < cy0
                or cl.src[0] + cl.src[2] > cx1 or cl.src[1] + cl.src[3] > cy1):
            raise ClipManifestError(
                f"R9 clip {cl.id!r}: src_rect ({_rect_str(cl.src)}) is not inside "
                f"{cl.donor}@{cl.zone}'s camera-box crop "
                f"(x {cx0}..{cx1}, y {cy0}..{cy1} px, from that tree's zone.json). "
                f"Outside the crop there is only the converter's zero padding; a rect that "
                f"runs past it is a clip that reads smaller than it looks.", [_subject_of(cl)])

        # R11 — the design's §2.2 section-boundary recommendation, opt-out in the file
        if cl.dst[0] % sec_px or cl.dst[1] % sec_px:
            if not cl.unaligned_dst_reason:
                raise ClipManifestError(
                    f"R11 clip {cl.id!r}: dst_rect origin ({cl.dst[0]}, {cl.dst[1]}) is not "
                    f"on a {sec_px}-px section boundary. Section-aligned placement is the "
                    f"design's §2.2 default, and what it buys (MEASURED, see W3 and "
                    f"tools/clip_act_bake.py measure-alignment) is a smaller per-section local "
                    f"tile map: one section carries ONE 11-bit local map capped at 2047 "
                    f"entries, and a section holding two zones needs the sum of both. It "
                    f"does NOT buy a better camera-window page budget — that measured the "
                    f"same either way. Finer placement is available: set "
                    f"\"unaligned_dst_reason\" on this clip to the argument for it, and it "
                    f"will be carried into the bake's clipact.json.", [_subject_of(cl)])

        # R12 — the collision quantum. W1's replacement; see the rule table.
        shift = (cl.dst[0] - cl.src[0], cl.dst[1] - cl.src[1])
        if any(v % COLL_QUANTUM_PX for v in shift):
            raise ClipManifestError(
                f"R12 clip {cl.id!r}: the paste shifts the clip by "
                f"({shift[0]}, {shift[1]}) px, and collision is only correct when BOTH "
                f"axes shift by a multiple of {COLL_QUANTUM_PX}. DERIVED, not a "
                f"convention: a collision cell's height profile is {COLL_QUANTUM_PX} "
                f"bytes covering a {COLL_QUANTUM_PX}-px block, and the runtime picks the "
                f"column with `andi.w #$F, d0` on the WORLD x "
                f"(games/sonic4/player/player_sensors.emp probe_core); the row is picked "
                f"the same way in y (`lsr.w #1` of the tile row, "
                f"engine/level/collision_lookup.emp). Shift the data by 8 px and every "
                f"probe reads the wrong half of the profile while the ART, which is one "
                f"word per 8-px cell, moves correctly — so this fails as ground that is "
                f"8 px out of place, not as anything that looks broken in a screenshot. "
                f"Move src_rect or dst_rect so the difference is a multiple of "
                f"{COLL_QUANTUM_PX} in both axes.", [_subject_of(cl)])

        # W2 — an all-blank clip
        bbox = zm["extent"].get("painted_bbox_tiles")
        if bbox:
            bx0, bx1, by0, by1 = (int(v) * TILE_PX for v in bbox)
            if (cl.src[0] >= bx1 or cl.src[0] + cl.src[2] <= bx0
                    or cl.src[1] >= by1 or cl.src[1] + cl.src[3] <= by0):
                _warn(f"W2 clip {cl.id!r}: src_rect ({_rect_str(cl.src)}) does not meet "
                      f"{cl.donor}@{cl.zone}'s painted bounding box "
                      f"(x {bx0}..{bx1}, y {by0}..{by1} px) — this clip is entirely blank.",
                      [_subject_of(cl)])

    # K1-K3 — corridors (see CORRIDORS in the header)
    corridors = []
    corr_raw = raw.get("corridors", [])
    if not isinstance(corr_raw, list):
        raise ClipManifestError(f"K1 {path}: `corridors` must be a list")
    for i, kr in enumerate(corr_raw):
        if not isinstance(kr, dict):
            raise ClipManifestError(f"K1 {path}: corridors[{i}] is not an object",
                                    [subject("corridor", i, None)])
        raw_id = kr.get("id")
        here = [subject("corridor", i, raw_id if isinstance(raw_id, str) else None)]
        for k in ("id", "dst_rect", "floor_y"):
            if k not in kr:
                raise ClipManifestError(f"K1 {path}: corridors[{i}] is missing {k!r}", here)
        kid = str(kr["id"])
        here = [subject("corridor", i, kid)]
        if not _ID_RE.match(kid):
            raise ClipManifestError(
                f"K1 {path}: corridor id {kid!r} does not match {REGION_ID_PATTERN} — a "
                f"corridor is a place in the act exactly as a clip is, and its id is held to "
                f"the same region-id pattern", here)
        if kid in seen_ids:
            raise ClipManifestError(
                f"K1 {path}: corridor id {kid!r} is already used by clips[{seen_ids[kid]}] "
                f"or an earlier corridor; one name is one rectangle", [owner[kid]] + here)
        seen_ids[kid] = f"corridors[{i}]"
        owner[kid] = here[0]
        _require_rect(f"corridors[{i}].dst_rect", kr["dst_rect"], here)
        co = Corridor(kr, i)
        for k, v in zip(_RECT_KEYS, co.dst):
            if v % TILE_PX:
                raise ClipManifestError(
                    f"K2 corridor {kid!r}: dst_rect.{k} = {v} is not a multiple of "
                    f"{TILE_PX} px (the editor cell grid, R6's reason)", here)
        if co.dst[0] + co.dst[2] > grid_w * sec_px or co.dst[1] + co.dst[3] > grid_h * sec_px:
            raise ClipManifestError(
                f"K2 corridor {kid!r}: dst_rect ({_rect_str(co.dst)}) runs past the declared "
                f"{grid_w}x{grid_h}-section act ({grid_w * sec_px}x{grid_h * sec_px} px)", here)
        fy = kr["floor_y"]
        if not isinstance(fy, int) or isinstance(fy, bool):
            raise ClipManifestError(f"K3 corridor {kid!r}: floor_y = {fy!r} is not an integer",
                                    here)
        if fy % COLL_QUANTUM_PX or not (co.dst[1] <= fy < co.dst[1] + co.dst[3]):
            raise ClipManifestError(
                f"K3 corridor {kid!r}: floor_y = {fy} must be a multiple of "
                f"{COLL_QUANTUM_PX} (a collision row: the runtime picks the row with "
                f"`lsr.w #1` of the tile row, engine/level/collision_lookup.emp) and lie "
                f"inside the rect's y span {co.dst[1]}..{co.dst[1] + co.dst[3] - 1}. A floor "
                f"off the collision grid would be drawn at one y and stood on at another.", here)
        corridors.append(co)

    # R10 / K2 — dst overlap, over clips AND corridors
    placed = list(clips) + corridors
    for i, a in enumerate(placed):
        for b in placed[i + 1:]:
            if (a.dst[0] < b.dst[0] + b.dst[2] and b.dst[0] < a.dst[0] + a.dst[2]
                    and a.dst[1] < b.dst[1] + b.dst[3] and b.dst[1] < a.dst[1] + a.dst[3]):
                raise ClipManifestError(
                    f"R10 clips {a.id!r} ({_rect_str(a.dst)}) and {b.id!r} "
                    f"({_rect_str(b.dst)}) overlap in the act. Whichever the bake wrote "
                    f"second would silently win; say which one you meant.",
                    [_subject_of(a), _subject_of(b)])

    # W3 — sections holding more than one zone key. A warning, not a refusal: the only
    # cost MEASURED is the section's local tile map, and the exact limit on that lives
    # downstream in ojz_strip_gen.build_section_local_map, which raises past 2047.
    per_section = {}
    for cl in clips:
        sx0, sy0 = cl.dst[0] // sec_px, cl.dst[1] // sec_px
        sx1 = (cl.dst[0] + cl.dst[2] - 1) // sec_px
        sy1 = (cl.dst[1] + cl.dst[3] - 1) // sec_px
        for sy in range(sy0, sy1 + 1):
            for sx in range(sx0, sx1 + 1):
                per_section.setdefault(sy * grid_w + sx, []).append(cl)
    for n, members in sorted(per_section.items()):
        zk = {m.zone_key for m in members}
        if len(zk) > 1:
            who = ", ".join(f"{m.id!r} ({'/'.join(m.tree_key)})" for m in members)
            _warn(f"W3 act section {n} holds {len(zk)} zones: {who}. One section carries "
                  f"ONE local tile map — a single 11-bit space capped at 2047 entries "
                  f"(ojz_strip_gen.build_section_local_map) — and a mixed section needs "
                  f"the sum of both zones' tiles in it. The bake prints the map size per "
                  f"section and refuses past the cap.", [_subject_of(m) for m in members])

    return ClipAct(path, raw, clips, grid_w, grid_h, c, warnings, corridors)


# ---------------------------------------------------------------------------
# Cell grids — the per-cell tileset key, and the words it keys
# ---------------------------------------------------------------------------

def section_word_grid(tree_dir, manifest, section_tiles):
    """One converted zone's whole word grid, (grid_h*st, grid_w*st) uint16.

    Reassembled from the tree's section files exactly as tools/s2_zone_convert.read_tree_words
    does (flat row-major N = sy * grid_w + sx). Imported rather than re-derived would be
    circular: that function is the converter's own verification path.
    """
    import numpy as np
    gw, gh = manifest["grid"]["w"], manifest["grid"]["h"]
    out = np.zeros((gh * section_tiles, gw * section_tiles), dtype=np.uint16)
    for sy in range(gh):
        for sx in range(gw):
            n = sy * gw + sx
            p = os.path.join(tree_dir, f"section_{n}.tiles.bin")
            with open(p, "rb") as fh:
                data = fh.read()
            want = section_tiles * section_tiles * 2
            if len(data) != want:
                raise ClipManifestError(f"{p}: {len(data)} bytes, expected {want}")
            out[sy * section_tiles:(sy + 1) * section_tiles,
                sx * section_tiles:(sx + 1) * section_tiles] = \
                np.frombuffer(data, dtype=">u2").reshape(section_tiles, section_tiles)
    return out


def cell_grids(act, donor_root=None):
    """(words, zone_id) for the whole target act.

    words   (rows, cols) uint16 — each clip's OWN nametable words, unmodified. A word's
            11-bit index means "tile N of the tileset of the zone `zone_id` names".
    zone_id (rows, cols) int16  — the per-cell tileset key. -1 = VOID: no clip covers this
            cell. VOID is not zone 0: `fg_page_order.zone_split` and
            `megaact_window_pageset.Act` both read -1 as "no zone", and a void cell that
            claimed zone 0 would put blank cells into a zone's page group.
    """
    import numpy as np
    donor_root = _root(donor_root)
    st = act.section_tiles
    words = np.zeros((act.rows, act.cols), dtype=np.uint16)
    zone_id = np.full((act.rows, act.cols), -1, dtype=np.int16)
    cache = {}
    for cl in act.clips:
        if cl.tree_key not in cache:
            zm = _zone_manifest(cl, donor_root)
            cache[cl.tree_key] = (section_word_grid(cl.tree_dir(donor_root), zm, st), zm)
        src_words, _zm = cache[cl.tree_key]
        sx, sy, sw, sh = (v // TILE_PX for v in cl.src)
        dx, dy = cl.dst[0] // TILE_PX, cl.dst[1] // TILE_PX
        words[dy:dy + sh, dx:dx + sw] = src_words[sy:sy + sh, sx:sx + sw]
        zone_id[dy:dy + sh, dx:dx + sw] = cl.zone_key
    for co in act.corridors:
        cw, ck = corridor_cells(co)
        dx, dy, w, h = (v // TILE_PX for v in co.dst)
        words[dy:dy + h, dx:dx + w] = cw
        zone_id[dy:dy + h, dx:dx + w] = act.corridor_key
    return words, zone_id


def corridor_cells(co):
    """(words, None) for one corridor's rect: blank above the floor, the edge tile ON the
    floor row, the fill below it — all on CORRIDOR_PAL_LINE, priority 0, unflipped."""
    import numpy as np
    w, h = co.dst[2] // TILE_PX, co.dst[3] // TILE_PX
    out = np.full((h, w), CORRIDOR_TILE_BLANK, dtype=np.uint16)
    floor_row = (co.floor_y - co.dst[1]) // TILE_PX
    pal = CORRIDOR_PAL_LINE << 13
    out[floor_row, :] = CORRIDOR_TILE_EDGE | pal
    out[floor_row + 1:, :] = CORRIDOR_TILE_FILL | pal
    return out, None


def section_plane_grid(tree_dir, manifest, section_tiles, suffix):
    """One converted zone's whole COLLISION plane grid, (grid_h*st, grid_w*st) uint16.

    `suffix` is "collattr" (plane A) or "collattrb" (plane B). Same reassembly as
    `section_word_grid` — a plane file is the same shape as a tiles file on purpose
    (`tools/s2_zone_convert.py` rule 5), so a clip rectangle slices all three grids
    with one pair of indices.
    """
    import numpy as np
    gw, gh = manifest["grid"]["w"], manifest["grid"]["h"]
    out = np.zeros((gh * section_tiles, gw * section_tiles), dtype=np.uint16)
    for sy in range(gh):
        for sx in range(gw):
            n = sy * gw + sx
            p = os.path.join(tree_dir, f"section_{n}.{suffix}.bin")
            if not os.path.isfile(p):
                raise ClipManifestError(
                    f"{p} is missing. A converted donor tree carries both collision "
                    f"planes since S2-COMPRESSED-ACT row 5; a tree without them was "
                    f"written by the row-2 converter and is stale. Re-run "
                    f"tools/s2_zone_convert.py convert.")
            with open(p, "rb") as fh:
                data = fh.read()
            want = section_tiles * section_tiles * 2
            if len(data) != want:
                raise ClipManifestError(f"{p}: {len(data)} bytes, expected {want}")
            out[sy * section_tiles:(sy + 1) * section_tiles,
                sx * section_tiles:(sx + 1) * section_tiles] = \
                np.frombuffer(data, dtype=">u2").reshape(section_tiles, section_tiles)
    return out


def collision_grids(act, donor_root=None):
    """(plane_a, plane_b) for the whole target act — the collision twin of `cell_grids`.

    Same rectangles, same order, same VOID rule: a cell no clip covers is word 0,
    which is air on both planes. Row 5's §8 hand-off says the clip rectangles come
    from here rather than being re-derived, so this shares `cell_grids`' loop
    shape deliberately.

    Each word is an AURORA per-plane cell word whose low 10 bits index the donor's
    base bank — `zone.json`'s `collision.base_bank`, NOT the S&K bank — so a caller
    that bakes these must select that bank. `collision_banks()` returns it.
    """
    import numpy as np
    donor_root = _root(donor_root)
    st = act.section_tiles
    planes = [np.zeros((act.rows, act.cols), dtype=np.uint16) for _ in range(2)]
    cache = {}
    for cl in act.clips:
        if cl.tree_key not in cache:
            zm = _zone_manifest(cl, donor_root)
            d = cl.tree_dir(donor_root)
            cache[cl.tree_key] = tuple(
                section_plane_grid(d, zm, st, s) for s in ("collattr", "collattrb"))
        src = cache[cl.tree_key]
        sx, sy, sw, sh = (v // TILE_PX for v in cl.src)
        dx, dy = cl.dst[0] // TILE_PX, cl.dst[1] // TILE_PX
        for p in range(2):
            planes[p][dy:dy + sh, dx:dx + sw] = src[p][sy:sy + sh, sx:sx + sw]
    if act.corridors:
        word = (corridor_floor_shape(collision_banks(act, donor_root))
                | (collision_pipeline.SOL_ALL << collision_pipeline.PLANE_SOL_SHIFT))
        for co in act.corridors:
            dx, dy, w, h = (v // TILE_PX for v in co.dst)
            floor_row = (co.floor_y - co.dst[1]) // TILE_PX
            for p in range(2):
                planes[p][dy + floor_row:dy + h, dx:dx + w] = word
    return planes[0], planes[1]


def collision_banks(act, donor_root=None):
    """The base collision bank directory every clip's zone names, as ONE path.

    REFUSES an act whose zones disagree. Nothing today can produce one — both S2
    donors share one shape vocabulary byte for byte (parcel 4) — but the attr set
    is act-wide and a single byte in it is a shape index, so two banks in one act
    would mean one index standing for two shapes with nothing to say which. A
    refusal is the only honest answer, and it is here rather than discovered in the
    bake's output.
    """
    donor_root = _root(donor_root)
    banks = {}
    for cl in act.clips:
        zm = _zone_manifest(cl, donor_root)
        coll = zm.get("collision")
        if not coll or not coll.get("base_bank"):
            raise ClipManifestError(
                f"clip {cl.id!r}: {'/'.join(cl.tree_key)}'s zone.json names no "
                f"collision base bank. That tree predates S2-COMPRESSED-ACT row 5; "
                f"re-run tools/s2_zone_convert.py convert.")
        banks.setdefault(os.path.join(REPO, coll["base_bank"]), []).append(cl.id)
    if len(banks) > 1:
        detail = "; ".join(f"{b} <- {', '.join(ids)}" for b, ids in sorted(banks.items()))
        raise ClipManifestError(
            f"this act's clips name {len(banks)} different collision base banks "
            f"({detail}). One act has ONE attr set and a shape index inside it means "
            f"one shape; two banks would make the same index mean two.")
    return next(iter(banks))


def tilesets(act, donor_root=None):
    """[(donor, zone, tileset bytes, zone.json)] indexed by zone key — `sheet_table`'s
    order, so the corridor sheet (synthesised, with a zone.json-shaped stand-in naming its
    sha and no palette) is last when the act has a corridor."""
    donor_root = _root(donor_root)
    out = []
    for donor, zone in act.zone_table:
        d = os.path.join(donor_root, donor, zone)
        with open(os.path.join(d, "zone.json")) as fh:
            zm = json.load(fh)
        with open(os.path.join(d, "tileset.bin"), "rb") as fh:
            blob = fh.read()
        if len(blob) != zm["tileset"]["bytes"]:
            raise ClipManifestError(
                f"{d}/tileset.bin is {len(blob)} bytes but its zone.json says "
                f"{zm['tileset']['bytes']} — the converted tree is inconsistent; re-run "
                f"tools/s2_zone_convert.py convert {donor}@{zone}")
        out.append((donor, zone, blob, zm))
    if act.corridors:
        import hashlib
        blob = corridor_sheet()
        out.append((CORRIDOR_SHEET[0], CORRIDOR_SHEET[1], blob,
                    {"tileset": {"bytes": len(blob),
                                 "sha256": hashlib.sha256(blob).hexdigest()},
                     "palette": None,
                     "synthesised": "clip_manifest.corridor_sheet()"}))
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

USAGE = "Usage: python3 tools/clip_manifest.py validate <clips.json> [--donor-root DIR]"


#: `validate --json` document schema. Bump it on any change a vendored reader could notice.
VALIDATE_JSON_SCHEMA = 1


def refusal_record(exc):
    """One `--json` refusal entry, `{rule, subjects, message}`, from a refusal exception.

    Shared by `validate --json` and `tools/clip_act_bake.py bake --json`, so the two
    documents cannot drift apart. `exc` is a ClipManifestError or the bake's ClipBakeError;
    both carry `.rule` (the message's leading tag, or None) and `.subjects`."""
    return {"rule": exc.rule, "subjects": [dict(s) for s in exc.subjects],
            "message": str(exc)}


def json_text(doc):
    """How every clip tool prints its `--json` document: ONE document, indent 2, sorted
    keys, ASCII-escaped (json.dumps' default)."""
    return json.dumps(doc, indent=2, sort_keys=True)


def validate_json(path, donor_root=None):
    """(the `validate --json` document, exit code). See "--json" in the module header."""
    warnings = []
    doc = {"schema": VALIDATE_JSON_SCHEMA, "ok": False, "refusals": [], "warnings": warnings}
    try:
        load(path, donor_root=_root(donor_root), warning_records=warnings)
    except ClipManifestError as exc:
        doc["refusals"].append(refusal_record(exc))
        return doc, 1
    doc["ok"] = True
    return doc, 0


def _mode_validate(rest):
    if not rest:
        print(USAGE)
        return 1
    path, root, as_json = rest[0], None, False
    extra = rest[1:]
    while extra:
        if extra[0] == "--donor-root" and len(extra) > 1:
            root = extra[1]
            extra = extra[2:]
        elif extra[0] == "--json":
            as_json = True
            extra = extra[1:]
        else:
            print(f"ERROR: unknown argument {extra[0]!r}")
            print(USAGE)
            return 1
    if as_json:
        doc, rc = validate_json(path, root)
        print(json_text(doc))
        return rc
    try:
        act = load(path, donor_root=_root(root), warn=lambda m: print(f"  WARNING: {m}"))
    except ClipManifestError as exc:
        print(f"clips.json REFUSED — {exc}")
        return 1
    print(f"clips.json OK — {act.summary()}")
    for i, (donor, zone) in enumerate(act.zone_table):
        ids = [c.id for c in act.clips if c.tree_key == (donor, zone)]
        print(f"  zone key {i}: {donor}@{zone}  clips {ids}")
    for cl in act.clips:
        note = ""
        if cl.unaligned_dst_reason:
            note = f"  [R11 opt-out: {cl.unaligned_dst_reason}]"
        print(f"  {cl.id}: src {_rect_str(cl.src)} -> dst {_rect_str(cl.dst)}{note}")
    for co in act.corridors:
        print(f"  corridor {co.id}: dst {_rect_str(co.dst)}, floor y={co.floor_y} "
              f"(zone key {act.corridor_key}, synthesised)")
    print(f"  {len(act.warnings)} warning(s)")
    return 0


MODES = {"validate": _mode_validate}


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    handler = MODES.get(args[0] if args else None)
    if handler is None:
        print(USAGE)
        sys.exit(1)
    return handler(args[1:])


if __name__ == "__main__":
    sys.exit(main())
