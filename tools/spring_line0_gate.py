#!/usr/bin/env python3
"""spring_line0_gate — do the spring's palette indices resolve to the SAME colours
whichever character is active?

THE CLAIM UNDER TEST, and it is a runtime one. `Art_Spring` is drawn with palette 0
(`vram_art(VRAM_SPRING)` in games/sonic4/objects/test_solid.emp), and CRAM line 0 is the
PER-CHARACTER line: Player_RefreshPhysics copies the active CharacterDef.cd_palette into
`Palette_Buffer` and sets `Palette_Dirty` bit 0, and the VBlank buffer ship carries it to
CRAM. So the spring's seven indices — 0, 1, 6, 7, 8, 12, 13 — render through whichever
character's line is loaded. The 2026-09-09 bug was four of them disagreeing between
Pal_SonicTails and Pal_Knuckles; the fourth, index 9, left the art on the owner's ruling
(SPRING-PAL-IDX9: gen_spring.py moves it onto 8), so there is no exemption left.

WHAT THIS READS: the VDP's own CRAM, out of a running headless build, once as Sonic and
once as Knuckles, and it compares the two AT THE SPRING'S INDICES.

EXPECTATIONS ARE DERIVED, NOT COPIED. The per-index verdict comes from the two palette
FILES on disk (art/palettes/SonicAndTails.bin, art/palettes/knuckles.bin) and the index
set comes from a nibble histogram of the ART FILE
(games/sonic4/data/generated/spring/art_spring.bin). Nothing here restates a number that
lives somewhere else — re-cut the sprite or re-export a palette and this gate re-derives.

HOW THE SWAP IS DRIVEN: the live debug hotkey — `Debug_CharacterHotkey`,
games/sonic4/test/ojz_scroll_test.emp. The OJZ test state boots ALREADY in debug fly
(`debug_flag` = $FF at frame 240, measured), so A alone cycles; no B is pressed, and
pressing one would LEAVE debug fly and make every later A inert. `press` is the LIVE pad,
which matters: the hotkey stands down when `Input_Source` is non-zero (replay or record),
so `play_input` would silently make this gate vacuous.

`Character_ID` IS A WORD. Reading it as a byte reads the high half and answers 0 for every
character — which is exactly how this gate first "measured" that the hotkey did not work
at all. It is read as a word here and asserted to have REACHED CHAR_KNUCKLES, so a swap
that does not land is a refusal rather than a comparison of one palette against itself.

CRAM ENTRY 0 IS NOT THE PALETTE FILE'S ENTRY 0 and that is not this bug: both
`Palette_Buffer` and CRAM hold $000E there where the file holds $0000, under BOTH
characters (measured). Entry 0 is the VDP's transparent/backdrop slot — no sprite pixel
renders through it — so the gate prints it and excludes it from every comparison. Which
writer sets it was not established here.

LOUD ON UNMEASURABLE. Every failure to establish something — the swap not landing, CRAM
reading identical under two different characters, a palette file the wrong length — is a
REFUSAL with a message, never a 0 or a green.

WHAT THIS DOES NOT COVER: the SPRING's own pixels are never read (this is CRAM, not the
framebuffer) — that a given index is used by the sprite comes from the art histogram, not
from the screen; a shared line-0 sprite other than the spring (the effect dust and the
insta-shield are the other two — knuckles_data.emp enumerates them); and the third
character, Tails, who shares Sonic's palette file by construction and so cannot differ.

Usage:  python3 tools/spring_line0_gate.py [--rom s4.debug.bin] [--lst s4.debug.lst]
Exit 0 = every spring index resolves identically under both characters.
"""
import argparse
import asyncio
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # tools/, for suite_paths
from suite_paths import add_client_path, repo_path          # noqa: E402
add_client_path()                                           # loud if the client is absent
from aether import BusClient                                # noqa: E402
from aether_instance import aether_emulator, read_bytes     # noqa: E402
from raster_cost_probe import parse_lst                     # noqa: E402

PAL_SONIC = "art/palettes/SonicAndTails.bin"
PAL_KNUX = "art/palettes/knuckles.bin"
SPRING_ART = "games/sonic4/data/generated/spring/art_spring.bin"

# CRAM entry 0 is the VDP's transparent/backdrop slot; the engine holds a colour there that
# is not the palette file's entry 0, identically under both characters (see the header). No
# sprite pixel renders through it, so it is printed and excluded from every comparison.
BACKDROP_INDEX = 0

# PlayerV.debug_flag — Sst.sst_custom ($30) + the overlay offset (games/sonic4/player/
# player_common.emp: ground_speed .w, player_state .b, status_secondary .b, move_lock .w,
# spindash_charge .w, flip_angle .b, air_left .b, invuln_time .b, stick_convex .b).
DEBUG_FLAG_OFF = 0x3C

# Frames to settle after boot and after each pad action. The level's own init streams art
# for a while; the palette ship is one VBlank, so these are generous rather than tuned.
BOOT_FRAMES = 240
SETTLE_FRAMES = 8


class Refuse(Exception):
    """Something could not be MEASURED. Never rendered as a pass or a zero."""


def cram_line(path: Path):
    d = path.read_bytes()
    if len(d) != 32:
        raise Refuse(f"{path} is {len(d)} bytes, not the 32 of one 16-entry CRAM line — "
                     f"the per-index expectations cannot be derived from it")
    return [struct.unpack_from(">H", d, i * 2)[0] for i in range(16)]


def spring_indices(path: Path):
    """The 4bpp indices the spring art actually draws, with pixel counts. 2 px/byte."""
    d = path.read_bytes()
    if not d or len(d) % 32:
        raise Refuse(f"{path} is {len(d)} bytes — not a whole number of 32-byte tiles")
    c = Counter()
    for b in d:
        c[b >> 4] += 1
        c[b & 0x0F] += 1
    return {i: n for i, n in sorted(c.items()) if n}


async def read_line0(b):
    """CRAM line 0 as 16 words, tolerant of the reply's list-key spelling."""
    r = await b.call("emulator/read_cram", {"line": 0})
    ents = next((v for v in r.values()
                 if isinstance(v, list) and v and isinstance(v[0], dict) and "raw" in v[0]),
                None)
    if ents is None or len(ents) < 16:
        raise Refuse(f"emulator/read_cram gave no readable 16-entry line 0 (keys "
                     f"{sorted(r)}) — the CRAM instrument is UNMEASURABLE here, not green")
    return [int(ents[i]["raw"], 16) & 0x0FFF for i in range(16)]


async def press(b, buttons, frames=2):
    await b.call("emulator/press", {"buttons": buttons, "frames": frames})
    await b.call("emulator/run_frames", {"frames": SETTLE_FRAMES})


async def run(sock, lst, want_id):
    b = BusClient(socket_path=sock, client_id="springpal", client_name="spring_line0_gate")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})
    sym = parse_lst(lst)
    for n in ("Character_ID", "Player_1"):
        if n not in sym:
            raise Refuse(f"symbol {n} is absent from {lst} — the swap cannot be verified, "
                         f"only assumed")
    await b.call("emulator/reset", {})
    await b.call("emulator/run_frames", {"frames": BOOT_FRAMES})

    async def char_id():
        return int(await read_bytes(b, sym["Character_ID"], 2), 16)      # WORD, see header

    async def debug_flag():
        return int(await read_bytes(b, sym["Player_1"] + DEBUG_FLAG_OFF, 1), 16)

    if await debug_flag() == 0:
        raise Refuse(f"the state is not in debug fly at frame {BOOT_FRAMES} "
                     f"(PlayerV.debug_flag = 0), so A is the jump button and the character "
                     f"hotkey cannot fire — this run measures nothing")
    if await char_id() != 0:
        raise Refuse(f"Character_ID is {await char_id()} at boot, not 0 — the 'as Sonic' "
                     f"read is not Sonic's")
    as_sonic = await read_line0(b)

    # A cycles; the state is already in debug fly, so no B (a B press would LEAVE it and
    # make every later A inert — that is how this gate first mis-measured).
    for _ in range(want_id):
        await press(b, ["a"])
    got_id = await char_id()
    if got_id != want_id:
        raise Refuse(f"after {want_id} A press(es) Character_ID is {got_id}, not {want_id} "
                     f"(CHAR_KNUCKLES) — the hotkey did not cycle as expected")
    as_knux = await read_line0(b)
    return as_sonic, as_knux


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(repo_path("s4.debug.bin")))
    ap.add_argument("--lst", default=str(repo_path("s4.debug.lst")))
    ap.add_argument("--cycles", type=int, default=2,
                    help="A presses to reach Knuckles (roster Sonic->Tails->Knuckles); "
                         "also the Character_ID the run must REACH")
    a = ap.parse_args()

    try:
        want_sonic = cram_line(repo_path(PAL_SONIC))
        want_knux = cram_line(repo_path(PAL_KNUX))
        used = spring_indices(repo_path(SPRING_ART))
        with aether_emulator(a.rom, symbols=a.lst) as sock:
            got_sonic, got_knux = asyncio.run(run(sock, a.lst, a.cycles))
    except Refuse as e:
        print(f"REFUSE: {e}")
        return 2

    print(f"spring art draws {len(used)} indices: "
          + ", ".join(f"{i} ({n} px)" for i, n in used.items()))
    print()
    print("CRAM line 0 read out of the running build:")
    print("  as Sonic   : " + " ".join(f"{v:04X}" for v in got_sonic))
    print("  as Knuckles: " + " ".join(f"{v:04X}" for v in got_knux))
    print()

    fails = []
    # The swap must have LANDED, or "the two agree" is a statement about one palette read
    # twice. Both halves are checked against the files, so a wrong-character read is loud.
    # Entry 0 is excluded: it is the VDP backdrop, not the palette file's slot 0.
    def body(v):
        return [c for i, c in enumerate(v) if i != BACKDROP_INDEX]

    if body(got_sonic) != body(want_sonic):
        fails.append(f"CRAM line 0 after boot is not {PAL_SONIC} — the pre-swap read is "
                     "not Sonic's palette, so nothing below is about the character it names")
    if got_knux == got_sonic:
        fails.append("CRAM line 0 is IDENTICAL before and after the swap — the character "
                     "hotkey did not land (VACUOUS: this gate would pass on any palette)")
    if body(got_knux) != body(want_knux):
        fails.append(f"CRAM line 0 after the swap is not {PAL_KNUX} — the run did not "
                     "reach Knuckles, so the per-index verdicts below are not his")
    if fails:
        for f in fails:
            print("REFUSE: " + f)
        return 2

    print("per-index verdict at the spring's own indices "
          "(expectations derived from the two palette files):")
    bad = []
    for i, n in used.items():
        s, k = got_sonic[i], got_knux[i]
        if i == BACKDROP_INDEX:
            verdict = "VDP backdrop / transparent — not rendered, excluded"
        elif s == k:
            verdict = "SAME"
        else:
            verdict = "DIFFERS — FAIL"
            bad.append(i)
        print(f"  idx {i:2d} ({n:4d} px): Sonic ${s:04X}  Knuckles ${k:04X}   {verdict}")

    print()
    if bad:
        print(f"FAIL: {len(bad)} spring index(es) recolour on a character swap: {bad}")
        return 1
    print("PASS: every spring index resolves identically under both characters.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
