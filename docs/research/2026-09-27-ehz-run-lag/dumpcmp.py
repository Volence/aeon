#!/usr/bin/env python3
"""dumpcmp — is the parallax output byte-identical between two ROMs at matched ticks?

usage: dumpcmp.py A.json B.json
Both are run_probe.py --dump legs of the SAME drive. Each holds, per logic tick that ended on
time, the camera and the bytes of Hscroll_Buffer + Parallax_Vscroll_Column_Buf + Vscroll_Factor
(run_probe.DUMP). Compared at every tick both recorded:
  * the camera must agree (else the two legs did not see the same scene and the tick is
    reported as CAMERA DIFFERS, never compared);
  * the bytes must agree; a differing tick prints which HScroll lines / VSRAM columns differ.
Exit 0 = identical at every common tick, 1 = a difference, 2 = could not measure (no common
ticks, or a camera mismatch).
"""
import json
import sys

a, b = (json.load(open(p)) for p in sys.argv[1:3])
A, B = a["dumps"], b["dumps"]
common = sorted(set(A) & set(B), key=int)
print(f"A {a['rom']} crc={a['crc']} dumps={len(A)}   B {b['rom']} crc={b['crc']} dumps={len(B)}")
if not common:
    print("COULD NOT MEASURE: no tick recorded on both")
    sys.exit(2)
cam_bad = [t for t in common if A[t][:2] != B[t][:2]]
if cam_bad:
    print(f"COULD NOT MEASURE: camera differs at {len(cam_bad)} common ticks, first {cam_bad[0]}: "
          f"{A[cam_bad[0]][:2]} vs {B[cam_bad[0]][:2]}")
    sys.exit(2)
diff = [t for t in common if A[t][2] != B[t][2]]
ehz = [t for t in common if A[t][1] < 1024]
print(f"common ticks {len(common)} (camera y < 1024, Emerald Hill's band: {len(ehz)}); "
      f"cameras agree at all; bytes differ at {len(diff)}")
for t in diff[:8]:
    x, y = bytes.fromhex(A[t][2]), bytes.fromhex(B[t][2])
    lines = [i for i in range(224) if x[i * 4:i * 4 + 4] != y[i * 4:i * 4 + 4]]
    cols = [i for i in range(40) if x[896 + i * 2:898 + i * 2] != y[896 + i * 2:898 + i * 2]]
    print(f"  tick {t} cam {A[t][:2]}: HScroll lines {lines[:10]}{'...' if len(lines) > 10 else ''} "
          f"({len(lines)}), VSRAM cols {cols[:10]} ({len(cols)}), factor "
          f"{'differs' if x[976:] != y[976:] else 'same'}")
print("finished=1")
sys.exit(1 if diff else 0)
