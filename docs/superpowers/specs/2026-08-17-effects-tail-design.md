# DESIGN — the effects tail: band-budget relax (Part A) + VSRAM op-class split (Part B)

**Status: DRAFT, revision 1 — unswept.** Per the brief (`../2026-08-18-band-budget-brief.md`):
research → THIS DRAFT → three mixed-model adversarial lenses → owner sign-off → plan → execute.
Two parts, one sweep; the parts are independent and either can ship (or die) alone.

**The price, stated first (Part A): this parcel is worth about 3 screen rows.** OJZ channel 0's
band is capped at 220 because channel 1 holds 222..223 and the disjointness budget is exactly
full; rows 221-223 render dry when the world says wet. Relaxing the budget buys those rows and
the general freedom for two channels to traverse the whole screen. If the sweep or the owner
rules 3 rows is not worth a wire-format change, that is a legitimate outcome. (Part B's price is
independent: 54 cycles per VSRAM op + the 3-word ceiling, against a 16-cycle rung tax on `reg`
dispatch.)

---

# PART A — relax `check_intervals`: overlapping bands, runtime collision resolution

## A1. What the reference corpus settles (survey 2026-08-17, full report in the session log)

1. **No precedent exists.** S.C.E./S2/S3K: one channel per mode, contention structurally
   impossible. B&R: whole-frame authored compositions, last-writer-wins at the MODE level.
   Ristar: one handler at a time, sequencing compiled into pointer-swap chains. Gunstar/TF4:
   fixed cadence, dense streams, no events. Nobody resolves line collisions at runtime — every
   shipped game avoids them by construction. This design argues from the timing contract, not
   from precedent, and says so.
2. **The one-reload-late behaviour is hardware-tested** (genvdp.txt: the counter reloads from
   reg $0A at expiry / line 0 / lines 225+, NEVER on write; SpritesMind t=1511: a value written
   at fire N is consumed at fire N+1's reload and positions fire N+2). Our builder already
   encodes exactly this — THE ARM SLOT IS TWO RECORDS BACK (`raster.emp:1067-1072`), the hand
   pin is the witness — and building the whole schedule before VBlank arms it is the right side
   of the hazard. The survey's "first entry executes twice" trap is our two priming records.
   Nothing in this parcel touches that seam; stated so the sweep checks the claim.
3. **Dual-consumer discipline: single producer, publish, never re-derive.** Everywhere the
   pattern works (S2 water: one derivation writes counter + fullscreen flag in adjacent
   instructions; S2 2P: VBlank snapshots the split for the interrupt consumer), ONE routine
   computes and every consumer reads the published result. The one case that re-derives
   independently — Ristar's main-loop shimmer against its VBlank palette split — ships a
   1-frame skew under vertical camera motion that nothing compensates. This is the strongest
   external argument for the resolver hoist below.
4. **Edge-yield precedent is positional**: Ristar degrades to a full-screen VBlank palette
   apply when the split lands at line <= 4; S3K trims its own colour count past line 200. Our
   frame-top ship IS the Ristar pattern and is untouched here.

## A2. The design in one paragraph

Hoist collision resolution OUT of both consumers into one main-loop producer,
`Raster_ResolveLines`, running immediately after `Effects_LatchWorldLines`: it walks the patch
table once in authored order, derives each record's fire line (latch → clamp → the existing
suppress rule), resolves collisions by **authored order wins, loser pushed down by the
program's spacing word, suppressed if the push exits its band**, and publishes per-record
resolved fire lines to a RAM bank. `Raster_BuildSchedule` (VBlank) stops deriving and just
emits what the bank says; the parallax overlay stops calling `Raster_GetChannelBand` and reads
the same bank. Both consumers see the identical post-resolution answer on the identical tick
by construction — there is no second computer to disagree. The builder keeps ONE defensive
compare (every emitted line strictly greater than the previous emitted line; violator
suppressed) so park-safety is structural even under a resolver bug — the adviser's ruled
safety/quality split, with the safety compare demoted to a backstop that should never fire.

## A3. The pieces

### A3.1 Comptime: what `check_intervals` becomes

DELETED: the disjointness walk and the band budget `sum(hi-lo+1) + (N-1) <= 221`.

REPLACED BY (all in `raster_program`, build-fatal):
- bands still individually sane: `3 <= lo <= hi <= 223` (screen space), unchanged.
- records still authored in **non-descending `band_lo`** order. The table order is the
  priority order (A3.3), so it must remain meaningful; ties (two full-screen channels) are
  legal and the authored order IS the tiebreak.
- **one patchable record per channel** — previously §5.6's recommended guard, now REQUIRED:
  the published bank is per-record but the parallax consumer indexes per-channel, so a channel
  with two records has no single answer. (`compose` guard 9 already refuses two patchables on
  one LINE; this extends to the program.)
- `check_density` retained for static-static neighbour pairs only (their lines cannot move).
  For any pair involving a patchable, comptime worst-case density is unsatisfiable under
  overlap BY DESIGN (two overlapping bands have worst-case gap <= 0); density for those pairs
  moves to the runtime spacing rule (A3.3), which the adviser ruled sufficient because density
  is cosmetic (`raster_dsl.emp:1195-1199`), only park is fatal.
- **the spacing word**: `ceil(max(fire_cost_cycles(f)) / RASTER_SCANLINE_CYC)` over the
  program's fires, emitted as one header word next to `pal_dirty_mask`. Currently 2 for OJZ
  (the 704-cycle `pal_restore` fire). At most one line of pessimism on cheap records — priced
  and accepted by the adviser's ruling.
- arm ceiling: `ensure` the widest constructible gap still fits a byte. Resolved lines live in
  fire-line space `[2, 222]`; widest gap = 222 - 1 - 1 = 220 <= 255. Stated as an ensure with
  the derivation in the message, not inherited silently from §5.2.

### A3.2 The producer: `Raster_ResolveLines` (main loop)

Runs after `Effects_LatchWorldLines`, before `Parallax_Update`. Guarded on
`Raster_Patch_Tab != 0` exactly as the builder is. Walks the table once:

```
prev = 1                                  // priming fire line, as the builder seeds d0 today
for each record k (table order):
    if patchable: L = Effects_Screen_L[ch] - 1        // fire line
                  if L > band_hi_fl:  resolved[k] = RESOLVED_NONE; next   // existing suppress
                  if L < band_lo_fl:  L = band_lo_fl                      // existing clamp-up
    else:         L = authored fire line               // statics enter the walk too
    if L < prev + spacing:                             // COLLISION (or too close)
        L = prev + spacing                             // push down: authored order wins
        if patchable and L > band_hi_fl: resolved[k] = RESOLVED_NONE; next
        if static:                        resolved[k] = RESOLVED_NONE; next
                                          // a static's reach is its own line: any push exits it
        if L > 222:                       resolved[k] = RESOLVED_NONE; next
    resolved[k] = L;  prev = L
```

- `resolved[]` is `Effects_Resolved_FL[RASTER_MAX_RECORDS]`, per-RECORD, fire-line space,
  `RESOLVED_NONE = $7FFF` (same inert-by-construction reasoning as `PATCH_ANCHOR_NONE`).
  `RASTER_MAX_RECORDS = 8` proposed (16 bytes RAM; OJZ ships 2; `raster_program` ensures
  `fires.len <= RASTER_MAX_RECORDS`).
- The per-channel view the parallax needs is published in the same walk:
  `Effects_Resolved_Ch[RASTER_MAX_PATCH]` (8 bytes), `RESOLVED_NONE` for suppressed or absent
  channels. Well-defined because of the one-record-per-channel guard.
- Statics are pushable IN PRINCIPLE but their reach is a point, so a push always suppresses
  them. Uniform rule, no special case in the loop beyond the reach test. A suppressed static
  is a content-visible event; the comptime `band_lo` ordering makes it constructible only when
  a patchable AUTHORED EARLIER can reach the static's line — an author choice, diagnosable at
  authoring time by reading the program, and the sweep should attack whether a comptime warn
  for "patchable band swallows a later static" is worth adding.
- On a lag frame VBlank runs twice against one resolve — both builder passes read the same
  bank, which is today's `Effects_Screen_L` staleness contract unchanged.

### A3.3 The priority ruling (open question 1): AUTHORED ORDER WINS

The earlier table entry keeps its line; the later one is pushed to `prev + spacing`, and
suppressed only if that exits its band (or a static's point reach, or the screen). Argument:

- **It is the only rule a one-pass in-order emitter gets for free.** Any rule where a LATER
  record can displace an EARLIER one (narrower-band-wins, least-moved-anchor) needs lookahead
  or a sort in VBlank-adjacent code. The resolver runs in the main loop so it COULD afford a
  sort — but every candidate that needs one also needs the author to predict the outcome from
  runtime state, which makes the content non-deterministic to author.
- **It gives the author the knob.** Priority is expressed by ordering fires in the program —
  the same place every other property of the program is authored. The survey found the only
  shipped "who wins" conventions are authored-order compositions (B&R) — this matches.
- **Push beats suppress as the default disposition** because a pushed boundary is a <=
  spacing-row displacement while a suppressed one is a vanished effect; the fatal park is
  impossible either way, so the cheaper visual failure wins.
- Rejected: **merge the colliding fires into one record** (Ristar's degrade-to-VBlank cousin).
  It preserves both effects' lines exactly, but the merged fire can exceed the 2-stream-op /
  3-stream-word ceilings, trading a 1-2 row displacement for a mid-line write artifact, and
  the builder grows an op-count rewriter. More moving parts for a worse artifact. Named so
  the sweep can disagree.

### A3.4 The consumers

**Builder** (`Raster_BuildSchedule`): the derive/clamp/suppress block (`raster.emp:1128-1139`)
is replaced by one read of `Effects_Resolved_FL[k]` (RESOLVED_NONE → `.suppress`). The
defensive backstop stays exactly where the gap is computed: emitted `L <= prev` → `.suppress`
(cannot happen if the resolver is correct; costs one compare; makes park impossible by
construction rather than by trust). Everything else — two-back arm slot, park tail, double
buffer, swap — is untouched.

**Parallax** (`parallax.emp` step 4b): the `Raster_GetChannelBand` call and the local
hi-first/clamp-up logic (`:774-802`) are replaced by one read of `Effects_Resolved_Ch[ch]`:
`RESOLVED_NONE` → no split (record not emitted — same as today's past-hi path); else split at
`resolved + 1` (fire line → screen line). The `L <= 0` frame-top state keeps reading the raw
latch exactly as today (`:763-764`) — the resolver's clamp-up cannot express "above screen",
which is the same reason `Effects_LatchWorldLines` stores unclamped. THE THREE STATES SURVIVE
IDENTICALLY; what changes is that the mid-band state's line is now the POST-COLLISION line, so
palette and scroll agree even on frames where a push moved the boundary.

**`Raster_GetChannelBand`**: DELETED (clean-not-bolted-on). Its doc block's reason to exist —
"so a second consumer clamps exactly where the builder clamps" — is subsumed by the bank; its
W0 semantic answer (no live table → caller must not clamp) is preserved by the parallax
no-split default when `Raster_Patch_Tab == 0` (the resolver never ran; `Effects_Resolved_Ch`
holds RESOLVED_NONE from the program-install reset — see lifecycle below).

**Lifecycle**: `Raster_InstallPatched` and `Raster_Install`/uninstall reset both banks to
RESOLVED_NONE, so a frame between install and the first main-loop resolve emits an empty
schedule rather than a stale one — same shape as the priming-park argument.

## A4. §5 re-proved under the new rules (the brief's open question 3)

1. **A negative gap is impossible — now by two independent mechanisms.** (a) The resolver's
   output is strictly ascending by construction: every published line satisfies
   `L >= prev + spacing`, `spacing >= 1` (it is `ceil(cost/488)` of a fire whose cost >=
   `RASTER_FIRE_BASE_CYC` = 302 > 0). The builder emits a subsequence of a strictly ascending
   list — the §5.1 subsequence argument, restored with the resolver as the new premise-holder.
   (b) The builder's backstop compare suppresses any non-ascending record independently of
   (a). Park requires BOTH to fail.
2. **The 8-bit arm ceiling survives.** All resolved lines lie in `[2, 222]`: clamp-up floors
   at `band_lo_fl >= 2`, push caps at 222 (else suppressed), suppress-past-hi caps at
   `band_hi_fl <= 222`. Widest gap 220 <= 255. (Old §5.2 said "gaps only grow" under removal —
   that argument is DEAD, replaced by the interval bound.)
3. **Density.** Static-static pairs: comptime, unchanged. Pairs involving a patchable: the
   runtime spacing rule guarantees `gap >= spacing >= ceil(max_cost/488)` lines between any
   two EMITTED fires, which is the program-wide-max form the adviser ruled sufficient; at most
   one line of pessimism. Cosmetic anyway — an overrun pushes writes into active display, it
   does not drop fires.
4. **Park is structural** — untouched (builder tail identical).
5. **No fire races the build** — untouched (inactive buffer + VBlank).
6. **The §5.6 residual is CLOSED**, not carried: one-record-per-channel is now a build error,
   and the FIRST-match hazard dies with `Raster_GetChannelBand`.

## A5. What this does NOT buy, stated

- The frame-top residual (boundary at screen 3 while the world says 1..3) is untouched.
- During a collision frame, the losing boundary renders up to `spacing` rows below its world
  line (and its scroll split moves WITH it — they agree, but both are displaced). The residual
  after this parcel is: 0 dry rows in the non-colliding case (band caps lift to 222), a
  <= spacing-row displacement on the loser during collisions, suppression only when pushed out
  of band. Re-measured numbers go in the gate evidence, per DoD 4.
- Runtime reordering stays out of scope (§8 of the previous design).

## A6. Gates (sketch — the plan details them; DoD from the brief)

- The scene fixtures grow a fourth state: TWO channels forced into collision
  (`write_memory` both anchors, one frame), asserting the winner's line, the loser's pushed
  line, both from walked arm gaps, and payload byte-diff per surviving record — the
  three-state matrix of `tools/scenes/README.md` extended, expectations DERIVED from the
  resolver rules, never copied from pins.
- Poison-proof (DoD 3): a program whose bands overlap such that the OLD guard refuses it and
  the NEW build accepts it; and the builder-backstop proved live by a poisoned resolver bank
  (write RESOLVED garbage, one frame, assert suppression not park) — the
  guard-nobody-saw-fire rule.
- Cross-compare palette vs scroll boundary in the COLLISION state, against each other, same
  frame — the sweep-era rule that two consumers must be tested against each other, not each
  against the shared formula.
- The negative-build lane gains the new-guard poisons via `--extra-entry` (cheap now).
- Byte-parity control: a program with disjoint bands must build a byte-identical ROM apart
  from the new header word — the relax must not move anything it did not claim.

---

# PART B — split the VSRAM op class off `OP_CRAM`

## B1. The question, and what is already measured

A `stream_vsram` op IS `OP_CRAM` with a VSRAM command longword (`EFFECTS_OP_CLASSES.md` §1).
It therefore pays the CRAM class's blanking delay (`EFX_BLANK_DELAY`, 54 cycles) and shares
the 2-stream-op / 3-stream-word per-fire ceilings, which exist because CRAM is read every dot
and a write outside blanking paints a visible dot. Measured (fixture F7): a VSRAM word costs
exactly a colour word today — same path. The split is not about word cost; it is whether
VSRAM writes need the delay and the ceiling AT ALL. Ristar phase 3 writes 21 column pairs
(42 words) in one fire — the existence proof that somebody shipped far past our ceiling.

The cost model prices the change exactly (handoff 2026-08-16 §2): a new dispatch rung costs
16 cycles to every op BEHIND it; placed last before the fall-through, only `reg` ops pay.
Weigh 54 saved per VSRAM op + the ceiling lift against 16 per `reg_set`.

## B2. The load-bearing unknown — this gates the whole part

**"Only CRAM writes glitch mid-line" is a positive claim with one witness** (the handoff says
so and orders it swept before building). The hardware model says VSRAM is read per 2-cell
column during active display, so a mid-line VSRAM write does not paint a DOT — it can TEAR:
columns right of the beam take the new scroll this line, columns left keep the old one. Whether
that is visible depends on where the words land relative to HBlank and whether the affected
columns are moving. Ristar's 42-word fire has an unmeasured artifact profile — it may simply
tear into art where tearing is invisible.

**Design decision contingent on a measurement, and the measurement is designed here:**
a fixture writing N VSRAM words with NO delay at a mid-screen fire over high-contrast
vertically-striped art, N swept over {1, 3, 8, 21}, captured per-scanline. Instrument: this is
a PIXEL question — it lands on oracle-next's per-scanline capture (`ScanlineCapture`), the
first consumer of the switch ruled 2026-08-17, with the DENSITY-EVIDENCE profiler/row method
as fallback if the capture path is not ready. Outcomes:
- **No visible artifact for N <= K**: `OP_VSRAM` ships with no delay and a K-word ceiling
  priced by `fire_cost_cycles` (the scanline budget, not the CRAM dot budget).
- **Tearing visible at any N**: the split still ships the rung (54-cycle saving stands IF the
  delay proves unneeded for words that land in HBlank anyway — measure with delay 0 and N = 3)
  but the ceiling stays 3; the parcel shrinks to a cost-accounting change and says so.

## B3. The shape (contingent on B2)

- `OP_VSRAM`, inserted LAST before the fall-through. Dispatch depths: every stream op
  unchanged; `reg` +16 (94 → 110; a one-`reg` fire 412 → 428 <= 488 — DERIVED from the F1 pin
  plus one rung, to be re-measured not asserted, per the derive-not-copy rule).
- `stream_vsram` emits `OP_VSRAM`; the handler is the `OP_CRAM` body minus the delay, plus
  its own word ceiling.
- Every F-pin behind the insertion point re-measured (RUNGS bump — the F1/F5 pins already
  carry one RUNGS=4→5 re-measurement each in their comments; this is RUNGS=5→6). New fixture
  F9 (1-word `stream_vsram` via `OP_VSRAM`, expected 458 - 54 + 0 = 404, MEASURED not
  assumed). The fixture-pin discipline (8 measurements, 0 residual) is the whole reason the
  model may be trusted; a split that skips re-measurement is refused.
- `EFFECTS_OP_CLASSES.md` §5/§6 updated; `check_density`/`fire_cost_cycles` inherit the new
  class automatically (cost = f(class, depth, words)).
- Byte-changing on both counts (opcode values, emitted twins): repin/refreeze, pair-merge.

## B4. Priced honestly

OJZ today ships ONE `stream_vsram` op (the vscroll-split gate fixture). The immediate win is
54 cycles on one fire and a tax of 16 on every `reg` fire — for shipped content, approximately
NOTHING. The real payload is the ceiling lift (B2-contingent) enabling multi-column VSRAM
work — the per-column deform mode the OJZ showcase's "BG reading deeper" ask points at, and
Ristar's 21-pair precedent. If B2 measures "tearing always visible", Part B's honest verdict
is likely DEFER until content wants the cost accounting — the sweep should treat "do not
ship Part B now" as a first-class outcome.

---

# Open questions FOR THE SWEEP (not the owner yet)

1. A3.3's authored-order ruling — attack it. Especially: is there content (moving bands
   crossing each other) where the author CANNOT express the right winner statically?
2. A3.2's uniform static-push-suppression — is a comptime warn for "earlier patchable band
   swallows a later static" worth its noise?
3. The spacing word doubles as BOTH collision epsilon and density floor. Is one word enough,
   or does a cheap-fire-behind-expensive-fire program lose a row it could have kept?
4. RESOLVED_NONE = $7FFF aliasing PATCH_ANCHOR_NONE's value — same constant, different space
   (world Y vs fire line). Confusable? Should they differ?
5. B2's measurement design — does the fixture actually discriminate? (High-contrast striped
   art, mid-screen fire, per-scanline capture — is there a state where tearing exists but the
   fixture cannot see it?)
6. The RAM cost (24 bytes, two banks) and `RASTER_MAX_RECORDS = 8` — right size?
7. What breaks in `games/sonic4/data/effects/ojz_effects.emp`'s hand twins and the
   `tools/scenes` expectations — enumerate, don't gesture.
