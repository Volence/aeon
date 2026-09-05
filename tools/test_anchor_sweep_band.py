"""tools/test_anchor_sweep_band.py — the anchor mover's CROSS-FILE bound.

EFFECTS-W1 DoD item 4. There is one thing about an authored sweep that the compiler
structurally cannot check, and it is the thing most likely to go wrong first.

A sweep's peak-to-peak travel has to stay inside the `patchable(lo, hi)` band of the channel
it is authored on. Leaving that band UPWARD does not stop the edge and does not clamp it:
`Raster_BuildSchedule` REMOVES the record for the frame (`bgt .suppress`), so the band does not
move, it VANISHES — and it comes back at the next zero crossing. A sweep one rung too wide
therefore reads as a band flickering out once per cycle, which looks like a rendering bug
rather than an amplitude the author chose.

`engine/effects/raster_dsl.emp`'s `anchor_sweep()` refuses an amplitude wider than the SCREEN,
which is a necessary condition and the strongest one available to it. It cannot check the band,
and the design says why in the same words: `lo`/`hi` live in the raster program's `patchable(..)`
call, `amp_shift` lives in the preset, and the two are associated by a POINTER at runtime.
There is no comptime scope in which both numbers exist. This file is that scope.

RED-FIRST, and the mutation is on disk rather than described: raising
`games/sonic4/data/effects/ojz_effects.emp`'s `anchor_sweep(amp_shift: 4, ...)` to
`amp_shift: 1` makes `test_every_authored_sweep_fits_its_channels_patchable_band` fail with
`channel 0: peak-to-peak 512 px does not fit band 3..220 (218 lines)`, and lowering it back
makes it pass. Measured 2026-09-03.

Runner: the `pytest tools` lane in build.sh (`python3 -m pytest tools -q`), which is
build-fatal on the canonical path and skipped under FAST=1.

----------------------------------------------------------------------------------------
THE GENERATED ARM (2026-09-03) — and what it does NOT yet prove
----------------------------------------------------------------------------------------

Everything above was written against ONE module and ONE shape: the hand-authored
`ojz_effects.emp`, with the sweep at an ARRAY POSITION inside `patch_motion: [...]`. Once
the authoring key of `docs/superpowers/specs/2026-09-03-anchor-authoring-key-shape.md` has a
reader, an author's sweep lands somewhere else entirely and in a different shape: a CHOOSER
BODY (`if sec == N && ch == C { out = anchor_sweep(...) }`) inside the generated module
`games/<game>/data/generated/<zone>/<act>/effects_scenes.emp`.

The blindness was MEASURED before it was fixed, on both axes (2026-09-03, `origin/master`
`81b2a719`):

  * PATH-BLIND — with a chooser-shaped, demonstrably out-of-band sweep sitting on disk in
    the tree, the whole file ran `7 passed`. The guard that exists to catch exactly that
    amplitude said nothing at all.
  * SHAPE-BLIND — pointed DIRECTLY at that file, `authored_sweeps()` returned `[]`. So it is
    not merely that the scanner looked in the wrong place; the scan it performs would not
    have matched the record even in the right one.

That matters more than an ordinary coverage hole because of WHO it goes silent for. The
hand-authored sweep was written by someone who could read `anchor_sweep()`'s own ensure. The
generated one is written by an author in Aurora, who gets no comptime error at all — and the
failure is not a crash but a DROPPED record, i.e. an effect that simply is not there.

**THE LIVE POPULATION IS NO LONGER EMPTY (2026-09-03, step 4 landed).** The paragraph that
stood here said a green from the generated arm proved nothing, because no real document could
legally carry the key. `tools/effects_gen.py` reads it now: the preset document
`games/sonic4/data/editor/effects/presets/ojz_sec5_showcase.json` authors
`patch_world_ys[0] = 2272` and `patch_motion[0] = {"sweep": {"amp_shift": 4,
"period_shift": 1}}`, and the generated module carries the chooser row
`if sec == 5 && ch == 0 { out = anchor_sweep(amp_shift: 4, period_shift: 1) }`. The scan sees
it — `coverage_report()` prints `LIVE GENERATED POPULATION: 1 sweep(s)` — so
`test_every_scanned_sweep_fits_its_channels_patchable_band` has a real subject on the
generated side for the first time, and the fixtures in `tools/fixtures/anchor_sweep/` are now
its FLOOR rather than its only subject. They stay: they are the only way to exercise the
REFUSING arms (out-of-band amplitude, a dead channel, an unresolvable occurrence), since a
tree carrying any of those would simply be a broken tree.

The fixtures are read through the SAME `scan_module()` the real modules go through — never a
parallel implementation.

RED-FIRST FOR THE GENERATED ARM, mutation on disk (2026-09-03): with
`tools/fixtures/anchor_sweep/generated_chooser_out_of_band.emp`'s `amp_shift` lowered from
`7` to `8` — i.e. the fixture made in-band — `test_the_fixtures_still_straddle_the_real_band`
and `test_the_out_of_band_fixture_is_refused_for_its_amplitude` both fail, and restoring `7`
makes them pass.

WHAT THE ARM STILL CANNOT SEE, stated so a green is not over-read:
  * The generated SHAPE was a prediction and is now CONFIRMED: the emission
    `effects_gen.py` produced is the `if sec == N && ch == C { out = anchor_sweep(..) }` form
    `_chooser_sweeps()` was written against, and the scan reads it with no change. Had it come
    out different, the occurrence would have landed in `unresolved` and the scan would have
    FAILED rather than falling silent — which is what `generated_chooser_unguarded.emp` still
    proves for the next shape that appears.
  * Seeded HEADROOM is only checked where the seed is discoverable AND the sweep is on the
    spawn section. A generated sweep may legally inherit its anchor from the section's
    hand-authored `patch_world_ys` (the key's "index absent -> keep" state), which needs a
    section->preset map this file does not have; and `SPAWN_CAMERA_Y` is the camera at the ACT
    SPAWN, which is only the right camera for the section the spawn is in (see SPAWN_SECTION).
    The live section-5 sweep is in the second class and is reported as NOT EVALUATED. Band fit
    and channel liveness apply to every record and need no camera; the report names which is
    which on every run.
  * On channel 0 the band bound is currently WEAKER than `anchor_sweep()`'s own screen bound:
    the band is 218 lines and the widest legal rung travels 128 px, so no legal amplitude on
    that channel can fail the band fit. Today only channel 1 (2 lines) can be failed by
    amplitude alone — which is why the refuse fixture is authored there. Measured, not
    assumed; `test_the_fixtures_still_straddle_the_real_band` re-derives it every run.
"""

import os
import re
import glob
import json
import warnings
import unittest
import collections

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RASTER_DSL = os.path.join(AEON, "engine/effects/raster_dsl.emp")
CONSTANTS = os.path.join(AEON, "engine/system/constants.emp")
OJZ_EFFECTS = os.path.join(AEON, "games/sonic4/data/effects/ojz_effects.emp")
# The section -> preset edge. A generated sweep is keyed on a SECTION, and a section names
# a patchable band only through the preset its `effects:` argument binds, so the band
# resolution crosses out of the effects library exactly here.
DESCRIPTOR = os.path.join(AEON, "games/sonic4/data/levels/ojz/act1/act_descriptor.emp")
SCENES_DIR = os.path.join(AEON, "tools/scenes")

# THE TWO MODULE SETS THIS FILE COVERS. Globs and not literals: a second game, a second act
# or a second hand-authored effects library must not be able to introduce a sweep this file
# never looks at, which is the failure the generated arm exists to end rather than to
# reproduce one level up.
HAND_GLOB = os.path.join(AEON, "games", "*", "data", "effects", "*.emp")
GENERATED_GLOB = os.path.join(AEON, "games", "*", "data", "generated", "*", "*",
                              "effects_scenes.emp")
FIXTURE_DIR = os.path.join(AEON, "tools", "fixtures", "anchor_sweep")

# The camera the seeded-headroom bound is evaluated at — tools/scenes/*.json's pinned
# Camera_Y and the act's own spawn. Hoisted from the test body it used to be a local of,
# because the generated arm needs the same number.
SPAWN_CAMERA_Y = 144

# ...AND IT IS ONLY TRUE FOR ONE SECTION, which the generated arm made visible the moment it
# had a subject (2026-09-03, step 4 of the authoring-key chain).
#
# `SPAWN_CAMERA_Y` is the camera at the ACT SPAWN, and the act spawn is in section 0. Anchors
# are act-relative world Ys (`assert_act_relative_tagged`, scene_registry.emp), so a section
# in grid row 1 legitimately seeds an anchor a whole section-height further down — section
# 5's channel 0 is 2272, which is 2048 + 224, i.e. section 0's own anchor one row down. Held
# against a camera of 144 that is a screen line of 2128 and the headroom bound reports a
# violation that is an artifact of the wrong camera, not a property of the sweep.
#
# The check is therefore SCOPED to the spawn section rather than loosened, and everything
# else is reported as NOT EVALUATED. Making it evaluable for another section needs a camera
# for that section, and there is no such number in the tree: the gate scenes pin one camera,
# and where a player's camera sits inside section N is a gameplay fact, not a source fact.
# BAND FIT AND CHANNEL LIVENESS ARE UNAFFECTED — they need no camera and still cover every
# scanned sweep, which is what makes this a narrowing of one bound and not of the file.
SPAWN_SECTION = 0


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _const(src, name, path):
    """A `[pub ]const NAME = <int>` declaration, decimal or $hex."""
    m = re.search(r"^(?:pub )?const %s\s*=\s*(\$?[0-9A-Fa-f]+)\s*(?://.*)?$" % re.escape(name),
                  src, re.M)
    if not m:
        raise AssertionError(
            "%s: no `const %s = <literal>` declaration. This test re-derives the sweep "
            "ladders from the literals that file states; if the spelling changed, every "
            "derivation below would be against a name that no longer exists." % (path, name))
    tok = m.group(1)
    return int(tok[1:], 16) if tok.startswith("$") else int(tok)


# The three ladder derivations, transcribed from raster_dsl.emp's comptime fns. They are
# TRANSCRIBED and not read, deliberately: a test that re-executed the file's own arithmetic
# could not disagree with it. What makes this non-vacuous is that the transcription is checked
# against the `pub const` values the file publishes, so a silent edit to either half fails.
def _shift_min(amp, lines):
    s = 0
    for i in range(16):
        if (amp >> i) * 2 > lines:
            s = i + 1
    return s


def _shift_max(amp):
    s = 0
    for i in range(16):
        if (amp >> i) >= 1:
            s = i
    return s


def _period_shift_max(entries, width):
    p = 0
    for i in range(32):
        if (entries << i) <= (1 << width):
            p = i
    return p


def _balanced(src, start, opener="(", closer=")"):
    """The substring inside the bracket at/after `start`, by balance. Returns (body, end)."""
    i = src.index(opener, start)
    depth, j = 0, i
    while j < len(src):
        if src[j] == opener:
            depth += 1
        elif src[j] == closer:
            depth -= 1
            if depth == 0:
                return src[i + 1:j], j
        j += 1
    raise AssertionError("unbalanced %s from offset %d" % (opener, start))


_BAND_TRIPLE = re.compile(r"\bch:\s*(\d+)\s*,\s*lo:\s*(\d+)\s*,\s*hi:\s*(\d+)")


def patched_programs():
    """{program label: {channel: (lo, hi)}} — one map PER PATCHED PROGRAM, in SCREEN lines.

    ---- WHY THIS IS NOT ONE ACT-WIDE MAP ANY MORE (2026-09-05) ----

    It was, and the test that guarded that shape said what would end it, in its own words:
    *"One patched program in the tree means one band per channel. The moment a second one
    exists, `patchable(ch: 0, ...)` names two different bands and this file's association is
    wrong — so it must refuse rather than pick one."* EFFECTS-W1 item 9c's precondition landed
    that second program (`OJZ_WorldWater` on section 7, channels 2 and 3), so the map is built
    the way that refusal prescribed: per program, resolved through the section that installs it.

    A CHANNEL IS A PER-PROGRAM INDEX and always was — `raster_program`'s guard 11 refuses two
    records on one channel WITHIN one program and says nothing across programs. The act-wide
    union was only ever sound because there was one program; under two it answers the wrong
    question in the one case that matters, and it answers it QUIETLY: a sweep authored for a
    section whose preset binds no patched program at all would have been resolved against some
    other section's band and reported in-band. That is the dead-channel fixture exactly
    (`sec == 2 && ch == 3`), and it went green under the union the moment channel 3 acquired a
    band anywhere in the act.

    Read from the source, never restated: `pub data <label>: [u16; patched_words(<P>)] =
    patched_program(<P>)` gives label -> program const, and `const <P> = compose([..])` carries
    the `patchable(.., ch:, lo:, hi:)` calls."""
    src = _blank(_read(OJZ_EFFECTS))
    out = {}
    for m in re.finditer(r"pub data (\w+)\s*:\s*\[u16;\s*patched_words\(\s*(\w+)\s*\)\s*\]"
                         r"\s*=\s*patched_program\(\s*(\w+)\s*\)", src):
        label, sized_by, emitted = m.group(1), m.group(2), m.group(3)
        if sized_by != emitted:
            raise AssertionError(
                "%s: `pub data %s` is SIZED by patched_words(%s) and EMITTED from "
                "patched_program(%s). Those must be the same program — a mismatch would emit "
                "one image into another's length, and this reader would attribute the wrong "
                "bands to the label."
                % (os.path.relpath(OJZ_EFFECTS, AEON), label, sized_by, emitted))
        cm = re.search(r"\bconst\s+%s\s*=\s*compose\s*\(" % re.escape(emitted), src)
        if not cm:
            raise AssertionError(
                "%s: `pub data %s` is built from patched_program(%s), but there is no "
                "`const %s = compose(` for this reader to take the bands out of. Teach it the "
                "new spelling — a program whose bands cannot be read is a program every band "
                "bound in this file silently skips."
                % (os.path.relpath(OJZ_EFFECTS, AEON), label, emitted, emitted))
        body, _ = _balanced(src, cm.end() - 1)
        out[label] = {int(c): (int(lo), int(hi))
                      for c, lo, hi in _BAND_TRIPLE.findall(body)}
    return out


def preset_patched_programs():
    """{preset name: the label its `patched:` argument names} for every preset that binds one.

    A preset that binds none is ABSENT rather than empty: "this section installs no patched
    program" and "this section installs one with no channels" are different facts and only the
    first is a legitimate dead channel."""
    src = _blank(_read(OJZ_EFFECTS))
    out = {}
    for m in re.finditer(r"pub data (\w+)\s*:\s*EffectsPreset\s*=\s*preset\s*\(", src):
        body, _ = _balanced(src, m.end() - 1)
        pm = re.search(r"\bpatched:\s*([A-Za-z_]\w*)", body)
        if pm:
            out[m.group(1)] = pm.group(1)
    return out


def section_presets():
    """{section index: the preset name its `effects:` argument names}, from act_descriptor.emp.

    The generated arm's sweeps are keyed on a SECTION, and a section names a band only through
    the preset it binds. This is the one edge that crosses out of the effects library, and it
    is read rather than assumed for the same reason everything else here is."""
    src = _blank(_read(DESCRIPTOR))
    out = {}
    for m in re.finditer(r"\bojz_sec\s*\(", src):
        body, _ = _balanced(src, m.end() - 1)
        sm = re.search(r"\bsec:\s*(\d+)", body)
        em = re.search(r"\beffects:\s*([A-Za-z_]\w*)", body)
        if sm and em:
            out[int(sm.group(1))] = em.group(1)
    return out


def _sweep_section(s):
    """The section a scanned sweep is authored for, or None. Chooser sites carry it."""
    m = re.search(r"sec:\s*(\d+)", s.site)
    return int(m.group(1)) if m else None


def bands_for_preset(name, progs=None, presets=None):
    """({channel: (lo, hi)}, provenance, installs_a_program) for one preset.

    THE THIRD MEMBER IS NOT A CONVENIENCE. "This section installs a patched program that has
    no record on channel N" and "this section installs no patched program at all" look the
    same from the bands dict and are different facts:

      * the first is a DEAD raster channel — the program is there, the record is not, and
        nothing about the section can consume that channel's line as a raster boundary;
      * the second means there is NO BAND TO FIT, so the band-fit bound does not apply and
        cannot be evaluated either way. It is ALSO not proof the sweep is idle: a channel's
        line is latched into `Effects_Screen_L[ch]` for every channel every frame, and a
        SCENE anchor (`SceneAnchor.At(ch, ..)`) consumes it with no `patchable()` record
        anywhere — which is exactly what `OJZ_Preset_Sec5`'s d-53 `parallax:` loan does for
        the one live generated sweep in this tree.

    Reporting the second as a violation would turn a deliberate, documented arrangement red
    and would be a claim this file cannot support: it does not read scene anchors."""
    progs = patched_programs() if progs is None else progs
    presets = preset_patched_programs() if presets is None else presets
    prog = presets.get(name)
    if prog is None:
        return {}, ("preset %s binds no `patched:` program, so there is no raster band on any "
                    "channel in the section(s) that install it" % name), False
    if prog not in progs:
        raise AssertionError(
            "preset %s binds `patched: %s`, which is not a `patched_program(..)` this reader "
            "can find in %s. If the argument became a chooser call (the `boundary` document "
            "key's shape), teach bands_for_preset() to resolve it — resolving it to nothing "
            "would silently disable every band bound in this file for that section."
            % (name, prog, os.path.relpath(OJZ_EFFECTS, AEON)))
    return progs[prog], "preset %s -> %s" % (name, prog), True


def bands_for_sweep(s, progs=None, presets=None, sections=None):
    """({channel: (lo, hi)}, provenance) for ONE scanned sweep, resolved the way the RUNTIME
    resolves it: the sweep's section installs a preset, the preset installs a patched program,
    and that program's `patchable()` records are the only bands that sweep can ever move."""
    sections = section_presets() if sections is None else sections
    if s.shape == "array":
        return bands_for_preset(s.site, progs, presets)
    sec = _sweep_section(s)
    if sec is None:
        return {}, ("the site %r names no section, so no preset and no program can be "
                    "resolved for it" % s.site), False
    name = sections.get(sec)
    if name is None:
        return {}, ("no `ojz_sec(sec: %d, .., effects: ..)` row in %s, so the section binds no "
                    "preset this reader can see"
                    % (sec, os.path.relpath(DESCRIPTOR, AEON))), False
    bands, why, has_prog = bands_for_preset(name, progs, presets)
    return bands, "section %d -> %s" % (sec, why), has_prog


def patchable_bands():
    """The ACT-WIDE UNION of every program's bands — FOR THE COVERAGE REPORT ONLY.

    Deliberately not used by any bound: with two patched programs in the act a channel index
    alone does not name a band (see `patched_programs()`). It is still worth PRINTING, because
    the report's job is to say what the source contains, and a per-channel line is how a reader
    checks the numbers against the file."""
    out = {}
    for label, bands in sorted(patched_programs().items()):
        for ch, band in bands.items():
            out.setdefault(ch, []).append((label, band))
    return out


def authored_sweeps():
    """[(preset_name, channel, amp_shift, period_shift, phase)] over every `patch_motion:` list.

    The channel is the POSITION in the array, which is what Effects_InstallPreset's seed loop
    means by it — element i of ep_patch_motion becomes Effects_Motion[i].
    """
    src = _read(OJZ_EFFECTS)
    out = []
    for m in re.finditer(r"pub data (\w+):\s*EffectsPreset\s*=\s*preset\(", src):
        name = m.group(1)
        # Walk to the matching close paren of this preset( call.
        i = m.end() - 1
        depth = 0
        while i < len(src):
            if src[i] == "(":
                depth += 1
            elif src[i] == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body = src[m.end():i]
        pm = re.search(r"patch_motion:\s*\[", body)
        if not pm:
            continue
        j = pm.end() - 1
        depth = 0
        while j < len(body):
            if body[j] == "[":
                depth += 1
            elif body[j] == "]":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        arr = body[pm.end():j]
        # Element split at top level (anchor_sweep(..) carries its own commas).
        elems, depth, cur = [], 0, ""
        for ch in arr:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if ch == "," and depth == 0:
                elems.append(cur)
                cur = ""
            else:
                cur += ch
        elems.append(cur)
        for idx, e in enumerate(elems):
            s = re.search(r"anchor_sweep\(\s*amp_shift:\s*(\d+)\s*,\s*period_shift:\s*(\d+)"
                          r"(?:\s*,\s*phase:\s*(\d+))?\s*\)", e)
            if s:
                out.append((name, idx, int(s.group(1)), int(s.group(2)),
                            int(s.group(3) or 0)))
    return out


# =========================================================================================
# THE UNIFIED SCANNER — BOTH MODULE SETS, BOTH SHAPES, AND NO SILENT DROP
# =========================================================================================
#
# `authored_sweeps()` above is left exactly as it was, and it stays the reader the original
# four tests use: "existing coverage unchanged" is worth more as a thing that can be CHECKED
# than as a thing that is claimed. `test_the_unified_scan_agrees_with_the_original_reader`
# holds the two together on the hand module, so the new code cannot quietly re-interpret the
# record the old code was gating.
#
# The design rule for everything below: an `anchor_sweep(` occurrence is classified into
# exactly one of {array, chooser, unresolved}, and `unresolved` is a HARD FAILURE naming the
# file and line. A scan that finds nothing must be distinguishable from a scan that looked in
# the wrong place, and the only way to get that is to account for every occurrence rather
# than to count the ones a pattern happened to match.

Sweep = collections.namedtuple(
    "Sweep", "path shape site channel amp_shift period_shift phase offset")
Unresolved = collections.namedtuple("Unresolved", "path offset why text")

_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_SWEEP_CALL = re.compile(r"\banchor_sweep\s*\(")
_SWEEP_ARGS = re.compile(r"\(\s*amp_shift:\s*(\d+)\s*,\s*period_shift:\s*(\d+)"
                         r"(?:\s*,\s*phase:\s*(\d+))?\s*\)")


def _blank(src):
    """`src` with comment and string-literal bodies replaced by spaces, offsets preserved.

    Load-bearing twice over. `//` comments in both module sets quote `anchor_sweep(...)` calls
    in prose, and every `ensure` message in the generated module contains `{sec}`-style braces
    that would derail the brace walk below. Offsets are preserved so a diagnostic can still
    name the real line."""
    out = list(src)
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                out[i] = " "
                i += 1
        elif c == '"':
            out[i] = " "
            i += 1
            while i < n and src[i] != '"':
                esc = src[i] == "\\"
                out[i] = "\n" if src[i] == "\n" else " "
                i += 1
                if esc and i < n:
                    out[i] = "\n" if src[i] == "\n" else " "
                    i += 1
            if i < n:
                out[i] = " "
                i += 1
        else:
            i += 1
    return "".join(out)


def _line_of(src, offset):
    return src.count("\n", 0, offset) + 1


def _array_sweeps(path, blanked):
    """The hand shape: `preset(... patch_motion: [ anchor_sweep(..), .. ] ..)`.

    Same reading as `authored_sweeps()`, restated over an arbitrary path and carrying the
    absolute OFFSET of each call so the chooser walk can tell which occurrences are already
    accounted for. The channel is the POSITION in the array, which is what
    Effects_InstallPreset's seed loop means by it."""
    found = []
    for m in re.finditer(r"pub data (\w+):\s*EffectsPreset\s*=\s*preset\(", blanked):
        name = m.group(1)
        i, depth = m.end() - 1, 0
        while i < len(blanked):
            if blanked[i] == "(":
                depth += 1
            elif blanked[i] == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        base = m.end()
        body = blanked[base:i]
        pm = re.search(r"patch_motion:\s*\[", body)
        if not pm:
            continue
        j, depth = pm.end() - 1, 0
        while j < len(body):
            if body[j] == "[":
                depth += 1
            elif body[j] == "]":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        arr_base = base + pm.end()
        arr = body[pm.end():j]
        elems, depth, start = [], 0, 0
        for k, ch in enumerate(arr):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "," and depth == 0:
                elems.append((start, arr[start:k]))
                start = k + 1
        elems.append((start, arr[start:]))
        for idx, (off, e) in enumerate(elems):
            s = _SWEEP_CALL.search(e)
            if not s:
                continue
            a = _SWEEP_ARGS.match(e, s.end() - 1)
            abs_off = arr_base + off + s.start()
            if not a:
                found.append((None, Unresolved(
                    path, abs_off, "argument list is not the `amp_shift:/period_shift:"
                    "[/phase:]` keyword form this scanner can read", e.strip())))
                continue
            found.append((Sweep(path, "array", name, idx, int(a.group(1)), int(a.group(2)),
                                int(a.group(3) or 0), abs_off), None))
    return found


def _chooser_sweeps(path, blanked, claimed):
    """The generated shape: `if sec == N && ch == C { out = anchor_sweep(..) }`.

    A brace walk keeping a stack of the enclosing `comptime fn` name and `if` conditions, so
    both the one-line chooser body every other binding in `effects_scenes.emp` already uses
    and a multi-line one are read the same way. The channel comes from the `ch ==` term of the
    guard, because in this shape there is no array position to carry it.

    An occurrence whose guard names no channel is UNRESOLVED, not skipped. That is the whole
    anti-silence contract: the emitted shape is a prediction until step 4 of the authoring-key
    chain lands, and a prediction that turns out wrong must fail loudly rather than scan to
    zero and read as "every sweep is in band"."""
    n = len(blanked)
    i, depth = 0, 0
    pending = None
    stack = []
    found = []
    while i < n:
        c = blanked[i]
        if c == "{":
            depth += 1
            if pending is not None:
                stack.append((depth, pending))
                pending = None
            i += 1
            continue
        if c == "}":
            while stack and stack[-1][0] == depth:
                stack.pop()
            depth -= 1
            i += 1
            continue
        w = _WORD.match(blanked, i)
        if not w:
            i += 1
            continue
        word, end = w.group(0), w.end()
        if word == "if":
            j, pd = end, 0
            while j < n:
                if blanked[j] == "(":
                    pd += 1
                elif blanked[j] == ")":
                    pd -= 1
                elif pd == 0 and blanked[j] in "{}":
                    break
                j += 1
            pending = ("if", blanked[end:j].strip()) if j < n and blanked[j] == "{" else None
            i = end
            continue
        if word == "fn":
            nm = _WORD.match(blanked, end + (len(blanked[end:]) - len(blanked[end:].lstrip())))
            pending = ("fn", nm.group(0) if nm else "<anonymous>")
            i = end
            continue
        if word == "anchor_sweep":
            rest = blanked[end:]
            pad = len(rest) - len(rest.lstrip())
            if not rest[pad:pad + 1] == "(":
                # The NAME and not a CALL — an import list (`use ...{anchor_sweep, ..}`) or a
                # prose mention that survived blanking. `_SWEEP_CALL` does not count it, so
                # neither may the walk, or scan_module()'s occurrence accounting reports a
                # phantom. Found by that accounting on the first run, which is what it is for.
                i = end
                continue
            if i in claimed:
                i = end
                continue
            a = _SWEEP_ARGS.match(blanked, end + pad)
            guards = [t for kind, t in (s[1] for s in stack) if kind == "if"]
            fns = [t for kind, t in (s[1] for s in stack) if kind == "fn"]
            chm = None
            for g in reversed(guards):
                q = re.search(r"\bch\s*==\s*(\d+)", g)
                if q:
                    chm = int(q.group(1))
                    break
            secm = None
            for g in reversed(guards):
                q = re.search(r"\bsec\s*==\s*(\d+)", g)
                if q:
                    secm = int(q.group(1))
                    break
            if a is None:
                found.append((None, Unresolved(
                    path, i, "argument list is not the `amp_shift:/period_shift:[/phase:]` "
                    "keyword form this scanner can read", blanked[i:i + 90].strip())))
            elif chm is None:
                found.append((None, Unresolved(
                    path, i, "no enclosing guard names a channel (`ch == <int>`), and this "
                    "occurrence is not at a `patch_motion:` array position either, so there "
                    "is nothing to associate a patchable band with",
                    ("in %s, guards %r" % (fns[-1] if fns else "<file scope>", guards))[:200])))
            else:
                site = "%s(sec: %s, ch: %d)" % (fns[-1] if fns else "<file scope>",
                                                secm if secm is not None else "*", chm)
                found.append((Sweep(path, "chooser", site, chm, int(a.group(1)),
                                    int(a.group(2)), int(a.group(3) or 0), i), None))
            i = end
            continue
        i = end
    return found


def scan_module(path):
    """(sweeps, unresolved) for ONE module, over BOTH shapes, accounting for EVERY occurrence.

    The one entry point. The real modules and the fixtures go through it identically, so the
    fixtures prove the code that runs in production and not a sibling of it."""
    src = _read(path)
    blanked = _blank(src)
    sweeps, unresolved = [], []
    claimed = set()
    for s, u in _array_sweeps(path, blanked):
        if s is not None:
            sweeps.append(s)
            claimed.add(s.offset)
        else:
            unresolved.append(u)
            claimed.add(u.offset)
    for s, u in _chooser_sweeps(path, blanked, claimed):
        (sweeps if s is not None else unresolved).append(s if s is not None else u)
    total = len(_SWEEP_CALL.findall(blanked))
    if len(sweeps) + len(unresolved) != total:
        raise AssertionError(
            "%s: the scan accounted for %d of %d `anchor_sweep(` occurrences. An occurrence "
            "that is neither classified nor refused is the exact silence this file exists to "
            "prevent — fix the walk, do not widen the pattern."
            % (path, len(sweeps) + len(unresolved), total))
    return sweeps, unresolved


def hand_modules():
    return sorted(glob.glob(HAND_GLOB))


def generated_modules():
    return sorted(glob.glob(GENERATED_GLOB))


def scanned_modules():
    return hand_modules() + generated_modules()


def scan_all():
    sweeps, unresolved = [], []
    for p in scanned_modules():
        s, u = scan_module(p)
        sweeps.extend(s)
        unresolved.extend(u)
    return sweeps, unresolved


# ---- THE BOUNDS, one function per obligation, applied to hand and generated alike ----------
#
# Every expectation here is DERIVED at call time: the bands come from the `patchable(..)`
# calls in source and the peak excursion from `ANCHOR_SINE_AMP` in raster_dsl.emp. Not one
# number below is transcribed from a nearby pin.

def band_violations(sweeps, amp=None):
    """[(sweep, kind, message)] — the checks that need only the sweep and its channel's band.

    The band comes from `bands_for_sweep`, i.e. from the program the sweep's own SECTION
    installs. Under one patched program that was the same answer as the act-wide union; under
    two it is not, and the union's answer is wrong in the direction that reads as a pass."""
    amp = _const(_read(RASTER_DSL), "ANCHOR_SINE_AMP", RASTER_DSL) if amp is None else amp
    progs, presets, sections = patched_programs(), preset_patched_programs(), section_presets()
    out = []
    for s in sweeps:
        bands, why, has_prog = bands_for_sweep(s, progs, presets, sections)
        if not has_prog:
            continue                      # no band exists to fit — see band_unevaluated()
        if s.channel not in bands:
            out.append((s, "dead-channel",
                        "%s (%s, %s) authors a sweep on channel %d, which no patchable() call "
                        "REACHABLE FROM THAT SECTION declares a band for (%s; channels with a "
                        "band there: %s). Nothing consumes that channel's line, so the "
                        "sweep is invisible — and if a band is added later it inherits an "
                        "amplitude nobody checked against it."
                        % (s.site, s.shape, os.path.relpath(s.path, AEON), s.channel, why,
                           sorted(bands) or "none")))
            continue
        lo, hi = bands[s.channel]
        height = hi - lo + 1
        peak_to_peak = 2 * (amp >> s.amp_shift)
        if peak_to_peak > height:
            out.append((s, "band-fit",
                        "%s (%s, %s) channel %d: peak-to-peak %d px does not fit band "
                        "%d..%d (%d lines). Above `hi` Raster_BuildSchedule DROPS the record "
                        "rather than clamping it, so the band vanishes at the top of every "
                        "cycle and returns at the next zero crossing — a flicker, not an "
                        "amplitude. Lower the sweep (amp_shift %d -> %d halves the travel) or "
                        "widen the channel's patchable band."
                        % (s.site, s.shape, os.path.relpath(s.path, AEON), s.channel,
                           peak_to_peak, lo, hi, height, s.amp_shift, s.amp_shift + 1)))
    return out


def band_unevaluated(sweeps):
    """[(sweep, why)] for the sweeps the band-fit bound CANNOT be evaluated for.

    A sweep whose section installs no patched program has no band to fit. That is not a pass
    and it is not a violation, and the one thing it must never be is invisible — this file has
    booked "a green that states nothing" as its own failure mode more than once, so the count
    goes into the coverage report and a test asserts every member really is in this state."""
    progs, presets, sections = patched_programs(), preset_patched_programs(), section_presets()
    out = []
    for s in sweeps:
        _bands, why, has_prog = bands_for_sweep(s, progs, presets, sections)
        if not has_prog:
            out.append((s, why))
    return out


def chooser_seeds(path):
    """{(sec, ch): world_y} from a generated module's world-Y chooser, where one is emitted.

    The authoring key is TWO keys or nothing (spec §2's own words): a motion without a seed
    leaves the anchor at PATCH_ANCHOR_NONE and the sweep is invisible. But a document may
    legally say nothing and KEEP the section's hand-authored seed, so a missing entry here is
    not by itself a violation — it is the reason the seeded-headroom bound is reported as NOT
    APPLIED rather than silently passed."""
    blanked = _blank(_read(path))
    seeds = {}
    for m in re.finditer(r"\bif\b([^{}]*?)\{([^{}]*?)\}", blanked, re.S):
        cond, body = m.group(1), m.group(2)
        c = re.search(r"\bch\s*==\s*(\d+)", cond)
        s = re.search(r"\bsec\s*==\s*(\d+)", cond)
        v = re.search(r"\bout\s*=\s*(-?\d+)\s*$", body.strip())
        if c and v:
            seeds[(int(s.group(1)) if s else None, int(c.group(1)))] = int(v.group(1))
    return seeds


def headroom_violations(sweeps, seeds_by_path, amp=None):
    """[(sweep, kind, message)] for the sweeps whose seeded anchor is in reach.

    Returns the violations AND the set of sweeps it could not evaluate, because "not checked"
    has to be reportable rather than indistinguishable from "checked and fine"."""
    amp = _const(_read(RASTER_DSL), "ANCHOR_SINE_AMP", RASTER_DSL) if amp is None else amp
    progs, presets, sections = patched_programs(), preset_patched_programs(), section_presets()
    out, unevaluated = [], []
    for s in sweeps:
        bands, _why, _has = bands_for_sweep(s, progs, presets, sections)
        if s.channel not in bands:
            continue                      # already reported by band_violations
        seed = seeds_by_path.get(s.path, {})
        key = None
        for k in seed:
            if k[1] == s.channel and ("sec: %s" % k[0]) in s.site:
                key = k
                break
        # THE CAMERA HAS TO BELONG TO THE SECTION, or the bound is arithmetic about a place
        # the sweep is not. SPAWN_CAMERA_Y is the act spawn's camera and the act spawn is in
        # SPAWN_SECTION; a sweep authored on any other section is reported as not evaluated
        # rather than judged against it. See the SPAWN_SECTION note above.
        if key is not None and key[0] is not None and key[0] != SPAWN_SECTION:
            unevaluated.append(s)
            continue
        if key is None:
            unevaluated.append(s)
            continue
        lo, hi = bands[s.channel]
        line = seed[key] - SPAWN_CAMERA_Y
        peak = amp >> s.amp_shift
        if line - peak < lo:
            out.append((s, "headroom-lo",
                        "%s (%s) channel %d: at the spawn camera (Y %d) the seeded line is %d "
                        "and the sweep's peak takes it to %d, below the band floor %d. Below "
                        "`lo` the fire clamps up, so the top of every cycle stops tracking."
                        % (s.site, os.path.relpath(s.path, AEON), s.channel, SPAWN_CAMERA_Y,
                           line, line - peak, lo)))
        if line + peak > hi:
            out.append((s, "headroom-hi",
                        "%s (%s) channel %d: at the spawn camera (Y %d) the seeded line is %d "
                        "and the sweep's peak takes it to %d, past the band ceiling %d, where "
                        "the record is DROPPED and the band disappears for that frame."
                        % (s.site, os.path.relpath(s.path, AEON), s.channel, SPAWN_CAMERA_Y,
                           line, line + peak, hi)))
    return out, unevaluated


def coverage_report():
    """What this file scanned and what it did not — the text a green run still has to say.

    BAR 25's problem in miniature: `pytest -q` prints dots, so a scan that found nothing
    because it looked in the wrong place is indistinguishable from a scan that found nothing
    because there is nothing wrong. This is the difference, spelled out."""
    lines = ["anchor-sweep band scan — coverage, stated because a green cannot state it:"]
    bands = patchable_bands()
    sections = section_presets()
    for label, paths in (("hand-authored (%s)" % os.path.relpath(HAND_GLOB, AEON),
                          hand_modules()),
                         ("generated (%s)" % os.path.relpath(GENERATED_GLOB, AEON),
                          generated_modules())):
        lines.append("  %s: %d module(s)" % (label, len(paths)))
        if not paths:
            lines.append("    (NONE MATCHED — this is a scanner looking in the wrong place, "
                         "not an all-clear)")
        for p in paths:
            s, u = scan_module(p)
            shapes = collections.Counter(x.shape for x in s)
            lines.append("    %-58s  %d sweep(s) [%s]%s"
                         % (os.path.relpath(p, AEON), len(s),
                            ", ".join("%d %s" % (v, k) for k, v in sorted(shapes.items()))
                            or "none",
                            "  UNRESOLVED: %d" % len(u) if u else ""))
    lines.append("  bands read from %s, PER PATCHED PROGRAM (a channel is a per-program "
                 "index): %s" % (os.path.relpath(OJZ_EFFECTS, AEON),
                                 "; ".join("%s ch %d = %d..%d (%d lines)"
                                           % (label, c, lo, hi, hi - lo + 1)
                                           for c, entries in sorted(bands.items())
                                           for label, (lo, hi) in entries)))
    lines.append("  sections -> presets (%s): %s"
                 % (os.path.relpath(DESCRIPTOR, AEON),
                    ", ".join("%d=%s" % (k, v) for k, v in sorted(sections.items()))))
    sweeps, unresolved = scan_all()
    gen = [s for s in sweeps if s.path in set(generated_modules())]
    lines.append("  LIVE GENERATED POPULATION: %d sweep(s). %s"
                 % (len(gen),
                    "EMPTY — the authoring key has a shape but no reader "
                    "(docs/superpowers/specs/2026-09-03-anchor-authoring-key-shape.md, steps "
                    "2-4 open), so the generated arm is green against NOTHING and is proven "
                    "instead by tools/fixtures/anchor_sweep/." if not gen
                    else "the arm has a real subject; the fixtures remain as its floor."))
    seeds = {p: chooser_seeds(p) for p in generated_modules()}
    _, unevaluated = headroom_violations(gen, seeds)
    lines.append("  NOT CHECKED: seeded headroom for %d of the %d generated sweep(s) — either "
                 "the anchor is not in this file's reach (a document may legally keep the "
                 "section's hand-authored patch_world_ys) or the sweep is not on the spawn "
                 "section %d, the only section SPAWN_CAMERA_Y (%d) is the camera for. Band "
                 "fit and channel liveness ARE checked for all %d scanned sweep(s)."
                 % (len(unevaluated), len(gen), SPAWN_SECTION, SPAWN_CAMERA_Y, len(sweeps)))
    no_band = band_unevaluated(sweeps)
    lines.append("  NO BAND TO FIT: %d of the %d scanned sweep(s)%s" %
                 (len(no_band), len(sweeps),
                  "" if not no_band else " — " + "; ".join(
                      "%s (%s)" % (s.site, why) for s, why in no_band)))
    if unresolved:
        lines.append("  UNRESOLVED OCCURRENCES: %d — see the failing test" % len(unresolved))
    return "\n".join(lines)


class TestTheLaddersAreDerivedFromTheConstantsTheyClaim(unittest.TestCase):
    """raster_dsl.emp spells three sine/screen facts as LITERALS because a COMPTIME_HELPERS
    `pub const` must fold from its own file's names. engine/effects/raster.emp pins those
    literals to engine.constants at BUILD time. This is the same fact checked from outside
    the compiler, so a build run with CONTRACTS=0 or a stale sigil still cannot hide it."""

    def setUp(self):
        self.dsl = _read(RASTER_DSL)
        self.consts = _read(CONSTANTS)

    def test_the_inlined_sine_and_screen_facts_match_engine_constants(self):
        for local, canonical in (("ANCHOR_SINE_AMP", "SINE_AMPLITUDE"),
                                 ("ANCHOR_SINE_ENTRIES", "SINE_CYCLE_ENTRIES"),
                                 ("ANCHOR_SCREEN_LINES", "SCREEN_HEIGHT")):
            self.assertEqual(
                _const(self.dsl, local, RASTER_DSL),
                _const(self.consts, canonical, CONSTANTS),
                "engine/effects/raster_dsl.emp's %s has drifted from engine.constants.%s. "
                "Every sweep ladder is derived from it, so every authored amp_shift and "
                "period_shift changes meaning silently." % (local, canonical))

    def test_the_published_ladders_are_what_the_derivations_produce(self):
        amp = _const(self.dsl, "ANCHOR_SINE_AMP", RASTER_DSL)
        entries = _const(self.dsl, "ANCHOR_SINE_ENTRIES", RASTER_DSL)
        lines = _const(self.dsl, "ANCHOR_SCREEN_LINES", RASTER_DSL)
        bits = _const(self.dsl, "ANCHOR_TICK_BITS", RASTER_DSL)
        # The published values, read as the expressions raster_dsl.emp writes them as.
        self.assertIn("pub const ANCHOR_SWEEP_SHIFT_MIN        = anchor_shift_min(ANCHOR_SINE_AMP, ANCHOR_SCREEN_LINES)",
                      self.dsl,
                      "ANCHOR_SWEEP_SHIFT_MIN is no longer derived from the two literals this "
                      "test re-derives it from — if it became a hand-written number, the "
                      "derivation stopped being the authority and this check is measuring "
                      "nothing")
        self.assertGreaterEqual(_shift_min(amp, lines), 1,
                                "the amplitude ladder admits shift 0, which collides with the "
                                "ANCHOR_MOTION_NONE sentinel")
        self.assertLessEqual(_shift_min(amp, lines), _shift_max(amp),
                             "the amplitude ladder is empty")
        self.assertLessEqual(_period_shift_max(entries, bits), 15,
                             "the period ladder does not fit the nibble the motion word packs "
                             "it into")


class TestAuthoredSweepsFitTheirBands(unittest.TestCase):
    """THE CHECK THE COMPILER CANNOT MAKE — the design's §11 Q1, answered outside comptime."""

    def test_every_patchable_band_in_the_source_is_reachable_through_a_program(self):
        """THE ANTI-SILENCE EDGE OF THE RESOLVER, and the successor to
        `test_the_channel_to_band_map_is_unambiguous`.

        That test asserted ONE patched program in the tree and said, in its own message, what
        to do when a second appeared: *"the map has to be built per (preset -> program) before
        this test means anything again."* EFFECTS-W1 item 9c's precondition landed the second
        program and `patched_programs()` is that map. What has to hold now is not uniqueness —
        two programs may legitimately both use channel 0 — but that the resolver SEES every
        band the source declares. A `patchable()` outside any program this reader can find
        would make every bound below skip it silently, which is the failure mode the old test
        was really protecting against."""
        src = _blank(_read(OJZ_EFFECTS))
        in_source = len(_BAND_TRIPLE.findall(src))
        progs = patched_programs()
        reached = sum(len(b) for b in progs.values())
        self.assertTrue(progs, "no patched program at all was found in %s — every band bound "
                               "in this file would be vacuous"
                               % os.path.relpath(OJZ_EFFECTS, AEON))
        self.assertEqual(
            in_source, reached,
            "%s declares %d `patchable(ch:, lo:, hi:)` band(s) but the resolver reaches only "
            "%d of them through %d patched program(s) (%r). A band the resolver cannot see is "
            "a band no bound in this file applies to — teach patched_programs() the spelling "
            "rather than widening a pattern."
            % (os.path.relpath(OJZ_EFFECTS, AEON), in_source, reached, len(progs),
               {k: sorted(v) for k, v in progs.items()}))

    def test_every_section_resolves_to_a_preset_and_every_patched_preset_to_a_program(self):
        """The two edges `bands_for_sweep` walks, asserted where a break names itself.

        Without this, a descriptor that stopped spelling `effects:` in a readable form would
        make every generated sweep resolve to "no preset", i.e. to a dead channel — which is a
        LOUD failure, but one whose message would blame the document instead of this reader.
        With a preset that binds `patched:` through a chooser it is the opposite: silence."""
        sections = section_presets()
        self.assertEqual(
            sorted(sections), list(range(9)),
            "%s no longer yields one `ojz_sec(sec: N, .., effects: ..)` row per section 0..8; "
            "got %r. Every generated sweep resolves its band through this map."
            % (os.path.relpath(DESCRIPTOR, AEON), sorted(sections)))
        progs = patched_programs()
        for name, prog in sorted(preset_patched_programs().items()):
            self.assertIn(
                prog, progs,
                "preset %s binds `patched: %s`, which is not a program patched_programs() "
                "found. bands_for_preset() raises on this rather than resolving to nothing, "
                "so it is a hard stop either way — this test is the one that names it before "
                "a sweep does." % (name, prog))

    def test_there_is_at_least_one_authored_sweep(self):
        """The anchor mover's engine half landed with exactly one authored edge. A tree with
        none would make every assertion below vacuously true, and this suite has booked that
        failure mode more than once."""
        self.assertTrue(
            authored_sweeps(),
            "no `anchor_sweep(...)` is authored anywhere in "
            "games/sonic4/data/effects/ojz_effects.emp. EFFECTS-W1 item 4 landed one, on "
            "OJZ_Preset_Sec0 channel 0; if it was deliberately removed, the capability bit "
            "CAP_ANCHOR_MOTION in games/sonic4/config/game.emp is now declared for a feature "
            "nothing raises and should come out in the same commit")

    def test_every_authored_sweep_fits_its_channels_patchable_band(self):
        amp = _const(_read(RASTER_DSL), "ANCHOR_SINE_AMP", RASTER_DSL)
        for name, ch, a, p, ph in authored_sweeps():
            bands, why, _has = bands_for_preset(name)
            self.assertIn(
                ch, bands,
                "%s authors a sweep on channel %d, which no patchable() call in the program "
                "THAT PRESET installs declares a band for (%s; channels with a band there: "
                "%s). Nothing consumes that channel's line, so the sweep is invisible — and "
                "if a band is added later it inherits an amplitude nobody checked against it."
                % (name, ch, why, sorted(bands) or "none"))
            lo, hi = bands[ch]
            height = hi - lo + 1
            peak_to_peak = 2 * (amp >> a)
            self.assertLessEqual(
                peak_to_peak, height,
                "%s channel %d: peak-to-peak %d px does not fit band %d..%d (%d lines). "
                "Above `hi` Raster_BuildSchedule DROPS the record rather than clamping it, so "
                "the band vanishes at the top of every cycle and returns at the next zero "
                "crossing — a flicker, not an amplitude. Lower the sweep (amp_shift %d -> %d "
                "halves the travel) or widen the channel's patchable band."
                % (name, ch, peak_to_peak, lo, hi, height, a, a + 1))

    def test_every_authored_sweep_leaves_headroom_at_its_seeded_position(self):
        """Fitting the band is necessary; sitting somewhere the excursion actually fits is the
        rest of it. The seeded anchor and the band are both in the source, and the camera at
        which they are compared is the one the gate scenes and the act's own notes use."""
        amp = _const(_read(RASTER_DSL), "ANCHOR_SINE_AMP", RASTER_DSL)
        src = _read(OJZ_EFFECTS)
        for name, ch, a, p, ph in authored_sweeps():
            bands, _why, _has = bands_for_preset(name)
            m = re.search(r"pub data %s:\s*EffectsPreset\s*=\s*preset\(" % re.escape(name), src)
            body = src[m.end():m.end() + 4000]
            wy = re.search(r"patch_world_ys:\s*\[([^\]]*)\]", body)
            self.assertIsNotNone(
                wy, "%s authors motion but no patch_world_ys — the anchor it sweeps around "
                    "would be whatever preset() defaults to" % name)
            elems = [e.strip() for e in wy.group(1).split(",")]
            self.assertGreater(len(elems), ch, "%s: patch_world_ys is shorter than the "
                                               "channel its motion is authored on" % name)
            self.assertTrue(elems[ch].lstrip("-").isdigit(),
                            "%s channel %d: the seeded anchor %r is not a literal, so this "
                            "bound cannot be evaluated" % (name, ch, elems[ch]))
            line = int(elems[ch]) - SPAWN_CAMERA_Y
            lo, hi = bands[ch]
            peak = amp >> a
            self.assertGreaterEqual(
                line - peak, lo,
                "%s channel %d: at the spawn camera (Y %d) the seeded line is %d and the "
                "sweep's peak takes it to %d, below the band floor %d. Below `lo` the fire "
                "clamps up, so the top of every cycle stops tracking."
                % (name, ch, SPAWN_CAMERA_Y, line, line - peak, lo))
            self.assertLessEqual(
                line + peak, hi,
                "%s channel %d: at the spawn camera (Y %d) the seeded line is %d and the "
                "sweep's peak takes it to %d, past the band ceiling %d, where the record is "
                "DROPPED and the band disappears for that frame."
                % (name, ch, SPAWN_CAMERA_Y, line, line + peak, hi))


class TestTheGateScenesHoldTheMoverStill(unittest.TestCase):
    """tools/effects_gates.py derives every expected arm word from `anchor - Camera_Y`. That
    arithmetic is only true while nothing is moving the anchor, and the mover deliberately runs
    OUTSIDE `Debug_Scene_Freeze` — a frozen camera still has to be latched. So every scene that
    pins channel 0's anchor must also disarm the mover, or its expectations become a function
    of which frame the capture landed on."""

    def test_every_scene_that_pins_an_anchor_also_disarms_the_mover(self):
        for fn in sorted(os.listdir(SCENES_DIR)):
            if not fn.endswith(".json"):
                continue
            sc = json.loads(_read(os.path.join(SCENES_DIR, fn)))
            pokes = {s["poke"]["symbol"]: s["poke"]
                     for s in sc.get("steps", []) if "poke" in s and "symbol" in s["poke"]}
            if "Effects_World_Y" not in pokes and "Camera_Y" not in pokes:
                continue
            self.assertIn(
                "Effects_Motion_Any", pokes,
                "tools/scenes/%s pins the camera and/or channel 0's anchor but does not poke "
                "Effects_Motion_Any. Since EFFECTS-W1 item 4, OJZ_Preset_Sec0 authors a sweep "
                "on channel 0 and Effects_LatchWorldLines adds it to the latched line every "
                "frame, outside the scene freeze — so the derived arm words in "
                "tools/effects_gates.py would be measuring the sine, not the schedule builder."
                % fn)
            self.assertEqual(
                pokes["Effects_Motion_Any"].get("value"), 0,
                "tools/scenes/%s pokes Effects_Motion_Any to %r, not 0. Any nonzero value ARMS "
                "the mover — the word is a `tst.w`, not a bitfield the gate can pick apart."
                % (fn, pokes["Effects_Motion_Any"].get("value")))


class TestTheScanCoversBothModuleSetsAndBothShapes(unittest.TestCase):
    """THE GENERATED ARM. Everything above reads one file in one shape; these read the set.

    The order matters: the module set is asserted to be non-empty and to contain the path the
    generator itself computes BEFORE any sweep is examined, because a scanner pointed at
    nothing passes every downstream check trivially. That is the failure this class exists to
    make impossible, not the one it exists to survive."""

    def test_the_hand_set_still_contains_the_module_the_original_tests_read(self):
        self.assertIn(
            OJZ_EFFECTS, hand_modules(),
            "the hand-module glob %r no longer matches %s, which the four original tests in "
            "this file read directly. The two readings have drifted apart and the unified "
            "scan is now covering a different tree than the checks above."
            % (HAND_GLOB, OJZ_EFFECTS))

    def test_the_generated_module_set_is_not_empty_and_is_where_the_generator_writes(self):
        """The anti-silence check with the most leverage: it converts "the scanner is looking
        in the wrong place" from a green run into a red one. The expected path is taken from
        `tools/effects_gen.py`'s own `out_path()` rather than transcribed, so a generator that
        moves its output moves this test with it."""
        mods = generated_modules()
        self.assertTrue(
            mods,
            "the generated-module glob %r matched NOTHING. Every generated-arm assertion "
            "below would pass vacuously. Either the bake has not run, or "
            "tools/effects_gen.py's ActNames.out_path() no longer writes there — check that "
            "first, because a scanner that finds no sweeps because it looked in the wrong "
            "place reads exactly like a tree in which all sweeps are in band." % GENERATED_GLOB)
        import sys
        if os.path.join(AEON, "tools") not in sys.path:
            sys.path.insert(0, os.path.join(AEON, "tools"))
        try:
            import effects_gen
        except Exception as exc:                                    # pragma: no cover
            self.fail("cannot import tools/effects_gen.py to derive the generated module's "
                      "path (%r), so the glob above is an unchecked copy of a path this file "
                      "does not own" % (exc,))
        expected = effects_gen.act_names(AEON, 0, 0).out_path(AEON)
        self.assertIn(
            os.path.normpath(expected), [os.path.normpath(m) for m in mods],
            "tools/effects_gen.py writes act 0/0's module to %r, which the glob %r does not "
            "match. The generated arm is scanning somewhere the generator does not write."
            % (expected, GENERATED_GLOB))

    def test_no_anchor_sweep_occurrence_is_left_unaccounted_for(self):
        """Every `anchor_sweep(` in every scanned module is classified as an array position or
        a chooser body, or it is a failure here. There is no third outcome, and specifically
        there is no 'skipped'."""
        _, unresolved = scan_all()
        self.assertEqual(
            [], unresolved,
            "an `anchor_sweep(` occurrence was found that this scanner cannot associate with "
            "a channel:\n" + "\n".join(
                "  %s:%d — %s\n      %s"
                % (os.path.relpath(u.path, AEON), _line_of(_read(u.path), u.offset), u.why,
                   u.text)
                for u in unresolved) +
            "\n\nThis is NOT a reason to loosen the pattern. The emitted chooser shape is a "
            "prediction until step 4 of the authoring-key chain lands; if it came out "
            "different, teach _chooser_sweeps() the real shape. An occurrence this file "
            "cannot read is an amplitude nothing is checking.")

    def test_the_unified_scan_agrees_with_the_original_reader_on_the_hand_module(self):
        """PROOF, not assertion, that the existing coverage is unchanged: the new scanner's
        array arm must reproduce `authored_sweeps()` exactly on `ojz_effects.emp`, record for
        record. If the new code re-interpreted the record the four original tests gate, the
        two readings would disagree here."""
        old = sorted(authored_sweeps())
        new = sorted((s.site, s.channel, s.amp_shift, s.period_shift, s.phase)
                     for s in scan_module(OJZ_EFFECTS)[0] if s.shape == "array")
        self.assertEqual(
            old, new,
            "the unified scan reads %s differently from authored_sweeps(): %r vs %r. The "
            "original reader is the one the four tests above gate on, so a disagreement means "
            "the generated arm changed what the hand arm sees."
            % (os.path.relpath(OJZ_EFFECTS, AEON), old, new))

    def test_only_one_scanned_module_declares_patchable_bands(self):
        """`test_the_channel_to_band_map_is_unambiguous` above holds this inside
        ojz_effects.emp. The scan set is wider than that file, so the same fact has to hold
        across the set — a generated module that emitted its own `patchable(..)` would make
        `bands[ch]` name two different bands and every bound below would be resolved against
        the wrong one."""
        declaring = [p for p in scanned_modules() if re.search(r"\bpatchable\s*\(", _blank(_read(p)))]
        self.assertEqual(
            [OJZ_EFFECTS], declaring,
            "patchable() bands are declared in %r, not in %s alone. A channel index no longer "
            "names one band across the scanned set, so patchable_bands() is resolving sweeps "
            "against a band that may not be theirs — the map has to be built per "
            "(module -> program) before the bounds below mean anything again."
            % ([os.path.relpath(p, AEON) for p in declaring],
               os.path.relpath(OJZ_EFFECTS, AEON)))

    def test_every_scanned_sweep_fits_its_channels_patchable_band(self):
        """The check the compiler cannot make, now over BOTH module sets and BOTH shapes.

        Today this adds nothing over the hand-only test above, because the generated
        population is empty — said out loud rather than left to be inferred from a green."""
        sweeps, _ = scan_all()
        bad = band_violations(sweeps)
        self.assertEqual([], [m for _, _, m in bad], "\n".join(m for _, _, m in bad))

    def test_every_generated_sweep_with_a_reachable_seed_has_headroom(self):
        gen_paths = set(generated_modules())
        sweeps = [s for s in scan_all()[0] if s.path in gen_paths]
        seeds = {p: chooser_seeds(p) for p in gen_paths}
        bad, _ = headroom_violations(sweeps, seeds)
        self.assertEqual([], [m for _, _, m in bad], "\n".join(m for _, _, m in bad))

    def test_the_scan_says_what_it_did_and_did_not_cover(self):
        """`pytest -q` prints dots, so a green run names nothing it looked at. The report goes
        out as a warning, which pytest surfaces in its summary even under -q, and the
        assertions below are on the report's CONTENT — a report that stopped naming the
        generated glob or stopped stating the live population would be a scanner that went
        quiet again."""
        report = coverage_report()
        warnings.warn("\n" + report, UserWarning, stacklevel=1)
        self.assertIn("generated", report)
        self.assertIn("LIVE GENERATED POPULATION", report,
                      "the coverage report no longer states how many generated sweeps it "
                      "actually saw, which is the one number that separates 'nothing is "
                      "wrong' from 'nothing was scanned'")
        self.assertIn("NOT CHECKED", report,
                      "the coverage report no longer states what it did NOT check. A report "
                      "that lists only its successes is the silent failure in a longer form")


class TestTheGeneratedArmIsProvenByItsFixtures(unittest.TestCase):
    """The live population is no longer empty (see this file's docstring), so these fixtures
    are the generated arm's FLOOR rather than its only subject — and they stay, because they
    are the only way to exercise the arm's REFUSING paths. A tree that carried an out-of-band
    amplitude, a dead channel or an unreadable occurrence would simply be a broken tree, so
    those three cases can never have a live subject.

    They go through `scan_module()` — the same function the real modules go through — so what
    is proven here is the production path and not a sibling of it."""

    OUT_OF_BAND = os.path.join(FIXTURE_DIR, "generated_chooser_out_of_band.emp")
    IN_BAND = os.path.join(FIXTURE_DIR, "generated_chooser_in_band.emp")
    DEAD_CHANNEL = os.path.join(FIXTURE_DIR, "generated_chooser_dead_channel.emp")
    UNGUARDED = os.path.join(FIXTURE_DIR, "generated_chooser_unguarded.emp")

    def test_the_live_generated_population_is_not_empty(self):
        """Was `..._really_is_empty`, a statement of record, written so that the day it
        stopped being true this test would say so. That day is 2026-09-03: step 4 landed, a
        document authors the key, and the assertion INVERTS rather than being deleted — an
        arm that silently loses its live subject again is exactly the state the old name was
        watching for, and it is now a red instead of a warning."""
        gen_paths = set(generated_modules())
        gen = [s for s in scan_all()[0] if s.path in gen_paths]
        self.assertTrue(generated_modules(),
                        "there is no generated module at all, so 'the population' is not even "
                        "a measurement of the right thing — run tools/effects_gen.py emit")
        self.assertTrue(
            gen,
            "the generated arm's live population is EMPTY again. It was 1 when step 4 of the "
            "authoring-key chain landed (a `patch_motion` sweep in "
            "games/sonic4/data/editor/effects/presets/ojz_sec5_showcase.json, bound through "
            "section_5.meta.json's rasterRef). With it gone, every green from "
            "test_every_scanned_sweep_fits_its_channels_patchable_band is vacuous for the "
            "generated half and only the fixtures in %s prove that arm works. Either a "
            "document lost its key, a sidecar lost its binding, or tools/effects_gen.py "
            "stopped emitting the chooser row."
            % os.path.relpath(FIXTURE_DIR, AEON))
        warnings.warn("the generated arm has %d REAL sweep(s); the fixtures below are its "
                      "floor, not its only subject" % len(gen), UserWarning, stacklevel=1)

    def test_the_fixtures_exist_and_are_not_build_inputs(self):
        for p in (self.OUT_OF_BAND, self.IN_BAND, self.DEAD_CHANNEL, self.UNGUARDED):
            self.assertTrue(os.path.isfile(p), "missing fixture %s — the generated arm has no "
                                               "subject at all without it" % p)
            self.assertNotIn(p, scanned_modules(),
                             "%s is inside the SCANNED set. The refuse fixtures would fail the "
                             "real bounds and the suite would be red for a reason that is not "
                             "a defect." % p)
        self.assertEqual(
            [], glob.glob(os.path.join(FIXTURE_DIR, "*.emp")) and
            [p for p in glob.glob(os.path.join(FIXTURE_DIR, "*.emp"))
             if os.path.normpath(p) in [os.path.normpath(m) for m in scanned_modules()]],
            "a fixture is reachable from the production globs")

    def test_the_fixtures_still_straddle_the_real_band(self):
        """DERIVED, so the fixtures cannot rot into agreement with whatever the source says.

        Three facts are re-derived from source every run: both fixture amplitudes are rungs
        `anchor_sweep()` itself ADMITS (otherwise the compiler would refuse them and this file
        would be checking something already checked); the refuse fixture's travel does NOT fit
        its channel's band; and the accept fixture's does. If channel 1's band ever widens,
        this fails and names the fixture rather than letting it pass vacuously."""
        dsl = _read(RASTER_DSL)
        amp = _const(dsl, "ANCHOR_SINE_AMP", RASTER_DSL)
        lines = _const(dsl, "ANCHOR_SCREEN_LINES", RASTER_DSL)
        lo_rung, hi_rung = _shift_min(amp, lines), _shift_max(amp)
        for path, must_fit in ((self.OUT_OF_BAND, False), (self.IN_BAND, True)):
            sweeps, unresolved = scan_module(path)
            self.assertEqual([], unresolved, "%s: %r" % (path, unresolved))
            self.assertEqual(1, len(sweeps), "%s should carry exactly one sweep" % path)
            s = sweeps[0]
            self.assertEqual("chooser", s.shape,
                             "%s is meant to exercise the CHOOSER shape; it was read as %r"
                             % (path, s.shape))
            self.assertTrue(
                lo_rung <= s.amp_shift <= hi_rung,
                "%s uses amp_shift %d, outside anchor_sweep()'s own derived ladder %d..%d. "
                "The compiler would refuse it, so the fixture would be exercising a bound "
                "that already exists instead of the band bound that does not."
                % (path, s.amp_shift, lo_rung, hi_rung))
            bands, why, _has = bands_for_sweep(s)
            self.assertIn(s.channel, bands,
                          "%s authors channel %d, which no patchable() reachable from its own "
                          "section declares (%s) — it would be refused for its channel, not "
                          "its amplitude" % (path, s.channel, why))
            lo, hi = bands[s.channel]
            fits = 2 * (amp >> s.amp_shift) <= hi - lo + 1
            self.assertEqual(
                must_fit, fits,
                "%s was built to be %s its channel's band, but with the CURRENT band "
                "(ch %d = %d..%d, %d lines) and amplitude (%d) its peak-to-peak %d px %s. "
                "The fixture has stopped being the subject it claims to be — re-pick its "
                "amp_shift or its channel."
                % (path, "inside" if must_fit else "outside", s.channel, lo, hi,
                   hi - lo + 1, amp, 2 * (amp >> s.amp_shift),
                   "fits" if fits else "does not fit"))

    def test_the_out_of_band_fixture_is_refused_for_its_amplitude(self):
        sweeps, _ = scan_module(self.OUT_OF_BAND)
        kinds = [k for _, k, _ in band_violations(sweeps)]
        self.assertIn(
            "band-fit", kinds,
            "the generated arm ACCEPTED a chooser-shaped sweep whose peak-to-peak travel does "
            "not fit its channel's patchable band (%s). That is the whole failure this file "
            "exists to catch, in the exact shape an author will produce it."
            % os.path.relpath(self.OUT_OF_BAND, AEON))

    def test_the_in_band_fixture_is_accepted_with_no_violation_at_all(self):
        """The control. Without it, "the arm refuses everything it sees" and "the arm checks
        the band" are the same green."""
        sweeps, unresolved = scan_module(self.IN_BAND)
        self.assertEqual([], unresolved)
        bad = band_violations(sweeps)
        seeds = {self.IN_BAND: chooser_seeds(self.IN_BAND)}
        head, unevaluated = headroom_violations(sweeps, seeds)
        self.assertEqual([], [m for _, _, m in bad] + [m for _, _, m in head],
                         "the generated arm refused a sweep that is the shipped hand-authored "
                         "one re-expressed as a chooser body:\n" +
                         "\n".join(m for _, _, m in bad + head))
        self.assertEqual([], unevaluated,
                         "the in-band fixture's seed was not reachable, so its headroom was "
                         "never actually evaluated and this control is weaker than it reads")

    def test_the_dead_channel_fixture_is_refused_for_its_channel(self):
        """Obligation (c) of the authoring-key spec's §4, in the generated shape."""
        sweeps, _ = scan_module(self.DEAD_CHANNEL)
        kinds = [k for _, k, _ in band_violations(sweeps)]
        self.assertEqual(
            ["dead-channel"], kinds,
            "a generated sweep on a channel no patchable() declares was not refused (kinds: "
            "%r). Nothing consumes that channel's line, so the authored effect is simply not "
            "there — and the amplitude is the shipped rung, so nothing else about the "
            "document is wrong." % (kinds,))

    def test_a_sweep_with_no_band_to_fit_is_NAMED_and_not_silently_passed(self):
        """The partition's own control. `band_violations` skips a sweep whose section installs
        no patched program — correctly, since there is no band to fit — and a skip that
        nothing reports is the silence this file exists to end.

        Asserted as a PROPERTY, not as a list: every member really is in that state, and the
        coverage report carries the count. The live member today is section 5's generated
        sweep, whose `OJZ_Preset_Sec5` binds `raster:` and reaches channel 0 through the d-53
        `parallax:` loan instead — the arrangement that file documents at length."""
        sweeps, _ = scan_all()
        presets, sections = preset_patched_programs(), section_presets()
        for sw, why in band_unevaluated(sweeps):
            sec = _sweep_section(sw)
            name = sections.get(sec) if sec is not None else sw.site
            self.assertNotIn(
                name, presets,
                "%s was skipped by the band-fit bound as having no band to fit, but its "
                "preset %s DOES bind `patched: %s`. The partition is misreading a dead "
                "channel as an absent program, which turns a real violation into a skip."
                % (sw.site, name, presets.get(name)))
            self.assertIn("no `patched:` program", why,
                          "%s is unevaluated for a reason this test does not recognise: %r"
                          % (sw.site, why))
        self.assertIn("NO BAND TO FIT", coverage_report(),
                      "the coverage report no longer states how many scanned sweeps had no "
                      "band to fit, so the partition's skipped half is invisible again")

    def test_the_unguarded_fixture_is_refused_as_unresolved(self):
        """THE ANTI-SILENCE PROOF. The emitted shape is a prediction; this is what happens when
        the prediction is wrong. A scanner that returned `[]` here would be reporting "no
        sweeps, all in band" about a file that contains an unchecked sweep."""
        sweeps, unresolved = scan_module(self.UNGUARDED)
        self.assertEqual([], sweeps,
                         "the unguarded fixture was read as a resolvable sweep (%r); it "
                         "carries no `ch ==` guard, so any channel this produced was invented"
                         % (sweeps,))
        self.assertEqual(
            1, len(unresolved),
            "an `anchor_sweep(` with no channel guard was neither classified nor refused. "
            "That is silence, and silence is the defect — scan_module()'s occurrence count "
            "should have caught it.")
        self.assertIn("ch ==", unresolved[0].why)


if __name__ == "__main__":
    unittest.main()
