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
  * THE OBJECTS AND RINGS — NO LONGER (2026-09-27, the woven report's §C item 8). The
    staged project says `entities: none`, so Pass 8 (`ojz_entity_gen`) emits every
    section's tables empty at the clip act's own grid. Until then it read the shipped
    act's editor objects/rings (OJZ's entities at OJZ's world positions over Sonic 2
    geometry), which also held every clip grid to >= 9 sections in whole rows of 3.
    Objects are out of scope for the whole first cut (owner's scope).
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
     `.collattrb.bin`, and runs R1-R12 / C2-C4 including the 255-entry attr cap.
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
import ojz_entity_gen           # noqa: E402

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
    """Put the paths this bake overwrites back to their committed bytes. Returns True
    only when BOTH git commands exited 0.

    THE EXIT STATUS IS READ (PRINTED-NOT-GATED, 2026-09-25). This ran git with
    `check=False` and never looked at the return code, so a git that refused (a held
    index.lock, say) was followed by "tree RESTORED" and True; and `bake` discarded the
    return value anyway. Now a non-zero git is a False here, and `bake` raises on it."""
    for cmd in (["checkout", "--"], ["clean", "-fdq", "--"]):
        args = [git] + cmd + ([GEN_REL] if cmd[0] == "clean" else list(RESTORE_PATHS))
        try:
            p = subprocess.run(args, cwd=REPO, capture_output=True, text=True, check=False)
            why = None if p.returncode == 0 else (
                f"`{' '.join(args)}` exited {p.returncode}: {(p.stderr or '').strip()[:300]}")
        except OSError as exc:                      # noqa: BLE001 — reported, not swallowed
            why = str(exc)
        if why is not None:
            if log:
                log(f"clip_rom_bake: ERROR — could not restore the tree ({why}). "
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

def check_zone_separation(act, summary, model=None):
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
        if model is not None and (gap is None or gap < 0):
            # BOTH AXES (the woven report's §C item 15). Zones that share columns (stacked)
            # have no column gap to measure; what the override protects — no screen showing
            # two zones — is then counted on the SCREEN over every REACHABLE camera centre
            # (clip_camera: the report's woven.py check, promoted). A sealed seam may be
            # closer than a screen (the report's §A.2: 96 to 176 px), because no camera
            # reaches the centres that would see both: those are counted and REPORTED.
            mixed = int(model.mixed().sum())
            anywhere = int(model.mixed(everywhere=True).sum())
            if mixed:
                import numpy as np
                ys, xs = np.nonzero(model.mixed())
                raise ClipRomError(
                    f"Z1 (zone_separation = screen, per-clip override, both axes) {mixed} "
                    f"REACHABLE camera centre(s) of {int(model.centres.sum())} show two donor "
                    f"zones on one screen (first at centre ({int(xs[0]) * 8 + 4}, "
                    f"{int(ys[0]) * 8 + 4})): the zones are closer than a screen where a "
                    f"player can put the camera. Lengthen the connector or the neutral fill "
                    f"between them")
            return {"window": "screen", "axes": "both", "need_cells": need, "gap_cells": gap,
                    "reachable_centres": int(model.centres.sum()), "mixed_reachable": 0,
                    "mixed_unreachable": anywhere,
                    "tile_cache_windows_mixed": z["mixed"]}
        if gap is None or gap < need:
            raise ClipRomError(
                f"Z1 (zone_separation = screen, per-clip override) the narrowest gap between two "
                f"donor zones is {gap} cell(s); a screen is SCREEN_WIDTH / 8 = {need} cells, so "
                f"one camera position can show both zones")
        out = {"window": "screen", "need_cells": need, "gap_cells": gap,
               "tile_cache_windows_mixed": z["mixed"]}
        if model is not None:
            mixed = int(model.mixed().sum())
            if mixed:
                raise ClipRomError(
                    f"Z1 (zone_separation = screen) {mixed} reachable camera centre(s) show two "
                    f"donor zones on one screen although the column gap is {gap} cells")
            out.update(axes="both", reachable_centres=int(model.centres.sum()),
                       mixed_reachable=0, mixed_unreachable=int(model.mixed(True).sum()))
        return out
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
# (it is unused data in a clip ROM). The BACKGROUND stopped being inherited on 2026-09-25
# (see the BACKGROUNDS block) and the OBJECTS AND RINGS on 2026-09-27 (stage_project's
# `entities: none`).

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
CLIP_DATA_USES = ("use engine.structs.{Region, LayerLine}\n"
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
        f"rg_effects: {r['preset_label']}, rg_parallax: {r.get('parallax') or 0}, "
        f"rg_bg_layout: {r.get('bg_layout') or 0}, rg_bg_span: {r.get('bg_span') or 0}, "
        f"rg_bg_tiles: {r.get('bg_tiles') or 0}, "
        # rg_song: the id of the clip's per-zone `music` on a zone's OUTER row, 0 ("no song
        # named, leave the music alone") on the corridor's inner rows and on every row of a
        # zone that names no music (the MUSIC block). rg_pad_1b is the even-stride pad.
        f"rg_song: {r.get('song_id') or 0}, rg_pad_1b: 0 }},  // {r['why']}"
        for r in plan["rows"])


# ---------------------------------------------------------------------------
# THE CLIP ACT'S LAYER LINES (S2CLIP-PLANE-SWITCH, 2026-09-26)
# ---------------------------------------------------------------------------
#
# Sonic 2 moves the player between its two collision paths with Obj03 lines; a clip act
# carries no Sonic 2 objects, so without these the player never left plane A and no loop
# could be completed (docs/research/2026-09-26-s2clip-loops-planes.md). tools/s2_layer_lines.py
# reads every Obj03 inside each clip's source rectangle out of the donor's own object layout;
# this block emits them the way the regions are emitted: the ROWS as a const in the clip
# module (act_descriptor.emp's layer_line_table_check walks them), the same text as the
# `OJZ_Clip_LayerLines` table in the data block, and a chooser the descriptor binds
# `act_layer_lines` through. LL1 below reads both back and holds them to the plan. An act with
# no lines emits no table and the chooser hands back `hand` (0).

_LAYER_LINES_NEUTRAL = (
    "// THE LAYER LINES (S2CLIP-PLANE-SWITCH, LINES-EVERYWHERE). None of the clip's in the\n"
    "// canonical act: the descriptor binds Act.act_layer_lines through this chooser and gets its\n"
    "// `hand`, the act's own authored table (OJZ_Act1_LayerLines), and the clip rows the\n"
    "// descriptor checks are empty.\n"
    "pub const OJZ_CLIP_LAYER_LINE_ROWS: array = []\n\n"
    "pub comptime fn ojz_clip_act_layer_lines(hand: Label) -> Label {\n"
    "    return hand\n"
    "}\n")


def _layer_lines_module_text(plan):
    ll = plan.get("layer_lines") or {}
    if not ll.get("rows"):
        # NOT the neutral chooser: that hands back `hand`, the canonical act's own table, whose
        # lines are OJZ's geometry and mean nothing in a clip act.
        return ("// THE LAYER LINES (S2CLIP-PLANE-SWITCH): none in this clip act's donor "
                "rectangles, so the\n// act binds no table (not the canonical act's, which is "
                "OJZ's geometry) and Player_Main's\n// null test is all it pays.\n"
                "pub const OJZ_CLIP_LAYER_LINE_ROWS: array = []\n\n"
                "pub comptime fn ojz_clip_act_layer_lines(hand: Label) -> int {\n"
                "    return 0\n"
                "}\n")
    import layer_lines as LLS
    n = len(ll["rows"]) + 2
    return (f"// THE LAYER LINES (S2CLIP-PLANE-SWITCH): {len(ll['lines'])} Sonic 2 Obj03 line(s) "
            f"from the donors'\n// own object layouts, {len(ll['rows'])} row(s) with the horizontal "
            f"ones cut into segments, between\n// two sentinels. tools/s2_layer_lines.py wrote "
            f"them; the SAME text is the data block's\n// `OJZ_Clip_LayerLines`, and LL1 holds the "
            f"two identical.\n"
            f"pub const OJZ_CLIP_LAYER_LINE_ROWS: [LayerLine; {n}] = [\n    "
            f"{LLS.rows_text(ll)}\n]\n\n"
            "pub comptime fn ojz_clip_act_layer_lines(hand: Label) -> Label {\n"
            "    return OJZ_Clip_LayerLines\n"
            "}\n")


# ---------------------------------------------------------------------------
# THE CLIP ACT'S OWN START (woven mega-act item 7, first cut for s2_mtz_cpz, 2026-09-27)
# ---------------------------------------------------------------------------
#
# The shipped descriptor starts the player at world (256, 256): section 0, local $0100 on both
# axes. Emerald Hill happens to have ground under that; Metropolis, pasted 448 px down so its
# floors meet Chemical Plant's, does not (the point is above the clip, and the first plane-A
# surface under it, MEASURED, is inside the maze's roof at y 832). So a clip may name the clip
# whose DONOR start it begins at (`"start": {"clip": <id>}`): Sonic 2's own startpos for that
# zone (`startpos/<ZONE>_1.bin`, the player's centre), moved into act coordinates. The
# descriptor binds its four start fields through the choosers below, the regions pattern:
# the neutral module hands back `hand` (the shipped literals), so the canonical ROMs are
# unchanged, and a clip without a `start` hands back `hand` too (s2_ehz_cpz keeps (256, 256)).

START_FIELDS = ("start_sec_x", "start_local_x", "start_sec_y", "start_local_y")

_START_NEUTRAL = (
    "// THE START (woven item 7). None of the clip's in the canonical act: the descriptor binds\n"
    "// its four start fields through these choosers and gets its `hand`, the shipped literals.\n"
    + "\n".join(f"pub comptime fn ojz_clip_act_{f}(hand: int) -> int {{\n    return hand\n}}\n"
                for f in START_FIELDS))


def act_start(act):
    """The clip act's own start, or None (the descriptor's shipped start stands).

    Two forms. `"start": {"clip": <clip id>}` names the clip whose DONOR start the player
    begins at: Sonic 2's `startpos/<ZONE>_1.bin` (x then y, big-endian words: the player's
    centre), which must lie inside that clip's source rectangle, moved by the clip's paste
    offset. `"start": {"x": X, "y": Y, "why": "..."}` is a world point (the player's centre)
    chosen by the act, for when the donor's start cannot reach what the act exists to show
    (s2_mtz_cpz: Sonic 2 crosses the pit between Metropolis's start and the first tunnel on
    objects the clip does not carry). It must lie inside a clip or corridor rectangle and
    say why. Returns {"x", "y", "clip", "donor_start"} in world px (clip/donor_start None
    for the second form)."""
    raw = getattr(act, "raw", None) or {}
    raw = raw.get("start")
    if raw is None:
        return None
    if isinstance(raw, dict) and set(raw) == {"x", "y", "why"}:
        x, y, why = raw["x"], raw["y"], raw["why"]
        if not (isinstance(x, int) and isinstance(y, int) and not isinstance(x, bool)
                and not isinstance(y, bool)):
            raise ClipRomError(f"ST0 `start` x and y must be integers, not {x!r}, {y!r}")
        if not (isinstance(why, str) and why.strip()):
            raise ClipRomError("ST0 `start` names a point without a `why`")
        rects = [c.dst for c in act.clips] + [co.dst for co in act.corridors]
        if not any(rx <= x < rx + rw and ry <= y < ry + rh for rx, ry, rw, rh in rects):
            raise ClipRomError(f"ST0 `start` ({x}, {y}) lies in no clip or corridor rectangle")
        return {"x": x, "y": y, "clip": None, "donor_start": None, "why": why}
    if not isinstance(raw, dict) or set(raw) != {"clip"}:
        raise ClipRomError(f"ST0 `start` must be {{\"clip\": <clip id>}} or "
                           f"{{\"x\": X, \"y\": Y, \"why\": ...}}, not {raw!r}")
    clip = next((c for c in act.clips if c.id == raw["clip"]), None)
    if clip is None:
        raise ClipRomError(f"ST0 `start` names clip {raw['clip']!r}, which the act does not have")
    import s2_donor
    import struct as _s
    p = os.path.join(s2_donor.donor_root(clip.donor), "startpos", f"{clip.zone}_1.bin")
    if not os.path.isfile(p):
        raise ClipRomError(f"ST0 `start` names clip {clip.id!r}, but its donor has no start "
                           f"position at {p}")
    sx, sy = _s.unpack(">HH", open(p, "rb").read()[:4])
    x0, y0, w, h = clip.src
    if not (x0 <= sx < x0 + w and y0 <= sy < y0 + h):
        raise ClipRomError(f"ST0 {clip.donor}:{clip.zone} starts the player at ({sx}, {sy}), "
                           f"outside clip {clip.id!r}'s source rectangle ({x0}, {y0}, {w}, {h})")
    return {"x": sx - x0 + clip.dst[0], "y": sy - y0 + clip.dst[1], "clip": clip.id,
            "donor_start": [sx, sy]}


def start_fields(start, constants_path=None):
    """{descriptor field: value} for a world-px start: the section and the local offset."""
    from fg_working_set import ConstantSource
    src = ConstantSource()
    src.load_file(constants_path or os.path.join(REPO, "engine", "system", "constants.emp"))
    shift = int(src.get("SECTION_SIZE_SHIFT"))
    mask = (1 << shift) - 1
    return {"start_sec_x": start["x"] >> shift, "start_local_x": start["x"] & mask,
            "start_sec_y": start["y"] >> shift, "start_local_y": start["y"] & mask}


def _start_module_text(plan):
    st = plan.get("start")
    if st is None:
        return ("// THE START (woven item 7): this clip act names none, so the descriptor's shipped\n"
                "// start stands.\n"
                + "\n".join(f"pub comptime fn ojz_clip_act_{f}(hand: int) -> int {{\n"
                            f"    return hand\n}}\n" for f in START_FIELDS))
    fields = start_fields(st)
    said = (f"clip {st['clip']!r}'s donor start ({st['donor_start'][0]}, {st['donor_start'][1]})"
            if st.get("clip") else "the act's own point (its manifest says why)")
    return (f"// THE START (woven item 7): {said}, at world ({st['x']}, {st['y']}).\n"
            + "\n".join(f"pub comptime fn ojz_clip_act_{f}(hand: int) -> int {{\n"
                        f"    return {fields[f]}\n}}\n" for f in START_FIELDS))


def check_start(plan, mod_text):
    """ST1 — the four choosers the descriptor binds return this plan's start, read back from
    what was EMITTED (or `hand` when the act names none)."""
    import re as _re
    st = plan.get("start")
    want = start_fields(st) if st else None
    for f in START_FIELDS:
        m = _re.search(rf"pub comptime fn ojz_clip_act_{f}\(hand: int\) -> int \{{\s*return (\w+)\s*\}}",
                       mod_text)
        if not m:
            raise ClipRomError(f"ST1 the clip module declares no ojz_clip_act_{f} chooser")
        got = m.group(1)
        exp = "hand" if want is None else str(want[f])
        if got != exp:
            raise ClipRomError(f"ST1 ojz_clip_act_{f} returns {got}, the plan says {exp}")
    return want


def _layer_lines_data_text(ll):
    import layer_lines as LLS
    n = len(ll["rows"]) + 2
    return (f"// THE LAYER LINES (S2CLIP-PLANE-SWITCH): Act.act_layer_lines names this table; "
            f"Player_LayerLines\n// (games/sonic4/player/player_common.emp) runs it. "
            f"(align: 2): every field is read as a word.\n"
            f"pub data OJZ_Clip_LayerLines (align: 2): [LayerLine; {n}] = [\n    "
            f"{LLS.rows_text(ll)}\n]\n")


def layer_line_plan(act, log=None):
    """tools/s2_layer_lines.plan() for the act, its refusals as ClipRomError."""
    import s2_layer_lines as SLL
    try:
        ll = SLL.plan(act)
    except SLL.LayerLineError as exc:
        raise ClipRomError(str(exc)) from None
    if log:
        zones = {}
        for ln in ll["lines"]:
            zones[ln["zone"]] = zones.get(ln["zone"], 0) + 1
        log(f"clip_rom_bake: LL {len(ll['lines'])} Sonic 2 plane-switcher line(s) -> "
            f"{len(ll['rows'])} layer-line row(s) ("
            + ", ".join(f"{z} {n}" for z, n in zones.items()) + ")")
    return ll


_LL_ROW_RE = None


def _layer_line_rows(text, name, what):
    """[(key, a, b, flags)] of a `NAME ... = [ LayerLine{...}, ... ]` block, sentinels included."""
    import re
    m = re.search(rf"{re.escape(name)}\b[^=]*=\s*\[(.*?)^\]", text, re.S | re.M)
    if not m:
        raise ClipRomError(f"LL1 {what} carries no `{name}` table")
    out = []
    for r in re.finditer(r"LayerLine\{\s*ll_key:\s*(\$?[0-9A-Fa-f]+),\s*ll_a:\s*(\d+),\s*"
                         r"ll_b:\s*(\d+),\s*ll_flags:\s*(\$?[0-9A-Fa-f]+)", m.group(1)):
        out.append(tuple(int(v[1:], 16) if v.startswith("$") else int(v) for v in r.groups()))
    return out


def check_layer_lines(plan, mod_text, data_text):
    """LL1: the rows the descriptor checks (the clip module's OJZ_CLIP_LAYER_LINE_ROWS) and the
    table the Act names (the data block's OJZ_Clip_LayerLines) are the plan's rows, read back
    out of what was WRITTEN, in order, sentinels included. Returns the row count (0 = none)."""
    ll = plan.get("layer_lines") or {}
    if not ll.get("rows"):
        if "OJZ_Clip_LayerLines" in data_text:
            raise ClipRomError("LL1 the plan has no layer lines but the data block names a table")
        return 0
    c = ll["consts"]
    want = ([(c["LL_KEY_BEFORE"], 0, 0, 0)]
            + [(r["key"], r["a"], r["b"], r["flags"]) for r in ll["rows"]]
            + [(c["LL_KEY_AFTER"], 0, 0, 0)])
    for text, name, what in ((mod_text, "OJZ_CLIP_LAYER_LINE_ROWS", "the clip module"),
                             (data_text, "OJZ_Clip_LayerLines", "the data block")):
        got = _layer_line_rows(text, name, what)
        if got != want:
            first = next((i for i, (g, w) in enumerate(zip(got, want)) if g != w),
                         min(len(got), len(want)))
            raise ClipRomError(
                f"LL1 {what}'s {name} is not the plan's table: {len(got)} row(s) against "
                f"{len(want)}, first difference at row {first}")
    return len(ll["rows"])


def _region_bg_labels(plan):
    """Every per-zone background label the rows name, in zone order (none for the act
    default's zone)."""
    return [lab for z in plan["zones"] for lab in (z.get("bg_layout_label"),
                                                  z.get("bg_tiles_label")) if lab]


def _scroll_transition(plan):
    """scene()'s transition for the clip's scroll records: TRANS_INSTANT (1) under the per-clip
    override crossing_overrides.parallax = snap, else the default TRANS_SMOOTH (0). B-2 bound a
    parallax record to each zone's preset, so a crossing now also LERPS the background scroll
    for PARALLAX_TRANS_DEFAULT frames, which a short tunnel cannot hide past its mouth. Inside
    the tunnel the background is covered, so an instant switch there cannot be seen."""
    return 1 if (plan.get("overrides") or {}).get("parallax") == "snap" else 0


def _scroll_zones(plan):
    """[(label key, scroll spec)] for every zone the SCROLL block derived one for, in key order.
    A TALL zone's chain contributes every layout: config 0 under the zone's key (its preset
    binds it), config i under "<key>_W<i>" (tall_parallax_label; the split rows name them)."""
    out = []
    for z in plan["zones"]:
        if z.get("scroll_chain"):
            out += [(z["key"] if i == 0 else f"{z['key']}_W{i}", sp)
                    for i, sp in enumerate(z["scroll_chain"]["specs"])]
        elif z.get("scroll"):
            out.append((z["key"], z["scroll"]))
    return out


def _row_parallax_labels(plan):
    """The parallax records the region ROWS name (a tall zone's split rows), in first use."""
    seen = []
    for r in plan["rows"]:
        if r.get("parallax") and r["parallax"] not in seen:
            seen.append(r["parallax"])
    return seen


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
                "}\n\n"
                + _LAYER_LINES_NEUTRAL + "\n" + _START_NEUTRAL)
    presets = ", ".join([z["preset_label"] for z in plan["zones"]] + _region_bg_labels(plan)
                        + _row_parallax_labels(plan))
    uses_ll = ", LayerLine" if (plan.get("layer_lines") or {}).get("rows") else ""
    n = len(plan["rows"])
    backdrop = plan.get("backdrop_reg", 0)
    return (_CLIP_HEADER +
            f"// CLIP ACT {plan['act']} — {len(plan['zones'])} donor zone(s), {n} region row(s).\n"
            "// Written by a THROWAWAY S2CLIP bake; build.sh's EXIT trap restores the neutral\n"
            "// module. Never commit this version. The palettes, presets and the emitted table\n"
            f"// are appended to {CLIP_DATA_REL} (between its CLIP ACT DATA markers).\n\n"
            f"module {CLIP_MODULE_NAME}\n\n"
            f"use engine.structs.{{Region{uses_ll}}}\n"
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
            "}\n\n"
            + _layer_lines_module_text(plan) + "\n" + _start_module_text(plan))


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
        out.append(CBS.data_block_text(scrolled, plan["act_span"], _scroll_transition(plan)))
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
    ll = plan.get("layer_lines") or {}
    if ll.get("rows"):
        out.append(_layer_lines_data_text(ll))
    for z in plan["zones"]:
        if not z.get("bg_layout_label"):
            continue
        bg = z["bg"]
        # TYPED, both of them, like act_assets.emp's act default: the length is the guard.
        # (align: 2) on the tile blob because it is a DMA SOURCE — BG_Stream_Update's
        # overwrite queues it word-wise and raise_errors on an odd address in DEBUG.
        tiles_line = (f"pub data {z['bg_tiles_label']} (align: 2): [u8; {z['bg_tiles_bytes']}] = "
                      f"embed(\"{z['bg_tiles_embed']}\")\n"
                      if z.get("bg_tiles_label") and z.get("bg_tiles_owner", True) else
                      f"// NO tile blob of its own: its tiles are in {z['bg_tiles_label']}, its "
                      f"background blob group's\n// (crossing_overrides.bg_blobs), so a crossing "
                      f"inside the group overwrites nothing.\n" if z.get("bg_tiles_label") else
                      "// NO tile blob: PER-CLIP OVERRIDE crossing_overrides.background = "
                      + ("blobs, and this zone's group holds the start zone. Its"
                         if (plan.get("overrides") or {}).get("background") == "blobs" else
                         "co_resident. This zone's")
                      + "\n// tiles are inside the act default's blob "
                      "(rg_bg_tiles 0), so the crossing overwrites nothing.\n")
        out.append(
            f"// zone key {z['key']}: {z['donor']} {z['zone']}'s own Sonic 2 background "
            f"(tools/clip_bg_lower.py): {bg['tiles']} tiles,\n// crop start chunk "
            f"{bg['crop_start_chunk']} of a {bg['period_cells']}-cell period, invented-seam "
            f"cost {bg['seam_cost_pixels']} px. Named by this zone's region rows.\n"
            + (f"// TALL: {z['bg_span']} lines of map (rg_bg_span), BG rows "
               f"{z['tall']['r0']}..{z['tall']['r0'] + z['bg_span'] - 1}, streamed by "
               f"BG_Stream_Update (WINDOWED-BG-VERTICAL-CLAMP).\n" if z.get("bg_span") else "")
            + f"pub data {z['bg_layout_label']} (align: 2): "
            + (f"[u8; {z['bg_layout_bytes']}]" if z.get("bg_span") else "[u8; BG_LAYOUT_SIZE]")
            + f" = embed(\"{z['bg_layout_embed']}\")\n"
            + (tiles_line if z.get("bg_role") != "act_default" else
               "// its tiles are the act default's blob (rg_bg_tiles 0): it IS the start zone.\n"))
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
                            "background": ("overwrite", "co_resident", "blobs"),
                            "zone_separation": ("tile_cache", "screen"),
                            "crossing_margin": ("enforce", "report"),
                            "parallax": ("lerp", "snap")}


def crossing_overrides(act):
    """The act's `crossing_overrides`, validated: {"palette", "background", "why",
    "declared"}. `declared` is False for an act without the key (the defaults)."""
    raw = (getattr(act, "raw", None) or {}).get(CROSSING_OVERRIDES_KEY)
    out = {"palette": "fade", "background": "overwrite", "zone_separation": "tile_cache",
           "crossing_margin": "enforce", "parallax": "lerp", "why": None, "declared": False}
    if raw is None:
        return out
    if not isinstance(raw, dict):
        raise ClipRomError(f"{CROSSING_OVERRIDES_KEY} must be an object")
    unknown = sorted(set(raw) - set(CROSSING_OVERRIDE_VALUES) - {"why", "bg_blobs"})
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
    # BACKGROUND BLOB GROUPS (the woven report's §C item 14): `background = blobs` names the
    # groups in `bg_blobs`; either without the other is refused (blob_groups resolves them)
    if (out["background"] == "blobs") != ("bg_blobs" in raw):
        raise ClipRomError(f"{CROSSING_OVERRIDES_KEY}.background = blobs and "
                           f"{CROSSING_OVERRIDES_KEY}.bg_blobs go together: the groups are "
                           f"named in bg_blobs, and bg_blobs means nothing under another "
                           f"background rule")
    if "bg_blobs" in raw:
        out["bg_blobs"] = raw["bg_blobs"]
    return out


def background_constants():
    """(overwrite chunk bytes, wipe rows per frame, rows the screen can show) — READ from the
    engine (engine/level/bg.emp and the files its expressions reach), never typed.

    The wipe rate is BG_WIPE_DMA_ROWS: since 2026-09-25 a one-plane map, and since
    WOVEN-TALL-ENTRY (2026-09-27) a TALL one too (HPZ, WFZ), is swept by DMA from ROM
    (BG_Stream_Update's `.wipe_spend`) at that many rows a frame; the CPU sweep's
    BG_WIPE_ROWS_PER_FRAME is deleted. Entering a tall zone also snaps its BG scroll on the
    crossing frame (Parallax_BG_Snap), so it adds no term here."""
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
    plane BG_WIPE_DMA_ROWS rows a frame by DMA starting at the top VISIBLE row, so the rows
    the screen can show are repainted after ceil(BG_SCREEN_ROWS / BG_WIPE_DMA_ROWS) frames
    (the CPU sweep, BG_WIPE_ROWS_PER_FRAME = 4, is what the measurement below was taken on;
    it is deleted). A zone whose effective blob is the one the arena already holds (co-resident)
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


# ---------------------------------------------------------------------------
# THE 2-D REGION PLAN (the woven report's §C item 1, 2026-09-27)
# ---------------------------------------------------------------------------
#
# WHAT CHANGED, and what did not. Until the woven act the plan was a left-to-right chain of
# full-height strips, one crossing per corridor at its middle; a stacked layout was REFUSED
# ("a stacked layout needs a horizontal crossing this bake does not write"). The engine never
# needed that: a Region is a RECTANGLE (engine/structs.emp), Parallax_CheckBoundary installs
# the row holding the camera CENTRE on both axes, and the descriptor's checks (rows tile the
# act, REGION_MIN_SPAN on each axis, interior edges inside the centre's reachable band on each
# axis) are 2-D already. So the plan now writes rectangles, and a 1-D act's plan is the
# special case whose rectangles all happen to be full height — MEASURED identical, row for
# row, on every committed clip act (tools/test_clip_woven_2d.py).
#
# HOW, in three steps:
#   1. LABELS. Every 8-px camera-centre cell that must be in one zone's region says so:
#        * a clip's own rectangle -> its zone, playing its song ("live");
#        * a connector (corridor or shaft) joining two zones -> the zone on its side of the
#          CROSSING, naming no song ("dead": the cut-at-exit dead band, S2CLIP-MUSIC-FEEL);
#        * a REACHABLE centre (clip_camera) whose screen shows exactly one zone -> that zone,
#          song unconstrained.
#      Everything else — the fill, void nobody reaches — is unconstrained.
#   2. THE CROSSING. Along a connector's axis it sits where the two sides' SLACK balances
#      (the report's balanced-slack rule, woven.py's): each side needs the screen's half
#      extent on that axis plus CAM_MAX_{X,Y}_STEP x the frames the crossing INTO that side
#      takes (crossing_frames: the palette's, or the background's when it is longer), and
#      the crossing is the midpoint of what is left, rounded down to the 16-px collision
#      grid. With equal needs on both sides it is the old rule exactly, the connector's
#      middle rounded down to 16.
#   3. RECTANGLES. A guillotine split of the whole act: cut the act (then each piece) along
#      one full-length line until every piece holds one zone and at most one song state.
#      Among the cuts that leave labels on both sides, it takes the one leaving the fewest
#      zones, then a connector's own crossing, then one of its mouths, then the fewest song
#      states, lowest coordinate first. Every cut is on the 8-px cell grid, inside the camera
#      centre's reachable band and at least REGION_MIN_SPAN from the piece's edges, so each
#      row passes the descriptor's rules by construction. A piece no legal cut can make pure
#      is REFUSED by name (a connector too short for its rows is the usual cause).
# The plan is then only as good as the checks that read it back out of the EMITTED rows:
# Z2 and MUSIC walk every connector on its own axis, and the SCREEN check (check_screen)
# holds every reachable centre to what its screen shows.

#: a region edge the plan cuts at a CROSSING is on the collision grid, as it always was
CROSSING_GRID_PX = 16


def blob_groups(act):
    """[frozenset of zone keys] — the BACKGROUND BLOBS: zones in one blob have their
    background tiles resident together in the BG arena, so a crossing between them pays no
    tile overwrite. `crossing_overrides.background = co_resident` puts every zone in one
    blob; `background = blobs` names the groups (`bg_blobs`, the woven report's §C item 14:
    its blobs A, M, O); without either every zone is its own blob.

    `bg_blobs` is a list of groups, each a list of zone names — "CPZ", or "s2disasm/CPZ"
    where the act holds one zone name from two donors. BG0 refuses a name the act does not
    have, an ambiguous one, a zone in two groups or in none, and an empty group."""
    ov = crossing_overrides(act)
    keys = sorted({c.zone_key for c in act.clips})
    if ov["background"] == "co_resident":
        return [frozenset(keys)]
    if ov["background"] != "blobs":
        return [frozenset([k]) for k in keys]
    raw = ov["bg_blobs"]
    if not isinstance(raw, list) or not raw or not all(
            isinstance(g, list) and g and all(isinstance(n, str) for n in g) for g in raw):
        raise ClipRomError("BG0 crossing_overrides.bg_blobs must be a non-empty list of "
                           "non-empty lists of zone names")
    tree = {c.zone_key: c.tree_key for c in act.clips}
    groups, seen = [], {}
    for gi, g in enumerate(raw):
        keys_g = set()
        for name in g:
            hits = [k for k, (d, z) in tree.items() if name in (z, f"{d}/{z}")]
            if len(hits) != 1:
                raise ClipRomError(
                    f"BG0 crossing_overrides.bg_blobs[{gi}] names {name!r}, which is "
                    + ("no zone of this act" if not hits else
                       f"{len(hits)} zones of this act (write donor/ZONE)")
                    + f"; the act's zones are {sorted('/'.join(t) for t in tree.values())}")
            k = hits[0]
            if k in seen:
                raise ClipRomError(f"BG0 crossing_overrides.bg_blobs puts {name!r} in groups "
                                   f"{seen[k]} and {gi}: a zone's tiles are in ONE blob")
            seen[k] = gi
            keys_g.add(k)
        groups.append(frozenset(keys_g))
    missing = sorted('/'.join(tree[k]) for k in keys if k not in seen)
    if missing:
        raise ClipRomError(f"BG0 crossing_overrides.bg_blobs leaves {missing} in no group; "
                           f"name every zone of the act once")
    return groups


_LOWERED = {}


def lower_zone(donor, zone, tall=None):
    """clip_bg_lower.lower() for one zone: its one-plane window, or its TALL map when
    `tall` (tall_plans' entry) says the window cannot hold the screen tops its clips reach."""
    import clip_bg_lower as CBL
    if not tall:
        return CBL.lower(donor, zone)
    return CBL.lower(donor, zone, r0=tall["r0"], rows=tall["rows"], x_reach=tall["x_reach"])


def _lowered_tiles(donor, zone, tall=None):
    """The tile list lower_zone() gives one zone (memoised: it is pure)."""
    key = (donor, zone) + ((tall["r0"], tall["rows"], tall["x_reach"]) if tall else ())
    if key not in _LOWERED:
        _LOWERED[key] = lower_zone(donor, zone, tall)[1]
    return _LOWERED[key]


# ---------------------------------------------------------------------------
# TALL BACKGROUNDS (WINDOWED-BG-VERTICAL-CLAMP, 2026-09-27)
# ---------------------------------------------------------------------------
#
# A zone whose clips reach screen tops its one 512-line window cannot hold (Hidden Palace,
# Wing Fortress) is lowered as a TALL map instead: every BG row its clips reach, one blob named
# by its region rows (rg_bg_layout) with its height (rg_bg_span), streamed by the engine's own
# BG_Stream_Update. Its scroll is a CHAIN of band layouts (clip_bg_scroll.derive_tall), one per
# stretch of height, and the zone's rows are SPLIT at the chain's switch heights so each row
# names its layout (rg_parallax). A zone the window holds is untouched, byte for byte.
# docs/research/2026-09-27-windowed-bg-vertical-clamp.md has the finding and the options.

#: How far past a clip's rightmost camera the period test looks, in BG px: the width of the
#: plane, which is what Sonic 2's own 64-cell ring can hold ahead of a camera whose BG X moves
#: no faster than it (1:1 at most, for every zone this path takes).
TALL_X_MARGIN = 512

#: WHETHER A ZONE THAT OTHER ZONES CROSS INTO MAY GO TALL. True since WOVEN-TALL-ENTRY
#: (2026-09-27). It was False, MEASURED: on s2_woven with HPZ and WFZ tall (DEBUG crc cfc3e006)
#: crossing_witness counted 29 glitch ticks on hpz_to_ooz (leftward, INTO Hidden Palace, slack
#: -6 frames) and 9 on hpz_to_mtz (the drop into Hidden Palace, slack -9); the other 9
#: connectors stayed at 0. Entering a TALL region cost what entering a one-plane region did
#: not: Step 5's rate clamp slid the scroll 16 px a frame from the zone left, and the tall-map
#: wipe was the CPU sweep. The engine now snaps the scroll on a crossing that changes the
#: layout (Parallax_BG_Snap) and DMA-sweeps every map with the window held, and the same
#: witness reads 0 glitch ticks on all 11 connectors (worst slack +2, hpz_to_mtz). False
#: keeps a multi-zone act's zones windowed, the pre-fix bake, for an A/B.
TALL_JOINED_ZONES = True


def tall_plans(act, joined=None):
    """{zone key: tall extent} for every zone that needs a tall map (clip_bg_scroll.tall_extent
    plus the paste dy, the rightmost donor camera X its clips reach and the period test's
    x_reach). Derived from the manifest alone, so the region plan (crossing frames, from the
    lowered tiles) and the backgrounds agree on it. A zone pasted at two dys is left to SC0."""
    import clip_bg_scroll as CBS
    import s2_donor as sd
    by = {}
    for c in act.clips:
        by.setdefault(c.zone_key, []).append(c)
    out = {}
    if len(by) > 1 and not (TALL_JOINED_ZONES if joined is None else joined):
        return out                      # every zone is crossed into: see TALL_JOINED_ZONES
    for key, cl in sorted(by.items()):
        dys = {c.dst[1] - c.src[1] for c in cl}
        if len(dys) != 1:
            continue
        dy = dys.pop()
        c = cl[0]
        lo = min(x.dst[1] for x in cl)
        hi = max(max(x.dst[1], x.dst[1] + x.dst[3] - CBS.SCREEN_LINES) for x in cl)
        ext = CBS.tall_extent(c.donor, c.zone, dy, lo, hi,
                              sd.load_bg_grid(c.zone, c.donor).shape[0] * CBS.CHUNK_LINES)
        if ext is None:
            continue
        cam_x = max(x.src[0] + x.src[2] for x in cl) - 320
        ext.update(paste_dy=dy, donor_cam_x_max=cam_x, x_reach=cam_x + 320 + TALL_X_MARGIN)
        out[key] = ext
    return out


def tall_chains(act, joined=None):
    """{zone key: clip_bg_scroll.derive_tall(...)} for every tall zone of `act`: what the bake
    binds and what a witness holds the ROM to. Pure (it re-lowers each tall map)."""
    import clip_bg_scroll as CBS
    tree = {c.zone_key: c.tree_key for c in act.clips}
    out = {}
    for key, ext in tall_plans(act, joined).items():
        donor, zone = tree[key]
        words = lower_zone(donor, zone, ext)[0]
        out[key] = CBS.derive_tall(donor, zone, ext["paste_dy"], ext, words,
                                   ext["donor_cam_x_max"])
    return out


def tall_parallax_label(key, i):
    """The parallax record of config i of zone `key`'s chain: config 0 is the zone's own
    PARALLAX_LABEL (the one its preset binds), later ones carry a _W<i> suffix."""
    import clip_bg_scroll as CBS
    return CBS.PARALLAX_LABEL.format(key=key if i == 0 else f"{key}_W{i}")


def crossing_frames(act, consts=None, bg_consts=None, tiles_of=None):
    """{"palette": frames, "wipe": frames, "pair": {(from key, into key): frames}} — how many
    frames a crossing INTO a zone takes to settle, per pair: the larger of the palette's
    (SNAP_FRAMES with the snap override, else PAL_FADE_FRAMES) and the background's (the
    visible-row wipe when both zones share a blob; the blob's overwrite chunks plus the wipe
    when they do not — background_switch_frames' model, per pair instead of per zone).

    A blob's bytes are its zones' lowered tiles, deduplicated across the blob (the union
    co_resident_backgrounds builds) x 32. `tiles_of(donor, zone)` is injectable for tests."""
    fade, _step, _half = consts or crossing_constants()
    ov = crossing_overrides(act)
    pal = SNAP_FRAMES if ov["palette"] == "snap" else fade
    chunk, rows_per_frame, screen_rows = bg_consts or background_constants()
    wipe = -(-screen_rows // rows_per_frame)
    tree = {c.zone_key: c.tree_key for c in act.clips}
    if tiles_of is None:
        tall = {tree[k]: t for k, t in tall_plans(act).items()}
        tiles_of = (lambda donor, zone: _lowered_tiles(donor, zone, tall.get((donor, zone))))
    groups = blob_groups(act)
    group_of = {k: g for g in groups for k in g}
    nbytes = {}
    for g in groups:
        union = set()
        for k in g:
            union.update(tiles_of(*tree[k]))
        nbytes[g] = len(union) * 32
    pair = {}
    for r in tree:
        for z in tree:
            if r == z:
                continue
            bg = wipe if group_of[r] == group_of[z] else -(-nbytes[group_of[z]] // chunk) + wipe
            pair[(r, z)] = max(pal, bg)
    return {"palette": pal, "wipe": wipe, "pair": pair,
            "blob_bytes": {tuple(sorted(g)): n for g, n in nbytes.items()}}


def connector_crossings(act, frames, cam=None):
    """Every connector JOINING TWO ZONES, with its balanced crossing — see step 2 above.
    [{"connector", "id", "axis", "before", "after" (clips), "a" (the before-clip's end = the
    connector's near edge), "b" (its far edge = the after-clip's start), "c" (the crossing:
    the first centre coordinate in the after-zone's region), "need_before", "need_after"}].
    A connector joining one zone to itself, or touching a clip on one side only, is not a
    crossing and is left out (its cells are labelled by the zone it touches)."""
    c = cam or _cam_constants()
    out = []
    for k in list(getattr(act, "corridors", [])) + list(getattr(act, "shafts", [])):
        ax, before, after = clip_manifest.connector_ends(act, k)
        if before is None or after is None or before.zone_key == after.zone_key:
            continue
        i = 0 if ax == "x" else 1
        half = c["CAM_SCREEN_HALF_W"] if ax == "x" else c["CAM_SCREEN_HALF_H"]
        step = c["CAM_MAX_X_STEP"] if ax == "x" else c["CAM_MAX_Y_STEP"]
        a, b = k.dst[i], k.dst[i] + k.dst[i + 2]
        need_b = half + step * frames["pair"][(after.zone_key, before.zone_key)]
        need_a = half + step * frames["pair"][(before.zone_key, after.zone_key)]
        at = ((a + b + need_b - need_a) // 2) & ~(CROSSING_GRID_PX - 1)
        out.append({"connector": k, "id": k.id, "axis": ax, "before": before, "after": after,
                    "a": a, "b": b, "c": at, "need_before": need_b, "need_after": need_a})
    return out


def _cam_constants():
    import clip_camera
    return clip_camera.constants()


def _region_bounds():
    """(REGION_MIN_SPAN, centre band per axis as (min, max)) — the descriptor's own row
    rules, READ from the constants its expressions reach (act_descriptor.emp: CENTRE_X_MIN =
    CAM_SCREEN_HALF_W, CENTRE_X_MAX = ACT_W - SCREEN_WIDTH + CAM_SCREEN_HALF_W, the same in y,
    REGION_MIN_SPAN = 2 x CAM_MAX_Y_STEP)."""
    c = _cam_constants()
    return 2 * c["CAM_MAX_Y_STEP"], c["CAM_SCREEN_HALF_W"], c["CAM_SCREEN_HALF_H"]


def check_zone_faces(act):
    """Z2 — two clips of DIFFERENT zones that face each other along an axis (overlapping
    across it, no clip between) are joined by a connector, or everything between them is
    painted (fill or connector). A void between two zones shows the background while nobody
    installs either zone's, and butting them puts both on one screen. Owner ruling
    S2ACT-SEAM-CORRIDORS: corridors, never butted zones. (The 1-D plan's refusal, "different
    zones with no corridor filling the gap", generalised to both axes.)"""
    import numpy as np
    fill = clip_manifest.fill_mask(act) if getattr(act, "fill", None) is not None else None
    conns = list(getattr(act, "corridors", [])) + list(getattr(act, "shafts", []))
    joined = set()
    for k in conns:
        _ax, b4, af = clip_manifest.connector_ends(act, k)
        if b4 is not None and af is not None:
            joined.add((b4.id, af.id))
    clips = list(act.clips)
    for ax in ("x", "y"):
        i, j = (0, 1) if ax == "x" else (1, 0)
        for a in clips:
            for b in clips:
                if a is b or a.zone_key == b.zone_key:
                    continue
                g0, g1 = a.dst[i] + a.dst[i + 2], b.dst[i]
                p0 = max(a.dst[j], b.dst[j])
                p1 = min(a.dst[j] + a.dst[j + 2], b.dst[j] + b.dst[j + 2])
                if g1 < g0 or p1 <= p0:
                    continue
                if any(o is not a and o is not b and o.dst[i] < g1 and g0 < o.dst[i] + o.dst[i + 2]
                       and o.dst[j] < p1 and p0 < o.dst[j] + o.dst[j + 2] for o in clips):
                    continue
                if (a.id, b.id) in joined:
                    continue
                gap = g1 - g0
                if gap > 0:
                    painted = np.zeros((act.rows, act.cols), dtype=bool)
                    if fill is not None:
                        painted |= fill
                    for k in conns:
                        x, y, w, h = (v // clip_manifest.TILE_PX for v in k.dst)
                        painted[y:y + h, x:x + w] = True
                    lo, hi, q0, q1 = (v // clip_manifest.TILE_PX for v in (g0, g1, p0, p1))
                    sub = painted[lo:hi, q0:q1] if ax == "y" else painted[q0:q1, lo:hi]
                    if sub.all():
                        continue
                raise ClipRomError(
                    f"Z2 clips {a.id!r} ({'/'.join(a.tree_key)}) and {b.id!r} "
                    f"({'/'.join(b.tree_key)}) are different zones facing each other along "
                    f"{ax} with no corridor or shaft joining them and "
                    + ("nothing between them (butted)" if gap <= 0 else
                       f"void in the {gap} px between them")
                    + ". Owner ruling S2ACT-SEAM-CORRIDORS: corridors, never butted zones; "
                      "a seam nobody crosses is neutral fill (`fill`).")


def _guillotine(zl, sl, nzones, declared, min_cells, band, log_name="region plan"):
    """Split the label grid into pure rectangles (step 3 of the plan). `zl` (rows, cols)
    int: zone key or -1; `sl` int: -1 unconstrained, 0 dead, 1 live. `declared[axis]` =
    {cell index: rank} (0 a crossing, 1 a mouth). `band[axis]` = (lo, hi) the legal cut
    indices. Returns [(c0, c1, r0, r1, zone, song state or -1)] in cell units, half-open,
    left/top piece first."""
    import numpy as np
    rows, cols = zl.shape
    planes = [(zl == k) for k in range(nzones)] + [(sl == 0), (sl == 1)]
    pre = []
    for p in planes:
        a = np.zeros((rows + 1, cols + 1), dtype=np.int64)
        np.cumsum(np.cumsum(p, axis=0), axis=1, out=a[1:, 1:])
        pre.append(a)

    def count(P, c0, c1, r0, r1):
        return P[r1, c1] - P[r0, c1] - P[r1, c0] + P[r0, c0]

    def solve(c0, c1, r0, r1):
        present = [count(P, c0, c1, r0, r1) > 0 for P in pre]
        zs = [k for k in range(nzones) if present[k]]
        ss = [s for s, on in ((0, present[nzones]), (1, present[nzones + 1])) if on]
        if len(zs) <= 1 and len(ss) <= 1:
            if not zs:
                raise ClipRomError(f"Z2 {log_name}: a piece with no label was cut "
                                   f"(cells x {c0}..{c1} y {r0}..{r1}) — a planner fault")
            return [(c0, c1, r0, r1, zs[0], ss[0] if ss else -1)]
        best = None
        for axis in (0, 1):
            lo, hi = (c0, c1) if axis == 0 else (r0, r1)
            blo, bhi = band[axis]
            ps = np.arange(max(lo + min_cells, blo), min(hi - min_cells, bhi) + 1)
            if not len(ps):
                continue
            left, right = [], []
            for P in pre:
                if axis == 0:
                    L = P[r1, ps] - P[r0, ps] - P[r1, c0] + P[r0, c0]
                else:
                    L = P[ps, c1] - P[ps, c0] - P[r0, c1] + P[r0, c0]
                tot = count(P, c0, c1, r0, r1)
                left.append(L > 0)
                right.append((tot - L) > 0)
            left, right = np.array(left), np.array(right)
            nzl, nzr = left[:nzones].sum(axis=0), right[:nzones].sum(axis=0)
            ok = (nzl > 0) & (nzr > 0)
            nsl, nsr = left[nzones:].sum(axis=0), right[nzones:].sum(axis=0)
            for idx in np.flatnonzero(ok):
                p = int(ps[idx])
                key = (int(nzl[idx] + nzr[idx]), declared[axis].get(p, 2),
                       int(nsl[idx] + nsr[idx]), p, axis)
                if best is None or key < best[0]:
                    best = (key, axis, p)
        if best is None:
            raise ClipRomError(
                f"Z2 {log_name}: the piece x {c0 * 8}..{c1 * 8 - 1}, y {r0 * 8}..{r1 * 8 - 1} "
                f"holds zones {zs} (song states {ss}) and no legal cut separates them (every "
                f"cut must keep REGION_MIN_SPAN on both sides and lie in the camera centre's "
                f"band). A connector is too short for the rows its crossing needs, or two zones "
                f"meet with nothing between them")
        _key, axis, p = best
        if axis == 0:
            return solve(c0, p, r0, r1) + solve(p, c1, r0, r1)
        return solve(c0, c1, r0, p) + solve(c0, c1, p, r1)

    sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))
    return solve(0, cols, 0, rows)


def region_plan(act, donor_root, act_h_px=None, frames=None, model=None):
    """The clip act's region rows — rectangles, planned in 2-D (the block above). Returns
    {"act", "zones", "rows", "overrides", "crossings", "frames"}; each row
    {"x0", "x1", "y0", "y1" (inclusive px), "key", "preset_label", "song", "song_id", "why"}.

    `frames` (crossing_frames) and `model` (clip_camera.CameraModel) are computed from the act
    when not handed in."""
    import numpy as np
    import clip_camera
    sec = act.section_px
    act_w = act.grid_w * sec
    act_h = act_h_px or act.grid_h * sec
    check_zone_faces(act)
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
    music = zone_music(act)
    ids = song_ids() if music else {}
    for z in zones:
        z["music"] = music.get(z["key"])
    frames = frames or crossing_frames(act)
    model = model or clip_camera.CameraModel.for_act(act, donor_root)
    cam = model.c
    crossings = connector_crossings(act, frames, cam)

    C = clip_manifest.TILE_PX
    cols, rows = act_w // C, act_h // C
    zl = np.full((rows, cols), -1, dtype=np.int16)
    sl = np.full((rows, cols), -1, dtype=np.int8)
    # (1) reachable centres whose screen shows exactly one zone (song unconstrained)
    vis = model.visible()[:, :rows, :cols]
    one = (vis.sum(axis=0) == 1) & model.centres[:rows, :cols]
    for i, k in enumerate(model.keys):
        zl[one & vis[i]] = k
    # (2) connectors: each side of the crossing, the dead band (song 0 for a zone WITH a song)
    for k in list(act.corridors) + list(getattr(act, "shafts", [])):
        _ax, b4, af = clip_manifest.connector_ends(act, k)
        x, y, w, h = (v // C for v in k.dst)
        if b4 is None and af is None:
            continue
        if b4 is None or af is None or b4.zone_key == af.zone_key:
            z = (b4 or af).zone_key
            zl[y:y + h, x:x + w] = z
            sl[y:y + h, x:x + w] = -1
    for cr in crossings:
        k = cr["connector"]
        x, y, w, h = (v // C for v in k.dst)
        cut = cr["c"] // C
        for side, clip in (("before", cr["before"]), ("after", cr["after"])):
            if cr["axis"] == "x":
                xs = slice(x, cut) if side == "before" else slice(cut, x + w)
                ys = slice(y, y + h)
            else:
                ys = slice(y, cut) if side == "before" else slice(cut, y + h)
                xs = slice(x, x + w)
            zl[ys, xs] = clip.zone_key
            sl[ys, xs] = 0 if music.get(clip.zone_key) else -1
    # (3) the clips' own rectangles, playing their zone's song
    for cl in act.clips:
        x, y, w, h = (v // C for v in cl.dst)
        zl[y:y + h, x:x + w] = cl.zone_key
        sl[y:y + h, x:x + w] = 1 if music.get(cl.zone_key) else -1

    declared = ({}, {})
    for cr in crossings:
        ax = 0 if cr["axis"] == "x" else 1
        declared[ax][cr["c"] // C] = 0
        for m in (cr["a"], cr["b"]):
            declared[ax].setdefault(m // C, 1)
    min_span, half_w, half_h = _region_bounds()
    min_cells = -(-min_span // C)
    # a cut at cell p makes p*8 a row's x0 (and p*8 - 1 the previous row's x1): the
    # descriptor wants x0 - 1 >= CENTRE_X_MIN and x0 <= CENTRE_X_MAX
    band = ((-(-(half_w + 1) // C), (act_w - half_w) // C),
            (-(-(half_h + 1) // C), (act_h - half_h) // C))
    pieces = _guillotine(zl, sl, len(zones), declared, min_cells, band)

    rows_out = []
    for c0, c1, r0, r1, key, state in pieces:
        z = zones[key]
        song = music.get(key) if state == 1 else None
        where = f"x {c0 * C}..{c1 * C - 1}, y {r0 * C}..{r1 * C - 1}"
        if state == 1 and song:
            why = f"{z['donor']} {z['zone']}: plays {song} = {ids[song]}"
        elif state == 0:
            why = f"{z['donor']} {z['zone']}: a connector's dead band, no song"
        else:
            why = f"{z['donor']} {z['zone']}"
        row = {"x0": c0 * C, "x1": c1 * C - 1, "y0": r0 * C, "y1": r1 * C - 1, "key": key,
               "preset_label": z["preset_label"], "song": song,
               "why": f"{why} ({where})"}
        if song:
            row["song_id"] = ids[song]
        rows_out.append(row)
    out_cross = []
    for cr in crossings:
        d = {"connector": cr["id"], "axis": cr["axis"], "at": cr["c"],
             "from_key": cr["before"].zone_key, "to_key": cr["after"].zone_key,
             "gap": [cr["a"], cr["b"]], "need": [cr["need_before"], cr["need_after"]]}
        if cr["axis"] == "x":
            d.update(x=cr["c"], corridor=cr["id"])
        else:
            d.update(y=cr["c"], shaft=cr["id"])
        out_cross.append(d)
    for key, ext in tall_plans(act).items():
        zones[key]["tall"] = ext
    return {"act": act.id, "zones": zones, "rows": rows_out,
            "overrides": crossing_overrides(act), "crossings": out_cross,
            "frames": frames, "blob_groups": [sorted(g) for g in blob_groups(act)]}


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


def check_palette_crossings(act, mod_text, data_text, consts=None, log=None, bg_frames=None,
                            frames=None, cam=None):
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

    BOTH AXES, EVERY CONNECTOR (the woven report's §C items 3 and 4, 2026-09-27). The walk is
    per CONNECTOR joining two zones (clip_manifest.connector_ends), on that connector's own
    axis: a corridor is walked in x at every 16-px y of its rectangle, a SHAFT in y at every
    16-px x of its rectangle, with CAM_SCREEN_HALF_H and CAM_MAX_Y_STEP for the vertical one.
    (Until then it walked each left-to-right neighbour pair through the FIRST corridor
    covering their gap only, `corr[0]`: a second corridor in one gap was never walked.)
    `frames` (crossing_frames) gives the background term PER PAIR — the frames INTO a side
    from the other — where `bg_frames` gave it per zone; either may be given. Rule (a) holds
    a row to a clip only where they overlap on BOTH axes (a 2-D row plan puts zones side by
    side in y as well).
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
            if (r[0] <= c.dst[0] + c.dst[2] - 1 and c.dst[0] <= r[1]
                    and r[2] <= c.dst[1] + c.dst[3] - 1 and c.dst[1] <= r[3]
                    and r[4] != want[c.zone_key]):
                raise ClipRomError(
                    f"Z2 clip {c.id!r} ({'/'.join(c.tree_key)}) reaches region x "
                    f"{r[0]}..{r[1]}, y {r[2]}..{r[3]}, which binds {r[4]} — that zone is "
                    f"drawn in another zone's colours there")
    # (b) walk every connector joining two different zones, on its own axis, at every 16 px
    # across it
    cam_c = cam or _cam_constants()
    out = []
    for k in list(getattr(act, "corridors", [])) + list(getattr(act, "shafts", [])):
        ax, a, b = clip_manifest.connector_ends(act, k)
        if a is None or b is None or a.zone_key == b.zone_key:
            continue
        i, j = (0, 1) if ax == "x" else (1, 0)
        if ax == "x":
            half, stp = half_w, step
        else:
            half, stp = cam_c["CAM_SCREEN_HALF_H"], cam_c["CAM_MAX_Y_STEP"]
        a_end = a.dst[i] + a.dst[i + 2]          # first px past zone a along the axis
        b_start = b.dst[i]
        across = range(k.dst[j], k.dst[j] + k.dst[j + 2], 16)
        at = (lambda u, v: row_at(u, v)) if ax == "x" else (lambda u, v: row_at(v, u))
        if frames is not None:
            bf_a = frames["pair"][(b.zone_key, a.zone_key)]
            bf_b = frames["pair"][(a.zone_key, b.zone_key)]
        else:
            bf_a, bf_b = bgf.get(a.zone_key, 0), bgf.get(b.zone_key, 0)
        reported = False
        shortfall = None
        for v in across:
            # a change is a change of PRESET: two rows binding one preset (the MUSIC block's
            # dead-band split, or the 2-D plan's extra pieces) re-run Effects_InstallPreset on
            # the same record, which installs nothing new (measured by the crossing
            # witnesses, not assumed here)
            changes = []
            prev = at(a_end - 1, v)
            for u in range(a_end - 1, b_start + 1):
                r = at(u, v)
                if r[4] != prev[4]:
                    changes.append((u, prev[4], r[4]))
                prev = r
            pal_changes = [ch for ch in changes if presets[ch[1]][0] != presets[ch[2]][0]]
            if len(changes) != 1 or len(pal_changes) != 1:
                raise ClipRomError(
                    f"Z2 walking the camera centre from {a.id!r} to {b.id!r} along {ax} at "
                    f"{'y' if ax == 'x' else 'x'}={v} installs {len(changes)} preset(s) and "
                    f"changes the palette {len(pal_changes)} time(s), not exactly once: "
                    f"{changes}")
            x_c = changes[0][0]
            fr_l = max(pal_frames, bf_a)
            fr_r = max(pal_frames, bf_b)
            need_l, need_r = half + fr_l * stp, half + fr_r * stp
            short_l, short_r = need_l - (x_c - a_end), need_r - (b_start - x_c)
            if (short_l > 0 or short_r > 0) and ov["crossing_margin"] == "report":
                # PER-CLIP OVERRIDE crossing_overrides.crossing_margin = report: a LIMIT TEST
                # the owner asked to see glitch. The shortfall is NOT waived silently: it is
                # printed on every bake and returned, in frames at the camera cap.
                shortfall = {"left_px": max(0, short_l), "right_px": max(0, short_r),
                             "left_frames": -(-max(0, short_l) // stp),
                             "right_frames": -(-max(0, short_r) // stp)}
                if log and not reported:
                    reported = True
                    log("clip_rom_bake: " + "!" * 72)
                    log(f"clip_rom_bake: Z2 SHORTFALL, NOT ENFORCED (per-clip override "
                        f"crossing_margin = report): the crossing at {ax}={x_c} has "
                        f"{x_c - a_end} px {'left' if ax == 'x' else 'above'} / "
                        f"{b_start - x_c} px {'right' if ax == 'x' else 'below'} and the rule "
                        f"needs {need_l} / {need_r}. Expect up to "
                        f"{shortfall['left_frames']} frame(s) arriving "
                        f"{'LEFT' if ax == 'x' else 'UP'} and {shortfall['right_frames']} "
                        f"arriving {'RIGHT' if ax == 'x' else 'DOWN'}, at the camera cap, where "
                        f"the far zone is on screen before its palette or background has landed")
                    log("clip_rom_bake: " + "!" * 72)
            elif x_c - need_l < a_end or x_c + need_r > b_start:
                what = "a cross-fade" if want_trans == 1 else "a SNAP (per-clip override)"
                pal_term = (f"PAL_FADE_FRAMES {fade}" if want_trans == 1
                            else f"SNAP_FRAMES {SNAP_FRAMES}")
                hname = "CAM_SCREEN_HALF_W" if ax == "x" else "CAM_SCREEN_HALF_H"
                sname = "CAM_MAX_X_STEP" if ax == "x" else "CAM_MAX_Y_STEP"
                sides = ("left", "right") if ax == "x" else ("above", "below")
                raise ClipRomError(
                    f"Z2 the crossing from {a.id!r} to {b.id!r} is at {ax}={x_c}, but {what} "
                    f"needs {need_l} px of {k.id!r} {sides[0]} of it and {need_r} "
                    f"{sides[1]} ({hname} {half} + {sname} {stp} x the larger of {pal_term} "
                    f"and the background switch into that side's zone, {bf_a} / {bf_b} "
                    f"frames) and the connector runs {ax} {a_end}..{b_start - 1}: "
                    f"{x_c - a_end} px {sides[0]}, {b_start - x_c} {sides[1]}")
        row = {"from": a.id, "to": b.id, "axis": ax, "connector": k.id,
               "margin_needed": max(need_l, need_r),
               "shortfall": shortfall,
               "palette": "snap" if want_trans == 0 else "fade",
               "palette_frames": pal_frames,
               "background_frames": [bf_a, bf_b]}
        if ax == "x":
            row.update(x=x_c, margin_needed_left=need_l, margin_needed_right=need_r,
                       margin_left=x_c - a_end, margin_right=b_start - x_c,
                       ys_walked=len(across))
        else:
            row.update(y=x_c, margin_needed_top=need_l, margin_needed_bottom=need_r,
                       margin_top=x_c - a_end, margin_bottom=b_start - x_c,
                       xs_walked=len(across))
        out.append(row)
        if log:
            log(f"clip_rom_bake: Z2 {a.id} -> {b.id} ({k.id}, axis {ax}): ONE preset install "
                f"and ONE palette change at {ax}={x_c} on every one of {len(across)} "
                f"{'rows' if ax == 'x' else 'columns'}; {x_c - a_end} px of connector before "
                f"it and {b_start - x_c} after, {need_l} / {need_r} needed (palette "
                f"{'SNAP' if want_trans == 0 else 'fade'} {pal_frames} frames, background "
                f"switch {bf_a} / {bf_b} frames)")
    return out


def check_screen(act, model, mod_text, data_text, frames, cam=None, log=None):
    """THE SCREEN CHECK (the woven report's §C item 15; its woven.py check, promoted): over
    every REACHABLE camera centre (clip_camera), against the region rows parsed back out of
    what was EMITTED:
      * MIXED — no screen shows two zones (always refused);
      * WRONG — no screen shows a zone while its centre is in another zone's region (always
        refused: that zone would be drawn in the other's palette and background);
      * SLACK — wherever two neighbouring reachable centres (8 px apart, either axis) sit in
        regions of different zones, the zone being ENTERED is still off screen by at least
        CAM_MAX_{X,Y}_STEP x the frames that crossing takes (crossing_frames, per pair): the
        camera moves at most that far a frame, so the zone cannot appear before its palette
        and background have landed. The boundary lies between the two cell centres, so the
        distance there is the entered cell's gap + 4 — the reading under which a connector
        cut exactly to the rule reads slack 0 (the report's calibration against the 384-px
        tunnel crossing_witness measured glitch-free). Refused unless the act carries
        crossing_margin = report, which prints it instead;
      * VOID — a reachable centre inside a connector whose screen shows an unpainted act cell
        (no clip, connector or fill): while a crossing replaces the background, a void cell
        shows it. REPORTED (count and first centre); refused only when the act has a `fill`,
        whose whole purpose is that nothing between the zones is void.
    Returns the counts and the per-pair slack table."""
    import numpy as np
    cam = cam or model.c
    rows, _presets = parse_clip_module_rows(mod_text, data_text)
    C = clip_manifest.TILE_PX
    R, K = model.centres.shape
    region = np.full((R, K), -1, dtype=np.int16)
    cover = np.zeros((R, K), dtype=np.int16)
    for x0, x1, y0, y1, lab in rows:
        if x0 % C or (x1 + 1) % C or y0 % C or (y1 + 1) % C:
            raise ClipRomError(f"SCREEN row x {x0}..{x1}, y {y0}..{y1} is not on the {C}-px "
                               f"cell grid the model counts on — UNMEASURABLE")
        k = int(lab.rsplit("_", 1)[1])
        region[y0 // C:(y1 + 1) // C, x0 // C:(x1 + 1) // C] = k
        cover[y0 // C:(y1 + 1) // C, x0 // C:(x1 + 1) // C] += 1
    if (cover != 1).any():
        raise ClipRomError(f"SCREEN the emitted rows cover {int((cover == 0).sum())} cell(s) "
                           f"zero times and {int((cover > 1).sum())} more than once; they must "
                           f"tile the act — UNMEASURABLE")
    cen = model.centres
    vis = model.visible()
    nvis = vis.sum(axis=0)
    keys = model.keys
    mixed = cen & (nvis > 1)
    vis_key = np.full((R, K), -1, dtype=np.int16)
    for i, k in enumerate(keys):
        vis_key[vis[i] & (nvis == 1)] = k
    wrong = cen & (nvis == 1) & (vis_key != region)
    out = {"reachable_centres": int(cen.sum()), "mixed": int(mixed.sum()),
           "wrong": int(wrong.sum()), "crossings": [], "void": 0}
    if mixed.any():
        ys, xs = np.nonzero(mixed)
        raise ClipRomError(f"Z1 (screen, both axes) {out['mixed']} reachable camera centre(s) "
                           f"show two zones on one screen, first at ({xs[0] * C + 4}, "
                           f"{ys[0] * C + 4})")
    if wrong.any():
        ys, xs = np.nonzero(wrong)
        y, x = int(ys[0]), int(xs[0])
        raise ClipRomError(
            f"Z2 (screen, both axes) {out['wrong']} reachable camera centre(s) show one zone "
            f"from inside ANOTHER zone's region — first at ({x * C + 4}, {y * C + 4}), which "
            f"shows zone {int(vis_key[y, x])} and installs zone {int(region[y, x])}'s palette "
            f"and background")
    table = {}
    gaps = {k: model.gap(k) for k in keys}
    for dy, dx, ax in ((0, 1, "x"), (1, 0, "y")):
        step = cam["CAM_MAX_X_STEP"] if ax == "x" else cam["CAM_MAX_Y_STEP"]
        a_cen, b_cen = cen[:R - dy, :K - dx], cen[dy:, dx:]
        a_reg, b_reg = region[:R - dy, :K - dx], region[dy:, dx:]
        edge = a_cen & b_cen & (a_reg != b_reg)
        if not edge.any():
            continue
        for into_first in (True, False):
            # entering the FIRST cell's zone from the second, then the other way round
            reg_in, reg_from = (a_reg, b_reg) if into_first else (b_reg, a_reg)
            for z in keys:
                gz = gaps[z][:R - dy, :K - dx] if into_first else gaps[z][dy:, dx:]
                for r in keys:
                    if r == z:
                        continue
                    m = edge & (reg_in == z) & (reg_from == r)
                    if not m.any():
                        continue
                    s_min = int(gz[m].min()) + C // 2
                    f = frames["pair"][(r, z)]
                    slack = s_min - step * f
                    key = (r, z)
                    if key not in table or slack < table[key]["slack"]:
                        table[key] = {"from_key": r, "into_key": z, "frames": f,
                                      "need_px": step * f, "s_min": s_min, "slack": slack,
                                      "axis": ax, "pairs": int(m.sum())}
    out["crossings"] = [table[k] for k in sorted(table)]
    short = [t for t in out["crossings"] if t["slack"] < 0]
    ov = crossing_overrides(act)
    if short and ov["crossing_margin"] != "report":
        t = short[0]
        raise ClipRomError(
            f"Z2 (screen, both axes) crossing into zone {t['into_key']} from zone "
            f"{t['from_key']} ({t['axis']}): at the region boundary the entered zone is "
            f"{t['s_min']} px off screen and the crossing needs {t['need_px']} "
            f"({t['frames']} frames at the camera cap): slack {t['slack']} px. "
            f"{len(short)} crossing direction(s) short")
    if short and log:
        log("clip_rom_bake: SCREEN SHORTFALL, NOT ENFORCED (crossing_margin = report): "
            + "; ".join(f"{t['from_key']}->{t['into_key']} slack {t['slack']} px"
                        for t in short))
    # VOID seen from inside a connector
    lane = np.zeros((R, K), dtype=bool)
    for k in list(act.corridors) + list(getattr(act, "shafts", [])):
        x, y, w, h = (v // C for v in k.dst)
        lane[y:y + h, x:x + w] = True
    lc = lane & cen
    if lc.any():
        unp = (~model.painted).astype(np.int64)
        ii = np.zeros((R + 1, K + 1), dtype=np.int64)
        np.cumsum(np.cumsum(unp, axis=0), axis=1, out=ii[1:, 1:])
        ys, xs = np.nonzero(lc)
        hw, hh = cam["CAM_SCREEN_HALF_W"] // C, cam["CAM_SCREEN_HALF_H"] // C
        x0 = np.clip(xs - hw, 0, K)
        x1 = np.clip(xs + hw, 0, K)
        y0 = np.clip(ys - hh, 0, R)
        y1 = np.clip(ys + hh, 0, R)
        cnt = ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0]
        out["void"] = int((cnt > 0).sum())
        if out["void"]:
            i = int(np.flatnonzero(cnt > 0)[0])
            out["void_first"] = [int(xs[i]) * C + 4, int(ys[i]) * C + 4]
            if getattr(act, "fill", None) is not None:
                raise ClipRomError(
                    f"VOID {out['void']} reachable camera centre(s) inside a connector show "
                    f"unpainted act cells (first at {out['void_first']}); this act has a "
                    f"`fill`, so nothing between its zones may be void — widen the fill")
    if log:
        log(f"clip_rom_bake: SCREEN {out['reachable_centres']} reachable centres: MIXED 0, "
            f"WRONG 0, VOID {out['void']}; crossings "
            + (", ".join(f"{t['from_key']}->{t['into_key']} ({t['axis']}) slack "
                         f"{t['slack']:+d} px" for t in out["crossings"]) or "none"))
    return out


# ---------------------------------------------------------------------------
# MUSIC — each zone's own song, changed where the camera LEAVES the corridor
# (S2CLIP-REGION-MUSIC step 6; owner ruling S2CLIP-MUSIC-FEEL = cut-at-exit)
# ---------------------------------------------------------------------------
#
# THE ENGINE HALF landed at step 5: `Region.rg_song` names a region's song (0 = leave the
# music alone); Parallax_CheckBoundary's slow path records a non-zero one in Music_Want, and
# Music_Service posts it when it differs from Music_Current. So a song changes when the
# camera centre enters a row NAMING a different song, and a 0 row never changes anything.
#
# THE DATA HALF is here. A clip's optional `music` (a SONG_* NAME, clip_manifest R3) is its
# zone's song. region_plan splits each zone's strip at the corridor mouths it touches: the
# corridor-side part names 0, the outer part the zone's song. The crossing (preset, palette,
# background) stays at the corridor's middle; the SONG changes at the far mouth, as the camera
# comes out into the new zone, and going back the old zone's song starts as it comes out on
# that side. The whole corridor is a dead band for music, so a player wiggling on any one line
# re-enters a row naming the song already current, or a 0 row: no request (the step-5
# compare). The rows carry the song's ID, read from the game's authority
# (games/sonic4/config/sound_ids.emp) by song_ids() on every bake, with the NAME in the row's
# comment; act_descriptor.emp's rule 9 bounds it. (Emitting the NAME was tried first: the
# descriptor's comptime row check then read it as a Label — "`<` not defined for label and
# int" at its rule 9 — measured 2026-09-25.)

SOUND_IDS_REL = "games/sonic4/config/sound_ids.emp"


def zone_music(act):
    """{zone key: SONG_* name} for every zone whose clips name `music` (clip_manifest R3
    already holds one song per zone), each name resolved against the game's authority."""
    out = {}
    for c in act.clips:
        if getattr(c, "music", None):
            out[c.zone_key] = c.music
    if out:
        ids = song_ids()
        unknown = sorted({n for n in out.values() if n not in ids})
        if unknown:
            raise ClipRomError(f"MUSIC {unknown} is not a song id in {SOUND_IDS_REL} (it has "
                               f"{sorted(ids)})")
    return out


def song_ids():
    """{SONG_* name: id} READ from the game's authority, never typed (SONG_COUNT excluded:
    a bound, not an id)."""
    from effects_budget_check import emp_constants, eval_int_expr
    c = emp_constants(os.path.join(REPO, SOUND_IDS_REL))
    return {k: eval_int_expr(v, c) for k, v in c.items()
            if k.startswith("SONG_") and k != "SONG_COUNT"}


_SONG_ROW_RE = re.compile(
    r"Region\{\s*rg_x0:\s*(\d+),\s*rg_x1:\s*(\d+),\s*rg_y0:\s*(\d+),\s*rg_y1:\s*(\d+),"
    r"[^}]*?rg_song:\s*(\d+),")


def _song_rows(text, name, what):
    """[(x0, x1, y0, y1, song NAME or None)] parsed back out of an emitted table; an id the
    game's authority does not define is refused by number."""
    m = re.search(name + r":\s*\[Region;\s*(\d+)\]\s*=\s*\[(.*?)\n\]", text, re.S)
    if not m:
        raise ClipRomError(f"MUSIC {what} carries no {name} table — UNMEASURABLE")
    found = _SONG_ROW_RE.findall(m.group(2))
    by_id = {v: k for k, v in song_ids().items()} if any(e != "0" for *_x, e in found) else {}
    bad = sorted({int(e) for *_x, e in found if e != "0" and int(e) not in by_id})
    if bad:
        raise ClipRomError(f"MUSIC {what}'s {name} names song id(s) {bad}, which "
                           f"{SOUND_IDS_REL} does not define")
    rows = [(int(a), int(b), int(c), int(d), (None if e == "0" else by_id[int(e)]))
            for a, b, c, d, e in found]
    if len(rows) != int(m.group(1)):
        raise ClipRomError(f"MUSIC {what} declares {m.group(1)} rows for {name} and "
                           f"{len(rows)} carry an rg_song that parses — UNMEASURABLE")
    return rows


def check_music_crossings(act, mod_text, data_text, spawn=None, log=None):
    """MUSIC — read back out of what was EMITTED (both tables, which must agree):

      * every row covering part of a clip (on BOTH axes) names that clip's `music` (or 0 if
        it names none), unless the row lies wholly inside a connector's span along that
        connector's axis (its dead band);
      * every row overlapping a connector between two zones names 0 (the dead band);
      * walking the camera centre along each such connector's axis, at every 16 px across
        it, the FIRST row naming a song after the near zone's is at the far mouth and names
        the far zone's song; walking back, the first is one px before the near mouth and
        names the near zone's. Exactly one song change each way, at the mouth;
      * the row holding `spawn` (the act's start) names the start zone's song, so the
        act-load rescan requests it.
    A corridor is walked in x, a SHAFT in y (the woven report's §C item 3). Returns
    [{from, to, axis, connector, right_x, left_x (or down_y, up_y), dead_band_px, songs}]
    per connector. An act whose clips name no music is held to "every row names 0" and
    returns []."""
    rows = _song_rows(mod_text, "OJZ_CLIP_REGION_ROWS", "the clip module")
    emitted = _song_rows(data_text, "OJZ_Clip_Regions", "the clip data block")
    if rows != emitted:
        raise ClipRomError(f"MUSIC the descriptor's rows and the Act's differ in rg_song: "
                           f"{rows} vs {emitted}")
    want = {c.zone_key: getattr(c, "music", None) for c in act.clips}
    if not any(want.values()):
        named = [r for r in rows if r[4]]
        if named:
            raise ClipRomError(f"MUSIC no clip names music, yet rows name songs: {named}")
        return []

    def song_at(x, y):
        hit = [r for r in rows if r[0] <= x <= r[1] and r[2] <= y <= r[3]]
        if len(hit) != 1:
            raise ClipRomError(f"MUSIC ({x}, {y}) is in {len(hit)} region rows; they must "
                               f"tile the act")
        return hit[0][4]

    conns = []
    for k in list(getattr(act, "corridors", [])) + list(getattr(act, "shafts", [])):
        ax, a, b = clip_manifest.connector_ends(act, k)
        if a is not None and b is not None and a.zone_key != b.zone_key:
            i = 0 if ax == "x" else 1
            conns.append((k, ax, a, b, a.dst[i] + a.dst[i + 2], b.dst[i]))

    def in_band(r):
        """wholly inside some connector's span along ITS axis (the 1-D plan's `in_gap`)"""
        for _k, ax, _a, _b, g0, g1 in conns:
            lo, hi = (r[0], r[1]) if ax == "x" else (r[2], r[3])
            if g0 <= lo and hi < g1:
                return True
        return False

    for c in act.clips:
        for r in rows:
            if (r[0] <= c.dst[0] + c.dst[2] - 1 and c.dst[0] <= r[1]
                    and r[2] <= c.dst[1] + c.dst[3] - 1 and c.dst[1] <= r[3]
                    and not in_band(r) and r[4] != want[c.zone_key]):
                raise ClipRomError(f"MUSIC clip {c.id!r} reaches row x {r[0]}..{r[1]}, y "
                                   f"{r[2]}..{r[3]}, which names {r[4] or 0}, not its own "
                                   f"music {want[c.zone_key] or 0}")
    out = []
    for k, ax, a, b, g0, g1 in conns:
        kx, ky, kw, kh = k.dst
        for r in rows:
            if (r[0] < kx + kw and kx <= r[1] and r[2] < ky + kh and ky <= r[3]
                    and in_band(r) and r[4]):
                raise ClipRomError(f"MUSIC row x {r[0]}..{r[1]}, y {r[2]}..{r[3]} lies "
                                   f"inside connector {k.id!r} and names {r[4]}: the dead "
                                   f"band must name 0")
        # the engine's rule replayed: a row naming a song different from the current one
        # changes it; a 0 row changes nothing (Music_Want only takes non-zero songs)
        j = 1 if ax == "x" else 0
        across = range(k.dst[j], k.dst[j] + k.dst[j + 2], 16)
        pt = (lambda u, v: (u, v)) if ax == "x" else (lambda u, v: (v, u))
        want_f = [(g1, want[b.zone_key])] if want[b.zone_key] else []
        want_b = [(g0 - 1, want[a.zone_key])] if want[a.zone_key] else []
        for v in across:
            def changes(us):
                cur, out_ = song_at(*pt(us[0], v)), []
                for u in us[1:]:
                    s_ = song_at(*pt(u, v))
                    if s_ and s_ != cur:
                        out_.append((u, s_))
                        cur = s_
                return out_
            fwd = changes(range(g0 - 1, g1 + 1))
            bwd = changes(range(g1, g0 - 2, -1))
            if fwd != want_f or bwd != want_b:
                raise ClipRomError(
                    f"MUSIC connector {k.id!r} {a.id!r} -> {b.id!r} ({ax} {g0}..{g1 - 1}, at "
                    f"{'y' if ax == 'x' else 'x'}={v}): walking "
                    f"{'right' if ax == 'x' else 'down'} the song changes at {fwd}, the rule is "
                    f"{want_f} (the far mouth); walking {'left' if ax == 'x' else 'up'} at "
                    f"{bwd}, the rule is {want_b} (the near mouth)")
        row = {"from": a.id, "to": b.id, "axis": ax, "connector": k.id,
               "dead_band_px": g1 - g0, "songs": [want[a.zone_key], want[b.zone_key]]}
        if ax == "x":
            row.update(right_x=g1, left_x=g0 - 1)
        else:
            row.update(down_y=g1, up_y=g0 - 1)
        out.append(row)
        if log:
            log(f"clip_rom_bake: MUSIC {a.id} -> {b.id} ({k.id}, axis {ax}): "
                f"{want[b.zone_key]} starts where the camera centre reaches {ax}={g1} going "
                f"{'right' if ax == 'x' else 'down'}, {want[a.zone_key]} at {ax}={g0 - 1} "
                f"going {'left' if ax == 'x' else 'up'}; the connector {ax} {g0}..{g1 - 1} "
                f"({g1 - g0} px) names no song")
    if spawn is not None:
        holder = [c for c in act.clips if c.dst[0] <= spawn[0] < c.dst[0] + c.dst[2]
                  and c.dst[1] <= spawn[1] < c.dst[1] + c.dst[3]]
        if len(holder) == 1 and song_at(spawn[0], spawn[1]) != want[holder[0].zone_key]:
            raise ClipRomError(f"MUSIC the start ({spawn[0]}, {spawn[1]}) is in a row naming "
                               f"{song_at(spawn[0], spawn[1])}, not the start zone's "
                               f"{want[holder[0].zone_key]}: the act-load request would miss it")
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


def _union_backgrounds(own, order, what):
    """{key: (words re-indexed into the union, the union, info with co_resident=True)} and the
    union — the zones in `order` sharing ONE tile blob. The first zone's tiles keep their own
    indices; every later zone's tiles not already in it are appended, by clip_bg_lower's
    CANONICAL form (the least of a tile's four flips), so a word's flip bits stay valid when
    only its index is rewritten. `what` names the blob in a refusal."""
    from vram_map import BG_TILE_CAPACITY
    union, index = [], {}
    for t in own[order[0]][1]:
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
                    f"BG {what}: {info['zone']} cell {i} re-indexes to word $0000, which "
                    f"inject_editor_bg.rebase_layout keeps as the TRANSPARENT word — this "
                    f"opaque tile would vanish")
            # FIDELITY: the union entry the new word names IS the tile the old word named
            if union[nw & 0x7FF] != tiles[w & 0x7FF]:
                raise ClipRomError(f"BG {what}: {info['zone']} cell {i} re-indexed to a "
                                   f"different tile")
            new.append(nw)
        out[k] = (new, None, dict(info, co_resident=True))
    if len(union) > BG_TILE_CAPACITY:
        raise ClipRomError(
            f"BG {what}: the zones' backgrounds need {len(union)} tiles together and the "
            f"arena holds BG_TILE_CAPACITY = {BG_TILE_CAPACITY} (vram.toml bg_region, a hard "
            f"VRAM boundary). They cannot be co-resident; "
            + ("drop the override." if what == "co-resident" else "split the group."))
    return {k: (w, list(union), info) for k, (w, _n, info) in out.items()}, union


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
    out, union = _union_backgrounds(own, order, "co-resident")
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
    start = start_zone_key(plan, spawn)
    co_resident = (plan.get("overrides") or {}).get("background") == "co_resident"
    lowered, own = {}, {}
    for z in plan["zones"]:
        # a TALL zone (tall_plans) is lowered over its whole reachable height; an injected
        # `lower` (the tests') sees exactly the call it always did
        own[z["key"]] = (lower(z["donor"], z["zone"]) if lower else
                         lower_zone(z["donor"], z["zone"], z.get("tall")))
    # BLOB GROUPS (the woven report's §C item 14): every group of two or more zones shares ONE
    # tile blob — the act default when it holds the start zone (its rows name rg_bg_tiles 0,
    # as co_resident's do), else one blob named by every member's rows. A crossing between
    # two zones of one group finds the arena already holding the blob (BG_Stream_Update's
    # pointer compare) and pays only the repaint; into another group it pays the overwrite.
    groups = [set(g) for g in plan.get("blob_groups") or []]
    group_of = {k: g for g in groups for k in g}
    unions = {}
    if co_resident:
        own = co_resident_backgrounds(plan, own, start, log=log)
    else:
        from vram_map import BG_TILE_CAPACITY
        for g in groups:
            if len(g) < 2:
                continue
            order = ([start] + sorted(g - {start})) if start in g else sorted(g)
            names = "+".join(own[k][2]["zone"] for k in order)
            sizes = " + ".join(str(len(own[k][1])) for k in order)
            sub, union = _union_backgrounds({k: own[k] for k in g}, order,
                                            f"blob group {names}")
            own.update(sub)
            unions[min(g)] = union
            if log:
                log(f"clip_rom_bake: BACKGROUND BLOB GROUP {names}: {sizes} tiles share ONE "
                    f"{len(union)}-tile blob "
                    + ("(the act default: it holds the start zone)" if start in g else
                       f"(OJZ_Clip_BG_Tiles_{min(g)})")
                    + f"; arena {BG_TILE_CAPACITY} tiles")
    start_shared = co_resident or len(group_of.get(start, ())) > 1
    for z in plan["zones"]:
        words, tiles, info = own[z["key"]]
        lowered[z["key"]] = (words, tiles)
        z["bg"] = info
        z["bg_tile_bytes_effective"] = len(tiles) * 32
        if info["line0_cells"] and log:
            log(f"clip_rom_bake: BG WARNING — {z['donor']}:{z['zone']}'s background draws "
                f"{info['line0_cells']} cell(s) on CRAM line 0, the character line; kept as "
                f"the donor has them (TAGGED)")
        tall = z.get("tall")
        plane = CBL.PLANE_COLS * CBL.PLANE_ROWS
        if z["key"] == start:
            override = os.path.join(baked_dir, DEFAULT_BG_OVERRIDE)
            with open(override, "w") as fh:
                # the act default is ONE plane by contract (bg.emp's BG_LAYOUT_SIZE ensure:
                # BG_Init blits it before any camera exists). A TALL start zone hands it the
                # map's first plane; its rows name the whole map, and Section_RedrawPlanes'
                # windowed prime replaces the plane before the first visible frame.
                json.dump(CBL.override_doc(words[:plane], tiles), fh)
            import inject_editor_bg as ieb
            ieb.main(_ClipDefaultBgAct(override, gen_dir))
            if start_shared:
                # the co-resident blob may reach into the band reserve ONLY because no band
                # exists to use it: read that back out of what the injector wrote
                with open(os.path.join(gen_dir, "bg_anim.emp")) as fh:
                    if "BgAnim_Table: u16 = 0" not in fh.read():
                        raise ClipRomError(
                            "BG co-resident: the act default's bg_anim.emp is not the "
                            "zero-band stub, so the band reserve the shared blob uses may "
                            "be claimed by a band — refused")
            z["bg_role"] = "act_default"
            if not tall:
                continue
        else:
            z["bg_role"] = "region"
        lay = CLIP_BG_LAYOUT_BIN.format(key=z["key"])
        blob = CBL.layout_blob(words)
        with open(os.path.join(gen_dir, lay), "wb") as fh:
            fh.write(blob)
        z.update(bg_layout_label=f"OJZ_Clip_BG_Layout_{z['key']}",
                 bg_layout_embed=f"{GEN_REL}/{lay}", bg_layout_bytes=len(blob),
                 bg_span=(len(words) // CBL.PLANE_COLS) * 8 if tall else 0)
        if z["key"] == start:
            continue                    # its tiles ARE the act default's (rg_bg_tiles 0)
        if co_resident or (start_shared and z["key"] in group_of.get(start, ())):
            continue                    # its tiles are in the act default's blob
        owner = min(group_of.get(z["key"], {z["key"]}))
        til = CLIP_BG_TILES_BIN.format(key=owner)
        blob = CBL.tiles_blob(tiles)
        with open(os.path.join(gen_dir, til), "wb") as fh:
            fh.write(blob)
        z.update(bg_tiles_label=f"OJZ_Clip_BG_Tiles_{owner}",
                 bg_tiles_embed=f"{GEN_REL}/{til}", bg_tiles_bytes=len(blob),
                 bg_tiles_owner=owner == z["key"], bg_tiles_file=til)
    from vram_map import BG_STATIC_TILE_BUDGET
    for owner, union in unions.items():
        if owner not in group_of.get(start, ()) and len(union) > BG_STATIC_TILE_BUDGET:
            # a region blob past the static budget uses the band reserve too: legal only
            # while the act has no BgAnim band (read back out of what the injector wrote)
            with open(os.path.join(gen_dir, "bg_anim.emp")) as fh:
                if "BgAnim_Table: u16 = 0" not in fh.read():
                    raise ClipRomError(
                        f"BG blob group of zone key {owner}: {len(union)} tiles pass the "
                        f"static budget {BG_STATIC_TILE_BUDGET} and the act default's "
                        f"bg_anim.emp is not the zero-band stub — refused")
    zones = {z["key"]: z for z in plan["zones"]}
    for r in plan["rows"]:
        r["bg_layout"] = zones[r["key"]].get("bg_layout_label")
        r["bg_tiles"] = zones[r["key"]].get("bg_tiles_label")
        r["bg_span"] = zones[r["key"]].get("bg_span") or 0
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
            # a TALL start zone's rows name its whole map (the act default is only the map's
            # first plane, for BG_Init) and the act default's tiles
            want = ((z["bg_layout_label"], z.get("bg_tiles_label") or "0")
                    if z.get("bg_layout_label") else ("0", "0"))
            want_span = str(z.get("bg_span") or 0)
            if (lay, til) != want or span != want_span:
                raise ClipRomError(
                    f"BG1 {what}: the row x {r['x0']}..{r['x1']} ({z['zone']}) names "
                    f"background ({lay}, span {span}, {til}); its zone's own is {want}, "
                    f"span {want_span}")
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
            fw, ft, _ = lower_zone(z["donor"], z["zone"], z.get("tall"))
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
            plane = CBL.PLANE_COLS * CBL.PLANE_ROWS
            files = (("zone_bg.bin", CBL.layout_blob(words[:plane])),
                     ("bg_tiles.bin", CBL.tiles_blob(tiles)))
            if z.get("bg_span"):            # a TALL start zone: its rows' whole map too
                files = files + ((CLIP_BG_LAYOUT_BIN.format(key=key), CBL.layout_blob(words)),)
        elif not z.get("bg_tiles_label"):          # co-resident: layout only
            files = ((CLIP_BG_LAYOUT_BIN.format(key=key), CBL.layout_blob(words)),)
            if os.path.exists(os.path.join(gen_dir, CLIP_BG_TILES_BIN.format(key=key))):
                raise ClipRomError(f"BG1 {z['zone']} is co-resident but a tile blob "
                                   f"{CLIP_BG_TILES_BIN.format(key=key)} was written for it")
        else:
            files = ((CLIP_BG_LAYOUT_BIN.format(key=key), CBL.layout_blob(words)),
                     (z.get("bg_tiles_file") or CLIP_BG_TILES_BIN.format(key=key),
                      CBL.tiles_blob(tiles)))
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
        if z.get("tall") and derive is CBS.derive:
            # a TALL zone: its chain of band layouts over the map plan_backgrounds lowered
            # (the transparent rows are read off those words), rows split at its switches
            ext = z["tall"]
            chain = CBS.derive_tall(z["donor"], z["zone"], dys[0], ext,
                                    plan["_bg_lowered"][z["key"]][0], ext["donor_cam_x_max"])
            z["scroll_chain"] = chain
            z["scroll"] = chain["specs"][0]
            z["parallax_label"] = tall_parallax_label(z["key"], 0)
            if log:
                log(f"clip_rom_bake: TALL BACKGROUND {z['zone']} — BG rows {chain['r0']}.."
                    f"{chain['r0'] + chain['span'] - 1} ({chain['span']} lines, rg_bg_span), "
                    f"screen tops {chain['v_lo']}..{chain['v_hi']}; "
                    f"{len(chain['specs'])} band layout(s) "
                    f"{[len(s['bands']) for s in chain['specs']]} switching at screen tops "
                    f"{chain['switch_rows']} (overlaps {chain['overlap']}), camera-centre Y "
                    f"{chain['cuts']}")
            continue
        spec = derive(z["donor"], z["zone"], dys[0])
        z["scroll"] = spec
        if spec is None:
            if log:
                log(f"clip_rom_bake: SCROLL WARNING — no Sonic 2 scroll transcription for "
                    f"{z['donor']}:{z['zone']}; it scrolls with the act default (TAGGED)")
            continue
        z["parallax_label"] = CBS.PARALLAX_LABEL.format(key=z["key"])
    split_tall_rows(plan)
    if log:
        log("clip_rom_bake: scroll — " + "; ".join(
            f"{z['zone']} {len(z['scroll']['bands'])} band(s) from {z['scroll']['routine']} "
            f"(v_factor {z['scroll']['v_factor']}, v_center {z['scroll']['v_center']})"
            if z.get("scroll") else f"{z['zone']} act default" for z in plan["zones"]))


def split_tall_rows(plan):
    """Split each row of a zone with a CHAIN of band layouts at the chain's camera-centre cuts
    (clip_bg_scroll.derive_tall), so each piece names its layout in rg_parallax. A cut at Y
    makes rows [.., Y-1] and [Y, ..]: Parallax_CheckBoundary installs the row holding the
    camera centre, and the centre at Y is the first whose screen top is the switch row, where
    both neighbouring layouts are exact. Every piece keeps REGION_MIN_SPAN (the descriptor
    refuses less); a cut that would leave less is REFUSED by name rather than moved, because
    moving it off the overlap would put a layout on screen tops it is not exact for. The cut
    is inside a row the guillotine already placed inside the camera centre's band, so the
    band rule holds for the new edge too."""
    min_span = _region_bounds()[0]
    zones = {z["key"]: z for z in plan["zones"]}
    out = []
    for r in plan["rows"]:
        chain = zones[r["key"]].get("scroll_chain")
        if not chain or len(chain["specs"]) == 1:
            out.append(r)
            continue
        cuts = chain["cuts"]
        edges = [r["y0"]] + [c for c in cuts if r["y0"] < c <= r["y1"]] + [r["y1"] + 1]
        for a, b in zip(edges, edges[1:]):
            if b - a < min_span:
                raise ClipRomError(
                    f"TALL {zones[r['key']]['zone']}: splitting the row x {r['x0']}..{r['x1']}, "
                    f"y {r['y0']}..{r['y1']} at the band-layout switches {cuts} leaves y "
                    f"{a}..{b - 1}, under REGION_MIN_SPAN {min_span}")
            i = sum(1 for c in cuts if c <= a)
            piece = dict(r, y0=a, y1=b - 1,
                         parallax=tall_parallax_label(r["key"], i),
                         why=f"{r['why']} [tall band layout {i} of {len(cuts) + 1}]")
            out.append(piece)
    plan["rows"] = out


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
        want = CBS.data_block_text(scrolled, plan["act_span"], _scroll_transition(plan))
        if want not in data_text:
            raise ClipRomError("SC1 the data block's scroll text is not a fresh derivation's — "
                               "something rewrote it after the bake emitted it")
    return {z["zone"]: (len(z["scroll"]["bands"]) if z.get("scroll") else None)
            for z in plan["zones"]}


def emit_clip_module(act, donor_root, path=CLIP_MODULE, data_path=CLIP_DATA, log=None,
                     gen_dir=GEN_DIR, baked_dir=None):
    """Write the clip act's module + append its data, then run Z2, MUSIC, the SCREEN check
    and BG1 over what was WRITTEN."""
    import clip_camera
    frames = crossing_frames(act)
    model = clip_camera.CameraModel.for_act(act, donor_root)
    plan = region_plan(act, donor_root, frames=frames, model=model)
    desc = os.path.join(REPO, "games", "sonic4", "data", "levels", "ojz", "act1",
                        "act_descriptor.emp")
    plan["start"] = act_start(act)
    spawn = engine_spawn(desc, start=plan["start"])
    if log:
        st = plan["start"]
        log(f"clip_rom_bake: START — "
            + ("the descriptor's shipped start" if not st else
               f"clip {st['clip']!r}'s donor start ({st['donor_start'][0]}, "
               f"{st['donor_start'][1]}) at world ({st['x']}, {st['y']})" if st.get("clip") else
               f"the act's own point ({st['x']}, {st['y']}): {st['why']}")
            + f"; the boot state puts the player at {spawn}")
    plan_backgrounds(plan, spawn, gen_dir, baked_dir or gen_dir, log=log)
    plan_scroll(plan, act, log=log)
    plan["layer_lines"] = layer_line_plan(act, log=log)
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
            f"zone_separation = {ov['zone_separation'].upper()}, "
            f"parallax = {ov['parallax'].upper()}, crossing_margin = {ov['crossing_margin'].upper()}. "
            f"This act is NOT held to the default crossing rule (16-frame fade, tile "
            f"overwrite); Z2 below holds it to the re-derived one. Why: {ov['why']}")
        log("clip_rom_bake: " + "!" * 72)
    bgf = background_switch_frames(plan)
    # the frames the plan was CUT with (crossing_frames, from the blob groups and the lowered
    # tiles) must be the frames the EMITTED blobs take (background_switch_frames reads the
    # plan's blobs back): a difference means the rows were placed for a background that is
    # not the one the ROM carries
    for z, fr in bgf.items():
        into = [frames["pair"][p_] for p_ in frames["pair"] if p_[1] == z]
        if not into:
            continue                    # a one-zone act: nothing crosses into it
        planned = max(into)
        if max(fr, frames["palette"]) != planned:
            raise ClipRomError(
                f"Z2 zone key {z}: the region plan was cut for {planned} frame(s) into it and "
                f"the emitted background takes {max(fr, frames['palette'])} — the plan and "
                f"the blobs disagree")
    z2 = check_palette_crossings(act, mod, data, log=log, frames=frames, cam=model.c)
    plan["music"] = check_music_crossings(act, mod, data, spawn=spawn, log=log)
    plan["screen"] = check_screen(act, model, mod, data, frames, log=log)
    plan["st1"] = check_start(plan, mod)
    plan["bg1"] = check_backgrounds(plan, mod, data, gen_dir)
    if log:
        log(f"clip_rom_bake: BG1 {plan['bg1']['default']} is the act default background and "
            f"{', '.join(plan['bg1']['regions']) or 'no zone'} carr(ies) its own on its "
            f"region rows — rows and blobs read back from what was emitted")
    plan["sc1"] = check_scroll(plan, data)
    plan["ll1"] = check_layer_lines(plan, mod, data)
    if log:
        log(f"clip_rom_bake: LL1 {plan['ll1']} layer-line row(s) in the clip module and the data "
            f"block, read back from what was emitted and equal to the plan")
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
                # NO INHERITED ENTITIES (the woven report's §C item 8). Pass 8
                # (ojz_entity_gen) reads this key: "none" emits every section's object,
                # type and ring tables empty at THIS grid, instead of the shipped act's
                # OJZ objects and rings at OJZ's world positions over Sonic 2 geometry —
                # which also forced every clip grid to >= 9 sections, whole rows of 3.
                ojz_entity_gen.ENTITIES_KEY: "none",
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
        result = _bake(manifest_path, donor_root=donor_root, gen_dir=gen_dir,
                       coll_dir=coll_dir,
                       skip_clean_check=skip_clean_check, keep=keep, log=log)
    except BaseException:
        # The bake already failed: restore, but let ITS exception be the one that
        # propagates (restore_tree logs its own failure).
        if not keep:
            restore_tree(log=log)
        raise
    if not keep and not restore_tree(log=log):
        raise ClipRomError(
            "the bake succeeded but the committed level tree could NOT be restored (see "
            "the ERROR above); the clip bake is still in "
            + ", ".join(RESTORE_PATHS) + ". Restore it by hand before building or committing.")
    return result


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
    import clip_camera
    z1 = check_zone_separation(act, summary,
                               model=clip_camera.CameraModel.for_act(act, donor_root))
    if z1:
        log(f"clip_rom_bake: PER-CLIP OVERRIDE crossing_overrides.zone_separation = screen — "
            f"Z1 counted on the SCREEN ({z1['need_cells']} cells), not the tile cache: gap "
            f"{z1['gap_cells']} cells; {z1['tile_cache_windows_mixed']} tile-cache window(s) "
            f"hold both zones (their margin columns are never displayed)"
            + (f"; BOTH AXES: 0 of {z1['reachable_centres']} reachable camera centres show two "
               f"zones ({z1['mixed_unreachable']} unreachable ones would, REPORTED)"
               if z1.get("axes") == "both" else ""))

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
        "regions": [dict({k: r[k] for k in ("x0", "x1", "y0", "y1", "preset_label", "why")},
                         song=r.get("song"))
                    for r in region_plan_["rows"]],
        "music": region_plan_.get("music"),
        "palette_crossings": z2,
        "screen": region_plan_.get("screen"),
        "backgrounds": {
            "act_default": region_plan_["bg1"]["default"],
            "regions": region_plan_["bg1"]["regions"],
            "backdrop_reg": region_plan_["bg1"]["backdrop_reg"],
            "per_zone": {z["zone"]: z["bg"] for z in region_plan_["zones"]},
        },
        "layer_lines": {"lines": len(region_plan_["layer_lines"]["lines"]),
                        "rows": len(region_plan_["layer_lines"]["rows"]),
                        "per_zone": {z: sum(1 for ln in region_plan_["layer_lines"]["lines"]
                                            if ln["zone"] == z)
                                     for z in sorted({ln["zone"] for ln in
                                                      region_plan_["layer_lines"]["lines"]})}},
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
            "the shipped region table is still ASSEMBLED (unused: act_regions points at "
            "the clip act's own table)",
        ],
    }
    if act.shafts:
        report["shafts"] = [sh.as_json() for sh in act.shafts]  # only when there are any
    if act.fill is not None:
        report["fill"] = act.fill.as_json()      # only when there is one (byte identity)
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
    spawn_x, spawn_y = engine_spawn(desc, start=act_start(act))
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


def engine_spawn(descriptor_path, constants_path=None, grid_path=None, start=None):
    """(x, y) world px the boot state puts Player_1 at, DERIVED from the engine.

    Camera_Init seeds Camera_X = (start_sec_x << SECTION_SIZE_SHIFT) + start_local_x
    - CAM_SCREEN_HALF_W, clamped to [0, Camera_X_Max]; the boot state then places
    Player_1 at Camera_X + CAM_SCREEN_HALF_W. The half-screen therefore cancels
    EXCEPT where the clamp bites, which is precisely why this is computed rather than
    assumed to be the descriptor's start_local.

    The descriptor spells each start field as `ojz_clip_act_<field>(hand: <literal>)` (the
    clip start chooser, woven item 7); the literal is the shipped act's. `start` (an
    `act_start` dict) is a clip act's own start, which the chooser returns in its build.
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

    own = start_fields(start, constants_path) if start else None

    def field(name):
        if own is not None and name in own:
            return own[name]
        m = re.search(rf"^\s*{name}:\s*(?:ojz_clip_act_{name}\(hand:\s*)?(\$?[0-9A-Fa-f]+|GRID_[WH])",
                      text, re.M)
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
