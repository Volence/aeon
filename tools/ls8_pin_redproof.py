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
skipped lanes are the ones that matter for a GREEN claim, never for this. The exception is
a mutation listed in CANONICAL, whose guard lives in build.sh's pre-build pytest lane, which
FAST skips: those run a canonical `DEBUG=1 ./build.sh`.

EXTENDED 2026-09-11 (parcel/lens-pins-0911) with the four lens-sweep pins that parcel
landed, P1..P12 below: B2b-5 (collected/killed mask width), C2a-5 (DMA queue RAM spans),
B2b-4 (the YM floor mirrors, a pytest, hence CANONICAL) and B1-2 / LS-8a (the plane-wrap
family per axis, plus the reg $10 byte). Same method, same rules; each fired guard's first
log line is now printed, because a count says a message appeared and not what it said.
"""
import os, subprocess, sys, shutil, json

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
 # ---- 2026-09-11 lens-pins parcel ----
 "P1  entity_win  mask width vs list size":     "the ring-collected and object-killed bitmasks are COLLECTED_MASK_BYTES",
 "P2  entity_win  16-byte unrolled sites":      "are hand-unrolled for 4 * 4 = 16-byte masks",
 "P3  dma_queue   Critical span":               "DMA_Critical is no longer the first thing at DMA_Queue",
 "P4  dma_queue   Important span":              "DMA_Important no longer starts at DMA_Critical_End",
 "P5  dma_queue   Deferrable span":             "DMA_Deferrable no longer starts at DMA_Important_End",
 "P6  dma_queue   whole queue":                 "DMA_Queue .. DMA_Queue_End in engine/ram.emp is no longer",
 "P7  pytest      YM mirror value":             "out of step with its authority",
 "P8  pytest      YM mirror not a literal":     "not an integer literal. In a seam-1 resident module",
 "P9  section     plane H family":              "but engine/level/section.emp hand-spells a 64-column plane",
 "P10 section     plane V family":              "but engine/level/section.emp hand-spells a 64-row plane",
 "P11 plane_buf   plane H family":              "but engine/level/plane_buffer.emp hand-spells a 64-column plane",
 "P12 plane_buf   plane V family":              "but engine/level/plane_buffer.emp hand-spells a 64-row plane",
 "P13 boot_data   reg $10 byte":                "BootData_VDPRegs writes reg $10 = VDP_REG_PLANE_SIZE",
}

# Mutations whose guard is a pytest in build.sh's pre-build lane: FAST skips that lane,
# so these build canonically (DEBUG=1, no FAST).
CANONICAL = {"M15_ym_authority_raised", "M16_ym_mirror_low", "M17_ym_mirror_extern"}

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
 # ---- 2026-09-11 lens-pins parcel ----
 # M9 is B2b-5's OWN scenario: lower the killed offset, and the ring mask is 8 bytes for a
 # 128-entry list. Expect P1 and P2.
 "M9_killed_offset_lowered": [
   ("engine/system/constants.emp", "pub const KILLED_BITMASK_OFFSET   = 18", "pub const KILLED_BITMASK_OFFSET   = 10"),
 ],
 # M10: raise the list size alone. Expect P1 (and the loaded-mask twin, which is not in GUARDS).
 "M10_max_list_entries_raised": [
   ("engine/system/constants.emp", "pub const MAX_LIST_ENTRIES        = 128", "pub const MAX_LIST_ENTRIES        = 256"),
 ],
 # M11 does exactly what P1's message instructs (move KILLED_BITMASK_OFFSET with the list).
 # P1 must go quiet and P2 must stay RED: the unrolled sites are the rest of the edit.
 "M11_list_raised_plus_p1_fix": [
   ("engine/system/constants.emp", "pub const MAX_LIST_ENTRIES        = 128", "pub const MAX_LIST_ENTRIES        = 256"),
   ("engine/system/constants.emp", "pub const KILLED_BITMASK_OFFSET   = 18", "pub const KILLED_BITMASK_OFFSET   = 34"),
 ],
 # M12-M14: C2a-5's own scenario, a field inserted into the queue run at three places.
 "M12_field_inside_critical": [
   ("engine/ram.emp", "    DMA_Critical:           [u8; DMA_CRITICAL_SLOTS * sizeof(DMAEntry)],\n    mark DMA_Critical_End,",
                      "    DMA_Critical:           [u8; DMA_CRITICAL_SLOTS * sizeof(DMAEntry)],\n    pad(2),\n    mark DMA_Critical_End,"),
 ],
 "M13_field_between_important_and_deferrable": [
   ("engine/ram.emp", "    mark DMA_Important_End,\n    DMA_Deferrable:",
                      "    mark DMA_Important_End,\n    pad(2),\n    DMA_Deferrable:"),
 ],
 "M14_field_before_queue_end": [
   ("engine/ram.emp", "    mark DMA_Deferrable_End,\n    mark DMA_Queue_End,",
                      "    mark DMA_Deferrable_End,\n    pad(2),\n    mark DMA_Queue_End,"),
 ],
 # M15-M17: B2b-4. Raise the authority (the mirrors are now LOW), lower one mirror, and
 # the tempting extern() respelling that sigil itself builds green (probe T2/T3a).
 "M15_ym_authority_raised": [
   ("engine/sound/sound_fm.emp", "pub const YM_ADDR_TO_DATA_MIN_T = 8 ", "pub const YM_ADDR_TO_DATA_MIN_T = 12 "),
 ],
 "M16_ym_mirror_low": [
   ("engine/sound/z80_sound_driver.emp", "const YM_ADDR_TO_DATA_MIN_T = 8\n", "const YM_ADDR_TO_DATA_MIN_T = 4\n"),
 ],
 "M17_ym_mirror_extern": [
   ("engine/sound/sound_sequencer.emp", "const YM_ADDR_TO_DATA_MIN_T = 8\n", "const YM_ADDR_TO_DATA_MIN_T = extern(\"YM_ADDR_TO_DATA_MIN_T\")\n"),
 ],
 # M18-M20: B1-2 / LS-8a. Each axis alone must fire only its own axis's pins (plus reg $10);
 # M20 moves the register byte alone.
 "M18_plane_h_cells": [
   ("engine/system/constants.emp", "pub const PLANE_H_CELLS     = 64", "pub const PLANE_H_CELLS     = 128"),
 ],
 "M19_plane_v_cells": [
   ("engine/system/constants.emp", "pub const PLANE_V_CELLS    = 64", "pub const PLANE_V_CELLS    = 32"),
 ],
 "M20_reg10_byte_alone": [
   ("engine/system/boot_data.emp", "const VDP_REG_PLANE_SIZE = $11", "const VDP_REG_PLANE_SIZE = $01"),
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
    run_env = dict(env)
    if name in CANONICAL:
        run_env.pop("FAST", None)
    print(f"--- building: {'CANONICAL DEBUG=1 ./build.sh' if name in CANONICAL else 'FAST=1 DEBUG=1 ./build.sh'} ---", flush=True)
    with open(log, "w") as fh:
        rc = subprocess.run(["./build.sh"], stdout=fh, stderr=subprocess.STDOUT, env=run_env).returncode
    text = open(log, errors="replace").read()
    fired = {k: text.count(v) for k, v in GUARDS.items() if v in text}
    results[name] = {"exit": rc, "fired": fired, "log": log}
    print(f"--- build exit={rc}   guards fired: {len(fired)} ---", flush=True)
    for k in sorted(fired):
        print(f"    RED  {k}   (message seen {fired[k]}x)", flush=True)
        first = next(l for l in text.split("\n") if GUARDS[k] in l)
        print(f"         first line: {first.strip()[:420]}", flush=True)
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
    print(f"{n:36s} exit={r['exit']}  guards={len(r['fired'])}")
    allfired |= set(r["fired"])
partial = len(names) < len(MUTATIONS)
print(f"\nguards seen RED in THIS invocation: {len(allfired)}/{len(GUARDS)}"
      + ("   (PARTIAL RUN -- a guard not listed below simply had no mutation here that\n"
         "    could reach it. Only a run with NO mutation arguments covers all of them;\n"
         "    do not read an unlisted guard as dead.)" if partial else ""))
for k in sorted(GUARDS):
    print(("  RED      " if k in allfired else ("  not-hit  " if partial else "  NOT-RED  ")) + k)
if not partial and len(allfired) != len(GUARDS):
    sys.exit("FULL RUN LEFT A GUARD UNPROVEN -- that is a defect in the guard or in this harness, not a pass")
