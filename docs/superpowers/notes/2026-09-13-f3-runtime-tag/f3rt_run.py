#!/usr/bin/env python3
"""F3 RUNTIME-TAG runner: fire the 16 SFX on one ROM, trace the Z80 SfxChannel state per frame.

usage: f3rt_run.py <rom> <lst> <sfx_bin_dir> <out.json>

Each pointer a channel holds (stream, patch base) is recorded RELATIVE to the SFX's own blob
window when it lies inside it, and as ('abs', value) otherwise, so traces from two ROMs whose
blobs sit at different addresses compare equal iff the driver behaves identically. Blob windows
are found by a UNIQUE byte match of each sfx_NN.bin in the ROM (refuses otherwise).
"""
import asyncio, json, re, sys
sys.path.insert(0, '/home/volence/sonic_hacks/.aeon-ls8-land/tools')
import aether_instance as ai  # noqa: E402

IDS = ['33', '34', '35', '36', '3C', '42', '4A', '4C', '62', '7E', 'AB', 'B1', 'B6', 'B9', 'BA', 'BB']
CH_BASE, CH_LEN, CH_N = 0x1D00, 68, 7          # SND_SFX_CHANNELS / SfxChannel_len / SFX_VOICE_COUNT
STAT = 0x1F10                                   # ALIVE, PING_ECHO, ACK_COUNT, TICK
ALIVE = 0x5A
BOOT_FRAMES, MAX_FRAMES, QUIET_FRAMES = 600, 900, 3


def lst_addr(lst: str, name: str) -> int:
    m = re.search(rf'^\s*{name}\s*:\s*([0-9A-F]+)\s', open(lst, encoding='latin-1').read(), re.M)
    if not m:
        sys.exit(f'REFUSE: {name} not in {lst}')
    return int(m.group(1), 16) & 0xFFFFFF


def windows(rom: str, sfxdir: str) -> dict:
    data = open(rom, 'rb').read()
    out = {}
    for n in IDS:
        blob = open(f'{sfxdir}/sfx_{n}.bin', 'rb').read()
        hits, i = [], data.find(blob)
        while i != -1:
            hits.append(i)
            i = data.find(blob, i + 1)
        if len(hits) != 1:
            sys.exit(f'REFUSE: sfx_{n}.bin has {len(hits)} matches in {rom}')
        out[n] = (hits[0], 0x8000 | (hits[0] & 0x7FFF), len(blob))
    return out


def rel(v: int, win: int, ln: int):
    return ('in', v - win) if win <= v < win + ln else ('abs', v)


def main(rom, lst, sfxdir, outp):
    wins = windows(rom, sfxdir)
    ring = lst_addr(lst, 'Sfx_Ring_Buf')
    ring_wr = lst_addr(lst, 'Sfx_Ring_Wr')
    assert ring_wr == ring + 8, (hex(ring), hex(ring_wr))
    res = {'rom': rom, 'lst': lst, 'ring': hex(ring), 'windows': {k: [hex(a), hex(w), l] for k, (a, w, l) in wins.items()}, 'sfx': {}}
    # aether_emulator runs its own asyncio handshake, so it must be entered OUTSIDE any loop
    with ai.aether_emulator(rom, symbols=lst) as sock:
        asyncio.run(body(sock, wins, ring, res))
    json.dump(res, open(outp, 'w'))


async def body(sock, wins, ring, res):
    if True:
        b = ai.BusClient(socket_path=sock, client_id='f3rt', client_name='f3rt')
        await b.connect()

        async def z(addr, ln):
            r = await b.call('emulator/z80_read', {'addr': hex(addr), 'len': ln})
            return bytes.fromhex(ai.unprefix(r['bytes']))

        await b.call('emulator/run_frames', {'frames': BOOT_FRAMES})
        st = await z(STAT, 4)
        rb = bytes.fromhex(ai.unprefix((await b.call('emulator/read_memory', {'addr': hex(0xFF0000 | ring), 'len': 10}))['bytes']))
        res['baseline'] = {'stat': st.hex(), 'ring': rb.hex()}
        if st[0] != ALIVE or rb[8] != rb[9]:
            sys.exit(f'REFUSE: baseline not alive/empty: stat={st.hex()} ring={rb.hex()}')
        wr = rb[8]
        cp = (await b.call('emulator/checkpoint', {'label': 'f3rt baseline'}))['id']
        for n in IDS:
            _, win, ln = wins[n]
            await b.call('emulator/restore', {'id': cp})
            buf = bytearray(rb[:8]); buf[wr] = int(n, 16)
            await b.call('emulator/write_memory', {'addr': hex(0xFF0000 | ring), 'bytes': '0x' + (bytes(buf) + bytes([(wr + 1) & 7])).hex().upper()})
            ack0 = (await z(STAT, 4))[2]
            trace, started, quiet, oob, f, dead = [], None, 0, [], 0, None
            while f < MAX_FRAMES:
                await b.call('emulator/run_frames', {'frames': 1}); f += 1
                ch = await z(CH_BASE, CH_LEN * CH_N)
                s4 = await z(STAT, 4)
                if s4[0] != ALIVE and dead is None:
                    dead = f
                row = []
                for s in range(CH_N):
                    c = ch[s * CH_LEN:(s + 1) * CH_LEN]
                    if not c[10] & 1:
                        continue
                    sp, pb = rel(c[0] | c[1] << 8, win, ln), rel(c[59] | c[60] << 8, win, ln)
                    if sp[0] == 'abs' or (c[10] & 4 and pb[0] == 'abs'):
                        oob.append([f, s, sp, pb])
                    row.append([s, c[10], c[11], sp, pb, c[4], c[6], c[8], c[9], c[57], c[63]])
                trace.append(row)
                if row:
                    started = started or f; quiet = 0
                elif started:
                    quiet += 1
                    if quiet >= QUIET_FRAMES:
                        break
            st_end = await b.call('emulator/status', {})
            res['sfx'][n] = {'ack_delta': (s4[2] - ack0) & 0xFF, 'start_frame': started, 'frames_run': f,
                             'ended': bool(started) and quiet >= QUIET_FRAMES, 'alive_lost_at': dead,
                             'out_of_blob': oob, 'fm_patch_bases': sorted({tuple(r[4]) for fr in trace for r in fr if r[1] & 4}),
                             'pc_end': st_end.get('pc'), 'trace': trace}
            print(f"${n}: ack+{res['sfx'][n]['ack_delta']} start@{started} ran {f} ended={res['sfx'][n]['ended']} "
                  f"oob={len(oob)} alive_lost={dead} fm_patch={res['sfx'][n]['fm_patch_bases']}")
        await b.close()


if __name__ == '__main__':
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(*sys.argv[1:])
