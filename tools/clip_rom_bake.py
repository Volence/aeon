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

  * THE BACKGROUND — NO LONGER (2026-09-25, research (B) parcel B-1). Each donor zone now
    shows its own Sonic 2 background: the start zone's as the act default, every other
    zone's through its region rows, and Oracle Jungle's (with its animation bank) is gone
    from the clip act. See the BACKGROUNDS block. Parallax is still the act default's.
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
import re
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
    if act is not None and crossing_overrides(act)["zone_separation"] == "screen":
        # PER-CLIP OVERRIDE crossing_overrides.zone_separation = screen. What Z1 protects is
        # the palette on SCREEN (its own docstring); the tile-cache window it counts is 20
        # columns wider than the screen on each side, and those margin cells are never
        # displayed. So the override counts the screen instead: no two donor zones may be
        # closer than SCREEN_WIDTH px, i.e. no camera can put both on one screen. Z2 (which
        # walks the actual crossing with the screen's half-width) is the precise statement
        # and still runs; this is the floor under it.
        from fg_working_set import ConstantSource
        src = ConstantSource()
        src.load_file(os.path.join(REPO, "engine/system/constants.emp"))
        need = int(src.get("SCREEN_WIDTH")) // clip_manifest.TILE_PX
        gap = z["min_column_gap_cells"]
        if gap is None or gap < need:
            raise ClipRomError(
                f"Z1 (zone_separation = screen, per-clip override) the narrowest gap between two "
                f"donor zones is {gap} cell(s); a screen is SCREEN_WIDTH / 8 = {need} cells, so "
                f"one camera position can show both zones")
        return {"window": "screen", "need_cells": need, "gap_cells": gap,
                "tile_cache_windows_mixed": z["mixed"]}
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
# own palettes and its own region table in a GENERATED module, `clip_act.emp` (plus a data block
# appended to the regenerated entity_data.emp — see CLIP_DATA_REL), which is
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
# (it is unused data in a clip ROM), and the objects and rings are still the shipped act's.
# The BACKGROUND stopped being inherited on 2026-09-25: see the BACKGROUNDS block.

CLIP_MODULE_REL = GEN_REL + "/clip_act.emp"
CLIP_MODULE = os.path.join(REPO, CLIP_MODULE_REL)
CLIP_MODULE_NAME = "games.sonic4.ojz_clip_act_act1"
#: WHERE THE CLIP ACT'S BYTES GO: appended to the END of `entity_data.emp`, the module
#: tools/ojz_entity_gen.py writes — which the clip bake itself regenerates (ojz_strip_gen
#: Pass 8), so in the S2CLIP shape the whole file is already this bake's output. Its
#: section `entity_data` is placed by its head label `OJZ_Sec0_TypeTable`; appended bytes
#: follow in source order and leave the head alone. The clip MODULE carries no data at all.
#:
#: ⚠ WHY THERE, AND WHY NOT A SECTION OF ITS OWN — three measured refusals, 2026-09-25:
#:   1. A module of its own declared `in ojz_effects_editor_act1` (effects_gen's section,
#:      placed by NAME, so no map.toml row) landed its data AHEAD of effects_gen's block,
#:      `OJZ_Clip_Palette_0` became the section's head label, and sigil refused:
#:      `[layout.undeclared-alignment] ... head label OJZ_Clip_Palette_0 has NO declared
#:      alignment` — sigil keys section alignment by HEAD LABEL (sigil-harness
#:      section_align.rs), and a new row there is a sigil change this lane may not make.
#:   2. Renaming that module and file so both sort after effects_scenes changed nothing —
#:      the build refused identically. The intra-section order is not the name order.
#:   3. Appended to effects_scenes.emp itself, the build linked — and `effects_gen.py check`
#:      (build.sh, strict) then refused the tree as DRIFT, correctly: that file is
#:      effects_gen's output and the clip bake does not own it.
#:   entity_data.emp is the one generated module the clip bake REGENERATES whose section is
#:   placed by a head label the appended bytes cannot displace, and no lane holds its text to
#:   another generator. The honest home is a section of the clip act's own — a map.toml row
#:   plus a sigil section_align row — booked in docs/DEFERRED_WORK.md (row 7's entry).
CLIP_DATA_REL = GEN_REL + "/entity_data.emp"
CLIP_DATA = os.path.join(REPO, CLIP_DATA_REL)
CLIP_DATA_MODULE = "games.sonic4.ojz_entity_data_act1"

_CLIP_HEADER = """\
// AUTO-GENERATED by tools/clip_rom_bake.py — DO NOT EDIT.
//
// THE CLIP ACT'S OWN REGIONS AND PALETTES (S2-COMPRESSED-ACT row 7). act_descriptor.emp
// binds `act_regions` / `act_region_count` through `ojz_clip_act_regions(hand:)` and
// `OJZ_CLIP_ACT` below; see the ROW 7 block in tools/clip_rom_bake.py for the design.
//
"""


CLIP_DATA_BEGIN = "// ==== BEGIN CLIP ACT DATA (tools/clip_rom_bake.py, S2-COMPRESSED-ACT row 7) ===="
CLIP_DATA_END = "// ==== END CLIP ACT DATA ===="
#: The imports the appended block needs, inserted after the module's own `use` block (an
#: import is a declaration of the module, not of the block).
CLIP_DATA_USES = ("use engine.structs.{Region}\n"
                  "use engine.effects.preset.{EffectsPreset, preset}\n"
                  "use engine.effects.raster.{Raster_Program_None}\n"
                  "use engine.effects.palette.{Pal_Cycle_None}\n")
#: Only when a zone carries a region background (the BACKGROUNDS block).
CLIP_DATA_BG_USES = "use engine.bg.{BG_LAYOUT_SIZE}\n"


def _region_rows_text(plan):
    # The trailing comma goes BEFORE the comment: a comma after `//` is inside the comment
    # (measured — the first emission of this table did that and sigil refused row 2).
    # rg_bg_layout / rg_bg_tiles: 0 is "the act's own" (the start zone's background, the
    # BACKGROUNDS block); a row of any other zone names that zone's own blobs.
    return "\n    ".join(
        f"Region{{ rg_x0: {r['x0']}, rg_x1: {r['x1']}, rg_y0: {r['y0']}, rg_y1: {r['y1']}, "
        f"rg_effects: {r['preset_label']}, rg_parallax: 0, "
        f"rg_bg_layout: {r.get('bg_layout') or 0}, rg_bg_span: 0, "
        f"rg_bg_tiles: {r.get('bg_tiles') or 0} }},  // {r['why']}"
        for r in plan["rows"])


def _region_bg_labels(plan):
    """Every per-zone background label the rows name, in zone order (none for the act
    default's zone)."""
    return [lab for z in plan["zones"] for lab in (z.get("bg_layout_label"),
                                                  z.get("bg_tiles_label")) if lab]


def _scroll_zones(plan):
    """[(zone key, scroll spec)] for every zone the SCROLL block derived one for, in key order."""
    return [(z["key"], z["scroll"]) for z in plan["zones"] if z.get("scroll")]


def clip_module_text(plan=None):
    """The clip module's text. `plan` None is the NEUTRAL module the tree commits: no clip
    act, the chooser hands back the descriptor's own table, zero bytes and zero labels — so
    the canonical ROMs are the shipped act exactly. A plan (from `region_plan`) is a clip
    act: its constants, its region ROWS (for the descriptor's table walk) and the chooser.
    It carries NO data — the bytes are `clip_data_block`'s, appended to entity_data.emp."""
    if plan is None:
        return (_CLIP_HEADER +
                "// THIS IS THE NEUTRAL MODULE — the one the tree commits and the canonical\n"
                "// build reads. OJZ_CLIP_ACT = 0: the descriptor's own region table stands,\n"
                "// the chooser returns `hand`, and nothing here emits a byte or a label. An\n"
                "// S2CLIP build overwrites this file and build.sh's EXIT trap restores it.\n\n"
                f"module {CLIP_MODULE_NAME}\n\n"
                "pub const OJZ_CLIP_ACT = 0\n"
                "// The clip act's VDP register-7 byte (backdrop line/entry). Read ONLY under\n"
                "// `if OJZ_CLIP_ACT == 1` (games/sonic4/test/ojz_scroll_test.emp), so this 0\n"
                "// is never written by a canonical shape; the boot table's $00 stands.\n"
                "pub const OJZ_CLIP_BACKDROP = 0\n"
                "pub const OJZ_CLIP_REGION_ROWS: array = []\n\n"
                "pub comptime fn ojz_clip_act_regions(hand: Label) -> Label {\n"
                "    return hand\n"
                "}\n")
    presets = ", ".join([z["preset_label"] for z in plan["zones"]] + _region_bg_labels(plan))
    n = len(plan["rows"])
    backdrop = plan.get("backdrop_reg", 0)
    return (_CLIP_HEADER +
            f"// CLIP ACT {plan['act']} — {len(plan['zones'])} donor zone(s), {n} region row(s).\n"
            "// Written by a THROWAWAY S2CLIP bake; build.sh's EXIT trap restores the neutral\n"
            "// module. Never commit this version. The palettes, presets and the emitted table\n"
            f"// are appended to {CLIP_DATA_REL} (between its CLIP ACT DATA markers).\n\n"
            f"module {CLIP_MODULE_NAME}\n\n"
            "use engine.structs.{Region}\n"
            f"use {CLIP_DATA_MODULE}.{{{presets}}}\n\n"
            "pub const OJZ_CLIP_ACT = 1\n"
            "// VDP register 7 (backdrop = CRAM line/entry), Sonic 2's own `Level:` write\n"
            "// (`move.w #$87xx`), read out of the donor's s2.asm by tools/clip_bg_lower.py.\n"
            f"pub const OJZ_CLIP_BACKDROP = ${backdrop:02X}\n\n"
            "// The rows the descriptor re-checks. The SAME text is emitted as the table\n"
            "// `OJZ_Clip_Regions` in the data block; Z2 holds the two byte-identical.\n"
            f"pub const OJZ_CLIP_REGION_ROWS: [Region; {n}] = [\n    {_region_rows_text(plan)}\n]\n\n"
            "// `OJZ_Clip_Regions` is not imported at the call site: a comptime fn's free names\n"
            "// resolve THERE (docs/EMP_PITFALLS.md §2), and an unknown name in a Label position\n"
            "// becomes a link extern — the route effects_gen's choosers already take.\n"
            "pub comptime fn ojz_clip_act_regions(hand: Label) -> Label {\n"
            "    return OJZ_Clip_Regions\n"
            "}\n")


def clip_data_block(plan):
    """The clip act's BYTES: per zone a palette and an EffectsPreset, then the region table
    the Act names. Appended to entity_data.emp so they follow its own data."""
    out = [CLIP_DATA_BEGIN + "\n",
           f"// CLIP ACT {plan['act']}. A THROWAWAY S2CLIP bake appended this; build.sh's EXIT\n"
           "// trap restores the committed file. NOT effects_gen output — never commit it.\n"]
    snap = (plan.get("overrides") or {}).get("palette") == "snap"
    scrolled = _scroll_zones(plan)
    if scrolled:
        import clip_bg_scroll as CBS
        out.append(CBS.data_block_text(scrolled, plan["act_span"]))
    for z in plan["zones"]:
        words = z["palette_words"]
        body = ",\n    ".join(", ".join(f"${w:04X}" for w in words[i:i + 8])
                              for i in range(0, 48, 8))
        why = ("// transition: 0 — PER-CLIP OVERRIDE crossing_overrides.palette = snap: the "
               "palette is\n// installed in one frame while the screen shows only line-0 "
               "corridor (Z2 holds it).\n" if snap else
               "// transition: 1 — the 16-frame cross-fade arms on EVERY install of this "
               "preset,\n// so the crossing fades both ways (engine/effects/preset.emp).\n")
        out.append(
            f"// zone key {z['key']}: {z['donor']} {z['zone']} — the donor's own 96 palette "
            f"bytes (CRAM lines 1-3),\n// {z['palette_file']} sha256 {z['palette_sha256']}\n"
            f"pub data {z['palette_label']}: [u16; 48] = [\n    {body}\n]\n"
            + why +
            f"pub data {z['preset_label']}: EffectsPreset = preset(pal: {z['palette_label']}, "
            + (f"parallax: {z['parallax_label']}, " if z.get("parallax_label") else "")
            + "raster: Raster_Program_None, cycle: Pal_Cycle_None, "
            + f"transition: {0 if snap else 1})\n")
    n = len(plan["rows"])
    out.append(f"pub data OJZ_Clip_Regions: [Region; {n}] = [\n    {_region_rows_text(plan)}\n]\n")
    for z in plan["zones"]:
        if not z.get("bg_layout_label"):
            continue
        bg = z["bg"]
        # TYPED, both of them, like act_assets.emp's act default: the length is the guard.
        # (align: 2) on the tile blob because it is a DMA SOURCE — BG_Stream_Update's
        # overwrite queues it word-wise and raise_errors on an odd address in DEBUG.
        tiles_line = (f"pub data {z['bg_tiles_label']} (align: 2): [u8; {z['bg_tiles_bytes']}] = "
                      f"embed(\"{z['bg_tiles_embed']}\")\n" if z.get("bg_tiles_label") else
                      "// NO tile blob: PER-CLIP OVERRIDE crossing_overrides.background = "
                      "co_resident. This zone's\n// tiles are inside the act default's blob "
                      "(rg_bg_tiles 0), so the crossing overwrites nothing.\n")
        out.append(
            f"// zone key {z['key']}: {z['donor']} {z['zone']}'s own Sonic 2 background "
            f"(tools/clip_bg_lower.py): {bg['tiles']} tiles,\n// crop start chunk "
            f"{bg['crop_start_chunk']} of a {bg['period_cells']}-cell period, invented-seam "
            f"cost {bg['seam_cost_pixels']} px. Named by this zone's region rows.\n"
            f"pub data {z['bg_layout_label']} (align: 2): [u8; BG_LAYOUT_SIZE] = "
            f"embed(\"{z['bg_layout_embed']}\")\n" + tiles_line)
    out.append(CLIP_DATA_END + "\n")
    return "".join(out)


def append_clip_data(plan, path=CLIP_DATA):
    """Insert CLIP_DATA_USES after the module's `use` block and append the data block.
    Refuses a file that already carries a block (a stale throwaway) rather than stacking."""
    text = open(path).read()
    if CLIP_DATA_BEGIN in text:
        raise ClipRomError(
            f"{os.path.relpath(path, REPO)} already carries a CLIP ACT DATA block — a previous "
            f"clip bake's throwaway was not restored. git checkout -- {GEN_REL}")
    lines = text.split("\n")
    heads = [i for i, ln in enumerate(lines) if ln.startswith("use ")] or \
            [i for i, ln in enumerate(lines) if ln.startswith("module ")]
    if not heads:
        raise ClipRomError(f"{os.path.relpath(path, REPO)} has no `module` line — not the "
                           f"generated module this bake appends to")
    uses = CLIP_DATA_USES + (CLIP_DATA_BG_USES if _region_bg_labels(plan) else "")
    scrolled = _scroll_zones(plan)
    if scrolled:
        import clip_bg_scroll as CBS
        uses += CBS.data_uses([len(spec["bands"]) for _k, spec in scrolled])
    lines.insert(max(heads) + 1, "// clip act (row 7) imports, with the appended block below\n"
                 + uses.rstrip("\n"))
    text = "\n".join(lines).rstrip("\n") + "\n\n" + clip_data_block(plan)
    with open(path, "w") as fh:
        fh.write(text)


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


#: Frames a SNAP install takes to reach the screen, counted the way Z2 counts the fade (the
#: camera may travel this many CAM_MAX_X_STEPs after the crossing frame before the new
#: palette is certain to be scanned out). The install runs in the crossing tick
#: (Parallax_CheckBoundary -> Effects_InstallPreset -> Palette_LoadPal's snap arm), the base
#: copy in that tick's Palette_Compose (engine/system/game_loop.emp, after the state), and
#: the CRAM DMA in the VBlank that ships the same tick's HScroll — so 0 frames when the
#: Critical queue accepts the line, and ONE more when it refuses it and
#: Enqueue_Dirty_Buffers leaves the line dirty for the next VBlank (buffers.emp `bcs`).
#: 1 is that worst case. Measured by tools/crossing_witness.py (docs/research/
#: 2026-09-25-shorter-connector.md), not assumed.
SNAP_FRAMES = 1

#: The manifest key a clip act uses to change HOW its zones cross, and the only values it
#: may take. Absent = the rule every clip act gets: a 16-frame palette cross-fade and a
#: background whose tiles are overwritten at the crossing. Any other value is a NAMED,
#: PER-CLIP override — reported loudly by the bake, carried with a `why`, and it never
#: changes what an act without the key is held to.
CROSSING_OVERRIDES_KEY = "crossing_overrides"
CROSSING_OVERRIDE_VALUES = {"palette": ("fade", "snap"),
                            "background": ("overwrite", "co_resident"),
                            "zone_separation": ("tile_cache", "screen"),
                            "crossing_margin": ("enforce", "report")}


def crossing_overrides(act):
    """The act's `crossing_overrides`, validated: {"palette", "background", "why",
    "declared"}. `declared` is False for an act without the key (the defaults)."""
    raw = (getattr(act, "raw", None) or {}).get(CROSSING_OVERRIDES_KEY)
    out = {"palette": "fade", "background": "overwrite", "zone_separation": "tile_cache",
           "crossing_margin": "enforce", "why": None, "declared": False}
    if raw is None:
        return out
    if not isinstance(raw, dict):
        raise ClipRomError(f"{CROSSING_OVERRIDES_KEY} must be an object")
    unknown = sorted(set(raw) - set(CROSSING_OVERRIDE_VALUES) - {"why"})
    if unknown:
        raise ClipRomError(f"{CROSSING_OVERRIDES_KEY} carries {unknown}; the keys it may "
                           f"carry are {sorted(CROSSING_OVERRIDE_VALUES)} and `why`")
    for k, allowed in CROSSING_OVERRIDE_VALUES.items():
        if k in raw:
            if raw[k] not in allowed:
                raise ClipRomError(f"{CROSSING_OVERRIDES_KEY}.{k} is {raw[k]!r}; it may be "
                                   f"one of {list(allowed)}")
            out[k] = raw[k]
    if not (isinstance(raw.get("why"), str) and raw["why"].strip()):
        raise ClipRomError(f"{CROSSING_OVERRIDES_KEY} without a `why`: an override of how "
                           f"zones cross is the author's decision and has to say why")
    out["why"], out["declared"] = raw["why"], True
    return out


def background_constants():
    """(overwrite chunk bytes, wipe rows per frame, rows the screen can show) — READ from the
    engine (engine/level/bg.emp and the files its expressions reach), never typed.

    The wipe rate is BG_WIPE_DMA_ROWS: every clip background is ONE plane tall
    (clip_bg_lower lowers to the plane, rows carry rg_bg_span 0), and since 2026-09-25 a
    one-plane map is swept by DMA from ROM (BG_Stream_Update's `.wipe_dma`) at that many rows
    a frame, not by the CPU path's BG_WIPE_ROWS_PER_FRAME."""
    from fg_working_set import ConstantSource
    src = ConstantSource()
    for path in ("engine/system/constants.emp", "engine/level/parallax.emp",
                 "engine/level/bg.emp"):
        src.load_file(os.path.join(REPO, path))
    return (int(src.get("BG_OVERWRITE_CHUNK_BYTES")), int(src.get("BG_WIPE_DMA_ROWS")),
            int(src.get("BG_SCREEN_ROWS")))


def background_switch_frames(plan, consts=None):
    """{zone key: frames the background takes to settle when the camera crosses INTO that
    zone}, from the blobs the plan emitted — the term Z2 did not have until 2026-09-25.

    THE MECHANISM (engine/level/bg.emp, BG_Stream_Update). On the crossing frame the region
    names a tile blob; if the arena does not already hold it, ONE chunk of
    BG_OVERWRITE_CHUNK_BYTES is queued per frame until it has all landed, and the wipe and
    the streamer are SUSPENDED for the whole overwrite (the plane shows the old layout over
    tiles that are being replaced — garbage, if it is on screen). Then the wipe repaints the
    plane BG_WIPE_ROWS_PER_FRAME rows a frame starting at the top VISIBLE row, so the rows
    the screen can show are repainted after ceil(BG_SCREEN_ROWS / BG_WIPE_ROWS_PER_FRAME)
    frames. A zone whose effective blob is the one the arena already holds (co-resident)
    pays no overwrite at all.

    MODEL = chunks + visible-wipe frames. MEASURED against tools/crossing_witness.py on the
    landed s2_ehz_cpz (crc e4ce79c9, the CPU sweep at 4 rows a frame): CPZ 7584 B -> 5 + 8 = 13
    modelled, 12 measured; EHZ 4512 B -> 3 + 8 = 11 modelled, 10-11 measured. The model is
    conservative by <= 1 frame (the completion frame falls through into the wipe's first
    rows). The DMA sweep (BG_WIPE_DMA_ROWS a frame) re-measured in the research doc."""
    chunk, rows_per_frame, screen_rows = consts or background_constants()
    wipe = -(-screen_rows // rows_per_frame)
    blob_of = {}
    for z in plan["zones"]:
        lab = z.get("bg_tiles_label")
        blob_of[z["key"]] = lab if lab else "__act_default__"
    out = {}
    for z in plan["zones"]:
        others = {blob_of[o["key"]] for o in plan["zones"] if o["key"] != z["key"]}
        if others == {blob_of[z["key"]]}:
            chunks = 0                  # every other zone's rows already hold this blob
        else:
            nbytes = z.get("bg_tile_bytes_effective")
            if nbytes is None:
                raise ClipRomError(f"Z2 the background switch into {z.get('zone')} cannot be "
                                   f"timed: the plan carries no tile-blob size for it — "
                                   f"UNMEASURABLE")
            chunks = -(-nbytes // chunk)
        out[z["key"]] = chunks + wipe
    return out


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
            "overrides": crossing_overrides(act),
            "crossings": [{"x": c[0], "from_key": c[1], "to_key": c[2], "corridor": c[3],
                           "gap": [c[4], c[5]]} for c in cuts]}


_ROW_RE = None


def _parse_rows(text, name, what):
    import re
    global _ROW_RE
    if _ROW_RE is None:
        _ROW_RE = re.compile(
            r"Region\{\s*rg_x0:\s*(\d+),\s*rg_x1:\s*(\d+),\s*rg_y0:\s*(\d+),\s*rg_y1:\s*(\d+),"
            r"\s*rg_effects:\s*(\w+)")
    m = re.search(name + r":\s*\[Region;\s*(\d+)\]\s*=\s*\[(.*?)\n\]", text, re.S)
    if not m:
        raise ClipRomError(f"Z2 {what} carries no {name} table — UNMEASURABLE")
    rows = [(int(a), int(b), int(c), int(d), e) for a, b, c, d, e in _ROW_RE.findall(m.group(2))]
    if len(rows) != int(m.group(1)):
        raise ClipRomError(f"Z2 {what} declares {m.group(1)} rows for {name} and {len(rows)} "
                           f"parse — UNMEASURABLE")
    return rows


def parse_clip_module_rows(mod_text, data_text):
    """The region rows back OUT of what was EMITTED: [(x0, x1, y0, y1, preset label)] and
    {preset label: (palette label, transition)}. Z2 runs on THIS, not on the plan, so it
    measures what the ROM will carry. The descriptor checks the module's
    `OJZ_CLIP_REGION_ROWS`; the Act names the data block's `OJZ_Clip_Regions`; they are one
    table written twice, and a difference between them is refused here by name."""
    import re
    rows = _parse_rows(mod_text, "OJZ_CLIP_REGION_ROWS", "the clip module")
    emitted = _parse_rows(data_text, "OJZ_Clip_Regions", "the clip data block")
    if rows != emitted:
        raise ClipRomError(
            f"Z2 the rows the descriptor checks (OJZ_CLIP_REGION_ROWS, {len(rows)}) are not the "
            f"rows the Act names (OJZ_Clip_Regions, {len(emitted)}): {rows} vs {emitted}")
    presets = {p: (pal, int(t)) for p, pal, t in re.findall(
        r"pub data (OJZ_Clip_Preset_\d+): EffectsPreset = preset\(pal: (\w+),"
        r"[^\n]*?transition: (\d)\)", data_text)}
    return rows, presets


def check_palette_crossings(act, mod_text, data_text, consts=None, log=None, bg_frames=None):
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

    THE BACKGROUND TERM (2026-09-25, docs/research/2026-09-25-shorter-connector.md). The
    region also switches the BACKGROUND, and that takes frames too (background_switch_frames:
    the tile overwrite, then the visible-row wipe). tools/crossing_witness.py measured it on
    the landed act at 12 frames into CPZ and 10-11 into EHZ, no shorter than the 11-12-frame
    fade those palettes actually take, so it was a real floor and nothing modelled it.
    `bg_frames` ({zone key: frames to settle INTO that zone}) adds it: the side of the
    crossing a zone lies on needs HALF_W + STEP x max(palette frames, that zone's background
    frames). For an act on the default rule (fade 16, backgrounds <= 16) that is exactly the
    old HALF_W + FADE x STEP both sides; None (a caller with no plan) leaves it at 0.

    THE SNAP OVERRIDE. With `crossing_overrides.palette = "snap"` (a named, per-clip
    override, see crossing_overrides) every preset must carry transition 0 instead, and the
    palette term is SNAP_FRAMES instead of PAL_FADE_FRAMES: the swap is instant, so what has
    to be true is only that the screen shows no zone cell on the frames it lands. The
    tunnel is drawn on CRAM line 0, which no install writes. An act WITHOUT the override is
    held to the fade exactly as before, and a transition-0 preset there is still refused.
    """
    fade, step, half_w = consts or crossing_constants()
    ov = crossing_overrides(act)
    want_trans = 0 if ov["palette"] == "snap" else 1
    pal_frames = SNAP_FRAMES if want_trans == 0 else fade
    bgf = bg_frames or {}
    rows, presets = parse_clip_module_rows(mod_text, data_text)
    if not presets:
        raise ClipRomError("Z2 no OJZ_Clip_Preset_* records parse out of the clip data "
                           "block — UNMEASURABLE")
    unbound = sorted({r[4] for r in rows} - set(presets))
    if unbound:
        raise ClipRomError(f"Z2 region rows bind {unbound}, which the data block does not "
                           f"define as presets")
    for lab, (_pal, trans) in presets.items():
        if trans != want_trans and want_trans == 1:
            raise ClipRomError(f"Z2 {lab} does not arm the cross-fade (transition {trans}); "
                               f"the crossing would SNAP the palette")
        if trans != want_trans:
            raise ClipRomError(f"Z2 {lab} carries transition {trans}, but this act's "
                               f"{CROSSING_OVERRIDES_KEY}.palette = snap says every crossing "
                               f"snaps (transition 0)")

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
        reported = False
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
            fr_l = max(pal_frames, bgf.get(a.zone_key, 0))
            fr_r = max(pal_frames, bgf.get(b.zone_key, 0))
            need_l, need_r = half_w + fr_l * step, half_w + fr_r * step
            short_l, short_r = need_l - (x_c - a_right), need_r - (b_left - x_c)
            if (short_l > 0 or short_r > 0) and ov["crossing_margin"] == "report":
                # PER-CLIP OVERRIDE crossing_overrides.crossing_margin = report: a LIMIT TEST
                # the owner asked to see glitch. The shortfall is NOT waived silently: it is
                # printed on every bake and returned, in frames at the camera cap.
                shortfall = {"left_px": max(0, short_l), "right_px": max(0, short_r),
                             "left_frames": -(-max(0, short_l) // step),
                             "right_frames": -(-max(0, short_r) // step)}
                if log and not reported:
                    reported = True
                    log("clip_rom_bake: " + "!" * 72)
                    log(f"clip_rom_bake: Z2 SHORTFALL, NOT ENFORCED (per-clip override "
                        f"crossing_margin = report): the crossing at x={x_c} has "
                        f"{x_c - a_right} px left / {b_left - x_c} px right and the rule needs "
                        f"{need_l} / {need_r}. Expect up to {shortfall['left_frames']} frame(s) "
                        f"arriving LEFT and {shortfall['right_frames']} arriving RIGHT, at the "
                        f"camera cap, where the far zone is on screen before its palette or "
                        f"background has landed")
                    log("clip_rom_bake: " + "!" * 72)
            elif x_c - need_l < a_right or x_c + need_r > b_left:
                what = "a cross-fade" if want_trans == 1 else "a SNAP (per-clip override)"
                pal_term = (f"PAL_FADE_FRAMES {fade}" if want_trans == 1
                            else f"SNAP_FRAMES {SNAP_FRAMES}")
                raise ClipRomError(
                    f"Z2 the crossing from {a.id!r} to {b.id!r} is at x={x_c}, but {what} "
                    f"needs {need_l} px of corridor on the left of it and {need_r} on the "
                    f"right (CAM_SCREEN_HALF_W {half_w} + CAM_MAX_X_STEP {step} x the larger "
                    f"of {pal_term} and the background switch into that side's zone, "
                    f"{bgf.get(a.zone_key, 0)} / {bgf.get(b.zone_key, 0)} frames) and the "
                    f"corridor runs x {a_right}..{b_left - 1}: {x_c - a_right} px on the "
                    f"left, {b_left - x_c} on the right")
        out.append({"from": a.id, "to": b.id, "x": x_c, "margin_needed": max(need_l, need_r),
                    "shortfall": shortfall if ov["crossing_margin"] == "report" and
                    (short_l > 0 or short_r > 0) else None,
                    "margin_needed_left": need_l, "margin_needed_right": need_r,
                    "palette": "snap" if want_trans == 0 else "fade",
                    "palette_frames": pal_frames,
                    "background_frames": [bgf.get(a.zone_key, 0), bgf.get(b.zone_key, 0)],
                    "margin_left": x_c - a_right, "margin_right": b_left - x_c,
                    "ys_walked": len(list(ys))})
        if log:
            log(f"clip_rom_bake: Z2 {a.id} -> {b.id}: ONE preset install and ONE palette "
                f"change at x={x_c} on every one of {len(list(ys))} corridor rows; "
                f"{x_c - a_right} px of corridor left of it and {b_left - x_c} right, "
                f"{need_l} / {need_r} needed (palette {'SNAP' if want_trans == 0 else 'fade'} "
                f"{pal_frames} frames, background switch {bgf.get(a.zone_key, 0)} / "
                f"{bgf.get(b.zone_key, 0)} frames)")
    return out


# ---------------------------------------------------------------------------
# EACH ZONE'S OWN SONIC 2 BACKGROUND (research 2026-09-25 (B), parcel B-1)
# ---------------------------------------------------------------------------
#
# WHAT THIS REPLACES. Until B-1 the clip bake re-ran tools/inject_editor_bg.py on the
# SHIPPED act's editor_bg_override.json, so every clip act showed Oracle Jungle's
# editor-drawn background (recoloured by whichever Sonic 2 palette was installed) and
# carried its 8 KB animation bank, which is `default_off` and which nothing in a clip act
# can switch on except the DEBUG effects lab — where it would animate OJZ art over a
# Sonic 2 picture. The owner flew it and asked for "the bgs ... from the games".
#
# THE DESIGN (research doc §4.2), and why each half is where it is:
#   * THE START ZONE'S BACKGROUND IS THE ACT DEFAULT. BG_Init blits Act.act_bg_layout
#     before the camera exists (BG-BOOT-REGION-BLIT), so the boot picture is right only if
#     the zone the act starts in IS the default. "Starts in" is DERIVED: the region row
#     that holds the spawn engine_spawn() re-derives from the descriptor and the engine's
#     camera constants — never "clip 0". It is written by inject_editor_bg.main() itself,
#     handed a synthetic override (clip_bg_lower.override_doc) with no `anims`, so
#     zone_bg.bin, bg_tiles.bin and a ZERO-BAND bg_anim.emp (`BgAnim_Banks = Data.empty`)
#     come out of the shipped emitter, not a copy of it. That drops the OJZ bank.
#   * EVERY OTHER ZONE GETS A REGION OVERRIDE: its layout and tile blobs are written into
#     the generated tree (clip_bg_*_<key>.bin, removed by the trap's `git clean`),
#     embedded in the CLIP ACT DATA block and named by that zone's rows through the
#     existing rg_bg_layout / rg_bg_tiles fields. The crossing's tile overwrite and repaint
#     (engine/level/bg.emp BG_Stream_Update) are the region-BG-switch machinery, unchanged.
#   * THE BACKDROP. A Sonic 2 sky is mostly colour-0 pixels over the backdrop register,
#     which S2 sets to line 2 entry 0 ($8720) and Aeon boots at $00 (black). The clip
#     module carries that byte as OJZ_CLIP_BACKDROP, and ojz_scroll_test.emp's level init
#     stores it into the VDP shadow under `if OJZ_CLIP_ACT == 1` — zero bytes in every
#     canonical shape, whose neutral module says OJZ_CLIP_ACT = 0.
#   * PARALLAX IS THE SCROLL BLOCK's (below, parcel B-2): each zone's preset binds its own
#     Sonic 2 scroll through preset(parallax:). Rows keep rg_parallax 0 — the preset's binding
#     is the rung Effects_ResolveParallax falls to — so the row text Z2 and BG1 read is unchanged.
#
# BG1 (check_backgrounds) re-reads what was EMITTED: the rows' background fields parsed
# back out of both module texts, and the blobs on disk against a fresh lowering.

CLIP_BG_LAYOUT_BIN = "clip_bg_layout_{key}.bin"
CLIP_BG_TILES_BIN = "clip_bg_tiles_{key}.bin"
DEFAULT_BG_OVERRIDE = "clip_bg_act_default.json"


def start_zone_key(plan, spawn):
    """The zone key of the ONE region row holding the spawn point (x, y)."""
    x, y = spawn
    hit = [r for r in plan["rows"] if r["x0"] <= x <= r["x1"] and r["y0"] <= y <= r["y1"]]
    if len(hit) != 1:
        raise ClipRomError(f"BG1 the spawn ({x}, {y}) is in {len(hit)} region rows; the act "
                           f"default background is the START zone's, so it must be exactly one")
    return hit[0]["key"]


class _ClipDefaultBgAct:
    """An inject_editor_bg.BgActNames with the override and output redirected. Built
    lazily (the injector derives its act from project.json at import)."""

    def __new__(cls, override, out_dir):
        import inject_editor_bg as ieb

        class _Act(ieb.BgActNames):
            def out_dir(self, repo=None):
                return out_dir

            def override_path(self, repo=None):
                return override
        base = ieb.ACT
        return _Act(base.zone_id, base.act_id, base.repo)


def co_resident_backgrounds(plan, own, start, log=None):
    """PER-CLIP OVERRIDE crossing_overrides.background = "co_resident": every zone's
    background tiles in ONE blob, the act default's, so a crossing changes only the LAYOUT
    and BG_Stream_Update overwrites nothing (its `cmpa.l BG_Tiles_Current` finds the arena
    already holding the region's effective blob, rg_bg_tiles 0 = the act default).

    `own` is {zone key: (words, tiles, info)} as clip_bg_lower.lower() returned them. The
    union keeps the start zone's tiles at their own indices and appends every other zone's
    tiles that are not already in it — by clip_bg_lower's CANONICAL form (the least of a
    tile's four flips), which is the form both lowerings store, so a word's flip bits stay
    valid when only its index is rewritten. Returns the same shape with every zone's words
    re-indexed into the union and the union as every zone's tile list.

    WHAT IT MAY SPEND, and why that is legal here only. The arena is BG_TILE_CAPACITY tiles
    (vram.toml bg_region, a hard VRAM boundary: the SAT follows it). BG_STATIC_TILE_BUDGET
    (tiles - band_reserve) is what a STATIC background may use, the reserve being held for
    BgAnim bands. A clip act has NO band (the injector writes its zero-band stub, checked in
    plan_backgrounds), so the union may reach into the reserve; it may never pass the arena.
    Both numbers are printed."""
    from vram_map import BG_TILE_CAPACITY, BG_STATIC_TILE_BUDGET
    order = [start] + sorted(k for k in own if k != start)
    union, index = [], {}
    for t in own[start][1]:
        index.setdefault(t, len(union))
        union.append(t)
    out = {}
    for k in order:
        words, tiles, info = own[k]
        remap = []
        for t in tiles:
            if t not in index:
                index[t] = len(union)
                union.append(t)
            remap.append(index[t])
        new = []
        for i, w in enumerate(words):
            if w == 0:
                new.append(0)
                continue
            nw = (w & ~0x7FF) | remap[w & 0x7FF]
            if nw == 0:
                raise ClipRomError(
                    f"BG co-resident: {info['zone']} cell {i} re-indexes to word $0000, which "
                    f"inject_editor_bg.rebase_layout keeps as the TRANSPARENT word — this "
                    f"opaque tile would vanish")
            # FIDELITY: the union entry the new word names IS the tile the old word named
            if union[nw & 0x7FF] != tiles[w & 0x7FF]:
                raise ClipRomError(f"BG co-resident: {info['zone']} cell {i} re-indexed to a "
                                   f"different tile")
            new.append(nw)
        out[k] = [new, None, dict(info, co_resident=True)]
    if len(union) > BG_TILE_CAPACITY:
        raise ClipRomError(
            f"BG co-resident: the zones' backgrounds need {len(union)} tiles together and the "
            f"arena holds BG_TILE_CAPACITY = {BG_TILE_CAPACITY} (vram.toml bg_region, a hard "
            f"VRAM boundary). They cannot be co-resident; drop the override.")
    for k in out:
        out[k][1] = list(union)
        out[k] = tuple(out[k])
    if log:
        log(f"clip_rom_bake: PER-CLIP OVERRIDE crossing_overrides.background = co_resident — "
            f"{' + '.join(str(len(own[k][1])) for k in order)} tiles of "
            f"{', '.join(own[k][2]['zone'] for k in order)} background share ONE "
            f"{len(union)}-tile blob (the act default); arena {BG_TILE_CAPACITY} tiles, "
            f"static budget {BG_STATIC_TILE_BUDGET}, so "
            + (f"{len(union) - BG_STATIC_TILE_BUDGET} tile(s) of the band reserve are USED "
               f"(legal only because this act has no BgAnim band)"
               if len(union) > BG_STATIC_TILE_BUDGET else "the band reserve is untouched")
            + f"; {BG_TILE_CAPACITY - len(union)} arena tile(s) spare")
    return out


def plan_backgrounds(plan, spawn, gen_dir, baked_dir, lower=None, backdrop=None, log=None):
    """Lower every zone's own background, write the act default through the shipped
    injector and each other zone's blobs into `gen_dir`, and bind them into `plan` (zones
    and rows) for the module and data-block emitters. Returns the default zone's key."""
    import clip_bg_lower as CBL
    lower = lower or CBL.lower
    start = start_zone_key(plan, spawn)
    co_resident = (plan.get("overrides") or {}).get("background") == "co_resident"
    lowered, own = {}, {}
    for z in plan["zones"]:
        own[z["key"]] = lower(z["donor"], z["zone"])
    if co_resident:
        own = co_resident_backgrounds(plan, own, start, log=log)
    for z in plan["zones"]:
        words, tiles, info = own[z["key"]]
        lowered[z["key"]] = (words, tiles)
        z["bg"] = info
        z["bg_tile_bytes_effective"] = len(tiles) * 32
        if info["line0_cells"] and log:
            log(f"clip_rom_bake: BG WARNING — {z['donor']}:{z['zone']}'s background draws "
                f"{info['line0_cells']} cell(s) on CRAM line 0, the character line; kept as "
                f"the donor has them (TAGGED)")
        if z["key"] == start:
            override = os.path.join(baked_dir, DEFAULT_BG_OVERRIDE)
            with open(override, "w") as fh:
                json.dump(CBL.override_doc(words, tiles), fh)
            import inject_editor_bg as ieb
            ieb.main(_ClipDefaultBgAct(override, gen_dir))
            if co_resident:
                # the co-resident blob may reach into the band reserve ONLY because no band
                # exists to use it: read that back out of what the injector wrote
                with open(os.path.join(gen_dir, "bg_anim.emp")) as fh:
                    if "BgAnim_Table: u16 = 0" not in fh.read():
                        raise ClipRomError(
                            "BG co-resident: the act default's bg_anim.emp is not the "
                            "zero-band stub, so the band reserve the shared blob uses may "
                            "be claimed by a band — refused")
            z["bg_role"] = "act_default"
            continue
        z["bg_role"] = "region"
        lay = CLIP_BG_LAYOUT_BIN.format(key=z["key"])
        with open(os.path.join(gen_dir, lay), "wb") as fh:
            fh.write(CBL.layout_blob(words))
        z.update(bg_layout_label=f"OJZ_Clip_BG_Layout_{z['key']}",
                 bg_layout_embed=f"{GEN_REL}/{lay}")
        if co_resident:
            continue                    # its tiles are in the act default's blob
        til = CLIP_BG_TILES_BIN.format(key=z["key"])
        blob = CBL.tiles_blob(tiles)
        with open(os.path.join(gen_dir, til), "wb") as fh:
            fh.write(blob)
        z.update(bg_tiles_label=f"OJZ_Clip_BG_Tiles_{z['key']}",
                 bg_tiles_embed=f"{GEN_REL}/{til}", bg_tiles_bytes=len(blob))
    zones = {z["key"]: z for z in plan["zones"]}
    for r in plan["rows"]:
        r["bg_layout"] = zones[r["key"]].get("bg_layout_label")
        r["bg_tiles"] = zones[r["key"]].get("bg_tiles_label")
    plan["bg_default_key"] = start
    plan["backdrop_reg"] = (CBL.s2_backdrop_register(zones[start]["donor"])
                            if backdrop is None else backdrop)
    plan["_bg_lowered"] = lowered
    if log:
        log("clip_rom_bake: backgrounds — " + "; ".join(
            f"{z['zone']} {z['bg']['tiles']} tiles as the "
            + ("ACT DEFAULT" if z["bg_role"] == "act_default" else "region override")
            for z in plan["zones"]) + f"; backdrop register 7 = ${plan['backdrop_reg']:02X}")
    return start


_BG_ROW_RE = re.compile(r"rg_bg_layout:\s*(\w+),\s*rg_bg_span:\s*(\d+),\s*rg_bg_tiles:\s*(\w+)")


def check_backgrounds(plan, mod_text, data_text, gen_dir):
    """BG1 — each zone is drawn over ITS OWN background, read back out of what was EMITTED.

    * every row in both tables (the descriptor's OJZ_CLIP_REGION_ROWS and the Act's
      OJZ_Clip_Regions) carries rg_bg_span 0, and rg_bg_layout / rg_bg_tiles that are 0 on
      the act-default zone's rows and that zone's OWN pair on every other zone's rows;
    * every label a row names is declared in the data block;
    * the act default on disk (zone_bg.bin, bg_tiles.bin) and every region blob are the
      bytes a fresh lowering of that zone produces — so a skipped or stale write, or the
      shipped act's background left in place, is refused by name."""
    import clip_bg_lower as CBL
    zones = {z["key"]: z for z in plan["zones"]}
    for text, name, what in ((mod_text, "OJZ_CLIP_REGION_ROWS", "the clip module"),
                             (data_text, "OJZ_Clip_Regions", "the clip data block")):
        m = re.search(name + r":\s*\[Region;\s*(\d+)\]\s*=\s*\[(.*?)\n\]", text, re.S)
        got = _BG_ROW_RE.findall(m.group(2)) if m else []
        if len(got) != len(plan["rows"]):
            raise ClipRomError(f"BG1 {what}'s {name} carries {len(got)} background field "
                               f"triple(s) for {len(plan['rows'])} row(s) — UNMEASURABLE")
        for r, (lay, span, til) in zip(plan["rows"], got):
            z = zones[r["key"]]
            # co-resident (per-clip override): the rows name their own LAYOUT and tile blob
            # 0, the act default's, which holds every zone's tiles
            want = ((z["bg_layout_label"], z.get("bg_tiles_label") or "0")
                    if z["key"] != plan["bg_default_key"] else ("0", "0"))
            if (lay, til) != want or span != "0":
                raise ClipRomError(
                    f"BG1 {what}: the row x {r['x0']}..{r['x1']} ({z['zone']}) names "
                    f"background ({lay}, span {span}, {til}); its zone's own is {want}, span 0")
    for lab in _region_bg_labels(plan):
        if not re.search(rf"pub data {lab}\b", data_text):
            raise ClipRomError(f"BG1 a region row names {lab} and the data block declares "
                               f"no such data")
    for key, (words, tiles) in plan["_bg_lowered"].items():
        z = zones[key]
        if z["bg"].get("co_resident"):
            # the planned words are RE-INDEXED, so "bytes of a fresh lowering" is not the
            # comparison: every cell must name, through the shared blob, the same tile with
            # the same flip, line and priority bits as a fresh lowering of its own zone
            fw, ft, _ = CBL.lower(z["donor"], z["zone"])
            for i, (a, b) in enumerate(zip(fw, words)):
                if (a == 0) != (b == 0) or (a & ~0x7FF) != (b & ~0x7FF) or \
                        (a and ft[a & 0x7FF] != tiles[b & 0x7FF]):
                    raise ClipRomError(f"BG1 {z['zone']} cell {i}: the shared blob does not "
                                       f"draw what a fresh lowering draws (word ${a:04X} -> "
                                       f"${b:04X})")
            if len(fw) != len(words):
                raise ClipRomError(f"BG1 {z['zone']}: {len(words)} planned cells against "
                                   f"{len(fw)} lowered")
        if key == plan["bg_default_key"]:
            files = (("zone_bg.bin", CBL.layout_blob(words)), ("bg_tiles.bin", CBL.tiles_blob(tiles)))
        elif not z.get("bg_tiles_label"):          # co-resident: layout only
            files = ((CLIP_BG_LAYOUT_BIN.format(key=key), CBL.layout_blob(words)),)
            if os.path.exists(os.path.join(gen_dir, CLIP_BG_TILES_BIN.format(key=key))):
                raise ClipRomError(f"BG1 {z['zone']} is co-resident but a tile blob "
                                   f"{CLIP_BG_TILES_BIN.format(key=key)} was written for it")
        else:
            files = ((CLIP_BG_LAYOUT_BIN.format(key=key), CBL.layout_blob(words)),
                     (CLIP_BG_TILES_BIN.format(key=key), CBL.tiles_blob(tiles)))
        for fname, want in files:
            with open(os.path.join(gen_dir, fname), "rb") as fh:
                if fh.read() != want:
                    raise ClipRomError(
                        f"BG1 {GEN_REL}/{fname} is not {z['donor']}:{z['zone']}'s lowered "
                        f"background — the write did not happen, or something wrote over it "
                        f"(the shipped act's background, if the injector ran on its own "
                        f"override afterwards)")
    return {"default": zones[plan["bg_default_key"]]["zone"],
            "regions": [zones[k]["zone"] for k in sorted(zones) if k != plan["bg_default_key"]],
            "backdrop_reg": plan["backdrop_reg"]}


# ---------------------------------------------------------------------------
# EACH ZONE'S OWN SONIC 2 SCROLL (research 2026-09-25 (B), parcel B-2)
# ---------------------------------------------------------------------------
#
# B-1 put each zone's own background on Plane B; it scrolled with the act default (OJZ's
# config). This binds each zone's region preset to a parallax record derived from ITS donor's
# s2.asm by tools/clip_bg_scroll.py (EHZ by running SwScrl_EHZ; CPZ read from InitCam_CPZ /
# SwScrl_CPZ). The records are scene_dsl scenes — the engine's existing band mechanism, as
# data; no engine code — emitted into the CLIP ACT DATA block and lowered there by the
# registry's lowerN. A zone with no transcription keeps the act default and the bake SAYS SO.
#
# THE VERTICAL PASTE IS PER ZONE: a scrolling background maps act Y to its plane through
# v_center, and the clip act moved Sonic 2's Y 0 to dst.y - src.y. Every clip of one zone must
# agree on it (one region, one record); two that do not are refused (SC0).
#
# SC1 (check_scroll) re-reads what was EMITTED: each preset binds exactly its own zone's
# record (or none, for a zone with no transcription), every bound record is declared, and the
# scroll block is byte-for-byte a fresh derivation's text.

def plan_scroll(plan, act, log=None, derive=None):
    """Derive each zone's scroll spec and bind its labels into `plan`."""
    import clip_bg_scroll as CBS
    derive = derive or CBS.derive
    plan["act_span"] = act.grid_h * act.section_px
    for z in plan["zones"]:
        dys = sorted({c.dst[1] - c.src[1] for c in act.clips if c.zone_key == z["key"]})
        if len(dys) != 1:
            raise ClipRomError(f"SC0 zone {z['donor']}:{z['zone']} is pasted at {len(dys)} "
                               f"different vertical offsets {dys}; its one region and one "
                               f"scroll record can anchor only one")
        spec = derive(z["donor"], z["zone"], dys[0])
        z["scroll"] = spec
        if spec is None:
            if log:
                log(f"clip_rom_bake: SCROLL WARNING — no Sonic 2 scroll transcription for "
                    f"{z['donor']}:{z['zone']}; it scrolls with the act default (TAGGED)")
            continue
        z["parallax_label"] = CBS.PARALLAX_LABEL.format(key=z["key"])
    if log:
        log("clip_rom_bake: scroll — " + "; ".join(
            f"{z['zone']} {len(z['scroll']['bands'])} band(s) from {z['scroll']['routine']} "
            f"(v_factor {z['scroll']['v_factor']}, v_center {z['scroll']['v_center']})"
            if z.get("scroll") else f"{z['zone']} act default" for z in plan["zones"]))


def check_scroll(plan, data_text):
    """SC1 — each zone's preset binds its OWN scroll record, read back from what was EMITTED."""
    import clip_bg_scroll as CBS
    got = dict(re.findall(r"pub data (OJZ_Clip_Preset_\d+): EffectsPreset = "
                          r"preset\(pal: \w+, (?:parallax: (\w+), )?", data_text))
    for z in plan["zones"]:
        if z["preset_label"] not in got:
            raise ClipRomError(f"SC1 the data block declares no {z['preset_label']} — UNMEASURABLE")
        bound = got[z["preset_label"]] or None
        want = z.get("parallax_label")
        if bound != want:
            raise ClipRomError(f"SC1 {z['preset_label']} ({z['donor']}:{z['zone']}) binds parallax "
                               f"{bound or 'none'}; its zone's own record is {want or 'none'}")
        if want and not re.search(rf"pub data {want} \(align: 2\): SceneCfg\d+ = lower\d+\(", data_text):
            raise ClipRomError(f"SC1 {z['preset_label']} binds {want} and the data block declares "
                               f"no such lowered record")
    scrolled = _scroll_zones(plan)
    if scrolled:
        want = CBS.data_block_text(scrolled, plan["act_span"])
        if want not in data_text:
            raise ClipRomError("SC1 the data block's scroll text is not a fresh derivation's — "
                               "something rewrote it after the bake emitted it")
    return {z["zone"]: (len(z["scroll"]["bands"]) if z.get("scroll") else None)
            for z in plan["zones"]}


def emit_clip_module(act, donor_root, path=CLIP_MODULE, data_path=CLIP_DATA, log=None,
                     gen_dir=GEN_DIR, baked_dir=None):
    """Write the clip act's module + append its data, then run Z2 and BG1 over what was
    WRITTEN."""
    plan = region_plan(act, donor_root)
    desc = os.path.join(REPO, "games", "sonic4", "data", "levels", "ojz", "act1",
                        "act_descriptor.emp")
    plan_backgrounds(plan, engine_spawn(desc), gen_dir, baked_dir or gen_dir, log=log)
    plan_scroll(plan, act, log=log)
    with open(path, "w") as fh:
        fh.write(clip_module_text(plan))
    append_clip_data(plan, data_path)
    if log:
        log(f"clip_rom_bake: {os.path.relpath(path, REPO)} + a CLIP ACT DATA block in "
            f"{os.path.relpath(data_path, REPO)} — "
            + ", ".join(f"{z['zone']} palette + preset" for z in plan["zones"])
            + f", {len(plan['rows'])} region row(s): "
            + "; ".join(f"x {r['x0']}..{r['x1']} {r['preset_label']}" for r in plan["rows"]))
    with open(path) as fh:
        mod = fh.read()
    with open(data_path) as fh:
        data = fh.read()
    ov = plan.get("overrides") or crossing_overrides(act)
    if ov["declared"] and log:
        log("clip_rom_bake: " + "!" * 72)
        log(f"clip_rom_bake: PER-CLIP OVERRIDE {CROSSING_OVERRIDES_KEY} on act {act.id!r}: "
            f"palette = {ov['palette'].upper()}, background = {ov['background'].upper()}, "
            f"zone_separation = {ov['zone_separation'].upper()}. "
            f"This act is NOT held to the default crossing rule (16-frame fade, tile "
            f"overwrite); Z2 below holds it to the re-derived one. Why: {ov['why']}")
        log("clip_rom_bake: " + "!" * 72)
    bgf = background_switch_frames(plan)
    z2 = check_palette_crossings(act, mod, data, log=log, bg_frames=bgf)
    plan["bg1"] = check_backgrounds(plan, mod, data, gen_dir)
    if log:
        log(f"clip_rom_bake: BG1 {plan['bg1']['default']} is the act default background and "
            f"{', '.join(plan['bg1']['regions']) or 'no zone'} carr(ies) its own on its "
            f"region rows — rows and blobs read back from what was emitted")
    plan["sc1"] = check_scroll(plan, data)
    if log:
        log("clip_rom_bake: SC1 " + ", ".join(
            f"{zone} {'binds its own ' + str(n) + '-band scroll' if n else 'keeps the act default'}"
            for zone, n in plan["sc1"].items()) + " — presets read back from what was emitted")
    return z2, plan


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
    z1 = check_zone_separation(act, summary)
    if z1:
        log(f"clip_rom_bake: PER-CLIP OVERRIDE crossing_overrides.zone_separation = screen — "
            f"Z1 counted on the SCREEN ({z1['need_cells']} cells), not the tile cache: gap "
            f"{z1['gap_cells']} cells; {z1['tile_cache_windows_mixed']} tile-cache window(s) "
            f"hold both zones (their margin columns are never displayed)")

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
    log("clip_rom_bake: strips, local maps, art pool, palette, collision tables...")
    ojz_strip_gen.generate()
    check_rom_pool_is_composed_pool(baked_dir, gen_dir, log=log)
    # THE CLIP ACT'S OWN REGIONS AND PALETTES (the ROW 7 block). AFTER generate(), and that
    # order is load-bearing: the data block is appended to entity_data.emp, which
    # generate()'s Pass 8 rewrites whole — written before it, the block was erased and the
    # clip module's imports named presets that no longer existed (measured, 2026-09-25).
    # `ojz_palette.bin` is left to the shipped act.
    #
    # THE BACKGROUNDS ride the same call (the BACKGROUNDS block): the start zone's own
    # Sonic 2 background is written as the act default THROUGH inject_editor_bg.main(), so
    # the full-plane 8,192-B zone_bg.bin act_assets.emp types OJZ_Act1_BG_Layout at still
    # replaces Pass 6b's 4,096-B one (skipping that was a real link failure once:
    # `[emit.size-mismatch] data OJZ_Act1_BG_Layout: declared type is 8192 byte(s),
    # initializer produced 4096`). The shipped act's editor override is no longer run: the
    # clip act does not show Oracle Jungle's background any more, so it does not carry it.
    z2, region_plan_ = emit_clip_module(act, donor_root, data_path=os.path.join(
        gen_dir, os.path.basename(CLIP_DATA)), log=log, gen_dir=gen_dir, baked_dir=baked_dir)

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
        "backgrounds": {
            "act_default": region_plan_["bg1"]["default"],
            "regions": region_plan_["bg1"]["regions"],
            "backdrop_reg": region_plan_["bg1"]["backdrop_reg"],
            "per_zone": {z["zone"]: z["bg"] for z in region_plan_["zones"]},
        },
        "scroll": {z["zone"]: ({"routine": z["scroll"]["routine"],
                                "v_factor": z["scroll"]["v_factor"],
                                "v_center": z["scroll"]["v_center"],
                                "record": z["parallax_label"],
                                "bands": [{"plane_top": b["plane_top"], "kind": b["kind"],
                                           "ratio": str(b["ratio"]),
                                           "to_ratio": str(b["to_ratio"]) if "to_ratio" in b else None,
                                           "factor": list(b["factor"])}
                                          for b in z["scroll"]["bands"]]}
                               if z.get("scroll") else "the act default (no transcription)")
                   for z in region_plan_["zones"]},
        "inherited_from_the_shipped_act": [
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
    # EVERY clip whose donor start lies in its source rectangle is corroborated (row 7): a
    # second zone is a second paste, and its shift is exactly as invisible in a screenshot
    # as the first one's. Clip 0 is also kept under the old key for its readers.
    out["donor_corroborations"] = [
        dict(donor_corroboration(act, gen_dir, coll_dir, grid_w, grid_h, sect_px,
                                 log=log, clip=c), clip=c.id)
        for c in act.clips]
    out["donor_corroboration"] = (out["donor_corroborations"][0] if act.clips else
                                  {"measured": False, "why": "the act names no clip"})
    return out


def donor_corroboration(act, gen_dir, coll_dir, grid_w, grid_h, sect_px,
                        donor_root=None, log=print, clip=None):
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

    `clip` (row 7) names which clip to corroborate; None keeps the old meaning, clip 0.
    """
    clip = act.clips[0] if clip is None else clip
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
