#!/usr/bin/env python3
"""LS-8 red-first harness — the reproducible proof for the mask/stride/section-shift pins.

This is NOT a gate and build.sh does not run it. The RUNNER for every guard below is
`sigil build`, invoked by ./build.sh: the pins are comptime `ensure`s, so they are
evaluated on every build of every shape whose `use` closure reaches their module, and a
failure is build-fatal. What this script does is prove that claim by INVERSION, which is
the only thing that distinguishes a live guard from a decorative one (docs/EMP_PITFALLS.md
section 10).

For each mutation it: asserts the tree is COMMITTED-clean, clears every __pycache__ (the
repo's measured same-second false-green trap), applies exact-string edits, QUOTES THE
MUTATED LINES BACK OUT OF THE FILE (an unapplied mutation and a restored baseline both
print `ok` — reading the bytes back is what tells them apart), runs the real build, records
which guard MESSAGES appear, and restores with `git checkout --` of the exact paths.

C0 is the control: no edits, build green, zero guards fired.

M7 and M8 are the ones that matter. They replicate the 2026-09-06 lens-sweep controller
runs end to end — perturb the constant, then do EXACTLY what the original guard's message
instructed — and both of those were measured GREEN on aeon 61f22403 with the geometry still
half-moved. If either goes green again, the LS-8 pins have regressed.

    python3 tools/ls8_pin_redproof.py                # every mutation
    python3 tools/ls8_pin_redproof.py C0_control_unmutated M8_cols_plus_the_old_incomplete_fix

Needs SIGIL_BUILD / SIGIL_EMIT / AEON_SKDISASM_DIR in the environment (no dotfile sets
them). Uses FAST=1 DEBUG=1 deliberately: a RED proof only needs the sigil stage, and the
skipped lanes are the ones that matter for a GREEN claim, never for this.
"""
import os, re, subprocess, sys, shutil, json

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SC = os.environ.get("LS8_OUT", os.path.join(REPO, ".ls8-redproof"))
os.makedirs(SC, exist_ok=True)
os.chdir(REPO)

GUARDS = {
 "G1  tile_cache  block-tile mask family":      "BLOCK-TILE GEOMETRY MOVED",
 "G2  tile_cache  blocks-per-section family":   "AND THIS MODULE STILL HAND-SPELLS THE 16-BLOCK LITERALS",
 "G3  tile_cache  world-tile->section shift":   "AND THIS MODULE HAND-SPELLS `lsr.w #8`",
 "G4  tile_cache  CopyBlockColumn x80 chains":  "TileCache_CopyBlockColumn's two hand-rolled",
 "G5  tile_cache  FillRow inline #80":          "TileCache_FillRow hand-spells",
 "G6  section     RedrawPlanes #160":           "Section_RedrawPlanes hand-spells",
 "G7  section     UpdateColumns lsl #8":        "Section_UpdateColumns hand-spells",
 "G8  plane_buf   Draw_TileColumn #160":        "Draw_TileColumn hand-spells",
 "G9  plane_buf   Draw_TileRow_FromCache #80":  "Draw_TileRow_FromCache hand-spells",
 "G10 page_cache  blocks-per-section family":   "AND PageCache_Prefetch_Strips STILL HAND-SPELLS",
 "G11 page_cache  world-tile->section shift":   "AND PageCache_Prefetch_Strips HAND-SPELLS `lsr.w #8`",
 "E1  collision   Collision_GetType #80":       "Collision_GetType hand-spells",
 "E2  tile_cache  mul_cache_stride #80":        "mul_cache_stride hand-spells",
 "E3  tile_cache  coll_src_row_base lsl #4":    "coll_src_row_base hand-spells",
 "E4  constants   BLOCK_TILE_SHIFT vs SIZE":    "divides by the wrong power of two. WHAT SATISFYING THIS PIN DOES NOT COVER, said here because it was measured",
 "E5  constants   BPS_SHIFT vs BPS_AXIS":       "the world-block to section decompose divides by the wrong power of two",
}

MUTATIONS = {
 "M1_block_tile_size": [
   ("engine/system/constants.emp", "pub const BLOCK_TILE_SIZE       = 16", "pub const BLOCK_TILE_SIZE       = 32"),
   ("engine/system/constants.emp", "pub const BLOCK_TILE_SHIFT      = 4", "pub const BLOCK_TILE_SHIFT      = 5"),
 ],
 "M2_blocks_per_section": [
   ("engine/system/constants.emp", "pub const BLOCKS_PER_SECTION_AXIS = 16", "pub const BLOCKS_PER_SECTION_AXIS = 8"),
   ("engine/system/constants.emp", "pub const BLOCKS_PER_SECTION_SHIFT = 4", "pub const BLOCKS_PER_SECTION_SHIFT = 3"),
 ],
 "M3_tile_cache_cols": [
   ("engine/system/constants.emp", "pub const TILE_CACHE_COLS    = 80", "pub const TILE_CACHE_COLS    = 84"),
 ],
 "M4_section_size_shift": [
   ("engine/system/constants.emp", "pub const SECTION_SIZE_SHIFT = 11", "pub const SECTION_SIZE_SHIFT = 12"),
 ],
 "M5_block_tile_shift_only": [
   ("engine/system/constants.emp", "pub const BLOCK_TILE_SHIFT      = 4", "pub const BLOCK_TILE_SHIFT      = 5"),
 ],
 "M6_bps_shift_only": [
   ("engine/system/constants.emp", "pub const BLOCKS_PER_SECTION_SHIFT = 4", "pub const BLOCKS_PER_SECTION_SHIFT = 3"),
 ],
 "C0_control_unmutated": [],
 # M7/M8 replicate the 2026-09-06 controller runs END TO END: perturb the constant AND
 # then do exactly what the ORIGINAL guard's message instructed. Both were measured GREEN
 # on 61f22403. If either is green now, this parcel did not close the row.
 "M7_bts_plus_the_old_incomplete_fix": [
   ("engine/system/constants.emp", "pub const BLOCK_TILE_SIZE       = 16", "pub const BLOCK_TILE_SIZE       = 32"),
   ("engine/system/constants.emp", "pub const BLOCK_TILE_SHIFT      = 4", "pub const BLOCK_TILE_SHIFT      = 5"),
   ("engine/level/tile_cache.emp", "ensure(BLOCK_COLL_COLS == 16 && (1 << 4) == BLOCK_COLL_COLS,", "ensure(BLOCK_COLL_COLS == 32 && (1 << 5) == BLOCK_COLL_COLS,"),
   ("engine/level/tile_cache.emp", "        lsl.w   #4, {reg}                        // * BLOCK_COLL_COLS (16 bytes per row)", "        lsl.w   #5, {reg}                        // * BLOCK_COLL_COLS (16 bytes per row)"),
 ],
 "M8_cols_plus_the_old_incomplete_fix": [
   ("engine/system/constants.emp", "pub const TILE_CACHE_COLS    = 80", "pub const TILE_CACHE_COLS    = 84"),
   ("engine/level/tile_cache.emp", "comptime fn mul_cache_stride(dst: Reg, scratch: Reg) -> Code {\n    ensure(TILE_CACHE_STRIDE == 80", "comptime fn mul_cache_stride(dst: Reg, scratch: Reg) -> Code {\n    ensure(TILE_CACHE_STRIDE == 84"),
   ("engine/level/tile_cache.emp", "        mul_const.w {dst}, #80, {scratch}", "        mul_const.w {dst}, #84, {scratch}"),
   ("engine/level/collision_lookup.emp", "        ensure(TILE_CACHE_STRIDE == 80 && TILE_CACHE_STRIDE == TILE_CACHE_COLS,", "        ensure(TILE_CACHE_STRIDE == 84 && TILE_CACHE_STRIDE == TILE_CACHE_COLS,"),
   ("engine/level/collision_lookup.emp", "        mul_const.w d1, #80, d2", "        mul_const.w d1, #84, d2"),
 ],
}

def sh(cmd, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)

def clean_check():
    r = sh("git status --porcelain")
    assert r.stdout.strip() == "", "TREE DIRTY before mutation:\n" + r.stdout

def clear_pycache():
    n = 0
    for root, dirs, files in os.walk(REPO):
        if ".git" in root: continue
        if os.path.basename(root) == "__pycache__":
            shutil.rmtree(root, ignore_errors=True); n += 1
    return n

for _v in ("SIGIL_BUILD", "SIGIL_EMIT"):
    if not os.environ.get(_v):
        sys.exit(f"BLOCKED: {_v} is not set. No dotfile sets it; export it before running.")
env = dict(os.environ)
env.update({
 "FAST": "1", "DEBUG": "1",
 "PYTHONPYCACHEPREFIX": SC + "/pycache",
})

results = {}
names = sys.argv[1:] or list(MUTATIONS)
for name in names:
    edits = MUTATIONS[name]
    print(f"\n{'='*78}\n== {name}\n{'='*78}", flush=True)
    clean_check()
    npc = clear_pycache()
    print(f"[pycache] removed {npc} __pycache__ dirs; PYTHONPYCACHEPREFIX={env['PYTHONPYCACHEPREFIX']}", flush=True)

    touched = set()
    for path, old, new in edits:
        s = open(path).read()
        assert s.count(old) == 1, f"anchor count {s.count(old)} for {old!r} in {path}"
        open(path, "w").write(s.replace(old, new))
        touched.add(path)

    # PROOF THE MUTATION IS ON DISK: quote it back out of the file, and show the diff
    print("--- mutation as read back FROM DISK ---", flush=True)
    for path, old, new in edits:
        disk = open(path).read()
        assert new in disk and old not in disk, "MUTATION NOT ON DISK"
        for i, line in enumerate(disk.split("\n"), 1):
            if new.strip() and new in line:
                print(f"    {path}:{i}: {line}", flush=True)
    print(sh("git diff --stat").stdout.strip() or "    (no diff -- control run)", flush=True)

    log = f"{SC}/red_{name}.log"
    with open(log, "w") as fh:
        rc = subprocess.run(["./build.sh"], stdout=fh, stderr=subprocess.STDOUT, env=env).returncode
    text = open(log, errors="replace").read()
    fired = {k: text.count(v) for k, v in GUARDS.items() if v in text}
    results[name] = {"exit": rc, "fired": fired, "log": log}
    print(f"--- build exit={rc}   guards fired: {len(fired)} ---", flush=True)
    for k in sorted(fired):
        print(f"    RED  {k}   (message seen {fired[k]}x)", flush=True)
    if "<?>" in text:
        print("    !! '<?>' present in log -- an interpolation failed to resolve", flush=True)

    for path in touched:
        r = sh(f"git checkout -- {path}")
        assert r.returncode == 0, r.stderr
    clean_check()
    print("[restore] tree clean again (git checkout of the exact mutated paths)", flush=True)

json.dump(results, open(f"{SC}/redproof_results.json", "w"), indent=1)
print("\n\n===== SUMMARY =====")
allfired = set()
for n, r in results.items():
    print(f"{n:26s} exit={r['exit']}  guards={len(r['fired'])}")
    allfired |= set(r["fired"])
print(f"\nguards proven red: {len(allfired)}/{len(GUARDS)}")
for k in sorted(GUARDS):
    print(("  RED    " if k in allfired else "  NOT-RED ") + k)
