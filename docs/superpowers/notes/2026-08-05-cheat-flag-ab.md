# Debug-fly behind a runtime cheat bit — oracle A/B evidence

Evidence packet for the `cheat-flag` provenance chain entry, per
`sigil/crates/sigil-harness/golden/ab/AB_PROTOCOL.md`. Class: **BA**
(behaviour-adjacent, release-only behaviour change). Follows the `crash-report`
parcel (chain 42), whose no-debug-equipment audit was too narrow and missed this.

## The ruling

Free-flight debug mode was reachable in the shipped release ROM. Owner ruling
(Volence, 2026-08-05): **debug-fly is a CHEAT, not debug equipment.** The code
SHIPS in release as cheat payload; what changes is that it is unreachable until a
runtime bit is set. A future cheat code (button sequence, menu unlock) sets that
bit and needs no code change, because the payload is already shipped and already
exercised by the regression net.

That reclassification is the right one and it sharpens `CODING_CONVENTIONS.md`
§1.7: **equipment is gated at BUILD time and absent from release; a cheat is gated
at RUNTIME and present but unreachable.** Asserts, hotkeys, the self-test and the
boot autoplay stay build-gated and absent. Debug-fly is now runtime-gated.

## What was actually wrong — worse than first reported

The original finding was "a B press reaches debug mode". The real state was worse:
`Player_Init` ended with an **unconditional** `jbra Player_DebugEnter`
(`player_common.emp:200`), so **the shipped game booted into debug-fly and stayed
there**. The B toggle was the only way out. Gating only the toggle would therefore
have shipped a release ROM that boots flying and can *never* leave — strictly
worse than the ungated state. Both sites had to move together.

## Design

- **`Cheat_Flags`** — a `u8` bitfield in game-side RAM (`games/sonic4/config/ram.emp`;
  cheats are game content, not engine), followed by `pad(1)` to keep the following
  words even-aligned. A bitfield, not a bool, so the next cheat needs no new plumbing.
- **`CHEAT_DEBUG_FLY = 1 << 0`** (`games/sonic4/config/constants.emp`).
- **Three gate sites**, all the same three-instruction idiom
  (`moveq #CHEAT_DEBUG_FLY, d0` / `and.b Cheat_Flags, d0` / branch):
  `Player_Main`'s B toggle, `TestPlayer_Main`'s B toggle, and `Player_Init`'s
  boot-entry tail-call.
- **The default costs release ZERO bytes.** Boot already clears all Work RAM, so
  the release/lean default of 0 needs no write at all. Only the DEBUG shape writes
  the flag, one `move.b` at `GameState_OJZScroll_Init`.

`Player_Init`'s only exit had been that tail-call (`Player_DebugEnter` ends in
`rts`, which was serving as `Player_Init`'s return), so the gate-clear path is a
plain `rts`. The slot is fully initialised before the gate — `Player_SetState
PSTATE_AIR`, `Player_RefreshPhysics` and `code_addr = Player_Main` all run ahead of
it — so the normal-player path needed nothing added.

**Init site:** `GameState_OJZScroll_Init` (= `Game.entry`), not `Game.boot_hook`.
The hook is the structurally purer "once per boot" seam but it is already bound
(`SoundTest_BootPing`) in the Config-A shape and can only bind once; a DEBUG-shape
binding would mean registry surgery in `native.rs` for no gain. `Game.entry` is
this game's single boot funnel in every shape and runs before anything can read
the flag, and `Cheat_Flags` is global RAM so the bit stays armed across state
changes.

## Builds

| shape | before (chain 42) | after | delta |
|---|---|---|---|
| `s4.bin` | `36e875f1` / 413,268 | **`a4db281b` / 413,276** | +8 |
| `s4.debug.bin` | `ca450ce0` / 423,388 | **`f05f5b86` / 423,404** | +16 |
| `demo.bin` | `12289484` / 91,224 | `12289484` / 91,224 | **0** |
| `demo.debug.bin` | `18e5ec7f` / 93,963 | `18e5ec7f` / 93,963 | **0** |

Both demo shapes are **byte-identical** — demo has no player and shares no changed
module, which is the control on the blast radius.

`ASSEMBLED_LEN` is **unchanged** at `0x5DC30`: all three gate sites live in the
fixed `0x10000`-byte object bank, whose growth is absorbed by fill. The release +8
is the deb2 appendix gaining the `Cheat_Flags` symbol. `DEBUG_ASSEMBLED_LEN` moves
`0x5F71E` -> `0x5F724` (+6, the DEBUG-only arm write) plus appendix.

`Cheat_Flags` resolves to `$FFFFB464` (release) and `$FFFFDC90` (debug) — the first
game-RAM byte, coincident with `Engine_RAM_End`. Even in both shapes.

Emitted-byte verification, not symbol names (the §1.7 lesson): release `Player_Main`
`$10084` = `1c38 802d / 0806 0004 / 6718 / 7001 / c038 b464 / 6710`, and
`Player_Init`'s tail = `7001 c038 b464 6600 0356 4e75`. The gates are in the
release ROM; the DEBUG arm write (`11fc 0001 dc90`) is not.

## Two process notes from this parcel

**The MDDBG blob-end guard earned its keep immediately.** `DEBUG_ASSEMBLED_LEN`
moved, which shifts `EndOfRom`. Had the fault-handler island not still been the
final emission, the build would have hard-errored instead of silently regressing
every future crash report to `<unknown>`. It passed, first parcel after landing.

**An address-arithmetic claim was wrong again, in a new costume.** The implementation
pass reported `pins.rs` as stale on master, having back-derived a pre-change region
base by subtracting the bytes it had added. Regions are **16-byte aligned**, so +8
of code ate a 2-byte tail pad and pushed the next region a full 16 — the subtracted
value existed in no build. `repin --check` had been right. Same lesson as the
`Debug_AssertObjLoop` retraction one parcel earlier: **measure spans, never do
arithmetic on addresses.**

---

> **[CONTROLLER]** Result 1 — RELEASE boots as a normal player, B inert —
> **DONE, PASS**
>
> `s4.bin`, 180 frames from reset: **Sonic, standing on the ground**
> (`assets/2026-08-05-cheat-flag-release-boot.png`) — not the yellow debug-fly
> square. `Cheat_Flags` (`$FFFFB464`) reads `00`. A 30-frame B press changes
> nothing: the frame after is Sonic, unmoved. Before this parcel the same ROM
> booted into free-flight.

> **[CONTROLLER]** Result 2 — DEBUG behaviourally unchanged — **DONE, PASS**
>
> `s4.debug.bin`: `Cheat_Flags` (`$FFFFDC90`) reads `01` — armed by the
> `GameState_OJZScroll_Init` write. Boots into the **yellow square**
> (`assets/2026-08-05-cheat-flag-debug-boot.png`), and a B press toggles OUT to
> Sonic falling. Identical to pre-parcel behaviour, which is the point: the
> streaming-test workflow is untouched.

> **[CONTROLLER]** Result 3 — release replay regression net — **DONE, PASS**
>
> The fixture contains exactly one B run (`tick 1349, byte 0x10, x3`, followed by
> 110 ticks of right), i.e. the recording session toggling debug-fly OFF. Since
> release now defaults the bit clear, the runbook gains **one more poke**
> alongside `Input_Source` and `Replay_Ptr`: `Cheat_Flags |= CHEAT_DEBUG_FLY` at
> the `GameState_OJZScroll_Init` breakpoint, before resume.
>
> **`Replay_Done` = `$FF`, no `REPLAY DESYNC`, no error screen = PASS**
> (`assets/2026-08-05-cheat-flag-replay-pass.png`), reproducing all 33 curated
> checkpoints across 2,059 ticks.
>
> Poking was chosen over re-recording deliberately. Re-recording would have
> discarded the curated hashes and their provenance to encode a *default*, when
> the run's job is to exercise the same code path in both shapes. The poke also
> means the net now covers the cheat payload itself — shipped code that would
> otherwise have no coverage at all.

> **[CONTROLLER]** Result 4 — repin / refreeze / strict suite — **DONE, clean**
>
> - `refreeze --freeze cheat-flag` -> chain entry 43, seven targets.
> - `refreeze --check`: OK (tip `cheat-flag`, chain len 43). `repin --check`:
>   `pins.rs unchanged`.
> - Strict suite: **3095 passed, 0 failed.**
>
> **The suite caught 13 real failures the implementation pass did not, in three
> classes — none of them stale goldens:**
>
> 1. **9 failures: `Cheat_Flags` was not pin-sourced.** `test_p1_player_port` and
>    `test_g4_final_objects_port` compile `player_common` / `test_player`
>    STANDALONE, so a new game-RAM symbol has to be supplied to those links. Fixed
>    the way the repo's own t24 rule prescribes — a `[[symbol]]` entry in
>    `repin.toml` minting `pins::CHEAT_FLAGS` (shape-dependent, `$FFFFB464` /
>    `$FFFFDC90`), injected in both tests exactly as `Player_1` and
>    `Ctrl_1_Held` already were. Never hand-shift a RAM VMA into a test.
> 2. **2 failures: a hand-maintained literal.** `native_full_rom`'s
>    `Ground_Move_Cap` row moved `+0x10` in both shapes. Updated by hand **on
>    purpose** — that row is an INDEPENDENT expectation checking the convsym
>    resolve path, so pinning it would make the assertion circular. Its comment now
>    says so, to stop a future pass from "fixing" it.
> 3. **2 failures: a seam that had been hand-shifted every parcel.**
>    `ojz_run_a_port`'s `OBJDEF_SEAM` was three literal address pairs feeding the
>    standalone compile; the object bank moved `+0x20` and it failed as a one-byte
>    diff deep inside a data blob. Its own comment already recorded the exact
>    relations (`ObjDef_Static == OBJDEFS base`, `ObjDef_Solid == base + one
>    ObjDef`, `ObjDef_PathSwap == PATH_SWAP base`), so it is now **computed from
>    the pins**. Not circular here: the seam is an *input* to the compile and the
>    assertion compares against the real built ROM, so this removes hand-maintenance
>    without weakening anything. That is one recurring maintenance tax retired.
>
> Counting note: `test result: FAILED. N passed; M failed` has different awk field
> positions than `test result: ok.`, so summing field 4 across the log silently
> under-reports. Count `^test result: FAILED` lines and `---- name stdout ----`
> blocks instead — an early run here reported "0 failed" while 13 tests were red.
