#!/usr/bin/env python3
"""v1_reference — the v1 behaviour reference: replayable inputs + per-frame hashes and semantic
fields (Empyrean v2 step 0, E1).

WHY. v2 rewrites the engine. The continuity rule says v1 master stays the behaviour reference,
so before anything is rewritten v1's behaviour is captured in a form a LATER engine can be
diffed against -- even one with a different RAM layout:

  * `<shape>/<leg>.inputs.json` -- the InputLog `{t0, held}` the closed-loop policy produced
    (tools/leg_drive.py). Replaying it open-loop (`leg_drive.Replay`) re-applies exactly those
    bytes, one per Logic_Tick, at the same Input_Tick seam.
  * `<shape>/<leg>.frames.jsonl.gz` -- one row per tick (ROW_FIELDS):
      - RAW hashes (same-layout regression only): `fb` = state_hash{includeFramebuffer}
        .framebuffer, `vdp` = .combined, `obj_ram` = memory_hash over Object_RAM ..
        Object_RAM_End, `game_ram` = memory_hash over the game RAM block (Engine_RAM_End, where
        games/sonic4/config/ram.emp's `game_ram @ after(upper_ram)` begins, .. Game_RAM_End).
      - SEMANTIC plain values (diffable across layouts): held, px, py, xvel, yvel, status (the
        leader's SST status byte), cx, cy, lag_before (dFrame_Counter - dLogic_Tick into this
        tick: the lag frames that preceded it).
  * `MANIFEST.json` -- per recording: provenance (tools/leg_provenance.py), status, ticks,
    wall-clock, file sha256s; plus the determinism diff and oracle's replay_runner verdict.

`record` REFUSES to write from a dirty aeon tree (Task 2 review carry-over): a reference whose
source cannot be named by a commit is not a reference. A replay made for a proof on a
deliberately dirty tree passes `allow_dirty` and is stamped `reference_grade: false`.

`diff` answers, per (shape, leg), None (identical over the chosen fields) or the first
divergent (Logic_Tick, field); a leg present on one side only, or with no rows, is
DID NOT RUN -- never equal.

    v1_reference.py record --rom s4.bin --lst s4.lst --leg run --out DIR
    v1_reference.py replay --rom s4.bin --lst s4.lst --leg run --ref REFDIR --out DIR
    v1_reference.py diff --ref REFDIR --run DIR [--semantic | --fields px,py]
"""
from __future__ import annotations

import argparse
import asyncio
import gzip
import hashlib
import io
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import leg_drive as ld  # noqa: E402
import leg_provenance as lp  # noqa: E402

ROW_FIELDS = ("tick", "held", "fb", "vdp", "obj_ram", "game_ram", "px", "py", "xvel", "yvel",
              "status", "cx", "cy", "lag_before")
RAW_HASHES = ("fb", "vdp", "obj_ram", "game_ram")
SEMANTIC = ("held", "px", "py", "xvel", "yvel", "status", "cx", "cy", "lag_before")
ALL = ("held",) + RAW_HASHES + SEMANTIC[1:]
DID_NOT_RUN = "DID NOT RUN"
ROW_MISSING = "<row missing>"

#: The E1 scope: phase 0 of the five canonical legs (objheavy/sidekick/stream are stress shapes,
#: not v1 canonical). Caps are leg_run's, so a recording is the same leg leg_run drives.
LEGS = ("idle", "run", "topspeed", "diagfall", "spindash")
CAP = {"idle": ld.IDLE_NEED_TICKS, "run": 3000, "topspeed": 3000, "diagfall": 3000,
       "spindash": 3000}
PHASE = 0

#: name -> (start symbol, end symbol) of each hashed RAM block, both from the build's listing.
RAM_BLOCKS = {"obj_ram": ("Object_RAM", "Object_RAM_End"),
              "game_ram": ("Engine_RAM_End", "Game_RAM_End")}


class DirtyTree(RuntimeError):
    """The aeon tree is dirty: no reference is written from it."""


# ---- frame files ----------------------------------------------------------------------------

def write_frames(path: Path, rows: list) -> None:
    """gzip'd JSON lines, byte-deterministic (mtime 0, no filename in the header)."""
    raw = "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows).encode()
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0, compresslevel=9) as g:
        g.write(raw)
    Path(path).write_bytes(buf.getvalue())


def read_frames(path: Path) -> list:
    with gzip.open(path, "rt") as g:
        return [json.loads(ln) for ln in g if ln.strip()]


def frame_row(s: ld.TickState, drow: dict, status_byte: int, hashes: dict) -> dict:
    """One reference row from the drive's TickState and LegCore row (`dfc`, `dlt`, `held`)."""
    return dict(tick=s.tick, held=drow["held"], fb=hashes["fb"], vdp=hashes["vdp"],
                obj_ram=hashes["obj_ram"], game_ram=hashes["game_ram"], px=s.px, py=s.py,
                xvel=s.xvel, yvel=s.yvel, status=status_byte, cx=s.cx, cy=s.cy,
                lag_before=drow["dfc"] - drow["dlt"])


# ---- diff -----------------------------------------------------------------------------------

@dataclass
class DiffReport:
    #: (shape, leg) -> None (identical) | (first Logic_Tick, field) | DID_NOT_RUN
    results: dict

    @property
    def ok(self) -> bool:
        return bool(self.results) and all(v is None for v in self.results.values())

    def lines(self) -> list[str]:
        out = []
        for (sh, leg), v in sorted(self.results.items()):
            if v is None:
                out.append(f"{sh}/{leg}: identical")
            elif v == DID_NOT_RUN:
                out.append(f"{sh}/{leg}: DID NOT RUN")
            else:
                out.append(f"{sh}/{leg}: DIVERGES at tick {v[0]} on {v[1]}")
        return out


def _frame_path(d: Path, shape: str, leg: str) -> Path:
    return Path(d) / shape / f"{leg}.frames.jsonl.gz"


def _legs_in(d: Path) -> set:
    d = Path(d)
    got = {(p.parent.name, p.name[:-len(".frames.jsonl.gz")])
           for p in d.glob("*/*.frames.jsonl.gz")} if d.is_dir() else set()
    m = d / "MANIFEST.json"
    if m.is_file():
        for k in json.loads(m.read_text()).get("recordings", {}):
            sh, _, leg = k.rpartition("/")
            got.add((sh, leg))
    return got


def _first_divergence(a: list, b: list, fields, where: str):
    ia, ib = {r["tick"]: r for r in a}, {r["tick"]: r for r in b}
    for t in sorted(set(ia) | set(ib)):
        ra, rb = ia.get(t), ib.get(t)
        if ra is None or rb is None:
            return (t, ROW_MISSING)
        for f in fields:
            if f not in ra or f not in rb:
                raise ValueError(f"{where}: tick {t} row lacks field {f!r}: unmeasurable")
            if ra[f] != rb[f]:
                return (t, f)
    return None


def diff(ref_dir: Path, run_dir: Path, fields: tuple = ALL) -> DiffReport:
    bad = [f for f in fields if f not in ALL]
    if bad or not fields:
        raise ValueError(f"unknown field(s) {bad} (known: {ALL})")
    res = {}
    for sh, leg in sorted(_legs_in(ref_dir) | _legs_in(run_dir)):
        pa, pb = _frame_path(ref_dir, sh, leg), _frame_path(run_dir, sh, leg)
        if not (pa.is_file() and pb.is_file()):
            res[(sh, leg)] = DID_NOT_RUN
            continue
        a, b = read_frames(pa), read_frames(pb)
        if not a or not b:
            res[(sh, leg)] = DID_NOT_RUN
            continue
        res[(sh, leg)] = _first_divergence(a, b, fields, f"{sh}/{leg}")
    return DiffReport(res)


# ---- recording ------------------------------------------------------------------------------

@dataclass
class RecordStats:
    shape: str
    leg: str
    mode: str                 # "closed-loop" (the policy; its InputLog is saved) | "replay"
    status: str
    reason: str
    ticks: int
    t0: int
    first_tick: int
    last_tick: int
    lag_frames: int
    wall_s: float
    inputs_sha256: str
    frames_sha256: str
    frames_bytes: int
    reference_grade: bool


def _ram_spans(syms) -> dict:
    out = {}
    for name, (lo, hi) in RAM_BLOCKS.items():
        if lo not in syms.addr or hi not in syms.addr:
            raise ld.DriveError(f"{syms.lst}: no `{lo}`/`{hi}` label; cannot bound {name}")
        n = syms.addr[hi] - syms.addr[lo]
        if n <= 0:
            raise ld.DriveError(f"{name}: {hi} <= {lo} in {syms.lst}")
        out[name] = (lo, syms.addr[lo], n)
    return out


async def _hashes(c, spans: dict) -> dict:
    sh = await c.call("emulator/state_hash", {"includeFramebuffer": True})
    if sh.get("displayMask") not in ([], None):
        raise ld.DriveError(f"state_hash under a display mask {sh['displayMask']}: the "
                            "framebuffer digest is not the machine's picture")
    out = {"fb": sh["framebuffer"], "vdp": sh["combined"]}
    for name, (sym, addr, n) in spans.items():
        r = await c.call("emulator/memory_hash", {"symbol": sym, "len": n})
        if int(ld._unhex(r["addr"]), 16) & 0xFFFFFF != addr or r["len"] != n:
            raise ld.DriveError(f"memory_hash {sym}: served {r['addr']}+{r['len']}, listing "
                                f"says ${addr:06X}+{n}")
        out[name] = r["fnv1a64"]
    return out


async def _status_byte(c, syms) -> int:
    tgt = ld._be(await ld._rd(c, syms.addr["Camera_Target"], 2), 0, 2)
    leader = (0xFF0000 | tgt) if tgt & 0x8000 else tgt
    if not leader:
        return -1
    return (await ld._rd(c, leader + syms.off["status"], 1))[0]


async def _drive(inst, syms, spans, policy, t0, cap):
    from suite_paths import add_client_path
    add_client_path()
    from aether import BusClient
    c = BusClient(socket_path=inst.socket_path, client_id=f"v1-reference-{os.getpid()}",
                  client_name="v1_reference")
    await c.connect()
    rows = []
    try:
        await c.call("emulator/reset", {})

        async def on_tick(s, drow):
            rows.append(frame_row(s, drow, await _status_byte(c, syms), await _hashes(c, spans)))

        tr = await ld.drive_leg(c, syms, policy, t0=t0, cap_ticks=cap, on_tick=on_tick)
    finally:
        await c.close()
    return tr, rows


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _manifest_update(out: Path, key: str, entry: dict) -> None:
    m = Path(out) / "MANIFEST.json"
    doc = json.loads(m.read_text()) if m.is_file() else {}
    doc.setdefault("schema", {
        "what": "v1 behaviour reference (Empyrean v2 E1), tools/v1_reference.py",
        "row_fields": list(ROW_FIELDS), "semantic": list(SEMANTIC),
        "raw_hashes": list(RAW_HASHES), "ram_blocks": RAM_BLOCKS,
        "fb": "the framebuffer digest of the state_hash method with includeFramebuffer:true (FNV-1a-64 of RGB)",
        "vdp": "the combined digest of the state_hash method",
        "ram_hash": "the fnv1a64 of the memory_hash method over {symbol, len}",
        "tick": "Logic_Tick at the Input_Tick hit; held = the byte written at that hit",
        "lag_before": "dFrame_Counter - dLogic_Tick into this tick"})
    doc.setdefault("recordings", {})[key] = entry
    tmp = m.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    tmp.replace(m)


def record(rom, lst, leg: str, out: Path, inputs: ld.InputLog | None = None,
           allow_dirty: bool = False, cap: int | None = None) -> RecordStats:
    """Drive `leg` on `rom` from reset and write out/<shape>/<leg>.{inputs.json,frames.jsonl.gz}
    plus its MANIFEST entry. Without `inputs` the drive is the closed-loop policy (phase 0) and
    its InputLog is saved as the replay; with `inputs` it is the open-loop replay of that log."""
    if leg not in LEGS:
        raise ValueError(f"leg {leg!r} is not in the E1 scope {LEGS} (objheavy/sidekick/stream "
                         "are stress shapes, not v1 canonical)")
    rom, lst, out = Path(rom).resolve(), Path(lst).resolve(), Path(out)
    syms = ld.resolve_syms(lst)
    spans = _ram_spans(syms)
    if inputs is None:
        policy, t0, n = ld.POLICIES[leg](syms.buttons, syms.equ), ld.T0 + ld.PHASE_OFFSETS[PHASE], \
            cap or CAP[leg]
    else:
        policy = ld.Replay(inputs)
        t0, n = inputs["t0"], len(inputs["held"])
    wall0 = time.monotonic()
    inst = lp.spawn_pinned(rom, lst)
    try:
        prov = lp.provenance(lp.load_pin(), inst.handshake, rom, lst)
        a = prov["aeon"]
        if a["dirty"] and not allow_dirty:
            raise DirtyTree(f"aeon tree {a['commit'][:12]} is dirty ({a.get('dirty_count')} "
                            f"path(s)): {a.get('dirty_paths')} -- a reference is never written "
                            "from a dirty tree; commit or remove them")
        tr, rows = asyncio.run(_drive(inst, syms, spans, policy, t0, n))
    finally:
        inst.reap()
    wall = time.monotonic() - wall0
    prov["harness"]["v1_reference_sha256"] = lp.sha256_file(Path(__file__).resolve())
    prov["harness"]["leg_drive_sha256"] = lp.sha256_file(TOOLS / "leg_drive.py")
    lp.require_provenance(prov)
    if inputs is not None and tr.input_log != {"t0": t0, "held": list(inputs["held"])}:
        raise ld.DriveError("the replay applied bytes that differ from its InputLog")
    if len(rows) != len(tr.rows) or not rows:
        raise ld.DriveError(f"{len(rows)} frame rows for {len(tr.rows)} driven ticks")
    shape = rom.stem
    d = out / shape
    d.mkdir(parents=True, exist_ok=True)
    ip, fp = d / f"{leg}.inputs.json", d / f"{leg}.frames.jsonl.gz"
    ip.write_text(json.dumps(tr.input_log, separators=(",", ":")) + "\n")
    write_frames(fp, rows)
    st = RecordStats(shape=shape, leg=leg, mode="closed-loop" if inputs is None else "replay",
                     status=tr.status, reason=tr.reason, ticks=len(rows), t0=t0,
                     first_tick=rows[0]["tick"], last_tick=rows[-1]["tick"],
                     lag_frames=tr.lag_frames, wall_s=round(wall, 2), inputs_sha256=_sha(ip),
                     frames_sha256=_sha(fp), frames_bytes=fp.stat().st_size,
                     reference_grade=not prov["aeon"]["dirty"])
    _manifest_update(out, f"{shape}/{leg}", dict(asdict(st), phase=PHASE, notes=tr.notes,
                                                 provenance=prov,
                                                 date_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                                        time.gmtime())))
    return st


# ---- CLI ------------------------------------------------------------------------------------

def _could_not_run():
    from suite_paths import add_client_path
    add_client_path()
    from aether import BusError
    return (DirtyTree, lp.StalePair, lp.PinMismatch, lp.MissingProvenance, ld.DriveError,
            BusError, ConnectionError, EOFError, asyncio.IncompleteReadError, TimeoutError,
            OSError)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("record", "replay"):
        p = sub.add_parser(name)
        p.add_argument("--rom", required=True)
        p.add_argument("--lst", required=True)
        p.add_argument("--leg", required=True, choices=LEGS)
        p.add_argument("--out", required=True)
        if name == "replay":
            p.add_argument("--ref", required=True, help="reference dir holding the inputs.json")
            p.add_argument("--allow-dirty", action="store_true",
                           help="proof runs only: the output is stamped reference_grade=false")
    p = sub.add_parser("diff")
    p.add_argument("--ref", required=True)
    p.add_argument("--run", required=True)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--semantic", action="store_true")
    g.add_argument("--fields")
    p = sub.add_parser("annotate", help="set a top-level MANIFEST key from a JSON file")
    p.add_argument("--out", required=True)
    p.add_argument("--key", required=True)
    p.add_argument("--json", required=True)
    a = ap.parse_args(argv)

    if a.cmd == "diff":
        fields = SEMANTIC if a.semantic else (tuple(a.fields.split(",")) if a.fields else ALL)
        rep = diff(Path(a.ref), Path(a.run), fields)
        for ln in rep.lines():
            print(ln)
        n = len(rep.results)
        same = sum(v is None for v in rep.results.values())
        print(f"diff: {same}/{n} identical over {len(fields)} field(s)"
              + ("" if rep.ok else " -- NOT EQUAL"))
        return 0 if rep.ok else 1
    if a.cmd == "annotate":
        if a.key in ("schema", "recordings"):
            print(f"v1_reference: `{a.key}` is written by record, not annotate", file=sys.stderr)
            return 2
        m = Path(a.out) / "MANIFEST.json"
        doc = json.loads(m.read_text())
        doc[a.key] = json.loads(Path(a.json).read_text())
        m.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
        return 0
    inputs = None
    if a.cmd == "replay":
        src = Path(a.ref) / Path(a.rom).stem / f"{a.leg}.inputs.json"
        try:
            inputs = json.loads(src.read_text())
        except (OSError, ValueError) as e:
            print(f"v1_reference: COULD NOT RUN -- {src}: {e}", file=sys.stderr)
            return 2
    try:
        st = record(a.rom, a.lst, a.leg, Path(a.out), inputs=inputs,
                    allow_dirty=getattr(a, "allow_dirty", False))
    except _could_not_run() as e:
        print(f"v1_reference: COULD NOT RUN {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    print(f"{st.shape}/{st.leg} {st.mode}: {st.status} ({st.reason}); {st.ticks} ticks "
          f"{st.first_tick}..{st.last_tick}; lag {st.lag_frames}; frames {st.frames_bytes} B; "
          f"wall {st.wall_s}s{'' if st.reference_grade else '; NOT reference grade (dirty)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
