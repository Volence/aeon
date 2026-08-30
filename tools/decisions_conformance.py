#!/usr/bin/env python3
"""decisions_conformance — does docs/decisions.jsonl parse for the OWNER'S reader?

A DIFFERENT QUESTION FROM `lane_status_audit.py`, and they were confused for each other on
2026-08-30 (by a peer, from a citation this lane gave them). That tool asks whether the BOARD
and the ledger agree — the three `contract/LANE_STATUS.md` boundary checks. This one asks
whether Dominion's reader can parse each ledger line at all. A card that does not parse is a
question the owner is never shown, however well the board points at it.

THE PREDICATE IS TRANSCRIBED, NOT INVENTED, from dominion `796bc1e`
`server/src/decisions.ts` (`parseEntry`), relayed by the hub. **This is a second
implementation of someone else's parser, so it can drift from the real one.** If it disagrees
with Dominion, Dominion is right and this file is the bug. Re-transcribe rather than patching
to match a number.

WHY THIS FILE EXISTS AT ALL: the 55/31/22 measurement was first run in a throwaway script and
recorded only as prose in OVERSEER.md, which made the number unreproducible by anyone but its
author — the same "deliverables are committed" rule this repo applies to everything else.
Caught by the sigil lane.

⚠ THE HISTOGRAM DESCRIBES THE DATA, NOT THE READER'S OUTPUT — and that distinction has teeth.
Dominion's `parseOptions` RETURNS ON THE FIRST FAILING MEMBER (`796bc1e:server/src/decisions.ts`
`:232-239`), so the reader emits at most ONE options-error per line. This tool collects every
reason instead, deliberately, because as a REPAIR LIST that is the useful shape. The line counts
are identical either way — a line with one error and a line with nine are both rejected — but
anyone reading the histogram as "what the reader would say" will over-count, and anyone using it
to size a repair will get the true figure. Caught by the sigil lane, whose implementation returns
early like the reader's.

⚠ COUNT LINES, NEVER KEY BY ID. Rule 8c closures carry the settled id, and lanes have reused
ids outright, so ids repeat by design. The first run of this measurement keyed a dict on `id`
and reported 28 of 31 — three lines vanished into three existing keys, silently, and 28 looked
like a clean answer. `contract/DECISIONS.md` now states the rule with that as its precedent.

Exit codes: 0 every line parses, 1 at least one is rejected, 2 could not measure.
"""
from __future__ import annotations
import json
import os
import re
import sys
from collections import Counter

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(AEON, "docs/decisions.jsonl")
# Stand-in for the reader's `parseContractAt`. Deliberately strict, and the message says the
# EXACT SHAPE rather than "unparseable ISO-8601": `2026-08-24T01:38:39+00:00` is perfectly good
# ISO-8601 and is still rejected, by Dominion and here alike. Calling that "not parseable" sent
# a peer looking for a leniency difference that does not exist (their probe found identical
# verdicts; only my wording diverged). An `at` this rejects that Dominion accepts is a drift
# between the two implementations and wants re-transcribing, not loosening here.
AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def nonempty(v) -> bool:
    """The reader's `str(v)`: a string whose trim() has length."""
    return isinstance(v, str) and len(v.strip()) > 0


def reject_reasons(d: dict) -> list[str]:
    """Every reason this line is rejected. Errors are COLLECTED, as the reader collects them,
    so one line can carry several — the histogram is only meaningful that way."""
    e: list[str] = []
    if not nonempty(d.get("id")):
        e.append("id is missing or empty")
    if not nonempty(d.get("at")):
        e.append("at is missing or empty")
    elif not AT_RE.match(d["at"]):
        e.append("at is not the exact `date -u +%Y-%m-%dT%H:%M:%SZ` shape")
    if not nonempty(d.get("question")):
        e.append("question is missing or empty")

    o = d.get("options")
    if o is None:
        e.append("options missing")
    elif not isinstance(o, list):
        e.append("options not an array")
    else:
        if len(o) < 2:
            e.append("options must list two or more")
        seen = set()
        for it in o:
            if not isinstance(it, dict):
                e.append("option is not an object")
                continue
            for f in ("key", "name", "what", "costs"):
                if not nonempty(it.get(f)):
                    e.append(f"option missing {f}")
            if nonempty(it.get("key")):
                if it["key"] in seen:
                    e.append("repeated option key")
                seen.add(it["key"])

    r = d.get("recommend")
    if r is None:
        e.append("recommend missing")
    elif not isinstance(r, dict):
        e.append("recommend must be an object")
    else:
        if not nonempty(r.get("key")):
            e.append("recommend.key missing")
        if not nonempty(r.get("because")):
            e.append("recommend.because missing")
        if nonempty(r.get("key")) and isinstance(o, list):
            keys = {i.get("key") for i in o if isinstance(i, dict)}
            if r["key"] not in keys:
                e.append("recommend.key names no option in this entry")
    return e


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else LEDGER
    try:
        raw = [(n, line) for n, line in enumerate(open(path), 1) if line.strip()]
    except OSError as ex:
        print(f"CANNOT MEASURE: {path}: {ex}")
        return 2
    if not raw:
        print(f"CANNOT MEASURE: {path} holds no entries — refusing to report a ledger clean "
              f"against an empty file")
        return 2

    # A line that is not JSON is REJECTED AS A LINE, never a reason to abandon the file.
    # Dominion does exactly this (`:615-619`: push kind 'json', then `continue`), and the
    # first version of this tool returned 2 for the whole ledger instead — so a single bad
    # line made the file unmeasurable here while remaining perfectly measurable to the
    # reader, and it failed in the "we cannot know" direction. Found by the sigil lane
    # running this tool against their own red-first fixture.
    rows, bad = [], []
    for n, line in raw:
        try:
            rows.append((n, json.loads(line)))
        except json.JSONDecodeError as ex:
            bad.append((n, None, [f"not valid JSON: {ex}"]))

    bad += [(n, d.get("id"), reject_reasons(d)) for n, d in rows
            if reject_reasons(d)]
    bad.sort(key=lambda b: b[0])

    print(f"{path}")
    total = len(raw)
    print(f"  {total} lines · {total-len(bad)} parse · {len(bad)} REJECTED "
          f"(counted per LINE, never by id)")
    if bad:
        print("\n  reasons in the DATA (this tool collects all; the reader stops at the first\n  options failure and emits one, so these totals exceed its output — the LINE count above\n  is the figure that matches it):")
        for reason, n in Counter(x for _, _, e in bad for x in e).most_common():
            print(f"    {n:3d}  {reason}")
        print("\n  rejected lines:")
        for n, i, e in bad:
            print(f"    line {n:3d}  {i!r} — {'; '.join(sorted(set(e)))}")
        ids = [i for _, i, _ in bad]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            print(f"\n  NOTE: {len(dupes)} id(s) appear on more than one rejected line "
                  f"({', '.join(map(str, dupes))}). This is NORMAL under rule 8c and is exactly "
                  f"what an id-keyed count loses.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
