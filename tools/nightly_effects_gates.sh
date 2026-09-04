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

# worst-wins: 2 (could not run) beats 1 (failed) beats 0
worst=0
for r in "$rc" "$rc_lab"; do
    if [ "$r" = 2 ] || { [ "$r" != 0 ] && [ "$worst" != 2 ]; }; then
        [ "$r" = 2 ] && worst=2 || worst=1
    fi
done
exit $worst
