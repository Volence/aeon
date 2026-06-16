#!/usr/bin/env python3
import sys

r = ['b','c','d','e','h','l','(hl)','a']
rp = ['bc','de','hl','sp']
rp2 = ['bc','de','hl','af']
cc = ['nz','z','nc','c','po','pe','p','m']
alu = ['add a,','adc a,','sub ','sbc a,','and ','xor ','or ','cp ']
rot = ['rlc','rrc','rl','rr','sla','sra','sll','srl']

def s8(b): return b-256 if b>127 else b

class D:
    def __init__(self, data, base=0):
        self.d=data; self.base=base
    def u8(self,p): return self.d[p]
    def u16(self,p): return self.d[p]|(self.d[p+1]<<8)
    def disasm(self,p):
        # returns (length, text)
        d=self.d; o=d[p]
        if o==0xCB: return self.cb(p)
        if o==0xED: return self.ed(p)
        if o==0xDD: return self.idx(p,'ix')
        if o==0xFD: return self.idx(p,'iy')
        return self.main(p)
    def main(self,p):
        d=self.d; o=d[p]
        x=o>>6; y=(o>>3)&7; z=o&7; pp=(o>>4)&3; q=(o>>3)&1
        if o==0x00: return 1,'nop'
        if o==0x76: return 1,'halt'
        if o==0xF3: return 1,'di'
        if o==0xFB: return 1,'ei'
        if o==0x07: return 1,'rlca'
        if o==0x0F: return 1,'rrca'
        if o==0x17: return 1,'rla'
        if o==0x1F: return 1,'rra'
        if o==0x27: return 1,'daa'
        if o==0x2F: return 1,'cpl'
        if o==0x37: return 1,'scf'
        if o==0x3F: return 1,'ccf'
        if o==0xE9: return 1,'jp (hl)'
        if o==0xF9: return 1,'ld sp,hl'
        if o==0xEB: return 1,'ex de,hl'
        if o==0x08: return 1,"ex af,af'"
        if o==0xD9: return 1,'exx'
        if o==0xE3: return 1,'ex (sp),hl'
        # ld r,n / various
        if x==0: # misc
            if z==0:
                if y==0: return 1,'nop'
                if y==1: return 1,"ex af,af'"
                if y==2: return 2,'djnz $%04X'%(p+2+s8(d[p+1])+self.base)
                if y==3: return 2,'jr $%04X'%(p+2+s8(d[p+1])+self.base)
                return 2,'jr %s,$%04X'%(cc[y-4],p+2+s8(d[p+1])+self.base)
            if z==1:
                if q==0: return 3,'ld %s,$%04X'%(rp[pp],self.u16(p+1))
                return 1,'add hl,%s'%rp[pp]
            if z==2:
                tbl={0:'ld (bc),a',1:'ld a,(bc)',2:'ld (de),a',3:'ld a,(de)'}
                if y<4: return 1,tbl[y]
                if y==4: return 3,'ld ($%04X),hl'%self.u16(p+1)
                if y==5: return 3,'ld hl,($%04X)'%self.u16(p+1)
                if y==6: return 3,'ld ($%04X),a'%self.u16(p+1)
                return 3,'ld a,($%04X)'%self.u16(p+1)
            if z==3:
                if q==0: return 1,'inc %s'%rp[pp]
                return 1,'dec %s'%rp[pp]
            if z==4: return 1,'inc %s'%r[y]
            if z==5: return 1,'dec %s'%r[y]
            if z==6: return 2,'ld %s,$%02X'%(r[y],d[p+1])
            # z==7 handled above (rlca etc) but fallback
            rota=['rlca','rrca','rla','rra','daa','cpl','scf','ccf']
            return 1,rota[y]
        if x==1: # ld r,r'
            return 1,'ld %s,%s'%(r[y],r[z])
        if x==2: # alu r
            return 1,'%s%s'%(alu[y],r[z])
        # x==3
        if z==0: return 1,'ret %s'%cc[y]
        if z==1:
            if q==0: return 1,'pop %s'%rp2[pp]
            sp={0:'ret',1:'exx',2:'jp (hl)',3:'ld sp,hl'}
            return 1,sp[pp]
        if z==2: return 3,'jp %s,$%04X'%(cc[y],self.u16(p+1))
        if z==3:
            if y==0: return 3,'jp $%04X'%self.u16(p+1)
            if y==2: return 2,'out ($%02X),a'%d[p+1]
            if y==3: return 2,'in a,($%02X)'%d[p+1]
            sp={4:'ex (sp),hl',5:'ex de,hl',6:'di',7:'ei'}
            return 1,sp[y]
        if z==4: return 3,'call %s,$%04X'%(cc[y],self.u16(p+1))
        if z==5:
            if q==0: return 1,'push %s'%rp2[pp]
            if pp==0: return 3,'call $%04X'%self.u16(p+1)
            return 1,'?'
        if z==6: return 2,'%s$%02X'%(alu[y],d[p+1])
        return 1,'rst $%02X'%(y*8)
    def cb(self,p):
        d=self.d; o=d[p+1]; x=o>>6; y=(o>>3)&7; z=o&7
        if x==0: return 2,'%s %s'%(rot[y],r[z])
        if x==1: return 2,'bit %d,%s'%(y,r[z])
        if x==2: return 2,'res %d,%s'%(y,r[z])
        return 2,'set %d,%s'%(y,r[z])
    def ed(self,p):
        d=self.d; o=d[p+1]; x=o>>6; y=(o>>3)&7; z=o&7; pp=(o>>4)&3; q=(o>>3)&1
        ext={0x44:'neg',0x45:'retn',0x4D:'reti',0x46:'im 0',0x56:'im 1',0x5E:'im 2',
             0x47:'ld i,a',0x4F:'ld r,a',0x57:'ld a,i',0x5F:'ld a,r',0x67:'rrd',0x6F:'rld',
             0xA0:'ldi',0xA1:'cpi',0xA2:'ini',0xA3:'outi',0xA8:'ldd',0xA9:'cpd',0xAA:'ind',0xAB:'outd',
             0xB0:'ldir',0xB1:'cpir',0xB2:'inir',0xB3:'otir',0xB8:'lddr',0xB9:'cpdr',0xBA:'indr',0xBB:'otdr'}
        if o in ext: return 2,ext[o]
        if x==1:
            if z==2:
                return 2,('sbc hl,%s' if q==0 else 'adc hl,%s')%rp[pp]
            if z==3:
                if q==0: return 4,'ld ($%04X),%s'%(self.u16(p+2),rp[pp])
                return 4,'ld %s,($%04X)'%(rp[pp],self.u16(p+2))
            if z==0: return 2,'in %s,(c)'%r[y]
            if z==1: return 2,'out (c),%s'%r[y]
        return 2,'ed?%02X'%o
    def idx(self,p,ix):
        d=self.d; o=d[p+1]
        if o==0xCB:
            disp=s8(d[p+2]); sub=d[p+3]; y=(sub>>3)&7; x=sub>>6; z=sub&7
            tgt='(%s%+d)'%(ix,disp)
            if x==0: return 4,'%s %s'%(rot[y],tgt)
            if x==1: return 4,'bit %d,%s'%(y,tgt)
            if x==2: return 4,'res %d,%s'%(y,tgt)
            return 4,'set %d,%s'%(y,tgt)
        # LD (IX+d),n : DD 36 d n -- immediate follows the displacement byte.
        # The generic path mis-reads the immediate from the displacement slot,
        # so handle it explicitly (this is the only main opcode mixing (hl)+imm).
        if o==0x36:
            disp=s8(d[p+2]); n=d[p+3]
            return 4,'ld (%s%+d),$%02X'%(ix,disp,n)
        # substitute hl->ix, (hl)->(ix+d), h/l->ixh/ixl
        ln,txt=self.main(p+1)
        # determine if (hl) used -> needs displacement byte
        x=o>>6; y=(o>>3)&7; z=o&7
        uses_mem = ('(hl)' in txt)
        t=txt.replace('hl',ix)
        if uses_mem:
            disp=s8(d[p+2]); t=t.replace('(%s)'%ix,'(%s%+d)'%(ix,disp))
            return ln+2, t
        return ln+1, t

def run(path, base=0, maxlen=None, start=0):
    data=open(path,'rb').read()
    if maxlen: data=data[:maxlen]
    dis=D(data, base)
    p=start
    out=[]
    while p < len(data):
        try:
            ln,txt=dis.disasm(p)
        except Exception as e:
            ln,txt=1,'db $%02X'%data[p]
        if ln<=0: ln=1
        hexb=' '.join('%02X'%data[p+i] for i in range(ln) if p+i<len(data))
        out.append('%04X  %-12s %s'%(p+base,hexb,txt))
        p+=ln
    return out

if __name__=='__main__':
    path=sys.argv[1]
    base=int(sys.argv[2],0) if len(sys.argv)>2 else 0
    start=int(sys.argv[3],0) if len(sys.argv)>3 else 0
    for line in run(path,base,start=start):
        print(line)
