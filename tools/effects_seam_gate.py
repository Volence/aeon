#!/usr/bin/env python3
"""effects_seam_gate — is the editor-scene binding seam actually REACHED?

Scanline P5 slice 5. `act_descriptor.emp` imports two `pub comptime fn`s from the
generated module `games/sonic4/data/generated/ojz/act1/effects_scenes.emp`; that
import is the ONLY route by which an Aurora-authored scene reaches the ROM, and it
is also the module's only `use`-closure edge.

WHY A GATE AT ALL — "the import exists today" is not "the import cannot be dropped
tomorrow", and the failure mode of dropping it is SILENT. An unreached `.emp` module
gets parse + scan coverage and ZERO body elaboration (docs/EMP_PITFALLS.md §3), so
every guard in the generated module — the editor-scene budget fold, the capability
subset test, the section-count pin — would keep building green while asserting
nothing at all. MEASURED on this exact seam (2026-08-22): with the descriptor's `use`
line removed, an `ensure(1 == 0)` planted in the generated module built CLEAN with an
unchanged CRC (060401e4). Nothing else in the tree notices, because the descriptor's
hand default is what the binding resolves to today anyway — the ROM would be correct
and the gate coverage would be gone.

WHAT IT OBSERVES, AND WHY THAT OBSERVATION IS POSITIVE. The generated module declares
five `pub equ` witnesses — two scene counts and one per `EffectsPreset` channel (raster,
cycle, variant). The three channel counts are legitimately 0 until a sidecar carries a
`rasterRef` naming a document that carries the matching key; ONE ref binds the whole
document (empyrean AURORA_EFFECTS_SCHEMA.md §7.2, ruling Q1), which is why there is one
sidecar key and three witnesses. An equ mints a link-level symbol that reaches the build's
listing (the mechanism scene_registry.emp's budget ledger rows use), and it is
defined ONLY if the module is lowered — so its PRESENCE in `s4.lst` is direct
evidence that the module is inside the target's `use` closure. Presence is also what
makes the gate hard to make vacuous: a misspelled symbol name here FAILS the gate
(absent) rather than passing it, which is the opposite of an absence test like
"the module is not in the [module.unreachable] list", where a typo passes silently.

The expected VALUES are re-derived from the editor JSON inputs through
`effects_gen`'s own loaders — never read out of the generated `.emp` — so this gate
and `effects_gen.py check` (the drift gate) fail for different reasons: drift means
the committed module does not match its inputs; a value mismatch here means the
ARTIFACT does not carry what the inputs say it should.

THE RASTER SEAM IS A SECOND CALL SITE, IN A DIFFERENT FILE (EFFECTS-W1 item 1 step 5).
The two scene choosers are called from `act_descriptor.emp`; the third — the raster
chooser — is called from `games/sonic4/data/effects/ojz_effects.emp`, because a raster
program is an `EffectsPreset` channel and not a `Sec` field. It needs its own check for
the reason above AND for one more: `Sec.sec_effects` is a per-section POINTER to a record
several sections may share, so threading a SECTION-KEYED chooser into a SHARED preset
would silently give every one of those sections the same band. Step 2b checks that a
preset which chooses on sec N is bound by exactly one section, and that it is N.

Both halves are silent-and-green failures today: with no sidecar carrying a `rasterRef`
the chooser resolves to `hand`, so deleting the call and typing the literal back leaves
every witness value and every ROM byte identical.

TWO CHOOSERS, NOT ONE — THE ARM PARTITION (2026-09-04, docs/DEFERRED_WORK.md
RASTER-BOUNDARY-2). A preset document's ONE raster program lands in one of TWO `preset()`
parameters: `boundary` lowers through `patched_program()` into `EffectsPreset.ep_patched`,
everything else into `ep_raster`. One `rasterRef` still binds the whole document (ruling
Q1) — the sidecar key is not split — but the CHOOSERS are, so this gate reads each bound
document and requires the section to be threaded through the chooser THAT DOCUMENT names
(`document_arm`). Before that it required the raster chooser for every `rasterRef`, which
refused a correct patched binding outright (measured, and reported from Aurora's lane) and
was blind to a dropped one. `seam_faults`' own docstring carries the design and what was
rejected.

SIX CHOOSERS, NOT TWO — THE REQUIRED SET IS A FUNCTION OF THE DOCUMENT (2026-09-04).
The two arms above are the document's ONE raster program. The same `rasterRef` also binds
every other channel the document carries — `cycles`, `variants`, `patch_world_ys`,
`patch_motion` — and each of those is a SEPARATE generated chooser threaded into a
SEPARATE `preset()` parameter. Those four used to be checked only ACT-WIDE (step 2b: the
library imports each one and calls it somewhere), which `OJZ_Preset_Sec5` satisfied on
behalf of every other section, so a section whose document carried the two patch keys
while its own `preset()` threaded neither built GREEN AND BYTE-IDENTICAL — Aurora measured
exactly that (their `docs/reviews/2026-09-04-boundary-moving-witness.md`), and it was
re-derived against the committed gate here before the fix: zero faults. `channel_faults`
closes it, and it derives the required set from `effects_gen.SECTION_CHANNELS` — the same
table `render_module` partitions its chooser tables with — rather than from a list of
four names, so the seventh key is required on the commit that starts emitting its rows.

--source-only — THE FAST LOOP'S ARM (2026-09-02, walkthrough finding b4).
Steps 1, 2 and 2b below read SOURCE ONLY: the generated module, the descriptor, the
effects library and the section sidecars. Step 3 is the one that needs the build's
listing. `FAST=1 ./build.sh` skips this whole gate along with the rest of the pytest
lane, so binding a raster preset to a section no preset threads the chooser for goes
GREEN in the loop the author is told to use and RED in the canonical build — 7
`tools/test_effects_seam_gate.py` failures found at landing time, after the work.
`--source-only` runs 1/2/2b before the build so that class fails in the loop, with the
same message. MEASURED 2026-09-02, this repo, 5 consecutive runs including interpreter
startup: 0.014 s each, against a FAST build of 2.07 s on the same box (16 cores, load
~6.8; the header's 1.3 s figure is a quieter box). Under 1% either way.

WHAT --source-only DOES NOT CHECK, stated so a green line is not over-read: step 3 —
the REACHABILITY evidence and the witness VALUES. It cannot: the equates it reads are
minted by the build it runs before. A `--source-only` pass says the binding seam is
spelled and wired correctly in the source; it does NOT say the module reached the ROM.
Only the canonical build answers that, and only that answer gates a landing.

USAGE:  python3 tools/effects_seam_gate.py [--lst s4.lst] [--source-only]
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import effects_gen  # noqa: E402

REPO = effects_gen.REPO
DESCRIPTOR = os.path.join("games", "sonic4", "data", "levels", "ojz", "act1",
                          "act_descriptor.emp")
# The RASTER chooser's call site is NOT the descriptor. A raster program is an
# `EffectsPreset` channel, not a `Sec` field, so the third generated `pub comptime fn`
# is threaded into the section's own `preset()` in the game's effects library.
EFFECTS_LIB = os.path.join("games", "sonic4", "data", "effects", "ojz_effects.emp")

# `EQU NAME = $0000001F` — the listing's equate table (sigil 0df77f83).
EQU_RE = re.compile(r"^EQU\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\$([0-9A-Fa-f]+)\s*$",
                    re.MULTILINE)
MODULE_RE = re.compile(r"^module\s+([a-z0-9_.]+)\s+in\s+([a-z0-9_]+)\s*$", re.MULTILINE)

# `pub data OJZ_Preset_Sec5: EffectsPreset = preset(` — the head of one preset record.
# The body is taken by paren balance, not by a regex, because the shipped records wrap
# across up to three lines and a line-anchored pattern would silently see half of one.
PRESET_HEAD_RE = re.compile(
    r"^pub\s+data\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*EffectsPreset\s*=\s*preset\s*\(",
    re.MULTILINE)


def preset_records(src: str) -> dict:
    """{preset name: the text between preset('s parens} for one effects library.

    Paren-balanced rather than line-based. Comments cannot contain an unbalanced
    paren in the shipped file and `.emp` has no paren-bearing string literals in a
    `preset()` argument list, so a balance scan is exact here; it is also the only
    reading that survives the three-line wrap the shipped records already use.
    """
    out = {}
    for m in PRESET_HEAD_RE.finditer(src):
        depth, i = 1, m.end()
        while i < len(src) and depth:
            if src[i] == "(":
                depth += 1
            elif src[i] == ")":
                depth -= 1
            i += 1
        out[m.group(1)] = src[m.end():i - 1]
    return out


def raster_call_sites(src: str, fn: str) -> dict:
    """{preset name: (sec index, whether a `hand:` argument was passed)}.

    Only presets whose `raster:` channel is a call to the generated chooser appear.
    A preset that hands `raster:` a literal program is not a fault — most of them do,
    and that is what an unbound section looks like.
    """
    call_re = re.compile(r"raster\s*:\s*" + re.escape(fn) +
                         r"\s*\(\s*sec\s*:\s*(\d+)\s*(,\s*hand\s*:)?")
    out = {}
    for name, body in preset_records(src).items():
        m = call_re.search(body)
        if m:
            out[name] = (int(m.group(1)), bool(m.group(2)))
    return out


def patched_call_sites(src: str, fn: str) -> dict:
    """{preset name: (sec index, whether a `hand:` argument was passed)}, `patched:` arm.

    THE MIRROR OF `raster_call_sites`, ONE `preset()` PARAMETER OVER. `boundary` documents
    lower into `EffectsPreset.ep_patched` through `patched_program()`, which is a DIFFERENT
    `preset()` parameter from `raster:` — so they are chosen by a DIFFERENT generated
    function (`names.fn_sec_patched`) and threaded at a different argument. A parse that
    lumped the two would report a patched binding as a raster one and vice versa, which is
    precisely the confusion this whole arm exists to end.

    `hand:` IS RECORDED AND NOT REQUIRED, and that asymmetry against the raster arm is
    deliberate rather than an omission. The raster arm demands `hand: Raster_Program_None`
    because a real "no raster program" label exists and 0 means "keep" (ARCH §7.12). There
    is NO `Patched_Program_None` in this tree — `patchable()` builds a patch table and there
    is no empty one — so a gate that demanded `hand:` here would demand a spelling nobody
    can write. What IS checked, below, is the case where omitting it does not assemble: a
    section the chooser has no arm for.
    """
    call_re = re.compile(r"patched\s*:\s*" + re.escape(fn) +
                         r"\s*\(\s*sec\s*:\s*(\d+)\s*(,\s*hand\s*:)?")
    out = {}
    for name, body in preset_records(src).items():
        m = call_re.search(body)
        if m:
            out[name] = (int(m.group(1)), bool(m.group(2)))
    return out


def document_arm(preset: dict) -> str:
    """Which `preset()` parameter one preset DOCUMENT's raster program lands in.

    THE ARM IS THE DOCUMENT'S OWN PROPERTY, read from the document, and this function is
    the gate's answer to "which of the two ARMS does this `rasterRef` owe". It is now
    literally `effects_gen`'s own function rather than a second spelling of the same
    predicate: `SECTION_CHANNELS` is the one table both the generator's chooser partition
    and this gate's requirement derive from, so they cannot disagree about a document.

    IT IS ONLY THE ARM. The same `rasterRef` binds every OTHER channel the document
    carries too (ruling Q1: one ref binds the whole document), and those are
    `document_channels` — see `channel_faults` for the hole that cost.
    """
    return effects_gen.document_arm(preset)


def channel_call_sites(src: str, fn: str, index_param: str) -> dict:
    """{preset name: {sec index: set of INDEX arguments}} for one chooser, matched BY NAME.

    THE NON-ARM CHANNELS' PARSE, and it is deliberately parameter-BLIND where
    `raster_call_sites` / `patched_call_sites` are parameter-AWARE. Those two exist to tell
    `raster:` from `patched:`, because ONE document lands in one of them and threading the
    wrong one is the silent failure the arm partition is for. The other four choosers have
    exactly one legal `preset()` parameter each AND a name of their own, so the name alone
    identifies the channel and a call anywhere in the record's body is the evidence.

    `index_param` is `"slot"` / `"ch"` / None, from `SECTION_CHANNELS` — a chooser that is
    not indexed records the sentinel index 0 so the callers can treat all six alike.
    """
    if index_param:
        pat = re.compile(re.escape(fn) + r"\s*\(\s*sec\s*:\s*(\d+)\s*,\s*"
                         + re.escape(index_param) + r"\s*:\s*(\d+)")
    else:
        pat = re.compile(re.escape(fn) + r"\s*\(\s*sec\s*:\s*(\d+)")
    out = {}
    for name, body in preset_records(src).items():
        for m in pat.finditer(body):
            sec = int(m.group(1))
            idx = int(m.group(2)) if index_param else 0
            out.setdefault(name, {}).setdefault(sec, set()).add(idx)
    return out


def prescription(ch, fn: str, sec: int) -> str:
    """The `preset()` argument to WRITE for one owed channel, spelled as it assembles.

    A GATE MUST NEVER PRESCRIBE A SPELLING NOBODY CAN WRITE — the failure
    docs/DEFERRED_WORK.md RASTER-BOUNDARY-2 is named for, and the reason two earlier
    parcels refused to add an arm at all. So every form below is COPIED from a record
    `games/sonic4/data/effects/ojz_effects.emp` already carries and this repo already
    assembles: `OJZ_Preset_Sec3` for `cycle:` and `variants:`, `OJZ_Preset_Sec5` for the
    two patch arrays.

    THE ARRAY LENGTH IS THE ENGINE'S, NOT THE DOCUMENT'S, and the difference is
    load-bearing. `preset()` ensures `variants.len == PAL_MAX_VARIANTS` and
    `patch_world_ys.len == patch_motion.len == RASTER_MAX_PATCH` AT THE CALL SITE, so a
    prescription trimmed to the indices the document authors would not build. What the
    document decides is which indices must be CHOSEN (`SectionChannel.indices`); the rest
    of the array is still spelled, and the chooser returns their `hand:` untouched.
    """
    if ch.index_param is None:
        return f"{ch.param}: {fn}(sec: {sec}, hand: {ch.hand})"
    arity = (effects_gen.PAL_MAX_VARIANTS if ch.index_param == "slot"
             else effects_gen.RASTER_MAX_PATCH)
    hand = (f", hand: {ch.hand}" if ch.hand else
            ", hand: <the literal that slot carries today; a slot whose literal is 0 "
            "omits `hand:` — 0 CLEARS here, it does not mean \"keep\">")
    args = ", ".join(f"{fn}(sec: {sec}, {ch.index_param}: {i}{hand})"
                     for i in range(arity))
    return f"{ch.param}: [{args}]"


def descriptor_effects_bindings(desc: str) -> dict:
    """{sec index: the preset name that section's `ojz_sec(...)` binds}.

    Sections that bind no `effects:` are absent rather than mapped to None — the
    field defaults to 0 = "no preset" and that is a legal state, not a fault here.
    """
    out = {}
    chunks = re.split(r"ojz_sec\s*\(\s*sec\s*:\s*(\d+)", desc)
    for i in range(1, len(chunks), 2):
        m = re.search(r"effects\s*:\s*([A-Za-z_][A-Za-z0-9_]*)", chunks[i + 1])
        if m:
            out[int(chunks[i])] = m.group(1)
    return out


def chooser_call_faults(calls: dict, bindings: dict, sections: int, fn: str,
                        channel: str) -> list:
    """The per-call-site invariants, shared by the `raster:` and `patched:` arms.

    THE INVARIANT, in one sentence: a preset whose channel is chosen BY SECTION INDEX must
    belong to exactly one section, and to that index. `Sec.sec_effects` is a per-section
    POINTER to a shared record (sections 6-8 share one today), so threading `<fn>(sec: N)`
    into a record two sections point at silently gives BOTH the band — the design's §3.3(b)
    hazard, which has no other symptom. That hazard is a property of SECTION-KEYED CHOOSING,
    not of the raster channel, so it applies identically to `patched:` and the check is
    factored rather than copied (a copied check is the one that drifts).

    `hand:` IS RASTER-ONLY, and the reason is in `patched_call_sites`' docstring: there is
    no `Patched_Program_None` to demand. The patched arm's own `hand:` case — a call site
    for a section the chooser has no arm for — is checked in `seam_faults` instead, where
    the arming is known.
    """
    faults = []
    seen = {}
    for name in sorted(calls):
        sec, has_hand = calls[name]
        if channel == "raster" and not has_hand:
            faults.append(
                f"{name} calls {fn}(sec: {sec}) with NO `hand:` argument. The "
                f"parameter defaults to 0, and 0 in ep_raster means \"keep\", not "
                f"\"off\" (ARCH §7.12) — an unbound section would inherit the previous "
                f"section's program instead of clearing it. Pass "
                f"`hand: Raster_Program_None`. A section that binds `patched:` is the "
                f"one exception, and it is NOT spelled `hand: 0`: that spelling does not "
                f"assemble (`expected a label (a `Label` argument), got int` — a bare 0 "
                f"is not a `Value::Label`, measured 2026-09-04). Such a section omits the "
                f"`raster:` argument ALTOGETHER, letting preset()'s own un-class-checked "
                f"`raster: Label = 0` default land the same 0 in ep_raster, and threads "
                f"only the patched chooser. See docs/DEFERRED_WORK.md RASTER-BOUNDARY-1.")
        if not 0 <= sec < sections:
            faults.append(
                f"{name} calls {fn}(sec: {sec}) but this act has {sections} sections "
                f"(0-{sections - 1}). The chooser's own `ensure` would catch it at "
                f"build time; it is caught here so the message names the preset.")
        if sec in seen:
            faults.append(
                f"{name} and {seen[sec]} both choose on sec {sec} in the {channel} "
                f"chooser. Two presets keyed on one section index means one of them can "
                f"never receive its band.")
        else:
            seen[sec] = name
        owners = sorted(i for i, p in bindings.items() if p == name)
        if not owners:
            faults.append(
                f"{name} threads the {channel} chooser but NO section binds it in "
                f"{DESCRIPTOR}. A preset nothing points at is a record the crossing "
                f"never installs.")
        elif owners != [sec]:
            faults.append(
                f"{name} chooses on sec {sec} but is bound by section(s) "
                f"{owners} in {DESCRIPTOR}. "
                + (f"A preset SHARED by {len(owners)} sections cannot carry a "
                   f"section-keyed band: every one of them would get sec {sec}'s "
                   f"program. Split it first (one 38-byte EffectsPreset per section "
                   f"that needs its own channel)."
                   if len(owners) > 1 else
                   f"The index and the binding disagree, so this section would "
                   f"receive another section's band."))
    return faults


def channel_faults(channel_calls: dict, bindings: dict, raster_refs: dict, presets: dict,
                   names) -> list:
    """The NON-ARM channels: every chooser a bound DOCUMENT owes is actually threaded.

    ---- THE HOLE THIS CLOSES (2026-09-04) ----

    Before this arm the gate checked SIX choosers at two different resolutions. The two
    arms (`raster:` / `patched:`) were checked PER SECTION — does the preset section N
    binds thread the chooser on index N. The other four (`cycle:`, `variants:`,
    `patch_world_ys:`, `patch_motion:`) were checked only ACT-WIDE, in step 2b: the
    effects library must IMPORT each one and must CALL it somewhere. `OJZ_Preset_Sec5`
    calls all four, so the act-wide half was satisfied by section 5 for every other
    section in the act.

    MEASURED CONSEQUENCE, which is Aurora's and not a hypothesis. Their
    `docs/reviews/2026-09-04-boundary-moving-witness.md` (lane-log `630def5c`): a section-6
    document carrying `boundary` + `patch_world_ys` + `patch_motion`, bound by
    `section_6.meta.json`'s `rasterRef`, whose `OJZ_Preset_Sec6` threaded the patched arm
    and neither patch chooser — "the first rebuild was green and byte-identical because
    the preset did not thread the choosers; import, patched:, patch_world_ys: and
    patch_motion: all needed, spelling copied from Sec5". Re-derived here against the
    committed gate before the fix: `seam_faults` returned ZERO faults for exactly that
    input. The author's only route to the four required threadings was copying
    `OJZ_Preset_Sec5` and noticing what it had.

    ---- WHY THE REQUIRED SET IS DERIVED AND NOT LISTED ----

    A gate that named the four channels would close this hole and reopen it at the fifth
    key — `boundary` itself was the fourth key added in a fortnight. The requirement is a
    FUNCTION of the document (`effects_gen.document_channels`), evaluated against
    `effects_gen.SECTION_CHANNELS`, which is the SAME table `render_module` partitions its
    chooser tables with. A key that starts emitting rows starts being required here on the
    same commit, with no edit to this file.

    ---- WHY THE INDICES AND NOT ONLY THE CHANNEL ----

    `render_module` emits one row per INDEX of the document's array (`enumerate`, `null`
    entries included — they lower to the engine sentinel). A `preset()` that threads
    `ch: 0` while the document authors four channels leaves three rows emitted and unread,
    which is the same silent-and-green shape one tier down. So the requirement is the
    index SET `SectionChannel.indices` returns, and a partial threading gets its own
    sentence rather than passing as "threaded".

    THIS ARM IS PURELY ADDITIVE ON A CORRECT TREE: it requires threadings, it never
    forbids one. A preset threading a chooser for a section no document binds is the
    ordinary `hand:` pass-through (`OJZ_Preset_Sec3` does exactly that today) and is not
    a fault here.
    """
    faults = []
    for sec in sorted(raster_refs):
        doc = presets.get(raster_refs[sec])
        if doc is None:
            continue            # already faulted, loudly, in the arm partition below
        owner = bindings.get(sec)
        where = (f"{owner}, the preset section {sec} binds in {DESCRIPTOR},"
                 if owner else
                 f"section {sec} binds NO `effects:` preset at all in {DESCRIPTOR}, so")
        for ch in effects_gen.document_channels(doc):
            if ch.channel in effects_gen.ARM_CHANNELS:
                continue        # the arms have their own three sentences below
            fn = getattr(names, ch.names_attr)
            want = set(ch.indices(doc) or {0})
            got = (channel_calls.get(ch.channel) or {}).get(owner, {}).get(sec, set())
            if not got:
                faults.append(
                    f"section {sec}'s sidecar names rasterRef {raster_refs[sec]!r}, whose "
                    f"document carries `{ch.key}` — so the generator emits {len(want)} "
                    f"{ch.channel} binding row(s) for sec {sec} into {fn}. But {where} "
                    f"threads {fn} for sec {sec} NOWHERE. One `rasterRef` binds the WHOLE "
                    f"document (ruling Q1), so every key it carries owes its own chooser "
                    f"at that section's `preset()` — a row nothing calls is a row nothing "
                    f"reads, which presents to the author as an assignment that did "
                    f"nothing, and this is what made the whole binding green and "
                    f"byte-identical (Aurora, 2026-09-04). Write, inside that `preset()`:"
                    f"\n      {prescription(ch, fn, sec)}")
            elif want - got:
                missing = sorted(want - got)
                faults.append(
                    f"section {sec}'s sidecar names rasterRef {raster_refs[sec]!r}, whose "
                    f"document authors {ch.channel} {ch.index_param}(s) "
                    f"{sorted(want)} — but {where} threads {fn} for sec {sec} only at "
                    f"{ch.index_param} {sorted(got)}. The generator emits a row per index "
                    f"the document's array reaches, so {ch.index_param} {missing} would be "
                    f"emitted and never read. Thread every index:"
                    f"\n      {prescription(ch, fn, sec)}")
    return faults


def seam_faults(raster_calls: dict, patched_calls: dict, channel_calls: dict,
                bindings: dict, sections: int, raster_refs: dict, presets: dict,
                names) -> list:
    """Every way the preset-binding seam can be wrong, as sentences. Empty == it holds.

    PURE, and separated from `main` for the same reason step 4's `unreachable_presets`
    was: the combinations that matter (a shared preset, a mismatched index, a duplicate
    index, a missing `hand:`, a document on the wrong arm) cannot all be produced by
    editing the real tree without breaking the build, so the arms have to be exercisable
    on synthetic inputs.

    ---- WHY THIS FUNCTION TOOK TWO CHOOSERS (2026-09-04, RASTER-BOUNDARY-2) ----

    It used to take one. `raster_refs` counts EVERY sidecar `rasterRef` — the correct and
    only key for binding a document to a section, ruling Q1 — but `chosen` came from the
    RASTER chooser alone, so a section whose document lowers into `ep_patched` could not
    satisfy this gate under ANY spelling: `raster:` with no arm is refused at type-check,
    `raster:` with a non-zero hand trips `preset()`'s `ep_raster == 0 || ep_patched == 0`
    ensure, and the buildable spelling (omit `raster:`, thread `patched:`) was INVISIBLE
    here and fired the last arm. Measured refusing a correct binding on 2026-09-04.

    The same blindness ran the other way: nothing in this tree required a `patched:` call
    site at all, so DROPPING one was silent-and-green — the identical hole the raster arm
    exists to close, one channel over.

    ---- WHAT WAS CHOSEN, AND WHAT WAS REJECTED ----

    The requirement is "a section carrying a `rasterRef` must be threaded". Three readings:

      (A) THREADED IN EITHER CHOOSER. Rejected: it greens the genuinely silent failure.
          A `boundary` document threaded through `raster: <fn>(sec: N, hand:
          Raster_Program_None)` BUILDS — the raster chooser has no arm for N, so it
          returns the hand label, `ep_raster` is set, `ep_patched` is 0, the exclusivity
          ensure passes — and the authored boundary is simply never installed. "Either
          arm" cannot see that, and it is the exact shape (`§3.3(b)`, and
          `effects_gen.render_module`'s own note: "a patched image threaded into `raster:`
          would install a padded body with no patch table") this seam is gated for.

      (B) THE SIDECAR DECLARES THE ARM (a `patchedRef` key, or an arm tag beside
          `rasterRef`). Rejected on three counts: it is a cross-repo schema change needing
          the hub and Aurora's serializer, so it cannot be built from here at all; it
          duplicates a fact the DOCUMENT already carries, giving one question two
          authorities that can disagree; and ruling Q1 is explicitly that ONE ref binds
          the whole document, which this would begin to unpick.

      (C) DERIVE THE ARM FROM THE DOCUMENT — `document_arm`, above. CHOSEN. It is the same
          predicate the generator already partitions its two chooser tables with, so the
          gate and the generator cannot disagree about which chooser a document owes; it
          needs no schema change and no other repo; and it is strictly stronger than (A),
          which it contains.

    ---- WHY THERE IS NO "NOTHING CALLS THE PATCHED CHOOSER" ARM ----

    The raster arm has one ("the chooser is generated for every act but nothing calls it").
    The patched arm deliberately does NOT, and this is a refusal rather than an oversight:
    a `patched:` call site for a section no `boundary` document arms does not assemble
    (`expected a label (a `Label` argument), got int` — the chooser returns its int default
    and `preset(patched:)` is class-checked), and this tree carries no `boundary` document.
    An arm demanding a spelling nobody can write is the failure RASTER-BOUNDARY-2 is about.
    So the patched arm is CONDITIONAL: it fires exactly when a document that needs it is
    bound. Until one is, it is vacuous and the gate's final line says so.

    ---- WHY IT NOW TAKES `names` AND `channel_calls` (2026-09-04, the no-chooser hole) ----

    The two chooser NAMES used to be passed as two strings, because the two arms were the
    only choosers this function knew about. There are six, `effects_gen.SECTION_CHANNELS`
    is the table that says which of them a document owes, and each entry names its own
    `ActNames` attribute — so the whole set arrives as one `names` object rather than as a
    growing argument list, and `channel_calls` carries the other four channels' call sites
    keyed by that same table's channel names. See `channel_faults` for what was green.
    """
    fn, fn_patched = names.fn_sec_raster, names.fn_sec_patched
    faults = []
    if not raster_calls:
        faults.append(
            f"no `preset()` in the effects library threads {fn} into its `raster:` — "
            f"the chooser is generated for every act but nothing calls it, so no "
            f"section can carry an editor-authored raster band and every raster "
            f"channel is hand-typed again. Bind one section's preset through it.")
    faults += chooser_call_faults(raster_calls, bindings, sections, fn, "raster")
    faults += chooser_call_faults(patched_calls, bindings, sections, fn_patched,
                                  "patched")

    for name in sorted(set(raster_calls) & set(patched_calls)):
        faults.append(
            f"{name} threads BOTH {fn} into `raster:` and {fn_patched} into "
            f"`patched:`. `preset()` asserts `ep_raster == 0 || ep_patched == 0` because "
            f"whichever installs LAST wins DESTRUCTIVELY (Raster_InstallPatched clears "
            f"Raster_Pending), so this record cannot build. A section binds ONE arm: the "
            f"one its document carries.")

    raster_chosen = {sec: name for name, (sec, _h) in raster_calls.items()}
    patched_chosen = {sec: name for name, (sec, _h) in patched_calls.items()}

    # ---- THE ARM PARTITION: each `rasterRef` owes the chooser its DOCUMENT names ----
    #
    # THREE SITUATIONS, THREE SENTENCES. "No preset threads this section" used to be one
    # message covering what are now three different states — threaded on raster, threaded
    # on patched, threaded on neither — and this repo treats a gate's stated REASON as
    # separately checkable from its verdict. The two wrong-arm directions do not even fail
    # the same way (one is silent-and-green, the other is build-fatal), so they get their
    # own sentences rather than a shared "wrong arm".
    for sec in sorted(raster_refs):
        pid = raster_refs[sec]
        doc = presets.get(pid)
        if doc is None:
            faults.append(
                f"section {sec}'s sidecar names rasterRef {pid!r}, but no preset "
                f"document with that id loaded. This gate cannot tell which chooser "
                f"that section owes without reading the document — it is the DOCUMENT "
                f"that decides the arm (`boundary` lowers into ep_patched, everything "
                f"else into ep_raster). Loud rather than assuming the raster arm.")
            continue
        arm = document_arm(doc)
        if arm == "patched":
            if sec in patched_chosen:
                continue
            if sec in raster_chosen:
                faults.append(
                    f"section {sec}'s sidecar names rasterRef {pid!r}, which carries "
                    f"`boundary` — so it lowers through patched_program() into "
                    f"EffectsPreset.ep_patched and the generator puts it in "
                    f"{fn_patched}'s table, NOT {fn}'s. But {raster_chosen[sec]} threads "
                    f"{fn}(sec: {sec}) instead. THAT COMBINATION BUILDS AND DOES "
                    f"NOTHING: the raster chooser has no arm for {sec}, so it returns "
                    f"the `hand:` program, ep_raster is set, the exclusivity ensure "
                    f"passes, and the authored boundary is never installed. Omit the "
                    f"`raster:` argument ALTOGETHER and thread "
                    f"`patched: {fn_patched}(sec: {sec})`.")
            else:
                faults.append(
                    f"section {sec}'s sidecar names rasterRef {pid!r}, which carries "
                    f"`boundary` — so it owes a PATCHED binding — but no preset threads "
                    f"{fn_patched}(sec: {sec}). Neither chooser reaches this section: "
                    f"the generator would emit the binding row and nothing would read "
                    f"it, which presents to the author as an assignment that did "
                    f"nothing. Omit `raster:` from that section's preset() and thread "
                    f"`patched: {fn_patched}(sec: {sec})`.")
        else:
            if sec in raster_chosen:
                continue
            if sec in patched_chosen:
                faults.append(
                    f"section {sec}'s sidecar names rasterRef {pid!r}, which carries no "
                    f"`boundary` key — so its program lowers into "
                    f"EffectsPreset.ep_raster and the generator puts it in {fn}'s table, "
                    f"NOT {fn_patched}'s. But {patched_chosen[sec]} threads "
                    f"{fn_patched}(sec: {sec}) instead. That does not assemble: the "
                    f"patched chooser has no arm for {sec}, so it returns its int "
                    f"default and `preset(patched:)` refuses it (`expected a label (a "
                    f"`Label` argument), got int`). Thread "
                    f"`raster: {fn}(sec: {sec}, hand: Raster_Program_None)`.")
            else:
                faults.append(
                    f"section {sec}'s sidecar names rasterRef {pid!r}, but no "
                    f"preset threads {fn}(sec: {sec}) — the generator would emit the "
                    f"binding row and nothing would read it, which presents to the author "
                    f"as an assignment that did nothing.")

    # ---- the patched arm's own `hand:` case, which needs the arming to be known ----
    for name in sorted(patched_calls):
        sec, has_hand = patched_calls[name]
        pid = raster_refs.get(sec)
        armed = pid is not None and document_arm(presets.get(pid, {})) == "patched"
        if not armed and not has_hand:
            faults.append(
                f"{name} calls {fn_patched}(sec: {sec}) with NO `hand:` argument, and no "
                f"sidecar binds a `boundary` document to section {sec} — so the chooser "
                f"has no arm for it and returns its int default, which "
                f"`preset(patched:)` refuses (`expected a label (a `Label` argument), "
                f"got int`, measured 2026-09-04). Either bind a `boundary` document to "
                f"section {sec}'s `rasterRef`, or pass a real hand-authored patched "
                f"program as `hand:` — there is no `Patched_Program_None` to pass.")

    # ---- the OTHER FOUR channels the same `rasterRef` binds; see `channel_faults` ----
    faults += channel_faults(channel_calls or {}, bindings, raster_refs, presets, names)
    return faults


def threaded_line(raster_calls: dict, patched_calls: dict) -> str:
    """The gate's OK line names the presets AND THE ARM, never counts them.

    "1 call site" would read the same whether it were section 5's or section 3's, and
    WHICH section owns a section-keyed chooser is the entire property being checked. The
    arm is now part of that: two presets can thread on the same index through different
    choosers, and a line that hid the arm would read identically for a correct patched
    binding and a silently-dead raster one.
    """
    parts = [f"raster {n}(sec: {raster_calls[n][0]})" for n in sorted(raster_calls)]
    parts += [f"patched {n}(sec: {patched_calls[n][0]})" for n in sorted(patched_calls)]
    return ", ".join(parts) if parts else "nothing threaded"


def fail(msg: str) -> None:
    print(f"effects_seam_gate: FAIL — {msg}")
    sys.exit(1)


def main() -> int:
    lst = "s4.lst"
    if "--lst" in sys.argv:
        lst = sys.argv[sys.argv.index("--lst") + 1]
    lst_path = lst if os.path.isabs(lst) else os.path.join(REPO, lst)
    source_only = "--source-only" in sys.argv

    names = effects_gen.act_names(REPO)

    # ---- 1. the generated module exists and declares the module id we expect ----
    gen_path = names.out_path(REPO)
    if not os.path.isfile(gen_path):
        fail(f"the generated binding module is missing: "
             f"{os.path.relpath(gen_path, REPO)}. It is emitted for EVERY act "
             f"whether or not editor content exists (owner ruling 2026-08-22) — run "
             f"`python3 tools/effects_gen.py emit`.")
    with open(gen_path, "r") as f:
        gen_src = f.read()
    m = MODULE_RE.search(gen_src)
    if not m or m.group(1) != names.module:
        fail(f"{os.path.relpath(gen_path, REPO)} declares module "
             f"{m.group(1) if m else '(none)'!r}, not {names.module!r} — the "
             f"descriptor's `use` line names the latter, so this gate would be "
             f"watching a module nothing imports.")

    # ---- 2. the descriptor's SEAM is spelled the way the ruling requires ----
    # A name list, never a glob; both bindings, unconditionally. This is a SOURCE
    # check and it is deliberately not the reachability evidence — step 3 is. It
    # exists so a seam that was rewritten into some other shape fails HERE with a
    # sentence about the ruling, instead of failing step 3 with "symbol absent".
    with open(os.path.join(REPO, DESCRIPTOR), "r") as f:
        desc = f.read()
    # Whitespace-tolerant on purpose (a reformat is not a seam change), strict on
    # the two things that ARE the seam: the form is a NAME LIST, never a glob, and
    # it names BOTH bindings.
    use_m = re.search(r"^\s*use\s+" + re.escape(names.module) + r"\s*\.\s*(\*|\{([^}]*)\})",
                      desc, re.MULTILINE)
    if not use_m:
        fail(f"{DESCRIPTOR} carries no `use {names.module}...` line at all. That "
             f"import IS the seam and IS the module's only `use`-closure edge — "
             f"without it every guard in the generated module is dead.")
    if use_m.group(1) == "*":
        fail(f"{DESCRIPTOR} imports {names.module} as a GLOB. The seam is a name "
             f"list, never a glob (wave-1 design §3, and docs/DEFERRED_WORK.md's "
             f"glob re-evaluation note).")
    imported = {n.strip() for n in use_m.group(2).split(",") if n.strip()}
    missing = {names.fn_act_default, names.fn_sec_scene} - imported
    if missing:
        fail(f"{DESCRIPTOR}'s seam import does not name {', '.join(sorted(missing))}. "
             f"BOTH bindings are imported unconditionally — the generator emits both "
             f"for every act (owner ruling 2026-08-22), so there is nothing to "
             f"condition on and nothing that legitimately disappears.")
    if f"{names.fn_act_default}(hand:" not in desc:
        fail(f"{DESCRIPTOR} imports {names.fn_act_default} but never calls it with "
             f"a `hand:` fallback — the act default would stop flowing through the "
             f"editor seam.")
    if f"{names.fn_sec_scene}(sec:" not in desc:
        fail(f"{DESCRIPTOR} imports {names.fn_sec_scene} but never calls it — no "
             f"section can carry an editor-authored scene.")
    # EVERY section index reaches the binding, exactly once. The descriptor funnels
    # the call through its own `ojz_sec` constructor, so what has to be checked is
    # the INDEX each call site passes: a duplicated or missing `sec:` would leave a
    # section permanently unbindable (or bound to another section's scene) with no
    # other symptom, since every index resolves to 0 = "act default" today. Derived
    # from project.json's grid, never typed.
    sections = effects_gen.act_section_count(REPO)
    passed = sorted(int(n) for n in re.findall(r"ojz_sec\(sec:\s*(\d+)", desc))
    if passed != list(range(sections)):
        fail(f"{DESCRIPTOR}'s section table passes sec indices {passed} to the "
             f"binding constructor, but project.json's grid declares {sections} "
             f"sections ({list(range(sections))}). A missing index is a section "
             f"that can never carry an editor scene; a duplicate is two sections "
             f"sharing one binding slot. Neither has any other symptom.")
    calls = len(passed)

    # ---- 2b. THE RASTER SEAM — a SECOND call site, in a different file ----
    #
    # The scene choosers are called from the descriptor; the raster chooser is called
    # from the game's effects library, because a raster program is an `EffectsPreset`
    # channel rather than a `Sec` field. Step 2 above cannot see it, and until this
    # block existed nothing in the tree did: dropping the `raster:` call and typing a
    # literal back in its place would have left every witness value unchanged and every
    # byte identical, because the chooser resolves to `hand` while no sidecar binds.
    # That is the same silent-and-green shape step 3's witnesses exist for, one tier
    # down.
    lib_path = os.path.join(REPO, EFFECTS_LIB)
    if not os.path.isfile(lib_path):
        fail(f"the effects library {EFFECTS_LIB} is missing — it is the raster "
             f"chooser's only call site.")
    with open(lib_path, "r") as f:
        lib = f.read()
    lib_use = re.search(r"^\s*use\s+" + re.escape(names.module) + r"\s*\.\s*(\*|\{([^}]*)\})",
                        lib, re.MULTILINE)
    if not lib_use:
        fail(f"{EFFECTS_LIB} carries no `use {names.module}...` line. The raster "
             f"chooser is generated for every act, but a preset can only thread one "
             f"it imports.")
    if lib_use.group(1) == "*":
        fail(f"{EFFECTS_LIB} imports {names.module} as a GLOB. Name list, never a "
             f"glob — same rule as the descriptor's seam.")
    lib_imported = {n.strip() for n in lib_use.group(2).split(",")}
    if names.fn_sec_raster not in lib_imported:
        fail(f"{EFFECTS_LIB}'s import of {names.module} does not name "
             f"{names.fn_sec_raster}. That function is the raster channel's whole "
             f"binding route.")
    # THE OTHER TWO PRESET CHANNELS (EFFECTS-W1 item 5), same silent-and-green shape.
    # `ep_cycle` and `ep_variants` are fields of the same record `ep_raster` is, and one
    # `rasterRef` binds the whole document (ruling Q1) — so if the library stops importing
    # or calling these two choosers, a document's `cycles` / `variants` become ROM nothing
    # installs, with no other symptom: the choosers resolve to `hand` today, so dropping
    # the call and typing the literal back leaves every byte identical. An UNCALLED
    # `pub comptime fn` is also an unelaborated one — every `ensure` inside it would be
    # asserting nothing (docs/EMP_PITFALLS.md §3, one tier down).
    # The patch channels (item 4) ride the same rule for the same reason: `ep_patch_world_ys`
    # and `ep_patch_motion` are fields of the same record, one `rasterRef` binds them, and an
    # unimported or uncalled chooser makes a document's anchor authoring ROM nothing reads —
    # with no other symptom, because both choosers resolve to `hand` on an unbound section.
    for fn, channel in ((names.fn_sec_cycle, "cycle"),
                        (names.fn_sec_variant, "variant"),
                        (names.fn_sec_patch_world_y, "patch world-Y"),
                        (names.fn_sec_patch_motion, "patch motion")):
        if fn not in lib_imported:
            fail(f"{EFFECTS_LIB}'s import of {names.module} does not name {fn}. That "
                 f"function is the palette {channel} channel's whole binding route, and "
                 f"an unimported chooser cannot be called — so every document's "
                 f"`{channel}s` would be ROM nothing installs.")
        if f"{fn}(sec:" not in lib:
            fail(f"{EFFECTS_LIB} imports {fn} but never calls it. The chooser is emitted "
                 f"for every act whether or not a document carries the key, so nothing "
                 f"legitimately stops calling it — and an uncalled `pub comptime fn` is "
                 f"never elaborated, which makes its own `ensure`s dead too.")
    raster_calls = raster_call_sites(lib, names.fn_sec_raster)
    patched_calls = patched_call_sites(lib, names.fn_sec_patched)
    # THE OTHER FOUR CHANNELS' CALL SITES, per preset and per index. Step 2b's loop above
    # only asks whether each chooser is imported and called SOMEWHERE in the act; this is
    # the per-section reading `channel_faults` needs, and the two are different questions
    # (`OJZ_Preset_Sec5` satisfied the act-wide one on behalf of every other section).
    # Walked from `SECTION_CHANNELS` so a seventh channel is collected without an edit here.
    channel_calls = {
        ch.channel: channel_call_sites(lib, getattr(names, ch.names_attr), ch.index_param)
        for ch in effects_gen.SECTION_CHANNELS
        if ch.channel not in effects_gen.ARM_CHANNELS}
    want_raster_refs = effects_gen.load_section_raster_refs(REPO)
    # THE DOCUMENTS, read HERE and not only in step 3, because which chooser a section owes
    # is a property of its DOCUMENT (`seam_faults`' design note (C)) and step 2b is the
    # `--source-only` half. Both are source reads, so this costs the fast loop nothing it
    # was not already paying in the canonical one.
    try:
        want_presets = effects_gen.load_all_presets("sonic4", REPO)
    except effects_gen.SceneShapeError as e:
        fail(f"a preset document does not load, so this gate cannot tell which chooser "
             f"each bound section owes — the arm is the document's own property: {e}")
    # THE PATCHED CHOOSER'S IMPORT, and it is the ONE conditional import check here while
    # the five above are unconditional. The others are unconditional because every section
    # can call them (they all take a real `hand:` fallback), so nothing legitimately stops
    # calling them. `fn_sec_patched` cannot be called at all until a `boundary` document
    # arms a section: the chooser would return its int default and `preset(patched:)`
    # refuses it. Demanding the import (and the call) unconditionally would be a gate arm
    # requiring a spelling nobody can write — the failure docs/DEFERRED_WORK.md
    # RASTER-BOUNDARY-2 exists to name. So it is required exactly when it is buildable.
    patched_needed = sorted(sec for sec, pid in want_raster_refs.items()
                            if document_arm(want_presets.get(pid, {})) == "patched")
    if (patched_needed or patched_calls) and names.fn_sec_patched not in lib_imported:
        fail(f"{EFFECTS_LIB}'s import of {names.module} does not name "
             f"{names.fn_sec_patched}, but "
             + (f"section(s) {patched_needed} bind a `boundary` document"
                if patched_needed else
                f"a preset already threads it")
             + f". A `boundary` document lowers into EffectsPreset.ep_patched through a "
               f"DIFFERENT `preset()` parameter from `raster:`, so it is chosen by "
               f"{names.fn_sec_patched} and an unimported chooser cannot be called — the "
               f"authored boundary would be ROM nothing installs.")
    faults = seam_faults(raster_calls,
                         patched_calls,
                         channel_calls,
                         descriptor_effects_bindings(desc),
                         sections,
                         want_raster_refs,
                         want_presets,
                         names)
    if faults:
        fail(f"the preset binding seam is broken in {EFFECTS_LIB}:\n  - "
             + "\n  - ".join(faults))

    # WHAT THE NON-ARM ARM ACTUALLY MEASURED, counted rather than assumed. A channel arm
    # that fires only when a bound document carries the key can be VACUOUS, and this repo's
    # rule is that a vacuous arm says so rather than reading green (the patched half's own
    # line below does exactly this). Derived from the documents, not from a nearby pin.
    owed = sorted((sec, c.channel)
                  for sec, pid in want_raster_refs.items()
                  for c in effects_gen.document_channels(want_presets.get(pid, {}))
                  if c.channel not in effects_gen.ARM_CHANNELS)
    owed_line = (", ".join(f"sec {s} {c}" for s, c in owed) if owed else
                 "NONE — the non-arm channel arm is VACUOUS in this tree and says so "
                 "rather than reading green")

    if source_only:
        # Say what was NOT measured, in the same breath as the pass. A gate that
        # reports only its green half is how a partial check gets read as the whole
        # one — and this half deliberately runs BEFORE the artifact exists.
        print(f"effects_seam_gate: OK (--source-only) — seam spelling + preset binding "
              f"in {EFFECTS_LIB} [{threaded_line(raster_calls, patched_calls)}]; "
              f"{calls} section call site(s), "
              f"{len(want_raster_refs)} sidecar rasterRef(s) "
              f"({len(patched_needed)} on the patched arm); "
              f"non-arm channel threadings required and found: {owed_line}.")
        print("  NOT CHECKED here: the reachability witnesses and their values (step 3) "
              "— they live in the build's listing, which does not exist yet. Only the "
              "canonical `./build.sh` answers that.")
        return 0

    # ---- 3. THE REACHABILITY EVIDENCE: the witnesses reached the artifact ----
    if not os.path.isfile(lst_path):
        fail(f"listing {lst} not found — this gate reads the build's own artifact "
             f"and cannot fall back to reasoning about the source.")
    with open(lst_path, "r", errors="replace") as f:
        equs = {n: int(v, 16) for n, v in EQU_RE.findall(f.read())}
    if not equs:
        # LOUD ON UNMEASURABLE. An empty parse means the listing format moved, not
        # that the seam is broken — and reporting "symbol absent" here would be a
        # gate failing for a reason it does not understand.
        fail(f"parsed ZERO `EQU` rows out of {lst} — the listing's equate-table "
             f"format has moved and this gate can no longer observe its subject. "
             f"Fix the parser (EQU_RE); do NOT read this as a broken seam.")

    scenes = effects_gen.load_all_scenes("sonic4", REPO)
    act_ref = effects_gen.load_act_scene_ref(REPO)
    sec_refs = effects_gen.load_section_scene_refs(REPO)
    # Derived from the editor inputs, not read from the generated module.
    want_bindings = len(sec_refs) + (1 if act_ref else 0)
    want_scenes = len(set(sec_refs.values()) | ({act_ref} if act_ref else set()))
    if act_ref and act_ref not in scenes:
        fail(f"project.json's act sceneRef {act_ref!r} names no scene in "
             f"{effects_gen.scene_dir()}")

    # THE RASTER BINDING WITNESS, third of three. Zero today and that is the state it
    # has to be able to express: an equate is minted whether or not any section binds a
    # raster program, so a value of 0 is positive evidence that the module was lowered
    # and carries no binding — which is a DIFFERENT observation from the symbol being
    # absent, and absence is what a dropped seam looks like. Derived from the sidecars
    # through the generator's own reader, never read out of the generated `.emp`.
    want_raster = len(want_raster_refs)

    # THE PALETTE WITNESSES (item 5), counted the same way and from the same sidecars:
    # one `rasterRef` binds the WHOLE document, so a section's cycle/variant binding is
    # its raster binding filtered by which keys that document carries. Both are 0 today
    # and that is a state they have to be able to express — a value of 0 says "the module
    # was lowered and binds nothing", which is a DIFFERENT observation from absence.
    # `want_presets` was loaded in step 2b — one read, one authority. It used to be loaded
    # here as well, which was fine while only this step needed it; a second `load_all_presets`
    # now would be a second chance for the two halves of one gate to disagree about the
    # documents they are checking.
    want_cycle = sum(1 for sec, pid in want_raster_refs.items()
                     if "cycles" in want_presets.get(pid, {}))
    want_variant = sum(1 for sec, pid in want_raster_refs.items()
                       if want_presets.get(pid, {}).get("variants") is not None)
    # THE PATCH WITNESS (item 4), counted the same way off the same sidecars. EITHER key
    # binds: a document may author only the world-Y seed (a boundary that sits somewhere new
    # but does not move) or, keeping the section's hand anchor, only the motion.
    want_patch = sum(1 for sec, pid in want_raster_refs.items()
                     if ("patch_world_ys" in want_presets.get(pid, {})
                         or "patch_motion" in want_presets.get(pid, {})))

    expected = {names.equ_scenes: want_scenes, names.equ_bindings: want_bindings,
                names.equ_raster_bindings: want_raster,
                names.equ_cycle_bindings: want_cycle,
                names.equ_variant_bindings: want_variant,
                names.equ_patch_bindings: want_patch}
    for sym, want in expected.items():
        if sym not in equs:
            fail(f"witness `{sym}` is ABSENT from {lst}. An equ is defined only if "
                 f"its module is LOWERED, so the generated binding module is "
                 f"OUTSIDE this target's `use` closure — act_descriptor.emp's seam "
                 f"import has been dropped or renamed. Every guard in that module "
                 f"is now dead: it builds green while asserting nothing "
                 f"(docs/EMP_PITFALLS.md §3).")
        if equs[sym] != want:
            fail(f"witness `{sym}` is {equs[sym]} in {lst}, but the editor inputs "
                 f"say {want} (scenes reached by an assignment: {want_scenes}; "
                 f"scene bindings: {want_bindings}; raster bindings: {want_raster}; "
                 f"cycle bindings: {want_cycle}; variant bindings: {want_variant}; "
                 f"patch bindings: {want_patch}). "
                 f"The built artifact does not carry "
                 f"what project.json + the section sidecars declare — re-bake with "
                 f"tools/regenerate-level.sh.")

    print(f"effects_seam_gate: OK — binding seam reached "
          f"({names.equ_scenes}={want_scenes}, {names.equ_bindings}={want_bindings}, "
          f"{names.equ_raster_bindings}={want_raster}, "
          f"{names.equ_cycle_bindings}={want_cycle}, "
          f"{names.equ_variant_bindings}={want_variant}, "
          f"{names.equ_patch_bindings}={want_patch}, "
          f"{calls} section call site(s), {len(equs)} equates parsed from {lst})")
    # The preset seam's own line — see `threaded_line` for why it names rather than counts.
    print(f"effects_seam_gate: OK — preset seam threaded in {EFFECTS_LIB} "
          f"[{threaded_line(raster_calls, patched_calls)}]; "
          f"{len(want_raster_refs)} sidecar rasterRef(s)"
          + (" — the sidecar arm is VACUOUS today and says so rather than reading green"
             if not want_raster_refs else
             f", {len(patched_needed)} of them on the patched arm"
             + (" — the PATCHED half of the arm partition is VACUOUS today (no bound "
                "document carries `boundary`) and says so rather than reading green"
                if not patched_needed else ""))
          + f"; non-arm channel threadings required and found: {owed_line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
