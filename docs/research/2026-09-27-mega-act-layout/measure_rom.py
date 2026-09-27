#!/usr/bin/env python3
"""The level-data ROM bytes a clip manifest would add, measured through the REAL generators.

A MEASUREMENT, not a bake and not a ROM. `tools/clip_rom_bake.py bake` cannot run on the
mega-act draft: its `region_plan` refuses stacked clips (and its layer-line plan refuses the
prototype donor). But the region, palette, music and background passes it would refuse at
come AFTER the two things that decide most of the ROM cost, and neither of those cares about
the layout's shape. So this runs exactly the bake's own calls, in its own order, into
SCRATCH directories, and stops before the region pass:

    clip_act_bake.bake  -> clip_rom_bake.stage_project -> act_grid.emit ->
    ojz_strip_gen.configure/generate  (strips, local maps, pool, collision tables)
    -> elect_pool_pages.elect  (the ZX0/raw page election, the art pool's ROM form)
    -> ojz_block_gen.generate_all  (THE BLOCK STREAM, S4LZ v3, per-section dictionaries)

and then sums the bytes the generated `.emp` modules would embed. `act_grid.emit` writes the
repo's generated `act_grid.emp`; its bytes are saved first and written back on the way out,
win or lose, and the caller is told if that failed.

WHAT IT DOES NOT COUNT: region rows, palettes, presets, parallax scenes, background layouts
and tiles, layer lines, music. Those are small next to the block stream (the two-zone act's
whole CLIP ACT DATA block is a few KB, see its report), but they are not zero, and a
linked ROM is the only thing that says where the anchors land.

    python3 measure_rom.py <clips.json> --scratch DIR
"""
import argparse
import hashlib
import json
import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--salvador", default=str(REPO / "tools" / "bin" / "salvador"),
                    help="the ZX0 packer build.sh builds into tools/bin (absent in a fresh worktree)")
    a = ap.parse_args()

    import act_grid
    import clip_act_bake
    import clip_manifest
    import clip_rom_bake
    import elect_pool_pages

    import ojz_common
    scratch = pathlib.Path(a.scratch).resolve()
    # ojz_strip_gen derives the AUTHORED palette from the generated dir's shape
    # (ojz_common.authored_palette_for: .../data/generated/<zone>/<act> -> .../editor/...),
    # so the scratch generated dir must have that shape and the scratch editor dir a copy of
    # the committed authored palette. Nothing is written under the repo's own trees.
    gen = scratch / "games/sonic4/data/generated/ojz/act1"
    baked, coll = scratch / "baked", scratch / "coll"
    for d in (baked, gen, coll):
        d.mkdir(parents=True, exist_ok=True)
    authored = pathlib.Path(ojz_common.authored_palette_for(str(gen)))
    authored.parent.mkdir(parents=True, exist_ok=True)
    authored.write_bytes(pathlib.Path(ojz_common.authored_palette_for(
        str(REPO / "games/sonic4/data/generated/ojz/act1"))).read_bytes())
    saved = pathlib.Path(act_grid.ACT_GRID_EMP).read_bytes()
    try:
        donor_root = clip_manifest._root(None)
        act = clip_manifest.load(a.manifest, donor_root=donor_root)
        _act, _st, summary, _v1, _v2 = clip_act_bake.bake(
            a.manifest, out_dir=str(baked), donor_root=donor_root, log=lambda m: None)
        sheets = [os.path.join(REPO, z["tileset_file"]) for z in summary["zone_table"]]
        project, _zt = clip_rom_bake.stage_project(act, str(baked), donor_root, str(gen),
                                                   sheet_files=sheets)
        act_grid.emit(act.grid_w, act.grid_h)
        import ojz_strip_gen
        ojz_strip_gen.configure(project_json=project, output_dir=str(gen),
                                collision_dir=str(coll),
                                bank_dir=clip_manifest.collision_banks(act, donor_root))
        ojz_strip_gen.generate()
        elect_pool_pages.elect(
            str(gen), clip_rom_bake._art_pool_page_bytes(),
            a.salvador,
            module="games.sonic4.ojz_act_pool_act1", section="ojz_act_pool",
            symbol_prefix="OJZ_Act_Pool_Page", table_symbol="OJZ_Act_Pool_PageTable",
            emp_name="ojz_act_pool.emp", embed_prefix=str(gen), log=lambda m: None)
        import multiprocessing
        import ojz_block_gen
        # ojz_block_gen fans sections out over a multiprocessing.Pool and its workers read the
        # module-level OUTPUT_DIR. The real bake never notices because it points OUTPUT_DIR at
        # the default path; a scratch redirect only reaches the workers if they are FORKED
        # (Python 3.14's Linux default start method is forkserver, which re-imports the module).
        multiprocessing.set_start_method("fork", force=True)
        ojz_block_gen.OUTPUT_DIR = str(gen)
        ojz_block_gen.generate_all(project_json=project)
    finally:
        pathlib.Path(act_grid.ACT_GRID_EMP).write_bytes(saved)
        ok = pathlib.Path(act_grid.ACT_GRID_EMP).read_bytes() == saved
        print(f"act_grid.emp restored: {'yes' if ok else 'NO - restore it by hand'}")

    def unique_bytes(pattern):
        seen, total, n = set(), 0, 0
        for p in sorted(gen.glob(pattern)):
            b = p.read_bytes()
            n += 1
            h = hashlib.sha256(b).hexdigest()
            if h not in seen:
                seen.add(h)
                total += len(b)
        return n, len(seen), total

    import re
    rows = {}
    for label, pat in (("block stream (sec*_blocks.bin)", "sec*_blocks.bin"),
                       ("local maps (sec*_local_map.bin)", "sec*_local_map.bin")):
        rows[label] = unique_bytes(pat)
    # The art pool's ROM form is whichever file ojz_act_pool.emp embeds per page (the
    # election picks ZX0 or raw per page), so read the names back out of the emitted module.
    elected = sorted(set(re.findall(r"act_pool_page\d+\.(?:zx0|bin)",
                                    (gen / "ojz_act_pool.emp").read_text())))
    rows["art pool, elected page files"] = (len(elected), len(elected),
                                            sum((gen / f).stat().st_size for f in elected))
    total = sum(v[2] for v in rows.values())
    for k, v in rows.items():
        print(f"{k:36s} {v[0]:3d} files, {v[1]:3d} unique, {v[2]:8d} B")
    print(f"{'TOTAL level data measured':36s} {total:8d} B  (grid {act.grid_w}x{act.grid_h}, "
          f"pool {summary['pool']['tiles']} tiles)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
