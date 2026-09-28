#!/usr/bin/env python3
"""parallax_shadow_key_witness — Step 4a's cached shadow view equals a rebuilt one, tick by tick.

WHAT IT GUARDS (PERF-PARALLAX-PERBAND, 2026-09-28). `Parallax_Step4_Fill` no longer rebuilds
the rotated shadow band view every tick: it keeps it while (config, Vscroll_BG & 511) equals
`Parallax_Shadow_Key_Config` / `_VS`, and Step 4b's anchored split drops the key because it
rewrites the view (engine/level/parallax.emp, Step 4a's banner: four clauses). A key that
vouches for a view it does not describe paints stale band tops or a doubled split, and
nothing else in the tree would see it: `parallax_hscroll_identity.py` installs RAM fixtures,
and a RAM config is never keyed, so it only ever exercises the rebuild path.

HOW, WITHOUT A MODEL. The question "is the cached view the view a rebuild would make?" is
asked of the machine itself, differentially, at every sampled tick:

    checkpoint -> run one frame (the ROM's own choice: hit or rebuild) -> capture A
    restore    -> poke Parallax_Shadow_Key_Config = 0 (forces the rebuild) and
                  Parallax_Band_Sel_Valid = 0 (forces the fill's selection pass)
               -> run one frame -> capture B
    A must equal B: Hscroll_Buffer, the VSRAM column buffer, Vscroll_Factor, the whole
    shadow band array and both shadow scroll arrays, the fill's cached loop selection
    (Parallax_Band_Sel) and the curve hoist's walk (Parallax_Curve_Walk).

Zero is never a config pointer, so the poke selects the rebuild path and nothing else; both
runs start from one restored state, so any difference IS the cache. No expectation is typed:
the reference is the engine's own rebuild.

THE TWO CACHES KEPT UNDER THE SAME KEY (PPB-3 / PPB-5, 2026-09-28, perf/parallax-perband-2).
The selection bytes are re-derived only while their flag is 0, and a forced view rebuild
clears it the ROM's own way; the flag is poked anyway, so B re-derives them even on a tree
whose rebuild path forgot to (red-first: mutant K in
docs/research/2026-09-28-parallax-perband-2/build_mutant2.sh). The curve walk is derived on
every rebuild, so the key poke alone re-derives it. Both are compared as well as the output
they steer, because a stale cache that happens to steer to the same output on a sampled tick
is still stale.

WHAT MAKES A GREEN MEAN SOMETHING — the coverage witnesses, printed every run and REQUIRED:
  * hit      samples whose PRE-frame key was live (non-zero): the cached path was taken
             (or could have been); a leg with none tests nothing;
  * vs-moved samples where the key was live and Vscroll_BG & 511 changed in the frame: the
             state a key that ignored vs would get wrong;
  * split    samples on a ROM config where Step 4b split the view (the key read 0 after the
             frame): the state a split that kept the key would get wrong.
Any class at 0 is COULD NOT RUN, never green.

LEGS (DEBUG free flight, which the shape boots in): from spawn, fly down (vs moves); then,
through the DEBUG warp mailbox, into the act's anchored region (derived from the ROM's
region table: a region whose resolved config consumes an anchor channel and whose preset
seeds a world anchor on it), fly right and then down with the anchor line on screen.

Exit 0 GREEN, 1 RED (a sample differed), 2 COULD NOT RUN (missing symbols, no anchored
region, a coverage class at 0). The last line is finished=1 on every path that gets that
far. Red-first: the two mutants in docs/research/2026-09-28-parallax-perband/build_mutant.sh.
"""
import argparse
import asyncio
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient  # noqa: E402
from aether_bytes import read_bytes, write_bytes  # noqa: E402
import region_table  # noqa: E402

AEON = HERE.parent
ROM_TOP = 0x400000     # the engine's own test (Step 4a's `.shadow_built`): ROM is below it
CAPTURE = [("Hscroll_Buffer", 896), ("Parallax_Vscroll_Column_Buf", 80), ("Vscroll_Factor", 4)]
# Everything from the key to the end of Parallax_State, captured after the shadow arrays: the
# key itself, then the caches kept under it besides the view (PPB-3's selection bytes and flag,
# PPB-5's curve walk). One linked distance, so a field added to that tail is compared without
# an edit here. (Until 2026-09-28 round 2 the shadow capture was sized `Scroll_B + 2 x (B - A)`,
# which over-read 32 bytes past Scroll_B's end and so took in the key by accident; the capture
# is exact now and the key is named.)
CACHES = [("Parallax_Shadow_Key_Config", "Parallax_State_End")]
TAIL_FIELDS = ["Parallax_Shadow_Key_Config", "Parallax_Band_Sel", "Parallax_Band_Sel_Valid",
               "Parallax_Curve_Walk"]


class CouldNotRun(Exception):
    pass


def parse_lst(path):
    """(symbols, equates) from a sigil listing: `(0) <idx>/<hex> :   Name:` and `EQU name = $v`."""
    syms, equs = {}, {}
    for line in Path(path).read_text(errors="replace").splitlines():
        if line.startswith("(0) "):
            try:
                addrpart, namepart = line[4:].split(" :", 1)
                addr = int(addrpart.split("/", 1)[1], 16)
            except (ValueError, IndexError):
                continue
            name = namepart.strip().rstrip(":")
            if name and "$" not in name and name not in syms:
                syms[name] = addr & 0xFFFFFF
        else:
            m = re.match(r"^EQU\s+(\w+)\s*=\s*\$([0-9A-Fa-f]+)", line)
            if m:
                equs[m.group(1)] = int(m.group(2), 16)
    return syms, equs


def emp_const(rel, name):
    m = re.search(rf"^pub const {name}\s*=\s*\$([0-9A-Fa-f]+)", (AEON / rel).read_text(), re.M)
    if not m:
        raise CouldNotRun(f"{rel} no longer declares `pub const {name} = $..`")
    return int(m.group(1), 16)


def preset_field(name):
    txt = (AEON / "engine/effects/preset.emp").read_text()
    m = re.search(rf"^\s*{re.escape(name)}\s*:[^@\n]*@\s*\$([0-9A-Fa-f]+)", txt, re.M)
    if not m:
        raise CouldNotRun(f"struct EffectsPreset no longer declares `{name}` with an `@ $HH` offset")
    return int(m.group(1), 16)


def anchored_region(rom, act_base, equs):
    """The first region whose RESOLVED config (rg_parallax, else ep_parallax, else the act's)
    names an anchor channel its preset seeds with a real world Y: (region row, world Y)."""
    act_off, _ = region_table.struct_layout("Act")
    act_default = int.from_bytes(rom[act_base + act_off["act_parallax_config"]:][:4], "big")
    ep_par, ep_wy = preset_field("ep_parallax"), preset_field("ep_patch_world_ys")
    none_ch = 0xFF
    none_wy = emp_const("engine/effects/raster_dsl.emp", "PATCH_ANCHOR_NONE")
    ach = equs["parallax_config_pcfg_anchor_ch"]
    for r in region_table.read_regions(rom, act_base):
        ep = r["effects"]
        cfg = r["parallax"] or int.from_bytes(rom[ep + ep_par:][:4], "big") or act_default
        ch = rom[cfg + ach]
        if ch == none_ch:
            continue
        wy = int.from_bytes(rom[ep + ep_wy + 2 * ch:][:2], "big")
        if wy != none_wy:
            return r, wy
    return None, None


async def rd(b, addr, n):
    return bytes.fromhex(await read_bytes(b, addr, n))


async def snap(b, s, shadow_len):
    out = b""
    for nm, n in CAPTURE:
        out += await rd(b, s[nm], n)
    out += await rd(b, s["Parallax_Shadow_Bands"], shadow_len)
    for nm, end in CACHES:
        out += await rd(b, s[nm], s[end] - s[nm])
    return out


async def sample(b, s, shadow_len, stats, leg):
    """One tick, twice: as the ROM chooses, then with the key forced to 0. Compare."""
    key0 = int.from_bytes(await rd(b, s["Parallax_Shadow_Key_Config"], 8), "big")
    kcfg, kvs = key0 >> 32, (key0 >> 16) & 0xFFFF
    cp = (await b.call("emulator/checkpoint", {}))["id"]
    try:
        await b.call("emulator/run_frames", {"frames": 1})
        a = await snap(b, s, shadow_len)
        cfg = int.from_bytes(await rd(b, s["Parallax_Current_Config"], 4), "big") & 0xFFFFFF
        vs = int.from_bytes(await rd(b, s["Parallax_Current_Vscroll_BG"], 2), "big") & 0x1FF
        key1 = int.from_bytes(await rd(b, s["Parallax_Shadow_Key_Config"], 4), "big")
        await b.call("emulator/restore", {"id": cp})
        await write_bytes(b, s["Parallax_Shadow_Key_Config"], "00000000")
        await write_bytes(b, s["Parallax_Band_Sel_Valid"], "00")
        await b.call("emulator/run_frames", {"frames": 1})
        bb = await snap(b, s, shadow_len)
        # leave the machine on the ROM's own path (A), not the forced one, for the next tick
        await b.call("emulator/restore", {"id": cp})
        await b.call("emulator/run_frames", {"frames": 1})
    finally:
        await b.call("emulator/checkpoint_drop", {"id": cp})
    stats["samples"] += 1
    if kcfg:
        stats["hit"] += 1
        if vs != kvs:
            stats["vs_moved"] += 1
    if key1 == 0 and cfg < ROM_TOP:
        stats["split"] += 1
    if a != bb:
        stats["differ"] += 1
        if len(stats["first"]) < 5:
            i = next(k for k in range(len(a)) if a[k] != bb[k])
            j = i - 980 - shadow_len
            if j >= 0:
                at = s["Parallax_Shadow_Key_Config"] + j
                fld = max((f for f in TAIL_FIELDS if s[f] <= at), key=lambda f: s[f])
                where = f"{fld} byte {at - s[fld]}"
            else:
                where = ("Hscroll_Buffer" if i < 896 else "VSRAM column buf" if i < 976 else
                         "Vscroll_Factor" if i < 980 else f"shadow band byte {i - 980}")
            stats["first"].append(f"{leg}: sample {stats['samples']} (pre-key cfg ${kcfg:06X} "
                                  f"vs {kvs}, now vs {vs}) first difference at {where}")


async def drive(sock, s, equs, rom, legs_frames):
    b = BusClient(socket_path=sock, client_id="pxkey", client_name="parallax_shadow_key_witness")
    await b.connect()
    # the band records and both scroll arrays: Scroll_B's end is Scroll_B + (B - A)
    shadow_len = s["Parallax_Shadow_Scroll_B"] + (s["Parallax_Shadow_Scroll_B"]
                                                  - s["Parallax_Shadow_Scroll_A"]) \
        - s["Parallax_Shadow_Bands"]
    await b.call("emulator/run_frames", {"frames": 420})   # boot, title-less, settle in flight
    act = int.from_bytes(await rd(b, s["Current_Act_Ptr"], 4), "big") & 0xFFFFFF
    if not act:
        raise CouldNotRun("Current_Act_Ptr read 0 after boot: no act to derive a region from")
    reg, wy = anchored_region(rom, act, equs)
    if reg is None:
        raise CouldNotRun(f"the act at ${act:06X} has no region pairing an anchor channel with a "
                          f"world anchor, so the split class cannot be reached")
    out = {}
    for leg, dirs, warp in (("spawn down", ["down"], None),
                            ("anchor right", ["right"], (reg["x0"] + 104, wy - 22)),
                            ("anchor down", ["down"], (reg["x0"] + 104, wy - 372))):
        if warp:
            wx, wyy = warp
            await write_bytes(b, s["Warp_Req_X"], f"{wx:04X}")
            await write_bytes(b, s["Warp_Req_Y"], f"{wyy:04X}")
            await write_bytes(b, s["Warp_Req_Flag"], "01")
            for _ in range(120):
                await b.call("emulator/run_frames", {"frames": 1})
                if (await rd(b, s["Warp_Req_Flag"], 1))[0] == 0:
                    break
            else:
                raise CouldNotRun("the DEBUG warp mailbox never acknowledged")
            await b.call("emulator/run_frames", {"frames": 30})
        await b.call("emulator/hold", {"buttons": dirs, "down": True})
        st = {"samples": 0, "hit": 0, "vs_moved": 0, "split": 0, "differ": 0, "first": []}
        for _ in range(legs_frames):
            await sample(b, s, shadow_len, st, leg)
        await b.call("emulator/hold", {"buttons": dirs, "down": False})
        out[leg] = st
    await b.close()
    return reg, wy, out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--frames", type=int, default=60, help="sampled ticks per leg")
    a = ap.parse_args(argv)
    try:
        if not (Path(a.rom).is_file() and Path(a.lst).is_file()):
            raise CouldNotRun(f"{a.rom} / {a.lst} missing")
        s, equs = parse_lst(a.lst)
        need = [nm for nm, _ in CAPTURE] + [
            "Parallax_Shadow_Bands", "Parallax_Shadow_Scroll_A", "Parallax_Shadow_Scroll_B",
            "Parallax_Shadow_Key_Config", "Parallax_Current_Config", "Parallax_Current_Vscroll_BG",
            "Parallax_Band_Sel", "Parallax_Band_Sel_Valid", "Parallax_Curve_Walk", "Parallax_State_End",
            "Current_Act_Ptr", "Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag"]
        miss = [n for n in need if n not in s]
        if miss:
            raise CouldNotRun(f"{a.lst} carries no {', '.join(miss)} (a DEBUG shape of a tree with "
                              f"Step 4a's key and the PPB-3/PPB-5 caches is required)")
        if "parallax_config_pcfg_anchor_ch" not in equs:
            raise CouldNotRun("the listing publishes no EQU parallax_config_pcfg_anchor_ch")
        rom = Path(a.rom).read_bytes()
        from aether_instance import aether_emulator
        with aether_emulator(a.rom, symbols=a.lst) as sock:
            reg, wy, out = asyncio.run(drive(sock, s, equs, rom, a.frames))
    except CouldNotRun as e:
        print(f"COULD NOT RUN: {e}")
        print("finished=1")
        return 2
    print(f"anchored region {reg['index']} x {reg['x0']}..{reg['x1']} y {reg['y0']}..{reg['y1']}, "
          f"world anchor {wy}")
    tot = {k: sum(v[k] for v in out.values()) for k in ("samples", "hit", "vs_moved", "split", "differ")}
    for leg, st in out.items():
        print(f"  {leg:13s} samples {st['samples']:4d}  hit {st['hit']:4d}  vs-moved {st['vs_moved']:4d}  "
              f"split {st['split']:4d}  DIFFER {st['differ']}")
    print(f"  {'total':13s} samples {tot['samples']:4d}  hit {tot['hit']:4d}  vs-moved {tot['vs_moved']:4d}  "
          f"split {tot['split']:4d}  DIFFER {tot['differ']}")
    for st in out.values():
        for f in st["first"]:
            print(f"  {f}")
    if tot["differ"]:
        print("VERDICT: RED — the cached shadow view is not the view a rebuild makes")
        print("finished=1")
        return 1
    empty = [k for k in ("hit", "vs_moved", "split") if tot[k] == 0]
    if empty:
        print(f"COULD NOT RUN: coverage class(es) {', '.join(empty)} at 0 — the legs never reached "
              f"the state that class exists to test, so a green would be vacuous")
        print("finished=1")
        return 2
    print("VERDICT: GREEN")
    print("finished=1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
