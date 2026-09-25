#!/usr/bin/env python3
"""clip_rom_bake.py — a clip act, in the format the ROM reads.

S2-COMPRESSED-ACT staged plan row 6, the first parcel that produces a picture
(`docs/research/2026-09-17-s2-compressed-act-design.md` §10 row 6). Parcel 5 named
exactly what row 6 inherits: *"What is still missing is the BLOCK STREAM. Nothing here
exercises `ojz_block_gen` or S4LZ. `sec{N}_blocks.bin` is where the collision planes
and the art meet in the format the ROM reads."* This is that.

────────────────────────────────────────────────────────────────────────────────
HOW A SECOND ACT COEXISTS WITH THE SHIPPED ONE — and why it is a THROWAWAY
────────────────────────────────────────────────────────────────────────────────

The shipped act's bytes must not move. Three mechanisms were available (the owner
named all three): a separate game, a second act entry, a build-time selection. This
is the third, in the shape the repo already has for exactly this problem —
build.sh's STRESS_ART: an off-canonical DEV shape that RE-BAKES THE ONE ACT SLOT IN
PLACE under an EXIT trap that restores the committed tree from git.

WHY NOT A SECOND ACT ENTRY. sigil places the generated `.emp` modules
(`ojz_act_pool`, `sec_block_blobs`, `sec_local_maps`, …) by a FIXED registry path,
and `games/sonic4/map.toml`'s order array names their head labels. A second act's
modules are therefore not linked without a sigil registry change, a map.toml change
and a second `act_descriptor.emp`, all of which land bytes in the canonical ROM. A
throwaway keeps the canonical shapes byte-identical BY CONSTRUCTION rather than by
promise: the canonical build reads the committed tree, this writes over it, the trap
puts it back, and no `.emp`, no map.toml row and no engine constant is touched.

WHY NOT A SEPARATE GAME. `games/demo` is the proof the engine is game-agnostic and
it has ZERO Sonic code. "Sonic stands on its ground" needs the player, the character
art, the mappings and the DPLC — i.e. a fork of the whole `games/sonic4` game layer.
Duplication on that scale is what CLAUDE.md's "clean, not bolted-on" refuses.

WHAT THE THROWAWAY INHERITS FROM THE SHIPPED ACT, deliberately and stated rather
than hidden — these are the parts of the picture that are NOT Emerald Hill:

  * THE BACKGROUND. `ojz_strip_gen` Pass 6b builds Plane B from the sonic_hack donor
    unconditionally ("BG layout always uses sonic_hack data"), so a clip act shows
    Emerald Hill's FOREGROUND over Oracle Jungle's BACKGROUND. Not a defect to fix
    here: a per-clip background is the design's §9.1 corridor work (row 7+), and a
    second act's BG animation has nowhere to live yet (DEFERRED_WORK, risk 5).
  * THE OBJECTS AND RINGS. Pass 8 (`ojz_entity_gen`) reads the shipped act's editor
    objects/rings, so OJZ's entities appear at OJZ's world positions over Emerald
    Hill geometry. Objects are out of scope for the whole first cut (owner's scope).
  * THE EFFECTS PRESETS AND THE REGION TABLE. Both live in the hand-written
    `act_descriptor.emp`, which this does not touch. Nearly every OJZ preset binds
    `OJZ_Palette` — `embed(".../ojz_palette.bin")`, a GENERATED file — so the clip's
    palette DOES reach the screen through them. Section 0's preset also installs a
    VSRAM raster program that bands Plane B below screen line 112; that will still
    fire, over Emerald Hill.

────────────────────────────────────────────────────────────────────────────────
ONE CLIP, AND WHY THAT IS A REFUSAL RATHER THAN A DEFAULT
────────────────────────────────────────────────────────────────────────────────

An editor nametable word's tile index is 11 bits into ONE act-wide tileset
(`clip_manifest`'s header, design §8). `ojz_strip_gen.generate()` reads exactly one
tileset — `project.json` zones[0].tileset — and hands `place_pool` a uniform zone
grid. A ONE-clip act has exactly one donor zone and is therefore an ORDINARY aeon act:
no per-cell tileset key is needed and nothing is faked. A TWO-clip act is not, and
this refuses it by name (R20) rather than baking the second clip's indices against the
first clip's art — which produces a tree every gate accepts and half a picture that is
the wrong zone. Teaching the ROM path a per-cell key is row 7's work, alongside the
corridor.

────────────────────────────────────────────────────────────────────────────────
WHAT IT RUNS
────────────────────────────────────────────────────────────────────────────────

  1. `clip_act_bake.bake` — the row 3 + row 5 composer. Writes the act's editor-shaped
     tree: `section_N.tiles.bin` (donor tile indices), `section_N.collattr.bin` /
     `.collattrb.bin`, and runs R1-R12 / C1-C3 including the 255-entry attr cap.
  2. a staged `project.json` beside that tree, naming the donor zone's `tileset.bin`
     and the act grid. `dataPath` is `.` — the tree IS the act directory.
  3. `ojz_strip_gen.generate()`, redirected at that project through `configure()`,
     with the SONIC 2 collision bank (row 4's `base_s2`) and the donor zone's
     `palette.bin` as the authored palette. Emits strips, local maps, the pool pages,
     the manifest, the interned ROM collision tables and the palette.
  4. `tools/elect_pool_pages.py` — per-page ZX0/raw election + `ojz_act_pool.emp`.
  5. `ojz_block_gen.generate_all()` — THE BLOCK STREAM. `sec{N}_blocks.bin` per
     section (S4LZ v3 with a per-section block dictionary), `sec_block_blobs.emp`,
     `sec_block_dicts.emp`.

Every output lands in the SHIPPED act's generated directory, because that is the one
sigil links. Run it only under build.sh's S2CLIP shape, which owns the restore trap;
the `bake` mode refuses to start on a dirty tree for the same reason STRESS_ART does.

  python3 tools/clip_rom_bake.py bake games/sonic4/data/clips/s2_ehz_boot/clips.json
  python3 tools/clip_rom_bake.py ground games/sonic4/data/clips/s2_ehz_boot/clips.json

`ground` is the STATIC half of row 6's check — see its own docstring.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import act_grid                 # noqa: E402
import clip_act_bake            # noqa: E402
import clip_manifest            # noqa: E402
import collision_pipeline       # noqa: E402
import elect_pool_pages         # noqa: E402

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
GEN_DIR = os.path.join(REPO, "games", "sonic4", "data", "generated", "ojz", "act1")
COLL_DIR = os.path.join(REPO, "games", "sonic4", "data", "collision")
GEN_REL = "games/sonic4/data/generated/ojz/act1"


class ClipRomError(Exception):
    """A named refusal."""


# ---------------------------------------------------------------------------
# THE STAMP, and why a bare bake now restores by default (parcel 7, 2026-09-17)
# ---------------------------------------------------------------------------
#
# TWO DEFECTS, ONE MECHANISM. Parcel 6 left both and the owner hit both in one session:
#
#   (1) `bake` RUN BY HAND DIRTIED THE SHIPPED TREE. R22 refuses to START over
#       uncommitted work, but nothing put the tree back afterwards: build.sh's S2CLIP
#       shape owns an EXIT trap, a bare invocation owned nothing, and the next person to
#       `git commit -a` would have committed the clip act's bytes into the shipped act's
#       slot. The default is therefore now RESTORE-ON-EXIT, on success and on failure.
#       It is exact rather than best-effort because R22 has already proven the pre-state
#       clean — a restore is only safe when something guaranteed what it restores TO.
#
#       WHY NOT "WRITE ELSEWHERE", which would be the obvious fix: it is not available.
#       sigil places the generated `.emp` modules by a FIXED registry path and
#       games/sonic4/map.toml names their head labels (this file's header). The bake
#       MUST land in the shipped act's slot; the only question was who cleans it up.
#
#   (2) A STALE TREE ANSWERED AS A PASTE SHIFT. `ground` run against a tree baked from
#       something else refused — correctly — but with `donor_corroboration`'s message,
#       which says "a difference that is a multiple of 8 or 16 is a PASTE SHIFT". It was
#       not a paste shift. It was the wrong act. A reader acting on that message would
#       go and look at R12 and the clip rectangle, which are innocent.
#
# The stamp closes (2) and makes (1)'s opt-out safe. `--keep` leaves the tree in place
# for `ground` / `clip_reachability` to read, and writes STAMP_NAME beside it naming the
# clip act that produced it. Both readers refuse on a missing or mismatched stamp, BY
# NAME, before they measure anything — so "you are looking at the shipped act" and "you
# are looking at a different clip" can no longer arrive dressed as geometry.
#
# The stamp is deliberately UNTRACKED: it must not exist in the committed tree, because
# the committed tree is the shipped act and a stamp there would be a lie. R22 skips it
# for that reason (it is the one path this bake creates that is not a modification of
# something the restore can put back), and build.sh's `git clean -fdq` removes it.

STAMP_NAME = "clip_bake_stamp.json"

RESTORE_PATHS = (GEN_REL, "games/sonic4/data/collision")


def write_stamp(act, gen_dir, manifest_path):
    """Name the clip act this generated tree was baked from."""
    with open(os.path.join(gen_dir, STAMP_NAME), "w") as fh:
        json.dump({
            "schema": 1,
            "produced_by": "tools/clip_rom_bake.py",
            "act": act.id,
            "manifest": os.path.relpath(os.path.abspath(manifest_path), REPO),
            "_note": ("UNTRACKED and deliberately so: this tree is the SHIPPED act's "
                      "slot holding a THROWAWAY clip bake. Its presence is what tells "
                      "`ground` and `clip_reachability` they are not reading the shipped "
                      "act. Never commit it; `git clean -fdq` on the generated tree is "
                      "part of the restore."),
        }, fh, indent=2, sort_keys=True)
        fh.write("\n")


def require_stamp(act_id, gen_dir, reader):
    """Refuse to measure a tree that is not this clip act's. Raises ClipRomError."""
    path = os.path.join(gen_dir, STAMP_NAME)
    if not os.path.isfile(path):
        raise ClipRomError(
            f"{reader}: {GEN_REL} carries no {STAMP_NAME}, so it is NOT a clip bake — "
            f"it is the committed SHIPPED act (or a restored tree). Measuring it would "
            f"answer about Oracle Jungle while naming this clip, which is how a stale "
            f"tree gets read as a paste shift. Run "
            f"`python3 tools/clip_rom_bake.py bake <manifest> --keep` first; a bare "
            f"`bake` restores the tree on exit precisely so this cannot be ambiguous.")
    try:
        stamped = json.load(open(path))["act"]
    except (OSError, ValueError, KeyError) as exc:
        raise ClipRomError(
            f"{reader}: {GEN_REL}/{STAMP_NAME} could not be read ({exc}). It is the only "
            f"thing that says which act these bytes are; without it nothing here can be "
            f"attributed.") from exc
    if stamped != act_id:
        raise ClipRomError(
            f"{reader}: {GEN_REL} was baked from clip act '{stamped}', not '{act_id}'. "
            f"This is a STALE TREE, not a geometry problem — do not read the numbers as "
            f"a paste shift. Re-bake with "
            f"`python3 tools/clip_rom_bake.py bake <this act's manifest> --keep`.")


def restore_tree(git="git", log=print):
    """Put the paths this bake overwrites back to their committed bytes."""
    for cmd in (["checkout", "--"], ["clean", "-fdq", "--"]):
        args = [git] + cmd + ([GEN_REL] if cmd[0] == "clean" else list(RESTORE_PATHS))
        try:
            subprocess.run(args, cwd=REPO, capture_output=True, check=False)
        except OSError as exc:                      # noqa: BLE001 — reported, not swallowed
            if log:
                log(f"clip_rom_bake: WARNING — could not restore the tree ({exc}). "
                    f"Run by hand: git checkout -- {' '.join(RESTORE_PATHS)} && "
                    f"git clean -fdq -- {GEN_REL}")
            return False
    if log:
        log(f"clip_rom_bake: tree RESTORED — {', '.join(RESTORE_PATHS)} are back at "
            f"their committed bytes. Pass --keep to inspect the bake instead "
            f"(`ground` and `clip_reachability` need the kept tree).")
    return True


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------

def check_zone_separation(act, summary):
    """Z1 — no camera position holds cells of two donor zones. REPLACES R20.

    R20 refused every act with more than one clip, because the ROM path read ONE tileset
    and a second clip's indices would have resolved against the first clip's art. Row 7
    (2026-09-25) put the per-cell tileset key on the ROM path (`stage_project`'s
    `tilesets`, ojz_strip_gen's keyed bake), so that refusal's reason is gone and R20 is
    deleted rather than left to refuse a case that now works.

    What a two-zone act still must not do is let one screen show both zones: they
    disagree about which CRAM line their ground is (design §5.3) and one palette is
    installed at a time. That is `clip_act_bake.zone_separation`'s count over every tile
    cache window the act can produce, and it is refused HERE — at the ROM bake — rather
    than in clip_act_bake, whose row-3 fixtures butt two zones on purpose to measure the
    tileset key and have never been, and must never become, ROMs. The owner's ruling is
    corridors, never butted zones (S2ACT-SEAM-CORRIDORS, 2026-09-17).
    """
    z = summary["zone_separation"]
    if z["mixed"]:
        f = z["first_mixed"]
        raise ClipRomError(
            f"Z1 {z['mixed']} of {z['windows']} camera windows hold cells of two donor "
            f"zones (first at tile column {f['left_tile']}, row {f['top_tile']}, camera x "
            f"~{f['camera_x_px_approx']} px). Two Sonic 2 zones disagree about which CRAM "
            f"line their ground is and the act installs one palette at a time, so one of "
            f"them is on screen in the other's colours. Put a corridor between them "
            f"(clips.json `corridors`) wider than the {z['window_cells'][0]}-cell tile-cache "
            f"window; the narrowest gap between two zones here is "
            f"{z['min_column_gap_cells']} cell(s). Owner ruling S2ACT-SEAM-CORRIDORS: "
            f"corridors, never butted zones.")


def check_act_grid_matches_engine(act, descriptor=None):
    """R21 — the manifest's act grid is the grid the ENGINE WILL COMPILE.

    ────────────────────────────────────────────────────────────────────────────────
    RE-AIMED 2026-09-17 (S2-COMPRESSED-ACT parcel 9). READ THIS BEFORE TRUSTING IT.
    ────────────────────────────────────────────────────────────────────────────────

    WHAT IT USED TO BE. The grid was two hand-typed lines in `act_descriptor.emp`, a file
    this throwaway cannot write, so the only grid a clip act could declare was the shipped
    act's and this row's whole job was to say NO to anything else. It named a real hazard
    (a local-map table shorter than the grid the engine indexes by flat id — the
    2026-09-12 F2 incident, one act over), but it enforced it by forbidding the subject.

    WHAT IT IS NOW. The grid is GENERATED from project.json into
    `games/sonic4/data/generated/ojz/act1/act_grid.emp`, which IS inside the tree this
    bake rewrites and the S2CLIP trap restores. `stage_project` writes the clip's grid
    into the staged project and `emit_engine_grid` lowers it into that module, so this row
    runs AFTER the emit and reads the emitted value back out.

    WHAT IT STILL CATCHES, and it is not nothing:
      * an emit that did not happen or wrote the wrong numbers — a STALE module left by a
        previous bake at a previous grid, which is the F2 staleness exactly, and the case
        a bake is most likely to produce by accident;
      * a descriptor that stopped taking its grid from that module at all
        (`act_grid.descriptor_grid` RAISES rather than falling back — an unreadable grid
        is Unmeasurable, never a pass).

    WHAT IT NO LONGER CATCHES, NAMED RATHER THAN IMPLIED: a clip act declaring a grid
    different from the shipped act's. That case is now the FEATURE and refusing it was the
    cap this parcel removed, so it is deliberately given up.

    WHAT TOOK OVER THE GUARANTEE IT USED TO GIVE. "The section table is exactly as long as
    the grid" is now a comptime `ensure` in the descriptor itself
    (`OJZ_SEC_ROWS_TOTAL == GRID_W * GRID_H`), which no bake can skip, and
    `verify_level_bin`'s local-map lane still holds `OJZ_Sec_LocalMaps`' arity to
    `act_grid.section_count`. A short table fails the BUILD now instead of being refused at
    the manifest.

    Read from the engine, never typed: `act_grid.descriptor_grid` parses
    `pub const OJZ_ACT_GRID_W = <int>` out of the generated module.
    """
    kw = {} if descriptor is None else {"descriptor": descriptor}
    gw, gh = act_grid.descriptor_grid(**kw)
    if (act.grid_w, act.grid_h) != (gw, gh):
        raise ClipRomError(
            f"R21 the manifest declares a {act.grid_w}x{act.grid_h} act grid and the grid "
            f"the engine will compile is {gw}x{gh} "
            f"({os.path.relpath(act_grid.ACT_GRID_EMP, REPO)}). Those are emitted from the "
            f"manifest by this bake, so a disagreement means the emit did not happen or "
            f"wrote something else — a STALE module from a previous bake at a previous "
            f"grid is the likely cause. Re-run the bake; do not edit the generated module "
            f"by hand.")


def check_rom_pool_is_composed_pool(baked_dir, gen_dir, log=None):
    """K4 — the ROM bake placed EXACTLY the art pool the composer placed.

    THE PER-CELL KEY'S END-TO-END WITNESS ON THE ROM PATH (row 7). Two different programs
    dedupe and place this act: `clip_act_bake` (from clips.json, keyed by construction)
    and `ojz_strip_gen.generate()` (from the staged project's `tilesets` and the
    `section_N.zonekey.bin` files). Both hand `fg_page_order.place_pool` a canonical grid
    and a zone grid, so if the key reached the ROM path intact the two pools are the same
    bytes, page for page. A ROM path that lost the key dedupes two zones' equal indices
    into one entry and lands a SMALLER pool — which every self-consistency lane accepts,
    because a smaller pool is internally consistent. This one does not.

    Compared over the page CONTENTS padded to whole pages, which is what the ROM streams;
    `pool.bin` is written that way by clip_act_bake.emit.
    """
    with open(os.path.join(baked_dir, "pool.bin"), "rb") as fh:
        composed = fh.read()
    with open(os.path.join(gen_dir, "ojz_act_pool_manifest.json")) as fh:
        side = json.load(fh)
    page_bytes = side["page_bytes"]
    rom = bytearray()
    for p in side["pages"]:
        with open(os.path.join(gen_dir, f"act_pool_page{p['index']}.bin"), "rb") as fh:
            blob = fh.read()
        rom += blob + bytes(page_bytes - len(blob))
    if bytes(rom) != composed:
        first = next((i for i in range(min(len(rom), len(composed)))
                      if rom[i] != composed[i]), min(len(rom), len(composed)))
        raise ClipRomError(
            f"K4 the ROM bake's art pool ({len(side['pages'])} pages, {len(rom)} B padded) "
            f"is not the pool clip_act_bake composed ({len(composed)} B); first difference "
            f"at byte {first} (page {first // page_bytes}). Both place the same act through "
            f"fg_page_order.place_pool, so a difference means the per-cell tileset key did "
            f"not reach ojz_strip_gen intact — the staged project's `tilesets` or a "
            f"section_N.zonekey.bin is not what clip_act_bake wrote.")
    if log:
        log(f"clip_rom_bake: K4 the ROM bake's pool IS the composed pool — "
            f"{len(side['pages'])} pages, {len(rom)} B, byte for byte")


def check_tree_is_clean(paths, git="git"):
    """R22 — refuse to start over uncommitted work in what this OVERWRITES.

    STRESS_ART's rule, for STRESS_ART's reason: the restore is `git checkout`, so an
    uncommitted change under these paths is discarded by the shape that is supposed to
    be a throwaway. Absence of git is UNMEASURABLE, and is refused rather than assumed
    clean.
    """
    try:
        out = subprocess.run([git, "status", "--porcelain", "--"] + list(paths),
                             cwd=REPO, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ClipRomError(
            f"R22 could not read `git status` for {', '.join(paths)} ({exc}). This bake "
            f"OVERWRITES those paths and the restore is `git checkout`, so it will not "
            f"run without being able to see what it would destroy.") from exc
    # The stamp is this bake's own untracked marker (see the STAMP block). It is the one
    # path here the restore does not put back but `git clean` removes, and a previous
    # `--keep` run leaving one must not refuse the next bake.
    dirty = [ln for ln in out.rstrip().splitlines()
             if os.path.basename(ln.strip()) != STAMP_NAME]
    if dirty:
        raise ClipRomError(
            "R22 the paths this bake overwrites are not clean:\n  "
            + "\n  ".join(dirty)
            + "\nCommit or stash them first — this is a THROWAWAY bake whose restore "
              "is `git checkout`, and it would discard them.")


# ---------------------------------------------------------------------------
# THE CLIP ACT'S OWN REGIONS AND PALETTES (S2-COMPRESSED-ACT row 7, 2026-09-25)
# ---------------------------------------------------------------------------
#
# WHAT THIS REPLACES. Parcel 6 shipped `S2CLIP_PALETTE=shipped` — every clip act drawn in
# Oracle Jungle's colours — because the only palette a clip bake could reach was
# `ojz_palette.bin`, which EIGHT top-level comptime pins in ojz_effects.emp hold to the
# SHIPPED act's statistics (parcel 6's BLOCKED ruling; options a/b/c). Row 7 takes neither
# (a) nor (b): the clip act no longer touches `ojz_palette.bin` at all. It carries its
# own palettes and its own region table in a GENERATED module, `clip_act.emp`, which is
# inside the tree the S2CLIP trap restores — so the pins keep describing exactly the
# palette they were written for, unchanged, in every shape.
#
# THE SEAM. act_descriptor.emp imports `ojz_clip_act_regions(hand:)` and `OJZ_CLIP_ACT`
# from that module and binds `act_regions` / `act_region_count` through them — the same
# always-live binding-function pattern effects_gen's `ojz_act1_act_default(hand:)` uses.
# The COMMITTED module is the neutral one (`OJZ_CLIP_ACT = 0`, the chooser returns `hand`,
# zero data, zero labels), so the canonical ROMs carry the shipped table exactly as before.
# A clip bake overwrites it with the act's palettes, one EffectsPreset per donor zone and
# the region rows; the descriptor then re-checks those rows with the SAME table walk it
# runs over the shipped document (per-row rules, overlap, exact coverage).
#
# ⚠ WHAT THE CLIP ACT STILL INHERITS: the shipped act's region TABLE is still assembled
# (it is unused data in a clip ROM), and the background, objects and rings are still the
# shipped act's. The BACKGROUND now shows in each zone's palette rather than Oracle
# Jungle's: Plane B uses CRAM lines 2 and 3 (games/sonic4/test/ojz_scroll_test.emp's
# boot-palette note), so it is recoloured by whichever zone the camera is in. TAGGED for
# the owner's look; a per-region background is the region-BG-switch machinery's job.

CLIP_MODULE_REL = GEN_REL + "/clip_act.emp"
CLIP_MODULE = os.path.join(REPO, CLIP_MODULE_REL)
CLIP_MODULE_NAME = "games.sonic4.ojz_clip_act_act1"
#: The section the clip act's data joins. effects_gen's own generated block, placed in
#: games/sonic4/map.toml by SECTION NAME, so new bytes there need no map.toml edit (its
#: header says so) — a clip act adds bytes without adding a placement row, which is what
#: keeps the canonical map untouched.
CLIP_MODULE_SECTION = "ojz_effects_editor_act1"

_CLIP_HEADER = """\
// AUTO-GENERATED by tools/clip_rom_bake.py — DO NOT EDIT.
//
// THE CLIP ACT'S OWN REGIONS AND PALETTES (S2-COMPRESSED-ACT row 7). act_descriptor.emp
// binds `act_regions` / `act_region_count` through `ojz_clip_act_regions(hand:)` and
// `OJZ_CLIP_ACT` below; see the ROW 7 block in tools/clip_rom_bake.py for the design.
//
"""


def clip_module_text(plan=None):
    """The module text. `plan` None is the NEUTRAL module the tree commits: no clip act, the
    chooser hands back the descriptor's own table, zero bytes and zero labels — so the
    canonical ROMs are the shipped act exactly. A plan (from `region_plan`) is a clip act."""
    if plan is None:
        return (_CLIP_HEADER +
                "// THIS IS THE NEUTRAL MODULE — the one the tree commits and the canonical\n"
                "// build reads. OJZ_CLIP_ACT = 0: the descriptor's own region table stands,\n"
                "// the chooser returns `hand`, and nothing here emits a byte or a label. An\n"
                "// S2CLIP build overwrites this file and build.sh's EXIT trap restores it.\n\n"
                f"module {CLIP_MODULE_NAME}\n\n"
                "pub const OJZ_CLIP_ACT = 0\n"
                "pub const OJZ_CLIP_REGION_ROWS: array = []\n\n"
                "pub comptime fn ojz_clip_act_regions(hand: Label) -> Label {\n"
                "    return hand\n"
                "}\n")
    lines = [_CLIP_HEADER,
             f"// CLIP ACT {plan['act']} — {len(plan['zones'])} donor zone(s), "
             f"{len(plan['rows'])} region row(s).\n",
             "// Written by a THROWAWAY S2CLIP bake into the shipped act's slot; build.sh's\n"
             "// EXIT trap restores the neutral module. Never commit this version.\n\n",
             f"module {CLIP_MODULE_NAME} in {CLIP_MODULE_SECTION}\n\n",
             "use engine.structs.{Region}\n",
             "use engine.effects.preset.{EffectsPreset, preset}\n",
             "use engine.effects.raster.{Raster_Program_None}\n",
             "use engine.effects.palette.{Pal_Cycle_None}\n\n",
             "pub const OJZ_CLIP_ACT = 1\n\n"]
    for z in plan["zones"]:
        words = z["palette_words"]
        body = ",\n    ".join(", ".join(f"${w:04X}" for w in words[i:i + 8])
                              for i in range(0, 48, 8))
        lines.append(
            f"// zone key {z['key']}: {z['donor']} {z['zone']} — the donor's own 96 palette "
            f"bytes (CRAM lines 1-3),\n// {z['palette_file']} sha256 {z['palette_sha256']}\n"
            f"pub data {z['palette_label']}: [u16; 48] = [\n    {body}\n]\n"
            f"// transition: 1 — the 16-frame cross-fade arms on EVERY install of this "
            f"preset,\n// so the crossing fades both ways (engine/effects/preset.emp).\n"
            f"pub data {z['preset_label']}: EffectsPreset = preset(pal: {z['palette_label']}, "
            f"raster: Raster_Program_None, cycle: Pal_Cycle_None, transition: 1)\n\n")
    rows = ",\n    ".join(
        f"Region{{ rg_x0: {r['x0']}, rg_x1: {r['x1']}, rg_y0: {r['y0']}, rg_y1: {r['y1']}, "
        f"rg_effects: {r['preset_label']}, rg_parallax: 0, rg_bg_layout: 0, rg_bg_span: 0, "
        f"rg_bg_tiles: 0 }}  // {r['why']}"
        for r in plan["rows"])
    lines.append(
        f"pub const OJZ_CLIP_REGION_ROWS: [Region; {len(plan['rows'])}] = [\n    {rows}\n]\n"
        f"pub data OJZ_Clip_Regions: [Region; {len(plan['rows'])}] = OJZ_CLIP_REGION_ROWS\n\n"
        "// `OJZ_Clip_Regions` is not imported at the call site: a comptime fn's free names\n"
        "// resolve THERE (docs/EMP_PITFALLS.md §2), and an unknown name in a Label position\n"
        "// becomes a link extern — the route effects_gen's choosers already take.\n"
        "pub comptime fn ojz_clip_act_regions(hand: Label) -> Label {\n"
        "    return OJZ_Clip_Regions\n"
        "}\n")
    return "".join(lines)


def _palette_words(path):
    data = open(path, "rb").read()
    if len(data) != 96:
        raise ClipRomError(f"{path} is {len(data)} bytes; a zone palette is 96 (CRAM lines 1-3)")
    return [(data[i] << 8) | data[i + 1] for i in range(0, 96, 2)]


def crossing_constants():
    """(fade frames, camera x step, screen half width) — READ from the engine, never typed."""
    from fg_working_set import ConstantSource

    def get(path, name):
        src = ConstantSource()
        src.load_file(os.path.join(REPO, path))
        return int(src.get(name))
    return (get("engine/effects/palette.emp", "PAL_FADE_FRAMES"),
            get("engine/level/camera.emp", "CAM_MAX_X_STEP"),
            get("engine/system/constants.emp", "CAM_SCREEN_HALF_W"))


def region_plan(act, donor_root, act_h_px=None):
    """The clip act's region rows: one vertical strip per run of same-zone clips, left to
    right, each crossing at the MIDDLE of the corridor between two zones (rounded down to
    the 16-px collision grid), full act height. Z2 refuses a layout this cannot express
    rather than guessing: clips must form a left-to-right chain, and two neighbouring
    clips of DIFFERENT zones must have a corridor filling the gap between them."""
    sec = act.section_px
    act_w = act.grid_w * sec
    act_h = act_h_px or act.grid_h * sec
    clips = sorted(act.clips, key=lambda c: c.dst[0])
    for a, b in zip(clips, clips[1:]):
        if b.dst[0] < a.dst[0] + a.dst[2]:
            raise ClipRomError(
                f"Z2 clips {a.id!r} and {b.id!r} overlap in x. The region plan is a "
                f"left-to-right chain of full-height strips; a stacked layout needs a "
                f"horizontal crossing this bake does not write.")
    zones = []
    for key, (donor, zone) in enumerate(act.zone_table):
        pal = os.path.join(donor_root, donor, zone, "palette.bin")
        with open(os.path.join(donor_root, donor, zone, "zone.json")) as fh:
            zm = json.load(fh)
        zones.append({"key": key, "donor": donor, "zone": zone,
                      "palette_file": os.path.relpath(pal, REPO),
                      "palette_sha256": zm["palette"]["sha256"],
                      "palette_words": _palette_words(pal),
                      "palette_label": f"OJZ_Clip_Palette_{key}",
                      "preset_label": f"OJZ_Clip_Preset_{key}"})
    cuts = []                       # (x of the crossing, left zone, right zone, corridor)
    for a, b in zip(clips, clips[1:]):
        if a.zone_key == b.zone_key:
            continue
        gap0, gap1 = a.dst[0] + a.dst[2], b.dst[0]
        corr = [c for c in act.corridors if c.dst[0] <= gap0 and c.dst[0] + c.dst[2] >= gap1]
        if not corr or gap1 <= gap0:
            raise ClipRomError(
                f"Z2 clips {a.id!r} ({'/'.join(a.tree_key)}) and {b.id!r} "
                f"({'/'.join(b.tree_key)}) are different zones with no corridor filling "
                f"the {max(0, gap1 - gap0)} px between them. Owner ruling "
                f"S2ACT-SEAM-CORRIDORS: corridors, never butted zones.")
        mid = ((gap0 + gap1) // 2) & ~15
        cuts.append((mid, a.zone_key, b.zone_key, corr[0].id, gap0, gap1))
    rows, x0 = [], 0
    order = [clips[0].zone_key] + [c[2] for c in cuts]
    for i, key in enumerate(order):
        x1 = (cuts[i][0] - 1) if i < len(cuts) else act_w - 1
        why = (f"{zones[key]['donor']} {zones[key]['zone']}"
               + (f", to the middle of corridor {cuts[i][3]}" if i < len(cuts) else
                  ", to the act's right edge"))
        rows.append({"x0": x0, "x1": x1, "y0": 0, "y1": act_h - 1, "key": key,
                     "preset_label": zones[key]["preset_label"], "why": why})
        x0 = x1 + 1
    return {"act": act.id, "zones": zones, "rows": rows,
            "crossings": [{"x": c[0], "from_key": c[1], "to_key": c[2], "corridor": c[3],
                           "gap": [c[4], c[5]]} for c in cuts]}


_ROW_RE = None


def parse_clip_module_rows(text):
    """The region rows back OUT of an emitted clip module: [(x0, x1, y0, y1, preset label)].
    Z2 is run on THIS, not on the plan — so it measures what the ROM will carry."""
    import re
    global _ROW_RE
    if _ROW_RE is None:
        _ROW_RE = re.compile(
            r"Region\{\s*rg_x0:\s*(\d+),\s*rg_x1:\s*(\d+),\s*rg_y0:\s*(\d+),\s*rg_y1:\s*(\d+),"
            r"\s*rg_effects:\s*(\w+)")
    m = re.search(r"OJZ_CLIP_REGION_ROWS:\s*\[Region;\s*(\d+)\]\s*=\s*\[(.*?)\n\]", text, re.S)
    if not m:
        raise ClipRomError("Z2 the clip module carries no OJZ_CLIP_REGION_ROWS table — UNMEASURABLE")
    rows = [(int(a), int(b), int(c), int(d), e) for a, b, c, d, e in _ROW_RE.findall(m.group(2))]
    if len(rows) != int(m.group(1)):
        raise ClipRomError(f"Z2 the clip module declares {m.group(1)} region rows and "
                           f"{len(rows)} parse — UNMEASURABLE")
    presets = {p: (pal, int(t)) for p, pal, t in re.findall(
        r"pub data (OJZ_Clip_Preset_\d+): EffectsPreset = preset\(pal: (\w+),"
        r"[^\n]*?transition: (\d)\)", text)}
    return rows, presets


def check_palette_crossings(act, text, consts=None, log=None):
    """Z2 — each zone is drawn under its OWN palette, and walking from one zone to the next
    installs the other palette EXACTLY ONCE, where the screen shows only corridor for the
    whole cross-fade. Run over the rows parsed back out of the EMITTED module.

    The row-7 check as the design words it: "the palette cross-fade fires exactly once per
    crossing". A runtime claim; this is how far a static check reaches, built from the
    engine's own terms rather than restated ones:
      * the region the engine installs is the one containing the camera CENTRE
        (Parallax_CheckBoundary: Camera_X + CAM_SCREEN_HALF_W);
      * an install is one change of EffectsPreset, and a palette change is one change of
        ep_pal — so the walk counts both and requires exactly one of each per zone pair;
      * the fade runs PAL_FADE_FRAMES frames (engine/effects/palette.emp) while the camera
        moves up to CAM_MAX_X_STEP px a frame (engine/level/camera.emp). So from the frame
        the centre crosses, the screen — CAM_SCREEN_HALF_W either side of the centre — may
        travel FADE x STEP px before the new palette has fully arrived, in either
        direction. The crossing must sit at least HALF_W + FADE x STEP px inside the
        corridor from BOTH zones' nearest cells, or a zone is on screen in a half-faded
        palette, or the old zone is on screen when the new palette lands.
    Every preset the rows bind must arm the fade (transition 1), or the crossing snaps.
    """
    fade, step, half_w = consts or crossing_constants()
    margin = half_w + fade * step
    rows, presets = parse_clip_module_rows(text)
    if not presets:
        raise ClipRomError("Z2 no OJZ_Clip_Preset_* records parse out of the clip module — "
                           "UNMEASURABLE")
    for lab, (_pal, trans) in presets.items():
        if trans != 1:
            raise ClipRomError(f"Z2 {lab} does not arm the cross-fade (transition {trans}); "
                               f"the crossing would SNAP the palette")

    def row_at(x, y):
        hit = [r for r in rows if r[0] <= x <= r[1] and r[2] <= y <= r[3]]
        if len(hit) != 1:
            raise ClipRomError(f"Z2 the camera centre ({x}, {y}) is in {len(hit)} region "
                               f"rows; the rows must tile the act exactly")
        return hit[0]

    # (a) every clip cell sits under its own zone's preset
    want = {c.zone_key: f"OJZ_Clip_Preset_{c.zone_key}" for c in act.clips}
    for c in act.clips:
        for r in rows:
            if r[0] <= c.dst[0] + c.dst[2] - 1 and c.dst[0] <= r[1] and r[4] != want[c.zone_key]:
                raise ClipRomError(
                    f"Z2 clip {c.id!r} ({'/'.join(c.tree_key)}) reaches region x "
                    f"{r[0]}..{r[1]}, which binds {r[4]} — that zone is drawn in another "
                    f"zone's colours there")
    # (b) walk every neighbouring pair of different zones, at every 16-px y the corridor spans
    clips = sorted(act.clips, key=lambda c: c.dst[0])
    out = []
    for a, b in zip(clips, clips[1:]):
        if a.zone_key == b.zone_key:
            continue
        a_right = a.dst[0] + a.dst[2]            # first x past zone a
        b_left = b.dst[0]
        corr = [k for k in act.corridors
                if k.dst[0] <= a_right and k.dst[0] + k.dst[2] >= b_left]
        ys = range(corr[0].dst[1], corr[0].dst[1] + corr[0].dst[3], 16) if corr else [0]
        for y in ys:
            changes = []
            prev = row_at(a_right - 1, y)
            for x in range(a_right - 1, b_left + 1):
                r = row_at(x, y)
                if r is not prev:
                    changes.append((x, prev[4], r[4]))
                    prev = r
            pal_changes = [ch for ch in changes if presets[ch[1]][0] != presets[ch[2]][0]]
            if len(changes) != 1 or len(pal_changes) != 1:
                raise ClipRomError(
                    f"Z2 walking the camera centre from {a.id!r} to {b.id!r} at y={y} "
                    f"installs {len(changes)} preset(s) and changes the palette "
                    f"{len(pal_changes)} time(s), not exactly once: {changes}")
            x_c = changes[0][0]
            if x_c - margin < a_right or x_c + margin > b_left:
                raise ClipRomError(
                    f"Z2 the crossing from {a.id!r} to {b.id!r} is at x={x_c}, but a "
                    f"cross-fade needs {margin} px of corridor on EACH side of it "
                    f"(CAM_SCREEN_HALF_W {half_w} + PAL_FADE_FRAMES {fade} x CAM_MAX_X_STEP "
                    f"{step}) and the corridor runs x {a_right}..{b_left - 1}: "
                    f"{x_c - a_right} px on the left, {b_left - x_c} on the right")
        out.append({"from": a.id, "to": b.id, "x": x_c, "margin_needed": margin,
                    "margin_left": x_c - a_right, "margin_right": b_left - x_c,
                    "ys_walked": len(list(ys))})
        if log:
            log(f"clip_rom_bake: Z2 {a.id} -> {b.id}: ONE preset install and ONE palette "
                f"change at x={x_c} on every one of {len(list(ys))} corridor rows; "
                f"{x_c - a_right} px of corridor left of it and {b_left - x_c} right, "
                f"{margin} needed each side")
    return out


def emit_clip_module(act, donor_root, path=CLIP_MODULE, log=None):
    """Write the clip act's module and run Z2 over what was written. Returns the Z2 rows."""
    plan = region_plan(act, donor_root)
    text = clip_module_text(plan)
    with open(path, "w") as fh:
        fh.write(text)
    if log:
        log(f"clip_rom_bake: {os.path.relpath(path, REPO)} — "
            + ", ".join(f"{z['zone']} palette + preset" for z in plan["zones"])
            + f", {len(plan['rows'])} region row(s): "
            + "; ".join(f"x {r['x0']}..{r['x1']} {r['preset_label']}" for r in plan["rows"]))
    with open(path) as fh:
        return check_palette_crossings(act, fh.read(), log=log), plan


# ---------------------------------------------------------------------------
# The staged project
# ---------------------------------------------------------------------------

def stage_project(act, baked_dir, donor_root, gen_dir=GEN_DIR, sheet_files=None):
    """Write the `project.json` that points the shipped generators at the clip tree.

    Paths inside it are relative TO IT, which is the rule `validate_editor_inputs`
    already used and the one `generate()` was taught on 2026-09-17 (it resolved
    `dataPath` against the repo root, which is the same thing only for a project file
    that sits at the repo root).

    `dataPath` is "." — `clip_act_bake` already wrote the act directory, so the tree is
    the act. `bgLayout`/`bgTiles` are carried over from the shipped project verbatim and
    are inert: Pass 6b builds Plane B from the sonic_hack donor and reads neither.

    `tilesets` (row 7) is THE PER-CELL TILESET KEY ON THE ROM PATH: every sheet the act's
    cells index, in zone-key order (`clip_act_bake`'s `zone_table`, donor zones then the
    corridor sheet), beside the `section_N.zonekey.bin` files clip_act_bake wrote into
    this tree. `ojz_strip_gen._project_tilesets` reads it and bakes KEYED. Written for
    EVERY clip act — one zone or several — so a one-clip act takes the same path as a
    two-zone one and there is no case that is only exercised by the bigger act.
    `tileset` stays too (sheet 0) for the readers that know only it.
    """
    clip = act.clips[0]
    zone_tree = os.path.join(donor_root, clip.donor, clip.zone)
    if sheet_files is None:
        sheet_files = [os.path.join(donor_root, d, z, "tileset.bin")
                       for d, z in act.zone_table]
    with open(os.path.join(REPO, "project.json")) as fh:
        shipped = json.load(fh)
    sz, sa = shipped["zones"][0], shipped["zones"][0]["acts"][0]
    rel = lambda p: os.path.relpath(p, baked_dir)     # noqa: E731
    proj = {
        "name": f"{shipped['name']} — clip act {act.id}",
        "engine": shipped["engine"],
        "_note": (
            "AUTO-GENERATED by tools/clip_rom_bake.py — a THROWAWAY project file for one "
            "clip act. It is NOT the shipped project.json; it exists so the shipped "
            "generators can be pointed at this clip's editor tree without editing the "
            "real one. dataPath, tileset(s) and palette are relative to THIS file."),
        "zones": [{
            "id": sz["id"],
            "name": " + ".join(f"{d}:{z}" for d, z in act.sheet_table),
            "tileset": rel(sheet_files[0]),
            "tilesets": [rel(p) for p in sheet_files],
            "palette": rel(os.path.join(zone_tree, "palette.bin")),
            "acts": [{
                "id": sa["id"],
                "gridWidth": act.grid_w, "gridHeight": act.grid_h,
                "dataPath": ".",
                "stripPath": rel(gen_dir),
                "stripPrefix": sa["stripPrefix"],
                "bgLayout": rel(os.path.join(REPO, sa["bgLayout"])),
                "bgTiles": rel(os.path.join(REPO, sa["bgTiles"])),
                "sceneRef": None,
                "startPosition": dict(sa["startPosition"]),
            }],
        }],
        "objectLibrary": rel(os.path.join(REPO, shipped["objectLibrary"])),
        "chunkLibrary": rel(os.path.join(REPO, shipped["chunkLibrary"])),
    }
    path = os.path.join(baked_dir, "project.json")
    with open(path, "w") as fh:
        json.dump(proj, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return path, zone_tree


# ---------------------------------------------------------------------------
# The bake
# ---------------------------------------------------------------------------

# THE PALETTE KNOB IS GONE (row 7, 2026-09-25). Parcel 6 shipped `--palette shipped|clip`
# because the only palette a clip bake could reach was `ojz_palette.bin`, and eight comptime
# pins in ojz_effects.emp refuse any palette but the shipped act's there (its BLOCKED
# ruling, options a/b/c). A clip act now carries its OWN palettes and region table in the
# generated clip_act.emp (the ROW 7 block above), so `ojz_palette.bin` is never rewritten,
# the pins describe exactly what they always did, and `clip` — which could only ever fail
# — and `shipped` — which drew every zone in Oracle Jungle's colours — have nothing left
# to choose between. Deleted, not defaulted: a knob with one working position is a scaffold.


def bake(manifest_path, donor_root=None, gen_dir=GEN_DIR, coll_dir=COLL_DIR,
         skip_clean_check=False, keep=False, log=print):
    """Bake the clip act into the shipped act's slot.

    `keep=False` (a bare invocation) RESTORES the overwritten tree on the way out, win or
    lose — see the STAMP block for why that is the default and why it is safe. `keep=True`
    leaves it, stamped, for build.sh and for `ground` / `clip_reachability`.
    """
    try:
        return _bake(manifest_path, donor_root=donor_root, gen_dir=gen_dir,
                     coll_dir=coll_dir,
                     skip_clean_check=skip_clean_check, keep=keep, log=log)
    finally:
        if not keep:
            restore_tree(log=log)


def _bake(manifest_path, donor_root=None, gen_dir=GEN_DIR, coll_dir=COLL_DIR,
          skip_clean_check=False, keep=False, log=print):
    donor_root = clip_manifest._root(donor_root)
    act = clip_manifest.load(manifest_path, donor_root=donor_root)
    if not skip_clean_check:
        check_tree_is_clean([os.path.relpath(gen_dir, REPO),
                             os.path.relpath(coll_dir, REPO)])

    baked_dir = os.path.join(os.path.dirname(os.path.abspath(manifest_path)), "baked")
    log(f"clip_rom_bake: composing {act.id} -> {os.path.relpath(baked_dir, REPO)}")
    _act, _st, summary, _v1, _v2 = clip_act_bake.bake(
        manifest_path, out_dir=baked_dir, donor_root=donor_root, log=log)
    check_zone_separation(act, summary)

    sheet_files = [os.path.join(REPO, z["tileset_file"]) for z in summary["zone_table"]]
    project_path, zone_tree = stage_project(act, baked_dir, donor_root, gen_dir,
                                            sheet_files=sheet_files)

    # THE ENGINE'S GRID, LOWERED FROM THE MANIFEST (S2-COMPRESSED-ACT parcel 9). This is
    # the whole of what lets a clip act be a different SHAPE from the shipped one: the
    # descriptor reads `GRID_W`/`GRID_H` out of this generated module, the module is inside
    # the tree the S2CLIP trap restores, and so the grid is finally something a throwaway
    # bake can set. It must happen BEFORE ojz_strip_gen, whose section count is
    # act_grid.section_count(staged project) and which refuses unless the engine agrees.
    #
    # R21 runs immediately after and reads the value back OUT of the emitted module, so a
    # stale or unwritten module is still a named refusal — see its docstring for what that
    # re-aiming keeps and what it gives up.
    act_grid.emit(act.grid_w, act.grid_h)
    check_act_grid_matches_engine(act)
    log(f"clip_rom_bake: engine grid {act.grid_w}x{act.grid_h} -> "
        f"{os.path.relpath(act_grid.ACT_GRID_EMP, REPO)} "
        f"({act.grid_w * act.grid_h} sections)")
    bank_dir = clip_manifest.collision_banks(act, donor_root)
    log(f"clip_rom_bake: staged project {os.path.relpath(project_path, REPO)} "
        f"(bank {os.path.relpath(bank_dir, REPO)})")

    # THE REDIRECT. configure() re-derives the tileset and the editor act directory
    # from the project it is handed, so this cannot half-point: setting the project
    # and keeping the shipped act's tileset is the failure it exists to prevent.
    import ojz_strip_gen
    ojz_strip_gen.configure(
        project_json=project_path,
        output_dir=gen_dir,
        collision_dir=coll_dir,
        bank_dir=bank_dir,
    )
    # THE CLIP ACT'S OWN REGIONS AND PALETTES (the ROW 7 block). Written before the strip
    # bake so a Z2 refusal costs nothing; `ojz_palette.bin` is left to the shipped act.
    z2, region_plan_ = emit_clip_module(act, donor_root, log=log)
    log("clip_rom_bake: strips, local maps, art pool, palette, collision tables...")
    ojz_strip_gen.generate()
    check_rom_pool_is_composed_pool(baked_dir, gen_dir, log=log)

    # THE EDITOR-AUTHORED BG OVERRIDE, exactly as tools/regenerate-level.sh runs it.
    # Skipping it was a REAL failure and not a cosmetic one: the raw generated zone BG is
    # 4,096 B and the override's is 8,192, and act_assets.emp declares
    # OJZ_Act1_BG_Layout at the override's size, so the clip build died with
    # `[emit.size-mismatch] data OJZ_Act1_BG_Layout: declared type is 8192 byte(s),
    # initializer produced 4096`. The clip act keeps the shipped act's background (see
    # this file's header), so it must keep the whole shipped BG path.
    override = os.path.join(REPO, "games", "sonic4", "data", "editor_bg_override.json")
    if os.path.isfile(override):
        log("clip_rom_bake: editor BG override...")
        r = subprocess.run([sys.executable, os.path.join(REPO, "tools", "inject_editor_bg.py")],
                           cwd=REPO)
        if r.returncode != 0:
            raise ClipRomError(
                f"inject_editor_bg.py exited {r.returncode}. The clip act keeps the "
                f"shipped act's background, so it needs the same BG injection the shipped "
                f"re-bake runs; without it OJZ_Act1_BG_Layout is emitted at half its "
                f"declared size and the build dies at the link.")

    page_bytes = _art_pool_page_bytes()
    elect_pool_pages.elect(
        gen_dir, page_bytes, os.path.join(REPO, "tools", "bin", "salvador"),
        module="games.sonic4.ojz_act_pool_act1", section="ojz_act_pool",
        symbol_prefix="OJZ_Act_Pool_Page", table_symbol="OJZ_Act_Pool_PageTable",
        emp_name="ojz_act_pool.emp", embed_prefix=GEN_REL, log=log)

    # THE BLOCK STREAM — row 6's inheritance. ojz_block_gen reads sec{N}_strips_a.bin out
    # of its own OUTPUT_DIR and the section count out of act_grid.
    #
    # ⚠ THE SENTENCE THAT STOOD HERE IS FALSE SINCE PARCEL 9 and is corrected rather than
    # deleted: it said the count "reads the SHIPPED project.json ... the shipped act's here
    # by construction (this bakes into its slot at its grid, R21)". R21 no longer pins the
    # clip to the shipped grid — that cap is exactly what parcel 9 removed — so the shipped
    # project.json is the WRONG count for any clip that declares its own, and both the
    # output dir and the project are redirected now.
    log("clip_rom_bake: block stream (S4LZ v3, per-section dictionaries)...")
    import ojz_block_gen
    ojz_block_gen.OUTPUT_DIR = gen_dir
    ojz_block_gen.generate_all(project_json=project_path)

    report = {
        "schema": 1,
        "produced_by": "tools/clip_rom_bake.py",
        "act": act.id,
        "clips": [{"id": c.id, "donor": c.donor, "zone": c.zone, "zone_key": c.zone_key,
                   "src_rect": list(c.src), "dst_rect": list(c.dst)} for c in act.clips],
        "corridors": [c.as_json() for c in act.corridors],
        "zone_separation": summary["zone_separation"],
        "grid": [act.grid_w, act.grid_h],
        "pool": summary["pool"],
        "collision": {k: summary["collision"][k]
                      for k in ("attr_entries", "cap", "base_bank")},
        "verdict_at_placement": summary["verdict_at_placement"],
        "generated_dir": GEN_REL,
        "palette": "per-zone, from each donor zone's palette.bin, in generated clip_act.emp",
        "regions": [{k: r[k] for k in ("x0", "x1", "y0", "y1", "preset_label", "why")}
                    for r in region_plan_["rows"]],
        "palette_crossings": z2,
        "inherited_from_the_shipped_act": [
            "background (Plane B is built from the sonic_hack donor by Pass 6b)",
            "objects and rings (Pass 8 reads the shipped act's editor entities)",
            "the shipped region table is still ASSEMBLED (unused: act_regions points at "
            "the clip act's own table)",
        ],
    }
    with open(os.path.join(baked_dir, "clip_rom_bake.json"), "w") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")
    if keep:
        write_stamp(act, gen_dir, manifest_path)
        log(f"clip_rom_bake: --keep — {GEN_REL} and {os.path.relpath(coll_dir, REPO)} "
            f"now hold THIS CLIP ACT, not the shipped one, and they are TRACKED PATHS. "
            f"Put them back with:\n"
            f"    git checkout -- {' '.join(RESTORE_PATHS)} && "
            f"git clean -fdq -- {GEN_REL}")
    log(f"clip_rom_bake: DONE — {act.id} is in {GEN_REL}; "
        f"{report['pool']['tiles']} pool tiles in {report['pool']['pages']} pages, "
        f"{report['collision']['attr_entries']} of {report['collision']['cap']} attr entries")
    return report


def _art_pool_page_bytes():
    from fg_working_set import ConstantSource
    src = ConstantSource()
    src.load_file(os.path.join(REPO, "engine", "system", "constants.emp"))
    return int(src.get("ART_POOL_PAGE_BYTES"))


# ---------------------------------------------------------------------------
# `ground` — the static half of row 6's check
# ---------------------------------------------------------------------------
#
# Row 6's check as the design writes it is "the clip renders and Sonic stands on its
# ground", which is a RUNTIME claim. This is how far a static check reaches, and it is
# deliberately built out of the ENGINE's own arithmetic rather than out of a
# convenient restatement of it:
#
#   * the spawn comes from `Camera_Init` + the boot state, re-derived below from the
#     descriptor's own `start_*` fields and the engine's CAM_* constants — NOT typed;
#   * the collision cell the sensor reads is picked the way `probe_core` picks it
#     (`andi.w #$F` on world x for the column inside a 16-byte height profile,
#     `lsr.w #1` in y for the row), so a 16-px misalignment of the paste — R12's whole
#     subject, which no screenshot shows — fails here;
#   * the height byte comes from the EMITTED ROM tables (heightmaps.bin, indexed by the
#     attr byte the EMITTED strips carry), not from the donor and not from the plane
#     files. Everything between the donor and the ROM is therefore in the loop.
#
# WHAT IT CANNOT SAY: that anything is on screen. It says the ground is under the spawn
# in the bytes the ROM will read. The runtime confirmation is TAGGED in the parcel
# report, not claimed here.

def ground(manifest_path, donor_root=None, gen_dir=GEN_DIR, coll_dir=COLL_DIR,
           log=print):
    import struct
    donor_root = clip_manifest._root(donor_root)
    act = clip_manifest.load(manifest_path, donor_root=donor_root)
    # BEFORE anything is measured: these numbers are only about this clip if this tree
    # is this clip's. A stale tree used to arrive here dressed as a paste shift.
    require_stamp(act.id, gen_dir, "ground")
    desc = os.path.join(REPO, "games", "sonic4", "data", "levels", "ojz", "act1",
                        "act_descriptor.emp")
    spawn_x, spawn_y = engine_spawn(desc)
    if log:
        log(f"ground: spawn re-derived from the engine = world ({spawn_x}, {spawn_y}) px")

    grid_w, grid_h = act_grid.descriptor_grid()
    sect_px = act.section_px
    heights = open(os.path.join(coll_dir, "heightmaps.bin"), "rb").read()
    angles = open(os.path.join(coll_dir, "angles.bin"), "rb").read()
    solidity = open(os.path.join(coll_dir, "solidity.bin"), "rb").read()

    # `probe_core` (games/sonic4/player/player_sensors.emp:200-226), step by step:
    #   solidity[attr] & d6 == 0 -> air. A FLOOR sensor passes d6 = SOLID_TOP.
    #     Parcel 4's own check omitted this gate and answered solid for 158,442
    #     probes Sonic 2 answers air; it is in the loop here for that reason.
    #   height = HeightMaps[attr*16 + (world_x & $F)]. 0 -> air. NEGATIVE is a
    #     near-edge-anchored ("hanging") run and is NOT a floor under a falling
    #     sensor in general, so it is reported and not counted as the landing.
    solid_top = int(_engine_const("SOLID_TOP"))
    col_in_block = spawn_x & 0xF
    y = (spawn_y // 16) * 16                     # the cell row the sensor starts in
    hit = None
    skipped = []
    while y < grid_h * sect_px:
        attr = attr_byte_at(gen_dir, grid_w, sect_px, spawn_x, y)
        if attr and (solidity[attr] & solid_top):
            h = heights[attr * 16 + col_in_block]
            sh = h - 256 if h > 127 else h       # the engine's ext.w + bmi
            if sh > 0:
                hit = (y, attr, sh, angles[attr])
                break
            if sh < 0:
                skipped.append((y, attr, sh))
        y += 16
    if hit is None:
        raise ClipRomError(
            f"ground: NOTHING SOLID under the spawn. A floor sensor dropped from world "
            f"({spawn_x}, {spawn_y}) through every 16-px collision row to the bottom of "
            f"the {grid_w}x{grid_h}-section act found no attr byte that is both "
            f"SOLID_TOP and has a positive height in column {col_in_block} of its "
            f"profile. Sonic falls forever. Either the clip's destination rectangle does "
            f"not cover the spawn column, or the paste shift moved the geometry off it."
            + (f" ({len(skipped)} hanging run(s) were passed through: {skipped[:4]})"
               if skipped else ""))
    y, attr, h, ang = hit
    # A height byte is how many pixels of the 16-px cell are solid, measured UP from
    # the cell's bottom, so the surface is at the cell bottom minus the height.
    surface = y + 16 - h
    if log:
        log(f"ground: SOLID at world y={y} (cell row {y // 16}), attr byte {attr}, "
            f"solidity ${solidity[attr]:02X}, height {h} px in column {col_in_block}, "
            f"angle ${ang:02X}; surface at world y={surface}, "
            f"{surface - spawn_y} px below the spawn")
    out = {"spawn": [spawn_x, spawn_y], "cell_y": y, "attr": attr, "height": h,
           "angle": ang, "solidity": solidity[attr], "surface_y": surface,
           "fall_px": surface - spawn_y, "hanging_passed": skipped}
    out["donor_corroboration"] = donor_corroboration(
        act, gen_dir, coll_dir, grid_w, grid_h, sect_px, log=log)
    return out


def donor_corroboration(act, gen_dir, coll_dir, grid_w, grid_h, sect_px,
                        donor_root=None, log=print):
    """The SECOND witness, and the one that can see a shifted paste.

    "Something solid is under the spawn" is a weak claim: air is the only thing it
    rules out, and a clip pasted 16 px wrong still has ground under it. This asks a
    question with a number in it instead — WHERE is the floor, compared with where the
    donor game itself says the floor is.

    Sonic 2 ships a start position per act (`startpos/<ZONE>_1.bin`: two big-endian
    words, x then y). The player stands ON the floor there, so the floor's surface must
    be at `start_y + PLAYER_Y_RADIUS`, give or take however far above it the game
    spawns you. DERIVED tolerance, not a fitted one: at or below the feet (never above
    — that would spawn the player inside the ground) and within ONE 16-px collision
    cell of them (a spawn further up than a cell is a fall, not a stand). A paste
    shifted by the 16-px block quantum R12 guards, or by the 8 px that moves collision
    and not art, lands OUTSIDE that window in the y axis.

    LOUD WHEN IT CANNOT MEASURE. A donor with no startpos file, a start x outside the
    clip's source rectangle, or a nonzero paste shift in a version of this that has not
    worked out the shifted comparison: all say so and return a reason. None of them is
    a pass.
    """
    clip = act.clips[0]
    import s2_donor
    try:
        droot = s2_donor.donor_root(clip.donor)
    except Exception as exc:                        # noqa: BLE001 — reported, not swallowed
        return {"measured": False, "why": f"donor root unavailable: {exc}"}
    p = os.path.join(droot, "startpos", f"{clip.zone}_1.bin")
    if not os.path.isfile(p):
        return {"measured": False,
                "why": f"no donor start position at {p} (the prototype donor spells "
                       f"its start positions differently)"}
    import struct as _s
    sx, sy = _s.unpack(">HH", open(p, "rb").read()[:4])
    x0, y0, w, hgt = clip.src
    dx0, dy0 = clip.dst[0], clip.dst[1]
    if not (x0 <= sx < x0 + w and y0 <= sy < y0 + hgt):
        return {"measured": False,
                "why": f"the donor's start ({sx}, {sy}) is outside this clip's source "
                       f"rectangle ({x0}, {y0}, {w}, {hgt}) — nothing to compare"}
    act_x = sx - x0 + dx0
    act_y = sy - y0 + dy0
    heights = open(os.path.join(coll_dir, "heightmaps.bin"), "rb").read()
    solidity = open(os.path.join(coll_dir, "solidity.bin"), "rb").read()
    solid_top = int(_engine_const("SOLID_TOP"))
    radius = int(_engine_const("PLAYER_Y_RADIUS"))
    col = act_x & 0xF
    y = (act_y // 16) * 16
    surface = None
    while y < grid_h * sect_px:
        a = attr_byte_at(gen_dir, grid_w, sect_px, act_x, y)
        if a and (solidity[a] & solid_top):
            hh = heights[a * 16 + col]
            sh = hh - 256 if hh > 127 else hh
            if sh > 0:
                surface = y + 16 - sh
                break
        y += 16
    feet = act_y + radius
    ok = surface is not None and 0 <= surface - feet <= 16
    res = {"measured": True, "donor_start": [sx, sy], "act_point": [act_x, act_y],
           "player_y_radius": radius, "feet_y": feet, "surface_y": surface,
           "delta": None if surface is None else surface - feet, "ok": ok}
    if log:
        log(f"ground: donor corroboration — {clip.donor}:{clip.zone} starts the player "
            f"at ({sx}, {sy}); at that point in the ACT the ROM's floor surface is "
            f"y={surface} and the player's feet are at y={feet} "
            f"({res['delta']} px). Window: 0..16 (at or below the feet, within one "
            f"collision cell). {'AGREES' if ok else 'DISAGREES'}")
    if not ok:
        raise ClipRomError(
            f"ground: the donor corroboration DISAGREES. {clip.donor}:{clip.zone} puts "
            f"the player at ({sx}, {sy}), so with PLAYER_Y_RADIUS {radius} the floor "
            f"should be at y={feet}..{feet + 16} in the act; the ROM's collision says "
            f"{surface}. A difference that is a multiple of 8 or 16 is a PASTE SHIFT — "
            f"the failure R12 exists to stop, which moves ground without moving art and "
            f"which no screenshot shows.")
    return res


def _engine_const(name, path=None):
    from fg_working_set import ConstantSource
    src = ConstantSource()
    src.load_file(path or os.path.join(REPO, "engine", "system", "constants.emp"))
    return src.get(name)


def engine_spawn(descriptor_path, constants_path=None, grid_path=None):
    """(x, y) world px the boot state puts Player_1 at, DERIVED from the engine.

    Camera_Init seeds Camera_X = (start_sec_x << SECTION_SIZE_SHIFT) + start_local_x
    - CAM_SCREEN_HALF_W, clamped to [0, Camera_X_Max]; the boot state then places
    Player_1 at Camera_X + CAM_SCREEN_HALF_W. The half-screen therefore cancels
    EXCEPT where the clamp bites, which is precisely why this is computed rather than
    assumed to be the descriptor's start_local.
    """
    import re
    from fg_working_set import ConstantSource
    src = ConstantSource()
    src.load_file(constants_path or os.path.join(REPO, "engine", "system", "constants.emp"))
    shift = int(src.get("SECTION_SIZE_SHIFT"))
    half_w = int(src.get("CAM_SCREEN_HALF_W"))
    half_h = int(src.get("CAM_SCREEN_HALF_H"))
    screen_w = int(src.get("SCREEN_WIDTH"))
    screen_h = int(src.get("SCREEN_HEIGHT"))
    text = open(descriptor_path).read()

    def field(name):
        m = re.search(rf"^\s*{name}:\s*(\$?[0-9A-Fa-f]+|GRID_[WH])", text, re.M)
        if not m:
            raise ClipRomError(f"engine_spawn: {descriptor_path} has no {name}: field")
        v = m.group(1)
        return int(v[1:], 16) if v.startswith("$") else int(v)

    # THE GRID IS NOT IN THE DESCRIPTOR ANY MORE (parcel 9): it is the generated
    # act_grid.emp, which is what bounds the clamp below. `grid_path` exists so a test can
    # move the grid and the spawn fields independently.
    gw, gh = act_grid.descriptor_grid(grid_path or act_grid.ACT_GRID_EMP)
    cam_x = (field("start_sec_x") << shift) + field("start_local_x") - half_w
    cam_y = (field("start_sec_y") << shift) + field("start_local_y") - half_h
    cam_x = max(0, min(cam_x, (gw << shift) - screen_w))
    cam_y = max(0, min(cam_y, (gh << shift) - screen_h))
    return cam_x + half_w, cam_y + half_h


def attr_byte_at(gen_dir, grid_w, sect_px, world_x, world_y, plane="a"):
    """The plane-A collision attr byte the ROM carries for one world pixel.

    Read out of `sec{N}_strips_a.bin` — the bake's own emitted strips, which are what
    `ojz_block_gen` packs into the block stream. Strip layout, from
    `ojz_strip_gen.write_strips_to_file`: one 776-byte record per tile COLUMN, holding
    256 big-endian nametable words, then 128 plane-A collision bytes, then 128 plane-B,
    then 8 pad. A collision row is 16 px; `collision_lookup.emp` picks it with one
    `lsr.w #1` off the tile row, which is this file's `// 16`.
    """
    import struct as _s
    sect_tiles = sect_px // 8
    sx, lx = divmod(world_x // 8, sect_tiles)
    sy, ly = divmod(world_y // 8, sect_tiles)
    n = sy * grid_w + sx
    path = os.path.join(gen_dir, f"sec{n}_strips_a.bin")
    stride = 776
    nt_bytes = 512
    coll_rows = 128
    off = stride * lx + nt_bytes + (0 if plane == "a" else coll_rows) + (ly // 2)
    with open(path, "rb") as fh:
        fh.seek(off)
        b = fh.read(1)
    if len(b) != 1:
        raise ClipRomError(f"attr_byte_at: {path} is short at offset {off}")
    return b[0]


# ---------------------------------------------------------------------------
# CLI — a MODES table, dispatched BEFORE any handler runs (tools/test_cli_dispatch.py's
# rule for a tool that OVERWRITES tracked bytes: an unrecognised mode must write
# nothing, and main() raises SystemExit rather than returning).
# ---------------------------------------------------------------------------

def _mode_bake(rest):
    ap = argparse.ArgumentParser(prog="clip_rom_bake.py bake")
    ap.add_argument("manifest")
    ap.add_argument("--donor-root", default=None)
    ap.add_argument("--allow-dirty", action="store_true",
                    help="skip R22 (build.sh's S2CLIP shape owns the restore trap "
                         "and has already checked)")
    ap.add_argument("--keep", action="store_true",
                    help="leave the baked tree in place (stamped) instead of restoring "
                         "it on exit. `ground` and clip_reachability.py need it; "
                         "build.sh's S2CLIP shape passes it and owns its own trap")
    a = ap.parse_args(rest)
    bake(a.manifest, donor_root=a.donor_root,
         skip_clean_check=a.allow_dirty, keep=a.keep)
    return 0


def _mode_ground(rest):
    ap = argparse.ArgumentParser(prog="clip_rom_bake.py ground")
    ap.add_argument("manifest")
    ap.add_argument("--donor-root", default=None)
    a = ap.parse_args(rest)
    ground(a.manifest, donor_root=a.donor_root)
    return 0


def _mode_emit_neutral(rest):
    """Re-write the COMMITTED neutral clip_act.emp (the ROW 7 block). It is what every
    canonical shape compiles; tools/test_clip_two_zone.py holds the committed file to this
    text byte for byte, so a hand edit or a stale copy fails the pre-build lane."""
    if rest:
        print("usage: clip_rom_bake.py emit-neutral")
        return 1
    with open(CLIP_MODULE, "w") as fh:
        fh.write(clip_module_text(None))
    print(f"clip_rom_bake: wrote the neutral {CLIP_MODULE_REL}")
    return 0


MODES = {"bake": _mode_bake, "ground": _mode_ground, "emit-neutral": _mode_emit_neutral}


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    handler = MODES.get(args[0] if args else None)
    if handler is None:
        # STDOUT, like every other MODES-table tool in this repo: the usage IS the
        # refusal's only actionable line, and a caller redirecting stderr would eat it.
        print(f"usage: clip_rom_bake.py {{{'|'.join(MODES)}}} <clips.json> [options]")
        raise SystemExit(1)
    try:
        raise SystemExit(handler(args[1:]))
    except (ClipRomError, clip_manifest.ClipManifestError,
            clip_act_bake.ClipBakeError, clip_act_bake.ClipCollisionError) as exc:
        print(f"clip_rom_bake: REFUSED — {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
