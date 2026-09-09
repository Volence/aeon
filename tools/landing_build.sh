#!/usr/bin/env bash
# landing_build.sh — the four-shape landing verification, as a COMMAND rather than a ritual.
#
# WHY THIS EXISTS. docs/OVERSEER.md's landing lane said "four shapes, ROMs deleted first,
# so existence proves freshness". Every session implemented that by hand, and the natural
# implementation -- delete all four, then build them one at a time -- left each ROM missing
# for the whole of every OTHER shape's build as well as its own. The oracle lane measured
# s4.debug.bin ABSENT CONTINUOUSLY for 7+ minutes across three of our builds while its own
# consumers were reading that file.
#
# The hazard is not the outage. It is what a blocked consumer reaches for: a stale alternate
# ROM that IS present, yielding findings from a different build that look exactly like
# findings from yours. Absence is loud; the substitute is silent.
#
# So each shape is built to a TEMP name and RENAMED into place. That keeps the property the
# delete existed for -- the temp's existence proves the build actually ran, so a stale ROM
# cannot masquerade as a fresh one -- while removing the window, because rename(2) is atomic
# on one filesystem: a reader sees the previous complete ROM or the new one, never a gap and
# never a partial.
#
# This repo prefers a check that cannot be omitted to a rule that must be remembered. The
# rule is now this file.
#
# Usage:  tools/landing_build.sh [logfile]
# Reads:  SIGIL_BUILD, SIGIL_EMIT (required; set by no dotfile on this machine)
set -u

cd "$(dirname "$0")/.." || { echo "cannot reach the repo root"; exit 2; }

: "${SIGIL_BUILD:?SIGIL_BUILD is unset -- that is a BLOCKED report, not a workaround hunt}"
: "${SIGIL_EMIT:?SIGIL_EMIT is unset -- required for any sound-ON game, i.e. every sonic4 build}"

rc=0

# shape name -> the build invocation that produces <name>.bin
run_shape() {
    local rom="$1"; shift
    local tmp="${rom}.landing-tmp"

    rm -f "$tmp"                       # the temp, never the live artifact
    if ! ( "$@" ) ; then
        echo "EXIT_${rom}=FAILED (build command returned non-zero)"
        rc=1
        return
    fi

    # build.sh writes <rom>.bin in place; move it aside atomically only once complete.
    if [ ! -f "${rom}.bin" ]; then
        # Loud on unmeasurable: a missing artifact is "did not run", never a verdict.
        echo "EXIT_${rom}=NO_ARTIFACT (${rom}.bin absent after a zero-exit build)"
        rc=1
        return
    fi
    mv -f "${rom}.bin" "$tmp" && mv -f "$tmp" "${rom}.bin"
    echo "EXIT_${rom}=0 size=$(stat -c %s "${rom}.bin")"
}

{
    run_shape s4          ./build.sh
    run_shape s4.debug    env DEBUG=1 ./build.sh
    run_shape demo        ./build.sh demo
    run_shape demo.debug  env DEBUG=1 ./build.sh demo

    echo "--- md5 (quote these WITH the assembler revision beside them; a CRC alone is"
    echo "--- meaningless across sessions because the toolchain is the one unpinned input) ---"
    md5sum s4.bin s4.debug.bin demo.bin demo.debug.bin 2>&1
    echo "--- assembler ---"
    "$SIGIL_BUILD" --version 2>&1 | head -1
    echo "md5(SIGIL_BUILD)=$(md5sum "$SIGIL_BUILD" | cut -d' ' -f1)"
} 2>&1

# The stamp is the only thing that distinguishes a completed run from a vanished one:
# in a log they trail IDENTICALLY. Keep the NUMBER, not just the fact -- 137 vs 143
# separates a hard reclaim from a polite one.
echo "finished=$rc"
exit "$rc"
