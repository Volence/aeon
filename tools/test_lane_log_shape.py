"""Shape gate for `docs/lane-log.jsonl` — the notes this lane writes for the owner.

WHY THIS EXISTS (2026-09-10). On 2026-09-09 two entries were appended wrapped in a
single-element JSON ARRAY, `[{...}]` instead of `{...}`. The console that renders the
changelog reads one JSON *object* per line and skips anything that is not one, so both
notes were invisible to the owner from the moment they landed, while the file still
parsed as JSONL, git was happy, and every check in this repo passed. A peer lane found
it by reading the console's source. Nothing here could have: there was no lane-log
validator anywhere under `tools/` — checked with `git ls-files`, not a directory
listing, because a shell alias in this workspace turns a failed listing into what reads
as an empty one.

THE AUTHORITY IS THE HUB CONTRACT, NOT THIS FILE. Every assertion below is derived from
`contract/LANE_LOG.md` in the empyrean repo, read at a committed revision
(`git --git-dir=<empyrean>/.git show origin/main:contract/LANE_LOG.md`) and never
through the sibling working-tree path, which is a peer's live tree. Each assertion cites
the clause it came from at the assertion itself. If the contract moves, this file is
wrong until it is re-derived from the contract; do not re-derive it from this docstring.

THIS GATE REPORTS. IT NEVER REPAIRS.
Rule 7 of the contract makes the file APPEND ONLY, with a short closed list of legal
edits to an existing byte (heal a missing final newline; split a glued line; as of
2026-09-10, unwrap an array whose elements are all objects). Nothing here writes to the
log, proposes a rewrite, or auto-fixes anything. A gate that edits the artifact it
grades would be making the durable record say what should have been true, which is the
exact thing rule 7 exists to prevent.

WHAT THIS GATE CANNOT SEE, and it must not be read as having checked any of it:

  * It is a SHAPE check, not a CONTENT check. Rules 1 through 5 of the contract bind
    what `headline` and `matters` actually SAY — one entry per finished thing rather
    than per commit; no suite-invented code, identifier, or filename a stranger could
    not say out loud; no "X, not Y" contrastive correction; `matters` naming a
    consequence the owner can picture; no em or en dashes. NONE of that is checked
    here. A line can pass every assertion below and still be a note the owner cannot
    read, which is the failure the whole format was written to fix. The console runs
    its own lint for the checkable half of that (rules 2 and 5) and that lint lives
    there, not here.
  * It does not check whether an entry SHOULD exist. The implication runs one way
    only: IF a line exists it must be well formed. "These entries must exist" is the
    opposite claim, it pins content, and the contract names it explicitly as the form
    this check must not take.
  * It does not check `refs` or `detail` at all, and that is deliberate rather than an
    omission. The contract: "None of this can reject the note. Only `at`, `headline`,
    and `matters` can do that. A problem in `refs` (or in `detail`, held to the
    identical rule) costs that one field, set to 'did not say,' while the note itself
    survives in full." A gate that failed the build over a mistyped sha would be
    enforcing a cost the contract deliberately did not impose.
  * It does not check whether an `at` is in the FUTURE. Rule 6's SHAPE failure rejects
    a line outright; a shape-valid timestamp naming a moment more than a minute ahead
    does not. The contract: "A timestamp the reader cannot trust keeps the note and
    loses only its place in time" — it renders in an Undated group instead. Failing
    the build for that would invent a cost the contract explicitly declined.
  * It ignores blank lines, and this is the one place it is LAXER than the contract's
    own text. Rule 7's posted verification recipe is
    `[json.loads(l) for l in open(f)]`, which raises on a blank line, so strictly a
    blank line is already a failure by that recipe. There are none in the file today.
    If one ever appears, this gate will stay green and the recipe will go red.
  * It reads the file on disk, not the committed blob, because that is what an append
    in progress looks like and what build.sh grades everywhere else.
"""

import hashlib
import json
import os
import re

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(AEON, "docs", "lane-log.jsonl")

#: The three fields that, and only which, can reject a note.
#: Contract, "The shape" field table: `at`, `headline`, `matters` are each "Required:
#: yes". Contract, "`refs`: three fields...": "None of this can reject the note. Only
#: `at`, `headline`, and `matters` can do that."
REQUIRED_FIELDS = ("at", "headline", "matters")

#: The exact literal shape `date -u +%Y-%m-%dT%H:%M:%SZ` produces.
#: Contract rule 6: "`at` must come from exactly `date -u +%Y-%m-%dT%H:%M:%SZ`... the
#: reader checks that the string carries the exact literal shape that command produces.
#: `date -Is -u` produces a trailing `+00:00` instead of `Z` and is rejected.
#: `new Date().toISOString()` produces milliseconds and is rejected too."
#: `\A`/`\Z` rather than `^`/`$` on purpose: `$` also matches before a trailing newline,
#: which would quietly accept a value this rule rejects.
AT_SHAPE = re.compile(r"\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


# --------------------------------------------------------------------------------------
# The exemption, and the shape of it is the point.
# --------------------------------------------------------------------------------------
#
# Two lines on master are known bad and are NOT this gate's to repair. Each is keyed by
# the sha256 of its own exact line bytes (newline excluded), so the exemption names those
# two specific lines and nothing else. Any other array-wrapped line, including a
# re-wrapped version of these two with a byte changed, hashes differently and fails.
#
# THE RELATION IS ONE-WAY, AND THAT IS THE WHOLE DESIGN. An exempt hash SUPPRESSES a
# defect if it is present. Nothing anywhere asserts that these hashes ARE present, that
# exactly two exemptions are used, or that the exempt lines are still broken. This repo
# has a booked instance of a guard that failed the build when someone fixed the bug it
# documented; "the known-bad lines must still be known-bad" is that same defect wearing a
# different hat, and it would make repairing the log a build failure.
#
# WHAT HAPPENS WHEN THE REPAIR LANDS: the unwrap rewrites those two lines, their bytes
# hash to something else, the two entries below stop matching anything, and this gate
# stays GREEN with zero edits. At that moment these two entries are INERT, not
# load-bearing, and the next reader should delete them. Until then, deleting them turns
# the build red on a defect nobody has been cleared to fix.
#
# WHY THE REPAIR IS NOT DONE HERE: rule 7 makes the log append only. When these two lines
# were found, the contract permitted exactly two edits to an existing byte (heal a missing
# final newline; split a glued line) and an unwrap was a third, so unwrapping them would
# have been a lane taking a self-serving reading of a contract it does not own. The hub
# has since RULED (empyrean origin/main e923e7d, 2026-09-10) that unwrapping an array
# whose elements are all objects is the third legal edit, so the repair is now permitted.
# It is still not performed by this gate, for two separate reasons: this parcel does not
# own the log (its repair is held by the controlling lane), and a gate that repairs what
# it grades can never report the defect it just erased.
EXEMPT_LINES = {
    # docs/lane-log.jsonl line 218 as of 2026-09-10: a well-written entry wrapped in a
    # single-element array, so the owner's console skipped it. Content is fine; only the
    # wrapper is wrong.
    "fb7da0dff12fc61cbbd6d4e82e9fb48b82679b4d009c069136c0210e536cc18e": {
        "dated": "2026-09-10",
        "reason": (
            "Array-wrapped entry from 2026-09-09. Repair is an unwrap, ruled the third "
            "legal edit by the hub on 2026-09-10 (empyrean e923e7d) but not this "
            "parcel's to perform. Inert the moment the unwrap lands."
        ),
    },
    # docs/lane-log.jsonl line 220 as of 2026-09-10: same defect, same day, same repair.
    "d5a28e1ab8a5e1f2ace469629e1c5e7b0901c1ca6bc7abceb68816fda06e0612": {
        "dated": "2026-09-10",
        "reason": (
            "Array-wrapped entry from 2026-09-09. Repair is an unwrap, ruled the third "
            "legal edit by the hub on 2026-09-10 (empyrean e923e7d) but not this "
            "parcel's to perform. Inert the moment the unwrap lands."
        ),
    },
}


# --------------------------------------------------------------------------------------
# The checker. Pure over bytes so the tests below can prove every arm on a fixture
# without touching the committed log, whose contract forbids rewriting it.
# --------------------------------------------------------------------------------------

def line_hash(raw_line):
    """sha256 of one line's exact bytes, newline excluded."""
    return hashlib.sha256(raw_line).hexdigest()


def split_lines(data):
    """(lineno, raw bytes) for every line, with a trailing empty final element dropped.

    A file ending in a newline splits to a final empty element that is not a line; a file
    NOT ending in one has a real last line here, which `trailing_newline_missing` reports
    separately.
    """
    parts = data.split(b"\n")
    if parts and parts[-1] == b"":
        parts.pop()
    return list(enumerate(parts, start=1))


def trailing_newline_missing(data):
    """True when a non-empty file does not end in a newline.

    Contract rule 7's append recipe: "an ordinary `>>` is only correct when the file
    already ends in a newline... When it does not, the new record is glued onto the last
    one and BOTH become one unparseable line: the previous session's entry is destroyed
    along with the new one, in a file whose contract forbids rewriting. Nothing in the
    format detects it."

    HONEST SCOPE. The contract does not state "the file must end in a newline" as a rule;
    it states that the appender heals a missing one BEFORE appending, so a file at rest
    without a final newline is a state the recipe survives. This assertion is therefore
    STRICTER than the letter of the contract. It is a precondition of the recipe rather
    than an invention: it is exactly the state in which a plain `>>` by anyone not
    following the recipe destroys a record, and rule 7 says nothing in the format detects
    it. This is the detector.
    """
    return len(data) > 0 and not data.endswith(b"\n")


def line_defects(raw_line):
    """Every contract defect in one line's bytes, as a list of human strings.

    Empty list means the line is well formed as far as SHAPE goes. See the module
    docstring for the large set of contract rules this deliberately does not check.
    """
    defects = []

    try:
        text = raw_line.decode("utf-8")
    except UnicodeDecodeError as exc:
        return ["not valid UTF-8: %s" % exc]

    if not text.strip():
        return []  # blank line; see the module docstring for why this is ignored

    # Contract, "The shape": "one JSON object per line, newest at the bottom".
    # Contract, "What a bad line costs": "A line that is not usable JSON... is rejected
    # outright".
    try:
        obj = json.loads(text)
    except ValueError as exc:
        return ["does not parse as JSON: %s" % exc]

    # Contract rule 7 unwrap clause (2026-09-10): aeon's lines "each held a single-element
    # ARRAY, `[{...}]`, which `laneLog.ts` skips as 'not a JSON object', so two
    # well-written reader-facing entries had been invisible to the owner for a day."
    # That clause also insists the wrapper is detected by PARSING, never by matching `[{`
    # or `}]`, "since a bracket-brace pair occurs inside any string value quoting JSON,
    # including an entry describing this very bug" — hence the isinstance check on the
    # parsed value rather than any text match.
    if not isinstance(obj, dict):
        return ["parses to a JSON %s, not an object; the owner's console skips it"
                % type(obj).__name__]

    for field in REQUIRED_FIELDS:
        # Contract, "What a bad line costs": "A line that is not usable JSON, or is
        # missing `at`, `headline`, or `matters`... is rejected outright".
        if field not in obj:
            defects.append("missing the required field %r" % field)
            continue
        value = obj[field]
        # DERIVED, NOT LITERAL, and flagged as such. The contract's reject list names
        # "missing". Treating a non-string or a blank string as missing comes from two
        # other clauses rather than from that sentence: the `refs` paragraph's own notion
        # of trust is "a commit id that is not a usable string", and the field table
        # defines `headline` as "One or two sentences" and `matters` as "What is different
        # for him now", neither of which a number, a null, or "   " can be. A note whose
        # required field carries no readable sentence has failed the one thing this file
        # exists to do just as completely as one that omitted the field.
        if not isinstance(value, str):
            defects.append("required field %r is a %s, not a string"
                           % (field, type(value).__name__))
        elif not value.strip():
            defects.append("required field %r is empty or whitespace only" % field)

    # Contract rule 6, quoted at AT_SHAPE above. Only reached when `at` is a real string;
    # a missing or non-string `at` is already reported, and reporting it twice would say
    # two things went wrong when one did.
    at = obj.get("at")
    if isinstance(at, str) and at.strip() and not AT_SHAPE.match(at):
        defects.append(
            "field 'at' is %r, which is not the exact shape "
            "`date -u +%%Y-%%m-%%dT%%H:%%M:%%SZ` produces (rule 6)" % at)

    return defects


def scan(data):
    """Every unexempted defect in a whole lane-log file, as a list of report strings."""
    findings = []

    if trailing_newline_missing(data):
        findings.append(
            "the file does not end in a newline: the next plain `>>` append glues the "
            "new record onto the last one and destroys both (rule 7)")

    for lineno, raw_line in split_lines(data):
        defects = line_defects(raw_line)
        if not defects:
            continue
        # One-way: an exempt hash SUPPRESSES. Nothing requires it to be reached.
        if line_hash(raw_line) in EXEMPT_LINES:
            continue
        for defect in defects:
            findings.append("line %d: %s" % (lineno, defect))

    return findings


def _read_log():
    with open(LOG_PATH, "rb") as handle:
        return handle.read()


def _log_present():
    # Contract rule 8: "A lane that has landed nothing yet writes nothing: this file
    # records landings, it is not a heartbeat." An absent log is a legal state, so its
    # absence is a skip and never a failure.
    return os.path.isfile(LOG_PATH)


def _skip_if_absent():
    import pytest
    if not _log_present():
        pytest.skip("this lane has written no notes yet; docs/lane-log.jsonl is absent, "
                    "which contract rule 8 makes a legal state")


# --------------------------------------------------------------------------------------
# The gate over the real file. Four assertions, one per contract failure mode, kept
# apart so a red run names WHICH rule broke instead of "the log is bad".
# --------------------------------------------------------------------------------------

def test_every_line_parses_to_a_json_object():
    """Contract, "The shape": one JSON object per line.

    This is the assertion that would have caught the 2026-09-09 array wrapping on the day
    it landed instead of a day later.
    """
    _skip_if_absent()
    bad = []
    for lineno, raw_line in split_lines(_read_log()):
        for defect in line_defects(raw_line):
            if "parse" in defect or "not an object" in defect or "UTF-8" in defect:
                if line_hash(raw_line) not in EXEMPT_LINES:
                    bad.append("line %d: %s" % (lineno, defect))
    assert not bad, (
        "docs/lane-log.jsonl carries %d line(s) the owner's console cannot render as an "
        "entry. This gate reports; it does not repair, and the log is append only (rule "
        "7).\n  %s" % (len(bad), "\n  ".join(bad)))


def test_required_fields_are_present_and_usable():
    """Contract field table plus "Only `at`, `headline`, and `matters` can [reject]"."""
    _skip_if_absent()
    bad = []
    for lineno, raw_line in split_lines(_read_log()):
        for defect in line_defects(raw_line):
            if "required field" in defect:
                if line_hash(raw_line) not in EXEMPT_LINES:
                    bad.append("line %d: %s" % (lineno, defect))
    assert not bad, (
        "docs/lane-log.jsonl carries %d line(s) the console rejects outright for a "
        "required field.\n  %s" % (len(bad), "\n  ".join(bad)))


def test_at_carries_the_exact_shape_rule_6_names():
    """Contract rule 6, the rule it says to get exactly right."""
    _skip_if_absent()
    bad = []
    for lineno, raw_line in split_lines(_read_log()):
        for defect in line_defects(raw_line):
            if defect.startswith("field 'at'"):
                if line_hash(raw_line) not in EXEMPT_LINES:
                    bad.append("line %d: %s" % (lineno, defect))
    assert not bad, (
        "docs/lane-log.jsonl carries %d timestamp(s) rule 6 rejects. Get them from "
        "`date -u +%%Y-%%m-%%dT%%H:%%M:%%SZ` verbatim; a rejected line does not "
        "partially land.\n  %s" % (len(bad), "\n  ".join(bad)))


def test_file_ends_in_a_newline():
    """Contract rule 7's append recipe. See `trailing_newline_missing` for the honest
    note that this is stricter than the letter of the rule."""
    _skip_if_absent()
    assert not trailing_newline_missing(_read_log()), (
        "docs/lane-log.jsonl does not end in a newline. The next plain `>>` append will "
        "glue the new record onto the last one and BOTH become one unparseable line, "
        "destroying an entry in a file whose contract forbids rewriting. The heal line "
        "in rule 7's recipe is the fix and it is the appender's to run, not this gate's.")


def test_the_whole_file_is_clean_or_exempt():
    """The union of the four above, so a defect class nobody thought to bucket cannot
    fall between them. The three field-classified tests filter by defect text; this one
    filters by nothing."""
    _skip_if_absent()
    findings = scan(_read_log())
    assert not findings, (
        "docs/lane-log.jsonl has %d shape problem(s):\n  %s"
        % (len(findings), "\n  ".join(findings)))


# --------------------------------------------------------------------------------------
# Self-tests over synthetic fixtures. These keep the gate from going vacuous: a checker
# that stopped detecting anything would leave the five tests above green forever, since
# the real file is clean. Every arm is proved on bytes constructed here, never by
# mutating the committed log.
# --------------------------------------------------------------------------------------

GOOD_LINE = (
    b'{"at":"2026-09-10T02:00:00Z","headline":"A thing finished.",'
    b'"matters":"You can see it on screen now."}'
)


def test_checker_accepts_a_well_formed_fixture():
    """The control. Without it, a checker that flagged EVERYTHING would pass all four
    red-side self-tests below."""
    assert scan(GOOD_LINE + b"\n") == []


def test_checker_flags_an_array_wrapped_line():
    findings = scan(b"[" + GOOD_LINE + b"]\n")
    assert len(findings) == 1 and "not an object" in findings[0], findings


def test_checker_flags_an_unparseable_line():
    findings = scan(GOOD_LINE[:-1] + b"\n")  # truncated: no closing brace
    assert len(findings) == 1 and "does not parse" in findings[0], findings


def test_checker_flags_each_missing_required_field():
    """One line per required field, so a checker that only ever looked at `at` cannot
    pass this."""
    for field in REQUIRED_FIELDS:
        obj = json.loads(GOOD_LINE.decode())
        del obj[field]
        findings = scan(json.dumps(obj).encode() + b"\n")
        assert any("missing the required field %r" % field in f for f in findings), (
            field, findings)


def test_checker_flags_an_unusable_required_field():
    """Non-string and blank-string arms of the DERIVED reading; see `line_defects`."""
    for bad_value, expected in ((17, "not a string"), ("   ", "empty or whitespace")):
        obj = json.loads(GOOD_LINE.decode())
        obj["headline"] = bad_value
        findings = scan(json.dumps(obj).encode() + b"\n")
        assert any(expected in f for f in findings), (bad_value, findings)


def test_checker_flags_a_malformed_at():
    """The two shapes rule 6 names by name, plus a hand-typed one."""
    for bad_at in ("2026-09-10T02:00:00+00:00",       # `date -Is -u`
                   "2026-09-10T02:00:00.000Z",         # toISOString()
                   "2026-09-10 02:00:00Z",             # hand typed
                   "2026-09-10T02:00:00Z\n"):          # why AT_SHAPE uses \Z not $
        obj = json.loads(GOOD_LINE.decode())
        obj["at"] = bad_at
        findings = scan(json.dumps(obj).encode() + b"\n")
        assert any("rule 6" in f for f in findings), (bad_at, findings)


def test_checker_flags_a_missing_trailing_newline():
    findings = scan(GOOD_LINE)  # no newline
    assert len(findings) == 1 and "does not end in a newline" in findings[0], findings


def test_checker_ignores_refs_and_detail_problems():
    """Contract: "None of this can reject the note." A gate that failed on a mistyped sha
    would enforce a cost the contract deliberately declined."""
    obj = json.loads(GOOD_LINE.decode())
    obj["refs"] = {"commits": [17, None], "queue": "not a list", "project": 3}
    obj["detail"] = 42
    assert scan(json.dumps(obj).encode() + b"\n") == []

    for refs in (None, {}, {"commits": []}, {"commits": None}):
        # Contract: absent, `null`, and `[]` are different claims and none is an error.
        obj = json.loads(GOOD_LINE.decode())
        obj["refs"] = refs
        assert scan(json.dumps(obj).encode() + b"\n") == []


def test_checker_does_not_reject_a_future_timestamp():
    """Contract: a timestamp naming a future moment "keeps the note and loses only its
    place in time" — it renders in an Undated group. Only rule 6's SHAPE failure rejects.
    """
    obj = json.loads(GOOD_LINE.decode())
    obj["at"] = "2099-01-01T00:00:00Z"
    assert scan(json.dumps(obj).encode() + b"\n") == []


def test_exemption_suppresses_only_its_own_exact_bytes():
    """The exemption is keyed by content hash, so a DIFFERENT bad line is never covered
    by it — including the same defect with one byte changed."""
    exempt_line = None
    for _, raw_line in (split_lines(_read_log()) if _log_present() else []):
        if line_hash(raw_line) in EXEMPT_LINES:
            exempt_line = raw_line
            break
    if exempt_line is None:
        # The repair landed and the exemptions are inert. Nothing to prove and nothing
        # is wrong: this arm going quiet is the DESIGNED end state, never a failure.
        return
    assert scan(exempt_line + b"\n") == [], "an exempt line must be suppressed"
    nudged = exempt_line + b" "  # same defect, one byte different, hashes differently
    assert scan(nudged + b"\n"), "a near-miss of an exempt line must still be reported"


def test_the_exemption_table_is_self_describing():
    """The exemption entries themselves, not the log.

    Deliberately NOT asserted here, and this is the sharp part: nothing checks that the
    table is non-empty, that it has exactly two entries, or that its hashes appear in the
    file. All three would fail the build the day someone repairs the lines the table
    documents, which is a defect this repo has already booked once.
    """
    for digest, note in EXEMPT_LINES.items():
        assert re.fullmatch(r"[0-9a-f]{64}", digest), digest
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", note["dated"]), note
        assert note["reason"].strip(), digest
