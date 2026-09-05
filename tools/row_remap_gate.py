#!/usr/bin/env python3
"""row_remap_gate — the ROW REMAP LADDER's three invariants, checked IN THE BUILT ROM.

EFFECTS-W1 item 9, parcel 9a. The ladder is generated at comptime by
`row_remap_ladder16()` (engine/level/parallax_dsl.emp), and that generator's own
construction is what makes the invariants true. THIS GATE DOES NOT ASK THE GENERATOR. It
reads the bytes out of the linked image, at the address the listing gives, and re-checks
them — because "the generator is right" and "the right bytes reached the ROM" are two
different claims, and only the second one is what the 68000 indexes through.

THE THREE INVARIANTS, and each is a correctness property rather than a style one:

  entry[i] >= i         The permute is IN PLACE and FORWARD — Parallax_Fill_PerLine's pass
                        uses one address for both the read base and the write cursor, which
                        is S3K's own shape (sonic3k.asm:105849-105850). A line either reads a
                        slot it has not written yet or reads its own value back. Break this
                        and the loop feeds on its own output, which does not crash and does
                        not look obviously wrong.
  entry non-decreasing  Rows are reordered, repeated and dropped; never SWAPPED. A descending
                        pair is a scroll word travelling backwards down the band, which reads
                        as a tear rather than as compression.
  entry[i] <= 2i        The READ BOUND. It is what lets the pass cap the remapped run at
                        span/2 and know every fetch lands inside the band's OWN longwords.
                        Without it a tall |p| over a short band pulls the NEXT band's scroll
                        words into this one — which looks like a plausible effect and is not
                        one.

Plus the SHAPE: the emitted table must be exactly (H+1) rows of H bytes, with H derived from
the height shift authored on the band record — never typed here.

AND, SINCE 2026-09-04 (parcel 9b), MODEL AGREEMENT. The three invariants are satisfied by
MANY tables — the identity satisfies all three — so they say the emitted bytes are SAFE and
cannot say they are THIS MODEL. That arm re-derives the whole table from
`tools/row_remap_ladder_gen.py` at the H the record declares and compares. It is not a byte
pin: nothing checked in is being matched, the table is recomputed from the parameterised
model that `engine/level/parallax_dsl.emp`'s `row_remap_ladder16()` is one instantiation of.
Two spellings of one model are two models unless something holds them together.

AND, SINCE 2026-09-03, THE VISIBILITY ARM — because "the mechanism is live" was not the bar
and had never been the bar. Parcel 9a shipped gated five ways, separating from its own flat
control on 12 of 12 samples, and the owner looked at the screen and said "I don't see the
effect at all". Every gate on it had asked a BOOLEAN question — does a band remap, does the
ladder permute, does the source vary — and every one of them answered yes truthfully about a
four-pixel wobble.

So this arm asks the MAGNITUDE question, on the linked image: it reads the config's own
plane-B deform table pointer and the shift that actually reaches the remapped band's lines,
and computes the peak-to-peak horizontal travel in pixels. That number is not a proxy — it is
exactly what a bus read of Hscroll_Buffer reports across those lines, verified against the
machine both ways before it was trusted (Shimmer at shift 2 computes 4 and the live buffer
measured 4; at shift 0 it computes 16 and the live buffer measured 16).

⚠ THE FAILURE IT REFUSES IS NOT THE ONE THE DESIGN NAMED, and conflating them is what cost a
night. Design §9.1 precondition 1 is REMAPPING A CONSTANT — a flat source, where the permute
is byte-for-byte the identity. That is a real trap and `scene()` refuses it. What happened on
2026-09-03 was the OTHER one: a source that varies correctly, on exactly the right rows, by an
amount too small to see. The proposed fix for the first (move the band to where the variation
is) would have produced a second invisible screen, because the band was already there.

AND THE BINDING REPORT (design §9.2 step 3), which is PRINTED and not gated. Precondition 4
— "the bound section must permit vertical camera travel across the anchor line" — is not
machine-checkable: in a section the camera only crosses horizontally the effect is a still
picture and nobody will find it. It belongs in a gate's OUTPUT, where a reviewer sees it, and
not in its exit code, where it would become a guess with authority.

WHAT THIS GATE DELIBERATELY DOES NOT DO. It does not run an emulator and it does not look at
Hscroll_Buffer. Whether the pass actually RAN, on the band the mark named, with the ladder row
the perspective quantity selected, is tools/row_remap_witness.py's question, and it needs a
machine. Keeping them apart is what lets this one be build-fatal in every canonical shape.

⚠ A GAME WITH NO LADDER IS A PASS, AND IT IS DERIVED, NOT ASSUMED. `demo` declares no
CAP_ROW_REMAP and emits no ladder, so there is nothing in its image to check. That is read off
the game's own SCANLINE_CAPS and CAP_ROW_REMAP declarations — if a game DECLARES the bit and
its image carries no ladder, that is a FAILURE, not an absence. A gate that answered "no
symbol, nothing to do" would pass hardest exactly when the emission had been lost.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXIT_OK, EXIT_FAIL, EXIT_UNMEASURABLE = 0, 1, 2


class Unmeasurable(RuntimeError):
    pass


def parse_lst(path: str) -> dict:
    out = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            m = re.match(r"\(\d+\) \d+/([0-9A-Fa-f]+) :\s+(\S+):", ln)
            if m:
                out[m.group(2)] = int(m.group(1), 16)
    if not out:
        raise Unmeasurable(f"{path} yielded no symbols — not a sigil listing")
    return out


def cap_bit(repo: str, name: str) -> int:
    text = open(os.path.join(repo, "engine/level/scene_dsl.emp"), encoding="utf-8").read()
    m = re.search(r"pub const " + name + r"\s+= \$([0-9A-Fa-f]+)", text)
    if not m:
        raise Unmeasurable(f"{name} is not declared in engine/level/scene_dsl.emp")
    return int(m.group(1), 16)


def game_caps(repo: str, game: str) -> int:
    """This game's declared mask. BOTH SPELLINGS ARE ACCEPTED because both ship: sonic4
    writes `$07DE` and demo writes a bare `0`, and a regex that only knew the hex form
    reported demo as UNMEASURABLE — which on a four-shape gate is two shapes silently not
    gated. Measured 2026-09-03."""
    p = os.path.join(repo, "games", game, "config", "game.emp")
    if not os.path.isfile(p):
        raise Unmeasurable(f"{p} does not exist — cannot read this game's SCANLINE_CAPS")
    text = open(p, encoding="utf-8").read()
    m = re.search(r"const SCANLINE_CAPS = \$([0-9A-Fa-f]+)", text)
    if m:
        return int(m.group(1), 16)
    m = re.search(r"const SCANLINE_CAPS = (\d+)", text)
    if not m:
        raise Unmeasurable(f"SCANLINE_CAPS is not declared in {p}")
    return int(m.group(1))


def pcfg_offset(repo: str, want: str) -> int:
    """A parallax_config field's byte offset, WALKED off engine/structs.emp rather than typed.
    The first draft of this gate typed 25 for pcfg_anchor_ch (it is 11) and reported a correct
    ROM as broken — the gate measuring the gate, which is the failure mode a hand-copied
    offset always has."""
    text = open(os.path.join(repo, "engine/structs.emp"), encoding="utf-8").read()
    m = re.search(r"pub struct parallax_config[^{]*\{(.*?)\n\}", text, re.S)
    if not m:
        raise Unmeasurable("could not find `pub struct parallax_config` in engine/structs.emp")
    widths = {"u8": 1, "u16": 2, "u32": 4, "*u8": 4, "i8": 1, "i16": 2}
    off = 0
    for name, ty in re.findall(r"\n\s+(pcfg_\w+):\s+(\*?[iu]\d+)[,\s]", m.group(1)):
        if want is not None and name == want:
            return off
        off += widths[ty]
    if want is None:
        return off          # the whole header's length
    raise Unmeasurable(f"parallax_config has no field {want!r}")


def pcfg_size(repo: str) -> int:
    """The config header's length — SUMMED over parallax_config's own fields, because the
    struct carries no `(size: N)` claim. It is the stride between a config's base and its
    band array, and the design's own note that the header is 30 bytes is a fact about the
    fields, not a declaration to read."""
    return pcfg_offset(repo, None)


def record_geometry(repo: str) -> tuple[int, int]:
    """(offsetof(band_record, br_remap), sizeof(band_record)) — derived from the four tail
    declarations and their capability counts, never typed."""
    text = open(os.path.join(repo, "engine/level/parallax.emp"), encoding="utf-8").read()
    sizes = {}
    for nm in ("band_ext", "band_curve", "band_drift", "band_remap"):
        m = re.search(r"pub struct " + nm + r" \(size: (\d+)\)", text)
        if not m:
            raise Unmeasurable(f"could not size `{nm}`")
        sizes[nm] = int(m.group(1))
    ram = open(os.path.join(repo, "engine/ram.emp"), encoding="utf-8").read()
    m = re.search(r"const BAND_ENTRY_LEN\s+= (\d+)", ram)
    if not m:
        raise Unmeasurable("could not read BAND_ENTRY_LEN from engine/ram.emp")
    sizes["band_entry"] = int(m.group(1))
    ns = {}
    for nm in ("BAND_EXT_N", "BAND_CURVE_N", "BAND_DRIFT_N", "BAND_REMAP_N"):
        m = re.search(r"pub const " + nm + r" = (\d+)", text)
        if not m:
            raise Unmeasurable(f"could not read `{nm}`")
        ns[nm] = int(m.group(1))
    tail = (sizes["band_entry"] + sizes["band_ext"] * ns["BAND_EXT_N"]
            + sizes["band_curve"] * ns["BAND_CURVE_N"]
            + sizes["band_drift"] * ns["BAND_DRIFT_N"])
    return tail, tail + sizes["band_remap"] * ns["BAND_REMAP_N"], ns["BAND_REMAP_N"]


def band_entry_offset(repo: str, want: str) -> int:
    """A band_entry field's displacement, WALKED off engine/level/parallax.emp. Same
    discipline as pcfg_offset above and for the same measured reason."""
    text = open(os.path.join(repo, "engine/level/parallax.emp"), encoding="utf-8").read()
    m = re.search(r"pub struct band_entry \{(.*?)\n\}", text, re.S)
    if not m:
        raise Unmeasurable("could not find `pub struct band_entry` in engine/level/parallax.emp")
    widths = {"u8": 1, "u16": 2, "u32": 4, "*u8": 4, "i8": 1, "i16": 2}
    off = 0
    for name, ty in re.findall(r"\n\s+(\w+):\s+(\*?[iu]\d+),", m.group(1)):
        if name == want:
            return off
        off += widths[ty]
    raise Unmeasurable(f"band_entry has no field {want!r}")


def struct_field_offset(repo: str, struct: str, want: str) -> int:
    """A field's displacement inside any `pub struct` in engine/level/parallax.emp.

    `band_entry_offset` above is this walk specialised to one struct; the visibility arm
    needs the same walk over `band_curve`, so the general one lives here and that one is
    left alone (it is quoted by name in the arms that use it). Same discipline, same
    reason: never type a displacement a declaration already states."""
    text = open(os.path.join(repo, "engine/level/parallax.emp"), encoding="utf-8").read()
    m = re.search(r"pub struct " + re.escape(struct) + r"[^{]*\{(.*?)\n\}", text, re.S)
    if not m:
        raise Unmeasurable(f"could not find `pub struct {struct}` in "
                           f"engine/level/parallax.emp")
    widths = {"u8": 1, "u16": 2, "u32": 4, "*u8": 4, "i8": 1, "i16": 2}
    off = 0
    for name, ty in re.findall(r"\n\s+(\w+):\s+(\*?[iu]\d+),", m.group(1)):
        if name == want:
            return off
        off += widths[ty]
    raise Unmeasurable(f"{struct} has no field {want!r}")


def curve_geometry(repo: str) -> tuple:
    """(offset of band_curve.bc_flags inside a band_record, CURVE_FLAG_ACTIVE_BIT), or
    (None, None) when this game compiles BAND_CURVE_N = 0 and no band can carry a curve.

    DERIVED, never typed — the tail's position is `sizeof(band_entry) + sizeof(band_ext) *
    BAND_EXT_N`, exactly the prefix `record_geometry` already sums, and the bit position is
    the `pub const` in engine/level/parallax.emp that `Parallax_Fill_PerLine` btsts.

    THE (None, None) CASE IS NOT AN UNMEASURABLE. With the capability compiled out there is
    no curve tail, so "does this band carry an active curve" has a correct answer and it is
    NO for every band. Raising Unmeasurable there would refuse a game that simply does not
    have the feature."""
    text = open(os.path.join(repo, "engine/level/parallax.emp"), encoding="utf-8").read()
    m = re.search(r"pub const BAND_CURVE_N = (\d+)", text)
    if not m:
        raise Unmeasurable("could not read `BAND_CURVE_N` from engine/level/parallax.emp")
    if int(m.group(1)) == 0:
        return None, None
    m = re.search(r"pub const CURVE_FLAG_ACTIVE_BIT\s*=\s*(\d+)", text)
    if not m:
        raise Unmeasurable("CURVE_FLAG_ACTIVE_BIT is not declared in "
                           "engine/level/parallax.emp — the arm that reads a band's curve "
                           "bit cannot name the bit")
    bit = int(m.group(1))
    ram = open(os.path.join(repo, "engine/ram.emp"), encoding="utf-8").read()
    m2 = re.search(r"const BAND_ENTRY_LEN\s+= (\d+)", ram)
    if not m2:
        raise Unmeasurable("could not read BAND_ENTRY_LEN from engine/ram.emp")
    m3 = re.search(r"pub struct band_ext \(size: (\d+)\)", text)
    m4 = re.search(r"pub const BAND_EXT_N = (\d+)", text)
    if not (m3 and m4):
        raise Unmeasurable("could not size the band_ext tail that precedes band_curve")
    prefix = int(m2.group(1)) + int(m3.group(1)) * int(m4.group(1))
    return prefix + struct_field_offset(repo, "band_curve", "bc_flags"), bit


def visibility_floor(repo: str) -> int:
    """REMAP_VISIBLE_MIN_PX, read from engine/level/parallax_dsl.emp — the SAME constant the
    comptime guard beside the scene uses. Two copies of a threshold is two thresholds."""
    text = open(os.path.join(repo, "engine/level/parallax_dsl.emp"), encoding="utf-8").read()
    m = re.search(r"pub const REMAP_VISIBLE_MIN_PX = (\d+)", text)
    if not m:
        raise Unmeasurable("REMAP_VISIBLE_MIN_PX is not declared in engine/level/parallax_dsl.emp")
    return int(m.group(1))


def asr(v: int, n: int) -> int:
    """68000 `asr.w` — floor division by 2^n. Python's >> already floors."""
    return v >> n


def excursion(rom: bytes, table_addr: int, shift: int) -> int:
    """The band's peak-to-peak horizontal travel in PIXELS, from the emitted 256-byte signed
    table at the emitted shift: max(asr(t,s)) - min(asr(t,s)).

    This is the SAME arithmetic as `deform_excursion` in engine/level/parallax_dsl.emp, and
    the duplication is the point — one side reads the generator's comptime array, this one
    reads the bytes that actually linked. A table that was generated correctly and emitted at
    the wrong address, or a shift the lowering dropped, separates the two."""
    tbl = [b - 256 if b >= 128 else b for b in rom[table_addr:table_addr + 256]]
    if len(tbl) != 256:
        raise Unmeasurable(f"the deform table at ${table_addr:06X} runs past the image")
    vals = [asr(t, shift) for t in tbl]
    return max(vals) - min(vals)


def ladder_symbols(syms: dict) -> list[str]:
    return sorted(n for n in syms if n.startswith("RowRemapLadder_"))


def generator_ladder(H: int) -> bytes:
    """The ladder `tools/row_remap_ladder_gen.py` produces at this H (parcel 9b).

    ⚠ THIS IS NOT A BYTE PIN AND THE DIFFERENCE MATTERS. A pin would be a checked-in blob
    that goes red on any deliberate change to H or to the model and never says which. This
    RE-DERIVES the table from the parameterised generator and holds the linked image against
    it, so it is an AGREEMENT between the model's two spellings: `row_remap_ladder16()`, the
    `.emp` comptime fn that ships (fixed H, because an `.emp` fn must return a concrete array
    type), and `row_remap_ladder_gen.py`, the same model with H as an argument. Two spellings
    of one model is two models unless something checks. Change the model on purpose and BOTH
    sides move together; change one and this is the arm that notices.

    A MISSING GENERATOR IS UNMEASURABLE, never a skip — same rule as everything else here."""
    path = os.path.join(REPO, "tools/row_remap_ladder_gen.py")
    if not os.path.isfile(path):
        raise Unmeasurable(
            f"{path} does not exist — the ROM's ladder cannot be held against the model it is "
            f"supposed to be an instantiation of (EFFECTS-W1 item 9b).")
    import importlib.util
    spec = importlib.util.spec_from_file_location("row_remap_ladder_gen", path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        return mod.ladder(H)
    except Exception as exc:
        raise Unmeasurable(f"tools/row_remap_ladder_gen.py could not produce a ladder at "
                           f"H={H}: {exc}")


def check_ladder(rom: bytes, addr: int, hshift: int, name: str, out: list) -> list:
    H = 1 << hshift
    rows = H + 1
    need = rows * H
    if addr + need > len(rom):
        return [f"{name}: the declared (H+1)xH table ({rows}x{H} = {need} B) runs past the "
                f"{len(rom)}-byte image from ${addr:06X}"]
    bad = []
    moved = 0
    for r in range(rows):
        row = rom[addr + r * H: addr + (r + 1) * H]
        prev = -1
        for i, v in enumerate(row):
            if v < i:
                bad.append(f"{name}: row {r} entry {i} = {v} < i — the in-place forward "
                           f"permute would read a slot it has already written")
                break
            if v > 2 * i:
                bad.append(f"{name}: row {r} entry {i} = {v} > 2i — the pass caps its run at "
                           f"span/2 on the strength of this bound, so the fetch would leave "
                           f"the band")
                break
            if v < prev:
                bad.append(f"{name}: row {r} entry {i} = {v} descends from {prev} — a scroll "
                           f"word travelling backwards down the band is a tear, not compression")
                break
            prev = v
        if r != H and list(row) != list(range(H)):
            moved += 1
    if moved == 0:
        bad.append(f"{name}: EVERY row is the identity. The three invariants above cannot see "
                   f"this — `entry[i] = i` satisfies all of them — but a remap through the "
                   f"identity writes the buffer back unchanged and NOTHING IS ON SCREEN. This "
                   f"is design §9.1 precondition 1 in the ladder rather than in the source")
    out.append(f"    {name} @ ${addr:06X}: {rows} rows x {H} bytes = {need} B")
    out.append(f"      rows differing from the identity: {moved} of {rows - 1} "
               f"(row {H} is the identity by construction and is exempt)")
    out.append(f"      row 0 (max |p|) tail : {list(rom[addr + H - 8:addr + H])}  "
               f"(identity would be {list(range(H - 8, H))})")
    out.append(f"      row {rows - 1} (|p| = 0): {list(rom[addr + (rows - 1) * H + H - 8:addr + rows * H])}  "
               f"(the identity, by construction)")

    # ---- THE MODEL-AGREEMENT ARM (parcel 9b, 2026-09-04) ----
    # The three invariants above are satisfied by MANY tables — the identity satisfies all
    # three, and so does any other monotone forward permute inside the bound. They say the
    # emitted bytes are SAFE; they cannot say the emitted bytes are THIS MODEL. This arm does,
    # by re-deriving the table at the H the record declares and comparing.
    linked = list(rom[addr:addr + need])
    want = list(generator_ladder(H))
    if linked != want:
        first = next(i for i in range(need) if linked[i] != want[i])
        bad.append(
            f"{name}: the linked table and tools/row_remap_ladder_gen.py at H={H} DISAGREE. "
            f"First difference at flat index {first} (row {first // H}, line {first % H}): "
            f"ROM has {linked[first]}, the generator derives {want[first]}; "
            f"{sum(1 for a, b in zip(linked, want) if a != b)} of {need} bytes differ. "
            f"engine/level/parallax_dsl.emp's row_remap_ladder16() and the generator are two "
            f"spellings of ONE model — if they have separated, one of them was edited alone.")
    else:
        out.append(f"      agrees byte-for-byte with tools/row_remap_ladder_gen.py at H={H} "
                   f"({need} B re-derived, not pinned)")
    return bad


def band_tails(rom: bytes, syms: dict, tail_off: int, stride: int,
               hdr_len: int, anchor_off: int, offs: dict = None) -> list[dict]:
    """Every emitted parallax config's bands, with their remap tails decoded. The config
    records are `ParallaxConfig_*` and `EditorSceneBinding_*` labels; a config's band count is
    its first header byte (pcfg_band_count), read from the image rather than assumed."""
    found = []
    for name, addr in sorted(syms.items(), key=lambda kv: kv[1]):
        if not (name.startswith("ParallaxConfig_") or name.startswith("EditorSceneBinding_")):
            continue
        a = addr & 0xFFFFFF
        if a + hdr_len > len(rom):
            continue
        n = rom[a]
        if not (1 <= n <= 16):
            continue
        for b in range(n):
            base = a + hdr_len + stride * b
            if base + stride > len(rom):
                break
            ladder = int.from_bytes(rom[base + tail_off:base + tail_off + 4], "big")
            if ladder == 0:
                continue
            rec = {
                "config": name, "band": b, "ladder": ladder & 0xFFFFFF,
                "plane_y": int.from_bytes(rom[base + tail_off + 4:base + tail_off + 6], "big"),
                "hshift": rom[base + tail_off + 6],
                "anchor_ch": rom[base + tail_off + 7],
                "anchor_ch_hdr": rom[a + anchor_off],
            }
            if offs:
                # THE THREE BYTES THE VISIBILITY ARM NEEDS, all out of the linked image.
                rec["deform_table_bg"] = int.from_bytes(
                    rom[a + offs["tbl"]:a + offs["tbl"] + 4], "big") & 0xFFFFFF
                rec["anchor_dsb"] = rom[a + offs["adsb"]]
                rec["band_dsb"] = rom[base + offs["bdsb"]]
                # THE CURVE BIT, out of the same linked image and off THIS band's record.
                # `offs["curve"]` is None only when BAND_CURVE_N == 0, i.e. no band in this
                # game HAS a curve tail — which is a definite NO, not a missing reading.
                rec["curve_active"] = (
                    0 if offs["curve"] is None
                    else (rom[base + offs["curve"]] >> offs["curve_bit"]) & 1)
            found.append(rec)
    return found


def effective_dsb(t: dict) -> tuple:
    """WHICH shift actually reaches the remapped band's lines, and why — returned with its
    reason so the report can say it rather than the reader having to know it.

    The remapped band is the anchored split's LOWER half, by construction: Step 4b splits the
    band the anchor line falls in and Parallax_Fill_PerLine's last-mark-wins takes the lower
    piece (see the mark banner in engine/level/parallax.emp). The overlay writes the config's
    pcfg_anchor_dsb into every band from the split DOWN — so on an anchored config it is the
    anchor's shift that reaches these lines, not the band's authored one, and reading the
    band's own byte there would report the no-deform sentinel 15 and a 0 px excursion on a
    scene that is working. Without an anchor the band keeps its own."""
    if t.get("anchor_ch_hdr", 0xFF) != 0xFF:
        return t["anchor_dsb"], "the config's pcfg_anchor_dsb (the overlay writes it into every band from the split down, and the remapped band IS the split's lower half)"
    return t["band_dsb"], "the band's own band_deform_shift_b (this config declares no anchor)"


def band_varies(t: dict) -> tuple:
    """(does this band's plane-B scroll take a PER-LINE value, why) — the visibility arm's
    one decision, as a function so it can be exercised on mutated bytes below.

    TWO SOURCES, EITHER SUFFICIENT, which is `scene()`'s own comptime guard restated over
    the emitted record rather than over the authored scene:

      * A DEFORM TABLE on the config (`pcfg_deform_table_bg` non-NULL). The sample loop
        indexes it per line. This is the shipped waterline's source.
      * AN ACTIVE CURVE on the band (`band_curve.bc_flags` bit CURVE_FLAG_ACTIVE_BIT). The
        curve hoist decodes the far-end factor to a real scroll value and Bresenhams
        `spread/span` per line, so every line differs BY CONSTRUCTION.

    A curve layer structurally cannot also carry a live deform amplitude — `layer()` refuses
    `curve` together with `dsa`/`dsb` != 15 — so demanding the table of a curve band asks for
    something the constructor forbids. That was this arm's bug until 2026-09-05; see the
    banner at its call site and docs/witness/rowremap-gate-vs-guard-2026-09-05.md."""
    if t["deform_table_bg"] != 0:
        return True, "a deform table is attached to the config"
    if t["curve_active"]:
        return True, "the band carries an active curve"
    return False, "no deform table and no active curve"


def visibility_arm_self_test(rom: bytes, syms: dict, tail_off: int, stride: int,
                             hdr_len: int, anchor_off: int, offs: dict,
                             out: list) -> list:
    """THE ARM THAT TESTS THE ARM, on the REAL linked record, by MUTATING BYTES.

    ⚠ WHY THIS EXISTS AND WHY IT IS NOT A UNIT TEST. The visibility arm's 2026-09-05 fix
    turns on ONE bit in ONE byte at a DERIVED offset inside the band record. Three things
    can be wrong with that and only one of them is the logic: the offset can be derived
    wrong, the bit position can be read wrong, and the decision can be right about a dict
    while reading the wrong byte. A fixture built from this file's own model would agree
    with all three mistakes. So the subject here is the SHIPPED record, out of the image the
    gate was just handed, mutated in place — the mutation is quoted from disk by
    construction because the thing being mutated came off disk.

    The three cases, and each one is a different prediction:

      NULL table + curve bit SET   -> VARIES     (the case the old arm refused; the fix)
      NULL table + curve bit CLEAR -> DOES NOT   (the control: the fix did not make the arm
                                                  vacuous — a genuinely flat band is still
                                                  caught)
      the record UNMUTATED         -> VARIES     (the shipped waterline, unchanged)

    LOUD, NEVER SKIPPED: reaching this with no remapped band is Unmeasurable. It cannot go
    vacuous quietly, because the caller only gets here when the capability is declared and
    the main arm has already refused an image with no subject."""
    live = band_tails(rom, syms, tail_off, stride, hdr_len, anchor_off, offs)
    if not live:
        raise Unmeasurable("the visibility arm's self-test has no remapped band to mutate")
    t0 = live[0]
    a = next((v & 0xFFFFFF for k, v in syms.items() if k == t0["config"]), None)
    if a is None:
        raise Unmeasurable(f"cannot re-find the config symbol {t0['config']} to mutate")
    base = a + hdr_len + stride * t0["band"]

    def decide(null_table: bool, curve_bit: int) -> bool:
        img = bytearray(rom)
        if null_table:
            img[a + offs["tbl"]:a + offs["tbl"] + 4] = b"\x00\x00\x00\x00"
        if offs["curve"] is not None:
            p = base + offs["curve"]
            img[p] = (img[p] | (1 << offs["curve_bit"])) if curve_bit else \
                     (img[p] & ~(1 << offs["curve_bit"]) & 0xFF)
        again = band_tails(bytes(img), syms, tail_off, stride, hdr_len, anchor_off, offs)
        hit = next((x for x in again
                    if x["config"] == t0["config"] and x["band"] == t0["band"]), None)
        if hit is None:
            raise Unmeasurable("the mutated image no longer carries the band being tested — "
                               "the mutation reached the remap tail, which it must not")
        return band_varies(hit)[0]

    if offs["curve"] is None:
        out.append("    visibility self-test: NOT RUN — this game compiles BAND_CURVE_N = 0, "
                   "so no band has a curve tail and the OR arm has nothing to exercise. The "
                   "table arm below still ran.")
        if decide(True, 0):
            return ["visibility self-test: with BAND_CURVE_N = 0 and the table NULLed, the "
                    "arm still reports the band as varying — it is reading something that "
                    "is not there"]
        return []

    bad = []
    if not decide(True, 1):
        bad.append("visibility self-test: with pcfg_deform_table_bg NULLed and "
                   "CURVE_FLAG_ACTIVE_BIT SET on the real band record, the arm still says "
                   "this band does not vary. That is the exact case the 2026-09-05 ruling "
                   "corrected — either the bc_flags offset or the bit position is wrong")
    if decide(True, 0):
        bad.append("visibility self-test: with pcfg_deform_table_bg NULLed and "
                   "CURVE_FLAG_ACTIVE_BIT CLEAR, the arm says the band varies anyway. The "
                   "fix has gone VACUOUS — a genuinely flat band would now pass")
    if not decide(False, 1):
        bad.append("visibility self-test: the UNMUTATED shipped record does not read as "
                   "varying — the parse itself is wrong, not the decision")
    if not bad:
        out.append(f"    visibility self-test on {t0['config']} band {t0['band']} "
                   f"(bc_flags at record offset {offs['curve']}, bit {offs['curve_bit']}): "
                   f"NULL+curve VARIES · NULL+no-curve DOES NOT · unmutated VARIES — 3/3")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--rom", required=True)
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--game", default="sonic4")
    ap.add_argument("--built-after", type=float, default=None,
                    help="epoch seconds; listing and ROM must both post-date it")
    a = ap.parse_args()

    try:
        if a.built_after is not None:
            for p in (a.lst, a.rom):
                if not os.path.isfile(p):
                    raise Unmeasurable(f"{p} does not exist")
                if os.path.getmtime(p) < a.built_after:
                    raise Unmeasurable(
                        f"{p} predates this build ({os.path.getmtime(p):.0f} < {a.built_after:.0f}) "
                        f"— it is a PREVIOUS invocation's artifact and gating on it would be "
                        f"measuring the wrong ROM")
        syms = parse_lst(a.lst)
        rom = open(a.rom, "rb").read()
        tail_off, stride, remap_n = record_geometry(a.repo)
        caps = game_caps(a.repo, a.game)
        anchor_off = pcfg_offset(a.repo, "pcfg_anchor_ch")
        hdr_len = pcfg_size(a.repo)
        bit = cap_bit(a.repo, "CAP_ROW_REMAP")
        declared = bool(caps & bit)
        offs = {"tbl": pcfg_offset(a.repo, "pcfg_deform_table_bg"),
                "adsb": pcfg_offset(a.repo, "pcfg_anchor_dsb"),
                "bdsb": band_entry_offset(a.repo, "band_deform_shift_b")}
        offs["curve"], offs["curve_bit"] = curve_geometry(a.repo)
        floor_px = visibility_floor(a.repo)
    except Unmeasurable as e:
        print(f"row_remap_gate: UNMEASURABLE — {e}")
        return EXIT_UNMEASURABLE

    print(f"row_remap_gate: {a.game} SCANLINE_CAPS ${caps:04X}, CAP_ROW_REMAP ${bit:04X} "
          f"-> declared={declared}; BAND_REMAP_N={remap_n}, br_remap at record offset "
          f"{tail_off}, sizeof(band_record)={stride}, header {hdr_len} B, "
          f"pcfg_anchor_ch at {anchor_off}")

    names = ladder_symbols(syms)
    tails = band_tails(rom, syms, tail_off, stride, hdr_len, anchor_off, offs) if remap_n else []

    if not declared:
        # DERIVED, not assumed: an undeclared game must emit NEITHER a ladder NOR a tail that
        # points at one. Both directions, so the absence is a checked fact.
        bad = []
        if names:
            bad.append(f"{a.game} does not declare CAP_ROW_REMAP but the image carries "
                       f"{names} — a table nothing can index")
        if tails:
            bad.append(f"{a.game} does not declare CAP_ROW_REMAP but {len(tails)} band(s) "
                       f"carry a non-NULL ladder pointer")
        if bad:
            print("row_remap_gate: FAIL")
            for b in bad:
                print("  - " + b)
            return EXIT_FAIL
        print("row_remap_gate: OK — capability undeclared, and the image carries no ladder "
              "symbol and no non-NULL remap tail (both checked)")
        return EXIT_OK

    problems, report = [], []
    if not names:
        problems.append("this game DECLARES CAP_ROW_REMAP but no RowRemapLadder_* symbol is "
                        "in the listing — the emission was lost and every remapping band "
                        "would index through a stale address")
    if not tails:
        problems.append("this game DECLARES CAP_ROW_REMAP but NO emitted band carries a "
                        "non-NULL ladder pointer — the capability has no subject, which is "
                        "the vacuous-gate shape the registry's own pin exists to refuse")

    report.append("  ladders in the image:")
    seen_h = {}
    for n in names:
        # H comes from the BAND that points at this table, never from the table's own size —
        # sizing a table by its own length would make the shape check tautological.
        hs = {t["hshift"] for t in tails if t["ladder"] == (syms[n] & 0xFFFFFF)}
        if len(hs) != 1:
            problems.append(f"{n} is referenced by {len(hs)} distinct height shifts {sorted(hs)} "
                            f"— the table's shape is then not decidable from the record")
            continue
        h = hs.pop()
        seen_h[n] = h
        try:
            problems += check_ladder(rom, syms[n] & 0xFFFFFF, h, n, report)
        except Unmeasurable as e:
            # The model-agreement arm's only failure mode that is not a real disagreement:
            # the generator is gone or unimportable. Loud, and NOT a pass.
            for line in report:
                print(line)
            print(f"row_remap_gate: UNMEASURABLE — {e}")
            return EXIT_UNMEASURABLE

    report.append("  remapped bands, and WHERE THEY ARE BOUND (design §9.2 step 3, informational):")
    for t in tails:
        lname = next((n for n in names if (syms[n] & 0xFFFFFF) == t["ladder"]), f"${t['ladder']:06X}")
        report.append(f"    {t['config']} band {t['band']}: ladder {lname}, surface plane line "
                      f"{t['plane_y']}, H={1 << t['hshift']}, anchor ch {t['anchor_ch']}")
        if t["anchor_ch"] != t["anchor_ch_hdr"]:
            problems.append(f"{t['config']} band {t['band']}: the tail names anchor channel "
                            f"{t['anchor_ch']} but the config header's pcfg_anchor_ch is "
                            f"{t['anchor_ch_hdr']} — the remap would read a channel the "
                            f"overlay does not split on, so its band top would not be the "
                            f"anchored line")

        # ---- THE VISIBILITY ARM (added 2026-09-03; CORRECTED 2026-09-05) ----
        #
        # A BAND VARIES IF EITHER A DEFORM TABLE IS PRESENT **OR** IT CARRIES AN ACTIVE
        # CURVE. It used to demand the table unconditionally, and that was wrong twice over
        # — owner ruling, docs/witness/rowremap-gate-vs-guard-2026-09-05.md:
        #
        #   1. OVER-STRICT. The authority it cited, `scene()`'s comptime guard, requires a
        #      table "alongside a live shift". A curve layer STRUCTURALLY CANNOT have a live
        #      shift: `layer()` refuses `curve` together with any live deform amplitude
        #      (`dsa`/`dsb` != 15) for a measured register reason. So a curve band has
        #      dsb = 15, no live shift, and the guard correctly requires no table — while
        #      this arm demanded one anyway. It enforced something its own quotation
        #      conditioned away. `scene()`'s guard is UNCHANGED by this fix and must stay so:
        #      it already lists `(c) a curve: on that layer` as a sufficient source.
        #
        #   2. ITS STATED REASON WAS FALSE HERE, WHICH MATTERS MORE. It said a NULL table
        #      means "every line of this band gets the same plane-B scroll word". With a
        #      curve present that is simply untrue: the curve hoist
        #      (engine/level/parallax.emp, `.cap_factor_curve_hoist`) decodes the far-end
        #      factor to a real scroll value, takes `spread = far_end - base`, and
        #      Bresenhams `spread/span` PER LINE. Every line differs — that is what a curve
        #      IS. So the remap was not the identity, and the refusal was for a reason that
        #      did not hold.
        #
        # A gate that quotes an authority has to be tested against that authority. This one
        # was not, and the citation is what made it look right.
        dsb, why = effective_dsb(t)
        varies, _how = band_varies(t)
        if not varies:
            problems.append(f"{t['config']} band {t['band']}: pcfg_deform_table_bg is NULL "
                            f"AND this band's band_curve.bc_flags has no "
                            f"CURVE_FLAG_ACTIVE_BIT, so nothing gives its plane-B scroll a "
                            f"per-line value: the sample loop is flat-pathed and every line "
                            f"gets the same word. Remapping that is the identity. Give the "
                            f"band ONE of the sources `scene()`'s own guard names — a "
                            f"`deform_bg:` table with a live shift (its own `dsb:` or the "
                            f"anchor's), or a `curve:` on that layer. A live shift with no "
                            f"table is flat-pathed at runtime and does not count")
            continue
        if t["deform_table_bg"] == 0:
            # THE CURVE-ONLY BAND. It varies, so it is not refused — and its MAGNITUDE is
            # deliberately not gated here. The curve's per-line delta is Bresenhamed from
            # `spread/span` over the layer's whole on-screen span, while the remap acts on
            # the anchored split's LOWER half; deriving the travel across just those lines
            # needs the split line, which is a runtime quantity (`plane_y - Vscroll_BG`
            # minus `Effects_Screen_L[ch]`) and is not in the image. Printing a whole-span
            # number and calling it this band's travel would be a measurement without its
            # referent. The floor arm below therefore owns the table case only, and this
            # line says so rather than leaving a silent gap.
            report.append(f"      varies by CURVE, not by a deform table (bc_flags carries "
                          f"CURVE_FLAG_ACTIVE_BIT). NOT magnitude-gated: the curve's travel "
                          f"across the REMAPPED lines depends on the runtime split line, "
                          f"which is not in the image. Design §9.1 precondition 1 is "
                          f"satisfied — the source is not flat")
            continue
        px = excursion(rom, t["deform_table_bg"], dsb)
        report.append(f"      plane-B travel across these lines: {px} px peak to peak "
                      f"(table ${t['deform_table_bg']:06X} at shift {dsb} — {why}); "
                      f"floor {floor_px} px")
        if px < floor_px and t["curve_active"]:
            # TABLE **AND** CURVE. Failing here on the table's excursion alone would be the
            # same defect one line down: the curve adds travel this number does not contain,
            # so `px < floor` is not evidence the band is invisible. Reported, not gated.
            report.append(f"      ...and this band ALSO carries an active curve, so the "
                          f"{px} px above is the deform half ONLY and is not the band's "
                          f"travel. NOT FAILED on it: the floor gate owns table-only bands, "
                          f"for the reason in the curve-only note above")
        elif px < floor_px:
            problems.append(
                f"{t['config']} band {t['band']}: the plane-B scroll this band remaps travels "
                f"only {px} px peak to peak, under the {floor_px} px visibility floor — the "
                f"remap runs, costs its cycles, and NOBODY CAN SEE IT. Read this as a MAGNITUDE "
                f"failure and not as design §9.1 precondition 1's flat-source failure: those "
                f"are different faults with different fixes, and on 2026-09-03 the shipped "
                f"waterline was misdiagnosed as the flat one. It was not flat — the anchor's "
                f"shift reached exactly the band the mark named, tools/row_remap_witness.py "
                f"separated the head from the flat prediction on 12 of 12 samples, and the "
                f"whole excursion was 4 px. Moving the band would have produced a second "
                f"invisible screen; RAISING THE AMPLITUDE is the fix. The shift above is the "
                f"control (lower it toward 0), or attach a bigger table — DeformTable_Shimmer "
                f"is amplitude 8 where DeformTable_OJZ_Calm is 96. A taller ladder is NOT the "
                f"lever: H = 32 costs 1,056 B of packed data against ~558 B of DEBUG-shape "
                f"headroom. The floor's provenance is an observation and is recorded at "
                f"REMAP_VISIBLE_MIN_PX in engine/level/parallax_dsl.emp")
    # THE VISIBILITY ARM'S OWN RED/GREEN, on the shipped record. See the function's banner
    # for why this is here and not in the pytest lane: the thing under test is a derived
    # BYTE OFFSET into a linked image, and the pytest lane runs before a ROM exists.
    try:
        problems += visibility_arm_self_test(rom, syms, tail_off, stride, hdr_len,
                                             anchor_off, offs, report)
    except Unmeasurable as e:
        for line in report:
            print(line)
        print(f"row_remap_gate: UNMEASURABLE — {e}")
        return EXIT_UNMEASURABLE

    report.append("    NOT GATED, and it cannot be: whether the bound section lets the camera "
                  "cross the anchor line VERTICALLY decides whether a human ever sees this. In "
                  "a horizontally-crossed section the effect is a still picture. Read the list "
                  "above against the act's camera paths (design §9.1 precondition 4).")

    for line in report:
        print(line)
    if problems:
        print("row_remap_gate: FAIL")
        for p in problems:
            print("  - " + p)
        return EXIT_FAIL
    print(f"row_remap_gate: OK — {len(names)} ladder(s), {len(tails)} remapped band(s), all "
          f"three invariants hold on the emitted bytes, and each table agrees with "
          f"tools/row_remap_ladder_gen.py re-derived at its own declared H")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
