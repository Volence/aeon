#!/usr/bin/env python3
"""Golden-vector generator for the DEBUG boot compression self-test.

Builds one fixed payload that forces every S4LZ v3 decoder path, compresses
it three ways (S4LZ v3 plain, S4LZ v3 + dictionary, ZX0 via salvador), and
emits the blobs plus an asm include with expected-size/checksum constants
into data/generated/test/. The 68000 self-test (debug/compression_selftest.asm)
decompresses each vector at boot and compares a 16-bit additive word checksum
against the constants emitted here — the only ASM-vs-encoder verification in
the project (everything else is Python-vs-Python).

Path coverage is PROVEN at build time: a token walker inspects the encoder's
actual output streams and the generator fails if any required v3 feature is
missing (so encoder changes can't silently rot the fixture).

Token map of the payload (verified by the walker, see require() calls):
    token 1: lit=1, match-ext (23w), offmark=1   -> overlap copy at offset 2,
                                                    match extension, short form
    token 2: lit-ext (40w), match-ext (30w),
             offmark=40                          -> BOTH nibbles extended with
                                                    short-form offset
    token 3: lit-ext (260w), match=8w, offmark=0 -> long-form offset word
                                                    (after the literals)
    token 4: lit=3, match=3, offmark=3           -> small unrolled literal +
                                                    small short-form match
    token 5: lit=4, match=0                      -> literal-only tail
Dictionary vector: dict = payload[0:256]; first token is a 128-word
short-form match reaching entirely below the output start (rebase path).

Usage:
    python3 tools/gen_compression_vectors.py            # generate
    python3 tools/gen_compression_vectors.py --check    # generate + verbose
"""

import os
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s4lz

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUTPUT_DIR = os.path.join(ROOT, "games", "sonic4", "data", "generated", "test")
SALVADOR = os.path.join(ROOT, "tools", "bin", "salvador")

DICT_LEN = 256          # dictionary bytes for the dict vector (word-even)
POISON_WORD = 0xA5A5    # must match debug/compression_selftest.asm poison fill

# ZX0 wrapper — must match build.sh / constants.asm ART_VER_ZX0
ART_VER_ZX0 = 2


# ---------------------------------------------------------------------------
# Payload construction
# ---------------------------------------------------------------------------

def build_payload() -> bytes:
    """Fixed payload engineered so the v3 DP encoder emits every token form."""
    out = bytearray()

    # A (0..47): word run -> 1 literal + 23-word overlapping match at offset 2
    out += bytes([0xAB, 0xCD]) * 24

    # B (48..127): 40 unique words -> literal extension fodder
    for i in range(40):
        out += struct.pack(">H", 0x1000 + 17 * i)

    # B2 (128..187): 30-word repeat of B's start at distance 80 (short form).
    # Combined with B's 40 literals this forces ONE token with both nibbles
    # extended and a short-form offmark.
    out += out[48:48 + 60]

    # C (188..707): 260 unique filler words — pushes D's source > 510 bytes
    # away so its offset must take the long form.
    for i in range(260):
        out += struct.pack(">H", 0x4000 + 23 * i)

    # D (708..723): 8-word repeat of B words 30..37 (bytes 108..123). Distance
    # = 708-108 = 600 > 510 -> long-form offset word (emitted after the 260
    # literals, exercising the v3 stream-order rule).
    out += out[108:108 + 16]

    # E (724..735): 3 unique words, then repeat them at distance 6 -> small
    # short-form match through the unrolled copy path.
    for i in range(3):
        out += struct.pack(">H", 0x7001 + 2 * i)
    out += out[-6:]

    # Tail (736..743): 4 unique words -> literal-only final token.
    for i in range(4):
        out += struct.pack(">H", 0x7101 + 2 * i)

    assert len(out) % 2 == 0
    assert len(out) <= 1024, f"payload {len(out)}B exceeds the 1KB budget"
    return bytes(out)


def word_checksum(data: bytes) -> int:
    """16-bit additive big-endian word checksum (mirrors the 68000 loop)."""
    assert len(data) % 2 == 0
    total = 0
    for i in range(0, len(data), 2):
        total = (total + struct.unpack_from(">H", data, i)[0]) & 0xFFFF
    return total


# ---------------------------------------------------------------------------
# v3 stream walker — proves which decoder paths a stream exercises
# ---------------------------------------------------------------------------

def walk_v3_stream(stream: bytes, dict_len: int = 0) -> dict:
    """Walk a v3 token stream; return coverage flags for every decoder path."""
    flags = {
        "lit_small": False,      # 1-14 literal words (unrolled copy)
        "lit_ext": False,        # literal extension word
        "match_small": False,    # 1-14 match words (unrolled copy)
        "match_ext": False,      # match extension word
        "short_offset": False,   # offmark != 0
        "long_offset": False,    # offmark == 0 with a match (offset word)
        "both_ext_short": False, # lit nibble 15 AND match nibble 15, short form
        "overlap_2": False,      # offmark == 1 (offset 2, overlapping copy)
        "dict_hit": False,       # match source below the output start
        "lit_only_token": False, # match nibble 0 (token-loop continue path)
    }
    out_len = 0
    pos = 4  # skip [size.w][flags.b][version.b]
    if stream[3] != s4lz.VERSION_V3:
        raise ValueError(f"not a v3 stream (version byte {stream[3]})")

    while pos + 1 < len(stream):
        token = stream[pos]
        offmark = stream[pos + 1]
        pos += 2
        if token == 0x00:
            break

        lit_raw = (token >> 4) & 0x0F
        match_raw = token & 0x0F

        lit_count = lit_raw
        if lit_raw == 15:
            flags["lit_ext"] = True
            lit_count = struct.unpack_from(">H", stream, pos)[0]
            pos += 2
        elif lit_raw > 0:
            flags["lit_small"] = True
        pos += lit_count * 2
        out_len += lit_count * 2

        if match_raw == 0:
            flags["lit_only_token"] = True
            continue

        if offmark != 0:
            flags["short_offset"] = True
            offset = offmark * 2
            if offmark == 1:
                flags["overlap_2"] = True
        else:
            flags["long_offset"] = True
            offset = struct.unpack_from(">H", stream, pos)[0]
            pos += 2

        if lit_raw == 15 and match_raw == 15 and offmark != 0:
            flags["both_ext_short"] = True

        match_count = match_raw
        if match_raw == 15:
            flags["match_ext"] = True
            match_count = struct.unpack_from(">H", stream, pos)[0]
            pos += 2
        else:
            flags["match_small"] = True

        if out_len - offset < 0:
            if dict_len + (out_len - offset) < 0:
                raise ValueError("match reaches below the dictionary")
            flags["dict_hit"] = True
        out_len += match_count * 2

    # Ground-truth hard checks: the stream must be fully consumed at EOS
    # and the decompressed length must match the header's size field.
    expected_size = struct.unpack_from(">H", stream, 0)[0]
    if out_len != expected_size:
        raise SystemExit(
            f"FAIL: walker out_len={out_len} != header size={expected_size} "
            f"— decompressed length mismatch; encoder or payload changed")
    if pos != len(stream):
        raise SystemExit(
            f"FAIL: stream not fully consumed at EOS — {len(stream) - pos} "
            f"trailing bytes beyond expected padding; encoder or walker changed")

    return flags


def require(flags: dict, name: str, vector: str) -> None:
    if not flags[name]:
        raise SystemExit(
            f"FAIL: {vector} vector does not exercise '{name}' — the encoder's "
            f"parse changed; adjust build_payload() in {__file__}")


# ---------------------------------------------------------------------------
# ZX0 via salvador
# ---------------------------------------------------------------------------

def zx0_compress(payload: bytes) -> bytes:
    """Compress with salvador (modern/V2 format) and round-trip verify."""
    if not os.access(SALVADOR, os.X_OK):
        raise SystemExit(f"FAIL: salvador binary missing at {SALVADOR} "
                         f"(build.sh builds it before calling this script)")
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "in.bin")
        dst = os.path.join(td, "out.zx0")
        rtp = os.path.join(td, "roundtrip.bin")
        with open(src, "wb") as f:
            f.write(payload)
        subprocess.run([SALVADOR, src, dst], check=True,
                       stdout=subprocess.DEVNULL)
        subprocess.run([SALVADOR, "-d", dst, rtp], check=True,
                       stdout=subprocess.DEVNULL)
        with open(rtp, "rb") as f:
            if f.read() != payload:
                raise SystemExit("FAIL: salvador ZX0 round-trip mismatch")
        with open(dst, "rb") as f:
            stream = f.read()
    return struct.pack(">HBB", len(payload), 0, ART_VER_ZX0) + stream


# ---------------------------------------------------------------------------
# Corruption sensitivity unit
# ---------------------------------------------------------------------------

def check_corruption_detected(plain: bytes, payload: bytes, checksum: int) -> None:
    """Prove the checksum mechanism catches a single corrupted stream byte.

    This is the build-time stand-in for "corrupt a byte, watch the boot
    assert fire" — the live Exodus verification happens in Task 6.
    """
    # Corrupt one literal byte mid-stream (offset 20 sits inside segment B's
    # literal words for this fixture).
    corrupted = bytearray(plain)
    corrupted[20] ^= 0xFF
    try:
        out = s4lz.decompress(bytes(corrupted))
    except ValueError:
        return  # decode error = detected, fine
    if len(out) == len(payload) and word_checksum(out) == checksum:
        raise SystemExit("FAIL: corrupted stream produced the expected "
                         "checksum — checksum mechanism is broken")

    # And a corrupted PAYLOAD byte must change the checksum (sensitivity).
    bent = bytearray(payload)
    bent[0] ^= 0x01
    if word_checksum(bytes(bent)) == checksum:
        raise SystemExit("FAIL: payload checksum insensitive to corruption")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    verbose = "--check" in sys.argv[1:]
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    payload = build_payload()
    checksum = word_checksum(payload)

    # The asm self-test poisons the buffer with POISON_WORD between vectors;
    # the poison pattern's checksum must differ or a no-op decode could pass.
    poison_sum = (POISON_WORD * (len(payload) // 2)) & 0xFFFF
    if poison_sum == checksum:
        raise SystemExit("FAIL: payload checksum equals the poison-fill "
                         "checksum — perturb build_payload()")

    # --- Vector 1: S4LZ v3, no dictionary ---
    plain = s4lz.compress(payload)
    if s4lz.decompress(plain) != payload:
        raise SystemExit("FAIL: plain vector python round-trip mismatch")
    pflags = walk_v3_stream(plain)
    for feature in ("lit_small", "lit_ext", "match_small", "match_ext",
                    "short_offset", "long_offset", "both_ext_short",
                    "overlap_2", "lit_only_token"):
        require(pflags, feature, "plain")
    if pflags["dict_hit"]:
        raise SystemExit("FAIL: plain vector has dict hits?!")

    # --- Vector 2: same payload with a dictionary (rebase path) ---
    dictionary = payload[:DICT_LEN]
    dict_stream = s4lz.compress(payload, dictionary=dictionary)
    if s4lz.decompress(dict_stream, dictionary=dictionary) != payload:
        raise SystemExit("FAIL: dict vector python round-trip mismatch")
    dflags = walk_v3_stream(dict_stream, dict_len=DICT_LEN)
    require(dflags, "dict_hit", "dict")
    require(dflags, "short_offset", "dict")

    # --- Vector 3: ZX0 (salvador) with our 4-byte wrapper ---
    zx0 = zx0_compress(payload)

    check_corruption_detected(plain, payload, checksum)

    # Each vector decompresses into Decomp_Buffer (9,600 B) at boot.
    assert len(payload) <= 9600

    # --- Emit blobs ---
    blobs = {
        "payload.bin": payload,
        "s4lz_plain.bin": plain,
        "s4lz_dict.bin": dict_stream,
        "s4lz_dict_blob.bin": dictionary,
        "zx0.bin": zx0,
    }
    for name, data in blobs.items():
        with open(os.path.join(OUTPUT_DIR, name), "wb") as f:
            f.write(data)

    # --- Emit asm include (BINCLUDEs + expected constants) ---
    asm_path = os.path.join(OUTPUT_DIR, "vectors.asm")
    with open(asm_path, "w") as f:
        f.write(
            "; Golden compression self-test vectors — auto-generated by\n"
            "; tools/gen_compression_vectors.py — DO NOT EDIT\n"
            "; One payload, three encodings; see the generator for the token\n"
            "; map proving which decoder paths each vector exercises.\n"
            f"CSELF_PAYLOAD_SIZE = {len(payload)}\n"
            f"CSELF_PAYLOAD_SUM = ${checksum:04X}    "
            "; 16-bit additive BE word checksum\n"
            f"CSELF_DICT_LEN = {DICT_LEN}\n"
            "CSelf_S4LZ_Plain:\n"
            "    BINCLUDE \"data/generated/test/s4lz_plain.bin\"\n"
            "    align 2\n"
            "CSelf_S4LZ_Dict:\n"
            "    BINCLUDE \"data/generated/test/s4lz_dict.bin\"\n"
            "    align 2\n"
            "CSelf_Dict_Blob:\n"
            "    BINCLUDE \"data/generated/test/s4lz_dict_blob.bin\"\n"
            "    align 2\n"
            "CSelf_ZX0:\n"
            "    BINCLUDE \"data/generated/test/zx0.bin\"\n"
            "    align 2\n"
            "; Expected uncompressed payload (debug byte-compare reference)\n"
            "CSelf_Expected:\n"
            "    BINCLUDE \"data/generated/test/payload.bin\"\n"
            "    align 2\n"
        )

    if verbose:
        print(f"payload: {len(payload)}B checksum ${checksum:04X}")
        print(f"plain:   {len(plain)}B  flags: "
              f"{[k for k, v in pflags.items() if v]}")
        print(f"dict:    {len(dict_stream)}B (+{DICT_LEN}B dict)  flags: "
              f"{[k for k, v in dflags.items() if v]}")
        print(f"zx0:     {len(zx0)}B (wrapped)")
    print(f"Compression self-test vectors OK -> {OUTPUT_DIR} "
          f"(payload {len(payload)}B, sum ${checksum:04X}; "
          f"plain {len(plain)}B, dict {len(dict_stream)}B+{DICT_LEN}B, "
          f"zx0 {len(zx0)}B)")


if __name__ == "__main__":
    main()
