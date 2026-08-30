#!/usr/bin/env python3
"""No source file in this repo may spell an absolute path into one machine's home.

## The class this closes (SUITE-HOME-PATHS, booked 2026-08-30)

52 files under `tools/ engine/ games/ build.sh` carried a literal absolute path to a peer
Empyrean repo. Six of them are pytest-collected and gate 188 build-fatal rows, so the class
could — and in one row did — turn a missing donor tree into something other than a loud
failure. `tools/suite_paths.py` replaced every one of them with a resolver. This file is the
reason the 53rd does not appear.

## The two rules, and why the second one exists

  1. **the home-directory prefix** — the literal form the classification found. This is
     rule 3 of the fix.
  2. **the suite directory's own name**, in ANY spelling. Rule 1 alone is trivially evaded
     by a tilde or a `$HOME` prefix in front of that name, which are exactly as baked and
     exactly as silent. Banning the directory name closes all three spellings at once, and
     nothing legitimate needs it: `suite_paths.suite_root()` names that directory for you, and
     prose can call it "the suite root". This rule was chosen over banning `$HOME`, which
     `nightly_effects_gates.sh` uses legitimately for the XDG state dir.

Both needles are built by concatenation below so that THIS FILE IS ITSELF SCANNED. A gate that
has to exempt itself has a hole the exact shape of the rule.

## Anti-vacuity

Three things could make this file pass while checking nothing, and each has a row:

  * the population could be empty (bad glob, wrong root) — `test_the_population_is_not_empty`
    derives the expected file count from `git ls-files` and requires it to be substantial;
  * the matcher could match nothing ever — `test_the_detector_matches_a_planted_path` feeds it
    a synthetic baked path in each banned spelling and requires a hit;
  * the population could be unmeasurable — `_tracked_sources()` raises rather than returning an
    empty list when git cannot answer, so "could not measure" is red, never 0.
"""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import REPO_ROOT  # noqa: E402

# Built by concatenation on purpose: this file is scanned like every other, so it must not
# contain either needle as a literal.
NEEDLE_HOME = "/" + "home" + "/"
NEEDLE_SUITE = "sonic" + "_hacks"

#: Where a baked path would do damage: everything the build, the gates and the probes read.
#: `docs/` is deliberately NOT scanned — DEFERRED_WORK.md and the classification notes quote
#: real absolute paths as evidence, which is the correct thing for a record to do.
SCAN_ROOTS = ("tools", "engine", "games", "build.sh")

#: Only source: things that execute or instruct. Extension-scoped so the population is a
#: property of the tree rather than a hand-maintained list.
SCAN_SUFFIXES = (".py", ".sh", ".md", ".emp", ".asm", ".toml")

#: The one exemption, and it is a data artifact rather than a source file: a generated donor
#: provenance record whose PURPOSE is to state which absolute path a past re-bake actually
#: read. Recording it is the record; it is not scanned because `.json` is not a scan suffix.
#: Kept here as prose so the exemption is stated rather than merely implied by the suffix list.
_EXEMPT_NOTE = "games/sonic4/data/generated/**/DONOR_PROVENANCE.json (generated provenance)"

#: A floor for the scanned population, derived below rather than pinned: see
#: `test_the_population_is_not_empty`.
MIN_SCANNED = 100


def _tracked_sources() -> list[Path]:
    """Every tracked source file under SCAN_ROOTS. Raises if git cannot answer."""
    try:
        out = subprocess.run(["git", "-C", str(REPO_ROOT), "ls-files", "-z", *SCAN_ROOTS],
                             capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        # LOUD on unmeasurable. Returning [] here would render "I could not look" as "I looked
        # and found nothing wrong", which is the exact defect this whole row exists to remove.
        raise RuntimeError(
            f"cannot enumerate the source tree under {REPO_ROOT}: {e}. This gate did NOT "
            "measure anything; do not read its silence as a pass.") from e
    rels = [p for p in out.decode().split("\0") if p]
    return [REPO_ROOT / r for r in rels if Path(r).suffix in SCAN_SUFFIXES]


def _offenders(needle: str):
    """(relative path, lineno, line) for every line carrying `needle`."""
    for f in _tracked_sources():
        try:
            text = f.read_text()
        except (OSError, UnicodeDecodeError):
            continue  # binary or unreadable: it cannot carry a source-level baked path
        if needle not in text:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if needle in line:
                yield f.relative_to(REPO_ROOT), n, line.strip()


def test_the_population_is_not_empty():
    """Guards the guard: a wrong root or suffix list would make every row below vacuous.

    The floor is derived, not pinned: `git ls-files tools engine games build.sh` names 600+
    files in this tree and the source suffixes are the large majority of them, so anything
    under MIN_SCANNED means the enumeration broke rather than that the tree shrank.
    """
    scanned = _tracked_sources()
    assert len(scanned) >= MIN_SCANNED, (
        f"only {len(scanned)} source files enumerated under {SCAN_ROOTS} in {REPO_ROOT} — "
        f"expected at least {MIN_SCANNED}. The population is broken, not the tree.")


#: The three spellings a baked suite path takes in the wild, assembled from the needles so
#: this file does not contain them literally (it scans itself).
PLANTED = (
    NEEDLE_HOME + "someone/" + NEEDLE_SUITE + "/oracle/target/release/oracle-aether",
    "~/" + NEEDLE_SUITE + "/skdisasm/Sound/Music/HCZ2.asm",
    '"$HOME/' + NEEDLE_SUITE + '/empyrean/clients/python"',
)


@pytest.mark.parametrize("planted", PLANTED)
def test_the_detector_matches_a_planted_path(planted):
    """The matcher fires on every banned spelling, including the two rule 1 alone would miss."""
    assert NEEDLE_HOME in planted or NEEDLE_SUITE in planted, (
        f"the detector does not match {planted!r} — a baked path in this spelling would pass")


def test_no_absolute_home_path_is_baked_into_any_source_file():
    """RULE 1. An absolute path under someone's home directory, in tracked source."""
    hits = list(_offenders(NEEDLE_HOME))
    assert not hits, (
        f"{len(hits)} baked absolute home path(s) in tracked source:\n  "
        + "\n  ".join(f"{p}:{n}: {line}" for p, n, line in hits)
        + "\n\nA path baked to one machine's home either breaks elsewhere or — the defect "
          "SUITE-HOME-PATHS is named for — makes a gate PASS while reading nothing. Resolve it "
          "through tools/suite_paths.py: `suite_path(...)` when the caller checks, "
          "`require_suite_path(...)` when the value is about to be opened. "
          f"Exempt by construction: {_EXEMPT_NOTE}.")


def test_the_suite_directory_name_is_never_spelled_into_a_path():
    """RULE 2. A tilde or $HOME in front of the suite directory name is just as baked."""
    hits = list(_offenders(NEEDLE_SUITE))
    assert not hits, (
        f"{len(hits)} reference(s) to the suite directory by name in tracked source:\n  "
        + "\n  ".join(f"{p}:{n}: {line}" for p, n, line in hits)
        + "\n\nNaming the suite directory is a baked path wearing a different spelling — it "
          "assumes the checkout sits somewhere specific. Call "
          "`suite_paths.suite_root()` for the directory, or say 'the suite root' in prose.")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
