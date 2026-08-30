#!/usr/bin/env python3
"""lane_status_audit — the boundary audit of docs/lane-status.json against docs/decisions.jsonl.

The three checks are empyrean `contract/LANE_STATUS.md`'s, not this lane's invention:

  1. every owner-blocking claim has a decision card behind it;
  2. every still-open card is surfaced to him (blockedOnOwner, or explicitly parked);
  3. no queue row carries an owner blocker in `blockedBy` prose.

TWO THINGS THIS TOOL EXISTS TO GET RIGHT, both of which a hand-rolled version got WRONG here
on 2026-08-30 before it was written down. They are the whole value; the checks themselves are
three lines each.

(a) CHECK 1 MUST ENUMERATE FROM BOTH FIELDS. Oracle ran check 1 over `blockedOnOwner` alone,
    reported "no missing cards", and the report was TRUE AND USELESS: their one uncarded owner
    blocker lived in a queue row's `blockedBy` prose, where that enumeration structurally could
    not see it. An audit that draws its population from the field the defect avoids is a green
    that never visited the defect. Enumerate from the UNION.

(b) THE OWNER-BLOCKER DETECTOR MUST NOT MATCH SUBSTRINGS ACROSS WORD BOUNDARIES. The first
    version here keyed on `"he "` among others, so it flagged `"the VRAM re-plan"` and
    `"the sigil lane"` — three false positives out of five reported violations, i.e. the check
    was mostly noise while looking like a finding. Word-boundary regex, and a phrase list that
    is about ownership rather than about English.

    The asymmetry that decides the tuning: a false positive costs a reader one glance at a row
    they then dismiss. A false negative is a decision the owner is never shown. So the list
    leans inclusive on genuine ownership words and refuses substring matching, rather than
    leaning conservative on both.

(c) RULE 8c CLOSING ENTRIES ARE NOT OPEN CARDS. `contract/DECISIONS.md` closes a decision by
    APPENDING an entry with `supersedes` set to the settled id and the identical question,
    options and recommend. So the ledger's closing entries look exactly like open cards to a
    naive reader — the first version here reported 38 open cards against a board with one.
    A card is OPEN only if nothing supersedes it AND it does not itself supersede something.

Exit codes (the house contract): 0 clean, 1 a check failed, 2 could not measure.
"""
from __future__ import annotations
import json
import os
import re
import sys

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS = os.path.join(AEON, "docs/lane-status.json")
LEDGER = os.path.join(AEON, "docs/decisions.jsonl")

# Ownership words, matched on WORD BOUNDARIES. Every entry names a person or an act only the
# owner performs; none is a common English fragment. See (b) above for why that matters.
OWNER_PHRASES = [
    r"\byour\b", r"\byou\b", r"\bowner'?s?\b", r"\bhis\b", r"\bhim\b",
    r"\bfeel\b", r"\btaste\b", r"\bruling\b", r"\bsign-?off\b", r"\bapproval\b",
]
OWNER_RE = re.compile("|".join(OWNER_PHRASES), re.I)


# The seven entries closed OUT OF SHAPE before rule 8c was being followed, and RULED
# 2026-08-30 by the hub as "do not repair" — rule 8 forbids rewriting, Dominion builds
# owner-facing cards only from `blockedOnOwner` joined by id so these reach him nowhere,
# and the first-class `answered` field supersedes the whole question. Full write-up in
# docs/OVERSEER.md, section "SEVEN LEDGER ENTRIES ARE CLOSED OUT OF SHAPE".
#
# They are EXEMPTED FROM CHECK 2 AND REPORTED ANYWAY, never silently skipped: an audit that
# hides what it forgave is an audit nobody can review. Adding an id here requires a RULING,
# not a judgement that it looks settled — the whole failure mode this list guards is a lane
# quietly deciding its own board is fine.
RULED_NOT_TO_REPAIR = {
    "d-45", "d-45-answered",
    "d-46", "d-46-downgraded",
    "d-47-revised", "d-47-revised-answered",
    "vram-replan", "vram-replan-deferred",
}


def load():
    try:
        status = json.load(open(STATUS))
    except Exception as e:
        print(f"AUDIT CANNOT MEASURE: {STATUS} did not parse: {e}")
        sys.exit(2)
    cards = []
    try:
        for n, line in enumerate(open(LEDGER), 1):
            line = line.strip()
            if line:
                cards.append(json.loads(line))
    except Exception as e:
        print(f"AUDIT CANNOT MEASURE: {LEDGER} line {n} did not parse: {e}")
        sys.exit(2)
    if not cards:
        print(f"AUDIT CANNOT MEASURE: {LEDGER} holds no entries — refusing to report a board "
              f"clean against an empty ledger")
        sys.exit(2)
    return status, cards


def open_card_ids(cards) -> set[str]:
    """Open = nothing supersedes it, and it is not itself a rule-8c closing entry."""
    superseded = {c["supersedes"] for c in cards if c.get("supersedes")}
    closers = {c.get("id") for c in cards if c.get("supersedes")}
    return {c.get("id") for c in cards
            if c.get("id") and c["id"] not in superseded and c["id"] not in closers}


def main() -> int:
    status, cards = load()
    by_id = {c.get("id") for c in cards if c.get("id")}
    fails: list[str] = []

    # ---- check 1, over the UNION of both fields -------------------------------
    claims = []
    for b in status.get("blockedOnOwner", []):
        claims.append(("blockedOnOwner", b.get("id"), b.get("what", "")))
    for q in status.get("queue", []):
        bb = q.get("blockedBy")
        if bb and OWNER_RE.search(bb):
            claims.append((f"queue[{q.get('id')}].blockedBy", None, bb))

    print(f"check 1 — owner-blocking claims, enumerated from blockedOnOwner AND every "
          f"blockedBy string: {len(claims)} found")
    for src, cid, txt in claims:
        if cid is None:
            fails.append(f"check 1/3: {src} states an owner blocker in prose ({txt!r}) and "
                         f"therefore carries no id and can have no card")
            print(f"  FAIL {src}: no id -> no card possible  {txt!r}")
        elif cid not in by_id:
            fails.append(f"check 1: blockedOnOwner {cid!r} has no card in the ledger")
            print(f"  FAIL {src}: id={cid!r} has NO CARD")
        else:
            print(f"  ok   {src}: id={cid!r} has a card")

    # ---- check 2 --------------------------------------------------------------
    surfaced = {b.get("id") for b in status.get("blockedOnOwner", [])}
    surfaced |= {p.get("id") for p in status.get("parkedQuestions", [])}
    opens = open_card_ids(cards)
    unsurfaced = opens - surfaced
    exempt = sorted(unsurfaced & RULED_NOT_TO_REPAIR)
    missing = sorted(unsurfaced - RULED_NOT_TO_REPAIR)
    print(f"check 2 — still-open cards: {len(opens)}; surfaced to him: "
          f"{len(opens & surfaced)}; unsurfaced: {len(unsurfaced)} "
          f"({len(exempt)} ruled not-to-repair, {len(missing)} to answer for)")
    for e in exempt:
        print(f"  known {e!r}: closed out of shape, hub-ruled 2026-08-30 not to repair")
    for m in missing:
        fails.append(f"check 2: card {m!r} is open but is on neither blockedOnOwner nor "
                     f"parkedQuestions — he is never shown it")
        print(f"  FAIL open card {m!r} is not surfaced anywhere")

    # ---- check 3 --------------------------------------------------------------
    bad = [(q.get("id"), q["blockedBy"]) for q in status.get("queue", [])
           if q.get("blockedBy") and OWNER_RE.search(q["blockedBy"])]
    print(f"check 3 — queue rows carrying an owner blocker in blockedBy prose: {len(bad)}")
    for qid, bb in bad:
        print(f"  FAIL {qid}: {bb!r}")

    print()
    if fails:
        print(f"AUDIT FAILED — {len(fails)} finding(s)")
        return 1
    print("AUDIT CLEAN — every owner-blocking claim carries a card, every open card is "
          "surfaced, and no queue row hides an owner blocker in prose")
    return 0


if __name__ == "__main__":
    sys.exit(main())
