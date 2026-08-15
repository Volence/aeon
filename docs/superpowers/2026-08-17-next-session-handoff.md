# NEXT-SESSION WORK ORDER — 2026-08-17

Supersedes `2026-08-16-next-session-handoff.md`. That file's queue item 0 (the Ristar HBlank
schedule) is **DONE**; its standing rules and its "oracle pixel capture is not a gate here" section
still apply and are still worth reading.

---

## State at handoff

**Both repos on `master`, green, pushed, nothing in flight.**

- aeon `ad7728f1` — Merge parcel/hint-schedule-local-removal: a raster record can leave the schedule
- sigil `b30b136a` — refreeze for aeon's HBlank schedule local removal (chain 127)
- Verified pair. Suite **3717 / 0** across 328 result lines, 289 test binaries, 0 failed targets
- Four shapes build AND boot: s4, s4.debug, demo, demo.debug

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
```

ROM CRCs: s4 `f0e45751` · s4.debug `3da516e4` · demo `dca06660` · demo.debug `6c5e1875`

**One number to reconcile, stated rather than buried:** the previous handoff recorded 3721/0 across
329 result lines for master; this session measures 3717/0 across 328. Both of this session's runs
(pre- and post-refreeze) agree at 3717 across the same 289 targets, so nothing was lost *within* the
branch. I did NOT re-run master's suite to attribute the 4-test difference. The likely explanation is
benign — several sigil tests are data-driven from the aeon tree and this parcel deleted a proc
(`Raster_CopyPatchedTemplate`) — but it is unverified. If a later session wants certainty, run the
suite with the aeon tree at `f3a4b4ec` and compare per-target counts.

---

## What shipped

**A raster record can now leave the schedule.** `Raster_PatchAll` rewrote one arm BYTE per record
inside the live buffer; it could move a boundary but never remove one, because arm gaps are RELATIVE
and the HInt handler's cursor advance is IMPLICIT — a record is left behind only by having been
walked. `Raster_BuildSchedule` re-records the whole schedule from the ROM template into the INACTIVE
buffer each VBlank and swaps, so a record past its band is simply not emitted **and the tail
survives** — which parking the counter never allowed.

`Raster_HInt` is byte-for-byte unchanged. That was the point: zero added HBlank cycles. Ristar's own
spelling (a NEXT link per record) would have spent ~12 cycles of a ~60-cycle per-fire budget forever.
The cost moved to VBlank instead: **+856 cycles** on the proc, **+922** on the enclosing bracket
(`VInt_Level` 7499 -> 8421), ~1.9 scanlines of an ~18,200-cycle NTSC VBlank window.

Design: `docs/superpowers/specs/2026-08-16-hint-schedule-local-removal-design.md` (revision 2).
Plan: `docs/superpowers/plans/2026-08-16-hint-schedule-local-removal.md`.
Evidence: `docs/benchmarks/effects-p3-removal/GATE-EVIDENCE.md`.

### The three-state machine, now explicit and measured

| latched `L` | palette fire | parallax split | frame-top ship |
|---|---|---|---|
| `L <= 0` | clamped UP to `band_lo` | split at line 0 | ships (whole screen) |
| inside the band | fires at `L` | splits at `L` | no |
| `L > band_hi` | **record not emitted** | **no split** | no |

Both boundaries read the same two band words from the same table, so they cannot drift apart by
editing one number. The threshold is measured to the line: anchor 364 -> `L` 220 fires, 365 -> `L`
221 vanishes.

### Lessons this parcel paid for

- **The design draft was WRONG in two load-bearing places and three independent lens seats caught
  both.** The builder's arm arithmetic paired the two-back arm SLOT with the two-back LINE (the delta
  is one-back), and the suppression threshold was written in fire-line space in one section and
  screen-line space in another, leaving `L = 224` clamped-and-wet while the other two consumers had
  gone dry. Neither is cosmetic; both would have shipped behind green-looking gates. **The lens sweep
  on a design draft is not optional and it is not ceremony.**
- **I wrote two of my own gates against copied numbers rather than derived ones**, and caught both
  only by working the arithmetic out again: Task 2's gate expected the TEMPLATE's arm words from a
  buffer that carries RUNTIME lines, and Task 4's parallax edit was told to delete a `cmpi.w #224`
  that is still the no-band-declared path's only threshold. Derive every expected number from the
  values you actually wrote, and show the derivation in the evidence.
- **A guard that checks a derivation against an image does not check the TABLE.** `check_rec_layout`
  as first written recomputed the offsets and compared them to the emitted body — so a wrong
  `patch_table` sailed past it, which is exactly the counterexample a reviewer had raised. It now
  reads the emitted table too: table -> derivation -> image. Both halves poison-proved.
- **Count the readers before you change a shared fact.** The band had a THIRD reader nobody listed —
  a DEBUG anchor-nudge hotkey that clamped the nudge INTO the band, which would have fenced the one
  instrument built to watch the boundary out of the newly-reachable suppressed state.

---

## The queue

### 1. `replay_runner` framebuffer dump — now the top item

Design fully settled in the 2026-08-15 order (whole frames as the dump primitive, a separate
`replay_framediff` binary, `--expect-identical` as the control, no committed golden images, gates may
read the REPORT but never pixels). Repo: `oracle-next`.

**THREE parcels have now hand-built their gates because it does not exist**, and this one ran its
entire three-state matrix as a foreground oracle ritual that nothing will ever re-run. Every
assertion in `effects-p3-removal/GATE-EVIDENCE.md` is a number in a prose file.

### 2. The band-budget parcel — relax `check_intervals`

The design's §8, and the adviser settled its crux: **it does NOT need per-record cost in the table.**
The fatal property (a negative gap stores `$FF`, which IS the park word, killing the frame's tail)
needs ONE runtime compare — every emitted line strictly greater than the previous — and no cycle
model. Density is merely cosmetic (`raster_dsl.emp`: an overrun does not drop the next fire, it
pushes writes into active display) and closes with a single program-wide minimum separation in the
header, derived at comptime from the existing `fire_cost_cycles`.

What makes it a real parcel is the **priority ruling** (who yields when two records collide) and the
**parallax-agreement contract** — under collision the winner is a COMPUTED outcome, and both
consumers must reach the same answer from the shared latch, which is a contract change to
`Raster_GetChannelBand`. It also deletes the disjointness that §5.1-5.3's correctness arguments rest
on, so those need re-proving. Design-first, with a lens sweep.

**Payoff, priced honestly: ~3 rows.** The re-band already took the residual from 10 to 3. Do not
oversell it — an earlier draft of the design claimed "to zero", which was wrong.

### 3. Parcel R — mid-screen restore. STILL STOPPED, and its brief has a new input

Its recommendation was "(C) defer R until after W", because R's hard part is ownership of derived
state. W shipped, then the off-screen ship added one such owner (`Effects_Screen_L`), and now this
parcel has added another shape of the same idea: a per-frame REBUILD that owns the whole live
artifact rather than patching it. Re-read the brief against BOTH.

### 4. Parcel D — starter pack + content.

### Also open

- Sound packages **5** and **6**; the `STRESS_EVICT` famine root-cause.
- **EFX-2** (cross-fade unreachable) and **EFX-7** (`Raster_Clear` no-op, `HBlank_Uninstall`
  unreachable) — both byte-changing, both deliberately open.
- **Splitting the VSRAM op class** off `RASTER_CRAM_MAX` — only CRAM writes glitch, so `vsram`
  inheriting the 3-word ceiling is pure loss.
- **Spacing sweep 2/4/8 lines**, to find where the adjacent-`cram` dot disappears.
- `tools/demo_drift_classifier.py` is still **run by nothing**.
- **NEW — a sigil bug worth booking:** `lea -NAMED_CONST(aN), aN` (a negated NAMED constant in a
  displacement) is silently DROPPED by the contract-closure walk — reported as dropped instructions,
  gate-fatal. `-128` resolves; `-RASTER_BUF_SIZE` does not. The instruction LOWERS correctly, so this
  is gate blindness, not codegen. Workaround in tree: `suba.w #CONST, aN`.

---

## Traps confirmed live this session

- **A 700-frame `emulator_press` WEDGES the oracle MCP** (the StopSystem-race deadlock: every later
  call, `emulator_status` included, hangs). Recovery needs `kill -9` — `pkill -x` was not enough —
  plus a relaunch. Presses of <= 200 frames ran all session without recurrence.
- **Oracle's `interrupts.hint` counter INCLUDES VBlank.** It moved 9446 -> 10307 across this
  parcel's A/B while `Raster_HInt`'s code was byte-identical. Do not read it as HBlank cost.
- **`Raster_Active_Buf` now alternates A/B every frame.** Anything reading the live raster buffer
  must go through that pointer; assuming Buf_B is now wrong.
- **A `.emp` comptime `var[i] = x` does not parse** — `Stmt::Assign`'s target is a bare dotted path
  with no indexing form, and it fails as a parse error rather than a diagnostic. Accumulate into a
  scalar (a bitmask) instead, as `prog_mask` does.
- Comparing warning counts across BUILD SHAPES is meaningless (plain is 88/14/7, debug 85/13/5).
  Match the shape before calling a delta a regression — I raised a false alarm on myself doing this.
