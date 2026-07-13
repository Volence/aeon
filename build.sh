#!/bin/bash
set -euo pipefail

GAME="${1:-sonic4}"
# sonic4 keeps the historical ROM name s4.bin (game content); other games use their own name.
if [[ "$GAME" == "sonic4" ]]; then ROM_NAME="s4"; else ROM_NAME="$GAME"; fi
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
