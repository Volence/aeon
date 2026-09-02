#!/usr/bin/env python3
"""editor_palette_golden — do the emitted `cycles` / `variants` bytes SAY WHAT THE
DOCUMENT SAID?

EFFECTS-W1 DoD item 5. The generator lowers a preset document's `cycles` and `variants`
keys into `pub data` records through the engine's own constructors; this gate reads those
records back OUT OF THE BUILT ROM, at the addresses the build's own listing gives, and
decodes them against the JSON the author wrote.

WHY IT CANNOT BE A COMPTIME `ensure`, and this is not a preference — it was measured.
docs/superpowers/probes/2026-09-02-item5-comptime-probe.md (verdict Q2-e, evidence RED-4)
put the hand `pub data` twin in exactly the position such a guard needs: bare in an
`ensure` it is `unknown name`; INSIDE AN ARRAY LITERAL it resolves as a LABEL, and
label-vs-struct `!=` is always true, so
`first_mismatch([Variant_Water_Deep], [variant(shift_r: 1, shift_g: 1)]) == -1` reports
index 0 for the EQUAL twin — an ALWAYS-RED guard. The probe measured the next step too:
flipping the expectation from `== -1` to `== 0` makes it pass. So one keystroke converts
an always-red guard into a permanently vacuous one, and it looks like debugging the whole
way. The demand artifact's §3.4 carries the withdrawal. This file is the alternative it
names: Python, over the artifact, needing no comptime equality at all.

TWO ARMS, AND THE SECOND IS THE ONE THAT GENERALISES.

  1. THE TWIN ARM (`GOLDEN_TWINS`). The document at `games/sonic4/data/editor/effects/
     presets/ojz_sec3_shimmer.json` is section 3's hand-authored channels re-expressed as
     JSON, so the record it emits must be the SAME BYTES as the hand `pub data` it mirrors:
     `EditorCycle_OJZ_Act1_ojz_sec3_shimmer` == `OJZ_ShimmerCycle`, and
     `EditorVariant_OJZ_Act1_ojz_sec3_shimmer_0` == `Variant_Water_Deep`. This arm is a
     DECLARED golden — the hand names and the document id are typed here, because "which
     hand instance is this document a copy of" is not derivable from anything.

  2. THE DECODE ARM. Every document carrying either key, whether or not it has a twin, is
     decoded field by field out of the ROM and compared against its own JSON. This is
     where the `period` translation is actually checked: the document's `period` is in
     FRAMES and the generator emits `pc_period = period - 1` (empyrean
     docs/AURORA_EFFECTS_SCHEMA.md §7.2, ruling Q7), so this arm asserts
     `rom_byte == authored - 1` and nothing else in the tree does. If rider 5 lands the
     runtime cadence fix and the generator's `- 1` becomes a passthrough, THIS LINE MOVES
     WITH IT — see the RIDER 5 PAIRING block in tools/effects_gen.py.

EVERY EXPECTATION IS DERIVED, and the derivations are named:
  * the generated symbol names come from `effects_gen.act_names().cycle()/.variant()` —
    the same calls `render_module` makes, never re-spelled here;
  * the record SIZES come from parsing the `pub struct` declarations in
    engine/effects/palette.emp and summing their field widths;
  * the field ORDER inside a record comes from those same declarations;
  * the constructor DEFAULTS for fields a document omits come from parsing the
    `variant(...)` / `cycle_channel(...)` signatures in engine/effects/palette_dsl.emp.
Nothing below is a number copied from a doc page.

LOUD RATHER THAN GREEN WHEN IT CANNOT MEASURE. A missing listing, a missing ROM, a symbol
absent from the listing, a struct this parser cannot size, a signature it cannot read: all
exit 2 with the reason, never 0. A gate that quietly finds nothing to check and passes is
the vacuity this tree has been bitten by.

USAGE:  python3 tools/editor_palette_golden.py --lst s4.debug.lst --rom s4.debug.bin
        [--built-after <epoch seconds>]
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import effects_gen  # noqa: E402

REPO = effects_gen.REPO
PALETTE = os.path.join(REPO, "engine", "effects", "palette.emp")
PALETTE_DSL = os.path.join(REPO, "engine", "effects", "palette_dsl.emp")
HAND_LIB = os.path.join(REPO, "games", "sonic4", "data", "effects", "ojz_effects.emp")

# THE DECLARED HALF, and the only typed thing in this file: which hand `pub data` each
# authored document is a byte-for-byte copy of. `cycle` is the hand cycle script;
# `variants` maps a SLOT INDEX to the hand descriptor that slot must reproduce. A document
# with no hand twin simply has no row here and is still covered by the decode arm.
GOLDEN_TWINS = {
    "ojz_sec3_shimmer": {
        "cycle": "OJZ_ShimmerCycle",
        "variants": {0: "Variant_Water_Deep"},
    },
}

# `(0) 2072/13EB4 :        Variant_Water_Deep:` — the same shape tools/bganim_room.py reads.
_LST_LABEL = re.compile(r"^\(0\)\s+\d+/([0-9A-Fa-f]+)\s+:\s+([A-Za-z_$][\w$.]*):")

_STRUCT = re.compile(r"^\s*(?:pub\s+)?struct\s+([A-Za-z_]\w*)\s*\{(.*?)\}",
                     re.MULTILINE | re.DOTALL)
_SCALARS = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4}


class Unmeasurable(Exception):
    """The gate cannot observe its subject. Exit 2, never 0."""


def _read(path):
    if not os.path.isfile(path):
        raise Unmeasurable(f"{path} does not exist")
    with open(path, "r", errors="replace") as f:
        return f.read()


def _strip_comments(text):
    return re.sub(r"//[^\n]*", "", text)


def struct_fields(src, name):
    """[(field, width)] for one `.emp` struct, in declaration order.

    Widths come from the scalar table or, for `[<struct>; N]`, from that struct's own
    field sum — which is how `PalCycleScript1` gets its 2 + 1 x 6.
    """
    for m in _STRUCT.finditer(src):
        if m.group(1) != name:
            continue
        out = []
        for decl in _strip_comments(m.group(2)).split(","):
            decl = decl.strip()
            if not decl:
                continue
            field, _, ty = (p.strip() for p in decl.partition(":"))
            if not ty:
                raise Unmeasurable(
                    f"struct {name}: could not split {decl!r} into `field: type`. The "
                    f"declaration shape in {PALETTE} moved and this parser can no "
                    f"longer size the record it is supposed to read out of the ROM.")
            arr = re.fullmatch(r"\[\s*([A-Za-z_]\w*)\s*;\s*(\d+)\s*\]", ty)
            if arr:
                inner = sum(w for _, w in struct_fields(src, arr.group(1)))
                if not inner:
                    raise Unmeasurable(
                        f"struct {name}: inner struct {arr.group(1)!r} sized to 0")
                out.append((field, inner * int(arr.group(2))))
            elif ty in _SCALARS:
                out.append((field, _SCALARS[ty]))
            else:
                raise Unmeasurable(
                    f"struct {name}: field {field!r} has type {ty!r}, which this parser "
                    f"cannot size. Add it to _SCALARS or teach the array arm about it — "
                    f"do NOT let the gate skip the record.")
        if not out:
            raise Unmeasurable(f"struct {name}: parsed zero fields")
        return out
    raise Unmeasurable(
        f"no `struct {name}` in {PALETTE}. It is the wire format this gate decodes; if it "
        f"was renamed, this gate has to move with it rather than pass.")


def signature_defaults(src, fn):
    """{parameter: default} for a `pub comptime fn` signature, defaults only.

    Parsed so that a document which omits an optional field is compared against the
    CONSTRUCTOR's default rather than against a number typed into this file. `%1110` is
    `.emp` binary; `$0E` is hex.
    """
    m = re.search(r"comptime\s+fn\s+" + re.escape(fn) + r"\s*\((.*?)\)\s*->",
                  src, re.DOTALL)
    if not m:
        raise Unmeasurable(
            f"no `comptime fn {fn}(...)` signature in {PALETTE_DSL} — this gate reads the "
            f"constructor's own defaults from it and must not guess them.")
    out = {}
    for param, raw in re.findall(r"([A-Za-z_]\w*)\s*:\s*int\s*=\s*(%[01]+|\$[0-9A-Fa-f]+|-?\d+)",
                                 m.group(1)):
        if raw.startswith("%"):
            out[param] = int(raw[1:], 2)
        elif raw.startswith("$"):
            out[param] = int(raw[1:], 16)
        else:
            out[param] = int(raw)
    if not out:
        raise Unmeasurable(f"parsed zero defaults out of `{fn}`'s signature in {PALETTE_DSL}")
    return out


def lst_labels(lst_path):
    labels = {}
    for line in _read(lst_path).splitlines():
        m = _LST_LABEL.match(line)
        if m:
            labels.setdefault(m.group(2), int(m.group(1), 16))
    if not labels:
        raise Unmeasurable(
            f"parsed ZERO labels out of {lst_path}. The listing's label format has moved "
            f"and this gate can no longer locate its subject. Fix _LST_LABEL; do NOT read "
            f"this as a byte mismatch.")
    return labels


def span(rom, labels, sym, size, lst_path):
    if sym not in labels:
        raise Unmeasurable(
            f"symbol `{sym}` is ABSENT from {lst_path}. Either the generator stopped "
            f"emitting it, the module it lives in left the target's `use` closure, or the "
            f"name moved — all three are failures, and none of them is 'the bytes match'.")
    at = labels[sym]
    if at + size > len(rom):
        raise Unmeasurable(f"`{sym}` at ${at:X} + {size} bytes runs past the end of the ROM")
    return at, rom[at:at + size]


def _hex(b):
    return " ".join(f"{x:02X}" for x in b)


def main() -> int:
    args = sys.argv[1:]

    def opt(flag, default=None):
        return args[args.index(flag) + 1] if flag in args else default

    lst = opt("--lst", "s4.debug.lst")
    rom_name = opt("--rom", "s4.debug.bin")
    built_after = opt("--built-after")
    lst_path = lst if os.path.isabs(lst) else os.path.join(REPO, lst)
    rom_path = rom_name if os.path.isabs(rom_name) else os.path.join(REPO, rom_name)

    for p in (lst_path, rom_path):
        if not os.path.isfile(p):
            print(f"editor_palette_golden: UNMEASURABLE — {p} does not exist")
            return 2
    if built_after is not None:
        # Temporal provenance, bganim_room's rule: a listing carries no ROM identity of
        # its own, so "it post-dates the instant this invocation started sigil" is the
        # check it supports — and it excludes a previous build's listing by construction.
        try:
            t0 = float(built_after)
        except ValueError:
            print(f"editor_palette_golden: UNMEASURABLE — --built-after {built_after!r} "
                  f"is not a number of seconds")
            return 2
        for p in (lst_path, rom_path):
            if os.path.getmtime(p) < t0:
                print(f"editor_palette_golden: UNMEASURABLE — {os.path.basename(p)} "
                      f"predates this invocation's sigil run; it is a PREVIOUS build's "
                      f"artifact and reading it would measure the past")
                return 2

    try:
        pal_src = _read(PALETTE)
        dsl_src = _read(PALETTE_DSL)
        variant_fields = struct_fields(pal_src, "pal_variant")
        channel_fields = struct_fields(pal_src, "pal_cycle_channel")
        variant_defaults = signature_defaults(dsl_src, "variant")
        channel_defaults = signature_defaults(dsl_src, "cycle_channel")
        labels = lst_labels(lst_path)
        with open(rom_path, "rb") as f:
            rom = f.read()
    except Unmeasurable as e:
        print(f"editor_palette_golden: UNMEASURABLE — {e}")
        return 2

    names = effects_gen.act_names(REPO)
    try:
        presets = effects_gen.load_all_presets("sonic4", REPO)
    except effects_gen.SceneShapeError as e:
        print(f"editor_palette_golden: UNMEASURABLE — a preset document does not load: {e}")
        return 2

    authored = {pid: p for pid, p in presets.items()
                if p.get("cycles") or any(v is not None
                                          for v in (p.get("variants") or []))}
    if not authored:
        # NOT a pass. This gate exists because documents carry these keys; with none, it
        # is measuring an empty set and the item's own content is gone.
        print("editor_palette_golden: UNMEASURABLE — no preset document in "
              f"{effects_gen.preset_dir()} carries an authored `cycles` or `variants`. "
              "This gate would check nothing, which is not the same as passing. If the "
              "keys were deliberately retired, delete this gate in the same commit.")
        return 2

    faults, checks = [], 0
    variant_size = sum(w for _, w in variant_fields)
    channel_size = sum(w for _, w in channel_fields)

    for pid in sorted(authored):
        doc = authored[pid]
        twins = GOLDEN_TWINS.get(pid, {})

        # ---- the cycle script ----
        if doc.get("cycles"):
            n = len(doc["cycles"])
            try:
                script_fields = struct_fields(pal_src, f"PalCycleScript{n}")
                size = sum(w for _, w in script_fields)
                sym = names.cycle(pid)
                at, got = span(rom, labels, sym, size, lst_path)
            except Unmeasurable as e:
                print(f"editor_palette_golden: UNMEASURABLE — {e}")
                return 2
            # header word = the channel count, DERIVED by the wrapper from the array
            head = int.from_bytes(got[:2], "big")
            checks += 1
            if head != n:
                faults.append(f"{sym} @ ${at:X}: header word is {head}, but the document "
                              f"carries {n} channel(s). `cycle_scriptN` derives the header "
                              f"from the array length, so these cannot disagree unless the "
                              f"wrong wrapper was emitted.")
            for i, ch in enumerate(doc["cycles"]):
                base = 2 + i * channel_size
                off = 0
                for field, width in channel_fields:
                    val = int.from_bytes(got[base + off:base + off + width], "big")
                    off += width
                    key = {"pc_line": "line", "pc_first": "first", "pc_count": "count",
                           "pc_period": "period", "pc_dir": "dir"}.get(field)
                    if key is None:                       # pc_pad
                        checks += 1
                        if val != 0:
                            faults.append(f"{sym} @ ${at:X}: channel {i}'s {field} is "
                                          f"{val}, not 0")
                        continue
                    want = ch.get(key, channel_defaults.get(key))
                    if key == "period":
                        # RULING Q7 — the document is in FRAMES, the byte is one less.
                        want = want - 1
                    checks += 1
                    if val != want:
                        faults.append(
                            f"{sym} @ ${at:X}: channel {i}'s {field} reads {val} in the "
                            f"ROM, but the document says `{key}` = {ch.get(key, '(default)')} "
                            f"which lowers to {want}"
                            + (" (the document's `period` is in FRAMES and the generator "
                               "emits period - 1 — empyrean AURORA_EFFECTS_SCHEMA.md §7.2, "
                               "ruling Q7)" if key == "period" else ""))
            hand = twins.get("cycle")
            if hand:
                try:
                    hat, hgot = span(rom, labels, hand, size, lst_path)
                except Unmeasurable as e:
                    print(f"editor_palette_golden: UNMEASURABLE — {e}")
                    return 2
                checks += 1
                if got != hgot:
                    faults.append(
                        f"THE TWIN GOLDEN FAILED. {sym} @ ${at:X} is [{_hex(got)}] but the "
                        f"hand-authored {hand} @ ${hat:X} is [{_hex(hgot)}]. The document "
                        f"{pid}.json is section 3's hand cycle re-expressed as JSON, so "
                        f"the two records must be the same bytes.")

        # ---- the variant descriptors ----
        for slot, v in enumerate(doc.get("variants") or []):
            if v is None:
                continue
            sym = names.variant(pid, slot)
            try:
                at, got = span(rom, labels, sym, variant_size, lst_path)
            except Unmeasurable as e:
                print(f"editor_palette_golden: UNMEASURABLE — {e}")
                return 2
            off = 0
            for field, width in variant_fields:
                raw = got[off:off + width]
                off += width
                if field == "v_pad":
                    checks += 1
                    if raw != b"\x00" * width:
                        faults.append(f"{sym} @ ${at:X}: {field} is not zero")
                    continue
                key = field[2:]                            # v_shift_r -> shift_r
                want = v.get(key, variant_defaults.get(key))
                signed = field.startswith("v_bias")
                val = int.from_bytes(raw, "big", signed=signed)
                checks += 1
                if val != want:
                    faults.append(
                        f"{sym} @ ${at:X}: {field} reads {val} in the ROM, but the "
                        f"document says `{key}` = {v.get(key, '(constructor default)')} "
                        f"= {want}.")
            hand = twins.get("variants", {}).get(slot)
            if hand:
                try:
                    hat, hgot = span(rom, labels, hand, variant_size, lst_path)
                except Unmeasurable as e:
                    print(f"editor_palette_golden: UNMEASURABLE — {e}")
                    return 2
                checks += 1
                if got != hgot:
                    faults.append(
                        f"THE TWIN GOLDEN FAILED. {sym} @ ${at:X} is [{_hex(got)}] but the "
                        f"hand-authored {hand} @ ${hat:X} is [{_hex(hgot)}].")

    if faults:
        print("editor_palette_golden: FAIL — the emitted palette records do not say what "
              "the documents say:")
        for f in faults:
            print(f"  - {f}")
        return 1

    print(f"editor_palette_golden: OK — {checks} field/span comparison(s) over "
          f"{len(authored)} authored document(s) in {os.path.basename(rom_path)}; "
          f"twins checked: "
          + (", ".join(sorted(set(GOLDEN_TWINS) & set(authored))) or "(none)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
