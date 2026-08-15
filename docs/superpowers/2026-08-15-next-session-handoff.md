# NEXT-SESSION WORK ORDER — 2026-08-15 (rev 2, after P-a merged)

Supersedes rev 1 of this file, which named Parcel P as next. P was **split** on adversarial
review; its encoder half is done.

---

## State at handoff

**Both repos on `master`, green, nothing in flight.**

- aeon `7761de5d` — Merge parcel/effects-p3-p-a: the patch generalisation, encoder half
- sigil `f00408e1` — Merge parcel/effects-p3-p-a: harness lockstep (chain 119)
- refreeze **chain 119** · sigil suite **3716 / 0** across 327 binaries · four shapes boot
- Verified pair. Both `parcel/effects-p3-p-a` branches merged and deleted.

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
```

ROM CRCs: s4 `416be247` · s4.debug `9ef00c29` · demo `6af0112d` · demo.debug `fdc82cc0`

Working tree carries only the pre-existing editor JSON churn — auto-commit-daemon territory.

**PUSHED.** aeon and sigil `master` both match `origin/master` as of this handoff.

(Rev 1 of this file said "aeon is 78 commits ahead, sigil 14", and rev 2 initially did arithmetic on
top of that to claim 89/16. Both were wrong — `git fetch` showed the true divergence was 14 and 2,
so origin had been pushed in between. Verify divergence with `git fetch` before quoting it; a stale
count copied forward reads as fact.)

---

## What P-a shipped, and what it deliberately did not

`patchable(fires, ch, lo, hi)` marks a fire whose line moves at runtime within a screen-line band;
`patched_program` emits the program padded to 128 bytes plus a self-describing patch table at a
constant `+128`. Thirteen build-time guards, each proved by inversion. Fixture `OJZ_TwoChannel`
pinned word-for-word by three hand twins.

**No runtime code exists.** Nothing installs the fixture, nothing walks the table, nothing renders.
That was the point of the split: P-b's entire risk is trusting the table's `arm_off` values, and
P-a proves them byte-exactly first.

Design (P-b fully specified in it): `docs/superpowers/specs/2026-08-15-effects-p3-parcel-p-design.md`
Evidence: `docs/benchmarks/effects-p3-p-a/GATE-EVIDENCE.md`
Authoring: `docs/EFFECTS_AUTHORING.md` · wire format: `docs/ENGINE_ARCHITECTURE.md` §7.13

---

## NEXT — Parcel P-b, the runtime

Read the spec's §6 and §7. The rulings that are already made, so they are not re-litigated:

1. **`Raster_PatchAll` runs at VBlank, not the main loop.** Today's single-word patch gets away with
   main-loop timing because its one arm is consumed at the frame-top rewind. P-b writes one byte per
   record scattered across the buffer while the HInt handler is walking it, and every arm is a
   RELATIVE gap — so a half-updated set desynchronises the entire tail of the chain, on every frame
   the camera moves.
2. **Liveness is `Raster_Patch_Tab != 0`, not `Active_Buf == Buf_B`.** `Raster_VBlank`'s
   explicit-clear path never touches `Active_Buf`, so an `Active_Buf`-gated patcher would keep
   writing a dead buffer forever after a `Raster_Install(0)`. Clear `Patch_Tab` in BOTH teardown
   paths, and set it BEFORE `Active_Buf` at install.
3. **Anchors go INLINE in `EffectsPreset`** (`[u16; RASTER_MAX_PATCH]`, struct 32 → 38), not behind
   a pointer: a `Label` carries no length and an `ensure` comparing one to an integer is unevaluable
   and silently always passes.
4. **Name the RAM `Effects_World_Y[]`, owner-neutral**, and ship `Effects_SetWorldY(ch, y)`. Without
   a setter, "lava that rises" is only expressible by poking RAM at a guessed index. The array must
   stay in RAM (reading the preset's ROM array in place would make anchors immutable and foreclose
   the motivating case).
5. **`clr.w Raster_Dense_Lines` at patched install** — nothing clears it today, so crossing from the
   dense gradient section mid-run leaves the handler streaming a stale cursor.
6. `move.w (Raster_Patch_World_Y, d2.w), d2` **is not a 68000 addressing mode.** Indexed access to an
   absolute array is `lea` + `(An, Dn.w)`, and the routine needs a third address register for it.

### P-b cannot be gated until EFX-8 is fixed

**`docs/BUGS.md` EFX-8: no patched program has rendered since Parcel C2 merged.** Total binding
drove the patched channel past "off" into unreachable. Any gate phrased around "the water boundary"
measures nothing today, and a broken patcher would score identically to a correct one. P-b must
convert an OJZ section's preset to `patched:` — which, by `preset.emp`'s exclusivity ensure, means
that section surrenders its static raster program.

### The gate instrument, ruled 2026-08-15

**`replay_runner` is pixel-blind** — no framebuffer, screenshot or image output of any kind; its
`--negative-control` corrupts a checkpoint payload to prove the HARNESS still detects drift. Owner
ruling: **manual oracle capture with the camera PINNED**, asserting **absolute predicted rows**
(channel *i* at `wy_i - Camera_Y`) at three camera positions including one where each channel clamps
to `lo` and one to `hi`, with distinguishable colours per channel.

Do NOT phrase the claim as "their separation changes" — two world-anchored channels hold a CONSTANT
separation, so that predicate fails correct implementations and passes broken ones. Negative
controls: an overlapping band pair must fail the BUILD, and replacing one anchor with a fixed screen
row must make the separation drift by exactly the camera delta.

---

## Mechanics this parcel paid for — do not rediscover

- **`ensure` does not short-circuit.** One bad input fires every guard it violates; two messages does
  not mean the wrong guard tripped.
- **`first_mismatch` is blind to length in BOTH directions**, not only the prefix case its comment
  described. Deleting a trailing table entry produced no mismatch report at all. The separate `.len`
  ensure beside every twin is load-bearing. (Comment corrected in source.)
- **ROM length is not the measure of added data.** The fixture added 146 bytes and the ROM grew
  **14**; pins moved a uniform **+0x90** and trailing fill absorbed the rest. Measure pin deltas.
- **An unexercised authoring surface is unverified.** `fx_tint_band` shipped broken in Parcel C1 (its
  body called `pal_stage_off`, which resolves at the CALL site) and nothing noticed for two parcels
  because nothing had ever called it. Fixed by inlining at the source, pinned to its authority.
- **Guard proof standard:** inversion (flip false → build MUST fail with its own message → restore),
  PLUS showing the guard accepts the adjacent legal case. A guard needing two independent
  predicates needs both proved separately — guard 6's wrong-record offset passes the word-class test
  and only the value test catches it.
- **Ritual order for a byte-moving parcel:** freeze FIRST, then the strict suite, then
  `refreeze --check` + `repin --check`. Running the suite first reports the golden ROM comparisons
  red, because the freeze is what regenerates them.

---

## Also open, unrelated

- Sound packages **5** and **6**; the `STRESS_EVICT` famine root-cause.
- **A vacuous gate found in passing:** the pins tagged `tests = ["raster_port"]` are consumed by NO
  test — there is no `raster_port` binary in `crates/`. The raster module has no standalone port
  oracle, which is exactly the coverage P-b's runtime rewrite would want. Fill it or declare it.
- **A framebuffer dump for `replay_runner`** — its own oracle-next parcel, and the thing that would
  make every future effects gate deterministic.
- `sigil`'s `deep_nesting_aborts` still aborts without printing a `test result` line, so suite
  totals remain a lower bound. Booked, user-ruled not to chase.
- The demo-shape `.lst` symbol skew (boot_head symbols report 4 bytes high) — ROM is correct.
