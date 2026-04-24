#!/usr/bin/env python3
"""Kosinski Plus Moduled (KosPM) decompressor — for compression ratio comparison only."""

import struct
import sys


class BitReader:
    def __init__(self, data, pos):
        self.data = data
        self.pos = pos
        self.bits_left = 0
        self.current = 0

    def pop(self):
        if self.bits_left == 0:
            self.current = self.data[self.pos]
            self.pos += 1
            self.bits_left = 8
        self.bits_left -= 1
        bit = (self.current >> 7) & 1
        self.current = (self.current << 1) & 0xFF
        return bit


def decompress_kosplus(data, pos):
    """Decompress one Kosinski Plus module. Returns (decompressed_bytes, new_pos)."""
    bits = BitReader(data, pos)
    output = bytearray()

    while True:
        if bits.pop():
            output.append(data[bits.pos])
            bits.pos += 1
        else:
            if bits.pop():
                high_byte = data[bits.pos]
                low_byte = data[bits.pos + 1]
                bits.pos += 2

                offset = ((high_byte & 0xF8) << 5) | low_byte
                offset = 0x2000 - offset
                count = high_byte & 7

                if count != 0:
                    count = 10 - count
                else:
                    count = data[bits.pos] + 9
                    bits.pos += 1
                    if count == 9:
                        break
            else:
                offset = 0x100 - data[bits.pos]
                bits.pos += 1
                count = 2
                if bits.pop():
                    count += 2
                if bits.pop():
                    count += 1

            src = len(output) - offset
            for j in range(count):
                output.append(output[src + j])

    return bytes(output), bits.pos


def decompress_kospm(data):
    """Decompress Kosinski Plus Moduled data. Returns decompressed bytes."""
    total_size = struct.unpack_from('>H', data, 0)[0]
    total_modules = (total_size + 0xFFF) // 0x1000
    pos = 2

    output = bytearray()
    for i in range(total_modules):
        module_data, pos = decompress_kosplus(data, pos)
        output.extend(module_data)

    return bytes(output)


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <input.kospm> <output.bin>")
        sys.exit(1)

    with open(sys.argv[1], 'rb') as f:
        compressed = f.read()

    decompressed = decompress_kospm(compressed)

    with open(sys.argv[2], 'wb') as f:
        f.write(decompressed)

    ratio = len(compressed) / len(decompressed) if decompressed else 0
    print(f"KosPM: {len(compressed)} -> {len(decompressed)} bytes (ratio {ratio:.3f})")


if __name__ == '__main__':
    main()
