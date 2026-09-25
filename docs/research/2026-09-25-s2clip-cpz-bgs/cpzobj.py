import struct, collections
d = open('/home/volence/sonic_hacks/s2disasm/level/objects/CPZ_1.bin', 'rb').read()
objs = []
for i in range(0, len(d) - 5, 6):
    x, y, oid, sub = struct.unpack('>HHBB', d[i:i + 6])
    if x == 0xFFFF:
        break
    objs.append((x, y & 0xFFF, oid, sub))
print(len(objs), 'objects')
for x, y, oid, sub in objs:
    if oid == 0x79:
        print(f"starpost x={x} y={y} sub={sub}")
# objects per 2048 section
cnt = collections.Counter(x // 2048 for x, *_ in objs)
print('objects per 2048-px zone section', sorted(cnt.items()))
ids = collections.Counter(oid for *_, oid, s in objs)
print('ids', {f"${k:02X}": v for k, v in sorted(ids.items())})
