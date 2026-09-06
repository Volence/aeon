#!/usr/bin/env python3
"""bganim_vprobe_witness — does the vertical BgAnim band actually move VERTICALLY?

THE CLAIM THIS ANSWERS, AND THE TWO WEAKER ONES IT REFUSES TO SETTLE FOR
------------------------------------------------------------------------
Weak claim 1, "the bytes are in the ROM": a `grep` of the listing settles that, and it is
what every record of EFFECTS-W1 item 8 has been able to say until now.
Weak claim 2, "something in VRAM changes": a band on EITHER axis satisfies it, so a green
run would say nothing about the axis, which is the whole of the item.

What this asserts instead: the 256 bytes at the band's VRAM destination equal, byte for
byte, the image `BgAnim_Update` is REQUIRED to produce by the record sitting in the ROM —
and, decoded in the band's row-major slot order, that image is phase 0 of the art rolled
UP by exactly `step` pixels. The prediction is derived from the record the ROM carries
(driver / rate_shift / step_mask / col_shift / tile_count / vram_dest, read out of the ROM
image), not from anything this file believes about the band.

THE CONTROL, WHICH IS THE POINT
-------------------------------
`s4.debug.bin` carries TWO probe tables — `BgAnim_View_Vert` and `BgAnim_View_VertCtl` —
over the SAME art, the SAME driver, the SAME rate and the SAME destination, differing only
in the two fields that carry the axis (col_shift 6 vs 7, step_mask 31 vs 15). So this runs
BOTH and requires, per sampled step:

  vertical arm     VRAM == the VERTICAL prediction        (and the picture is a y-roll)
  horizontal arm   VRAM == the HORIZONTAL prediction      (the engine works there too)
  horizontal arm   VRAM != the VERTICAL prediction        ← THE NEGATIVE ARM

Without the third line a green vertical arm would be consistent with "any band anywhere
satisfies this predicate". The run FAILS if the negative arm ever passes the vertical
predicate at a sample where the two predictions differ — and it also fails, as
UNMEASURABLE rather than green, if the two predictions never differ across the samples it
took, because then the negative arm was never actually asked anything.

A THIRD ARM, THE INSTRUMENT'S OWN CONTROL
-----------------------------------------
Before either band is installed, the destination is read twice several frames apart and
required to be UNCHANGED, and required NOT to already match either prediction. The band
aims at the BG region's reserved run ($A800, slot 1344 — `band_reserve` in
games/sonic4/vram.toml), which no plane cell references and no other writer touches; this
arm is what turns that from a claim into a measurement, and it is what makes a later match
attributable to the band rather than to whatever was lying there.

WHAT THIS IS NOT
----------------
NOT a pixel capture. Nothing here looks at a rendered frame, and the band is deliberately
aimed at VRAM tiles no plane cell points at, so there is nothing on screen to look at. The
sentence this run supports is "the engine's vertical arm runs end to end into VRAM" — the
sentence it does NOT support is "a vertical band was seen on screen". Getting the second
needs plane cells in row-major order over the band's slots, which is an authoring change
to the act's document.

"NO PLANE CELL POINTS AT IT" IS A GATE, NOT CURRENT-ART LUCK (promoted from assertion to
measurement 2026-09-06, the aurora lane's finding, re-derived here). Arm 0 above measures
"no other WRITER touches the destination"; the REFERENCE half used to be asserted in this
paragraph and is now measured: all 4,096 layout words in `editor_bg_override.json` index
tiles 0..317, and `BG_STATIC_TILE_BUDGET` is `BG_TILE_CAPACITY - BG_BAND_RESERVE` = 400 -
80 = 320, which `tools/png_to_bg_override.py` REFUSES to exceed at import. So the band's
target is unreferenced because a build-time gate forbids referencing it, not because
today's art happens not to.

THE ONE THING STILL UNDERIVED, and it is NOT the roll's sign. `decode_rowmajor()` DEFINES
which slot is which picture row; that mapping is this file's convention, and "up" is a
statement in the frame it establishes. The sign itself IS under test: `is_yroll` compares
live VRAM against `banks[0]` AS IT SITS IN THE ROM at the FULL step including the fine
bits, so a generator whose banks rolled the other way would make the fine and coarse
halves fight and go red at every nonzero fine phase — see `bganim_vprobe_gen.bank()`,
whose docstring states exactly that coupling. *(This corrects a caveat this lane sent the
aurora lane on 2026-09-06 claiming the fine-phase sign was baked in and therefore
untested. It was drawn from that generator's one-line summary without reading the function
underneath it, which says the opposite.)*

Usage:  python3 tools/bganim_vprobe_witness.py s4.debug.bin s4.debug.lst
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient                       # noqa: E402
from aether_instance import aether_emulator, read_bytes  # noqa: E402
from raster_cost_probe import parse_lst            # noqa: E402

BOOT_FRAMES = 180

#: How many settled plateaux each arm is sampled at, and how many plateaux to skip
#: between samples. Both are chosen so the VERTICAL arm walks past every coarse rotation
#: position rather than sitting inside one: its period is 32 steps and it has 4 coarse
#: positions 8 steps apart, so a stride of 1 covers at most 2 of them over 12 samples
#: (measured — the first run of this file reported "2 of 4"). SAMPLES * STRIDE = 48 > 32
#: walks the whole period with a stride coprime to 8, which visits all four. The same
#: numbers give the 16-step horizontal control a full period too, so every one of its
#: coarse-1 steps — the ones where the two predictions differ and the negative arm is
#: actually asked something — gets sampled.
SAMPLES = 16
STRIDE = 3

TILE_BYTES = 32
BANKS = 8            # BGANIM_BANKS


# ───────────────────────────────── the record, read out of the ROM ─────────────

class Band:
    """One 44-byte BgAnim record plus the geometry its fields imply.

    Field order is engine/level/bg_anim.emp's `struct bganim_band`:
      u16 driver, u16 rate_shift, u16 step_mask, u16 col_shift, u16 tile_count,
      u16 vram_dest, then 8 x u32 bank pointers.
    """

    def __init__(self, rom: bytes, table_addr: int, name: str):
        self.name = name
        self.count = int.from_bytes(rom[table_addr:table_addr + 2], "big")
        r = table_addr + 2
        (self.driver, self.rate_shift, self.step_mask, self.col_shift,
         self.tile_count, self.vram_dest) = (
            int.from_bytes(rom[r + 2 * i:r + 2 * i + 2], "big") for i in range(6))
        self.bank_ptrs = [int.from_bytes(rom[r + 12 + 4 * i:r + 16 + 4 * i], "big")
                          for i in range(BANKS)]
        self.total_bytes = self.tile_count * TILE_BYTES
        self.unit_bytes = 1 << self.col_shift
        self.period_px = self.step_mask + 1
        # The band's tile grid, DERIVED from the two axis fields rather than assumed:
        # a vertical band rotates by whole ROWS of cols*32 B and repeats every rows*8 px.
        self.cols = self.unit_bytes // TILE_BYTES
        self.rows = self.period_px // 8
        self.banks = [rom[p:p + self.total_bytes] for p in self.bank_ptrs]

    def axis_is_vertical(self) -> bool:
        """True iff the record's own two fields multiply out the VERTICAL way."""
        return self.cols * self.rows * TILE_BYTES == self.total_bytes and \
            self.rows * self.unit_bytes == self.total_bytes

    def predict(self, step: int) -> bytes:
        """The 256 bytes BgAnim_Update must leave at `vram_dest` for this step.

        Derived from the proc, not from a table: it queues
            DMA1  src = bank + shift, dest = base,          len = total - shift
            DMA2  src = bank,         dest = base + len1,   len = shift
        with bank = banks[step & 7] and shift = (step >> 3) << col_shift, so
        VRAM[i] == bank[(i + shift) % total].
        """
        bank = self.banks[step & (BANKS - 1)]
        shift = ((step >> 3) << self.col_shift) % self.total_bytes
        return bank[shift:] + bank[:shift]

    def step_for(self, driver_value: int) -> int:
        return (driver_value >> self.rate_shift) & self.step_mask

    def summary(self) -> str:
        return (f"{self.name}: count={self.count} driver={self.driver} "
                f"rate_shift={self.rate_shift} step_mask={self.step_mask} "
                f"col_shift={self.col_shift} (unit {self.unit_bytes} B) "
                f"tile_count={self.tile_count} vram_dest=${self.vram_dest:04X} "
                f"-> {self.cols}x{self.rows} tiles, period {self.period_px} px, "
                f"{self.total_bytes // self.unit_bytes} coarse positions")


# ───────────────────────────────── picture decode ──────────────────────────────

def decode_rowmajor(buf: bytes, cols: int, rows: int) -> list[list[int]]:
    """The band's 4bpp picture, reading slots in ROW-MAJOR order (slot j = (j//cols, j%cols)).

    Row-major is what a VERTICAL band's slots must be in; decoding a horizontal band this
    way deliberately assembles a permutation of its real picture, which is exactly why the
    negative arm's picture is not a y-roll of phase 0.
    """
    img = [[0] * (cols * 8) for _ in range(rows * 8)]
    for j in range(cols * rows):
        tr, tc = j // cols, j % cols
        t = buf[j * TILE_BYTES:(j + 1) * TILE_BYTES]
        for dy in range(8):
            for k in range(4):
                b = t[dy * 4 + k]
                img[tr * 8 + dy][tc * 8 + k * 2] = b >> 4
                img[tr * 8 + dy][tc * 8 + k * 2 + 1] = b & 0xF
    return img


def roll_up(img: list[list[int]], k: int) -> list[list[int]]:
    h = len(img)
    return [img[(y + k) % h] for y in range(h)]


# ───────────────────────────────── the run ─────────────────────────────────────

async def read_u32(b, addr):
    return int(await read_bytes(b, addr, 4), 16)


async def read_u16(b, addr):
    return int(await read_bytes(b, addr, 2), 16)


async def read_vram(b, addr, n):
    r = await b.call("emulator/read_vram", {"addr": hex(addr), "len": n})
    raw = r["bytes"]
    raw = raw[2:] if raw[:2].lower() == "0x" else raw
    got = bytes.fromhex(raw)
    if len(got) != n:
        raise RuntimeError(f"read_vram({addr:#x}, {n}) returned {len(got)} B")
    return got


async def install(b, sym, table_addr):
    """Point the walk at `table_addr` and poison the per-band step state.

    The poison is not optional and is not this file's invention: BgAnim_LastStep is keyed
    by band INDEX, not band identity, so two tables' band 0 share one state word and a
    switch between tables sitting on the same step would take `.skip_band` forever and
    never repaint. BgAnim_SetTable does exactly this (moveq #-1 into both longs); doing it
    by hand here keeps the measurement off the input path.
    """
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["BgAnim_Table_Ptr"]), "value": table_addr, "width": 4})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["BgAnim_LastStep"]), "bytes": "0x" + "FF" * 8})


async def sample_at_plateau(b, sym, band, max_frames=90):
    """Advance to the MIDDLE of a step plateau and return (tick, committed_step, vram).

    `rate_shift` makes each step last `1 << rate_shift` ticks. Sampling mid-plateau rather
    than at its edge is what keeps this off the DMA's own settling window: BgAnim_Update
    queues DEFERRABLE entries that drain in the following VInt, and the per-entry VBlank
    budget may split the pair across two frames (the proc's own PAIR-ATOMICITY note). A
    sample taken at the instant the step changes could therefore legitimately read a
    half-updated band, and calling that a failure would be measuring the queue, not the
    axis.
    """
    plateau = 1 << band.rate_shift
    want_lo, want_hi = plateau // 2, plateau - 1
    for _ in range(max_frames):
        tick = (await read_u32(b, sym["Logic_Tick"])) & 0xFFFF
        phase = tick & (plateau - 1)
        committed = await read_u16(b, sym["BgAnim_LastStep"])
        if want_lo <= phase <= want_hi and committed == band.step_for(tick):
            return tick, committed, await read_vram(b, band.vram_dest, band.total_bytes)
        await b.call("emulator/run_frames", {"frames": 1})
    raise RuntimeError(f"never reached a settled plateau for {band.name} within "
                       f"{max_frames} frames (last tick {tick}, committed {committed})")


async def run(sock, lst, rom):
    b = BusClient(socket_path=sock, client_id="vprobe", client_name="bganim_vprobe_witness")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})
    sym = parse_lst(lst)
    for need in ("BgAnim_Table_Ptr", "BgAnim_LastStep", "Logic_Tick",
                 "BgAnim_View_Vert", "BgAnim_View_VertCtl"):
        if need not in sym:
            return 1, [f"UNMEASURABLE: {lst} has no symbol `{need}` — this is not the "
                       f"DEBUG shape, or the probe did not build into it"]

    vert = Band(rom, sym["BgAnim_View_Vert"], "vertical")
    horz = Band(rom, sym["BgAnim_View_VertCtl"], "horizontal control")
    print(vert.summary())
    print(horz.summary())
    fails = []

    if not vert.axis_is_vertical():
        fails.append("the `vertical` record's own fields do not multiply out the vertical "
                     "way (rows * unit_bytes != tile_count * 32)")
    if (vert.vram_dest, vert.tile_count, vert.bank_ptrs) != \
       (horz.vram_dest, horz.tile_count, horz.bank_ptrs):
        fails.append("the two arms are NOT a matched pair — they differ in more than the "
                     "two axis fields, so the control does not isolate the axis")
    if (vert.col_shift, vert.step_mask) == (horz.col_shift, horz.step_mask):
        fails.append("the two arms carry IDENTICAL axis fields — there is no control here")
    if fails:
        return 1, fails

    await b.call("emulator/reset", {})
    await b.call("emulator/run_frames", {"frames": BOOT_FRAMES})
    if "Debug_Scene_Freeze" in sym:
        # A section crossing calls BgAnim_Init, which would re-point the walk at the act's
        # own (empty) table mid-run and read as a dead band.
        await b.call("emulator/write_memory",
                     {"addr": hex(sym["Debug_Scene_Freeze"]), "value": 1, "width": 1})
        await b.call("emulator/run_frames", {"frames": 2})

    # ── arm 0: the destination is untouched, and does not already look like the answer ──
    before = await read_vram(b, vert.vram_dest, vert.total_bytes)
    await b.call("emulator/run_frames", {"frames": 20})
    before2 = await read_vram(b, vert.vram_dest, vert.total_bytes)
    print(f"\narm 0 (instrument control) — ${vert.vram_dest:04X}, {vert.total_bytes} B, "
          f"nothing installed:")
    if before != before2:
        fails.append("arm 0: the band's destination CHANGED with no band installed — "
                     "something else writes this VRAM run and every later match is "
                     "confounded")
    else:
        print(f"  unchanged across 20 frames (first 8 B {before[:8].hex()}) — no other "
              f"writer")
    pre_hits = sum(1 for s in range(vert.step_mask + 1) if before == vert.predict(s))
    if pre_hits:
        fails.append(f"arm 0: the untouched destination ALREADY matches {pre_hits} of the "
                     f"vertical predictions — a later match would not be attributable")
    else:
        print(f"  matches none of the {vert.step_mask + 1} vertical predictions before "
              f"install")

    # ── arms V and H ──
    rows = []
    for band, other in ((vert, horz), (horz, vert)):
        await install(b, sym, sym["BgAnim_View_Vert" if band is vert
                                  else "BgAnim_View_VertCtl"])
        await b.call("emulator/run_frames", {"frames": 4})
        print(f"\narm `{band.name}` — {SAMPLES} settled plateaux:")
        for _ in range(SAMPLES):
            tick, step, got = await sample_at_plateau(b, sym, band)
            own = got == band.predict(step)
            v_step = vert.step_for(tick)
            h_step = horz.step_for(tick)
            v_pred = vert.predict(v_step)
            h_pred = horz.predict(h_step)
            cross = got == (h_pred if band is vert else v_pred)
            distinguishable = v_pred != h_pred
            # the human-legible form of the vertical claim
            img = decode_rowmajor(got, vert.cols, vert.rows)
            phase0 = decode_rowmajor(vert.banks[0], vert.cols, vert.rows)
            is_yroll = img == roll_up(phase0, v_step)
            rows.append(dict(arm=band.name, tick=tick, step=step, own=own, cross=cross,
                             distinguishable=distinguishable, is_yroll=is_yroll,
                             v_step=v_step))
            print(f"  tick {tick:5d}  step {step:2d}  own-prediction "
                  f"{'MATCH ' if own else 'differ'}  other-axis prediction "
                  f"{'MATCH ' if cross else 'differ'}  "
                  f"picture is a {v_step}px y-roll of phase 0: {'YES' if is_yroll else 'no'}"
                  f"{'' if distinguishable else '   [predictions COINCIDE here]'}")
            # step off this plateau so the next sample is a different step; STRIDE
            # plateaux rather than one, so the walk covers the period (see STRIDE)
            await b.call("emulator/run_frames",
                         {"frames": STRIDE << band.rate_shift})

    # ── verdict ──
    v = [r for r in rows if r["arm"] == "vertical"]
    h = [r for r in rows if r["arm"] == "horizontal control"]

    bad = [r for r in v if not r["own"]]
    if bad:
        fails.append(f"vertical arm: {len(bad)} of {len(v)} samples did not match the "
                     f"record's own prediction (steps {[r['step'] for r in bad]})")
    bad = [r for r in v if not r["is_yroll"]]
    if bad:
        fails.append(f"vertical arm: {len(bad)} of {len(v)} samples are not a y-roll of "
                     f"phase 0 (steps {[r['step'] for r in bad]})")
    bad = [r for r in h if not r["own"]]
    if bad:
        fails.append(f"horizontal control: {len(bad)} of {len(h)} samples did not match "
                     f"its OWN prediction — the control is broken, not the subject "
                     f"(steps {[r['step'] for r in bad]})")

    # THE NEGATIVE ARM. Only samples where the two predictions actually differ can
    # discriminate; a sample where they coincide is not evidence either way.
    usable = [r for r in h if r["distinguishable"]]
    if not usable:
        fails.append("UNMEASURABLE: at every sampled step the vertical and horizontal "
                     "predictions COINCIDED, so the negative arm was never asked "
                     "anything — a green vertical arm here would mean nothing")
    else:
        leaked = [r for r in usable if r["cross"] or r["is_yroll"]]
        if leaked:
            fails.append(f"NEGATIVE ARM PASSED: {len(leaked)} of {len(usable)} "
                         f"discriminating samples on the horizontal control also "
                         f"satisfied the VERTICAL predicate — the predicate does not "
                         f"discriminate the axis and the vertical arm proves nothing")
        else:
            print(f"\nnegative arm: {len(usable)} of {len(h)} horizontal-control samples "
                  f"were discriminating, and the vertical predicate FAILED on all "
                  f"{len(usable)} — as it must")

    # Every coarse position, not merely more than one: the coarse rotate is the half of
    # the mechanism the axis actually lives in (the fine half is a bank index and is the
    # same instruction on either axis), and its positions are a small enumerable set. A
    # sampler that stopped covering them would be reporting on the fine phase alone.
    coarse = {r["step"] >> 3 for r in v}
    want_coarse = vert.total_bytes // vert.unit_bytes
    if len(coarse) < want_coarse:
        fails.append(f"UNMEASURABLE: the vertical arm's samples exercised "
                     f"{len(coarse)} of {want_coarse} coarse rotation positions "
                     f"({sorted(coarse)}) — the two-piece wrapped DMA, which is where an "
                     f"axis mistake shows, was not fully exercised")
    else:
        print(f"coarse coverage: the vertical arm's samples hit all {want_coarse} coarse "
              f"rotation positions {sorted(coarse)}")

    return (1, fails) if fails else (0, [])


def main():
    if len(sys.argv) != 3:
        print(__doc__.strip().splitlines()[-1])
        return 2
    rom_path, lst = sys.argv[1], sys.argv[2]
    rom = Path(rom_path).read_bytes()
    with aether_emulator(rom_path, symbols=lst) as sock:
        rc, fails = asyncio.run(run(sock, lst, rom))
    if rc == 0:
        print("\nRESULT: PASS — the band at the vertical record's destination holds, at "
              "every sampled step, exactly the image that record requires, and that image "
              "is phase 0 rolled UP by the step. The same art under a HORIZONTAL record "
              "fails that predicate. (A VRAM measurement, not a pixel capture.)")
    else:
        print(f"\nRESULT: FAIL — {len(fails)} finding(s):")
        for f in fails:
            print(f"  - {f}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
