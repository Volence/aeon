# The off-screen frame-top ship — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** When a patch channel's world anchor goes ABOVE the screen, the effect it drives covers the
whole screen instead of pinning at its band floor. For OJZ that means fully submerged actually looks
submerged — today the top 2 rows render exactly as if you were bone dry.

**Architecture:** One latch, three readers, zero new decoders. The main loop latches the unclamped
per-channel screen line `L` once; `Raster_PatchAll`, the parallax overlay and the palette enqueue all
read that one value. A patched program carries, in a ROM trailer generated from the fire's own
arguments, a ready-made `DMAEntry` that re-ships the fire's colours at frame top; install stores a
pointer to it, `Enqueue_Dirty_Buffers` ships it on the frames `L <= 0`.

**Tech Stack:** `.emp` (68000), sigil toolchain. No `.emp` test runner — a guard is proved by a
**failing build**; runtime behaviour is proved on oracle.

**Spec:** `docs/superpowers/specs/2026-08-15-water-offscreen-state-design.md` — **read §0 and §1
only.** The body below them is a REJECTED draft kept for its reasoning; do not build from it.
**Before-measurement (the gate's other half):** `docs/benchmarks/effects-p3-water-state/BEFORE-EVIDENCE.md`

---

## Before you start

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
git checkout -b parcel/water-submerged-state   # already exists
```

Baseline: aeon `eb48808d` (chain 124), sigil `26d8834c`. CRCs s4 `bf1e6fe0` · s4.debug `9c63bc1a`.
**This parcel adds engine RAM, so it moves bytes in both sonic4 shapes** and must not move either
demo shape beyond what `tools/demo_drift_classifier.py` classifies.

### Rulings already made. Do not re-litigate them.

Taken to a Fable adviser 2026-08-15 with the tree's own file:line evidence, twice (the second round
overturned part of the first). Recorded here because the reasoning is what makes them binding.

1. **The frame-top ship covers the FIRE'S OWN 3 ENTRIES, not all 16 of the palette line.**
   The sweep's §1 wrote "all 16 entries, which is more correct", reasoning from S3K. That reasoning
   does not transfer: S3K's full-screen swap is continuous with *S3K's* mid-screen state, because
   S3K's H-int reloads the whole water palette below the line. Aeon's mid-screen state is a 3-entry
   fire, so in Aeon the continuous analogue of S3K's design is the 3-entry ship; the 16-entry one is
   a 13-entry whole-screen snap on one pixel of camera movement — **the exact failure class that
   killed the rejected draft.** The 16-entry variant is not built and is not reachable as an option:
   if content later wants more underwater, the lever is widening the fire's own `pal_region`, and
   the ship follows automatically because it is generated from it.
2. **The descriptor is COMPTIME-EMITTED into the program, not walked at install.** An install-time
   walk of the op words would be a SECOND reader of the variable-length op wire format — today only
   the HInt handler decodes ops — and it would have to track that format forever. The comptime
   emitter derives the entry from the same `fire` arguments the op words are generated from, in the
   same pass: one authored source, no runtime parsing, drift structurally impossible.
3. **`EffectsPreset` does NOT get a channel field.** The pointer cell is an unconditional pure
   function of the installed program (a program with no trailer writes 0, `ep_patched == 0` writes
   0), so the "install with NONE must CLEAR, not skip" failure the field would need a guard for
   **cannot be expressed**. `pal_dirty_mask` is the precedent: this is a program property.
4. **Name it for its GEOMETRY, never for water.** `offscreen_ship`, not `submerge`. Sweep defect 3
   was that water vocabulary installed at the raster level constrains every future patched effect.
   The mechanism is "when this channel's anchor is above the screen, ship this pre-built entry at
   frame top"; water is merely its first client.
5. **ONE derivation of L.** The latch is the only place `anchor - Camera_Y` is computed; `Raster_PatchAll`
   and the parallax overlay both become readers. Three derivations was the pre-existing state and it
   is what makes a `VInt_Lag` frame split the fire line from the state.
6. **Latch in the MAIN LOOP, after `Camera_Update`, before `Parallax_Update`** — not in VBlank.
   Verified ordering: `Camera_Update` (`ojz_scroll_test.emp:310`) → `Parallax_Update` (`:481`) →
   VBlank → `Raster_PatchAll`. A VBlank-computed state reaches the parallax overlay one
   `Camera_Update` later: palette whole-screen wet while the shimmer still splits mid-screen, a
   guaranteed one-frame pop at every transition.
7. **The DRY direction stays broken, deliberately.** Suppressing a fire needs per-record parking,
   which Aeon's array-of-relative-gaps encoding cannot express (parking one record kills the whole
   tail). Blocked on the Ristar linked-list parcel. Today both boundaries clamp to the same line and
   are wrong TOGETHER; "fixing" only the parallax side would trade a consistent 10-line error for a
   9-line disagreement, undoing Parcel W's thesis to fix nothing.
8. **Never write `Palette_Buffer`.** `Palette_DeriveVariant` reads it (`palette.emp:688`), so water
   written there compounds every stale frame — base R 6 → 3 → 1 → 0 in three frames. The source
   stays `Pal_Variant_Stage`; the next frame-top base ship is the exact restore.

### Feasibility, already checked (2026-08-15) — do not re-run, but do not assume beyond it

- **comptime RAM-address folding WORKS.** A probe built through `build.sh` proved
  `((extern("Pal_Variant_Stage") + 72) >> 1) & $7FFFFF` = `$7FC5E7` inside a `comptime fn`, and
  `dma_length(6)` = 3. `Pal_Variant_Stage` = `$FF8B86`. So the emitter can fold the absolute source
  address; the fallback (emit zeroed source bytes, patch three bytes at install) is NOT needed.
- **The determinism control on the gate instrument failed once and is now fixed.** See the
  before-evidence doc; use the reset-anchored protocol, never the freeze-and-poke one.

### Inversion ritual

For every new guard: flip the predicate false → build MUST fail with your message → restore → build
green. **Then show the guard accepts the adjacent legal case.** A guard that refuses everything is as
useless as one that refuses nothing. `ensure` does not short-circuit: one bad input fires every guard
it violates, so two messages does not mean the wrong guard tripped.

---

## File Structure

| File | Change |
|---|---|
| `engine/ram.emp` | `+ Effects_Screen_L[4]`, `+ Effects_Offscreen_Entry` in `Raster_State` |
| `engine/effects/raster.emp` | `RASTER_STATE_SIZE`; `Effects_LatchWorldLines`; `Raster_PatchAll` reads the latch; install stores/clears the pointer |
| `engine/effects/preset.emp` | seed the latch beside the anchors; clear the pointer when `ep_patched == 0` |
| `engine/effects/raster_dsl.emp` | `patchable(offscreen_ship:)`, the comptime `DMAEntry` emitter + its byte pin, the trailer in `patched_program`, `patched_words` |
| `engine/level/parallax.emp` | overlay reads the latch; `L <= 0` skips the band clamp |
| `engine/system/buffers.emp` | `queue_static_dma` split so the copy body is shared; the overlay enqueue |
| `games/sonic4/data/effects/ojz_effects.emp` | `offscreen_ship: 1` on channel 0 + extend the hand twin |
| `games/sonic4/test/ojz_scroll_test.emp` | call the latch in the update loop |
| `tools/effects_budget_model.toml` | `raster_state_bytes` (a LIVE build-fatal gate since Parcel B) |
| `docs/ENGINE_ARCHITECTURE.md` §7.13 | the trailer's wire format |
| `docs/EFFECTS_AUTHORING.md` | `offscreen_ship` |
| `docs/BUGS.md` / `docs/DEFERRED_WORK.md` | the dry direction, blocked on Ristar |

---

## The wire format this parcel adds

A patched template today is `[64-word body][patch table]`, the table at a constant byte +128 and
`1 + 4*records` words long. This appends a trailer **after** the table:

```
+128                    [record count (word)][4 words x record]      <- P-a's patch table, untouched
+128 + 2 + 8*records    [n (word)][n x 16-byte entry]                <- NEW
                        entry = [channel (word)][DMAEntry (14 bytes)]
```

- **The count word is always emitted**, zero for programs with no ship, so the runtime reads a
  fixed shape and never branches on format.
- **`n <= 1` is a comptime ensure, not a wire fact.** If a second off-screen channel ever becomes
  real content, relax the ensure and loop — no wire change, no reader change.
- **The channel word is required**: with ruling 3 there is no preset field, so the channel identity
  must travel with the descriptor. It also keeps the entry even-aligned.
- **Compute the trailer address from the ROM template (`ep_patched`), never from the RAM working
  copy.** The descriptor is fully static; nothing in it is ever patched. The runtime copy is a fixed
  128 bytes, so the trailer is never copied into the working buffer.

---

### Task 1: RAM + the budget gate

**Files:** `engine/ram.emp`, `engine/effects/raster.emp`, `tools/effects_budget_model.toml`

- [ ] **Step 1:** In `Raster_State`, after `Effects_World_Y`, add:
  - `Effects_Screen_L: [u16; 4]` — the latched UNCLAMPED screen line per patch channel, signed.
    Comment it: the 4 mirrors `RASTER_MAX_PATCH` as a literal and must, because `ram.emp` is built
    by a separate ram-harvest pass outside the `COMPTIME_HELPERS` glob injection and cannot NAME the
    constant. `RASTER_STATE_SIZE`'s span ensure is what holds the literal to the constant.
  - `Effects_Offscreen_Entry: u32` — pointer to the live program's trailer entry; 0 = none.
- [ ] **Step 2:** Update `RASTER_STATE_SIZE` (`raster.emp:237`) and its comment block at `:226-229`.
      `+ (2 * RASTER_MAX_PATCH) + 4`. The span ensure must stay green — if it fails, the RAM and the
      constant disagree and that is the guard doing its job.
- [ ] **Step 3:** `raster_state_bytes` in `tools/effects_budget_model.toml`: 306 → 318.
      **This checker is build-fatal since Parcel B**, so a wrong number fails the build rather than
      going quiet. Confirm by building BEFORE changing it and seeing `effects_budget_check` fire.

**Verify:** `./build.sh` green; note the new CRCs (they WILL move).

---

### Task 2: The latch

**Files:** `engine/effects/raster.emp`, `engine/effects/preset.emp`, `games/sonic4/test/ojz_scroll_test.emp`

- [ ] **Step 1:** `pub proc Effects_LatchWorldLines ()` — for each of `RASTER_MAX_PATCH` channels,
      `Effects_Screen_L[ch] = Effects_World_Y[ch] - Camera_Y.int`. Unclamped and signed; the whole
      point is the values the band clamp cannot see.
- [ ] **Step 2:** Call it in `GameState_OJZScroll_Update` **after `Camera_Update`, before
      `Parallax_Update`** (ruling 6). Put it immediately after the camera block so the ordering is
      visible at the call site, and comment WHY it is not in VBlank.
- [ ] **Step 3: the install-time trap.** `Raster_InstallPatched` tail-calls `Raster_PatchAll`, which
      after Task 3 reads the latch — but at install the latch still holds the PREVIOUS section's
      values (or zero at first install). Seed it in `Effects_InstallPreset` immediately after the
      unconditional `ep_patch_world_ys` → `Effects_World_Y` seed, so the latch is total-bound
      exactly like the anchors it derives from. **Do not seed it inside `Raster_InstallPatched`** —
      W0's whole lesson was that anchor state gated on a patched program is silently inherited by
      sections that have none.

**Verify:** build green. No behaviour change yet — nothing reads the latch.

---

### Task 3: Rewire the two existing readers — the no-op refactor

**Files:** `engine/effects/raster.emp`, `engine/level/parallax.emp`

This task must produce **identical rendering**. Do it separately from Task 4 so that if the gate
moves, you know which task moved it.

- [ ] **Step 1:** `Raster_PatchAll` (`raster.emp:877-913`): point `a2` at `Effects_Screen_L` instead
      of `Effects_World_Y`, delete `move.w Camera_Y, d3` and the `sub.w d3, d2`. The `subq.w #1, d2`
      fire-line conversion and BOTH clamps stay exactly as they are — the clamp is load-bearing (a
      negative gap stores `$FF`, which IS the park word, and kills every later fire in the frame).
      Note d3 becomes free; do not repurpose it, the register budget comment above the proc explains
      why the ceiling is d4.
- [ ] **Step 2:** parallax overlay (`parallax.emp:742-748`): replace the `Effects_World_Y` read and
      the `Camera_Y` subtraction with a single `Effects_Screen_L` read. Everything downstream —
      the `Raster_GetChannelBand` call, both clamps, the split — is untouched in this task.
- [ ] **Step 3:** Update both call sites' comments to name the latch as the single derivation.

**Verify (this is a real gate, not a formality):** rebuild, then run the reset-anchored protocol from
the before-evidence doc at the MID config (anchor 224, camera 144<<16) and confirm the capture is
**pixel-identical** to the pre-change build's. A refactor that moves a pixel is not a refactor.

---

### Task 4: The parallax submerged path

**Files:** `engine/level/parallax.emp`

- [ ] **Step 1:** Before the `Raster_GetChannelBand` clamp, test the latched L: if `L <= 0`, jump
      straight to `.anchor_nonneg` with 0, skipping the band clamp entirely. The code at `:775-781`
      already calls this "S3K's whole-screen water state reached structurally instead of as a
      special case" — it is currently DEAD behind the band clamp, and this step is what makes that
      comment true.
- [ ] **Step 2:** Leave the `L >= 224` dry path exactly as it is (ruling 7). Comment it with the
      block: consistent-with-the-palette beats correct-alone, and it is waiting on per-record parking.
- [ ] **Step 3:** Keep the threshold at exactly `L <= 0` and note that it must match the enqueue
      side's threshold in Task 7. Do not "improve" one side to `L <= 3`: in the 1..3 window the two
      boundaries would disagree, which is the defect Parcel W exists to remove. The residual — at
      `L` in 1..3 the boundary still renders at screen 4 — is ACCEPTED, same class as the dry side's 10.

**Verify:** build green. The shimmer now splits at row 0 when submerged while the palette still does
not — a visible, expected, temporary disagreement. Record a capture; it is the proof Task 7 closes it.

---

### Task 5: The DSL — descriptor, trailer, guards

**Files:** `engine/effects/raster_dsl.emp`

- [ ] **Step 1: the emitter.** `comptime fn dma_entry_words(src_abs: int, bytes: int, cmd: int)`
      returning the 14 bytes of a `DMAEntry` in the struct's interleaved order
      (`engine/structs.emp:140-152`): `$94, SizeH, $93, SizeL, $97, SrcH, $96, SrcM, $95, SrcL,
      Command(4)`, with `src = (src_abs >> 1) & $7FFFFF` and size in WORDS (`dma_length`).
- [ ] **Step 2: the byte pin (the adviser's condition for allowing a third site to know this
      layout).** An `ensure` vector: the emitter run on the OJZ arguments must equal a hand-computed
      14-byte literal, pinned the way `variant_word()` is. The three sites that now know the layout
      are `.build_entry`'s movep sequence, `queue_static_dma`'s copy width, and this emitter — the
      pin is what stops them drifting silently. Prove it by inversion.
- [ ] **Step 3:** `patchable(fires, ch, lo, hi, offscreen_ship: int = 0)`.
      Guards, each proved by inversion AND shown to accept the adjacent legal case:
      - `offscreen_ship` is 0 or 1.
      - `offscreen_ship == 1` requires the fire to carry **exactly one** `PalRegion` op — a fire
        with none (e.g. the vscroll channel) must FAIL THE BUILD with its own message, not build a
        garbage entry. This replaces what would otherwise be a runtime clear-to-none.
- [ ] **Step 4:** `patched_program` emits the trailer: walk `fires`, collect the flagged one, emit
      `[n][channel][entry...]`. `ensure(n <= 1, ...)` — spell the message so it says the limit is a
      current-content decision and names what to relax.
- [ ] **Step 5:** `patched_words` += `1 + 8*n` words. Its own ensure (`emitted {out.len} but
      patched_words counted ...`) is the cross-check; make sure it still runs.

**Verify:** build green with `offscreen_ship` unused anywhere (default 0 must emit exactly one extra
zero word per patched program — confirm the ROM grew by exactly that, and that the OJZ hand twin
fails until Task 6 extends it. That failure is the twin doing its job).

---

### Task 6: Extend the OJZ hand twin

**Files:** `games/sonic4/data/effects/ojz_effects.emp`

- [ ] **Step 1:** Add the trailer to `OJZ_TC_TABLE_HAND` (or a new `OJZ_TC_TRAILER_HAND`), with the
      14 entry bytes written as LITERALS, computed by hand from the fire's arguments — `$C048...`
      for CRAM $48, 3 words, source `Pal_Variant_Stage + 72`. **A pin sharing symbols with the
      encoder it pins is weaker**; that is why the existing pin spells 72 as a literal and says so.
- [ ] **Step 2:** Update the `.len` ensures. **`first_mismatch` is blind to length in BOTH
      directions** — deleting a trailing entry produces no mismatch report at all — so the separate
      `.len` ensure beside every twin is load-bearing, not decorative.

**Verify:** build green; deliberately corrupt one trailer byte in the hand twin and confirm
`first_mismatch` reports that exact index.

---

### Task 7: The runtime — install, enqueue

**Files:** `engine/effects/raster.emp`, `engine/effects/preset.emp`, `engine/system/buffers.emp`

- [ ] **Step 1: share the copy body.** Split `queue_static_dma(entry: Label)` so the 3×`move.l` +
      `move.w` copy (and its carry contract, and the `ensure(sizeof(DMAEntry) == 14)`) lives in ONE
      comptime fn that assumes `a2` preloaded; `queue_static_dma` becomes `lea {entry}, a2` plus that
      body. **Do not fork a second copy loop** — parameterise the one that exists.
- [ ] **Step 2: install.** In `Raster_InstallPatched`, compute the trailer address from the ROM
      template: read the record count word at `+RASTER_BUF_SIZE`, `entry_ptr = template + 128 + 2 +
      8*count`; read `n` there; store `entry_ptr + 2` into `Effects_Offscreen_Entry`, or 0 when
      `n == 0`. Keep it on the same side of the `Raster_Patch_Tab`-before-`Active_Buf` ordering that
      proc's comment declares load-bearing.
- [ ] **Step 3: the unconditional clear.** `Effects_InstallPreset` must write `Effects_Offscreen_Entry`
      on EVERY install — 0 when `ep_patched == 0`. This is what makes ruling 3's "cannot express the
      failure" true; if it is conditional, the cell is a side channel again and water survives its
      section. **Test it by inversion**: install the water section, cross into one with no patched
      program, read the cell, assert 0.
- [ ] **Step 4: the enqueue.** In `Enqueue_Dirty_Buffers`, **after the `.skip_pal3`/`.no_pal` block**
      (d0's palette snapshot is dead there; CRAM-line-2 ordering against the base ship is what
      matters and is preserved):
      - `Effects_Offscreen_Entry` zero → skip.
      - `btst #2, Palette_Dirty` — nonzero means the base line-2 ship DROPPED this frame; skip.
        One test covers both legal cases (shipped, or was not dirty).
      - read the channel word from the entry, index `Effects_Screen_L`, ship only when `L <= 0`.
      - `a2 = entry + 2`, then the shared copy body.
      Declare no new clobbers: d0/a1-a2 is enough.
- [ ] **Step 5:** Comment the drop behaviour honestly: the ship and the fire are **idempotent** (same
      source, same CRAM address), so a dropped ship degrades to TODAY'S look for one frame — not to a
      stale water frame.

**Verify:** build green; `Effects_Offscreen_Entry` reads as a plausible ROM pointer on the water
section and 0 after crossing out of it.

---

### Task 8: Author it, and gate it

**Files:** `games/sonic4/data/effects/ojz_effects.emp`

- [ ] **Step 1:** `patchable(fx_tint_band(...), ch: 0, lo: 3, hi: 214, offscreen_ship: 1)`.
- [ ] **Step 2: THE GATE.** Reset-anchored protocol from the before-evidence doc, `s4.debug.bin`:
      1. **Determinism control** — two identical submerged runs, must be **0 differing pixels**.
         Run this FIRST; without it a "differs" result is unreadable.
      2. **The fix** — submerged (anchor 224) vs dry (anchor 700) at camera 400: **rows 0..1 must now
         DIFFER.** Before: identical. This is the whole parcel.
      3. **No collateral** — the MID config (anchor 224, camera 144) pixel-identical to the
         pre-change build.
      4. **Negative control** — with `offscreen_ship` back to 0, rows 0..1 must go identical again.
         This is what proves the gate measures THIS mechanism and not something adjacent.
- [ ] **Step 3:** Write `docs/benchmarks/effects-p3-water-state/GATE-EVIDENCE.md`. Before/after row
      bands, the four results above, and the accepted residuals (the 1..3 window; the dry side).

---

### Task 9: Ritual, docs, merge

- [ ] **Step 1: byte-moving ritual, IN THIS ORDER** — freeze FIRST, then the strict suite, then
      `refreeze --check` + `repin --check`. Running the suite first reports the golden ROM comparisons
      red, because the freeze is what regenerates them. Re-verify CRCs AFTER the freeze; pins feed
      placement. `refreeze --check` is NOT the goldens — it has gone green with 16 golden ROM tests red.
- [ ] **Step 2:** Full sigil suite. **Never tail it** — read aggregate totals and every failing-target
      line. Totals are a LOWER BOUND (`deep_nesting_aborts` aborts without printing a result line).
- [ ] **Step 3:** `tools/demo_drift_classifier.py` — both demo shapes, **zero unclassified bytes**.
- [ ] **Step 4:** Boot all four shapes. **Every shape**, not just the debug one — the release-shape
      blackout was a boot cursor crossing a section seam and no gate looked at a screen.
- [ ] **Step 5:** Docs: ARCH §7.13 (wire format), `EFFECTS_AUTHORING.md` (`offscreen_ship`), and the
      dry-direction block written into whichever of `BUGS.md` / `DEFERRED_WORK.md` holds the Ristar
      ticket — ruling 7 exists so the next session does not re-derive it.
- [ ] **Step 6:** Merge aeon + sigil **as a pair** if sigil moved; verify the branch at commit time
      (parallel sessions share this tree).

---

## Things that have bitten this lane before

- **An unexercised authoring surface is unverified.** `fx_tint_band` shipped broken for two parcels
  because nothing had ever called it. `offscreen_ship: 1` MUST have a call site in this parcel.
- **ROM length is not the measure of added data.** P-a added 146 bytes and the ROM grew 14; pins moved
  a uniform +0x90 and trailing fill absorbed the rest. Measure pin deltas.
- **A gate can measure the placer, or go vacuous, and still look green.** Before trusting a gate, ask
  what a BROKEN implementation would score on it. That is why Task 8 has a negative control.
- **`.emp` comptime free names resolve at the CALL site.** An imported helper breaks SILENTLY —
  empty range, zero results. Inline and pin.
- **Docs in this tree drift.** Re-derive every file:line reference above against the tree before
  trusting it; treat specs as INTENT.
