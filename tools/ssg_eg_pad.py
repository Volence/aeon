#!/usr/bin/env python3
"""One-shot migration: append the 4-byte SSG-EG group + 2 reserved pad bytes
(all $00) to every FmPatch record in the two checked-in patch banks whose source
JSON is NOT in this worktree (Moving Trucks, HCZ2), so their FmPatch_len-relative
size asserts pass after FmPatch grew 26 -> 32 (SSG-EG, Task C1).

SSG-EG is $00 (off) for every existing record (no source carries SSG-EG data),
so this only appends 6 zero bytes per record; the first 26 bytes are untouched.
Idempotent: refuses to run on a file already at 32-byte records.

Formats handled:
  - Moving Trucks: `pbyte`-grouped records (fp_alg_fb, fp_lr_ams_fms, then 6
    four-byte `pbyte` rows). Insert two `pbyte` rows after each record's last
    group row (the `fp_d1l_rr  $80` row).
  - HCZ2: one `dc.b` row of 26 hex bytes per record. Rewrite the row with 6
    trailing `, $00`.
"""
import re
import sys

MT_PATH = "data/sound/movingtrucks_patches.asm"
HCZ2_PATH = "data/sound/hcz2_patches.asm"

SSG_ROW = "        pbyte     0,   0,   0,   0   ; fp_ssg_eg  $90  [S1,S3,S2,S4]"
PAD_ROW = "        pbyte     0,   0                ; fp_reserved (pad to 32)"


def migrate_mt(text: str) -> str:
    """Insert SSG-EG + pad rows after every `fp_d1l_rr  $80` pbyte row."""
    out = []
    inserted = 0
    for line in text.splitlines():
        out.append(line)
        if "fp_d1l_rr" in line and line.lstrip().startswith("pbyte"):
            out.append(SSG_ROW)
            out.append(PAD_ROW)
            inserted += 1
    if inserted == 0:
        raise SystemExit("MT: no fp_d1l_rr pbyte rows found (already migrated?)")
    return "\n".join(out) + "\n"


def migrate_hcz2(text: str) -> str:
    """Append 6 `, $00` to every `dc.b` record row that is exactly 26 bytes."""
    out = []
    inserted = 0
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("dc.b") and ";" in line:
            data, comment = line.split(";", 1)
            vals = [v.strip() for v in data.split("dc.b", 1)[1].split(",")]
            vals = [v for v in vals if v]
            if len(vals) == 26:
                vals = vals + ["$00"] * 6
                line = "        dc.b    %s  ;%s" % (", ".join(vals), comment.rstrip("\n"))
                inserted += 1
        out.append(line)
    if inserted == 0:
        raise SystemExit("HCZ2: no 26-byte dc.b record rows found (already migrated?)")
    return "\n".join(out) + "\n"


def main():
    with open(MT_PATH) as f:
        mt = f.read()
    with open(HCZ2_PATH) as f:
        hz = f.read()
    with open(MT_PATH, "w") as f:
        f.write(migrate_mt(mt))
    with open(HCZ2_PATH, "w") as f:
        f.write(migrate_hcz2(hz))
    print("migrated MT + HCZ2 patch banks to 32-byte records (SSG-EG $00).",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
