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
  W1  src rect coordinates are not multiples of 128 px (the chunk quantum both games
      share). Warning ONLY at this parcel: nothing on the ART path cares, because a
      nametable word is per cell. It is the COLLISION path that is authored per 128-px
      chunk, so upgrading W1 to a refusal is staged-plan row 5's call, with its evidence.
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

Usage:
    python3 tools/clip_manifest.py validate <clips.json> [--donor-root DIR]
"""

import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(REPO, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import s2_donor                                  # noqa: E402
from fg_working_set import ConstantSource        # noqa: E402  (stdlib-only at import)

SCHEMA = 1

#: Where tools/s2_zone_convert.py writes converted donor zones.
DEFAULT_DONOR_ROOT = os.path.join(REPO, "games", "sonic4", "data", "donors")

CONSTANTS_EMP = os.path.join(REPO, "engine", "system", "constants.emp")

#: World pixels per nametable cell. Hardware (an 8x8 tile), not a policy.
TILE_PX = 8
#: World pixels per 128x128 chunk — Sonic 2's layout byte and aeon's streaming block.
CHUNK_PX = 128

#: The suite contract's region-id pattern, transcribed from
#: `empyrean:contract/schema/aurora-regions.schema.json` `$defs/region/properties/id` at
#: 0742b5ed. Act ids, clip ids and any `region_id` write-back are all held to it, so a name
#: in this file is a name aurora can use in the regions document without translating it.
REGION_ID_PATTERN = r"^[a-z][a-z0-9_]{0,31}$"
_ID_RE = re.compile(REGION_ID_PATTERN)
#: The only unit this file speaks, on both sides, declared in the file itself.
UNITS = "world_px"
_RECT_KEYS = ("x", "y", "w", "h")


class ClipManifestError(ValueError):
    """A clips.json this loader will not hand to a bake."""


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
                 "unaligned_dst_reason", "zone_key", "index")

    def __init__(self, raw, index):
        self.index = index
        self.id = raw["id"]
        self.donor = raw["donor"]
        self.zone = raw["zone"]
        self.src = tuple(int(raw["src_rect"][k]) for k in _RECT_KEYS)
        self.dst = tuple(int(raw["dst_rect"][k]) for k in _RECT_KEYS)
        self.region_id = raw.get("region_id") or None
        self.unaligned_dst_reason = raw.get("unaligned_dst_reason") or None
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
        }

    def __repr__(self):
        return f"<Clip {self.id} {self.donor}@{self.zone} src={self.src} dst={self.dst}>"


class ClipAct:
    """A validated clips.json: the act grid, the clips, and the derived zone-key table."""

    def __init__(self, path, raw, clips, grid_w, grid_h, constants, warnings):
        self.path = path
        self.raw = raw
        self.id = raw["id"]
        self.name = raw.get("name") or raw["id"]
        self.clips = clips
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
        """[(donor, zone)] indexed by zone key, first-appearance order."""
        out = []
        for c in self.clips:
            if c.tree_key not in out:
                out.append(c.tree_key)
        return out

    def summary(self):
        return (f"{self.id}: {len(self.clips)} clip(s), {len(self.zone_table)} zone(s), "
                f"act grid {self.grid_w}x{self.grid_h} sections "
                f"({self.cols}x{self.rows} cells)")


# ---------------------------------------------------------------------------
# Loading + validation
# ---------------------------------------------------------------------------

def _rect_str(r):
    return f"x={r[0]} y={r[1]} w={r[2]} h={r[3]}"


def _require_rect(where, raw):
    if not isinstance(raw, dict):
        raise ClipManifestError(f"R5 {where}: not an object")
    missing = [k for k in _RECT_KEYS if k not in raw]
    if missing:
        raise ClipManifestError(f"R5 {where}: missing {missing}; a rect is x, y, w, h")
    for k in _RECT_KEYS:
        v = raw[k]
        if not isinstance(v, int) or isinstance(v, bool):
            raise ClipManifestError(f"R5 {where}.{k} = {v!r} is not an integer "
                                    f"(world pixels, never a float or a string)")
        if v < 0:
            raise ClipManifestError(f"R5 {where}.{k} = {v} is negative")
    if raw["w"] <= 0 or raw["h"] <= 0:
        raise ClipManifestError(f"R5 {where}: zero-area rect ({_rect_str([raw[k] for k in _RECT_KEYS])})")


def _zone_manifest(clip, donor_root):
    p = os.path.join(clip.tree_dir(donor_root), "zone.json")
    if not os.path.isfile(p):
        raise ClipManifestError(
            f"R4 clip {clip.id!r}: no converted tree at {os.path.relpath(clip.tree_dir(donor_root), REPO)} "
            f"(looked for zone.json). Convert it first:\n"
            f"    python3 tools/s2_zone_convert.py convert {clip.donor}@{clip.zone}")
    with open(p) as fh:
        return json.load(fh)


def load(path, donor_root=DEFAULT_DONOR_ROOT, constants=None, warn=None):
    """Read and fully validate a clips.json. Returns a ClipAct or raises ClipManifestError.

    `warn` is called with each W-rule message; the messages are also kept on the
    returned ClipAct (`.warnings`) so a caller that swallowed them can still record them.
    """
    warnings = []

    def _warn(msg):
        warnings.append(msg)
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
    for i, cr in enumerate(clips_raw):
        if not isinstance(cr, dict):
            raise ClipManifestError(f"R3 {path}: clips[{i}] is not an object")
        for k in ("id", "donor", "zone", "src_rect", "dst_rect"):
            if k not in cr:
                raise ClipManifestError(f"R3 {path}: clips[{i}] is missing {k!r}")
        cid = str(cr["id"])
        rid = cr.get("region_id") or None
        if not _ID_RE.match(cid):
            raise ClipManifestError(
                f"R3 {path}: clip id {cid!r} does not match {REGION_ID_PATTERN}. That is the "
                f"suite contract's REGION id pattern: a pasted clip becomes a region, region "
                f"ids are validated against it, and a clip id that already satisfies it is "
                f"one aurora can use verbatim — so one rectangle keeps one name across both "
                f"documents. The donor and zone names (EHZ, s2disasm) live in their own "
                f"fields, where upper case is fine.")
        if cid in seen_ids:
            raise ClipManifestError(
                f"R3 {path}: clip id {cid!r} used twice (clips[{seen_ids[cid]}] and clips[{i}])")
        seen_ids[cid] = i
        if rid is not None:
            if rid in seen_regions:
                raise ClipManifestError(
                    f"R3 {path}: region_id {rid!r} claimed by clips {seen_regions[rid]!r} and "
                    f"{cid!r}. A region is ONE rectangle in the regions document; two clips "
                    f"cannot write back the same one.")
            seen_regions[rid] = cid
        if rid is not None and not (isinstance(rid, str) and _ID_RE.match(rid)):
            raise ClipManifestError(
                f"R3 {path}: clip {cid!r} region_id {rid!r} does not match "
                f"{REGION_ID_PATTERN}. `region_id` is aurora's WRITE-BACK of the id it "
                f"derived, not a name this file gets to invent; an id that fails the "
                f"contract's pattern is one no regions document could have carried.")
        if "palette" in cr:
            raise ClipManifestError(
                f"R3 {path}: clip {cid!r} carries a `palette` field. Schema 1 has none: a "
                f"region's palette comes from its REQUIRED `preset`, which names a record in "
                f"the game's effects library, and a Sonic 2 zone cannot supply that. What the "
                f"clip supplies is donors/{cr.get('donor')}/{cr.get('zone')}/palette.bin; the "
                f"preset that installs it is named at paste time.")
        _require_rect(f"clips[{i}].src_rect", cr["src_rect"])
        _require_rect(f"clips[{i}].dst_rect", cr["dst_rect"])
        clips.append(Clip(cr, i))

    # R4 — donor registry, then the converted tree
    for cl in clips:
        if cl.donor not in s2_donor.DONORS:
            raise ClipManifestError(
                f"R4 clip {cl.id!r}: donor {cl.donor!r} is not registered "
                f"(tools/s2_donor.py knows {', '.join(s2_donor.DONORS)})")
        names = s2_donor.zone_names(cl.donor)
        if cl.zone not in names:
            raise ClipManifestError(
                f"R4 clip {cl.id!r}: donor {cl.donor} has no zone {cl.zone!r} "
                f"(it has {', '.join(names)}). Five zone names exist in both donors and "
                f"mean different levels; the donor is not a guess.")

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
                        f"there is no sub-tile addressing to round to.")

        # R7 — a clip is a paste, not a scale
        if cl.src[2:] != cl.dst[2:]:
            raise ClipManifestError(
                f"R7 clip {cl.id!r}: src {cl.src[2]}x{cl.src[3]} != dst {cl.dst[2]}x{cl.dst[3]}. "
                f"A clip is a paste; nothing in this pipeline rescales nametable cells.")

        # R8 — inside the declared act
        if cl.dst[0] + cl.dst[2] > grid_w * sec_px or cl.dst[1] + cl.dst[3] > grid_h * sec_px:
            raise ClipManifestError(
                f"R8 clip {cl.id!r}: dst_rect ({_rect_str(cl.dst)}) runs past the declared "
                f"{grid_w}x{grid_h}-section act ({grid_w * sec_px}x{grid_h * sec_px} px)")

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
                f"runs past it is a clip that reads smaller than it looks.")

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
                    f"will be carried into the bake's clipact.json.")

        # W1 — the 128-px chunk quantum: art does not care, collision will
        if any(v % CHUNK_PX for v in cl.src):
            _warn(f"W1 clip {cl.id!r}: src_rect ({_rect_str(cl.src)}) is not 128-px "
                  f"chunk-aligned. Harmless on the ART path (a nametable word is per cell), "
                  f"but Sonic 2 authors collision per 128-px chunk, so staged-plan row 5 may "
                  f"turn this into a refusal.")

        # W2 — an all-blank clip
        bbox = zm["extent"].get("painted_bbox_tiles")
        if bbox:
            bx0, bx1, by0, by1 = (int(v) * TILE_PX for v in bbox)
            if (cl.src[0] >= bx1 or cl.src[0] + cl.src[2] <= bx0
                    or cl.src[1] >= by1 or cl.src[1] + cl.src[3] <= by0):
                _warn(f"W2 clip {cl.id!r}: src_rect ({_rect_str(cl.src)}) does not meet "
                      f"{cl.donor}@{cl.zone}'s painted bounding box "
                      f"(x {bx0}..{bx1}, y {by0}..{by1} px) — this clip is entirely blank.")

    # R10 — dst overlap
    for i, a in enumerate(clips):
        for b in clips[i + 1:]:
            if (a.dst[0] < b.dst[0] + b.dst[2] and b.dst[0] < a.dst[0] + a.dst[2]
                    and a.dst[1] < b.dst[1] + b.dst[3] and b.dst[1] < a.dst[1] + a.dst[3]):
                raise ClipManifestError(
                    f"R10 clips {a.id!r} ({_rect_str(a.dst)}) and {b.id!r} "
                    f"({_rect_str(b.dst)}) overlap in the act. Whichever the bake wrote "
                    f"second would silently win; say which one you meant.")

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
                  f"section and refuses past the cap.")

    return ClipAct(path, raw, clips, grid_w, grid_h, c, warnings)


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


def cell_grids(act, donor_root=DEFAULT_DONOR_ROOT):
    """(words, zone_id) for the whole target act.

    words   (rows, cols) uint16 — each clip's OWN nametable words, unmodified. A word's
            11-bit index means "tile N of the tileset of the zone `zone_id` names".
    zone_id (rows, cols) int16  — the per-cell tileset key. -1 = VOID: no clip covers this
            cell. VOID is not zone 0: `fg_page_order.zone_split` and
            `megaact_window_pageset.Act` both read -1 as "no zone", and a void cell that
            claimed zone 0 would put blank cells into a zone's page group.
    """
    import numpy as np
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
    return words, zone_id


def tilesets(act, donor_root=DEFAULT_DONOR_ROOT):
    """[(donor, zone, tileset bytes, zone.json)] indexed by zone key."""
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
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

USAGE = "Usage: python3 tools/clip_manifest.py validate <clips.json> [--donor-root DIR]"


def _mode_validate(rest):
    if not rest:
        print(USAGE)
        return 1
    path, root = rest[0], DEFAULT_DONOR_ROOT
    extra = rest[1:]
    while extra:
        if extra[0] == "--donor-root" and len(extra) > 1:
            root = extra[1]
            extra = extra[2:]
        else:
            print(f"ERROR: unknown argument {extra[0]!r}")
            print(USAGE)
            return 1
    try:
        act = load(path, donor_root=root, warn=lambda m: print(f"  WARNING: {m}"))
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
