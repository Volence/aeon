# Item 25 (sequencer reclaim) — oracle A/B evidence

Evidence packet for the `item25-sequencer-reclaim` provenance chain entry, per
`sigil/crates/sigil-harness/golden/ab/AB_PROTOCOL.md`. Class: **PS** (pure-size /
value-identical). Both changes are behaviour-identical by construction:

- **H3** retargets 18 `jp Seq_ContinueFetch` at `Sequencer_NextOpcode.fetch`.
  The trampoline is a pure `jp` with an empty `clobbers()`, so the only thing
  that changed at each site is the jump's destination address. Zero bytes.
- **M1** replaces `or (ix+(sc_porta_incr+1))` with `or a` at four portamento
  gates. Same Z flag, same `a`, given the field's high byte is 0 — which four
  independent writers enforce and which `Porta_Apply` already depends on.

The standard PS bar (framebuffer + VRAM/CRAM identity) is BLIND to this parcel:
the changes are Z80-side and touch no plane data. The bar used here is the
sound-specific equivalent the wave-4 parcel established — driver state identity
plus emitted-chip-stream identity.

## Builds compared

| side | tree | plain ROM | debug ROM | config_a |
|---|---|---|---|---|
| OLD | `master` @ `b96606e` | `crc=d585979e` / 413246 | `crc=2b9aa464` / 423383 | `crc=db13551e` / 423749 |
| NEW | `parcel/item25-sequencer-reclaim` @ `33eb4b9` | `crc=56f1b3ba` / 413246 | `crc=abf1d304` / 423383 | `crc=e7ed9d66` / 423749 |

Z80 resident blob **5941 -> 5933 plain**, **6067 -> 6059 debug** (-8 B each, all
of it M1). DEBUG headroom against the `$18F0` ceiling: **317 -> 325 B**. Both
shapes built with the size tripwire **ARMED** — no `SIGIL_BLOB_LEN_DRIFT`
override.

Scene: the `config_a` profile (DEBUG + sound hotkeys + mirror), whose
`SoundTest_BootPing` autoplays music at boot — a reset-deterministic scene with
no human input timing, as the protocol requires.

## Result 1 — chip-stream identity

VGM captured from reset on both sides, ~42 s each, then reduced to per-channel
YM2612 key-on timelines with the F-number/block latched at each onset
(`tools/vgm_onsets.py`).

| | OLD | NEW |
|---|---|---|
| VGM size | 179,511 B | 192,333 B |
| duration | 42.29 s | 45.88 s |
| onsets | 1431 | 1500 |

The captures begin at different song phases (VGM capture is realtime-only, so
the start point is not reproducible). Aligning by maximising sequence match over
a wide offset search finds OLD skip 0 / NEW skip 38, and on that alignment:

- **1431 / 1431 onsets identical** in `(channel, fnum, block)` — 100.000%,
  **zero mismatches**.
- **Cumulative tempo drift: 1 sample = 0.02 ms over 42.2 s**, bounded
  (min -43, max +2), linear slope 0.0007 samples/onset. Mean per-interval
  jitter 1.3 samples (0.03 ms) is sub-frame capture phase noise. A tempo change
  would show as a persistent non-zero slope; there is none.

This is a tighter result than the wave-4 parcel's own (22 samples / 0.50 ms),
which is what a pure-jump-retarget plus a flag-equivalent instruction swap
should look like.

## Result 2 — driver state identity

Z80 state block `$18F0..$18FF` after ~42 s of music:

```
NEW  00 0B 0B 0B 00 00 00 00 00 00 34 1B 00 00 00 00
```

Byte-identical to the value the wave-4 packet recorded for this same scene on
both of its sides: same DAC phase, same song bank (`$0B`), same ROM/current
bank, same ring read/write pointers, same FM6 channel pointer (`$1B34`), same
adaptive flag.

## Result 3 — no crash

The 68k stays in the normal main loop throughout (PC in `Process_DMA_Important`
/ `Process_DMA_Critical`), never in `ErrorHandlerBlob`.

## What this does NOT cover

- **The four `jr Seq_ContinueFetch` sites** still route through the trampoline
  by design (they need it to stay in short-branch range). They are unchanged and
  therefore not exercised differently by this A/B.
- **The M1 invariant is argued statically, not observed.** A non-zero
  `sc_porta_incr` high byte is unreachable, so no scene can exhibit the
  difference. The census of writers is in the commit message; the corroborating
  argument is that `Porta_Apply` already assumes hi==0 today (`ld h,0`, and an
  8-bit `sub`), so a reachable non-zero high byte would mean portamento is
  already broken independently of this change.
- **Portamento itself is not exercised by this scene** beyond whatever the
  autoplayed song contains. The gates were verified by identity of the whole
  chip stream rather than by a targeted glide fixture.

## Dropped from this parcel (see the commit message for full reasoning)

**H1** (global tempo accumulator) — premise proven wrong on 2026-08-03; it is a
chip-stream change on a tempo-event frame and needs a ruling. **H2**
(page-aligned opcode dispatch) — would move eight pinned regions in a bank head
with zero slack; wave-4 dropped SFX S1 for exactly that. **M3** (Porta_Apply
ladder factoring) — buys bytes we no longer need at a cycle cost, now that
headroom is 325 B rather than 86 B.
