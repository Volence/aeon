#!/usr/bin/env bash
# Nightly keepalive for the bus instruments nothing else runs.
#
# THE DEFECT: a channel that cannot report is indistinguishable from a channel reporting
# nothing wrong. tools/parallax_hscroll_probe.py crashed on startup from 2026-08-26 until
# it was found on 2026-09-18, and the crash was hiding 35 findings.
# tools/parallax_hscroll_identity.py had not run since 2026-08-29. Both are bus
# instruments that nothing executes. This lane executes them.
#
# ⚠ WHAT "EXECUTES THEM" COVERS, MEASURED 2026-09-19 (parcel KEEPALIVE-DEFAULT-ARGS).
# It is one invocation per tool, not a tool's whole surface, and the difference is
# enumerated rather than left to the reader:
#
#     35 wired instruments, and all 35 are in the census's "nothing else runs this" set.
#     28 of them have surface this invocation does not set, over 90 options. Of those:
#        38 options gate 241 lines whose DEFAULT leaves them unexecuted -- never run here
#         1 selector reaches 1 of its 5 subjects (lens_residue_raster_witness efx4b)
#         1 tool takes another TOOL as its subject and is pointed at 1 of 85
#             (transition_window_probe)
#         3 tools also take input from os.environ, which no argv can reach
#             (PB_ROM/PB_LST, RAMP_WITNESS_TREE, SHIM_OUT)
#
# tools/keepalive_surface.py re-derives that split from the parsers and the code on
# demand. A 20-arm sample of the unreached surface was run on 2026-09-19 against
# s4.debug.bin crc32 62238a15 and found 0 dead -- so this is a stated LIMIT of the lane's
# reach, not a backlog of known-broken arms.
#
# WHY A NIGHTLY AND NOT build.sh. The cost is ~30 s per instrument because there is no
# observation short of EXECUTION that distinguishes a dead instrument from a quiet one
# (a --help smoke over all 85 costs 7.9 s, catches NEITHER real defect, and has a 9%
# false-positive rate -- measured by the DEAD-INSTRUMENT-PAIR parcel, 2026-09-18). Tens
# of minutes does not belong in a build. It belongs exactly where the effects gates live,
# and this file is deliberately shaped like tools/nightly_effects_gates.sh.
#
# EXIT CONTRACT, and it is the whole point:
#     0  every wired instrument exited its DECLARED BASELINE status
#     1  FAILED       -- an instrument ran and reported something other than its baseline
#     2  COULD NOT RUN -- an instrument could not reach a verdict at all, OR the lane's
#                         declared population and the tree have diverged
# 2 outranks 1 in the worst-wins fold, same as the effects gates. Collapsing COULD NOT RUN
# into FAILED buries a dead instrument among real failures; collapsing it into PASSED
# recreates the original defect inside the fix.
#
# ⚠ SOME INSTRUMENTS ARE RED TODAY AND THAT IS DECLARED, NOT BROKEN.
# tools/keepalive_manifest.toml records each ROW's CURRENT honest exit status as its
# baseline -- three rows are `expect = 1` on 2026-09-19 (loop_step_over_witness,
# sprite_owner_probe, waterline_art_witness), each for a reason its note states. The lane
# reports a baseline-1 row that starts exiting 0 as FAILED, on purpose: otherwise the
# cheapest way to green this lane would be to weaken an instrument until it stops
# complaining, which would make it a machine for hiding exactly what it exists to surface.
# (This paragraph named parallax_hscroll_identity and "three deliberate stale-fixture reds"
# until 2026-09-19, when IDENTITY-FIXTURE-RULING settled them and its baseline went to 0.)
#
# ⚠ A BASELINE BELONGS TO A ROW, AND A ROW IS AN INVOCATION. A manifest key is `tool.py`
# or `tool.py#arm-label`, and a non-zero `expect` must carry `baseline_args` equal to that
# row's own `args` -- so a red measured on one arm cannot grade a different one. A row
# whose baseline does not describe its own argv is COULD NOT RUN, which lands here as
# exit 2.
#
# --selftest-fail exercises the notification path without running anything.
# --checkout-only resolves and checks out the target and exits, for testing this file.
set -uo pipefail

# Every path DERIVED from this script's location, never baked to one machine's $HOME
# (SUITE-HOME-PATHS, 2026-08-30). MAIN is resolved through --git-common-dir because this
# file may be running from a worktree copy.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN="$(dirname "$(git -C "$HERE" rev-parse --path-format=absolute --git-common-dir)")" \
    || { echo "keepalive: $HERE is not inside a git checkout"; exit 2; }
SUITE="$(dirname "$MAIN")"
# Its OWN checkout, not .aeon-nightly: this lane and the effects nightly must be able to
# run without one's build rewriting the tree the other is measuring.
NIGHTLY="$SUITE/.aeon-keepalive-nightly"
STATE=${XDG_STATE_HOME:-$HOME/.local/state}/aeon-keepalive
LOG="$STATE/keepalive.log"
RUNLOG="$STATE/lane.log"
TOOLLOGS="$STATE/tools"
mkdir -p "$STATE"

export SIGIL_BUILD="$SUITE/sigil/target/release/sigil"
export SIGIL_EMIT="$SUITE/sigil/target/release/emit_sound_blob"

note() {
    echo "$(date -Is) $1" >> "$LOG"
    notify-send -u critical "aeon instrument keepalive" "$1" 2>/dev/null || true
}

if [[ ${1:-} == --selftest-fail ]]; then
    note "SELFTEST: the failure-notification path works"
    exit 1
fi
CHECKOUT_ONLY=0
[[ ${1:-} == --checkout-only ]] && CHECKOUT_ONLY=1

for b in "$SIGIL_BUILD" "$SIGIL_EMIT"; do
    [ -x "$b" ] || { note "COULD NOT RUN: no sigil binary at $b (suite root $SUITE)"; exit 2; }
done

# ---- what to test: origin/master, fetched now --------------------------------------
# Every landing in this repo is PUSHED, so origin/master is what "landed" means. A FAILED
# FETCH IS COULD NOT RUN: there is deliberately no fallback to the on-disk ref, which is
# exactly as stale as the last successful fetch, and grading that under an OK line is the
# defect this whole file is about.
if ! GIT_TERMINAL_PROMPT=0 timeout 300 git -C "$MAIN" fetch --quiet origin \
        "+refs/heads/master:refs/remotes/origin/master" >> "$LOG" 2>&1; then
    note "COULD NOT RUN: git fetch of origin master failed in $MAIN; refusing to grade a possibly-stale ref -- see $LOG"
    exit 2
fi
SHA=$(git -C "$MAIN" rev-parse --verify --quiet "refs/remotes/origin/master^{commit}") \
    || { note "COULD NOT RUN: origin/master does not resolve in $MAIN after the fetch"; exit 2; }
AT="origin/master ${SHA:0:8}"

if [[ ! -d "$NIGHTLY" ]]; then
    git -C "$MAIN" worktree add --detach "$NIGHTLY" "$SHA" >> "$LOG" 2>&1 \
        || { note "COULD NOT RUN: keepalive worktree creation at $AT failed"; exit 2; }
fi
git -C "$NIGHTLY" checkout --force --detach "$SHA" >> "$LOG" 2>&1 \
    || { note "COULD NOT RUN: checkout of $AT failed"; exit 2; }

if [[ $CHECKOUT_ONLY == 1 ]]; then
    echo "$SHA"
    exit 0
fi

cd "$NIGHTLY" || { note "COULD NOT RUN: cannot enter $NIGHTLY"; exit 2; }

# ---- the ROM these instruments measure ----------------------------------------------
# Built here rather than borrowed: every instrument is pointed at ONE artifact, and the
# lane prints its crc32, so a verdict names the thing it graded. A build failure is COULD
# NOT RUN -- no instrument can report on a ROM that does not exist.
if ! DEBUG=1 ./build.sh > "$STATE/build.log" 2>&1; then
    note "COULD NOT RUN: DEBUG build failed at $AT -- see $STATE/build.log"
    exit 2
fi

rm -rf "$TOOLLOGS"
python3 tools/keepalive_lane.py \
        --rom "$NIGHTLY/s4.debug.bin" --lst "$NIGHTLY/s4.debug.lst" \
        --logdir "$TOOLLOGS" > "$RUNLOG" 2>&1
rc=$?

# The counts, straight out of the lane's own summary, so the notification says WHAT rather
# than only THAT. Aggregate totals -- never a tail excerpt.
SUMMARY=$(grep -E "^  (PASSED|FAILED|COULD NOT RUN) " "$RUNLOG" | tr -s ' ' | paste -sd' ' -)
POP=$(grep -E "^  (bus instruments|declared in the manifest|wired INVOCATIONS|unexecuted AND not wired)" "$RUNLOG" | tr -s ' ' | paste -sd' | ' -)
FINISHED=$(grep -E "^finished=" "$RUNLOG" | tail -1)

case $rc in
    0) echo "$(date -Is) OK at $AT ($SUMMARY; $POP; $FINISHED)" >> "$LOG" ;;
    1) note "INSTRUMENT KEEPALIVE: an instrument FAILED at $AT -- $SUMMARY -- see $RUNLOG and $TOOLLOGS" ;;
    2) note "INSTRUMENT KEEPALIVE: an instrument COULD NOT RUN (or the population drifted) at $AT -- $SUMMARY -- see $RUNLOG and $TOOLLOGS" ;;
    *) note "COULD NOT RUN: the keepalive lane itself exited $rc at $AT -- see $RUNLOG" ;;
esac
exit $rc

# =====================================================================================
#  HOW THIS WOULD BE ARMED -- NOT ARMED HERE. Arming is the owner's, deliberately.
# =====================================================================================
#  Two systemd USER units, the same shape as aeon-effects-gates.{service,timer}:
#
#    ~/.config/systemd/user/aeon-instrument-keepalive.service
#        [Unit]
#        Description=aeon bus-instrument keepalive
#        [Service]
#        Type=oneshot
#        ExecStart=<the aeon checkout>/tools/nightly_instrument_keepalive.sh
#        # ^ spell the absolute path to THIS file, wherever the aeon checkout lives:
#        #     systemctl --user edit --full aeon-instrument-keepalive.service
#        #   The script derives every other path from its own location, so this is the
#        #   only place the unit has to know where anything is.
#
#    ~/.config/systemd/user/aeon-instrument-keepalive.timer
#        [Unit]
#        Description=nightly aeon bus-instrument keepalive
#        [Timer]
#        OnCalendar=*-*-* 04:30:00
#        Persistent=true
#        [Install]
#        WantedBy=timers.target
#
#    systemctl --user daemon-reload
#    systemctl --user enable --now aeon-instrument-keepalive.timer
#
#  ⚠ PICK AN HOUR THAT DOES NOT COLLIDE WITH aeon-effects-gates.timer. Both build a ROM
#    and both boot headless emulators; overlapping them puts each one's timings under the
#    other's load, and this lane's per-instrument timeouts are sized against a measured
#    load average, not an idle machine. 04:30 above assumes the effects gates run earlier;
#    check `systemctl --user list-timers` before choosing.
#
#  Verify the notification path without waiting for a night:
#      tools/nightly_instrument_keepalive.sh --selftest-fail   # expect exit 1 + a toast
