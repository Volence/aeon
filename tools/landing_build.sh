#!/usr/bin/env bash
# landing_build.sh — the four-shape landing verification, as a COMMAND rather than a ritual.
#
# WHY THIS EXISTS. The landing lane (docs/OVERSEER-REFERENCE.md since 2026-09-10) said "four shapes, ROMs deleted first,
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

# FAST=1 skips every verification lane inside build.sh and NO_LINT=1 skips BOTH halves of
# the split pytest lane -- including the post-sigil half, and the needs_build lane at the
# bottom of this file grades exactly those tests. A FAST landing build would produce four
# ROMs and verify almost nothing while printing the same `finished=0` a real one does.
# Refused rather than honoured: this script IS the landing evidence (LS-1c, 2026-09-10).
if [ "${FAST:-0}" != 0 ]; then
    echo "landing_build: COULD NOT RUN: FAST=${FAST} skips build.sh's verification lanes."
    echo "  FAST is a content-authoring loop and is never landing evidence. Unset it."
    echo "finished=2"
    exit 2
fi
if [ "${NO_LINT:-0}" != 0 ]; then
    echo "landing_build: COULD NOT RUN: NO_LINT=${NO_LINT} skips the pytest lane this grades."
    echo "finished=2"
    exit 2
fi

# A DEBUG exported by the caller would turn the two plain shapes into debug ones: build.sh
# reads ${DEBUG:-0}, so `run_shape s4 ./build.sh` would write s4.debug.bin, leave s4.bin
# untouched, and run_shape's own `[ -f s4.bin ]` check would pass on a STALE file from a
# previous run. Every shape here sets DEBUG explicitly or must not have it at all.
unset DEBUG

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

# The provenance instant for the needs_build lane at the bottom: every artifact it grades
# must post-date this, i.e. must have been written by one of the four shapes below. Taken
# from `date +%s` for the reason build.sh's SIGIL_T0 is -- whole seconds truncate DOWN, so
# a file written in the same second still counts as fresh. It is a PROVENANCE claim ("this
# run wrote the file") and NOT a content one ("the file matches the source it was built
# from"); nothing here checks the second, and that gap is LS-1a, open across all fourteen
# consumers of this rule and deliberately not narrowed here.
T0=$(date +%s)

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

    # ---- the needs_build pytest lane (LS-1c, 2026-09-10) ----------------------------
    #
    # THIS IS THE ONLY PLACE THE MARKED LANE IS GRADED BEFORE A MERGE. LS-1 moved the
    # tests that read a build artifact out of the working tree into a POST-SIGIL lane
    # inside build.sh. One of them --
    # tools/test_effects_gates_segments.py::test_segmented_parent_checks_the_row_set_it_aggregated
    # -- declares s4.debug.bin, s4.debug.lst AND demo.debug.lst at once, and one build.sh
    # invocation writes exactly one game's .bin/.lst pair (GAME is a single scalar threaded
    # into one ${SIGIL_BUILD} build). So it DEFERS in all four shapes and, until now, ran
    # nowhere except tools/nightly_effects_gates.sh -- once a day, after the merge.
    #
    # It belongs HERE and not in build.sh, re-checked rather than inherited: build.sh
    # builds one game per invocation and every other gate in it depends on that contract.
    # This script is already the multi-shape caller, it is already the landing lane nobody
    # merges past, and the four shapes it builds are every shape build.sh can produce --
    # hence all eight names in tools/conftest.py's BUILD_ARTIFACTS. The lane costs one
    # pytest run on artifacts that are already on disk.
    #
    # IT IS A TOOL AND NOT AN INLINE `python3 -m pytest`, for the reason
    # tools/needs_build_lane.py's header gives: pytest exits 0 when every test it collected
    # was SKIPPED, which is precisely the state this lane exists to catch. The verdict is
    # read out of a JUnit report instead. ZERO deferrals are legitimate here -- this script
    # builds every shape the marked tests declare -- so a deferral is exit 2, COULD NOT RUN.
    #
    # NOT RUN AFTER A FAILED BUILD: the lane would then defer on the shape that did not
    # write, and report COULD NOT RUN on top of a real build failure, burying it. The skip
    # is printed by name and rc is already non-zero, so it is never a silent pass.
    if [ "$rc" = 0 ]; then
        echo "--- needs_build lane (--built-after $T0) ---"
        python3 tools/needs_build_lane.py --built-after "$T0"
        nb=$?
        echo "EXIT_needs_build=$nb"
        # worst-wins, matching effects_gates.py and nightly_effects_gates.sh: 2 (could not
        # run) outranks 1 (failed) outranks 0. This widens the script's exit set from {0,1}
        # to {0,1,2}; the stamp below carries the NUMBER for exactly this reason.
        if [ "$nb" != 0 ]; then rc=$nb; fi
    else
        echo "--- needs_build lane SKIPPED: a shape above did not build (rc=$rc) ---"
        echo "--- Not a pass. The lane grades artifacts THIS run wrote; one is missing. ---"
    fi
} 2>&1

# The stamp is the only thing that distinguishes a completed run from a vanished one:
# in a log they trail IDENTICALLY. Keep the NUMBER, not just the fact -- 137 vs 143
# separates a hard reclaim from a polite one.
echo "finished=$rc"
exit "$rc"
