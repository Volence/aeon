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
two `pub equ` witnesses. An equ mints a link-level symbol that reaches the build's
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

USAGE:  python3 tools/effects_seam_gate.py [--lst s4.lst]
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import effects_gen  # noqa: E402

REPO = effects_gen.REPO
DESCRIPTOR = os.path.join("games", "sonic4", "data", "levels", "ojz", "act1",
                          "act_descriptor.emp")

# `EQU NAME = $0000001F` — the listing's equate table (sigil 0df77f83).
EQU_RE = re.compile(r"^EQU\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\$([0-9A-Fa-f]+)\s*$",
                    re.MULTILINE)
MODULE_RE = re.compile(r"^module\s+([a-z0-9_.]+)\s+in\s+([a-z0-9_]+)\s*$", re.MULTILINE)


def fail(msg: str) -> None:
    print(f"effects_seam_gate: FAIL — {msg}")
    sys.exit(1)


def main() -> int:
    lst = "s4.lst"
    if "--lst" in sys.argv:
        lst = sys.argv[sys.argv.index("--lst") + 1]
    lst_path = lst if os.path.isabs(lst) else os.path.join(REPO, lst)

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

    expected = {names.equ_scenes: want_scenes, names.equ_bindings: want_bindings}
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
                 f"bindings: {want_bindings}). The built artifact does not carry "
                 f"what project.json + the section sidecars declare — re-bake with "
                 f"tools/regenerate-level.sh.")

    print(f"effects_seam_gate: OK — binding seam reached "
          f"({names.equ_scenes}={want_scenes}, {names.equ_bindings}={want_bindings}, "
          f"{calls} section call site(s), {len(equs)} equates parsed from {lst})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
