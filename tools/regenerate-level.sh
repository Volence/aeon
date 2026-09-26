#!/bin/bash
set -euo pipefail

# regenerate-level.sh — MANUAL re-bake of the OJZ generated level tree +
# collision tables. These outputs are COMMITTED artifacts the build consumes
# directly (see .gitignore, the level-gen parcel); the build never runs these
# generators, because they read TWO out-of-repo donor projects at paths that
# only exist on an authoring machine:
#
#   sonic_hack  (level layouts / Kosinski art / chunk+block maps) — override
#               with AEON_SONIC_HACK_DIR; default <suite>/sonic_hack, beside this
#               aeon checkout
#   skdisasm    (S&K collision shape vocabulary) — override with
#               AEON_SKDISASM_DIR; default ../skdisasm relative to this repo
#
# Run this by hand when the editor data or a donor project changes, then commit
# the regenerated tree (the level drift check — tools/verify_level_bin.py — and
# the whole-ROM byte gate confirm it). A missing donor / absent editor data is a
# HARD ERROR (ojz_strip_gen.generate() refuses the silent legacy-air fallback).
#
# USAGE (from the repo root):  tools/regenerate-level.sh [--no-cache]
#
# INCREMENTAL RE-BAKE (2026-08-19). The editor's edit-look-edit loop re-bakes
# after every save, and a REAL one-chunk edit used to cost 7-15 s against a
# 0.85-1.5 s no-change re-bake. MEASURED (16 cores, load ~30): the whole balloon
# was ojz_block_gen's per-section S4LZ K-sweep — 13.15 s of a 13.19 s section
# rebuild, 282 s4lz.compress calls at ~47 ms each. It was NOT the ZX0 pool
# packing (10 salvador spawns, 0.35 s total) and NOT the dedupe/spatial-order
# pass. ojz_block_gen now memoizes per (block, dictionary) as well as per
# section, so a one-chunk edit recompresses ~4 blocks instead of 282.
#
# --no-cache forces a full recompute through every cache tier (the trust escape
# hatch). The caches are PURE memoization keyed on a hash of the exact inputs
# INCLUDING the compressor source, so cached and --no-cache output are
# byte-identical by construction; see the key-completeness argument in
# tools/ojz_block_gen.py. Cache lives in tools/.cache/ (gitignored) — never in
# data/generated/, which is a committed artifact with an orphan check.

NO_CACHE=""
for arg in "$@"; do
    case "$arg" in
        --no-cache) NO_CACHE="--no-cache" ;;
    esac
done

cd "$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
TOOLS="${TOOLS:-tools}"

# Build the vendored salvador (ZX0 packer) once if missing (build.sh does the
# same; re-bakes may run standalone).
if [[ ! -x "${TOOLS}/bin/salvador" ]]; then
    echo "Building salvador (ZX0 packer)..."
    make -C "${TOOLS}/salvador" -s
    mkdir -p "${TOOLS}/bin"
    cp "${TOOLS}/salvador/salvador" "${TOOLS}/bin/salvador"
fi

# PREFLIGHT — validate EVERY precondition before the first destructive step.
#
# tools lens sweep D1 (CRITICAL): this script used to run import_sk_collision.py
# first, which unconditionally overwrites the ROM-consumed
# data/collision/{heightmaps,heightmaps_rot,angles,solidity}.bin with the base
# S&K bank — and only THEN reach ojz_strip_gen, which aborts on a missing donor
# or absent editor data. `set -euo pipefail` with no trap, so the script exited
# having already destroyed the pairing between those tables and the interned
# strip indices. The tree is normally in the interned state (data/collision/
# DIFFERS from collision/base/), so one invocation on a machine missing a donor
# left every solid surface resolving to the wrong height, angle and solidity —
# and nothing caught it: verify_level_bin.py does not look at collision at all.
#
# The preflight writes nothing. Keep it FIRST, and keep every new precondition
# in it rather than at the point of use, or this defect comes straight back.
#
# WHAT KEEPS THAT PROMISE TRUE (2026-09-12 gap lens sweep F5). It used to hold for
# donors only: generate()'s refusals of a malformed EDITOR file (a wrong-sized
# collattr/collattrb, a missing section file, a tile index past the tileset) all fired
# AFTER import_sk_collision.py had rewritten the tables. Two mechanisms now:
#   1. Every editor-input refusal is decided by ojz_strip_gen.validate_editor_inputs,
#      which the preflight runs, before the first write.
#   2. The refusals that depend on the BAKE rather than on one input file (R1/R2
#      crossover marks, attr-set overflow, the 11-bit local palette, the page-table
#      cap, BG capacity, and the drift gate at the end) cannot move up here without
#      running the bake twice. For those, the snapshot below: every tool-owned output
#      directory is copied before the first write and put back if this script exits
#      non-zero, so a failed re-bake leaves the ROM-consumed collision tables and the
#      generated tree exactly as it found them.
# data/editor/ is deliberately NOT snapshotted, although a bake can write one file
# there (the authored palette.bin, which ojz_common seeds when it is absent and
# inject_editor_bg.py stamps its BG lines into): that is the owner's authoring tree,
# and a restore racing an editor save would throw the save away.
echo "Preflight: checking donors + editor data before anything is written..."
python3 "${TOOLS}/ojz_strip_gen.py" preflight
# One act art pool page's bytes, READ FROM THE ENGINE, not restated
# (PAGE-SIZE-CONSTANT-ONLY, 2026-09-17). The page-size guard below used the literal
# 2048, and the page size is a parameter of the owner's open card FG-CACHE-10-HOW
# (64 -> 32 tiles). Same reader the generator, the page order and verify_level_bin use:
# fg_working_set.ConstantSource on engine/system/constants.emp. A precondition, so it
# lives here in the preflight; an unreadable constant is a hard error, never a default.
ART_POOL_PAGE_BYTES=$(python3 -c "import sys; sys.path.insert(0, sys.argv[1]); from fg_working_set import ConstantSource; s = ConstantSource(); s.load_file('engine/system/constants.emp'); print(s.get('ART_POOL_PAGE_BYTES'))" "${TOOLS}") || {
    echo "ERROR: could not read ART_POOL_PAGE_BYTES from engine/system/constants.emp."; exit 1; }
if ! [[ "${ART_POOL_PAGE_BYTES}" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: ART_POOL_PAGE_BYTES read as '${ART_POOL_PAGE_BYTES}', not a positive integer."; exit 1
fi

# RESTORE-ON-FAILURE (mechanism 2 above). Taken AFTER the preflight, which writes
# nothing, and BEFORE the first write. REBAKE_OUTPUTS is every directory outside tools/
# that the steps below write (tools/.cache is pure memoization and needs no restore).
REBAKE_OUTPUTS=(games/sonic4/data/collision games/sonic4/data/generated)
REBAKE_SNAP="$(mktemp -d "${TMPDIR:-/tmp}/regenerate-level.XXXXXX")"
for out in "${REBAKE_OUTPUTS[@]}"; do
    mkdir -p "${REBAKE_SNAP}/$(dirname "${out}")"
    cp -a "${out}" "${REBAKE_SNAP}/${out}"
done
REBAKE_COMPLETE=0
restore_rebake_outputs() {
    local rc=$?
    if [[ "${REBAKE_COMPLETE}" != 1 ]]; then
        echo "regenerate-level.sh: FAILED (exit ${rc}); restoring ${REBAKE_OUTPUTS[*]} to their state before this run" >&2
        for out in "${REBAKE_OUTPUTS[@]}"; do
            if [[ ! -d "${REBAKE_SNAP}/${out}" ]]; then
                echo "regenerate-level.sh: NO SNAPSHOT of ${out}; NOT restored, check it by hand" >&2
                continue
            fi
            rm -rf -- "${out}"
            cp -a "${REBAKE_SNAP}/${out}" "${out}"
        done
        echo "regenerate-level.sh: restored; the failed bake's outputs were discarded" >&2
        (( rc == 0 )) && rc=1
    fi
    rm -rf -- "${REBAKE_SNAP}"
    exit "${rc}"
}
trap restore_rebake_outputs EXIT

echo "Importing Sonic & Knuckles collision shape set (fixed 252-shape vocabulary)..."
python3 "${TOOLS}/import_sk_collision.py"

# STRESS_UNIQUIFY (P2c Task 11 stress fixture — set by build.sh's STRESS_ART path):
# inflate the act art pool to N distinct tiles via deterministic tile clones with
# re-pointed block references (see ojz_strip_gen.stress_uniquify_pool). This is a
# THROWAWAY re-bake — build.sh restores the committed tree from git afterward, so
# the uniquified pool never reaches a commit. When unset, the real pool is baked.
if [[ -n "${STRESS_UNIQUIFY:-}" ]]; then
    echo "Generating OJZ section data (STRESS uniquify N=${STRESS_UNIQUIFY})..."
    python3 "${TOOLS}/ojz_strip_gen.py" generate --stress-uniquify "${STRESS_UNIQUIFY}"
else
    echo "Generating OJZ section data..."
    python3 "${TOOLS}/ojz_strip_gen.py" generate
fi

# Editor-authored BG override (level editor art) — replaces the generated
# zone BG when games/sonic4/data/editor_bg_override.json exists.
if [[ -f games/sonic4/data/editor_bg_override.json ]]; then
    python3 "${TOOLS}/inject_editor_bg.py"
fi

# Act art pool pages -> per-page ZX0/raw election (P2b manifest v2, load-time tier).
# THE ELECTION LIVES IN tools/elect_pool_pages.py since 2026-09-17 (S2-COMPRESSED-ACT
# row 6): the clip-act bake (tools/clip_rom_bake.py) has to produce the same artifacts
# for a second act, and a second copy of a byte-exact emitter is how two trees end up
# disagreeing about a wrapper header nobody looks at. That file carries the election
# rule, the even-length padding rule and the numeric-index rule, with their reasons.
# ART_POOL_PAGE_BYTES is read from the engine in the preflight above and passed in —
# never retyped here.
echo "Electing ZX0/raw form for the act art pool pages (salvador)..."
python3 "${TOOLS}/elect_pool_pages.py" \
    --pool-dir games/sonic4/data/generated/ojz/act1 \
    --page-bytes "${ART_POOL_PAGE_BYTES}" \
    --salvador "${TOOLS}/bin/salvador" \
    || { echo "regenerate-level.sh: the act art pool election refused (see above)" >&2; exit 1; }

# Aurora-authored effect scenes → the per-act binding module act_descriptor.emp
# imports (scanline P5 slice 5). UNCONDITIONAL, exactly like the module it writes:
# the generator emits the two binding functions for every act whether or not any
# editor scene exists (owner ruling 2026-08-22, wave-1 design §9 Q-c), so skipping
# it on "no editor content" would delete a module the descriptor imports.
echo "Generating editor effect scenes + bindings..."
python3 "${TOOLS}/effects_gen.py" emit

echo "Generating OJZ block data..."
python3 "${TOOLS}/ojz_block_gen.py" generate ${NO_CACHE}

# The re-bake is the ONE moment the committed tree actually changes — run the
# drift gate HERE, not just at the next build.sh. (set -euo pipefail above
# makes a verify failure abort the script with its nonzero exit.)
# A stress bake is verified as one (--stress): its clones are deliberately one byte off
# their parent, declared in stress_clones.json, and the editor-bake fidelity check holds
# each clone to the editor after undoing exactly that byte (verify_level_bin.py
# _stress_clone_scratch). A canonical bake gets no flag, and refuses that sidecar.
VERIFY_FLAGS=""
if [[ -n "${STRESS_UNIQUIFY:-}" ]]; then VERIFY_FLAGS="--stress"; fi
echo "Verifying the re-baked tree..."
python3 "${TOOLS}/verify_level_bin.py" ${VERIFY_FLAGS} || { echo "regenerate-level.sh: verify_level_bin refused the re-baked tree (see above)" >&2; exit 1; }

# FG page budget on the tree just written (STITCHED-ACT-PAGE-ORDER wiring). ojz_strip_gen
# Pass 4 already refused an over-budget placement before writing; this counts what the
# ROM will embed (block blobs through the local maps, pm_flags pins), so the bake and
# build.sh's lane read the same thing. A STRESS bake is held to the same budget (it used to
# be report-only; that is how the 2026-09-03 re-cut left it at a 13-page window over 12
# frames with nothing refusing, GPL-1): its pool overwhelms the cache, its windows must not.
# `set -e` is not trusted here (reference: it does not stop in this repo).
echo "Checking the FG page budget on the re-baked tree..."
python3 "${TOOLS}/fg_page_order.py" check || { echo "regenerate-level.sh: FG page budget refused (see above)" >&2; exit 1; }

# THE EDITOR-SOURCE STAMP — record WHICH editor bytes these outputs were baked from.
# LAST, and only on a fully successful run: a stamp written before the generators
# finish would certify a tree that does not exist. `set -euo pipefail` above means a
# failure anywhere upstream never reaches this line, which is the whole point — a
# half-baked tree stays STALE.
#
# It is the staleness gate's deletion-visible arm. mtime is monotonic per file, so
# DELETING an editor document lowers no mtime and the old check read the tree as
# fresh: the same build error came back, byte-identical, about a file the author had
# already removed, until they touched something (aurora
# docs/reviews/2026-09-02-effects-cold-walkthrough.md, finding b2). A content
# manifest cannot be fooled that way. See tools/level_staleness.py's docstring.
echo "Stamping the editor sources this bake read..."
python3 "${TOOLS}/level_staleness.py" --stamp sonic4
# Every writing step has succeeded: the restore trap above must now keep this bake.
REBAKE_COMPLETE=1

echo "Re-bake complete. Next: ./build.sh both shapes."
echo "The committed level tree should be byte-identical unless the editor data or"
echo "a donor project changed — review 'git status games/sonic4/data' before committing."
echo
echo "COMMIT games/sonic4/data/editor_sources.stamp.json WITH the tree too — it is what"
echo "lets the staleness gate see an editor document that was DELETED rather than edited."
echo
echo "COMMIT games/sonic4/data/generated/ojz/act1/DONOR_PROVENANCE.json WITH the tree."
echo "ojz_strip_gen stamped both donors' HEAD SHAs (and their dirty flags) into it as"
echo "part of this run; that stamp is the only record of which donor revisions these"
echo "bytes came from. Committing the tree without it re-opens exactly the gap it"
echo "closes. A donor reported DIRTY there means the SHA does not identify what was"
echo "read — commit the donor first if you want this bake to be reproducible."
