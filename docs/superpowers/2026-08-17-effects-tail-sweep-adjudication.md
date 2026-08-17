# ADJUDICATION — effects-tail design r1, sweep 1 (three seats, 2026-08-17)

Seats: A hardware/timing (Fable), B correctness/state (Opus), C gate-vacuity (Sonnet).
26 findings raised; dispositions below. Verification: every ACCEPTED finding with a source
claim was re-checked by the adjudicator against the file before acceptance; the one
inter-seat CONFLICT was resolved by direct code read.

## The conflict, ruled

**A verified "W0 semantics genuinely preserved"; B defect 1 says the design kills them. B is
RIGHT.** `parallax.emp:803-825`: the no-band path splits UNCLAMPED at raw L (its comment:
the 224 screen test is "the NO-BAND-DECLARED path's only threshold"); `raster.emp:1217-1220`
says "an unclamped [0,224] is correct". r1's single sentinel mapped "no record/no table" to
NO SPLIT — a behaviour change presented as equivalence. A's check was shallower (it verified
the RESOLVED_NONE default exists, not what the default MEANS against today's contract).

## Dispositions

| # | seat:finding | verdict | r2 action |
|---|---|---|---|
| 1 | A1 torn bank read by VBlank mid-resolve | ACCEPT | double-buffered resolved banks + one-word atomic flip (mirrors Raster_Buf_A/B idiom); ints-off publish REJECTED (touches IPL in main loop for no RAM saving worth having) |
| 2 | A2+B4 spacing floor suppresses comptime-admitted statics; C-A falsifier (`raster_dsl.emp:1403-1408`, verified verbatim) | ACCEPT, stronger fix | **overlap freedom is patchable-vs-patchable ONLY**: new comptime guard — every static's fire line must clear every EARLIER patchable's `band_hi_fl + spacing`; later patchables clear earlier statics by the walk. Statics can then never be pushed or suppressed at runtime, comptime totality restored, C-A stays sound (statics remain on one side of every patchable's reach) |
| 3 | A3+B3 unbounded push displacement; A5 price false | ACCEPT | rule split: `L < prev` (genuine order inversion) → SUPPRESS; `prev <= L < prev+spacing` (true near-collision) → push to `prev+spacing`. Displacement bound = spacing BY CONSTRUCTION; r1's A5 claim becomes true instead of being deleted |
| 4 | B1 RESOLVED_NONE conflates four states, kills W0 | ACCEPT (the ruled conflict) | two sentinels: `RESOLVED_NONE` (no record/no table → parallax does today's unclamped raw-L split) vs `RESOLVED_SUPPRESSED` (record present, dropped this frame → no split) |
| 5 | B5 backstop bounds ascent not the gap byte ($FF reachable via prev+256); placement after the arm store corrupts slot bookkeeping | ACCEPT | backstop = suppress unless `prev < L <= 222` (gap <= 221, park unreachable for ALL garbage), branch BEFORE the arm-byte store/slot shift/prev update |
| 6 | B6 resolver placed before Parallax_CheckBoundary → one-frame blink at every section crossing | ACCEPT | resolver runs AFTER Parallax_CheckBoundary (and the preset re-latch) and before Parallax_Update; the install-frame empty schedule thereby vanishes entirely |
| 7 | B2 install aliasing: new table + old bank | ACCEPT | banks reset inside the `Raster_Patch_Tab == 0` window (before the new table publishes); ordering documented load-bearing like `raster.emp:919-927` |
| 8 | B8 priming collision: spacing 2 pushes shipped clamp-up floor screen 3→4 | ACCEPT | first-iteration spacing = 1, justified by the F0 pin (priming fire 286 < 488); program word applies from the second record on |
| 9 | B7 GetChannelBand has a second live caller (debug hotkey, verified `ojz_scroll_test.emp:442-471`) + sigil carriers (verified pins.rs:359, repin.toml:1003, parallax_port.rs:233) | ACCEPT | **NOT deleted**: demoted to the debug/authoring band-words accessor; parallax caller removed; contract note + hotkey's "only call site" comment updated; carriers unchanged (repin still runs — byte-changing parcel regardless) |
| 10 | A5+B9 F9 mis-derived (+80 own dispatch, net +26 LOSS); B10a spacing provenance (tint ~628, not pal_restore — OJZ program cannot carry a restore, CLAIM 6) | ACCEPT | pricing corrected; spacing value 2 unchanged, provenance fixed |
| 11 | A4+A6+C4 Part B instrument: measures the emulator's VSRAM latch model (recorded known unknown, `2026-08-14-vsram-planeb-handoff.md:118-120`); striped art defeated a measurement once already (`:49-51`); no positive control; per-scanline capture may be structurally blind to per-column tear | ACCEPT, verdict changed | **Part B → DEFER** (design banked, not shipped): corrected pricing is a net loss today, the payload is the B2-contingent ceiling lift, and B2 cannot bind hardware with current instruments. Revisit when content demands multi-column VSRAM AND an instrument passes the positive control. Ristar 42-word claim marked UNCITED pending a disasm witness |
| 12 | C1 backstop poison overwritten before builder reads it | ACCEPT | gate redesigned: needs a mid-frame poke (ab_runner gains a `run_to_scanline` step — small harness addition, booked as part of the plan) landing after resolve, before VBlank; plus the bounded backstop makes "any garbage" assertable |
| 13 | C2 header-word insertion shifts every scene word index silently; byte-parity control imprecise | ACCEPT | the three scenes + README indices enumerated for update in the plan; parity control specified as semantic-offset comparison with the allowed diff named |
| 14 | C3 collision-scene expectations circular as phrased | ACCEPT | expectations = hand-arithmetic prose in the README table style, never computed by the resolver or recovered from emitted arms |
| 15 | C5 new comptime guards need enumerated poison CASES rows | ACCEPT | r2 lists each guard with its poison |
| 16 | C6 DoD-1 language conflates proved-by-construction with tested | ACCEPT | stated explicitly in r2's gate section |
| 17 | C7 spacing word not pinned | ACCEPT | comptime ensure deriving it from `fire_cost_cycles` over the program, F-pin style |
| 18 | C8 cross-compare needs parallax-side capture regions | ACCEPT | `Parallax_Shadow_Bands` added to scene regions; named in the plan |
| 19 | A8a resolver cost unbounded in draft | ACCEPT | envelope stated (~<=2k cyc worst case main-loop, builder gets CHEAPER); budget-model row added |
| 20 | A8b + B10c dead `L > 222` rule | ACCEPT | labelled backstop-only |
| 21 | B10b GUARD 11 already ships | ACCEPT | r1's "now REQUIRED" corrected to "already enforced (GUARD 11)" |
| 22 | B10d band_lo ordering does not make table order track screen order | ACCEPT | noted as exactly why disposition 3's suppress-on-inversion exists |
| 23 | A on W0 preservation | OVERRULED by B1 (see conflict) | — |
| 24 | C's table row "old-guard-refuses/new-build-accepts poison adequate" | CONFIRMED sound | kept |

Verified-correct lists from all three seats (arm/reload seam, [2,222] bounds, chained-push
soundness, lag-frame staleness, frame-top ship consistency, RESOLVED_NONE vs
PATCH_ANCHOR_NONE non-aliasing, RAM arithmetic, OJZ shipped values) are carried into r2 as
standing premises.

## Process note

Every fix above is adjudication-minted and therefore UNSWEPT (the R1 lesson). r2 gets a
focused delta re-sweep (two fresh seats on the changed mechanisms only) before owner
sign-off.
