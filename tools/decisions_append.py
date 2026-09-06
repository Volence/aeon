#!/usr/bin/env python3
"""decisions_append — THE WRITE SITE for docs/decisions.jsonl. Checks the entry the way the
owner's reader will, BEFORE it is written; a non-conforming entry never reaches the file.

WHY THIS EXISTS (DEFERRED_WORK "LEDGER CONFORMANCE IS CHECKED OVER THE HISTORY AND NEEDS
CHECKING AT THE WRITE SITE", booked 2026-08-30): `decisions_conformance.py` measures how many
ledger lines Dominion rejects. It found 31 and cannot stop the 32nd, because it runs after the
fact and only when someone remembers to run it. `refreeze` has teeth because it sits where the
write happens and cannot be omitted; this is the same shape for the ledger. Every lane's
closures on 2026-08-30 parsed because the tool was run AFTERWARDS, not because they were
written against the reader.

THE PREDICATE IS IMPORTED, NOT COPIED: `decisions_conformance.reject_reasons` is the
transcription of Dominion `796bc1e` `server/src/decisions.ts` `parseEntry`; a second copy here
would be a third implementation that could drift from both. If this file refuses an entry the
reader would accept, the bug is in the transcription, and it is fixed there.

WHAT IS REFUSED (exit 1, EVERY reason printed, nothing written):
  1. any reader reject reason (`reject_reasons` non-empty);
  2. `at` missing, or not the exact `date -u +%Y-%m-%dT%H:%M:%SZ` shape. `--now` stamps it from
     the clock; a hand-typed value is accepted only if it already has the exact shape, and
     contract rule 7 says do not hand type it at all (three of six lanes once stamped minutes
     into the future);
  3. `supersedes` naming an id that no parseable line of the file carries;
  4. an id already in the file, reused by an entry that does not supersede it: the reader
     resolves repeated ids last-line-wins, so the earlier decision would be silently shadowed
     (contract 8c, "never reuse an id for a different decision");
  5. a CLOSURE (an entry carrying `answered`, or given `--closure`) whose reproduced
     question/options/recommend differ from the settled card (contract 8c) — the FIRST
     differing field is named. "Identical" is 8c's amended sense, identical in SUBSTANCE:
     the question byte-equal after trim; every settled option reproduced with equal
     key/name/what/costs (matched by key where the settled option has one, else by
     position); ADDED options are allowed, because 8d says "add the option, then chose it"
     and the amendment says a one-option card's closure supplies the second; `recommend`
     equal where the settled one is an object. Where the settled card itself does not parse
     (the 8c trap: reproducing it faithfully adds a second rejected line), the closure must
     be in the reader's shape AND say so in `detail`;
  6. an `answered` object the reader would silently DROP (8d: a malformed `answered` costs
     the field, not the line). At the write site that is worse than a rejection, because the
     line lands looking complete. So: `answered` must be an object; `answered.at` the exact
     clock shape; `answered.by` one of owner/hub/lane; `answered.chose` null or one of THIS
     entry's option keys. These are write-site rules BEYOND the reader's predicate and are
     labelled as such in the output.
  Rule 6 (no em/en dashes) in the linted fields is also refused here, because the reader's
  lint is advisory and the owner's instruction is standing.

THE APPEND ITSELF follows contract rule 8's recipe exactly: heal a missing final newline
first (the one legal edit to an existing byte), write ONE newline-terminated line, then
re-measure the whole file and confirm the line count grew by exactly one and the new last
line parses. A failure after the write is reported as such and exits 1; it does not roll
back (rule 8: rolling back discards the record too).

Usage:
  decisions_append.py [ENTRY.json | -] [--now] [--closure] [--check-only] [--ledger PATH]
  With no file argument the entry is read from stdin.

Exit codes: 0 appended (or --check-only and clean); 1 refused / post-write check failed;
2 could not read the entry or the ledger.
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decisions_conformance as conf  # noqa: E402  (the predicate lives there; do not copy it)

DASHES = ("—", "–")           # em dash, en dash — contract rule 6
LINTED = ("question", "recommend.because", "answered.did",
          "options[].name", "options[].what", "options[].costs")
ANSWERED_BY = ("owner", "hub", "lane")
WRITE_SITE = "(write-site rule beyond the reader: the reader would DROP this field silently)"


def clock_now() -> str:
    """The clock, never the caller's head: contract rule 7 names this exact command."""
    return subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True,
                          text=True, check=True).stdout.strip()


def load_ledger(path: str) -> list[tuple[int, dict | None]]:
    """(line, dict-or-None) for every physical line; None where the line is not an object."""
    rows: list[tuple[int, dict | None]] = []
    with open(path) as fh:
        for n, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
                rows.append((n, d if isinstance(d, dict) else None))
            except json.JSONDecodeError:
                rows.append((n, None))
    return rows


def last_line_with_id(rows, id_) -> tuple[int, dict] | tuple[None, None]:
    """The reader resolves a repeated id last-line-wins (`byId`); so do we."""
    for n, d in reversed(rows):
        if d is not None and d.get("id") == id_:
            return n, d
    return None, None


def dash_reasons(d: dict) -> list[str]:
    e = []

    def check(label, v):
        if isinstance(v, str) and any(c in v for c in DASHES):
            e.append(f"{label} carries an em or en dash (contract rule 6, standing owner instruction)")
    check("question", d.get("question"))
    if isinstance(d.get("options"), list):
        for i, o in enumerate(d["options"]):
            if isinstance(o, dict):
                for f in ("name", "what", "costs"):
                    check(f"options[{i}].{f}", o.get(f))
    if isinstance(d.get("recommend"), dict):
        check("recommend.because", d["recommend"].get("because"))
    if isinstance(d.get("answered"), dict):
        check("answered.did", d["answered"].get("did"))
    return e


def answered_reasons(d: dict) -> list[str]:
    """8d shape. The reader never rejects a line for these; it drops the field. Refusing here
    is the point of a write site."""
    a = d.get("answered")
    if a is None:
        return []
    e = []
    if not isinstance(a, dict):
        return [f"answered is not an object {WRITE_SITE}"]
    at = a.get("at")
    if not conf.nonempty(at) or not conf.AT_RE.match(at):
        e.append(f"answered.at is not the exact `date -u +%Y-%m-%dT%H:%M:%SZ` shape {WRITE_SITE}")
    if a.get("by") not in ANSWERED_BY:
        e.append(f"answered.by must be one of {'/'.join(ANSWERED_BY)}, got {a.get('by')!r} {WRITE_SITE}")
    chose = a.get("chose")
    if chose is not None:
        keys = {o.get("key") for o in d.get("options", []) if isinstance(o, dict)} \
            if isinstance(d.get("options"), list) else set()
        if chose not in keys:
            e.append(f"answered.chose {chose!r} names no option in this entry; add the option, "
                     f"then chose it (contract 8b/8d) {WRITE_SITE}")
    if not conf.nonempty(a.get("did")):
        e.append(f"answered.did is missing or empty {WRITE_SITE}")
    return e


def closure_reasons(entry: dict, settled: dict, settled_line: int) -> list[str]:
    """Contract 8c: a closure reproduces the settled card's question, options and recommend
    identically IN SUBSTANCE (amendment 2026-08-30). Returns at most the FIRST differing
    field, as the task ruled, plus the amendment's `detail` requirement when the settled card
    is itself out of shape."""
    where = f"(settled card is line {settled_line}, id {settled.get('id')!r})"
    settled_broken = bool(conf.reject_reasons(settled))

    sq = settled.get("question")
    eq = entry.get("question")
    if isinstance(sq, str) and isinstance(eq, str) and sq.strip() != eq.strip():
        return [f"8c: question differs from the settled card's {where}"]

    so = settled.get("options")
    eo = entry.get("options") if isinstance(entry.get("options"), list) else []
    if isinstance(so, list):
        by_key = {o.get("key"): o for o in eo if isinstance(o, dict) and conf.nonempty(o.get("key"))}
        for i, s in enumerate(so):
            if not isinstance(s, dict):
                continue
            if conf.nonempty(s.get("key")):
                c = by_key.get(s["key"])
                if c is None:
                    return [f"8c: options[{i}] (key {s['key']!r}) of the settled card is not "
                            f"reproduced; a closure may add options, never drop one {where}"]
            else:
                c = eo[i] if i < len(eo) and isinstance(eo[i], dict) else None
                if c is None:
                    return [f"8c: options[{i}] of the settled card is not reproduced {where}"]
            for f in ("key", "name", "what", "costs"):
                if conf.nonempty(s.get(f)) and s.get(f) != c.get(f):
                    return [f"8c: options[{i}].{f} differs from the settled card's {where}"]

    sr = settled.get("recommend")
    er = entry.get("recommend")
    if isinstance(sr, dict) and isinstance(er, dict):
        for f in ("key", "because"):
            if conf.nonempty(sr.get(f)) and sr.get(f) != er.get(f):
                return [f"8c: recommend.{f} differs from the settled card's {where}"]

    if settled_broken and not conf.nonempty(entry.get("detail")):
        return [f"8c amendment: the settled card does not parse for the reader, so this closure "
                f"must say in `detail` that the original was out of shape and what was supplied "
                f"{where}"]
    return []


def refusals(entry: dict, rows, is_closure: bool) -> list[str]:
    """Every reason the entry must not be written. Order: the reader's own reasons first."""
    e = list(conf.reject_reasons(entry))
    e += dash_reasons(entry)
    e += answered_reasons(entry)

    sup = entry.get("supersedes")
    if sup is not None:
        if not conf.nonempty(sup):
            e.append("supersedes is present but not a non-empty string (use null for none)")
        else:
            n, settled = last_line_with_id(rows, sup)
            if settled is None:
                e.append(f"supersedes names {sup!r}, which no parseable line of the ledger carries")
            elif is_closure:
                e += closure_reasons(entry, settled, n)

    id_ = entry.get("id")
    if conf.nonempty(id_):
        n, prior = last_line_with_id(rows, id_)
        if prior is not None and sup != id_:
            e.append(f"id {id_!r} is already on line {n} and this entry does not supersede it; "
                     f"the reader resolves repeated ids last-line-wins, so the earlier decision "
                     f"would be silently shadowed (contract 8c: never reuse an id for a "
                     f"different decision)")
    return e


# ── FILE-TIME CHECK AGAINST THE HUB'S OPEN LIST (aurora's mechanism, 2026-09-06) ──────
#
# WHY IT IS AT FILE TIME AND NOT AT DRAFT TIME. A card is drafted, then validated, then
# appended, and the hub can rule on the same question inside that window -- measured: it
# happened here, a card for `bganim-second-band-refusal` was drafted and passing
# validation when the ruling arrived, and filing it would have handed the owner a decision
# already answered and already on his card. **A draft's premise ages exactly like a peer's
# status file** (shared-protocol bar 22), so the check has to bind where the write happens.
#
# The near-miss is the argument for a MECHANISM rather than care: the same lane had
# deliberately declined to file a duplicate two hours earlier, on a judgement about whose
# question it was. That is the discriminator-that-fires-by-luck bar arriving on the very
# rule it had just applied on purpose.
#
# FAIL-SOFT, LOUDLY. An unreachable empyrean must not block a legitimate append, and must
# never be silently green: it prints that it COULD NOT CHECK, which is a different artifact
# from a clean check.
def hub_open_list_warnings(entry: dict) -> list[str]:
    """Lines to show the operator before the write. Empty means nothing matched."""
    id_ = str(entry.get("id", ""))
    q = " ".join(str(entry.get("question", "")).split())
    try:
        subprocess.run(["git", "-C", "../empyrean", "fetch", "-q", "origin"],
                       check=True, capture_output=True, timeout=60)
        # BOTH artifacts, and pointing at only the first was a measured defect. The
        # hub's BOARD carries standing rulings; their LOG carries the dated ones, and a
        # ruling that pre-empts a card drafted today is by definition recent, so it is in
        # the log. Measured at the moment this was written: OVERSEER.md held 0
        # recent ruling-shaped lines and OVERSEER-LOG.md held 142. Reading the board alone
        # made this check STRUCTURALLY UNABLE TO FIRE -- found by running a positive
        # control, not by reading the code.
        board = ""
        for path in ("docs/OVERSEER.md", "docs/OVERSEER-LOG.md"):
            board += subprocess.run(
                ["git", "-C", "../empyrean", "show", f"origin/main:{path}"],
                check=True, capture_output=True, text=True, timeout=60).stdout + "\n"
    except Exception as ex:
        return [f"COULD NOT CHECK the hub's open list ({type(ex).__name__}). That is NOT a "
                f"clean check -- it is an absent one. Read it by hand before filing: "
                f"git -C ../empyrean show origin/main:docs/OVERSEER.md"]
    out = []
    if id_ and id_ in board:
        out.append(f"the hub's board already NAMES `{id_}` -- it may already be ruled or "
                   f"listed for him; filing would be a second framing of one question")

    # THE DISCRIMINATOR, and its first version was USELESS -- kept as a comment because
    # the failure is the lesson. A per-token probe over 5+ char words matched a
    # ruling-shaped line for EVERY id tried, including the nonsense control
    # `a-question-nobody-has-asked-xyzzy` (3 warnings), because tokens like "second",
    # "question" and "refusal" are everywhere on a board made of rulings. A warning that
    # fires on every run trains the reader to skip it, which is strictly worse than no
    # warning: the bar against a refusal that can fire on a correct run, arriving on a
    # WARNING. Caught by running the negative control, not by reading the code.
    #
    # What replaces it: a token is only evidence if it is RARE on the board, and a ruling
    # is only relevant if it is RECENT. Both bounds are derived from what actually failed.
    lines = board.splitlines()
    recent = _recent_cutoff()

    # A RARE-TOKEN MATCHER WAS BUILT HERE AND WITHDRAWN. It filtered out tokens appearing
    # on more than a few board lines, which killed the fires-on-everything noise -- and
    # then STILL did not catch the case that motivated the whole check, because the
    # motivating card was about a topic the board had been discussing all day, so every
    # one of its words was common ("decouple" alone: 52 lines). **The rarity filter is
    # backwards for the case that matters: duplication is likeliest exactly where the
    # topic is hot, which is where the tokens are common.** Measured, not reasoned.
    #
    # So the matcher is gone and what replaces it makes NO relevance claim at all. The
    # failure was never a bad match; it was that NOBODY LOOKED. This prints the recent
    # rulings and makes the operator read them -- an instrument that cannot be vacuous
    # because it does not judge, and cannot fire wrongly because it does not fire.
    rulings = [ln.strip() for ln in lines
               if any(k in ln.lower() for k in ("ruled", "ruling", "his card"))
               and _stamp_is_after(ln, recent)]
    if rulings:
        out.append(f"{len(rulings)} ruling-shaped line(s) on the hub's board/log in the "
                   f"last {RECENT_HOURS}h. READ THESE before filing -- the check does not "
                   f"judge relevance, you do:")
        for ln in rulings[-RECENT_SHOW:]:
            out.append(f"    {ln[:150]}")
    else:
        out.append(f"no ruling-shaped lines on the hub's board/log in the last "
                   f"{RECENT_HOURS}h -- nothing recent could have pre-empted this card.")
    return out


#: How far back a ruling can be and still plausibly pre-empt a card drafted today.
RECENT_HOURS = 48
#: How many of the recent rulings to print. Bounded so the prompt stays readable; the
#: COUNT is always stated, so a truncated list announces itself rather than looking whole.
RECENT_SHOW = 8


def _recent_cutoff():
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone.utc) - timedelta(hours=RECENT_HOURS)


def _stamp_is_after(line: str, cutoff) -> bool:
    """True iff the line carries an ISO stamp at or after `cutoff`. No stamp -> False:
    an undated ruling cannot be shown to be recent, and guessing would re-introduce the
    fires-on-everything failure this replaced."""
    import re
    from datetime import datetime, timezone
    m = re.search(r"(20\d\d-\d\d-\d\d)(?:T(\d\d):(\d\d):(\d\d)Z)?", line)
    if not m:
        return False
    try:
        d = datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    if m.group(2):
        d = d.replace(hour=int(m.group(2)), minute=int(m.group(3)), second=int(m.group(4)))
    return d >= cutoff


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("entry", nargs="?", default="-", help="JSON file with ONE entry, or - for stdin")
    ap.add_argument("--now", action="store_true",
                    help="stamp `at` from the clock (overrides any value in the entry)")
    ap.add_argument("--closure", action="store_true",
                    help="treat as an 8c closure even without `answered` (enforces identity)")
    ap.add_argument("--check-only", action="store_true", help="validate, write nothing")
    ap.add_argument("--ledger", default=conf.LEDGER)
    ap.add_argument("--skip-hub-check", action="store_true",
                    help="do not consult the hub's open list (say why in the report)")
    args = ap.parse_args()

    try:
        text = sys.stdin.read() if args.entry == "-" else open(args.entry).read()
    except OSError as ex:
        print(f"CANNOT READ ENTRY: {args.entry}: {ex}")
        return 2
    try:
        entry = json.loads(text)
    except json.JSONDecodeError as ex:
        print(f"REFUSED: the entry is not valid JSON: {ex}")
        return 1
    if not isinstance(entry, dict):
        print("REFUSED: the entry is not a JSON object")
        return 1
    if "\n" in json.dumps(entry):
        # json.dumps never emits a raw newline; this is a belt for a braces-and-suspenders
        # file: one object, one line, or the next reader glues records.
        print("REFUSED: the serialised entry would span more than one line")
        return 1

    if args.now:
        entry["at"] = clock_now()
    try:
        rows = load_ledger(args.ledger)
    except OSError as ex:
        print(f"CANNOT MEASURE LEDGER: {args.ledger}: {ex}")
        return 2
    if not rows:
        print(f"CANNOT MEASURE LEDGER: {args.ledger} holds no entries; refusing to append "
              f"against a file this tool cannot see")
        return 2

    is_closure = args.closure or ("answered" in entry)
    reasons = refusals(entry, rows, is_closure)
    if reasons:
        print(f"REFUSED: {entry.get('id')!r} would not reach the owner's reader as written "
              f"({len(reasons)} reason(s); nothing was written):")
        for r in reasons:
            print(f"  - {r}")
        return 1

    # THE FILE-TIME CHECK. After validation and BEFORE the write, because that window is
    # exactly where a draft's premise goes stale. It WARNS rather than refuses: a genuine
    # second card on a related question is legitimate, and a refusal that can fire on a
    # correct run is worse than the silence it replaces. What it removes is the case where
    # nobody looked.
    if args.skip_hub_check:
        print("hub open-list check SKIPPED by flag -- say why in the report; a skipped "
              "check and a clean one are the same artifact to a later reader.")
    else:
        warns = hub_open_list_warnings(entry)
        if warns:
            print("⚠ HUB OPEN-LIST CHECK, at file time:")
            for w in warns:
                print(f"  - {w}")
            print("  If this question is already answered or already listed for him, do "
                  "NOT file: two framings of one decision means he answers one and the "
                  "other reads as dealt with. Re-check before proceeding.")
        else:
            print("hub open-list check: nothing on the hub's board names this id or a "
                  "ruling-shaped line matching it (checked at file time, not at draft).")

    line = json.dumps(entry, ensure_ascii=False)
    if args.check_only:
        print(f"OK: {entry.get('id')!r} would be accepted by the reader"
              f"{' as an 8c closure of ' + repr(entry.get('supersedes')) if is_closure else ''}; "
              f"--check-only, nothing written")
        return 0

    before = len(conf.physical_ids(args.ledger))
    with open(args.ledger, "rb+") as fh:
        fh.seek(0, os.SEEK_END)
        if fh.tell() > 0:
            fh.seek(-1, os.SEEK_END)
            if fh.read(1) != b"\n":
                fh.write(b"\n")           # rule 8: heal the newline the last writer owed
                print(f"healed a missing final newline on {args.ledger} before appending")
        fh.write(line.encode("utf-8") + b"\n")

    # The post-write check rule 8 demands: the file still parses line by line, grew by
    # exactly one line, and the new last line is accepted.
    after = conf.measure(args.ledger)
    ids = conf.physical_ids(args.ledger)
    n_last, id_last, reasons_last = after[-1]
    if len(ids) != before + 1 or n_last != before + 1 or reasons_last or id_last != entry.get("id"):
        print(f"POST-WRITE CHECK FAILED on {args.ledger}: lines {before} -> {len(ids)}, last line "
              f"{n_last} id {id_last!r} reasons {reasons_last}. STOP (contract rule 8): do not "
              f"commit; repair per the rule and re-measure.")
        return 1
    print(f"appended line {n_last}: {id_last!r} to {args.ledger} ({len(ids)} lines, parses)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
