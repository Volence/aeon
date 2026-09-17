#!/usr/bin/env python3
"""gate_cut_shape — WHERE a fixture-pinned gate's cut comes from, per build shape
(STRESS-SHAPES-GATE-CUTS, 2026-09-17, controller ruling option (b)).

THE CUT-PINNED GATES. sprite_tilt_gate, instashield_gate (two subjects) and
loop_crossover_gate each execute their subject routine's bytes out of THIS build's ROM,
at the extent THIS build's listing gives. Their committed cuts (tools/fixtures/*_cut.json)
are not an input to that execution. A cut exists for ONE reason: build.sh's pre-build
pytest lane runs before sigil and cannot open a fresh ROM, so it grades a committed cut,
and the gate checks on the fresh artifact that the cut is still this build's routine (the
DRIFT PIN). A cut is produced mechanically by the gate's own producer
(`--emit-fixture` / `--write-fixture`) from a listing + ROM. Nothing in it is hand-reviewed.

THE RULE.
  * CANONICAL shape (a listing build.sh ships as a canonical artifact): the committed cut
    is required, exactly as before. A canonical shape with no committed cut FAILS.
  * OFF-CANONICAL fixture shape (a DEV shape build.sh declares, e.g. STRESS_EVICT's
    `s4.stress` and STRESS_ART's `s4.stressart`): the cut is DERIVED at gate time from
    that shape's OWN listing and ROM by the gate's own producer, never committed and
    never borrowed from another shape. The gate then runs every sweep it runs for a
    canonical shape. It says loudly that the cut was derived, and it does not report the
    drift pin as passed: a cut derived from a listing cannot disagree with that listing,
    and no pytest lane reads a cut for these shapes, so the pin has nothing to protect.
    Derivation failing is COULD NOT RUN (exit 2), never green. A committed cut for an
    off-canonical shape is refused (exit 1): it would be a second, unowned copy.
  * ANY OTHER listing name (a hand-renamed artifact, a typo): treated as canonical, i.e.
    the committed cut is required. Being unrecognised never earns a derived cut.

WHERE THE CLASSES COME FROM (no list is typed here).
  * canonical: `artifact_provenance.CANONICAL_SHAPES`, the table the ONE freshness
    verdict already uses for "the canonical artifact names build.sh writes"; its .bin
    names map to .lst names by suffix.
  * off-canonical: build.sh's own literal `ROM_NAME="<name>"` assignments, each alone on
    its line. The canonical names are computed there (`ROM_NAME="${ROM_NAME}.debug"`,
    `ROM_NAME="s4"` inside an if/else line), so only the fixture shapes' blocks carry a
    standalone literal. A name that is ALSO canonical is refused, not classified.
"""

import os
import pathlib
import re
import sys

TOOLS = pathlib.Path(__file__).resolve().parent
AEON = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import artifact_provenance  # noqa: E402

CANONICAL = "canonical"
OFF_CANONICAL = "off-canonical"

#: The exit code for a derived cut that could not be derived or does not check against
#: its own listing: the gate did not measure what it was asked about.
COULD_NOT_RUN = artifact_provenance.UNMEASURABLE

_STANDALONE_ROM_NAME = re.compile(r'^\s*ROM_NAME="([^"$]+)"\s*$', re.M)


class ShapeClassError(Exception):
    """The two sources disagree about a name, or a source cannot be read."""


def canonical_listings():
    """The canonical listing names, from artifact_provenance.CANONICAL_SHAPES."""
    out = set()
    for rom in artifact_provenance.CANONICAL_SHAPES:
        if not rom.endswith(".bin"):
            raise ShapeClassError("CANONICAL_SHAPES names %r, which is not a .bin" % rom)
        out.add(rom[:-len(".bin")] + ".lst")
    return out


def off_canonical_listings(build_sh=None):
    """The off-canonical fixture shapes' listing names, read off build.sh."""
    path = pathlib.Path(build_sh) if build_sh is not None else AEON / "build.sh"
    try:
        text = path.read_text()
    except OSError as e:
        raise ShapeClassError("cannot read %s to find the off-canonical shapes: %s"
                              % (path, e))
    names = {n + ".lst" for n in _STANDALONE_ROM_NAME.findall(text)}
    both = names & canonical_listings()
    if both:
        raise ShapeClassError(
            "build.sh assigns %s as a standalone literal ROM_NAME, but "
            "artifact_provenance.CANONICAL_SHAPES calls it canonical; the two sources "
            "disagree and neither is guessed" % ", ".join(sorted(both)))
    return names


def classify(lst_path, build_sh=None):
    """CANONICAL or OFF_CANONICAL for a listing path. Unrecognised names are CANONICAL
    (the committed cut is required), so an unknown name can never earn a derived cut."""
    name = os.path.basename(str(lst_path))
    if name in canonical_listings():
        return CANONICAL
    if name in off_canonical_listings(build_sh):
        return OFF_CANONICAL
    return CANONICAL


def derived_banner(gate, lst_path, fixture_name):
    """The loud line a gate prints before grading against a derived cut."""
    name = os.path.basename(str(lst_path))
    return ("%s: *** OFF-CANONICAL SHAPE %r: the %s cut is DERIVED from this shape's own "
            "listing and ROM by the gate's own producer, NOT committed and NOT borrowed "
            "(tools/gate_cut_shape.py). Every sweep below still executes this ROM. ***"
            % (gate, name, fixture_name))


def drift_pin_not_measured(fixture_name, lst_path):
    """What a gate prints in place of the drift-pin verdict for a derived cut."""
    return ("fixture: %s [%s] DERIVED — drift pin NOT MEASURED (a cut derived from this "
            "listing cannot disagree with it; no pytest lane reads a cut for an "
            "off-canonical shape). The derived cut did check clean against the listing, "
            "which proves only that the producer and the checker agree."
            % (fixture_name, os.path.basename(str(lst_path))))


def canonical_targets():
    """The digest `target=` words a canonical build carries: its game's name (sigil
    `digest_target`: Sonic4 -> sonic4, Demo -> demo), from CANONICAL_SHAPES' games."""
    return {game for game, _debug in artifact_provenance.CANONICAL_SHAPES.values()}


def digest_target_problem(lst_path):
    """None when the listing's own Source Digest names a NON-canonical build target;
    otherwise the reason, in words."""
    try:
        d = artifact_provenance.read_digest(str(lst_path))
    except (OSError, artifact_provenance.DigestError) as e:
        return "its Source Digest cannot be read (%s)" % e
    target = d.get("shape", {}).get("target")
    if target is None:
        return "its Source Digest carries no DIGEST-SHAPE target"
    if target in canonical_targets():
        return ("its Source Digest says target=%s, a CANONICAL build target; a canonical "
                "build under an off-canonical name is not an off-canonical shape" % target)
    return None


def derive_for_offcanonical(gate, lst_path, fixture, committed_shapes, produce, check):
    """Derive and self-check an off-canonical shape's cut. Returns an exit code to stop
    with (1: a committed cut exists for this shape; 2: COULD NOT RUN), or None when the
    derived cut exists and checks clean against its own listing.

    `committed_shapes(path)` lists the committed fixture's shape keys; `produce(path)`
    writes the derived cut document there using the gate's OWN producer; `check(path)`
    runs the gate's OWN cut check against it, returning a list of problems or raising
    SystemExit with one. Everything printed names the gate and the shape."""
    import tempfile
    name = os.path.basename(str(lst_path))
    fixture_name = pathlib.Path(fixture).name
    if pathlib.Path(fixture).exists():
        try:
            have = committed_shapes(fixture)
        except (SystemExit, Exception) as e:     # noqa: BLE001 — named, then refused
            print("%s: COULD NOT RUN — cannot read %s to confirm it holds no cut for "
                  "off-canonical shape %r: %s" % (gate, fixture, name, e))
            return COULD_NOT_RUN
        if name in have:
            print("%s: %s carries a COMMITTED cut for off-canonical shape %r. "
                  "Off-canonical cuts are derived at gate time and never committed "
                  "(tools/gate_cut_shape.py); remove that key." % (gate, fixture, name))
            return 1
    # The NAME says off-canonical; the listing must say so too. sigil's Source Digest
    # names the build target (`DIGEST-SHAPE target=`; canonical builds carry target ==
    # game, the fixture profiles `stress-evict` / `stress-art`), so a canonical build
    # renamed to a stress name cannot earn a derived cut.
    problem = digest_target_problem(lst_path)
    if problem:
        print("%s: COULD NOT RUN — %r is named as an off-canonical shape, but %s. No "
              "cut is derived for it." % (gate, name, problem))
        return COULD_NOT_RUN
    print(derived_banner(gate, lst_path, fixture_name))
    with tempfile.TemporaryDirectory(prefix="gate_cut_shape.") as td:
        path = pathlib.Path(td) / fixture_name
        try:
            produce(path)
        except (SystemExit, Exception) as e:     # noqa: BLE001 — named, then refused
            print("%s: COULD NOT RUN — deriving the %s cut for off-canonical shape %r "
                  "failed (%s: %s). No sweep is reported for a shape whose cut could not "
                  "be derived." % (gate, fixture_name, name, type(e).__name__, e))
            return COULD_NOT_RUN
        try:
            problems = check(path)
        except SystemExit as e:
            problems = [str(e)]
    if problems:
        print("%s: COULD NOT RUN — the %s cut DERIVED from %r does not check against "
              "that same listing, so the producer and the checker disagree (a gate bug, "
              "not a finding about the build):" % (gate, fixture_name, name))
        for p in problems:
            print("    " + p)
        return COULD_NOT_RUN
    return None


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("lst", nargs="*")
    a = ap.parse_args()
    print("canonical:     %s" % ", ".join(sorted(canonical_listings())))
    print("off-canonical: %s" % ", ".join(sorted(off_canonical_listings())))
    for p in a.lst:
        print("%s -> %s" % (p, classify(p)))
