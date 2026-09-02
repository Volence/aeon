#!/usr/bin/env python3
"""The BAND-DRIFT byte golden — does the authored rate actually reach the ROM?

EFFECTS-W1 item 3 (`parcel/drift-on`, 2026-09-02). One question, and it is the one
question nothing else in the tree asks:

    the four bands of `ParallaxConfig_OJZ_Default`, read out of THIS ROM at THIS
    listing's addresses, carry the 16.16 image of the rate
    `games/sonic4/data/effects/ojz_scenes.emp` authors on `Scene_OJZ_Default`.

WHY IT IS NOT COVERED ALREADY, stated precisely so this gate is not a duplicate:

  * `games/sonic4/test/scene_equiv_proof.emp` compares every band field-wise, but its
    `band_eq()` runs entirely through `.br_base` — its own banner says so — so it is
    structurally blind to a capability tail. It would go on passing with the drift tail
    emitting four zero bytes on every band.
  * `tools/effects_gates.py`'s `scanline_spans` differential proves the three
    `cap_band_drift_*` INSTRUCTION spans are emitted for sonic4 and elided for demo. That
    is the code half. It says nothing about the DATA the code reads: a runtime that
    faithfully accumulates a rate of zero costs the same cycles and emits the same spans.
  * `tools/demo_specialization_witness.py` pins demo's *absence* of the same spans.

So: spans without a rate is "green and dead", and this file is the half that catches it.

WHAT IT CANNOT SAY, and the distinction matters. This is a ROM-image check. It proves the
authored rate is in the band records the walker reads; it does NOT prove the walker moves
the picture. That is the runtime numeric witness `docs/benchmarks/scanline-p4/BAND-DRIFT.md`
§7 books as NOT PROVEN — with the camera frozen, `Parallax_Drift_Acc[i]` at frame N and
N+K must differ by exactly `K * (rate << 8)` — and it needs an emulator, which this lane
does not have. Do not read a green here as that check having been run.

EVERYTHING IS DERIVED, NOTHING IS COPIED:

  * the expected RATES come from the authored `.emp` (the `drift: SceneDrift.Rate(n)`
    arguments on `Scene_OJZ_Default`'s layers, in order), never from a number typed here;
  * the record STRIDE comes from `engine/ram.emp`'s four tail mirrors, the same sum
    `Parallax_Shadow_Bands` reserves by — `tools/parallax_hscroll_probe.py`'s banner is
    the story of what a hand-typed stride costs;
  * the drift tail's OFFSET is `stride - BAND_DRIFT_BYTES`, because `band_drift` is the
    LAST tail in `band_record` (parallax.emp says so at the struct);
  * `sizeof(parallax_config)` is derived from THIS listing — the distance between two
    adjacent emitted records of a known band count — and cross-checked against a second,
    independent adjacent pair. `parallax_config` carries no `(size: N)` to read.

REFUSES TO BE VACUOUS. A scene with no authored rate, a stride with no drift tail, or a
zero-band count is reported as UNMEASURABLE (exit 2), never as a pass: this gate passing
over an empty band list is precisely the failure it exists to prevent.

Usage:
    tools/band_drift_golden.py [--lst s4.lst] [--rom s4.bin] [--built-after <epoch s>]

Exit 0 = the rates match. 1 = a byte mismatch (a real failure). 2 = UNMEASURABLE.
"""

import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCENES = os.path.join(REPO, "games", "sonic4", "data", "effects", "ojz_scenes.emp")
RAM = os.path.join(REPO, "engine", "ram.emp")
PARALLAX = os.path.join(REPO, "engine", "level", "parallax.emp")

# The scene this gate is about, and the two symbols that bracket its record in ROM. The
# NEXT symbol is what makes `sizeof(parallax_config)` derivable, so it is named rather
# than found: a wrong neighbour would silently shift every read.
SCENE_NAME = "Scene_OJZ_Default"
CFG_SYM = "ParallaxConfig_OJZ_Default"
NEXT_SYM = "ParallaxConfig_OJZ_Underwater"
# The independent second pair, for the cross-check. OJZ_Underwater has the same band
# count as OJZ_Default (both are the four-band OJZ family), and the deform table that
# follows it is the next emitted symbol.
CHECK_SYM = "DeformTable_OJZ_Calm"

_LST_LABEL = re.compile(r"^\(0\)\s+\d+/([0-9A-Fa-f]+)\s+:\s+([A-Za-z_$][\w$.]*):")


class Unmeasurable(Exception):
    pass


def _read(path):
    if not os.path.isfile(path):
        raise Unmeasurable(f"{path} does not exist")
    with open(path, "r", errors="replace") as f:
        return f.read()


def emp_const(path, name):
    """A `const NAME = <int>` out of an `.emp`, or UNMEASURABLE naming both."""
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|-?\d+)",
                  _read(path), re.M)
    if not m:
        raise Unmeasurable(
            f"cannot find `const {name}` in {os.path.relpath(path, REPO)} — this gate "
            f"sizes its reads from it, and a guess would decode the wrong bytes and "
            f"report a byte mismatch that is really a parse failure")
    raw = m.group(1)
    return int(raw[1:], 16) if raw.startswith("$") else int(raw)


def scene_block(text, name):
    """The source text of `pub const <name>: Scene = scene( ... )`, brace/paren matched."""
    m = re.search(rf"^pub const {re.escape(name)}\s*:\s*Scene\s*=\s*scene\(", text, re.M)
    if not m:
        raise Unmeasurable(
            f"cannot find `pub const {name}: Scene = scene(` in "
            f"{os.path.relpath(SCENES, REPO)} — the scene this gate reads its expectation "
            f"from has been renamed or re-spelled")
    i = m.end() - 1
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
    raise Unmeasurable(f"unbalanced parentheses in `{name}`'s scene() call")


def authored(text_block, name):
    """(count, [rate per band]) as AUTHORED — the expectation, derived not copied.

    The rate list is per `layer(` call in source order, `None` where a layer authors no
    drift, truncated to `count:` because `scene()` lowers only that many bands.
    """
    m = re.search(r"\bcount:\s*(\d+)", text_block)
    if not m:
        raise Unmeasurable(f"`{name}` has no `count:` argument — cannot say how many "
                           f"bands it lowers, so a band-wise read has no length")
    count = int(m.group(1))
    if count <= 0:
        raise Unmeasurable(f"`{name}` lowers {count} bands; there is nothing to check")

    rates = []
    # One entry per `layer(`/`no_layer(` in order. `Rate(` is looked for INSIDE the
    # layer's own argument list, so a rate on a later layer cannot be attributed here.
    for call in re.finditer(r"\b(no_layer|layer)\(", text_block):
        if call.group(1) == "no_layer":
            rates.append(None)
            continue
        i = call.end() - 1
        depth = 0
        end = None
        for j in range(i, len(text_block)):
            if text_block[j] == "(":
                depth += 1
            elif text_block[j] == ")":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        if end is None:
            raise Unmeasurable(f"unbalanced parentheses in a `layer(` call inside `{name}`")
        args = text_block[i:end + 1]
        r = re.search(r"drift:\s*SceneDrift\.Rate\(\s*(-?\d+)\s*\)", args)
        rates.append(int(r.group(1)) if r else None)

    if len(rates) < count:
        raise Unmeasurable(f"`{name}` declares count: {count} but this parse found only "
                           f"{len(rates)} layer() calls — the parse is wrong, not the ROM")
    rates = rates[:count]
    if not any(r is not None for r in rates):
        raise Unmeasurable(
            f"`{name}` authors NO `drift: SceneDrift.Rate(..)` on any of its {count} "
            f"lowered layers, so this gate would pass over an all-zero expectation and "
            f"assert nothing. If the drift was deliberately dropped, this file and its "
            f"build.sh call go with it — see games/sonic4/data/effects/scene_registry.emp's "
            f"CAP_BAND_DRIFT arm for the rest of the retreat.")
    return count, rates


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


def at(labels, sym, lst_path):
    if sym not in labels:
        raise Unmeasurable(
            f"symbol `{sym}` is ABSENT from {lst_path}. Either the registry stopped "
            f"emitting it or the name moved — both are failures, and neither is "
            f"'the bytes match'.")
    return labels[sym]


def main() -> int:
    args = sys.argv[1:]

    def opt(flag, default=None):
        return args[args.index(flag) + 1] if flag in args else default

    lst = opt("--lst", "s4.lst")
    rom_name = opt("--rom", "s4.bin")
    built_after = opt("--built-after")
    lst_path = lst if os.path.isabs(lst) else os.path.join(REPO, lst)
    rom_path = rom_name if os.path.isabs(rom_name) else os.path.join(REPO, rom_name)

    try:
        for p in (lst_path, rom_path):
            if not os.path.isfile(p):
                raise Unmeasurable(f"{p} does not exist")
        if built_after is not None:
            # Temporal provenance, editor_palette_golden's rule: a listing carries no ROM
            # identity of its own, so "it post-dates the instant this invocation started
            # sigil" is the check it supports, and it excludes a previous build by
            # construction.
            try:
                t0 = float(built_after)
            except ValueError:
                raise Unmeasurable(f"--built-after {built_after!r} is not a number of seconds")
            for p in (lst_path, rom_path):
                if os.path.getmtime(p) < t0:
                    raise Unmeasurable(
                        f"{os.path.basename(p)} predates this invocation's sigil run; it "
                        f"is a PREVIOUS build's artifact and reading it would measure "
                        f"the past")

        # ---- the expectation, out of the authored source -------------------------
        block = scene_block(_read(SCENES), SCENE_NAME)
        count, rates = authored(block, SCENE_NAME)

        # ---- the record geometry, out of the engine's own mirrors ----------------
        drift_bytes = emp_const(RAM, "BAND_DRIFT_BYTES")
        stride = (emp_const(RAM, "BAND_ENTRY_LEN")
                  + emp_const(RAM, "BAND_EXT_BYTES")
                  + emp_const(RAM, "BAND_CURVE_BYTES")
                  + drift_bytes)
        drift_n = emp_const(PARALLAX, "BAND_DRIFT_N")
        if drift_bytes == 0 or drift_n == 0:
            raise Unmeasurable(
                f"this build carries NO drift tail (engine/ram.emp BAND_DRIFT_BYTES "
                f"{drift_bytes}, engine/level/parallax.emp BAND_DRIFT_N {drift_n}) while "
                f"{SCENE_NAME} authors a rate — there is no field in the record for this "
                f"gate to read. That mismatch is refused at build time by "
                f"games/sonic4/data/effects/scene_registry.emp's two-directional pin; "
                f"seeing it here means that pin is no longer running.")
        # `band_drift` is the LAST tail in `band_record`, which is what makes this
        # subtraction the offset rather than a guess (engine/level/parallax.emp, at the
        # struct: "LAST IN THE RECORD, so raising BAND_DRIFT_N alone moves neither
        # br_ext nor br_curve").
        drift_off = stride - drift_bytes

        labels = lst_labels(lst_path)
        cfg = at(labels, CFG_SYM, lst_path)
        nxt = at(labels, NEXT_SYM, lst_path)
        chk = at(labels, CHECK_SYM, lst_path)

        # sizeof(parallax_config), DERIVED from this listing: two adjacent records of
        # `count` bands each, so the header is whatever the gap is not bands.
        cfg_size = (nxt - cfg) - count * stride
        cfg_size_2 = (chk - nxt) - count * stride
        if cfg_size != cfg_size_2 or cfg_size <= 0 or cfg_size % 2:
            raise Unmeasurable(
                f"cannot derive sizeof(parallax_config): {CFG_SYM}->{NEXT_SYM} gives "
                f"{cfg_size} and {NEXT_SYM}->{CHECK_SYM} gives {cfg_size_2} at "
                f"stride {stride} / {count} bands. The two must agree and be a positive "
                f"even number. Either the emission order changed (these three symbols are "
                f"no longer adjacent in that order) or the stride is wrong — do NOT read "
                f"this as a byte mismatch.")

        with open(rom_path, "rb") as f:
            rom = f.read()

        print(f"band_drift_golden [{os.path.basename(lst_path)}]")
        print(f"  {SCENE_NAME}: {count} band(s), authored rates "
              f"{[('none' if r is None else r) for r in rates]} (1/256 px per frame)")
        print(f"  derived: sizeof(parallax_config) {cfg_size} (two independent pairs "
              f"agree), band_record stride {stride}, drift tail at +{drift_off}")
        print(f"  {CFG_SYM} at ${cfg:06X}")

        bad = 0
        for i, rate in enumerate(rates):
            # `None` (SceneDrift.None) and Rate(0) lower to the same four zero bytes,
            # which is exactly why layer() refuses Rate(0); a non-drifting band is
            # therefore checked as zero rather than skipped.
            want = ((rate or 0) << 8) & 0xFFFFFFFF
            off = cfg + cfg_size + i * stride + drift_off
            if off + 4 > len(rom):
                raise Unmeasurable(f"band {i}'s drift tail at ${off:06X} runs past the "
                                   f"end of the {len(rom)}-byte ROM")
            got = int.from_bytes(rom[off:off + 4], "big")
            ok = got == want
            bad += 0 if ok else 1
            px = "—" if rate is None else f"{rate / 256.0:+.4f} px/frame"
            print(f"  band {i}  ${off:06X}  {got:08X}  want {want:08X}  "
                  f"{'OK' if ok else 'MISMATCH'}   {px}")
            if not ok:
                print(f"        the authored rate is {rate!r} (1/256 px per frame), whose "
                      f"16.16 image is ${want:08X}; the ROM carries ${got:08X}. If the "
                      f"ROM reads $00000000 the tail is emitted but EMPTY — the lowering "
                      f"in engine/level/scene_dsl.emp's scene_band() dropped the rate. "
                      f"If it is shifted by a power of two, the 8.8 -> 16.16 alignment "
                      f"moved.")

        if bad:
            print(f"band_drift_golden: FAIL — {bad} of {count} band(s) do not carry "
                  f"their authored rate")
            return 1
        print(f"band_drift_golden: OK — all {count} band(s) carry the authored rate")
        return 0

    except Unmeasurable as e:
        print(f"band_drift_golden: UNMEASURABLE — {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
