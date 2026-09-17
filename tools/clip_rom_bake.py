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
# Refusals
# ---------------------------------------------------------------------------

def check_single_clip(act):
    """R20 — exactly one clip.

    See the module header: the ROM bake reads ONE tileset, so a second clip's tile
    indices would be resolved against the first clip's art. The failure is silent and
    looks like a rendering bug, which is why this is a refusal and not a warning.
    """
    if len(act.clips) != 1:
        raise ClipRomError(
            f"R20 this act has {len(act.clips)} clips and the ROM bake takes exactly "
            f"one. An editor nametable word's tile index is 11 bits into ONE act-wide "
            f"tileset (project.json zones[0].tileset), which ojz_strip_gen.generate() "
            f"reads and hands place_pool as a uniform zone grid. A one-clip act has one "
            f"donor zone and is an ordinary aeon act; a two-clip act needs the per-cell "
            f"tileset key on the ROM path, which is staged plan row 7. "
            f"Clips here: {', '.join(c.id for c in act.clips)}.")


def check_act_grid_matches_engine(act, descriptor=None):
    """R21 — the manifest's act grid is the grid the ENGINE's act descriptor declares.

    The throwaway re-bakes the shipped act SLOT, and that slot's section table, its
    map.toml placement rows and its `const GRID_W`/`GRID_H` are all fixed by the
    hand-written `act_descriptor.emp`. A clip act declaring a different grid would bake
    a local-map table shorter (or longer) than the grid the engine indexes by flat id —
    the 2026-09-12 F2 incident, one act over.

    Read from the engine, never typed: `act_grid.descriptor_grid` parses
    `const GRID_W = <int>` out of the descriptor.
    """
    kw = {} if descriptor is None else {"descriptor": descriptor}
    gw, gh = act_grid.descriptor_grid(**kw)
    if (act.grid_w, act.grid_h) != (gw, gh):
        raise ClipRomError(
            f"R21 the manifest declares a {act.grid_w}x{act.grid_h} act grid and the "
            f"engine's act descriptor declares {gw}x{gh}. A clip act is baked into the "
            f"SHIPPED act's slot (see this file's header), whose section table, map.toml "
            f"placement rows and GRID_W/GRID_H are fixed by the descriptor. Declare "
            f'"act": {{"grid_w": {gw}, "grid_h": {gh}}} — sections your clip does not '
            f"cover are baked as air, which is what an empty section is.")


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
    if out.strip():
        raise ClipRomError(
            "R22 the paths this bake overwrites are not clean:\n  "
            + "\n  ".join(out.rstrip().splitlines())
            + "\nCommit or stash them first — this is a THROWAWAY bake whose restore "
              "is `git checkout`, and it would discard them.")


# ---------------------------------------------------------------------------
# The staged project
# ---------------------------------------------------------------------------

def stage_project(act, baked_dir, donor_root, gen_dir=GEN_DIR):
    """Write the `project.json` that points the shipped generators at the clip tree.

    Paths inside it are relative TO IT, which is the rule `validate_editor_inputs`
    already used and the one `generate()` was taught on 2026-09-17 (it resolved
    `dataPath` against the repo root, which is the same thing only for a project file
    that sits at the repo root).

    `dataPath` is "." — `clip_act_bake` already wrote the act directory, so the tree is
    the act. `bgLayout`/`bgTiles` are carried over from the shipped project verbatim and
    are inert: Pass 6b builds Plane B from the sonic_hack donor and reads neither.
    """
    clip = act.clips[0]
    zone_tree = os.path.join(donor_root, clip.donor, clip.zone)
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
            "real one. dataPath, tileset and palette are relative to THIS file."),
        "zones": [{
            "id": sz["id"], "name": f"{clip.donor}:{clip.zone}",
            "tileset": rel(os.path.join(zone_tree, "tileset.bin")),
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

def bake(manifest_path, donor_root=None, gen_dir=GEN_DIR, coll_dir=COLL_DIR,
         skip_clean_check=False, log=print):
    donor_root = clip_manifest._root(donor_root)
    act = clip_manifest.load(manifest_path, donor_root=donor_root)
    check_single_clip(act)
    check_act_grid_matches_engine(act)
    if not skip_clean_check:
        check_tree_is_clean([os.path.relpath(gen_dir, REPO),
                             os.path.relpath(coll_dir, REPO)])

    baked_dir = os.path.join(os.path.dirname(os.path.abspath(manifest_path)), "baked")
    log(f"clip_rom_bake: composing {act.id} -> {os.path.relpath(baked_dir, REPO)}")
    _act, _st, summary, _v1, _v2 = clip_act_bake.bake(
        manifest_path, out_dir=baked_dir, donor_root=donor_root, log=log)

    project_path, zone_tree = stage_project(act, baked_dir, donor_root, gen_dir)
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
        authored_palette=os.path.join(zone_tree, "palette.bin"),
    )
    log("clip_rom_bake: strips, local maps, art pool, palette, collision tables...")
    ojz_strip_gen.generate()

    page_bytes = _art_pool_page_bytes()
    elect_pool_pages.elect(
        gen_dir, page_bytes, os.path.join(REPO, "tools", "bin", "salvador"),
        module="games.sonic4.ojz_act_pool_act1", section="ojz_act_pool",
        symbol_prefix="OJZ_Act_Pool_Page", table_symbol="OJZ_Act_Pool_PageTable",
        emp_name="ojz_act_pool.emp", embed_prefix=GEN_REL, log=log)

    # THE BLOCK STREAM — row 6's inheritance. ojz_block_gen reads sec{N}_strips_a.bin
    # out of its own OUTPUT_DIR and the section count out of act_grid, which reads the
    # SHIPPED project.json. Both are the shipped act's here by construction (this bakes
    # into its slot at its grid, R21), so neither is redirected.
    log("clip_rom_bake: block stream (S4LZ v3, per-section dictionaries)...")
    import ojz_block_gen
    ojz_block_gen.OUTPUT_DIR = gen_dir
    ojz_block_gen.generate_all()

    report = {
        "schema": 1,
        "produced_by": "tools/clip_rom_bake.py",
        "act": act.id,
        "clip": {"id": act.clips[0].id, "donor": act.clips[0].donor,
                 "zone": act.clips[0].zone,
                 "src_rect": list(act.clips[0].src), "dst_rect": list(act.clips[0].dst)},
        "grid": [act.grid_w, act.grid_h],
        "pool": summary["pool"],
        "collision": {k: summary["collision"][k]
                      for k in ("attr_entries", "cap", "base_bank")},
        "verdict_at_placement": summary["verdict_at_placement"],
        "generated_dir": GEN_REL,
        "inherited_from_the_shipped_act": [
            "background (Plane B is built from the sonic_hack donor by Pass 6b)",
            "objects and rings (Pass 8 reads the shipped act's editor entities)",
            "the region table and the effects presets (hand-written act_descriptor.emp)",
        ],
    }
    with open(os.path.join(baked_dir, "clip_rom_bake.json"), "w") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")
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
    desc = os.path.join(REPO, "games", "sonic4", "data", "levels", "ojz", "act1",
                        "act_descriptor.emp")
    spawn_x, spawn_y = engine_spawn(desc)
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


def engine_spawn(descriptor_path, constants_path=None):
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

    gw, gh = act_grid.descriptor_grid(descriptor_path)
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
    a = ap.parse_args(rest)
    bake(a.manifest, donor_root=a.donor_root, skip_clean_check=a.allow_dirty)
    return 0


def _mode_ground(rest):
    ap = argparse.ArgumentParser(prog="clip_rom_bake.py ground")
    ap.add_argument("manifest")
    ap.add_argument("--donor-root", default=None)
    a = ap.parse_args(rest)
    ground(a.manifest, donor_root=a.donor_root)
    return 0


MODES = {"bake": _mode_bake, "ground": _mode_ground}


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    handler = MODES.get(args[0] if args else None)
    if handler is None:
        print(f"usage: clip_rom_bake.py {{{'|'.join(MODES)}}} <clips.json> [options]",
              file=sys.stderr)
        raise SystemExit(1)
    try:
        raise SystemExit(handler(args[1:]))
    except (ClipRomError, clip_manifest.ClipManifestError,
            clip_act_bake.ClipBakeError, clip_act_bake.ClipCollisionError) as exc:
        print(f"clip_rom_bake: REFUSED — {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
