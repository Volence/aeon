# ADJUDICATION — effects-tail design r2, DELTA SWEEP (two seats, 2026-08-17)

Subject: the r2-changed mechanisms only — the 24 adjudication-minted fixes from sweep 1, which
were themselves unswept (the R1 lesson). Seats: **D1** mechanisms/timing/state (Opus),
**D2** guard-realizability + gate-vacuity (Sonnet).

20 findings. **20 ACCEPTED, 0 rejected.** Five are design-changing; one inverts the parcel's
value proposition and is the reason r3 is NOT being cut before owner input (see VERDICT).

Adjudicator verification: every finding accepted below with a source claim was re-read against
the file by the adjudicator before acceptance. Line cites in this document are the
adjudicator's own, not the seats'.

---

## The finding that changes the decision

**D1-5 — the three rows Part A buys are exactly the rows that kill OJZ's other shipped
channel.** VERIFIED against the shipped program and its table pin
(`games/sonic4/data/effects/ojz_effects.emp:637-642`, table pin `:673-679`):

- ch0 = tint, band 3..220 (fl 2..219), authored line 100, `offscreen_ship: 1`
- ch1 = `fx_vscroll_split`, band 222..223 (fl 221..222), authored line 222

To buy screen rows 221-223, ch0's `hi` must go to 223 → `band_hi_fl` 222, which overlaps ch1's
`[221,222]` entirely. Resolver arithmetic at `spacing = 2`:

| ch0 emitted (fire line) | ch1 outcome |
|---|---|
| 219 (screen 220) | fl 221 — unchanged |
| 220 (screen 221) | `221 < 222` → push to 222 — **displaced 1 row** |
| 221 (screen 222) | `221 == prev` → push to 223 > band_hi 222 → **SUPPRESSED** |
| 222 (screen 223) | `221 < prev` → inversion → **SUPPRESSED** |

So the parcel's stated payoff rows and its price are the SAME rows. Restated honestly for the
shipped program: today, when the water line is below row 220 the tint record is already
suppressed (`raster.emp:1135-1136`, `bgt .suppress`; `offscreen_ship` covers ABOVE the band,
not below), so rows 221-223 have no tint. After Part A they have tint — and lose the bottom
vscroll split on two of the three. **Part A does not add capability to shipped content; it
changes WHICH effect is absent in a 3-row window.** The general two-patchable-channel freedom
is real, but only cashes out for programs whose channels do not contend for the same rows,
and no such program exists today.

r2's price paragraph ("buys ~3 screen rows") is therefore not honest yet, for the second
revision running. This table belongs in it.

---

## Dispositions — D1 (mechanisms / timing / state)

| # | finding | verdict | r3 action |
|---|---|---|---|
| D1-1 | Install-window bank reset RE-CREATES the one-frame dropout r2 claims to have deleted. Verified: `Raster_InstallPatched` publishes the table as its SECOND instruction (`raster.emp:931`, comment "table first"), the builder's ONLY liveness test is that table (`raster.emp:1102-1103`), and the resolver does not run until control returns through `Effects_InstallPreset` (`preset.emp:288`) and all of `Parallax_StartTransition` (`parallax.emp:224-225`) to the main loop. A VBlank in that window builds an all-suppressed schedule and swaps it live. **Today that same VBlank is CORRECT** (it derives from `Effects_Screen_L`, already re-latched at `preset.emp:247`) — so r2 converts a correct window into a blank one | ACCEPT — regression, not a fix | resolve BEFORE the table is published: pass the incoming table pointer to `Raster_ResolveLines` as a parameter, write the selector, THEN write `Raster_Patch_Tab`. A VBlank then sees either `Patch_Tab == 0` (no-op, the already-accepted behaviour at `preset.emp:214-216`) or a table whose bank is already correct. Bank publish becomes atomic with table publish. The per-frame main-loop resolver stays as-is |
| D1-2 | Only the PATCHED path resets the banks. Verified: `Raster_InstallPatched` is called only on the `ep_patched != 0` branch (`preset.emp:282-288`); `.no_patch` (`:290-296`) calls `Raster_Install` and never touches them; the resolver early-outs on `Patch_Tab == 0` so it never writes NONE either. Crossing patched → non-patched-but-anchored leaves the PREVIOUS section's resolved line live and legitimate-looking. This is byte-for-byte the class `preset.emp:199-227` was written to close ("224/314 surviving the crossing from OJZ section 0 into section 1"), one bank over | ACCEPT | reset both banks + selector UNCONDITIONALLY in `Effects_InstallPreset`, beside `clr.l Raster_Patch_Tab` (`preset.emp:220`), inheriting that proc's total-binding argument verbatim. One site covers `Raster_Install` and the teardown paths too. **Note in the parcel's favour: r2's own W0 regression scene is exactly this configuration and would have gone RED — that gate is not vacuous** |
| D1-3 | The reset state is 0, not `RESOLVED_NONE`. Verified: boot zeroes ALL 64KB with no preserved region and a standing ruling forbidding a carve-out (`engine/system/boot.emp:158-172`). Under r2's three-way read, 0 is neither sentinel — it decodes as "resolved fire line 0" → split at screen line 1 → whole screen deforms, the exact most-invasive-default failure `PATCH_ANCHOR_NONE`'s own doc block refuses (`raster_dsl.emp:1085-1094`). Latency honest: today's reachable pre-install consumer binds `ParallaxConfig_OJZ_Default`, which declares no `anchor_ch` (`configs.emp:107-114`), so step 4b early-outs — it goes live the moment an anchored config is an act default | ACCEPT, **fix improved on the seat's** | seat proposed seeding both banks to `$7FFF` at engine init. Ruled better: **`RESOLVED_NONE = 0`.** Legitimate resolved lines live in `[2,222]` (seat's own verified item 7), so 0 and 1 are both unreachable by the walk — making 0 the NONE sentinel means boot's RAM clear establishes the correct default for free, install's reset becomes a `clr`, and the "someone forgets to seed" class cannot exist. `RESOLVED_SUPPRESSED` stays a distinct non-zero value. This is adjudication-minted and flagged as such |
| D1-4 | G-A3 is ASYMMETRIC (`+ spacing` on the earlier side, `+ 1` on the later side) and admits a build-green patchable that can NEVER render: static at `S_fl`, later patchable band `[S_fl+1, S_fl+1]` → resolver pushes to `S_fl+2` > `band_hi_fl` → suppressed every frame forever. **Today this is a build ERROR**: `check_intervals` admits it (`raster_dsl.emp:1188-1190`) and `check_density` then refuses it — verified, `ensure(cost <= gap * RASTER_SCANLINE_CYC)` at `raster_dsl.emp:1230`, and a 628-704-cycle static at gap 1 fails 488. r2 retires that refusal for every patchable-involved pair and replaces it with a silent runtime push. "Comptime totality restored" is true for statics only; nothing covers patchable totality | ACCEPT | (a) G-A3 becomes SYMMETRIC — later patchables need `band_lo_fl >= S_fl + spacing`; (b) **`check_density` is RETAINED for static→patchable and patchable→static pairs** — with G-A3 pinning which side moves, the worst-case edge arithmetic is still fully comptime. Only patchable↔patchable pairs lose it |
| D1-5 | The rows bought are the rows that kill ch1 | ACCEPT | see "The finding that changes the decision" above; price paragraph rewritten with that table |
| D1-6 | "Authored order wins" is not an independent knob — it is welded to the authored default screen line. Verified: `fire_lines` ensures strictly ascending authored screen lines (`raster_dsl.emp:1243-1253`, ensure at `:1248`), `patchable` ensures the authored line lies inside its own band (`:398-399`), and `compose` emits in ascending line order (`:421-424`). So priority == "lower authored default line wins", and that line is also the shipped template schedule and is band-constrained | ACCEPT | state the REAL rule in §A4 ("the lower authored default line wins; that IS the knob") and stop presenting priority as free. **A separate explicit priority field is REFUSED for now** — new record field = table-format churn + pin churn with no content demand; booked as a future knob if a program ever needs priority to disagree with screen order |
| D1-7 | G-A6's spacing provenance is STILL the wrong fixture — the class disposition 10 claimed to fix. Verified exactly: 628 is fixture F5, `reg_set + stream_cram(3)` (`raster_dsl.emp:1132`); OJZ's tint fire is `reg_sh_on + stream_pal_region(3)` (`ojz_effects.emp:638`). From the model's own anchors — base 302 (`RASTER_FIRE_BASE_CYC = 572/2 + 16`), `reg_set` = 412-302 = 110 (F1), `stream_pal_region(3)` = 566-302 = 264 (F4) — the real fire is **676**, not 628. `ceil(676/488) = 2` | ACCEPT | value 2 unchanged; provenance corrected to 676 with the derivation. **Process ruling: G-A6's pin message must COMPUTE the cost from the program's actual fire via the model, never name a fixture.** Naming fixtures by eye is what produced a wrong number twice |
| D1-8 | §A6.1(a)'s "gaps in [spacing_k, 220]" is false for static-involving pairs: the static path publishes nothing and only sets `prev = S_fl`, and nothing checks `S_fl >= prev + spacing_k`. For `(S1, P, S2)` with P suppressed the emitted gap can be 0 | ACCEPT | proof restated: strictly ascending with gap >= 0 ALWAYS; gap >= `spacing_k` whenever the later record is patchable. Park-safety conclusion survives unchanged (gap >= 0 → byte never $FF) |
| D1-9 | "check_density retained for static-static pairs" is VACUOUS for statics separated by a patchable — it only compares `i, i+1` (`raster_dsl.emp:1215-1231`), so in `(S1, P, S2)` both pairs involve a patchable and both are skipped, while S1→S2 becomes a runtime-reachable consecutive pair whenever P suppresses (D1-8). Both lines are comptime-known; the check is simply lost | ACCEPT | the retained static-static check walks FORWARD to the next static past any suppressible patchables, not only to `i+1`. Composes with D1-4(b) |
| D1-10 | r2 never states that `fire_lines`' strict-ascent ensure is RETAINED, and with `check_intervals`' walk gone it is the only thing left holding (a) static-static ordering and (b) "table order == authored-line order" — which two of r2's own premises need, since guard C-A classifies by authored screen line (`raster_dsl.emp:1445-1447`) while G-A3 speaks table order. An implementer reading G-A2 as the replacement ordering rule voids C-A by the very mechanism its FALSIFIER names | ACCEPT | §A3 states `fire_lines` retention explicitly, with the C-A coupling spelled out |
| D1-11 | Parallax reading `Effects_Resolved_*` + `Effects_Resolved_Sel` is a NEW cross-seam reference and must be declared in sigil's `parallax_port.rs` stub table (whose own comment records "TWO new cross-seam references, and both had to be declared here or this gate stops resolving") plus new `pins.rs` entries. Not mentioned anywhere in r2 | ACCEPT | plan item. This is the documented port-flip ritual — new cross-seam refs break `*_port` tests silently and `build.sh` will not warn |
| D1-12 | "INSIDE the `Raster_Patch_Tab == 0` window" mis-attributes the window and cites the opposite constraint. Verified: the window is opened by `clr.l Raster_Patch_Tab` at `preset.emp:220` (whose note records "a VBlank lands inside this window ROUTINELY"); inside `Raster_InstallPatched` it is one `lea` wide (`raster.emp:930-931`); and r2's citation `raster.emp:919-927` documents the OPPOSITE ordering (table FIRST) | ACCEPT | text corrected to name `preset.emp:220` as the opener; plus an assert/ensure so a future non-preset installer cannot silently lose the window |
| D1-13 | The backstop's insertion point needs a0 bookkeeping: `.suppress` (`raster.emp:1184-1186`) does `addq.l #8, a0`, valid at `:1136`/`:1138` but NOT after the `addq.l #4, a0` at `:1141` | ACCEPT | ruled: put the backstop test at `.have_line` BEFORE `:1141`, reusing the existing `.suppress` entry. No second entry, no 4-byte desync class |
| D1-14 | (a) "no park" is not assertable as phrased — every emitted record STARTS as `$8AFF` from the template and the two youngest slots plus the terminator park deliberately (`raster.emp:1074-1080`, `:1166-1172`); (b) `Raster_BuildSchedule` declares `clobbers(d0-d4/a0-a2)` and cannot widen it, so the bank cursor rides the existing stack frame (`subq.l #8, sp` → 12); (c) the literal `222` should be `RASTER_MAX_FIRE_LINE - 1` | ACCEPT all three | (a) assertable property restated: "no park in a slot belonging to a record with two emitted successors"; (b) frame change named, and §A4's "builder gets CHEAPER" qualified by it; (c) spelled from the constant so a ceiling edit cannot silently un-bound it |
| D1-15 | `RASTER_MAX_PATCH`'s rationale ("FOUR IS NOT A RAM DECISION. The binding constraint is the BAND BUDGET... Raising this without widening the band budget buys nothing", `raster_dsl.emp:1076-1081`) goes stale the moment Part A deletes that budget | ACCEPT | doc-sync in the same commit, per the repo rule |

## Dispositions — D2 (guard realizability / gate vacuity)

| # | finding | verdict | r3 action |
|---|---|---|---|
| D2-1 | G-A3's "later patchable clears earlier statics BY THE WALK" half is unsound if implemented as an extension of `check_intervals`, which carries a SINGLE `prev_hi` overwritten unconditionally — verified `raster_dsl.emp:1183-1193`, `prev_hi = hi_fl` at `:1190`. Counterexample is legal content (G-A2 orders by `band_lo` only, never makes `band_hi` monotonic): `P_wide(10,200)`, `P_narrow(12,15)`, `S(201)` passes a naive walk (`201 > 15`) while `P_wide` reaches fl 200 and violates G-A3's own rule | ACCEPT | merged with D1-4: **G-A3 is rewritten wholesale as one explicit symmetric two-sided scan** (for each static, scan the whole array for patchables before/after it in table order), NOT a patch to `check_intervals`' single-value chain. r2's phrase "the walk already forces later emission below S" is DELETED — it is what invites the unsound implementation |
| D2-2 | The backstop-poison gate is UNRUNNABLE as specified. Verified both sides: `run_to_scanline` polls VCounter once per ~16 ms GUI tick (`oracle/linux-port/gui/ControlSocket.cpp:1895-1898`), and this project ALREADY measured the consequence and filed it — `docs/research/parallax-§4.6.md:118` records a false "1-entry lag" as a measurement artifact, "can land many scanlines past the requested target", with that doc's own recommended fix being a breakpoint inside VBlank. ~16 ms is a whole NTSC frame. A poke aimed between resolve and VBlank can land a frame off, at which point a resolver that suppresses correctly and one that does not look IDENTICAL | ACCEPT — a gate that cannot fail for the right reason | **retires adjudication #12's "ab_runner gains a `run_to_scanline` step"**. Replaced with instruction-precise `breakpoint_add` + `wait_for_break` at the resolver's return / builder entry. Design must state why `run_to_scanline` was rejected so it is not re-proposed |
| D2-3 | `tools/effects_gates.py` is missing from the scene-index migration inventory — verified, `:154-156` hardcodes `--expect-word 1=` / `3=`, which an inserted header word shifts to 2/4 | ACCEPT | **dissolved by the D2-4 ruling below** (no live-buffer index shift → nothing to migrate). Recorded because it is the correct finding against r2 as written, and because it would have been a silent-hand-fix hazard against a file whose own header warns "two gates in this tree were written against copied numbers" |
| D2-4 | r2 never resolves whether the spacing word is COPIED into the live double-buffer or read once from the ROM template — and the whole §A7 parity gate's premise rides on the answer. Verified the header word IS copied today: `raster.emp:1119`, `move.w (a2)+, (a1)+ // pal_dirty_mask` | ACCEPT — real fork, and r2 picks neither | **Ruled, at the minimum-blast-radius placement: the spacing word goes in the PATCH TABLE header (beside the record count), not the body template header, and is never copied into the live buffer.** It is a build-time constant and only the main-loop resolver needs it; the builder walks the table in ROM. Consequences: `OJZ_TC_TABLE_HAND` gains one word (loud — it is a pinned hand twin); the body pin `OJZ_TC_HAND` is untouched; the live buffer is untouched; **the scene-index migration, its semantic-offset parity control, and `effects_gates.py`'s indices ALL DISSOLVE** (adjudication #13 retired). Cost named: the builder pays one `addq.l #2, a0` before reading the count |
| D2-5 | The collision scene's "independent anchor" restates the resolver's own rule, so it verifies the ENCODING, not the rule — a D2-1/D1-4-class bug (rule produces the wrong answer, correctly encoded) reproduces identically in the hand computation and the emitted arms and the gate passes. Not a regression: the shipped three-state gate's `derive_arms` already computes expectations with the exact production formula (`tools/effects_gates.py:72-98` vs `raster_dsl.emp:1267-1270`) | ACCEPT as a RECORDED RESIDUAL | r3 states the limit plainly instead of letting "independent anchor" imply more independence than it has. No fix attempted — the honest mitigation is that D2-1 and D1-4 were caught by REVIEW, which is the control that actually covers this class |

## Standing premises carried forward (seat-verified, adjudicator-spot-checked)

D1's verified-correct list is adopted, notably:

- **The double-buffer flip is genuinely tear-free — but for a better reason than r2 gives.** Not "a one-word selector read into a register": `Raster_BuildSchedule`'s only caller is `Raster_VBlank` (`raster.emp:588`), so the reader runs at interrupt level and the producer at IPL 0 — the producer cannot preempt the reader at all. A VBlank mid-write hits the UNSELECTED bank. r3 restates the invariant as the priority argument, since the register-read phrasing would not survive a future main-loop builder call. Open question 3: **answered YES-safe.**
- **First-gap seed `prev = 1, spacing_k = 1` is sound and the F0 pin does price it** (286 <= 488; min legal first fire line 2; arm word at gap 0 = `$8A00`, the every-line word `Raster_VBlank` already leaves in reg $0A at `:610-613`). Open question 4: **answered YES.** Confirms B8 — the shipped clamp-up floor does not move, so the three-state captures stay valid.
- **`$FF` is unreachable under the bounded backstop**: `prev` seeded 1, `prev < L <= 222` → stored byte in [0,220]; the `prev + 256` class r1 would have parked on is caught.
- **G-A3 IS sufficient for the restore direction**, because a restore's carrying fire and its equal-span partner are both forced static (`raster_dsl.emp:1427-1429`, `:1455-1457`) — conditional on D1-10 (table order == authored order must stay true).
- **Spacing value 2 and the `pal_restore` exclusion hold** (CLAIM 6: OJZ ch0 declares `offscreen_ship: 1`, so the program cannot carry a restore — CLAIM 6's own message names this program).
- **`RASTER_SCANLINE_CYC` and `fire_cost_cycles` are LOCAL to `raster_dsl.emp`** (`:983`, `:1102`), so G-A6 written there does NOT fall into this tree's imported-name silent-vacuity trap (`raster_dsl.emp:14-22`). Integer division and running-max are available; no `ceil`/`max` builtin needed.
- **`Parallax_Shadow_Bands` is real and already precedented as a capture region** (`engine/ram.emp:266`; `docs/benchmarks/effects-p3-w/GATE-EVIDENCE.md:25`).
- **`emp_expect_fail.py`'s `--extra-entry` poison mechanism is real and sentinel-gated against vacuity**; one CASES row per guard is realistic.
- **GUARD 11 already ships** (`raster_dsl.emp:1330-1356`).

## Open unknowns booked, not closed

1. **Width and phase of the D1-1 window** — bounded structurally, not in cycles; whether a VBlank lands there on the shipped build is phase-deterministic (tests green forever, then reproduces 100% on some later build). The finding does not depend on the measurement (r2's claim is "no blank frame EXISTS"), but its severity does. Settling evidence is emulator work, barred to the seats; it is the controller's to run if the parcel proceeds.
2. **`Effects_Resolved_*` RAM sizing** — `RASTER_STATE_SIZE`'s ensure measures the real emitted span (`raster.emp:258-259`), so two banks + selector must be added there and it moves pins. r2 states no RAM figure at all; r1's "24 bytes" is stale under double buffering. Byte-moving parcel regardless.

---

## VERDICT — r3 is deliberately NOT cut yet

Two revisions in, the mechanism set is converging (every structural fix above has a named,
verified landing site). What has NOT converged is the value proposition, and D1-5 is why: for
the only patched program that exists, Part A does not add capability — it swaps which of two
effects is absent in a 3-row window at the bottom of the screen. The generality it buys is
real but currently uncashed.

Against that sits the parcel's now-fully-enumerated cost: symmetric G-A3 as an explicit scan,
`check_density` retained for mixed pairs, resolve-inside-install for atomic publish,
unconditional bank reset, a re-encoded sentinel, a patch-table format change with a pin
update, sigil cross-seam declarations, `RASTER_STATE_SIZE` + pins churn, a breakpoint-based
poison gate, and doc-sync on two comment blocks.

Cutting r3 before the owner answers one content question would be writing a large document for
a parcel that may not want to exist. **The question: in the 3-row window where OJZ's water
line reaches the screen bottom, which effect should survive — the water tint, or the bottom
vscroll split?** "Tint" makes Part A worth its price. "Don't care" or "the split" means Part A
buys nothing for shipped content, and the honest move is to bank the design next to Part B and
spend the parcel elsewhere.

Part B (VSRAM split) remains DEFERRED on sweep 1's ruling; nothing in the delta sweep
disturbed it.
