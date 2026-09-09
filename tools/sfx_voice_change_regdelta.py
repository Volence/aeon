#!/usr/bin/env python3
"""sfx_voice_change_regdelta — SP-6 click triage: WHICH YM2612 registers actually
move across a mid-stream `smpsSetvoice`, and are the values we write the same ones
Sonic & Knuckles writes?

WHY THIS FILE EXISTS. The owner reported an audible click/pop in the re-sourced
two-voice spring. That splits into two very different answers:

  (a) the click is INHERENT to changing an FM voice under a sounding note — the
      data itself contains a discontinuity, and S&K's own driver executing S&K's
      own voice bytes would click the same; or
  (b) the click is a BUG in HOW we perform the switch — we write something S&K
      does not, or write it differently.

There is NO audio instrument in this suite (re-verified on the branch: the running
oracle server answers `[-32601] no such method` for every vgm_*/audio_* name in its
bus schema), so the click cannot be rendered or measured. What CAN be established,
and what decides (a) vs (b), is the REGISTER WRITE SET. This file derives both
drivers' write sets from their own sources and diffs them.

WHAT IT IS NOT. It does not claim the sound is right, does not claim the click is
present, and does not claim the click is absent. A green run says exactly one
thing: our mid-stream voice change puts the same values in the same YM2612
registers as S&K's does, so the switch MECHANISM cannot be the difference.

THE THREE LEGS.

  L1 VALUE PARITY      Every YM2612 register our Fm_PatchLoad writes for voice V
                       carries the same value S&K's zSendFMInstrument writes for
                       voice V, for every voice in the bank. The ONE structurally
                       licensed exception is the carrier TL slot, where an S&K TL
                       byte with bit 7 set means "add the track volume at upload
                       time" (zSendTL, Z80 Sound Driver.asm:3186-3194) while our
                       transcoder bakes a constant in at build time. That slot is
                       not skipped — it is compared modulo the flag and its
                       residual is REPORTED, because that residual is a real
                       carrier-amplitude step and hiding it would be the exact
                       failure this file was written to avoid.

  L2 DELTA CLASS       Of the registers that CHANGE VALUE between voice 0 and the
                       voice the stream switches to, none may be in the
                       instantaneous-amplitude class other than TL. The class
                       partition is not folklore: $40 (TL) and $B0 (algorithm /
                       feedback) are the two registers a YM2612 consumes with no
                       smoothing — Nuked-OPN2 adds `eg_tl << 3` to the level every
                       sample and re-reads `connect[channel] = data & 7` in
                       OPN2_FMPrepare every sample — while $50/$60/$70/$80 set
                       envelope SLOPES and cannot step the level. If this leg goes
                       red, a register outside the TL group moved and the click has
                       a second, previously unconsidered source.

  L3 DISCONTINUITY     Report (never assert) the per-operator TL deltas in units of
     LEDGER            0.75 dB, split carrier vs modulator by the algorithm's own
                       carrier mask. This is the (a)-side evidence: the pop, if it
                       is at the voice change at all, is here, and it is in the
                       DONOR DATA rather than in our code.

EVERY EXPECTATION IS DERIVED, NOTHING IS PINNED.
  * register bases   <- engine/sound/sound_constants.emp's SND_REG_* consts
  * FmPatch layout   <- the `struct FmPatch` in the same file (field order IS the
                        write order Fm_PatchLoad walks)
  * operator stride  <- FmPatch's own "index 0..3 = register offset +0,+4,+8,+C"
  * our voice bytes  <- the SHIPPED blob under games/sonic4/data/sound/sfx/
  * the changed voice<- that blob's own MEV_PATCH operand
  * S&K voice bytes  <- skdisasm's `B1 - Spring.asm` smpsVc* macros, packed by the
                        emission order in skdisasm's `_smps2asm_inc.asm`
  * S&K registers    <- zFMInstrumentRegTable / zFMInstrumentTLTable parsed out of
                        skdisasm's `Z80 Sound Driver.asm`
No value below is copied from a nearby pin, from a comment, or from an earlier
measurement of mine.

LOUD ON UNMEASURABLE. Every ambiguity raises Unmeasurable and exits 2. A run that
could not ask its question is NEVER reported as a pass.

RUN:  python3 tools/sfx_voice_change_regdelta.py
      python3 tools/sfx_voice_change_regdelta.py --sfx B1 --verbose
Exit: 0 = all legs pass, 1 = a leg failed, 2 = could not measure.
"""
import argparse
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKDISASM = Path("/home/volence/sonic_hacks/skdisasm")


class Unmeasurable(RuntimeError):
    """The run could not ask its question — never reported as a pass."""


# ---------------------------------------------------------------------------
# Derivation 1: OUR side. Register bases, FmPatch layout, and the shipped blob.
# ---------------------------------------------------------------------------
def emp_reg_bases(path):
    """-> {const_name: value} for every SND_REG_* in sound_constants.emp."""
    out = {}
    for line in path.read_text(errors="replace").splitlines():
        m = re.match(r"\s*pub const (SND_REG_\w+)\s*=\s*\$([0-9A-Fa-f]+)", line)
        if m:
            out[m.group(1)] = int(m.group(2), 16)
    need = {"SND_REG_ALG_FB", "SND_REG_LR_AMS_FMS", "SND_REG_OP_DT_MUL",
            "SND_REG_OP_TL", "SND_REG_OP_RS_AR", "SND_REG_OP_AM_D1R",
            "SND_REG_OP_D2R", "SND_REG_OP_D1L_RR", "SND_REG_OP_SSG_EG"}
    missing = need - out.keys()
    if missing:
        raise Unmeasurable(f"sound_constants.emp has no {sorted(missing)}")
    return out


def emp_fmpatch_layout(path):
    """-> ([(field, count)], total_len) read from `pub struct FmPatch`.

    The FIELD ORDER is the thing being derived: Fm_PatchLoad walks the record head
    to tail, so a reordered struct must reorder this table with it."""
    txt = path.read_text(errors="replace")
    m = re.search(r"pub struct FmPatch \{(.*?)\n\}", txt, re.S)
    if not m:
        raise Unmeasurable("no `pub struct FmPatch { ... }` in sound_constants.emp")
    fields, total = [], 0
    for fm in re.finditer(r"\n\s*(\w+):\s*(?:u8|\[u8;\s*(\d+)\])", m.group(1)):
        n = int(fm.group(2)) if fm.group(2) else 1
        fields.append((fm.group(1), n))
        total += n
    if not fields:
        raise Unmeasurable("FmPatch parsed to zero fields")
    return fields, total


# field name -> the SND_REG_* const whose base it is written to. `None` = the
# field emits no YM write (padding). Derived from the struct's own comments being
# load-bearing is NOT good enough, so this mapping is asserted against the
# register bases by name below.
FIELD_REG = {
    "fp_alg_fb":     ("SND_REG_ALG_FB", False),      # channel reg, no op stride
    "fp_lr_ams_fms": ("SND_REG_LR_AMS_FMS", False),  # channel reg, no op stride
    "fp_dt_mul":     ("SND_REG_OP_DT_MUL", True),
    "fp_tl":         ("SND_REG_OP_TL", True),
    "fp_rs_ar":      ("SND_REG_OP_RS_AR", True),
    "fp_am_d1r":     ("SND_REG_OP_AM_D1R", True),
    "fp_d2r":        ("SND_REG_OP_D2R", True),
    "fp_d1l_rr":     ("SND_REG_OP_D1L_RR", True),
    "fp_ssg_eg":     ("SND_REG_OP_SSG_EG", True),
    "fp_reserved":   (None, False),
}
OP_STRIDE = 4          # FmPatch: "index 0..3 = register offset +0,+4,+8,+C"


def our_writes(patch_bytes, layout, bases):
    """-> {reg_offset_within_channel: value} for one 32-byte FmPatch record.

    Register offsets are given WITHOUT the channel number, which is what makes the
    two drivers comparable: both add the same `+ch` at the end."""
    fields, total = layout
    if len(patch_bytes) != total:
        raise Unmeasurable(f"patch record is {len(patch_bytes)} B, struct says {total}")
    out, off = {}, 0
    for name, count in fields:
        if name not in FIELD_REG:
            raise Unmeasurable(
                f"FmPatch field `{name}` is not in this file's FIELD_REG table — the "
                "struct grew a field and the write set can no longer be derived")
        const, strided = FIELD_REG[name]
        if const is None:
            off += count
            continue
        base = bases[const]
        for i in range(count):
            reg = base + (i * OP_STRIDE if strided else 0)
            if reg in out:
                raise Unmeasurable(f"two FmPatch fields both write register ${reg:02X}")
            out[reg] = patch_bytes[off + i]
        off += count
    return out


def load_blob(sfx_id):
    """-> (blob, voice_ptr, cmd_ptr, voice_count, change_idx) from the SHIPPED .bin.

    Layout per tools/sfx_transcode.py:11 — SfxHeader is 8 bytes
    {priority, flags, chcount, gain, duck, cap, rsvd, rsvd}, then chcount 6-byte
    records {route, kind, cmd_hi, cmd_lo, voice_hi, voice_lo}."""
    p = REPO / "games/sonic4/data/sound/sfx" / f"sfx_{sfx_id}.bin"
    if not p.is_file():
        raise Unmeasurable(f"{p} does not exist")
    blob = p.read_bytes()
    if len(blob) < 8:
        raise Unmeasurable(f"{p.name} is {len(blob)} B, shorter than the 8-byte header")
    chcount = blob[2]
    voice_ptr = cmd_ptr = None
    for i in range(chcount):
        r = 8 + i * 6
        if r + 6 > len(blob):
            raise Unmeasurable(f"{p.name} declares chcount={chcount} but is too short")
        vp = (blob[r + 4] << 8) | blob[r + 5]
        if vp:
            voice_ptr, cmd_ptr = vp, (blob[r + 2] << 8) | blob[r + 3]
            break
    if voice_ptr is None:
        raise Unmeasurable(f"no channel in sfx_{sfx_id} carries an FmPatch bank pointer")
    return blob, voice_ptr, cmd_ptr


def decode_change(blob, cmd_ptr, voice_ptr, patch_len, mev_patch):
    bank = blob[voice_ptr:]
    count, rem = divmod(len(bank), patch_len)
    if rem:
        raise Unmeasurable(
            f"the patch bank is {len(bank)} B, not a whole number of {patch_len}-byte records")
    if count < 2:
        raise Unmeasurable(
            f"the subject carries {count} voice(s) — a MID-STREAM voice change needs at "
            "least two, and this file REFUSES rather than reporting a pass on a "
            "single-voice donor")
    stream = blob[cmd_ptr:voice_ptr]
    idxs = [i for i in range(len(stream) - 1) if stream[i] == mev_patch]
    if len(idxs) != 1:
        raise Unmeasurable(
            f"expected exactly one MEV_PATCH (${mev_patch:02X}) in the stream, found "
            f"{len(idxs)} — cannot name a single voice under test")
    v = stream[idxs[0] + 1]
    if not 0 < v < count:
        raise Unmeasurable(f"stream selects voice {v}, outside a {count}-voice bank")
    return count, v


# ---------------------------------------------------------------------------
# Derivation 2: S&K's side, from skdisasm's own sources.
# ---------------------------------------------------------------------------
def sk_reg_tables(driver_path):
    """-> ([6 op-group register orders], [TL register order]) from the driver's
    zFMInstrumentRegTable / zFMInstrumentTLTable `db` rows.

    zFMInstrumentRegTable is $B0 followed by five 4-entry operator groups; the TL
    group lives in its own table because zSendTL runs it separately (and last)."""
    txt = driver_path.read_text(errors="replace")
    def grab(start_label, end_label):
        m = re.search(re.escape(start_label) + r":(.*?)" + re.escape(end_label), txt, re.S)
        if not m:
            raise Unmeasurable(f"{start_label}..{end_label} not found in the S&K driver")
        vals = [int(h, 16) for h in re.findall(r"^\s*db\s+([0-9A-Fa-f]{2,3})h",
                                               m.group(1), re.M)]
        return vals
    main = grab("zFMInstrumentRegTable", "zFMInstrumentOperatorTable_End")
    tl = grab("zFMInstrumentTLTable", "zFMInstrumentTLTable_End")
    if len(main) != 21:
        raise Unmeasurable(
            f"zFMInstrumentRegTable..OperatorTable_End yielded {len(main)} entries, "
            "expected 21 ($B0 + five 4-entry operator groups)")
    if len(tl) != 4:
        raise Unmeasurable(f"zFMInstrumentTLTable yielded {len(tl)} entries, expected 4")
    return main, tl


def sk_voice_records(sfx_path):
    """-> [ {field: [op1..op4] or scalar} ] for every voice in an S&K SFX file.

    Reads the smpsVc* macro calls. Their per-operator arguments are op1..op4 in
    ALGORITHM order; the packing below reverses them, which is not an assumption —
    it is skdisasm's own `_smps2asm_inc.asm` emission (`vcDT4..vcDT1`)."""
    txt = sfx_path.read_text(errors="replace")
    voices, cur = [], None
    order = ["smpsVcAlgorithm", "smpsVcFeedback", "smpsVcUnusedBits", "smpsVcDetune",
             "smpsVcCoarseFreq", "smpsVcRateScale", "smpsVcAttackRate", "smpsVcAmpMod",
             "smpsVcDecayRate1", "smpsVcDecayRate2", "smpsVcDecayLevel",
             "smpsVcReleaseRate", "smpsVcTotalLevel"]
    for line in txt.splitlines():
        line = line.split(";")[0]
        m = re.match(r"\s*(smpsVc\w+)\s+(.*)$", line)
        if not m:
            continue
        macro, args = m.group(1), [a.strip() for a in m.group(2).split(",") if a.strip()]
        if macro not in order:
            raise Unmeasurable(f"unhandled voice macro `{macro}` in {sfx_path.name}")
        if macro == "smpsVcAlgorithm":
            cur = {}
            voices.append(cur)
        if cur is None:
            raise Unmeasurable(f"{macro} before any smpsVcAlgorithm in {sfx_path.name}")
        vals = []
        for a in args:
            if not re.fullmatch(r"\$[0-9A-Fa-f]+|\d+", a):
                raise Unmeasurable(f"non-literal voice macro argument `{a}` in {sfx_path.name}")
            vals.append(int(a[1:], 16) if a.startswith("$") else int(a))
        cur[macro] = vals[0] if len(vals) == 1 else vals
    for i, v in enumerate(voices):
        missing = [k for k in order if k not in v]
        if missing:
            raise Unmeasurable(f"voice {i} of {sfx_path.name} is missing {missing}")
    if not voices:
        raise Unmeasurable(f"no smpsVc* voice found in {sfx_path.name}")
    return voices


def sk_writes(v, main_tab, tl_tab):
    """-> ({reg_offset: value}, {reg_offset: True if 'add track volume'})

    Packs one parsed voice into S&K's own byte order and maps each byte through
    S&K's own register tables. The TL bit-7 masks are the `_smps2asm_inc.asm`
    rule verbatim: op1 always flagged; op2 iff alg>=5; op3 iff alg>=4; op4 iff
    alg==7 (the mask marks CARRIERS, which is what zSendTL adds the volume to)."""
    alg, fb, unused = v["smpsVcAlgorithm"], v["smpsVcFeedback"], v["smpsVcUnusedBits"]
    dt, cf = v["smpsVcDetune"], v["smpsVcCoarseFreq"]
    rs, ar = v["smpsVcRateScale"], v["smpsVcAttackRate"]
    am, d1r = v["smpsVcAmpMod"], v["smpsVcDecayRate1"]
    d2r, dl = v["smpsVcDecayRate2"], v["smpsVcDecayLevel"]
    rr, tl = v["smpsVcReleaseRate"], v["smpsVcTotalLevel"]
    # rev(x) = [op4, op3, op2, op1] — _smps2asm_inc.asm's SonicDriverVer>=3 order.
    rev = lambda a: [a[3], a[2], a[1], a[0]]
    body = []
    body += [((unused & 3) << 6) + (fb << 3) + alg]
    body += [(d << 4) + c for d, c in zip(rev(dt), rev(cf))]
    body += [(r << 6) + a for r, a in zip(rev(rs), rev(ar))]
    body += [(a << 5) | d for a, d in zip(rev(am), rev(d1r))]
    body += rev(d2r)
    body += [(l << 4) + r for l, r in zip(rev(dl), rev(rr))]
    if len(body) != len(main_tab):
        raise Unmeasurable(
            f"packed {len(body)} non-TL voice bytes for {len(main_tab)} register slots")
    regs = {r: b for r, b in zip(main_tab, body)}
    masks = [(alg == 7) << 7, (alg >= 4) << 7, (alg >= 5) << 7, 128]  # op4,op3,op2,op1
    tl_body = [(t & 127) for t in rev(tl)]
    volflag = {}
    for r, t, mk in zip(tl_tab, tl_body, masks):
        regs[r] = t
        volflag[r] = bool(mk)
    return regs, volflag


# Carrier mask per algorithm, bit i = "slot i is a carrier", i indexing the
# PHYSICAL slot order S1,S3,S2,S4 (bit0 = register offset +0), the same index space
# FmPatch's per-operator arrays use.
#   0-3  single carrier S4                          -> %1000
#   4    two chains S1->S2 and S3->S4, carriers S2+S4 -> %1100
#   5    S1 -> S2,S3,S4, carriers S2+S3+S4            -> %1110
#   6    S1->S2 plus bare S3,S4, carriers S2+S3+S4    -> %1110
#   7    all four independent                        -> %1111
# This is an INDEPENDENT derivation, and it is cross-checked at run time against
# tools/gen_sound_tables.py::carrier_mask_table (the generator that actually emits
# CarrierMaskTableZ). A disagreement is Unmeasurable, not a silent pick: on the
# first run of this file the two DID disagree and this side was the wrong one.
CARRIER_MASK = {0: 0b1000, 1: 0b1000, 2: 0b1000, 3: 0b1000,
                4: 0b1100, 5: 0b1110, 6: 0b1110, 7: 0b1111}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sfx", default="B1", help="SFX id (hex, as in sfx_<id>.bin)")
    ap.add_argument("--sk-sfx", default="B1 - Spring.asm",
                    help="the donor file under skdisasm/Sound/SFX/")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    consts = REPO / "engine/sound/sound_constants.emp"
    if not consts.is_file():
        raise Unmeasurable(f"{consts} does not exist")
    bases = emp_reg_bases(consts)
    layout = emp_fmpatch_layout(consts)
    patch_len = layout[1]

    sys.path.insert(0, str(REPO / "tools"))
    try:
        from song_packer import MEV_PATCH
        from gen_sound_tables import carrier_mask_table
    except Exception as e:                       # noqa: BLE001
        raise Unmeasurable(f"cannot import the engine-side generators: {e}")
    gen = carrier_mask_table()
    if list(gen[:8]) != [CARRIER_MASK[i] for i in range(8)]:
        raise Unmeasurable(
            "this file's carrier mask disagrees with gen_sound_tables.carrier_mask_table "
            f"({list(gen[:8])} vs {[CARRIER_MASK[i] for i in range(8)]}) — one of them is "
            "wrong and the carrier/modulator split below cannot be trusted")

    blob, voice_ptr, cmd_ptr = load_blob(a.sfx)
    vcount, changed = decode_change(blob, cmd_ptr, voice_ptr, patch_len, MEV_PATCH)
    ours = [our_writes(blob[voice_ptr + i * patch_len: voice_ptr + (i + 1) * patch_len],
                       layout, bases) for i in range(vcount)]

    drv = SKDISASM / "Sound/Z80 Sound Driver.asm"
    don = SKDISASM / "Sound/SFX" / a.sk_sfx
    for p in (drv, don):
        if not p.is_file():
            raise Unmeasurable(f"{p} does not exist — the S&K reference half cannot run")
    main_tab, tl_tab = sk_reg_tables(drv)
    sk_voices = sk_voice_records(don)
    if len(sk_voices) != vcount:
        raise Unmeasurable(
            f"our blob carries {vcount} voices, {don.name} declares {len(sk_voices)} — "
            "the two sides are not the same donor and cannot be compared")
    sk = [sk_writes(v, main_tab, tl_tab) for v in sk_voices]

    fails = []
    print(f"subject: sfx_{a.sfx}  voices={vcount}  stream switches to voice {changed}")
    print(f"donor:   {don.relative_to(SKDISASM)}")
    print()

    # --- L1 VALUE PARITY ---------------------------------------------------
    print("L1 VALUE PARITY (our Fm_PatchLoad write set vs S&K zSendFMInstrument)")
    vol_residual = {}
    for vi in range(vcount):
        sk_regs, volflag = sk[vi]
        # S&K's $B4 comes from track RAM (AMSFMSPan), never from the voice record,
        # so it has no counterpart to compare and is excluded by CONSTRUCTION here
        # rather than by a value that happened to match.
        skip = {bases["SND_REG_LR_AMS_FMS"]}
        # S&K's 25-byte record has no SSG-EG bytes at all; zSendFMInstrument does
        # not write $90. Ours does. That is a genuine extra write and is reported
        # under L2 rather than compared against a value that does not exist.
        ssg = {bases["SND_REG_OP_SSG_EG"] + i * OP_STRIDE for i in range(4)}
        common = (set(ours[vi]) & set(sk_regs)) - skip
        if not common:
            raise Unmeasurable(f"voice {vi}: no register is written by BOTH drivers")
        for reg in sorted(common):
            o, s = ours[vi][reg], sk_regs[reg]
            if o == s:
                continue
            if volflag.get(reg):
                # licensed: S&K defers +track volume to zSendTL; we bake at build
                # time. Report the residual, do not fail on it.
                vol_residual[(vi, reg)] = o - s
                continue
            fails.append(f"L1 voice {vi} reg ${reg:02X}: ours ${o:02X} != S&K ${s:02X}")
        extra = ssg & set(ours[vi])
        if a.verbose:
            print(f"  voice {vi}: {len(common)} shared registers compared, "
                  f"{len(extra)} SSG-EG registers written by us only, "
                  f"$B4 excluded (S&K sources it from track RAM)")
    if vol_residual:
        print("  carrier-TL residuals (S&K adds the track volume at upload time; we bake it):")
        for (vi, reg), d in sorted(vol_residual.items()):
            print(f"    voice {vi} reg ${reg:02X}: ours is {d:+d} TL steps "
                  f"({d * 0.75:+.2f} dB) vs S&K's un-added byte")
    print(f"  -> {'PASS' if not fails else 'FAIL'}"
          f" ({len([f for f in fails if f.startswith('L1')])} mismatches)")
    print()

    # --- L2 DELTA CLASS ----------------------------------------------------
    print(f"L2 DELTA CLASS (registers that change value, voice 0 -> voice {changed})")
    tl_regs = {bases["SND_REG_OP_TL"] + i * OP_STRIDE for i in range(4)}
    instant = tl_regs | {bases["SND_REG_ALG_FB"]}
    changed_regs = {r: (ours[0][r], ours[changed][r])
                    for r in ours[0] if ours[0][r] != ours[changed].get(r)}
    for r in sorted(changed_regs):
        o, n = changed_regs[r]
        cls = ("INSTANTANEOUS-AMPLITUDE" if r in instant
               else "envelope-slope / phase-continuous")
        print(f"  ${r:02X}+ch: ${o:02X} -> ${n:02X}   {cls}")
    bad = sorted(r for r in changed_regs
                 if r in instant and r not in tl_regs)
    if bad:
        fails.append("L2 a non-TL instantaneous-amplitude register changed: "
                     + ", ".join(f"${r:02X}" for r in bad))
    n_tl = len([r for r in changed_regs if r in tl_regs])
    print(f"  -> {'PASS' if not bad else 'FAIL'}"
          f" ({len(changed_regs)} registers move; {n_tl} of them TL)")
    print()

    # --- L3 DISCONTINUITY LEDGER (report only) ------------------------------
    alg = ours[changed][bases["SND_REG_ALG_FB"]] & 7
    mask = CARRIER_MASK[alg]
    print(f"L3 DISCONTINUITY LEDGER (algorithm {alg}, carrier mask %{mask:04b}, "
          "slot order S1,S3,S2,S4)")
    names = ["S1", "S3", "S2", "S4"]
    worst = 0
    for i in range(4):
        reg = bases["SND_REG_OP_TL"] + i * OP_STRIDE
        o, n = ours[0][reg], ours[changed][reg]
        role = "CARRIER " if (mask >> i) & 1 else "modulator"
        d = n - o
        worst = max(worst, abs(d))
        print(f"  {names[i]} (${reg:02X}+ch) {role}: TL ${o:02X} -> ${n:02X}  "
              f"{d:+d} steps = {-d * 0.75:+.2f} dB")
    print(f"  largest TL step across the change: {worst} steps = {worst * 0.75:.2f} dB")
    print("  (TL is consumed with no smoothing — Nuked-OPN2 adds eg_tl<<3 to the level")
    print("   every sample — so any TL step is a waveform discontinuity on the next")
    print("   sample, on ANY driver executing these bytes.)")
    print()

    if fails:
        print(f"FAILED ({len(fails)}):")
        for f in fails:
            print("  " + f)
        return 1
    print("ALL LEGS PASS — our mid-stream voice change writes S&K's values into S&K's")
    print("registers. The switch mechanism is not a difference between the two drivers.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Unmeasurable as e:
        print(f"UNMEASURABLE: {e}", file=sys.stderr)
        print("NOT A PASS — the run could not ask its question.", file=sys.stderr)
        sys.exit(2)
