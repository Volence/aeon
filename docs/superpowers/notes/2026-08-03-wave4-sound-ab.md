# Wave-4 Z80 sound reclaim — oracle A/B evidence

Evidence packet for the `wave4-z80-sound-reclaim` provenance chain entry, per
`sigil/crates/sigil-harness/golden/ab/AB_PROTOCOL.md`. Class: **PS** (pure-size /
value-identical) for the reclaim, **BA** (behaviour-adjacent) for the seven bug fixes.

The standard PS bar (framebuffer + VRAM/CRAM byte-identity) is BLIND to this parcel — the
changes are Z80-side and touch no plane data. The bar used here is the sound-specific
equivalent: Z80 driver state identity plus emitted-chip-stream identity.

## Builds compared

| side | tree | plain ROM | debug ROM |
|---|---|---|---|
| OLD | `master` @ `7d3dd18` | `crc=3add2a69` / 413224 | `crc=af882b6c` / 423377 |
| NEW | `parcel/wave4-z80-sound-reclaim` @ `5526113` | `crc=e4e55c84` / 413238 | `crc=6ee92ea7` / 423391 |

Cross-check that isolates the two Sigil changes: **master built with the NEW toolchain
reproduces `crc=3add2a69` / 413224 and blob md5 `98126bcf…` exactly**, so the derived-base
refactor and the opt-in dense-pad mode are provably neutral on unmodified source.

Scene: the `config_a` profile (DEBUG + sound hotkeys + mirror), whose `SoundTest_BootPing`
autoplays music at boot — a reset-deterministic scene with no human input timing, as the
protocol requires.

## Result 1 — driver state identity

Z80 state block `$18F0..$18FF`, captured after ~38 s of music in both runs:

```
OLD  00 0B 0B 0B 00 00 00 00 00 00 34 1B 00 00 00 00
NEW  00 0B 0B 0B 00 00 00 00 00 00 34 1B 00 00 00 00
```

Byte-identical: same DAC phase, same song bank (`$0B`), same ROM/current bank, same ring
read/write pointers, same FM6 channel pointer (`$1B34`), same adaptive flag.

Mailbox/status `$1F00..$1F13`: alive marker `$5A`, ping echo `$3C`, ack count `$02` — all
identical. The ack count matching is the direct positive observation for driver item 6.1
(the seven mailbox ack tails factored into `Snd_AckSlot`/`Snd_AckBump`): the mailbox is
still being consumed and acknowledged exactly as before. Only `SND_STAT_TICK` differs
(`$05` vs `$C6`), which is a free-running per-frame counter read at different wall-clock
moments — expected, and the documented tolerance.

## Result 2 — chip-stream identity

VGM captured from reset, both runs (`tools/vgm_onsets.py` → per-channel YM2612 key-on
timeline with the F-number/block latched at each onset).

| | OLD | NEW |
|---|---|---|
| VGM size | 157,311 B | 159,063 B |
| duration | 38.18 s | 37.91 s |
| onsets | 1311 | 1312 |

The captures begin at different song phases (VGM capture is realtime-only, so the start
point is not reproducible). Aligning by maximising sequence match over a wide offset search
finds OLD skip 9 / NEW skip 0, and on that alignment:

- **1302 / 1302 onsets identical** in `(channel, fnum, block)` — 100.000%, zero mismatches.
- **Cumulative tempo drift: 22 samples ≈ 0.50 ms over 37.5 s**, bounded (min −14, max +116),
  linear slope 0.0008 samples/onset. A tempo change would show as persistent non-zero slope;
  there is none. The per-interval jitter (mean 12.8 samples ≈ 0.29 ms) is sub-frame capture
  phase noise, not musical timing.

Verdict: the reclaim emits the same notes, on the same channels, at the same pitches, in the
same order, at the same tempo.

## Result 3 — the crash this A/B caught

The first A/B run FAILED and is the reason this phase exists. NEW produced only 26,721 bytes
of VGM against OLD's 157,311, and the 68k was sitting in `ErrorHandlerBlob`:
`ADDRESS ERROR` at `$001889` (debug) / `$001B91` (config_a) — odd addresses.

Cause: `boot.emp`'s copy loop walks `a5` through the Z80 blob and then continues with the
same register into `boot_tail`'s 4 PSG-silence bytes and its word-wide VDP command reads. The
reclaim moved the blob from 6172/6298 (even) to 5941/6067 (odd), so every following
`move.w (a5)+` landed misaligned.

Bisected to the reclaim half by building at the end of Phase 1 (`2adf697`), which boots
clean. Fixed in `5526113` with `align 2` inside the `Z80_Sound_Start`/`_End` brackets plus
`ensure((Z80_SOUND_SIZE & 1) == 0)`.

Two false leads recorded so they are not re-walked: `pins.rs` was stale (regenerated with
`repin`, every pin −0xE0/−0xE4..0xF0) but is a gate/record and NOT a placement input — the
ROM CRCs were byte-identical before and after the repin, so it was not the cause. And
`Z80_SOUND_SIZE` is link-derived with no hardcoded mirror in Aeon, so a stale size constant
was not the cause either.

**Consequence for the record:** every ROM built during Tasks 5-8 was unrunnable for this
reason. Those tasks' blob-size measurements remain valid (the blob is emitted independently
of the ROM link), but no functional claim about them could have been made before `5526113`.

## Result 4 — boot, both shapes

`s4.debug.bin` and `config_a.bin` both reach the normal main loop (`VSync_Wait`) after reset
and stay there; the driver reports its alive marker (`$5A`) and services the mailbox.

## Not covered here

- **Driver B1** (boot-window SFX garbage) is oracle-INVISIBLE by construction: emulators zero
  RAM at power-on, so the pre-fix behaviour cannot be exhibited. Verified statically; the
  deliberate garbage-poke demonstration is noted in the plan as outstanding.
- The audible bug fixes (SFX B1 duck-ramp drone, PSG zero-divisor, sequencer glide underflow,
  FM patch-pan clobber) change behaviour only in states this scene does not enter, so the
  onset-identity result above neither confirms nor refutes them; they are argued from source
  and from the reachability analysis in their commit messages.
- **PSG M5** is a guard for content that does not exist yet, so it is unobservable by design.
