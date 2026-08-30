#!/usr/bin/env bash
# freeze_preflight — the WHOLE pre-flight before `refreeze --freeze`, as ONE command.
#
# WHY THIS IS A SCRIPT AND NOT TWO LINES IN OVERSEER.md. The pre-flight has always had two
# steps, and on chain 187 this lane ran step 1, found exactly what step 1 exists to find, and
# went straight to the freeze. The sigil lane's diagnosis is the reason this file exists, and
# it is better than "someone skipped a check":
#
#     step 1 is genuinely useful on its own, so COMPLETING IT FELT LIKE COMPLETING THE
#     PRE-FLIGHT. A two-step ritual whose first step is independently satisfying is one that
#     will keep getting truncated there.
#
# The cost that bought this: a seven-ROM capture, committed and pushed, then unattestable —
# 8 strict failures, 7 of them one cross-seam symbol — and a second full capture to supersede
# it. Roughly twenty minutes to save two. That is the same lesson as this repo's rule to spell
# an invocation inside the command span rather than in prose beside it, arriving on a RITUAL
# instead of on a flag.
#
# STEP 1 — `repin_pins`, the READ-ONLY discriminator. It regenerates the pin table in memory
# and diffs it. A byte-moving parcel makes it RED by construction, and that red means the port
# failures below are STALE-INSTRUMENT and the freeze will clear them. Pins current + a port
# still red = the CROSS-SEAM class, which is real and needs a hand edit. Reading the port
# tests before knowing which class you are in turns a working gate into a phantom defect.
#
# STEP 2 — the port targets. `build.sh` links the whole map, so the standalone-module case it
# never exercises is exactly what these test. This is the step that was skipped.
#
# Exit: 0 pre-flight clear · 1 a real (cross-seam) failure · 2 could not run.
set -uo pipefail
SIGIL="${SIGIL_DIR:-/home/volence/sonic_hacks/sigil}"
[ -d "$SIGIL" ] || { echo "freeze_preflight: no sigil tree at $SIGIL (set SIGIL_DIR)"; exit 2; }
cd "$SIGIL" || exit 2

echo "freeze_preflight: step 1/2 — repin_pins (read-only staleness discriminator)"
if cargo test --release -p sigil-harness --test repin_pins 2>&1 | tee /tmp/fp_repin.$$ | tail -3; then
    PINS_CURRENT=1
    echo "  pins are CURRENT — any port failure below is the CROSS-SEAM class and is REAL"
else
    PINS_CURRENT=0
    if grep -q "is STALE against the live listings" /tmp/fp_repin.$$; then
        echo "  pins are STALE (expected for a byte-mover) — port failures below are"
        echo "  STALE-INSTRUMENT and the freeze's repin step clears them"
    else
        echo "freeze_preflight: repin_pins failed for a reason that is NOT staleness — stopping"
        rm -f /tmp/fp_repin.$$; exit 2
    fi
fi
rm -f /tmp/fp_repin.$$

echo
echo "freeze_preflight: step 2/2 — the port targets (the standalone-module case build.sh never exercises)"
OUT=/tmp/fp_ports.$$
cargo test --release -p sigil-cli --no-fail-fast 2>&1 | tee "$OUT" | grep -E "^test result:|FAILED|panicked at" | tail -25
FAILED=$(grep -cE "^test .* FAILED" "$OUT" 2>/dev/null || echo 0)
echo
echo "freeze_preflight: $FAILED port test failure(s)"
if [ "$FAILED" -gt 0 ]; then
    echo "  distinct cross-seam symbols named:"
    grep -oE "references symbol \`[A-Za-z_0-9]+\`" "$OUT" | sort -u | sed 's/^/    /'
    if [ "$PINS_CURRENT" = "1" ]; then
        echo "  VERDICT: pins were current, so these are REAL. Supply the composition BEFORE freezing."
        rm -f "$OUT"; exit 1
    fi
    echo "  VERDICT: pins were STALE, so these are expected. The freeze regenerates them."
    echo "  ⚠ But a CROSS-SEAM symbol named above is real even so — it is not a pin."
    grep -qE "references symbol" "$OUT" && { echo "  A cross-seam symbol IS named. Treat as REAL."; rm -f "$OUT"; exit 1; }
fi
rm -f "$OUT"
echo "freeze_preflight: CLEAR — safe to run refreeze --freeze"
