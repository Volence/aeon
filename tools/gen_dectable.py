# tools/gen_dectable.py — emit the DPCM DecTable rows (db) for inline inclusion in the Z80 blob.
from dac_encode import DELTA_TABLES
for i, t in enumerate(DELTA_TABLES):
    row = ", ".join(str(b & 0xFF) for b in t)
    print(f"        db      {row}   ; table {i}")
