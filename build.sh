#!/bin/bash
set -euo pipefail

GAME="${1:-sonic4}"
# sonic4 keeps the historical ROM name s4.bin (game content); other games use their own name.
if [[ "$GAME" == "sonic4" ]]; then ROM_NAME="s4"; else ROM_NAME="$GAME"; fi
# DEBUG builds emit SUFFIXED artifacts natively (s4.debug.bin/.lst/.log), so the
# two shapes never overwrite each other and no manual cp of the debug artifacts is
# needed. ROM_NAME threads through -OLIST/-o/-shareout, p2bin, convsym, s4budget
# and fixheader below, so every downstream consumer (repin, oracle, pins) sees the
# filenames it already expects.
if [[ "${DEBUG:-0}" == "1" ]]; then ROM_NAME="${ROM_NAME}.debug"; fi
MAIN_ASM="games/${GAME}/main.asm"
TOOLS="${TOOLS:-tools}"

# Per-game build config (optional): may set defaults, e.g. SOUND_DRIVER_ENABLED
if [[ -f "games/${GAME}/build.conf" ]]; then
    source "games/${GAME}/build.conf"
fi

export AS_MSGPATH="${TOOLS}"
export USEANSI="n"

# Parse flags
PRINT_ERRORS_ONLY=0
NO_LINT=0
for arg in "$@"; do
    case "$arg" in
        -pe) PRINT_ERRORS_ONLY=1 ;;
        -nl|--no-lint) NO_LINT=1 ;;
    esac
done

# Assembler flags
# -U: case-sensitive symbols — required since §5 RAM fields (Phys_accel)
# and physics constants (PHYS_ACCEL) differ only by case. Verified to
# produce byte-identical output on the pre-§5 codebase.
ASFLAGS="-cpu 68000 -xx -n -q -c -A -L -U"
ASFLAGS="${ASFLAGS} -OLIST ${ROM_NAME}.lst"
ASFLAGS="${ASFLAGS} -o ${ROM_NAME}.p"
ASFLAGS="${ASFLAGS} -shareout ${ROM_NAME}.h"
ASFLAGS="${ASFLAGS} -i ."

if [[ "${DEBUG:-0}" == "1" ]]; then
    ASFLAGS="${ASFLAGS} -D __DEBUG__"
fi

# Sound engine ON by default now (the driver is the active dev target). Disable
# explicitly with SOUND_DRIVER_ENABLED=0 ./build.sh for a smaller silent ROM.
if [[ "${SOUND_DRIVER_ENABLED:-1}" == "1" ]]; then
    ASFLAGS="${ASFLAGS} -D SOUND_DRIVER_ENABLED"
fi

# Sound debug HOTKEYS + boot autoplay (the sound test-harness): A = restart MT,
# B = SFX cycle, C = drum test, UP = HCZ2, START = MT toggle, plus the boot-time
# Moving Trucks autoplay. OFF by default — A/C double as the player's JUMP button
# and UP/START collide with gameplay, so normal play stays clean. Enable for
# sound-verification sessions: SOUND_DEBUG_HOTKEYS=1 (requires DEBUG=1 too).
if [[ "${SOUND_DEBUG_HOTKEYS:-0}" == "1" ]]; then
    ASFLAGS="${ASFLAGS} -D SOUND_DEBUG_HOTKEYS"
fi

# DEBUG-only: mirror Z80 driver state into 68k RAM each frame for MCP inspection.
# This stops the Z80 ~190us/frame for the copy -> an audible 60Hz tick, so it is
# OFF by default (clean audio in DEBUG builds). Enable only when inspecting Z80
# state via the Sound_Dbg_Mirror; expect the tick while it is on.
if [[ "${SOUND_DBG_MIRROR:-0}" == "1" ]]; then
    ASFLAGS="${ASFLAGS} -D SOUND_DBG_MIRROR"
fi

# seam-1 (Option A): THE NATIVE LINK IS THE BUILD. The resident sound blob is the
# five sound .emp files linked NATIVELY by sigil, emitted to a binary asl BINCLUDEs
# (the five .asm twins are DELETED — the .emp is the canonical source). THIS IS THE
# FIRST HARD aeon→sigil BUILD DEPENDENCY: there is NO asl fallback, so a missing/
# failed emitter is a HARD ERROR, never a silent skip. Byte-deterministic; the
# ASSEMBLED-ROM CRC is the provenance bar.
if [[ "${SOUND_DRIVER_ENABLED:-1}" == "1" ]]; then
    SIGIL_EMIT="${SIGIL_EMIT:-}"
    if [[ -z "${SIGIL_EMIT}" || ! -x "${SIGIL_EMIT}" ]]; then
        echo "ERROR: seam-1 needs the sigil emit_sound_blob binary — set SIGIL_EMIT to it."
        echo "  (the resident sound blob is sigil-native-linked; the .asm twins are gone,"
        echo "   so there is no asl fallback — build the sigil toolchain first.)"
        exit 1
    fi
    echo "Emitting the native-linked resident sound blob (sigil)..."
    mkdir -p engine/sound/generated
    if ! "${SIGIL_EMIT}" --aeon . --out-dir engine/sound/generated; then
        echo "ERROR: sigil emit_sound_blob failed — cannot build the resident sound blob."
        exit 1
    fi
fi

if [[ "${PRINT_ERRORS_ONLY}" == "0" ]]; then
    ASFLAGS="${ASFLAGS} -E ${ROM_NAME}.log"
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

# Generated sound data ships as .asm/.bin twins (the .asm for this asl build,
# the .bin for sigil `embed` — sound-migration DSM.4). A regen that updates one
# twin but not the other drifts the two builds apart silently; fail fast here.
echo "Verifying generated sound .asm/.bin twins..."
if ! python3 "${TOOLS}/verify_emit_bin.py"; then
    echo "Generated .asm/.bin twin mismatch — re-run the emitter with --emit-bin, then rebuild."
    exit 1
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

if [[ "${SIGIL_NATIVE:-0}" == "1" ]]; then
    # THE FLIP BUILD (behind the SIGIL_NATIVE flag — asl stays the default until the
    # Stage-2 no-return commit). One sigil invocation drives the WHOLE pipeline the
    # native gates bank: assemble (every .emp module lowered + AS residual) →
    # declared-order chained link → emit_rom (checksum folded) → sigil-canonical .lst
    # → convsym deb2 appendix → fixheader. The emitted .bin is byte-identical to the
    # native_full_rom / native_offcanonical_full gate outputs (proven CRCs).
    SIGIL_BUILD="${SIGIL_BUILD:-}"
    if [[ -z "${SIGIL_BUILD}" || ! -x "${SIGIL_BUILD}" ]]; then
        echo "ERROR: SIGIL_NATIVE=1 needs the sigil build binary — set SIGIL_BUILD to it."
        echo "  (build the sigil toolchain first; the native build is the flip build.)"
        exit 1
    fi
    NATIVE_FLAGS="--game ${GAME}"
    if [[ "${DEBUG:-0}" == "1" ]]; then NATIVE_FLAGS="${NATIVE_FLAGS} --debug"; fi
    echo "Building ${MAIN_ASM} natively (sigil)..."
    "${SIGIL_BUILD}" build --aeon . --native ${NATIVE_FLAGS} \
        -o "${ROM_NAME}.bin" --emit-lst "${ROM_NAME}.lst"
else
    # Remove stale intermediates so a failed assembly can't silently
    # leave a previous .p file for p2bin to convert.
    rm -f "${ROM_NAME}.p" "${ROM_NAME}.h"

    echo "Assembling ${MAIN_ASM}..."
    "${TOOLS}/asl" ${ASFLAGS} "${MAIN_ASM}"

    # asl can report assembler errors to the -E log yet STILL exit 0 and emit a .p
    # with the offending region silently zeroed — a malformed ROM that looks valid
    # by size and passes the .p-exists check below, but poisons provenance baselines
    # (real incident: a `jump distance too big` zeroed the sound_api region). `set -e`
    # does not catch it because asl's exit is 0. Fail HARD on any error line in the
    # log. (With -pe there is no -E log — errors stream to stdout for the dev to see.)
    if [[ -f "${ROM_NAME}.log" ]] && grep -qiE 'error #[0-9]|: error' "${ROM_NAME}.log"; then
        echo "ERROR: assembler reported errors (see ${ROM_NAME}.log):"
        grep -iE 'error #[0-9]|: error' "${ROM_NAME}.log" | head
        exit 1
    fi

    if [[ ! -f "${ROM_NAME}.p" ]]; then
        echo "ERROR: Assembly produced no output (${ROM_NAME}.p missing)."
        echo "       Check ${ROM_NAME}.log for errors."
        exit 1
    fi

    echo "Converting to binary..."
    "${TOOLS}/p2bin" "${ROM_NAME}.p" "${ROM_NAME}.bin" "${ROM_NAME}.h"

    # Symbol table for MD Debugger (if listing exists)
    if [[ -f "${ROM_NAME}.lst" ]]; then
        "${TOOLS}/convsym" "${ROM_NAME}.lst" "${ROM_NAME}.bin" \
            -input as_lst -range 0 FFFFFF -exclude -filter "z[A-Z].+" -a 2>/dev/null || true
    fi

    echo "Fixing header checksum..."
    "${TOOLS}/fixheader" "${ROM_NAME}.bin"

    # Clean intermediates
    rm -f "${ROM_NAME}.p" "${ROM_NAME}.h"
fi

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
