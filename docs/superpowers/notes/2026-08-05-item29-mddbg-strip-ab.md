# Item 29 part 4 (release-shape MDDBG strip) — oracle A/B evidence

Evidence packet for the `item29-mddbg-strip` provenance chain entry, per
`sigil/crates/sigil-harness/golden/ab/AB_PROTOCOL.md`. Class: **BA**
(behaviour-adjacent, shape-split). RELEASE builds now ship ZERO debug equipment
(the vendored MD Debugger / error_handler island is gone) but a fault still HALTS
LOUDLY via the new `ReleaseFault`. DEBUG builds are unchanged in their fault
handling (the per-class error_handler stubs + MDDBG blob stay). The bar is:

1. all shapes boot and run (RELEASE + DEBUG, sonic4 + demo);
2. the RELEASE vector table routes every fault at `ReleaseFault`;
3. `ReleaseFault` actually paints the red screen and freezes on an induced fault;
4. the MDDBG blob is present in DEBUG, absent in RELEASE.

Results 1 and 3 are oracle work (CONTROLLER placeholders below). Results 2 and 4,
plus the byte-level structure, are proven statically here.

## What changed

- `engine/debug/error_handler.emp` (12 exception stubs `0x15A` + vendored MDDBG
  v2.6 blob `0xF56` = `0x10B0` / 4,272 B) is now **DEBUG-ONLY**: registry `if
  debug` (`sigil/.../native.rs`), repin.toml `debug_only`, and the `debugger.asm`
  include is `__DEBUG__`-gated in both `game_root.asm`s (its `MDDBG__*` externs are
  unresolvable once the blob is stripped — confirmed by a release build that
  errored on `MDDBG__Debugger_AddressRegisters` before the gate went in).
- NEW `engine/system/release_fault.emp` — `ReleaseFault` (38 B): mask, reset VDP
  command state, red backdrop, freeze. RELEASE-ONLY (registry `if !debug`,
  repin.toml `plain_only`).
- `engine/system/vectors.emp` — the 60 fault cells are `if DEBUG`-split: DEBUG →
  per-class stubs (unchanged), RELEASE → `ReleaseFault` (all 60). `$00`/`$04`/`$70`/
  `$78` (SSP / EntryPoint / HBlank slot / VBlank) invariant in both arms.
- `engine/system/null_interrupt.emp` — **DELETED** (no vector referencer since item
  27; the strip answered its open "does release need a tolerant handler?" with
  `ReleaseFault`).
- A one-line `__Aeon_AS_Carrier: equ 0` was added to both `game_root.asm`s: with
  `debugger.asm` gated out, the RELEASE AS root has no section, which suppressed
  the harvested-engine-constant EquSym re-export (`attach_guarded_equ_exports`
  needs ≥1 section). The equate forces the carrier section. Byte-neutral (EquSyms
  are zero bytes and filtered from the DEBUG-only deb2 appendix).

## Builds compared

Step-0 baseline is `master` at the branch point (`b96051a`). NEW is
`parcel/item29-mddbg-strip`. `SIGIL_BUILD`/`SIGIL_EMIT` from the rebuilt sigil
`master` binaries.

| shape | OLD (`master` @ `b96051a`) | NEW (`parcel/item29-mddbg-strip`) |
|---|---|---|
| `s4.bin` (release) | `crc=3879b953` / 384,048 | `crc=9ed74be5` / 379,802  (see note) |
| `s4.debug.bin` | `crc=2623ee7f` / 423,383 | `crc=b45a553a` / 423,354 |
| `demo.bin` (release) | `crc=f7a93a04` / 70,180 | (see note — not authoritative) |
| `demo.debug.bin` | `crc=e3243cbb` / 93,943 | `crc=3e28584b` / 93,929 |

**DEBUG shapes are authoritative** (they build clean off the committed tree):
`s4.debug.bin` shrinks 29 B, `demo.debug.bin` shrinks 14 B — the `null_interrupt`
deletion plus alignment. The DEBUG vector table and MDDBG island are unchanged in
content.

**RELEASE shapes require the controller's refreeze to build off the committed
tree** — see "Refreeze blocker" below. The `s4.bin` crc/len above come from a
*transient* verification build (a temporary `[[anchor]]` in aeon `map.toml`,
reverted): its content is correct and contiguous (ReleaseFault → Replay_OJZ_Fixture
→ end; no gap), so `crc=9ed74be5` / `len=379,802` should match the controller's
refrozen release ROM. The `s4.bin` shrink is **4,246 B ≈ the 4,272 B error_handler
island** (net of the +38 B ReleaseFault and −2 B NullInterrupt). The `demo.bin`
transient build is NOT authoritative (demo has no section after ReleaseFault, so
the transient anchor islanded ReleaseFault itself at the stale EndOfRom); its
content — vectors and MDDBG absence — is still verified below.

## Result 2 — RELEASE vector table routes every fault at ReleaseFault (STATIC, PROVEN)

> Errata (controller): the addresses/decode below are the implementation agent's
> TRANSIENT build (handler 38 B @ `$5CA34`). The final handler is 46 B @ `$5CA40`
> (the display-off write added after the oracle run — see Result 3), so the final
> cells read `0005 CA40` and the decode gains `33fc 8134 00c0 0004` before the
> reg-7 write. Re-verified on the final ROM: vector $10 = `0005CA40`, PC freezes
> at `$5CA6C`.

`s4.bin` (transient verification build), first 64 bytes + the interspersed cells:

```
$00: ffff ff00   SYSTEM_STACK ($FFFFFF00, initial SSP)     invariant
$04: 0000 0200   EntryPoint ($200)                          invariant
$08..$6C:        0005 ca34  (x26)  ReleaseFault             all faults
$70: ffff b11e   HBlank_Vector_Slot (RAM trampoline)        invariant
$74: 0005 ca34   ReleaseFault (IRQ5)
$78: 0000 20d0   VBlank_Handler                             invariant
$7C: 0005 ca34   ReleaseFault (IRQ7/NMI)
$80..$FC:        0005 ca34  (x32)  ReleaseFault             all TRAPs
```

All 60 fault cells = `0x0005CA34` (ReleaseFault); the 4 invariant cells intact.

`ReleaseFault` bytes @ `0x5CA34` decode exactly to the ruled sequence:

```
46fc 2700              move.w  #$2700, sr
3039 00c0 0004         move.w  ($C00004), d0        ; VDP_CTRL read (reset cmd state)
33fc 8700 00c0 0004    move.w  #$8700, ($C00004)    ; reg 7 = backdrop CRAM[0]
23fc c000 0000 00c0 0004  move.l #$C0000000, ($C00004) ; vdp_comm(0,CRAM,WRITE)
33fc 000e 00c0 0000    move.w  #$000E, ($C00000)    ; CRAM[0] = red
60fe                   bra.s   *                    ; .halt freeze
```

No stack use, no `rte`, no `rts`, no `stop_z80` — as ruled.

## Result 4 — MDDBG present in DEBUG, absent in RELEASE (STATIC, PROVEN)

Distinctive MDDBG blob string `<unknown>` (the symbol-format fallback text):

- `s4.bin` (release): **absent** (0 occurrences).
- `s4.debug.bin`: **present** at offset 389,052.

`ReleaseFault` symbol: **absent** from `s4.debug.lst`; present in `s4.lst`.
`BusError`/`ErrorHandlerBlob`/`MDDBG*`: absent from `s4.lst`; present in
`s4.debug.lst`.

## Strict suite

`SIGIL_STRICT_GATE=1 cargo test --release --workspace --no-fail-fast` is
**compile-blocked on the stale `pins.rs`** (category a — the controller's `repin`
mints the new pins):

```
error[E0425]: cannot find value `RELEASE_FAULT` in module `pins`
error[E0277]: Vec<(&str, u32)>: Extend<(&str, ...pins::Pin)>   (BUS_ERROR is still a Pin, not the debug_only u32)
```

These are exactly the post-repin dependencies: `pins::RELEASE_FAULT` (the new
plain-only region pin) and the per-class pins becoming `u32` (`debug_only`). The
repin machinery itself is exercised green: the 8 `sigil-harness` `repin` unit tests
pass (the new `plain_only` / `debug_end` paths compile and validate). Every test
edited to the post-repin shape is listed in the sigil commit draft.

## Refreeze blocker (CONTROLLER — read before repin)

The RELEASE shapes shrink ~4.2 KB, which drops `EndOfRom` **more than `ANCHOR_GAP`
(0x400)** below its address in the stale frozen size tables
(`golden/offcanonical_sizes/s4.txt` EndOfRom `0x5DC30`, `demo.txt`, `config_b.txt`).
The packing walk then classifies `EndOfRom` (and, in demo, `ReleaseFault` itself) as
an undeclared ANCHOR_GAP island and the full build hard-errors:

```
[map.undeclared-island] ROM section at 0x5DC30 is an ANCHOR_GAP-inferred island ...
```

`repin`'s listing resolve (`resolve_frozen_sections`) does not run that validate, so
`repin` should still produce correct pins for `release_fault` / `error_handler`
(their bases derive off `ReleaseFault` / `Replay_OJZ_Fixture`, which pack
contiguously) — but `ASSEMBLED_LEN`/`EndOfRom` will read stale until the size tables
are re-derived. **Sequence the size-table refreeze so the release EndOfRom
re-baselines; the exact repin↔refreeze ordering (and whether a `--bootstrap-canonical`
re-mint is needed for the shrink past the old anchor) is the controller's ritual.**
I did NOT run `repin`, `refreeze`, or `derive_offcanon`, and did not touch `pins.rs`
or `repin_pins.rs`.

---

> **[CONTROLLER]** Result 1 — all four shapes boot and run in oracle — **DONE, all pass**
>
> | shape | after reset + input | 68k state | fault handler entered? |
> |---|---|---|---|
> | `s4.debug.bin` | OJZ renders + scrolls (240f right) | `VInt_DrawLevel`, SP `$FFFFFEB2` | no |
> | `s4.bin` (release) | OJZ renders + scrolls (240f right), frame pixel-identical to pre-parcel | `EntityWindow_InitSection`, SP `$FFFFFEB2` | no |
> | `demo.debug.bin` | white box on blue | normal main loop | no |
> | `demo.bin` (release, 65,954 B) | white box on blue | normal main loop, SP `$FFFFFEF4` | no |

> **[CONTROLLER]** Result 3 — induced fault — **DONE, both sides pass, and it found a real gap**
>
> Probe: the first instruction of `Camera_Update` replaced with ILLEGAL (`$4AFC`)
> in a scratch copy of each ROM (boot does not verify the checksum), so the fault
> fires on the first gameplay frame. Same fault, both shapes:
>
> - **RELEASE**: 68k frozen at `ReleaseFault.halt`, SR `$2700`, CRAM[0] = `$000E`.
>   **First run showed NO red** — the handler as ruled only recoloured the
>   backdrop, and a scene whose planes cover the screen hides the backdrop
>   completely; the freeze looked like a normal frame. Fixed by adding one write
>   (`$8134`, display OFF) so the entire raster IS the backdrop: re-run gives a
>   **solid red screen**, PC frozen at `.halt` (`$5CA6C`), SR `$2700`. Handler is
>   46 B final (`plain_len $2E`).
> - **DEBUG**: the identical probe lands in the full MDDBG "ILLEGAL INSTRUCTION"
>   screen, offset `006B66` = the patched `Camera_Update` — the strip did not
>   degrade the debug path.

> **[CONTROLLER]** Refreeze + authoritative crc/len — **DONE**
>
> The transient-anchor figures were superseded twice (the controller's
> size-table bootstrap packs 12 B differently than the transient anchor did, and
> the display-off write adds 8): authoritative post-refreeze values are
> `s4.bin crc=40ac3e52 / 379,822` (−4,226), `demo.bin crc=3bf54b74 / 65,954`
> (−4,226), `s4.debug.bin crc=b45a553a / 423,354` (−29),
> `demo.debug.bin crc=3e28584b / 93,929` (−14). Unblock path used for the frozen
> tables: hand-bootstrap of the six offcanonical caches (drop `NullInterrupt`
> everywhere; swap `BusError`→`ReleaseFault` + lower `EndOfRom` in the three
> release tables), immediately re-derived by the refreeze.
