#!/bin/bash
# collect.sh : this round's raw results from $HOME/pxperf into results/ (tables, witness and
# identity runs, crcs, leg metas, the mutants' diffs / builds / tables / witness runs).
HERE=$(cd "$(dirname "$0")" && pwd)
R1="$HERE/../2026-09-28-parallax-perband"
R="$HERE/results"; P=$HOME/pxperf
mkdir -p "$R/mutants"
{ for t in p4_base p4_v1 p4_v2 p4_v3 p4_v4; do echo "$t head $(cat $P/$t/head.txt)"; cat "$P/$t/crc.txt"; done
  echo "p4_noderive (measurement variant of the v2 tree, cdebug only; its source: tools/ed_noderive.py)"
  python3 -c "import zlib,sys;b=open(sys.argv[1],'rb').read();print('cdebug.bin %08x %d'%(zlib.crc32(b),len(b)))" "$P/p4_noderive/cdebug.bin"; } > "$R/crcs.txt"
python3 "$R1/cmptable.py" "$P/L_p4_base" "$P/L_p4_v4" > "$R/cmp_base_v4.txt"
python3 "$R1/cmptable.py" "$P/L_p4_base" "$P/L_p4_v1" > "$R/cmp_base_v1.txt"
python3 "$R1/cmptable.py" "$P/L_p4_base" "$P/L_p4_v2" cdebug_anchor_right cdebug_anchor_down cdebug_diag cdebug_run > "$R/cmp_base_v2.txt"
python3 "$R1/cmptable.py" "$P/L_p4_base" "$P/L_p4_noderive" cdebug_anchor_right cdebug_anchor_down > "$R/cmp_base_noderive.txt"
python3 "$R1/cmptable.py" "$P/L_p4_base" "$P/L_p4_base2" debug_spin > "$R/cmp_base_base2_debug_spin.txt"
python3 "$R1/pxsum.py" "$P/L_p4_base" cdebug_anchor_right cdebug_anchor_down debug_run cdebug_run > "$R/base_pxsum.txt"
python3 "$R1/pxsum.py" "$P/L_p4_v4" cdebug_anchor_right cdebug_anchor_down debug_run cdebug_run > "$R/v4_pxsum.txt"
for t in base v1 v2 v4; do cp "$P/L_p4_$t/legs.meta" "$R/legs_$t.meta"; done
cp "$P/p4_wit_base.txt" "$R/witness_base_unextended.txt"
cp "$P/p4_wit_v1.txt" "$R/witness_v1_unextended.txt"
cp "$P/p4_wit_v3.txt" "$R/witness_v3_provisional_red.txt"
cp "$P/p4_wit_v4.txt" "$R/witness_v4.txt"
cp "$P/p4_ident_base.txt" "$R/ident_base.txt"
cp "$P/p4_ident_v4.txt" "$R/ident_v4.txt"
cp "$P/p4_probe_still.txt" "$R/probe_still_sweep.txt"
for m in L M N P R Q S; do
  cp "$P/p4_mut$m/mutant.diff" "$R/mutants/mut$m.diff"
  { cat "$P/p4_mut$m/done"; cat "$P/p4_mut$m/crc.txt"; } > "$R/mutants/mut${m}_build.txt"
  grep -E '\[Error\]|FIRED|error\(s\)' "$P/p4_mut$m/b_cdebug.log" | cut -c1-400 >> "$R/mutants/mut${m}_build.txt"
done
for m in L M N P R Q; do
  python3 "$R1/cmptable.py" "$P/L_p4_base" "$P/L_p4_mut$m" cdebug_diag cdebug_down cdebug_run \
      cdebug_anchor_right cdebug_anchor_down > "$R/mutants/cmp_base_mut$m.txt"
  cp "$P/p4_witness_mut$m.txt" "$R/mutants/witness_mut$m.txt"
done
echo "finished=1"
