# Overnight hardening run — review items 25-30

**Context:** Volence wants the hardening/optimizing backlog cleared so feature work on the
engine can start. This run closes the remaining wave-4 items from
`docs/reviews/2026-07-16-emp-port-optimization-review.md`. Items 23+24 already landed
(`parcel/wave4-z80-sound-reclaim`, 2026-08-03).

**Shape:** SEQUENTIAL parcels, one per item, each with its own branch, its own A/B, its own
`refreeze`. **No mega-branch.** Each merges to master ONLY when verified; anything
unverified stays on its branch with a written status. **Master is never left broken** — that
is the hard constraint of an unattended run.

## RULINGS (Volence, 2026-08-04, pre-run)

1. **Release artifacts (item 29): STRIP EVERYTHING.** Gate convsym on DEBUG (no symbol table
   in release), strip the MDDBG blob + exception stubs, DEBUG-gate RaiseError/Console, make
   `SOUND_DEBUG_HOTKEYS` require/imply `DEBUG`. Release becomes genuinely clean; the debug
   shape is the debugging vehicle.
2. **Spurious/unexpected interrupt (item 27): HALT LOUDLY IN BOTH SHAPES.** A spurious IRQ
   means a state the engine does not model; surface it during development rather than let it
   corrupt silently.
3. **Sprite-cull camera skew (item 26): ADD A CULL MARGIN**, do NOT reorder
   `Camera_Update`/`RunObjects`. Margin ≥ one frame of camera motion (~16 px/frame worst
   case → 16-32 px). Reordering would shift gameplay-visible timing and very likely
   invalidate the recorded OJZ replay fixture; the margin cannot perturb update order.
4. **Boot hardening (item 27): PROVABLY-SAFE SUBSET ONLY.** Land the PSG-after-fill reorder,
   `EntryPoint` SP reload, `z80_init` SP, and the vector policy. **LEAVE THE YM KEY-OFF
   BUSY-WAIT RACE UNTOUCHED**, documented with a written spec — there is no real hardware
   here, and getting its timing wrong is worse than the current state because it would look
   addressed.

### Defaults I am taking on the un-ruled sub-decisions (each FLAGGED in its parcel)

- **Cross-reset RAM (item 27):** research what the engine actually assumes today, implement
  the option that matches existing behaviour, and document rather than change semantics.
  A soft-reset semantics change is not an unattended-run decision.
- **`Spawn_Count` guard (item 30):** delete if grep proves it genuinely unused; implement
  only if something reads it. Do not invent a new runtime guard overnight.
- **`Camera_Init` clamp + the per-frame direct `$8B` write (item 26):** both are
  unambiguous defects with no design fork — just fix them.
- **Blit posture (item 28):** if the `move.l`/DMA choice turns out to be coupled to a
  design fork I cannot settle from the code, STOP and leave it for review rather than pick.

## Order (highest confidence + highest severity first)

| # | Parcel | Why here |
|---|---|---|
| 1 | **26** — game-shell: `stopZ80` in `Section_RedrawPlanes` (**High**), cull margin, `Camera_Init` clamp, kill per-frame `$8B` | Contains the only High-severity item left; fully specified by the rulings |
| 2 | **25** — sequencer reclaim (−71..−94 B) | Sound context warm from the wave-4 parcel; lowest risk; verification harness already built |
| 3 | **29** — build hygiene / release leaks | Mechanical, ruled, self-contained |
| 4 | **30** — RAM/constants cleanup | Mechanical; RAM layout changes need a runtime boot check after |
| 5 | **27** — boot hardening (subset per ruling 4) | Real-hardware class; smallest verifiable diff |
| 6 | **28** — `bg.asm` blits → `move.l`/DMA + BG transpose | Biggest and most likely to need Volence's eye; last |

**Expectation set with Volence: 4-5 of 6 landing well beats 6 mediocre ones.** Depth over
coverage. If an item turns out to need a decision, it stops and gets written up.

## Standing constraints (from the wave-4 parcel, all still binding)

- `git add` exact paths only. Verify `git branch --show-current` before every commit.
- Rebuild **BOTH** sigil binaries after any sigil change (`-p sigil-cli -p sigil-harness`).
- Byte-changing parcel ritual: re-pin → `repin` → `refreeze --freeze <parcel> --ab <note>` →
  strict suite → `refreeze --check` + `repin --check`.
- `repin_pins.rs` is a HAND-TYPED baseline — update values *and* narrative.
- Emulator work is FOREGROUND ONLY, never from a subagent.
- A parallel session has uncommitted work in the sigil tree — never stage or revert anything
  outside the exact files being changed.
- **Every parcel that changes RAM layout gets a runtime boot check** (AS does not auto-align
  `ds.w`/`ds.l`; an odd `ds.b` before a word is an address error at runtime).
