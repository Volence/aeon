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
exit $rc
