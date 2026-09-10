#!/usr/bin/env bash
# Nightly backstop for the emulator-backed effects gate lane (owner ruling
# 2026-08-18: ritual + nightly). The ritual half lives in CLAUDE.md's Testing
# section; this is the half that fires when the ritual gets skipped.
#
# Runs against current aeon master in a DETACHED checkout at
# <suite root>/.aeon-nightly so it never races an overnight session or the
# auto-commit daemon in the main tree, and never appears inside the main
# repo directory (a worktree under the repo root double-counts every module
# in tools/emp_helper_closure.py's tree scan).
#
# Exit-code contract mirrors effects_gates.py: a lane FAILURE and a lane that
# COULD NOT RUN are both loud — a backstop that silently can't run is the
# vacuous-gate pattern this exists to prevent.
#
# IT ALSO RUNS THE `needs_build` PYTEST LANE (LS-1b, 2026-09-06), and that is why
# it builds FOUR shapes rather than two — every shape build.sh can produce, which is
# what makes the covering claim below structural instead of remembered (LS-1c,
# 2026-09-10; it was THREE, and the drift cost three red nights). It no longer OWNS
# that lane: tools/merge_lane.sh runs the same lane over the same four shapes at merge
# time, so a parcel is graded before it lands rather than the next morning. This stays
# as the backstop for a parcel that skipped the ritual. LS-1 moved the tests that read a build
# artifact into a post-sigil lane inside build.sh; one of them —
# test_segmented_parent_checks_the_row_set_it_aggregated — declares s4.debug.bin,
# s4.debug.lst AND demo.debug.lst, and one build.sh invocation writes exactly one
# game's .bin/.lst pair, so it defers in every shape and stopped running anywhere.
# It is the exact test whose failure killed this nightly nine times. This script is
# the only place several shapes are built back to back in one checkout, so it is the
# only place the whole marked lane is reachable — and the release shape is built here
# purely so the fourth marked test (s4.lst) is reachable too. The rule that keeps the
# lane honest is that ZERO deferrals are legitimate HERE: every artifact the marked
# tests declare is built by this script, so a deferral means a build did not write
# what it was supposed to, and tools/needs_build_lane.py calls that COULD NOT RUN.
# Do NOT "fix" this by adding a second game's build to build.sh: one invocation
# builds one game, and that is the contract every other gate in it depends on.
#
# --selftest-fail exercises the notification path without running anything.
set -uo pipefail

# Every path below is DERIVED from this script's own location, never baked to one
# machine's $HOME (SUITE-HOME-PATHS, 2026-08-30). MAIN is resolved through
# --git-common-dir rather than `dirname $0`/..: this file may be running from a
# worktree copy, and the whole point of NIGHTLY is that it is cut from the MAIN
# checkout's master.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN="$(dirname "$(git -C "$HERE" rev-parse --path-format=absolute --git-common-dir)")" \
    || { echo "nightly: $HERE is not inside a git checkout"; exit 2; }
SUITE="$(dirname "$MAIN")"
NIGHTLY="$SUITE/.aeon-nightly"
STATE=${XDG_STATE_HOME:-$HOME/.local/state}/aeon-nightly
LOG="$STATE/nightly.log"
mkdir -p "$STATE"

export SIGIL_BUILD="$SUITE/sigil/target/release/sigil"
export SIGIL_EMIT="$SUITE/sigil/target/release/emit_sound_blob"
note() {
    echo "$(date -Is) $1" >> "$LOG"
    notify-send -u critical "aeon effects gates" "$1" 2>/dev/null || true
}

if [[ ${1:-} == --selftest-fail ]]; then
    note "SELFTEST: the failure-notification path works"
    exit 1
fi

# A derived path that resolves to nothing must say so HERE, naming the file. Without
# this the nightly reports "DEBUG build failed", which is loud but points at the ROM.
for b in "$SIGIL_BUILD" "$SIGIL_EMIT"; do
    [ -x "$b" ] || { note "COULD NOT RUN: no sigil binary at $b (suite root $SUITE)"; exit 2; }
done

if [[ ! -d "$NIGHTLY" ]]; then
    git -C "$MAIN" worktree add --detach "$NIGHTLY" master >> "$LOG" 2>&1 \
        || { note "COULD NOT RUN: nightly worktree creation failed"; exit 2; }
fi

SHA=$(git -C "$MAIN" rev-parse master)
git -C "$NIGHTLY" checkout --force --detach "$SHA" >> "$LOG" 2>&1 \
    || { note "COULD NOT RUN: checkout of master ($SHA) failed"; exit 2; }

cd "$NIGHTLY"
# The provenance instant for the needs_build lane below: every artifact it grades must
# have been written AFTER this, i.e. by one of the three builds that follow. Taken from
# `date +%s` for the reason build.sh's SIGIL_T0 is — whole seconds truncate DOWN, so a
# file written in the same second still counts as fresh. It is a PROVENANCE claim ("this
# run wrote the file") and not a content one ("the file matches the source"); nothing
# here checks the second, and the tests themselves are what ask about content.
BUILD_T0=$(date +%s)
if ! DEBUG=1 ./build.sh > "$STATE/build.log" 2>&1; then
    note "COULD NOT RUN: DEBUG build failed at ${SHA:0:8} — see $STATE/build.log"
    exit 2
fi
# Second fixture: the P2 Phase 1 span/witness gates are two-fixture differentials
# (sonic4 vs demo) and hard-error without demo.debug.lst — a one-fixture run is
# not the gate. First bit the nightly 2026-08-19, the night Phase 1 landed.
if ! DEBUG=1 ./build.sh demo >> "$STATE/build.log" 2>&1; then
    note "COULD NOT RUN: DEBUG demo build failed at ${SHA:0:8} — see $STATE/build.log"
    exit 2
fi
# Third fixture, and it is NOT for the emulator gates — they run against s4.debug.*.
# It exists so `s4.lst` is on disk and fresh, which is the one artifact the fourth
# needs_build test (tools/test_bg_emit.py) declares. Without it that test defers, the
# needs_build lane reports COULD NOT RUN, and this script would be red every night for
# a shape it simply never built. Building it is cheaper and more honest than teaching
# the lane which deferrals to forgive — an expected deferral is a silent skip wearing
# a label, which is the thing LS-1 was about. It also means the RELEASE shape, the one
# that ships, gets built nightly for the first time.
if ! ./build.sh >> "$STATE/build.log" 2>&1; then
    note "COULD NOT RUN: release build failed at ${SHA:0:8} — see $STATE/build.log"
    exit 2
fi
# Fourth fixture, and it is a REPAIR (LS-1c, 2026-09-10). The three shapes above were
# chosen on 2026-09-06, when four tests carried @pytest.mark.needs_build and those three
# covered every artifact they declared. On 2026-09-07 tools/test_deb2_appendix.py
# parametrized the marker over all four build shapes, adding the PLAIN demo pair
# (demo.bin / demo.lst) that no shape here built. From the next night the needs_build lane
# below reported COULD NOT RUN — measured in this script's own state log, three nights
# running (2026-09-08 4557b939, 2026-09-09 37e543c2, 2026-09-10 d3b01f07), each with
# `...[demo.bin] (demo.bin (absent), demo.lst (absent))  1 deferred` — while the header
# above still asserted that every declared artifact is built here. A hand-written shape
# list drifts under a growing marker population and nothing could see it.
# The list is no longer trusted: tools/test_merge_lane_shapes.py derives the declared set
# from the markers actually in the tree, derives this script's shape set from the
# invocations actually in this file, and fails in build.sh's PRE-build lane if the second
# does not cover the first. With this build the four shapes here are the four build.sh can
# produce, so the covering claim is now structural rather than remembered.
if ! ./build.sh demo >> "$STATE/build.log" 2>&1; then
    note "COULD NOT RUN: release demo build failed at ${SHA:0:8} — see $STATE/build.log"
    exit 2
fi

python3 tools/effects_gates.py --rom s4.debug.bin --lst s4.debug.lst \
    > "$STATE/gates.log" 2>&1
rc=$?
case $rc in
    0) echo "$(date -Is) OK at ${SHA:0:8} (all gates pass)" >> "$LOG" ;;
    1) note "EFFECTS GATES FAILED at ${SHA:0:8} — see $STATE/gates.log" ;;
    *) note "COULD NOT RUN: gate setup problem (exit $rc) at ${SHA:0:8} — see $STATE/gates.log" ;;
esac

# ---- second lane: the effects LAB itself -------------------------------------
# The lab is the instrument the owner reviews effects THROUGH, so a lab that has
# silently stopped installing (or stopped telling the truth about what it installed)
# costs a review session before anyone notices. It rides here rather than in build.sh
# for the same reason the gates do: it boots a headless emulator.
#
# It cannot be wired anywhere cheaper. The two older lab tiers each carry a `dc.l`
# table and a pytest lint that counts its rows; this tier has NO table — its cycle
# list is the act's own section grid — so there is nothing textual to lint and the
# only question left is a runtime one.
#
# SAME EXIT CONTRACT, and it is combined WORST-WINS: a lane that could not run (2)
# outranks a lane that failed (1). A backstop that reports the gates' green while its
# own lane refused to run is the vacuous pattern this file exists to prevent.
python3 tools/preset_lab_witness.py --rom s4.debug.bin --lst s4.debug.lst \
    > "$STATE/preset_lab.log" 2>&1
rc_lab=$?
case $rc_lab in
    0) echo "$(date -Is) OK at ${SHA:0:8} (preset lab witness)" >> "$LOG" ;;
    1) note "PRESET LAB WITNESS FAILED at ${SHA:0:8} — see $STATE/preset_lab.log" ;;
    *) note "COULD NOT RUN: preset lab witness (exit $rc_lab) at ${SHA:0:8} — see $STATE/preset_lab.log" ;;
esac

# ---- third lane: the needs_build pytest lane (LS-1b) --------------------------
# The tests LS-1 moved below the sigil build. Three of the four are reachable from a
# build.sh shape; the segments parent is reachable from NONE, because it declares a
# DEBUG sonic4 and a DEBUG demo at once. Here all three shapes have just been built,
# so all four run — and `--built-after $BUILD_T0` makes that a claim rather than a
# hope: an artifact left over from a previous night is DEFERRED exactly as an absent
# one is, and a deferral here is exit 2.
#
# SAME EXIT CONTRACT, same worst-wins combination as the two lanes above. It is a tool
# and not an inline `python3 -m pytest` for one reason: pytest exits 0 when every test
# it collected was SKIPPED, so an inline invocation would report this lane green in
# precisely the state the lane exists to catch. tools/needs_build_lane.py reads the
# verdict out of a JUnit report instead, and its own arms are gated by
# tools/test_needs_build_lane.py in build.sh's pre-build lane.
python3 tools/needs_build_lane.py --built-after "$BUILD_T0" \
    > "$STATE/needs_build.log" 2>&1
rc_nb=$?
case $rc_nb in
    0) echo "$(date -Is) OK at ${SHA:0:8} (needs_build lane)" >> "$LOG" ;;
    1) note "NEEDS_BUILD TESTS FAILED at ${SHA:0:8} — see $STATE/needs_build.log" ;;
    *) note "COULD NOT RUN: needs_build lane (exit $rc_nb) at ${SHA:0:8} — see $STATE/needs_build.log" ;;
esac

# worst-wins: 2 (could not run) beats 1 (failed) beats 0
worst=0
for r in "$rc" "$rc_lab" "$rc_nb"; do
    if [ "$r" = 2 ] || { [ "$r" != 0 ] && [ "$worst" != 2 ]; }; then
        [ "$r" = 2 ] && worst=2 || worst=1
    fi
done
exit $worst
