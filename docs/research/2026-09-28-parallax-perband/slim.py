#!/usr/bin/env python3
"""slim.py OUT.tar.gz DIR [DIR ..] — keep a leg set's evidence at a committable size.

Each leg JSON is rewritten with the parallax dump bytes reduced to their SHA-1 (the identity
comparison only ever asks equal / not equal) and each profile segment reduced to its tick
count plus the Parallax_* / Decode_Factor_* rows (what pxsum.py and cmptable.py read). Rows,
path, coverage, watch, notes and the summary are kept whole.
"""
import hashlib
import io
import json
import os
import sys
import tarfile

KEEP = ("Parallax_", "Decode_Factor_", "PxM_")


def slim(h):
    h["dumps"] = {t: [v[0], v[1], hashlib.sha1(bytes.fromhex(v[2])).hexdigest()]
                  for t, v in h.get("dumps", {}).items()}
    for g in h.get("segs", []):
        p = g.get("profile")
        if p:
            g["profile"] = {"ticks": p["ticks"], "items": [
                {k: r[k] for k in ("name", "cyclesTotal", "cyclesSelfTotal", "callsTotal")}
                for r in p["items"] if (r.get("name") or "").startswith(KEEP)]}
    return h


out = sys.argv[1]
with tarfile.open(out, "w:gz") as tf:
    for d in sys.argv[2:]:
        for f in sorted(os.listdir(d)):
            if not f.endswith(".json"):
                continue
            b = json.dumps(slim(json.load(open(os.path.join(d, f))))).encode()
            ti = tarfile.TarInfo(f"{os.path.basename(d)}/{f}")
            ti.size = len(b)
            tf.addfile(ti, io.BytesIO(b))
print(f"wrote {out} ({os.path.getsize(out)} bytes)")
