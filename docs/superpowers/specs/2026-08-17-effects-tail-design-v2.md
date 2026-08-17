# DESIGN — the effects tail, revision 2 (post sweep 1)

**Status: r2, delta-sweep pending, then owner sign-off.** Supersedes
`2026-08-17-effects-tail-design.md` (r1). Sweep-1 adjudication:
`../2026-08-17-effects-tail-sweep-adjudication.md` — 24 accepted dispositions folded in here.
Sections changed materially from r1 are marked **[r2]** and are the delta-sweep's subject.

**The price, restated honestly [r2]:** Part A buys ~3 screen rows (OJZ rows 221-223) plus the
general freedom for two PATCHABLE channels to traverse the whole screen. During a genuine
band crossing the later-authored channel's boundary is SUPPRESSED (not displaced — r1's
push-anywhere rule allowed a 100+-row lie and is dead); during a near-collision it is pushed
by at most `spacing` (= 2 for OJZ) rows. **Part B (VSRAM split) is DEFERRED** — corrected
arithmetic makes it a net +26-cycle loss per VSRAM op today, its entire payload is a ceiling
lift gated on a measurement no current instrument can bind to hardware (§B below). "Not worth
it" remains a legitimate verdict on Part A too; that is the owner's call at sign-off.

---

# PART A — patchable-overlap relax with runtime collision resolution

## A1. Corpus + timing contract (unchanged from r1, sweep-verified)

No shipped MD game resolves raster line collisions at runtime — this design argues from the
hardware timing contract. The one-reload-late behaviour (reg $0A consumed at the NEXT
expiry, hardware-tested) is already encoded by the builder's two-back arm slot
(`raster.emp:1067-1072`) and is untouched. Dual-consumer discipline: single producer +
publish (the one shipped counter-example, Ristar, ships a 1-frame skew). All three seats
verified the arm/reload seam claims.

## A2. The design in one paragraph [r2]

Collision resolution moves into ONE main-loop producer, `Raster_ResolveLines`, running
**after `Parallax_CheckBoundary` (and any preset re-latch) and before `Parallax_Update`**
[r2: was after LatchWorldLines — that ordering blinked at every section crossing]. It walks
the patch table in authored order, derives each PATCHABLE record's fire line (latch → clamp
→ suppress, exactly the builder's current rules), resolves patchable-vs-patchable collisions
(§A4), and publishes into a **double-buffered** resolved bank flipped by one atomic word
write [r2: torn-read fix]. Statics are NEVER resolved, pushed, or suppressed — a new
comptime guard keeps every patchable's reach clear of every static (§A3), so the
comptime-adjudicated schedule for statics survives verbatim [r2: closes the
silent-static-suppression class and the C-A falsifier]. The VBlank builder emits what the
bank says, keeping a bounded backstop — suppress unless `prev < L <= 222`, tested BEFORE
the arm store [r2: ascent alone left $FF reachable via prev+256] — so park is unreachable
for arbitrary bank garbage. The parallax overlay reads the same bank with THREE outcomes:
a line (split there), `RESOLVED_SUPPRESSED` (no split), `RESOLVED_NONE` (no record/table —
today's unclamped raw-L split, preserving W0) [r2: r1's single sentinel silently killed the
anchored-overlay-without-program contract].

## A3. Comptime guards [r2]

DELETED: `check_intervals`' disjointness walk and the band budget — **for patchable pairs
only**.

The guard set (each with its negative-lane poison, listed in §A7):
- G-A1: bands individually sane, `3 <= lo <= hi <= 223` screen — unchanged.
- G-A2: patchables in non-descending `band_lo` order; table order is priority order; ties
  legal (authored order is the tiebreak). NOTE this does NOT make table order track screen
  order — that is exactly why suppress-on-inversion (§A4) exists.
- G-A3 **[r2, new]**: **statics are sacrosanct** — for every static record S, every
  patchable EARLIER in table order must satisfy `band_hi_fl + spacing <= S_fl`, and every
  LATER patchable's `band_lo_fl >= S_fl + 1` (the walk already forces later emission below
  S). Statics therefore never collide at runtime, comptime totality holds (a build-green
  static always renders), and guard C-A's earlier/later comparison
  (`raster_dsl.emp:1403-1408` — its falsifier names this parcel) stays sound: every
  patchable's reachable range remains on one side of every static, restores included.
- G-A4: one patchable per channel — **already enforced (GUARD 11,
  `raster_dsl.emp:1330-1355`)** [r2: r1 claimed it was new]; the bank's per-channel view
  rests on it.
- G-A5: `fires.len <= RASTER_MAX_RECORDS` (= 8 proposed).
- G-A6 **[r2]**: the spacing word derivation is PINNED, F-pin style: a comptime ensure that
  `program_spacing == ceil(max(fire_cost_cycles) / RASTER_SCANLINE_CYC)` computed over the
  program's fires, with the value in the message. For OJZ: 2, from the ~628-cycle tint fire
  (NOT pal_restore — the OJZ patched program cannot carry one, CLAIM 6) [r2: provenance].
- G-A7: arm ceiling ensure with derivation in the message (fire lines [2,222], widest gap
  220 <= 255).
- `check_density` retained verbatim for static-static pairs (comptime-adjudicated, and
  G-A3 keeps runtime out of their way). Patchable-involved density is the runtime spacing.

## A4. The resolver [r2]

```
prev = 1;  spacing_k = 1                    // first gap priced by the F0 pin: priming
                                            // fire 286 < 488, so gap 1 is proven
                                            // [r2: fixes the clamp-up floor moving 3->4]
for each record k (table order):
    if static:  publish nothing; prev = S_fl; spacing_k = program_spacing; next
                // G-A3 proves S_fl >= prev + spacing_k already
    L = Effects_Screen_L[ch] - 1
    if L > band_hi_fl:  resolved_ch[ch] = SUPPRESSED; next     // existing rule
    if L < band_lo_fl:  L = band_lo_fl                          // existing clamp-up
    if L < prev:                                                // ORDER INVERSION
        resolved_ch[ch] = SUPPRESSED; next                      // suppress: a boundary
                                                                // 100 rows adrift is a
                                                                // worse lie than absence
    if L < prev + spacing_k:                                    // NEAR-COLLISION
        L = prev + spacing_k                                    // push: bound = spacing
        if L > band_hi_fl: resolved_ch[ch] = SUPPRESSED; next
    resolved_ch[ch] = L;  resolved_rec[k] = L
    prev = L;  spacing_k = program_spacing
```

- Two banks (`Effects_Resolved_*_A/B`), publish into the inactive one, flip
  `Effects_Resolved_Sel` with a single word write — torn reads impossible, IPL untouched
  [r2; ints-off publish rejected in adjudication #1].
- Sentinels: `RESOLVED_NONE = $7FFF` (never written by the walk; the reset state),
  `RESOLVED_SUPPRESSED = $7FFE` [r2]. Non-aliasing with `PATCH_ANCHOR_NONE` verified
  (different space; the inert chain composes).
- Suppressed records do not advance `prev` (subsequence bookkeeping, seat-verified).
- Cost envelope [r2]: <= ~2k cycles worst case at 8 records, main loop (~1.5% of frame
  budget headroom class); the VBlank builder gets CHEAPER (its derive/clamp block collapses
  to a bank read) — a net win inside the tight VBlank bracket. Budget-model row added.

**Priority ruling (unchanged in spirit, bounded in effect [r2]): authored order wins.**
The author expresses priority by fire order — the only knob the corpus has any precedent
for (B&R's authored compositions). What changed: the loser is pushed ONLY within `spacing`
(true near-collision); a genuine inversion suppresses. Rejected again: merge-fires (worse
artifact class, op-count rewriter in VBlank).

## A5. Consumers and lifecycle [r2]

**Builder**: reads `resolved_rec[k]` via the selected bank (RESOLVED_* → `.suppress`);
bounded backstop `prev < L <= 222` BEFORE the arm-byte store / slot shift / prev update.
Two-back slot seam untouched.

**Parallax step 4b**: three-way read of `resolved_ch[ch]`: line → split at `line + 1`;
SUPPRESSED → no split; NONE → the EXISTING unclamped raw-L path (`parallax.emp:803-825`)
— W0 and the anchored-overlay-without-program case preserved byte-for-byte. The `L <= 0`
frame-top state keeps reading the raw latch (unchanged; ship covers the whole screen; all
L<=0 combinations seat-verified consistent).

**`Raster_GetChannelBand` is NOT deleted** [r2]: the debug anchor-nudge hotkey
(`ojz_scroll_test.emp:442-471`) needs band WORDS in world space, which a per-frame resolved
line cannot serve. It is demoted to the debug/authoring accessor: parallax caller removed,
its doc block and the hotkey's "only call site" comment rewritten, sigil carriers
(pins.rs:359, repin.toml:1003, parallax_port.rs:233) stay live through the ordinary repin.

**Lifecycle** [r2]: `Raster_InstallPatched` resets both banks + selector INSIDE the
`Raster_Patch_Tab == 0` window (before the new table publishes — the ordering is
load-bearing and documented like `raster.emp:919-927`), closing new-table/old-bank
aliasing. With the resolver after `Parallax_CheckBoundary`, a section crossing resolves the
NEW table with the NEW latch on the same frame — no blank frame exists at install or
crossing (r1's "empty install frame" is gone, not accepted).

## A6. §5 re-proved (deltas only [r2])

1. No park: (a) resolver output strictly ascending with gaps in [spacing_k, 220]; (b) the
   BOUNDED backstop suppresses anything outside `(prev, 222]` — the $FF byte is
   unreachable for ALL garbage, not just descending garbage. Independent mechanisms, both
   required to fail.
2. Arm ceiling: [2,222] holds on every path (push capped by band_hi <= 222; statics
   comptime-placed).
3. Density: static pairs comptime; emitted patchable pairs >= spacing_k by the walk; first
   gap 1 justified by the F0 pin. Cosmetic class regardless.
4-5. Park-structural + no-build-race: untouched.
6. GUARD 11 + G-A3 close both residuals of old §5.6.

## A7. Gates [r2 — every sweep-C defect answered]

- **Collision scene** (fourth state): expectations are HAND-ARITHMETIC IN PROSE in the
  scenes README table style (`$8A00|(99-1-1) = $8A61` precedent) — never computed by the
  resolver's formula in harness code, never recovered from emitted arms. Independent
  anchor: the authored band words + the pinned spacing word + the rule text.
- **Backstop poison**: requires a mid-frame poke landing after the resolve and before
  VBlank — `ab_runner` gains a `run_to_scanline` step (small, booked in the plan). Poison
  values include the `prev + 256` class (which r1's backstop would have PARKED on).
  Assert: suppression, no park, chain tail intact.
- **Scene index migration**: the header spacing word shifts every live-buffer word index by
  one; the three committed scenes + README derivations are UPDATED IN THE SAME COMMIT as
  the format change. Byte-parity control: compare at semantic offsets (old index i ==
  new index i+1 for all words after the header), the allowed diff enumerated as exactly
  {the inserted spacing word}.
- **Cross-compare**: palette fire line (walked from arm gaps) vs `Parallax_Shadow_Bands`
  split, same frame, against EACH OTHER; `Parallax_Shadow_Bands` added to the scene
  capture regions (infrastructure named, not assumed).
- **Poisons for every new guard**: G-A2 (descending band_lo), G-A3 (patchable band
  touching a static, both orders), G-A5 (9 records), G-A6 (wrong spacing constant), G-A7
  (band edit that breaks the ceiling derivation) — one CASES row each in
  `emp_expect_fail.py` format, via `--extra-entry`.
- **W0 regression scene**: anchored parallax config, NO patched program — split present at
  raw L (the contract r1 nearly deleted; now it has a gate).
- **DoD-1 language**: "no park ever" is PROVED BY CONSTRUCTION (A6.1) and WITNESSED by the
  backstop poison + build-time pins — not exhaustively tested; stated so nobody reads the
  gate list as a universal sweep.
- Budget row for the resolver; re-baseline of the three-state evidence captures (the
  clamp-up floor does NOT move under r2 — B8 fixed — so existing captures stay valid;
  asserted, and if the delta sweep disagrees the captures are re-cut).

---

# PART B — VSRAM op-class split: **DEFER** [r2]

The honest arithmetic (sweep A5/B9): moving `stream_vsram` from rung 1 (`OP_CRAM`) to a new
last-rung `OP_VSRAM` costs the op +80 cycles of its own dispatch against −54 delay saved —
**net +26 per VSRAM op**, plus +16 per `reg` op. The only payload is the ceiling lift, and
its gating measurement cannot currently bind hardware: mid-frame VSRAM visibility is an
emulator-model property (Exodus-derived oracle consults VSRAM continuously; GensKMod latches
at HBlank — the recorded known unknown, `2026-08-14-vsram-planeb-handoff.md:118-120`), this
project has no real hardware, r1's striped-art fixture was translation-invariant (the same
art defeated a measurement once, `:49-51`), and per-scanline capture may be structurally
blind to a per-column tear. The Ristar 42-word precedent is UNCITED pending a disasm
witness.

**Banked here for revival**, with the revival conditions: (1) content actually wants
multi-column VSRAM work; (2) an instrument exists that passes a POSITIVE control (a
documented-hardware column-boundary discontinuity it must reproduce — art varying in Y per
column, per-column phase); (3) the pricing is redone at the placement that survives (early
rung re-taxes the chain and must be priced). Until then `stream_vsram` stays `OP_CRAM`-class
and correctly priced by F7.

---

# Open questions for the DELTA SWEEP (changed mechanisms only)

1. §A4's suppress-on-inversion: is a vanishing boundary during a crossing acceptable
   content behaviour, or does content need a cross-fade/hand-off idiom (out of scope but
   the semantic should not preclude it)?
2. G-A3's static-sacrosanct rule: too strong? (A patchable band may legitimately want to
   sweep past a static reg_set — G-A3 forbids authoring it. Priced: the author splits the
   band or reorders; is that acceptable?)
3. The double-buffered bank + selector: any reader (builder in VBlank) that reads the
   selector then the bank non-atomically — can a flip land between? (One-word selector read
   into a register, then indexed reads — should be safe; verify.)
4. The first-gap spacing_k = 1 seed: sound for a program whose FIRST record is authored at
   band_lo 3 (fire 2)? (F0 says yes; check the arm arithmetic at gap 0... fire 2 - prev 1
   - 1 = 0 = $8A00, the every-line word, legal per §5.1's corollary.)
5. §A7's scene-index migration: is "same commit" enforceable — can the format change and
   scene update land atomically given the auto-commit daemon never touches tools/scenes?
