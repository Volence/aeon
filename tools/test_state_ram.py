#!/usr/bin/env python3
"""pytest wrapper for tools/state_ram.py — run by build.sh's `pytest tools` lane.

The save-state decoder's whole value is that it REFUSES a state it cannot
justify: a wrong ROM, a corrupt payload, or a `System` layout that moved must be
errors, never a plausible-looking page of nonsense. These tests build synthetic
`ONSS` containers from the formulas in
oracle/crates/oracle-frontend/src/save_state.rs and assert each refusal fires.

No fixture file is committed: a real `.state` is ~900 KB and couples the suite to
one ROM build. The synthetic container carries the same header and the same
`seed / scheduler / rom / ram / ...` field order, which is all the decoder reads.
"""

import struct

import pytest

import state_ram as SR


def _rom(n=4096, k=7, c=3):
    return bytes((i * k + c) & 0xFF for i in range(n))


def _ram(pattern=13, c=5):
    return bytes((i * pattern + c) & 0xFF for i in range(SR.RAM_BYTES))


def _write(tmp_path, name, blob):
    p = tmp_path / name
    p.write_bytes(blob)
    return str(p)


def _pair(tmp_path, rom, ram, **kw):
    """(state path, rom path) for a synthetic container."""
    return (_write(tmp_path, "s.state0", SR._synth(rom, ram, **kw)),
            _write(tmp_path, "rom.bin", rom))


def test_round_trip_recovers_ram(tmp_path):
    rom, ram = _rom(), _ram()
    state, rom_p = _pair(tmp_path, rom, ram)
    assert SR.read_state(state, rom_p) == ram


def test_rom_fingerprint_matches_save_state_rs():
    # rom_fingerprint(rom) = fnv1a(rom) ^ (len * 0x9E3779B97F4A7C15), derived
    # from save_state.rs, not copied from an observed header.
    rom = _rom()
    expect = SR.fnv1a(rom) ^ ((len(rom) * 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF)
    assert SR.rom_fingerprint(rom) == expect
    assert SR.rom_fingerprint(_rom(k=11, c=1)) != expect


def test_refuses_a_state_from_a_different_rom(tmp_path):
    state, _ = _pair(tmp_path, _rom(), _ram())
    other = _write(tmp_path, "other.bin", _rom(k=11, c=1))
    with pytest.raises(SR.StateError, match="DIFFERENT ROM"):
        SR.read_state(state, other)


def test_refuses_bad_magic(tmp_path):
    state, rom_p = _pair(tmp_path, _rom(), _ram(), magic=b"XXXX")
    with pytest.raises(SR.StateError, match="not an oracle-frontend save state"):
        SR.read_state(state, rom_p)


def test_refuses_corrupt_payload(tmp_path):
    # bincode has no integrity check: a flipped byte inside RAM decodes silently.
    state, rom_p = _pair(tmp_path, _rom(), _ram(), corrupt=True)
    with pytest.raises(SR.StateError, match="checksum"):
        SR.read_state(state, rom_p)


def test_refuses_truncated_file(tmp_path):
    rom, ram = _rom(), _ram()
    blob = SR._synth(rom, ram)
    state = _write(tmp_path, "s.state0", blob[:-64])
    rom_p = _write(tmp_path, "rom.bin", rom)
    with pytest.raises(SR.StateError, match="truncated or appended"):
        SR.read_state(state, rom_p)


def test_refuses_ram_that_is_not_64k(tmp_path):
    """A shrunk/grown `ram` Vec means System's layout moved — fail, don't decode."""
    rom = _rom()
    state, rom_p = _pair(tmp_path, rom, _ram()[:SR.RAM_BYTES // 2])
    with pytest.raises(SR.StateError, match="not the 64 KiB work RAM"):
        SR.read_state(state, rom_p)


def test_refuses_when_ram_no_longer_follows_rom(tmp_path):
    """Reordering System's fields changes the varint marker after `rom`."""
    state, rom_p = _pair(tmp_path, _rom(), _ram(), marker=0x10)
    with pytest.raises(SR.StateError, match="varint marker"):
        SR.read_state(state, rom_p)


def test_ram_identical_to_rom_prefix_still_decodes(tmp_path):
    """The `rom` locate step must not mistake RAM content for the cartridge."""
    rom = _rom()
    twin = bytes(rom[i % len(rom)] for i in range(SR.RAM_BYTES))
    state, rom_p = _pair(tmp_path, rom, twin)
    assert SR.read_state(state, rom_p) == twin


def test_ram_accessors_are_big_endian_and_window_checked():
    """68K is big-endian; the low 16 bits of an $FFFFxxxx address are the offset."""
    data = bytearray(SR.RAM_BYTES)
    data[0x1234], data[0x1235] = 0x12, 0x34
    data[0x2000], data[0x2001] = 0xFF, 0xFE
    ram = SR.Ram(bytes(data), {})
    assert ram.u16(0xFFFF1234) == 0x1234, "u16 must be big-endian"
    assert ram.u16(0xFF1234) == 0x1234, "the $FF0000 mirror must resolve the same"
    assert ram.s16(0xFFFF2000) == -2, "s16 must sign-extend"
    with pytest.raises(SR.StateError, match="work-RAM window"):
        ram.u8(0x006E340)                       # a ROM address, not RAM


def test_status_bits_are_bit_numbers_not_masks():
    """ST_* in engine/system/constants.emp are BIT NUMBERS. Reading them as masks
    turns status $02 (xflip only) into a false 'in_air' report."""
    names = dict((b, n) for b, n in SR.STATUS_BITS)
    assert names[3] == "IN_AIR", "ST_IN_AIR is bit 3"
    status = 0x02
    set_bits = [n for b, n in SR.STATUS_BITS if status & (1 << b)]
    assert set_bits == ["xflip"], f"status $02 sets xflip only, got {set_bits}"


def test_camera_y_is_not_camera_x_plus_two():
    """Camera_X is a LONGWORD, so Camera_Y is +4, not +2. Reading $A606 returns
    Camera_X's fractional word (always ~0) and reports 'camera y = 0'."""
    cx = SR.FALLBACK_SYMBOLS["Camera_X"]
    cy = SR.FALLBACK_SYMBOLS["Camera_Y"]
    assert cy == cx + 4, f"Camera_Y {cy:#x} must be Camera_X {cx:#x} + 4"


def test_load_symbols_parses_a_sigil_listing(tmp_path):
    lst = tmp_path / "x.lst"
    lst.write_text(
        "(0) 2554/FFFFA604 :        Camera_X:\n"
        "(0) 2555/FFFFA608 :        Camera_Y:\n"
        "(0) 2373/FFFF2580 :        Tile_Cache_Collision:\n"
        " Camera_X : FFFFA604 C |\n")
    syms = SR.load_symbols(str(lst))
    assert syms["Camera_X"] == 0xFFFFA604
    assert syms["Camera_Y"] == 0xFFFFA608
    assert syms["Tile_Cache_Collision"] == 0xFFFF2580


def test_load_symbols_on_a_missing_listing_is_empty_not_an_error():
    assert SR.load_symbols("/nonexistent/nope.lst") == {}
