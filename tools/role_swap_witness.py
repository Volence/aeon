#!/usr/bin/env python3
"""role_swap_witness — does EFFECTS-W1 item 10b's plane-role swap reach the SCREEN?

`tools/plane_role_swap_gate.py` proves the code is in the image on every canonical build.
The item-10b booking then tags the rest as owed, in the standing form: "No emulator was
used (standing invariant). What to look for..." This runs it.

THE SUBJECT. `Parallax_Roles_Swapped` is a RAM flag. With it set, `Parallax_Update`
reasserts BOTH plane base registers trading places — reg $02 takes Plane B's byte and reg
$04 takes Plane A's — and packs the scroll feeds in the swapped order, so the background
art presents through the foreground's priority slot and vice versa. It is settled whole-
frame state, not a mid-frame raster op: item 11a's door does not fit a multi-frame set
piece, which is why the two items look adjacent and are built differently.

THREE ARMS, AND THE THIRD IS THE ONE THAT SEPARATES A SWAP FROM A CORRUPTION.

  1. NO DRIFT. With the scene frozen, capture the picture twice with the same number of
     frames between them. They must be identical, or the picture is animating and no
     later comparison means anything. This is the arm that makes the rest attributable,
     and it is cheaper here than spawning twin instances because the flag is reversible
     inside one machine.

  2. THE MECHANISM, READ AT THE SHADOW. `Flush_VDP_Shadow` walks the shadow table into
     the VDP at frame top on both the VInt and lag paths, so the shadow IS what the VDP
     gets. Expectations are DERIVED, not copied: reg $02 carries `VRAM_PLANE_x >> 10` and
     reg $04 carries `VRAM_PLANE_x >> 13`, both shifts read out of `engine/vdp.emp`'s own
     `vdp_base_shift` match arms rather than typed in. Unswapped, $02 must name Plane A
     and $04 Plane B; swapped, each must name the other's plane. A witness that only
     watched pixels could not tell a role trade from any other whole-frame change.

  3. REVERSIBILITY. Clear the flag and the picture must return BYTE-IDENTICALLY to the
     unswapped capture. This is what says the swap is settled state rather than
     accumulating damage: corruption does not un-corrupt when you clear a flag, and a
     one-way change that merely looked like a swap would fail here. It is also the arm
     the booking's own step 3 describes ("write 0 back... the next Parallax_Update
     reasserts the normal registers and pack order") and nobody had run.

WHAT THIS DOES NOT ESTABLISH, and it is the same boundary item 11a's witness draws:
  * It does not say the swapped picture LOOKS like a clean role trade — that each layer
    keeps its own scroll behaviour and neither reads as a seam or a snap. That is the
    booking's failure mode (b), it is taste plus scroll judgement, and it wants the
    owner's eye on a moving picture. This witness can only say the registers traded, the
    picture changed, and it went back.
  * It samples the composed frame and cannot attribute a row to a layer.
"""
import argparse
import asyncio
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient  # noqa: E402
from aether_instance import aether_emulator  # noqa: E402
from raster_cost_probe import parse_lst  # noqa: E402
from base_swap_witness import read_const  # noqa: E402

SCREEN_LINES = 224
SETTLE = 400
STEP = 8          # frames allowed for a reassert to take effect and the picture to settle
BASELINE = 6      # baseline captures; 3 missed a slow band edge (line 65) on the first run


def base_shift(vdp_emp, plane):
    src = Path(vdp_emp).read_text()
    m = re.search(r"fn\s+vdp_base_shift.*?\{(.*?)\n\}", src, re.S)
    if not m:
        raise SystemExit("%s: could not find vdp_base_shift" % vdp_emp)
    arm = re.search(r"%s\s*=>\s*(\d+)" % plane, m.group(1))
    if not arm:
        raise SystemExit("%s: vdp_base_shift has no %s arm" % (vdp_emp, plane))
    return int(arm.group(1))


def bus24(a):
    return a & 0xFFFFFF


async def rows(b):
    out = []
    got = 0
    while got < SCREEN_LINES:
        n = min(16, SCREEN_LINES - got)
        r = await b.call("emulator/scanlines", {"startLine": got, "count": n})
        if r.get("source") != "raster":
            raise SystemExit(
                "VOID: emulator/scanlines answered source=%r, not 'raster'. A stateRender "
                "capture reports end-of-frame state and would look clean whatever the "
                "planes did." % r.get("source"))
        for row in (r.get("rows") or r.get("lines")):
            t = row["rgb"] if isinstance(row, dict) else str(row)
            out.append(hashlib.md5(t.encode()).hexdigest()[:10])
        got += n
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    a = ap.parse_args()

    rom, lst, root = Path(a.rom), Path(a.lst), Path(a.root)
    for p in (rom, lst):
        if not p.is_file():
            raise SystemExit("missing %s" % p)

    plane_a = read_const(root / "engine/system/constants.emp", "VRAM_PLANE_A")
    plane_b = read_const(root / "engine/system/constants.emp", "VRAM_PLANE_B")
    sh_a = base_shift(root / "engine/vdp.emp", "PlaneA")
    sh_b = base_shift(root / "engine/vdp.emp", "PlaneB")

    # reg $02 presents whichever plane it names, at PlaneA's granule; reg $04 likewise at
    # PlaneB's. Unswapped each names its own plane; swapped they trade. Four bytes, all
    # folded here the way the engine folds them.
    r02_normal, r02_swapped = plane_a >> sh_a, plane_b >> sh_a
    r04_normal, r04_swapped = plane_b >> sh_b, plane_a >> sh_b

    sym = parse_lst(str(lst))
    need = ("Parallax_Roles_Swapped", "VDP_Shadow_Table", "Debug_Scene_Freeze")
    for n in need:
        if n not in sym:
            raise SystemExit("%s carries no symbol %s" % (lst, n))

    print("DERIVED FROM THE TREE — the four register bytes, folded not typed")
    print("  VRAM_PLANE_A $%04X   VRAM_PLANE_B $%04X" % (plane_a, plane_b))
    print("  PlaneA shift %d, PlaneB shift %d   (engine/vdp.emp vdp_base_shift)" % (sh_a, sh_b))
    print("  reg $02   normal $%02X -> swapped $%02X" % (r02_normal, r02_swapped))
    print("  reg $04   normal $%02X -> swapped $%02X" % (r04_normal, r04_swapped))
    print("  flag      Parallax_Roles_Swapped at $%08X" % sym["Parallax_Roles_Swapped"])
    print()
    if r02_normal == r02_swapped or r04_normal == r04_swapped:
        raise SystemExit(
            "NOTHING TO MEASURE: a register's normal and swapped bytes are equal, so a swap "
            "would be invisible by construction. The two planes must fold to different bytes "
            "in BOTH registers for item 10b to be demonstrable.")

    with aether_emulator(rom, symbols=lst) as sock:
        async def go():
            b = BusClient(socket_path=sock, client_id="rsw", client_name="role_swap_witness")
            await b.connect()

            async def regs():
                out = []
                for off in (0x02, 0x04):
                    v = (await b.call("emulator/read_memory",
                                      {"addr": "0x%08X" % bus24(sym["VDP_Shadow_Table"] + off),
                                       "len": 1}))["bytes"]
                    out.append(int(v, 16))
                return out

            async def flag(v):
                await b.call("emulator/write_memory",
                             {"addr": "0x%08X" % bus24(sym["Parallax_Roles_Swapped"]),
                              "value": v, "width": 1})
                await b.call("emulator/run_frames", {"frames": STEP})

            done = 0
            while done < SETTLE:
                n = min(100, SETTLE - done)
                await b.call("emulator/run_frames", {"frames": n})
                done += n
            await b.call("emulator/write_memory",
                         {"addr": "0x%08X" % bus24(sym["Debug_Scene_Freeze"]),
                          "value": 1, "width": 1})
            await b.call("emulator/run_frames", {"frames": STEP})

            # THE BASELINE IS THREE CAPTURES, NOT TWO. Debug_Scene_Freeze stops the scene
            # cycling; it does not stop everything the act animates, and two captures
            # cannot tell a row that drifts from a row that happened to differ once.
            base = []
            for _ in range(BASELINE):
                base.append(await rows(b))
                await b.call("emulator/run_frames", {"frames": STEP})
            r_off = await regs()
            await flag(1)
            p1 = await rows(b)
            r_on = await regs()
            await flag(0)
            p2 = await rows(b)
            r_back = await regs()
            return base, p1, p2, r_off, r_on, r_back

        base, p1, p2, r_off, r_on, r_back = asyncio.run(go())
        p0 = base[0]

    fails = []

    # THE DRIFT SET — the act's own animation, measured rather than assumed away. Rows that
    # move on their own cannot testify about the flag in EITHER direction, so they are
    # excluded from arm 3 and their size is reported. This is the ramp witness's lesson
    # arriving on a time axis: a control is only a control where it does nothing.
    drift = sorted({i for i in range(SCREEN_LINES)
                    for c in base[1:] if base[0][i] != c[i]})
    stable = [i for i in range(SCREEN_LINES) if i not in set(drift)]

    print("ARM 1  THE ACT'S OWN DRIFT — which rows cannot testify?")
    print("  %d of %d rows move on their own across %d captures %d frames apart"
          % (len(drift), SCREEN_LINES, BASELINE, STEP))
    if drift:
        runs, s = [], drift[0]
        for x, y in zip(drift, drift[1:] + [None]):
            if y != x + 1:
                runs.append((s, x))
                s = y
        print("  drifting bands: %s" % ", ".join("%d-%d" % r if r[0] != r[1] else "%d" % r[0]
                                                 for r in runs))
    print("  %d stable rows carry arm 3." % len(stable))
    if len(stable) < SCREEN_LINES // 2:
        raise SystemExit(
            "ARM 1 FAILED: only %d of %d rows are stable, so a majority of the picture is "
            "animating and arm 3 would be measuring the act rather than the flag. Freeze "
            "more, or sample at a fixed animation phase — do not report this run."
            % (len(stable), SCREEN_LINES))
    print()

    print("ARM 2  THE MECHANISM AT THE VDP SHADOW")
    print("  flag 0   reg $02 $%02X   reg $04 $%02X   (expected $%02X / $%02X)"
          % (r_off[0], r_off[1], r02_normal, r04_normal))
    print("  flag 1   reg $02 $%02X   reg $04 $%02X   (expected $%02X / $%02X)"
          % (r_on[0], r_on[1], r02_swapped, r04_swapped))
    print("  flag 0   reg $02 $%02X   reg $04 $%02X   (expected $%02X / $%02X)"
          % (r_back[0], r_back[1], r02_normal, r04_normal))
    for tag, got, want in (("unswapped", r_off, (r02_normal, r04_normal)),
                           ("swapped", r_on, (r02_swapped, r04_swapped)),
                           ("restored", r_back, (r02_normal, r04_normal))):
        if tuple(got) != want:
            fails.append(
                "%s: the shadow holds reg $02 $%02X / reg $04 $%02X, derived expectation is "
                "$%02X / $%02X. Flush_VDP_Shadow walks this table into the VDP every frame, "
                "so this is what the planes are actually being pointed at."
                % (tag, got[0], got[1], want[0], want[1]))
    print()

    print("ARM 3  THE PICTURE, AND WHETHER IT COMES BACK  (stable rows only)")
    changed = [i for i in stable if p1[i] != p0[i]]
    residue = [i for i in stable if p2[i] != p0[i]]
    print("  rows changed by the swap        %d of %d stable" % (len(changed), len(stable)))
    if changed:
        runs, s = [], changed[0]
        for x, y in zip(changed, changed[1:] + [None]):
            if y != x + 1:
                runs.append((s, x))
                s = y
        print("    bands: %s" % ", ".join("%d-%d" % r if r[0] != r[1] else "%d" % r[0]
                                          for r in runs))
    print("  rows still changed after clear  %d of %d stable  (must be 0)"
          % (len(residue), len(stable)))
    if residue:
        print("    rows: %s" % residue[:20])
    if not changed:
        fails.append(
            "the swap changed NO row. The registers may have traded while the picture did "
            "not, which would mean the two planes are drawing indistinguishable content in "
            "this scene — a scene problem, not necessarily a mechanism one, but it is not a "
            "witness of the effect either. Report it rather than passing.")
    if residue:
        fails.append(
            "%d row(s) did NOT come back after the flag was cleared (first at line %d). The "
            "swap is supposed to be settled whole-frame state that Parallax_Update reasserts "
            "both ways; state that does not reverse is accumulating, which is the shape of "
            "corruption rather than of a role trade." % (len(residue), residue[0]))
    print()

    if fails:
        print("FAILED")
        for f in fails:
            print("  * %s" % f)
        return 1
    print("PASSED — both base registers trade to the bytes the plane constants fold to, the")
    print("picture changes with them, and clearing the flag restores it byte-identically.")
    print("The swap is settled, reversible whole-frame state. Whether it READS as a clean")
    print("role trade — each layer keeping its own scroll feel — is taste, and still owed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
