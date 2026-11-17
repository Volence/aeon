#!/usr/bin/env python3
"""vblank_dma_probe — when does the LAST DMA of each VBlank end? (Empyrean v2 step 0, B3)

WHY. VBlank work is judged by when the last DMA ends, not by the handler's `rte`: the tail
after the last DMA is CPU work that may run into the picture, a DMA that does may not. The
audit's two earlier figures ("rte at line 260", "102% of the window") both timed the handler
(Oracle fitness finding 3, oracle/docs/audits/Oracle fitness.md:75-80); the reviewer's worst
DEBUG frame was last-DMA-end line 257 + 2,097 mclk.

METHOD (fitness plan item 3, harness version).
  * Sites. Every instruction that writes the LAST command word of a 14-byte DMA entry to the
    VDP control port, inside the two drain bodies `Process_DMA_Critical` and
    `Drain_Budgeted_Queue` (engine/system/dma_queue.emp:303-321, 359-474), bounded by their
    listing labels. That word is the `move.w (An)+,(a5)` that ends each `move.l x3, move.w`
    group; writing it is what starts the DMA. The listing sigil emits publishes LABELS, not
    instruction lines (MEASURED: its sections are the Source Digest, the code labels, the
    Symbol Table, the Equate Table and the Phase Table), so the instruction bytes come from
    the ROM the listing vouches for (`artifact_provenance.check_pair`, run by leg_run before
    any probe). Anchors come from the listing's LABEL LINES (the harness's symbol dict holds
    no `$` locals): Process_DMA_Critical's sites are EXACTLY one per `$drain_k` label (at
    label + 6, k = 1..DMA_CRITICAL_SLOTS when that equate is published), and the scan may find
    no other group; Drain_Budgeted_Queue has exactly one group, after its `$loop` label. Any
    mismatch is `NoTriggerSites` (unmeasurable), never a probe silently watching fewer DMAs.
  * Timing. Break on each site: `start = reply.mclk`; then `emulator/step {count: 1}`:
    `end = reply.mclk`. Oracle charges the DMA's CPU stall to the triggering instruction, so
    the step's return time is the DMA end on Oracle's model (MEASURED model; hardware's
    correction is Task 4's).
  * Calibration. A breakpoint at `VBlank_Handler` must compute the listing's `SCREEN_HEIGHT`
    (224) on every frame (mclk mod 262 x MCLK_PER_LINE is the line). Any other value, a site
    hit outside a calibrated VBlank, a step that does not land on site + 2, no VBlank seen,
    or no sites at all makes the WHOLE probe `unmeasurable` (a loud string), never a number.
  * Check. An event whose end is after `DMA_END_LIMIT_LINE` + 0 mclk is an overrun. Lines are
    relative to the VBlank's own frame and are NOT wrapped: a DMA ending in the next frame
    reads line >= 262, never line 0.

STATED LIMIT (scope). Only DMAs triggered from the two drain bodies are seen. Everything
else VBlank does to the VDP (the level-mode callees: VInt_DrawLevel's nametable writes,
Vscroll_Write, register writes) is CPU port writes, not DMA, and is outside this probe; a DMA
added anywhere else would be invisible to it until its trigger site is added here.

"No DMA this VBlank" (a calibrated VBlank with 0 events; `worst_end.status == "NO DMA"` when
the whole window had none) and "the probe cannot see" (`unmeasurable`) are different results.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

import leg_correction as lc
# The probe only ever runs on a client from `leg_provenance.spawn_pinned` (the pinned Rust
# oracle-aether); importing it declares that seam to tools/test_legacy_seam_keys.py, which
# otherwise reads a library handed a client as "ambient" (legacy-server vocabulary) -- the
# same declaration leg_drive.py makes.
import leg_provenance as _lp  # noqa: F401,E402

LINES_PER_FRAME = 262                       # NTSC (PAL is out of scope: fitness finding 8)
FRAME_MCLK = LINES_PER_FRAME * lc.MCLK_PER_LINE     # 896,040

DRAIN_PROCS = ("Process_DMA_Critical", "Drain_Budgeted_Queue")


def _move_an_postinc_to_a5(size_bits: int, n: int) -> int:
    """MOVE <size> (An)+,(a5): 00 SS 101 010 011 nnn (dst reg 5, mode (An); src mode (An)+)."""
    return (size_bits << 12) | (5 << 9) | (2 << 6) | (3 << 3) | n


MOVE_L = {n: _move_an_postinc_to_a5(0b10, n) for n in range(8)}     # $2A98 | n
MOVE_W = {n: _move_an_postinc_to_a5(0b11, n) for n in range(8)}     # $3A98 | n


class NoTriggerSites(RuntimeError):
    """The drain bodies or their trigger instructions could not be resolved: the probe cannot
    see, which is never the same as "no DMA"."""


_LABEL = re.compile(r"^\((\d+)\)\s+\d+/([0-9A-Fa-f]+)\s*:\s+(\S+):\s*$")


def _labels(lst_text: str) -> list[tuple[int, int, str]]:
    """(section, address, name) for every code-label line of the listing, locals included.
    The harness's symbol dict (`leg_drive.parse_listing`) holds NO `$`-prefixed locals, so the
    label lines are the only place the drain_k / loop anchors exist."""
    out = []
    for ln in lst_text.splitlines():
        m = _LABEL.match(ln.strip())
        if m:
            out.append((int(m.group(1)), int(m.group(2), 16), m.group(3)))
    return out


_EQU = re.compile(r"^EQU\s+([A-Za-z_]\w*)\s*=\s*\$([0-9A-Fa-f]+)\s*$")


def _equ(lst_text: str, name: str) -> int | None:
    for ln in lst_text.splitlines():
        m = _EQU.match(ln.strip())
        if m and m.group(1) == name:
            return int(m.group(2), 16)
    return None


def proc_bounds(lst_text: str, labels=None) -> dict:
    """{proc: (start, end)} for each DRAIN_PROCS proc found in the listing's label lines. `end`
    is the next non-local label (a `$`-prefixed name is a local or an asm-block label) in the
    same listing section."""
    labels = _labels(lst_text) if labels is None else labels
    out = {}
    for sec, addr, name in labels:
        if name in DRAIN_PROCS:
            nxt = [a for s, a, n in labels if s == sec and a > addr and not n.startswith("$")]
            if nxt:
                out[name] = (addr, min(nxt))
    return out


def _word(rom: bytes, a: int) -> int:
    if a < 0 or a + 2 > len(rom):
        raise NoTriggerSites(f"${a:X} is outside the ROM ({len(rom)} bytes)")
    return int.from_bytes(rom[a:a + 2], "big")


def _group_end_at(rom: bytes, a: int) -> bool:
    """Is `a` the move.w that ends a `move.l (An)+,(a5) x3; move.w (An)+,(a5)` group?"""
    if a < 6:
        return False
    w = _word(rom, a)
    n = next((k for k, v in MOVE_W.items() if v == w), None)
    return n is not None and all(_word(rom, a - 2 * i) == MOVE_L[n] for i in (1, 2, 3))


_DRAIN_K = re.compile(r"\$Process_DMA_Critical\$drain_(\d+)$")


def _critical_sites(proc, lo, hi, labels, scan, rom, lst_text) -> list[int]:
    """Exactly one site at each `$Process_DMA_Critical$drain_k` label + 6, k = 1..N, N equal
    to the listing's DMA_CRITICAL_SLOTS when published; the scan may find nothing else."""
    anchors = sorted((int(m.group(1)), a, n) for _s, a, n in labels
                     if lo <= a < hi and (m := _DRAIN_K.search(n)))
    if not anchors:
        raise NoTriggerSites(f"`{proc}`: no `$drain_k` label lines in the listing to anchor on")
    ks = [k for k, _a, _n in anchors]
    if ks != list(range(1, len(ks) + 1)):
        raise NoTriggerSites(f"`{proc}`: drain labels are k={ks}, not 1..{len(ks)}")
    slots = _equ(lst_text, "DMA_CRITICAL_SLOTS")
    if slots is not None and len(anchors) != slots:
        raise NoTriggerSites(f"`{proc}`: {len(anchors)} drain_k labels != DMA_CRITICAL_SLOTS "
                             f"{slots}")
    want = []
    for _k, a, name in anchors:
        if not _group_end_at(rom, a + 6):
            got = " ".join(f"{_word(rom, a + 2 * i):04X}" for i in range(4))
            raise NoTriggerSites(f"`{name}` (${a:X}): no `move.l x3; move.w (An)+,(a5)` group "
                                 f"ending at label + 6; words there are {got}")
        want.append(a + 6)
    extra = sorted(set(scan) - set(want))
    if extra:
        raise NoTriggerSites(f"`{proc}`: group(s) at {[hex(x) for x in extra]} carry no "
                             "drain_k label")
    return want


def _budgeted_sites(proc, lo, hi, labels, scan) -> list[int]:
    """Exactly one group (dma_queue.emp:461-474), lying after `$Drain_Budgeted_Queue$loop`."""
    loop = [a for _s, a, n in labels if n.endswith(f"${proc}$loop") and lo <= a < hi]
    if len(loop) != 1:
        raise NoTriggerSites(f"`{proc}`: expected one `$loop` label line, found {len(loop)}")
    if len(scan) != 1 or scan[0] < loop[0]:
        raise NoTriggerSites(f"`{proc}`: expected exactly one group after `$loop` "
                             f"(${loop[0]:X}), found {[hex(x) for x in scan]}")
    return scan


def dma_trigger_sites(lst_text: str, symbols: dict, rom: bytes) -> list[int]:
    """Every DMA trigger site in the two drain bodies, sorted. `symbols` is the listing's
    symbol table (name -> address; it holds no locals) and must agree with the label lines;
    the anchors (drain_k, loop) and the DMA_CRITICAL_SLOTS equate are read from the listing
    TEXT; `rom` is the ROM the listing describes (the listing carries no instruction bytes).
    Any shape mismatch raises NoTriggerSites: a changed drain is refused, never read as less
    DMA."""
    labels = _labels(lst_text)
    bounds = proc_bounds(lst_text, labels)
    sites = []
    for proc in DRAIN_PROCS:
        if proc not in bounds:
            raise NoTriggerSites(f"`{proc}` (a drain body) has no bounded label in the listing")
        lo, hi = bounds[proc]
        if symbols.get(proc) != lo:
            got = symbols.get(proc)
            raise NoTriggerSites(f"`{proc}`: symbol table ${got:X} != label ${lo:X}"
                                 if got is not None else f"`{proc}` is not in the symbol table")
        scan = [a for a in range(lo + 6, hi - 1, 2) if _group_end_at(rom, a)]
        if proc == "Process_DMA_Critical":
            sites += _critical_sites(proc, lo, hi, labels, scan, rom, lst_text)
        else:
            sites += _budgeted_sites(proc, lo, hi, labels, scan)
    return sorted(sites)


def line_of(mclk: int) -> tuple[int, int]:
    """(line, mclk into the line) within its frame of FRAME_MCLK."""
    m = mclk % FRAME_MCLK
    return m // lc.MCLK_PER_LINE, m % lc.MCLK_PER_LINE


@dataclass(frozen=True)
class DmaEvent:
    tick: int
    vblank: int
    site: int
    start_line: int
    start_off: int
    end_line: int
    end_off: int
    #: Opt-in (DmaProbe `site_regs`, v2 C3): the entry's VDP command decoded at the trigger
    #: site, BEFORE the step -- the VRAM/CRAM/VSRAM byte address and the CD code (VRAM write
    #: DMA = $21). None when the probe was not asked to decode.
    dest: int | None = None
    cd: int | None = None


def decode_command(hi: int, lo: int) -> tuple[int, int]:
    """(address, CD5..CD0) of a VDP command long `hi:lo` (plutiedev's layout: CD1-0 in hi's
    top two bits, A13-0 in hi's low 14, CD5-2 in lo bits 7-4, A15-14 in lo bits 1-0)."""
    addr = (hi & 0x3FFF) | ((lo & 0x3) << 14)
    cd = ((hi >> 14) & 0x3) | ((lo >> 2) & 0x3C)
    return addr, cd


#: CD for a VRAM-write DMA (CD5 DMA + CD0 VRAM write).
CD_VRAM_DMA = 0x21


def _end_key(e: DmaEvent):
    return (e.end_line, e.end_off)


def vblank_end(events) -> DmaEvent | None:
    """The VBlank's end: the event whose DMA ENDS latest (not the last hit, not the rte)."""
    return max(events, key=_end_key, default=None)


def overruns(events) -> list[DmaEvent]:
    """Events ending after DMA_END_LIMIT_LINE + 0 mclk (read at call time)."""
    lim = (lc.DMA_END_LIMIT_LINE, 0)
    return [e for e in events if _end_key(e) > lim]


def _hexpc(v) -> int:
    if isinstance(v, int):
        return v & 0xFFFFFF
    s = str(v)
    return int(s[2:] if s[:2].lower() == "0x" else s.lstrip("$"), 16) & 0xFFFFFF


class DmaProbe:
    """Breakpoints on every trigger site plus `VBlank_Handler` (calibration) and `VInt_Lag`
    (marks a lag VBlank). Shares the drive's client: `drive_leg(on_break=probe.on_break)`.
    The caller sets `probe.tick` to the current Logic_Tick on every row."""

    def __init__(self, sites, vblank_addr: int, lag_addr: int | None, entry_line: int,
                 site_regs: dict | None = None):
        self.sites = sorted(set(sites))
        #: {site: n}: decode each event's destination from the DMAEntry An points into at
        #: the site (`move.w (An)+,(a5)` writes Command's low word; its high word is at
        #: An - 2). None = do not decode (every leg but sidekick: no extra bus calls).
        self.site_regs = site_regs
        self.vblank_addr, self.lag_addr, self.entry_line = vblank_addr, lag_addr, entry_line
        self.events: list[DmaEvent] = []
        self.vblanks: list[dict] = []
        self.unmeasurable: str | None = None
        self.tick: int | None = None
        self.armed = False
        self._bps: list[str] = []
        self._cur: dict | None = None

    def _cannot_see(self, why: str):
        if self.unmeasurable is None:
            self.unmeasurable = why

    async def arm(self, client):
        if not self.sites:
            self._cannot_see("no DMA trigger sites resolved: the probe cannot see the drains")
        addrs = list(self.sites) + [self.vblank_addr] + (
            [self.lag_addr] if self.lag_addr is not None else [])
        for a in addrs:
            if a < 0:
                continue
            r = await client.call("emulator/breakpoint_add", {"addr": hex(a)})
            self._bps.append(r["breakpoint"])
        self.armed = True

    async def disarm(self, client):
        for b in self._bps:
            await client.call("emulator/breakpoint_clear", {"breakpoint": b})
        self._bps = []
        self.armed = False

    async def on_break(self, client, pc, reply) -> bool:
        pc = _hexpc(pc)
        m = int(reply["mclk"])
        if pc == self.vblank_addr:
            line, off = line_of(m)
            self._cur = dict(index=len(self.vblanks), tick=self.tick, entry_line=line,
                             entry_off=off, lag=False, events=0, end_line=None, end_off=None,
                             _mclk=m, _base=m - m % FRAME_MCLK)
            self.vblanks.append(self._cur)
            if line != self.entry_line:
                self._cannot_see(f"VBlank_Handler entered at line {line} + {off} (vblank "
                                 f"{self._cur['index']}, tick {self.tick}); calibration "
                                 f"expects line {self.entry_line} (SCREEN_HEIGHT)")
            return True
        if self.lag_addr is not None and pc == self.lag_addr:
            if self._cur is None or m - self._cur["_mclk"] >= FRAME_MCLK:
                self._cannot_see(f"VInt_Lag hit at ${pc:X} outside a calibrated VBlank")
            else:
                self._cur["lag"] = True
            return True
        if pc not in self.sites:
            return False
        cur = self._cur
        if cur is None or m - cur["_mclk"] >= FRAME_MCLK:
            self._cannot_see(f"DMA site ${pc:X} hit at mclk {m}, outside a calibrated VBlank "
                             f"(tick {self.tick})")
            return True
        dest = cd = None
        if self.site_regs is not None:
            n = self.site_regs.get(pc)
            regs = await client.call("emulator/registers", {})
            an = _hexpc(regs.get(f"a{n}", -1)) if n is not None else -1
            if an < 2:
                self._cannot_see(f"DMA site ${pc:X}: cannot read a{n} to decode the command")
            else:
                r = await client.call("emulator/read_memory", {"addr": hex(an - 2), "len": 4})
                b = bytes.fromhex(str(r["bytes"]).removeprefix("0x").lstrip("$")[:8])
                dest, cd = decode_command(int.from_bytes(b[:2], "big"),
                                          int.from_bytes(b[2:4], "big"))
        s = await client.call("emulator/step", {"count": 1})
        if s.get("stepped") != 1 or "mclk" not in s:
            self._cannot_see(f"step from DMA site ${pc:X} did not step one instruction: {s}")
            return True
        if _hexpc(s.get("pc", -1)) != pc + 2:
            self._cannot_see(f"step from DMA site ${pc:X} landed at {s['pc']}, not ${pc + 2:X} "
                             "(an exception inside the step would fold into the DMA end)")
        end, base, mpl = int(s["mclk"]), cur["_base"], lc.MCLK_PER_LINE
        e = DmaEvent(tick=self.tick, vblank=cur["index"], site=pc,
                     start_line=(m - base) // mpl, start_off=(m - base) % mpl,
                     end_line=(end - base) // mpl, end_off=(end - base) % mpl,
                     dest=dest, cd=cd)
        self.events.append(e)
        cur["events"] += 1
        if cur["end_line"] is None or _end_key(e) > (cur["end_line"], cur["end_off"]):
            cur["end_line"], cur["end_off"] = e.end_line, e.end_off
        return True

    def result(self) -> dict:
        if self.armed is False and not self.vblanks and self.unmeasurable is None:
            self._cannot_see("the probe was never armed")
        if not self.vblanks:
            self._cannot_see("no VBlank_Handler hit while armed: calibration impossible")
        vbs = [{k: v for k, v in vb.items() if not k.startswith("_")} for vb in self.vblanks]
        worst = None
        if self.unmeasurable is None:
            ends = [e for e in (vblank_end([x for x in self.events if x.vblank == vb["index"]])
                                for vb in self.vblanks) if e is not None]
            w = vblank_end(ends)
            worst = ({"line": None, "off": None, "tick": None, "vblank": None,
                      "status": "NO DMA"} if w is None else
                     {"line": w.end_line, "off": w.end_off, "tick": w.tick, "vblank": w.vblank,
                      "site": w.site, "status": "MEASURED"})
        return {
            "status": "UNMEASURABLE" if self.unmeasurable else "MEASURED",
            "sites": self.sites,
            "events": [asdict(e) for e in self.events],
            "worst_end": worst,
            "overruns": [asdict(e) for e in overruns(self.events)],
            "limit": {"line": lc.DMA_END_LIMIT_LINE, "off": 0},
            "entry_line_expected": self.entry_line,
            "vblanks": vbs,
            "unmeasurable": self.unmeasurable,
            "dest_decoded": self.site_regs is not None,
        }


def site_regs_of(sites, rom: bytes) -> dict:
    """{site: n} -- the An of each trigger site's `move.w (An)+,(a5)` (from the ROM word)."""
    out = {}
    for a in sites:
        w = _word(rom, a)
        n = next((k for k, v in MOVE_W.items() if v == w), None)
        if n is None:
            raise NoTriggerSites(f"site ${a:X} is not a move.w (An)+,(a5) (word {w:04X})")
        out[a] = n
    return out


def probe_for(lst_text: str, syms_addr: dict, syms_equ: dict, rom: bytes,
              decode_dest: bool = False) -> DmaProbe:
    """Build the probe from a build's listing + ROM. Whatever cannot be resolved becomes the
    probe's `unmeasurable` (so the leg still runs and the result says so), never a guess."""
    why = None
    try:
        sites = dma_trigger_sites(lst_text, syms_addr, rom)
    except NoTriggerSites as e:
        sites, why = [], f"NoTriggerSites: {e}"
    miss = [n for n in ("VBlank_Handler", "VInt_Lag") if n not in syms_addr]
    if "SCREEN_HEIGHT" not in syms_equ:
        miss.append("EQU SCREEN_HEIGHT")
    p = DmaProbe(sites, vblank_addr=syms_addr.get("VBlank_Handler", -1),
                 lag_addr=syms_addr.get("VInt_Lag"), entry_line=syms_equ.get("SCREEN_HEIGHT", -1))
    if decode_dest and sites:
        try:
            p.site_regs = site_regs_of(sites, rom)
        except NoTriggerSites as e:
            why = why or f"NoTriggerSites: {e}"
    if miss:
        why = why or f"the listing publishes no {miss}: calibration impossible"
    if why:
        p.unmeasurable = why
    return p
