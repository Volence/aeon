#!/bin/bash
set -euo pipefail

# THE FLIP (Spec-5 Stage 2, the point of no return): `sigil build` IS the build.
# The AS Macro Assembler (asl) + p2bin + fixheader have left the pipeline; one sigil
# invocation assembles (every .emp module lowered natively + the residual .asm DATA
# via sigil-frontend-as), links in declared order, folds the header checksum in
# emit_rom, emits the sigil-canonical .lst, and appends the deb2 symbol table via the
# surviving `convsym`. The .asm CODE twins are deleted — the .emp is the only source.
#
# APPENDIX SHAPE SPLIT (crash-report axis, owner-ruled 2026-08-04 — this SUPERSEDES the
# review-item-29 release strip): the MD Debugger island and its deb2 symbol table are
# DIAGNOSTICS, not debug EQUIPMENT. A player's crash has to be reportable, and the
# release ROM is ~9% of a 4 MB cart, so both canonical shapes this script builds —
# release and DEBUG — carry the island AND the appendix. What release still does NOT
# carry is equipment: asserts, SOUND_DEBUG_HOTKEYS, SOUND_DBG_MIRROR, boot autoplay,
# CompressionSelfTest, the sound-debug mirror.
#
# The one shape without the debugger is the opt-in LEAN profile, which is NOT reachable
# from here (it is a named off-canonical profile, like config-a/config-b):
#   sigil build --aeon . --native --lean -o lean.bin
# Lean routes every fault vector at ReleaseFault (mask, red backdrop, freeze) instead.
#
# ARTIFACT LEDGER (post-flip): the assembled anchor — the header-neutral prefix
# [0,EndOfRom) — is the PRIMARY value, and both it and the full-file CRC move on
# every golden re-freeze that changes emitted bytes. The asl-witnessed anchors
# e5765873/dab4f06c are the CONVERSION provenance, not a standing bar; deliberate
# optimization parcels have moved the anchors since. Current values live in
# sigil-harness golden/provenance.toml, not here. See golden/PROVENANCE.md and the
# native_full_rom / native_offcanonical_full gates.

GAME="${1:-sonic4}"
# sonic4 keeps the historical ROM name s4.bin (game content); other games use their own name.
if [[ "$GAME" == "sonic4" ]]; then ROM_NAME="s4"; else ROM_NAME="$GAME"; fi
# DEBUG builds emit SUFFIXED artifacts (s4.debug.bin/.lst), so the two shapes never
# overwrite each other. ROM_NAME threads through -o/--emit-lst and s4budget below.
if [[ "${DEBUG:-0}" == "1" ]]; then ROM_NAME="${ROM_NAME}.debug"; fi

# STRESS_EVICT=1 (Art-streaming P2b Task 7 forced-eviction fixture): an off-canonical
# DEV shape — sonic4 DEBUG with the STRESS_EVICT comptime define flipped on (clamps the
# residency cache below the pool size, forcing continuous evict/reload). UNFROZEN: no
# golden, not a refreeze target — built on demand for the controller's soak. It emits a
# DISTINCT artifact (s4.stress.bin/.lst) so it never collides with the canonical shapes,
# and it fixes the whole shape (sonic4 debug), so it ignores DEBUG/GAME overrides.
if [[ "${STRESS_EVICT:-0}" == "1" ]]; then
    if [[ "$GAME" != "sonic4" ]]; then
        echo "ERROR: STRESS_EVICT=1 is a sonic4-only fixture (the OJZ act pool is the target)."
        exit 1
    fi
    ROM_NAME="s4.stress"
fi

# STRESS_ART=1 (Art-streaming P2c Task 11 stress fixture): the sonic4 DEBUG shape
# built against a UNIQUIFIED act art pool (ojz_strip_gen --stress-uniquify N,
# default 2600 tiles / >40 pages) that overwhelms the 15-frame residency cache with
# continuous evict/reload traffic. Like STRESS_EVICT it is an off-canonical DEV
# shape: UNFROZEN, no golden, a DISTINCT artifact (s4.stressart.bin/.lst), and it
# fixes the whole shape (sonic4 DEBUG), ignoring DEBUG/GAME overrides.
#
# ISOLATION — the committed real act data is NEVER overwritten. sigil places the
# act-pool .emp module by a FIXED registry PATH (not a tree walk), so a parallel
# generated dir cannot be linked without a sigil registry/path change. Instead the
# stress pool is a THROWAWAY in-place re-bake (regenerate-level.sh with
# STRESS_UNIQUIFY set) guarded by an EXIT trap that restores the generated tree +
# collision from git and cleans stress-only files (see below) — so `git status` is
# left clean of real-data changes, no sigil-side change needed.
if [[ "${STRESS_ART:-0}" == "1" ]]; then
    if [[ "$GAME" != "sonic4" ]]; then
        echo "ERROR: STRESS_ART=1 is a sonic4-only fixture (the OJZ act pool is the target)."
        exit 1
    fi
    if [[ "${STRESS_EVICT:-0}" == "1" ]]; then
        echo "ERROR: STRESS_ART and STRESS_EVICT are mutually exclusive shapes."
        exit 1
    fi
    DEBUG=1                      # the fixture needs asserts + the refcount/orphan audit
    ROM_NAME="s4.stressart"
fi
MAIN_ASM="games/${GAME}/game_root.asm"
TOOLS="${TOOLS:-tools}"

# Per-game build config (optional): may set defaults, e.g. SOUND_DRIVER_ENABLED
# (demo sets SOUND_DRIVER_ENABLED=0 — it ships no sound bank yet).
if [[ -f "games/${GAME}/build.conf" ]]; then
    source "games/${GAME}/build.conf"
fi

# Parse flags. -pe (asl print-errors-only) is now a no-op — the native build always
# streams errors — but stays accepted for CLI compatibility.
NO_LINT=0
for arg in "$@"; do
    case "$arg" in
        -nl|--no-lint) NO_LINT=1 ;;
    esac
done

# The canonical shapes (the frozen goldens) are what build.sh ships: plain + debug,
# both games. The NON-canonical sonic4 sound shapes (silent / hotkeys / mirror) are
# named off-canonical profiles now — build them directly and diff their own goldens:
#   silent sonic4          -> sigil build --native --config-b
#   debug + hotkeys+mirror -> sigil build --native --config-a
# (Building an UNPROVEN sound-toggle combo from here would ship bytes no golden gates,
# so build.sh refuses rather than emit something unverifiable. The full toggle matrix
# folds back in with the Stage-3 debug-runtime work.) demo's SOUND_DRIVER_ENABLED=0 is
# its canonical state, not an override, so this only guards sonic4.
if [[ "$GAME" == "sonic4" ]]; then
    if [[ "${SOUND_DRIVER_ENABLED:-1}" != "1" \
       || "${SOUND_DEBUG_HOTKEYS:-0}" == "1" \
       || "${SOUND_DBG_MIRROR:-0}" == "1" ]]; then
        echo "ERROR: non-canonical sonic4 sound shapes are the off-canonical profiles now:"
        echo "  silent sonic4          -> sigil build --native --config-b -o s4.bin"
        echo "  debug + hotkeys+mirror -> sigil build --native --config-a -o s4.debug.bin"
        exit 1
    fi
fi

# CRASH_REPORT is not an env axis of this script: the two shapes build.sh ships (release
# and DEBUG) both carry the MD Debugger island + deb2 symbols, by the 2026-08-04 ruling.
# The debugger-less shape is the named LEAN profile, gated by its own goldens — same
# treatment as the non-canonical sound shapes above.
if [[ "${CRASH_REPORT:-1}" != "1" ]]; then
    echo "ERROR: CRASH_REPORT=0 is not a build.sh shape — it is the off-canonical lean profile:"
    echo "  no debugger, no deb2 symbols -> sigil build --aeon . --native --lean -o lean.bin"
    exit 1
fi

# The sigil build binary — THE assembler now. No asl fallback: a missing/failed sigil
# is a HARD ERROR (mirrors the seam-1 SIGIL_EMIT dependency).
SIGIL_BUILD="${SIGIL_BUILD:-}"
if [[ -z "${SIGIL_BUILD}" || ! -x "${SIGIL_BUILD}" ]]; then
    echo "ERROR: build.sh needs the sigil build binary — set SIGIL_BUILD to it."
    echo "  (sigil build IS the build now; asl has left the pipeline. Build the sigil"
    echo "   toolchain first: cargo build --release --bin sigil.)"
    exit 1
fi

# The resident sound blob + banked sound data are sigil-native-linked (seam-1/seam-2);
# this preflight regenerates engine/sound/generated (the .bin blobs the sound-bank .emp
# sections embed(), including the three-way-split MT bank) from the .emp sources.
# Sound-ON games only (demo is silent).
if [[ "${SOUND_DRIVER_ENABLED:-1}" == "1" ]]; then
    SIGIL_EMIT="${SIGIL_EMIT:-}"
    if [[ -z "${SIGIL_EMIT}" || ! -x "${SIGIL_EMIT}" ]]; then
        echo "ERROR: seam-1 needs the sigil emit_sound_blob binary — set SIGIL_EMIT to it."
        exit 1
    fi
    echo "Emitting the native-linked resident sound blob (sigil)..."
    mkdir -p engine/sound/generated
    if ! "${SIGIL_EMIT}" --aeon . --out-dir engine/sound/generated; then
        echo "ERROR: sigil emit_sound_blob failed — cannot build the resident sound blob."
        exit 1
    fi
fi

# Build the vendored salvador (ZX0 packer) once if missing
if [[ ! -x "${TOOLS}/bin/salvador" ]]; then
    echo "Building salvador (ZX0 packer)..."
    make -C "${TOOLS}/salvador" -s
    mkdir -p "${TOOLS}/bin"
    cp "${TOOLS}/salvador/salvador" "${TOOLS}/bin/salvador"
fi

# Per-game content generators (optional)
if [[ -x "games/${GAME}/prebuild.sh" ]]; then
    "games/${GAME}/prebuild.sh"
fi

echo "Generating compression self-test vectors..."
python3 "${TOOLS}/gen_compression_vectors.py"

if [[ "${NO_LINT:-0}" == "0" ]]; then
    echo "Linting..."
    if ! python3 "${TOOLS}/s4lint.py" "${MAIN_ASM}"; then
        echo "Lint errors found — fix before assembling."
        exit 1
    fi
fi

# STRESS_ART throwaway re-bake: regenerate the uniquified act pool IN PLACE under an
# EXIT trap that restores the committed tree from git (covers success AND set -e
# failures). Requires donors (like regenerate-level.sh). verify_level_bin below then
# runs against the stress tree (it stays internally consistent), and the sigil build
# links the uniquified pool into s4.stressart.bin.
if [[ "${STRESS_ART:-0}" == "1" ]]; then
    STRESS_GEN_TREE="games/sonic4/data/generated/ojz/act1"
    STRESS_COLL_TREE="games/sonic4/data/collision"
    if [[ -n "$(git status --porcelain -- "$STRESS_GEN_TREE" "$STRESS_COLL_TREE")" ]]; then
        echo "ERROR: STRESS_ART needs a clean generated tree, but git status shows changes"
        echo "  under $STRESS_GEN_TREE or $STRESS_COLL_TREE. Commit or stash them first —"
        echo "  the stress re-bake restores from git and would discard uncommitted changes."
        exit 1
    fi
    _restore_stress_tree() {
        echo "STRESS_ART: restoring the committed level tree from git..."
        git checkout -q -- "$STRESS_GEN_TREE" "$STRESS_COLL_TREE" 2>/dev/null || true
        git clean -fdq -- "$STRESS_GEN_TREE" 2>/dev/null || true
    }
    trap _restore_stress_tree EXIT
    echo "STRESS_ART: throwaway re-bake with uniquified act pool (N=${STRESS_ART_N:-2600})..."
    STRESS_UNIQUIFY="${STRESS_ART_N:-2600}" "${TOOLS}/regenerate-level.sh"
fi

# The committed OJZ level tree is consumed directly (its generators need
# out-of-repo donors — tools/regenerate-level.sh). Fail LOUDLY on internal
# drift (hand-edited head, missing blob, stale .zx0) the whole-ROM gate would
# only catch after the ROM already moved.
echo "Verifying committed OJZ level tree..."
if ! python3 "${TOOLS}/verify_level_bin.py"; then
    echo "Level-tree drift — re-bake with tools/regenerate-level.sh, then rebuild."
    exit 1
fi

# THE BUILD: one sigil invocation — assemble -> declared-order link -> emit_rom
# (checksum folded) -> sigil-canonical .lst -> ROM. DEBUG additionally gets the
# convsym deb2 appendix; release ships the assembled image alone (item 29).
if [[ "${STRESS_EVICT:-0}" == "1" ]]; then
    # The stress fixture fixes the shape (sonic4 debug + STRESS_EVICT define); it does
    # NOT combine with --game/--debug (the CLI rejects that).
    NATIVE_FLAGS="--stress-evict"
elif [[ "${STRESS_ART:-0}" == "1" ]]; then
    # The stress-art fixture fixes the shape (sonic4 debug + fixture placement) against
    # the uniquified pool re-baked above; --stress-art selects the fixture-scoped derived
    # placement (greedy pack from measured sizes, org anchors held). It does NOT combine
    # with --game/--debug (the CLI rejects that).
    NATIVE_FLAGS="--stress-art"
else
    NATIVE_FLAGS="--game ${GAME}"
    if [[ "${DEBUG:-0}" == "1" ]]; then NATIVE_FLAGS="${NATIVE_FLAGS} --debug"; fi
fi
# CONTRACT CLOSURE GATE — default ON.
#
# `sigil build` runs the whole-corpus contract closure before it links. The
# closure needs the whole call graph, so it cannot be a per-file check; this is
# where it gates. A firing outside the frozen baseline fails the build with the
# list, and so does a baseline row that STOPS firing — a silently narrowing
# analysis is the destructive direction, not a free pass.
#
# CONTRACTS=0 is the EMERGENCY OPT-OUT, not a normal knob. It exists so a
# contract-checker defect cannot block shipping a ROM; using it means the build
# is not contract-checked, and the skip says so on stderr. Reach for it only when
# the gate itself is wrong, and open a ledger row when you do.
if [[ "${CONTRACTS:-1}" == "0" ]]; then
    export SIGIL_CONTRACTS=0
fi

echo "Building ${MAIN_ASM} (sigil)..."
"${SIGIL_BUILD}" build --aeon . --native ${NATIVE_FLAGS} \
    -o "${ROM_NAME}.bin" --emit-lst "${ROM_NAME}.lst"

ROM_SIZE=$(stat -c%s "${ROM_NAME}.bin")
ROM_KB=$(awk "BEGIN {printf \"%.1f\", ${ROM_SIZE}/1024}")
ROM_PCT=$(awk "BEGIN {printf \"%.1f\", ${ROM_SIZE}/4194304*100}")
echo "Build complete: ${ROM_NAME}.bin — ${ROM_SIZE} bytes (${ROM_KB} KB, ${ROM_PCT}% of 4MB)"

# Budget summary
if [[ -f "${ROM_NAME}.lst" ]]; then
    python3 "${TOOLS}/s4budget.py" "${ROM_NAME}.lst" "${ROM_NAME}.bin" --summary || true
fi

# Update ctags symbol index
if command -v ctags &>/dev/null; then
    ctags -R .
fi
