"""The built sound-bank head carries every PSG/FM volume envelope the generator declares,
at the addresses its pointer tables say, and the resident Z80 driver names those addresses.

WHY (S2CLIP-REGION-MUSIC step 2, 2026-09-25). Five Sonic 2 envelopes ($41/$42/$43/$48/$4B)
were appended to the `sound_tables_z80` head, which moved every label after the PSG id list.
Nothing in aeon types those addresses any more: sigil (6b724981) derives the eleven banked
carriers the resident driver reads, and soundbankhead.emp lays the heads down from their
measured lengths. This is the BUILT-IMAGE check that the derivation reached the bytes: it reads
the head out of the ROM and decodes it the way `PsgVolEnv_Resolve` / the FM env reader do (scan
the id list, index the pointer table, read the body through the $8000 window), against
tools/gen_sound_tables.py's own tables. The layout it decodes with is computed from the
generator (table lengths, in emission order), never from sigil or a number written here.

WHAT IT CHECKS, per shape:
  1. the id list, pointer table and every body, PSG and FM, decode to the generator's tables
     (so the eleven S3K ids keep their ids, order and bodies, and the S2 ids are reachable);
  2. the listing's `SndDefaultPitchTable` window VMA is $8000 + the table's length (the head
     after it follows the measured table, not a pinned address);
  3. the resident Z80 blob contains, as a little-endian operand, the window address of each of
     the four vol-env tables and of SndDefaultPitchTable.

WHAT A GREEN DOES NOT SAY. (3) is presence, not placement: it does not prove each operand sits
in the instruction that reads that table (sigil's banked_carrier_derivation test doctors each
carrier and proves the blob moves). Nothing here was listened to.
"""

import os
import re
import unittest

import pytest

import gen_sound_tables as gst

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WINDOW = 0x8000


def lst_symbols(path):
    """Symbol -> address from a sigil listing's symbol table (` Name : HEX C |`)."""
    out = {}
    with open(path, errors="replace") as fh:
        for line in fh:
            m = re.match(r"^ (\w+) : ([0-9A-F]+) C \|", line)
            if m:
                out[m.group(1)] = int(m.group(2), 16)
    return out


def phase_lma(path, name):
    """The LMA sigil's listing records for a phased label (`PHASE <n> VMA $.. LMA $..`)."""
    with open(path, errors="replace") as fh:
        for line in fh:
            m = re.match(r"^PHASE (\w+) VMA \$([0-9A-F]+) LMA \$([0-9A-F]+)", line)
            if m and m.group(1) == name:
                return int(m.group(3), 16)
    return None


def generator_layout():
    """Offsets of the vol-env pieces inside sound_tables_z80, from the generator's own tables
    in the order emit_emp_z80 emits them: 4 LUTs, PSG ids/ptrs/bodies, FM ids/ptrs/bodies."""
    off = 2 * len(gst.fm_pitch_table()) + 2 * len(gst.psg_divisor_table())
    off += len(gst.log_volume_lut()) + len(gst.carrier_mask_table())
    lay = {}
    for kind, envs in (("Psg", gst._PSG_VOL_ENVS), ("Fm", gst._FM_VOL_ENVS)):
        lay[kind + "VolEnv_Ids"] = off
        off += len(envs)
        lay[kind + "VolEnv_Ptrs"] = off
        off += 2 * len(envs)
        for env_id, _name, body in envs:
            lay[(kind, env_id)] = off
            off += len(body)
    lay["length"] = off
    return lay


def check_shape(tc, rom_name, lst_name):
    rom_p, lst_p = os.path.join(AEON, rom_name), os.path.join(AEON, lst_name)
    for p in (rom_p, lst_p):
        tc.assertTrue(os.path.isfile(p), f"{p} is missing: this grades the built image")
    rom = open(rom_p, "rb").read()
    syms = lst_symbols(lst_p)
    head = phase_lma(lst_p, "SoundTablesZ80_Head")
    tc.assertIsNotNone(head, f"{lst_name} has no PHASE line for SoundTablesZ80_Head")
    lay = generator_layout()

    def u8(off):
        return rom[head + off]

    def le16(off):
        return rom[head + off] | (rom[head + off + 1] << 8)

    report = []
    for kind, envs in (("Psg", gst._PSG_VOL_ENVS), ("Fm", gst._FM_VOL_ENVS)):
        ids_off, ptrs_off = lay[kind + "VolEnv_Ids"], lay[kind + "VolEnv_Ptrs"]
        got_ids = [u8(ids_off + i) for i in range(len(envs))]
        tc.assertEqual(got_ids, [e[0] for e in envs],
                       f"{rom_name}: {kind}VolEnv_Ids in the ROM differ from the generator")
        for i, (env_id, name, body) in enumerate(envs):
            ptr = le16(ptrs_off + 2 * i)
            tc.assertEqual(ptr, WINDOW + lay[(kind, env_id)],
                           f"{rom_name}: {kind} env ${env_id:02X} ({name}) pointer ${ptr:04X} is "
                           f"not its body's window address ${WINDOW + lay[(kind, env_id)]:04X}")
            got = [u8(ptr - WINDOW + k) for k in range(len(body))]
            tc.assertEqual(got, list(body),
                           f"{rom_name}: {kind} env ${env_id:02X} ({name}) body at ${ptr:04X} differs")
            report.append(f"{kind} ${env_id:02X}@${ptr:04X}")

    # (2) the head after the table follows its measured length.
    tc.assertEqual(syms.get("SndDefaultPitchTable"), WINDOW + lay["length"],
                   f"{rom_name}: SndDefaultPitchTable is not at $8000 + the table length "
                   f"(${WINDOW + lay['length']:04X})")

    # (3) the resident driver names each derived table address as an operand.
    z0, z1 = syms.get("Z80_Sound_Start"), syms.get("Z80_Sound_End")
    tc.assertTrue(z0 is not None and z1 is not None and z1 > z0,
                  f"{lst_name} lacks Z80_Sound_Start/End")
    blob = rom[z0:z1]
    for label in ("PsgVolEnv_Ids", "PsgVolEnv_Ptrs", "FmVolEnv_Ids", "FmVolEnv_Ptrs"):
        vma = WINDOW + lay[label]
        tc.assertIn(bytes([vma & 0xFF, vma >> 8]), blob,
                    f"{rom_name}: no operand ${vma:04X} ({label}) in the resident Z80 blob")
    pitch = WINDOW + lay["length"]
    tc.assertIn(bytes([pitch & 0xFF, pitch >> 8]), blob,
                f"{rom_name}: no operand ${pitch:04X} (SndDefaultPitchTable) in the Z80 blob")
    return report


class SoundHeadEnvelopes(unittest.TestCase):

    def test_generator_carries_the_s2_envelopes(self):
        ids = [e[0] for e in gst._PSG_VOL_ENVS]
        for s2 in (0x41, 0x42, 0x43, 0x48, 0x4B):
            self.assertIn(s2, ids)

    @pytest.mark.needs_build("s4.bin", "s4.lst")
    def test_plain_rom(self):
        check_shape(self, "s4.bin", "s4.lst")

    @pytest.mark.needs_build("s4.debug.bin", "s4.debug.lst")
    def test_debug_rom(self):
        check_shape(self, "s4.debug.bin", "s4.debug.lst")


if __name__ == "__main__":
    unittest.main()
