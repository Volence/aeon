#!/usr/bin/env python3
"""ITEM 10a's BYTE GOLDEN — is the "reels" per-strip vertical scroll source in the ROM?

EFFECTS-W1 DoD item 10a (`parcel/item10a-reels`, 2026-09-03). One question:

    `OJZ_Reel_Speed`, read out of THIS ROM at THIS listing's address, holds
    REEL_BAND_COUNT independently-authored, pairwise-DISTINCT per-frame phase
    increments — the "reel source" `OJZ_Reels_Fill` (games/sonic4/data/effects/
    ojz_effects.emp) advances every frame and composes onto the per-column VSRAM
    buffer's BG words. And `OJZ_Reels_Fill` itself, the routine that does that
    composing, actually reaches the ROM.

WHY A SOURCE-LEVEL CHECK CANNOT ANSWER IT, plane_base_swap_gate.py's reason, restated
for this fixture:

  * The `.emp` `ensure`s (distinctness, the REEL_BAND_COUNT * REEL_COLS_PER_BAND
    identity) are comptime-vs-comptime. They prove the AUTHORED numbers have the
    property; they say nothing about whether the `pub data`/`pub proc` carrying them
    actually emitted a byte, or emitted it DEBUG-gated the wrong way round.
  * `tools/effects_gates.py` boots an emulator per gate and is the pixel half. It did
    not run here (no emulator in a subagent) — see the TAGGED section below.

So: a fixture that agrees with itself is "green and possibly absent from the ROM
entirely", and this file is the half that reads the actual bytes.

THE EXPECTATION IS DERIVED FROM FILES THE FIXTURE DOES NOT AUTHOR-TWICE:

  * `REEL_BAND_COUNT`      games/sonic4/config/constants.emp
  * `OJZ_REEL_SPEEDS`      games/sonic4/data/effects/ojz_effects.emp (the array literal
                           itself — re-parsed, not re-typed, so a hand edit to either
                           the source array or the emitted bytes is caught independently)

Change the array's values without moving REEL_BAND_COUNT and this gate's byte compare
goes red naming the mismatched index. Change any value so two entries collide and the
gate's own distinctness check goes red BEFORE the ROM is even opened — the same
property `reel_rates_ok()` (games/sonic4/config/constants.emp) already proves at compile
time, measured here a second, independent way, against the actual image. (That guard was
`distinct5()` beside the array in ojz_effects.emp until EFFECTS-W1 item 10 step 4, which
made it shared so a GENERATED reel table inherits it too; a five-ary hand-called fn
could not travel.)

THREE SYMBOLS, TWO GAPS. `OJZ_Reel_Speed` (data) is declared immediately before
`OJZ_Reels_Fill` (code), which is declared immediately before `OJZ_TestPal` (the next
real content in games/sonic4/data/effects/ojz_effects.emp) — so the label arithmetic
plane_base_swap_gate.py uses (gap between two ADJACENT declared symbols is the actual
byte size of the first) applies twice: once for the table, once for the whole proc.

BOTH SHAPES ARE ASSERTED, IN OPPOSITE DIRECTIONS, for OJZ_BaseSwap's reason: nothing in
the release shape can ever set `OJZ_Reel_Active` (`tools/reels_witness.py` is the only
writer, and it pokes a DEBUG-only RAM cell), so an unconditionally-emitted table or
proc would be a dormant scaffold in the ROM the owner ships.

    --shape debug     OJZ_Reel_Speed is exactly REEL_BAND_COUNT bytes and its content
                      is the derived image; OJZ_Reels_Fill is non-empty (code exists —
                      this gate does NOT decode its instruction bytes; see below)
    --shape release   BOTH symbols emit ZERO bytes (their labels collapse onto
                      OJZ_TestPal's address, exactly as OJZ_BaseSwap's does)

WHAT IT CANNOT SAY, AND WHY OJZ_Reels_Fill's BYTES ARE NOT DECODED. Unlike OJZ_BaseSwap
— an 11-word DATA program with a fixed, DSL-derived shape — OJZ_Reels_Fill is CODE: a
loop with a `dbf` and a shift. Pinning a compiler's exact encoding of a loop is
precisely the coupling this tree spends real effort avoiding elsewhere (a sigil
codegen change unrelated to this parcel would false-red a byte-for-byte pin on
`move.b`/`dbf` encodings). So this gate proves the routine's BYTES REACH THE ROM WITH
THE RIGHT SHAPE (present in DEBUG with a real, nonzero size; absent in release) and
proves the DATA it reads is exactly what the source declares; it does NOT prove the
loop composes those bytes onto VSRAM correctly at runtime, and it does NOT prove
anything reaches the screen. That is TAGGED for the controller's emulator pass
(tools/reels_witness.py), exactly as item 11a's gate tags its own on-screen half.

REFUSES TO BE VACUOUS. A missing symbol, a missing neighbour, a gap that is neither the
full image nor zero (nor a plausible nonzero code size, for the proc), or a constant
this file cannot parse out of its source is reported as UNMEASURABLE (exit 2), never as
a pass.

THE AUTHORED HALF (EFFECTS-W1 item 10 step 4, gate widened 2026-09-04). Everything above
this paragraph describes `OJZ_Reel_Speed` — the FALLBACK table, this file's own five-band
demo. Since aeon 09d964c7 a scene document can carry a `reels` key, which lowers into a
per-scene `[i8; REEL_BAND_COUNT]` table plus a 0-terminated association table
(`EditorReelBindings_<CAP>`) that `OJZ_Reels_Fill` walks against `Parallax_Current_Config`
to pick a table, falling back to `OJZ_Reel_Speed` on a miss.

    Until this widening the AUTHORED tables had NO aeon gate at all — this file read only
    `SPEED_SYM`, so a generator that emitted the wrong rates, pointed a binding at the
    wrong scene, or emitted the whole authored block into the RELEASE shape would have
    left every check here green.

THREE LEGS, and the point of having three is that each is a DIFFERENT authority, so no
leg can be satisfied by restating another:

  1. the editor SCENE DOCUMENT   games/sonic4/data/editor/effects/<scene_id>.json,
                                 key `reels.rates` — what the author actually wrote
  2. the GENERATED module        games/sonic4/data/generated/<zone>/<act>/effects_scenes.emp,
                                 `const EditorReelsSrc_<CAP>_<scene_id> = [...]` — what
                                 tools/effects_gen.py carried across
  3. the ROM                     the bytes at the `EditorReels_*` label in THIS listing —
                                 what sigil actually emitted

Leg 1 vs leg 2 catches a generator that drops, reorders or rescales an author's rates
(the CR's named hazard: item 3's `drift.rate` is 1/256 px per frame and the editor
multiplies it by 256 on export, which applied here would emit 768 for an intended 3).
Leg 2 vs leg 3 catches a table that never emitted, emitted DEBUG-gated the wrong way
round, or was hand-patched in the image. NOTHING IS RE-TYPED into this file: a Python
list of today's rates would make all three legs one leg wearing three hats.

THE ASSOCIATION TABLE IS READ OUT OF THE ROM AND RESOLVED THE WAY THE ENGINE DOES —
`(config, rates)` longs until a zero config — and each long is required to equal the
listing address of the symbol the generated module names in that slot. That is what
proves the binding points where the author aimed it; a table whose pointers are merely
"plausible addresses" is exactly the failure a byte-count check cannot see.

RELEASE: the authored tables AND the association table must emit ZERO bytes, for the
same dormant-scaffold reason as the two symbols above, proven the same way — their
labels must collapse onto the address of the next `pub data` declared after them in the
generated module.

A TREE WITH NO AUTHORED REELS IS STILL GRADABLE, deliberately: the association table is
emitted in every bake (`OJZ_Reels_Fill` names it in a `lea`, so the symbol must exist),
and with no `reels` key anywhere it is exactly one terminator long. This gate asserts
that shape rather than skipping.

Usage:
    tools/reels_gate.py --shape debug|release [--lst s4.lst] [--rom s4.bin]
                        [--built-after <epoch s>]

Exit 0 = the mechanism is in the ROM (or correctly absent). 1 = a real failure.
2 = UNMEASURABLE.
"""

import glob
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GAME_CONSTANTS = os.path.join(REPO, "games", "sonic4", "config", "constants.emp")
FIXTURE = os.path.join(REPO, "games", "sonic4", "data", "effects", "ojz_effects.emp")

# The generator's own two paths, re-derived here rather than imported: importing
# tools/effects_gen.py would make this gate's expectation and the thing it grades the
# same object, which is the restatement failure the header refuses.
# `ActNames.out_path` (tools/effects_gen.py) builds the first; `scene_dir()` the second,
# where a document's `id` is REQUIRED to equal its filename stem (effects_gen refuses
# otherwise), which is what makes scene_id -> document path a derivation and not a guess.
GENERATED_GLOB = os.path.join(REPO, "games", "sonic4", "data", "generated",
                              "*", "*", "effects_scenes.emp")
SCENE_DOC_DIR = os.path.join(REPO, "games", "sonic4", "data", "editor", "effects")

SPEED_SYM = "OJZ_Reel_Speed"
FILL_SYM = "OJZ_Reels_Fill"
# The symbol immediately after OJZ_Reels_Fill in emission order. NOT OJZ_TestPal — the
# OJZ_Reels block sits at the END of games/sonic4/data/effects/ojz_effects.emp (moved
# there deliberately so inserting it does not fall BETWEEN OJZ_BaseSwap and OJZ_TestPal,
# which would break tools/plane_base_swap_gate.py's own adjacency assumption for item
# 11a — measured red the first time this file was drafted). The module's last content
# is followed by whatever games/sonic4/map.toml's `order` list names next after the
# "OJZ_TestRaster" section head this whole module IS (map.toml: `"OJZ_TestRaster",
# "ObjDef_Static",`), which is `ObjDef_Static` (games/sonic4/data/effects/ojz_effects.emp
# ends and the object-index data begins).
NEXT_SYM = "ObjDef_Static"

_LST_LABEL = re.compile(r"^\(0\)\s+\d+/([0-9A-Fa-f]+)\s+:\s+([A-Za-z_$][\w$.]*):")


class Unmeasurable(Exception):
    pass


def _read(path):
    if not os.path.isfile(path):
        raise Unmeasurable(f"{path} does not exist")
    with open(path, "r", errors="replace") as f:
        return f.read()


def _int(raw):
    return int(raw[1:], 16) if raw.startswith("$") else int(raw)


def emp_const(path, name):
    """A `const NAME = <int literal>` out of an `.emp`, or UNMEASURABLE naming both."""
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|-?\d+)\s*(?://.*)?$",
                  _read(path), re.M)
    if not m:
        raise Unmeasurable(
            f"cannot find `const {name} = <literal>` in {os.path.relpath(path, REPO)} — "
            f"this gate DERIVES its expectation from that declaration, and guessing would "
            f"produce a byte mismatch that is really a parse failure")
    return _int(m.group(1))


def emp_int_array(path, name):
    """The literal ints inside `const NAME[: [T; N]] = [a, b, c, ...]`, in source order.

    Pure text parse, deliberately: re-typing the values as a second Python list would
    make this a restatement rather than a re-derivation, exactly the gap OJZ_BaseSwap's
    header explains for its own five-source expectation.

    THE TYPE ANNOTATION IS OPTIONAL and that is not laxity: `OJZ_REEL_SPEEDS` carries
    `: [i8; REEL_BAND_COUNT]`, while every generated `EditorReelsSrc_*` is deliberately
    UNANNOTATED so `reel_rates_ok`'s magnitude arm sees the RAW authored ints rather than
    values already narrowed by emission (tools/effects_gen.py says so at the emission
    site). Two parsers for the two spellings would be two places for this gate to drift
    from the source it grades.
    """
    m = re.search(rf"^\s*const\s+{re.escape(name)}\s*(?::\s*\[[^\]]*\]\s*)?=\s*\[([^\]]*)\]",
                  _read(path), re.M)
    if not m:
        raise Unmeasurable(
            f"cannot find `const {name} = [...]` in {os.path.relpath(path, REPO)}")
    items = [x.strip() for x in m.group(1).split(",") if x.strip() != ""]
    if not items:
        raise Unmeasurable(f"`{name}` in {os.path.relpath(path, REPO)} parsed to an empty array")
    return [_int(x) for x in items]


def to_bytes_i8(values):
    """Signed byte values -> their two's-complement unsigned byte encoding."""
    out = []
    for v in values:
        if not -128 <= v <= 127:
            raise Unmeasurable(f"{v} does not fit in a signed byte (i8)")
        out.append(v & 0xFF)
    return out


def all_distinct(values):
    return len(set(values)) == len(values)


# --------------------------------------------------------------------------------------
# THE AUTHORED HALF — the three legs the header describes.
# --------------------------------------------------------------------------------------

_PUB_DATA = re.compile(r"^pub\s+data\s+([A-Za-z_$][\w$]*)\s*:", re.M)
_REELS_TABLE = re.compile(r"^pub\s+data\s+(EditorReels_[\w$]+)\s*:\s*\[i8;", re.M)
_BIND_TABLE = re.compile(
    r"^pub\s+data\s+(EditorReelBindings_[\w$]+)\s*:\s*\[\*u8;[^\]]*\]\s*=\s*"
    r"if\s+DEBUG\s*==\s*1\s*\{\s*\[([^\]]*)\]\s*\}\s*else\s*\{\s*\[\s*\]\s*\}", re.M)
_EXTERN = re.compile(r'extern\("([A-Za-z_$][\w$]*)"\)')


def generated_modules():
    """Every generated per-act effects module, sorted. Zero of them is UNMEASURABLE.

    An empty glob is NOT "this tree authors no reels" — it is indistinguishable from
    "this gate is looking in the wrong directory", and the two demand opposite reactions.
    """
    mods = sorted(glob.glob(GENERATED_GLOB))
    if not mods:
        raise Unmeasurable(
            f"no generated effects module matched {os.path.relpath(GENERATED_GLOB, REPO)} — "
            f"the authored-reels half of this gate reads its expectation out of that file, "
            f"and an empty glob cannot be told apart from a moved output path")
    return mods


def scene_doc_rates(scene_id):
    """`reels.rates` out of the editor scene document whose stem is `scene_id`.

    tools/effects_gen.py REFUSES a document whose `id` differs from its filename stem, so
    the stem is a derivation of the symbol component and not a convention this file hopes
    holds. A missing document, or one with no `reels` key, is UNMEASURABLE: the generated
    module says a scene authored rates, so the document that authored them must exist.
    """
    path = os.path.join(SCENE_DOC_DIR, scene_id + ".json")
    if not os.path.isfile(path):
        raise Unmeasurable(
            f"the generated module declares rates for scene {scene_id!r} but "
            f"{os.path.relpath(path, REPO)} does not exist — this gate compares the "
            f"generator's output against the AUTHOR's document, and with the document "
            f"missing it would be comparing the generator against itself")
    try:
        doc = json.loads(_read(path))
    except json.JSONDecodeError as e:
        raise Unmeasurable(f"{os.path.relpath(path, REPO)} is not valid JSON: {e}")
    reels = doc.get("reels")
    if not isinstance(reels, dict) or "rates" not in reels:
        raise Unmeasurable(
            f"{os.path.relpath(path, REPO)} has no `reels.rates` key, but the generated "
            f"module emitted a rate table for it — the two disagree about whether this "
            f"scene authors reels at all")
    rates = reels["rates"]
    if not isinstance(rates, list) or not all(isinstance(r, int) for r in rates):
        raise Unmeasurable(
            f"{os.path.relpath(path, REPO)}'s `reels.rates` is {rates!r}, not a list of "
            f"whole-pixel ints")
    return rates


def authored_reels(path):
    """Parse ONE generated module's reels block.

    Returns (cap, [(table_sym, scene_id, rates_from_generated)], bind_sym, [(cfg, rates)],
             next_decl) where `next_decl` is the `pub data` declared immediately after the
    association table — the neighbour whose address gives the table's byte size in DEBUG
    and proves the whole block collapsed in release.
    """
    text = _read(path)
    m = _BIND_TABLE.search(text)
    if not m:
        raise Unmeasurable(
            f"cannot find `pub data EditorReelBindings_<CAP>: [*u8; ..] = if DEBUG == 1 "
            f"{{ [..] }} else {{ [] }}` in {os.path.relpath(path, REPO)}. That table is "
            f"emitted in EVERY bake (OJZ_Reels_Fill names it in a `lea`), so its absence "
            f"is a parse failure or a generator change, never 'no reels authored'")
    bind_sym = m.group(1)
    cap = bind_sym[len("EditorReelBindings_"):]

    # the initializer: (config, rates) extern pairs, then a literal 0 terminator
    items = [x.strip() for x in m.group(2).split(",") if x.strip() != ""]
    if not items or items[-1] != "0":
        raise Unmeasurable(
            f"`{bind_sym}`'s initializer in {os.path.relpath(path, REPO)} does not end in "
            f"a literal `0` terminator (parsed {items!r}). OJZ_Reels_Fill walks it until a "
            f"zero config long; without one the walk runs off the end of the table")
    body = items[:-1]
    if len(body) % 2:
        raise Unmeasurable(
            f"`{bind_sym}` carries {len(body)} entries before the terminator, which is odd "
            f"— OJZ_Reels_Fill reads (config, rates) PAIRS, so an odd count would leave it "
            f"reading the terminator as a rate table pointer")
    pairs = []
    for i in range(0, len(body), 2):
        cfg, rates = _EXTERN.fullmatch(body[i]), _EXTERN.fullmatch(body[i + 1])
        if not cfg or not rates:
            raise Unmeasurable(
                f"`{bind_sym}` entry {i // 2} is ({body[i]}, {body[i + 1]}), not the "
                f"`extern(\"Name\")` pair this gate resolves against the listing")
        pairs.append((cfg.group(1), rates.group(1)))

    tables = []
    for tm in _REELS_TABLE.finditer(text):
        sym = tm.group(1)
        prefix = f"EditorReels_{cap}_"
        if not sym.startswith(prefix):
            raise Unmeasurable(
                f"{sym} in {os.path.relpath(path, REPO)} does not start with {prefix!r}, so "
                f"this gate cannot derive its scene id — and a guessed scene id would read "
                f"the wrong author's document")
        scene_id = sym[len(prefix):]
        tables.append((sym, scene_id, emp_int_array(path, f"EditorReelsSrc_{cap}_{scene_id}")))

    # the neighbour: the first `pub data` DECLARED after the association table
    after = [d for d in _PUB_DATA.finditer(text) if d.start() > m.start()]
    if not after:
        raise Unmeasurable(
            f"`{bind_sym}` is the last `pub data` in {os.path.relpath(path, REPO)}, so this "
            f"gate has no following symbol to measure its size against. The gap arithmetic "
            f"below needs a neighbour; without one, a table emitting bytes in the RELEASE "
            f"shape would be invisible here")
    return cap, tables, bind_sym, pairs, after[0].group(1)


def rom_longs(rom, addr, count):
    if addr + count * 4 > len(rom):
        raise Unmeasurable(
            f"${addr:06X} + {count} long(s) runs past the end of the {len(rom)}-byte ROM")
    return [int.from_bytes(rom[addr + i * 4: addr + i * 4 + 4], "big") for i in range(count)]


def lst_labels(path):
    out = {}
    for line in _read(path).splitlines():
        m = _LST_LABEL.match(line)
        if m:
            out.setdefault(m.group(2), int(m.group(1), 16))
    if not out:
        raise Unmeasurable(
            f"{os.path.relpath(path, REPO)} yielded no `(0) n/ADDR : Name:` label lines — "
            f"the listing format changed and this gate cannot locate anything in it")
    return out


def at(labels, name, path):
    if name not in labels:
        raise Unmeasurable(
            f"`{name}` is not in {os.path.relpath(path, REPO)}. This gate reads its bytes "
            f"at that label; a missing symbol is not a pass — the content may simply not "
            f"have been emitted at all")
    return labels[name]


def authored_checks(shape, labels, rom, lst_path, band_count):
    """The authored half, both shapes. Returns a list of FAILURE strings (empty = pass);
    anything this gate cannot measure raises Unmeasurable, never a silent skip."""
    fails = []
    for mod in generated_modules():
        rel = os.path.relpath(mod, REPO)
        cap, tables, bind_sym, pairs, next_decl = authored_reels(mod)
        bind_addr = at(labels, bind_sym, lst_path)
        next_addr = at(labels, next_decl, lst_path)
        bind_gap = next_addr - bind_addr
        print(f"  [{rel}] cap={cap}, {len(tables)} authored table(s), "
              f"{len(pairs)} binding(s); `{bind_sym}` at ${bind_addr:06X}, next declared "
              f"`{next_decl}` at ${next_addr:06X} — {bind_gap} byte(s) between")

        if shape == "release":
            # Everything in the block must collapse onto the neighbour's address. Equality
            # among the reels symbols alone would NOT do: a table emitting 0 and the
            # association table emitting 12 would leave their labels equal and 12 bytes of
            # dormant scaffold in the shipped ROM. The neighbour is what closes that.
            if bind_gap != 0:
                fails.append(f"`{bind_sym}` emits {bind_gap} bytes in the RELEASE shape")
            for sym, scene_id, _ in tables:
                a = at(labels, sym, lst_path)
                if a != bind_addr:
                    fails.append(
                        f"`{sym}` is at ${a:06X} but `{bind_sym}` is at ${bind_addr:06X} — "
                        f"the authored rate table for scene {scene_id!r} emits "
                        f"{bind_addr - a} byte(s) in the RELEASE shape")
            continue

        # ---- debug shape ----
        # leg 1 vs leg 2: the author's document against the generator's output
        for sym, scene_id, gen_rates in tables:
            doc_rates = scene_doc_rates(scene_id)
            if gen_rates != doc_rates:
                fails.append(
                    f"scene {scene_id!r}: the document authored {doc_rates} but "
                    f"{rel} emitted {gen_rates} — tools/effects_gen.py dropped, "
                    f"reordered or rescaled the author's rates (index i owns screen X "
                    f"64i..64i+63, so a reorder silently relocates every strip)")
            if len(gen_rates) != band_count:
                raise Unmeasurable(
                    f"`EditorReelsSrc_{cap}_{scene_id}` has {len(gen_rates)} rates but "
                    f"REEL_BAND_COUNT is {band_count} — the generated module's own "
                    f"reel_rates_ok ensure should have refused this build first")
            if not all_distinct(gen_rates):
                raise Unmeasurable(
                    f"scene {scene_id!r}'s rates {gen_rates} are not pairwise distinct; "
                    f"reel_rates_ok should have refused this build before this gate ran")
            # leg 2 vs leg 3: the generated source against the emitted bytes
            addr = at(labels, sym, lst_path)
            want = to_bytes_i8(gen_rates)
            if addr + band_count > len(rom):
                raise Unmeasurable(
                    f"`{sym}` at ${addr:06X} + {band_count} bytes runs past the end of the "
                    f"{len(rom)}-byte ROM")
            got = list(rom[addr:addr + band_count])
            for i, (g, w) in enumerate(zip(got, want)):
                sgn = g - 256 if g >= 128 else g
                ok = g == w
                print(f"    {scene_id} band {i}  ${addr + i:06X}  {g:02X} ({sgn:+d})  "
                      f"want {w:02X} ({gen_rates[i]:+d})  {'OK' if ok else 'MISMATCH'}")
                if not ok:
                    fails.append(f"`{sym}` band {i}: ROM {g:02X}, source wants {w:02X}")

        # the association table, resolved OUT OF THE ROM the way OJZ_Reels_Fill does
        want_longs = len(pairs) * 2 + 1
        if bind_gap != want_longs * 4:
            raise Unmeasurable(
                f"`{bind_sym}` occupies {bind_gap} bytes, not the {want_longs * 4} "
                f"({len(pairs)} (config, rates) pair(s) plus a terminator, 4 bytes each) "
                f"this gate derived from {rel}. Either the symbols are no longer adjacent "
                f"in emission order or the table's declared length moved — do NOT read "
                f"this as a pointer mismatch")
        longs = rom_longs(rom, bind_addr, want_longs)
        walked = []
        i = 0
        while i < len(longs) and longs[i] != 0:      # OJZ_Reels_Fill's own loop shape
            if i + 1 >= len(longs):
                fails.append(f"`{bind_sym}`: config ${longs[i]:06X} has no rates long after "
                             f"it before the table ends")
                break
            walked.append((longs[i], longs[i + 1]))
            i += 2
        if i >= len(longs):
            fails.append(f"`{bind_sym}` has no zero terminator in its {want_longs} longs — "
                         f"OJZ_Reels_Fill's `.bind` walk would run past the table")
        if len(walked) != len(pairs):
            fails.append(f"`{bind_sym}`: the ROM walk found {len(walked)} binding(s), the "
                         f"source declares {len(pairs)}")
        for n, ((cfg_sym, rate_sym), (cfg_val, rate_val)) in enumerate(zip(pairs, walked)):
            cfg_want = at(labels, cfg_sym, lst_path)
            rate_want = at(labels, rate_sym, lst_path)
            ok = (cfg_val == cfg_want) and (rate_val == rate_want)
            print(f"    binding {n}: config ${cfg_val:06X} (want ${cfg_want:06X} "
                  f"{cfg_sym}), rates ${rate_val:06X} (want ${rate_want:06X} {rate_sym})  "
                  f"{'OK' if ok else 'MISMATCH'}")
            if cfg_val != cfg_want:
                fails.append(f"`{bind_sym}` binding {n}'s config long is ${cfg_val:06X}, not "
                             f"`{cfg_sym}`'s ${cfg_want:06X} — the binding selects on a "
                             f"DIFFERENT section's config than the author aimed it at")
            if rate_val != rate_want:
                fails.append(f"`{bind_sym}` binding {n}'s rates long is ${rate_val:06X}, not "
                             f"`{rate_sym}`'s ${rate_want:06X} — the binding hands "
                             f"OJZ_Reels_Fill someone else's rate table")
        if not pairs:
            print(f"    no scene in this act authors `reels` — the association table is one "
                  f"terminator long, and OJZ_Reels_Fill keeps `{SPEED_SYM}` for every "
                  f"section. The fallback path is what this bake exercises.")
    return fails


def main():
    args = sys.argv[1:]

    def opt(flag, default=None):
        return args[args.index(flag) + 1] if flag in args else default

    lst = opt("--lst", "s4.lst")
    rom_name = opt("--rom", "s4.bin")
    shape = opt("--shape")
    built_after = opt("--built-after")
    lst_path = lst if os.path.isabs(lst) else os.path.join(REPO, lst)
    rom_path = rom_name if os.path.isabs(rom_name) else os.path.join(REPO, rom_name)

    try:
        if shape not in ("debug", "release"):
            raise Unmeasurable(
                f"--shape must be `debug` or `release` (got {shape!r}). This gate asserts "
                f"OPPOSITE things in the two shapes — the table+proc present in DEBUG, both "
                f"empty in release — so it cannot guess, and guessing from the artifact's "
                f"NAME would be a name standing in for a behaviour")
        for p in (lst_path, rom_path):
            if not os.path.isfile(p):
                raise Unmeasurable(f"{p} does not exist")
        if built_after is not None:
            try:
                t0 = float(built_after)
            except ValueError:
                raise Unmeasurable(f"--built-after {built_after!r} is not a number of seconds")
            for p in (lst_path, rom_path):
                if os.path.getmtime(p) < t0:
                    raise Unmeasurable(
                        f"{os.path.basename(p)} predates this invocation's sigil run; it is "
                        f"a PREVIOUS build's artifact and reading it would measure the past")

        # ---- the expectation, out of the two sources the fixture does not author twice ----
        band_count = emp_const(GAME_CONSTANTS, "REEL_BAND_COUNT")
        speeds = emp_int_array(FIXTURE, "OJZ_REEL_SPEEDS")

        if len(speeds) != band_count:
            raise Unmeasurable(
                f"OJZ_REEL_SPEEDS has {len(speeds)} entries but REEL_BAND_COUNT is "
                f"{band_count} — the source's own `.len == REEL_BAND_COUNT` ensure should "
                f"have refused this build before this gate ever ran")
        if not all_distinct(speeds):
            raise Unmeasurable(
                f"OJZ_REEL_SPEEDS = {speeds} are not pairwise distinct — the whole 'reels' "
                f"claim is that every strip has its OWN rate; two bands sharing one would "
                f"read as a single wide strip. The source's own reel_rates_ok() ensure should "
                f"have refused this build before this gate ever ran")

        want_bytes = to_bytes_i8(speeds)

        labels = lst_labels(lst_path)
        speed_addr = at(labels, SPEED_SYM, lst_path)
        fill_addr = at(labels, FILL_SYM, lst_path)
        next_addr = at(labels, NEXT_SYM, lst_path)
        table_gap = fill_addr - speed_addr
        proc_gap = next_addr - fill_addr

        print(f"reels_gate [{os.path.basename(lst_path)}, shape={shape}]")
        print(f"  derived: REEL_BAND_COUNT {band_count}, OJZ_REEL_SPEEDS {speeds}")
        print(f"  {SPEED_SYM} at ${speed_addr:06X}, {FILL_SYM} at ${fill_addr:06X} — "
              f"{table_gap} byte(s) between (the table)")
        print(f"  {FILL_SYM} at ${fill_addr:06X}, {NEXT_SYM} at ${next_addr:06X} — "
              f"{proc_gap} byte(s) between (the proc)")

        with open(rom_path, "rb") as f:
            rom = f.read()

        if shape == "release":
            bad = []
            if table_gap != 0:
                bad.append(f"`{SPEED_SYM}` emits {table_gap} bytes in the RELEASE shape")
            if proc_gap != 0:
                bad.append(f"`{FILL_SYM}` emits {proc_gap} bytes in the RELEASE shape")
            bad += authored_checks(shape, labels, rom, lst_path, band_count)
            if bad:
                print("reels_gate: FAIL — " + "; ".join(bad) + ". Nothing in the release "
                      "shape can ever set OJZ_Reel_Active (its only writer is "
                      "tools/reels_witness.py poking a DEBUG-only RAM cell), so this is a "
                      "dormant scaffold in the shipped ROM. Restore the `if DEBUG == 1` / "
                      "else-empty gate on the `pub data` and the `if DEBUG == 1 {}` wrap on "
                      "the `pub proc` in games/sonic4/data/effects/ojz_effects.emp (and, "
                      "for an EditorReels_*/EditorReelBindings_* row, the same gate in "
                      "tools/effects_gen.py's emitted module).")
                return 1
            print(f"reels_gate: OK — `{SPEED_SYM}`, `{FILL_SYM}` and every authored reel "
                  f"table + association table emit no bytes in the release shape, as their "
                  f"DEBUG-only reason requires")
            return 0

        # shape == "debug"
        # REEL_BAND_COUNT (5) is odd, so games/sonic4/data/effects/ojz_effects.emp
        # carries an explicit `align 2` between the table and OJZ_Reels_Fill (CODE
        # landing at an odd address is a hard 68k address-error crash, [layout.odd-item]
        # is a build error for a proc). An even band_count would need no pad; this gate
        # derives the expected gap the same way the source's own comment does, rather
        # than hardcoding "+1".
        expected_table_gap = band_count + (band_count % 2)
        if table_gap != expected_table_gap:
            raise Unmeasurable(
                f"`{SPEED_SYM}` occupies {table_gap} bytes, not the {expected_table_gap} "
                f"(REEL_BAND_COUNT {band_count}, plus one alignment byte if odd) this gate "
                f"derived. Either the two symbols are no longer adjacent in emission order "
                f"(they are declared adjacently in games/sonic4/data/effects/ojz_effects.emp), "
                f"or the table's declared length or the `align 2` pad moved — do NOT read "
                f"this as a byte mismatch")
        if proc_gap <= 0:
            print(f"reels_gate: FAIL — `{FILL_SYM}` emits NO bytes in the DEBUG shape, so "
                  f"item 10a's reel source is not in this ROM at all. The `if DEBUG == 1` "
                  f"wrap on the `pub proc` is inverted, or the proc stopped being emitted.")
            return 1

        if speed_addr + band_count > len(rom):
            raise Unmeasurable(
                f"`{SPEED_SYM}` at ${speed_addr:06X} + {band_count} bytes runs past the "
                f"end of the {len(rom)}-byte ROM")
        got_bytes = list(rom[speed_addr:speed_addr + band_count])

        bad = []
        for i, (g, w) in enumerate(zip(got_bytes, want_bytes)):
            ok = g == w
            signed = g - 256 if g >= 128 else g
            print(f"  band {i}  ${speed_addr + i:06X}  {g:02X} ({signed:+d})  "
                  f"want {w:02X} ({speeds[i]:+d})  {'OK' if ok else 'MISMATCH'}")
            if not ok:
                bad.append(f"`{SPEED_SYM}` band {i}: ROM {g:02X}, source wants {w:02X}")

        bad += authored_checks(shape, labels, rom, lst_path, band_count)

        if bad:
            print(f"reels_gate: FAIL — {len(bad)} failure(s):")
            for line in bad:
                print(f"  - {line}")
            return 1

        print(f"reels_gate: OK — the reel source is in this ROM: {band_count} pairwise-"
              f"distinct per-band FALLBACK rates {speeds} at ${speed_addr:06X}, "
              f"`{FILL_SYM}` ({proc_gap} bytes of code) reaches the ROM to advance and "
              f"compose them, and every AUTHORED table matches its scene document and its "
              f"association-table pointers resolve to the symbols the generator named")
        return 0

    except Unmeasurable as e:
        print(f"reels_gate: UNMEASURABLE — {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
