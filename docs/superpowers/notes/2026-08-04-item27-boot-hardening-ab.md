# Item 27 (boot hardening) — oracle A/B evidence

Evidence packet for the `item27-boot-hardening` provenance chain entry, per
`sigil/crates/sigil-harness/golden/ab/AB_PROTOCOL.md`. Class: **BA**
(behaviour-adjacent). Every change is on the reset path, which is the one path
whose failure mode is "nothing boots at all" — so the bar here is boot-and-run in
**all three shapes**, not byte identity.

Scope is the owner's ruling-4 **provably-safe subset**. The YM key-off race is
deliberately NOT fixed; see the bottom of this note.

## Builds compared

| shape | OLD (`master` @ `0395fa7`) | NEW (`parcel/item27-boot-hardening`) |
|---|---|---|
| `s4.bin` (release) | `crc=b06fc575` / 384,048 | `crc=056aa103` / 384,048 |
| `s4.debug.bin` | `crc=abf1d304` / 423,383 | `crc=b5c1a039` / 423,383 |
| `demo.debug.bin` | `crc=d4c00097` / 93,929 | `crc=cdb58b5a` / 93,943 |

Boot region: plain `0x198 -> 0x1A0`, debug `0x19C -> 0x1A0`. Plain grows +8 (the
4-byte `lea` plus a 4-byte align pad the new length needs), debug +4 (the `lea`
alone — it was already aligned), so the two shapes converge on one `BootData`
base for the first time. Everything downstream slides +0x10.

Byte-diff of the boot body against a probe build with ONLY the `lea` removed:
**10 differing bytes, all low bytes of relocated address/displacement operands.**
No instruction changed size; no relaxation flipped.

## Result 1 — all three shapes boot and run

This is the load-bearing result for a reset-path parcel.

| shape | after reset + 240 frames of input | 68k state |
|---|---|---|
| `s4.debug.bin` | OJZ renders and scrolls correctly | PC in `VInt_DrawLevel`, SP `$FFFFFEB2` |
| `s4.bin` (release) | OJZ renders and scrolls correctly | PC in `EntityWindow_InitSection`, SP `$FFFFFEB2` |
| `demo.debug.bin` | the documented white 16x16 box on the dark-blue backdrop | running, normal PC |

None entered `ErrorHandlerBlob`. The release capture is **pixel-identical** to the
pre-parcel release capture, so the boot changes are visually inert as intended.

SP reads `$FFFFFEB2` in both sonic4 shapes — sane, and below `SYSTEM_STACK`
(`$FFFFFF00`), which is what the new `lea (SYSTEM_STACK).w, sp` seeds.

`demo.debug.bin` is the shape that actually carries the changed `z80_init` idle
blob (sound-off), which is why it is in the packet rather than treated as
incidental.

## Result 2 — the PSG reorder does not desync the `a5` stream

The hazard this reorder had to avoid: boot walks a SINGLE cursor `a5` through the
Z80 blob, then the 4 PSG-silence bytes, then word- and long-wide VDP command
reads. An earlier parcel took a real boot ADDRESS ERROR from exactly that stream
going out of step, so "it is only a reorder" is not sufficient argument.

`.wait_fill` is `move.w (a4),d2` / `btst #1,d2` / `bne` — **a4 is read with no
post-increment and only `d2` is written**. It touches neither `a5` nor `a3` (the
VDP_DATA base the PSG displacement rides). So moving the PSG block across it
leaves the `(a5)+` consumption order byte-for-byte identical (blob, 4 PSG bytes,
autoinc word, CRAM long, VSRAM long) and `a5`'s value identical at every
consumer. `d2` has no cross-boundary dependency either way.

Confirmed empirically: a probe build with only the `lea` removed places
`BootData` at `$398` — exactly the pre-parcel pinned base. **The reorder is
byte-neutral**; all of the growth is the `lea`.

## Result 3 — the vector policy, and a stale review premise

The review's premise did not match HEAD. It described a shape split
("`NullInterrupt` in release, `ErrorExcept` under `__DEBUG__`") that was **never
implemented** — `vectors.emp` has no `if DEBUG` anywhere. The real inconsistency
was *within* the table: `$60` spurious halted loudly while the unmodelled IRQ
levels silently `rte`'d.

Under the owner's ruling ("halt loudly in BOTH shapes"), these five moved from
`NullInterrupt` (a bare `rte`) to `ErrorExcept`:

| vector | before | after |
|---|---|---|
| `$64` IRQ1 | `NullInterrupt` | `ErrorExcept` |
| `$68` IRQ2 (external, controller TH) | `NullInterrupt` | `ErrorExcept` |
| `$6C` IRQ3 | `NullInterrupt` | `ErrorExcept` |
| `$74` IRQ5 | `NullInterrupt` | `ErrorExcept` |
| `$7C` IRQ7 (NMI) | `NullInterrupt` | `ErrorExcept` |

`$60` and the 12 reserved slots were already `ErrorExcept`. `$70` (HBlank slot)
and `$78` (VBlank) untouched. Byte-neutral — only `dc.l` values change — and
verified in all three ROMs at `$60..$7F`.

Consequence: **`NullInterrupt` now has zero referencers.** Deliberately NOT
deleted — that is the blocked release-strip parcel's call — and both
`null_interrupt.emp` and the policy comment in `vectors.emp` say so. The policy
block is marked owner-ruled and warns a future strip parcel that it must preserve
loud failure rather than revert to `rte` (which is actively wrong for the fault
classes: it re-executes the faulting instruction). `DEFERRED_WORK.md`'s dangling
count was corrected 55 -> 60 accordingly.

## Result 4 — `z80_init` SP

`ld sp,hl` (with `hl == 0`) became `ld sp, Z80_RAM_SIZE - 2` = `$1FFE` — the top
of the Z80's own 8 KB RAM, and exactly the convention the real driver already
uses (`SndDrv_Init`'s `ld sp, SND_STACK_TOP`). The old SP of 0 meant a first push
would wrap to `$FFFF`, which is the 68k bank window.

This blob is only resident in sound-OFF shapes (`demo`, `config_b`) — the sound
blob replaces it otherwise — so it can never collide with the driver's stack.

**Size consequence, accepted:** no 1-byte Z80 instruction loads SP with a
constant, so the idle body grew **38 -> 40 B**. Both halves of the size mirror
moved with it (`boot_data.emp`'s `Z80_IDLE_SIZE`, `z80_init.emp`'s `ensure`).
Verified in `demo.debug.bin`: idle at `$3D0`, `.code_end` at +40, and the tail
resumes contiguously into `boot_tail`'s PSG bytes with no hole.

## Deliberately NOT fixed — the YM key-off race

Per the owner's ruling, verbatim: *"LEAVE THE YM KEY-OFF BUSY-WAIT RACE
UNTOUCHED, documented with a written spec — there is no real hardware here, and
getting its timing wrong is worse than the current state because it would look
addressed."*

The key-off block is **byte-for-byte untouched** (a comment-filtered diff of
`boot.emp` contains zero lines from it). The spec is
`docs/specs/boot-ym-keyoff-race.md`, covering the mechanism, the sharper
dual-owner latch race against the already-running Z80 driver, why it is mostly
moot today (the `/IC` reset pulse earlier in boot already keyed everything off),
both candidate fixes, and the revisit triggers — the dangerous one being anyone
shortening that `/IC` pulse, which would make these six unpaced writes
load-bearing.

## Also stale in the review, recorded rather than acted on

**Cross-reset RAM (finding 1) does not exist.** `grep -r CROSS_RESET engine/
games/` returns nothing — no region, no magic, no write. The finding described
the pre-`.emp` tree. Per the owner's default ("document rather than change
semantics"), the clear loop was left untouched and two `ENGINE_ARCHITECTURE.md`
feature-table rows that read as though the persistence ships were corrected to
say it is DESIGN ONLY. It has now survived two review passes as a design with no
code, and is flagged for a keep-or-delete ruling.

**Finding 4 (Z80 blob evenness assert) was already done** by the wave-4 parcel
(`align 2` + the evenness `ensure`); verified present, not redone.

## Gates

Strict suite **3000 passed / 0 failed** after the re-pin. 132 tests failed before
it, all stale-pin fallout from boot legitimately moving (`pins_rs_is_current`
named 89 changed pins; everything else followed). One failure was NOT staleness
and was fixed as a harness input: `boot_port` lowers `boot.emp` standalone and
had never needed `SYSTEM_STACK`, so it was added to that gate's value-equ table
(`vectors_port` already carried it at the same value). `refreeze --check` +
`repin --check` clean.
