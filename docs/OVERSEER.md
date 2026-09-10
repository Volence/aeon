# Aeon Overseer

**Boot prompt** (paste into a fresh session started in this repo):

> You're the overseer for this repo. Read `docs/OVERSEER.md` first, then
> `../empyrean/docs/OVERSEER-PROTOCOL.md`. Work the queue. Peers may or may not be
> running — check `ListAgents`; coordinate if present, proceed solo if not.

The role, delegation discipline, review bars, and peer protocol live in the shared
protocol doc. This file and `docs/OVERSEER-REFERENCE.md` are what's aeon-specific.
<!-- SPLIT-NOTE -->
**THIS FILE IS THE BOOT READ, AND IT IS CUT BY *WHEN A RULE IS READ* — never by size and never by
what is "movable"** (owner, 2026-09-04T15:38:47Z, hub card 7, his words to the hub's recommendation
being *"7. Sounds fine"*; empyrean `origin/main` `docs/OVERSEER-PROTOCOL.md`, section
"The boot read is bounded", read at a committed revision and never through the sibling path).
What is here is what a fresh session must know **to act at boot**: scope, the queue, any resume
brief, and the standing rulings that change what a session does *first*.

**Everything read at a LATER, SPECIFIC MOMENT is in `docs/OVERSEER-REFERENCE.md`** — named here by
path so you can reach it at that moment, and not read at boot:

- **the landing lane** — before you merge, build the four shapes, freeze, or append to the ledger;
- **recovering a vintage artifact** — before ANY toolchain-archaeology parcel;
- **instruments (which oracle for what)** — before you measure anything;
- **there is no auto-commit daemon** — before you defer to an owner of a tree you have not
  confirmed exists (`games/sonic4/data/editor/**` is staged like any other work);
- **worktree quirks** — before you dispatch, freeze, or remove a tree;
- **changed-parameter moves** — a pointer into sigil, when you need bar 19;
- **the aeon-specific review bars** — when you judge returned work.

**Dated precedent narratives live in `docs/OVERSEER-LOG.md`** (append-only, newest last, read by
`tail`/`grep`, never at boot). A ruling that must survive a rotation is written HERE as well as
there, never only into the log.

**DO NOT TRIM A RULING TO HIT THE BOUND.** Every rule survives a cut somewhere; the only choice is
which file it lives in. `tools/test_overseer_bound.py` asserts the ruled 100,000 B bound directly
as of this cut (2026-09-10) — the growth ratchet it carried while card 7 was open is retired,
per that file's own instruction. Narrative: `docs/OVERSEER-LOG.md`, search `BOOT-READ BOUND`.
<!-- /SPLIT-NOTE -->

## ⚠ STANDING RULING THAT OUTRANKS EVERY BAR IN `docs/OVERSEER-REFERENCE.md` — read it before those bars

**2026-09-02T18:20:19Z — CUT THE CEREMONY (the owner's own ruling).** It ends the paired
aeon+sigil freeze, puts a moratorium on new process bars and boot-doc growth, confines lanes
to DoD items and the bug tier, and keeps "correct" meaning build + the lane's own tests + on
screen or in a witness. **Read it at the artifact, do not trust this summary of it:**

```sh
git -C ../empyrean fetch -q origin && \
git -C ../empyrean show origin/main:docs/OVERSEER.md | grep -n "18:20:19Z"
```

(empyrean `origin/main` `docs/OVERSEER.md`, the bullet beginning
`2026-09-02T18:20:19Z — CUT THE CEREMONY`, carried by empyrean `90554f2`.)

Banked here 2026-09-03 because it was being applied **from mail only** — a `git grep` over
this repo's `docs/` for it returned nothing, so a rotated aeon would have booted without the
one ruling that outranks the rest of this file and every bar in `docs/OVERSEER-REFERENCE.md`. The same gap was found at oracle and sigil
the same night. That is the failure this repo keeps re-finding in other forms: **a rule that
lives only in a message is not in force for your successor.**

**2026-09-02T17:17:18Z / 2026-09-03T04:24:58Z / 2026-09-03T05:21:01Z — THREE OWNER RULINGS THAT
TOGETHER OVERRIDE THE `/overseer` SKILL'S BOOT STOP.** Banked here 2026-09-04 for the same reason
as the ruling above: a `grep` of this repo's `docs/` found none of the three, so every aeon boot
was learning them from the hub's relay. Read them at their carrying commits, never from a relay
and never from this summary:

```sh
git -C ../empyrean show cdb72e9b:docs/OVERSEER.md | grep -n -A5 '17:17:18Z'   # keep pushing the list
git -C ../empyrean show 61dfcaa8:docs/OVERSEER.md | grep -n -A6 'Turning on sleep mode'
git -C ../empyrean show f04afe32:docs/OVERSEER.md | grep -n -A4 'tell the agents any time'
```

All three verified here as ancestors of empyrean `origin/main` and read firsthand out of those
blobs. In force: (1) a lane that reaches a boundary does **not** stop for a go — it takes the next
item on its list, unless that item waits on another lane or on an owner call, in which case it
takes the next one that does not; (2) overnight under sleep mode the same holds, with an exhausted
lane taking fallback project work (aeon's fallbacks: EFFECTS-W2, LOOPS-P, LIVE-OBJECTS); (3)
**every** finish or stop — a landing, a boundary, a block, an owner question, an agent returning
with nothing next — sends the hub one message saying what landed or why you stopped and what you
need. Byte-movers still serialize behind the aeon/sigil chain, and look/taste calls still park.

## ⚠ STANDING RULE — SAY WHEN YOU NEED A CONTEXT CLEAR (owner, 2026-09-09)

*"Remind the agents to let us know when they need a clear."* **Sibling of the 2026-09-03T05:21:01Z
report-when-you-finish-or-stop rule.** Say it in **both** places: your hub message, and
`lane-status.json`'s `awaiting`.

**REPORT THE MEASUREMENT, NOT A FEELING — oracle's amendment, and it is the load-bearing half.** The
risk is not a lane refusing to ask; it is that **a session near its limit is the least able to judge
that it is.** So give the fraction of context used and what is unbanked, and let him decide. *"I feel
fine"* is the artifact nobody can check — same reason `updatedAt` comes from the clock and never from
your own sense of the time.

**The resume anchor is A FILE AT A COMMITTED SHA, never a summary.** A summary is written by the
session about to stop, it is the one artifact its successor cannot verify, and it lives only in a
message where no reader can meet the contradiction. If that file does not exist yet, writing it IS
the work to do before asking.

## The queue

> ### RESUME BRIEF FOR THE NEXT AEON SESSION (first written 2026-08-30T00:38Z; **partly superseded, revised 2026-08-30T09:07Z** — read the strikes, they are the point)
> **DO NOT BOOT INTO A STOP AND WAIT FOR A PICK.** The owner's go is recorded — empyrean
> `origin/main` `7149b39`, verified reachable here, and his standing instruction in it reads
> *"Do not boot into a stop and wait for a pick: his pick is this paragraph."* The hub pushes
> lanes continuously through the ratified plan and rules in his place where a lane is blocked.
> **This overrides the `/overseer` skill's boot stop, which is exactly the exception that skill
> names.**
>
>
> **START WITH:** whatever `docs/lane-status.json` `resume` says — it is written from the clock
> and this block is not. **The 09:07Z sentence that stood here is SPENT: the arm is MERGED**
> (`4aa2abc0`, steps 0-4, re-verified on the merged tree), so `parcel/effects-ref-arm` is no
> longer in flight and a reader who executes that line will re-do landed work. As of
> 2026-08-30T10:01Z the live piece is **item 1 STEP 5** on `parcel/preset-sec5-split`. Its
> contract question is **ADJUDICATED**: the sidecar key is **`rasterRef`**, not `effectsRef`
> (empyrean `da91abce`, option B — verified reachable from `origin/main` here, and §3.1 read
> firsthand rather than relayed).
>
> **AND ITS SECOND BLOCKER IS RULED — BLOCKED-2, the owner's call, taken in his place by the hub
> under the standing instruction: the band goes on SECTION 5** (the 38-byte split that evicts
> nothing; section 4 was rejected because it evicts the d-15 showcase he asked to see). What the
> band LOOKS like stays his: a legible default ships with a parked capture naming the section,
> and he moves or recolours it in aurora once `assign_section_preset` lands. Carrying commit
> empyrean `e874427decc99c3717892a68a583f5a9bafc6dcc`, `docs/OVERSEER.md`, found with
> `git log -1 -S 'SECTION 5, look parked' -- docs/OVERSEER.md`. **Reachable from `origin/main`,
> re-verified here at 10:03Z after the hub pushed on this lane's catch.**
>
> **The falsifier travels with the ruling**, because the ruling rests on a number: if section 5's
> split is not 38 bytes, or evicts anything when built, the ground under the choice is gone —
> report the true cost and stop rather than proceeding on a different one. The design branch `design/effects-ref-binding` (`2cf29126`, unmerged)
> **predates the ruling and says `effectsRef` throughout** — that is a stale planning document
> too, and the same bar applies to it. Then items 3 and 5 — but note **item 5 is NOT unblocked by
> item 1's ruling**: option C, the one that would have carried item 5's keys, was refused
> precisely because it would have inverted the ratified order. Item 5 needs its own, unwritten CR.
>
> **THE PLAN:** `docs/DEFERRED_WORK.md` → *"EFFECTS-W1 — the owner-ratified definition of done,
> priced and sequenced"*. All eleven aeon items priced S/M/L with byte status, the sequence, and
> **item 0** — the spare-nametable prerequisite that items 10 and 11 both need and that is on
> nobody's list. Card `vram-replan` is filed; his answer is not needed until 10/11 are reached.
>
> **⚠ THE PROJECT GREW A SECOND HALF (owner, 2026-08-30).** EFFECTS-W1 is not done until the
> side-effect bugs are fixed too — his words and the enumeration are at empyrean `origin/main`
> (`contract/projects.json` → EFFECTS-W1 `completionRequires`; DoD items 14-17). **The canopy gap
> is no longer backgroundable** (item 17: *"a found cause and a fix, not a backgrounded card"*).
> **Its plan is to INSTRUMENT for the next sighting, not to derive a third explanation** — two
> code-read explanations are already refuted, so derivation is the approach with a demonstrated
> failure rate here. `d-47-revised` is RULED `targeted`; **measure the append-disturbs-nothing risk
> before any art ships — a measurement, not the argument.**
>
> **RE-MEASURE, DO NOT INHERIT:** the sigil binary's staleness (rebuilt at their `85a5726c` as of
> 2026-08-30T00:33Z — but re-derive at the moment you need it, never from this line); and the
> lost `+$60` derivation described under *"AN OPEN MEASUREMENT THREAD WITH SIGIL"* in
> `DEFERRED_WORK.md`, which must be re-derived and never reconstructed from a peer's paraphrase.
>
> **SHELF LIFE — treat every coordinate in this block as expired and every SHAPE as sound.**
> The shapes above (there is a ratified plan; the project grew a second half; re-measure rather
> than inherit) age well. The specific rows, SHAs and next-actions do not, and the two that went
> stale here both went stale because work landed *elsewhere* — one in this repo, one in empyrean.

**`docs/DEFERRED_WORK.md` is the living queue** — check it at the start of every
planning phase; it books everything with provenance. The current arc and any owner
rulings live in the session memory and the most recent `docs/superpowers/*handoff*` /
`*summary*` docs. Do not duplicate queue content here; this file only says where it is.
