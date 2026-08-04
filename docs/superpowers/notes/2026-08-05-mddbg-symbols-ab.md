# MDDBG `<unknown>` symbol resolution — oracle A/B evidence

Evidence packet for the `mddbg-symbols` provenance chain entry, per
`sigil/crates/sigil-harness/golden/ab/AB_PROTOCOL.md`. Class: **BA**
(behaviour-adjacent, placement-only). Plan:
`docs/superpowers/plans/2026-08-05-crash-reporting-and-symbols.md`, Part A.

The DEBUG crash screen printed raw hex with no names. It now prints names. The
fix is a **placement reorder plus a hard build guard**; no blob byte, no
instruction, and no gameplay address moved.

## The symptom, reproduced

Probe (the parcel-7 recipe — boot does not verify the checksum, so patching a
scratch ROM needs no source change): the first instruction of `Camera_Update` in
a copy of `s4.debug.bin` replaced with `ILLEGAL` (`$4AFC`), so the fault fires on
the first gameplay frame.

Before (`assets/2026-08-05-mddbg-symbols-before.png`):

```
ILLEGAL INSTRUCTION
Offset:  006B86   <unknown>
Caller:  05E430   <unknown>
```

After (`assets/2026-08-05-mddbg-symbols-after.png`):

```
ILLEGAL INSTRUCTION
Offset:  006B86   Camera_Update
Caller:  05E430   GameState_OJZScroll_Update.skip_camera_update
```

Both `Offset:` and `Caller:` resolve, which is the plan's stated acceptance for
Part A.

## Root cause

Established twice, independently, by two agents that did not share results, and
then confirmed by a live control (below).

The vendored MD Debugger blob does **not** read a toolchain-patched pointer, the
Sega header `$1A4` field, or a scan. It locates the deb2 symbol table through
**two PC-relative `lea` displacements baked into the opaque blob bytes**:

| site | source | decodes to | target |
|---|---|---|---|
| `MDDBG__GetSymbolByOffset` (blob+`$64A`) | `error_handler.emp` `dc.l $43FA090A` | `lea $90A(pc),a1` | `ErrorHandlerBlob + $F56` |
| symbol-name decompressor (blob+`$6E2`) | `error_handler.emp` `dc.l $47FA0872` | `lea $872(pc),a3` | `ErrorHandlerBlob + $F56` |

`$F56` is the blob's own length, so both say the same thing: **the symbol table
begins at the byte immediately past my last byte.** That is upstream MD
Debugger's contract — convsym appends the table right after the blob.

Aeon's `s4` link order put `Replay_OJZ_Fixture` (`$140` bytes, ASCII magic
`ARP0`) *between* the blob and `EndOfRom`, where convsym actually appends:

| symbol | before | after |
|---|---|---|
| `Replay_OJZ_Fixture` | `$5F5DE` | **`$5E52E`** |
| `BusError` (island head) | `$5E52E` | **`$5E66E`** |
| `ErrorHandlerBlob` | `$5E688` | **`$5E7C8`** |
| blob end (`+$F56`) | `$5F5DE` | **`$5F71E`** |
| `EndOfRom` / deb2 magic | `$5F71E` | `$5F71E` (unchanged) |

So the blob's `cmpi.w #$DEB2,(a1)+` read `$4152` (`"AR"`), mismatched, returned
`d0 = -1`, and the caller printed its `<unknown>` fallback. Both routines failed
identically, so even a lucky hit would have produced no name. This violated the
invariant `error_handler.emp` already documented in one line at its top
(*"this region MUST stay the final ROM emission"*) — the file said it, nothing
enforced it, and the fixture was later placed last for an unrelated reason.

**The producer was never at fault.** The appended table was verified well-formed
and complete independently of the fix: 1,620 distinct addresses, byte-identical
to a clean convsym regeneration from the same listing, absolute 24-bit addresses
matching the listing exactly, `Camera_Update` present at `$6B86`, header
`$1A4 = $675DB` = len-1 and the checksum fold correct. The 41 symbols short of
the 1,661 input are same-address aliases the deb2 format cannot represent (one
name per offset), not a filter defect. `-range 0 FFFFFF -exclude -filter
"z[A-Z].+"` drops nothing but Z80 names, as the plan already recorded.

## The control that settled it before any code changed

`games/demo/map.toml` **already** ended `… "GameState_Demo_Init",
"ReleaseFault", "BusError",` — the island last, the invariant accidentally
intact. The identical probe on the *unmodified* `demo.debug.bin`
(`assets/2026-08-05-mddbg-symbols-demo-control.png`):

```
ILLEGAL INSTRUCTION
Offset:  010002   DemoBox_Main
Caller:  0196C    RunObjects.culled_loop+3A
```

Same blob, same convsym invocation, same deb2 format, names resolve. That
isolates the defect to `s4`'s placement alone and rules out format, version,
address-space and name-mangling hypotheses without a single edit.

## What changed

- **`games/sonic4/map.toml`** — order tail is now
  `… "GameState_OJZScroll_Init", "__align$games.sonic4.replay_fixture$0",
  "Replay_OJZ_Fixture", "ReleaseFault", "BusError", "EndOfRom",`. Header gains an
  `INVARIANT — THE FAULT-HANDLER ISLAND IS LAST` block stating the mechanism.
  Subsequence validity is preserved: no target carries both fault handlers, so
  release derives `… Replay_OJZ_Fixture, ReleaseFault, EndOfRom` and debug
  derives `… Replay_OJZ_Fixture, BusError, EndOfRom` — each strictly increasing
  in the union list.
- **`engine/debug/error_handler.emp`** — the one-line WARNING is promoted to the
  full mechanism: both baked `lea`s quoted with their line numbers and
  blob-relative sites, the `$F56` / `$15A + $F56 = $10B0` geometry, the
  `cmpi.w #$DEB2` validation, and the instruction to *fix the placement, not the
  displacements*. **Zero blob bytes touched.**
- **`games/sonic4/test/replay_fixture.emp`** — its header claimed "Placed LAST in
  the emitting order". That is now false and is corrected: it sits after all
  gameplay content but before the fault-handler island. Re-recording still shifts
  zero *gameplay* addresses (the property the fixture was placed for); it now
  additionally shifts `ReleaseFault` / the error-handler island, which is pure
  fault-handling equipment that `repin` re-pins.
- **`sigil` `crates/sigil-harness/src/native.rs`** — new
  `check_error_handler_is_last`, called as the first statement of
  `append_deb2_appendix`, before convsym is shelled. If the listing contains
  `ErrorHandlerBlob`, then `EndOfRom` must equal `ErrorHandlerBlob +
  ERROR_HANDLER_BLOB_LEN (0xF56)`; otherwise the build **hard-errors** with the
  drift in bytes and an explanation of the baked-`lea` mechanism. Inert when the
  blob is absent (today's release shapes, and the two t24 negative controls).
  Four new unit tests cover pass-at-blob-end, fire-at-`+0x140` (the shipped bug),
  fire-at-`-2`, and inert-on-release.

### Why a guard, and why this guard

This repository has twice been bitten by a `[closed by <pending mechanism>]`
marker standing in for a mechanism that never shipped (the D8 blob-evenness
assert, which took a real boot ADDRESS ERROR on 2026-08-03; the D10 flag algebra,
which hid the whole release-leak half of item 29). A comment stating the
invariant is what we already had — and it is exactly what failed here. The guard
is a hard build error in the single funnel through which every appendix is
produced, so the next section appended after the island fails the build loudly
instead of silently degrading every future crash report.

### Alternative considered and rejected

Re-spelling the two baked `lea` displacements as link expressions
(`EndOfRom - here - 2`) would make the locator derived rather than positional and
would let the fixture keep the last slot. Rejected: it edits vendored opaque blob
semantics for a convenience, splits two `dc.l` transliterations into `dc.w`
pairs, and introduces a new `±32 KB` PC-displacement range constraint that would
itself need a guard. The reorder restores the invariant the vendored source
already documents and costs nothing but the fixture's tail position.

## Builds

`SIGIL_BUILD`/`SIGIL_EMIT` from freshly rebuilt sigil binaries
(`cargo build --release -p sigil-cli -p sigil-harness`).

| shape | OLD (`master` @ `e48d669`) | NEW (`parcel/mddbg-symbols`) |
|---|---|---|
| `s4.bin` | `730a9f99` / 379,822 | `a46a39f6` / 379,822 |
| `s4.debug.bin` | `b3aaa1df` / 423,388 | `ca450ce0` / 423,388 |
| `demo.bin` | `ea6213bc` / 65,954 | `ea6213bc` / 65,954 (untouched) |
| `demo.debug.bin` | `18e5ec7f` / 93,963 | `18e5ec7f` / 93,963 (untouched) |
| `config_a.bin` | `bea7e57b` / 423,765 | `fa15ffa1` / 423,765 |
| `config_b.bin` | `12ff0a4f` / 271,790 | `b991af6c` / 271,790 |

`config_a` / `config_b` move because they are sonic4-rooted and share
`games/sonic4/map.toml`; both lengths are likewise unchanged.

**Every length is unchanged** — this is a pure permutation of the `s4` tail. The
island moved `+$140`, the fixture moved back into the island's old slot,
`EndOfRom` did not move, and no `ANCHOR_GAP` island reclassification is possible.
`demo` is byte-identical in both shapes (its map was already correct and was not
edited).

Byte verification on the new `s4.debug.bin`: `ErrorHandlerBlob $5E7C8 + $F56 =
$5F71E == EndOfRom`, and the bytes at `$5F71E` are `de b2 04 02` — the deb2 magic
now sits exactly where both baked `lea`s point.

---

> **[CONTROLLER]** Result 1 — induced fault resolves symbols — **DONE, PASS**
>
> | ROM | `Offset:` | `Caller:` |
> |---|---|---|
> | `s4.debug.bin` BEFORE | `006B86 <unknown>` | `05E430 <unknown>` |
> | `s4.debug.bin` AFTER | `006B86 Camera_Update` | `05E430 GameState_OJZScroll_Update.skip_camera_update` |
> | `demo.debug.bin` (control, unmodified) | `010002 DemoBox_Main` | `0196C RunObjects.culled_loop+3A` |

> **[CONTROLLER]** Result 2 — all four shapes boot and run — **DONE, all pass**
>
> | shape | after reset + input | 68k state |
> |---|---|---|
> | `s4.bin` (release) | OJZ renders + scrolls (240f right) | `EntityWindow_InitSection`, SP `$FFFFFEB2` |
> | `s4.debug.bin` | OJZ renders + scrolls (240f right) | `VInt_DrawLevel`, SP `$FFFFFEB2` |
> | `demo.bin` (release) | white box on dark blue | normal main loop |
> | `demo.debug.bin` | white box on dark blue | normal main loop |
>
> Both sonic4 shapes match the states parcel 7 recorded for the same probe, so
> the reorder changed nothing observable in normal play.

> **[CONTROLLER]** Result 3 — the RELEASE fault path is undamaged — **DONE, PASS**
>
> The island moved `+$140` in DEBUG and `ReleaseFault` moved `+$140` in RELEASE
> (`$5CA40` -> `$5CB80`), so the release arm needed re-proving. Same ILLEGAL probe
> on `s4.bin`: **solid red screen**, PC frozen at `$5CBAC` = `ReleaseFault + $2C`
> (the `.halt` `bra`), SR `$2700`. Unchanged behaviour at a new address.

> **[CONTROLLER]** Result 4 — repin / refreeze / strict suite — **DONE, clean**
>
> `repin` moved 18 pins, every one of them the tail: `OJZ_SCROLL_TEST` plain_len
> `-0xC` and `REPLAY_FIXTURE` plain_len `+0xC` (the `ReleaseFault` align pad
> re-attributed across the new boundary), `REPLAY_FIXTURE` bases down to the
> island's old slot, and the island plus all 12 exception stubs plus both MDDBG
> pins `+0x140`. `ASSEMBLED_LEN` (`0x5CBAE`) and `DEBUG_ASSEMBLED_LEN`
> (`0x5F71E`) are **unchanged** — the parcel is a permutation.
>
> `repin.toml` needed four region edits to match the new order: `ojz_scroll_test`
> ends at `Replay_OJZ_Fixture` in both shapes (its `debug_end` split is gone),
> `replay_fixture` inherits the shape split (`end = ReleaseFault`,
> `debug_end = BusError`), and both fault regions now end at `EndOfRom` with
> anchors re-pointed at the tail position (`release_fault.debug_anchor =
> BusError`, `error_handler.plain_anchor = EndOfRom`).
>
> - `refreeze --freeze mddbg-symbols --ab <this note>` -> chain entry 41.
> - Strict suite: **3057 passed / 0 failed**. The plan's 3024 baseline had already
>   moved: sigil master gained 29 tests in the merged D-batch after the chain-40
>   refreeze, and this parcel adds the 4 new guard tests. 3024 + 29 + 4 = 3057,
>   exactly.
> - `refreeze --check`: OK (tip `mddbg-symbols`, chain len 41).
> - `repin --check`: `pins.rs unchanged`.
>
> Harness hazard worth recording: `oracle_gui` wedged twice mid-run
> (`system_running=0`, every MCP call hanging past 120 s). Recovery is
> `pkill -9 -x oracle_gui` then a single fresh launch, load the ROM first, and
> drive it immediately. Confirm exactly one instance with `pgrep -a oracle_gui`
> before and after: `pgrep -x` did NOT match the running process here, and
> trusting it caused two duplicate instances to be spawned (both killed).
