#!/usr/bin/env python3
"""The aeon lane's drift record, and the reader sigil's nightly drift job calls.

WHAT THIS IS. `sigil/scripts/nightly_ref_drift.sh` builds this engine's four ROM shapes
at a committed aeon revision with a freshly-built assembler, CRCs them, and then asks
somebody else what it should have got. It holds NO expectation of its own and is built
so it cannot acquire one: every expectation enters through the single command named by
`DRIFT_RECORD_READER`, and when that command is absent the job reports NOTHING MEASURED
rather than a pass. This file is that command, and `tools/drift_record.jsonl` is the
record behind it. Until both exist their job credits no chain — which is correct
behaviour and is NOT a result.

THE PROTOCOL is sigil's, at `sigil/docs/DRIFT_RECORD_SEAM.md` (read it at a committed
revision; that tree is a peer's working directory). Re-derived here from their actual
caller, `sigil/scripts/drift_report.py` at 8acee94a:

    <reader> shapes                      one shape name per line              exit 0
    <reader> lookup <aeon> <sigil>       `<shape> <crc8> <size>` per line     0 hit / 3 miss
    <reader> lookup-aeon <aeon>          `<sigil> <shape> <crc8> <size>`      0 hit / 3 miss
    <reader> has-sigil <sigil>           no stdout                            0 hit / 3 miss

    exit 2 from ANY verb  =  the reader could not answer.

THE THREE EXITS ARE NOT DECORATION. `_reader()` in their caller maps 3 to "no entry" and
every other non-zero to `ReaderUnavailable`, which the job records as NOTHING MEASURED
naming the failing verb. So a reader that cannot reach its data MUST exit 2 and say why;
returning 3 would let the caller read a broken record as a clean miss, and a clean miss
is quiet. Every "could not answer" path in this file exits 2 with a sentence on stderr.

  ⚠ `shapes` HAS NO MISS CODE. Their `record_shapes()` discards the hit flag, so an
  exit 3 there would silently become "the record covers no shapes" — coverage read out
  of an absence. This reader therefore never exits 3 from `shapes`: an empty or
  unloadable record is 2.

WHY THE SIGIL REVISION THE JOB PASSES IS THE *CLOSURE* REVISION. Their caller runs
`classify(cmd, a.aeon_rev, a.sigil_closure_rev, measured)` — the last commit that touched
the paths cargo actually compiles the assembler from, read out of `sigil --version`, not
`git HEAD`. `revision:` moves on every commit in that repository including docs-only ones
no compilation can see, so keying on it would make two byte-identical assemblers look
like two different ones and would manufacture case-2 misses carrying no evidence.
So `lookup` and `has-sigil` match on `sigil_closure_rev` ONLY, and an entry whose closure
revision is genuinely unknown carries `null` and is never matched by them. It is still
served by `lookup-aeon`, where the revision is grouping and display rather than a key —
which is the verb case 2 runs on, so an unknown closure revision costs nothing that
matters.

── THE BIAS DIRECTION, WHICH IS THE POINT OF THE ORIGIN FIELD ──────────────────────────

This record feeds a decision: whether the sigil<->aeon byte-identity gate has become
ceremony and can be retired. The evidence for retiring it is N chains observed quiet.
So every error in this file has a DIRECTION: an expectation that should not be here
makes a chain read as "quiet AND evidence-bearing" that nobody observed, and that errs
toward "the gate is spent" — precisely the conclusion someone is hoping to reach. A
miscount here is not neutral.

Two structural consequences, both load-bearing:

1. THIS FILE HOLDS EXPECTATIONS. IT HOLDS NO OBSERVATIONS AND CANNOT.
   N is counted by `drift_report.py report` over sigil's LEDGER
   (`$XDG_STATE_HOME/sigil-ref-drift/observations.jsonl`), which only the job writes and
   which lives outside every repo. Nothing in this repository can append to it. An entry
   here can only ever turn a future observation the job actually makes from UNVERIFIED
   into evidence-bearing; it can never BE one.

2. AN ENTRY CANNOT SPELL "THE JOB OBSERVED THIS".
   `origin` is REQUIRED on every entry and its domain is the closed set `ORIGINS` below.
   Every member maps to `is_job_observation = False`, and there is deliberately no member
   that maps to True. The names someone would reach for to claim otherwise are listed in
   `REFUSED_ORIGINS` BY NAME, and writing one does not produce a wrong answer — it makes
   the whole record fail to load, so the reader exits 2 and the job reports NOTHING
   MEASURED. The distinction is a required field with a closed domain, not a convention.

   The occasion for that: the hub suggested chain 188 counts as chain one of the watch.
   Sigil refused, and they were right — the job did not observe chain 188, because the
   job was not installed. Chain 188's engine revision may perfectly well appear here as
   an EXPECTATION (that is what makes the first real observation at it evidence-bearing);
   what it may not do is appear as an observation, and the schema is why it cannot.

3. NOTHING AUTOMATED WRITES THIS FILE. There is no write verb. `measure` PRINTS a
   candidate row to stdout for a human to paste and commit; it never touches the record.
   That is the enforceable half of sigil's one constraint on our format — *"the record
   must not mint an entry for a pair from the build that pair is about to be judged
   against"* — because a file only a reviewed commit can change cannot be regenerated by
   the run that is about to be graded by it.

── CADENCE, AND WHAT A MISMATCH MEANS ──────────────────────────────────────────────────

An entry is added WHEN AEON MOVES, never when sigil moves. That is not style: it is the
condition under which sigil's case 2 works at all. If the record gained an entry each
time the assembler moved, every sigil-only move would be a `lookup` HIT against an
expectation minted by the very build being judged, case 2 would collapse into case 1, and
the job's ability to see assembler drift would disappear silently — green, and measuring
nothing.

A mismatch means one of two different things and the job already discriminates them:

  same pair, different CRC  — identical inputs on both sides gave different bytes.
                              Nondeterminism or an environment leak. A red.
  `lookup` misses, `lookup-aeon` hits — the assembler moved bytes under engine source
                              this record already covers. THE RED THE WHOLE JOB EXISTS
                              FOR, and the population step 4 needs.

WHEN THE ASSEMBLER HAS LEGITIMATELY MOVED BYTES — a deliberate encoding change, a
placement fix — the answer is NOT to edit the old entry. The old entry is a true
statement about a build that happened. Land the engine-side change, then add a NEW entry
at the new aeon revision. Two CRCs at one aeon revision is a state the job reports as
`the-record-disagrees` rather than picking one, and that is the correct reading: the
record has already recorded an assembler-caused move.

See `docs/DRIFT_RECORD.md` for the operator's half.
"""

import argparse
import json
import os
import re
import sys

HEX40 = re.compile(r"\A[0-9a-f]{40}\Z")
HEX8 = re.compile(r"\A[0-9a-f]{8}\Z")

SCHEMA = 1

DEFAULT_RECORD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "drift_record.jsonl")

# ── the closed origin domain ─────────────────────────────────────────────────────────
# Every entry declares one. The VALUE is what makes an unobserved chain structurally
# uncountable: no member is True, and a member that was True would be a claim this file
# is not able to make, because the observations it would be claiming live in a ledger in
# another repository's state directory that nothing here can write.
ORIGIN_IS_JOB_OBSERVATION = {
    # A build this lane ran by hand and CRCed, at a committed aeon revision, naming the
    # command in the entry. Not an observation of the drift job.
    "aeon-hand-measurement": False,
    # The build taken at an aeon landing, recorded as the expectation for that revision.
    # Also not an observation of the drift job.
    "aeon-landing": False,
}
ORIGINS = frozenset(ORIGIN_IS_JOB_OBSERVATION)

# Names someone would reach for to credit a chain the job never observed. Refused BY
# NAME so the refusal survives the reasoning that produced it. Writing one of these does
# not yield a wrong answer; it makes the record fail to load and the reader exit 2.
REFUSED_ORIGINS = {
    "sigil-nightly-drift-job":
        "the drift job's observations live in ITS ledger, not in this record",
    "drift-job-observation":
        "the drift job's observations live in ITS ledger, not in this record",
    "nightly-observation":
        "the drift job's observations live in ITS ledger, not in this record",
    "observed":
        "this record holds expectations; an observation is something the job makes",
    "chain-188":
        "the job did not observe chain 188 because the job was not installed; sigil "
        "refused this credit and were right",
}

# The four protocol verbs, exactly. `validate` and `measure` are aeon-local and are not
# part of sigil's protocol. NONE of them reports a count of chains, observations or
# nights: this record is not a place any such number can be read from.
PROTOCOL_VERBS = ("shapes", "lookup", "lookup-aeon", "has-sigil")
LOCAL_VERBS = ("validate", "measure")

REQUIRED_KEYS = ("schema", "aeon_rev", "sigil_linked_rev", "sigil_closure_rev",
                 "sigil_tree_state", "origin", "measured_on", "build", "shapes", "note")

TREE_STATES = frozenset({"clean", "dirty", "unknown"})

EXIT_OK = 0
EXIT_COULD_NOT_ANSWER = 2
EXIT_NO_ENTRY = 3


class RecordUnreadable(Exception):
    """The record could not be loaded. ALWAYS exit 2 — never 3, never 0."""


def _bad(where, why):
    raise RecordUnreadable(f"{where}: {why}")


def _check_shapes(where, shapes):
    if not isinstance(shapes, dict) or not shapes:
        _bad(where, "`shapes` must be a non-empty object")
    for name, v in shapes.items():
        if not isinstance(name, str) or not name:
            _bad(where, "a shape name must be a non-empty string")
        if not isinstance(v, dict) or set(v) != {"crc", "size"}:
            _bad(where, f"shape `{name}` must be exactly {{crc, size}}")
        if not isinstance(v["crc"], str) or not HEX8.match(v["crc"]):
            _bad(where, f"shape `{name}` crc must be eight lowercase hex digits "
                        f"(CRC32), got {v['crc']!r}")
        if not isinstance(v["size"], int) or isinstance(v["size"], bool) or v["size"] <= 0:
            _bad(where, f"shape `{name}` size must be a positive integer byte length, "
                        f"got {v['size']!r}")


def _check_entry(where, e):
    if not isinstance(e, dict):
        _bad(where, "an entry must be a JSON object")
    missing = [k for k in REQUIRED_KEYS if k not in e]
    if missing:
        _bad(where, f"missing required key(s): {', '.join(missing)}")
    extra = [k for k in e if k not in REQUIRED_KEYS]
    if extra:
        _bad(where, f"unknown key(s): {', '.join(sorted(extra))} — the schema is closed "
                    f"so a typo'd field cannot pass as data")
    if e["schema"] != SCHEMA:
        _bad(where, f"schema {e['schema']!r}, this reader understands only {SCHEMA}")
    for k in ("aeon_rev", "sigil_linked_rev"):
        if not isinstance(e[k], str) or not HEX40.match(e[k]):
            _bad(where, f"`{k}` must be a full 40-character lowercase SHA, "
                        f"got {e[k]!r}")
    cl = e["sigil_closure_rev"]
    if cl is not None and not (isinstance(cl, str) and HEX40.match(cl)):
        _bad(where, "`sigil_closure_rev` must be a full 40-character lowercase SHA or "
                    f"null when genuinely unknown, got {cl!r}")
    if e["sigil_tree_state"] not in TREE_STATES:
        _bad(where, f"`sigil_tree_state` must be one of {sorted(TREE_STATES)}, "
                    f"got {e['sigil_tree_state']!r}")
    origin = e["origin"]
    if origin in REFUSED_ORIGINS:
        _bad(where, f"`origin` {origin!r} is REFUSED: {REFUSED_ORIGINS[origin]}. This "
                    f"record holds expectations; N is counted by the drift job over its "
                    f"own ledger, which nothing in this repository can write.")
    if origin not in ORIGINS:
        _bad(where, f"`origin` must be one of {sorted(ORIGINS)}, got {origin!r}")
    if ORIGIN_IS_JOB_OBSERVATION[origin]:
        # Unreachable by construction, and it stays here so that adding a True member
        # trips over a refusal instead of quietly becoming expressible.
        _bad(where, f"`origin` {origin!r} claims a drift-job observation, which this "
                    f"record cannot hold")
    for k in ("measured_on", "build", "note"):
        if not isinstance(e[k], str) or not e[k].strip():
            _bad(where, f"`{k}` must be a non-empty string")
    if not re.match(r"\A\d{4}-\d{2}-\d{2}\Z", e["measured_on"]):
        _bad(where, f"`measured_on` must be YYYY-MM-DD, got {e['measured_on']!r}")
    _check_shapes(where, e["shapes"])


def load(path):
    """Load and fully validate the record. Raises RecordUnreadable -> exit 2."""
    if not os.path.exists(path):
        _bad(path, "the record file does not exist")
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError as exc:
        _bad(path, f"the record file could not be read: {exc}")
    entries = []
    for i, line in enumerate(raw.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        where = f"{path}:{i}"
        try:
            e = json.loads(s)
        except ValueError as exc:
            _bad(where, f"not valid JSON: {exc}")
        _check_entry(where, e)
        entries.append(e)
    if not entries:
        # NOT a miss. A configured reader over an empty record has no expectation to
        # offer, and letting that read as "no entry" would let an empty deployment pass
        # for a clean one.
        _bad(path, "the record holds no entries, so this reader has nothing to answer "
                   "with; that is an unanswerable state and not a clean miss")
    seen = {}
    for e in entries:
        k = (e["aeon_rev"], e["sigil_linked_rev"])
        if k in seen:
            _bad(path, f"two entries for the same build (aeon {k[0][:8]} / sigil linked "
                       f"{k[1][:8]}); one build has one set of bytes, so the record is "
                       f"ambiguous and this reader will not pick")
        seen[k] = e
    return entries


# ── the four protocol verbs ──────────────────────────────────────────────────────────

def verb_shapes(entries, _args, out):
    names = sorted({s for e in entries for s in e["shapes"]})
    for n in names:
        out.write(n + "\n")
    return EXIT_OK


def verb_lookup(entries, args, out):
    aeon, sigil = args
    rows = [e for e in entries
            if e["aeon_rev"] == aeon and e["sigil_closure_rev"] == sigil]
    if not rows:
        return EXIT_NO_ENTRY
    for e in rows:
        for shape in sorted(e["shapes"]):
            v = e["shapes"][shape]
            out.write(f"{shape} {v['crc']} {v['size']}\n")
    return EXIT_OK


def verb_lookup_aeon(entries, args, out):
    (aeon,) = args
    rows = [e for e in entries if e["aeon_rev"] == aeon]
    if not rows:
        return EXIT_NO_ENTRY
    for e in rows:
        # The caller groups on this token and prints it truncated; it never keys on it.
        # An entry whose closure revision is unknown is served under the revision the
        # assembler reported it was LINKED at, which is the honest coordinate we have.
        srev = e["sigil_closure_rev"] or e["sigil_linked_rev"]
        for shape in sorted(e["shapes"]):
            v = e["shapes"][shape]
            out.write(f"{srev} {shape} {v['crc']} {v['size']}\n")
    return EXIT_OK


def verb_has_sigil(entries, args, _out):
    (sigil,) = args
    return EXIT_OK if any(e["sigil_closure_rev"] == sigil for e in entries) \
        else EXIT_NO_ENTRY


# ── aeon-local verbs (NOT part of sigil's protocol) ──────────────────────────────────

def verb_validate(entries, _args, out):
    out.write(f"record OK: {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}, "
              f"{len(sorted({s for e in entries for s in e['shapes']}))} shape(s) "
              f"covered\n")
    out.write("this file holds EXPECTATIONS. N is counted by sigil's drift job over its "
              "own ledger;\nno number in this file is a count of anything the job "
              "observed.\n")
    for e in entries:
        cl = e["sigil_closure_rev"] or "closure-unknown"
        out.write(f"  aeon {e['aeon_rev'][:8]} / sigil {cl[:12]} "
                  f"[{e['origin']}] {sorted(e['shapes'])}\n")
    return EXIT_OK


def verb_measure(_entries, args, out):
    """PRINT a candidate entry for the ROMs in a tree. Never writes the record."""
    import subprocess
    import zlib
    tree, aeon_rev = args
    sigil_bin = os.environ.get("SIGIL_BUILD", "")
    if not sigil_bin or not os.path.exists(sigil_bin):
        _bad("measure", "SIGIL_BUILD must name the assembler binary that produced these "
                        "ROMs; the key names the binary that ran, not a git tip")
    ver = subprocess.run([sigil_bin, "--version"], capture_output=True, text=True)
    if ver.returncode != 0:
        _bad("measure", "the assembler cannot report its version, so this build has no "
                        "honest key")

    def field(name):
        m = re.search(rf"^\s*{re.escape(name)}:\s*(\S+)", ver.stdout, re.M)
        return m.group(1) if m else None

    linked, closure = field("revision"), field("closure-revision")
    tree_state = "clean" if "clean at capture" in ver.stdout else \
                 ("dirty" if "tree:" in ver.stdout else "unknown")
    if not linked:
        _bad("measure", "`sigil --version` reported no linked revision")
    names = {"s4": "s4.bin", "s4_debug": "s4.debug.bin",
             "demo": "demo.bin", "demo_debug": "demo.debug.bin"}
    shapes = {}
    for key, fn in names.items():
        p = os.path.join(tree, fn)
        if not os.path.exists(p):
            continue
        d = open(p, "rb").read()
        shapes[key] = {"crc": format(zlib.crc32(d) & 0xffffffff, "08x"), "size": len(d)}
    if not shapes:
        _bad("measure", f"no ROM shape was found under {tree}")
    entry = {
        "schema": SCHEMA,
        "aeon_rev": aeon_rev,
        "sigil_linked_rev": linked,
        "sigil_closure_rev": closure,
        "sigil_tree_state": tree_state,
        "origin": "aeon-hand-measurement",
        "measured_on": "YYYY-MM-DD",
        "build": "FILL IN the exact command that produced these ROMs",
        "shapes": shapes,
        "note": "FILL IN why this entry exists",
    }
    out.write(json.dumps(entry, sort_keys=True) + "\n")
    out.write("\n# NOT WRITTEN. Fill the placeholders, review, append to "
              "tools/drift_record.jsonl and COMMIT.\n"
              "# Nothing automated writes that file: an entry a nightly run could mint "
              "for itself is an\n# expectation authored by the build it is about to "
              "judge.\n")
    return EXIT_OK


VERBS = {
    "shapes": (verb_shapes, 0),
    "lookup": (verb_lookup, 2),
    "lookup-aeon": (verb_lookup_aeon, 1),
    "has-sigil": (verb_has_sigil, 1),
    "validate": (verb_validate, 0),
    "measure": (verb_measure, 2),
}


def main(argv):
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--record", default=os.environ.get("AEON_DRIFT_RECORD",
                                                       DEFAULT_RECORD))
    ap.add_argument("verb", nargs="?")
    ap.add_argument("args", nargs="*")
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        # argparse's own exit code is 2, which happens to be right, but say why.
        sys.stderr.write("drift_record: could not parse arguments\n")
        return EXIT_COULD_NOT_ANSWER
    if a.verb not in VERBS:
        sys.stderr.write(
            f"drift_record: unknown verb {a.verb!r}; known verbs are "
            f"{', '.join(PROTOCOL_VERBS)} (sigil's protocol) and "
            f"{', '.join(LOCAL_VERBS)} (aeon-local)\n")
        return EXIT_COULD_NOT_ANSWER
    fn, argc = VERBS[a.verb]
    if len(a.args) != argc:
        sys.stderr.write(f"drift_record: `{a.verb}` takes {argc} argument(s), "
                         f"got {len(a.args)}\n")
        return EXIT_COULD_NOT_ANSWER
    if a.verb in ("lookup", "lookup-aeon", "has-sigil"):
        for v in a.args:
            if not HEX40.match(v):
                sys.stderr.write(
                    f"drift_record: `{a.verb}` takes full 40-character lowercase SHAs; "
                    f"got {v!r}. Answering a short or malformed revision would be "
                    f"answering a different question.\n")
                return EXIT_COULD_NOT_ANSWER
    try:
        entries = load(a.record)
        return fn(entries, a.args, sys.stdout)
    except RecordUnreadable as exc:
        sys.stderr.write(f"drift_record: could not answer `{a.verb}`: {exc}\n")
        return EXIT_COULD_NOT_ANSWER


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
