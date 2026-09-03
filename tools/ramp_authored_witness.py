#!/usr/bin/env python3
"""ramp_authored_witness — does an AUTHORED ramp document move the PICTURE?

EFFECTS-W1 DoD item 6's certification. The item landed in three parts and none of them
witnessed this: the engine half measured the HBlank budget, `OJZ_TestRamp` is a build-time
fixture that never renders, and step 4 proved the generator READS the key. Merged is not
certified — the owner's standing rule is that a landing shows on screen or in a witness.

THE SUBJECT IS A PRESET DOCUMENT, NAMED ON THE COMMAND LINE, and every expectation below
is DERIVED FROM THAT DOCUMENT — never typed here. `--preset` defaults to the original
subject, `ramp_probe` (top 128, lines 64, VSRAM addr 2, +1.5 px/line). The document that
motivated the 2026-09-03 rewrite is `aurora_local_rampctl_probe`: authored in aurora's real
editor panel (top 3, lines 220, addr 2, start 0, step -1.5), the first NEGATIVE step
anything in this tree ever authored, and the run that found `raster_ramp_program` was
never encoding one.

    python3 tools/ramp_authored_witness.py --preset aurora_local_rampctl_probe

TWO HALVES, and the first one needs no emulator at all.

  THE WIRE HALF reads the program's record straight out of the ROM FILE at the address the
  .lst gives its symbol, decodes all 34 bytes, and compares every field against the
  document's own numbers put through the SAME encodings the constructor uses. This is where
  a sign defect shows: the two's-complement image of a negative step is a fact about the
  bytes, not about the picture.

  THE PICTURE HALF is three arms, and the second and third are the point — a single
  before/after is NOT a control here, because the game keeps running and every line changes
  anyway:

    1. CONTROL vs CONTROL — two independent instances, same frame count, same lines. They
       must agree completely, or no difference below is attributable to anything.
    2. RAMP vs CONTROL — install the document's program. Its DISPLAYED span is
       `top+1 .. top+lines`, one line later than the written span, which is the VSRAM N+1
       latency the engine documents.
    3. RAMP vs ITS OWN STEP-0 TWIN — the discriminator, and it is the tree's own idiom
       rather than an invention: `games/sonic4/data/effects/ojz_effects.emp` says it in as
       many words beside OJZ_TestRamp — *"The run WRITES the VSRAM entry rather than adding
       to it, so the control must be a ramp too — same program, step 0 — or the comparison
       would confound 'the ramp' with 'the ramp replaced the parallax system's base
       scroll'."* Arm 3 builds that twin AT RUNTIME by copying the subject's own record and
       zeroing `rrp_step`, so the two programs differ in FOUR BYTES and nothing else. Every
       line that differs between arm 2 and arm 3 is attributable to the STEP alone.

WHY NOT THE OLD ARM 3 (install `OJZ_BaseSwap` instead). It was the right discriminator for
a 64-line run in the middle of the screen, where "outside the span" was 110 - 64 lines of
real estate. It is USELESS for a run that covers 4..223: outside the span is four lines, and
worse, `OJZ_BaseSwap` re-points Plane A below line 160, so it changes lines for a reason
that has nothing to do with either ramp. A held-constant control is only a control where it
does nothing. The step-0 twin holds the program REPLACEMENT constant exactly, which is the
confound that actually needs holding, and it does nothing anywhere else.

⚠ VSCR IS RE-READ AT CAPTURE TIME AND PRINTED. `addr 2` is "plane B, full width" only while
VDP shadow register $0B reads $03 (full-screen vertical scroll). `engine/level/parallax.emp`
writes that register at two runtime sites (:1081 and :1463-1464), so a scene can switch to
per-column mode ($07), and there a plane-B VSRAM entry-1 write moves a SIXTEEN-PIXEL COLUMN,
not the plane. A full-width shear claim resting on an unverified register is not a result, so
this script reads `VDP_Shadow_Table + VDP_MODE3_OFF` in every arm and prints what it found.

⚠ NOTHING HERE POKES `Debug_Scene_Index`. It is a cursor a hotkey INSTALLS FROM; writing it
installs nothing, so a sweep driven that way reads "unchanged on every scene" and looks like
a clean refutation. This script does not change scenes at all — it measures the boot scene.

ADDRESSES ARE READ FROM THE .lst AT THE MOMENT OF USE. Every one of them: the program
symbol, `Raster_Pending`, `Raster_Program`, `VDP_Shadow_Table`. Symbols move whenever bytes
move, and this script was written once against hard-coded constants (`RAMP_ADDR`,
`PENDING`) while its own docstring claimed otherwise — the claim is now true.

MEASURED 2026-09-03 at aeon origin/master, subject `ramp_probe`: arm 1 110/110 identical;
arm 2 all 64 displayed lines changed; the old arm 3 found 46 outside lines changed by BOTH
and 0 unique to the ramp. Those numbers were taken with the old sampling window and the old
arm 3; re-run rather than compared against.
"""
import os, sys, asyncio, hashlib, json, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from suite_paths import add_client_path
add_client_path()
from aether import BusClient
from aether_instance import aether_emulator

W = os.environ.get("RAMP_WITNESS_TREE", str(Path(__file__).resolve().parents[1]))

# Screen geometry. 224 lines exist; 223 is the last. The constructor's own ceiling ensure
# (`top + lines <= 223`) is written against this and is quoted in the report.
SCREEN_LINES = 224

# The record's field offsets. NOT typed as magic numbers below: `decode_record` derives the
# layout from this table — and `check_record_layout()` re-derives the table from
# engine/effects/raster.emp's own `struct RasterRampProgram` declaration on every run and
# refuses to measure if they disagree. That check is not decoration: this whole script reads
# a ROM record by OFFSET, so a field reordered or resized in the .emp would have it decoding
# the wrong four bytes as the step and reporting a confident wrong number.
REC_FIELDS = [("rrp_mask", 2), ("rrp_arm0", 2), ("rrp_ops0", 2), ("rrp_arm1", 2),
              ("rrp_ops1", 2), ("rrp_arm2", 2), ("rrp_ops2", 2), ("rrp_op", 2),
              ("rrp_cmd", 4), ("rrp_lines", 2), ("rrp_start", 4), ("rrp_step", 4),
              ("rrp_end_arm", 2), ("rrp_end_ops", 2)]
REC_SIZE = sum(n for _, n in REC_FIELDS)


def check_record_layout(repo: Path) -> None:
    """REC_FIELDS must be exactly `struct RasterRampProgram`'s fields, in order, with the
    sizes its `u16`/`u32` types imply. Raises rather than warning: a silent drift here is a
    wrong number reported confidently, which is worse than no number."""
    import re
    src = (repo / "engine/effects/raster.emp").read_text()
    m = re.search(r"pub struct RasterRampProgram \{(.*?)^\}", src, re.S | re.M)
    if m is None:
        raise SystemExit("engine/effects/raster.emp: cannot find `pub struct "
                         "RasterRampProgram { ... }`. This script decodes that record BY "
                         "OFFSET; with the declaration unreadable it must not guess.")
    sizes = {"u8": 1, "u16": 2, "u32": 4}
    found = [(n, sizes[t]) for n, t in
             re.findall(r"(rrp_\w+):\s*(u8|u16|u32)", m.group(1))]
    if found != REC_FIELDS:
        raise SystemExit(
            "RasterRampProgram's declared layout has DRIFTED from this script's REC_FIELDS.\n"
            "  declared: %s\n  here    : %s\n"
            "Update REC_FIELDS. Decoding by a stale offset table would read the wrong four "
            "bytes as rrp_step and report a confident wrong sign." % (found, REC_FIELDS))

SETTLE, AFTER = 400, 8


# ---------------------------------------------------------------------------
# The encodings, spelled ONCE, mirroring the .emp constructors they name. Every expected
# value in the report goes through these rather than being typed as a number.
# ---------------------------------------------------------------------------

def fp16(whole: int, frac256: int) -> int:
    """engine/effects/raster.emp's `fp16` — and note the asymmetry it documents at length:
    for whole < 0 the fractional term SUBTRACTS, i.e. adds MAGNITUDE. fp16(-1, 128) is
    -1.5, not -0.5."""
    return whole * 65536 + (frac256 * 256 if whole >= 0 else -frac256 * 256)


def u32_image(v: int) -> int:
    """The two's-complement u32 image of a signed long — what `raster_ramp_program` stores
    into `rrp_start`/`rrp_step`, and what `add.l Raster_Ramp_Step, d1` consumes."""
    return v + 0x100000000 if v < 0 else v


def vdp_comm_vsram_write(addr: int) -> int:
    """engine/vdp.emp's `vdp_comm(addr, VdpTarget.Vsram, VdpOp.Write)`.

    Decomposed exactly as engine/vdp.emp decomposes it, rather than as one folded magic
    constant, so a reader can check this against that file line by line:
        target_bits(Vsram) = %100101,  op_bits(Write) = %000111,  tr = t & r = %000101
        vdp_comm  = ((tr & 3) << 30) | vdp_comm_delta(addr) | ((tr & $FC) << 2)
        vdp_comm_delta(addr) = ((addr & $3FFF) << 16) | ((addr & $C000) >> 14)
    """
    tr = 0b100101 & 0b000111
    delta = ((addr & 0x3FFF) << 16) | ((addr & 0xC000) >> 14)
    return ((tr & 3) << 30) | delta | ((tr & 0xFC) << 2)


def raster_arm(next_fire: int, after_fire: int) -> int:
    """engine/effects/raster.emp's `raster_arm`."""
    return 0x8A00 | (after_fire - next_fire - 1)


def top_from_arm0(arm0: int) -> int:
    """The inverse of `raster_arm(1, top - 1)`; how the ROM record itself states its `top`."""
    return (arm0 & 0xFF) + 3


# ---------------------------------------------------------------------------
# Inputs: the .lst symbol table, the preset document, the ROM image.
# ---------------------------------------------------------------------------

def lst_symbols(lst_path: Path) -> dict:
    """Every label in the listing's symbol table, name -> address.

    LOUD ON UNMEASURABLE: a listing that yields no symbols raises. A silent empty dict here
    would make every `sym()` below fail with a KeyError that reads like a typo.
    """
    import re
    pat = re.compile(r"^\(0\)\s+\d+/([0-9A-Fa-f]+)\s+:\s+([A-Za-z_$][\w$.]*):")
    out = {}
    for line in lst_path.read_text(errors="replace").splitlines():
        m = pat.match(line)
        if m:
            out[m.group(2)] = int(m.group(1), 16)
    if not out:
        raise SystemExit(f"{lst_path}: parsed 0 symbols. This script resolves every address "
                         f"from the listing at the moment of use; with no symbols it cannot "
                         f"measure anything and must not pretend to.")
    return out


def bus24(addr: int) -> int:
    """The Aether bus is 24 bits (aether_instance's own note). $FFFF8B52 and $FF8B52 are the
    same byte; the wide form is REFUSED with -32004."""
    return addr & 0xFFFFFF


def load_document(repo: Path, pid: str) -> dict:
    path = repo / "games/sonic4/data/editor/effects/presets" / f"{pid}.json"
    if not path.is_file():
        # The id need not equal the filename, so fall back to a scan before giving up.
        for cand in sorted((repo / "games/sonic4/data/editor/effects/presets").glob("*.json")):
            doc = json.loads(cand.read_text())
            if doc.get("id") == pid:
                return doc
        raise SystemExit(f"no preset document with id {pid!r} under "
                         f"games/sonic4/data/editor/effects/presets/")
    return json.loads(path.read_text())


def decode_record(blob: bytes) -> dict:
    out, off = {}, 0
    for name, n in REC_FIELDS:
        out[name] = int.from_bytes(blob[off:off + n], "big")
        off += n
    return out


def field_offset(name: str) -> int:
    off = 0
    for n, sz in REC_FIELDS:
        if n == name:
            return off
        off += sz
    raise KeyError(name)


# ---------------------------------------------------------------------------
# The picture half.
# ---------------------------------------------------------------------------

async def rows(b, start, count, chunk=10):
    out, got = [], 0
    while got < count:
        n = min(chunk, count - got)
        r = await b.call("emulator/scanlines", {"startLine": start + got, "count": n})
        assert r.get("source") == "raster", r.get("source")
        px = r.get("lines") or r.get("rows") or r.get("pixels")
        for i, ln in enumerate(px):
            t = ln if isinstance(ln, str) else json.dumps(ln)
            out.append((start + got + i, hashlib.md5(t.encode()).hexdigest()[:8]))
        got += n
    return out


def run(rom, lst, sym, install=None, patch=None):
    """One instance. `install` is a program address to stage in Raster_Pending; `patch` is
    an optional (addr, bytes) applied to the ROM image before the install, used only by the
    step-0 twin. Returns (Raster_Program, mode3_shadow, rows, frame_track).

    ⚠ NO REWIND MAY HAPPEN INSIDE A MEASUREMENT WINDOW, and this function proves it rather
    than assuming it (oracle `91b21a8`, 2026-09-03: `emulator/reset` puts the absolute frame
    index back to 0, and anything gated on a strictly advancing index then silently does
    NOTHING until the machine climbs back — which reports as "no change observed" and is
    INDISTINGUISHABLE FROM A REAL NEGATIVE). This witness's whole subject is whether a ramp
    changes lines, so a false negative here would read as the ROM not honouring the
    document. Three defences, in order of strength:
      1. Each arm gets its OWN instance, spawned by `aether_emulator`, which boots PAUSED at
         frame 0. Nothing here calls `reset`, `restore`, a checkpoint, or `run_to`.
      2. The window is bracketed: the frame index is read at entry and at every step, and a
         non-advancing index raises rather than being carried across.
      3. The bracket is RETURNED and printed, so the report can state — as a measured fact,
         not a promise — that no rewind landed inside the sample window.
    """
    with aether_emulator(rom, symbols=lst) as sock:
        async def go():
            b = BusClient(socket_path=sock, client_id="ab", client_name="ab")
            await b.connect()
            track = []

            async def mark(what, r=None):
                f = (r or await b.call("emulator/status", {}))["frame"]
                if track and f < track[-1][1]:
                    raise SystemExit(
                        "FRAME INDEX REWOUND inside the measurement window: %s -> %s at "
                        "%r. Something reset or restored the machine mid-sample. Every "
                        "line comparison in this run is void — a rewind produces 'no "
                        "change observed', which is indistinguishable from a real "
                        "negative, and this witness refuses to report one it cannot tell "
                        "apart." % (track[-1], (what, f), what))
                track.append((what, f))
                return f

            await mark("connect")
            done = 0
            while done < SETTLE:
                n = min(100, SETTLE - done)
                r = await b.call("emulator/run_frames", {"frames": n})
                done += n
                await mark("settle+%d" % done, r)
            if patch is not None:
                # THE TWIN LIVES IN WORK RAM, NOT IN A PATCHED ROM — MEASURED, NOT CHOSEN.
                # The first shape of this arm patched `rrp_step` in place at the program's
                # own ROM address; the Rust core refuses that outright:
                #   [-32004] 0x00013BD0: only the work-RAM window ($E00000-$FFFFFF) is
                #            writable; ROM and I/O writes are refused
                # So the twin is WRITTEN INTO RAM and `Raster_Pending` is pointed at it.
                # That is sound for the same reason the install itself is: `Raster_Install`
                # only stores a pointer, and the walker reads the record through a1 from
                # wherever it points. It also makes the twin a strictly better control than
                # a ROM patch would have been — the SUBJECT's bytes are never touched, so
                # arm 2 and arm 3 are two installs of two records rather than one record
                # mutated between runs.
                addr, data = patch
                # `bytes` must carry the "0x" prefix (protocol §2.5; measured -32602 without
                # it).
                await b.call("emulator/write_memory",
                             {"addr": "0x%08X" % bus24(addr), "bytes": "0x" + data.hex()})
                back = (await b.call("emulator/read_memory",
                                     {"addr": "0x%08X" % bus24(addr),
                                      "len": len(data)}))["bytes"]
                if bytes.fromhex(back[2:] if back.startswith("0x") else back) != data:
                    raise SystemExit(
                        "ARM 3 CANNOT BE STAGED: the step-0 twin was written to scratch RAM "
                        "at $%06X and the read-back does not match (wrote %s, read %s). "
                        "That is a MISSING MEASUREMENT, not a pass — arm 2 alone cannot "
                        "separate the ramp from the program replacement."
                        % (bus24(addr), data.hex(), back))
            if install is not None:
                await b.call("emulator/write_memory",
                             {"addr": "0x%08X" % bus24(sym["Raster_Pending"]),
                              "bytes": "0x%08X" % install})
            r = await b.call("emulator/run_frames", {"frames": AFTER})
            await mark("after-install", r)
            if patch is not None:
                # THE SCRATCH MUST STILL HOLD THE TWIN. It sits above Game_RAM_End and well
                # below the initial stack pointer, but "well below" is an argument and this
                # is a measurement: a clobbered record would have the walker reading
                # whatever landed there, and the resulting line diff would be attributed to
                # the step.
                addr, data = patch
                back = (await b.call("emulator/read_memory",
                                     {"addr": "0x%08X" % bus24(addr),
                                      "len": len(data)}))["bytes"]
                if bytes.fromhex(back[2:] if back.startswith("0x") else back) != data:
                    raise SystemExit(
                        "ARM 3 IS VOID: the step-0 twin at $%06X was CLOBBERED during the "
                        "%d frames it was live (wrote %s, read %s). Something in the game "
                        "owns that scratch after all; pick another address rather than "
                        "reporting a diff produced by whatever overwrote it."
                        % (bus24(addr), AFTER, data.hex(), back))
            prog = (await b.call("emulator/read_memory",
                                 {"symbol": "Raster_Program", "len": 4}))["bytes"]
            # ⚠ RE-READ AT THE POINT OF USE, not once at boot. `addr 2` is "plane B, full
            # width" only while this register reads $03; parallax.emp writes it at two
            # runtime sites, so a scene can be in per-column mode ($07) and the same VSRAM
            # write then moves a 16-pixel column instead of the plane.
            mode3 = (await b.call("emulator/read_memory",
                                  {"addr": "0x%08X" % bus24(sym["VDP_Shadow_Table"] + 0x0B),
                                   "len": 1}))["bytes"]
            px = await rows(b, 0, SCREEN_LINES)
            await mark("after-capture")
            return prog, mode3, px, track
        return asyncio.run(go())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="ramp_probe")
    ap.add_argument("--rom", default=None)
    ap.add_argument("--lst", default=None)
    ap.add_argument("--wire-only", action="store_true",
                    help="the ROM-file half only; no emulator")
    a = ap.parse_args()
    repo = Path(W)
    rom = Path(a.rom or (repo / "s4.debug.bin"))
    lst = Path(a.lst or (repo / "s4.debug.lst"))

    check_record_layout(repo)
    doc = load_document(repo, a.preset)
    ramp = doc["ramp"]
    top, lines = ramp["top"], ramp["lines"]
    addr = ramp["target"]["vsram"]["addr"]
    start_v = fp16(ramp["start"]["whole"], ramp["start"]["frac256"])
    step_v = fp16(ramp["step"]["whole"], ramp["step"]["frac256"])

    # THE DERIVATION, stated before anything is measured so the report cannot be read as
    # having been fitted to the result.
    w_lo, w_hi = top, top + lines - 1
    d_lo, d_hi = top + 1, top + lines
    print("THE DOCUMENT   %s" % a.preset)
    print("  top %d, lines %d, VSRAM byte %d, start %s, step %s"
          % (top, lines, addr, ramp["start"], ramp["step"]))
    print("  start = %+d (16.16) = %+.4f px   step = %+d (16.16) = %+.4f px/line"
          % (start_v, start_v / 65536, step_v, step_v / 65536))
    print("THE DERIVATION (from raster_ramp_program's own ensures and its N+1 note)")
    print("  WRITE span   %d..%d engine lines   (top .. top+lines-1)" % (w_lo, w_hi))
    print("  DISPLAY span %d..%d screen lines   (VSRAM: value j displays on top+j+1)"
          % (d_lo, d_hi))
    print("  the ceiling ensure is `top + lines <= 223`; this document sits at %d"
          % (top + lines))
    print("  the last line that exists is %d" % (SCREEN_LINES - 1))
    print()

    # ---- THE WIRE HALF -----------------------------------------------------
    sym = lst_symbols(lst)
    label = "EditorRaster_OJZ_Act1_%s" % a.preset
    if label not in sym:
        raise SystemExit(f"{lst}: no symbol {label!r}. Either this listing is not from a "
                         f"build that carries the document, or the generated label spelling "
                         f"moved. Refusing to measure a program this ROM may not contain.")
    at = sym[label]
    blob = rom.read_bytes()[at:at + REC_SIZE]
    rec = decode_record(blob)
    want = {
        "rrp_arm0":    raster_arm(1, top - 1),
        "rrp_arm1":    raster_arm(top - 1, top),
        "rrp_cmd":     vdp_comm_vsram_write(addr),
        "rrp_lines":   lines,
        "rrp_start":   u32_image(start_v),
        "rrp_step":    u32_image(step_v),
    }
    print("THE WIRE FORM  %s @ $%06X in %s" % (label, at, rom.name))
    print("  %s" % blob.hex())
    bad = []
    for k in ("rrp_arm0", "rrp_arm1", "rrp_cmd", "rrp_lines", "rrp_start", "rrp_step"):
        ok = rec[k] == want[k]
        bad += [] if ok else [k]
        print("  %-10s ROM $%08X   document -> $%08X   %s"
              % (k, rec[k], want[k], "ok" if ok else "*** MISMATCH ***"))
    print("  top, read back out of rrp_arm0: %d   (document says %d)"
          % (top_from_arm0(rec["rrp_arm0"]), top))
    print("  rrp_step as a SIGNED long: %+d = %+.4f px/line"
          % (rec["rrp_step"] - 0x100000000 if rec["rrp_step"] >= 0x80000000
             else rec["rrp_step"],
             (rec["rrp_step"] - 0x100000000 if rec["rrp_step"] >= 0x80000000
              else rec["rrp_step"]) / 65536))
    if bad:
        raise SystemExit("WIRE FORM DOES NOT HONOUR THE DOCUMENT: %s. Stopping before the "
                         "picture half — a picture measured against a record that already "
                         "disagrees with the document measures the wrong thing." % bad)
    print("  -> the ROM record matches the document in every field.")
    print()
    if a.wire_only:
        return 0

    # ---- THE PICTURE HALF --------------------------------------------------
    print("ARM 1  CONTROL vs CONTROL")
    p0, m0, base, t0 = run(str(rom), str(lst), sym)
    p0b, m0b, base2, t0b = run(str(rom), str(lst), sym)
    same = sum(1 for (l, x), (_, y) in zip(base, base2) if x == y)
    print("  %d of %d lines identical  (want all)" % (same, len(base)))
    print("  VDP shadow reg $0B at capture: %s / %s" % (m0, m0b))
    print("  frame bracket A: %s .. %s   B: %s .. %s   (strictly advancing, no rewind)"
          % (t0[0], t0[-1], t0b[0], t0b[-1]))
    if same != len(base):
        print("  -> the two instances are NOT reproducing each other; nothing below is "
              "attributable. STOPPING.")
        return 1
    print()

    print("ARM 2  RAMP vs CONTROL")
    p1, m1, rampr, t1 = run(str(rom), str(lst), sym, install=at)
    inside = [l for (l, x), (_, y) in zip(base, rampr) if x != y and d_lo <= l <= d_hi]
    outside = [l for (l, x), (_, y) in zip(base, rampr) if x != y and not (d_lo <= l <= d_hi)]
    firsts = [l for (l, x), (_, y) in zip(base, rampr) if x != y]
    print("  control Raster_Program = %s     ramp Raster_Program = %s" % (p0, p1))
    print("  VDP shadow reg $0B at capture: %s" % m1)
    print("  frame bracket: %s .. %s   (strictly advancing, no rewind)" % (t1[0], t1[-1]))
    print("  changed INSIDE the displayed span %d..%d : %d of %d"
          % (d_lo, d_hi, len(inside), d_hi - d_lo + 1))
    print("  changed OUTSIDE it                       : %d %s"
          % (len(outside), sorted(outside) if len(outside) <= 12 else ""))
    print("  first differing line                     : %s" % (firsts[0] if firsts else None))
    print("  NOTE: arm 2 CANNOT separate the ramp from the program replacement. That is "
          "arm 3's job.")
    print()

    print("ARM 3  RAMP vs ITS OWN STEP-0 TWIN  (the replacement held constant EXACTLY)")
    twin = bytearray(blob)
    off = field_offset("rrp_step")
    twin[off:off + 4] = (0).to_bytes(4, "big")
    # WHERE THE TWIN GOES, DERIVED FROM THE TREE rather than picked. `Game_RAM_End` is the
    # last address any RAM region claims; the ROM header's first longword is the initial
    # stack pointer, and the stack grows DOWN from it. The scratch sits a page above the
    # one and thousands of bytes below the other, and both margins are asserted here rather
    # than asserted in prose.
    ram_end = sym["Game_RAM_End"]
    init_sp = int.from_bytes(rom.read_bytes()[0:4], "big")
    scratch = (ram_end + 0x1DA) & ~1          # a page-ish above the last claimed byte, even
    if not (ram_end < scratch and scratch + REC_SIZE + 0x800 < init_sp):
        raise SystemExit(
            "no safe scratch for the step-0 twin: Game_RAM_End $%08X, initial SP $%08X, "
            "candidate $%08X. Refusing to place a control record where it might be the "
            "stack or a RAM region." % (ram_end, init_sp, scratch))
    print("  twin at $%08X   (Game_RAM_End $%08X, initial SP $%08X, %d bytes of stack "
          "headroom below it)" % (scratch, ram_end, init_sp, init_sp - scratch))
    p2, m2, flat, t2 = run(str(rom), str(lst), sym, install=scratch,
                           patch=(scratch, bytes(twin)))
    print("  twin Raster_Program = %s   (the subject's own 34 bytes with rrp_step zeroed)"
          % p2)
    print("  VDP shadow reg $0B at capture: %s" % m2)
    print("  frame bracket: %s .. %s   (strictly advancing, no rewind)" % (t2[0], t2[-1]))
    diff = [l for (l, x), (_, y) in zip(flat, rampr) if x != y]
    d_in = [l for l in diff if d_lo <= l <= d_hi]
    d_out = [l for l in diff if not (d_lo <= l <= d_hi)]
    print("  lines differing between the RAMP and its STEP-0 twin: %d" % len(diff))
    print("    inside  the displayed span %d..%d : %d of %d"
          % (d_lo, d_hi, len(d_in), d_hi - d_lo + 1))
    print("    outside it                        : %d %s"
          % (len(d_out), sorted(d_out) if len(d_out) <= 12 else ""))
    print("  first line attributable to the STEP : %s" % (diff[0] if diff else None))
    print("  last  line attributable to the STEP : %s" % (diff[-1] if diff else None))
    print("  -> the two programs differ in FOUR BYTES, so every line above is the step.")
    print()

    # -----------------------------------------------------------------------
    # ARM 4 — WHICH LINES DOES THE RUN ACTUALLY REACH?
    #
    # Arms 2 and 3 both answer "where did the RAMP change the picture", and a ramp can be
    # visually degenerate on a line: at the top of a run the accumulator is still small, so
    # a line the run genuinely writes can render IDENTICALLY to one it does not. That is a
    # real ambiguity and it is not resolvable by looking harder at arm 3 — "changed" and
    # "written" are different questions.
    #
    # So arm 4 asks the WRITTEN question directly, with two FLAT twins: both the subject's
    # own record with step 0, differing only in `rrp_start`. Every line the run reaches gets
    # a constant offset, and the two constants differ, so EVERY reached line differs and no
    # unreached line can. The first and last differing lines ARE the displayed span, with no
    # dependence on the document's own step being visible at any particular line.
    #
    # The offset is -37 px and the oddness is deliberate: plane B is 64 tiles tall and a
    # round multiple of the 8-pixel tile height could alias against a vertically periodic
    # background and produce a false "unreached".
    print("ARM 4  THE SPAN ITSELF  (two FLAT twins, step 0, differing only in rrp_start)")
    probe_px = -37
    flat_a = bytearray(blob)
    flat_a[field_offset("rrp_step"):field_offset("rrp_step") + 4] = (0).to_bytes(4, "big")
    flat_a[field_offset("rrp_start"):field_offset("rrp_start") + 4] = (0).to_bytes(4, "big")
    flat_b = bytearray(flat_a)
    flat_b[field_offset("rrp_start"):field_offset("rrp_start") + 4] =         u32_image(fp16(probe_px, 0)).to_bytes(4, "big")
    pa, ma, rows_a, ta = run(str(rom), str(lst), sym, install=scratch,
                             patch=(scratch, bytes(flat_a)))
    pb, mb, rows_b, tb = run(str(rom), str(lst), sym, install=scratch,
                             patch=(scratch, bytes(flat_b)))
    print("  VDP shadow reg $0B at capture: %s / %s" % (ma, mb))
    print("  frame brackets: %s..%s and %s..%s   (strictly advancing, no rewind)"
          % (ta[0], ta[-1], tb[0], tb[-1]))
    reached = [l for (l, x), (_, y) in zip(rows_a, rows_b) if x != y]
    if not reached:
        print("  *** the two flat twins are IDENTICAL on every line — the run reached "
              "nothing, or a %+d px plane-B offset is invisible in this scene. This arm "
              "measured NOTHING; do not read it as a span of zero." % probe_px)
    else:
        gaps = [l for l in range(reached[0], reached[-1] + 1) if l not in set(reached)]
        print("  offset %+d px changes lines %d..%d, %d of them, %d interior gap(s) %s"
              % (probe_px, reached[0], reached[-1], len(reached), len(gaps),
                 gaps if len(gaps) <= 12 else ""))
        print("  MEASURED DISPLAY SPAN  : %d..%d" % (reached[0], reached[-1]))
        print("  DERIVED DISPLAY SPAN   : %d..%d" % (d_lo, d_hi))
        print("  agreement              : %s"
              % ("EXACT" if (reached[0], reached[-1]) == (d_lo, d_hi)
                 else "top %+d, bottom %+d" % (reached[0] - d_lo, reached[-1] - d_hi)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
