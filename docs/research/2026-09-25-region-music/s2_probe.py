#!/usr/bin/env python3
"""THROWAWAY feasibility probe (docs/research/2026-09-25-region-music-design.md, Q1).
Run from the repo root:  python3 docs/research/2026-09-25-region-music/s2_probe.py [--write]
--write drops song_{ehz,cpz}.bin + {ehz,cpz}_patches.bin into games/sonic4/data/sound/ (gitignored)
for the slot-swap assemble test the design doc describes; delete them afterwards.

Original header: feasibility probe: run tools/smps_import.py on Sonic 2's EHZ + CPZ.

Applies the S2 (SourceDriver=2) -> S3K (SonicDriverVer>=3) conversions that
s2disasm/sound/_smps2asm_inc.asm itself defines, as a textual pre-pass:
  * smpsHeaderTempo div,mod  -> mod' = s2TempotoS3(mod) = (0x100 - mod) & 0xFF
  * smpsHeaderPSG pitch      -> pitch + psgdelta (12)       (PSGPitchConvert)
  * smpsModSet w,s,c,st      -> w+1, s, c, ((st+1)*s)&0xFF  (smpsModSet)
  * fTone_NN                 -> recorded, mapped to a placeholder (NO S2 PSG envs exist in engine)
  * S2 DAC enum              -> dKick $81 dSnare $82 dMidTom $8C dFloorTom $8E
Voices: parsed from the song's own <ZONE>_Voices smpsVc* block.
"""
import os, re, sys, collections

from pathlib import Path
WT = str(Path(__file__).resolve().parents[3])   # the aeon repo root
sys.path.insert(0, os.path.join(WT, "tools"))
import smps_import as si
from song_packer import pack_song

from suite_paths import require_suite_path
S2 = str(require_suite_path("s2disasm", "sound", "music", what="the Sonic 2 song sources"))

# S2 DAC enum (s2disasm _smps2asm_inc.asm:156-158, use_s2_samples arm)
S2_DAC = dict(dKick=0x81, dSnare=0x82, dClap=0x83, dScratch=0x84, dTimpani=0x85,
              dHiTom=0x86, dVLowClap=0x87, dHiTimpani=0x88, dMidTimpani=0x89,
              dLowTimpani=0x8A, dVLowTimpani=0x8B, dMidTom=0x8C, dLowTom=0x8D,
              dFloorTom=0x8E)
si.DAC_IDS.update(S2_DAC)
# _smps2asm_inc.asm:56-58, SonicDriverVer>=3 arm: nMaxPSG = nBb6 - psgdelta
si.NOTE_BYTES["nMaxPSG"] = si.NOTE_BYTES["nBb6"] - 12

ftones = collections.Counter()

def fix(lines):
    out = []
    for ln in lines:
        for t in re.findall(r"fTone_([0-9A-Fa-f]{2})", ln.split(";", 1)[0]):
            ftones[t] += 1
        ln = re.sub(r"fTone_", "sTone_", ln)
        code = ln.split(";", 1)[0]
        m = re.match(r"(\s*)smpsHeaderTempo\s+(\S+),\s*(\S+)", code)
        if m:
            mod = si.resolve_const(m.group(3))
            out.append("%ssmpsHeaderTempo %s, $%02X\n" % (m.group(1), m.group(2), (0x100 - mod) & 0xFF))
            continue
        m = re.match(r"(\s*)smpsHeaderPSG\s+(.*)", code)
        if m:
            a = [x.strip() for x in m.group(2).split(",")]
            a[1] = "$%02X" % ((si.resolve_const(a[1]) + 12) & 0xFF)
            out.append("%ssmpsHeaderPSG %s\n" % (m.group(1), ", ".join(a)))
            continue
        m = re.match(r"(\s*)smpsModSet\s+(.*)", code)
        if m:
            w, s, c, st = [si.resolve_const(x.strip()) for x in m.group(2).split(",")]
            out.append("%ssmpsModSet $%02X, $%02X, $%02X, $%02X\n" % (m.group(1), (w + 1) & 0xFF, s, c, ((st + 1) * s) & 0xFF))
            continue
        # placeholder: S2 fTone ids have NO engine envelope; mapped to sTone_ form so
        # resolve_const accepts it (the converter then warns + emits PsgEnv(0) if the id
        # is absent from the engine's S3K envelope table -- i.e. WRONG timbre either way).
        out.append(ln)
    return out

def voices(lines, label):
    i = next(k for k, l in enumerate(lines) if l.strip() == label + ":")
    blocks = si._parse_vc_blocks([l.split(";")[0] if "smpsVc" in l else l for l in lines], i + 1)
    return [si.smps_voice_to_fmpatch(b) for b in blocks]

for fn, zone in (("82 - EHZ.asm", "EHZ"), ("8E - CPZ.asm", "CPZ")):
    ftones.clear()
    src = open(os.path.join(S2, fn)).readlines()
    lines = fix(src)
    used_v = sorted({si.resolve_const(m) for l in src for m in re.findall(r"smpsSetvoice\s+(\S+)", l.split(";")[0])})
    used_d = sorted({S2_DAC[m] & 0x7F for l in src for m in re.findall(r"\b(d(?:Kick|Snare|MidTom|FloorTom|Clap|Timpani|HiTom|LowTom))\b", l.split(";")[0])})
    # placeholder DAC remap onto EXISTING engine ids (kick=2 snare=3 s3k_midtom=8 s3k_floortom=10)
    dac_remap = {1: 2, 2: 3, 0x0C: 8, 0x0E: 10}
    patch_remap = {v: i for i, v in enumerate(used_v)}
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf), contextlib.redirect_stdout(buf):
        song = si.convert_song(lines, dac_remap=dac_remap, patch_remap=patch_remap)
        blob = pack_song(song)
    vs = voices(src, zone + "_Voices")
    warns = collections.Counter(l.strip() for l in buf.getvalue().splitlines() if l.strip())
    print("== %s: song blob %d B, %d channels, tempo_mod $%02X; voices in bank %d, used %s -> patches %d B"
          % (zone, len(blob), len(song.channels), song.tempo_mod, len(vs),
             ["$%02X" % v for v in used_v], 32 * len(used_v)))
    print("   DAC ids used (1-based):", ["$%02X" % d for d in used_d], " fTone ids:", dict(ftones))
    print("   converter warnings (%d distinct, %d total):" % (len(warns), sum(warns.values())))
    for w, n in warns.most_common():
        print("     %4d x %s" % (n, w[:150]))
    if "--write" in sys.argv:
        out = os.path.join(WT, "games/sonic4/data/sound")
        pat = b"".join(bytes(vs[v]) + b"\0" * (32 - len(vs[v])) for v in used_v)
        open(os.path.join(out, "song_%s.bin" % zone.lower()), "wb").write(blob)
        open(os.path.join(out, "%s_patches.bin" % zone.lower()), "wb").write(pat)
        print("   wrote song_%s.bin (%d) + %s_patches.bin (%d)" % (zone.lower(), len(blob), zone.lower(), len(pat)))
