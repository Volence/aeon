# The drift record — aeon's half of sigil's nightly byte-identity watch

`tools/drift_record.jsonl` and its reader `tools/drift_record.py`.

## What the record is for, in one paragraph

sigil's nightly job (`sigil/scripts/nightly_ref_drift.sh`) provisions a reference
checkout of this engine at a committed revision, builds all four ROM shapes with a
freshly-compiled assembler, and CRCs them. Then it asks somebody else what it should have
got. **It holds no expectation of its own and is built so it cannot acquire one** — a
drift job whose expectations it generated itself measures nothing, which is the failure
the whole exercise exists to retire. Every expectation enters through the one command
named by `DRIFT_RECORD_READER`. That command is ours. Until it existed, the job reported

```
STATUS: NOTHING MEASURED — no drift record is configured
```

with a non-zero exit, no chain credited. That was correct behaviour and **not a result**.

## The protocol

Sigil's, defined at `sigil/docs/DRIFT_RECORD_SEAM.md`. Read it at a committed revision —
that tree is a peer's live working directory. Re-derived from their actual caller
(`sigil/scripts/drift_report.py`, `_reader()` / `classify()`, at `8acee94a`):

| invocation | stdout | exit |
|---|---|---|
| `<reader> shapes` | one shape name per line | 0 |
| `<reader> lookup <aeon_rev> <sigil_rev>` | `<shape> <crc8> <size>` per line | 0 hit / 3 no entry |
| `<reader> lookup-aeon <aeon_rev>` | `<sigil_rev> <shape> <crc8> <size>` per line | 0 hit / 3 no entry |
| `<reader> has-sigil <sigil_rev>` | — | 0 hit / 3 none |

**Exit 2 from any verb means the reader could not answer** and is never treated as "no
drift": the job records NOTHING MEASURED and names the failing verb.

**There are FOUR verbs, not one.** A brief that quotes only `lookup-aeon` is quoting the
verb case 2 runs on — the load-bearing one — but a reader implementing only that verb
would fail the job's `shapes` call before it ever got there.

Revisions are full 40-character lowercase SHAs. `crc8` is eight lowercase hex digits of
CRC32; identity in this suite is CRC32 + size, never SHA1.

`<sigil_rev>` is the assembler's **closure revision** — `closure-revision` from
`sigil --version`, the last commit touching the paths cargo actually compiles that binary
from. Not `HEAD`, and not the `revision:` field: `revision` moves on every commit in that
repository including docs-only ones no compilation can see, so keying on it makes two
byte-identical assemblers look like two and manufactures misses that carry no evidence.
The reader keys `lookup` and `has-sigil` on the closure revision only.

### The three exits are not decoration

Their `_reader()` maps 3 to "no entry" and every other non-zero to `ReaderUnavailable`.
"No entry" is a **clean miss** and is quiet. "Could not answer" is **NOTHING MEASURED**
and is loud. A reader that cannot reach its data must report 2 and say why; returning 3
would let the caller read a broken record as quiet. Every unanswerable path in
`drift_record.py` exits 2 with a sentence on stderr, and `tools/test_drift_record.py`
pins each one.

One asymmetry worth knowing: **`shapes` has no miss code.** Their `record_shapes()`
discards the hit flag, so an exit 3 there would silently become "the record covers no
shapes" — coverage read out of an absence. The reader therefore never exits 3 from
`shapes`; an empty or unloadable record is 2.

## The bias direction, which is the reason for the schema

The record feeds a decision the owner is being asked to authorise: **whether the
sigil↔aeon byte-identity gate has become ceremony and can be retired.** The evidence for
retiring it is N chains observed quiet. So an error in this file is **not neutral** — a
spurious expectation makes a chain read as *quiet and evidence-bearing* that nobody
observed, and that errs toward "the gate is spent", which is exactly the conclusion
someone wants to reach.

Three structural properties hold that line. They are properties of the format and the
reader, not conventions anyone has to remember.

**1. This file holds expectations. It holds no observations and cannot.**
N is counted by `drift_report.py report` over sigil's **ledger**
(`$XDG_STATE_HOME/sigil-ref-drift/observations.jsonl`), which only the job writes and
which lives outside every repository. Nothing here can append to it. An entry in this
record can only turn a future observation the job actually makes from `unverified` into
evidence-bearing; it can never *be* one.

**2. An entry cannot spell "the drift job observed this".**
`origin` is required on every entry and its domain is the closed set in
`ORIGIN_IS_JOB_OBSERVATION`. Every member maps to `False`, and there is deliberately no
member mapping to `True`. The names someone would reach for to claim otherwise —
including `chain-188` — are listed in `REFUSED_ORIGINS` **by name**, and writing one does
not produce a wrong answer: it makes the whole record fail to load, so the reader exits 2
and the job reports NOTHING MEASURED. The distinction is a required field with a closed
domain, not a labelling nicety.

**3. Nothing automated writes this file.** The reader has no write verb. `measure` prints
a candidate row to stdout for a human to fill in, review and commit; it never touches the
record. That is the enforceable half of sigil's one constraint on our format — *"the
record must not mint an entry for a pair from the build that pair is about to be judged
against"* — because a file that only a reviewed commit can change cannot be regenerated
by the run about to be graded by it.

### Chain 188, specifically

The hub suggested chain 188 counts as chain one of the watch. Sigil refused and were
right: **the job did not observe chain 188, because the job was not installed.** That
refusal is preserved here mechanically — `origin: "chain-188"` is a refused name.

What chain 188's *engine revision* may perfectly well do is appear as an **expectation**.
That is not the same act, and conflating the two is the mistake in the other direction.
An expectation at aeon revision X does not advance N by any route; it makes a future
observation at X evidence-bearing rather than unverified. Crediting requires a row in
sigil's ledger, which only the job writes.

## What is in the record today, and what is not

Two entries, both `aeon-hand-measurement` — **this lane built these ROMs and CRCed them.
Neither is an observation of the drift job, and the job has still observed nothing.**

1. **`ec6a4791` / sigil `ec4c368d`, `s4_debug` only.** The relink datum of 2026-08-30
   (`docs/OVERSEER.md`): the sigil lane relinked the shared assembler across 41 commits
   while this lane sat at a boundary, and a rebuild at the same engine revision produced
   `s4.debug.bin 6516fc68/736315` — byte-identical. **A case-2 shape by hand, arrived at
   by accident**, and the population ordinary activity almost never produces.
   Only `s4_debug` is recorded because only `s4_debug` was built.

   *Not recorded: a row for the earlier assembler `85a5726c`.* Its CRC is known — it is
   the chain-188 golden — but that figure is **sigil's artifact**, and mirroring their
   goldens into this record would launder sigil's expectations back into the job that is
   supposed to be checked against ours. The record carries builds this lane ran.

2. **`d27ceba6` / sigil `ec4c368d`, all four shapes.** A provisioned worktree at aeon
   `origin/master`, built with the canonical `./build.sh` for each shape. This is the
   entry the next nightly actually exercises.

## The cadence: add an entry when AEON moves, never when sigil moves

This is not style. It is the condition under which sigil's case 2 works at all.

If the record gained an entry every time the assembler moved, every sigil-only move would
be a `lookup` **hit** against an expectation minted by the very build being judged, case
2 would collapse into case 1 with a self-authored expectation, and the job's ability to
see assembler drift would disappear **silently** — green, and measuring nothing.

**The ritual, at an aeon landing that moves ROM bytes:**

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
"$SIGIL_BUILD" --version > /tmp/v.before          # 1. pin the assembler's identity
./build.sh && DEBUG=1 ./build.sh                  # 2. build all four shapes
./build.sh demo && DEBUG=1 ./build.sh demo
"$SIGIL_BUILD" --version > /tmp/v.after           # 3. REFUSE if it changed:
diff /tmp/v.before /tmp/v.after || echo "relinked mid-measurement — no honest key"
python3 tools/drift_record.py measure . <the 40-char landed aeon SHA>
# 4. fill the placeholders, append to tools/drift_record.jsonl, COMMIT
```

Step 3 is not ceremony. `target/release/sigil` is shared across lanes and is relinked by
`cargo test --release --workspace` as readily as by `cargo build`; a relink mid-build
mis-keys the measurement with nothing visible in either tree.

The landed SHA does not exist until after the build. That is fine — the *tree* is what
produces the bytes, and a docs-and-tools-only merge does not move them. What is not fine
is recording a SHA whose tree differs from the one you built.

### ⚑ Why this ritual is a cost and not yet a fix

The job keys our half of the pair on `git rev-parse origin/master`, raw. **That is the same defect
sigil identified and fixed on their own half** — `revision` moves on commits no compilation can see —
**mirrored onto us, and unaddressed.** This lane commits docs all night. Measured 2026-08-30 while
this file was being written: `origin/master` moved `d27ceba6 → 07a97317` in three commits touching
only `docs/`. Identical bytes, and a `lookup-aeon` **miss**.

So without an entry per landing the steady state is `unverified` every night: N never advances and
the watch accumulates no evidence while appearing to run. The failure is **safe** — never quiet,
never a false red — but it is a real cost.

The obvious repair (resolve the queried `aeon_rev` to its ROM-path closure revision and match on
that) **widens every expectation to cover revisions nobody built, and errs toward more chains
counting as evidence-bearing** — the exact bias this record exists to resist. It is not this lane's
call. See `docs/DEFERRED_WORK.md` for the question as put to sigil and the owner.

## When the assembler legitimately moves bytes

Do **not** edit the old entry. It is a true statement about a build that happened. Land
the engine-side change, then add a **new** entry at the **new** aeon revision.

Two different CRCs at one aeon revision is a state the job reports as
`the-record-disagrees` rather than picking one, and that reading is correct: the record
has already recorded an assembler-caused move.

## Wiring it up (sigil's edit, not ours)

`DRIFT_RECORD_READER` is empty in `sigil/scripts/drift-nightly.conf`. The value:

```sh
DRIFT_RECORD_READER="/home/volence/sonic_hacks/.aeon-ref-drift/tools/drift_record.py"
```

**Not `"python3 <path>"`, and this is a real constraint rather than a preference.** Their
own harness — `crates/sigil-cli/tests/drift_nightly_harness.rs`,
`the_record_seam_is_empty_and_absence_is_not_a_pass` — asserts

```rust
reader.is_empty() || Path::new(&reader).exists() || reader.starts_with('/')
```

A `python3 …` string satisfies none of the three and fails that test: *"names nothing
runnable; an unusable reader must be empty rather than half-configured"*. So the reader is
committed **mode 755 with a `#!/usr/bin/env python3` shebang** and is invoked directly.
Their `_reader()` does `record_reader.split()`, so a bare absolute path becomes `argv[0]`
and the verbs append after it, exactly as intended.

**Read the reader out of the drift job's own reference tree** (`DRIFT_AEON_TREE`), not out
of `../aeon`. That tree is a peer's live working directory; the reference tree is a
worktree at aeon `origin/master`, so its record is the newest *committed* one and is
self-consistent with the revision being measured.

Two things for sigil to decide, flagged rather than guessed:

- **Ordering.** `DRIFT_RECORD_READER` is set above `DRIFT_AEON_TREE` in the conf, and the
  conf is *sourced*, so `"$DRIFT_AEON_TREE"` does not expand there. Either reorder or
  write the path literally.
- **Provisioning order.** The reader is called during `observe`, after provisioning, so
  the reference tree exists by then. If provisioning fails, the reader is missing and the
  job reports NOTHING MEASURED — which is the right answer, but it will read as a record
  problem rather than a provisioning one.

The reader is `cwd`-independent: it resolves the record next to its own file, overridable
with `--record` or `AEON_DRIFT_RECORD`.

## The gate

`tools/test_drift_record.py` runs in `build.sh`'s tool-suite lane
(`python3 -m pytest "${TOOLS}"`, build-fatal). It pins the three exits against each other,
the closed origin domain, every schema rule firing alone with its own name in the refusal,
the row shapes the caller unpacks, and the committed record's own validity.
