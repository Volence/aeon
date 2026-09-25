"""Write scratch candidate manifests (UNCOMMITTED) that widen the CPZ clip of s2_ehz_cpz."""
import json, os, copy, sys
base = json.load(open('games/sonic4/data/clips/s2_ehz_cpz/clips.json'))
for w in (int(a) for a in sys.argv[1:]):
    m = copy.deepcopy(base)
    cid = f"s2x_cpz{w}"
    m['id'] = cid
    m['name'] = f"SCRATCH measurement: CPZ clip {w} px wide"
    end = 12288 + w
    gw = -(-end // 2048)
    m['act']['grid_w'] = gw
    m['unpainted_remainder']['x_from'] = gw * 2048
    for c in m['clips']:
        if c['id'] == 'cpz_act1':
            c['src_rect']['w'] = w
            c['dst_rect']['w'] = w
    os.makedirs(f'games/sonic4/data/clips/{cid}', exist_ok=True)
    json.dump(m, open(f'games/sonic4/data/clips/{cid}/clips.json', 'w'), indent=2)
    print(cid, 'grid_w', gw, 'end', end)
