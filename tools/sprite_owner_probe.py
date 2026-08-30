#!/usr/bin/env python3
"""Witness that `Sprite_Owner` names the object behind each hardware sprite.

WHY THIS EXISTS SEPARATELY FROM `tools/test_sprite_owner.py`. That file pins the SOURCE
— that the stamp is spliced in the right place, that the bound is derived, that the block
is DEBUG-only. Every one of its pins would still pass if the emitted code stamped the
wrong index at runtime, because it never runs the ROM. This is the other half: it boots
the DEBUG ROM, plays frames, and reads what the engine actually wrote.

Three claims, none of which the source pins can reach:

  A. No stamped slot below `Sprites_Rendered` reads $0000. A $0000 in range means a SAT
     writer exists that nobody stamps — defect 1 of the design booking, which the
     VRAM-vs-buffer proof provably CANNOT catch (the SAT stays correct; only the
     ownership array skews).
  B. The sentinels appear: rings stamp $0001, masks stamp $0002.
  C. Every non-sentinel owner is a plausible SST address — inside the object RAM span and
     even. A cursor that desynchronised would still produce nonzero values here, so this
     is deliberately the WEAKEST of the three and is reported as such.

WHAT THE ROM ACTUALLY BOOTS, measured 2026-08-27, and the reason the witness is thin.
`s4.debug.bin` does not boot into player-controlled gameplay: holding `right` pans the
CAMERA (96 -> 2912 -> 5680 -> 5824 over three 180-frame holds) while the player SST does
not move at all. It is a scroll test. Consequence: the busiest frame this probe can reach
carries THREE sprites — one object and two rings — so claim C ever examines a single
non-sentinel owner, and the MASK sentinel is never exercised at all. That is a fact about
the content, not a failure of the feature, and it is why MIN_WITNESS_SPRITES exists rather
than a bare pass/fail. When the game boots something busier, re-run this unchanged and the
same claims start being worth something.

WHAT THIS PROBE CANNOT DO, stated because a green run reads stronger than it is: it
cannot confirm that slot i names the object DRAWING at slot i's screen position. That
needs a per-object position cross-check against the SAT entry's own X/Y, which is a
larger instrument. A owns the "did anyone forget to stamp" question; it does not own
"is the stamp correct". Do not report a pass here as the feature being verified end to
end.

Run:  python3 tools/sprite_owner_probe.py [--rom s4.debug.bin] [--lst s4.debug.lst]
Exit: 0 all claims held · 1 a claim failed · 2 could not run (setup/spawn)
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Same seam aether_instance uses; the client lives in the contract repo, not here.
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import add_client_path  # noqa: E402
add_client_path()  # the Aether client, resolved from the suite root; loud if absent

from aether import BusClient                                    # noqa: E402
from aether_instance import AetherInstance, SpawnError, read_bytes, WrongServerError  # noqa: E402

AEON = Path(__file__).resolve().parent.parent

# Derived, never typed: the bound comes from the constant the engine itself uses, so a
# moved ceiling moves this probe with it rather than leaving it measuring a stale span.
CONSTANTS = AEON / "engine/system/constants.emp"

SAT_ENTRY_BYTES = 8          # Y, size, link, tile-attrs, X — the VDP's own SAT stride
OWNER_ENTRY_BYTES = 2        # u16 per entry

OWNER_NONE, OWNER_RING, OWNER_MASK = 0x0000, 0x0001, 0x0002

# Object RAM span, read from the listing rather than assumed.
SST_SPAN_SYMBOLS = ("Object_RAM", "Object_RAM_End")

# SAMPLE AT SEVERAL POINTS, ASSERT AT EVERY ONE. A single frame is a thin witness: the
# first run of this probe caught 3 sprites, of which 2 were rings, leaving exactly ONE
# non-sentinel owner to check. Claims A and C are near-vacuous at that width, and a
# one-frame sample cannot see a cursor that only desynchronises once a second object
# enters. 180 frames is the tree-wide boot settle (warp_mailbox_gate's constant, which
# presses no buttons). The later samples buy nothing TODAY — see the boot-state note above —
# and are kept because they cost seconds and will matter the moment the scene grows.
SAMPLE_FRAMES = (180, 300, 600, 900)
MIN_WITNESS_SPRITES = 4      # below this the run reports THIN rather than OK


def max_vdp_sprites() -> int:
    m = re.search(r"^pub const MAX_VDP_SPRITES\s*=\s*(\d+)", CONSTANTS.read_text(), re.M)
    if not m:
        raise SystemExit(f"could not read MAX_VDP_SPRITES from {CONSTANTS}")
    return int(m.group(1))


def lst_symbols(path: Path, wanted: set[str]) -> dict[str, int]:
    """Pull symbol addresses out of a sigil listing's symbol table.

    Matches the ` Name : ADDR C |` form, which is the table rather than the inline
    listing — the inline form repeats and would give a last-wins answer.
    """
    out: dict[str, int] = {}
    pat = re.compile(r"^\s*(\w+)\s*:\s*([0-9A-Fa-f]{8})\s+\w\s*\|")
    for line in path.read_text(errors="replace").splitlines():
        m = pat.match(line)
        if m and m.group(1) in wanted:
            out[m.group(1)] = int(m.group(2), 16) & 0xFFFFFF
    return out


async def probe(sock: str, sym: dict[str, int], n_max: int) -> tuple[int, list[str]]:
    b = BusClient(socket_path=sock, client_id="sprite-owner-probe",
                  client_name="sprite_owner_probe")
    notes: list[str] = []
    failures: list[str] = []
    await b.connect()
    try:
        await b.call("emulator/reset", {})           # NO params - the core refuses extras

        lo, hi = sym.get("Object_RAM"), sym.get("Object_RAM_End")
        widest = 0
        total_rings = total_masks = 0
        elapsed = 0

        for target in SAMPLE_FRAMES:
            await b.call("emulator/run_frames", {"frames": target - elapsed})
            elapsed = target

            rendered = int(await read_bytes(b, sym["Sprites_Rendered"], 2), 16)
            if rendered > n_max:
                failures.append(f"f{target}: Sprites_Rendered={rendered} exceeds "
                                f"MAX_VDP_SPRITES={n_max}")
                continue
            widest = max(widest, rendered)

            owners_hex = await read_bytes(b, sym["Sprite_Owner"], n_max * OWNER_ENTRY_BYTES)
            owners = [int(owners_hex[i * 4:(i + 1) * 4], 16) for i in range(n_max)]

            # A: nothing in range is unstamped.
            blanks = [i for i in range(rendered) if owners[i] == OWNER_NONE]
            if blanks:
                failures.append(
                    f"f{target}: claim A FAILED - {len(blanks)} slot(s) below "
                    f"Sprites_Rendered={rendered} read $0000 (first index {blanks[0]}); "
                    f"a SAT writer exists that nothing stamps")

            # B: sentinels.
            rings = sum(1 for i in range(rendered) if owners[i] == OWNER_RING)
            masks = sum(1 for i in range(rendered) if owners[i] == OWNER_MASK)
            total_rings += rings
            total_masks += masks

            # C (weakest): non-sentinels look like even SST addresses.
            if lo is not None and hi is not None:
                bad = [(i, owners[i]) for i in range(rendered)
                       if owners[i] not in (OWNER_NONE, OWNER_RING, OWNER_MASK)
                       and not (lo <= (0xFF0000 | owners[i]) <= hi and owners[i] % 2 == 0)]
                if bad:
                    failures.append(
                        f"f{target}: claim C FAILED - {len(bad)} owner word(s) neither a "
                        f"sentinel nor an even SST address in "
                        f"[{lo:#08x},{hi:#08x}]; first {bad[0]}")

            # The whole-array clear: nothing stale above the bound.
            tail = [i for i in range(rendered, n_max) if owners[i] != OWNER_NONE]
            if tail:
                failures.append(
                    f"f{target}: clear FAILED - {len(tail)} slot(s) at/above "
                    f"Sprites_Rendered={rendered} are non-zero (first index {tail[0]}); a "
                    f"stale valid address can survive into a later frame")

            nonsent = rendered - rings - masks
            notes.append(f"f{target}: rendered={rendered} "
                         f"(objects={nonsent}, rings={rings}, masks={masks})")

        # WIDTH IS PART OF THE VERDICT, not a footnote. A green run over 3 sprites has
        # checked almost nothing, and reporting it as OK is the vacuous-gate shape this
        # whole parcel exists to avoid.
        if widest < MIN_WITNESS_SPRITES:
            failures.append(
                f"THIN: the widest frame sampled carried {widest} sprite(s), below the "
                f"{MIN_WITNESS_SPRITES} this probe treats as a real witness. The claims "
                f"above did not fail - they had almost nothing to check. Reach a busier "
                f"state before reading this as verification.")
        else:
            notes.append(f"witness width: {widest} sprites at the busiest sample")

        if total_rings == 0 and total_masks == 0:
            notes.append("claim B INCONCLUSIVE across every sample: no ring or mask sprite "
                         "was ever on screen, so neither sentinel path was exercised")
        else:
            notes.append(f"claim B: sentinels seen (ring stamps {total_rings}, "
                         f"mask stamps {total_masks}, summed over samples)")

        if not failures:
            notes.append("claims A and C held at every sample; clear held at every sample")
        return (1 if failures else 0), notes + failures
    finally:
        await b.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default=str(AEON / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    args = ap.parse_args()

    lst = Path(args.lst)
    if not lst.is_file():
        print(f"sprite_owner_probe: no listing at {lst}", file=sys.stderr)
        return 2

    n_max = max_vdp_sprites()
    wanted = {"Sprite_Owner", "Sprites_Rendered", "Sprite_Table_Buffer", *SST_SPAN_SYMBOLS}
    sym = lst_symbols(lst, wanted)
    missing = {"Sprite_Owner", "Sprites_Rendered"} - sym.keys()
    if missing:
        # Refuse rather than measure zeros: Sprite_Owner is absent from a RELEASE listing
        # BY DESIGN, so this is the likeliest way to point the probe at the wrong ROM.
        print(f"sprite_owner_probe: {sorted(missing)} not in {lst.name}. This is a DEBUG-only "
              f"feature - point --rom/--lst at the DEBUG shape.", file=sys.stderr)
        return 2

    print(f"sprite_owner_probe: MAX_VDP_SPRITES={n_max} (derived from constants.emp), "
          f"Sprite_Owner={sym['Sprite_Owner']:#08x}")
    inst = AetherInstance(rom=args.rom, symbols=str(lst))
    try:
        sock = inst.start()
    except (SpawnError, WrongServerError) as e:
        print(f"sprite_owner_probe: {e}", file=sys.stderr)
        return 2
    try:
        rc, lines = asyncio.run(probe(sock, sym, n_max))
    finally:
        inst.reap()

    for line in lines:
        print(f"  {line}")
    print(f"sprite_owner_probe: {'OK' if rc == 0 else 'FAILED'}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
