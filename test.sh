#!/bin/bash
set -euo pipefail

TOOLS="${TOOLS:-tools}"
PASSED=0
FAILED=0
TOTAL=0

pass_test() {
    echo "  PASS: $1"
    PASSED=$((PASSED + 1))
    TOTAL=$((TOTAL + 1))
}

fail_test() {
    echo "  FAIL: $1"
    FAILED=$((FAILED + 1))
    TOTAL=$((TOTAL + 1))
}

section() {
    echo ""
    echo "========================================"
    echo "$1"
    echo "========================================"
}

# -----------------------------------------------
section "1. S4LZ Compression Self-Tests"
# -----------------------------------------------
if python3 "${TOOLS}/s4lz.py" test; then
    pass_test "S4LZ self-tests"
else
    fail_test "S4LZ self-tests"
fi

# -----------------------------------------------
section "2. S4LZ Real-Data Round-Trip"
# -----------------------------------------------
if [ -f "test/title_art.bin" ]; then
    if python3 "${TOOLS}/s4lz.py" verify test/title_art.bin; then
        pass_test "S4LZ round-trip: title_art.bin"
    else
        fail_test "S4LZ round-trip: title_art.bin"
    fi

    if python3 "${TOOLS}/s4lz.py" verify --tile-delta test/title_art.bin; then
        pass_test "S4LZ round-trip: title_art.bin (tile-delta)"
    else
        fail_test "S4LZ round-trip: title_art.bin (tile-delta)"
    fi
else
    fail_test "test/title_art.bin not found"
fi

# -----------------------------------------------
section "3. DPLC Layout Tool Self-Tests"
# -----------------------------------------------
if python3 "${TOOLS}/dplc_layout.py" test; then
    pass_test "DPLC layout self-tests"
else
    fail_test "DPLC layout self-tests"
fi

# -----------------------------------------------
section "4. Sprite & DPLC Verification"
# -----------------------------------------------
if python3 "${TOOLS}/verify_sprites.py"; then
    pass_test "Sprite & DPLC verification"
else
    fail_test "Sprite & DPLC verification"
fi

# -----------------------------------------------
section "5. DPLC Optimized Art Integrity"
# -----------------------------------------------
# Verify optimized art+DPLC was produced correctly from originals
DPLC_OK=true

for char in sonic tails; do
    ART_ORIG="art/uncompressed/characters/${char}.bin"
    ART_OPT="art/optimized/characters/${char}.bin"
    DPLC_ORIG="data/dplc/${char}.bin"
    DPLC_OPT="data/dplc/optimized/${char}.bin"

    if [ -f "$ART_ORIG" ] && [ -f "$ART_OPT" ] && [ -f "$DPLC_ORIG" ] && [ -f "$DPLC_OPT" ]; then
        # Re-run the layout tool to a temp file and compare
        TMPDIR=$(mktemp -d)
        python3 "${TOOLS}/dplc_layout.py" "$ART_ORIG" "$DPLC_ORIG" \
            --out-art "${TMPDIR}/art.bin" --out-dplc "${TMPDIR}/dplc.bin" 2>/dev/null

        if cmp -s "${TMPDIR}/art.bin" "$ART_OPT"; then
            pass_test "Optimized art matches: ${char}"
        else
            fail_test "Optimized art mismatch: ${char}"
            DPLC_OK=false
        fi

        if cmp -s "${TMPDIR}/dplc.bin" "$DPLC_OPT"; then
            pass_test "Optimized DPLC matches: ${char}"
        else
            fail_test "Optimized DPLC mismatch: ${char}"
            DPLC_OK=false
        fi

        rm -rf "$TMPDIR"
    else
        echo "  SKIP: ${char} (missing files)"
    fi
done

# -----------------------------------------------
section "6. OJZ Strip Generator Self-Tests"
# -----------------------------------------------
if python3 "${TOOLS}/ojz_strip_gen.py" test; then
    pass_test "OJZ strip generator self-tests"
else
    fail_test "OJZ strip generator self-tests"
fi

# -----------------------------------------------
section "6b. Collision Pipeline Self-Tests"
# -----------------------------------------------
if python3 "${TOOLS}/collision_pipeline.py" test; then
    pass_test "Collision pipeline self-tests"
else
    fail_test "Collision pipeline self-tests"
fi

# -----------------------------------------------
section "7. ROM Build"
# -----------------------------------------------
if ./build.sh -pe 2>&1; then
    pass_test "ROM build"
else
    fail_test "ROM build"
fi

# ROM sanity checks
if [ -f "s4.bin" ]; then
    ROM_SIZE=$(stat -c%s "s4.bin")

    # Check ROM is not empty
    if [ "$ROM_SIZE" -gt 512 ]; then
        pass_test "ROM size > 512 bytes (${ROM_SIZE} bytes)"
    else
        fail_test "ROM too small: ${ROM_SIZE} bytes"
    fi

    # Check ROM fits in 4MB
    if [ "$ROM_SIZE" -le 4194304 ]; then
        pass_test "ROM fits in 4MB"
    else
        fail_test "ROM exceeds 4MB: ${ROM_SIZE} bytes"
    fi

    # Check ROM is even-sized (convsym symbol appendix may add odd bytes — warn only)
    if [ $((ROM_SIZE % 2)) -eq 0 ]; then
        pass_test "ROM size is even"
    else
        echo "  WARN: ROM file size is odd (${ROM_SIZE} bytes) — likely debug symbol appendix"
    fi

    # Check header magic at $100
    HEADER=$(xxd -s 256 -l 16 -p "s4.bin")
    if [[ "$HEADER" == "5345474120474"* ]]; then
        pass_test "ROM header: SEGA GENESIS"
    else
        fail_test "ROM header missing SEGA magic: ${HEADER}"
    fi

    # Check vector table: SSP at $0, Reset PC at $4
    SSP=$(xxd -s 0 -l 4 -p "s4.bin")
    RESET=$(xxd -s 4 -l 4 -p "s4.bin")
    if [[ "$SSP" != "00000000" ]]; then
        pass_test "Vector table: SSP set (0x${SSP})"
    else
        fail_test "Vector table: SSP is zero"
    fi
    if [[ "$RESET" != "00000000" ]]; then
        pass_test "Vector table: Reset PC set (0x${RESET})"
    else
        fail_test "Vector table: Reset PC is zero"
    fi
else
    fail_test "s4.bin not found after build"
fi

# -----------------------------------------------
section "RESULTS"
# -----------------------------------------------
echo ""
echo "${PASSED}/${TOTAL} passed, ${FAILED} failed"
if [ "$FAILED" -gt 0 ]; then
    echo "SOME TESTS FAILED"
    exit 1
else
    echo "ALL TESTS PASSED"
fi
