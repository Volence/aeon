import json, os, sys
# usage: lagsum.py <dirA> [<dirB>]   prints lag/video frames in motion per leg (+ camera end)
dirs = sys.argv[1:]
legs = sorted({f[:-5] for d in dirs for f in os.listdir(d) if f.endswith(".json")})
for leg in legs:
    row = [f"{leg:<18}"]
    for d in dirs:
        p = os.path.join(d, leg + ".json")
        if not os.path.isfile(p):
            row.append("DID NOT RUN".ljust(40)); continue
        j = json.load(open(p))
        m = j["summary"]["motion"]
        row.append(f"{j['crc']} {m['lag']}/{m['video_frames']} end {m['cam_end']}".ljust(40))
    print(" | ".join(row))
