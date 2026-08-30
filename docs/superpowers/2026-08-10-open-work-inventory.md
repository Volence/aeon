# Open-work inventory — sound + engine, 2026-08-10

The closeout sweep for the 2026-08-09/10 sound era. Written when the user
called a stop after packages 3 and 4 merged, to answer one question honestly:
**what is actually left, and what does "complete for now" mean?**

This is a *state* document, not a plan. It supersedes the status claims in the
sound queue doc and ROADMAP wherever they disagree (corrections applied and
listed in §8). Two full read-throughs back it: one over every sound source, one
over every non-sound source, both with file:line citations retained in the
session record.

---

## 1. What "complete for now" means

**The sound engine is feature-complete for the content that exists.** Every
banked correctness defect from the 2026-06-21 audit that was reachable has been
fixed; the driver plays music and SFX correctly on both build shapes, verified
by rendered audio rather than register traces. Two shipped songs and nine SFX
run through it. Nothing on the open list blocks authoring more content.

What is *not* true — and the queue doc still claims it — is that packages 5 and
6 close the book. They don't. Nine triage riders and two ruled-in work streams
were adopted on 2026-08-08, after that claim was written, and none of them has
a plan. See §3 and §8.

**The honest one-line summary:** sound is done as an *engine*; it is not done as
a *backlog*, and the backlog is now mostly enhancements rather than defects.

---

## 2. Where the build stands

| | value |
|---|---|
| `s4.bin` | 414,093 B / crc `92e4d868` |
| `s4.debug.bin` | 428,056 B / crc `b8249dad` |
| `demo.bin` / `demo.debug.bin` | 93,386 `e40a43ce` / 97,528 `b5a586d1` |
| ROM use | 418 KB of 4 MB (10%) |
| 68k RAM | 31.8 KB free before stack |
| **Z80 resident blob** | **plain 6,164 / debug 6,294 of 6,384 → 90 B headroom** |
| sigil provenance chain | entry 87 |
| Unmerged branches holding work | `perf/fillcol-hoist` (parked research), `lane-c` (2-line orphan) |
| In flight | nothing |

The Z80 number is the one that changed character this era. Packages 1-3 were
shaped by a 3-byte ceiling; package 4's item-25 reclaim returned 98 bytes
against 11 spent, so **the ceiling is no longer the binding constraint**. Three
documents still quote the old figure — corrected in §8.

---

## 3. Sound — what is open

### 3a. Ready to execute (banked plan, no prerequisite)

Only two, and both need the same mechanical prerequisite first: the
**path-migration rebase** (the plans predate the engine/game split *and* the
`.emp` migration, so they cite `sound_constants.asm`, `ram.asm`, `macros.asm`,
root `test/`, and the old debug-harness home). Whichever runs first applies it.

- **Package 5 — audio production suite.** Spec user-approved. Tier 0 (drum
  mastering chain, TL-filter-sweep generator, seeded generative variation,
  authoring cookbook) costs zero resident bytes and is pure tooling. Tier 1
  (kick-sidechain pump, macro autopan) is ~50-90 B and fits. **Tier 2 will hit
  its own budget gate and stop**: it demands ≥172 B free and we have 90. The
  plan treats "blocked at N bytes, door documented" as a legitimate recorded
  outcome, so it still runs to completion — just expect two tasks to record a
  stop rather than ship.
- **Package 6 — closeout sweep.** Tasks 1-4 and 7 are execution-independent.
  Tasks 5-6 are controller-session-only by construction (they need the
  emulator). Carries the R2 observability rider, which needs its plan written.

### 3b. Adopted but unplanned — the 2026-08-08 triage riders

Nine riders were adopted and **none has a plan**. This is the part the queue
doc's "backlog EMPTY after 5+6" claim misses entirely.

| rider | what | why it matters | size |
|---|---|---|---|
| **R3** log-domain pitch | one 8.8 semitone value per channel, f-num derived by interpolation | *"biggest single musical-correctness idea in the study."* Flagged for **user sign-off as a novel bet** | M-L, ~55 B reclaim |
| **R6** sequence-format revision v1 | four batched format wins (−26.2% on HCZ2, −14% on MT, 3,648 B of MT transpose) | one re-pack + one re-pin if batched; several if not | M |
| **R2** observability cluster | ring-lead telemetry, driver cost meter, SFX-channel debug mirror | *"cheapest leverage in the whole list"*; package 6 keeps wanting it | S |
| **R7** envelope release phase | continue-past-sustain on key-off, opt-in per envelope | sized to ride R6's session | S-M |
| **R8** macros write channel state | `TAG_MAC_SET`/`ADD` + reg-write form | offset **must** be build-gated or a music macro can poke an SFX slot | S-M |
| **R9** loop-split PHASE | −30 T/sample for ~15 B | **bank the cycles, don't spend on rate** (owner-ruled) | S-M |
| **R10** structure phase | `pat` subroutines, drum mode, nested loops | RAM is the cost: 88 B for a 2-level stack | M-L |
| **R11** generic pitch envelope | replaces the vibrato machine, frees ~90 B Z80 RAM | **"together with R3 or not at all"** | M |
| **R5** re-key flam | possible double attack on SFX restore | traced 2026-08-10, **not reproduced**; hazard narrowed to `MEV_PITCHENV`-during-steal, which no shipped song has | S |

Plus two ruled-in streams: the **multi-tick tempo + item-25 H1 parcel** (must
land as one parcel, "do not split") and the **68k SFX policy layer** design
task (queued after the banked packages).

And **B5**, the tone-tracked noise sweep, deferred out of package 4 with a full
costing: ≳40 B and three coupled changes, one of which re-opens the very D1
corruption package 4 just closed. Wants its own parcel, after R3.

### 3c. Sound defects still open

Ranked by how much they'd actually bite:

1. **PSG volume-envelope fold clamp is a single-bit test.** `bit 4,a` where a
   magnitude test belongs, so a fold sum in `$20..$2F` passes unclamped and
   writes attenuation to the **wrong PSG channel**. Unreachable today only
   because every authored envelope byte is ≤ `$10` — a margin of exactly one,
   held by a generator assert. **Contained, not repaired**, and the containment
   is a data invariant a content author could break.
2. **Bank-latch desync corrupter, unidentified.** Seen once; failure mode is
   permanent silence for every subsequent song. Persistence half fixed, cause
   unknown, may be an emulator artifact. Package 6 Task 5 is the bounded hunt.
3. **`pack_sfx` never calls `Event.validate`** — so *every* packer range/route
   rule is silently inapplicable to SFX streams. Package 4 patched the two
   rules it owned; the class hole stands.
4. **`sfx_transcode._process_lines` is dead and has already diverged** from the
   live v2 scan. Backstopped, not deleted.
5. Smaller, all sitting inside package 6's banked plan: the `$28` key-on guard
   gap, cold-boot DAC pan seed, FM envelope attack seam, `sc_base_freq`
   steal-latch (package 6 scopes only the comment, not the behaviour), HCZ2
   import loop residual.

Two documented disagreements I am **not** resolving unilaterally: whether **A2**
(two SFX in one frame) is discharged — the file says both — and whether **F3**
(dead ROM tables) is closed, where package 4's plan header and DEFERRED_WORK
contradict each other. DEFERRED_WORK is the later record and says do not treat
F3 as closed.

### 3d. Content-gated (build when content asks)

S3K drum-kit authoring (runbook shipped, fidelity pre-verified), Bank-D twin ROM
activation, per-frame pitch/volume envelopes, FM3 special mode, polyphonic PCM
(foreclosed by the ratified single-voice bet), Seraph/MegaDAW export retarget,
and the game-side game-feel call sites — act-clear, drowning tempo, 1-up jingle,
pause-all — which are **engine-complete and waiting on the screens/HUD package**.

---

## 4. Engine — what is open

### 4a. The three big ones

- **BG per-section seam streaming** — the largest undesigned engine surface, and
  the hard dependency of the mega-act goal. Research and a component inventory
  exist; **no spec, no plan**, and three unanswered user rulings (§6). On hold
  by explicit instruction.
- **Character dispatch v2** (Tails + Knuckles) — the largest item that already
  has a banked, re-anchored, executable plan: 12 tasks across four phases,
  ability-hook vectors, S3K asset conversion, CPU input filter. RAM anchors need
  re-pinning post-P2.
- **Mega-act tech demo** — an assembly rather than a work item: P2 (done) + BG
  themes + transition corridors + floating origin + shell polish + the ROM
  layout fix below.

### 4b. Engine defects and hazards

1. **`PHYS_FALL_CAP` 1-pixel tunnelling hole — in the shipped build.** The
   `$1000` fall cap is exactly one pixel hotter than the safe step for OJZ's
   16 px floors, so a frame ending at distance 0 plus a full step can skip the
   slab. A one-constant fix (`$0F00`) is on file. **User parked the topic**, so
   it stands as a known live hole.
2. **Mega-act ROM layout — the pre-DAC hole.** All act data links before the
   DAC bank anchor, and a real act **will not link** in the room ahead of it.
   Needs a layout decision, not a patch. *(Corrected 2026-08-30: this said "the
   hard `$48000` anchor". That address moved in the 2026-08-26 re-layout and the
   anchor is DERIVED by `map.toml`'s bank placement rule, not fixed — so the
   headroom is a derived quantity too. Read the rule; the "~21 KB" that stood
   here was a snapshot.)*
3. **STRESS_EVICT page famine** — root-caused this session as capacity
   arithmetic (4 pinned + 6 concurrent transients vs 9 frames). No fix, by
   ruling; folds into the C4-3 famine design. Best option on file: have the
   strip generator emit a per-act concurrent-page bound and `ensure` the clamp,
   turning famine into a build error.
4. **Diagonal budget at ~100% of frame** — 61 lag per 270 frames. The "copy
   chain is the top lever" premise was falsified by measurement 2026-08-10; the
   real residual is the flat decompress/patch-run/HBlank taxes. The owner's
   A/B/C product question is still unanswered.
5. Smaller: `Palette_Dirty` drop-retained analog (same class as the fixed
   sprite-table bug, deliberately left), BUG-005 one-frame stray sprite piece
   (unreproduced, instrumented), `SEC_VOID` flat-id 255 alias (harmless until
   grids approach 16×16), a stale `VInt_Level` header comment, and a
   five-item orphaned-RAM/dead-code cluster.

### 4c. The presentation gap

Worth stating plainly because it blocks the showcase goal: there is **no fade of
any kind, no title card, no act transition, no screen shake, no look-up/down, no
camera limits**, and `HBlank_Install` ships with zero consumers. Section §7 of
the architecture doc is PLANNED wholesale — including palette transitions on
section crossing, which have no code at all. Design #7 (screens/HUD) and #8
(raster engine) are banked but unexecuted; the rest is not yet specced.

**SRAM save (§9.6) is not implemented at all** — and since the CrossResetRAM
ruling, the engine has no persistence of any kind. It also carries a hidden
dependency: oracle would need to emulate SRAM persistence.

### 4d. Ready to execute, small

DPLC lookahead; `yflip`/`xyflip` SAT word merge; act-descriptor size assert;
OJZ sky-tint marker strip; real ring/object art at the pool slots; the
`VInt_Level` comment fix; the `test_import_sk_collision` tools hazard (it
rewrites committed bins in place — an auto-commit-daemon hazard). Variable
HScroll DMA is the biggest measured lever (~20% of frame) but its dirty-range
infrastructure was deleted and must be rebuilt.

---

## 5. Everything else, by shape

**Measure-first** (do not build on the estimate): S4LZ decoder micro-opts, SST
frame-pointer cache, P2 residuals (ZX0R unroll, pinned-class split, prefetch
bitmask, `Frame_Counter` hoist, PF_PROTECTED inversion), FG tile-flip mismatch.

**Trigger-gated and the trigger has not fired**: static sub-sprite array, boss
bbox culling, object-vs-object collision, dynamic tile override, FG H-deform
seam, RescanY burst budget, row-2 content test, respawn-memory minors, ring
frame swap, sprite multiplexing. These are correctly parked — nothing is served
by building them before the thing that needs them exists.

**Triggers that HAVE fired and were never acted on** — the list worth a look:
the cycle profiler (§8.5 counters exist but are unwired; we measured steady-state
lag this session, which is its stated trigger), variable HScroll DMA, DPLC
lookahead, the SST field audit, and the dynamic VRAM allocator — whose premise
may now be *moot* under the resident deduped pool, so re-read the art design
before planning it.

**Sigil-side asks** (not aeon work): declared `preserves()` is a non-fatal
diagnostic — which is exactly how a coherent-but-wrong render shipped once;
table-fold vs placement divergence must become a build error; the isolation-port
systemic inject; the undocumented per-module const-name seam.

---

## 6. Awaiting a decision from you

| # | question |
|---|---|
| 1 | **BG streaming — theme vertical slice height**: 512 px full plane wrap, or 256 px slices? (recommendation on file: 512) |
| 2 | **BG streaming — horizontal ambition**: is per-strip N-band streaming in scope for the mega-act, or is "horizontal seams share band config" an acceptable permanent authoring constraint? (recommendation: the constraint) |
| 3 | **Diagonal budget** — the standing A/B/C: accept the dip, cap the combined diagonal step, or cut BgAnim bands during fast scroll? The 2026-08-05 ruling was MARK AND REVISIT with "do not silently take (A)", and the revisit condition has now fired and been partly consumed. |
| 4 | **`PHYS_FALL_CAP`** — take the one-constant fix, or keep the topic parked with the hole known? |
| 5 | **R3 log-domain pitch** — flagged as a novel bet needing sign-off, and it wants to happen *before* the soundtrack grows. Its position relative to package 5 is a real ordering call. |
| 6 | **`test_player` in release** — should the test object set ship at all? |
| 7 | **Fonts** — HUD (leaning Emerald) and title face. |
| 8 | **Floating origin F2** — `section_id` byte→word widening (F1 alone already unblocks 256 sections). |
| 9 | **Debug-fly cheat code** — what unlocks it? Deliberately deferred to design #7. |

BG ruling 3 ("may work start before P2 merges?") has expired — P2 merged
2026-08-09 — but the lane stays on hold on your instruction regardless.

---

## 7. Invariants any future work must not break

Collected because they are scattered and each one has already cost something:

- **The SeqChannel↔SfxChannel shared prefix is load-bearing** (`sx_pad@+58`
  aliases `sc_detune`). No proposal may grow it — this binds R8, R10, item-25's
  RAM claim, and B5.
- **Only DATA may be banked; all in-frame code stays resident.** Banked-window
  code fetches corrupt under bus contention.
- **The DAC sample-bank anchor is DERIVED, not fixed** — `map.toml`'s bank
  placement rule puts banks after data, so growing the data moves the anchor.
  *(Corrected 2026-08-30. This line read "the `$48000` DAC sample-bank anchor
  cannot move — it is a Z80 `SetBank` latch". Both halves were wrong after the
  2026-08-26 re-layout, and this is the file people read to decide what is
  POSSIBLE, so a false immovability claim here rules out designs that are
  actually available. The Z80 SetBank latch is real; it is not what pins the
  address.)*
- **`MEV_EXT` sub-ops 0/1/2 are claimed** (COMM, PUMPSET, GHOSTSET). New tenants
  start at 3.
- **Any resident Z80 addition needs its reclaim identified first** — even with
  90 B, that discipline is what made package 4 affordable.
- **Item-25's H1 cannot ride a pure-size parcel** — it is a chip-stream change,
  and it must land with the multi-tick tempo work.
- **Two parallel byte-parcel lanes cannot share one sigil binary pair** — the
  contract baseline is a multiset equality; give each lane era-matched binaries.
- **Real-output gates run on BOTH build shapes.** Package 3 shipped a
  plain-shape silence that debug survived by parity luck.

---

## 8. Stale claims found, and what was done about them

Corrected in this pass:

- Triage doc's standing-state line said **~316 B DEBUG headroom** — actual is 90.
- DEFERRED_WORK said **"packages 1/3/4/5/6 still unexecuted"** and "package 4 —
  genuinely open"; 1, 3 and 4 have all merged.
- The 2026-08-09 handoff stated the **3-byte Z80 constraint** as a hard rule —
  retired; that is the first doc a cold session reads.
- The sound queue's **"post-5+6 backlog EMPTY"** claim — annotated as false, with
  a pointer to the riders.
- ROADMAP listed four items that are already closed or superseded (parallax
  jump-table unroll, the three conditional review rows, the FillColumn hoist as
  "next perf parcel", editor collision authoring).

Flagged but deliberately **not** resolved, because they need a judgement call
rather than an edit: the A2 discharge contradiction, the F3 closure
contradiction, DEFERRED_WORK's internally-contradicting parallax entry, and
three entries whose headings say RESOLVED/DONE/VOID while their bodies carry
live work.

Line-number citations inside the two banked plans and the triage doc have
drifted by hundreds of lines as DEFERRED_WORK grew. Whoever executes package 5
or 6 should expect to re-anchor by grepping, exactly as the package 3 and 4
porters had to.
