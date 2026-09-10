#!/usr/bin/env bash
# freeze_preflight — the WHOLE pre-flight before `refreeze --freeze`, as ONE command.
#
# WHY THIS IS A SCRIPT AND NOT TWO LINES IN OVERSEER-REFERENCE.md (the landing lane, moved
# out of the boot read 2026-09-10). The pre-flight has always had two
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
# ⚠ THE SUBJECT IS RESOLVED FROM THIS SCRIPT'S LOCATION, AND THAT IS NOT WHERE YOU ARE
# FREEZING FROM (found 2026-09-02, chain 199, after it cost two hours and three wrong stories).
# `$(dirname $(dirname $HERE))/sigil` is the SHARED MAIN CHECKOUT. Every landing in this lane
# runs from a dedicated worktree, because the lane's own rules require it — so unless SIGIL_DIR
# is set, THIS GATE TESTS A TREE THAT DOES NOT CONTAIN THE PARCEL BEING FROZEN, and it says
# nothing about that while doing it. Measured that day: the composition under test appeared 0
# times in the main checkout's pins.rs and once in the landing worktree, so every red was a
# TRUE report about the WRONG SUBJECT. Two further consequences, both worse than the reds:
#   · `cargo test` in the shared checkout RELINKS target/release/sigil, the binary other lanes
#     pin their freezes against. The gate presented as the mandatory pre-freeze ritual was the
#     single biggest relinker on the machine. A peer's rule forbidding "ad-hoc cargo here" did
#     not bind it, because a committed ritual is not ad-hoc — the rule was written one level
#     below its defect.
#   · "the gate was skipped" and "the gate ran and could not see the subject" leave IDENTICAL
#     evidence, so the first is the story everyone reaches for. Chain 198's red was blamed on a
#     skipped pre-flight in a commit message and a committed lane-log entry before this was
#     found. Prefer the explanation that a green could have distinguished.
# So: the tree is PRINTED before anything runs, and an unset SIGIL_DIR says so loudly. It is a
# banner and not a refusal on purpose — freezing from the main checkout is a legitimate run, and
# a refusal that can fire on a correct case is worse than the silence it replaces.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIGIL="${SIGIL_DIR:-$(dirname "$(dirname "$HERE")")/sigil}"
[ -d "$SIGIL" ] || { echo "freeze_preflight: no sigil tree at $SIGIL (set SIGIL_DIR)"; exit 2; }

# ⚠ THE OTHER TREE. THIS SCRIPT HAS TWO SUBJECTS AND ONLY ONE OF THEM WAS EVER NAMED
# (found 2026-09-09, LS-17, and it is the SIGIL_DIR defect above one level over).
# Both cargo runs below are REFERENCE-DEPENDENT on an aeon tree: sigil resolves it from
# `AEON_DIR` and falls back to its own sibling default, so a pre-flight launched without
# `AEON_DIR` in the environment measures the SIBLING MAIN CHECKOUT while the operator
# believes it measured the tree they are freezing. It then CLASSIFIES that result.
# Lived: step 1 stopped with "failed for a reason that is NOT staleness"; re-run with
# `AEON_DIR` pointed at the landing tree, the panic was `src/pins.rs is STALE against the
# live listings` — the exact string the grep below looks for, and the EXPECTED state for a
# byte-mover. A true measurement of the wrong tree, carried forward as a false reason.
# OVERSEER-REFERENCE.md's clean-checkout rule already says the checkout must be threaded through ALL
# THREE legs explicitly; the pre-flight is the suite leg, and it is the one nobody threaded.
# So resolve it HERE, EXPORT it (both cargo runs inherit it — the thread cannot be half
# done), and print it beside the sigil tree.
# The default is THIS SCRIPT'S OWN CHECKOUT, not a sibling: you run <tree>/tools/freeze_preflight.sh
# from the tree you are freezing, so the script's location is the better guess. It is still
# only a guess — an unset AEON_DIR says so as loudly as an unset SIGIL_DIR, and for the same
# reason it is a banner and not a refusal: freezing from the main tree is a legitimate run.
AEON_DIR_WAS_SET="${AEON_DIR:-}"   # captured BEFORE the export below overwrites the answer
AEON="${AEON_DIR:-$(dirname "$HERE")}"
[ -d "$AEON" ] || { echo "freeze_preflight: no aeon tree at $AEON (set AEON_DIR)"; exit 2; }
AEON="$(cd "$AEON" && pwd)"
export AEON_DIR="$AEON"
cd "$SIGIL" || exit 2

echo "freeze_preflight: SUBJECTS — every result below is about THESE TWO trees and no others:"
echo "    sigil tree $SIGIL"
echo "    HEAD       $(git rev-parse HEAD 2>/dev/null || echo '(not a git tree)')"
echo "    branch     $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')   dirty: $(git status --porcelain 2>/dev/null | wc -l) path(s)"
if [ -z "${SIGIL_DIR:-}" ]; then
    echo "    ⚠ SIGIL_DIR is UNSET, so this is the DEFAULT path, not a tree you chose."
    echo "      If you are freezing from a worktree, set SIGIL_DIR to it and re-run —"
    echo "      otherwise this gate cannot see your parcel and will report on the wrong tree."
fi
echo "    aeon tree  $AEON   (exported as AEON_DIR to BOTH runs below)"
echo "    HEAD       $(git -C "$AEON" rev-parse HEAD 2>/dev/null || echo '(not a git tree)')"
echo "    branch     $(git -C "$AEON" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')   dirty: $(git -C "$AEON" status --porcelain 2>/dev/null | wc -l) path(s)"
# BUILT SHAPES, informational. Read from sigil's own test sources: a reference-dependent
# port test whose ROM is absent prints `skip: reference ROM not at ...` and passes. Four
# present is what a step-2 green is worth reading; fewer means some of it was vacuous.
AEON_ROMS=""
for r in s4.bin s4.debug.bin demo.bin demo.debug.bin; do
    [ -f "$AEON/$r" ] && AEON_ROMS="$AEON_ROMS $r" || AEON_ROMS="$AEON_ROMS -$r"
done
echo "    shapes    $AEON_ROMS   (a leading '-' is ABSENT; the gates that read it SKIP GREEN)"
if [ -z "${AEON_DIR_WAS_SET:-}" ]; then
    echo "    ⚠ AEON_DIR was UNSET, so the aeon tree above is DERIVED FROM THIS SCRIPT'S"
    echo "      LOCATION, not a tree you chose. If you are freezing a different checkout,"
    echo "      set AEON_DIR to it and re-run — otherwise step 1 will classify a result it"
    echo "      measured somewhere else, which is exactly what it did on 2026-09-09."
fi
echo

echo "freeze_preflight: step 1/2 — repin_pins (read-only staleness discriminator)"
if cargo test --release -p sigil-harness --test repin_pins 2>&1 | tee /tmp/fp_repin.$$ | tail -3; then
    PINS_CURRENT=1
    echo "  pins are CURRENT — any port failure below is the CROSS-SEAM class and is REAL"
else
    PINS_CURRENT=0
    if grep -q "is STALE against the live listings" /tmp/fp_repin.$$; then
        echo "  pins are STALE (expected for a byte-mover) — port failures below are"
        echo "  STALE-INSTRUMENT and the freeze's repin step clears them"
        # The matching arm ships its evidence for the same reason the else-branch does: a
        # correct verdict reached from the wrong tree looks exactly like this one.
        echo "  matched on:"
        grep -m2 "is STALE against the live listings" /tmp/fp_repin.$$ | sed 's/^/    | /'
    else
        echo "freeze_preflight: repin_pins failed for a reason that is NOT staleness — stopping"
        # NAME THE FAILING TESTS. Printing only the aggregate is what made a red undiagnosable
        # for two hours on chain 199: the run said "1 passed; 1 failed" and nothing said WHICH,
        # so the failure could not be told apart from a transient. A count is not a diagnosis.
        echo "  failing test(s):"
        # ⚠ `^test .* FAILED` ALSO MATCHES CARGO'S AGGREGATE LINE — `test result: FAILED. 1
        # passed; 1 failed; …` starts with `test ` and ends in FAILED (measured 2026-09-09,
        # not reasoned about). So this list printed the summary line as if it were a failing
        # test NAME, and at line 158 below it was also COUNTED as one. That is the chain-199
        # "4 failures on a run where 3 tests failed" defect still alive: deriving the count
        # and the names from one list made them AGREE, which is worse than disagreeing —
        # they now agree on a number inflated by one per failing test binary. The name form
        # is `test <path> ... FAILED`; ANCHOR THE END and the summary cannot impersonate it,
# because it continues past FAILED with its counts. Do NOT narrow the name to [^ ]+
# to exclude the summary: a doctest is spelled `test src/lib.rs - m::f (line 12) ...
# FAILED` and HAS SPACES, so that form drops real failures while fixing the overcount
# - trading a defect that inflates for one that hides. Measured 2026-09-09; sigil's
# scripts/landing-run.sh:667 had the end-anchored form already.
        grep -E "^test .* \.\.\. FAILED$" /tmp/fp_repin.$$ | sed 's/^/    /' || echo "    (none named — read the log above)"
        # ⚠ PRINT THE TEXT THE CLASSIFICATION WAS MADE ON, NOT THE CATEGORY (2026-09-09).
        # This arm names a CLASS — "not staleness" — and a reader carries that forward as
        # "investigate a cross-seam symbol break". On LS-17 the truth was "your parcel moved
        # bytes, as intended": the run had been measured against a different aeon tree (the
        # defect fixed above), and the category survived the trip while the evidence did not.
        # A verdict and its stated reason are separately checkable ONLY if the reason ships
        # with the text it was derived from — so the grep's negative answer is shown, not
        # summarised. `tail -3` above is the shape of the log a reader would otherwise have,
        # and it is not enough: the panic body is usually further up than three lines.
        echo "  the text this classification was made on — the grep for"
        echo "  \"is STALE against the live listings\" did NOT match ANY of it:"
        FAILTEXT=$(awk '/panicked at|^error(\[|:)|^thread /{p=1} p' /tmp/fp_repin.$$ | head -40)
        [ -z "$FAILTEXT" ] && FAILTEXT=$(tail -20 /tmp/fp_repin.$$)
        [ -z "$FAILTEXT" ] && FAILTEXT="(the run produced NO output at all — suspect cargo itself, not the test)"
        printf '%s\n' "$FAILTEXT" | sed 's/^/    | /'
        echo "  If that text does NOT read like a failure of THIS parcel, re-read the SUBJECTS"
        echo "  block at the top before you re-read your diff."
        rm -f /tmp/fp_repin.$$; exit 2
    fi
fi
rm -f /tmp/fp_repin.$$

echo
echo "freeze_preflight: step 2/2 — the port targets (the standalone-module case build.sh never exercises)"
OUT=/tmp/fp_ports.$$
cargo test --release -p sigil-cli --no-fail-fast 2>&1 | tee "$OUT" | grep -E "^test result:|FAILED|panicked at" | tail -25
# COUNT AND NAME FROM THE SAME LINES. The old form ran `grep -c` in a command substitution
# alongside a `; true`, and reported 4 failures on a run where 3 tests failed — a count nobody
# could reconcile with the names, because the names were never printed. Derive both from one
# list so they cannot disagree.
# See the note at step 1: `^test .* FAILED` swallows cargo's `test result: FAILED.` summary,
# so with --no-fail-fast this counted one PHANTOM failure per failing test binary and printed
# the summary line among the names. Anchoring on the ` ... FAILED` name form fixes both,
# because both are derived from this one list.
FAILING=$(grep -E "^test .* \.\.\. FAILED$" "$OUT" 2>/dev/null | sed -E 's/^test (.*) \.\.\. FAILED$/\1/' | sort -u)
FAILED=$(printf '%s' "$FAILING" | grep -c . || true)
echo
echo "freeze_preflight: $FAILED port test failure(s)"
if [ "$FAILED" -gt 0 ]; then
    echo "  failing test(s):"
    printf '%s\n' "$FAILING" | sed 's/^/    /'
    SYMS=$(grep -oE "references symbol \`[A-Za-z_0-9]+\`" "$OUT" | sort -u)
    NSYMS=$(printf '%s' "$SYMS" | grep -c . || true)
    echo "  distinct cross-seam symbols named: $NSYMS"
    [ "$NSYMS" -gt 0 ] && printf '%s\n' "$SYMS" | sed 's/^/    /'
    # ⚠ A VERDICT MUST NOT NAME A CAUSE ITS OWN EVIDENCE DOES NOT CARRY (chain 199). This arm
    # used to announce "these are REAL, supply the composition" whenever pins were current —
    # including when ZERO cross-seam symbols were named, which prescribes an action with no
    # target. On chain 199 the three failures were version_provenance tests (a stale binary
    # against a moved tree) and are not port tests at all. A gate's verdict and its stated
    # reason are separately checkable, and the reason is the half a reader carries forward.
    if [ "$PINS_CURRENT" = "1" ] && [ "$NSYMS" -gt 0 ]; then
        echo "  VERDICT: pins were current AND a cross-seam symbol is named, so these are REAL."
        echo "           Supply the composition BEFORE freezing."
        rm -f "$OUT"; exit 1
    fi
    if [ "$PINS_CURRENT" = "1" ]; then
        echo "  VERDICT: pins were current but NO cross-seam symbol is named, so this is NOT the"
        echo "           cross-seam class and there is nothing to 'supply'. Read the failing"
        echo "           test names above and diagnose them on their own terms — a stale binary"
        echo "           against a moved tree presents here and is fixed by rebuilding, not by"
        echo "           a composition. Stopping so the freeze is a decision, not a default."
        rm -f "$OUT"; exit 1
    fi
    echo "  VERDICT: pins were STALE, so these are expected. The freeze regenerates them."
    echo "  ⚠ But a CROSS-SEAM symbol named above is real even so — it is not a pin."
    grep -qE "references symbol" "$OUT" && { echo "  A cross-seam symbol IS named. Treat as REAL."; rm -f "$OUT"; exit 1; }
fi
rm -f "$OUT"
echo "freeze_preflight: CLEAR — safe to run refreeze --freeze"
