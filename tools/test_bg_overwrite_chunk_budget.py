"""BG_OVERWRITE_CHUNK_BYTES — the region bg switch's per-frame upload chunk — is DERIVED, and
this test is where the derivation lives (plan docs/superpowers/plans/2026-09-16-region-bg-
switch.md, call C3; controller ruling 2026-09-16 on what the chunk must guarantee).

THE RULE IS LIVENESS. `Drain_Budgeted_Queue` (engine/system/dma_queue.emp) is strictly FIFO and
stops at the first entry that does not fit. A chunk at the head of the Deferrable queue therefore
DELAYS the Deferrable entries behind it, and that delay is the Deferrable contract ("budget-gated,
can slip one frame", engine/objects/dplc.emp, Perform_DPLC_Deferrable). What the chunk must
guarantee is that it fits on ANY frame where it is the only Deferrable entry, or it could starve
forever. So:

  chunk <= DMA_BUDGET_NTSC
           - FG plane-drain peak       (engine/level/bg.emp FG_PEAK_BYTES; the BG streamer and
                                        wipe are suspended while chunks are queued)
           - Critical peak             (BuildStaticDMA's 4 palette lines + SAT + HScroll, read by
                                        tools/dma_defer_headroom.py's own reader)
           - a full-CRAM raster ship   (64 colours x 2 B; Critical, unbudgeted)
           - the Important queue's player-art peak (the duo cast dplc_straddle reserves for:
                                        Sonic + Tails + Tails' appendage, or Knuckles if larger)

and the committed value is the LARGEST whole-tile (32 B) multiple that fits.

DELIBERATELY NOT CHARGED, each for a reason:
  * the other Deferrable producers — insta-shield and spindash-dust DPLC, waterline art. They may
    slip behind a chunk; GATE BG-SWITCH leg TRAFFIC measures that slip. Charging them gave 256 B,
    rejected by the ruling above.
  * act art page landings on the Important queue — the priority plan call C1 chose; a heavy
    streaming frame delays the chunk, it does not overrun anything.

If the bound cannot hold one tile the test fails loudly: a budget the design cannot meet.
"""
import re
from pathlib import Path

import dma_defer_headroom as H
import dplc_straddle as DS

REPO = Path(__file__).resolve().parent.parent
BG = REPO / "engine/level/bg.emp"


def _emp_const(path: Path, name: str) -> int:
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*([^/\n]+)", path.read_text(),
                  re.M)
    assert m, f"{path.relative_to(REPO)} no longer declares `const {name}`"
    expr = m.group(1).strip()
    for ident in sorted(set(re.findall(r"[A-Za-z_]\w*", expr)), key=len, reverse=True):
        try:
            v = H._const(ident)
        except H.Unmeasurable:
            v = _emp_const(path, ident)
        expr = re.sub(rf"\b{ident}\b", str(v), expr)
    assert re.fullmatch(r"[\d\s+\-*/()]+", expr), f"{name} = {expr!r} is not arithmetic"
    return int(eval(expr, {"__builtins__": {}}, {}))            # noqa: S307 -- gated above


def _dplc_peak_bytes(emp_rel: str, const: str) -> int:
    text = (REPO / emp_rel).read_text()
    m = re.search(rf"^const\s+{re.escape(const)}\s*=\s*embed\(\"([^\"]+)\"\)", text, re.M)
    assert m, f"{emp_rel} no longer embeds `{const}`"
    frames = DS.parse_dplc((REPO / m.group(1)).read_bytes(), m.group(1))
    return max(sum(c for _, c in f) for f in frames) * H._const("TILE_SIZE")


def _derive():
    crit = H.static_critical_lengths()
    critical = crit["palette_line"] * crit["palette_lines"] + crit["sat"] + crit["hscroll"]
    ship = 64 * 2                                                # a raster ship cannot exceed CRAM
    fg_peak = _emp_const(BG, "FG_PEAK_BYTES")
    duo = (_dplc_peak_bytes("games/sonic4/data/collision/collision_data.emp", "_dplc_sonic")
           + _dplc_peak_bytes("games/sonic4/data/characters/tails_data.emp", "_dplc_tails")
           + _dplc_peak_bytes("games/sonic4/data/characters/tails_data.emp", "_dplc_tail"))
    knux = _dplc_peak_bytes("games/sonic4/data/characters/knuckles_data.emp", "_dplc_knux")
    important = max(duo, knux)
    budget = H._const("DMA_BUDGET_NTSC")
    residual = budget - fg_peak - critical - ship - important
    parts = dict(budget=budget, fg_peak=fg_peak, critical=critical, ship=ship,
                 important=important,
                 residual=residual)
    return parts


def test_overwrite_chunk_is_the_largest_whole_tile_multiple_that_fits_when_it_is_the_only_deferrable_entry():
    p = _derive()
    tile = H._const("TILE_SIZE")
    assert p["residual"] >= tile, (
        f"the NTSC window's worst frame leaves {p['residual']} B for a BG overwrite chunk, less "
        f"than one tile: {p}. The switch cannot be guaranteed to progress on a worst frame; this "
        f"is a design-level budget failure, not a constant to lower")
    want = (p["residual"] // tile) * tile
    got = _emp_const(BG, "BG_OVERWRITE_CHUNK_BYTES")
    assert got == want, (
        f"engine/level/bg.emp BG_OVERWRITE_CHUNK_BYTES is {got}; the derivation gives {want} "
        f"(residual {p['residual']} B = {p})")


def test_critical_peak_in_bg_emp_matches_build_static_dma():
    crit = H.static_critical_lengths()
    want = crit["palette_line"] * crit["palette_lines"] + crit["sat"] + crit["hscroll"] + 64 * 2
    assert _emp_const(BG, "BG_CRITICAL_PEAK_BYTES") == want
