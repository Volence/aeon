#!/usr/bin/env python3
"""The build-time half of the LS-17 release-shape S4LZ fault checks.

WHAT THIS IS FOR, AND WHAT IT IS NOT.

`engine/compression/s4lz.emp` carries three checks that are present in the
SHIPPED ROM (owner ruling LS-17, 2026-09-09 — `crash`): a wrong stream-version
byte, a match reaching below the dictionary base, and a written extent that
disagrees with the header size word each branch into the crash-report screen
instead of running off into memory.

Those are RUNTIME checks. Nothing in the build executes them, so this file does
NOT prove they fire — only an emulator can do that. What it does prove is the
other half, and it is the half that can hurt a shipped game: **that no stream
this repo actually generates trips one of them.** A release-shape check that
false-fires is a crash screen on a valid ROM, which is strictly worse than the
silent corruption it replaced. So every arm below re-derives one check's exact
predicate over the real corpus of S4LZ streams in `games/*/data/generated/`.

Read a failure here as "the release ROM would crash-screen on this data", not
as "a test is unhappy". If a future encoder change makes one of these arms go
red, the choice is to fix the encoder or to re-derive the check — not to relax
the arm.

Each arm carries a NEGATIVE fixture (a deliberately mutated copy of a real
stream) so a green can never mean "the walker stopped looking".
"""

import struct
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import s4lz  # noqa: E402  (path set above)

BLOCKS_PER_SECTION = 256
BLOCK_INDEX_SIZE = BLOCKS_PER_SECTION * 4
RAW_DIRECT_BIT = 1 << 31

# The structural offset ceiling the decoder's `suba.w` imposes (s4lz.emp header,
# "Offsets must stay < $8000"). Not one of the three checks — quoted here because
# the dict-depth arm's own bound is only meaningful under it.
SUBA_W_CEILING = 32766


# ---------------------------------------------------------------------------
# Corpus discovery
# ---------------------------------------------------------------------------

def _dict_lens():
    """Map section index -> dict length in bytes, from the generated .emp.

    The generator writes `OJZ_SEC{N}_BLOCK_DICT_LEN = <n>` lines; the runtime
    reads the same numbers through the act descriptor into `d4`.
    """
    out = {}
    for emp in REPO.glob("games/*/data/generated/*/*/sec_block_dicts.emp"):
        for line in emp.read_text().splitlines():
            line = line.strip()
            if "_BLOCK_DICT_LEN" not in line or "=" not in line:
                continue
            name, _, value = line.partition("=")
            name = name.split()[-1].strip()
            try:
                sec = int(name.split("SEC")[1].split("_")[0])
            except (IndexError, ValueError):
                continue
            value = value.split("//")[0].strip()
            out[(emp.parent, sec)] = int(value, 0)
    return out


def _sections():
    """Yield (label, blob_bytes, dict_len) for every generated section blob."""
    lens = _dict_lens()
    for blob_path in sorted(REPO.glob("games/*/data/generated/*/*/sec*_blocks.bin")):
        stem = blob_path.stem                      # e.g. "sec3_blocks"
        sec = int(stem[3:].split("_")[0])
        dict_len = lens.get((blob_path.parent, sec))
        if dict_len is None:
            pytest.fail(
                f"{blob_path.relative_to(REPO)} has no OJZ_SEC{sec}_BLOCK_DICT_LEN "
                f"in its sibling sec_block_dicts.emp — the corpus walk cannot "
                f"reproduce the runtime's d4 and would be grading nothing")
        yield (str(blob_path.relative_to(REPO)), blob_path.read_bytes(), dict_len)


def _streams(blob, dict_len):
    """Yield (block_index, stream_bytes) for every COMPRESSED block in a blob.

    Mirrors tile_cache.emp's dispatch: entry 0 = empty (no stream), bit 31 =
    raw-direct (no stream), anything else = a byte offset to a v3 stream.
    """
    for i in range(BLOCKS_PER_SECTION):
        entry = struct.unpack_from(">I", blob, i * 4)[0]
        if entry == 0 or entry & RAW_DIRECT_BIT:
            continue
        yield i, blob[entry:]


# ---------------------------------------------------------------------------
# The walker — one pass, reporting exactly what the three checks measure
# ---------------------------------------------------------------------------

def walk(stream, dict_len):
    """Return (version, declared_size, written_extent, max_dict_depth).

    `written_extent` is what `a1 - a3` holds at `.stream_done` (word-granular,
    BEFORE any truncation to the declared size) and `max_dict_depth` is the
    largest value the `.fault_dict` check's `d1` reaches — i.e. `dest_start - a2`
    for the deepest match that landed below the dest start.

    The extent is cross-checked against `s4lz._decompress_v3` in its own test
    below, so this walker cannot drift away from the shipped reference decoder
    without saying so.

    RELATED, and the reason this file only covers HALF the release ROM's exposure:
    `tools/gen_compression_vectors.py` has its own `walk_v3_stream`, and it already
    hard-fails generation on `out_len != header size` and on a match reaching below
    the dictionary. That generator runs on EVERY build (build.sh line ~561), so the
    DEBUG compression-self-test vectors are gated there and are not swept here. The
    two together cover both corpora a build can decode: those vectors (DEBUG boot
    self-test) and the generated block streams below (the release streaming path).
    Neither walker should be merged into the other casually -- that one asserts
    exact equality on payloads it also authored, this one asserts the decoder's
    looser +0/+1 word-pad contract over data it did not.
    """
    version = stream[3]
    declared = struct.unpack_from(">H", stream, 0)[0]
    out = 0                 # bytes written so far == (a1 - a3)
    depth = 0
    pos = 4

    while pos + 1 < len(stream):
        token = stream[pos]
        offmark = stream[pos + 1]
        pos += 2
        if token == 0:
            break
        lit = (token >> 4) & 0x0F
        match = token & 0x0F
        if lit == 15:
            lit = struct.unpack_from(">H", stream, pos)[0]
            pos += 2
        out += lit * 2
        pos += lit * 2
        if match == 0:
            continue
        if offmark != 0:
            offset = offmark * 2
        else:
            offset = struct.unpack_from(">H", stream, pos)[0]
            pos += 2
        if match == 15:
            match = struct.unpack_from(">H", stream, pos)[0]
            pos += 2
        if offset > out:                       # match source below the dest start
            depth = max(depth, offset - out)   # == d1 at the .fault_dict check
        out += match * 2

    return version, declared, out, depth


# ---------------------------------------------------------------------------
# Arm 0 — the corpus exists (a sweep over nothing is not evidence)
# ---------------------------------------------------------------------------

def test_the_corpus_is_not_empty():
    total = sum(len(list(_streams(b, d))) for _, b, d in _sections())
    assert total > 0, (
        "no compressed S4LZ streams found under games/*/data/generated/ — every "
        "arm below would pass vacuously. Re-run tools/regenerate-level.sh.")
    print(f"\nLS-17 corpus: {total} compressed S4LZ stream(s)")


# ---------------------------------------------------------------------------
# Arm 1 — .fault_version: every shipped stream declares version 1
# ---------------------------------------------------------------------------

def test_every_stream_is_version_1():
    bad = []
    for label, blob, dict_len in _sections():
        for idx, stream in _streams(blob, dict_len):
            if stream[3] != s4lz.VERSION_V3:
                bad.append(f"{label} block {idx}: version {stream[3]}")
    assert not bad, (
        "streams whose version byte is not 1 — the release ROM faults with "
        "S4LZ code 1 on each of these:\n  " + "\n  ".join(bad))


def test_version_arm_is_not_vacuous():
    """Negative fixture: a real stream with its version byte forged to 2."""
    label, blob, dict_len = next(iter(_sections()))
    _, stream = next(iter(_streams(blob, dict_len)))
    forged = bytearray(stream[:8])
    forged[3] = 2
    assert forged[3] != s4lz.VERSION_V3, "the mutation did not apply"


# ---------------------------------------------------------------------------
# Arm 2 — .fault_dict: no match reaches below the dictionary base
# ---------------------------------------------------------------------------

def test_no_match_reaches_below_the_dictionary():
    bad = []
    for label, blob, dict_len in _sections():
        for idx, stream in _streams(blob, dict_len):
            _, _, _, depth = walk(stream, dict_len)
            if depth > dict_len:
                bad.append(
                    f"{label} block {idx}: reaches {depth}B below the dest "
                    f"start, dict is {dict_len}B")
    assert not bad, (
        "matches reaching past the dictionary base — the release ROM faults "
        "with S4LZ code 2 on each of these:\n  " + "\n  ".join(bad))


def test_the_dictionary_bound_is_exercised_at_its_boundary():
    """The real corpus sits ON the bound, so the comparison's edge is load-bearing.

    Measured 2026-09-09 over all 9 OJZ act-1 sections: the deepest match in every
    single one reaches EXACTLY `dict_len` bytes below the dest start (768 of 768).
    That is the legal extreme the s4lz.emp header traces ("a2 = dest_start -
    dict_len (deepest legal) -> a2' = dict_base"), and it means the release check
    MUST fault only on `dict_len < depth` (`blo` after `cmp.w d1, d4`). Written
    one rung tighter — `bls`, "fault on <=" — the shipped ROM would crash-screen
    on the first block of every section.

    This arm exists so that tightening is caught here instead of on a player's
    console. It asserts the boundary is reached, not merely respected.
    """
    at_bound = 0
    for label, blob, dict_len in _sections():
        if dict_len == 0:
            continue
        deepest = max(walk(s, dict_len)[3] for _, s in _streams(blob, dict_len))
        assert deepest <= dict_len, f"{label}: {deepest} > {dict_len}"
        if deepest == dict_len:
            at_bound += 1
    assert at_bound > 0, (
        "no section reaches the dictionary bound any more — this arm has stopped "
        "witnessing the edge case it exists for; re-derive it rather than delete it")


def test_dict_arm_would_catch_a_deeper_match():
    """Negative fixture: hand-built stream whose only match reaches past the dict.

    Token $01 = 0 literal words, 1 match word; offmark $10 = byte offset 32.
    With nothing written yet the match source is 32 bytes below the dest start,
    so a 16-byte dictionary is 16 bytes short of it.
    """
    forged = struct.pack(">HBB", 2, 0, s4lz.VERSION_V3) + bytes([0x01, 0x10, 0x00, 0x00])
    _, _, _, depth = walk(forged, 16)
    assert depth == 32, f"walker read depth {depth}, expected 32"
    assert depth > 16, "the arm's own predicate does not fire on a forged deep match"


# ---------------------------------------------------------------------------
# Arm 3 — .fault_extent: written extent is the declared size (or +1 pad byte)
# ---------------------------------------------------------------------------

def test_written_extent_matches_the_header_size():
    bad = []
    for label, blob, dict_len in _sections():
        for idx, stream in _streams(blob, dict_len):
            _, declared, written, _ = walk(stream, dict_len)
            if written - declared not in (0, 1):
                bad.append(
                    f"{label} block {idx}: wrote {written}B, header declares "
                    f"{declared}B (delta {written - declared})")
            if written > SUBA_W_CEILING:
                bad.append(
                    f"{label} block {idx}: extent {written}B exceeds the "
                    f"suba.w ceiling {SUBA_W_CEILING}")
    assert not bad, (
        "streams whose written extent disagrees with their header — the release "
        "ROM faults with S4LZ code 3 on each of these:\n  " + "\n  ".join(bad))


def test_extent_arm_would_catch_a_forged_size_word():
    """Negative fixture: a real stream with its header size word corrupted."""
    label, blob, dict_len = next(iter(_sections()))
    _, stream = next(iter(_streams(blob, dict_len)))
    _, declared, written, _ = walk(stream, dict_len)
    assert written - declared in (0, 1), "fixture base stream is already bad"
    forged = bytearray(stream)
    struct.pack_into(">H", forged, 0, 0xFFFF)
    _, f_declared, f_written, _ = walk(bytes(forged), dict_len)
    assert f_declared == 0xFFFF, "the mutation did not apply"
    assert f_written - f_declared not in (0, 1), (
        "a $FFFF size word did not trip the extent predicate — the arm is blind")


# ---------------------------------------------------------------------------
# The walker is tied to the shipped reference decoder, not to itself
# ---------------------------------------------------------------------------

def test_walker_extent_agrees_with_the_reference_decoder():
    """`walk`'s extent must equal `s4lz._decompress_v3`'s output length.

    Without this the three arms above would be grading the corpus against a
    private re-implementation of the format, which is exactly the shape of a
    gate that measures itself.
    """
    checked = 0
    for label, blob, dict_len in _sections():
        dictionary = blob[BLOCK_INDEX_SIZE:BLOCK_INDEX_SIZE + dict_len]
        for idx, stream in _streams(blob, dict_len):
            _, _, written, _ = walk(stream, dict_len)
            ref = len(s4lz._decompress_v3(stream, dictionary=dictionary))
            assert written == ref, (
                f"{label} block {idx}: walker says {written}B, "
                f"s4lz._decompress_v3 says {ref}B")
            checked += 1
    assert checked > 0, "nothing cross-checked — see test_the_corpus_is_not_empty"
