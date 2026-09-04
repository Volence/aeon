#!/usr/bin/env python3
"""row_remap_witness — does EFFECTS-W1 item 9's row remap reach Hscroll_Buffer, and is it
doing something a plain band could not?

THE SUBJECT. Parcel 9a (the Hydrocity waterline's SCROLL half) adds a second pass to
`Parallax_Fill_PerLine` that re-fetches one band's plane-B scroll words through a
viewpoint-selected index ladder. Nothing about that reaches VRAM as a distinct object: it
edits words the ordinary per-line fill already wrote, in a buffer the ordinary static DMA
already ships. So "did it run?" cannot be answered by looking for a new write — it has to be
answered by PREDICTING the buffer and comparing.

WHAT THIS MEASURES, AND WHY THE PREDICTION IS DERIVED RATHER THAN FITTED.

The remapped band is a `.lp_bg` band: every one of its lines is
`base + (deform_curve[(c + j) & 255] >> dsb)` for the line's own offset j, where `base` is the
band's constant BG scroll word and `c` folds the deform phase, the band phase, the plane
vscroll and the band top. The remap rewrites only the FIRST n lines of the band; lines
n..span are left exactly as that loop wrote them.

So the witness splits the band against itself:

  * THE TAIL (lines n..span) is UNTOUCHED by the remap and is what determines `c` and `base`.
    It is solved for, over a window the subject never wrote.

    ⚠ THE TAIL ALONE CANNOT ALWAYS IDENTIFY THE PHASE, WHICH IS WHY IT IS NOT ASKED TO. At
    the shipped amplitude (DeformTable_Shimmer at dsb 2) the per-line term is `sin*8 >> 2`, a
    five-value staircase, and several phases produce the same quantised tail — measured, 3 or
    4 candidates on 4 of 12 samples, and on 3 of them the candidates DISAGREED about the
    verdict. Two earlier drafts got this wrong in the two available ways: the first DROPPED
    the ambiguous samples (reporting 8/8 while a quarter of the run went unexamined — "a
    green row that never chose its bed cannot fail"), and the second failed them.

    So `c` is DERIVED FROM LIVE RAM instead of fitted:
        c = (Parallax_Deform_Phase_BG + band_phase_offset + Vscroll_BG + top) & $FF
    which is `.lp_bg`'s own index expression, restated. The tail is then a CHECK on that
    derivation rather than its source — the derived `c` must be among the tail's candidates
    and must hold `base` constant across the whole tail — and `base` comes from the tail too.
    A witness whose phase came out of the data it is testing would be choosing its own
    answer.
  * THE HEAD (lines 0..n) is then PREDICTED from the ladder bytes read out of the ROM and
    compared word for word. Nothing about the head is used to fit anything.

Two verdicts come out of that, and BOTH are required:

  1. POSITIVE — the head matches `base + (curve[(c + ladder[i]) & 255] >> dsb)` exactly. The
     remap ran, on the band the mark named, with the ladder row the perspective quantity
     selected.
  2. CONTROL — the head does NOT match the FLAT prediction `base + (curve[(c + i) & 255] >>
     dsb)`, i.e. what the same band would hold with no remap. This is the arm that refuses
     design §9.1 precondition 1's failure mode: REMAPPING A CONSTANT IS THE IDENTITY, and a
     remap that ran over a flat source would satisfy (1) and (2) identically. If the control
     cannot separate, the effect is invisible and this witness says so.

⚠ A CORRECTION TO THE DESIGN'S OWN GATE TELL, FOUND BY MEASUREMENT. Design §9.2 proposes
"a repeated value adjacent to a skipped one, which no other loop produces". A REPEAT cannot
occur: this parcel's generated ladder has `entry[i] - entry[i-1] >= 1` by construction, and
S3K's own shipped table is the same shape — its published step histograms (design §1.2: row
10 is 84x1, 10x2, 1x87) contain no zero step either. The observable signature of this
mechanism is the SKIP, not the repeat, and a gate written to the design's wording would look
for something neither table can produce and pass vacuously. The word-for-word prediction
above is what replaced it, and it is strictly stronger.

WHICH CONFIG. OJZ act 1 section 0 installs a GENERATED EDITOR BINDING
(`EditorSceneBinding_OJZ_Act1_Sec0`), not the shipped `ParallaxConfig_OJZ_Underwater` its
preset names — measured on this tree, and it is the reason parcel 9a's adoption is
HAND-AUTHORED on the registry scene rather than document-bound. Teaching the editor
document a `rowRemap` key is parcel 9c and is blocked on a hub schema CR. So the owner's
route is the DEBUG scene-cycle chord (START + LEFT/RIGHT, two-digit readout, scene 01), and
this witness installs the same config the same way that hotkey does — by writing the
parallax config pointer — because the bus cannot press a chord without risking the input
wedge. The SECTION's preset is untouched either way, which is what keeps patch channel 0
seeded and sweeping.

MOTION. Standing still this effect is a photograph, so the witness also records the remapped
height n over a frame sweep and requires it to CHANGE. In OJZ act 1 section 0 that happens
with no input at all, because the section's patch channel 0 carries an `anchor_sweep`.
Frame indices are recorded at every step and compared as DELTAS, and any rewind is reported
rather than absorbed.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from suite_paths import add_client_path  # noqa: E402

add_client_path()
from aether import BusClient  # noqa: E402
from aether_instance import AetherInstance  # noqa: E402


class Refused(RuntimeError):
    pass


def refuse(msg: str) -> Refused:
    return Refused(msg)


def _hex(s) -> int:
    s = str(s)
    return int(s[2:] if s[:2].lower() == "0x" else (s[1:] if s[:1] == "$" else s), 16)


def s16(v: int) -> int:
    return v - 0x10000 if v >= 0x8000 else v


def s8(v: int) -> int:
    return v - 0x100 if v >= 0x80 else v


def asr(v: int, n: int) -> int:
    """68000 asr.w on a sign-extended byte — Python's >> is already arithmetic."""
    return v >> n


async def lookup(c: BusClient, name: str) -> int:
    try:
        r = await c.call("emulator/lookup_symbol", {"name": name})
    except Exception as e:
        raise refuse(f"symbol {name!r} does not resolve against the loaded listing: {e}")
    return _hex(r["addr"])


async def rd(c: BusClient, addr: int, length: int) -> int:
    r = await c.call("emulator/read_memory", {"addr": hex(addr), "len": length})
    return _hex(r["bytes"])


async def rd_words(c: BusClient, addr: int, n: int) -> list[int]:
    r = await c.call("emulator/read_memory", {"addr": hex(addr), "len": 2 * n})
    raw = str(r["bytes"])
    raw = raw[2:] if raw[:2].lower() == "0x" else raw
    raw = raw.zfill(4 * n)
    return [int(raw[4 * i:4 * i + 4], 16) for i in range(n)]


async def frame_no(c: BusClient) -> int:
    return int((await c.call("emulator/status", {}))["frame"])


def rom_bytes(rom: bytes, addr: int, n: int) -> list[int]:
    if addr + n > len(rom):
        raise refuse(f"ROM read ${addr:06X}+{n} runs past the {len(rom)}-byte image")
    return list(rom[addr:addr + n])


# --------------------------------------------------------------------------- the record

def field_offsets(repo: str, tail_base: int) -> dict:
    """band_remap's field displacements FROM THE RECORD BASE, derived from the struct
    declaration in engine/level/parallax.emp rather than typed here.

    ⚠ `tail_base` IS NOT OPTIONAL, and leaving it out is a live defect this witness made
    once. The engine reads these as `offsetof(band_record, br_remap) + offsetof(band_remap,
    <field>)` — the .emp banner beside those consts says in as many words that the
    field-in-displacement sugar does not compose through a containing struct. A witness using
    the WITHIN-STRUCT offsets reads band_top_plane and the factor bytes as a ROM pointer and
    a height shift, and reports a live effect as dead: measured 2026-09-03, brm_hshift came
    back 0 (H = 1) and the perspective quantity came back 271."""
    import re
    text = open(os.path.join(repo, "engine/level/parallax.emp"), encoding="utf-8").read()
    m = re.search(r"pub struct band_remap \(size: (\d+)\) \{(.*?)\n\}", text, re.S)
    if not m:
        raise refuse("could not find `pub struct band_remap` in engine/level/parallax.emp")
    size = int(m.group(1))
    widths = {"u8": 1, "u16": 2, "u32": 4, "*u8": 4}
    off, out = 0, {}
    for name, ty in re.findall(r"\n\s+(\w+):\s+(\*?u\d+),", m.group(2)):
        out[name] = tail_base + off
        off += widths[ty]
    if off != size:
        raise refuse(f"band_remap fields sum to {off} bytes, declared size {size}")
    return out


def legacy_field_offset(repo: str, want: str) -> int:
    """A band_entry field's displacement from the record base — the legacy prefix sits at
    offset 0, which parallax.emp asserts, so the two coincide. Walked off the declaration."""
    import re
    text = open(os.path.join(repo, "engine/level/parallax.emp"), encoding="utf-8").read()
    m = re.search(r"pub struct band_entry \{(.*?)\n\}", text, re.S)
    if not m:
        raise refuse("could not find `pub struct band_entry` in engine/level/parallax.emp")
    widths = {"u8": 1, "u16": 2, "u32": 4, "*u8": 4}
    off = 0
    for name, ty in re.findall(r"\n\s+(\w+):\s+(\*?u\d+),", m.group(1)):
        if name == want:
            return off
        off += widths[ty]
    raise refuse(f"band_entry has no field {want!r}")


def record_stride(repo: str) -> int:
    """(offsetof(band_record, br_remap), sizeof(band_record)) — both derived from the four
    tail declarations and their capability counts, never typed."""
    import re
    text = open(os.path.join(repo, "engine/level/parallax.emp"), encoding="utf-8").read()
    sizes = {}
    for nm in ("band_ext", "band_curve", "band_drift", "band_remap"):
        m = re.search(r"pub struct " + nm + r" \(size: (\d+)\)", text)
        if not m:
            raise refuse(f"could not size `{nm}`")
        sizes[nm] = int(m.group(1))
    # band_entry carries no `(size: N)` claim — it is the LEGACY prefix and engine/ram.emp
    # holds its mirror, BAND_ENTRY_LEN, pinned by `extern("band_entry_len")` in parallax.emp.
    # Read it from the mirror rather than counting fields, so the witness sizes the record
    # off the same number the RAM reservation does.
    ram = open(os.path.join(repo, "engine/ram.emp"), encoding="utf-8").read()
    m = re.search(r"const BAND_ENTRY_LEN\s+= (\d+)", ram)
    if not m:
        raise refuse("could not read BAND_ENTRY_LEN from engine/ram.emp")
    sizes["band_entry"] = int(m.group(1))
    ns = {}
    for nm in ("BAND_EXT_N", "BAND_CURVE_N", "BAND_DRIFT_N", "BAND_REMAP_N"):
        m = re.search(r"pub const " + nm + r" = (\d+)", text)
        if not m:
            raise refuse(f"could not read `{nm}`")
        ns[nm] = int(m.group(1))
    tail_base = (sizes["band_entry"] + sizes["band_ext"] * ns["BAND_EXT_N"]
                 + sizes["band_curve"] * ns["BAND_CURVE_N"]
                 + sizes["band_drift"] * ns["BAND_DRIFT_N"])
    return tail_base, tail_base + sizes["band_remap"] * ns["BAND_REMAP_N"]


# --------------------------------------------------------------------------- the run

async def sample(c: BusClient, syms: dict, rom: bytes, foff: dict, stride: int,
                 phase_off: int) -> dict:
    """One frame's full picture: the mark, the perspective quantity, the ladder row, and the
    band's own longwords."""
    rec = await rd(c, syms["Parallax_Remap_State"], 4)
    out = {"rec": rec}
    if rec == 0:
        out["marked"] = False
        return out
    out["marked"] = True
    rec &= 0xFFFFFF
    out["top"] = top = s16(await rd(c, syms["Parallax_Remap_State"] + 4, 2))
    out["end"] = end = s16(await rd(c, syms["Parallax_Remap_State"] + 6, 2))
    out["span"] = span = end - top

    ladder = await rd(c, rec + foff["brm_ladder"], 4) & 0xFFFFFF
    plane_y = s16(await rd(c, rec + foff["brm_plane_y"], 2))
    hshift = await rd(c, rec + foff["brm_hshift"], 1)
    ch = await rd(c, rec + foff["brm_anchor_ch"], 1)
    out.update(ladder=ladder, plane_y=plane_y, hshift=hshift, anchor_ch=ch)

    vbg = s16(await rd(c, syms["Parallax_Current_Vscroll_BG"], 2))
    L = s16(await rd(c, syms["Effects_Screen_L"] + 2 * ch, 2))
    out.update(vscroll_bg=vbg, L=L)

    # THE SELECTOR, RE-DERIVED HERE FROM THE SAME THREE READS THE 68000 MAKES. Not copied
    # from the .emp: the arithmetic is restated so a change on one side and not the other
    # fails instead of agreeing with itself.
    H = 1 << hshift
    p = plane_y - vbg - L
    ap = min(abs(p), H - 1)
    out.update(H=H, p=p, abs_p=ap)
    if ap == 0:
        out["n"] = 0
        return out
    row = H - ap
    n = min(ap, span >> 1)
    out.update(row=row, n=n)
    if n <= 0:
        return out
    out["ladder_row"] = rom_bytes(rom, ladder + (row << hshift), n)

    # `.lp_bg`'s own deform index, restated: (phase_bg + band_phase + vscroll_bg + line) & $FF.
    # band_phase_offset is the LAST byte of the legacy prefix; its displacement is derived
    # from the struct rather than typed, for band_remap's reason.
    phase = await rd(c, syms["Parallax_Deform_Phase_BG"], 2)
    band_phase = await rd(c, rec + phase_off, 1)
    out["c_derived"] = (phase + band_phase + vbg + top) & 0xFF
    out["band_phase_offset"] = band_phase

    # the band's own longwords out of Hscroll_Buffer
    words = await rd_words(c, syms["Hscroll_Buffer"] + 4 * top, 2 * span)
    out["bg"] = [words[2 * j + 1] for j in range(span)]
    out["fg"] = [words[2 * j] for j in range(span)]
    return out


def base_for(s: dict, curve: list[int], dsb: int, c0: int):
    """`base` from the band's UNREMAPPED tail at the DERIVED phase, or None if the derived
    phase does not hold a constant base across that whole window — which would mean the model
    of what `.lp_bg` writes is wrong and every verdict below it is worthless."""
    bg, n, span = s["bg"], s["n"], s["span"]
    base = None
    for j in range(n, span):
        v = (bg[j] - asr(s8(curve[(c0 + j) & 255]), dsb)) & 0xFFFF
        if base is None:
            base = v
        elif v != base:
            return None
    return base


def solve_tail(s: dict, curve: list[int], dsb: int) -> list[tuple[int, int]]:
    """Every (c, base) consistent with the band's UNREMAPPED tail — lines n..span, which the
    pass never writes. Returns the WHOLE candidate set; the caller evaluates all of them and
    requires agreement. See the module docstring for why dropping a non-unique solve would be
    a vacuous pass."""
    bg, n, span = s["bg"], s["n"], s["span"]
    tail = list(range(n, span))
    if len(tail) < 8:
        return []
    hits = []
    for c0 in range(256):
        base = None
        ok = True
        for j in tail:
            v = (bg[j] - asr(s8(curve[(c0 + j) & 255]), dsb)) & 0xFFFF
            if base is None:
                base = v
            elif v != base:
                ok = False
                break
        if ok:
            hits.append((c0, base))
    return hits


def predict(c0: int, base: int, idx: list[int], curve: list[int], dsb: int) -> list[int]:
    return [(base + asr(s8(curve[(c0 + k) & 255]), dsb)) & 0xFFFF for k in idx]


async def run(a) -> int:
    rom_path = os.path.abspath(a.rom)
    lst = os.path.abspath(a.lst) if a.lst else rom_path[:-4] + ".lst"
    rom = open(rom_path, "rb").read()
    tail_base, stride = record_stride(a.repo)
    phase_off = legacy_field_offset(a.repo, "band_phase_offset")
    foff = field_offsets(a.repo, tail_base)
    print(f"  br_remap at record offset {tail_base}; displacements {foff}; "
          f"sizeof(band_record) = {stride}; band_phase_offset at {phase_off}")

    inst = AetherInstance(rom=rom_path, symbols=lst)
    sock = await asyncio.to_thread(inst.start)
    out = {"rom": rom_path, "rom_bytes": len(rom), "band_remap_offsets": foff,
           "band_record_stride": stride, "frames": []}
    try:
        c = BusClient(socket_path=sock, client_id="rowremapw", client_name="row_remap_witness")
        await c.connect()
        st = await c.call("emulator/status", {})
        if int(st["romBytes"]) != len(rom):
            raise refuse(f"server serves {st['romBytes']} bytes, {rom_path} is {len(rom)} — a different ROM")
        print(f"  server romPath={st['romPath']} romBytes={st['romBytes']} (matches disk)")
        out["server_rom_path"] = st["romPath"]

        names = ["Parallax_Remap_State", "Parallax_Current_Vscroll_BG", "Effects_Screen_L",
                 "Hscroll_Buffer", "Camera_Y", "Parallax_Deform_Phase_BG",
                 "Parallax_Prev_Sec_X", "Parallax_Prev_Sec_Y",
                 "Parallax_Current_Config", "Parallax_Target_Config",
                 "Parallax_Transition_Frames"]
        syms = {n: await lookup(c, n) for n in names}
        curve_addr = await lookup(c, a.curve)
        curve = rom_bytes(rom, curve_addr & 0xFFFFFF, 256)
        out["symbols"] = {k: f"${v:06X}" for k, v in syms.items()}
        out["curve"] = {"name": a.curve, "addr": f"${curve_addr:06X}"}

        f_prev = await frame_no(c)
        out["frame_start"] = f_prev
        await c.call("emulator/run_frames", {"frames": a.settle})
        f_now = await frame_no(c)
        rewound = f_now < f_prev
        out["frame_after_settle"] = f_now
        out["rewind_observed"] = bool(rewound)
        print(f"  frames {f_prev} -> {f_now} over {a.settle} settle frames "
              f"(delta {f_now - f_prev}); rewind observed: {rewound}")
        sec = (await rd(c, syms["Parallax_Prev_Sec_X"], 1), await rd(c, syms["Parallax_Prev_Sec_Y"], 1))
        out["section"] = sec
        was = await rd(c, syms["Parallax_Current_Config"], 4)
        print(f"  section {sec}; section-installed config ${was:06X}")
        out["config_installed_by_section"] = f"${was:06X}"

        # -- install the hand-authored scene, the way the DEBUG scene-cycle hotkey does --
        cfg = await lookup(c, a.config)
        for sym in ("Parallax_Current_Config", "Parallax_Target_Config"):
            await c.call("emulator/write_memory",
                         {"addr": hex(syms[sym]), "value": cfg, "width": 4})
        await c.call("emulator/write_memory",
                     {"addr": hex(syms["Parallax_Transition_Frames"]), "value": 0, "width": 1})
        await c.call("emulator/run_frames", {"frames": a.install_settle})
        now = await rd(c, syms["Parallax_Current_Config"], 4)
        if now != cfg:
            raise refuse(f"the engine replaced the installed config: wrote ${cfg:06X}, reads "
                         f"${now:06X} — a section crossing or a transition overwrote it")
        out["config_under_test"] = {"name": a.config, "addr": f"${cfg:06X}"}
        print(f"  installed {a.config} = ${cfg:06X}, held for {a.install_settle} frames")

        ok_pos = ok_ctrl = unsolved = disagreed = 0
        ns, sigs = [], []
        for step in range(a.samples):
            f_before = await frame_no(c)
            s = await sample(c, syms, rom, foff, stride, phase_off)
            f_after = await frame_no(c)
            if f_after < f_before:
                out["rewind_observed"] = True
            rec = {"frame": f_after, "marked": s["marked"]}
            if not s["marked"]:
                out["frames"].append(rec)
                raise refuse("Parallax_Remap_State is 0 — NO BAND WAS MARKED. Either no band "
                             "carries a ladder in the active config, or the mark span is not "
                             "emitted (CAP_ROW_REMAP not declared).")
            rec.update({k: s[k] for k in ("top", "end", "span", "p", "abs_p", "H") if k in s})
            n = s.get("n", 0)
            rec["n"] = n
            ns.append(n)
            if n > 0:
                cands = solve_tail(s, curve, a.dsb)
                c0 = s["c_derived"]
                rec["tail_candidates"] = len(cands)
                rec["c_derived"] = c0
                rec["c_derived_in_tail_candidates"] = c0 in [x for x, _ in cands]
                base = base_for(s, curve, a.dsb, c0)
                if base is None or not rec["c_derived_in_tail_candidates"]:
                    rec["verdict"] = "tail-refutes-derived-phase"
                    unsolved += 1
                else:
                    head = s["bg"][:n]
                    pred = predict(c0, base, s["ladder_row"], curve, a.dsb)
                    flat = predict(c0, base, list(range(n)), curve, a.dsb)
                    rec["base"] = base
                    rec["match_remapped"] = head == pred
                    rec["separates_from_flat"] = head != flat
                    rec["flat_differences"] = sum(1 for x, y in zip(head, flat) if x != y)
                    rec["peak_to_peak"] = max(head) - min(head) if head else 0
                    ok_pos += 1 if head == pred else 0
                    ok_ctrl += 1 if head != flat else 0
                    if head != pred:
                        rec["head"] = head
                        rec["pred"] = pred
                    sigs.append(tuple(head))
            out["frames"].append(rec)
            await c.call("emulator/run_frames", {"frames": a.stride})

        out["samples"] = a.samples
        out["positive_matches"] = ok_pos
        out["control_separations"] = ok_ctrl
        out["tail_unsolved"] = unsolved

        out["n_values"] = ns
        out["n_changed"] = len(set(ns)) > 1
        out["signature_changed"] = len(set(sigs)) > 1
    finally:
        inst.reap()

    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)

    print(f"\n  samples                {a.samples}")
    print(f"  remapped height n      {ns} (changed: {out['n_changed']})")
    print(f"  POSITIVE  head == remapped prediction   {ok_pos}/{len(sigs)}")
    print(f"  CONTROL   head != flat prediction       {ok_ctrl}/{len(sigs)}")
    print(f"  buffer signature changed across frames  {out['signature_changed']}")
    print(f"  samples where the tail REFUTED the phase {out['tail_unsolved']}")

    print(f"  rewind observed                         {out['rewind_observed']}")
    print(f"  -> {a.out}")

    bad = []
    if not sigs:
        bad.append("no frame produced a remapped run at all (n was 0 every sample)")
    if ok_pos != len(sigs):
        bad.append(f"the remapped prediction failed on {len(sigs) - ok_pos} of {len(sigs)} samples")
    if ok_ctrl != len(sigs):
        bad.append(f"the FLAT control could not be separated on {len(sigs) - ok_ctrl} of "
                   f"{len(sigs)} samples — on those frames the remap is the IDENTITY and "
                   f"nothing is on screen (design §9.1 precondition 1)")
    if out["tail_unsolved"]:
        bad.append(f"on {out['tail_unsolved']} samples the band's UNREMAPPED tail refuted the "
                   f"phase derived from live RAM — the model of what .lp_bg writes is wrong, "
                   f"and every verdict above rests on it")

    if not out["n_changed"]:
        bad.append("the remapped height never changed across the sweep — standing still this "
                   "effect is a photograph, and a witness that cannot see it move cannot tell "
                   "a live effect from a frozen one")
    if out["rewind_observed"]:
        bad.append("the emulator's frame index REWOUND during the run; every delta above is suspect")
    if bad:
        print("\nFAIL:")
        for b in bad:
            print("  - " + b)
        return 1
    print("\nPASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default=os.path.join(REPO, "s4.debug.bin"))
    ap.add_argument("--lst", default=None)
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--curve", default="DeformTable_Shimmer",
                    help="the BG deform table the remapped band samples")
    ap.add_argument("--dsb", type=int, default=2,
                    help="the band's BG deform amplitude shift (the anchor's, from the split down)")
    ap.add_argument("--config", default="ParallaxConfig_OJZ_Underwater",
                    help="the parallax config to install (the DEBUG scene-cycle's scene 01)")
    ap.add_argument("--settle", type=int, default=240)
    ap.add_argument("--install-settle", type=int, default=30,
                    help="frames after the config install, so Step 4a rebuilds the shadow view")
    ap.add_argument("--samples", type=int, default=12)
    ap.add_argument("--stride", type=int, default=10, help="frames between samples")
    ap.add_argument("--out", default=os.path.join(REPO, "row_remap_witness.json"))
    a = ap.parse_args()
    try:
        return asyncio.run(run(a))
    except Refused as e:
        print(f"REFUSED: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
