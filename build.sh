#!/bin/bash
set -euo pipefail

ROM_NAME="s4"
MAIN_ASM="main.asm"
TOOLS="${TOOLS:-tools}"

export AS_MSGPATH="${TOOLS}"
export USEANSI="n"

# Parse flags
PRINT_ERRORS_ONLY=0
for arg in "$@"; do
    case "$arg" in
        -pe) PRINT_ERRORS_ONLY=1 ;;
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

# Compress art assets
echo "Compressing art..."
python3 tools/s4lz.py compress test/title_art.bin test/title_art.s4lz

echo "Assembling ${MAIN_ASM}..."
"${TOOLS}/asl" ${ASFLAGS} "${MAIN_ASM}"

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
