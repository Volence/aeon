# Parcel R1 — gate evidence

All measurements on oracle (the only verification instrument — no real hardware exists for
this project). ROM identified by CRC per section.

---

## CLAIM 9 — the restore's `op_work_cyc` — MEASURED, CLOSED (2026-08-17)

**ROM:** `s4.debug.bin` crc=`04882b94` len=712732 (branch `feature/parcel-r1-palette-bands`
@ `25bad462` — encoder + constructor landed, guards not yet).

**Command:**
```
python3 tools/raster_cost_probe.py --rom s4.debug.bin --lst s4.debug.lst \
  --only F0,F1,F5,F8 --repeat 3
```

**Result — 3 independent boots, spread 0 on every fixture:**

| fixture | n | marginal cyc/fire | model (RUNGS=5) | verdict |
|---|---|---:|---:|---|
| F0 (floor) | 0 | 572 (absolute) | 572 | exact |
| F1 (reg_set) | 6 | **412.0** | 412 | exact — the +16 rung tax is real |
| F5 (reg_set + cram3) | 5 | **628.0** | 628 | exact — mixed fire additive at 5 rungs |
| F8 (pal_restore 3w) | 6 | **556.0** | 556 | exact — **claim 9 closed** |

**Derivation check:** 556 − 302 (fire base) − 8 (fetch) − 82 (dispatch, depth 4) − 90
(3×30 stream) − 10 (tail) = **64** = the derived `RASTER_WORK_REGION_CYC(122) − delay
site(58)`. The derived constant IS the measured one; the sweep-5 correction (64, not v5's
68) is hardware-confirmed.

**Consequences applied:**
- `RASTER_WORK_RESTORE_CYC = 64` re-labelled MEASURED in `raster_dsl.emp`.
- F1/F5 measured-equality ensures re-labelled `measured 412` / `measured 628` (they were
  honest-DERIVED from Task 4 until this run).
- New F8 pin ensure added (556) — the pin that keeps the `band()` minima honest.
- `effects_gates.py` cost_model gate now runs `--only F0,F1,F3,F5,F8` with computed
  expectations (F5 = f0 + 5×fire_mixed — five fires, buffer cap; F8 = f0 + 6×fire_rest).
- **The §6.2 minima may now freeze** (the spec's ordering rule is satisfied): restore fire
  1w = 496 / 3w = 556; downstream gap ≥ 2 at every count stands on measured ground.

**Pin-provenance correction from Task 1 (recorded so it is not repeated):** the +0x100
game-RAM pin shifts were `@align(256)` padding on the leader-only ring, NOT "two-player
width" — pin rationales must state the mechanical source only.

---

## CLAIM 8 — snapshot VBlank cost — MEASURED, CLOSED (2026-08-17)

`Enqueue_Dirty_Buffers` IS a distinct per-routine profiler row (confirmed via `--dump`).
Same scene (OJZ, camera frozen at settle 180), branch ROM (`04882b94`, splices) vs a
baseline ROM built in a temporary worktree at `d0710868` (RAM added, splices absent).

| condition | baseline | branch | splice delta |
|---|---:|---:|---:|
| steady state (mask %0101, 2 dirty lines/frame) | 971 | 1318 | **+347** (~173.5/line) |
| forced worst case (`Palette_Dirty = $0F`, single frame) | 1400 | 2104 | **+704 — the derived figure EXACTLY** |

- The estimate (~176/line, ~704 worst) is confirmed: 704/4 = 176.0/line on the clean
  4-line measurement; the steady-state 347 vs 352 sits inside per-path `lea`-form variance.
- Window headroom: the worst forced frame's `VBlank_Handler` row reads 10,028 cyc against
  the ≈18,565-cyc NTSC blanking window — the +704 is 3.8% of the window and end-of-window
  overrun is nowhere near (≈8.5k cyc of slack on the heaviest frame measured).
- `VInt_Level`'s self-time row is identical (5328) on both ROMs — the cost lives entirely
  in the `Enqueue_Dirty_Buffers` row, as placed.
- **Z80 DRAIN scope (Task 2 review I3): derivation only, booked.** 704 cyc ≈ 92 µs at
  7.67 MHz of additional ring-only DAC coverage (sound-ON) / held bus (sound-OFF) inside
  the `SND_CTRL_DMA_ACTIVE` bracket. No automated Z80-side instrument exists; an audible
  soak on the sound-ON shape is booked with the Task 13 capture session's notes.

## §7.3 landing captures — pending (R1 Task 13)

1. The restore's landing — FIRST datum at its shape; delay ladder per spec §3.2 (leading
   dots → step the knob; straddle → narrow stream count).
2. The +16 mixed-fire capture on `OJZ_TC_PROG` ch 0 — S/H-seam method, 8 px buckets. On
   failure: the fallback slot is VACANT and the owner re-rules (never a global retune).

## Boot evidence log

- Task 1 ROM (`f1a8d28d`): boots to OJZ on oracle, frame 928, PC in `VInt_Level`. 2026-08-16.
- Task 2 ROM (`f9e38b9f`): boots; `Palette_Ship_Snap` read live == `Palette_Buffer`
  byte-identical across all 128 bytes at frame ~101835 (splices live). 2026-08-16.
- Task 3-5 ROM (`04882b94`): boots; OJZ scene + HUD render normally with the live raster
  program; opcode body dead as designed. 2026-08-17.
