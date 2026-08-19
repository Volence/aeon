#!/usr/bin/env bash
# Nightly backstop for the emulator-backed effects gate lane (owner ruling
# 2026-08-18: ritual + nightly). The ritual half lives in CLAUDE.md's Testing
# section; this is the half that fires when the ritual gets skipped.
#
# Runs against current aeon master in a DETACHED checkout at
# ~/sonic_hacks/.aeon-nightly so it never races an overnight session or the
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

MAIN=/home/volence/sonic_hacks/aeon
NIGHTLY=/home/volence/sonic_hacks/.aeon-nightly
STATE=${XDG_STATE_HOME:-$HOME/.local/state}/aeon-nightly
LOG="$STATE/nightly.log"
mkdir -p "$STATE"

export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob

note() {
    echo "$(date -Is) $1" >> "$LOG"
    notify-send -u critical "aeon effects gates" "$1" 2>/dev/null || true
}

if [[ ${1:-} == --selftest-fail ]]; then
    note "SELFTEST: the failure-notification path works"
    exit 1
fi

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

python3 tools/effects_gates.py --rom s4.debug.bin --lst s4.debug.lst \
    > "$STATE/gates.log" 2>&1
rc=$?
case $rc in
    0) echo "$(date -Is) OK at ${SHA:0:8} (all gates pass)" >> "$LOG" ;;
    1) note "EFFECTS GATES FAILED at ${SHA:0:8} — see $STATE/gates.log" ;;
    *) note "COULD NOT RUN: gate setup problem (exit $rc) at ${SHA:0:8} — see $STATE/gates.log" ;;
esac
exit $rc
