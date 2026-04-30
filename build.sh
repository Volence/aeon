#!/bin/bash
set -euo pipefail

ROM_NAME="s4"
MAIN_ASM="main.asm"
TOOLS="${TOOLS:-tools}"

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
ASFLAGS="-cpu 68000 -xx -n -q -c -A -L"
ASFLAGS="${ASFLAGS} -OLIST ${ROM_NAME}.lst"
ASFLAGS="${ASFLAGS} -o ${ROM_NAME}.p"
ASFLAGS="${ASFLAGS} -shareout ${ROM_NAME}.h"
ASFLAGS="${ASFLAGS} -i ."

if [[ "${DEBUG:-0}" == "1" ]]; then
    ASFLAGS="${ASFLAGS} -D __DEBUG__"
fi

if [[ "${PRINT_ERRORS_ONLY}" == "0" ]]; then
    ASFLAGS="${ASFLAGS} -E ${ROM_NAME}.log"
fi

echo "Generating OJZ section data..."
python3 "${TOOLS}/ojz_strip_gen.py" generate

echo "Compressing OJZ per-section tile blobs with S4LZ..."
for sec_bin in data/generated/ojz/act1/sec*_tiles.bin; do
    sec_s4lz="${sec_bin%.bin}.s4lz"
    if [[ -s "$sec_bin" ]]; then
        python3 "${TOOLS}/s4lz.py" compress --tile-delta "$sec_bin" "$sec_s4lz"
    else
        # Zero-length section — write a 4-byte zero-length S4LZ header.
        printf '\x00\x00\x00\x00' > "$sec_s4lz"
    fi
done

if [[ "${NO_LINT:-0}" == "0" ]]; then
    echo "Linting..."
    if ! python3 "${TOOLS}/s4lint.py" "${MAIN_ASM}"; then
        echo "Lint errors found — fix before assembling."
        exit 1
    fi
fi

# Remove stale intermediates so a failed assembly can't silently
# leave a previous .p file for p2bin to convert.
rm -f "${ROM_NAME}.p" "${ROM_NAME}.h"

echo "Assembling ${MAIN_ASM}..."
"${TOOLS}/asl" ${ASFLAGS} "${MAIN_ASM}"

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
