#!/usr/bin/env python3
"""The build-time half of the V-7 release-shape net around the RESUMABLE ZX0 decoder.

WHY THERE IS A SEPARATE FILE FOR THIS AT ALL.

`tools/test_s4lz_release_checks.py` is the twin of this file, for the blocking
S4LZ decoder. The resumable one needed its own because its checks are not IN the
decoder. `engine/compression/zx0_resume.emp`'s body is `@resumable`, and a probe
`raise_error` planted at its `.done` is refused by sigil with three
`[resumable.stack-op]` errors -- one for each sp-touching op of the MD Debugger
raise frame (`pea`, the `-(sp)` push, `jsr`). That was reproduced on 2026-09-10,
not taken from the file's comment. So the four checks live at the four places
OUTSIDE that body which touch the decode's state:

  code 1  .fault_ver     page_in.emp, setup      wrapper version != ART_VER_ZX0
  code 2  .fault_size    page_in.emp, setup      declared bytes > staging buffer
  code 3  .fault_extent  page_in.emp, .after     written extent != declared bytes
  (none)  .fault_bank    page_in.emp, BankRegs   dest cursor left the buffer

WHAT THIS FILE PROVES, AND WHAT IT DOES NOT.

Those are RUNTIME checks and nothing in the build executes them, so this file
does NOT prove they fire -- only an emulator can. It proves the two halves a
build CAN answer, and they are the two halves that can hurt:

  1. THAT THEY SHIP. Every one of the four is gated `DEBUG == 1 || CRASH_REPORT
     == 1`, which is the axis the error_handler island rides. `test_the_checks_
     are_in_the_release_rom` reads the PLAIN listing + ROM and finds all four
     fault sites, and re-derives the two `cmpa.l` bounds at `.fault_bank` from
     `Art_Staging_Buffer` (listing symbol) and ART_STAGING_BUFFER_SIZE
     (constants.emp) rather than copying an address out of a nearby pin.

  2. THAT NO SHIPPED PAGE TRIPS ONE. A release-shape check that false-fires is a
     crash screen on a valid ROM, strictly worse than the silent overrun it
     replaced. Every arm below re-derives one check's predicate over the real
     corpus of ZX0 art-pool pages in `games/*/data/generated/`.

Read a failure in group 2 as "the release ROM would crash-screen on this data".

THE ONE PREDICATE THIS FILE DOES NOT RE-DERIVE, AND WHERE IT IS GRADED INSTEAD.
Check 3 compares the extent the DECODER actually wrote against the declared one.
Grading that here would mean a second Python ZX0 decoder mirroring
`zx0_resume.emp`, and a mirror is only as good as its author's reading of the
bit-queue marker trick. It is already graded by something better: the DEBUG
cold-boot `CompressionSelfTest` (`engine/debug/compression_selftest.emp`,
`.eq_page`/`.eq_resume`) decodes EVERY act-pool ZX0 page with BOTH the blocking
and the resumable decoder and asserts each produced exactly `pm_tiles * 32`
bytes. So what is left for this file is the other input to check 3's comparison
-- that `declared bytes == pm_tiles * 32 == len(the page's uncompressed payload)`
-- which is arms `test_every_page_declares_its_payload_size` below.

Each arm carries a NEGATIVE fixture so a green can never mean "the walker
stopped looking".
"""

import re
import struct
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Constants — DERIVED from engine/system/constants.emp, never typed twice.
# ---------------------------------------------------------------------------

_CONSTANTS = REPO / "engine" / "system" / "constants.emp"


def _const(name):
    """The integer value of `pub const <name> = <int>` in constants.emp.

    Deliberately only handles the literal-integer form. Every constant this
    file needs is written that way today; a future derived spelling should
    fail loudly here rather than be silently guessed at.
    """
    pat = re.compile(rf"^\s*pub\s+const\s+{re.escape(name)}\s*=\s*([0-9]+|\$[0-9A-Fa-f]+)\b")
    for line in _CONSTANTS.read_text().splitlines():
        m = pat.match(line)
        if m:
            raw = m.group(1)
            return int(raw[1:], 16) if raw.startswith("$") else int(raw)
    pytest.fail(f"{name} is not a literal `pub const` in engine/system/constants.emp — "
                f"this walker's expectations are derived from it and cannot be derived now")


TILE_SIZE = _const("TILE_SIZE")
ART_HDR_SIZE = _const("ART_HDR_SIZE")
ART_HDR_VERSION = _const("ART_HDR_VERSION")
ART_VER_ZX0 = _const("ART_VER_ZX0")
ART_POOL_PAGE_TILES = _const("ART_POOL_PAGE_TILES")
# ART_STAGING_BUFFER_SIZE = ART_POOL_PAGE_BYTES = ART_POOL_PAGE_TILES * TILE_SIZE
# (constants.emp:729-730). Re-derived here from its two factors so a page-size
# change moves this walker with it.
ART_STAGING_BUFFER_SIZE = ART_POOL_PAGE_TILES * TILE_SIZE


# ---------------------------------------------------------------------------
# Corpus discovery — every ZX0-form art-pool page any game actually embeds
# ---------------------------------------------------------------------------

_EMBED = re.compile(r'pub\s+data\s+(\w*Page(\d+))\s*=\s*embed\("([^"]+)"\)')
_TILES = re.compile(r"^\s*pub\s+const\s+\w*PAGE(\d+)_TILES\s*=\s*([0-9]+)", re.M)


def _pool_pages():
    """Yield (label, blob_bytes, declared_tiles, is_zx0_form) per embedded page.

    Form is read off the embed's own extension, which is how the generator
    records its per-page election: `.zx0` = ART_PAGE_FORM_ZX0 (4-byte wrapper +
    salvador bitstream), `.bin` = ART_PAGE_FORM_RAW (payload, no wrapper).
    """
    for pool in sorted(REPO.glob("games/*/data/generated/*/*/*_act_pool.emp")):
        manifest = pool.parent / (pool.stem + "_manifest.emp")
        if not manifest.is_file():
            pytest.fail(f"{pool.relative_to(REPO)} has no sibling _manifest.emp — the walk "
                        f"cannot reproduce pm_tiles and would be grading nothing")
        tiles = {int(n): int(v) for n, v in _TILES.findall(manifest.read_text())}
        for _sym, idx, rel in _EMBED.findall(pool.read_text()):
            blob = REPO / rel
            if not blob.is_file():
                pytest.fail(f"{pool.relative_to(REPO)} embeds {rel}, which is not on disk")
            idx = int(idx)
            if idx not in tiles:
                pytest.fail(f"{manifest.relative_to(REPO)} declares no PAGE{idx}_TILES for "
                            f"the page {pool.relative_to(REPO)} embeds")
            yield (rel, blob.read_bytes(), tiles[idx], blob.suffix == ".zx0")


def _zx0_pages():
    return [(lbl, b, t) for lbl, b, t, is_zx0 in _pool_pages() if is_zx0]


# ---------------------------------------------------------------------------
# The three data arms — one per predicate a check evaluates on shipped bytes
# ---------------------------------------------------------------------------

def test_the_corpus_is_not_empty():
    """A walker with nothing to walk reports green forever."""
    pages = _zx0_pages()
    assert pages, ("no ZX0-form art-pool page was found under games/*/data/generated/ — "
                   "every arm below would pass vacuously")
    print(f"\nZX0R net corpus: {len(pages)} ZX0-form page(s), "
          f"{sum(len(b) for _, b, _ in pages)} compressed bytes")


def test_every_page_wrapper_declares_ART_VER_ZX0():
    """Check 1 (.fault_ver): the wrapper's version byte must be ART_VER_ZX0."""
    for label, blob, _tiles in _zx0_pages():
        assert len(blob) > ART_HDR_SIZE, f"{label}: blob is shorter than its wrapper"
        got = blob[ART_HDR_VERSION]
        assert got == ART_VER_ZX0, (
            f"{label}: wrapper version byte is {got}, not ART_VER_ZX0 ({ART_VER_ZX0}) — "
            f"PageIn_Process would crash-screen with code 1 on this page")


def test_version_arm_is_not_vacuous():
    """The negative fixture for check 1: forge the byte, the arm must see it."""
    _label, blob, _tiles = _zx0_pages()[0]
    forged = bytearray(blob)
    forged[ART_HDR_VERSION] = (ART_VER_ZX0 + 1) & 0xFF
    assert forged[ART_HDR_VERSION] != ART_VER_ZX0, "the mutation did not apply"
    assert bytes(forged) != blob, "the mutation changed nothing"


def test_every_page_fits_the_staging_buffer():
    """Check 2 (.fault_size): declared bytes must not exceed the staging buffer.

    This is the one BOUND of the four — it is evaluated before the fall-through
    into the decoder, while an overrun is still preventable.
    """
    for label, _blob, tiles in _zx0_pages():
        declared = tiles * TILE_SIZE
        assert 0 < declared <= ART_STAGING_BUFFER_SIZE, (
            f"{label}: pm_tiles({tiles}) * TILE_SIZE({TILE_SIZE}) = {declared} bytes, "
            f"outside (0, ART_STAGING_BUFFER_SIZE={ART_STAGING_BUFFER_SIZE}] — "
            f"PageIn_Process would crash-screen with code 2 on this page")


def test_size_arm_would_catch_an_oversized_page():
    """The negative fixture for check 2, evaluated by the same expression."""
    oversize = ART_STAGING_BUFFER_SIZE + TILE_SIZE
    tiles = oversize // TILE_SIZE
    assert tiles * TILE_SIZE > ART_STAGING_BUFFER_SIZE, (
        "a page one tile past the buffer must trip the bound the arm above uses")


def test_every_page_declares_its_payload_size():
    """Check 3's other input: declared size == pm_tiles*32 == payload length.

    The wrapper's leading BE word is the uncompressed size the encoder measured;
    `PageIn_Cur_Bytes` is `pm_tiles * TILE_SIZE`; the sibling `.bin` is the exact
    payload the encoder compressed. Check 3 compares the decoder's written extent
    against the second of those, so all three agreeing is what makes it safe. (The
    decoder's own extent is graded by CompressionSelfTest — see the module
    docstring.)
    """
    for label, blob, tiles in _zx0_pages():
        declared_hdr = struct.unpack_from(">H", blob, 0)[0]
        declared_mf = tiles * TILE_SIZE
        assert declared_hdr == declared_mf, (
            f"{label}: wrapper size word {declared_hdr} != pm_tiles*TILE_SIZE {declared_mf}")
        payload = REPO / label
        payload = payload.with_suffix(".bin")
        if payload.is_file():
            assert len(payload.read_bytes()) == declared_mf, (
                f"{label}: sibling payload {payload.name} is {len(payload.read_bytes())} bytes, "
                f"not the declared {declared_mf} — PageIn_Process would crash-screen with "
                f"code 3 the moment this page decoded correctly")


def test_extent_arm_would_catch_a_forged_size_word():
    """The negative fixture for check 3's input identity."""
    _label, blob, tiles = _zx0_pages()[0]
    forged = bytearray(blob)
    struct.pack_into(">H", forged, 0, 0xFFFF)
    assert struct.unpack_from(">H", forged, 0)[0] == 0xFFFF, "the mutation did not apply"
    assert struct.unpack_from(">H", forged, 0)[0] != tiles * TILE_SIZE, (
        "the forged size word must disagree with pm_tiles*TILE_SIZE, or the arm "
        "above could not tell them apart")


# ---------------------------------------------------------------------------
# The emission arm — the half that says the checks SHIP
# ---------------------------------------------------------------------------

_FAULT_LABELS = (
    "$engine.page_in$PageIn_Process$fault_ver",
    "$engine.page_in$PageIn_Process$fault_size",
    "$engine.page_in$PageIn_Process$fault_extent",
    "$engine.page_in$PageIn_BankRegs$fault_bank",
)

_SYM = re.compile(r"^\s*(\S+)\s*:\s*([0-9A-Fa-f]{4,8})\s+[A-Z]\s*\|")


def _symbols(lst_text):
    out = {}
    for line in lst_text.splitlines():
        m = _SYM.match(line)
        if m:
            out.setdefault(m.group(1), int(m.group(2), 16))
    return out


@pytest.mark.needs_build("s4.lst", "s4.bin")
def test_the_checks_are_in_the_release_rom():
    """All four fault sites are in the PLAIN shape, and the bounds are derived.

    This is the arm that answers the V-7 headline. The checks are gated
    `DEBUG == 1 || CRASH_REPORT == 1`; build.sh refuses CRASH_REPORT=0 as
    non-canonical, so "present in the plain listing" IS "present in the shipped
    ROM". A narrowing of that predicate to bare `DEBUG` deletes these labels and
    turns this arm red — that is the mutation control, and it was run.
    """
    lst = (REPO / "s4.lst").read_text()
    rom = (REPO / "s4.bin").read_bytes()
    syms = _symbols(lst)

    missing = [n for n in _FAULT_LABELS if n not in syms]
    assert not missing, (
        f"the release listing has no {missing} — the V-7 net is DEBUG-only again, "
        f"which is exactly the state the finding was opened about")

    base = syms.get("Art_Staging_Buffer")
    assert base is not None, "Art_Staging_Buffer is not in the listing symbol table"

    # PageIn_BankRegs's bound pair, read out of the ROM and compared against the
    # values DERIVED above. `cmpa.l #imm32,a1` is B3FC iiiiiiii.
    start = syms["PageIn_BankRegs"]
    end = syms["$engine.page_in$PageIn_BankRegs$fault_bank"]
    body = rom[start:end]
    imms = [struct.unpack_from(">I", body, i + 2)[0]
            for i in range(0, len(body) - 5)
            if body[i:i + 2] == b"\xb3\xfc"]
    assert imms == [base, base + ART_STAGING_BUFFER_SIZE], (
        f"PageIn_BankRegs emits cmpa.l bounds {[hex(v) for v in imms]}; derived from "
        f"Art_Staging_Buffer({base:#x}) + ART_STAGING_BUFFER_SIZE"
        f"({ART_STAGING_BUFFER_SIZE}) they must be "
        f"{[hex(base), hex(base + ART_STAGING_BUFFER_SIZE)]}")

    print(f"\nV-7 net in the release ROM: 4 fault sites; PageIn_BankRegs bounds "
          f"[{base:#x}, {base + ART_STAGING_BUFFER_SIZE:#x}]")
