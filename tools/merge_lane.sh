#!/usr/bin/env bash
# merge_lane — the four canonical shapes, then the `needs_build` pytest lane over them.
#
# WHY THIS EXISTS (LS-1c, 2026-09-10).
#
# LS-1 split the tool-suite pytest lane around the sigil build; LS-1b gave the marked
# half a grader (tools/needs_build_lane.py) and a runner (tools/nightly_effects_gates.sh).
# That runner fires once a day. It is the ONLY thing that ever runs
# `test_segmented_parent_checks_the_row_set_it_aggregated`, which declares s4.debug.bin,
# s4.debug.lst AND demo.debug.lst at once — and one `build.sh` invocation writes exactly
# one game's .bin/.lst pair, so that test DEFERS in every build.sh shape. A parcel could
# therefore break it and merge green; the nightly said so the following morning.
#
# THE FIX IS NOT A NEW BUILD SHAPE, IT IS A RUNNER AT THE RIGHT ALTITUDE. Every parcel
# in this tree already has to build all four canonical shapes before it lands — plain and
# DEBUG, sonic4 and demo (CLAUDE.md, "Build"; every parcel brief repeats it, because
# sonic4 alone builds green over a broken tree). Those four invocations write all eight
# artifacts in `tools/conftest.py`'s BUILD_ARTIFACTS. This script IS that four-shape
# build, plus the lane over the complete artifact set it just produced. It costs a parcel
# nothing it was not already paying, and it is the reason the marked lane is now graded at
# merge time rather than once a night.
#
# It does NOT go into build.sh, and that was re-checked rather than inherited: build.sh
# builds one game per invocation (`GAME="${1:-sonic4}"` threaded through a single scalar
# `ROM_NAME` into one `${SIGIL_BUILD} build`), and every other gate in it depends on that
# contract. The multi-shape caller has to be above build.sh, not inside it.
#
# THE SHAPE LIST IS CHECKED, NOT TRUSTED, and that is a scar. The nightly's three-shape
# list was written when four tests carried the marker and every artifact they declared was
# covered. On 2026-09-07 `tools/test_deb2_appendix.py` parametrized the marker over all
# four SHAPES, adding demo.bin/demo.lst — which no nightly shape builds. From 2026-09-08
# the nightly's needs_build lane reported COULD NOT RUN every single night, with the
# script's own header still asserting "every artifact the marked tests declare is built by
# this script". A hand-maintained shape list drifts under a growing marker population.
# `tools/test_merge_lane_shapes.py` runs in build.sh's PRE-build lane (build-fatal, every
# shape, every parcel) and asserts the coverage this script and the nightly each claim,
# derived from the markers actually in the tree.
#
# EXIT CONTRACT, mirroring effects_gates.py and needs_build_lane.py:
#   0  all four shapes built and every marked test ran and passed.
#   1  a marked test RAN and FAILED — a real verdict about this tree.
#   2  COULD NOT RUN: a build failed, a required binary is missing, FAST=1 was set, or
#      the lane could not answer (a deferral, an empty collection, an unreadable report).
# A lane that could not run is never rendered as a pass; that is the defect LS-1 closed
# and the one this script is not allowed to rebuild one level up.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AEON="$(dirname "$HERE")"
cd "$AEON" || { echo "merge_lane: COULD NOT RUN: no $AEON"; exit 2; }

# FAST=1 skips every verification lane inside build.sh, so a FAST four-shape run would
# produce the artifacts and grade almost nothing. Refuse rather than quietly weaken.
if [[ "${FAST:-0}" != "0" ]]; then
    echo "merge_lane: COULD NOT RUN: FAST=1 skips build.sh's verification lanes."
    echo "  This script is landing evidence; FAST is a content-authoring loop. Unset it."
    exit 2
fi
# NO_LINT skips BOTH halves of the split pytest lane — including the post-sigil half this
# script exists to reach. Same reasoning.
if [[ "${NO_LINT:-0}" != "0" ]]; then
    echo "merge_lane: COULD NOT RUN: NO_LINT=${NO_LINT} skips the pytest lane this grades."
    exit 2
fi

for b in "${SIGIL_BUILD:-}" "${SIGIL_EMIT:-}"; do
    if [[ -z "$b" || ! -x "$b" ]]; then
        echo "merge_lane: COULD NOT RUN: SIGIL_BUILD and SIGIL_EMIT must both point at an"
        echo "  executable. They are set by no dotfile in this workspace; export them:"
        echo "    export SIGIL_BUILD=<suite>/sigil/target/release/sigil"
        echo "    export SIGIL_EMIT=<suite>/sigil/target/release/emit_sound_blob"
        exit 2
    fi
done

# A DEBUG exported by the caller would turn the two plain shapes into debug ones and the
# lane would then defer on s4.lst/demo.lst while every build reported success.
unset DEBUG

# The provenance instant for the lane below. Every artifact it grades must post-date this,
# i.e. must have been written by one of the four builds that follow. Whole seconds
# truncate DOWN, so a file written in the same second still counts as fresh — the same
# rule build.sh's ${SIGIL_T0} and every sibling --built-after gate uses, taken rather than
# reinvented. It is a PROVENANCE claim ("this run wrote the file"), NOT a content one
# ("the file matches the source it was built from"). Nothing here checks the second; that
# is LS-1a, open across the whole --built-after family and not narrowed by this script.
T0=$(date +%s)

# The four canonical shapes, in build.sh's own argument form. tools/test_merge_lane_shapes.py
# parses these lines and asserts they cover every artifact the marked tests declare.
if ! ./build.sh;             then echo "merge_lane: COULD NOT RUN: plain sonic4 build failed";  exit 2; fi
if ! DEBUG=1 ./build.sh;     then echo "merge_lane: COULD NOT RUN: DEBUG sonic4 build failed";  exit 2; fi
if ! ./build.sh demo;        then echo "merge_lane: COULD NOT RUN: plain demo build failed";    exit 2; fi
if ! DEBUG=1 ./build.sh demo; then echo "merge_lane: COULD NOT RUN: DEBUG demo build failed";   exit 2; fi

echo
echo "==== merge_lane: all four shapes built; grading the needs_build lane ===="
python3 tools/needs_build_lane.py --built-after "$T0"
rc=$?
case $rc in
    0) echo "merge_lane: OK — four shapes built, marked lane green." ;;
    1) echo "merge_lane: FAILED — a marked test ran and failed against artifacts this run built." ;;
    *) echo "merge_lane: COULD NOT RUN — the marked lane could not answer (exit $rc)." ;;
esac
exit $rc
