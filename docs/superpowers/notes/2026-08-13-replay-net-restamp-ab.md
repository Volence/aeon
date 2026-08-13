# Replay net re-stamp — evidence (Effects P3, Parcel 0)

**Date:** 2026-08-13
**Plan:** `docs/superpowers/plans/2026-08-13-replay-net-restamp.md`
**Repo state:** aeon master, re-stamp committed as `32a79e1d`
**Build used throughout:** `DEBUG=1 ./build.sh` — the compare, the record path and the
desync trap are all `if DEBUG == 1` (`engine/system/replay.emp:142, 168, 205-212`), so
release cannot exercise the net at all.

---

## Corrected reference data (the old numbers were all stale)

`docs/superpowers/notes/2026-08-09-replay-net-rerecord-ab.md` is superseded on every
statistic. Measured from the bytes on disk with `python3 tools/replay_pack.py dump`:

| fixture | bytes | ticks | checkpoints | core_hash |
|---|---|---|---|---|
| `ojz_fixture.bin` | 272 | 1721 | 27 | `0x7054d28b` |
| `ojz_slide_fixture.bin` | 336 | 2350 | 37 | `0x7054d28b` |

Checkpoints are at ring index 0, 64, … 1664 (and … 2304 for the slide). **`Logic_Tick` =
ring index + 2** — the recorder's first logged tick was 2.

Symbols (re-derived from `s4.debug.lst`; the 2026-08-10 handoff's `Replay_Ptr = $5E5AE` is
two layouts stale):

| symbol | addr |
|---|---|
| `GameState_OJZScroll_Init` | `$A1734` |
| `Replay_OJZ_Fixture` | `$A1DA0` (`Replay_Ptr` value = `$A1DB4` = **662964**) |
| `Replay_OJZ_Slide_Fixture` | `$A1EB0` (`Replay_Ptr` value = `$A1EC4` = **663236**) |
| `Input_Source` / `Replay_Done` / `Replay_Ptr` | `$FF803A` / `$FF803C` / `$FF8040` |

ROM CRCs: master debug **before** re-stamp `d792e8d6`, **after** `33f8142b`, length
`711252` unchanged in both.

---

## 1. Baseline — the failure, measured first-hand

Previously only reported in `notes/2026-08-13-replay-net-attribution.md`. Confirmed
independently here:

| register | value | meaning |
|---|---|---|
| `d0` | `BBB93779` | actual hash |
| `d1` | `00000502` | `Logic_Tick` 1282 |
| `d2` | `1F420103` | expected — matches the fixture's ring-1280 payload exactly |

Capture: `desync_1282.png`.

## 2. Positive control — the trap is known to be able to fire

A re-stamped fixture is green by construction, so the parcel needed a gate proven able to
fail. Ring 0's payload was doctored to `DEADBEEF` in the working ROM:

- trap moved to `Logic_Tick` **2** (ring 0 + 2), `d2 = DEADBEEF` — so the comparator reads
  the bytes being patched, and the patch offsets are correct.
- **`d0` read back `1D375066`** — which is *exactly* the ring-0 hash the committed fixture
  already carried. Independent confirmation that the early checkpoints genuinely pass on
  this build, so the divergence really does begin at 1280 rather than masking earlier drift.

Capture: `poscontrol_tick2.png`.

## 3. The harvest — seven checkpoints, all above ring 1280

Iterated against a patched ROM image: run → trap → read `d0`/`d1` off the MD Debugger
screen → patch that 4-byte payload → `reload_rom` → repeat.

| ring | tick | old | new |
|---|---|---|---|
| 1280 | 1282 | `1F420103` | `BBB93779` |
| 1344 | 1346 | `6D53A2B5` | `10247BDE` |
| 1408 | 1410 | `702B9883` | `1B2B5B80` |
| 1472 | 1474 | `CFA9F178` | `4BAA3F90` |
| 1536 | 1538 | `6D51F02D` | `4D51E8A5` |
| 1600 | 1602 | `354F6416` | `354F5C8E` |
| 1664 | 1666 | `155B3579` | `F55B2DF0` |

Every `d2` matched the committed fixture's payload for its ring, so the offset table and
the ROM agreed at every step.

**This is exactly the set of 7 that `notes/2026-08-13-replay-rerecord-attempt.md`
predicted**, and — the load-bearing observation — **all seven are at or above ring 1280**,
with all 20 checkpoints at or below ring 1216 passing untouched. The plan's STOP condition
(any stale checkpoint *below* 1280 means something other than the attributed cause is in
play) never triggered.

Note `d0` and `d2` converge as the run proceeds: by ring 1600 they differ only in the low
bytes (`354F5C8E` vs `354F6416`). That is the physics state re-settling after the spindash,
i.e. a bounded intended delta rather than a compounding divergence.

## 4. Why this is a re-stamp of intended behaviour, not a buried regression

- The fixture drives a **spindash charge-and-rev** at ring 1212 (`0x02` DOWN × 25, then
  `0x22` DOWN+C). Every stale checkpoint falls after it; everything before it passes.
- Knuckles C4 (`50d54612`) changed spindash dust, the line-0 palette, and `EnsureStanding` —
  shared player code, which is why a Sonic fixture moved.
- The hash is **address-free by contract** (`engine/system/replay.emp:7-16`, `:49-64`,
  pinned by six `ensure`s at `:87-92`). A layout break therefore desyncs at checkpoint
  **0**. A run that gets 1280 ticks in and *then* diverges cannot be layout-induced.

## 5. Post-change verification

**Byte-level diff of the fixture** (`decode_stream` before vs after):

```
input stream identical : True
tick_count             : 1721 -> 1721
checkpoint count       : 27 -> 27
checkpoint RINGS same  : True
core_hash              : 0x7054d28b -> 0x7054d28b
changed checkpoints    : 7   (all >= ring 1280)
BUTTON_C @1237/1248    : True True
DOWN hold 1212..1236   : True
```

The input stream being byte-identical is what lets the fixture *inherit* its coverage
rather than re-establish it. This had to be a re-stamp: the stream uses `BUTTON_C` in four
runs including the spindash rev inside the desyncing region, and the oracle driver cannot
press `c` at all, so a re-record could not reproduce it.

**Length unchanged at 272 bytes** — the fixture sits before the fault-handler island, so a
size change would move `EndOfRom` and require a sigil repin/refreeze. It did not, so
**Parcel 0 is aeon-only**, no sigil ritual.

**Rebuild cross-check:** the rebuilt `s4.debug.bin` differs from the hand-patched ROM that
was verified in **exactly two bytes**, `$18E-$18F` — the header checksum that `build.sh`
re-folds. Everything else is byte-identical, so the on-disk fixture edit reproduces
precisely what was tested in the emulator.

**Full playback on the properly-built ROM:** `Replay_Done = $FF`, `Input_Source`
self-cleared to 0, `Logic_Tick` 2423 (past the 1721 stream end), no fault screen, live
gameplay. Capture: `verify_green.png`.

## 6. The slide fixture — measured, and GREEN

Its status was **unmeasured** in every prior note; the attribution work only ever swapped
ROMs on the standing fixture. Measured here for the first time:

`Replay_Done = $FF`, `Input_Source` self-cleared, `Logic_Tick` 2801 (past its 2350 end), no
fault. **No re-stamp needed.** Capture: `slide_green.png`.

This matters because the slide fixture's whole purpose is proving `EntityWindow_Slide`
fires in all four crossing directions (`games/sonic4/test/replay_fixture.emp:19-35`), and a
silently-red slide fixture would have been a coverage hole nobody was tracking.

---

## Method notes that cost real time — read before re-running this

1. **`emulator_registers` does NOT give you the trap values.** By the time you can query,
   the handler is ~3630 bytes into `ErrorHandlerBlob` and has clobbered `d0`-`d2` drawing
   its own screen (a live read returned `d0=FFFFFF00, d1=FFFFFF00, d2=00000004`). The
   trap-time values survive only on the MD Debugger's **displayed** dump. **Use
   `emulator_screenshot`.** Cross-check `d1` against `emulator_read_memory 0xFF8004`.
2. **`emulator_write_memory`'s `value` is DECIMAL.** `$A1DB4` is 662964; an earlier
   revision of the plan carried 662452, which is `$A1BB4`. A wrong pointer is accepted
   silently and replays garbage from inside the header. **Always read back**, and verify
   the ROM at `Replay_OJZ_Fixture` starts `41525030` ("ARP0") with `FF 01` at offset 20.
3. **A desync presents as a hang over MCP** (`running=true`, `Logic_Tick` frozen). Check
   `symbol_at_pc` for `ErrorHandlerBlob` before concluding anything is broken.
4. **Never watchpoint `Replay_Done`** — a watchpoint on `$FF803C` wedges the emulator. Poll
   it. Reading `$FF803A` with `len=4` gets `Input_Source`, `Replay_Done` and the pad in one
   call, which is the cheapest completion check.
5. **Playback speed is dominated by host CPU contention, not the emulator.** Runs varied
   between ~30 fps and ~0.9 fps purely with competing desktop load (a media app at 282%
   CPU). An early restart appeared to "fix" a slowdown; that was coincidence. Budget on
   wall-clock, not tick count: one full 1721-tick playback took 10-20 minutes under load.
6. **Arm the breakpoint BEFORE `reload_rom`.** On a fresh oracle launch the OJZ init has
   already run by the time you can add one; `reload_rom` restarts it with the breakpoint
   armed.

## Open item this exposed

**The replay net has no automated runner** — not a pytest, not a cargo test, not in
`test.sh`, no CI. The aeon suite's "2 skipped" are `test_s4lint.py` looking for a deleted
`main.asm`, **not** the net. That is how master stayed red from the C4 merge until today
with nothing reporting it. `tools/test_replay_fixture.py` (added in `bb678954`) now gates
fixture *structure* — length, tick counts, ring alignment, and the `BUTTON_C` runs that
prove a re-stamp rather than a re-record — but it cannot detect a desync. Recorded in
`docs/DEFERRED_WORK.md` §5.
