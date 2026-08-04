#!/bin/bash
set -euo pipefail

# THE FLIP (Spec-5 Stage 2, the point of no return): `sigil build` IS the build.
# The AS Macro Assembler (asl) + p2bin + fixheader have left the pipeline; one sigil
# invocation assembles (every .emp module lowered natively + the residual .asm DATA
# via sigil-frontend-as), links in declared order, folds the header checksum in
# emit_rom, emits the sigil-canonical .lst, and — in DEBUG shapes ONLY — appends the
# deb2 symbol table via the surviving `convsym`. The .asm CODE twins are deleted — the
# .emp is the only source.
#
# APPENDIX SHAPE SPLIT (review item 29): the deb2 table is MD-Debugger equipment parked
# past EndOfRom, ~29 KB of a shipped cartridge that nothing on hardware reads. A release
# build therefore writes the assembled image verbatim (file length == EndOfRom, header
# untouched — emit_rom already checksummed exactly those bytes); DEBUG keeps the table.
# The `native_rom_plain` gate pins the no-appendix release shape byte-for-byte.
#
# ARTIFACT LEDGER (post-flip): the assembled anchors are the PRIMARY values and are
# UNCHANGED (the prefix [0,EndOfRom) stays byte-for-byte the asl-witnessed
# e5765873/dab4f06c, header-neutral); the full-file CRCs move on every golden re-freeze
# and live in sigil-harness golden/provenance.toml, not here. See golden/PROVENANCE.md
# and the native_full_rom / native_offcanonical_full gates.

GAME="${1:-sonic4}"
# sonic4 keeps the historical ROM name s4.bin (game content); other games use their own name.
if [[ "$GAME" == "sonic4" ]]; then ROM_NAME="s4"; else ROM_NAME="$GAME"; fi
# DEBUG builds emit SUFFIXED artifacts (s4.debug.bin/.lst), so the two shapes never
# overwrite each other. ROM_NAME threads through -o/--emit-lst and s4budget below.
if [[ "${DEBUG:-0}" == "1" ]]; then ROM_NAME="${ROM_NAME}.debug"; fi
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
NATIVE_FLAGS="--game ${GAME}"
if [[ "${DEBUG:-0}" == "1" ]]; then NATIVE_FLAGS="${NATIVE_FLAGS} --debug"; fi
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
