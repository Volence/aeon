#!/bin/bash
# collect.sh : copy this round's comparison tables, part sums, CRCs and leg metas from
# $HOME/pxperf into results/. Round 1's cmptable.py / pxsum.py are the instruments.
HERE=$(cd "$(dirname "$0")" && pwd)
R1="$HERE/../2026-09-28-parallax-perband"
R="$HERE/results"; P=$HOME/pxperf
mkdir -p "$R"
python3 "$R1/cmptable.py" "$P/L_r2_base" "$P/L_r2_p5" > "$R/cmp_base_p5.txt"
python3 "$R1/cmptable.py" "$P/L_r2_p5" "$P/L_r2_p3" > "$R/cmp_p5_p3first.txt"
python3 "$R1/cmptable.py" "$P/L_r2_p5" "$P/L_r2_p3b" > "$R/cmp_p5_p3.txt"
python3 "$R1/cmptable.py" "$P/L_r2_p3b" "$P/L_r2_p6" > "$R/cmp_p3_p6.txt"
python3 "$R1/cmptable.py" "$P/L_r2_base" "$P/L_r2_p6" > "$R/cmp_base_final.txt"
python3 "$R1/pxsum.py" "$P/L_r2_base" > "$R/base_pxsum.txt"
python3 "$R1/pxsum.py" "$P/L_r2_p6" > "$R/final_pxsum.txt"
for d in r2_decomp_base r2_decomp_final; do
  [ -d "$P/L_$d" ] && python3 "$R1/pxsum.py" "$P/L_$d" debug_run cdebug_run cdebug_anchor_right > "$R/${d#r2_}_pxsum.txt"
done
for t in r2_base r2_p5 r2_p3 r2_p3b r2_p6 r2_p6c r2_decomp_base r2_decomp_final; do
  [ -d "$P/$t" ] || continue
  echo "== $t"; cat "$P/$t/crc.txt"; cat "$P/$t/head.txt"
done > "$R/crcs.txt"
cp "$P/r2_ident_base.txt" "$R/ident_base.txt"
cp "$P/r2_ident_p6.txt" "$R/ident_final.txt"
for t in r2_base r2_p5 r2_p3 r2_p3b r2_p6; do cp "$P/L_$t/legs.meta" "$R/legs_${t#r2_}.meta"; done
echo "finished=1"
