#!/usr/bin/env python3
"""LS-19a — `file.emp:LINE` citations in LIVE prose must resolve to something.

WHAT THIS GATE ASSERTS, and why that shape was chosen
-----------------------------------------------------
Every `X.emp:N` citation in a LIVE-scope file must resolve: the cited `.emp` file
must exist and be named unambiguously, and line N must exist and not be blank or a
bare delimiter.

That assertion holds for ANY valid content. It is not a snapshot of what the tree
says today, and it pins no count. That distinction is the one sigil measured
(sigil `c966302d`, `PROBE-CONTENT-SNAPSHOT`): the axis separating a durable gate
from a defective one is not which directory a file lives in, it is whether the
assertion is content-invariant or pins today's snapshot. A register of "the 187
citations we currently know are stale" would have been the snapshot kind, so this
gate deliberately does not carry one — the drift census is a MEASUREMENT reported
in the LS-19a row, not a gate.

WHAT IT DOES NOT CATCH, stated so nobody reads a green as more than it is
------------------------------------------------------------------------
A citation whose line still exists and is non-blank but now points at the WRONG
thing. That is undecidable from text alone, and it is the majority of the real
staleness: of 438 live citations measured 2026-09-08, 126 were unchanged since
they were written, 172 pointed at text that had MOVED, and 31 at text that was
GONE. The repair for that class is the citation FORM (`file.emp` + symbol name),
not a number this gate could check. `ojz_scenes.emp` was the worst instance and
this gate would NOT have caught it: its numbers resolved to real, non-blank,
plausible, wrong symbols at the anchor it named.

So: green here means "no citation points at nothing". It does not mean "every
citation is accurate."

RECORDS vs LIVE
---------------
See CODING_CONVENTIONS.md, "RECORDS vs LIVE prose". A RECORD is a document that
reports what was true at a moment; its coordinates are frozen with it and are
never re-pointed. LIVE prose describes the tree as it stands and must be
re-pointable. The boundary below is the single source of truth; the convention
doc mirrors it in words.
"""
from __future__ import annotations

import os
import re
import subprocess
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- the boundary
# RECORDS: dated or evidence-shaped documents. Each entry below is a directory or
# file the tree ALREADY treats as frozen; none of these classes was invented here.
RECORD_DIRS = (
    "docs/superpowers/",     # notes/plans/designs/probes/specs, all dated (LS-14 closure)
    "docs/research/",        # dated research captures
    "docs/reviews/",         # dated review records
    "docs/benchmarks/",      # *-EVIDENCE.md measurement captures
    "docs/witness/",         # dated witness reads
    "docs/measurements/",    # dated measurement notes
    "docs/captures/",        # raw capture artefacts
    "docs/generated/",       # generated, not authored
    "docs/specs/",           # dated `status:`-stamped frozen specs
)
RECORD_FILES = (
    # DEFERRED_WORK's own MAINTENANCE PROTOCOL forbids rewriting an entry's text
    # ("Keep the original text beneath"), and its header already warns readers not
    # to chase its file:line citations blind. It is a record by its own rules.
    "docs/DEFERRED_WORK.md",
    # docs/BUGS.md was ARCHIVED 2026-09-09 to docs/2026-09-09-BUGS-archived.md, which the
    # dated docs/YYYY-MM-DD-* rule below already covers as a RECORD. The explicit entry was
    # removed with it: leaving it would have silently exempted a RECREATED docs/BUGS.md.
    # docs/DEFERRED_WORK.md, the parcel that swept the rest of the docs.
    "docs/OVERSEER-LOG.md",
    "docs/QUEUE-ARCHIVE.md",
    "docs/CHARACTER_BOX_AUDIT.md",              # "**Date:** 2026-08-28 ... Verdict:"
    "docs/SPRITE_OWNER_PIN_SLIDE_MEASUREMENT.md",
)


def is_record(path: str) -> bool:
    """True if `path` is a frozen record whose coordinates are never re-pointed."""
    p = path.replace(os.sep, "/")
    if p.startswith(RECORD_DIRS):
        return True
    if p in RECORD_FILES:
        return True
    # append-only logs and machine-written data are records by construction
    if p.endswith((".jsonl", ".json")):
        return True
    # a dated note at the docs root: docs/2026-09-06-whatever.md
    base = p.rsplit("/", 1)[-1]
    if p.startswith("docs/") and re.match(r"^\d{4}-\d{2}-\d{2}-", base):
        return True
    return False


# A citation is a `.emp` path followed by a colon and a line number.
# (Not spelled out as an example here: this gate scans itself, and an example
# written in citation form IS a citation -- measured, it failed exactly that way.)
CITE = re.compile(r"(?<![A-Za-z0-9_./-])([A-Za-z0-9_][A-Za-z0-9_/.-]*\.emp):(\d+)")


def _is_prose_elision(cited: str) -> bool:
    """`games/.../act_descriptor.emp` is prose shorthand, not a path.

    Excluded deliberately: reading an elided path as a citation manufactures a
    defect that is not there, and a gate that invents its own subject is worse
    than no gate.
    """
    return "..." in cited

# A file may freeze its citations against a named revision of a file that no longer
# exists at HEAD. Declared, so it can be checked rather than believed.
#
# The marker must OPEN a comment line and the path must look like a path. Prose that
# merely mentions the marker is not a declaration -- this gate's own docstring does, and
# a looser pattern read that sentence as a declaration of revision "`" at path "marker".
# It went unnoticed while the file was still untracked, because `git ls-files` did not
# yet list it: the gate was green only because it was not yet part of its own subject.
ANCHOR = re.compile(
    r"^\s*(?://|#)\s*CITATIONS-ANCHORED-AT:\s*(\S+)\s+(\S+\.(?:emp|asm|py|toml|md))\s*$",
    re.MULTILINE,
)

SKIP_DIRS = {".git", "__pycache__", ".cache", "node_modules", "target"}


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "-C", ROOT, "ls-files"], capture_output=True, text=True, check=True
    )
    return [f for f in out.stdout.split("\n") if f]


def _emp_index() -> tuple[set[str], dict[str, list[str]]]:
    """Every .emp file this repo actually owns, tracked or intentionally new.

    ENUMERATED FROM GIT, NOT FROM A DIRECTORY WALK, and that is the whole point.
    The walk this replaced descended into `.claude/worktrees/`, where agent
    parcels leave scores of full checkouts, so every bare `foo.emp:N` citation
    matched ~160 files and resolved as ambiguous. The gate then reported "183 of
    363 citations point at nothing" and FAILED THE BUILD -- in the main tree only.
    A clean checkout and every agent worktree stayed green, because neither
    contains nested worktrees, so the red was invisible to exactly the people who
    could have fixed it and unavoidable for everyone standing in the main tree.

    Adding ".claude" to SKIP_DIRS would have fixed the instance and left the
    class: the next ignored tree with a different name repeats it. Git already
    knows what this repo owns. Asking it cannot see an ignored tree BY
    CONSTRUCTION rather than by remembering to list one.

    Note the asymmetry this closes: the CITING side was already enumerated from
    `git ls-files` (see _tracked_files), while the CITED side walked the disk.
    Two populations, one question.

    Untracked-but-not-ignored files are included so a citation to an .emp added
    in the working tree resolves; ignored files never are.
    """
    by_path: set[str] = set()
    by_base: dict[str, list[str]] = defaultdict(list)
    for args in (["ls-files"], ["ls-files", "--others", "--exclude-standard"]):
        out = subprocess.run(["git", "-C", ROOT, *args],
                             capture_output=True, text=True)
        if out.returncode != 0:
            # Loud on unmeasurable (invariant 8d). A silent fall back to the walk
            # would restore the very defect this replaced, and print green.
            raise AssertionError(
                f"`git {' '.join(args)}` failed in {ROOT} -- this gate enumerates its "
                f"subject from git and will NOT fall back to a directory walk, which "
                f"is what made it fail in the main tree only. stderr: {out.stderr.strip()}"
            )
        for rel in out.stdout.split("\n"):
            if rel.endswith(".emp"):
                by_path.add(rel)
                by_base[rel.rsplit("/", 1)[-1]].append(rel)
    return by_path, by_base


def _read(path: str) -> str | None:
    try:
        with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
            return fh.read()
    except (UnicodeDecodeError, IsADirectoryError, FileNotFoundError):
        return None


def _show(rev: str, path: str) -> list[str] | None:
    out = subprocess.run(
        ["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True
    )
    return out.stdout.split("\n") if out.returncode == 0 else None


def _dead(line: str | None) -> str | None:
    """Why this target is a citation to nothing, or None if it is real."""
    if line is None:
        return "past end of file"
    s = line.strip()
    if s == "":
        return "blank line"
    if s in ("}", "{", ")", "(", "//", "*/"):
        return "bare delimiter"
    return None


def collect_live_citations():
    """Yield (citer, citer_line, cited_text, n, (anchor_path, rev) | None), LIVE scope."""
    for f in _tracked_files():
        if is_record(f):
            continue
        text = _read(f)
        if text is None:
            continue
        anchors = [(p, rev) for rev, p in ANCHOR.findall(text)]
        for i, line in enumerate(text.split("\n"), 1):
            if ANCHOR.search(line):
                continue  # the declaration itself is not a citation
            for m in CITE.finditer(line):
                cited, n = m.group(1), int(m.group(2))
                if _is_prose_elision(cited):
                    continue
                # An anchor is keyed by the path it DECLARES; a citation written as a
                # bare basename resolves through it to that full path, because the
                # anchored file does not exist at HEAD to be looked up.
                hit = next(
                    (ap_rev for ap_rev in anchors
                     if ap_rev[0] == cited or ap_rev[0].endswith("/" + cited)),
                    None,
                )
                yield f, i, cited, n, hit


def test_live_citations_resolve_to_something():
    """No LIVE-scope `X.emp:N` may point at a missing file or an empty line.

    Content-invariant: it constrains no particular content, only that a pointer
    has a referent. A record is exempt by design, never by accident -- see
    is_record() and CODING_CONVENTIONS.md.
    """
    by_path, by_base = _emp_index()
    assert by_path, "no .emp files found -- the gate cannot measure its subject"

    failures: list[str] = []
    checked = 0
    for citer, cline, cited, n, anchor in collect_live_citations():
        checked += 1
        if anchor is not None:
            apath, rev = anchor
            lines = _show(rev, apath)
            if lines is None:
                failures.append(
                    f"{citer}:{cline} cites {cited}:{n} anchored at {rev}, "
                    f"but {apath} does not exist at that revision"
                )
                continue
            why = _dead(lines[n - 1] if 1 <= n <= len(lines) else None)
            if why:
                failures.append(
                    f"{citer}:{cline} cites {cited}:{n} at declared anchor "
                    f"{rev}:{apath} -- {why}"
                )
            continue

        path = _resolve(cited, by_path, by_base)
        if path is None:
            failures.append(
                f"{citer}:{cline} cites {cited}:{n} -- no such .emp file at HEAD "
                f"(and no CITATIONS-ANCHORED-AT declares a revision for it)"
            )
            continue
        if path == "":
            cands = sorted(by_base.get(cited.rsplit("/", 1)[-1], []))
            failures.append(
                f"{citer}:{cline} cites bare `{cited}:{n}` which matches {len(cands)} "
                f"files ({', '.join(cands)}) -- name the path or the symbol"
            )
            continue
        body = _read(path)
        lines = body.split("\n") if body is not None else []
        why = _dead(lines[n - 1] if 1 <= n <= len(lines) else None)
        if why:
            failures.append(f"{citer}:{cline} cites {path}:{n} -- {why}")

    assert checked > 0, (
        "the gate resolved ZERO live citations. That is not a pass: either the "
        "boundary in is_record() swallowed the whole tree or CITE stopped matching. "
        "Loud on unmeasurable, per invariant 8(d)."
    )
    assert not failures, (
        f"{len(failures)} of {checked} live `.emp:LINE` citations point at nothing.\n"
        "Fix the FORM, not the number: cite `file.emp` plus the enclosing symbol "
        "name, which survives every edit (CODING_CONVENTIONS.md, 'CITE BY NAME').\n"
        + "\n".join("  " + f for f in sorted(failures))
    )


def _resolve(cited: str, by_path, by_base) -> str | None:
    """Return the path, "" if ambiguous, or None if absent."""
    if cited in by_path:
        return cited
    suffix = [p for p in by_path if p.endswith("/" + cited)]
    if len(suffix) == 1:
        return suffix[0]
    if len(suffix) > 1:
        return ""
    if "/" in cited:
        return None
    cands = by_base.get(cited, [])
    if len(cands) == 1:
        return cands[0]
    if len(cands) > 1:
        return ""
    return None


def test_declared_anchors_name_a_reachable_revision():
    """A `CITATIONS-ANCHORED-AT:` marker must name a revision that really has the file.

    Without this the marker is an exemption anyone can write to silence the gate
    above; with it, the exemption is itself checked.
    """
    markers: list[tuple[str, str, str]] = []
    for f in _tracked_files():
        text = _read(f)
        if text is None or "CITATIONS-ANCHORED-AT" not in text:
            continue
        for rev, path in ANCHOR.findall(text):
            markers.append((f, rev, path))

    failures = []
    for f, rev, path in markers:
        if _show(rev, path) is None:
            failures.append(f"{f}: CITATIONS-ANCHORED-AT {rev} {path} -- unreachable")
    assert not failures, "\n".join(failures)


def test_records_are_excluded_and_live_files_are_not():
    """The boundary itself, pinned by example on both sides.

    Named files, not counts: a count would fire on every legitimate addition while
    staying blind to a file changing sides, which is the same hazard with nothing
    to count (the reasoning tools/test_deb2_appendix.py states for `mark`).
    """
    for p in (
        "docs/superpowers/notes/anything.md",
        "docs/DEFERRED_WORK.md",
            "docs/research/2026-08-07-mdsdrv/core.md",
        "docs/2026-09-06-live-effects-ram-surface.md",
        "docs/decisions.jsonl",
        "docs/specs/boot-ym-keyoff-race.md",
    ):
        assert is_record(p), f"{p} should be a RECORD"
    for p in (
        "CODING_CONVENTIONS.md",
        "docs/ENGINE_ARCHITECTURE.md",
        "docs/OVERSEER.md",
        "docs/ART_PIPELINE_CONTRACT.md",
        "docs/EFFECTS_AUTHORING.md",
        "tools/EFFECTS_CONSUMER_CONTRACT.md",
        "engine/level/parallax.emp",
        "games/sonic4/data/effects/ojz_scenes.emp",
        "tools/effects_gen.py",
    ):
        assert not is_record(p), f"{p} should be LIVE"


def census() -> dict:
    """Measure the whole population, RECORDS and LIVE, and classify each citation.

    A MEASUREMENT, not a gate. It lives here so the numbers quoted in the LS-19a
    row are re-derivable by one command instead of being a figure to trust:

        python3 tools/test_citation_form.py --census

    METHOD, stated beside the result because a count without the parameter it was
    measured under is an answer to an unstated question. For each citation,
    `git blame` the CITING line for the revision at which it was last written; read
    the CITED file's line N at that same revision; compare with line N today.

      STABLE  identical -- the pointer still points at the text it was written for
      MOVED   that text exists today at a DIFFERENT line (pointer wrong, referent
              recoverable, so the repair is mechanical)
      GONE    that text is nowhere in the file today
      dead-*  the classes the gate fails on: no file, past EOF, blank, bare
              delimiter, ambiguous basename

    MOVED/GONE are deliberately NOT gated: whether a moved pointer is materially
    wrong depends on intent, so a threshold over them would pin a snapshot instead
    of asserting something content-invariant.
    """
    by_path, by_base = _emp_index()
    blame_cache: dict[str, dict[int, str]] = {}

    def blame(f: str) -> dict[int, str]:
        if f not in blame_cache:
            out = subprocess.run(
                ["git", "-C", ROOT, "blame", "--porcelain", "--", f],
                capture_output=True, text=True,
            )
            m: dict[int, str] = {}
            if out.returncode == 0:
                for ln in out.stdout.split("\n"):
                    parts = ln.split(" ")
                    if len(parts) >= 3 and len(parts[0]) == 40:
                        try:
                            m[int(parts[2])] = parts[0]
                        except ValueError:
                            pass
            blame_cache[f] = m
        return blame_cache[f]

    tally: dict[str, dict] = {"LIVE": defaultdict(int), "RECORDS": defaultdict(int)}
    for f in _tracked_files():
        text = _read(f)
        if text is None:
            continue
        scope = "RECORDS" if is_record(f) else "LIVE"
        anchored = [p for _, p in ANCHOR.findall(text)]
        for i, line in enumerate(text.split("\n"), 1):
            if ANCHOR.search(line):
                continue
            for m in CITE.finditer(line):
                cited, n = m.group(1), int(m.group(2))
                if _is_prose_elision(cited):
                    continue
                if any(ap == cited or ap.endswith("/" + cited) for ap in anchored):
                    tally[scope]["anchored"] += 1
                    continue
                path = _resolve(cited, by_path, by_base)
                if path is None:
                    tally[scope]["dead-no-file"] += 1
                    continue
                if path == "":
                    tally[scope]["dead-ambiguous"] += 1
                    continue
                now = (_read(path) or "").split("\n")
                why = _dead(now[n - 1] if 1 <= n <= len(now) else None)
                if why:
                    tally[scope]["dead-" + why.replace(" ", "-")] += 1
                    continue
                sha = blame(f).get(i)
                if not sha:
                    tally[scope]["no-blame"] += 1
                    continue
                then = _show(sha, path)
                if then is None:
                    tally[scope]["file-absent-at-write"] += 1
                    continue
                old = then[n - 1].strip() if 1 <= n <= len(then) else None
                if old is None:
                    tally[scope]["past-eof-at-write"] += 1
                elif old == now[n - 1].strip():
                    tally[scope]["STABLE"] += 1
                elif len(old) >= 8 and any(x.strip() == old for x in now):
                    tally[scope]["MOVED"] += 1
                else:
                    tally[scope]["GONE"] += 1
    return tally


if __name__ == "__main__":
    import sys

    if "--census" in sys.argv:
        t = census()
        for scope in ("LIVE", "RECORDS"):
            rows = t[scope]
            print(f"{scope}: {sum(rows.values())} citations")
            for k in sorted(rows, key=lambda k: -rows[k]):
                print(f"    {rows[k]:6d}  {k}")
        raise SystemExit(0)

    test_records_are_excluded_and_live_files_are_not()
    test_declared_anchors_name_a_reachable_revision()
    test_live_citations_resolve_to_something()
    print("citation form: OK")
