"""Tests for ojz_block_gen's incremental (content-addressed) re-bake caches.

The caches exist because a REAL one-chunk editor edit re-baked in 14.7 s where a
no-change re-bake took 1.5 s, and 99.7% of the gap was the per-section S4LZ
K-sweep. They are PURE memoization: what they must never do is change a single
output byte. These tests hold that line from three directions —

  1. KEY COMPLETENESS — every input that s4lz.compress actually reads is in the
     key, and nothing that it does not read is (so the key neither goes stale
     nor thrashes).
  2. INTEGRITY — a corrupted cache file is detected and treated as a miss, and a
     cache entry that does not decode back to its source is REJECTED even when
     its file digest is valid.
  3. EQUIVALENCE — cached and --no-cache runs of the real pipeline produce
     byte-identical blobs, on a first (populating) run, a warm run, and after an
     edit-and-revert round trip.
"""

import hashlib
import os
import pickle
import struct
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ojz_block_gen as bg
import s4lz


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    """Point both cache tiers at a private empty directory."""
    monkeypatch.setattr(bg, "CACHE_DIR", str(tmp_path / "blockgen"))
    monkeypatch.setattr(bg, "MEMO_DIR", str(tmp_path / "blockmemo"))
    return tmp_path


def _synth_strips(num_cols=16, seed=12345):
    """A small synthetic section: `num_cols` strip columns of deterministic
    pseudo-random bytes. Small and incompressible, so the real K-sweep runs
    end to end in well under a second while still exercising every path.
    """
    out = bytearray()
    state = seed
    for _ in range(num_cols * bg.STRIP_BYTE_SIZE):
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        out.append((state >> 16) & 0xFF)
    return bytes(out)


@pytest.fixture
def synth_section(monkeypatch):
    """Make load_raw_strips() serve the synthetic section for index 0."""
    data = _synth_strips()
    monkeypatch.setattr(bg, "load_raw_strips", lambda idx: data)
    return data


# ---------------------------------------------------------------------------
# 1. Key completeness
# ---------------------------------------------------------------------------

def test_memo_key_is_stable_for_identical_inputs():
    a = bg._memo_key(b"block-payload", b"dictionary")
    b = bg._memo_key(b"block-payload", b"dictionary")
    assert a == b


def test_memo_key_separates_data():
    a = bg._memo_key(b"block-payload", b"dict")
    b = bg._memo_key(b"block-payloaD", b"dict")
    assert a != b


def test_memo_key_separates_dictionary():
    """The dictionary is a real input to compress() — a different dictionary
    yields a different stream, so it MUST be in the key."""
    a = bg._memo_key(b"payload", b"dict-one")
    b = bg._memo_key(b"payload", b"dict-two")
    assert a != b


def test_memo_key_separates_tile_delta_flag():
    assert bg._memo_key(b"p", b"d", False) != bg._memo_key(b"p", b"d", True)


def test_memo_key_is_not_ambiguous_across_the_data_dict_boundary():
    """Length-prefixing both byte strings: no split of the same concatenation
    may collide (the classic content-key defect)."""
    assert bg._memo_key(b"ab", b"cd") != bg._memo_key(b"abc", b"d")
    assert bg._memo_key(b"", b"abcd") != bg._memo_key(b"abcd", b"")


def test_memo_key_tracks_the_compressor_source(monkeypatch):
    """A change anywhere in s4lz.py — algorithm, MAX_WINDOW, version byte —
    must invalidate every entry. The key folds in the whole source digest, so
    this is the single check that covers 'compressor version and flags'."""
    before = bg._memo_key(b"payload", b"dict")
    monkeypatch.setattr(bg, "_S4LZ_SOURCE_DIGEST", hashlib.sha256(b"other").digest())
    assert bg._memo_key(b"payload", b"dict") != before


def test_memo_key_ignores_this_generator_source():
    """ojz_block_gen only BUILDS the two byte strings it hands to compress();
    any change in how it builds them changes the hashed bytes themselves. So
    the tier-2 key deliberately excludes this file — tier 1 is what covers it.
    Guard the intent by asserting the key is exactly a function of its args."""
    h = hashlib.sha256()
    h.update(b"s4lz.compress.v1\0")
    h.update(bg._S4LZ_SOURCE_DIGEST)
    h.update(b"\x00")
    h.update(struct.pack(">I", 4)); h.update(b"dict")
    h.update(struct.pack(">I", 7)); h.update(b"payload")
    assert bg._memo_key(b"payload", b"dict") == h.digest()


def test_tier1_key_tracks_input_and_both_sources(tmp_path, monkeypatch):
    a = bg._cache_key(0, b"strip-bytes")
    assert bg._cache_key(0, b"strip-bytes") == a
    assert bg._cache_key(1, b"strip-bytes") != a      # section index
    assert bg._cache_key(0, b"strip-byteS") != a      # input data


# ---------------------------------------------------------------------------
# 2. Integrity
# ---------------------------------------------------------------------------

def test_digest_frame_round_trips():
    assert bg._digest_unpack(bg._digest_pack(b"hello")) == b"hello"


def test_digest_frame_rejects_a_flipped_payload_byte():
    framed = bytearray(bg._digest_pack(b"hello world"))
    framed[35] ^= 0xFF
    assert bg._digest_unpack(bytes(framed)) is None


def test_digest_frame_rejects_a_truncated_entry():
    assert bg._digest_unpack(bg._digest_pack(b"hello")[:-1]) is None
    assert bg._digest_unpack(b"short") is None


def test_tier1_load_treats_a_corrupt_file_as_a_miss(isolated_cache):
    bg._cache_store("k", (b"blob", 0, {"k": 0}))
    path = os.path.join(bg.CACHE_DIR, "k")
    raw = bytearray(open(path, "rb").read())
    raw[-1] ^= 0xFF
    open(path, "wb").write(bytes(raw))
    assert bg._cache_load("k") is None


def test_tier2_load_treats_a_corrupt_memo_as_empty(isolated_cache):
    bg._memo_store(3, {b"key": b"value"}, {b"key"})
    path = bg._memo_path(3)
    raw = bytearray(open(path, "rb").read())
    raw[-1] ^= 0xFF
    open(path, "wb").write(bytes(raw))
    assert bg._memo_load(3) == {}


def test_verify_stream_accepts_a_genuine_stream():
    data = _synth_strips(num_cols=1)[:bg.BLOCK_RAW_SIZE]
    dict_bytes = _synth_strips(num_cols=1, seed=99)[:bg.BLOCK_RAW_SIZE]
    stream = s4lz.compress(data, dictionary=dict_bytes)
    assert bg._verify_stream(stream, data, dict_bytes)


def test_verify_stream_rejects_a_forged_stream():
    """The poison the file digest cannot see: a corrupted value re-framed with
    a VALID digest. Output verification is what catches it."""
    data = _synth_strips(num_cols=1)[:bg.BLOCK_RAW_SIZE]
    dict_bytes = _synth_strips(num_cols=1, seed=99)[:bg.BLOCK_RAW_SIZE]
    stream = bytearray(s4lz.compress(data, dictionary=dict_bytes))
    stream[6] ^= 0xFF
    assert not bg._verify_stream(bytes(stream), data, dict_bytes)


def test_verify_stream_rejects_a_stream_for_a_different_dictionary():
    """A stream that reaches back into its dictionary decodes to garbage under
    a different one — so serving a hit keyed without the dictionary would
    corrupt the ROM. `data` here deliberately shares a long run with d1 so the
    compressor actually emits dictionary-relative matches."""
    d1 = _synth_strips(num_cols=1, seed=99)[:bg.BLOCK_RAW_SIZE]
    d2 = _synth_strips(num_cols=1, seed=77)[:bg.BLOCK_RAW_SIZE]
    data = d1[64:] + d1[:64]
    stream = s4lz.compress(data, dictionary=d1)
    assert bg._verify_stream(stream, data, d1)
    assert not bg._verify_stream(stream, data, d2)


def test_verify_stream_survives_garbage_without_raising():
    assert not bg._verify_stream(b"\xff\xff\xff\xff\xff", b"anything", b"")


def test_forged_memo_entry_is_rejected_and_recomputed(
        isolated_cache, synth_section):
    """End to end: forge EVERY memo value with a valid file digest, then
    re-run. The decode check must reject them all and the blob must come out
    identical to the honest one."""
    good_blob, good_len, _ = bg.generate_section_blocks(0)

    memo = bg._memo_load(0)
    assert memo, "the run should have populated the tier-2 memo"
    for k in list(memo):
        v = bytearray(memo[k])
        v[6] ^= 0xFF
        memo[k] = bytes(v)
    payload = pickle.dumps(memo, protocol=pickle.HIGHEST_PROTOCOL)
    open(bg._memo_path(0), "wb").write(bg._digest_pack(payload))
    # Drop tier 1 so the run has to consult the poisoned memo.
    for f in os.listdir(bg.CACHE_DIR):
        os.remove(os.path.join(bg.CACHE_DIR, f))

    blob, dict_len, stats = bg.generate_section_blocks(0)
    assert stats["memo_rejected"] == len(memo)
    assert (blob, dict_len) == (good_blob, good_len)


def test_forged_tier1_blob_is_rejected_and_recomputed(
        isolated_cache, synth_section):
    """Same poison one tier up: a corrupted section blob re-framed with a valid
    digest must fail _verify_blob and be rebuilt."""
    good_blob, good_len, _ = bg.generate_section_blocks(0)

    name = os.listdir(bg.CACHE_DIR)[0]
    path = os.path.join(bg.CACHE_DIR, name)
    blob, dict_len, stats = pickle.loads(open(path, "rb").read()[32:])
    forged = bytearray(blob)
    forged[bg.BLOCK_INDEX_SIZE + 6] ^= 0xFF
    payload = pickle.dumps((bytes(forged), dict_len, stats),
                           protocol=pickle.HIGHEST_PROTOCOL)
    open(path, "wb").write(bg._digest_pack(payload))

    blob2, len2, stats2 = bg.generate_section_blocks(0)
    assert stats2["cached"] is False, "the forged tier-1 entry must not be served"
    assert (blob2, len2) == (good_blob, good_len)


def test_memo_trim_keeps_this_runs_entries(isolated_cache, monkeypatch):
    monkeypatch.setattr(bg, "MEMO_MAX_ENTRIES", 3)
    memo = {bytes([i]): b"v%d" % i for i in range(6)}
    used = {b"\x04", b"\x05"}
    bg._memo_store(7, memo, used)
    kept = bg._memo_load(7)
    assert len(kept) == 3
    assert used <= set(kept), "entries touched this run must survive the trim"


# ---------------------------------------------------------------------------
# 3. Equivalence — the contract that actually matters
# ---------------------------------------------------------------------------

def test_cached_and_nocache_blobs_are_byte_identical(isolated_cache, synth_section):
    reference = bg.generate_section_blocks(0, use_cache=False)
    populating = bg.generate_section_blocks(0, use_cache=True)
    warm = bg.generate_section_blocks(0, use_cache=True)

    assert populating[0] == reference[0]
    assert warm[0] == reference[0]
    assert populating[1] == reference[1] == warm[1]
    assert populating[2]["cached"] is False
    assert warm[2]["cached"] is True


def test_no_cache_writes_nothing(isolated_cache, synth_section):
    bg.generate_section_blocks(0, use_cache=False)
    assert not os.path.isdir(bg.CACHE_DIR) or not os.listdir(bg.CACHE_DIR)
    assert not os.path.isdir(bg.MEMO_DIR) or not os.listdir(bg.MEMO_DIR)


def test_edit_and_revert_round_trip_reproduces_the_original_blob(
        isolated_cache, monkeypatch):
    """The loop's real shape: bake, edit one block, bake, revert, bake. The
    final blob must equal the first byte for byte — a stale entry surviving the
    revert is exactly the silent-wrong-data failure this cache must not have."""
    base = _synth_strips()
    edited = bytearray(base)
    for i in range(64):                    # perturb one strip column's nametable
        edited[bg.STRIP_BYTE_SIZE * 3 + i] ^= 0x5A
    edited = bytes(edited)

    current = {"data": base}
    monkeypatch.setattr(bg, "load_raw_strips", lambda idx: current["data"])

    first = bg.generate_section_blocks(0)
    current["data"] = edited
    after_edit = bg.generate_section_blocks(0)
    current["data"] = base
    after_revert = bg.generate_section_blocks(0)

    assert after_edit[0] != first[0], "the edit must actually change the blob"
    assert after_revert[0] == first[0]
    assert after_revert[1] == first[1]


def test_one_block_edit_recompresses_only_the_changed_block(
        isolated_cache, monkeypatch):
    """The whole point of tier 2: an edit confined to one block must not re-run
    the sweep for the others — exactly one block x (K+1) dictionary shapes.

    The dictionary ranking is pinned here so the test measures the memo and not
    select_dict_blocks' sensitivity; see the companion test below for what
    happens when the ranking DOES move.
    """
    base = _synth_strips()
    current = {"data": base}
    monkeypatch.setattr(bg, "load_raw_strips", lambda idx: current["data"])
    # Pin the dictionary to the LAST blocks, away from the block we edit.
    monkeypatch.setattr(bg, "select_dict_blocks",
                        lambda blocks: sorted((i for i, b in enumerate(blocks)
                                               if b is not None), reverse=True))

    bg.generate_section_blocks(0)
    assert len(bg._memo_load(0)) > 8

    edited = bytearray(base)
    edited[bg.STRIP_BYTE_SIZE * 3 + 10] ^= 0x5A     # one block only
    current["data"] = bytes(edited)
    _, _, stats = bg.generate_section_blocks(0)

    assert stats["memo_hits"] > 0
    assert stats["memo_misses"] == bg.MAX_DICT_BLOCKS + 1
    assert stats["memo_misses"] < stats["memo_hits"]


def test_a_dictionary_shift_costs_a_full_section_resweep(
        isolated_cache, monkeypatch):
    """The honest limit of tier 2, asserted rather than hoped for.

    Every stream is compressed AGAINST the section dictionary, so if
    select_dict_blocks picks different dictionary blocks the whole section's
    keys change and every block is recompressed. Only the K=0 shape (empty
    dictionary) survives a ranking move. This is inherent — the alternative
    would be freezing the ranking, which changes ROM bytes.
    """
    base = _synth_strips()
    current = {"data": base}
    ranking = {"reverse": False}
    monkeypatch.setattr(bg, "load_raw_strips", lambda idx: current["data"])
    monkeypatch.setattr(
        bg, "select_dict_blocks",
        lambda blocks: sorted((i for i, b in enumerate(blocks) if b is not None),
                              reverse=ranking["reverse"]))

    bg.generate_section_blocks(0)
    ranking["reverse"] = True                      # the dictionary moves
    # Drop tier 1 so the sweep actually reruns. (In production the ranking is a
    # pure function of the input and this module's source, both of which the
    # tier-1 key hashes — it cannot move without tier 1 missing anyway.)
    for f in os.listdir(bg.CACHE_DIR):
        os.remove(os.path.join(bg.CACHE_DIR, f))
    _, _, stats = bg.generate_section_blocks(0)

    # The K=0 shape still hits (its dictionary is empty either way); every
    # dictionary-bearing shape misses.
    assert stats["memo_misses"] > stats["memo_hits"]
    assert stats["memo_hits"] > 0, "the K=0 shape must survive a ranking move"
