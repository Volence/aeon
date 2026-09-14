#!/usr/bin/env bash
# landing_build.sh — the landing verification (the pre-merge check), as a COMMAND rather than a ritual.
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
# WHICH SHAPES (CTRL-3b, 2026-09-14). The hub picked A plus D of the CTRL-3 shapes proposal
# (empyrean cf430f7 docs/OVERSEER.md, "HUB PICK on aeon CTRL-3";
# docs/superpowers/notes/2026-09-13-ctrl3-shapes-proposal.md):
#   A  this check builds Sonic 4 normal, Sonic 4 debug and demo debug, and NOT demo normal.
#      Every Sonic 4 build still assembles demo normal in full for its placement, region
#      budget and image bounds (build.sh, "Evaluating the other game's link-time guards");
#      demo normal's own lanes run in `./build.sh demo` and in the nightly.
#   D  the shape-independent lanes (build.sh's pre-build `pytest tools -m "not needs_build"`
#      and tools/emp_expect_fail.py) run ONCE per check: inside the first shape's build.sh,
#      exactly as a person's ./build.sh runs them (same selection, flags and pre-state, with
#      nothing retyped here), and every later shape skips them on a RECEIPT this script
#      writes only after that shape exited 0. build.sh's LANDING_LANES_RECEIPT block says how
#      the receipt proves its caller, and why it is not a second FAST=1. If the carrier fails,
#      the next shape runs the lanes itself: they are never skipped on a build that did not pass.
# B (drop both demo shapes) is the OWNER'S, one word away, and it is ONE line: LANDING_SHAPES
# below. Everything else derives from it: which shapes build, the md5 line, the shape list
# the needs_build lane is handed (and so its exemption), and which shape carries the lanes.
# tools/test_landing_build_trim.py makes that swap in a sandbox and checks all of it.
# This is the PRE-MERGE CHECK only: ./build.sh still builds all four shapes on request, the
# nightly (tools/nightly_effects_gates.sh) builds all four, and sigil's goldens pin all six.
#
# Usage:  tools/landing_build.sh [logfile]
#   With a logfile, the WHOLE output (stdout and stderr, refusals included) also goes to that
#   file, truncated first, and `finished=<n>` is its last line exactly as it is stdout's. A
#   relative path is relative to the CALLER's directory. Without one: stdout only.
# Reads:  SIGIL_BUILD, SIGIL_EMIT (required; set by no dotfile on this machine)
set -u

# The shapes this check builds, in build order: ROM names by build.sh's rule (s4 for sonic4,
# else the game name, plus .debug for DEBUG=1). The first one carries the shared lanes. The
# A->B swap is the one line between the markers; tools/test_landing_build_trim.py parses it.
# >>> LANDING_SHAPES
LANDING_SHAPES="s4 s4.debug demo.debug"
# <<< LANDING_SHAPES

# ---- [logfile] (2026-09-11) ----------------------------------------------------------
# The usage line above advertised this for the script's whole life and nothing read $1: every
# run's evidence went to stdout only (measured twice on 2026-09-11). It works by RE-RUNNING
# this script with no argument and teeing that, so every path below (the refusals, the four
# shapes, the lane, the stamp) reaches the log by ONE mechanism, and the no-argument run is
# exactly what it was. The exit code is the child's (PIPESTATUS[0]), never tee's. The path is
# resolved BEFORE the `cd` below, or a relative one would land at the repo root. A log that
# cannot be written is COULD NOT RUN before anything is built: a landing whose evidence goes
# nowhere is the absence family, not a pass. tools/test_landing_build_logfile.py grades all of
# this in a sandbox with stub shapes.
if [ $# -gt 1 ] || { [ $# -eq 1 ] && [ "${1#-}" != "$1" ]; }; then
    echo "landing_build: COULD NOT RUN: usage: tools/landing_build.sh [logfile]"
    echo "finished=2"
    exit 2
fi
if [ $# -eq 1 ]; then
    case "$1" in /*) log="$1" ;; *) log="$PWD/$1" ;; esac
    if ! : 2>/dev/null > "$log"; then
        echo "landing_build: COULD NOT RUN: cannot write the logfile $log"
        echo "finished=2"
        exit 2
    fi
    "${BASH:-bash}" "$0" 2>&1 | tee "$log"
    exit "${PIPESTATUS[0]}"
fi

cd "$(dirname "$0")/.." || { echo "cannot reach the repo root"; exit 2; }

# ---- the two assembler variables (2026-09-11) --------------------------------------------
# These were `: "${SIGIL_BUILD:?...}"` expansions. A failed `:?` makes a non-interactive bash
# exit 1 with NO `finished=` stamp, so a run that died here trailed exactly like a killed one
# (the stamp at the bottom is the only thing that tells the two apart), and 1 is this
# script's "a shape FAILED" code although nothing had been built. An unset or EMPTY value
# (`:?` refused both, so this does too) is COULD NOT RUN: exit 2 with the stamp, like every
# other refusal in this file. Booked as item (b) of the side findings of the 2026-09-11
# lens-tools parcel in docs/DEFERRED_WORK.md; tools/test_landing_build_logfile.py grades it.
if [ -z "${SIGIL_BUILD:-}" ]; then
    echo "landing_build: COULD NOT RUN: SIGIL_BUILD is unset -- that is a BLOCKED report, not a workaround hunt"
    echo "finished=2"
    exit 2
fi
if [ -z "${SIGIL_EMIT:-}" ]; then
    echo "landing_build: COULD NOT RUN: SIGIL_EMIT is unset -- required for any sound-ON game, i.e. every sonic4 build"
    echo "finished=2"
    exit 2
fi

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
# The receipt that lets a later shape skip the shared lanes is THIS run's to write (below).
# One inherited from anywhere else must not reach the first shape, which is the one that
# has to run them.
unset AEON_LANDING_LANES_RECEIPT

# ---- the shape list, checked before anything is built (CTRL-3b) -----------------------
# Each shape must round-trip through build.sh's naming rule (game = s4 -> sonic4, else the
# name; .debug = DEBUG=1), so `sonic4` or `s4.debug.debug` is refused here instead of
# building something whose ROM name the rest of this script would not recognise. An empty
# list would build nothing and still print finished=0: refused too.
read -r -a SHAPES <<< "$LANDING_SHAPES"
if [ "${#SHAPES[@]}" -eq 0 ]; then
    echo "landing_build: COULD NOT RUN: LANDING_SHAPES is empty; this check would build nothing."
    echo "finished=2"
    exit 2
fi
for shape in "${SHAPES[@]}"; do
    base="${shape%.debug}"
    if [ "$base" = s4 ]; then game=sonic4; else game="$base"; fi
    rom="$base"; [ "$game" = sonic4 ] && rom=s4
    [ "$shape" != "$base" ] && rom="$rom.debug"
    case "$shape" in *[!a-z0-9_.]*) rom="" ;; esac
    if [ "$rom" != "$shape" ] || [ "$game" = s4 ]; then
        echo "landing_build: COULD NOT RUN: LANDING_SHAPES names '$shape', which is not a ROM name"
        echo "  build.sh produces (s4, s4.debug, <game>, <game>.debug)."
        echo "finished=2"
        exit 2
    fi
done

# The shared lanes run inside the first shape's build.sh, which SKIPS its pytest lane with a
# warning (not a failure) when pytest is missing; the receipt below would then claim lanes
# that never ran. So a missing pytest is COULD NOT RUN here, before anything is built.
if ! python3 -c "import pytest" 2>/dev/null; then
    echo "landing_build: COULD NOT RUN: python3 cannot import pytest, so neither the shared"
    echo "  pre-build lane nor the needs_build lane can run. A landing check without them is not one."
    echo "finished=2"
    exit 2
fi

# Where the receipt lives: outside the tree (an untracked file in it would make the land
# gate's end-of-run check read the tree as CHANGED), and gone when this run is.
LANES_DIR=$(mktemp -d "${TMPDIR:-/tmp}/aeon-landing-lanes.XXXXXX") || {
    echo "landing_build: COULD NOT RUN: cannot make a private directory for the lanes receipt"
    echo "finished=2"
    exit 2
}
trap 'rm -rf "$LANES_DIR"' EXIT
RECEIPT=""

rc=0

# shape name -> the build invocation that produces <name>.bin. Returns 0 only for a shape
# that built and left its ROM (the lanes receipt below is written on that and nothing less).
run_shape() {
    local rom="$1"; shift
    local tmp="${rom}.landing-tmp"
    # secs= on every EXIT_ line (CTRL-3, 2026-09-13): the per-shape wall clock is what the
    # "which shapes to keep" question is priced in, and it was nowhere in the log.
    local t0; t0=$(date +%s)

    rm -f "$tmp"                       # the temp, never the live artifact
    if ! ( "$@" ) ; then
        echo "EXIT_${rom}=FAILED (build command returned non-zero) secs=$(( $(date +%s) - t0 ))"
        rc=1
        return 1
    fi

    # build.sh writes <rom>.bin in place; move it aside atomically only once complete.
    if [ ! -f "${rom}.bin" ]; then
        # Loud on unmeasurable: a missing artifact is "did not run", never a verdict.
        echo "EXIT_${rom}=NO_ARTIFACT (${rom}.bin absent after a zero-exit build) secs=$(( $(date +%s) - t0 ))"
        rc=1
        return 1
    fi
    mv -f "${rom}.bin" "$tmp" && mv -f "$tmp" "${rom}.bin"
    echo "EXIT_${rom}=0 size=$(stat -c %s "${rom}.bin") secs=$(( $(date +%s) - t0 ))"
    return 0
}

# The provenance instant for the needs_build lane at the bottom: every artifact it grades
# must post-date this, i.e. must have been written by one of the shapes below. Taken
# from `date +%s` for the reason build.sh's SIGIL_T0 is -- whole seconds truncate DOWN, so
# a file written in the same second still counts as fresh. Since LS-1a (2026-09-12) it is
# BOTH claims: the lane's conftest asks tools/artifact_provenance.py, which calls a pair
# fresh only when it was written after T0 ("this run wrote the file") AND its listing's
# Source Digest reproduces ("the file matches the sources it was built from"). A pair that
# fails either is DEFERRED, which this lane reports as exit 2.
T0=$(date +%s)

# ---- the land gate (CTRL-3, 2026-09-13) -----------------------------------------------
# A completed green run of an unmoved, clean tree writes a STAMP keyed by the content of
# every code path (tools/land_gate.py, "THE STAMP IS KEYED BY CONTENT"). The pre-push hook
# (tools/hooks/pre-push) refuses a push to master whose code has no stamp. This block and
# the one above `finished=` are the only writers, so the stamp means exactly "this script
# finished 0 over this code". It changes nothing about what is built or graded, and the
# exit code only in one case: HEAD or a code path MOVED under the run, which is COULD NOT
# RUN (2), because nothing the run printed then describes any commit. A tree that is not
# a git repository, or has no tools/land_gate.py, is UNMEASURABLE: no stamp, same verdict.
G_HEAD=unmeasurable; G_KEY=unmeasurable; G_CLEAN=0
gate_begin=$(python3 tools/land_gate.py begin 2>&1)
printf '%s\n' "$gate_begin" | grep -v '^LAND_GATE_START '
gate_start=$(printf '%s\n' "$gate_begin" | grep '^LAND_GATE_START ' | tail -1)
if [ -n "$gate_start" ]; then
    read -r _ G_HEAD G_KEY G_CLEAN <<<"$gate_start"
else
    echo "land-gate: UNMEASURABLE at start (tools/land_gate.py did not answer): this run will write no stamp"
fi

{
    echo "landing_build: shapes this check builds, in order: ${SHAPES[*]} (LANDING_SHAPES)"
    for shape in "${SHAPES[@]}"; do
        base="${shape%.debug}"
        cmd=(env)
        [ "$shape" != "$base" ] && cmd+=(DEBUG=1)
        [ -n "$RECEIPT" ] && cmd+=("AEON_LANDING_LANES_RECEIPT=$RECEIPT")
        cmd+=(./build.sh)
        [ "$base" != s4 ] && cmd+=("$base")
        # The first shape that exits 0 without a receipt ran the shared lanes green (they are
        # build-fatal inside build.sh, pytest is importable, FAST/NO_LINT are refused above and
        # no -nl is passed). Only then is the receipt written; every later shape carries it.
        if run_shape "$shape" "${cmd[@]}" && [ -z "$RECEIPT" ]; then
            if printf 'landing_pid=%s\ncarrier=%s\nlanes=passed\n' "$$" "$shape" \
                    > "$LANES_DIR/receipt"; then
                RECEIPT="$LANES_DIR/receipt"
                echo "--- shared lanes: ran ONCE, green, inside the $shape build; the shapes after it skip them on a receipt ---"
            else
                echo "--- shared lanes: the receipt could not be written, so the shapes after $shape run them again ---"
            fi
        fi
    done

    echo "--- md5 (quote these WITH the assembler revision beside them; a CRC alone is"
    echo "--- meaningless across sessions because the toolchain is the one unpinned input) ---"
    md5sum "${SHAPES[@]/%/.bin}" 2>&1
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
    # into one ${SIGIL_BUILD} build). So it DEFERS in every build.sh shape and, until LS-1c,
    # ran nowhere except tools/nightly_effects_gates.sh -- once a day, after the merge.
    #
    # It belongs HERE and not in build.sh, re-checked rather than inherited: build.sh
    # builds one game per invocation and every other gate in it depends on that contract.
    # This script is already the multi-shape caller and the landing lane nobody merges past.
    # The lane costs one pytest run on artifacts that are already on disk.
    #
    # THE SHAPES IT DOES NOT BUILD ARE DECLARED, NOT FORGIVEN (CTRL-3b). Under A this script
    # does not build demo normal, so test_deb2_appendix[demo.bin] defers here by design. The
    # lane is handed LANDING_SHAPES with --shapes-built and derives the exemption itself:
    # BUILD_ARTIFACTS minus the listed shapes' .bin/.lst, printed, with every case it exempts
    # named as EXEMPTED. A deferral on anything a listed shape writes is still COULD NOT RUN,
    # so the segments parent (s4.debug + demo.debug, both built under A) still RUNS here.
    #
    # IT IS A TOOL AND NOT AN INLINE `python3 -m pytest`, for the reason
    # tools/needs_build_lane.py's header gives: pytest exits 0 when every test it collected
    # was SKIPPED, which is precisely the state this lane exists to catch. The verdict is
    # read out of a JUnit report instead. The only deferrals legitimate here are the declared
    # exemption above; any other is exit 2, COULD NOT RUN.
    #
    # NOT RUN AFTER A FAILED BUILD: the lane would then defer on the shape that did not
    # write, and report COULD NOT RUN on top of a real build failure, burying it. The skip
    # is printed by name and rc is already non-zero, so it is never a silent pass.
    if [ "$rc" = 0 ]; then
        echo "--- needs_build lane (--built-after $T0) ---"
        python3 tools/needs_build_lane.py --built-after "$T0" --shapes-built "${SHAPES[@]}"
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

# The land gate's stamp (CTRL-3): written only here, only for finished=0 over a tree that
# was clean at the start and did not move. See the block above T0.
if [ "$G_HEAD" != unmeasurable ]; then
    python3 tools/land_gate.py finish --head "$G_HEAD" --key "$G_KEY" --clean "$G_CLEAN" \
        --rc "$rc" --sigil "$SIGIL_BUILD" 2>&1
    frc=$?
    if [ "$frc" = 3 ]; then
        echo "landing_build: COULD NOT RUN: the tree moved under this run (above), so nothing it"
        echo "  printed describes a commit. Re-run on a tree nothing else is writing to."
        rc=2
    elif [ "$frc" != 0 ] && [ "$frc" != 1 ]; then
        echo "land-gate: finish exited $frc: NO STAMP"
    fi
else
    echo "land-gate: NO STAMP: the start could not be measured"
fi

# The stamp is the only thing that distinguishes a completed run from a vanished one:
# in a log they trail IDENTICALLY. Keep the NUMBER, not just the fact -- 137 vs 143
# separates a hard reclaim from a polite one.
echo "finished=$rc"
exit "$rc"
