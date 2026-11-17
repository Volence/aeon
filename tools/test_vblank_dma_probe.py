"""Tests for tools/vblank_dma_probe.py (v2 B3: per-DMA VBlank-end probe).

Pure lane: site discovery on synthetic listing+ROM pairs, the line arithmetic, the
calibration / overrun / "last DMA, not rte" rules, and the probe's break handling on a fake
bus. One test reads the real `s4.debug.lst` + `s4.debug.bin` and is `needs_build`."""
import asyncio
from pathlib import Path

import pytest

import leg_correction as lc
import vblank_dma_probe as vp

AEON = Path(__file__).resolve().parent.parent
FRAME = 262 * lc.MCLK_PER_LINE

# 68000 encodings of the drain's moves (MOVE = 00 size dreg dmode smode sreg):
ML1, MW1 = 0x2A99, 0x3A99      # move.l / move.w (a1)+,(a5)
ML0, MW0 = 0x2A98, 0x3A98      # move.l / move.w (a0)+,(a5)
NOP = 0x4E71


def _w(*words):
    return b"".join(w.to_bytes(2, "big") for w in words)


def synth(n_groups=3):
    """A tiny ROM + listing: Process_DMA_Critical at $100 with `n_groups` drain groups
    (labels .drain_k, k = n..1), then a move.w #imm,(abs).w, .done, rts; Drain_Budgeted_Queue
    at $200 with one group inside a loop; Next_Proc at $240."""
    rom = bytearray(0x300)
    labels = [("Process_DMA_Critical", 0x100)]
    a = 0x100
    rom[a:a + 4] = _w(NOP, NOP)
    a += 4
    for k in range(n_groups, 0, -1):
        labels.append((f"$engine.dma_queue$Process_DMA_Critical$drain_{k}", a))
        rom[a:a + 8] = _w(ML1, ML1, ML1, MW1)
        a += 8
    rom[a:a + 6] = _w(0x31FC, 0x1234, 0x5678)      # move.w #$1234,($5678).w
    a += 6
    labels.append(("$engine.dma_queue$Process_DMA_Critical$done", a))
    rom[a:a + 2] = _w(0x4E75)
    labels.append(("Drain_Budgeted_Queue", 0x200))
    labels.append(("$engine.dma_queue$Drain_Budgeted_Queue$loop", 0x208))
    rom[0x200:0x220] = _w(NOP, NOP, NOP, NOP, NOP, NOP, ML0, ML0, ML0, MW0, NOP, NOP,
                          0x4E75, NOP, NOP, NOP)
    labels.append(("Next_Proc", 0x240))
    lst = "\n".join(f"(0) {i}/{addr:X} :        {name}:" for i, (name, addr) in
                    enumerate(labels)) + "\n"
    syms = {name: addr for name, addr in labels}
    return lst, syms, bytes(rom)


# ---- sites --------------------------------------------------------------------------------

def test_synthetic_sites_are_the_last_command_word_of_each_group():
    lst, syms, rom = synth(3)
    sites = vp.dma_trigger_sites(lst, syms, rom)
    crit = [syms[f"$engine.dma_queue$Process_DMA_Critical$drain_{k}"] + 6 for k in (3, 2, 1)]
    assert sites == sorted(crit + [0x200 + 9 * 2])


def test_no_sites_is_unmeasurable():
    lst, syms, rom = synth(3)
    cut = "\n".join(ln for ln in lst.splitlines()
                    if "Process_DMA_Critical" not in ln and "Drain_Budgeted_Queue" not in ln)
    with pytest.raises(vp.NoTriggerSites):
        vp.dma_trigger_sites(cut, syms, rom)


def test_one_drain_body_without_sites_is_unmeasurable():
    """Both bodies must contribute: a Drain_Budgeted_Queue whose group is gone is refused,
    never a probe that silently watches only half the drains."""
    lst, syms, rom = synth(3)
    rom = bytearray(rom)
    rom[0x200:0x220] = _w(*([NOP] * 16))
    with pytest.raises(vp.NoTriggerSites, match="Drain_Budgeted_Queue"):
        vp.dma_trigger_sites(lst, syms, bytes(rom))


def test_drain_label_without_its_group_is_unmeasurable():
    lst, syms, rom = synth(3)
    rom = bytearray(rom)
    a = syms["$engine.dma_queue$Process_DMA_Critical$drain_2"]
    rom[a + 6:a + 8] = _w(NOP)
    with pytest.raises(vp.NoTriggerSites, match="drain_2"):
        vp.dma_trigger_sites(lst, syms, bytes(rom))


def test_listing_symbol_disagreement_is_unmeasurable():
    lst, syms, rom = synth(3)
    with pytest.raises(vp.NoTriggerSites, match="Process_DMA_Critical"):
        vp.dma_trigger_sites(lst, dict(syms, Process_DMA_Critical=0x104), rom)


def prod(syms):
    """The production symbol dict shape: `leg_drive.parse_listing` keeps no `$` locals."""
    return {k: v for k, v in syms.items() if not k.startswith("$")}


def test_anchors_bind_with_a_production_symbol_dict():
    lst, syms, rom = synth(3)
    assert not any(k.startswith("$") for k in prod(syms))
    assert vp.dma_trigger_sites(lst, prod(syms), rom) == vp.dma_trigger_sites(lst, syms, rom)


@pytest.mark.parametrize("word", [0, 6], ids=["first-move.l", "the-move.w"])
def test_changed_drain_group_shape_is_refused_with_production_symbols(word):
    """A partial change of shape in ONE drain group must be refused (unmeasurable), never a
    probe that silently watches fewer DMAs (Review Focus 4)."""
    lst, syms, rom = synth(3)
    rom = bytearray(rom)
    a = syms["$engine.dma_queue$Process_DMA_Critical$drain_2"]
    rom[a + word:a + word + 2] = _w(NOP)
    with pytest.raises(vp.NoTriggerSites, match=r"drain_2.*label \+ 6"):
        vp.dma_trigger_sites(lst, prod(syms), bytes(rom))


def test_drain_label_count_must_equal_the_slots_equate():
    lst, syms, rom = synth(3)
    with pytest.raises(vp.NoTriggerSites, match="DMA_CRITICAL_SLOTS 4"):
        vp.dma_trigger_sites(lst + "EQU DMA_CRITICAL_SLOTS = $00000004\n", prod(syms), rom)
    assert vp.dma_trigger_sites(lst + "EQU DMA_CRITICAL_SLOTS = $00000003\n", prod(syms), rom)


def test_unlabelled_group_in_critical_is_refused():
    """A group the scan finds with no drain_k label is refused: the Critical sites are exactly
    the anchored ones. Build it by moving the labels 8 bytes up past an extra leading group."""
    lst, syms, rom = synth(3)
    rom = bytearray(rom)
    rom[0x104:0x10C] = _w(ML1, ML1, ML1, MW1)            # the unlabelled group
    rom[0x10C:0x124] = _w(*([ML1, ML1, ML1, MW1] * 3))   # drain_3..drain_1, shifted by 8
    rom[0x124:0x12A] = _w(0x31FC, 0x1234, 0x5678)
    rom[0x12A:0x12C] = _w(0x4E75)
    moved = []
    for i, ln in enumerate(lst.splitlines()):
        m = vp._LABEL.match(ln.strip())
        name, a = m.group(3), int(m.group(2), 16)
        moved.append(f"(0) {i}/{a + 8 if 'Process_DMA_Critical$' in name else a:X} :        "
                     f"{name}:")
    with pytest.raises(vp.NoTriggerSites, match="carry no drain_k label"):
        vp.dma_trigger_sites("\n".join(moved) + "\n", prod(syms), bytes(rom))


def test_budgeted_queue_must_have_exactly_one_group():
    lst, syms, rom = synth(3)
    rom = bytearray(rom)
    rom[0x220:0x228] = _w(ML0, ML0, ML0, MW0)
    with pytest.raises(vp.NoTriggerSites, match="exactly one group"):
        vp.dma_trigger_sites(lst, prod(syms), bytes(rom))


def test_budgeted_queue_needs_its_loop_label():
    lst, syms, rom = synth(3)
    cut = "\n".join(ln for ln in lst.splitlines() if "$Drain_Budgeted_Queue$loop" not in ln)
    with pytest.raises(vp.NoTriggerSites, match=r"\$loop"):
        vp.dma_trigger_sites(cut, prod(syms), rom)


@pytest.mark.needs_build("s4.debug.bin", "s4.debug.lst")
def test_sites_found_in_both_drain_bodies():
    import leg_drive as ld
    lst_p = AEON / "s4.debug.lst"
    text = lst_p.read_text(errors="replace")
    addr, _equ, _dbg = ld.parse_listing(lst_p)
    sites = vp.dma_trigger_sites(text, addr, (AEON / "s4.debug.bin").read_bytes())
    assert sites
    bounds = vp.proc_bounds(text)
    ranges = [bounds[p] for p in vp.DRAIN_PROCS]
    assert all(any(lo <= s < hi for lo, hi in ranges) for s in sites)
    lo, hi = bounds["Process_DMA_Critical"]
    groups = sum(1 for ln in text.splitlines()
                 if "$Process_DMA_Critical$drain_" in ln and ln.startswith("("))
    assert groups >= 1
    assert sum(1 for s in sites if lo <= s < hi) >= groups
    blo, bhi = bounds["Drain_Budgeted_Queue"]
    assert sum(1 for s in sites if blo <= s < bhi) == 1
    # Production dict (no locals), exact counts: one site per Critical slot, from the equate.
    assert not any(k.startswith("$") for k in addr)
    assert sum(1 for s in sites if lo <= s < hi) == groups == _equ["DMA_CRITICAL_SLOTS"]


# ---- line arithmetic ----------------------------------------------------------------------

def test_line_of():
    assert vp.line_of(257 * 3420 + 2097) == (257, 2097)
    assert vp.line_of(5 * FRAME + 224 * 3420 + 395) == (224, 395)
    assert vp.FRAME_MCLK == 896_040


def ev(end_line, end_off, tick=1, vblank=0, site=0x100, start=(243, 0)):
    return vp.DmaEvent(tick=tick, vblank=vblank, site=site, start_line=start[0],
                       start_off=start[1], end_line=end_line, end_off=end_off)


def test_overrun_flagged_past_limit():
    L = lc.DMA_END_LIMIT_LINE
    assert L == 260
    assert vp.overruns([ev(L, 1)]) == [ev(L, 1)]
    assert vp.overruns([ev(L, 0)]) == []
    assert vp.overruns([ev(L - 3, 3000), ev(L + 1, 0)]) == [ev(L + 1, 0)]


def test_vblank_end_is_last_event_not_rte():
    """The VBlank's end is the latest DMA END among its events -- not the handler's rte, and
    not the last event in hit order (a short DMA issued last can end before a long one)."""
    a, b, c = ev(250, 100), ev(257, 2097), ev(255, 0)
    assert vp.vblank_end([a, b, c]) == b
    assert vp.vblank_end([]) is None


# ---- the probe on a fake bus --------------------------------------------------------------

class FakeBus:
    def __init__(self, step_cost=0):
        self.step_cost = step_cost
        self.now = 0
        self.bps = []
        self.calls = []
        self.calls_site = 0x106

    async def call(self, method, params):
        self.calls.append((method, params))
        if method == "emulator/breakpoint_add":
            self.bps.append(params)
            return {"breakpoint": f"b{len(self.bps)}"}
        if method == "emulator/breakpoint_clear":
            return {}
        if method == "emulator/step":
            self.now += self.step_cost
            return {"mclk": self.now, "stepped": 1, "pc": hex(self.calls_site + 2)}
        raise AssertionError(method)


def mk_probe(sites=(0x106, 0x212), entry_line=224):
    return vp.DmaProbe(list(sites), vblank_addr=0x247E, lag_addr=0x2600, entry_line=entry_line)


def at(line, off, frame=10):
    return frame * FRAME + line * 3420 + off


def test_probe_records_events_with_step_end():
    async def go():
        bus, p = FakeBus(step_cost=3420 * 10 + 7), mk_probe()
        await p.arm(bus)
        assert {b.get("addr") or b.get("symbol") for b in bus.bps} >= {hex(0x106), hex(0x212)}
        p.tick = 42
        assert await p.on_break(bus, 0x247E, {"mclk": at(224, 395)})
        bus.now = at(243, 100)
        assert await p.on_break(bus, 0x106, {"mclk": bus.now})
        assert not await p.on_break(bus, 0x9999, {"mclk": bus.now})
        return p
    p = asyncio.run(go())
    assert p.unmeasurable is None
    assert p.events == [vp.DmaEvent(tick=42, vblank=0, site=0x106, start_line=243,
                                    start_off=100, end_line=253, end_off=107)]
    r = p.result()
    assert r["unmeasurable"] is None and r["worst_end"] == {"line": 253, "off": 107, "tick": 42, "vblank": 0,
                                                     "site": 0x106, "status": "MEASURED"}
    assert r["overruns"] == [] and r["vblanks"][0]["entry_line"] == 224


def test_entry_line_mismatch_is_unmeasurable():
    async def go():
        bus, p = FakeBus(), mk_probe()
        await p.arm(bus)
        await p.on_break(bus, 0x247E, {"mclk": at(224, 300)})
        await p.on_break(bus, 0x247E, {"mclk": at(223, 3000, frame=11)})
        return p
    p = asyncio.run(go())
    assert p.unmeasurable and "223" in p.unmeasurable
    r = p.result()
    assert r["unmeasurable"] and r["worst_end"] is None


def test_empty_sites_is_unmeasurable_never_no_dma():
    async def go():
        bus, p = FakeBus(), mk_probe(sites=())
        await p.arm(bus)
        await p.on_break(bus, 0x247E, {"mclk": at(224, 300)})
        return p
    r = asyncio.run(go()).result()
    assert r["unmeasurable"] and "site" in r["unmeasurable"]
    assert r["worst_end"] is None


def test_no_vblank_seen_is_unmeasurable():
    async def go():
        bus, p = FakeBus(), mk_probe()
        await p.arm(bus)
        return p
    r = asyncio.run(go()).result()
    assert r["unmeasurable"] and "VBlank" in r["unmeasurable"]


def test_vblank_without_dma_is_a_result_not_unmeasurable():
    """A calibrated VBlank with no DMA is recorded as such (events 0), distinct from a probe
    that cannot see."""
    async def go():
        bus, p = FakeBus(), mk_probe()
        await p.arm(bus)
        await p.on_break(bus, 0x247E, {"mclk": at(224, 300)})
        return p
    r = asyncio.run(go()).result()
    assert r["unmeasurable"] is None
    assert r["vblanks"][0]["events"] == 0 and r["worst_end"]["line"] is None
    assert r["worst_end"]["status"] == "NO DMA"


def test_site_hit_outside_a_vblank_is_unmeasurable():
    async def go():
        bus, p = FakeBus(), mk_probe()
        await p.arm(bus)
        await p.on_break(bus, 0x106, {"mclk": at(100, 0)})
        return p
    r = asyncio.run(go()).result()
    assert r["unmeasurable"] and "outside" in r["unmeasurable"]


def test_lag_vblank_is_marked():
    async def go():
        bus, p = FakeBus(), mk_probe()
        await p.arm(bus)
        await p.on_break(bus, 0x247E, {"mclk": at(224, 300)})
        await p.on_break(bus, 0x2600, {"mclk": at(224, 900)})
        await p.on_break(bus, 0x247E, {"mclk": at(224, 300, frame=11)})
        return p
    r = asyncio.run(go()).result()
    assert [v["lag"] for v in r["vblanks"]] == [True, False]


def test_end_past_the_frame_is_not_wrapped():
    """A DMA that runs into the next frame must read as line >= 262, never wrap to line 0."""
    async def go():
        bus, p = FakeBus(step_cost=30 * 3420), mk_probe()
        await p.arm(bus)
        await p.on_break(bus, 0x247E, {"mclk": at(224, 300)})
        bus.now = at(250, 0)
        await p.on_break(bus, 0x106, {"mclk": bus.now})
        return p
    p = asyncio.run(go())
    assert p.events[0].end_line == 280 and vp.overruns(p.events) == p.events
