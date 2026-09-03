#!/usr/bin/env python3
"""ramp_boundary_probe — WHICH SCREEN LINE does a dense ramp's first value land on?

The question is a SUITE CONTRACT's, not a comment's. `raster_ramp_program`'s banner, its
`RAMP-EVIDENCE.md` and empyrean's `aurora-effects-preset.schema.json` all say a VSRAM
target's value `j` displays on `top + j + 1`, and aurora's editor REGEXES the number out of
that schema sentence into a constant it paints for a human author. `tools/ramp_authored_witness.py`
arm 4 then measured the first line a run reaches as `top + 2` on two documents. Two
instruments, two answers, one contract. This settles it.

FIVE THINGS ARE MEASURED, and the first needs no emulator at all.

  §0 RECONCILIATION — `--pngs`. `docs/benchmarks/effects-p3/ramp-vsram-05px.png` and
     `ramp-control-flat.png` are the ORIGINAL 2026-08-14 captures, committed in the very
     commit (`c2a7e1a9`) that wrote RAMP-EVIDENCE.md's rule, at 320x224 full frame. So the
     "is its full row set blind to the boundary?" question does not need to be inferred
     from the published excerpt — the row set can be RE-DERIVED, all 224 of them, and both
     candidate rules scored against it. Nothing here is taken on trust from the doc except
     the fixture's parameters, which are read out of `configs.emp` AT COMMIT c2a7e1a9.

  §1 SWEEP — the first line a VSRAM ramp REACHES, over many `top`s spanning 3..220. Two
     FLAT twins (step 0) of one record differing only in `rrp_start`: every line the run
     reaches takes a constant offset and no line it misses can move, so the first differing
     line IS the first reached line, with no dependence on any value being visible.

  §2 LENGTH — the same, sweeping `lines` at a fixed `top`. An offset that is a property of
     the ENTER schedule cannot depend on run length; one that is an artefact of the sample
     might.

  §3 VALUE MAP — WHICH VALUE lands on which line, VSRAM, at +1 px/line. This is the half
     the flat twins structurally cannot answer and the half the contract's sentence is
     actually about. At +1 px/line every emitted value is distinct and the integer part is
     exact, so there is NO floor degeneracy anywhere — unlike the 2026-08-14 fixture's
     +0.5, where every other line is pixel-identical to its neighbour's value.

  §4 CRAM — the same first-reached-line question with a CRAM target. The contract's claim
     is specifically about "the N+1 VSRAM latency"; if CRAM lands on a different line the
     latency is target-specific, and if it lands on the same one the "VSRAM" framing is
     wrong. Both outcomes are reportable. A CRAM probe can also be INVISIBLE (a palette
     entry no pixel on those rows uses), so §4 runs a full-screen coverage discovery first
     and REFUSES to report a boundary for an entry with no coverage.

  §5 REPLICA — the 2026-08-14 fixture's exact geometry (top 112, lines 96, +0.5 px/line,
     VSRAM byte 2, plane A and sprites muted) rebuilt on TODAY's ROM and scored against the
     same two rules. §0 asks what the old machine did; §5 asks whether this machine still
     does it. They are different questions and a difference between them is a finding.

THE RECORDS ARE SYNTHESISED AT RUNTIME, IN RAM, AND NOT ONE ROM BYTE MOVES. `Raster_Install`
only stores a pointer and the walker reads the record through a1 from wherever it points, so
a 34-byte record written into scratch RAM is as real as one linked into the ROM (this is
`ramp_authored_witness.py` arm 3's own finding, and the Rust core REFUSES a ROM write
anyway). That buys the whole sweep: any `top`, any `lines`, either target, with no rebuild,
no re-freeze and no fixture re-stamp.

AND THE SYNTHESISER IS VALIDATED AGAINST THE COMPTIME CONSTRUCTOR, not against this
docstring. `validate_synth()` builds records for the two shipped preset documents from their
OWN json and compares all 34 bytes against what `raster_ramp_program` actually emitted into
the ROM. If they differ this script refuses to measure: a synthesiser that does not speak the
constructor's language would produce a confident answer about a program the engine cannot author.

⚠ VSCR IS RE-READ AT CAPTURE TIME AND PRINTED IN EVERY ARM. `addr 2` is "plane B, full
width" only while VDP shadow register $0B reads $03; `engine/level/parallax.emp` writes that
register at runtime, and in per-column mode ($07) the same write moves a SIXTEEN-PIXEL COLUMN.

⚠ NO REWIND. Each arm gets its own instance (`aether_emulator` boots PAUSED at frame 0);
nothing here calls reset, restore, a checkpoint or run_to; the frame index is read at every
step and a non-advancing one RAISES. oracle `91b21a8` rewinds the absolute frame index on
reset/restore, and a rewind reports as "no change observed" — indistinguishable from a real
negative, which is the exact answer this probe would be reporting.

Usage:
    python3 tools/ramp_boundary_probe.py --pngs          # §0 only, no emulator
    python3 tools/ramp_boundary_probe.py                 # everything
"""
import os, sys, json, asyncio, argparse, re, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from suite_paths import add_client_path
add_client_path()
from aether import BusClient
from aether_instance import aether_emulator

W = os.environ.get("RAMP_WITNESS_TREE", str(Path(__file__).resolve().parents[1]))
REPO = Path(W)
SCREEN_LINES = 224
SETTLE, AFTER = 400, 8


# ---------------------------------------------------------------------------
# Constants and layout, READ OUT OF THE TREE. Nothing below is typed twice.
# ---------------------------------------------------------------------------

def _raster_src() -> str:
    return (REPO / "engine/effects/raster.emp").read_text()


def emp_const(name: str) -> int:
    """`pub const NAME = <int>` out of engine/effects/raster.emp, $hex or decimal."""
    m = re.search(r"^pub const %s\s*=\s*(\$[0-9A-Fa-f]+|-?\d+)\s*$" % re.escape(name),
                  _raster_src(), re.M)
    if m is None:
        raise SystemExit("engine/effects/raster.emp: no `pub const %s = ...`. This script "
                         "derives every wire constant from that file rather than restating "
                         "it, and must not guess one." % name)
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


def rec_fields() -> list:
    """`struct RasterRampProgram`'s fields, in order, with the sizes its types imply.
    DERIVED on every run: this script decodes and encodes a record BY OFFSET, so a field
    reordered or resized in the .emp would have it writing the wrong four bytes as the step
    and reporting a confident wrong answer."""
    m = re.search(r"pub struct RasterRampProgram \{(.*?)^\}", _raster_src(), re.S | re.M)
    if m is None:
        raise SystemExit("engine/effects/raster.emp: cannot find `pub struct "
                         "RasterRampProgram { ... }`.")
    sizes = {"u8": 1, "u16": 2, "u32": 4}
    out = [(n, sizes[t]) for n, t in re.findall(r"(rrp_\w+):\s*(u8|u16|u32)", m.group(1))]
    if not out:
        raise SystemExit("RasterRampProgram declared no rrp_ fields — refusing to encode a "
                         "record against an empty layout.")
    return out


REC_FIELDS = rec_fields()
REC_SIZE = sum(n for _, n in REC_FIELDS)
OP_RUN_RAMP = emp_const("OP_RUN_RAMP")
RASTER_ARM_PARK = emp_const("RASTER_ARM_PARK")
RASTER_OPS_END = emp_const("RASTER_OPS_END")


def field_offset(name: str) -> int:
    off = 0
    for n, sz in REC_FIELDS:
        if n == name:
            return off
        off += sz
    raise KeyError(name)


# ---- the encodings, mirroring the .emp constructors they name ---------------

def fp16(whole: int, frac256: int) -> int:
    """engine/effects/raster.emp's `fp16` — for whole < 0 the fractional term SUBTRACTS."""
    return whole * 65536 + (frac256 * 256 if whole >= 0 else -frac256 * 256)


def u32_image(v: int) -> int:
    return v + 0x100000000 if v < 0 else v


def vdp_comm_delta(addr: int) -> int:
    return ((addr & 0x3FFF) << 16) | ((addr & 0xC000) >> 14)


def vdp_comm(addr: int, target: str, op: str = "Write") -> int:
    """engine/vdp.emp's `vdp_comm`, decomposed exactly as that file decomposes it."""
    target_bits = {"Vram": 0b100001, "Cram": 0b101011, "Vsram": 0b100101}[target]
    op_bits = {"Read": 0b001100, "Write": 0b000111, "Dma": 0b100111}[op]
    tr = target_bits & op_bits
    return ((tr & 3) << 30) | vdp_comm_delta(addr) | ((tr & 0xFC) << 2)


def raster_arm(next_fire: int, after_fire: int) -> int:
    return 0x8A00 | (after_fire - next_fire - 1)


def synth(top: int, lines: int, target: str, addr: int, start: int, step: int) -> bytes:
    """`raster_ramp_program(top, lines, cmd, start, step)`'s emitted record, in Python.

    Every ensure the constructor carries is re-applied here, so this cannot synthesise a
    program the engine would refuse to author — a boundary measured on an unauthorable
    record would say nothing about what an author meets."""
    assert top >= 3, "top %d below 3" % top
    assert lines >= 1, "lines %d must be positive" % lines
    assert top + lines <= 223, "run %d..%d must end at 222 or above" % (top, top + lines - 1)
    lo, hi = fp16(-512, 255), fp16(511, 255)
    assert lo <= start <= hi, "start %d outside fp16's authored range" % start
    assert lo <= step <= hi, "step %d outside fp16's authored range" % step
    mask = 0
    if target == "Cram":
        assert addr <= 126 and (addr >> 5) != 0, "CRAM addr %d" % addr
        mask = 1 << (addr >> 5)
    else:
        assert target == "Vsram" and addr <= 78, "VSRAM addr %d" % addr
    vals = {
        "rrp_mask": mask,
        "rrp_arm0": raster_arm(1, top - 1), "rrp_ops0": 0,
        "rrp_arm1": raster_arm(top - 1, top), "rrp_ops1": 0,
        "rrp_arm2": 0x8A00, "rrp_ops2": 1,          # RASTER_ARM_EVERY_LINE
        "rrp_op": OP_RUN_RAMP,
        "rrp_cmd": vdp_comm(addr, target),
        "rrp_lines": lines,
        "rrp_start": u32_image(start),
        "rrp_step": u32_image(step),
        "rrp_end_arm": RASTER_ARM_PARK, "rrp_end_ops": RASTER_OPS_END,
    }
    out = bytearray()
    for n, sz in REC_FIELDS:
        out += vals[n].to_bytes(sz, "big")
    return bytes(out)


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

def lst_symbols(lst_path: Path) -> dict:
    pat = re.compile(r"^\(0\)\s+\d+/([0-9A-Fa-f]+)\s+:\s+([A-Za-z_$][\w$.]*):")
    out = {}
    for line in lst_path.read_text(errors="replace").splitlines():
        m = pat.match(line)
        if m:
            out[m.group(2)] = int(m.group(1), 16)
    if not out:
        raise SystemExit("%s: parsed 0 symbols — refusing to measure with no addresses."
                         % lst_path)
    return out


def bus24(a: int) -> int:
    return a & 0xFFFFFF


def validate_synth(rom: bytes, sym: dict) -> None:
    """THE SYNTHESISER IS THE CONSTRUCTOR, OR THIS SCRIPT DOES NOT RUN.

    Both shipped preset documents are re-synthesised from their own json and compared, all
    34 bytes, against what `raster_ramp_program` emitted into this ROM. That validates every
    field at once — the arm words, the ops counts, the op, the command encoding, the two's
    complement images, the terminator — against the only authority that matters."""
    pres = REPO / "games/sonic4/data/editor/effects/presets"
    checked = 0
    for path in sorted(pres.glob("*.json")):
        doc = json.loads(path.read_text())
        if "ramp" not in doc:
            continue
        label = "EditorRaster_OJZ_Act1_%s" % doc["id"]
        if label not in sym:
            continue
        r = doc["ramp"]
        tgt = "Vsram" if "vsram" in r["target"] else "Cram"
        addr = r["target"][tgt.lower()]["addr"]
        mine = synth(r["top"], r["lines"], tgt, addr,
                     fp16(r["start"]["whole"], r["start"]["frac256"]),
                     fp16(r["step"]["whole"], r["step"]["frac256"]))
        at = sym[label]
        theirs = rom[at:at + REC_SIZE]
        if mine != theirs:
            raise SystemExit(
                "SYNTHESISER DOES NOT SPEAK THE CONSTRUCTOR'S LANGUAGE.\n"
                "  %s @ $%06X\n  rom   %s\n  synth %s\n"
                "Every record this probe installs is built by synth(); if it disagrees with "
                "raster_ramp_program's own emission for a document both can see, every "
                "boundary below would be measured on a program the engine cannot author."
                % (label, at, theirs.hex(), mine.hex()))
        checked += 1
    if checked == 0:
        raise SystemExit(
            "validate_synth checked ZERO records. Neither shipped ramp preset resolved to a "
            "symbol in this listing, so the synthesiser is UNVALIDATED — and an unvalidated "
            "record encoder is exactly the instrument that reports a confident wrong "
            "boundary. Refusing to measure.")
    print("  synthesiser validated against %d ROM record(s) emitted by raster_ramp_program, "
          "byte-identical" % checked)


# ---------------------------------------------------------------------------
# One instance
# ---------------------------------------------------------------------------

async def _rows(b, start, count, chunk=8):
    out, got = [], 0
    while got < count:
        n = min(chunk, count - got)
        r = await b.call("emulator/scanlines", {"startLine": start + got, "count": n})
        assert r.get("source") == "raster", r.get("source")
        for ln in r["rows"]:
            out.append(ln["rgb"])
        got += n
    return out


def run(rom_path, lst_path, sym, record=None, mute=True, capture=True):
    """One instance, one arm. Returns (mode3, rows, bracket).

    `record` is the 34 bytes to stage in scratch RAM and install via Raster_Pending; None
    means "no install", the untouched control."""
    with aether_emulator(rom_path, symbols=lst_path) as sock:
        async def go():
            b = BusClient(socket_path=sock, client_id="rbp", client_name="rbp")
            await b.connect()
            track = []

            async def mark(what, r=None):
                f = (r or await b.call("emulator/status", {}))["frame"]
                if track and f < track[-1][1]:
                    raise SystemExit(
                        "FRAME INDEX REWOUND inside the measurement window: %s -> %s. "
                        "Every line comparison in this arm is void — a rewind reports as "
                        "'no change observed', which is indistinguishable from a real "
                        "negative." % (track[-1], (what, f)))
                track.append((what, f))
                return f

            await mark("connect")
            if mute:
                await b.call("emulator/set_layer_enabled",
                             {"layer": "planeA", "enabled": False})
                await b.call("emulator/set_layer_enabled",
                             {"layer": "sprites", "enabled": False})
            done = 0
            while done < SETTLE:
                n = min(100, SETTLE - done)
                r = await b.call("emulator/run_frames", {"frames": n})
                done += n
                await mark("settle+%d" % done, r)
            scratch = SCRATCH[0]
            if record is not None:
                await b.call("emulator/write_memory",
                             {"addr": "0x%08X" % bus24(scratch),
                              "bytes": "0x" + record.hex()})
                back = (await b.call("emulator/read_memory",
                                     {"addr": "0x%08X" % bus24(scratch),
                                      "len": len(record)}))["bytes"]
                if bytes.fromhex(back[2:]) != record:
                    raise SystemExit("record did not stage at $%06X (wrote %s read %s)"
                                     % (bus24(scratch), record.hex(), back))
                await b.call("emulator/write_memory",
                             {"addr": "0x%08X" % bus24(sym["Raster_Pending"]),
                              "bytes": "0x%08X" % scratch})
            r = await b.call("emulator/run_frames", {"frames": AFTER})
            await mark("after-install", r)
            if record is not None:
                back = (await b.call("emulator/read_memory",
                                     {"addr": "0x%08X" % bus24(scratch),
                                      "len": len(record)}))["bytes"]
                if bytes.fromhex(back[2:]) != record:
                    raise SystemExit(
                        "THE ARM IS VOID: the record at $%06X was CLOBBERED during the %d "
                        "frames it was live. Something owns that scratch; a diff produced "
                        "by whatever overwrote it is not a measurement."
                        % (bus24(scratch), AFTER))
            mode3 = (await b.call("emulator/read_memory",
                                  {"addr": "0x%08X" % bus24(sym["VDP_Shadow_Table"] + 0x0B),
                                   "len": 1}))["bytes"]
            px = await _rows(b, 0, SCREEN_LINES) if capture else []
            await mark("after-capture")
            return mode3, px, (track[0], track[-1])
        return asyncio.run(go())


SCRATCH = [None]


def pick_scratch(rom: bytes, sym: dict) -> int:
    ram_end = sym["Game_RAM_End"]
    init_sp = int.from_bytes(rom[0:4], "big")
    s = (ram_end + 0x1DA) & ~1
    if not (ram_end < s and s + REC_SIZE + 0x800 < init_sp):
        raise SystemExit("no safe scratch: Game_RAM_End $%08X initial SP $%08X candidate "
                         "$%08X" % (ram_end, init_sp, s))
    print("  scratch $%08X   (Game_RAM_End $%08X, initial SP $%08X, %d bytes of stack "
          "headroom)" % (s, ram_end, init_sp, init_sp - s))
    return s


def first_diff(a, b):
    d = [i for i in range(min(len(a), len(b))) if a[i] != b[i]]
    if not d:
        return None, [], []
    gaps = [l for l in range(d[0], d[-1] + 1) if a[l] == b[l]]
    return d[0], d, gaps


# ---------------------------------------------------------------------------
# §0 — the 2026-08-14 captures, re-derived row by row
# ---------------------------------------------------------------------------

def section0():
    from PIL import Image
    import numpy as np
    d = REPO / "docs/benchmarks/effects-p3"
    a = np.array(Image.open(d / "ramp-vsram-05px.png").convert("RGB"))
    c = np.array(Image.open(d / "ramp-control-flat.png").convert("RGB"))
    # THE FIXTURE'S PARAMETERS, READ OUT OF THE COMMIT THAT TOOK THE CAPTURES, not out of
    # RAMP-EVIDENCE.md's prose — the prose is the thing under test.
    import subprocess
    src = subprocess.run(["git", "-C", str(REPO), "show",
                          "c2a7e1a9:games/sonic4/data/parallax/configs.emp"],
                         capture_output=True, text=True, check=True).stdout
    TOP = int(re.search(r"^const OJZ_RAMP_TOP\s*=\s*(\d+)", src, re.M).group(1))
    LINES = int(re.search(r"^const OJZ_RAMP_LINES\s*=\s*(\d+)", src, re.M).group(1))
    sm = re.search(r"^const OJZ_RAMP_STEP\s*=\s*fp16\((-?\d+),\s*(\d+)\)", src, re.M)
    STEP = fp16(int(sm.group(1)), int(sm.group(2)))
    print("§0  RECONCILIATION — the ORIGINAL 2026-08-14 captures, re-derived row by row")
    print("    fixture read from configs.emp AT COMMIT c2a7e1a9: top %d, lines %d, "
          "step %+d (%.4f px/line), VSRAM byte 2" % (TOP, LINES, STEP, STEP / 65536))
    print("    images %s and %s, both %dx%d" % ("ramp-vsram-05px.png",
                                                "ramp-control-flat.png",
                                                a.shape[1], a.shape[0]))

    def ok(L, s):
        return 0 <= L + s < 224 and bool((a[L] == c[L + s]).all())

    # A row whose reference falls off the bottom of the control image CANNOT be scored, and
    # is excluded from every population below rather than counted as a miss. That exclusion
    # is what makes the doc's "74 of 74" a 74-row population out of the run's 96 lines.
    def model(lam):
        def f(D):
            k = D - TOP - lam
            if k < 0:
                return 0
            if k >= LINES:
                k = LINES - 1        # the run WRITES, so its last value persists downward
            return ((k + 1) * STEP) >> 16
        return f

    f1, f2 = model(1), model(2)
    ident = [L for L in range(224) if bool((a[L] == c[L]).all())]
    print("    rows pixel-identical between ramp and control: %d, first differing row %d "
          "(= top %+d)" % (len(ident), ident[-1] + 1 if ident else 0,
                           (ident[-1] + 1 - TOP) if ident else 0))
    scorable = [L for L in range(224) if 0 <= L + f1(L) < 224 and 0 <= L + f2(L) < 224]
    disc = [L for L in scorable if f1(L) != f2(L)]
    for lam, f in ((1, f1), (2, f2)):
        hit = [L for L in scorable if ok(L, f(L))]
        print("    rule 'first reached line = top + %d' : %d of %d scorable rows match "
              "exactly" % (lam, len(hit), len(scorable)))
    h1 = [L for L in disc if ok(L, f1(L))]
    h2 = [L for L in disc if ok(L, f2(L))]
    print("    DISCRIMINATING rows (the two rules predict different shifts): %d" % len(disc))
    print("      top+1 rule matches on %d of them;  top+2 rule matches on %d"
          % (len(h1), len(h2)))
    pub = [112, 116, 124, 140, 156, 172, 184]
    print("    the PUBLISHED excerpt's rows %s" % pub)
    print("      discriminating? %s"
          % {L: ("yes" if L in disc else "no") for L in pub})
    print("      -> the excerpt is %s to the boundary"
          % ("BLIND" if not any(L in disc for L in pub) else "NOT blind"))
    print()
    return TOP, LINES, STEP


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pngs", action="store_true", help="§0 only, no emulator")
    ap.add_argument("--rom", default=str(REPO / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(REPO / "s4.debug.lst"))
    a = ap.parse_args()
    t0 = time.time()
    print("ramp_boundary_probe — tree %s" % REPO)
    print("  RasterRampProgram: %d fields, %d bytes; OP_RUN_RAMP %d, ARM_PARK $%04X, "
          "OPS_END $%04X" % (len(REC_FIELDS), REC_SIZE, OP_RUN_RAMP, RASTER_ARM_PARK,
                             RASTER_OPS_END))
    print()
    p0 = section0()
    if a.pngs:
        return 0

    rom = Path(a.rom).read_bytes()
    sym = lst_symbols(Path(a.lst))
    print("§WIRE  the synthesiser against the constructor")
    validate_synth(rom, sym)
    SCRATCH[0] = pick_scratch(rom, sym)
    print()

    VS, VA = "Vsram", 2
    PROBE_PX = -37          # odd on purpose: a multiple of the 8-px tile height could alias

    def flat_pair(top, lines, target, addr, mute=True, lo=0, hi=None):
        """The two FLAT twins. Returns (first_reached, all_diff, gaps, mode3s, brackets)."""
        hi = PROBE_PX if hi is None else hi
        ra = synth(top, lines, target, addr, fp16(lo, 0), 0)
        rb = synth(top, lines, target, addr, fp16(hi, 0), 0)
        m1, r1, b1 = run(a.rom, a.lst, sym, record=ra, mute=mute)
        m2, r2, b2 = run(a.rom, a.lst, sym, record=rb, mute=mute)
        f, d, g = first_diff(r1, r2)
        return f, d, g, (m1, m2), (b1, b2)

    # ---- arm 1: control vs control ----------------------------------------
    print("§1a CONTROL vs CONTROL  (nothing is attributable until these agree)")
    mA, rA, bA = run(a.rom, a.lst, sym, record=None, mute=True)
    mB, rB, bB = run(a.rom, a.lst, sym, record=None, mute=True)
    same = sum(1 for x, y in zip(rA, rB) if x == y)
    print("    %d of %d lines identical (want all)   reg $0B %s / %s" % (same, len(rA), mA, mB))
    print("    frame brackets %s..%s and %s..%s" % (bA[0], bA[1], bB[0], bB[1]))
    if same != len(rA):
        print("    -> the two instances do NOT reproduce each other. STOPPING.")
        return 1
    print()

    # ---- §1: the top sweep -------------------------------------------------
    print("§1  VSRAM FLAT-TWIN SWEEP over `top`  (offset %+d px, planeA+sprites muted)"
          % PROBE_PX)
    print("    %-5s %-6s %-7s %-7s %-6s %-6s %-5s %s"
          % ("top", "lines", "derived", "reached", "delta", "last", "gaps", "reg $0B"))
    sweep = [3, 4, 5, 8, 17, 33, 45, 64, 77, 96, 112, 128, 150, 175, 190, 200, 210, 215, 220]
    results = []
    for top in sweep:
        lines = min(64, 223 - top)
        f, d, g, ms, bs = flat_pair(top, lines, VS, VA)
        results.append((top, lines, f))
        print("    %-5d %-6d %-7d %-7s %-6s %-6s %-5d %s"
              % (top, lines, top + 1, f, ("%+d" % (f - top)) if f is not None else "-",
                 d[-1] if d else "-", len(g), "/".join(x for x in ms)))
    deltas = sorted(set(f - t for t, l, f in results if f is not None))
    print("    distinct (reached - top) over %d tops: %s" % (len(results), deltas))
    print()

    # ---- §2: the lines sweep ----------------------------------------------
    print("§2  VSRAM FLAT-TWIN SWEEP over `lines` at top 112")
    print("    %-6s %-7s %-7s %-6s %-6s %s" % ("lines", "derived", "reached", "delta",
                                               "last", "gaps"))
    for lines in (1, 2, 3, 4, 8, 16, 64, 96, 111):
        f, d, g, ms, bs = flat_pair(112, lines, VS, VA)
        print("    %-6d %-7d %-7s %-6s %-6s %d"
              % (lines, 113, f, ("%+d" % (f - 112)) if f is not None else "-",
                 d[-1] if d else "-", len(g)))
    print()

    # ---- §3: the value map -------------------------------------------------
    print("§3  VSRAM VALUE MAP at +1 px/line  (no floor degeneracy anywhere)")
    for top, lines in ((112, 64), (40, 64)):
        ref = synth(top, lines, VS, VA, 0, 0)              # the same record, step 0 => V = 0
        sub = synth(top, lines, VS, VA, 0, fp16(1, 0))
        m1, rr, b1 = run(a.rom, a.lst, sym, record=ref, mute=True)
        m2, rs, b2 = run(a.rom, a.lst, sym, record=sub, mute=True)
        print("    top %d, lines %d   reg $0B %s / %s   brackets %s..%s, %s..%s"
              % (top, lines, m1, m2, b1[0], b1[1], b2[0], b2[1]))
        print("      %-5s %-8s %-8s %s" % ("line", "n=L-top", "shift(s)", "reading"))
        for L in range(top - 2, min(top + 12, 224)):
            ss = [s for s in range(-4, 80) if 0 <= L + s < 224 and rs[L] == rr[L + s]]
            print("      %-5d %-8d %-8s %s"
                  % (L, L - top, ss[:6],
                     "identical to the V=0 reference" if 0 in ss else ""))
        # the whole run, scored against both readings
        def score(vmap):
            hits = miss = 0
            for L in range(top, min(top + lines + 4, 224)):
                v = vmap(L)
                if not (0 <= L + v < 224):
                    continue
                if rs[L] == rr[L + v]:
                    hits += 1
                else:
                    miss += 1
            return hits, miss
        for name, vm in (("value j on top+j+1 (first reached top+1)",
                          lambda L: max(0, min(lines, L - top))),
                         ("value j on top+j   (first reached top+2)",
                          lambda L: max(0, min(lines + 1, L - top)) if L >= top + 2 else 0)):
            h, m = score(vm)
            print("      %-46s %d hit / %d miss" % (name, h, m))
        print()

    # ---- §4: CRAM ----------------------------------------------------------
    print("§4  CRAM TARGET  (all layers ON — muting a plane removes the pixels that use "
          "the entry)")
    BLACK, BRIGHT = 0x000, 0x0EE
    print("    coverage discovery: a FULL-SCREEN flat pair (top 3, lines 220) per entry, "
          "black $%03X vs $%03X" % (BLACK, BRIGHT))
    cov = {}
    for addr in (0x28, 0x48, 0x4A, 0x68, 0x6A):
        f, d, g, ms, bs = flat_pair(3, 220, "Cram", addr, mute=False, lo=BLACK, hi=BRIGHT)
        cov[addr] = set(d)
        print("      CRAM byte $%02X (line %d, entry %d): %d rows change, first %s, "
              "last %s, reg $0B %s"
              % (addr, addr >> 5, (addr & 31) >> 1, len(d), f, d[-1] if d else "-",
                 "/".join(x for x in ms)))
    usable = [x for x in cov if len(cov[x]) > 100]
    if not usable:
        print("    *** NO CRAM ENTRY HAS BROAD COVERAGE in this scene. §4 measured NOTHING "
              "about the CRAM boundary; do not read a null here as 'CRAM behaves the "
              "same'.")
    else:
        pick = max(usable, key=lambda x: len(cov[x]))
        print("    using CRAM byte $%02X (%d covered rows)" % (pick, len(cov[pick])))
        print("    %-5s %-6s %-7s %-7s %-6s %-6s %s"
              % ("top", "lines", "der.CRAM", "reached", "delta", "covered?", "reg $0B"))
        for top in (3, 40, 77, 112, 150, 190, 220):
            lines = min(64, 223 - top)
            # A boundary is only readable where the entry is actually on screen. The first
            # COVERED row at or below `top` is what the probe can see; say so explicitly
            # rather than reporting an unreadable null as a measurement.
            near = sorted(l for l in cov[pick] if top <= l <= top + 4)
            f, d, g, ms, bs = flat_pair(top, lines, "Cram", pick, mute=False,
                                        lo=BLACK, hi=BRIGHT)
            print("    %-5d %-6d %-7d %-7s %-6s %-6s %s"
                  % (top, lines, top, f, ("%+d" % (f - top)) if f is not None else "-",
                     "%s" % (near[:3] if near else "NONE"),
                     "/".join(x for x in ms)))
    print()

    # ---- §5: the replica ---------------------------------------------------
    TOP, LINES, STEP = p0
    print("§5  REPLICA of the 2026-08-14 fixture on TODAY's ROM  (top %d, lines %d, "
          "step %+.4f px/line)" % (TOP, LINES, STEP / 65536))
    ref = synth(TOP, LINES, VS, VA, 0, 0)
    sub = synth(TOP, LINES, VS, VA, 0, STEP)
    m1, rr, b1 = run(a.rom, a.lst, sym, record=ref, mute=True)
    m2, rs, b2 = run(a.rom, a.lst, sym, record=sub, mute=True)
    print("    reg $0B %s / %s   brackets %s..%s and %s..%s" % (m1, m2, b1[0], b1[1],
                                                                b2[0], b2[1]))
    ident = [L for L in range(224) if rs[L] == rr[L]]
    firstd = next((L for L in range(224) if rs[L] != rr[L]), None)
    print("    rows identical to the flat control: %d, first differing row %s (= top %+d)"
          % (len(ident), firstd, (firstd - TOP) if firstd is not None else 0))

    def model(lam):
        def f(D):
            k = D - TOP - lam
            if k < 0:
                return 0
            if k >= LINES:
                k = LINES - 1
            return ((k + 1) * STEP) >> 16
        return f

    f1, f2 = model(1), model(2)
    scorable = [L for L in range(224) if 0 <= L + f1(L) < 224 and 0 <= L + f2(L) < 224]
    disc = [L for L in scorable if f1(L) != f2(L)]
    for lam, f in ((1, f1), (2, f2)):
        hit = [L for L in scorable if rs[L] == rr[L + f(L)]]
        print("    rule 'first reached line = top + %d' : %d of %d scorable rows match"
              % (lam, len(hit), len(scorable)))
    h1 = [L for L in disc if rs[L] == rr[L + f1(L)]]
    h2 = [L for L in disc if rs[L] == rr[L + f2(L)]]
    print("    DISCRIMINATING rows: %d — top+1 rule matches %d, top+2 rule matches %d"
          % (len(disc), len(h1), len(h2)))
    print()
    print("elapsed %.1f s" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
