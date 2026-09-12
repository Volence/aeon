# Aeon overseer handoff, 2026-09-12 tenth session (booted 19:16Z after the owner's clear)

**Read this, then `docs/lane-status.json`, then `docs/DEFERRED_WORK.md`.** Supersedes "Next, in order" of
`docs/superpowers/2026-09-12-aeon-overseer-handoff-9.md`. Every SHA is on aeon `origin/master` unless marked.
Stopped by the owner's clear rule; see "Why it stopped".

## THE FIRST THING TO DO, BEFORE ANYTHING ELSE

**Check whether the owner's main checkout is still behind, and re-measure it — do not inherit this number.**

```sh
git -C /home/volence/sonic_hacks/aeon fetch -q origin
git -C /home/volence/sonic_hacks/aeon rev-list --left-right --count HEAD...origin/master
```

At 19:16Z it was **0 ahead / 130 behind** (the `WORKING-COPY-CATCHUP` card said 63 that morning — it doubled
in six hours). **Your boot read of `DEFERRED_WORK.md` out of the main tree will be stale by hundreds of lines
if it is still behind.** Read the queue at `origin/master` (`git show origin/master:docs/DEFERRED_WORK.md`),
not through the working tree. This session's first boot read was 485 lines out of date and only caught it by
checking.

That card is **blocked on the owner** and now carries **three** consequences, the third found this session and
the worst of them: see `docs/decisions.jsonl`, the latest `WORKING-COPY-CATCHUP` entry (there are three; take
the newest, `at` 2026-09-12T19:44:47Z).

## Landed this session — six parcels/commits, all pushed and read back out of the remote

| what | merge | evidence |
|---|---|---|
| **A2 follow-ups** (MEV_EXT mirror pin, MEV_MACRO refusal + the +59 alias pin, the stale `engine.inc` name) | `794beef8` | `7e33cd19` — four shapes `finished=0`, zero bytes, Z80 clobbers gate 5/5 |
| **F3 dead ROM** (`SfxTable`'s dead cells + ALL SIXTEEN `_Patches` embeds) | `0e05e2c0` | `7d6809b4` — **−932 B**, every size predicted before measured |
| **owed runtime witnesses** (A2-9b, A2-11b, A2-17b all measured) + `tools/cart_identity.py` | `ddd67c6b` | ⚠ see the note below this table |
| the `carry:` convention **RULED** and written into `CODING_CONVENTIONS.md` §2.8 | `454682fe`, `538c6d57`, `f4471190`, `9608fde8` | — |
| sigil's two answers banked; both of our findings were malformed | `9ef66936` | — |
| `CART-VERIFY-COVERAGE` booked, then corrected | `f6f37fba`, `cc0554f2`, `8947f93f` | — |

> **⚠ STATUS OF THE THIRD PARCEL AT THE MOMENT THIS FILE WAS WRITTEN — verify it, do not assume it.** The
> merge commit `ddd67c6b` exists on the landing branch `land/0912-s10c` in `/home/volence/sonic_hacks/.aeon-land-s10`,
> and its four-shape run was **still in flight** when this was committed. **Check whether it reached
> `origin/master`:**
>
> ```sh
> git -C /home/volence/sonic_hacks/aeon fetch -q origin
> git -C /home/volence/sonic_hacks/aeon log origin/master --oneline -3
> git -C /home/volence/sonic_hacks/aeon merge-base --is-ancestor ddd67c6b origin/master && echo LANDED || echo NOT LANDED
> ```
>
> If **NOT LANDED**: the merge is done and conflict-resolved (that was the expensive part) and what is missing is
> only the four-shape evidence. Re-run it from that tree — `tools/landing_build.sh .runlogs/<name>.log`, with
> `SIGIL_BUILD`/`SIGIL_EMIT` exported — and **expect the F3 sizes unchanged**, because the parcel is tools + docs:
> `s4` 820223 / `s4.debug` 846601 / `demo` 97109 / `demo.debug` 103501, md5s `d021c1da` / `0a5c8897` / `a8a84b6f`
> / `b4443af7`. Anything else is a finding, not a rounding note. The Z80 clobbers gate is **not** required (none
> of its seven inputs moved) and the effects ritual does not apply.
> **The parcel's own work is safe either way**: branch `witness/owed-runtime-0912c`, tip `973c24c2`, reachable in
> the shared `.git`.

## Next, in order

1. **`CART-VERIFY` — and the remedy now has a reference implementation in this tree.** `tools/cart_identity.py`
   (from the witness parcel) compares `romBytes` **and reads the whole cart back**, because these four shapes
   hold their sizes across landings so a length match is not an identity. **Three witnesses call it; ~62 other
   bus-touching tools do not.** The leverage is `tools/aether_instance.py`, the spawner they all go through —
   put it there and the hand-rolled copies collapse into it. Prove it red-first by pointing a witness at a
   different ROM and requiring `UNMEASURABLE`. Row: `CART-VERIFY-COVERAGE` in `DEFERRED_WORK.md`.
2. **`CARRY-CONVENTION` — the rule is landed, the RENAME is not.** 18 declarations across 9 files; 10 already
   carry-SET, **5 due for rename** (`found` ×4 on the three VolEnv resolvers and `Sfx_MusicChanPtr`, plus `ok`
   on `Snd_DacLookup`), 3 neutral (`music`, `gliding`, `target_below`). **Re-derive every one from its BODY,
   not from its comment** — that is binding, not advice: four correct comments sat directly above four wrong
   declarations, so a parcel classifying from comments reproduces the original error with every citation
   accurate. Move the 12 comment echoes and every `@discards(<label>)` site with each rename. Should be
   zero-byte; prove it.
3. **`BLOCKER2-REWRITE` (S).** `sound_fm.emp`'s blocker 2: three ops released (`pop af`, `bit n,r`, `add a,n`),
   two still refused by name (`call`/`rst` → `[cycles.opaque-call]`, `ret` → `[cycles.path-end]`) for a reason
   no table row can fix. Neither "closed" nor "stands".
4. **F3's RUNTIME-TAG, foreground only.** A green build cannot observe reachability: if anything *had* read
   those 932 bytes, deleting them changes behaviour and no build sees it. Boot `s4.debug.bin` and fire the 16
   SFX ids listed in the F3 row. **SFX need no off-canonical shape; only music does.**
5. **`GAP12-A2-9d`** (new, from the witness parcel): Moving Trucks loads a real FM6 music channel but with
   `SND_FM6_ADAPTIVE = 0`, so a DAC sample ending under it gets neither the `$2B` hand-back nor the FM6 re-key.
   Song flag or gate width — an open call. And **still unmeasured**: whether a song loaded over a half-finished
   fade inherits the faded-down master volume (`SND_MASTER_FADE` is outside the mirror window; the YM TL stream
   would settle it).
6. **Riders the F3 parcel booked** (all byte-neutral, all real): `sfx_transcode.py` still writes 16
   `sfx_NN_patches` files nothing reads, and still has `emit_sfx_table_asm` emitting into a `sfx_table.asm`
   **that exists nowhere**, with `TestSfxTableComplete` grading that generator's output string — a gate that
   outlived its subject. Plus the SFX block's size/base stale in four places, and the elided trailing
   `item_align` pad.
7. **`PER-GAME-BAND-DEFINES`** — the queue's standing `next` before this session's work arrived.
8. **Owner cards, none answered:** `WORKING-COPY-CATCHUP` (read the NEWEST of its three entries),
   `SECTION-EFFECTS-VISUAL`, `VRAM-FOR-OBJECTS`, `CTRL-3`, `EFX-2`, `CHAR-10`, `SP6-MODULATION-DIVERGENCE`.

## Things in the TREE that are wrong, found this session and not all fixed

- **`tools/aether_instance.py`'s handshake table is stale in four places** and one would block a parcel: it
  states flatly that `breakpoint_add` / `wait_for_break` **do not exist**. Measured today: `oracle-rs`, **61**
  methods not 41, `breakpoints: true`, plus a `watchpoints` capability the table omits entirely — which is the
  instrument all three new witnesses run on. Corrected comment-only by the witness parcel; **its stated
  retirement condition for rung 2 of `assert_rust_server` is now MET**, and deleting that rung has its own test
  and was deliberately not done in passing.
- **`Dbg_Music_On` is `$FFFFEC46`, not `$FFFFE10E`** — the wrong address is in session memory
  (`reference_no_music_in_canonical_shapes`) and I passed it to an agent in a brief.
- **The "746 EQU lines" figure is stale**: 797 in `s4.debug.lst`, 802 in the config-A listing.
- **`docs/lens-findings.jsonl` has duplicate ids by convention** — 231 rows, ~125 distinct ids. **Any merge of
  it must be resolved LINE-WISE, never keyed by id**, or rows collapse silently.
- **A 512-hit `watchpoint_hits` page overruns the Aether client's 64 KiB line limit and kills the connection
  mid-run.** Use 100 and carry the `cursor`. Also: `dropped` on a watch is **not** "did I lose hits" — a gap in
  `seq` is the real check.

## The shared-machine incident, and what was and was not established

An agent ran **`pkill -f "sigil.*--native"` at ~19:25Z** and self-reported it, unprompted. The pattern is
unanchored, so it matches **any** lane's sigil invocation.

**Established:** no tree was removed or written. It kills processes, not files. All three undeclared sigil-side
worktrees present with mtimes predating the window, 0 prunable entries, worktree count up by exactly the five
trees this session created. The F3 agent **was** hit — a control run with `LANDING_RC=143`, one of four "Build
complete", **no `finished=` stamp** and three artifacts missing — and caught it itself, archived the log,
relaunched under `setsid`, and used nothing from it. The witness agent checked and was not hit.

**Sigil's amendment, which is the more useful half:** these builds live *seconds*, so a killed one presents as
**a legitimate build FAILURE**, not a truncated pass — and the expensive outcome is somebody investigating an
error that never happened or booking a defect the tree does not have. **All agents are now told `pkill -f` is
not available here**; ownership goes through `/proc/<pid>/cmdline` argv and kill by PID.

## THE METHOD LESSON OF THIS SESSION, and it is about numbers

**I published wrong numbers five times. Each was plausible, quotable, and alarming in the right direction.**

1. `0 of 54` tools verify the cart — a loop over an unquoted variable matching nothing. Caught only by a
   **positive control** that had to hit all 54 and returned 0 too. Minutes from being sent to a peer and the owner.
2. `31 of 54` — the matcher included `rom_bytes`, which hits `int.from_bytes(...)`. Caught only by trying to
   *show* the matching lines.
3. `40 of 54` — **denominator** wrong: population enumerated by what a file *mentions*, missing 17 tools that
   import `BusClient` directly. **Fixing the matcher twice did not make me question the population once.**
4. `30 carry: declarations across 11 files` — population B (which sweeps in 12 comment echoes). Sigil
   independently reported 30 and **I took the agreement as corroboration**; it was two *different* wrong
   populations totalling the same. The real count is **18 across 9**.
5. `cell:` count 6 / `_Patches` 2 on the merged tree, which read as a failed merge — my matcher was hitting the
   agent's own *comments documenting the deletion*.

**And one regression, also mine:** the F3 ledger merge I hand-wrote used `json.dumps(..., sort_keys=True)`,
which re-serialized all 222 rows — reordering every key and escaping the raw non-ASCII in 20 of them, against
that file's own `ensure_ascii=False` convention. Semantically lossless, 222 lines of churn. Found by comparing
against the base while resolving the *next* conflict, and fixed by rebuilding from each side's verbatim bytes.

**The operative rules, earned rather than quoted:**
- **Run a positive AND a negative control in the same loop shape as the real question.** A failing command and
  an empty world produce identical output.
- **A peer's count matching yours is the moment to ask what each of you enumerated over, not to stop asking.**
- **Cite the span, not the gap** — sigil and I disagreed 8-vs-9 on two lines' distance and both were right; the
  thing being measured was three lines long and neither of us recorded which line we anchored on. *A count
  beside an artifact is evidence about an ANCHOR, never about the artifact.*
- **The row is still actionable because the numerator never moved.** `40 of 54` and `49 of 65` are different
  numbers and the same finding. Sigil published three populations and got **zero** every time. A conclusion
  invariant across independent wrong framings is what is worth acting on — not the latest figure. **Re-derive
  any number in this session's work before quoting it.**

## Merging a half-owned doc — this came up THREE times and cost real care each time

Every parcel touched `DEFERRED_WORK.md` and `lens-findings.jsonl`, and **both sides always edited different
bullets of the same list.** Taking either side whole silently drops the other's. Each was resolved by
**composing the union from each side's verbatim text**, then auditing that every dropped line had a *named*
superseding line. For the ledger: prove each side a pure append (or enumerate exactly which base lines it
rewrote) **before** composing, resolve line-wise, and take each agent's own bytes rather than re-serialising.

## What peer work this session depended on

Sigil answered two questions, then **re-opened its own answers three times against itself** — the adjacency
finding that reframed the `carry:` rule, the census reconciliation, and the Rust instance that gave the rule its
cross-language evidence (verified here at `cbe10440^`, not transcribed). Four of my five wrong numbers were
caught by a peer re-running something I handed them. **A fresh session does not have that and should not assume
this session's figures were checked by anyone.**

## Why it stopped

Owner rule (2026-09-11T23:19:31Z / 23:20:23Z). **MEASURED from the transcript usage record: 388,322 tokens at
2026-09-12T20:18Z** (`input 2 + cache_read 387,454 + cache_creation 866`), well past the ~200k line and past the
279k where session 9 stopped. No wave was dispatched after that measurement; the three in-flight parcels were
landed and then this file was written.

## Housekeeping

- **KEPT:** `.aeon-land-s10` (this session's landing tree, detached/clean), `.aeon-card-fix` (a clean
  `origin/master` checkout used for docs landings), `.sigil-pin-6884bfba` (the clean sigil checkout the Z80 gate
  runs from), `.aeon-landing-sigil-target` (its private cargo target), `.aeon-ls9-land`, `.aeon-ls8-land`.
- **DO NOT SWEEP** `.aeon-sigil-ref`, `.aeon-sigil-gates`, `.sigil-ref-197-mine` — sigil-side, undeclared in
  aeon's `worktree list`, and a prune driven by that list cost sigil a tree on 2026-08-27.
- The three agent worktrees under `aeon/.claude/worktrees/` and their branches are left for the next session to
  reap; each parcel's tip is an ancestor of master.
- The owner's main checkout was not touched beyond `docs/lane-status.json`.
