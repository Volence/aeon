# CRASH_REPORT — a shipped crash is reportable — oracle A/B evidence

Evidence packet for the `crash-report` provenance chain entry, per
`sigil/crates/sigil-harness/golden/ab/AB_PROTOCOL.md`. Class: **BA**
(behaviour-adjacent, shape-split). Plan:
`docs/superpowers/plans/2026-08-05-crash-reporting-and-symbols.md`, Part B.
Depends on Part A (`mddbg-symbols`, chain 41) — shipping the screen without
working symbols would have delivered hex addresses and a listing lookup.

## The ruling

Release showed `ReleaseFault`: mask IRQs, display off, red backdrop, freeze.
Loud, but carrying **zero diagnostic content**. Volence ruled that if a player
hits a crash they must be able to REPORT it, so the shipped build now shows the
full MD Debugger screen with resolved symbol names — something a person can
photograph and send.

The 4,272 B item-29 strip was never a space win: the release ROM was 379,822 B of
a 4 MB cart, **9% full**. The debugger is 0.1% of the cartridge and the symbol
table another ~0.7%. Space is not a constraint on the 68k side. (It IS on the
Z80 side — a hard 8 KB with ~316 B headroom — but nothing here touches it.)

Parcels 3 and 7 are **not reverted**. They converted unconditional behaviour into
*flags*; this chooses the other setting. `ReleaseFault` stays alive and verified
as the lean shape's arm.

## The shape matrix as implemented

Two independent axes. `DEBUG` is unchanged and still means "debug shape";
`CRASH_REPORT` (default **1**) means "carry diagnostics".

| profile | `DEBUG` | `CRASH_REPORT` | `__DEBUG__` | `__MDDBG__` | fault handler | asserts / hotkeys / selftest |
|---|---|---|---|---|---|---|
| `s4` (release, **ships**) | 0 | 1 | — | 1 | MDDBG screen | **no** |
| `s4_debug` | 1 | 1 | 1 | 1 | MDDBG screen | yes |
| `demo` | 0 | 1 | — | 1 | MDDBG screen | no |
| `demo_debug` | 1 | 1 | 1 | 1 | MDDBG screen | yes |
| `config_a` | 1 | 1 | 1 | 1 | MDDBG screen | yes + hotkeys + mirror |
| `config_b` | 0 | 1 | — | 1 | MDDBG screen | no |
| **`lean`** (opt-in) | 0 | **0** | — | — | **`ReleaseFault`** | no |

The rule that keeps this honest, now stated in `CODING_CONVENTIONS.md` §1.7:
**diagnostics ship, equipment does not.** A crash screen tells you what broke;
asserts, hotkeys, the boot autoplay, the compression self-test and the sound
debug mirror are things you *drive*, and they remain strictly `DEBUG`-only.

Owner rulings taken at plan time rather than assumed: lean is a full 7th
off-canonical profile (a buildable shape structurally needs a frozen size table,
which needs a committed golden blob — there is no cheaper honest arrangement);
`demo`'s release carries the debugger too (an engine that only crash-reports for
Sonic 4 is not the game-agnostic engine demo exists to prove); `config_b` follows
the release default so "release" means one thing everywhere.

## What changed

**aeon** — `engine/system/vectors.emp` (four fault-cell predicates widened to
`DEBUG == 1 || CRASH_REPORT == 1`; the four shape-invariant cells untouched);
both `game_root.asm`s (the `debugger.asm` include re-gated `ifdef __DEBUG__` ->
`ifdef __MDDBG__`); `release_fault.emp` and `error_handler.emp` (stale
shape claims corrected); `CODING_CONVENTIONS.md` §1.7 rewritten; `build.sh`
(header + a refusal for `CRASH_REPORT=0` pointing at `sigil build --native
--lean`); `docs/ENGINE_ARCHITECTURE.md` §8.2.

**sigil** — `GameProfile::crash_report`; `registry(debug, crash_report)` places
`error_handler` under `debug || crash_report` and `release_fault` under the
`else`; a `__MDDBG__` definedness push beside `__DEBUG__`; the appendix predicate
widened at all three sites; `lean_profile()` + `BuildTarget::Lean` + `--lean`;
the 7th target threaded through `derive_offcanon`, `refreeze` and
`capture_goldens.sh`; `repin.toml` (`error_handler` loses `debug_only`,
`replay_fixture` loses its `debug_end`, the `release_fault` region is deleted).

`__MDDBG__` is a separate definedness define rather than a reused `__DEBUG__`
because AS `ifdef` tests definedness, not value — a `CRASH_REPORT=0` would still
take the arm — and because `__DEBUG__` must keep meaning exactly "debug shape".

### Why `ReleaseFault` has no pin any more

`repin` resolves exactly two listings, the canonical plain and debug shapes.
`ReleaseFault` is now in **neither**, so it cannot be pinned; the `release_fault`
`[[region]]` is deleted and the registry entry uses `DUMMY_REGION`. Lean places
it from its own frozen size table, exactly as `config_a`/`config_b` place theirs.
The 12 per-class stub symbol pins stay `debug_only` **deliberately**: their
per-shape bases are already carried once by the `error_handler` REGION pin, the
island's internal layout is shape-invariant (`error_handler.emp` contains no
`if DEBUG` at all), and duplicating 12 addresses across two shapes would be 24
numbers free to rot independently of the one that matters. Release-arm consumers
derive `ERROR_HANDLER.plain_base + (PIN - BUS_ERROR)`. This is the pre-existing
idiom, not a new one — the `MDDBG__*` pins already carried the same note.

## Builds

| shape | OLD (`master` @ chain 41) | NEW (`parcel/crash-report`) |
|---|---|---|
| `s4.bin` (release) | `a46a39f6` / 379,822 | **`36e875f1` / 413,268** (+33,446) |
| `s4.debug.bin` | `ca450ce0` / 423,388 | `ca450ce0` / 423,388 (**unchanged**) |
| `demo.bin` (release) | `ea6213bc` / 65,954 | **`12289484` / 91,224** (+25,270) |
| `demo.debug.bin` | `18e5ec7f` / 93,963 | `18e5ec7f` / 93,963 (**unchanged**) |
| `config_a.bin` | `fa15ffa1` / 423,765 | `fa15ffa1` / 423,765 (**unchanged**) |
| `config_b.bin` | `b991af6c` / 271,790 | **`ed2ad40e` / 304,788** (+32,998) |
| `lean.bin` (new) | — | `a46a39f6` / 379,822 |

Two facts do the load-bearing verification work here:

1. **`lean.bin` is byte-identical to the pre-parcel release ROM** (`a46a39f6` /
   379,822, `cmp` clean). The whole axis is provably inert at `CRASH_REPORT=0`.
2. **All three debug-shape goldens are bit-for-bit unchanged.** The parcel could
   not have perturbed the debug shape even accidentally.

`s4.bin` grows by the 4,272 B island less the 46 B `ReleaseFault` (+0x1082
assembled) plus a 29,220 B deb2 appendix past `EndOfRom`. At 413,268 B the
shipped cart is **9.9% of 4 MB**.

### Size-table hand-seed (the ANCHOR_GAP unblock, growth direction)

The release shapes grow `EndOfRom` by more than `ANCHOR_GAP` (0x400), which makes
the packing walk classify it as an undeclared island and hard-error before the
build can run — parcel 7 hit the mirror of this in the shrink direction. The
three release tables were hand-seeded first: delete the `ReleaseFault` row, add
`BusError` at the same address (the island takes that tail slot), raise
`EndOfRom` / `# assembled_end=` by exactly `+0x1082`.

| table | `ReleaseFault` -> `BusError` | `EndOfRom` | `# labels=` |
|---|---|---|---|
| `s4.txt` | `0x5CB80` | `0x5CBAE` -> `0x5DC30` | 72 (one out, one in) |
| `demo.txt` | `0x10174` | `0x101A2` -> `0x11224` | 41 |
| `config_b.txt` | `0x42580` | `0x425AE` -> `0x43630` | 71 |

The seeds turned out **exact**, not approximate — the live builds landed on
precisely those `EndOfRom` values, so `derive_offcanon` had nothing to converge.

`lean.txt` / `lean.bin` were bootstrapped as literal copies of the pre-parcel
`s4.txt` / `s4.bin`, which is sound precisely because lean is byte-identical to
the old release.

## No debug equipment leaked into release

Verified by symbol search on the NEW `s4.lst`, not by assumption. Absent (0 hits
each): `CompressionSelfTest`, `CSelf_*`, `Debug_MusicToggle`, `Sound_DebugMirror`,
`Dbg_Music_On`, `Dbg_Sfx_Sel`, `Debug_Scene_Freeze`. Present: `BusError`,
`ErrorHandlerBlob`, `ErrorExcept`, `ErrorTrap`. The probe names are not typos —
the same greps against `config_a.lst` return 14-16 hits each. Boot autoplay lives
only in `games/sonic4/debug/game_debug.emp`, a Config-A-only registry module, and
is absent from release AND from `s4.debug.bin`. `lean.lst` inverts correctly:
`ReleaseFault` present, `BusError`/`ErrorHandlerBlob` absent.

### One pre-existing leak found in passing, NOT caused by this parcel

`Debug_AssertObjLoop` (`engine/objects/core.emp:564`) is an unconditional
`pub proc` whose only call sites are `if DEBUG == 1`-wrapped, so its bytes ship in
release. It sits at `0x2BEE` in both the new `s4.bin` **and** in `lean.bin` (= the
pre-ruling release ROM), which proves it predates this work. Recorded in
`docs/DEFERRED_WORK.md` for a one-line follow-up (registry-gate it or wrap the
proc); deliberately not fixed here, because folding an unrelated byte change into
a parcel whose central evidence is "lean is byte-identical" would have destroyed
that evidence.

---

> **[CONTROLLER]** Result 1 — the RELEASE shape shows the crash screen WITH
> symbol names — **DONE, the acceptance bar is MET**
>
> Probe: the first instruction of `Camera_Update` replaced with `ILLEGAL`
> (`$4AFC`) in a scratch copy, so the fault fires on the first gameplay frame.
>
> `s4.bin` (release), `assets/2026-08-05-crash-report-release.png`:
> ```
> ILLEGAL INSTRUCTION
> Offset:  005C66   Camera_Update
> Caller:  05C93C   GameState_OJZScroll_Update+C
> ```
> Full register dump, stack window and HInt line as in the debug shape. This is
> what a player photographs and sends.
>
> `demo.bin` (release), `assets/2026-08-05-crash-report-demo.png`:
> ```
> Offset:  010002   DemoBox_Main
> Caller:  00148A   RunObjects.culled_loop+3A
> ```
> The engine crash-reports for a game that contains no Sonic code at all — which
> is the point of demo existing.

> **[CONTROLLER]** Result 2 — the lean shape still red-screens and freezes —
> **DONE, PASS**
>
> Same probe on `lean.bin`: **solid red screen**
> (`assets/2026-08-05-crash-report-lean-redscreen.png`), PC frozen at `$5CBAC` =
> `ReleaseFault + $2C` (the `.halt` `bra`), SR `$2700`. Byte-for-byte the
> pre-parcel release behaviour, because it is byte-for-byte the pre-parcel ROM.

> **[CONTROLLER]** Result 3 — the debug shape is unchanged — **DONE, PASS**
>
> `s4.debug.bin` is byte-identical (`ca450ce0` / 423,388 both sides), so this is
> true by construction; re-run anyway and the screen is pixel-identical to Part
> A's (`Offset: 006B86 Camera_Update`, `Caller: 05E430
> GameState_OJZScroll_Update.skip_camera_update`). `demo.debug.bin` and
> `config_a.bin` are likewise byte-identical.

> **[CONTROLLER]** Result 4 — gameplay is unchanged — **DONE, PASS, by the
> standing regression net rather than a screenshot**
>
> I first tried the "standard deterministic capture" (reset, `start` 180f,
> `right` 240f, compare frames) and found it **is not frame-stable in oracle
> across reloads** — three runs of the SAME ROM in one session advanced 240, 240
> and 239 frames and produced three different frames. Screenshot equality at a
> press-frame budget is therefore not evidence, in either direction. Recording
> this because it would silently produce a false "regression" for the next
> parcel that leans on it.
>
> The right instrument is the input-replay net (`docs/superpowers/2026-08-02
> -engine-debts-opener-evidence.md`, "The standing runbook"): persistent bp at
> `GameState_OJZScroll_Init` **before** `reload_rom`, poke `Input_Source` = 1 and
> `Replay_Ptr` = `Replay_OJZ_Fixture + REPLAY_HEADER_LEN (20)`, clear bps, resume.
>
> **`s4.bin` (release, crash-report): `Replay_Done` = `$FF`, no `REPLAY DESYNC`,
> no error screen = PASS** (`assets/2026-08-05-crash-report-replay-pass.png`).
>
> This is strictly stronger than a frame compare. The fixture's curated
> per-checkpoint state hashes were recorded against the PRE-parcel ROM and the
> fixture blob is untouched by this parcel, so a clean run means release-shape
> gameplay state matches pre-parcel at **every checkpoint across ~1,282 ticks** —
> not at one arbitrary frame. Any physics, camera, streaming or object-lifecycle
> divergence would have desynced. Its replay entry points also resolve to
> identical addresses in both shapes (`Input_Source` `$FF803A`, `Replay_Ptr`
> `$FF8040`, `Replay_OJZ_Fixture` `$5CA34`), confirming the island lands entirely
> past everything the net covers.
>
> `demo.bin` (release) boots to the white box on dark blue, frame **`cmp`-identical
> to the pre-parcel capture** despite the ROM growing 25,270 B.
>
> Not separately re-run on `lean.bin`: it is byte-identical to the pre-parcel
> release ROM, so the net could only re-prove the recording.

> **[CONTROLLER]** Result 5 — repin / refreeze / strict suite — **DONE, clean**
>
> `repin` moved exactly four pins, all of them the tail, and all four are the
> arithmetic inverse of item 29 part 4's plain-shape delta:
> `ASSEMBLED_LEN 0x5CBAE -> 0x5DC30` (+0x1082), `ERROR_HANDLER` gains its plain
> arm (`plain_base 0x5CB80`, `plain_len 0x0 -> 0x10B0`), `EPILOGUE` +0x1082, and
> `RELEASE_FAULT` is **removed**. `DEBUG_ASSEMBLED_LEN` does not move.
>
> - `refreeze --freeze crash-report --ab <this note>` -> chain entry 42, now over
>   **seven** targets (`lean` derived clean at `a46a39f6` / end `0x5CBAE`).
> - Strict suite: **3062 passed / 0 failed**.
> - `refreeze --check`: OK (tip `crash-report`, chain len 42).
> - `repin --check`: `pins.rs unchanged`.
>
> **One real regression the implementation pass missed, found by the suite and
> fixed here:** `native_offcanonical_placement::config_b_doctored_size_table_
> breaks_the_build` derived its compare window as `eor = golden.len()`, justified
> by the comment *"Release ships NOTHING past EndOfRom since item 29"*. This
> parcel repeals exactly that premise — `config_b` is a release shape and now
> carries a ~28 KB appendix — so the test indexed `base[276016]` on a 276,016-byte
> image and panicked. The same line had **already rotted once** (a hand-typed
> `0x43470` that survived the item-29 strip); its own comment says so. Both
> cheap sources are now gone: it reads `provenance::tip_target("config_b")
> .anchor_end`, the same authority `native_offcanonical_rom::anchor_end` uses,
> with an explicit `golden.len() >= eor` guard. A premise written into a comment
> is not a gate — that is the third time this repo has paid for it.
