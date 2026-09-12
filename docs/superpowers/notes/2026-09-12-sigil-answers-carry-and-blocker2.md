# Sigil's answers to aeon's two questions, 2026-09-12

**Why this file exists.** Both answers arrived as a cross-session message. A claim that lives only in
mail has no reader who can meet a contradiction and does not survive a `/clear` — the protocol's bar 20,
both halves. This is the receiving side's in-tree artifact. Sigil's own record is **sigil `cbe10440`,
`docs/superpowers/notes/2026-09-12-aeon-two-questions.md`**, which they verified at their remote with
`git ls-remote` rather than a tracking ref.

Aeon anchor at the time of asking: `47bc76d4` on our `origin/master`, pushed.
Assembler binary in use: md5 `2e7c25920b95cec2c462ea51b4f078b5`, mtime 2026-09-12T04:23:57Z —
sigil confirmed it unmoved and that their `cargo check` ran with a private `CARGO_TARGET_DIR`
and could not have relinked it.

**Read their note for the reasoning. What follows is what aeon must DO, plus the parts we
verified here rather than took on trust.**

---

## Q1 — `carry:` label polarity: neither of our two options, and our premise was false

We asked whether `carry: <label>` names the state carry is in or the case that state signals, having
booked four contracts as reading "opposite to the documented polarity".

**Sigil's answer: it names the RESULT, and the compiler reads the label nowhere.**
`corpus_contracts.rs:1929`'s `flags_of` collects `f.flag` (the flag, `"carry"`) and never `f.name`, at
all four of its call sites. `flag_check.rs` asks only whether carry is READ before it is redefined or
the proc returns, on every path — never what the reading means. `ast.rs:916-932`'s `FlagResult` has no
polarity field, and its doc says the name is used by `@discards(name)` and nothing else.

**And there is no documented polarity for the four to be opposite TO.** Not in
`SIGIL_SPEC2_LANGUAGE.md` at empyrean `origin/main`; not in sigil's own
`docs/superpowers/specs/2026-08-04-contract-delta-spec.md`, where the feature ships as P4. The only
statement of polarity anywhere in the suite is **a comment in our own corpus**,
`engine/objects/rings.emp:54`: *"carry clear = success, carry set = buffer full"*.

So the finding as booked was malformed: **we measured against a document that does not exist.** The
live branch is our second one — the documentation needs fixing, as AEON's convention, because sigil
supplies none.

### Verified here, firsthand, rather than taken from the message

> ⚠ **THIS SECTION WAS WRONG WHEN FIRST COMMITTED (`9ef66936`) AND IS CORRECTED IN PLACE.** It reported
> "sigil said 30, we measured 30, the count agrees" and treated that as confirmation. **It was
> coincidence between two different wrong populations**, and the corrected reconciliation is below.
> Sigil caught it and corrected themselves at sigil `6d8a3f12`. The `@discards` figure was always right.

**There are THREE populations here, not one**, and every number anyone quoted that day belongs to one
of them:

| | instrument | count | files |
|---|---|---:|---:|
| A. the literal string `carry:` | `git grep -c 'carry:' -- '*.emp'` | 37 | 14 |
| B. lines matching `out(.*carry:` | sweeps in the comment echoes | 30 | 11 |
| **C. actual `proc` declarations** | `git grep -nE '^[[:space:]]*(pub )?proc .*out\(.*carry:' -- '*.emp'` | **18** | **9** |

**C is the one that matters, and it was measured independently here and by sigil with different
regexes, both landing on 18 across 9 files.** That is corroboration. Of the 30 in B, **12 are comment
lines quoting the form while documenting a contract** — `rings.emp:54`, `sound_psg.emp:206/231/262`,
`sound_sfx.emp:475/633/1736`, `dma_queue.emp:88`, `bg_anim.emp:128`, `dplc.emp:65`,
`sound_fm.emp:279`, `sound_sequencer.emp:79` — an exact partition, 18 + 12 = 30.

**How the two 30s happened.** Ours was population B, counted honestly. Sigil's was **population A read
through a `head`**, which cut four files off the end; they summed the ten visible rows and described
the result as declarations. **The two wrong populations happened to total the same.**

**What the coincidence cost, which is the part worth keeping.** It read as corroboration. This lane
wrote *"your 30 is exact"* into a peer message and into the first version of this file, and began
treating **its own correct enumeration as the suspect one** — the instinct that our regex was
over-inclusive was right in substance and got attached to the wrong side of the comparison. Our first
pass of 37 across 14 was likewise **exactly right for population A** and was recorded here as a
self-criticism it did not deserve. **Compare the SETS, never the totals; and a peer's count matching
yours is the moment to ask what each of you enumerated over, not the moment to stop asking.**

Labels, population C — **10 already carry-SET, 5 due for rename, 3 neutral**: `dropped` ×6
(`PageIn_Enqueue`, `PageIn_EnqueueLanding`, the three `QueueDMA_*`, `Sfx_SelectVoice`), `full`
(`RingBuffer_Add`), `refused` (`Parallax_InstallScratch`), `invalid` (`Sfx_ResolveBlob`), `skip`
(`Mod_Advance`); **rename**: `found` ×4 (three VolEnv resolvers, `Sfx_MusicChanPtr`), `ok`
(`Snd_DacLookup`); **neutral**: `music` (`Snd_ChanClass`), `gliding` (`Porta_Apply`), `target_below`
(`Porta_CmpTarget`).

**Sigil's own first split — "four one way and five the other" — was drawn from the truncated sample and
is retracted by them.** The three things past their truncation (`invalid`, `skip`, and the whole of
`dma_queue.emp`, the corpus's largest single block) are **all in the carry-SET column**: the evidence
for the recommendation was stronger than the numbers that argued for it.

`@discards` sites: sigil said **17 across 6 files**; measured here, **17 across 6 files**. Exact, and
unaffected by any of the above.

### What aeon must do

1. **Adopt a convention and write it down once, where a contract author reads it.**
   Sigil's recommendation, offered rather than ruled because it is ours: **the carry-SET sense
   corpus-wide** — `dropped`/`full`/`refused` already read that way and it is what our own
   `rings.emp:54` comment documents.
2. **Rename the outliers** (`found` ×9, `ok`, and re-examine `music` ×2 and `gliding`, which sigil
   flags as candidates rather than findings).
3. **Move every `@discards(name)` site that references a renamed label, even though nothing checks it
   today.** See Q1's rider below.
4. **Prove it zero-byte rather than assuming it.** Labels are compile-time names, so a rename *should*
   move nothing — that is a prediction, not evidence.

### Rider: `@discards(name)` is never matched against the callee — sigil's gap, not our defect

Sigil booked **`EMP-DISCARDS-NAME-UNMATCHED`**: `@discards(name)`'s argument is parsed and stored but
never resolved against the callee's declared `FlagResult.name`, so `@discards(typo)` suppresses the
must-use check exactly as the right name does, and a renamed flag result cannot be caught at its
discard sites.

Live instance in our tree: `engine/objects/load_object.emp:116` writes
`jbsr Load_Object @discards(success)` while `load_object.emp` declares **no `carry:` at all** —
confirmed here, `grep -c 'carry:'` on that file returns 0. **Legal under today's rules, nothing fires,
and sigil has undertaken to tell us before any check lands.** It becomes a finding against our line
only then.

Worth carrying, in sigil's own account: they first wrote this up as *latent*, on the strength of their
comment at `corpus_contracts.rs:1961` saying no corpus call site discards today. Our corpus has 17.
**The measurement refuted their own comment in about five minutes** — the perishable-comment bar
firing on the lane that holds it.

---

## Q2 — `sound_fm.emp` ledger blocker 2 ("OP COVERAGE"): the mechanism is stale, the conclusion half survives

We asked whether the blocker was stale, having recorded that sigil source at `fbe380b9` prices
`call`/`ret`/`push`/`pop`/`bit`/`add a,n` while the `6884bfba` binary was never re-probed.

**All five are priced**, in `crates/sigil-frontend-emp/src/z80_cycles.rs` at their master, each with
unit tests beside its arm: `call nn` :389 = 17 (test :635), `call cc` :415 = 17/10, `ret` :384 = 10
(test :705), `ret cc` :414 = 11/5, `push`/`pop` :259-260 = 11/10 and 15/14 indexed (tests :764-767),
`bit n,r` :362 = 8 / 12 `(hl)` / 20 `(ix+d)` (tests :791-800), `add a,n` :267 via `alu8_src_cost`
(test :757).

**They did not all arrive together, and the split matters to us.** `push`, `pop`, `bit`, `call` and the
`alu8` arm carrying `add a,n` landed at `ce059de8` (2026-09-06). Plain `ret` is much older,
`ce64b6d1` (2026-08-04), and `ret cc` at `7137aad9`, the original core parcel. **So our row's inclusion
of `ret` was not a claim that went stale — it was wrong when written.**

`6884bfba` is **a sigil commit, not an opaque build id**: *"chain: strict attest for entry 206,
link-zero-byte-move-placement"*, 2026-09-12T04:20:58-04:00. All three pricing commits are its
ancestors and it is itself an ancestor of their master. **The binary we ran was built six days after
the last pricing landed and already had every one of the five.** The probe that produced *"pop is not
in the timed-region T-state table"* predates `ce059de8`, and the current diagnostic does not use that
wording (`eval/builtins.rs:684`) — which dates it a second, independent way.

**Do not strike the row outright: two of the five still bail, for a reason the row does not state.**

| op | status |
|---|---|
| `pop af`, `bit n,r`, `add a,n` | **clean** — nothing bails on them any more |
| `call` / `rst` | still refused: `[cycles.opaque-call]` (`eval/builtins.rs:669`) — the instruction IS priced, its callee is not in the slice, so the sum would be a true T-state count of *less code than runs* |
| `ret` | still refused: `[cycles.path-end]` (`eval/builtins.rs:658`) |
| `ret cc`, `call cc` | additionally fire `[cycles.ambiguous-branch]` |

**None of those is something a table row can fix.** Our blocker 1 is the same fact arriving from the
structural side, and is untouched.

**AEON WORK, still open: rewrite blocker 2 to say this** — neither "closed" nor "stands", but *three
ops released, two refused by name*.

### Where our wrong claim came from — the part worth keeping

Sigil found their own `z80_cycles.rs` module doc contradicting itself: a `[cycles.unknown-op]` bullet
reading *"any op/form outside the driver-demand table. The table is the timed-region subset ONLY"*,
eight lines above a SCOPE paragraph reading *"The table is no longer the driver-demand subset"*. A
consumer reading top to bottom hits the stale sentence first, and **our blocker 2's wording — "absent
from `instr_cost`'s demand subset" — is that stale sentence's vocabulary.**

**A correct-looking wrong claim, sourced from a real file, with a correct citation.** That is the shape
nothing in either repo catches: every citation discipline we run would have passed it, because the
citation was accurate and the source was real. Sigil fixed the doc in `cbe10440` and wrote the
consequence into the bullet so the next editor does not restore the shorter form. The gate that
actually holds the scope is `tests::encoder_coverage` (`z80_cycles.rs:891`), which asks the encoder
which forms it accepts and requires the table to price each one.

---

## What is NOT claimed here

Every line-and-file citation into sigil's tree above is **transcribed from their message, not verified
here.** We hold no checkout of their source in this parcel and did not open one. What we verified
firsthand is only the aeon-side half: the 30 declarations, the 11 files, the 17 `@discards` sites,
`rings.emp:54`'s text, and `load_object.emp:116` declaring no `carry:`.
