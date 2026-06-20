#!/usr/bin/env python3
"""Measure INTRA-NOTE FM modulation in a VGM: how much does freq / carrier-TL move
*between* key-ons (i.e. during a held note) — that is the genuine software pitch /
volume envelope, as opposed to inter-note melody (changes that coincide with a new
key-on). The YM2612 hardware LFO does NOT emit register writes, so every freq/TL
write here is software; intra-note value CHANGES are the envelopes we'd replicate.

Usage: vgm_intranote.py <file.vgm> [label]
"""
import struct, sys

# channel -> (port, fnum_lo_reg, fnum_hi_reg, tl_regs[4], keysel)
# operators at reg offset +0/+4/+8/+C ; per-channel index added.
def chan_regs():
    chans = []
    # port0 ch 0,1,2 (keysel 0,1,2) ; port1 ch 3,4,5 (keysel 4,5,6)
    for port, base_ch, ksel in [(0,0,0),(0,1,1),(0,2,2),(1,0,4),(1,1,5),(1,2,6)]:
        lo = 0xA0 + base_ch
        hi = 0xA4 + base_ch
        tl = [0x40 + op*4 + base_ch for op in range(4)]
        chans.append({'port':port,'lo':lo,'hi':hi,'tl':tl,'ksel':ksel})
    return chans

def parse(path):
    b=open(path,'rb').read()
    ver=struct.unpack_from('<I',b,8)[0]; do=struct.unpack_from('<I',b,0x34)[0]
    i=0x40 if (ver<0x150 or do==0) else 0x34+do
    n=len(b)
    reg=[[0]*0x100,[0]*0x100]  # port0, port1
    chans=chan_regs()
    # per channel: list of "note intervals"; each = dict of fnum list, tl lists
    cur=[None]*6
    notes=[[] for _ in range(6)]
    def fnum(ci):
        c=chans[ci]; p=c['port']
        return ((reg[p][c['hi']]&0x3f)<<8)|reg[p][c['lo']]   # block(3)+fnum(11) packed; compare relative
    def snap_tl(ci):
        c=chans[ci]; p=c['port']
        return tuple(reg[p][t] for t in c['tl'])
    while i<n:
        cmd=b[i];i+=1
        if cmd==0x66:break
        elif cmd in (0x52,0x53):
            p=0 if cmd==0x52 else 1
            r=b[i];v=b[i+1];i+=2; reg[p][r]=v
            if r==0x28:
                ksel=v&0x07; ops=(v>>4)&0x0f
                ci=[j for j,c in enumerate(chans) if c['ksel']==ksel]
                if ci and ops:   # key ON -> start a new note interval
                    ci=ci[0]
                    cur[ci]={'fn':[fnum(ci)],'tl':[snap_tl(ci)]}
                    notes[ci].append(cur[ci])
            else:
                # if this reg belongs to a channel with an open note, record the new value
                for ci,c in enumerate(chans):
                    if cur[ci] is None: continue
                    if c['port']==p and r in (c['lo'],c['hi']):
                        cur[ci]['fn'].append(fnum(ci))
                    if c['port']==p and r in c['tl']:
                        cur[ci]['tl'].append(snap_tl(ci))
        elif cmd==0x61:i+=2
        elif cmd in (0x62,0x63):pass
        elif 0x70<=cmd<=0x7f:pass
        elif cmd==0x50:i+=1
        elif cmd==0x4f:i+=1
        elif cmd==0x67:sz=struct.unpack_from('<I',b,i+2)[0];i+=6+sz
        elif cmd==0x68:i+=11
        elif 0x51<=cmd<=0x5f:i+=2
        elif 0x40<=cmd<=0x4e:i+=2
        elif 0x90<=cmd<=0x95:i+=4
        elif 0xa0<=cmd<=0xbf:i+=2
        elif 0xc0<=cmd<=0xdf:i+=3
        elif 0xe0<=cmd<=0xff:i+=4
        elif 0x30<=cmd<=0x3f:i+=1
    return notes

def report(path,label):
    notes=parse(path)
    print(f"\n=== {label}: {path.split('/')[-1]} ===")
    print(f"{'ch':>4} {'notes':>6} {'fnumChg/note':>13} {'fnumRange':>10} {'tlChg/note':>11} {'tlRange':>8}")
    for ci in range(6):
        nl=[x for x in notes[ci] if x]
        if not nl:
            print(f"FM{ci+1:>2} {'(silent)':>6}"); continue
        # intra-note fnum changes = number of distinct consecutive fnum values minus 1
        fchg=[]; frng=[]; tchg=[]; trng=[]
        for note in nl:
            fns=note['fn']
            chg=sum(1 for a,b in zip(fns,fns[1:]) if a!=b)
            fchg.append(chg); frng.append(max(fns)-min(fns) if fns else 0)
            # carrier TL = the op whose TL moves most across the note
            tls=note['tl']
            if len(tls)>=1:
                per_op=[[t[op] for t in tls] for op in range(4)]
                opchg=[sum(1 for a,b in zip(seq,seq[1:]) if a!=b) for seq in per_op]
                oprng=[max(seq)-min(seq) for seq in per_op]
                tchg.append(max(opchg)); trng.append(max(oprng))
        avg=lambda L:sum(L)/len(L) if L else 0
        print(f"FM{ci+1:>2} {len(nl):>6} {avg(fchg):>13.1f} {avg(frng):>10.0f} {avg(tchg):>11.1f} {avg(trng):>8.0f}")

if __name__=='__main__':
    report(sys.argv[1], sys.argv[2] if len(sys.argv)>2 else 'capture')
