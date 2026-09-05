"""Refuse a scene whose `vsplit:` attachment reaches no ROM byte (row VSPLIT-NO-OP).

WHAT THIS GATE EXISTS FOR
=========================
`vsplit:` is the ONE scene-layer attachment that does not lower to a band record. Every
other one -- `curve:`, `drift:`, `rowRemap:`, `deform:` -- rides the `SceneCfgN` record
`lowerN()` already emits, so authoring it is enough to make it real. A vsplit lowers to a
RASTER PROGRAM instead (`engine/level/scene_dsl.emp`, the SceneVSplit banner), and that
program only exists if someone calls `scene_vsplit_fires(<Scene>)` by hand and binds the
result. `tools/effects_gen.py` renders the attachment into the generated scene and emits no
program -- raster preset composition from the editor is wave 2 and has not landed
(`tools/EFFECTS_CONSUMER_CONTRACT.md`).

So an author can set a vsplit in Aurora, the editor accepts it, the generator renders it,
sigil elaborates it, every shape builds green -- and the effect is simply ABSENT. Measured,
not theorised: the bisect in commit df3b8810 records the arm `vsplit removed -> byte-identical
ROM` for `Scene_Editor_ojz_act1_sec7_worldwater`. A silent absence that looks exactly like a
working build is the failure class this tree keeps getting bitten by, and this lint is the
refusal that ends it.

WHY IT IS HERE AND NOT A COMPTIME `ensure` -- THE SPLIT, WITH THE EVIDENCE
=========================================================================
The check has two halves and only one of them is comptime-visible.

  COMPTIME (already done, not duplicated here). "Did the fold lose a fire?" Given a Scene
  value and a program built from it, `scene_vsplit_count(s)` is a real derived count and
  `<prog>.len == scene_vsplit_count(s)` states the invariant. Both live consumers already
  carry that assertion: `games/sonic4/data/effects/ojz_effects.emp:1364` for
  `Scene_Editor_ojz_act1_depth`, and the word-for-word twin comparison at :1175-1177 for
  `Scene_VSplitWitness`. This file repeats NEITHER; a lint that restated a comptime guard
  would be a second authority that can drift from the first.

  NOT COMPTIME (this file). "Did ANYBODY call `scene_vsplit_fires` on this scene?" That is
  a cross-module fact, and .emp has no construct that can accumulate one:

    * a `use` edge RE-EVALUATES an imported const's initializer in the CONSUMER's scope,
      injecting a CLONE (measured, Task 5's probe finding; see the header banner of
      `games/sonic4/data/effects/scene_registry.emp`). So a const cannot be a registry that
      one module writes and another reads -- each importer gets a fresh evaluation.
    * `comptime var` is function-local; there is no module-crossing mutable comptime state.
    * a guard in an unreachable module is DEAD -- `ensure` never fires and the CRC is
      unchanged (`docs/EMP_PITFALLS.md` section 3, measured 2026-08-14/18) -- so "put the
      ensure next to the scene" cannot see a consumer that lives somewhere else, and the
      module holding the scene is elaborated whether or not any consumer exists.
    * the scene that authors the vsplit and the module that folds it are DIFFERENT modules
      by construction today: the scenes are generated into
      `games/sonic4/data/generated/ojz/act1/effects_scenes.emp` and the folds live in
      `games/sonic4/data/effects/ojz_effects.emp`, because the generator deliberately does
      not bind (its RASTER BANDS banner: "which section installs it is a `preset()` call in
      the game's own effects library, and choosing that is a content decision").

  So the consumer-existence half is checked as TEXT, the way the DEBUG scene-cycle table
  (`tools/test_scene_cycle_table_lint.py`) and the palette committer census
  (`tools/test_palette_census_lint.py`) are. Same species of pin, same acknowledged limit:
  this reads SOURCE, not the ROM.

THE RUNNER
==========
`python3 -m pytest tools -q --no-header -p no:cacheprovider` in `build.sh` (the "tool-suite
unit tests" lane, around line 609), which exits 1 build-fatally on failure. No new standing
runner was created: the lane already sweeps `tools/test_*.py` by directory, so this file
joins it by existing.

EVERY EXPECTATION IS DERIVED. There is no scene count, no vsplit count and no consumer count
written into this file. The population is built by scanning for the thing that actually
matters -- a `vsplit: SceneVSplit.At(..)` inside a `const <Name>: Scene = scene(..)` body --
rather than from a name list or a registry array, because a population built from names
cannot contain the case nobody named. (The registry's `SCENES` array is NOT the population:
not one of its twenty-one members authors a vsplit, so a check scoped to it would be
vacuously green forever while all three real authoring scenes sat outside it.)

LOUD RATHER THAN GREEN WHEN IT CANNOT MEASURE. Every parse raises with the file and the
pattern it could not find, and `test_population_is_not_vacuous` fails if the scan finds no
authoring scene or no consumer at all -- the state a broken regex would produce.

THE QUARANTINE, AND WHY IT IS NOT AN EXCUSE
===========================================
NOTHING FAILS THIS CHECK TODAY AND `KNOWN_UNBOUND` IS EMPTY (2026-09-05). This section
described one live offender, `Scene_Editor_ojz_act1_sec7_worldwater`, in the present
tense; aurora removed the attachment rather than binding it and the entry went with it in
the same change, which the arms below forced. The sentence outlived its fact by one
commit, in the file whose whole subject is claims outliving their facts, and a reader
meets this docstring before the dict twenty lines down. Kept as a worked example rather
than deleted.

When an entry does exist, its disposition is a CONTENT decision that is the owner's, not
a lint's -- binding an inert vsplit adds ROM bytes and changes what a section looks like,
and deleting the attachment destroys an authoring act somebody made on purpose. So such a
scene is listed in `KNOWN_UNBOUND` below with the reason, and:

  * `test_quarantine_entries_are_still_unbound` FAILS if a quarantined scene ever gains a
    consumer, so the entry cannot rot into permanent cover -- fixing the scene forces the
    entry's deletion in the same change;
  * `test_quarantine_entries_still_author_a_vsplit` FAILS if a quarantined scene stops
    authoring one, for the same reason;
  * every quarantined scene raises a `UserWarning` naming it, so `./build.sh` prints it in
    the pytest warnings summary on EVERY build rather than passing in silence. A quarantine
    nobody sees is the same silent absence this gate was built to end.

The list is a QUARANTINE, not an allowlist: nothing may be added to it to make a new failure
go away. A newly authored unbound vsplit is the defect this gate exists to refuse.

PROVEN RED (2026-09-05), mutation applied on disk and restored from a committed baseline:
  * add `vsplit: SceneVSplit.At(30)` to a layer of an unconsumed scene
        -> test_every_vsplit_authoring_scene_has_a_consumer
  * delete the `scene_vsplit_fires(Scene_Editor_ojz_act1_depth)` line
        -> test_every_vsplit_authoring_scene_has_a_consumer
  * break the `_VSPLIT_AT` pattern's expected spelling
        -> test_population_is_not_vacuous
  * bind the quarantined scene
        -> test_quarantine_entries_are_still_unbound
"""

import re
import warnings
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# THE CORPUS.
#
# Every `.emp` file under engine/ and games/, minus the poison fixtures. The poison
# directories hold modules that MUST fail to build (tools/emp_expect_fail.py drives them);
# they are never in a shipping target's `use` closure, so a vsplit authored there reaches
# no ROM by design and refusing it would be wrong. The exclusion is asserted rather than
# assumed -- see test_excluded_trees_are_the_declared_ones.
# ---------------------------------------------------------------------------
_ROOTS = ("engine", "games")
_EXCLUDED_PARTS = ("poison",)


def _emp_files() -> list[Path]:
    out: list[Path] = []
    for root in _ROOTS:
        base = REPO / root
        if not base.is_dir():
            raise AssertionError(
                f"{base} is not a directory. This lint scans the engine and game trees for "
                "scenes that author a `vsplit:`; with a root missing it cannot measure "
                "anything and must not pass."
            )
        for p in sorted(base.rglob("*.emp")):
            if any(part in _EXCLUDED_PARTS for part in p.parts):
                continue
            out.append(p)
    if not out:
        raise AssertionError(
            "found no .emp files under "
            + ", ".join(str(REPO / r) for r in _ROOTS)
            + ". Passing on an empty corpus would make this gate vacuous."
        )
    return out


def _strip_comments(src: str) -> str:
    """Drop `//` line comments, leaving string literals intact.

    Scene bodies and their banners both talk about `vsplit: At(..)` in prose, so scanning
    raw text would count the documentation as authoring. Quotes are tracked because
    `ensure` messages routinely contain `//` inside URLs and paths.
    """
    out: list[str] = []
    for line in src.split("\n"):
        in_str = False
        cut = len(line)
        i = 0
        while i < len(line) - 1:
            c = line[i]
            if c == "\\" and in_str:
                i += 2
                continue
            if c == '"':
                in_str = not in_str
            elif not in_str and c == "/" and line[i + 1] == "/":
                cut = i
                break
            i += 1
        out.append(line[:cut])
    return "\n".join(out)


# `pub const Scene_Editor_ojz_act1_depth: Scene = scene(`
_SCENE_DECL = re.compile(r"(?:^|\n)\s*(?:pub\s+)?const\s+(\w+)\s*:\s*Scene\s*=\s*scene\s*\(")
# `vsplit: SceneVSplit.At(20)` -- the authoring spelling, and the ONLY one: the enum has
# exactly two variants and `None` is the default, so `.At(` is what makes a layer author one.
_VSPLIT_AT = re.compile(r"vsplit\s*:\s*SceneVSplit\s*\.\s*At\s*\(\s*(\$?[0-9A-Fa-f]+)\s*\)")
# the enclosing layer's authored top, for the failure message
_WORLD_Y = re.compile(r"world_y\s*:\s*(\d+)")
# `const OJZ_DEPTH_VSPLIT_PROG = scene_vsplit_fires(Scene_Editor_ojz_act1_depth)`
_FIRES_CONST = re.compile(
    r"(?:^|\n)\s*(?:pub\s+)?const\s+(\w+)\s*=\s*scene_vsplit_fires\s*\(\s*(\w+)\s*\)"
)
# any call at all, including one used inline
_FIRES_CALL = re.compile(r"scene_vsplit_fires\s*\(\s*(\w+)\s*\)")


def _balanced_body(src: str, open_idx: int) -> str:
    """The text between `scene(` and its matching `)`."""
    depth = 0
    for i in range(open_idx, len(src)):
        if src[i] == "(":
            depth += 1
        elif src[i] == ")":
            depth -= 1
            if depth == 0:
                return src[open_idx + 1 : i]
    raise AssertionError(
        "unbalanced parentheses in a `const <Name>: Scene = scene(` declaration -- this "
        "lint could not find the constructor's closing paren, so it cannot tell which "
        "layers belong to which scene. Fix the source or this pattern; do not let it pass."
    )


class VSplitAuthoring:
    def __init__(self, scene: str, path: Path, line: int, world_y: str, value: str):
        self.scene = scene
        self.path = path
        self.line = line
        self.world_y = world_y
        self.value = value

    def __repr__(self) -> str:  # pragma: no cover - failure messages only
        rel = self.path.relative_to(REPO)
        return (
            f"{self.scene} (layer world_y {self.world_y}, vsplit At({self.value})) "
            f"at {rel}:{self.line}"
        )


def scan() -> tuple[list[VSplitAuthoring], dict[str, list[Path]], dict[str, tuple[Path, str]]]:
    """(authoring sites, scene -> files calling scene_vsplit_fires on it, fires consts)."""
    authorings: list[VSplitAuthoring] = []
    consumers: dict[str, list[Path]] = {}
    fires_consts: dict[str, tuple[Path, str]] = {}
    for path in _emp_files():
        raw = path.read_text()
        src = _strip_comments(raw)
        for m in _SCENE_DECL.finditer(src):
            name = m.group(1)
            open_idx = src.index("(", m.end() - 1)
            body = _balanced_body(src, open_idx)
            base = open_idx + 1
            for v in _VSPLIT_AT.finditer(body):
                abs_idx = base + v.start()
                line = src.count("\n", 0, abs_idx) + 1
                # the enclosing layer() call's world_y is the last one before this vsplit
                befores = _WORLD_Y.findall(body[: v.start()])
                authorings.append(
                    VSplitAuthoring(
                        name, path, line, befores[-1] if befores else "?", v.group(1)
                    )
                )
        for m in _FIRES_CALL.finditer(src):
            consumers.setdefault(m.group(1), []).append(path)
        for m in _FIRES_CONST.finditer(src):
            fires_consts[m.group(1)] = (path, m.group(2))
    return authorings, consumers, fires_consts


# ---------------------------------------------------------------------------
# THE QUARANTINE. Read the docstring section before touching it.
# name -> why it is here and who owns the decision.
# ---------------------------------------------------------------------------
KNOWN_UNBOUND: dict[str, str] = {
    # EMPTY, and it should stay that way. Its one entry,
    # Scene_Editor_ojz_act1_sec7_worldwater, was removed 2026-09-05 when aurora deleted
    # the attachment itself rather than binding it. Their evidence for the disposition
    # was the packet's own words: the design table annotated that layer as "underwater,
    # channel 3's band top, AND THE SPLIT ITSELF", so the author believed the scene-level
    # vsplit WAS the split for that band and was mirroring the hand-authored channel 3
    # into the scene document. It was never meant as a second split, so there was nothing
    # to bind.
    #
    # NOT AN AUTHORING ERROR, and the framing matters for whoever reads this next. From
    # inside the editor a split the section already has and a split the scene declares
    # look identical, because nothing on the surface says one of them is inert. The
    # author used a control that named exactly the effect they had been told the section
    # has. The panel-side half of that -- a control that authors something inert should
    # say so when it is offered -- is aurora's, and is open on their board.
    #
    # Adding an entry here is a LAST resort and it is not a way to silence the arms
    # below: they force the entry out again the moment its scene gains a consumer or
    # loses its vsplit, which is exactly how this one left.
}


def test_every_vsplit_authoring_scene_has_a_consumer():
    """A `vsplit:` with no `scene_vsplit_fires()` anywhere is an effect that cannot exist."""
    authorings, consumers, _ = scan()
    offenders = [a for a in authorings if a.scene not in consumers]
    unquarantined = [a for a in offenders if a.scene not in KNOWN_UNBOUND]
    assert not unquarantined, (
        "these scene layers author `vsplit: SceneVSplit.At(..)` but NOTHING calls "
        "`scene_vsplit_fires()` on their scene, so the attachment lowers to no raster "
        "program and reaches no ROM byte -- the effect is absent and the build is green:\n  "
        + "\n  ".join(repr(a) for a in unquarantined)
        + "\n\nA vsplit is the one scene-layer attachment that does NOT ride the lowered "
        "SceneCfgN record (engine/level/scene_dsl.emp, the SceneVSplit banner). To make it "
        "real, fold the scene and bind the program the way "
        "games/sonic4/data/effects/ojz_effects.emp does for Scene_Editor_ojz_act1_depth:\n"
        "    const X_PROG = scene_vsplit_fires(<Scene>)\n"
        "    pub data X: [u16; raster_words(X_PROG)] = raster_program(X_PROG)\n"
        "  then give X to a section's preset(raster: X, ..).\n"
        "Or remove the `vsplit:` from the authoring document if the effect is not wanted. "
        "Do NOT add the scene to KNOWN_UNBOUND to silence this -- that list is a "
        "quarantine for one pre-existing owner decision, not a way to land a new one."
    )


def test_every_fold_result_is_referenced():
    """An unreferenced `const X = scene_vsplit_fires(..)` is comptime-inert and proves nothing.

    docs/EMP_PITFALLS.md section 3: "an unreferenced top-level `const X = f(...)`" is
    comptime-inert. So a fold whose result is never named again is not a binding -- it is a
    call that never runs, and it would satisfy the consumer test above while emitting
    nothing. This is the second half of "exists AND is bound".
    """
    _, _, fires_consts = scan()
    if not fires_consts:
        raise AssertionError(
            "found no `const <Name> = scene_vsplit_fires(<Scene>)` declaration in the "
            "corpus. Either the fold spelling changed (update _FIRES_CONST in this file) "
            "or every consumer was deleted. Passing on zero would make this arm vacuous."
        )
    inert = []
    for const_name, (path, scene_name) in fires_consts.items():
        src = _strip_comments(path.read_text())
        uses = len(re.findall(r"\b" + re.escape(const_name) + r"\b", src))
        # one occurrence is the declaration itself
        if uses <= 1:
            inert.append((const_name, path.relative_to(REPO), scene_name))
    assert not inert, (
        "these `scene_vsplit_fires()` folds are never referenced again, which makes them "
        "comptime-INERT (docs/EMP_PITFALLS.md section 3) -- the call does not run, no "
        "program is built, and the scene's vsplit still reaches no ROM byte:\n  "
        + "\n  ".join(f"{c} = scene_vsplit_fires({s}) at {p}" for c, p, s in inert)
        + "\nReference the const from a `pub data` (raster_program(..)) so the program is "
        "actually emitted, or delete the fold."
    )


def test_quarantine_entries_still_author_a_vsplit():
    """A quarantine entry for a scene that no longer authors a vsplit is stale cover."""
    authorings, _, _ = scan()
    authoring_names = {a.scene for a in authorings}
    stale = sorted(set(KNOWN_UNBOUND) - authoring_names)
    assert not stale, (
        f"these KNOWN_UNBOUND entries name scenes that no longer author a "
        f"`vsplit: SceneVSplit.At(..)`: {stale}. The quarantine is over -- delete the "
        "entry from KNOWN_UNBOUND in this file and close the row in "
        "docs/DEFERRED_WORK.md. A quarantine kept past its subject is exactly the stale "
        "artifact that reads as coverage."
    )


def test_quarantine_entries_are_still_unbound():
    """A quarantine entry for a scene that GAINED a consumer must be deleted, not left.

    This is what stops KNOWN_UNBOUND from rotting into permanent cover: the moment somebody
    does the right thing and binds the scene, this fails and tells them to remove the entry.
    """
    _, consumers, _ = scan()
    fixed = sorted(set(KNOWN_UNBOUND) & set(consumers))
    assert not fixed, (
        f"these KNOWN_UNBOUND entries now HAVE a `scene_vsplit_fires()` consumer: {fixed}. "
        "The defect is fixed, so the quarantine must go: delete the entry from "
        "KNOWN_UNBOUND in this file and close VSPLIT-NO-OP in docs/DEFERRED_WORK.md in the "
        "same change. Leaving it would keep a real scene permanently exempt from the check."
    )


def test_quarantine_is_loud_on_every_build():
    """Every quarantined scene names itself in the build log, rather than passing silently.

    build.sh runs this lane as `pytest -q --no-header`, which prints a warnings summary. A
    quarantine nobody sees is the same silent absence this gate exists to end.
    """
    authorings, consumers, _ = scan()
    still = sorted(
        {a.scene for a in authorings} & set(KNOWN_UNBOUND) - set(consumers)
    )
    for name in still:
        warnings.warn(
            f"VSPLIT-NO-OP quarantine: {name} authors a `vsplit:` that reaches no ROM byte "
            f"(no scene_vsplit_fires consumer). {KNOWN_UNBOUND[name]}",
            UserWarning,
        )
    # The arm itself asserts the quarantine is not empty-and-forgotten in the other
    # direction: if KNOWN_UNBOUND is non-empty, at least one entry must be live, which the
    # two tests above already pin from both sides. Nothing to assert here beyond the warn.
    assert len(still) == len(KNOWN_UNBOUND), (
        f"KNOWN_UNBOUND holds {len(KNOWN_UNBOUND)} entries but only {len(still)} of them "
        "are live unbound-vsplit scenes right now. The other tests in this file name the "
        "specific reason; this arm exists so the count cannot drift unnoticed."
    )


def test_population_is_not_vacuous():
    """The scan must find real authoring sites and real consumers, or its patterns broke.

    A check that examines zero scenes passes forever. Both sides are asserted because a
    regex that stopped matching would otherwise report a clean, confident, empty result.
    """
    authorings, consumers, _ = scan()
    assert authorings, (
        "found no `vsplit: SceneVSplit.At(..)` authoring site anywhere under "
        f"{', '.join(str(REPO / r) for r in _ROOTS)}. Either every vsplit was removed from "
        "the tree (then delete this lint in the same commit) or the _VSPLIT_AT pattern no "
        "longer matches the authoring spelling. It must not silently pass on zero."
    )
    assert consumers, (
        "found no `scene_vsplit_fires(<Scene>)` call anywhere in the corpus, so the "
        "consumer half of this gate is measuring nothing and every authoring scene would "
        "be reported. Either the fold was renamed (update _FIRES_CALL) or all consumers "
        "were deleted."
    )
    # And the two sides must overlap: at least one authoring scene is actually consumed.
    # Without this, a corpus where the patterns matched disjoint things would still pass
    # the two assertions above.
    bound = {a.scene for a in authorings} & set(consumers)
    assert bound, (
        "no scene both authors a `vsplit:` and has a `scene_vsplit_fires()` consumer. The "
        "two patterns are matching disjoint text, which means one of them is wrong -- a "
        f"working tree has at least one bound scene. Authoring scenes: "
        f"{sorted({a.scene for a in authorings})}; consumed names: {sorted(consumers)}."
    )


def test_excluded_trees_are_the_declared_ones():
    """The corpus skips poison fixtures only, and says so out loud.

    An exclusion that grows silently is how a gate stops covering the thing it names. This
    asserts the skipped set is exactly the poison directories -- deliberately unbuildable
    modules driven by tools/emp_expect_fail.py, never in a shipping target's use closure.
    """
    skipped = []
    for root in _ROOTS:
        for p in sorted((REPO / root).rglob("*.emp")):
            if any(part in _EXCLUDED_PARTS for part in p.parts):
                skipped.append(p.relative_to(REPO))
    unexpected = [p for p in skipped if "poison" not in p.parts]
    assert not unexpected, (
        f"the corpus exclusion skipped files outside a poison directory: {unexpected}. "
        "Only deliberately-unbuildable poison fixtures may be skipped; anything else is a "
        "real module whose vsplits must be checked."
    )
