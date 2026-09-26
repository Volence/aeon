#!/usr/bin/env bash
# (stressart-budget SAH-2, 2026-09-26) Paths name the parcel's own cache dir, /home/volence/.cache/aeon-sab; re-point them to re-run.
# SAH-2: cpzdiag (plain + profiled from switch) on the pre-fix and post-fix clip DEBUG ROMs.
export TMPDIR=/home/volence/.cache/aeon-tmp
W=/home/volence/sonic_hacks/aeon/.claude/worktrees/agent-a3567df1063baa773
S=/home/volence/.cache/aeon-sab
L=$W/docs/research/2026-09-27-general-patch-loop/gpl_legs.sh
for t in "$@"; do
    bash "$L" "$S/clip_$t/s4.s2clip.debug.bin" "$S/clip_$t/s4.s2clip.debug.lst" "$S/sah2" "$t" cpzdiag,cpzdiagP
done
echo "finished=$#" > "$S/sah2_done_$(echo "$@" | tr ' ' _)"
