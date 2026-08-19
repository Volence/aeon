# HBlank window sweep — spec, prediction, and acceptance fixture

**Purpose (Aeon side):** locate the horizontal-blanking window in cycle space so the raster
spin solver can target its CENTRE instead of inheriting one of two hand-fitted anchors.
Closes substrate sweep item 1b; unblocks 1c.

**Purpose (oracle-next side):** this doubles as the worked example / acceptance fixture for
the scanline-readback bus surface, at oracle-next's request (2026-08-18). If the capability
can run this sweep and produce a stable answer, it is good enough for Aeon's raster work.

**Status:** spec only. Not yet run — blocked on a deterministic scanline readback.

---

## 1. Why a sweep is needed at all

`EFX_BLANK_DELAY` used to be one constant fitted to one op shape. Substrate item 1a replaced
it with a per-op spin word carried in the raster program, so the delay is now *authorable per
op* — but the VALUES are still the old hand-fitted ones, and a **leading** stream op is still
mis-timed. R1's §7.3 capture measured it landing at x≈170 of 320, i.e. mid-active-display.

There are two measured-clean anchors in the tree and **they disagree by 44 cycles**:

| Anchor | Shape | Burst starts at |
|---|---|---|
| Row-119 fixture | CRAM op **second**, after an `OP_SET_REG` | `P + 226` |
| R1 §7.3 | `pal_restore`, single op, dispatch depth 4 | `P + 270` |

Both read clean because blanking is wide enough to contain both. Neither is therefore "the"
target, and picking either is how the original defect happened. The window has to be measured.

## 2. The window arithmetic (what the sweep is expected to confirm)

H40, NTSC:

| Quantity | Cycles (68k) | Derivation |
|---|---|---|
| Scanline | ~488.6 | 3420 master / 7 |
| Active display | ~365.7 | 320 px at master/8 = 2560 master |
| **Blanking window** | **~122.9** | 860 master / 7 |
| 3-word CRAM burst | ~84 | 3 × `RASTER_STREAM_WORD_CYC` 30, less the expired `dbf` |
| **Slack** | **~39** | ≈ 3.9 `dbf` iterations at 10 cyc each |

So the clean range should be roughly **4 spin iterations wide**. That is the sweep's first
falsifiable prediction — a much wider or much narrower clean range means this model is wrong.

## 3. Pre-burst path for the fixture (leading single-op CRAM)

Post-item-1a, from fire start to the first `VDP_DATA` write:

```
op fetch                 RASTER_OP_FETCH_CYC        8
dispatch (OP_CRAM, d0)   RASTER_DISPATCH_HIT_CYC   18
move.l command                                      20
move.w spin  (was moveq)                             8
spin                     N*10 + 14
count read                                           8
                                          = P + 76 + N*10
```

Solving against each anchor:

| Anchor | Equation | N |
|---|---|---|
| Row-119 (`P + 226`) | `76 + 10N = 226` | **15** |
| R1 restore (`P + 270`) | `76 + 10N = 270` | **19.4 → 19** |

**PREDICTED CLEAN RANGE: N ∈ [15, 19], centre N = 17.**

Note this is a prediction, not an expectation to be enforced — see §7. The packet's original
"~21" is not reproduced by any derivation from the shipped constants and must not be adopted.

## 4. The fixture

One fire, ONE op, deliberately leading (no `reg_set` ahead of it) — that is the defective
shape. Authored at screen line 100, so the fire line is 99 and the write must land in the
blanking **between row 99 and row 100**.

Built by `tools/raster_cost_probe.py`'s encoder (do not write a second one — it is pinned by
`tools/test_raster_wire_pin.py`):

```python
program_words([(100, [stream_cram(0x4A, [0x0E0E, 0x0E0E, 0x0E0E])])])
```

Emitted image, 17 words / 34 bytes, poked to `Raster_Buf_A`:

| Word | Byte | Value | Meaning |
|---|---|---|---|
| 0 | 0 | `$0002` | header `pal_dirty_mask` |
| 1-4 | 2-8 | `$8A61,0,$8AFF,0` | the two priming records |
| 5 | 10 | `$8AFF` | fire arm |
| 6 | 12 | `$0001` | op count |
| 7 | 14 | `$0002` | `OP_CRAM` |
| 8-9 | 16-18 | `$C04A,$0000` | CRAM write command longword |
| **10** | **20** | **`$0004`** | **SPIN — the sweep variable** |
| 11 | 22 | `$0002` | count-1 (3 colours) |
| 12-14 | 24-28 | `$0E0E` ×3 | the tint |
| 15-16 | 30-32 | `$8AFF,$FFFF` | park + terminator |

**The sweep pokes ONE word: `Raster_Buf_A + 20`.** No rebuild per value — that is what item 1a
bought.

### Content trap, and it is a real one

The CRAM address must be an entry **the art at those rows actually references**, or the sweep
shows nothing and looks like a null result. R1 hit this: "line 1 entries 1-3 were tried first
and are nearly unused at those rows." Use line 2 (`$40`-`$5E`) with the camera frozen at spawn
(`Camera_Y = 144`), which is the configuration R1 verified against the trunk art.

## 5. Poke sequence

1. `reset`, run to a known frame, freeze the camera at spawn
2. **`pause`** — mandatory. A running machine's per-VBlank schedule re-record races the poke
   and rewrites the buffer; a capture was lost to exactly this before the discipline existed.
   On oracle-next this is enforced: `write_memory` refuses with `-32005 machineRunning`, so
   the race is inexpressible rather than silent
3. `write_memory` the 34-byte image to `Raster_Buf_A`
4. `write_memory` the three pointers that make it live:
   `Raster_Patch_Tab = 0`, `Effects_Offscreen_Entry = 0`,
   `Raster_Active_Buf = Raster_Program = &Raster_Buf_A`
5. `write_memory` the spin word at `Raster_Buf_A + 20` = N
6. `resume`, advance one frame
7. **Read rows 98, 99, 100, 101** — 98 and 101 are controls

## 6. Classification, per N

Let *old* be the base colour and *new* the tint. The discriminator is **the first row and
column at which *new* appears**:

| Observation | Verdict |
|---|---|
| *new* first appears at **row 100, x = 0** | **CLEAN** — landed in blanking |
| *new* appears mid-row on **row 99** (any x < 320) | **TOO EARLY** — spilled into row 99's active display |
| *new* first appears mid-row on **row 100** (x > 0) | **TOO LATE** — burst ran past blanking |
| row 98 not uniformly *old*, or row 101 not uniformly *new* | **FIXTURE BROKEN** — stop, do not record |

Sweep N over `0..30`. Record the x of the flip for every N, not just the verdict — the x values
give the cycles-per-pixel conversion as a by-product and cross-check the ~0.875 px/cyc figure
R1 derived.

**The answer is the CENTRE of the contiguous CLEAN range**, and it is what Task 1c pins.

## 6b. Run the two known-good anchors FIRST — they are the disagreement discriminator

Before sweeping the unmeasured shape, capture the two anchors from §1. Both were observed
clean on oracle, and both build from the same encoder, so they cost two extra runs:

| Anchor | Fixture | Observed on oracle |
|---|---|---|
| Row-119 | `fire(120, [reg_set($8C89), stream_cram($4A, [$000E])])` | 1 px spill → 0 px; boundary on the authored line |
| R1 §7.3 | `fire(140, [pal_restore($48, 3)])` | row 139 fully tinted, rows 140+ fully base |

They are the same handler, the same burst and the same window as the sweep fixture, differing
only in how much preamble sits ahead of the write. That is what makes them a discriminator when
the sweep disagrees with §3's prediction:

| Anchors capture as | Then the disagreement is |
|---|---|
| both CLEAN | **the §3 arithmetic** — Aeon's, re-derive it |
| either DIRTY | **the instrument's raster timing or sampling point** — it contradicts a landing already measured clean on a shape the spin change never touched |
| both DIRTY | **the fixture/harness** — check the §4 content trap first; an unsampled tint entry reproduces "everything is wrong" convincingly |

Worth running unconditionally rather than only on disagreement: they also give the sweep two
known-good calibration rows before it enters the unmeasured shape.

## 7. What this measurement may NOT be used for

If the measured clean range does not contain N = 15 and N = 19, **the model in §3 is wrong and
that is the finding** — do not adjust the fixture until it agrees with the prediction. The
prediction exists to be falsifiable, not to be met. Item 1's whole history is a constant that
was fitted and then believed.

---

## 8. Acceptance criteria for the scanline-readback capability

For oracle-next. These are what make the surface *usable*, as distinct from present:

- [ ] **A1 — Determinism.** Same ROM, same N, ≥3 runs → byte-identical rows. This is the one
      that matters most: three prior capture protocols in Aeon failed their own controls on
      exactly this, which is why raster landing has never been gateable here.
- [ ] **A2 — Liveness (the non-vacuity check).** **N = 0 and N = 17 MUST produce different
      content on row 99.** A capture that reports post-frame state would show them identical,
      because by end of frame the CRAM value is the same either way — the whole question is
      *when* it changed. If A2 fails, the surface is structurally blind to this defect class
      in the same way a post-hoc frame dump is, regardless of how good the pixels look.
- [ ] **A3 — Row range in one call.** Rows 98-101 in a single request; every assertion here is
      about a boundary and needs the rows either side of it.
- [ ] **A4 — Rendered RGB, S/H applied.** Pre-palette indices cannot see this defect at all:
      the tile data is unchanged across the write, so the indices are identical either side of
      the landing point. Field 1 alone satisfies this sweep.
- [ ] **A5 — Active pixels sufficient.** 320 active columns; the blanking region is not needed.
      A correctly-landed write is invisible *by definition*, and shows up here as the clean
      signal in §6 rather than as something to be inspected directly.

**A2 is the acceptance test worth keeping permanently.** It is a poison in the Aeon sense — it
perturbs the subject (the spin value) and requires the instrument to notice, rather than
asserting that the instrument returned something.

Fields 2-3 (per-pixel CRAM index, per-pixel S/H state) are **not** required by this sweep.
They are wanted for attribution and for splitting the palette-write op from the S/H-register
op in band effects — see the follow-up rationale sent 2026-08-18.

---

## 9. RUNBOOK — the capability shipped 2026-08-19, this is how to drive it

`emulator/scanlines` is live (oracle-next `fdb6903`, contract §11.14). Everything below was
verified 2026-08-19; a fresh session can start here.

**Do NOT use MCP for this.** `emulator_scanlines` exists as an MCP tool, but a default call
returns all 224 rows ≈ 430 KB of hex, and the sweep is ~30 poke/capture cycles. Drive the bus
socket from Python, the way `tools/raster_cost_probe.py` already does.

| Piece | Where |
|---|---|
| Server | `/home/volence/sonic_hacks/oracle-next/target/release/oracle-aether` |
| Client | `/home/volence/sonic_hacks/empyrean/clients/python/aether.py` (`BusClient`, async, NDJSON JSON-RPC 2.0 over a Unix socket) |
| Existing driver to copy | `tools/raster_cost_probe.py` — same poke sequence, same encoder |
| ROM | `s4.debug.bin` built from master at or after `ed015f0f` |

**The binary must post-date oracle-next `fdb6903`** — rebuild with
`cargo build --release -p oracle-aether` if unsure. A stale binary simply will not advertise
the method.

### Reply shape and the one assertion that matters

`emulator/scanlines` takes `{startLine, count}` and returns `{frame, source, mode, rows: [{line, width, rgb}]}`,
where `rgb` is a hex byte string of exactly `width` × 3 bytes, shadow/highlight already applied.

**ASSERT `source == "raster"` ON EVERY CAPTURE.** The other value is `"stateRender"`, a
post-hoc render returned when no completed frame is retained — at boot, and after any
`reset` / `reload_rom` / `restore`. It is a legitimate answer to the *method*, and a
**structurally invalid** answer to *this measurement*: a post-hoc render shows N=0 and N=17 as
identical, because by end of frame the CRAM value is the same either way. That is acceptance
criterion A2, and an unchecked `stateRender` reply is exactly how this sweep produces a
confident wrong answer.

Also: bounds are **refused, never clipped** (`-32602`) — `startLine` past 223, `count` below 1,
or the sum past 224. There is **no frame parameter**; drive to the frame with `run_frames` /
`run_to`, then read.

### Order of operations

1. Rows 98-101 in ONE call (§6's controls need the rows either side of the boundary)
2. The two anchors from §6b FIRST — they are the disagreement discriminator and double as
   calibration
3. Then sweep N over 0..30, one poke at `Raster_Buf_A + 20` per value, classify per §6
4. The answer is the CENTRE of the contiguous CLEAN range → feeds item 1c
5. §7 still governs: a disagreement with [15, 19] is the FINDING, not a cue to tune the fixture
