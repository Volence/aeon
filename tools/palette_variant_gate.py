#!/usr/bin/env python3
"""palette_variant_gate — run the palette_dsl variant MIRROR against the ASM that derives.

WHY THIS EXISTS. `engine/effects/palette_dsl.emp` carries a comptime model of the variant
derive (`clamp07` / `variant_channel` / `variant_word`) plus three module-level `ensure()`
vectors, and `engine/effects/palette.emp` told the reader that the packing in
`Palette_DeriveVariant` was therefore "proven at build time". It was not. Nothing connected
the two halves: the mirror's only callers were its own ensures, so the model proved the model.
`Palette_DeriveVariant` could have shifted G by 4 instead of 5, clamped at 6, or ignored
`v_lines` entirely and every one of those ensures would still have gone green. That is the
dormant-scaffold-vs-claimed-guarantee mismatch booked as B2 in the 2026-08-18 raster/substrate
sweep adjudication, and this gate is what closes it.

WHAT IT ASSERTS, AND WHERE EACH EXPECTATION COMES FROM

  1. PINNED VECTORS ON HARDWARE. The three `ensure(variant_word($C, variant(...)) == $W)`
     lines are parsed OUT OF palette_dsl.emp — colour, variant kwargs and expected word, all
     three read from the source text, never retyped here. Each vector's variant is then poked
     into RAM as a real `pal_variant`, its colour is poked into the live `Palette_Buffer`, and
     the ENGINE'S OWN once-per-frame path (`Palette_Compose` -> `Palette_DoVariants` ->
     `Palette_DeriveVariant`) is allowed to run. The word the asm wrote into
     `Pal_Variant_Stage` must equal the word the .emp pinned. This is the link that was
     missing: the mirror's build-time proofs are now also proofs about the asm.

  2. BREADTH. A single entry can be right by accident, and a uniform buffer is the vacuity
     trap this tree has already been bitten by. So all 48 entries of CRAM lines 1-3 are filled
     with 48 different colours spanning the whole 3-bit-per-channel space, and every one is
     predicted independently by the model below.

  3. THE MODEL IS BOUND TO THE MIRROR. The Python in `variant_word()` here is a transcription
     of the .emp, and a transcription can drift. So before it is trusted for the breadth
     sweep it must reproduce all three parsed vectors exactly. A model edited away from the
     mirror fails that check by name and the gate stops.

  4. `v_lines` COVERAGE — an assertion the mirror never made at all. The constructor
     validates the mask at build time; nothing checked that the asm HONOURS it. A fourth
     fixture covers line 1 only, and lines 0/2/3 of the staging image must still hold the
     sentinel poked before the frame ran. Line 0 (the character's) is sentinel-checked under
     every fixture: the derive must never touch it.

ANTI-VACUITY. The proof that this observes the asm and not itself is a rebuild poison: flip
one shift in `Palette_DeriveVariant` (G's `lsr.w #5` -> `#4`) and every fixture fails by name
on the G channel while the build stays green, because the .emp ensures cannot see asm. Restore
and it goes green again. The setup is separately self-guarding: `Palette_Buffer` is read back
after the frame and a fill that did not survive is reported as SETUP (exit 2), never as a
verdict, so "something else recomposed the palette" can never be mistaken for "the derive is
wrong".

Usage:
    python3 tools/palette_variant_gate.py [--rom s4.debug.bin] [--lst s4.debug.lst]
Exit: 0 the asm agrees with the mirror · 1 it does not · 2 setup/boot error
"""
import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, "/home/volence/sonic_hacks/oracle/linux-port/harness")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aether import BusClient                                   # noqa: E402
from launcher import headless_emulator                         # noqa: E402
from raster_cost_probe import parse_lst                        # noqa: E402

AEON = Path(__file__).resolve().parent.parent
DSL = "engine/effects/palette_dsl.emp"

# Sentinel word poked over the whole staging slot before each frame. Not a legal Genesis
# colour (bits 0/4/8 and 12-15 are set), and `Palette_DeriveVariant` builds its output word
# from `moveq #0,d4` + three OR'd fields, so it can never emit this by accident.
SENTINEL = 0xA5A5

# The RAM the descriptors are poked into: staging slot 1. Slot 1's pointer is cleared by this
# gate, so nothing writes those 128 bytes while it runs, and the derive under test writes only
# slot 0. Using real engine RAM keeps the gate off any address it would have to hand-pick.
SCRATCH_SYM, SCRATCH_OFF = "Pal_Variant_Stage", 128

VARIANT_DEFAULTS = {"shift_r": 0, "bias_r": 0, "shift_g": 0, "bias_g": 0,
                    "shift_b": 0, "bias_b": 0, "lines": 0b1110}


# ---------------------------------------------------------------------------
# the mirror, transcribed — bound to palette_dsl.emp by check 3 above
# ---------------------------------------------------------------------------
def clamp07(x: int) -> int:
    if x < 0:
        return 0
    if x > 7:
        return 7
    return x


def variant_channel(chan3: int, shift: int, bias: int) -> int:
    return clamp07((chan3 >> shift) + bias)


def variant_word(c: int, v: dict) -> int:
    r = variant_channel((c >> 1) & 7, v["shift_r"], v["bias_r"])
    g = variant_channel((c >> 5) & 7, v["shift_g"], v["bias_g"])
    b = variant_channel((c >> 9) & 7, v["shift_b"], v["bias_b"])
    return (b << 9) | (g << 5) | (r << 1)


# ---------------------------------------------------------------------------
# reading the .emp — no expectation in this file is hand-typed
# ---------------------------------------------------------------------------
def emp_const(rel: str, name: str) -> int:
    """A `const NAME = <int>` out of an .emp source. Handles $hex, %binary and decimal."""
    txt = (AEON / rel).read_text()
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*"
                  r"(\$[0-9A-Fa-f]+|%[01]+|-?\d+)", txt, re.M)
    if not m:
        raise SetupError(f"cannot find `const {name}` in {rel}")
    v = m.group(1)
    if v.startswith("$"):
        return int(v[1:], 16)
    if v.startswith("%"):
        return int(v[1:], 2)
    return int(v)


def emp_num(tok: str) -> int:
    tok = tok.strip()
    neg = tok.startswith("-")
    if neg:
        tok = tok[1:].strip()
    if tok.startswith("$"):
        n = int(tok[1:], 16)
    elif tok.startswith("%"):
        n = int(tok[1:], 2)
    else:
        n = int(tok)
    return -n if neg else n


VECTOR_RE = re.compile(
    r"ensure\(\s*variant_word\(\s*(\$[0-9A-Fa-f]+|%[01]+|\d+)\s*,\s*"
    r"variant\(([^)]*)\)\s*\)\s*==\s*(\$[0-9A-Fa-f]+|%[01]+|\d+)\s*,")


def parse_vectors() -> list[dict]:
    """The `ensure(variant_word(C, variant(..)) == W)` proofs, straight out of palette_dsl.emp.

    Colour, variant kwargs and expected word all come from the source text. If the mirror's
    vectors are edited, this gate re-derives from the edit rather than asserting a stale copy.
    """
    txt = (AEON / DSL).read_text()
    out = []
    for m in VECTOR_RE.finditer(txt):
        v = dict(VARIANT_DEFAULTS)
        for part in m.group(2).split(","):
            part = part.strip()
            if not part:
                continue
            if ":" not in part:
                raise SetupError(f"unparsable variant() argument {part!r} in {DSL} — this gate "
                                 f"reads the mirror's vectors literally and cannot guess a "
                                 f"positional argument")
            k, val = part.split(":", 1)
            k = k.strip()
            if k not in VARIANT_DEFAULTS:
                raise SetupError(f"unknown variant() keyword {k!r} in {DSL}")
            v[k] = emp_num(val)
        out.append({"colour": emp_num(m.group(1)), "variant": v,
                    "want": emp_num(m.group(3))})
    if not out:
        raise SetupError(
            f"no `ensure(variant_word(...) == ...)` vectors found in {DSL}. They are what this "
            f"gate proves against the asm; if the mirror lost them, this gate has nothing to "
            f"assert and the 'checked against the asm' claim in palette.emp is false again.")
    return out


# ---------------------------------------------------------------------------
class SetupError(Exception):
    """Something made the measurement impossible. Not a verdict — exit 2, never exit 1."""


def descriptor_bytes(v: dict) -> str:
    """A wire-format `pal_variant` (palette.emp:130) as a hex image.

    v_shift_r u8, v_bias_r i8, v_shift_g u8, v_bias_g i8, v_shift_b u8, v_bias_b i8,
    v_lines u8, v_pad u8.
    """
    fields = [v["shift_r"], v["bias_r"], v["shift_g"], v["bias_g"],
              v["shift_b"], v["bias_b"], v["lines"], 0]
    return "".join(f"{b & 0xFF:02X}" for b in fields)


def test_colours() -> list[int]:
    """48 colour words for CRAM lines 1-3 — every R value, a spread of G and B.

    Deliberately NOT uniform: a uniform source buffer makes a per-entry assertion vacuous,
    which is a trap this tree has already paid for once.
    """
    out = []
    for i in range(48):
        r = i & 7
        g = (i >> 3) & 7
        b = (i * 5) & 7
        out.append((b << 9) | (g << 5) | (r << 1))
    return out


def buffer_image(colours: list[int]) -> str:
    """The 96-byte Palette_Buffer image for CRAM lines 1-3 — exactly what the derive reads.

    Line 0 is deliberately NOT poked. It is the character's line and the engine keeps writing
    its entry 0 (the backdrop colour) every frame, so a sentinel there would fail the survival
    check below on correct code. The derive never reads or writes line 0 either — that it
    leaves the STAGING image's line 0 alone is asserted separately, off the staging sentinel.
    """
    return "".join(f"{w:04X}" for w in colours)


async def derive(b: BusClient, sym: dict, v: dict, colours: list[int],
                 settle: int, label: str) -> list[int]:
    """Poke a descriptor + a source palette, let the engine derive one frame, read it back.

    Returns the 64 words of staging slot 0 (4 CRAM lines x 16 entries).
    """
    scratch = sym[SCRATCH_SYM] + SCRATCH_OFF
    stage = sym["Pal_Variant_Stage"]
    src = sym["Palette_Buffer"] + 32          # CRAM line 1; line 0 is engine-owned, see below
    buf_img = buffer_image(colours)

    await b.call("emulator/reset", {"wait": True, "run": False})
    await b.call("emulator/run_frames", {"frames": settle})
    # Freeze the camera FIRST: a section crossing reloads the base palette and rebinds the
    # scene's own variant, and that would read as a derive failure rather than a lost fixture.
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Debug_Scene_Freeze"]), "value": 1, "width": 1})
    await b.call("emulator/run_frames", {"frames": 2})

    # Silence every compose layer except the variant one, so nothing recomposes over the
    # source palette between the poke and the derive.
    for name in ("Pal_Base_Dirty", "Pal_Fade_Frames", "Pal_Op"):
        await b.call("emulator/write_memory", {"addr": hex(sym[name]), "value": 0, "width": 1})
    await b.call("emulator/write_memory", {"addr": hex(scratch), "bytes": descriptor_bytes(v)})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Pal_Variant_Ptr"]), "value": scratch, "width": 4})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Pal_Variant_Ptr"] + 4), "value": 0, "width": 4})
    await b.call("emulator/write_memory", {"addr": hex(src), "bytes": buf_img})
    # Sentinel the whole staging slot: an entry the derive never writes must be visibly
    # unwritten, which is what the v_lines coverage assertion reads.
    await b.call("emulator/write_memory",
                 {"addr": hex(stage), "bytes": f"{SENTINEL:04X}" * 64})
    # PAL_ACT_VARIANT | PAL_ACT_VARIANT_STALE and nothing else.
    act = emp_const("engine/effects/palette.emp", "PAL_ACT_VARIANT") | \
        emp_const("engine/effects/palette.emp", "PAL_ACT_VARIANT_STALE")
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Pal_Active"]), "value": act, "width": 1})

    await b.call("emulator/run_frames", {"frames": 2})

    back = (await b.call("emulator/read_memory",
                         {"addr": hex(src), "len": 96}))["bytes"].upper()
    if back != buf_img:
        raise SetupError(
            f"{label}: the source palette did not survive the frame — something else wrote "
            f"Palette_Buffer lines 1-3, so the staging image is not a function of the poked "
            f"input.\n        wrote {buf_img}\n        read  {back}")
    raw = (await b.call("emulator/read_memory", {"addr": hex(stage), "len": 128}))["bytes"]
    return [int(raw[i * 4:i * 4 + 4], 16) for i in range(64)]


async def run(sock: str, sym: dict, lst: str, settle: int, vectors: list[dict]) -> list[str]:
    fails: list[str] = []
    b = BusClient(socket_path=sock, client_id="palvar", client_name="palette_variant_gate")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})
    colours = test_colours()

    def check(label: str, cond: bool, detail: str) -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {label}: {detail}")
        if not cond:
            fails.append(label)

    for n, vec in enumerate(vectors):
        v = vec["variant"]
        desc = ", ".join(f"{k}:{v[k]}" for k in ("shift_r", "bias_r", "shift_g", "bias_g",
                                                 "shift_b", "bias_b") if v[k])
        name = f"vector {n} (${vec['colour']:04X} through {desc or 'identity'})"
        # The vector's own colour goes at line 1 entry 0; the rest of the 48 stay varied.
        cols = list(colours)
        cols[0] = vec["colour"]
        got = await derive(b, sym, v, cols, settle, name)

        # (1) the .emp's pinned word, produced by the ASM.
        check(f"{name} pinned word", got[16] == vec["want"],
              f"asm wrote ${got[16]:04X}; {DSL} pins ${vec['want']:04X}")

        # (2) breadth — every covered entry, predicted independently.
        bad = [(i, cols[i], got[16 + i], variant_word(cols[i], v))
               for i in range(48)
               if (v["lines"] >> (1 + i // 16)) & 1 and got[16 + i] != variant_word(cols[i], v)]
        check(f"{name} 48-entry sweep", not bad,
              "every covered entry matches the mirror" if not bad else
              f"{len(bad)} of 48 differ, first: line {1 + bad[0][0] // 16} entry "
              f"{bad[0][0] % 16} source ${bad[0][1]:04X} -> asm ${bad[0][2]:04X}, "
              f"mirror ${bad[0][3]:04X}")

        # (3) line 0 is the character's — the derive must never touch it.
        touched = [i for i in range(16) if got[i] != SENTINEL]
        check(f"{name} line 0 untouched", not touched,
              "sentinel intact" if not touched else
              f"entries {touched} were written (${got[touched[0]]:04X})")

    # (4) v_lines coverage — an assertion the mirror's own ensures never made. The
    # constructor validates the mask; this is the only thing that checks the asm obeys it.
    v = dict(VARIANT_DEFAULTS, shift_r=1, lines=0b0010)
    got = await derive(b, sym, v, colours, settle, "lines-mask fixture")
    covered = [i for i in range(16) if got[16 + i] == variant_word(colours[i], v)]
    check("lines %0010 writes line 1", len(covered) == 16,
          f"{len(covered)} of 16 line-1 entries match the mirror")
    stray = [i for i in range(16, 48) if got[16 + i] != SENTINEL]
    check("lines %0010 leaves lines 2-3 alone", not stray,
          "sentinel intact across both uncovered lines" if not stray else
          f"{len(stray)} entries written outside the mask, first at line "
          f"{1 + stray[0] // 16} entry {stray[0] % 16} (${got[16 + stray[0]]:04X})")

    await b.close()
    return fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(AEON / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    ap.add_argument("--settle", type=int, default=180)
    args = ap.parse_args()
    # Absolute: headless_emulator launches oracle with `env -C <oracle repo>`, so a RELATIVE
    # ROM path silently fails to load while every poke and read still answers ok against
    # blank RAM.
    rom, lst = str(Path(args.rom).resolve()), str(Path(args.lst).resolve())
    if not Path(rom).is_file():
        print(f"palette_variant_gate: ROM not found: {rom} — build it first", file=sys.stderr)
        return 2

    sym = parse_lst(lst)
    need = ("Palette_Buffer", "Pal_Variant_Stage", "Pal_Variant_Ptr", "Pal_Active",
            "Pal_Base_Dirty", "Pal_Fade_Frames", "Pal_Op", "Debug_Scene_Freeze")
    missing = [s for s in need if s not in sym]
    if missing:
        print(f"palette_variant_gate: symbols missing from the listing: {', '.join(missing)}",
              file=sys.stderr)
        return 2

    try:
        vectors = parse_vectors()
    except SetupError as e:
        print(f"palette_variant_gate: SETUP — {e}", file=sys.stderr)
        return 2

    # THE MODEL MUST BE THE MIRROR. Before it predicts anything, it has to reproduce every
    # vector the .emp pins. A transcription edited away from palette_dsl.emp stops here.
    drift = [v for v in vectors if variant_word(v["colour"], v["variant"]) != v["want"]]
    if drift:
        d = drift[0]
        print(f"palette_variant_gate: this gate's model disagrees with {DSL} — "
              f"${d['colour']:04X} gives ${variant_word(d['colour'], d['variant']):04X}, the "
              f".emp pins ${d['want']:04X}. Re-transcribe variant_word() from the mirror; "
              f"predicting the sweep with a drifted model would assert nothing.",
              file=sys.stderr)
        return 1

    print(f"palette_variant_gate  ROM {rom}")
    print(f"  model agrees with all {len(vectors)} pinned vectors in {DSL}")
    for n, v in enumerate(vectors):
        print(f"  vector {n}: ${v['colour']:04X} -> ${v['want']:04X}  {v['variant']}")
    print()

    try:
        with headless_emulator(rom) as sock:
            fails = asyncio.run(run(sock, sym, lst, args.settle, vectors))
    except SetupError as e:
        print(f"\npalette_variant_gate: SETUP — {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"\npalette_variant_gate: run error: {e}", file=sys.stderr)
        return 2

    if fails:
        print(f"\npalette_variant_gate: FAIL — {len(fails)} assertion(s): {', '.join(fails)}")
        return 1
    print("\npalette_variant_gate: OK — Palette_DeriveVariant produces what palette_dsl models")
    return 0


if __name__ == "__main__":
    sys.exit(main())
