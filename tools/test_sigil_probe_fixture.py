#!/usr/bin/env python3
"""The aeon-side drift check on `games/sonic4/test/fixtures/sigil_objroutine_probe.emp`.

WHY THIS FILE EXISTS. That fixture is compiled by a PEER REPO — sigil's
`crates/sigil-cli/tests/tranche6_negative_probes.rs`, tests
`misspelled_objroutine_target_dangles_while_control_resolves` and
`reordered_falls_into_pair_fails_compile` (read at sigil revision `43bf606a`).
Nothing in THIS repo compiles it: it is in no `map.toml`, it reaches no ROM, and
`build.sh` never hands it to sigil. So without this file it is a fixture no runner
in our tree reads, and it can be edited into uselessness with every gate here still
green — which is precisely how its predecessor
`games/sonic4/objects/test_solid.emp` broke sigil's probes in the first place
(37 lines -> 715 as the spring grew inside it).

WHAT IT DOES NOT COVER, stated plainly because a guard that overstates itself is
worse than none:

  * IT DOES NOT COMPILE ANYTHING. It is a source-shape check. It cannot tell you
    the fixture still lowers, still links, or still fits the `test_solid` region.
    Only sigil's own probe run can say that.
  * IT CANNOT SEE SIGIL. The three permitted externs and the two routine names
    below are transcribed from sigil's test source at the revision cited, not
    derived from our tree — there is no in-tree oracle for a peer repo's
    expectations. If sigil renames them, this check goes on passing while their
    probe goes vacuous. That residual is the reason the fixture's header names
    the sigil file and test functions: a reader who changes one has the other's
    address.
  * IT SAYS NOTHING ABOUT `games/sonic4/objects/test_solid.emp`. Sigil's
    byte-identity port gates read that file deliberately and must keep doing so.

Everything else below IS derived from this tree: the Sst field set is parsed out
of `engine/objects/sst.emp`, and the routine/order/last-item rules are evaluated
with the same `str.find` rule sigil's reorder probe uses.

Runner: `build.sh`'s pre-build tool-suite lane (`python3 -m pytest tools/ -q
-m "not needs_build"`, build.sh:631) collects this file by the directory sweep.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "games/sonic4/test/fixtures/sigil_objroutine_probe.emp"
SST = ROOT / "engine/objects/sst.emp"

# ── Transcribed from sigil `43bf606a`, NOT derived (see the docstring) ──────────
# `crates/sigil-cli/tests/tranche6_negative_probes.rs`:
#   `as_truth_equs()`  -> the SST_* equs + `ObjCodeBase`
#   `solid_outcome()`  -> `as_label_at("Draw_Sprite", 0x2970)`
#                         `as_label_at("RefreshSpritePieceCount", 0x2A00)`
# Those, and nothing else, are the cross-seam names the standalone compile can
# resolve. A fourth reference dangles and turns the probe's CONTROL red, which
# reads as "sigil's guard broke" when only this fixture drifted.
PERMITTED_EXTERNS = {"ObjCodeBase", "Draw_Sprite", "RefreshSpritePieceCount"}

# The probe names these two by literal source search and by link symbol.
HEAD_ROUTINE = "TestSolid_Init"
TAIL_ROUTINE = "TestSolid_Main"
# The doctored spelling the probe synthesises. It must never be a real symbol
# here or the "misspelled target dangles" run would resolve and pass vacuously.
DOCTORED_SPELLING = "TestSolid_Innit"

# The probe places the emitted sections into a map region of this name.
SECTION = "test_solid"

# The ambient the probe supplies: engine/system/types.emp + engine/objects/sst.emp,
# prepended as items. Anything imported from outside those two modules is a
# dependency the standalone compile has no source for.
PERMITTED_USE_ROOTS = ("engine.objects.sst.", "engine.system.types.")

REGISTERS = {f"{k}{n}" for k in "ad" for n in range(8)} | {"sp", "pc", "ccr", "sr", "usp"}


def fixture_text() -> str:
    assert FIXTURE.is_file(), (
        f"{FIXTURE.relative_to(ROOT)} is GONE. It is sigil's probe fixture, not ours to "
        "delete — see its header, and sigil's tranche6_negative_probes.rs."
    )
    return FIXTURE.read_text()


def strip_comments(src: str) -> list[str]:
    """Code lines with `//` comments removed.

    Trailing-`//` stripping is safe in THIS file specifically: it contains no
    string literal and no `ensure` message, so no `//` can appear inside one.
    Do not lift this helper to a file that has either.
    """
    out = []
    for line in src.splitlines():
        code = line.split("//", 1)[0].rstrip()
        if code.strip():
            out.append(code)
    return out


def sst_field_names() -> set[str]:
    """Field names parsed out of `pub struct Sst` in engine/objects/sst.emp."""
    src = SST.read_text()
    start = src.find("pub struct Sst")
    assert start >= 0, f"no `pub struct Sst` in {SST.relative_to(ROOT)}"
    body_open = src.find("{", start)
    depth, i = 0, body_open
    while i < len(src):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    body = src[body_open + 1 : i]
    fields = set()
    for line in strip_comments(body):
        m = re.match(r"\s*([A-Za-z_]\w*)\s*:", line)
        if m:
            fields.add(m.group(1))
    assert len(fields) > 10, f"Sst field parse looks wrong: {sorted(fields)}"
    return fields


def split_procs(code: list[str]) -> dict[str, list[str]]:
    """{routine name: body lines} for each `pub proc` in the fixture."""
    procs, name, body = {}, None, []
    for line in code:
        m = re.match(r"pub\s+proc\s+([A-Za-z_]\w*)\b", line)
        if m:
            name, body = m.group(1), []
            continue
        if name is not None:
            if line.startswith("}"):
                procs[name] = body
                name, body = None, []
            else:
                body.append(line)
    assert name is None, "unterminated proc body in the fixture"
    return procs


# ── the checks ────────────────────────────────────────────────────────────────


def test_the_two_routines_exist_in_the_order_the_reorder_probe_requires():
    """Sigil's `reordered_falls_into_pair_fails_compile` locates both declarations
    with `str.find` on the literal `pub proc <name>` text and asserts Init < Main.
    Evaluated here by the same rule, including the comment trap: if either literal
    first appears inside a comment, sigil doctors the COMMENT and the probe stops
    testing anything."""
    src = fixture_text()
    head = src.find(f"pub proc {HEAD_ROUTINE}")
    tail = src.find(f"pub proc {TAIL_ROUTINE}")
    assert head >= 0, f"`pub proc {HEAD_ROUTINE}` is gone; sigil's probe unwraps on it"
    assert tail >= 0, f"`pub proc {TAIL_ROUTINE}` is gone; sigil's probe unwraps on it"
    assert head < tail, (
        f"{HEAD_ROUTINE} must be declared BEFORE {TAIL_ROUTINE} — sigil's reorder "
        f"probe asserts that source order before doctoring it (found {head} vs {tail})"
    )
    code = "\n".join(strip_comments(src))
    assert code.find(f"pub proc {HEAD_ROUTINE}") >= 0, (
        f"the first `pub proc {HEAD_ROUTINE}` in the file is inside a COMMENT — "
        "sigil's text search would doctor the comment and the probe would go vacuous"
    )
    assert f"falls_into {TAIL_ROUTINE}" in code, (
        f"the `falls_into {TAIL_ROUTINE}` contract is what the reorder probe expects "
        "the compiler to complain about; without it the doctored run fails silently"
    )


def test_the_tail_routine_is_the_last_item_in_the_file():
    """The reorder doctor takes `src[main_start..]` — everything from the tail
    routine's declaration to EOF — as ONE block and moves it above Init. Anything
    appended after it silently rides along, which is exactly how the live
    test_solid.emp stopped being a controlled input."""
    src = fixture_text()
    tail = src.find(f"pub proc {TAIL_ROUTINE}")
    after = src[tail + 1 :]
    stray = re.findall(r"^(?:pub\s+)?(?:proc|fn|comptime|struct|const|equ|data)\b.*",
                       "\n".join(strip_comments(after)), re.M)
    assert not stray, (
        f"item(s) declared AFTER {TAIL_ROUTINE}: {stray}. Sigil's reorder doctor "
        f"moves everything from {TAIL_ROUTINE} to EOF as one block, so a trailing "
        "item changes what the probe is testing. Put new code in a real game module."
    )


def test_the_doctored_spelling_is_never_a_real_symbol():
    """`misspelled_objroutine_target_dangles_while_control_resolves` requires the
    typo'd target to DANGLE. If this file ever defines it, the doctored run
    resolves and the probe passes without testing anything. Header prose may
    mention it; code may not."""
    code = "\n".join(strip_comments(fixture_text()))
    assert DOCTORED_SPELLING not in code, (
        f"`{DOCTORED_SPELLING}` appears in the fixture's CODE. That is the spelling "
        "sigil synthesises to prove a dangling target is loud; defining it makes the "
        "probe vacuous."
    )
    assert f"pub proc {HEAD_ROUTINE}" in code, (
        f"{HEAD_ROUTINE} must stay an exported proc — it is the probe's resolving CONTROL"
    )


def test_the_import_budget_is_the_two_ambient_modules():
    """The probe compiles this file with `engine/system/types.emp` and
    `engine/objects/sst.emp` prepended and NOTHING else — no include root, no
    import resolution. A `use` naming a third module is a source file the
    standalone compile cannot see."""
    uses = [ln.strip() for ln in strip_comments(fixture_text())
            if ln.strip().startswith("use ")]
    assert uses, "the fixture imports nothing at all — did the module body get deleted?"
    bad = [u for u in uses if not u[4:].startswith(PERMITTED_USE_ROOTS)]
    assert not bad, (
        f"import(s) outside sigil's standalone ambient: {bad}. The probe supplies only "
        f"{PERMITTED_USE_ROOTS}; anything else has no source at compile time and turns "
        "the probe's CONTROL red."
    )


def test_the_cross_seam_reference_budget_is_the_three_link_truths():
    """Every free symbol the code references must be one this file declares, an
    Sst field (derived from sst.emp), a register, or one of the three externs
    sigil's harness synthesises. A fourth dangles at link."""
    code = strip_comments(fixture_text())
    procs = split_procs(code)
    assert set(procs) == {HEAD_ROUTINE, TAIL_ROUTINE}, (
        f"the fixture declares {sorted(procs)}; sigil's probe is built around exactly "
        f"[{HEAD_ROUTINE}, {TAIL_ROUTINE}]"
    )
    fields = sst_field_names()
    local = set(procs)
    referenced: set[str] = set()
    unknown_fields: set[str] = set()
    for body in procs.values():
        for line in body:
            toks = re.findall(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[bwl])?", line)
            for tok in toks[1:]:  # toks[0] is the mnemonic
                base = tok.split(".")[0]
                if re.search(rf"\b{re.escape(base)}\s*\(", line):
                    if base not in fields:
                        unknown_fields.add(base)
                    continue
                if base in REGISTERS or base in local:
                    continue
                referenced.add(base)
    assert not unknown_fields, (
        f"field access(es) not on `Sst` as declared in {SST.relative_to(ROOT)}: "
        f"{sorted(unknown_fields)}. The probe's ambient is sst.emp; a field from any "
        "other struct has no definition there."
    )
    extra = referenced - PERMITTED_EXTERNS
    assert not extra, (
        f"cross-seam reference(s) sigil's harness supplies no truth for: {sorted(extra)}. "
        f"It synthesises exactly {sorted(PERMITTED_EXTERNS)}; anything else dangles at "
        "link and the probe's CONTROL — the run that must SUCCEED — goes red."
    )


def test_the_section_clause_is_the_region_the_probe_maps():
    """`link_with_truths` builds a map with a region literally named `test_solid`
    and sized from sigil's pins; `place_sections` errors if the emitted section
    does not match."""
    code = "\n".join(strip_comments(fixture_text()))
    m = re.search(r"^module\s+[\w.]+\s+in\s+([A-Za-z_]\w*)", code, re.M)
    assert m, "no `module ... in <section>` header in the fixture"
    assert m.group(1) == SECTION, (
        f"section clause is `{m.group(1)}`; sigil's probe maps a region named "
        f"`{SECTION}` and place_sections refuses anything else"
    )


def test_the_fixture_reaches_no_rom():
    """It is a peer's test input, not game code. If a map.toml ever names it, it
    starts moving ROM bytes and every byte-identity gate in both repos inherits
    a file whose whole contract is that it never changes."""
    named = []
    for toml in sorted(ROOT.glob("games/*/map.toml")):
        if "sigil_objroutine_probe" in toml.read_text():
            named.append(toml.relative_to(ROOT).as_posix())
    assert not named, (
        f"{named} names the sigil probe fixture. It must stay out of every map.toml — "
        "it is compiled only by sigil's standalone probe."
    )
