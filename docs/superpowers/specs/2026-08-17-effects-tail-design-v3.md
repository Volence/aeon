# DESIGN — the effects tail, revision 3.1 (post delta sweep + mini-sweep)

**Status: r3.1, SWEPT (three rounds), awaiting owner sign-off.**
Supersedes `2026-08-17-effects-tail-design-v2.md` (r2). Delta-sweep adjudication:
`../2026-08-17-effects-tail-delta-adjudication.md` (20/20 folded); mini-sweep adjudication
on the adjudication-minted mechanisms: `../2026-08-17-effects-tail-mini-adjudication.md`
(12/12 folded, marked **[r3.1]** below — headline: `resolved_rec[]` DELETED, the bank is
per-channel only, 18 bytes). Sections changed from r2 are marked **[r3]**.

## The price, restated honestly for the third time [r3]

Part A's headline payoff and its price are THE SAME ROWS. Shipped program
(`ojz_effects.emp:637-642`): ch0 tint, band 3..220; ch1 vscroll split, band 222..223. Buying
ch0 rows 221-223 requires `hi: 223`, overlapping ch1's whole band. Resolver outcomes at
spacing 2:

| ch0 emitted (fire line) | ch1 (vscroll split) outcome |
|---|---|
| 219 (screen 220) | fl 221 — unchanged |
| 220 (screen 221) | pushed to 222 — displaced 1 row |
| 221 (screen 222) | push to 223 > band_hi 222 — SUPPRESSED |
| 222 (screen 223) | inversion — SUPPRESSED |

Today rows 221-223 have no tint (the record suppresses past its band; `offscreen_ship` covers
ABOVE, not below). After Part A they have tint and lose the split on two of the three. **For
shipped content, Part A swaps which effect is absent in a 3-row strip; it adds nothing.**

Two facts frame that honestly rather than fatally:

1. **The outcome is authorable, not baked.** Priority is authored order (§A4), so which
   effect survives the strip is a one-line content edit (reorder, or re-band ch0 to 222) —
   revisable forever, no engine consequence.
2. **The real payload is the general freedom — two patchable channels traversing the whole
   screen — and it has a named consumer:** the OJZ BG showcase (Parcel D, owner re-aim
   2026-08-17: multi-band parallax + effects, Aurora-authored). Aurora cannot author freely
   against a comptime disjointness wall; Part A is what removes it.

"Not worth it" remains a legitimate verdict; that is the owner's call at sign-off. **Part B
(VSRAM split) stays DEFERRED** — nothing in the delta sweep disturbed sweep 1's ruling (§B).

---

# PART A — patchable-overlap relax with runtime collision resolution

## A1. Corpus + timing contract (unchanged from r1, sweep-verified twice)

No shipped MD game resolves raster line collisions at runtime — this design argues from the
hardware timing contract. One-reload-late (reg $0A consumed at the NEXT expiry) is already
encoded by the builder's two-back arm slot (`raster.emp:1067-1072`) and is untouched.
Single-producer + publish discipline throughout.

## A2. The design in one paragraph [r3]

Collision resolution is ONE pure routine, `Raster_ResolveLines(a0 = patch table)`, walking
the table in authored order: derive each PATCHABLE record's fire line (latch → clamp →
suppress, the builder's current rules), resolve patchable-vs-patchable collisions (§A4), and
publish into the inactive half of a double-buffered resolved bank, then flip the selector
with one word write. It runs from TWO sites **[r3, replaces r2's single site]**:

- **Per frame** from the main loop, after `Parallax_CheckBoundary` and before
  `Parallax_Update`, reading `Raster_Patch_Tab` (early-out when 0).
- **Inside `Raster_InstallPatched`**, on the incoming table pointer AS A PARAMETER, **before
  `Raster_Patch_Tab` is written** [minted, D1-1] — so the bank publish is atomic with the
  table publish. A VBlank then sees either `Patch_Tab == 0` (no-op; the outgoing program
  holds last frame's arms — the accepted behaviour documented at `preset.emp:214-216`) or a
  table whose bank is already correct. The fresh latch is guaranteed: `Effects_LatchWorldLines`
  runs at `preset.emp:247`, before the install call at `:288`. r2's "resolver after
  CheckBoundary fixes the install frame" was a REGRESSION — it converted a currently-correct
  VBlank window (builder derives from the already-relatched `Effects_Screen_L`) into a blank
  one; see adjudication D1-1.

Statics are NEVER resolved, pushed, or suppressed — G-A3 (§A3) keeps every patchable's reach
clear of every static, both sides, so the comptime-adjudicated schedule for statics survives
verbatim. The VBlank builder emits what the bank says behind a bounded backstop (§A5). The
parallax overlay reads the same bank with three outcomes: a line, SUPPRESSED, or NONE
(today's unclamped raw-L split, preserving W0).

## A3. Comptime guards [r3]

DELETED: `check_intervals`' disjointness walk and the band budget — **for
patchable-vs-patchable pairs only**. RETAINED EXPLICITLY [r3, D1-10]: `fire_lines`' strict
screen-line ascent (`raster_dsl.emp:1248`) — with the walk gone it is what still holds
(a) static-static ordering and (b) "table order == authored-line order", and premise (b) is
what guard C-A's earlier/later classification (`raster_dsl.emp:1445-1447`, authored-line
space) needs to keep matching G-A3's table-order phrasing. G-A2 is NOT a replacement
ordering rule.

The guard set (each with its negative-lane poison, §A7):

- G-A1: bands individually sane, `3 <= lo <= hi <= 223` screen — unchanged.
- G-A2: patchables in non-descending `band_lo` order; ties legal. Does NOT make table order
  track screen order — exactly why suppress-on-inversion exists.
- G-A3 **[r3, rewritten — symmetric, and specified as a SCAN]**: statics are sacrosanct.
  **One explicit two-sided pass, NOT an extension of `check_intervals`' single-`prev_hi`
  chain** (which is unsound here: G-A2 never makes `band_hi` monotonic, so a wide early
  patchable hides behind a narrow later one — adjudication D2-1). For every static S, scan
  ALL records: every patchable EARLIER in table order must satisfy
  `band_hi_fl + spacing <= S_fl`; every LATER patchable must satisfy
  `band_lo_fl >= S_fl + spacing` [r3: was `+ 1` — the asymmetry admitted a build-green
  patchable that could never render, D1-4]. Statics then never collide at runtime, comptime
  totality holds for statics, and C-A stays sound (every patchable's reach is on one side of
  every static, restores included — the restore's carrying fire and its equal-span partner
  are both forced static, `raster_dsl.emp:1427-1429`, `:1455-1457`).
- G-A4: one patchable per channel — already enforced (GUARD 11, `raster_dsl.emp:1330-1356`).
- G-A5: `fires.len <= RASTER_MAX_RECORDS` (= 8 proposed).
- G-A6: the spacing word is PINNED by a comptime ensure that **COMPUTES the max fire cost
  from the program's actual fires via the model** — the message carries the computed number,
  never a fixture name [r3: fixture-naming produced a wrong provenance twice; D1-7]. For
  OJZ: `reg_sh_on + stream_pal_region(3)` = 302 + 110 + 264 = **676** cycles →
  `ceil(676/488) = 2`. (`RASTER_SCANLINE_CYC` and `fire_cost_cycles` are LOCAL to
  `raster_dsl.emp` (`:983`, `:1102`), so this guard does not fall into the imported-name
  vacuity trap; ceil spelled `(c + CYC - 1) / CYC`.)
- G-A7: arm ceiling ensure with derivation in the message (fire lines [2,222], widest gap
  220 <= 255, matching `arm_at`'s module-level reasoning).
- `check_density` **[r3, D1-4b/D1-9]**: retained for static-static pairs AND for
  static↔patchable pairs (G-A3 pins which side moves, so the worst-case edge arithmetic is
  still fully comptime). For static-static it walks FORWARD past any intervening patchables
  to the next static (a suppressed patchable makes S1→S2 a runtime-reachable consecutive
  pair; `i,i+1`-only would go vacuous). Only patchable↔patchable pairs lose it — their
  density is the runtime spacing.

## A4. The resolver [r3]

```
prev = 1;  spacing_k = 1                    // first gap priced by the F0 pin (286 < 488)
for each record k (table order):
    if static:  publish nothing; prev = S_fl; spacing_k = program_spacing; next
                // G-A3 proves S_fl clears every patchable; static-static ascent is
                // fire_lines'. NOTE: a static gap may be < spacing (statics are
                // comptime-priced by check_density, not by the runtime word).
    L = Effects_Screen_L[ch] - 1
    if L > band_hi_fl:  resolved_ch[ch] = SUPPRESSED; next     // existing rule
    if L < band_lo_fl:  L = band_lo_fl                          // existing clamp-up
    if L < prev:                                                // ORDER INVERSION
        resolved_ch[ch] = SUPPRESSED; next
    if L < prev + spacing_k:                                    // NEAR-COLLISION
        L = prev + spacing_k                                    // push: bound = spacing
        if L > band_hi_fl: resolved_ch[ch] = SUPPRESSED; next
    resolved_ch[ch] = L
    prev = L;  spacing_k = program_spacing
```

**[r3.1] There is no `resolved_rec[]` — the bank is per-channel ONLY.** The mini-sweep
proved a record-indexed array unsound twice over: suppress paths and statics never wrote it,
so under double-buffering a suppressed record's slot served a two-frame-stale IN-RANGE line
the backstop provably cannot reject (palette/scroll divergence — the class this machinery
exists to prevent), and a literal builder read of a static's slot suppressed statics as a
class. Per-channel is total by construction: every resolver path writes `resolved_ch[ch]`
(a line or SUPPRESSED) for every channel WITH a record, and channels without records stay
NONE in both banks via the install reset. The builder already decodes the channel index
from `line_src` (`raster.emp:1130-1131`); GUARD 11 makes channel→record unambiguous.
Statics never touch the bank at all — they keep today's literal `line_src` path
(`bpl .have_line`) untouched.

- **Sentinels [r3, minted]: `RESOLVED_NONE = 0`, `RESOLVED_SUPPRESSED = 1`.** Legitimate
  resolved lines live in [2,222] (min: `patchable` lo >= 3 → fl 2; max: hi <= 223 → fl 222),
  so both are unreachable by the walk. Zero-as-NONE means boot's 64KB clear
  (`boot.emp:158-172`, no preserved region — a standing ruling) establishes the correct
  default for free, bank reset is a `clr`, and the forgot-to-seed class cannot exist
  [replaces r2's `$7FFF`, which decoded boot-state 0 as "split at screen line 1" — the
  most-invasive-default failure `PATCH_ANCHOR_NONE`'s own doc block refuses,
  `raster_dsl.emp:1085-1094`; D1-3]. Bonus: the builder's bounded backstop (`prev < L`,
  prev >= 1) rejects 0 and 1 arithmetically — the builder needs NO separate sentinel test.
  A channel with no record is simply never written: it stays NONE.
- Two banks, publish into the inactive one, flip `Effects_Resolved_Sel` with a single word
  write. **The tear-freedom argument is PRIORITY, not word-size** [r3]: the builder's only
  caller is `Raster_VBlank` (`raster.emp:588`), so the reader runs at interrupt level and
  the producer at IPL 0 — the producer cannot preempt the reader; a VBlank landing mid-write
  hits the unselected bank. (The one-word flip still matters for the parallax reader, which
  IS main-loop code — but it runs after the resolver in the same frame, same context, so no
  interleaving exists there either.) A future main-loop builder call would void this
  argument; that is why it is stated as the invariant.
- Suppressed records do not advance `prev` (matches the builder: `.suppress` skips the slot
  shift and the `move.w d2, d0`, so "two back" already means two EMITTED back).
- Output shape [r3, D1-8]: strictly ascending with gap >= 0 ALWAYS; gap >= `spacing_k`
  whenever the LATER record is patchable. (Static-involving gaps can be 0 — legal, priced at
  comptime.) Park-safety needs only gap >= 0.
- Cost envelope: <= ~2k cycles worst case at 8 records, main loop; the VBlank builder's
  derive/clamp block collapses to a bank read — cheaper in-bracket, **but its bank cursor
  rides the existing stack frame (`subq.l #8, sp` → 12 bytes): `clobbers(d0-d4/a0-a2)`
  cannot widen** (`raster.emp:1091-1095`) [r3, D1-14b].

**Priority ruling, stated as the real rule [r3, D1-6]: the lower authored default line wins —
that IS the knob.** Three surviving guards weld table order to authored screen-line order
(`fire_lines` ascent; `patchable`'s line-inside-band, `raster_dsl.emp:398-399`; `compose`'s
ascending emission, `:421-424`), so an author who wants channel B to beat channel A gives B
the lower default line, even where the default is visually meaningless at runtime. An
explicit priority field is REFUSED for now (record-format + pin churn, no content demand);
booked as the future knob if a program ever needs priority to disagree with screen order.

## A5. Consumers and lifecycle [r3]

**Builder [r3.1]**: for PATCHABLE records only, reads `resolved_ch[ch]` via the selected
bank (ch decoded from `line_src` exactly as today); statics keep the literal path and never
read the bank. Bounded backstop —
**suppress unless `prev < L <= RASTER_MAX_FIRE_LINE - 1`** [r3: spelled from the constant
(`raster.emp:903`) so a ceiling edit cannot silently un-bound it, D1-14c] — **placed at
`.have_line`, BEFORE the `addq.l #4, a0`** (`raster.emp:1141`), where a0 still points at
`band_lo` and the existing `.suppress` entry's `addq.l #8` bookkeeping is correct [r3: r2's
"before the arm store" placement sat after the +4 and would have desynced the table walk by
4 bytes, D1-13]. Statics pass through `.have_line` too — with their literal `line_src`
value, never a bank read; the backstop is redundant for them by construction (mini-sweep
verified: earlier patchables emit ≤ `S_fl - spacing` under symmetric G-A3; the shipped
adjacent-static zero-gap case passes strict `prev < L` with gap byte 0), and free. Stored
gap byte lands in [0, 220]; $FF is unreachable for ALL garbage including the `prev + 256`
class and both sentinels. Two-back slot seam untouched.

**Install-site plumbing [r3.1]**: the resolve call goes after `lea RASTER_BUF_SIZE(a0), a1`
(`raster.emp:930`) and before the `:931` table store; a0 (template) is dead after `:930`.
`Raster_ResolveLines` MUST fit `clobbers(d0-d4/a0-a2)` — the budget is exactly exhausted
(table cursor, bank cursor, latch base, prev, spacing, L, line_src, count), so a1
round-trips the call on the stack; widening the declaration propagates up the caller chain
(the d5 precedent, `raster.emp:1029-1036`). On a crossing frame the table is resolved TWICE
(install site, then the same frame's per-frame site) — idempotent by construction (both read
the latch seeded at `preset.emp:247`), one extra walk + flip; crossing frames pay the cost
envelope twice. Documented so nobody "fixes" it.

**Parallax step 4b**: three-way read of `resolved_ch[ch]`: >= 2 → split at `line + 1`;
1 (SUPPRESSED) → no split; 0 (NONE) → the EXISTING unclamped raw-L path
(`parallax.emp:803-825`) — W0 and anchored-overlay-without-program preserved byte-for-byte.
One compare picks the sentinel class (`cmpi.w #2 / blt`). The `L <= 0` frame-top state keeps
reading the raw latch (unchanged).

**`Raster_GetChannelBand`**: NOT deleted — demoted to the debug/authoring band-words
accessor (hotkey `ojz_scroll_test.emp:442-471` stays a caller); parallax caller removed; doc
block + "only call site" comment rewritten; sigil carriers (pins.rs:359, repin.toml:1003,
parallax_port.rs:233) live through the ordinary repin.

**Lifecycle [r3, both install paths]**:
- **Unconditional reset [r3.1]**: BOTH banks + selector are cleared FULLY (18 bytes — 2
  banks × 4 channel words + selector) in `Effects_InstallPreset` beside
  `clr.l Raster_Patch_Tab` (`preset.emp:220`), inheriting that proc's total-binding argument
  verbatim — gating it on `ep_patched` re-opens the stale-bank inheritance class that
  `preset.emp:199-227` documents closing (the 224/314 crossing witness), one bank over
  [D1-2]. Clearing only the SELECTED bank re-opens the stale-slot class through the other
  bank's first flip — both, always. Two ordering constraints, both load-bearing: table
  cleared FIRST, then banks (a VBlank between sees table 0 → no-op); and the clear strictly
  PRECEDES the install call, which publishes into one of the banks being cleared. This one
  site also covers `Raster_Install` and the VBlank teardown paths (verified: the only
  runtime callers of both installers are `Effects_InstallPreset`; teardown runs over
  already-cleared banks).
- **Atomic publish**: `Raster_InstallPatched` resolves the incoming table (parameter, not
  the global) into the inactive bank and flips the selector BEFORE its
  `move.l a1, Raster_Patch_Tab` [minted, D1-1]. No window exists in which a live table has a
  reset bank. The `Patch_Tab == 0` window itself is OPENED at `preset.emp:220` (not inside
  `Raster_InstallPatched`, where it is one `lea` wide) [r3: r2 mis-attributed it and cited
  `raster.emp:919-927`, which documents the OPPOSITE ordering; D1-12]. An ensure/assert is
  added so a future non-preset installer cannot silently lose the window.
- A section crossing therefore resolves the NEW table with the NEW latch inside the install
  itself; the per-frame resolver keeps it fresh from then on. No blank frame exists at
  install or crossing — now by construction, not by ordering luck.

**Cross-seam [r3.1, D1-11 + M1-F6]**: parallax reading `Effects_Resolved_*` +
`Effects_Resolved_Sel` is a NEW cross-seam reference — declared in sigil's
`parallax_port.rs` stub table plus new `pins.rs` entries. The stub table is a HAND edit,
not repin fallout: the `Raster_GetChannelBand` outbound stub is removed (its parallax call
dies) in the same edit that adds the bank stubs. Port-flip ritual applies; `build.sh` will
not warn.

**RAM [r3.1]**: two banks × 4 channel words + selector = **18 bytes** (was 50 with
`resolved_rec[]`), added to `RASTER_STATE_SIZE`'s span ensure (`raster.emp:258-259`) — it
measures the real emitted span, so this moves pins. Byte-changing parcel regardless.

**The spacing word [r3.1 — full reader enumeration]**: lives in the PATCH TABLE header —
layout PINNED as **`[count][spacing]`** (count stays word 0) — NOT in the body template, and
never copied into the live buffer. The trailer MOVES: `ship_trailer` is emitted immediately
after the patch table (`raster_dsl.emp:1771-1772`), so every reader below adjusts +2 in the
SAME commit:
  - `Raster_BuildSchedule`'s record walker (`raster.emp:1125`) — one `addq.l #2, a0`
  - `Raster_ResolveLines` (new) — same skip
  - `Raster_InstallPatched`'s trailer-offset arithmetic (`raster.emp:949-954` + the layout
    comment at `:934-935`) — misreading this corrupts the ship entry of the ONLY shipped
    patchable config (OJZ ch0 `offscreen_ship: 1`)
  - `Raster_GetChannelBand`'s walker (`raster.emp:1237-1246`), retained as the debug accessor
  - `patched_words` (`raster_dsl.emp:1751-1752`) and `check_rec_layout`'s entry index
    (`:1719`)
  - the ALREADY-stale trailer comment at `raster_dsl.emp:1623` ("8*records" — records are 10
    bytes) — fixed here because it is precisely the copied-number class this change trips
Consequences: `OJZ_TC_TABLE_HAND` gains one word (loud — three independent ensures trip on
any table-shape change, `ojz_effects.emp:665-668/:714/:724-726`); the body pin `OJZ_TC_HAND`
untouched; live-buffer indices untouched (verified: `effects_gates.py`'s `--expect-word`
targets are live-buffer arm words the table header never enters; sigil carries no
table-offset pins, symbol pins only) — r2's ENTIRE scene-index migration stays dissolved.

## A6. §5 re-proved (deltas only) [r3]

1. No park: (a) resolver output ascending with gap >= 0 always (>= spacing_k when the later
   record is patchable); (b) the bounded backstop suppresses anything outside
   `(prev, RASTER_MAX_FIRE_LINE - 1]` — the $FF byte unreachable for ALL garbage. Independent
   mechanisms, both required to fail. The assertable runtime property is **"no park in a
   slot belonging to a record with two emitted successors"** — templates seed $8AFF and the
   two youngest slots + terminator park DELIBERATELY (`raster.emp:1074-1080`, `:1166-1172`),
   so "no $8AFF in the buffer" is unsatisfiable as a predicate [D1-14a].
2. Arm ceiling: [2,222] on every path (push capped by band_hi <= 222; statics comptime).
3. Density: static-involved pairs comptime (retained check, forward-walking); emitted
   patchable pairs >= spacing_k; first gap 1 justified by the F0 pin (arm word at gap 0 =
   $8A00, the every-line word `Raster_VBlank` already leaves primed, `raster.emp:610-613`).
4-5. Park-structural + no-build-race: untouched.
6. GUARD 11 + symmetric G-A3 close both residuals of old §5.6.

## A7. Gates [r3]

- **Collision scene**: expectations are hand-arithmetic prose in the scenes README style,
  from the authored band words + the pinned spacing word + the rule text. **Recorded
  residual, stated plainly [D2-5]: this verifies the ENCODING of the rule, not the rule —
  a wrong rule correctly implemented reproduces identically in the hand computation and the
  emitted arms.** Same limit as the shipped three-state gate (`derive_arms` uses the
  production formula). The control that covers rule-wrongness is adversarial review, which
  caught D1-4 and D2-1; no gate is pretended into that role.
- **Backstop poison [r3, replaces r2's mechanism]**: the poke must land after resolve and
  before VBlank. `run_to_scanline` is REJECTED — it polls VCounter once per ~16 ms GUI tick
  (`ControlSocket.cpp:1895-1898`), i.e. whole-frame granularity, and this project already
  filed the consequence as a false measurement (`docs/research/parallax-§4.6.md:118`). A
  poke that misses the window makes a correct and a broken resolver indistinguishable — the
  gate could not fail for the right reason. Instrument: **instruction-precise
  `breakpoint_add` + `wait_for_break`** at the resolver's return (poke there) with the
  assert read after the next VBlank. Poison values include the `prev + 256` class and both
  sentinels poked into channel slots [r3.1]. Assert: suppression, no park in an
  emitted-successor slot, chain tail intact.
- **Scene-index migration: DISSOLVED** — the spacing word's table-header placement moves no
  live-buffer index (§A5). The table pin update is covered by the ordinary
  `OJZ_TC_TABLE_HAND` ensure, which is loud by construction.
- **Cross-compare**: palette fire line (walked from arm gaps) vs `Parallax_Shadow_Bands`
  split, same frame, against each other; `Parallax_Shadow_Bands` is real, RAM-declared
  (`engine/ram.emp:266`) and precedented as a capture region (effects-p3-w GATE-EVIDENCE).
- **Poisons for every guard [r3.1 — two added]**: G-A2 (descending band_lo), G-A3 two-record
  (patchable touching a static, BOTH sides — the later-side poison at `S_fl + 1` is the one
  r2's asymmetric guard would have PASSED), **G-A3 three-record [M2-2]** (two same-side
  patchables with NON-MONOTONIC `band_hi` — `P_wide`, `P_narrow` — then a static: refused by
  the full scan, wrongly ADMITTED by a single-`prev_hi` chain; the poison that catches a
  regression to "extend check_intervals"), G-A5 (9 records), G-A6 (wrong spacing constant),
  G-A7 (ceiling-breaking band edit), retained-density two-record (static-patchable at gap 1
  — today's refusal, must stay a refusal), **retained-density three-record [M2-3]**
  (`(S1, P, S2)` where S1↔S2 violates density only across the suppressible P — invisible to
  an `i,i+1`-only walk). One CASES row each, `emp_expect_fail.py` `--extra-entry`
  (sentinel-gated against vacuity; verified real).
- **W0 regression scene**: anchored parallax config, NO patched program — split present at
  raw L. Under r2-as-written this scene would have been RED (stale-bank class, D1-2) — it is
  not vacuous; it stays.
- **Install-crossing scene [r3, new]**: scripted section crossing (patched → patched and
  patched → anchored-unpatched), asserting no all-suppressed frame and no inherited resolved
  line — the D1-1/D1-2 witnesses.
- **DoD-1 language**: "no park ever" is proved by construction (A6.1) and witnessed by the
  poison gate — not exhaustively tested.
- **Doc-sync in the same commit [D1-15]**: `RASTER_MAX_PATCH`'s rationale
  (`raster_dsl.emp:1076-1081` — "the binding constraint is the BAND BUDGET") is rewritten
  when the budget dies; the `preset.emp:199-227` window comment gains the bank-reset
  sentence; §A5's ensure guards the window's single-caller assumption.
- **Atomic landing cluster [r3.1, M2-4]**: the RAM widening (`ram.emp` +
  `RASTER_STATE_SIZE`), the resolver proc, BOTH call sites, the parallax consumer switch,
  and the sigil `pins.rs`/`parallax_port.rs` declarations land as ONE commit. Staging the
  main-loop site before the install site reproduces D1-1's regression exactly — the
  intermediate commit would be red on this design's own install-crossing gate — and a
  resolver landing before the sigil declarations breaks the port gate SILENTLY. (Single-op
  landing precedent: Parcel R1.) The table-format +2 and its reader set are separable and
  can land first.
- Budget row for the resolver; the three-state captures stay valid (clamp-up floor does not
  move — confirmed by the delta sweep's F0 verification).

---

# PART B — VSRAM op-class split: DEFER (unchanged from r2)

Sweep-1 ruling stands, undisturbed by the delta sweep: corrected arithmetic is net +26
cycles per VSRAM op, the payload is a ceiling lift gated on a measurement no current
instrument can bind to hardware (the emulator-model known-unknown,
`2026-08-14-vsram-planeb-handoff.md:118-120`), and the fixture-art trap is on record. Banked
with revival conditions: (1) content wants multi-column VSRAM work; (2) an instrument passes
a positive control (a documented-hardware column discontinuity it must reproduce); (3)
pricing redone at the surviving placement. Until then `stream_vsram` stays `OP_CRAM`-class,
priced by F7.

---

# Mini-sweep: CLOSED [r3.1]

All five minted-mechanism questions were answered by the mini-sweep (two seats, 12/12
findings accepted — `../2026-08-17-effects-tail-mini-adjudication.md`): (1) install-site
plumbing feasible, constraints now stated in §A5; (2) sentinels sound, and the one real
defect found — the stale `resolved_rec[]` slot — is fixed by deleting the array (§A4);
(3) the trailer DOES move — full reader enumeration in §A5; (4) reset topology verified
closed, both-banks + ordering constraints stated; (5) statics cannot fail the backstop, and
with the bank per-channel they never read it at all.

# Open measurements (controller, foreground — not sweep work)

- **D1-1 window width on the shipped ROM**: breakpoint at `raster.emp:931` + VCounter read
  across a scripted crossing — severity evidence for the record (the fix stands regardless).
- The RAM figure (18 bytes, r3.1) folded into `RASTER_STATE_SIZE` + pin churn at
  implementation.
