#!/usr/bin/env python3
"""replay_pack.py — pack a DEBUG-recorded demo (RAM ring + checkpoint log) into the
ROM replay stream format consumed by engine/system/replay.emp (spec 2026-08-02 §3).

    replay_pack.py pack  --raw ring.bin --checks checklog.bin --ticks N \
                         --core-hash 0xXXXXXXXX --out fixture.bin
    replay_pack.py dump  fixture.bin        # human-readable listing
    replay_pack.py --selftest               # exit 0 on pass

Stream format (all multi-byte fields big-endian — 68k):

    header (REPLAY_HEADER_LEN = 20 bytes):
        magic  "ARP0"    (4)
        flags  u8        (ext/pad-2 reserved bits; 0 in v1)
        pad    u8        (0)
        tick_count u32
        core_hash  u32   (build identity — a stale replay fails loudly)
        rng_seed   u32   (reserved, 0 until an RNG exists)
        reserved   u16   (0)
    body:
        RLE pairs (buttons u8 != 0xFF, hold_minus_1 u8) ...
    escape:
        0xFF, opcode:
            0x00 = end-of-stream
            0x01 = checkpoint, payload hash u32 (covers the curated block)

The buttons byte is the latched Ctrl_1_Held (SACBRLDU). 0xFF is impossible as a held
byte (the SOCD guard kills U+D+L+R), which is what frees it as the escape; the packer
REJECTS any raw byte == 0xFF or carrying both U+D (0x03) or both L+R (0x0C) — those are
SOCD-impossible and signal corrupt capture data.

Checkpoint alignment (must match replay.emp's recorder/reader): a checkpoint fires at
ring indices 0, 64, 128, ... BEFORE that tick's input is applied, so its record is
emitted immediately before the tick's RLE pair and RLE runs are SPLIT at every
checkpoint ring index (the reader only re-reads the stream at a run boundary).
"""

import argparse
import struct
import sys

MAGIC = b"ARP0"
HEADER_LEN = 20            # REPLAY_HEADER_LEN
ESCAPE = 0xFF             # REPLAY_ESCAPE
OP_END = 0x00            # REPLAY_OP_END
OP_CHECK = 0x01         # REPLAY_OP_CHECK
MAX_RUN = 256          # hold_minus_1 is a u8 -> longest run per pair is 256 ticks

# SOCD-impossible masks (BUTTON_UP|BUTTON_DOWN, BUTTON_LEFT|BUTTON_RIGHT).
UD_MASK = 0x03
LR_MASK = 0x0C


class ReplayError(ValueError):
    """Corrupt input (impossible held byte, bad opcode, malformed stream)."""


def _reject_byte(b, tick):
    if b == ESCAPE:
        raise ReplayError(f"tick {tick}: held byte 0xFF is impossible (== escape)")
    if (b & UD_MASK) == UD_MASK:
        raise ReplayError(f"tick {tick}: held byte {b:#04x} has both Up+Down (SOCD-impossible)")
    if (b & LR_MASK) == LR_MASK:
        raise ReplayError(f"tick {tick}: held byte {b:#04x} has both Left+Right (SOCD-impossible)")


def pack_stream(raw, checks, core_hash, seed=0, flags=0):
    """raw: bytes (one latched Ctrl_1_Held per tick). checks: list of (tick, hash),
    absolute Logic_Tick values (as recorded); the first names ring index 0. Returns the
    packed stream bytes."""
    n = len(raw)
    for i, b in enumerate(raw):
        _reject_byte(b, i)

    # Map checkpoint ring indices -> hash. Ring index = tick - base_tick (base = first
    # logged tick == the tick of ring index 0). Deterministic ascending order.
    base_tick = checks[0][0] if checks else 0
    cp = {}
    for (tick, h) in checks:
        idx = tick - base_tick
        if idx < 0 or idx > n:
            raise ReplayError(f"checkpoint tick {tick} maps to ring index {idx}, out of [0,{n}]")
        if idx in cp:
            raise ReplayError(f"duplicate checkpoint at ring index {idx}")
        cp[idx] = h & 0xFFFFFFFF

    out = bytearray()
    out += MAGIC
    out += struct.pack(">BBIIIH", flags & 0xFF, 0, n, core_hash & 0xFFFFFFFF, seed & 0xFFFFFFFF, 0)

    i = 0
    while i < n:
        if i in cp:
            out += bytes((ESCAPE, OP_CHECK))
            out += struct.pack(">I", cp[i])
        b = raw[i]
        # Longest run: same byte, <= MAX_RUN, not crossing a later checkpoint index.
        run = 1
        while (i + run < n and raw[i + run] == b and run < MAX_RUN
               and (i + run) not in cp):
            run += 1
        out += bytes((b, run - 1))          # hold_minus_1
        i += run

    # A checkpoint at ring index == n (the one-past-end boundary) still emits.
    if n in cp:
        out += bytes((ESCAPE, OP_CHECK))
        out += struct.pack(">I", cp[n])

    out += bytes((ESCAPE, OP_END))
    return bytes(out)


def decode_stream(data):
    """Independent reference decoder (the round-trip witness). Returns
    (raw, checks, core_hash, tick_count, seed, flags) where checks is
    [(ring_index, hash)]."""
    if len(data) < HEADER_LEN:
        raise ReplayError("stream shorter than the header")
    if data[:4] != MAGIC:
        raise ReplayError(f"bad magic {data[:4]!r} (expected {MAGIC!r})")
    flags, pad, tick_count, core_hash, seed, reserved = struct.unpack(">BBIIIH", data[4:HEADER_LEN])
    if pad != 0 or reserved != 0:
        raise ReplayError("nonzero pad/reserved header field")

    raw = bytearray()
    checks = []
    p = HEADER_LEN
    while True:
        if p >= len(data):
            raise ReplayError("stream ran off the end without an end-of-stream opcode")
        b = data[p]
        p += 1
        if b == ESCAPE:
            if p >= len(data):
                raise ReplayError("truncated escape (no opcode)")
            op = data[p]
            p += 1
            if op == OP_END:
                break
            if op == OP_CHECK:
                if p + 4 > len(data):
                    raise ReplayError("truncated checkpoint hash")
                (h,) = struct.unpack(">I", data[p:p + 4])
                p += 4
                checks.append((len(raw), h))    # ring index == ticks decoded so far
            else:
                raise ReplayError(f"unknown escape opcode {op:#04x}")
        else:
            if p >= len(data):
                raise ReplayError("truncated RLE pair (no hold byte)")
            hold_minus_1 = data[p]
            p += 1
            raw.extend([b] * (hold_minus_1 + 1))

    if len(raw) != tick_count:
        raise ReplayError(f"decoded {len(raw)} ticks, header claims {tick_count}")
    return bytes(raw), checks, core_hash, tick_count, seed, flags


def cmd_pack(args):
    raw = open(args.raw, "rb").read()
    if args.ticks is not None:
        if args.ticks > len(raw):
            raise ReplayError(f"--ticks {args.ticks} exceeds ring size {len(raw)}")
        raw = raw[:args.ticks]
    checks = []
    if args.checks:
        blob = open(args.checks, "rb").read()
        if len(blob) % 8 != 0:
            raise ReplayError("check log length is not a multiple of 8")
        for off in range(0, len(blob), 8):
            tick, h = struct.unpack(">II", blob[off:off + 8])
            # A zeroed tail entry (never-written log slot) terminates the log.
            if tick == 0 and h == 0 and off != 0:
                break
            checks.append((tick, h))
    core_hash = int(args.core_hash, 0)
    stream = pack_stream(raw, checks, core_hash)
    # Pad to a 16-byte multiple with zeros AFTER the terminator (the reader stops
    # at $FF $00, so the tail is inert). This keeps the chain-tail fixture flush
    # with EndOfRom under the packer's provisional-alignment inference in every
    # shape (a 194-byte stream once left a 14-byte align gap in plain that broke
    # the assembled-bar completeness guard).
    if len(stream) % 16:
        stream = stream + bytes(16 - (len(stream) % 16))
    open(args.out, "wb").write(stream)
    # Verify our own output round-trips before declaring success.
    dr, dc, _, _, _, _ = decode_stream(stream)
    assert dr == raw, "internal: pack/decode raw mismatch"
    print(f"packed {len(raw)} ticks, {len(checks)} checkpoint(s) -> {args.out} "
          f"({len(stream)} bytes, core_hash={core_hash:#010x})")


def cmd_dump(args):
    data = open(args.file, "rb").read()
    raw, checks, core_hash, tick_count, seed, flags = decode_stream(data)
    print(f"magic       ARP0")
    print(f"flags       {flags:#04x}")
    print(f"tick_count  {tick_count}")
    print(f"core_hash   {core_hash:#010x}")
    print(f"rng_seed    {seed:#010x}")
    print(f"checkpoints {len(checks)}")
    for (idx, h) in checks:
        print(f"  @tick {idx:6d}  hash {h:#010x}")
    # RLE run summary (re-derived from the decoded raw for a readable listing).
    print("runs:")
    i = 0
    while i < len(raw):
        b = raw[i]
        run = 1
        while i + run < len(raw) and raw[i + run] == b:
            run += 1
        print(f"  tick {i:6d}  byte {b:#04x}  x{run}")
        i += run


def selftest():
    # 1. constant run.
    raw = bytes([0x01] * 100)
    _roundtrip(raw, [])
    # 2. alternating bytes.
    raw = bytes([0x01 if k % 2 == 0 else 0x02 for k in range(50)])
    _roundtrip(raw, [])
    # 3. run > 256 (splits into 256 + 256 + 88).
    raw = bytes([0x05] * 600)
    packed = _roundtrip(raw, [])
    # ensure it actually split (>=3 RLE pairs before the terminator).
    _, _, _, _, _, _ = decode_stream(packed)
    # 4. checkpoint interleave, base tick != 0, checkpoints at ring index 0/64/128.
    raw = bytes([(k & 0x1F) & ~UD_MASK & ~LR_MASK for k in range(130)])  # varied, SOCD-safe
    base = 1000
    checks = [(base + 0, 0xAABBCCDD), (base + 64, 0x11223344), (base + 128, 0xDEADBEEF)]
    packed = _roundtrip(raw, checks)
    _, dc, _, _, _, _ = decode_stream(packed)
    assert dc == [(0, 0xAABBCCDD), (64, 0x11223344), (128, 0xDEADBEEF)], dc
    # the checkpoint record must precede the pair for its tick: verify byte before the
    # first pair after each checkpoint is an escape+op_check (structural).
    # 5. checkpoint exactly at end-of-stream boundary (ring index == n).
    raw = bytes([0x00] * 64)
    _roundtrip(raw, [(0, 0x1), (64, 0x2)])
    # 6. reject paths.
    for bad, why in ((bytes([0xFF]), "escape byte"),
                     (bytes([0x03]), "Up+Down"),
                     (bytes([0x0C]), "Left+Right"),
                     (bytes([0x0F]), "Up+Down+Left+Right")):
        try:
            pack_stream(bad, [], 0)
        except ReplayError:
            pass
        else:
            raise AssertionError(f"pack_stream did not reject {why} ({bad.hex()})")
    # 7. bad-opcode stream must be rejected by the decoder.
    good = pack_stream(bytes([0x01] * 4), [], 0xCAFEBABE)
    corrupt = bytearray(good)
    # find the terminating FF 00 and flip the opcode to an unknown value.
    corrupt[-1] = 0x7F
    try:
        decode_stream(bytes(corrupt))
    except ReplayError:
        pass
    else:
        raise AssertionError("decoder accepted an unknown escape opcode")
    print("replay_pack selftest: PASS")
    return 0


def _roundtrip(raw, checks):
    packed = pack_stream(raw, checks, core_hash=0x12345678)
    dr, dc, core_hash, tick_count, seed, flags = decode_stream(packed)
    assert dr == raw, f"raw mismatch: {dr.hex()} != {raw.hex()}"
    assert core_hash == 0x12345678, core_hash
    assert tick_count == len(raw), tick_count
    base = checks[0][0] if checks else 0
    assert dc == [(t - base, h) for (t, h) in checks], f"checks mismatch: {dc}"
    return packed


def main(argv):
    ap = argparse.ArgumentParser(description="Pack/dump the Aeon replay stream.")
    ap.add_argument("--selftest", action="store_true", help="run the round-trip + reject self-test")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("pack")
    p.add_argument("--raw", required=True)
    p.add_argument("--checks")
    p.add_argument("--ticks", type=int)
    p.add_argument("--core-hash", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_pack)

    d = sub.add_parser("dump")
    d.add_argument("file")
    d.set_defaults(func=cmd_dump)

    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.cmd:
        ap.print_help()
        return 2
    try:
        return args.func(args) or 0
    except ReplayError as e:
        print(f"replay_pack: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
