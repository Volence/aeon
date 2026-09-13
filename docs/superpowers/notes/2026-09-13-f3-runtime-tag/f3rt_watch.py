#!/usr/bin/env python3
"""F3 RUNTIME-TAG, direct witness: read-watch the 932 deleted bytes in the PRE-deletion ROM (A).

usage: f3rt_watch.py <romA> <lstA> <sfx_bin_dir> <out.json>

Arms read-only bus watches BEFORE boot on: the SfxTable cells (548 B) and the 12 separate patch-bank
copies (384 B) that the F3 merge deleted, plus a POSITIVE CONTROL on $33's INLINE patch bank, which the Z80
must read when $33 plays. Boots, then fires all 16 SFX in one continuous timeline (no restore: a rewind
can discard hits). A zero on the subjects means something only if the control is non-zero.
"""
import asyncio, json, re, sys
sys.path.insert(0, '/home/volence/sonic_hacks/.aeon-ls8-land/tools')
import aether_instance as ai  # noqa: E402

IDS = ['33', '34', '35', '36', '3C', '42', '4A', '4C', '62', '7E', 'AB', 'B1', 'B6', 'B9', 'BA', 'BB']
CH_BASE, CH_LEN, CH_N = 0x1D00, 68, 7
LO, HI = 0xBD568, 0xBE2D4                       # A's sound block: Sfx_33 .. GameState_OJZScroll_Init
BOOT_FRAMES, MAX_FRAMES, QUIET = 600, 900, 3


def lst_addr(lst, name):
    m = re.search(rf'^\s*{name}\s*:\s*([0-9A-F]+)\s', open(lst, encoding='latin-1').read(), re.M)
    return int(m.group(1), 16) & 0xFFFFFF


def ranges(rom_path, sfxdir):
    rom = open(rom_path, 'rb').read()
    wins = {}
    for n in IDS:
        b = open(f'{sfxdir}/sfx_{n}.bin', 'rb').read()
        i = rom.find(b)
        assert i != -1 and rom.find(b, i + 1) == -1, n
        wins[n] = (i, len(b))
    addrs = {a for a, _ in wins.values()}
    tab = None
    for s in range(LO, HI - 548 + 1, 2):
        nz = [int.from_bytes(rom[s + 4 * k:s + 4 * k + 4], 'big') for k in range(137)]
        nz = [c for c in nz if c]
        if len(nz) == 16 and set(nz) == addrs:
            tab = s
            break
    assert tab is not None, 'SfxTable cells not found'
    copies = set()
    for n in IDS:
        try:
            pb = open(f'{sfxdir}/sfx_{n}_patches.bin', 'rb').read()
        except FileNotFoundError:
            continue
        if not pb:
            continue
        i = rom.find(pb, LO)
        while i != -1 and i < HI:
            if not any(a <= i < a + l for a, l in wins.values()):
                copies.add((i, len(pb)))
            i = rom.find(pb, i + 1)
    subj = [('subj-sfxtable', tab, 548)] + [(f'subj-copy-{a:06X}', a, l) for a, l in sorted(copies)]
    ctl_inline = rom.find(open(f'{sfxdir}/sfx_33_patches.bin', 'rb').read(), wins['33'][0])
    assert wins['33'][0] <= ctl_inline < sum(wins['33']), 'control not inside $33'
    return wins, subj, ('control-33-inline', ctl_inline, 32)


def main(rom, lst, sfxdir, outp):
    wins, subj, ctl = ranges(rom, sfxdir)
    assert sum(l for _, _, l in subj) == 932, sum(l for _, _, l in subj)
    ring = lst_addr(lst, 'Sfx_Ring_Buf')
    # 68k POSITIVE CONTROL with a PREDICTED count: boot copies the Z80 image to Z80 RAM one byte at a time
    # (engine/system/boot.emp `.load_z80`, move.b (a5)+,(a0)+), so its first 16 bytes are read exactly 16x.
    ctl68 = ('control-68k-z80image', lst_addr(lst, 'Z80_Sound_Start'), 16)
    watches = [ctl68, ctl] + subj
    res = {'rom': rom, 'watches': [[n, hex(a), l] for n, a, l in watches]}
    with ai.aether_emulator(rom, symbols=lst) as sock:
        asyncio.run(body(sock, ring, watches, res))
    json.dump(res, open(outp, 'w'), indent=1)
    c68 = res['hits'][ctl68[0]]['count']
    print(f"68k control: {c68} hits (predicted exactly 16) -> {'INSTRUMENT SEES 68k ROM READS' if c68 == 16 else 'CONTROL FAILED: subject zeros mean nothing'}")


async def body(sock, ring, watches, res):
    b = ai.BusClient(socket_path=sock, client_id='f3rt-watch', client_name='f3rt-watch')
    await b.connect()
    handles = {}
    for name, a, l in watches:
        r = await b.call('emulator/watchpoint_add', {'addr': hex(a), 'len': l, 'read': True, 'write': False, 'label': name})
        handles[name] = r.get('watch') or r.get('id') or r.get('handle')
    res['arm_reply_sample'] = r
    await b.call('emulator/run_frames', {'frames': BOOT_FRAMES})
    fired = []
    for n in IDS:
        rb = bytes.fromhex(ai.unprefix((await b.call('emulator/read_memory', {'addr': hex(0xFF0000 | ring), 'len': 10}))['bytes']))
        wr = rb[8]
        assert rb[8] == rb[9], f'ring not empty before ${n}: {rb.hex()}'
        await b.call('emulator/write_memory', {'addr': hex(0xFF0000 | ring + wr), 'value': int(n, 16), 'width': 1})
        await b.call('emulator/write_memory', {'addr': hex(0xFF0000 | ring + 8), 'value': (wr + 1) & 7, 'width': 1})
        f, started, quiet = 0, None, 0
        while f < MAX_FRAMES:
            r = await b.call('emulator/run_frames', {'frames': 1}); f += 1
            ch = bytes.fromhex(ai.unprefix((await b.call('emulator/z80_read', {'addr': hex(CH_BASE), 'len': CH_LEN * CH_N}))['bytes']))
            active = any(ch[s * CH_LEN + 10] & 1 for s in range(CH_N))
            if active:
                started = started or f; quiet = 0
            elif started:
                quiet += 1
                if quiet >= QUIET:
                    break
        fired.append([n, started, f, r.get('frame')])
    res['fired'] = fired
    res['hits'] = {}
    for name, h in handles.items():
        allh, cursor, dropped = [], None, 0
        while True:
            p = {'watch': h, 'limit': 4096}
            if cursor:
                p['cursor'] = cursor
            r = await b.call('emulator/watchpoint_hits', p)
            allh += r.get('hits', [])
            dropped = max(dropped, r.get('dropped', 0) or 0)
            cursor = r.get('cursor') or r.get('nextCursor')
            if not cursor or not r.get('hits'):
                break
        res['hits'][name] = {'handle': h, 'count': len(allh), 'dropped': dropped, 'first': allh[:3],
                             'pcs': sorted({str(x.get('pc')) + ' ' + str(x.get('symbol') or x.get('pcSymbol') or '') for x in allh}),
                             'fc': sorted({str(x.get('fc')) for x in allh}),
                             'addrs': sorted({str(x.get('addr') or x.get('address')) for x in allh})[:8]}
        print(f"{name}: {len(allh)} read hits, dropped={dropped}, fc={res['hits'][name]['fc']}, pcs={res['hits'][name]['pcs'][:4]}")
    await b.close()


if __name__ == '__main__':
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(*sys.argv[1:])
