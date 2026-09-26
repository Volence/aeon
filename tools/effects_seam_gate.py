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
program is an `EffectsPreset` channel and not a region field. It needs its own check for
the reason above AND for one more: `Region.rg_effects` (Sec.sec_effects until painted-regions
v1) is a POINTER to a record several rows may share, so threading a SIDECAR-KEYED chooser into
a SHARED preset would silently give every one of those rows the same band. Step 2b checks that
a preset which chooses on sec N is named by exactly one region row, and that it is keyed on N.

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
    """{preset name: (the RECORD its `preset:` key names, whether `hand:` was passed)}.

    Only presets whose `raster:` channel is a call to the generated chooser appear.
    A preset that hands `raster:` a literal program is not a fault — most of them do,
    and that is what an unbound record looks like.

    ⚠ KEYED ON THE RECORD SINCE SHAPE B′ (aeon `3fc9ffa5`). The call is
    `<fn>(preset: <Record>_KEY, ...)` and what this returns is `<Record>`, so the
    invariant `chooser_call_faults` checks is SELF-KEYING: the record a call site names
    must be the record the call site is inside. The old section-keyed invariant ("this
    preset must belong to exactly one region row, and to that index") is GONE because the
    hazard it guarded is gone: two rows sharing a record now share its channels, which is
    what sharing a record means.
    """
    call_re = re.compile(r"raster\s*:\s*" + re.escape(fn) +
                         r"\s*\(\s*preset\s*:\s*(\w+)_KEY\s*(,\s*hand\s*:)?")
    out = {}
    for name, body in preset_records(src).items():
        m = call_re.search(body)
        if m:
            out[name] = (m.group(1), bool(m.group(2)))
    return out


def patched_call_sites(src: str, fn: str) -> dict:
    """{preset name: (the RECORD its `preset:` key names, whether `hand:`)}, `patched:` arm.

    THE MIRROR OF `raster_call_sites`, ONE `preset()` PARAMETER OVER. `boundary` documents
    lower into `EffectsPreset.ep_patched` through `patched_program()`, which is a DIFFERENT
    `preset()` parameter from `raster:` — so they are chosen by a DIFFERENT generated
    function (`names.fn_preset_patched`) and threaded at a different argument. A parse that
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
                         r"\s*\(\s*preset\s*:\s*(\w+)_KEY\s*(,\s*hand\s*:)?")
    out = {}
    for name, body in preset_records(src).items():
        m = call_re.search(body)
        if m:
            out[name] = (m.group(1), bool(m.group(2)))
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
    """{preset name: {RECORD keyed: set of INDEX arguments}} for one chooser, matched BY NAME.

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
        pat = re.compile(re.escape(fn) + r"\s*\(\s*preset\s*:\s*(\w+)_KEY\s*,\s*"
                         + re.escape(index_param) + r"\s*:\s*(\d+)")
    else:
        pat = re.compile(re.escape(fn) + r"\s*\(\s*preset\s*:\s*(\w+)_KEY")
    out = {}
    for name, body in preset_records(src).items():
        for m in pat.finditer(body):
            keyed = m.group(1)
            idx = int(m.group(2)) if index_param else 0
            out.setdefault(name, {}).setdefault(keyed, set()).add(idx)
    return out


def prescription(ch, fn: str, rec: str) -> str:
    """The `preset()` argument to WRITE for one owed channel, spelled as it assembles.

    A GATE MUST NEVER PRESCRIBE A SPELLING NOBODY CAN WRITE — the failure
    docs/DEFERRED_WORK.md RASTER-BOUNDARY-2 is named for, and the reason two earlier
    parcels refused to add an arm at all. So every form below is COPIED from a record
    `games/sonic4/data/effects/ojz_effects.emp` already carries and this repo already
    assembles: `OJZ_Preset_Sec3` for `cycle:` and `variants:`, `OJZ_Preset_Sec5` for the
    two patch arrays. Since shape B′ the key is the record's OWN `<Record>_KEY`, which is
    what `chooser_call_faults` requires — so a prescription is always self-keyed.

    THE ARRAY LENGTH IS THE ENGINE'S, NOT THE DOCUMENT'S, and the difference is
    load-bearing. `preset()` ensures `variants.len == PAL_MAX_VARIANTS` and
    `patch_world_ys.len == patch_motion.len == RASTER_MAX_PATCH` AT THE CALL SITE, so a
    prescription trimmed to the indices the document authors would not build. What the
    document decides is which indices must be CHOSEN (`SectionChannel.indices`); the rest
    of the array is still spelled, and the chooser returns their `hand:` untouched.
    """
    if ch.index_param is None:
        return f"{ch.param}: {fn}(preset: {rec}_KEY, hand: {ch.hand})"
    arity = (effects_gen.PAL_MAX_VARIANTS if ch.index_param == "slot"
             else effects_gen.RASTER_MAX_PATCH)
    hand = (f", hand: {ch.hand}" if ch.hand else
            ", hand: <the literal that slot carries today; a slot whose literal is 0 "
            "omits `hand:` — 0 CLEARS here, it does not mean \"keep\">")
    args = ", ".join(f"{fn}(preset: {rec}_KEY, {ch.index_param}: {i}{hand})"
                     for i in range(arity))
    return f"{ch.param}: [{args}]"


def descriptor_effects_bindings(desc: str) -> dict:
    """{sidecar index: the preset name the region row keyed on that sidecar names}.

    Since painted-regions v1 a section binds no preset; a REGION row does, and each row names
    its sidecar's scene binding as `parallax: <chooser>(sec: N)`. The section-keyed choosers
    this gate checks are keyed by that same sidecar index, so it is the right key: a row whose
    own call carries `effects: X` and exactly one numeric `sec: N` pairs N -> X. A row naming
    no numeric `sec:` (no sidecar-keyed binding) is absent rather than mapped to None, and so
    is a row naming two different indices. `//` comments are stripped first, so prose that
    quotes a row cannot become one.
    """
    code = re.sub(r"//[^\n]*", "", desc)
    out = {}
    for m in re.finditer(r"\bojz_region\s*\(", code):
        if re.search(r"\bfn\s+$", code[:m.start()]):
            continue                                  # the constructor's declaration
        depth, j = 0, m.end() - 1
        while j < len(code):
            depth += {"(": 1, ")": -1}.get(code[j], 0)
            if depth == 0:
                break
            j += 1
        body = code[m.end():j]
        em = re.search(r"\beffects\s*:\s*([A-Za-z_][A-Za-z0-9_]*)", body)
        secs = {int(s) for s in re.findall(r"\bsec\s*:\s*(\d+)", body)}
        if em and len(secs) == 1:
            out[secs.pop()] = em.group(1)
    return out


def chooser_call_faults(calls: dict, bindings: dict, records: set, fn: str,
                        channel: str) -> list:
    """The per-call-site invariants, shared by the `raster:` and `patched:` arms.

    ---- RE-AIMED 2026-09-16 BY SHAPE B′ (aeon `3fc9ffa5`), AND THE OLD INVARIANT IS GONE
    RATHER THAN RELAXED ----

    It read: *"a preset whose channel is chosen BY SECTION INDEX must belong to exactly one
    region row, and to that index"*, and it guarded the design's §3.3(b) hazard —
    `Region.rg_effects` is a POINTER to a possibly shared record, so threading
    `<fn>(sec: N)` into a record two rows point at silently gave BOTH of them section N's
    band. That hazard was a property of SECTION-KEYED CHOOSING and it no longer exists:
    the chooser keys on the RECORD, so two rows sharing a record share its channels, which
    is what sharing a record means and is how a non-rectangular area is drawn under the
    regions model. The tree paid 92 bytes to work around the old rule by hand
    (`OJZ_Preset_Sec5` and `OJZ_Preset_Sec6` exist only because of it); that is now a
    choice rather than a requirement.

    ---- THE INVARIANT THAT REPLACES IT: SELF-KEYING ----

    A record threads its OWN key. `OJZ_Preset_Sec5` must pass `OJZ_Preset_Sec5_KEY`. The
    fault it forbids is the same FAMILY as the old one — a record receiving another
    record's band, with no symptom but the wrong picture — and it is strictly cheaper to
    check: it is a property of one line, visible to its author, needing no descriptor and
    no section grid. A gate that needed the section grid to decide a question about a
    record was answering it at the wrong altitude, which is why the old one had three
    sentences and this has one.

    `hand:` IS RASTER-ONLY, and the reason is in `patched_call_sites`' docstring: there is
    no `Patched_Program_None` to demand. The patched arm's own `hand:` case — a call site
    for a record the chooser has no arm for — is checked in `seam_faults` instead, where
    the arming is known.
    """
    faults = []
    for name in sorted(calls):
        keyed, has_hand = calls[name]
        if channel == "raster" and not has_hand:
            faults.append(
                f"{name} calls {fn}(preset: {keyed}_KEY) with NO `hand:` argument. The "
                f"parameter defaults to 0, and 0 in ep_raster means \"keep\", not "
                f"\"off\" (ARCH §7.12) — an unbound record would inherit the previously "
                f"installed program instead of clearing it. Pass "
                f"`hand: Raster_Program_None`. A record that binds `patched:` is the "
                f"one exception, and it is NOT spelled `hand: 0`: that spelling does not "
                f"assemble (`expected a label (a `Label` argument), got int` — a bare 0 "
                f"is not a `Value::Label`, measured 2026-09-04). Such a record omits the "
                f"`raster:` argument ALTOGETHER, letting preset()'s own un-class-checked "
                f"`raster: Label = 0` default land the same 0 in ep_raster, and threads "
                f"only the patched chooser. See docs/DEFERRED_WORK.md RASTER-BOUNDARY-1.")
        if keyed != name:
            faults.append(
                f"{name} calls {fn}(preset: {keyed}_KEY) — it threads ANOTHER RECORD'S "
                f"key. Since shape B′ the choosers are keyed on the `EffectsPreset` "
                f"record, and a record must name itself: what comes back is the program "
                f"bound to {keyed!r}, so every region that installs {name} would show "
                f"{keyed!r}'s band. Write `preset: {name}_KEY`. (This is the successor to "
                f"the section-keyed 'chooses on sec N but is bound by section M' fault, "
                f"one altitude down: it is a property of this line alone.)")
        elif records and keyed not in records:
            faults.append(
                f"{name} calls {fn}(preset: {keyed}_KEY), and {keyed!r} is not an "
                f"`EffectsPreset` record this library declares. The generator mints one "
                f"`<Record>_KEY` per declared record, so this cannot assemble — it is "
                f"caught here so the message names the channel and the record rather "
                f"than an unknown identifier in a generated file.")
        owners = sorted(i for i, p in bindings.items() if p == name)
        if not owners:
            faults.append(
                f"{name} threads the {channel} chooser but NOTHING binds it in "
                f"{DESCRIPTOR}. A preset nothing points at is a record the crossing "
                f"never installs.")
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
    # WHO OWNS A REF, IN WORDS. The owner is a REGION ROW in region mode and a SECTION in
    # legacy; the messages below name it, and an author sent to "section ojz_preset_night's
    # sidecar" would go looking for a file that has nothing in it. Inferred from the keys
    # rather than passed in, because every caller already has the right map and a seventh
    # parameter threaded through four functions is a seventh thing to forget.
    _owner_noun = "region" if any(isinstance(k, str) for k in raster_refs) else "section"
    _ref_home = "row" if _owner_noun == "region" else "sidecar"
    for sec in sorted(raster_refs):
        doc = presets.get(raster_refs[sec])
        if doc is None:
            continue            # already faulted, loudly, in the arm partition below
        owner = bindings.get(sec)
        if owner is None:
            faults.append(
                f"{_owner_noun} {sec}'s {_ref_home} names rasterRef {raster_refs[sec]!r}, but "
                f"{DESCRIPTOR} says no `EffectsPreset` record installs that section. "
                f"Since shape B′ the choosers key on the RECORD, so there is no key to "
                f"thread and the document's channels have nowhere to land.")
            continue
        where = f"{owner}, the record section {sec} binds in {DESCRIPTOR},"
        for ch in effects_gen.document_channels(doc):
            if ch.channel in effects_gen.ARM_CHANNELS:
                continue        # the arms have their own three sentences below
            fn = getattr(names, ch.names_attr)
            want = set(ch.indices(doc) or {0})
            # SELF-KEYED: `chooser_call_faults` requires a record to thread its OWN key,
            # so the call map's inner key for `owner` is `owner`. Reading it that way
            # rather than accepting any key is what stops a record that threads SOMEONE
            # ELSE'S key from also satisfying this arm — the two faults would otherwise
            # cancel and the pair would read green.
            got = (channel_calls.get(ch.channel) or {}).get(owner, {}).get(owner, set())
            if not got:
                faults.append(
                    f"{_owner_noun} {sec}'s {_ref_home} names rasterRef {raster_refs[sec]!r}, whose "
                    f"document carries `{ch.key}` — so the generator emits {len(want)} "
                    f"{ch.channel} binding row(s) for {owner} into {fn}. But {where} "
                    f"threads {fn}(preset: {owner}_KEY) NOWHERE. One `rasterRef` binds the "
                    f"WHOLE document (ruling Q1), so every key it carries owes its own "
                    f"chooser at that record's `preset()` — a row nothing calls is a row "
                    f"nothing reads, which presents to the author as an assignment that "
                    f"did nothing, and this is what made the whole binding green and "
                    f"byte-identical (Aurora, 2026-09-04). Write, inside that `preset()`:"
                    f"\n      {prescription(ch, fn, owner)}")
            elif want - got:
                missing = sorted(want - got)
                faults.append(
                    f"{_owner_noun} {sec}'s {_ref_home} names rasterRef {raster_refs[sec]!r}, whose "
                    f"document authors {ch.channel} {ch.index_param}(s) "
                    f"{sorted(want)} — but {where} threads {fn}(preset: {owner}_KEY) only "
                    f"at {ch.index_param} {sorted(got)}. The generator emits a row per "
                    f"index the document's array reaches, so {ch.index_param} {missing} "
                    f"would be emitted and never read. Thread every index:"
                    f"\n      {prescription(ch, fn, owner)}")
    return faults


def seam_faults(raster_calls: dict, patched_calls: dict, channel_calls: dict,
                bindings: dict, lib_records: set, raster_refs: dict, presets: dict,
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
    fn, fn_patched = names.fn_preset_raster, names.fn_preset_patched
    faults = []
    if not raster_calls:
        faults.append(
            f"no `preset()` in the effects library threads {fn} into its `raster:` — "
            f"the chooser is generated for every act but nothing calls it, so no "
            f"section can carry an editor-authored raster band and every raster "
            f"channel is hand-typed again. Bind one section's preset through it.")
    faults += chooser_call_faults(raster_calls, bindings, lib_records, fn, "raster")
    faults += chooser_call_faults(patched_calls, bindings, lib_records, fn_patched,
                                  "patched")

    for name in sorted(set(raster_calls) & set(patched_calls)):
        faults.append(
            f"{name} threads BOTH {fn} into `raster:` and {fn_patched} into "
            f"`patched:`. `preset()` asserts `ep_raster == 0 || ep_patched == 0` because "
            f"whichever installs LAST wins DESTRUCTIVELY (Raster_InstallPatched clears "
            f"Raster_Pending), so this record cannot build. A section binds ONE arm: the "
            f"one its document carries.")

    # ⚠ KEYED ON THE RECORD SINCE B′: a call site's own record IS its key (self-keying
    # is `chooser_call_faults`' invariant), so "which records thread this arm" is simply
    # the call maps' key sets. The arm partition below asks that question of the record a
    # section BINDS (`bindings[sec]`), one hop further than the old `sec in chosen`.
    raster_chosen = set(raster_calls)
    patched_chosen = set(patched_calls)

    # ---- THE ARM PARTITION: each `rasterRef` owes the chooser its DOCUMENT names ----
    #
    # THREE SITUATIONS, THREE SENTENCES. "No preset threads this section" used to be one
    # message covering what are now three different states — threaded on raster, threaded
    # on patched, threaded on neither — and this repo treats a gate's stated REASON as
    # separately checkable from its verdict. The two wrong-arm directions do not even fail
    # the same way (one is silent-and-green, the other is build-fatal), so they get their
    # own sentences rather than a shared "wrong arm".
    _owner_noun = "region" if any(isinstance(k, str) for k in raster_refs) else "section"
    _ref_home = "row" if _owner_noun == "region" else "sidecar"
    for sec in sorted(raster_refs):
        pid = raster_refs[sec]
        doc = presets.get(pid)
        if doc is None:
            faults.append(
                f"{_owner_noun} {sec}'s {_ref_home} names rasterRef {pid!r}, but no preset "
                f"document with that id loaded. This gate cannot tell which chooser "
                f"that section owes without reading the document — it is the DOCUMENT "
                f"that decides the arm (`boundary` lowers into ep_patched, everything "
                f"else into ep_raster). Loud rather than assuming the raster arm.")
            continue
        rec = bindings.get(sec)
        if rec is None:
            faults.append(
                f"{_owner_noun} {sec}'s {_ref_home} names rasterRef {pid!r}, but nothing in "
                f"{DESCRIPTOR} says which `EffectsPreset` record that section installs. "
                f"Since shape B′ the chooser is keyed on the RECORD, so without one this "
                f"gate cannot name the `preset()` that owes the threading — and the "
                f"generator's own `_rekey_bound_to_record` refuses the same tree.")
            continue
        arm = document_arm(doc)
        if arm == "patched":
            if rec in patched_chosen:
                continue
            if rec in raster_chosen:
                faults.append(
                    f"{_owner_noun} {sec}'s {_ref_home} names rasterRef {pid!r}, which carries "
                    f"`boundary` — so it lowers through patched_program() into "
                    f"EffectsPreset.ep_patched and the generator puts it in "
                    f"{fn_patched}'s table, NOT {fn}'s. But {rec} threads "
                    f"{fn}(preset: {rec}_KEY) instead. THAT COMBINATION BUILDS AND DOES "
                    f"NOTHING: the raster chooser has no arm for {rec}, so it returns "
                    f"the `hand:` program, ep_raster is set, the exclusivity ensure "
                    f"passes, and the authored boundary is never installed. Omit the "
                    f"`raster:` argument ALTOGETHER and thread "
                    f"`patched: {fn_patched}(preset: {rec}_KEY)`.")
            else:
                faults.append(
                    f"{_owner_noun} {sec}'s {_ref_home} names rasterRef {pid!r}, which carries "
                    f"`boundary` — so it owes a PATCHED binding — but no preset threads "
                    f"{fn_patched}(preset: {rec}_KEY). Neither chooser reaches this section: "
                    f"the generator would emit the binding row and nothing would read "
                    f"it, which presents to the author as an assignment that did "
                    f"nothing. Omit `raster:` from that section's preset() and thread "
                    f"`patched: {fn_patched}(preset: {rec}_KEY)`.")
        else:
            if rec in raster_chosen:
                continue
            if rec in patched_chosen:
                faults.append(
                    f"{_owner_noun} {sec}'s {_ref_home} names rasterRef {pid!r}, which carries no "
                    f"`boundary` key — so its program lowers into "
                    f"EffectsPreset.ep_raster and the generator puts it in {fn}'s table, "
                    f"NOT {fn_patched}'s. But {rec} threads "
                    f"{fn_patched}(preset: {rec}_KEY) instead. That does not assemble: the "
                    f"patched chooser has no arm for {sec}, so it returns its int "
                    f"default and `preset(patched:)` refuses it (`expected a label (a "
                    f"`Label` argument), got int`). Thread "
                    f"`raster: {fn}(preset: {rec}_KEY, hand: Raster_Program_None)`.")
            else:
                faults.append(
                    f"{_owner_noun} {sec}'s {_ref_home} names rasterRef {pid!r}, but no "
                    f"preset threads {fn}(preset: {rec}_KEY) — the generator would emit the "
                    f"binding row and nothing would read it, which presents to the author "
                    f"as an assignment that did nothing.")

    # ---- the patched arm's own `hand:` case, which needs the arming to be known ----
    # ⚠ THIS LOOP WAS THE ONE PIECE OF THE B′ RE-KEY THAT WAS MISSED, and it is written up
    # rather than silently corrected because all three of its faults were of the family this
    # repo keeps finding. The re-key left `sec, has_hand = patched_calls[name]` reading a
    # RECORD NAME into a variable called `sec` and then looking it up in `raster_refs`, which
    # is keyed by SECTION INDEX:
    #   1. `armed` became unconditionally False, so EVERY `patched:` call site without
    #      `hand:` faulted — including a correctly armed one. That is precisely the
    #      RASTER-BOUNDARY-2 failure this arm exists to avoid: a gate refusing the one
    #      spelling an author can actually write.
    #   2. the message interpolated `{rec}`, a LEAKED loop variable from the arm partition
    #      above — `UnboundLocalError` when `raster_refs` is empty, and the LAST iteration's
    #      unrelated record when it is not.
    #   3. it said "section {sec}" while printing a record name.
    # Latent on the real tree only because `patched_call_sites` is empty here today
    # (OJZ_Preset_Sec0/Sec7 hand `patched:` a literal), so `--source-only` stayed green
    # throughout. Found by the agent re-keying this gate's tests, which had no way to be
    # green against it — the reason those tests exist on synthetic inputs at all.
    for name in sorted(patched_calls):
        keyed, has_hand = patched_calls[name]
        # ARMED IS A QUESTION ABOUT THE RECORD, since the chooser's arms are. A record is
        # armed when SOME owner binds a `boundary` document to it — read through the same
        # owner->record edge the generator re-keys with, never by assuming the record's name
        # encodes an index.
        armed = any(document_arm(presets.get(pid, {})) == "patched"
                    for sec, pid in raster_refs.items()
                    if bindings.get(sec) == keyed)
        if not armed and not has_hand:
            faults.append(
                f"{name} calls {fn_patched}(preset: {keyed}_KEY) with NO `hand:` argument, "
                f"and nothing binds a `boundary` document to the record {keyed!r} — so the "
                f"chooser has no arm for it and returns its int default, which "
                f"`preset(patched:)` refuses (`expected a label (a `Label` argument), "
                f"got int`, measured 2026-09-04). Either bind a `boundary` document through "
                f"a `rasterRef` on a place that installs {keyed!r}, or pass a real "
                f"hand-authored patched program as `hand:` — there is no "
                f"`Patched_Program_None` to pass.")

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
    parts = [f"raster {n}(preset: {raster_calls[n][0]}_KEY)" for n in sorted(raster_calls)]
    parts += [f"patched {n}(preset: {patched_calls[n][0]}_KEY)"
              for n in sorted(patched_calls)]
    return ", ".join(parts) if parts else "nothing threaded"


def fail(msg: str) -> None:
    print(f"effects_seam_gate: FAIL — {msg}")
    sys.exit(1)


def owner_maps(repo: str = None, desc: str = None) -> tuple:
    """`(raster_refs, owner_records, region_mode)` — WHO owns a `rasterRef` in this tree.

    ONE DERIVATION, TWO MODES, AND ONE PLACE TO GET IT WRONG. Legacy: the owner is a SECTION,
    its ref comes from `section_N.meta.json` and the record it installs from the descriptor's
    rows. Region: the owner is a REGION ROW and BOTH come from `regions.json`. Everything
    downstream only ever asks "who owns this ref" and "what record does that owner install",
    so the flip is invisible past this function — which is exactly why it is a function and
    not two lines inlined in `main()`: the real-tree tests need the same pair, and when they
    built it themselves they went silently empty the day act 1 flipped.
    """
    repo = REPO if repo is None else repo
    region_mode = effects_gen.has_act_regions(repo)
    if region_mode:
        rows = effects_gen.act_region_rows(repo)
        return ({r["id"]: r[effects_gen.ACT_RASTER_REF_KEY] for r in rows
                 if r.get(effects_gen.ACT_RASTER_REF_KEY) is not None},
                {r["id"]: r["preset"] for r in rows},
                True)
    if desc is None:
        with open(os.path.join(repo, DESCRIPTOR)) as f:
            desc = f.read()
    return (effects_gen.load_section_raster_refs(repo),
            descriptor_effects_bindings(desc),
            False)


def region_seam_faults(names, imported: set, code: str, fail) -> int:
    """REGION MODE's half of step 2, and the count of bindings it proved reachable.

    ---- WHAT THE SEAM IS IN THIS MODE ----

    In legacy mode the seam is a CALL: the descriptor threads every sidecar index through
    `<act>_sec_scene`, and step 2 counts the indices. In region mode there is no call — the
    generated region table carries each bound row's scene binding as a `rg_parallax` POINTER,
    which is the same edge one indirection shorter. So the three things to check are:

      1. the descriptor imports the generated region table, by NAME and never as a glob (the
         seam's standing rule) and actually spells the rows const. Without that import the
         generated module has no `use`-closure edge and every guard in it is DEAD
         (docs/EMP_PITFALLS.md §3) — the same failure the legacy arm's import check exists
         for, one file over;
      2. `<act>_sec_scene` is ABSENT from both the import and the generated module. Not
         merely unused: an emitted-but-uncalled `pub comptime fn` is an unelaborated one
         whose own bounds `ensure` asserts nothing, and a stale import of a symbol the
         generator no longer emits does not assemble. Checked in both directions so "the
         generator stopped emitting it" and "the descriptor stopped importing it" cannot pass
         for each other;
      3. every region the DOCUMENT gives a `sceneRef` reaches a `rg_parallax:` in the
         generated table, and nothing else does. This is the region-mode successor to
         `passed != list(range(sections))`: a missing binding is a region that can never carry
         an editor scene, an extra one is a row bound to a scene its document does not name,
         and neither has any other symptom. Derived from the document through the generator's
         own reader, never from the table's text alone — a table checked against itself would
         agree with itself.
    """
    rel = os.path.relpath(effects_gen.region_table_path(names, REPO), REPO)
    rows = effects_gen.act_region_rows(REPO)
    want = {r["id"] for r in rows if r.get(effects_gen.ACT_SCENE_REF_KEY) is not None}

    if names.fn_sec_scene in imported:
        fail(f"{DESCRIPTOR} imports {names.fn_sec_scene}, but this act is in REGION mode "
             f"and the generator does not emit that chooser: a region row carries its scene "
             f"binding as a `rg_parallax` pointer in {rel}, so there is no call site for it. "
             f"A stale import of a symbol the generator no longer emits does not assemble.")
    gen = effects_gen.generate(REPO)[1]
    if names.fn_sec_scene in gen:
        fail(f"the generated module still emits {names.fn_sec_scene} while this act is in "
             f"REGION mode. Nothing can call it — an uncalled `pub comptime fn` is never "
             f"elaborated, so its own bounds `ensure` asserts nothing.")

    use_r = re.search(r"^\s*use\s+games\.sonic4\." + re.escape(names.zone_id)
                      + r"_regions_" + re.escape(names.act_id)
                      + r"\s*\.\s*(\*|\{([^}]*)\})", code, re.MULTILINE | re.DOTALL)
    if not use_r:
        fail(f"{DESCRIPTOR} carries no `use games.sonic4.{names.zone_id}_regions_"
             f"{names.act_id}...` line, but this act is in REGION mode and its rows live in "
             f"{rel}. That import IS the seam here and IS that module's only `use`-closure "
             f"edge — without it every guard in the generated table is dead.")
    if use_r.group(1) == "*":
        fail(f"{DESCRIPTOR} imports the generated region table as a GLOB. Name list, never a "
             f"glob — the same rule the effects seam's own import follows.")
    table = f"{names.cap.upper()}_GENERATED_REGION_ROWS"
    if table not in {n.strip() for n in use_r.group(2).split(",")}:
        fail(f"{DESCRIPTOR} imports the generated region module but not `{table}`, which is "
             f"the rows themselves. Whatever else it takes from there, without the rows this "
             f"act's identity table is not the document's.")

    text = effects_gen.generate_region_table(REPO)[1]
    got = set(re.findall(r"rg_parallax:\s*(\w+),.*?//\s*row\s+\d+\s+—\s+(\S+)", text))
    bound_ids = {rid for sym, rid in got if sym != "0"}
    if bound_ids != want:
        fail(f"{rel} binds `rg_parallax` on region(s) {sorted(bound_ids)}, but "
             f"{os.path.relpath(effects_gen.regions_path(REPO), REPO)} gives a "
             f"`{effects_gen.ACT_SCENE_REF_KEY}` to {sorted(want)}. A region in the document "
             f"and not the table can never carry an editor scene; one in the table and not "
             f"the document is a row bound to a scene nobody named. Neither has any other "
             f"symptom.")
    return len(want)


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
    region_mode = effects_gen.has_act_regions(REPO)
    # BOTH BINDINGS ARE IMPORTED UNCONDITIONALLY — IN LEGACY MODE. The owner ruling
    # (2026-08-22) is that the generator emits both for every act, so nothing legitimately
    # disappears. In REGION mode the scene chooser genuinely does: each row carries its
    # binding as a `rg_parallax` POINTER in the generated region table, so the chooser has no
    # call site anywhere and `render_module` does not emit it (see its region note). This is
    # the one thing that arm can legitimately lose, and it is checked in BOTH directions
    # below rather than merely excused.
    want = ({names.fn_act_default} if region_mode
            else {names.fn_act_default, names.fn_sec_scene})
    missing = want - imported
    if missing:
        fail(f"{DESCRIPTOR}'s seam import does not name {', '.join(sorted(missing))}. "
             f"The generator emits it for every act, so there is nothing to condition on "
             f"and nothing that legitimately disappears.")
    # THE CALL CHECKS READ COMMENT-STRIPPED SOURCE (GATE-PREDICATE-VS-PROMISE, 2026-09-26).
    # They read the raw text until then, and act_descriptor.emp carries a COMMENT quoting
    # `ojz_act1_act_default(hand:)`, so the substring was always present: replacing the call
    # with the bare `ParallaxConfig_OJZ_Default` it wraps built, and this check stayed green
    # (measured, exit 0). The promise is about a CALL, and a comment is not one.
    code = re.sub(r"//[^\n]*", "", desc)
    if f"{names.fn_act_default}(hand:" not in code:
        fail(f"{DESCRIPTOR} imports {names.fn_act_default} but never calls it with "
             f"a `hand:` fallback — the act default would stop flowing through the "
             f"editor seam.")
    sections = effects_gen.act_section_count(REPO)
    if region_mode:
        calls = region_seam_faults(names, imported, code, fail)
    else:
        if f"{names.fn_sec_scene}(sec:" not in code:
            fail(f"{DESCRIPTOR} imports {names.fn_sec_scene} but never calls it — no "
                 f"section can carry an editor-authored scene.")
        # EVERY sidecar index reaches the binding, exactly once. Since painted-regions v1 the
        # descriptor calls the scene chooser from its REGION rows (`parallax: <fn>(sec: N)`),
        # so what has to be checked is the INDEX each of those call sites passes: a duplicated
        # or missing `sec:` would leave a section's sidecar permanently unbindable (or bound
        # to another row's scene) with no other symptom. Derived from project.json's grid,
        # never typed; counted over the CALL with a literal index in comment-stripped source,
        # so the chooser's declaration, a `sec: sec` pass-through and prose quoting a call
        # cannot count.
        passed = sorted(int(n) for n in
                        re.findall(re.escape(names.fn_sec_scene) + r"\(sec:\s*(\d+)", code))
        if passed != list(range(sections)):
            fail(f"{DESCRIPTOR}'s region rows pass sidecar indices {passed} to "
                 f"{names.fn_sec_scene}, but project.json's grid declares {sections} "
                 f"sections ({list(range(sections))}). A missing index is a section "
                 f"whose sidecar can never carry an editor scene; a duplicate is two rows "
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
    if names.fn_preset_raster not in lib_imported:
        fail(f"{EFFECTS_LIB}'s import of {names.module} does not name "
             f"{names.fn_preset_raster}. That function is the raster channel's whole "
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
    for fn, channel in ((names.fn_preset_cycle, "cycle"),
                        (names.fn_preset_variant, "variant"),
                        (names.fn_preset_patch_world_y, "patch world-Y"),
                        (names.fn_preset_patch_motion, "patch motion")):
        if fn not in lib_imported:
            fail(f"{EFFECTS_LIB}'s import of {names.module} does not name {fn}. That "
                 f"function is the palette {channel} channel's whole binding route, and "
                 f"an unimported chooser cannot be called — so every document's "
                 f"`{channel}s` would be ROM nothing installs.")
        if f"{fn}(preset:" not in re.sub(r"//[^\n]*", "", lib):   # a call, not a comment
            fail(f"{EFFECTS_LIB} imports {fn} but never calls it. The chooser is emitted "
                 f"for every act whether or not a document carries the key, so nothing "
                 f"legitimately stops calling it — and an uncalled `pub comptime fn` is "
                 f"never elaborated, which makes its own `ensure`s dead too.")
    raster_calls = raster_call_sites(lib, names.fn_preset_raster)
    patched_calls = patched_call_sites(lib, names.fn_preset_patched)
    # THE OTHER FOUR CHANNELS' CALL SITES, per preset and per index. Step 2b's loop above
    # only asks whether each chooser is imported and called SOMEWHERE in the act; this is
    # the per-section reading `channel_faults` needs, and the two are different questions
    # (`OJZ_Preset_Sec5` satisfied the act-wide one on behalf of every other section).
    # Walked from `SECTION_CHANNELS` so a seventh channel is collected without an edit here.
    channel_calls = {
        ch.channel: channel_call_sites(lib, getattr(names, ch.names_attr), ch.index_param)
        for ch in effects_gen.SECTION_CHANNELS
        if ch.channel not in effects_gen.ARM_CHANNELS}
    # THE OWNER OF A `rasterRef`, WHICHEVER MODE THIS ACT IS IN. Legacy: a section, read
    # from its sidecar, with the record it installs read from the descriptor. Region: a
    # region row, with both read from the document — one file, one authority, and no hop
    # through the section grid that region mode deleted (ARCH §4.2). Everything downstream
    # of these two maps is mode-blind because it only ever asks "who owns this ref" and
    # "what record does that owner install", and both questions survive the flip.
    want_raster_refs, owner_records, _rm = owner_maps(REPO, desc)
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
    # calling them. `fn_preset_patched` cannot be called at all until a `boundary` document
    # arms a section: the chooser would return its int default and `preset(patched:)`
    # refuses it. Demanding the import (and the call) unconditionally would be a gate arm
    # requiring a spelling nobody can write — the failure docs/DEFERRED_WORK.md
    # RASTER-BOUNDARY-2 exists to name. So it is required exactly when it is buildable.
    patched_needed = sorted(sec for sec, pid in want_raster_refs.items()
                            if document_arm(want_presets.get(pid, {})) == "patched")
    if (patched_needed or patched_calls) and names.fn_preset_patched not in lib_imported:
        fail(f"{EFFECTS_LIB}'s import of {names.module} does not name "
             f"{names.fn_preset_patched}, but "
             + (f"section(s) {patched_needed} bind a `boundary` document"
                if patched_needed else
                f"a preset already threads it")
             + f". A `boundary` document lowers into EffectsPreset.ep_patched through a "
               f"DIFFERENT `preset()` parameter from `raster:`, so it is chosen by "
               f"{names.fn_preset_patched} and an unimported chooser cannot be called — the "
               f"authored boundary would be ROM nothing installs.")
    faults = seam_faults(raster_calls,
                         patched_calls,
                         channel_calls,
                         owner_records,
                         effects_gen.effects_library_records(names, REPO),
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
    owed = sorted((str(sec), c.channel)
                  for sec, pid in want_raster_refs.items()
                  for c in effects_gen.document_channels(want_presets.get(pid, {}))
                  if c.channel not in effects_gen.ARM_CHANNELS)
    _noun = "region" if region_mode else "sec"
    owed_line = (", ".join(f"{_noun} {s} {c}" for s, c in owed) if owed else
                 "NONE — the non-arm channel arm is VACUOUS in this tree and says so "
                 "rather than reading green")

    if source_only:
        # Say what was NOT measured, in the same breath as the pass. A gate that
        # reports only its green half is how a partial check gets read as the whole
        # one — and this half deliberately runs BEFORE the artifact exists.
        print(f"effects_seam_gate: OK (--source-only) — seam spelling + preset binding "
              f"in {EFFECTS_LIB} [{threaded_line(raster_calls, patched_calls)}]; "
              f"{calls} {'region scene binding(s)' if region_mode else 'section call site(s)'}, "
              f"{len(want_raster_refs)} {'region' if region_mode else 'sidecar'} rasterRef(s) "
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
    # ⚠ THE SCENE HALF OWNS ITS REFS THE SAME WAY THE RASTER HALF DOES, AND FOR A WHILE IT DID
    # NOT. This read `load_section_scene_refs` alone. In region mode those sidecars are nulled
    # and the `sceneRef`s live on the region rows, so both expectations went to ZERO against a
    # module correctly emitting four — and the gate refused the committed tree with a message
    # telling its reader to re-bake, which could not have helped. Found by the agent re-keying
    # this gate's own tests, not by any lane; `--source-only` (the FAST path) never reaches
    # step 3, so the whole authoring loop stayed green on it.
    #
    # The other four witnesses were already mode-correct because they route through
    # `owner_maps` + `_rekey_bound_to_record`. This is the same routing, one channel over.
    sec_refs = ({r["id"]: r[effects_gen.ACT_SCENE_REF_KEY]
                 for r in effects_gen.act_region_rows(REPO)
                 if r.get(effects_gen.ACT_SCENE_REF_KEY) is not None} if region_mode
                else effects_gen.load_section_scene_refs(REPO))
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
    #
    # ⚠ COUNTED PER RECORD SINCE SHAPE B′ (aeon `3fc9ffa5`, 2026-09-16), AND THAT IS A
    # CHANGE OF MEANING, NOT A RE-SPELLING. `render_module` re-keys its binding map from the
    # sidecar to the `EffectsPreset` RECORD before it counts, so two sections that bind ONE
    # record to ONE document now emit ONE binding row and the witness reads 1, where the
    # section count would read 2. The two numbers are EQUAL on act 1 today (two sections,
    # two distinct records), so a gate that went on counting sidecars would have stayed green
    # here and gone red on the first act that shared a record — with a message telling its
    # author to re-bake, which would not have helped. Derived through the generator's OWN
    # re-key rather than re-implemented, so the two cannot disagree about what a binding is.
    # ⚠ `owner_records`, NOT `section_preset_symbols` — the owner is a REGION in region mode
    # and a SECTION in legacy, and `want_raster_refs` above is keyed the same way. Reaching
    # for the section map here would look right and hit on nothing in region mode, leaving
    # every witness expectation at zero against a module that emits two.
    want_rec = effects_gen._rekey_bound_to_record(
        want_raster_refs, owner_records, "region" if region_mode else "section",
        (os.path.relpath(effects_gen.regions_path(REPO), REPO) if region_mode
         else DESCRIPTOR))
    want_raster = len(want_rec)

    # THE PALETTE WITNESSES (item 5), counted the same way and from the same sidecars:
    # one `rasterRef` binds the WHOLE document, so a section's cycle/variant binding is
    # its raster binding filtered by which keys that document carries. Both are 0 today
    # and that is a state they have to be able to express — a value of 0 says "the module
    # was lowered and binds nothing", which is a DIFFERENT observation from absence.
    # `want_presets` was loaded in step 2b — one read, one authority. It used to be loaded
    # here as well, which was fine while only this step needed it; a second `load_all_presets`
    # now would be a second chance for the two halves of one gate to disagree about the
    # documents they are checking.
    want_cycle = sum(1 for rec, pid in want_rec.items()
                     if "cycles" in want_presets.get(pid, {}))
    want_variant = sum(1 for rec, pid in want_rec.items()
                       if want_presets.get(pid, {}).get("variants") is not None)
    # THE PATCH WITNESS (item 4), counted the same way off the same sidecars. EITHER key
    # binds: a document may author only the world-Y seed (a boundary that sits somewhere new
    # but does not move) or, keeping the section's hand anchor, only the motion.
    want_patch = sum(1 for rec, pid in want_rec.items()
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
          f"{calls} {'region scene binding(s)' if region_mode else 'section call site(s)'}, "
          f"{len(equs)} equates parsed from {lst})")
    # The preset seam's own line — see `threaded_line` for why it names rather than counts.
    print(f"effects_seam_gate: OK — preset seam threaded in {EFFECTS_LIB} "
          f"[{threaded_line(raster_calls, patched_calls)}]; "
          f"{len(want_raster_refs)} {'region' if region_mode else 'sidecar'} rasterRef(s)"
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
