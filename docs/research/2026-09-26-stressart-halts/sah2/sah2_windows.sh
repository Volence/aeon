#!/usr/bin/env bash
# (stressart-budget SAH-2, 2026-09-26) Paths name the parcel's own cache dir, /home/volence/.cache/aeon-sab; re-point them to re-run.
# SAH-2: one-frame profile windows around the first divergence (row 910), both ROMs.
export TMPDIR=/home/volence/.cache/aeon-tmp
W=/home/volence/sonic_hacks/aeon/.claude/worktrees/agent-a3567df1063baa773
S=/home/volence/.cache/aeon-sab
P=$W/docs/research/2026-09-27-general-patch-loop/gpl_probe.py
mkdir -p "$S/sah2w"
n=0
for t in base fix; do
  for w in $(seq "$2" "$3"); do
    python3 "$P" --rom "$S/clip_$t/s4.s2clip.debug.bin" --lst "$S/clip_$t/s4.s2clip.debug.lst" \
      --mode fly --dirs right --then-dirs right,down --then-at-x 14400 --frames 2000 \
      --profile-window "$1,$w" --out "$S/sah2w/${t}_c$1_$w.json" > "$S/sah2w/${t}_c$1_$w.txt" 2>&1
    echo "$t c$1_$w rc=$?" >> "$S/sah2w/run.meta"
    n=$((n + 1))
  done
done
echo "finished=$n" >> "$S/sah2w/run.meta"
