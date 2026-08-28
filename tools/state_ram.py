#!/usr/bin/env python3
"""Read the 68K work RAM out of an oracle-frontend save state — WITHOUT an emulator.

An `.state<N>` file is oracle-frontend's container (`ONSS`) around the core's
bincode `System::snapshot()`. Everything this tool needs is static, so a save
state the owner drops next to the ROM becomes a debuggable artifact: player
position, camera, the tile-cache collision window, any RAM address at all — read
from a background agent, a CI job, or a machine with no display.

Container layout (oracle/crates/oracle-frontend/src/save_state.rs, all LE):

    off  0  4  magic b"ONSS"
    off  4  2  container FORMAT_VERSION
    off  6  8  layout fingerprint (bincode layout of `System`)
    off 14  8  rom fingerprint  = fnv1a(rom) ^ (len(rom) * 0x9E3779B97F4A7C15)
    off 22  8  payload length
    off 30  8  fnv1a(payload)
    off 38  .. the bincode payload

The RAM offset inside the payload is DERIVED, never searched for by content.
`System`'s field order (oracle/crates/oracle-core/src/system.rs) is

    seed: u64 / scheduler / rom: Vec<u8> / ram: Vec<u8> / z80_ram / vdp / ...

so `ram` begins immediately after `rom`, behind a bincode varint length prefix.
We locate `rom` by its own bytes (we have the cartridge on disk and its
fingerprint already matched), step over it, and require the next varint to read
exactly 0x10000. Searching the payload for a RAM-shaped window instead returns
tens of thousands of plausible-looking candidates and a confident wrong answer;
that mistake is why this is spelled out.

THREE assertions guard the decode, and all three are load-bearing — a `System`
layout change must fail loudly here rather than hand back garbage that looks
like RAM:

  * magic + payload length + payload checksum  -> the file is intact
  * rom fingerprint vs the ROM on disk         -> the state belongs to THIS ROM
  * the varint after `rom` reads exactly 64 KiB -> `ram` still follows `rom`

Symbol addresses are read from the build's `.lst` when one is present, so the
field offsets below are not a second, drifting copy of the RAM map.

Usage:
    python3 tools/state_ram.py s4.debug.state0                  # player + camera
    python3 tools/state_ram.py s4.debug.state0 --rom s4.debug.bin
    python3 tools/state_ram.py s4.debug.state0 --dump FFFFAD26 12
    python3 tools/state_ram.py s4.debug.state0 --raw out.bin    # 64 KiB of RAM
    python3 tools/state_ram.py test                             # self-tests
"""

import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AEON = os.path.normpath(os.path.join(HERE, ".."))

MAGIC = b"ONSS"
HEADER_LEN = 38
RAM_BYTES = 0x10000
RAM_BASE = 0xFFFF0000

# bincode varint: values >= 2**16 are marker 0xFC + u32 little-endian.
VARINT_U32_MARKER = 0xFC

# Sst field offsets — engine/objects/sst.emp. Kept here (not re-parsed) because
# they are a struct, not a symbol; sst.emp is the authority if they ever move.
SST_X_POS, SST_Y_POS = 0x02, 0x06
SST_X_VEL, SST_Y_VEL = 0x0A, 0x0C
SST_RENDER_FLAGS = 0x0E
SST_WIDTH, SST_HEIGHT = 0x16, 0x17
SST_ANIM = 0x18
SST_STATUS, SST_ANGLE = 0x1E, 0x1F
SST_MAP_FRAME = 0x23
SST_LAYER = 0x2D

# PlayerV overlay in sst_custom — games/sonic4/config/ram.emp.
PV_GROUND_SPEED = 0x30
PV_PLAYER_STATE = 0x32
PV_MOVE_LOCK = 0x34

# ST_* in engine/system/constants.emp are BIT NUMBERS, not masks. ST_IN_AIR = 3
# means bit 3 (mask $08). Reading them as masks reports contradictions that do
# not exist ("in_air set but state GROUND"); this table exists to stop that.
STATUS_BITS = (
    (1, "xflip"), (2, "yflip"), (3, "IN_AIR"), (4, "ROLLING"),
    (5, "on_object"), (6, "pushing"), (7, "underwater"),
)

# PSTATE_* / ANIM_* — games/sonic4/config/constants.emp.
PSTATE = {
    0: "GROUND", 2: "ROLL", 4: "SPINDASH", 6: "AIR", 8: "JUMP", 10: "ROLLJUMP",
    12: "AIRBALL", 14: "FLY", 16: "GLIDE", 18: "GLIDEFALL", 20: "SLIDE",
    22: "CLIMB", 24: "LEDGE",
}
ANIM = {
    0: "WALK", 1: "RUN", 2: "ROLL", 3: "SPINDASH", 4: "PUSH", 5: "IDLE",
    6: "BALANCE", 7: "LOOKUP", 8: "DUCK", 9: "SKID", 10: "GETUP", 11: "FLY",
    12: "FLY_TIRED", 13: "GLIDE_0", 14: "GLIDE_1", 15: "GLIDE_2", 16: "GLIDE_3",
    17: "GLIDE_4", 18: "GLIDEFALL", 19: "SLIDE", 20: "SLIDE_GETUP",
    21: "GLIDE_LAND", 22: "CLIMB", 23: "LEDGE",
}

# Fallback symbol addresses, used only when no .lst is available.
FALLBACK_SYMBOLS = {
    "Player_1": 0xFFFF8ED6,
    "Player_2": 0xFFFF8F26,
    "Camera_X": 0xFFFFA604,          # longword: integer px in the HIGH word
    "Camera_Y": 0xFFFFA608,          # NOT $A606 — that is Camera_X's fraction
}


class StateError(Exception):
    """A save state that cannot be trusted. Never downgraded to a warning."""


def fnv1a(data: bytes) -> int:
    h = 0xCBF29CE484222325
    for b in data:
        h = ((h ^ b) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def rom_fingerprint(rom: bytes) -> int:
    """save_state.rs::rom_fingerprint."""
    return fnv1a(rom) ^ ((len(rom) * 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF)


def read_state(path: str, rom_path: str) -> bytes:
    """The 64 KiB of 68K work RAM in `path`. Raises StateError on any doubt."""
    with open(path, "rb") as f:
        blob = f.read()
    with open(rom_path, "rb") as f:
        rom = f.read()

    if blob[:4] != MAGIC:
        raise StateError(
            f"{path}: magic {blob[:4]!r}, expected {MAGIC!r} — not an "
            f"oracle-frontend save state")
    version, _layout_fp, rom_fp, payload_len, checksum = struct.unpack_from(
        "<HQQQQ", blob, 4)
    payload = blob[HEADER_LEN:]
    if len(payload) != payload_len:
        raise StateError(
            f"{path}: payload is {len(payload)}B, header claims {payload_len}B "
            f"— truncated or appended file")
    if fnv1a(payload) != checksum:
        raise StateError(
            f"{path}: payload checksum {fnv1a(payload):#018x} != header "
            f"{checksum:#018x} — the file is corrupt (bincode has no integrity "
            f"check of its own; a flipped byte decodes silently)")
    want_fp = rom_fingerprint(rom)
    if want_fp != rom_fp:
        raise StateError(
            f"{path}: rom fingerprint {rom_fp:#018x} != {rom_path}'s "
            f"{want_fp:#018x} — this state belongs to a DIFFERENT ROM. Point "
            f"--rom at the build the state was saved from; measuring against "
            f"the wrong ROM is how a stale artifact passes for a fresh one.")

    # `rom` then `ram`: find the cartridge bytes, step past them, read the varint.
    start = payload.find(rom[:512])
    if start < 0 or payload[start:start + len(rom)] != rom:
        raise StateError(
            f"{path}: the cartridge image is not in the payload where "
            f"System's field order puts it — the bincode layout moved "
            f"(container version {version}). Re-derive the offset from "
            f"oracle-core/src/system.rs before trusting anything below.")
    end = start + len(rom)
    marker = payload[end]
    if marker != VARINT_U32_MARKER:
        raise StateError(
            f"{path}: varint marker {marker:#04x} after `rom`, expected "
            f"{VARINT_U32_MARKER:#04x} — `ram` no longer follows `rom` in "
            f"System, or its length left the u32 varint band")
    length = struct.unpack_from("<I", payload, end + 1)[0]
    if length != RAM_BYTES:
        raise StateError(
            f"{path}: the Vec after `rom` is {length:#x} bytes, not "
            f"{RAM_BYTES:#x} — that is not the 64 KiB work RAM. System's "
            f"layout changed; fix this tool rather than reading the bytes.")
    ram = payload[end + 5:end + 5 + length]
    if len(ram) != RAM_BYTES:
        raise StateError(f"{path}: RAM runs off the end of the payload")
    return ram


def load_symbols(lst_path: str) -> dict:
    """`name -> address` from a sigil `.lst` symbol table.

    Reading the build's own listing keeps this tool from carrying a second copy
    of the RAM map that silently drifts from `ram.emp`.
    """
    syms = {}
    if not lst_path or not os.path.isfile(lst_path):
        return syms
    with open(lst_path, "r", errors="replace") as f:
        for line in f:
            parts = line.split(":", 1)
            if len(parts) != 2 or "/" not in parts[0]:
                continue
            addr = parts[0].rsplit("/", 1)[1].strip()
            name = parts[1].strip()
            if name.endswith(":") and addr and all(c in "0123456789ABCDEF" for c in addr):
                syms.setdefault(name[:-1], int(addr, 16))
    return syms


class Ram:
    """RAM window with 68K-endian accessors, addressed by absolute $FFxxxx."""

    def __init__(self, data: bytes, symbols: dict):
        self.data = data
        self.symbols = symbols

    def _off(self, addr: int) -> int:
        # The 68K sees work RAM at $FFFF0000-$FFFFFFFF (and its $FF0000 mirror),
        # so the low 16 bits ARE the offset. Reject anything that is not in a
        # RAM window rather than silently wrapping a ROM address into RAM.
        if not (RAM_BASE <= addr <= RAM_BASE + 0xFFFF
                or 0xFF0000 <= addr <= 0xFFFFFF
                or 0 <= addr < RAM_BYTES):
            raise StateError(
                f"address {addr:#x} is not in the 68K work-RAM window "
                f"($FFFF0000-$FFFFFFFF, its $FF0000 mirror, or a bare offset)")
        return addr & 0xFFFF

    def u8(self, addr): return self.data[self._off(addr)]

    def u16(self, addr):
        o = self._off(addr)
        return self.data[o] << 8 | self.data[o + 1]

    def s16(self, addr):
        v = self.u16(addr)
        return v - 0x10000 if v & 0x8000 else v

    def addr_of(self, name: str) -> int:
        if name in self.symbols:
            return self.symbols[name]
        if name in FALLBACK_SYMBOLS:
            return FALLBACK_SYMBOLS[name]
        raise StateError(
            f"symbol {name!r} is in neither the .lst nor the fallback table — "
            f"pass --lst pointing at the build's listing")


def report(ram: Ram, tag: str) -> None:
    p1 = ram.addr_of("Player_1")
    camx = ram.addr_of("Camera_X")
    camy = ram.addr_of("Camera_Y")
    status = ram.u8(p1 + SST_STATUS)
    state = ram.u8(p1 + PV_PLAYER_STATE)
    anim = ram.u8(p1 + SST_ANIM)
    flags = " ".join(n for b, n in STATUS_BITS if status & (1 << b)) or "none set"
    print(f"===== {tag} =====")
    print(f"  position   x={ram.u16(p1 + SST_X_POS)}.{ram.u16(p1 + SST_X_POS + 2):05d}"
          f"   y={ram.u16(p1 + SST_Y_POS)}.{ram.u16(p1 + SST_Y_POS + 2):05d}   (16.16)")
    print(f"  camera     x={ram.u16(camx)}  y={ram.u16(camy)}"
          f"   (both longwords: integer px in the HIGH word)")
    print(f"  velocity   x_vel={ram.s16(p1 + SST_X_VEL) / 256:+8.3f}"
          f"  y_vel={ram.s16(p1 + SST_Y_VEL) / 256:+8.3f} px/frame")
    print(f"  ground_spd {ram.s16(p1 + PV_GROUND_SPEED) / 256:+8.3f} px/frame")
    print(f"  state      {PSTATE.get(state, hex(state))}"
          f"   angle=${ram.u8(p1 + SST_ANGLE):02X}   layer={ram.u8(p1 + SST_LAYER)}")
    print(f"  status     ${status:02X} [{flags}]   (ST_* are BIT NUMBERS)")
    w, h = ram.u8(p1 + SST_WIDTH), ram.u8(p1 + SST_HEIGHT)
    print(f"  hitbox     {w} x {h} px full  ->  radii {w // 2} x {h // 2}")
    print(f"  anim       ${anim:02X} {ANIM.get(anim, '?')}"
          f"   mapframe=${ram.u8(p1 + SST_MAP_FRAME):02X}"
          f"   render_flags=${ram.u8(p1 + SST_RENDER_FLAGS):02X}")
    print(f"  move_lock  {ram.u16(p1 + PV_MOVE_LOCK)}")


def hexdump(ram: Ram, addr: int, length: int) -> None:
    for base in range(addr, addr + length, 16):
        n = min(16, addr + length - base)
        row = " ".join(f"{ram.u8(base + i):02X}" for i in range(n))
        print(f"  {base:06X}  {row}")


# ---------------------------------------------------------------------------
# Self-tests. Every expectation is DERIVED from save_state.rs / system.rs, never
# copied from an observed file: the synthetic container below is built by the
# same formulas the tool decodes with, so a wrong formula fails on both sides
# and is caught by the negative cases rather than agreeing with itself.
# ---------------------------------------------------------------------------

def _synth(rom: bytes, ram: bytes, *, ram_len=None, marker=VARINT_U32_MARKER,
           rom_fp=None, corrupt=False, magic=MAGIC) -> bytes:
    payload = (b"\x00" * 8                      # seed: u64
               + b"\x00" * 4                    # scheduler stand-in
               + bytes([VARINT_U32_MARKER]) + struct.pack("<I", len(rom)) + rom
               + bytes([marker]) + struct.pack("<I", ram_len if ram_len is not None else len(ram)) + ram
               + b"\xAA" * 32)                  # trailing z80_ram/vdp/... stand-in
    # Corruption: check-sum the CLEAN payload, then flip a byte inside it — the
    # exact case bincode accepts silently and the checksum exists to catch.
    header_ck = fnv1a(payload)
    if corrupt:
        payload = payload[:-1] + bytes([payload[-1] ^ 0xFF])
    fp = rom_fingerprint(rom) if rom_fp is None else rom_fp
    return (magic + struct.pack("<H", 1) + struct.pack("<Q", 0)
            + struct.pack("<Q", fp) + struct.pack("<Q", len(payload))
            + struct.pack("<Q", header_ck) + payload)


def _tmp(name, blob):
    import tempfile
    path = os.path.join(tempfile.mkdtemp(prefix="aeon_state_ram_"), name)
    with open(path, "wb") as f:
        f.write(blob)
    return path


def _expect(fn, needle, label):
    try:
        fn()
    except StateError as exc:
        assert needle in str(exc), f"{label}: wrong error {exc!r} (wanted {needle!r})"
        print(f"  [OK] {label}")
        return
    raise AssertionError(f"{label}: decoded a state that must have been refused")


def run_tests() -> int:
    rom = bytes((i * 7 + 3) & 0xFF for i in range(4096))
    ram = bytes((i * 13 + 5) & 0xFF for i in range(RAM_BYTES))
    other = bytes((i * 11 + 1) & 0xFF for i in range(4096))

    rom_p, other_p = _tmp("rom.bin", rom), _tmp("other.bin", other)

    good = _tmp("good.state0", _synth(rom, ram))
    assert read_state(good, rom_p) == ram, "round-trip lost the RAM bytes"
    print("  [OK] test_round_trip_recovers_ram")

    # fingerprint formula is exercised in both directions, not assumed
    assert rom_fingerprint(rom) != rom_fingerprint(other)
    assert rom_fingerprint(b"") == fnv1a(b"")
    print("  [OK] test_rom_fingerprint_formula")

    _expect(lambda: read_state(good, other_p), "DIFFERENT ROM",
            "test_refuses_wrong_rom")
    _expect(lambda: read_state(_tmp("m.state0", _synth(rom, ram, magic=b"XXXX")), rom_p),
            "not an oracle-frontend save state", "test_refuses_bad_magic")
    _expect(lambda: read_state(_tmp("c.state0", _synth(rom, ram, corrupt=True)), rom_p),
            "checksum", "test_refuses_corrupt_payload")
    _expect(lambda: read_state(_tmp("s.state0", _synth(rom, ram[:RAM_BYTES // 2])), rom_p),
            "not the 64 KiB work RAM", "test_refuses_wrong_ram_length")
    _expect(lambda: read_state(_tmp("v.state0", _synth(rom, ram, marker=0x10)), rom_p),
            "varint marker", "test_refuses_moved_ram_field")
    truncated = _synth(rom, ram)
    _expect(lambda: read_state(_tmp("t.state0", truncated[:-64]), rom_p),
            "truncated or appended", "test_refuses_truncated_file")

    # Reading the ROM's own bytes must not be mistaken for RAM: a state whose
    # RAM happens to equal the ROM prefix still decodes to the RAM Vec.
    twin = bytes(rom[i % len(rom)] for i in range(RAM_BYTES))
    assert read_state(_tmp("tw.state0", _synth(rom, twin)), rom_p) == twin
    print("  [OK] test_ram_equal_to_rom_prefix_still_decodes")

    print("state_ram: all self-tests passed")
    return 0


def main(argv) -> int:
    if len(argv) >= 2 and argv[1] == "test":
        return run_tests()
    if len(argv) < 2:
        print(__doc__)
        return 2

    state = argv[1]
    rom = None
    lst = None
    dump = None
    raw = None
    i = 2
    while i < len(argv):
        if argv[i] == "--rom":
            rom = argv[i + 1]; i += 2
        elif argv[i] == "--lst":
            lst = argv[i + 1]; i += 2
        elif argv[i] == "--dump":
            dump = (int(argv[i + 1], 16), int(argv[i + 2], 0)); i += 3
        elif argv[i] == "--raw":
            raw = argv[i + 1]; i += 2
        else:
            print(f"unknown argument {argv[i]!r}")
            return 2

    if rom is None:
        # `foo.state3` was saved next to `foo.bin` — save_state.rs's naming rule.
        rom = os.path.splitext(state)[0] + ".bin"
    if lst is None:
        cand = os.path.splitext(rom)[0] + ".lst"
        lst = cand if os.path.isfile(cand) else None

    try:
        data = read_state(state, rom)
    except StateError as exc:
        print(f"REFUSED: {exc}")
        return 1

    ram = Ram(data, load_symbols(lst))
    if raw:
        with open(raw, "wb") as f:
            f.write(data)
        print(f"wrote {len(data)} bytes of work RAM to {raw}")
    if dump:
        hexdump(ram, dump[0], dump[1])
    if not raw and not dump:
        report(ram, f"{os.path.basename(state)}  (rom {os.path.basename(rom)}"
                    f"{', symbols from ' + os.path.basename(lst) if lst else ''})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
