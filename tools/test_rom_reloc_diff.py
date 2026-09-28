"""tools/rom_reloc_diff.py on a synthetic ROM pair: a clean relocation passes, and each kind of
real content change fails by name.

The pair mimics song bank 2 step 1: the song pointer tables move from before the SFX block to
after it, the SFX block moves down by the tables' size, a 68k absolute reference to SongTable
and a Z80 window pointer into the SFX block follow them, and the header checksum changes.
The songs are REAL committed blobs (the tool's table check matches against them), so this
test also fails if the tool stops finding the committed blobs.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rom_reloc_diff as rrd  # noqa: E402

SONG = (rrd.SOUND_DIR / "song_drumtest.bin").read_bytes()
PATCH = (rrd.SOUND_DIR / "s2_cpz_patches.bin").read_bytes()
SFX_LEN = 0x38
END = 0x800


def _lst(labels: dict[str, int]) -> str:
    return "".join(f"(0) {i + 1}/{a:X} :        {n}:\n" for i, (n, a) in enumerate(labels.items()))


def _sfx_block(base: int) -> bytearray:
    blk = bytearray(range(0x40, 0x40 + SFX_LEN))
    blk[8:10] = (0x8000 | ((base + 0x20) & 0x7FFF)).to_bytes(2, "little")  # a Z80 window ptr
    return blk


def build(tables_after_sfx: bool) -> tuple[bytearray, dict[str, int]]:
    rom = bytearray(END)
    lab: dict[str, int] = {"Vectors": 0}
    rom[0x18E:0x190] = b"\x12\x34" if tables_after_sfx else b"\xab\xcd"  # checksum word
    lab["Code"] = 0x200
    lab["Song_DrumTest"] = 0x240
    rom[0x240:0x240 + len(SONG)] = SONG
    lab["S2_CPZ_Patches"] = 0x300
    rom[0x300:0x300 + len(PATCH)] = PATCH
    tab = 0x3C0
    if tables_after_sfx:
        sfx, st = tab, tab + SFX_LEN
    else:
        sfx, st = tab + 8, tab
    lab["SongTable"], lab["SongPatchTable"], lab["Sfx_33"] = st, st + 4, sfx
    rom[st:st + 4] = (0x240).to_bytes(4, "big")
    rom[st + 4:st + 8] = (0x300).to_bytes(4, "big")
    rom[sfx:sfx + SFX_LEN] = _sfx_block(sfx)
    rom[0x200:0x206] = b"\x20\x7c" + st.to_bytes(4, "big")  # movea.l #SongTable, a0
    lab["Tail"] = 0x480
    rom[0x480:0x490] = bytes(range(16))
    lab["EndOfRom"] = END - 0x100
    lab = dict(sorted(lab.items(), key=lambda kv: kv[1]))
    return rom, lab


def run(tmp_path: Path, mutate=None) -> int:
    old, ol = build(False)
    new, nl = build(True)
    if mutate:
        mutate(new, nl)
    paths = []
    for tag, rom, lab in (("old", old, ol), ("new", new, nl)):
        (tmp_path / f"{tag}.bin").write_bytes(rom)
        (tmp_path / f"{tag}.lst").write_text(_lst(lab))
        paths += [f"--{tag}", str(tmp_path / f"{tag}.bin"), f"--{tag}-lst", str(tmp_path / f"{tag}.lst")]
    return rrd.main(paths)


def test_clean_relocation_passes(tmp_path, capsys):
    assert run(tmp_path) == 0
    out = capsys.readouterr().out
    assert "'abs32'" in out and "'win16l'" in out and "'header'" in out, out
    assert "SongTable[0] song_drumtest.bin" in out and "SongPatchTable[0] s2_cpz_patches.bin" in out


@pytest.mark.parametrize("name,mutate", [
    ("song byte", lambda r, l: r.__setitem__(0x250, r[0x250] ^ 1)),
    ("sfx byte", lambda r, l: r.__setitem__(l["Sfx_33"] + 3, r[l["Sfx_33"] + 3] ^ 1)),
    ("tail code byte", lambda r, l: r.__setitem__(0x485, 0xEE)),
    ("table entry retargeted", lambda r, l: r.__setitem__(slice(l["SongTable"], l["SongTable"] + 4),
                                                          (0x300).to_bytes(4, "big"))),
    ("window ptr off by 2", lambda r, l: r.__setitem__(
        slice(l["Sfx_33"] + 8, l["Sfx_33"] + 10),
        (0x8000 | ((l["Sfx_33"] + 0x22) & 0x7FFF)).to_bytes(2, "little"))),
    ("stray new byte in fill", lambda r, l: r.__setitem__(0x600, 0x55)),
])
def test_real_change_fails(tmp_path, capsys, name, mutate):
    assert run(tmp_path, mutate) == 1, capsys.readouterr().out


def test_no_end_of_rom_could_not_measure(tmp_path):
    def drop(r, l):
        del l["EndOfRom"]
    assert run(tmp_path, drop) == 2
