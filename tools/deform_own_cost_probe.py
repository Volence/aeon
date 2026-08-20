#!/usr/bin/env python3
"""deform_own_cost_probe — the per-band deform-table reload, measured on a build that has it.

P3 Task 9's model parameter. `deform: own(..)` moves the two curve pointers from a
once-per-fill hoist of the CONFIG's tables to a per-BAND load out of the band's extension
record (engine/level/parallax.emp, the `cap_multi_deform_table_band` bracket). That load is
the whole runtime cost of CAP_MULTI_DEFORM_TABLE and it is what this probe measures.

WHY THIS IS A SEPARATE TOOL AND NOT A FIXTURE ROW IN parallax_cost_probe
------------------------------------------------------------------------
The path does not exist in any canonical image. sonic4 declares SCANLINE_CAPS $001F and no
shipped scene authors `own()` (adoption is PARK-1, owner-gated), so BAND_EXT_N is 0, the
band record is the legacy 10 bytes and the gated block is elided. Everything here therefore
runs against a LOCAL, NON-CANONICAL INSTRUMENT BUILD, and mixing those rows into the fitted
walker model — whose every coefficient is pinned to the shipped walker — would poison it.
The recipe for the instrument builds is in docs/benchmarks/scanline-p3/DEFORM-OWN.md; this
tool refuses to run against a build whose record is not extended, so a canonical ROM cannot
be measured here by accident.

THE FIXTURE MACHINERY IS parallax_cost_probe's, IMPORTED, NOT RE-TYPED. `_one()` (the
Debug_Scene_Freeze + Replay_Record_Buf installer, the preemption-free window retry, the four
derived checks) and `row()` are its; only the RECORD BUILDER is new, because a band is 20
bytes here and carries two table pointers the legacy builder has no field for. `BE_SIZE` is
DERIVED from the build under measurement — `Parallax_Shadow_Scroll_A - Parallax_Shadow_Bands`
over MAX_PARALLAX_BANDS, which is the same span engine/level/parallax.emp pins the record
against — and pushed into that module, so nothing here types a stride.

WHAT THE TWO ARMS MEASURE
-------------------------
  --arm shared-vs-own   THE PLAN'S NAMED FIXTURE: N layers sharing one table against N
                        layers each with their own, on ONE build. PREDICTED ZERO before it
                        was run, and the prediction is the point: the lowering resolves
                        inheritance at comptime, so both shapes execute the SAME two
                        `movea.l`s per band and differ only in the values loaded. A non-zero
                        residual here would mean the load had become data-dependent.
  --arm per-band        THE PARAMETER: the per-band slope, from band counts 1/2/3 with FG
                        sampling live in every band (so the 224 sampled lines are constant
                        and the slope isolates per-band work). Run it on BOTH instrument
                        builds — I1 with the gated block, I0 with the block commented out
                        and NOTHING else changed — and the DIFFERENCE of the two slopes is
                        the two `movea.l`s, isolated. Both builds carry the extended record,
                        so Step 4a's wider copy and the wider stride are held FIXED across
                        the pair instead of being confounded into it.

Usage:
    python3 tools/deform_own_cost_probe.py --rom s4.i1.bin --lst s4.i1.lst --arm per-band
    python3 tools/deform_own_cost_probe.py --rom s4.i1.bin --lst s4.i1.lst --arm shared-vs-own
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

HARNESS = "/home/volence/sonic_hacks/oracle-old/linux-port/harness"
sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, HARNESS)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aether import BusClient            # noqa: E402
from launcher import headless_emulator  # noqa: E402
import parallax_cost_probe as pcp       # noqa: E402
from raster_cost_probe import parse_lst  # noqa: E402

# The extension's own layout (engine/level/parallax.emp, band_ext). Offsets FROM THE
# EXTENSION, added to the legacy prefix length, which is itself derived below.
BX_TABLE_A = 0    # *u8
BX_TABLE_B = 4    # *u8
BX_SPEED_A = 8    # u8
BX_SPEED_B = 9    # u8
BX_SIZE    = 10

LEGACY_BE_SIZE = 10   # sizeof(band_entry) — the prefix, which never grows (design §3.1)

# Six curves ship; three are enough for a three-band own() fixture. Any three distinct ROM
# tables would do — the loop's cost is data-independent (asr/add/move), which is itself part
# of what the shared-vs-own arm checks.
OWN_TABLES = ("DeformTable_Zero", "DeformTable_Shimmer", "DeformTable_Haze")


def ext_band(top: int, table_a: int, table_b: int = 0,
             dsa: int = 3, dsb: int = pcp.NO_DEFORM,
             speed_a: int = 1, speed_b: int = 1, stride: int = 20) -> bytes:
    """One EXTENDED band record: the legacy prefix, then band_ext.

    The prefix comes from parallax_cost_probe.band() rather than being re-typed, so the
    factor encoding and the shift sentinels are that tool's and stay in step with it.
    """
    # TRUNCATED TO THE PREFIX ON PURPOSE. `pcp.band()` sizes its buffer from that module's
    # `BE_SIZE`, which this tool has already re-pointed at the BUILD's record stride (20) so
    # the imported installer's shadow-slot poison covers a whole record. Every field band()
    # writes lives in the first nine bytes, so the first ten ARE the legacy prefix whatever
    # the buffer length is — and the extension is appended here, where its layout is known.
    b = bytearray(pcp.band(top, dsa, dsb))[:LEGACY_BE_SIZE]
    assert len(b) == LEGACY_BE_SIZE, f"legacy prefix is {len(b)}, expected {LEGACY_BE_SIZE}"
    ext = bytearray(BX_SIZE)
    ext[BX_TABLE_A:BX_TABLE_A + 4] = table_a.to_bytes(4, "big")
    ext[BX_TABLE_B:BX_TABLE_B + 4] = table_b.to_bytes(4, "big")
    ext[BX_SPEED_A] = speed_a
    ext[BX_SPEED_B] = speed_b
    out = bytes(b) + bytes(ext)
    assert len(out) == stride, f"record is {len(out)}, but the build's stride is {stride}"
    return out


def build_ext(base: bytes, *, bands: int, tables: list[int], head_tab_fg: int,
              stride: int) -> bytes:
    """The shipped header with one thing changed, plus `bands` EXTENDED band records.

    THE HEADER TABLE WORD IS STILL LOAD-BEARING UNDER THE CAPABILITY, and it is the one
    thing about this shape a reader will get wrong: the fill loop takes its curves from the
    BAND now, but `parallax_mode_key` — the runtime per-line/per-cell decision — still ORs
    the config's two HEADER table words and cannot see the bands. A fixture with null
    header tables would run the PER-CELL filler and measure nothing. (This is exactly why
    `scene()` refuses an own() scene that attaches no plane-shared table.)
    """
    h = bytearray(base[:pcp.CFG_SIZE])
    h[pcp.CFG_BAND_COUNT] = bands
    h[pcp.CFG_V_FACTOR_BG] = pcp.NO_DEFORM      # locked: Step 5 pins BG, as every W fixture
    h[pcp.CFG_LAYER_MASK] = 0xFF
    h[pcp.CFG_TRANSITION] = 0
    h[pcp.CFG_DEFORM_SPEED_FG] = 0
    h[pcp.CFG_DEFORM_SPEED_BG] = 0
    h[pcp.CFG_ANCHOR_CH] = pcp.ANCHOR_NONE
    h[pcp.CFG_ANCHOR_DSA] = pcp.NO_DEFORM
    h[pcp.CFG_ANCHOR_DSB] = pcp.NO_DEFORM
    h[pcp.CFG_V_DEFORM_SHIFT] = 3
    for off, val in ((pcp.CFG_DEFORM_TAB_FG, head_tab_fg),
                     (pcp.CFG_DEFORM_TAB_BG, 0),
                     (pcp.CFG_V_DEFORM_TAB_BG, 0)):
        h[off:off + 4] = val.to_bytes(4, "big")
    tops = pcp.band_tops(bands)
    body = b"".join(ext_band(t, tables[i], stride=stride) for i, t in enumerate(tops))
    return bytes(h) + body


def fixtures(base: bytes, sym: dict, stride: int, arm: str) -> dict:
    zero = sym["DeformTable_Zero"]
    own = [sym[n] for n in OWN_TABLES]
    fx: dict = {}
    for n in (1, 2, 3):
        fx[f"S{n}"] = {
            "what": f"{n} band(s), per-line, FG sampling live, EVERY band pointing at "
                    f"DeformTable_Zero — N layers SHARING one table",
            "vary": "band count" if n > 1 else "-",
            "cfg": build_ext(base, bands=n, tables=[zero] * n, head_tab_fg=zero,
                             stride=stride)}
    if arm == "shared-vs-own":
        for n in (1, 2, 3):
            fx[f"O{n}"] = {
                "what": f"{n} band(s), per-line, FG sampling live, each band pointing at a "
                        f"DIFFERENT curve — N layers each with their OWN table",
                "vary": f"table identity vs S{n} (nothing else)",
                "cfg": build_ext(base, bands=n, tables=own[:n], head_tab_fg=zero,
                                 stride=stride)}
    return fx


def scan_bracket(lst: Path) -> tuple[int | None, int | None]:
    """The gated block's two boundary labels, scanned OUT OF THE LISTING TEXT.

    `parse_lst` DELIBERATELY DROPS `$`-MANGLED NAMES (raster_cost_probe.py:492) and the
    §3.3 bracket labels are proc-locals, so they are all `$`-mangled — this is the same
    flat-`.lst` limitation that made raster_source_gate hand-roll its own resolver. Scanned
    here rather than worked around, because whether the block is present is EXACTLY what
    distinguishes the I1 build from its I0 control, and reporting the wrong answer would
    silently relabel which half of the measurement a run belongs to.
    """
    a = b = None
    for line in lst.read_text(errors="replace").splitlines():
        if not line.startswith("(0) "):
            continue
        try:
            addrpart, namepart = line[4:].split(" :", 1)
            addr = int(addrpart.split("/", 1)[1], 16) & 0xFFFFFF
        except (ValueError, IndexError):
            continue
        name = namepart.strip().rstrip(":")
        if name.endswith("$cap_multi_deform_table_band_begin") and a is None:
            a = addr
        elif name.endswith("$cap_multi_deform_table_band_end") and b is None:
            b = addr
    return a, b


def derive_stride(sym: dict) -> int:
    """The record stride, READ OFF THE BUILD — never typed, never inferred from a flag.

    `Parallax_Shadow_Bands` reserves one record per MAX_PARALLAX_BANDS and the next symbol
    starts immediately after it; engine/level/parallax.emp pins that span to
    `sizeof(band_record) * MAX_PARALLAX_BANDS` on every build, so this is the same number
    the walker's own displacement arithmetic used.
    """
    span = sym["Parallax_Shadow_Scroll_A"] - sym["Parallax_Shadow_Bands"]
    if span % pcp.MAX_SHADOW:
        sys.exit(f"shadow span {span} is not a multiple of MAX_PARALLAX_BANDS "
                 f"({pcp.MAX_SHADOW}) — the symbols moved, or this .lst is not this ROM's")
    return span // pcp.MAX_SHADOW


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--arm", choices=("per-band", "shared-vs-own"), default="per-band")
    ap.add_argument("--settle", type=int, default=180)
    ap.add_argument("--sample", type=int, default=31)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    if not Path(args.rom).exists():
        sys.exit(f"ROM not found: {args.rom}")
    sym = parse_lst(Path(args.lst))

    stride = derive_stride(sym)
    if stride == LEGACY_BE_SIZE:
        sys.exit(f"REFUSED: {args.rom} has a {stride}-byte band record, i.e. the LEGACY "
                 f"shape. This probe measures the per-band table reload, which only exists "
                 f"in a build that declares CAP_MULTI_DEFORM_TABLE (BAND_EXT_N 1, "
                 f"BAND_EXT_BYTES 10). See docs/benchmarks/scanline-p3/DEFORM-OWN.md for "
                 f"the instrument-build recipe. Refusing rather than measuring the wrong "
                 f"path and reporting a number.")
    if stride != LEGACY_BE_SIZE + BX_SIZE:
        sys.exit(f"REFUSED: band record is {stride} bytes, expected "
                 f"{LEGACY_BE_SIZE + BX_SIZE} (legacy prefix + one band_ext). The record "
                 f"grew by something this probe does not know how to fill.")
    # Push the derived stride into the imported installer: its shadow-slot poison writes and
    # reads exactly one record, and a 10-byte poison in a 20-byte world would leave half the
    # slot un-poisoned and the two-sided witness half-blind.
    pcp.BE_SIZE = stride

    rom = Path(args.rom).read_bytes()
    base = rom[sym["ParallaxConfig_OJZ_Default"]:
               sym["ParallaxConfig_OJZ_Default"] + pcp.CFG_SIZE]
    FX = fixtures(base, sym, stride, args.arm)
    results: dict[str, list[dict]] = {k: [] for k in FX}

    async def _sweep(sock: str) -> None:
        b = BusClient(socket_path=sock, client_id="dfownprobe",
                      client_name="deform_own_cost_probe")
        await b.connect()
        await b.call("emulator/load_symbols", {"path": args.lst})
        for k, fx in FX.items():
            results[k].append(await pcp._one(b, sym, fx["cfg"], args.settle, args.sample))
        await b.close()

    for _ in range(args.repeat):
        with headless_emulator(args.rom) as sock:
            asyncio.run(_sweep(sock))

    blk_a, blk_b = scan_bracket(Path(args.lst))
    has_block = blk_a is not None and blk_b is not None
    print(f"ROM {args.rom}   arm {args.arm}   stride {stride} B (DERIVED)   "
          f"sample {args.sample}   repeats {args.repeat}")
    print(f"gated block present in this build: {has_block}"
          + (f"   ({blk_b - blk_a} bytes at ${blk_a:06X})" if has_block
             else "   (control build — block removed)"))
    print("response = Parallax_Update's per-routine row, INCLUSIVE of its callees.\n")
    hdr = f"{'FIX':4} {'bands':>5} {'Px_Update':>10} {'spread':>7} {'Fill_PerLine':>12}  checks"
    print(hdr)
    print("-" * len(hdr))
    table: dict[str, dict] = {}
    failures: list[str] = []
    for k, fx in FX.items():
        runs = results[k]
        rows = [pcp.row(r["prof"], sym["Parallax_Update"]) for r in runs]
        if any(x is None for x in rows):
            print(f"{k:4} -- NO Parallax_Update ROW (fixture did not install?)")
            failures.append(f"{k}: no Parallax_Update row")
            continue
        checks = []
        for reason, key in (("config pointer moved off the fixture", "ptr_ok"),
                            ("fixture bytes were overwritten", "bytes_ok"),
                            ("the replay recorder woke up", "replay_idle"),
                            ("the window was not preemption-free", "preempt_free")):
            if not all(r[key] for r in runs):
                checks.append(key)
                failures.append(f"{k}: {reason}")
        cyc = [int(x["cycles"]) for x in rows]
        pl = pcp.row(runs[0]["prof"], sym["Parallax_Fill_PerLine"])
        pc = pcp.row(runs[0]["prof"], sym["Parallax_Fill_PerCell"])
        # THE MODE IS A DERIVED CHECK, NOT A COMMENT. A fixture that fell through to the
        # per-cell filler would still print a plausible Parallax_Update row while measuring
        # a path with no band table load in it at all.
        if pc is not None and pl is None:
            failures.append(f"{k}: ran the PER-CELL filler — the header table word is null "
                            f"or the mode key changed; this row is not evidence")
        n = fx["cfg"][pcp.CFG_BAND_COUNT]
        print(f"{k:4} {n:>5} {cyc[0]:>10} {max(cyc) - min(cyc):>7} "
              f"{(pl['cycles'] if pl else 0):>12}  {'ok' if not checks else '!! ' + ','.join(checks)}")
        table[k] = {"cycles": cyc, "bands": n, "what": fx["what"], "vary": fx["vary"],
                    "fill_per_line": pl["cycles"] if pl else 0}

    def slope(prefix: str) -> float | None:
        pts = [(table[f"{prefix}{n}"]["bands"], table[f"{prefix}{n}"]["cycles"][0])
               for n in (1, 2, 3) if f"{prefix}{n}" in table]
        if len(pts) < 2:
            return None
        # Least squares over the three points; with band count constant-spaced this is the
        # mean marginal, and reporting the two marginals beside it is what shows linearity.
        n = len(pts)
        mx = sum(p[0] for p in pts) / n
        my = sum(p[1] for p in pts) / n
        num = sum((p[0] - mx) * (p[1] - my) for p in pts)
        den = sum((p[0] - mx) ** 2 for p in pts)
        return num / den if den else None

    print()
    s_shared = slope("S")
    if s_shared is not None:
        m = [table[f"S{n+1}"]["cycles"][0] - table[f"S{n}"]["cycles"][0] for n in (1, 2)
             if f"S{n+1}" in table and f"S{n}" in table]
        print(f"PER-BAND SLOPE (shared arm): {s_shared:.2f} cyc/band   "
              f"marginals {m}   [linearity: the two marginals should agree]")
    if args.arm == "shared-vs-own":
        s_own = slope("O")
        print(f"PER-BAND SLOPE (own arm):    {s_own:.2f} cyc/band" if s_own is not None else "")
        print("\nSHARED vs OWN, per band count — the plan's named fixture pair.")
        print("PREDICTION STATED BEFORE THE RUN: exactly zero. The inheritance is resolved")
        print("at comptime, so both shapes execute the same two movea.l per band and differ")
        print("only in the pointer VALUES. A non-zero delta means the load became")
        print("data-dependent, or the two fixtures stopped being one thing apart.")
        for n in (1, 2, 3):
            a, b_ = table.get(f"S{n}"), table.get(f"O{n}")
            if a and b_:
                print(f"  {n} band(s): shared {a['cycles'][0]:>7}   own {b_['cycles'][0]:>7}"
                      f"   delta {b_['cycles'][0] - a['cycles'][0]:+d}")

    if args.out:
        Path(args.out).write_text(json.dumps(
            {"rom": args.rom, "arm": args.arm, "stride": stride,
             "block_present": has_block, "table": table,
             "slope_shared": s_shared, "failures": failures}, indent=1))
        print(f"\nraw: {args.out}")

    if failures:
        print("\nDERIVED CHECKS FAILED — the rows above are NOT evidence:")
        for f in failures:
            print(f"  {f}")
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
