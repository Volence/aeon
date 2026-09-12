#!/usr/bin/env python3
"""Compare the baked trees: pristine (committed at the pin) vs each run snapshot."""
import hashlib, os, sys
S = open("/tmp/claude-1000/-home-volence-sonic-hacks-aeon/0f66baa9-0a26-4066-a435-9516186c96f8/scratchpad/t1_S_path").read().strip()
P = os.path.join(S, "pristine", "games", "sonic4", "data")

def tree(root):
    out = {}
    for dp, _d, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            out[os.path.relpath(p, root)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out

base = {}
for sub in ("generated", "collision", "editor"):
    for k, v in tree(os.path.join(P, sub)).items():
        base[f"{sub}/{k}"] = v
base["editor_sources.stamp.json"] = hashlib.sha256(open(os.path.join(P, "editor_sources.stamp.json"), "rb").read()).hexdigest()

snaps = {}
for label in sys.argv[1:]:
    d = os.path.join(S, f"snap_{label}")
    t = {}
    for sub in ("generated", "collision", "editor"):
        for k, v in tree(os.path.join(d, sub)).items():
            t[f"{sub}/{k}"] = v
    t["editor_sources.stamp.json"] = hashlib.sha256(open(os.path.join(d, "editor_sources.stamp.json"), "rb").read()).hexdigest()
    snaps[label] = t

print(f"pristine files: {len(base)}")
for label, t in snaps.items():
    added = sorted(set(t) - set(base))
    removed = sorted(set(base) - set(t))
    changed = sorted(k for k in set(t) & set(base) if t[k] != base[k])
    print(f"== {label} vs pristine: files={len(t)} changed={len(changed)} added={len(added)} removed={len(removed)}")
    for k in changed: print("   changed", k)
    for k in added: print("   added  ", k)
    for k in removed: print("   removed", k)
labels = list(snaps)
for i in range(len(labels)):
    for j in range(i + 1, len(labels)):
        a, b = snaps[labels[i]], snaps[labels[j]]
        diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
        print(f"== {labels[i]} vs {labels[j]}: {len(diff)} differing files")
        for k in diff: print("   ", k)
