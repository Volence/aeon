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


def raster_seam_faults(calls: dict, bindings: dict, sections: int,
                       raster_refs: dict, fn: str) -> list:
    """Every way the raster seam can be wrong, as sentences. Empty == the seam holds.

    PURE, and separated from `main` for the same reason step 4's `unreachable_presets`
    was: the combinations that matter (a shared preset, a mismatched index, a duplicate
    index, a missing `hand:`) cannot all be produced by editing the real tree without
    breaking the build, so the arms have to be exercisable on synthetic inputs.

    THE INVARIANT, in one sentence: a preset whose raster channel is chosen BY SECTION
    INDEX must belong to exactly one section, and to that index. `Sec.sec_effects` is a
    per-section POINTER to a shared record (sections 6-8 share one today), so threading
    `<fn>(sec: N)` into a record two sections point at silently gives BOTH the band —
    the design's §3.3(b) hazard, which has no other symptom.
    """
    faults = []
    if not calls:
        faults.append(
            f"no `preset()` in the effects library threads {fn} into its `raster:` — "
            f"the chooser is generated for every act but nothing calls it, so no "
            f"section can carry an editor-authored raster band and every raster "
            f"channel is hand-typed again. Bind one section's preset through it.")
    seen = {}
    for name in sorted(calls):
        sec, has_hand = calls[name]
        if not has_hand:
            faults.append(
                f"{name} calls {fn}(sec: {sec}) with NO `hand:` argument. The "
                f"parameter defaults to 0, and 0 in ep_raster means \"keep\", not "
                f"\"off\" (ARCH §7.12) — an unbound section would inherit the previous "
                f"section's program instead of clearing it. Pass "
                f"`hand: Raster_Program_None` (or `hand: 0` on a section that binds "
                f"`patched:`, where a non-zero hand fires preset()'s exclusivity ensure).")
        if not 0 <= sec < sections:
            faults.append(
                f"{name} calls {fn}(sec: {sec}) but this act has {sections} sections "
                f"(0-{sections - 1}). The chooser's own `ensure` would catch it at "
                f"build time; it is caught here so the message names the preset.")
        if sec in seen:
            faults.append(
                f"{name} and {seen[sec]} both choose on sec {sec}. Two presets keyed "
                f"on one section index means one of them can never receive its band.")
        else:
            seen[sec] = name
        owners = sorted(i for i, p in bindings.items() if p == name)
        if not owners:
            faults.append(
                f"{name} threads the chooser but NO section binds it in "
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
    chosen = {s for s, _ in calls.values()}
    for sec in sorted(raster_refs):
        if sec not in chosen:
            faults.append(
                f"section {sec}'s sidecar names rasterRef {raster_refs[sec]!r}, but no "
                f"preset threads {fn}(sec: {sec}) — the generator would emit the "
                f"binding row and nothing would read it, which presents to the author "
                f"as an assignment that did nothing.")
    return faults


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
    for fn, channel in ((names.fn_sec_cycle, "cycle"),
                        (names.fn_sec_variant, "variant")):
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
    want_raster_refs = effects_gen.load_section_raster_refs(REPO)
    faults = raster_seam_faults(raster_calls,
                                descriptor_effects_bindings(desc),
                                sections,
                                want_raster_refs,
                                names.fn_sec_raster)
    if faults:
        fail(f"the raster binding seam is broken in {EFFECTS_LIB}:\n  - "
             + "\n  - ".join(faults))

    if source_only:
        # Say what was NOT measured, in the same breath as the pass. A gate that
        # reports only its green half is how a partial check gets read as the whole
        # one — and this half deliberately runs BEFORE the artifact exists.
        threaded = ", ".join(f"{n}(sec: {raster_calls[n][0]})"
                             for n in sorted(raster_calls))
        print(f"effects_seam_gate: OK (--source-only) — seam spelling + raster binding "
              f"in {EFFECTS_LIB} [{threaded}]; {calls} section call site(s), "
              f"{len(want_raster_refs)} sidecar rasterRef(s).")
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
    try:
        want_presets = effects_gen.load_all_presets("sonic4", REPO)
    except effects_gen.SceneShapeError as e:
        fail(f"a preset document does not load, so this gate cannot derive the palette "
             f"witness counts: {e}")
    want_cycle = sum(1 for sec, pid in want_raster_refs.items()
                     if "cycles" in want_presets.get(pid, {}))
    want_variant = sum(1 for sec, pid in want_raster_refs.items()
                       if want_presets.get(pid, {}).get("variants") is not None)

    expected = {names.equ_scenes: want_scenes, names.equ_bindings: want_bindings,
                names.equ_raster_bindings: want_raster,
                names.equ_cycle_bindings: want_cycle,
                names.equ_variant_bindings: want_variant}
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
                 f"cycle bindings: {want_cycle}; variant bindings: {want_variant}). "
                 f"The built artifact does not carry "
                 f"what project.json + the section sidecars declare — re-bake with "
                 f"tools/regenerate-level.sh.")

    print(f"effects_seam_gate: OK — binding seam reached "
          f"({names.equ_scenes}={want_scenes}, {names.equ_bindings}={want_bindings}, "
          f"{names.equ_raster_bindings}={want_raster}, "
          f"{names.equ_cycle_bindings}={want_cycle}, "
          f"{names.equ_variant_bindings}={want_variant}, "
          f"{calls} section call site(s), {len(equs)} equates parsed from {lst})")
    # The raster seam's own line, and it names the presets rather than counting them:
    # "1 call site" would read the same whether it were section 5's or section 3's, and
    # WHICH section owns a section-keyed chooser is the entire property being checked.
    threaded = ", ".join(f"{n}(sec: {raster_calls[n][0]})" for n in sorted(raster_calls))
    print(f"effects_seam_gate: OK — raster seam threaded in {EFFECTS_LIB} "
          f"[{threaded}]; {len(want_raster_refs)} sidecar rasterRef(s)"
          + (" — the sidecar arm is VACUOUS today and says so rather than reading green"
             if not want_raster_refs else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
