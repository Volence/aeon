# Owed runtime witnesses, batch c: the three A2 RUNTIME-TAGs (2026-09-12)

Worktree helper for the aeon controller, branch `witness/owed-runtime-0912c`, cut from
`origin/master` `47bc76d4`. Headless only: every emulator was an `oracle-aether` spawned and
reaped by `tools/aether_instance.py`. **No emulator MCP tool was called.** No tracked `.emp`
was changed by any commit here; one was patched, built from, and restored under verification
inside a witness run (Leg 2, below).

| booking | verdict | measured | control |
|---|---|---|---|
| GAP12-A2-9b, song load mid-drum | **SPLIT** — (i) HOLDS, (ii) NOT REPRODUCED | (i) 1067 more DAC bytes = **58.1 ms** of drum streamed into a DAC whose enable bit is off, over 133.8 ms of wall time, ending on `.stop`'s own `$2A <- $80`. (ii) `.stop`'s epilogue wrote **nothing** in all three load targets | the same drum with no load streams its whole 1509-byte / 82.2 ms remainder with the DAC **enabled**, and its `.stop` epilogue keys `$28 <- $F6` |
| GAP12-A2-11b, stale `FADE_BUSY` | **HOLDS, bounded** | after a mid-fade `Sound_StopMusic` the byte stays 1 for the whole **5.0 s** watch with `SEQ_ACTIVE = 0`; the next `Sound_PlayMusic` clears it in **2 frames (33 ms)** | the same fade with no stop clears the byte by itself after **127 frames (2.12 s)**; with no fade at all it reads 0 throughout |
| GAP12-A2-17b, poke storm "costs no sound" | **FALSE** | storm bracket **38.17 ms** against a derived **10.90 ms** ring lead = **3.50x**, and **2.29x** the 16.65 ms Timer-A period | the per-frame `VInt_*` bracket on the same flag in the same run: 895 pairs, median **0.918 ms**, max 1.053 ms |

## What is new to each booking

**A2-9b (i) holds, and the seat's mechanism is the right one.** `Snd_LoadSong` step 1 writes
`$2B = $00` and clears `SND_STAT_DAC_ACTIVE` unconditionally (confirmed by the no-drum control:
a load with nothing streaming still writes `$2B <- $00` once), the streaming loop never reads
that flag, and it runs on. With Moving Trucks loaded — a song with no `$E2` of its own — the
loop emits 1067 further `$2A` bytes with the DAC off and no re-enable inside 400 ms.

**A2-9b (ii) was not reproducible with any song this ROM ships, and the reason is structural.**
The `.stop` re-key is real: the no-load control shows it (`$28 <- $F6`, once, in `.stop`'s own
0.1 ms epilogue). It did not fire after any load because

* Moving Trucks and HCZ2 both load with `SND_FM6_ADAPTIVE = 0`, which gates the whole adaptive
  block — including the re-key — off; and
* the only FM6-**adaptive** song in the ROM is the drum-test song itself, so the only way to
  reach that branch at all is to load it over its own running drum — and there `.seq_clr`'s
  `ldir` has just wiped `SCF_KEYED`, so `.stop` takes `.stop_repark` instead.

That is a race the loader's own wipe wins, not a structural impossibility. In the self-reload
the new song's first key-on reached `$28` at +14.46 ms and `.stop` had run by then; a song whose
first sequencer frame keyed FM6 *before* the dying sample drained would land on the other side.

**A2-9b, a third behaviour nobody had booked.** When the new song has DAC drums of its own, its
first `Snd_StartSample` re-primes the streaming registers **over** the in-flight sample —
`SND_ROM_LEN` jumps UP (882 -> 1406 for HCZ2, 714 -> 1333 for the drum song reloaded) — so the
old drum's remainder is **abandoned**, not drained to `.stop`. 139 and 176 bytes of it go out
silent first. The header's "keeps consuming the ring and FILLing from ROM until the sample's own
`.stop`" describes only the no-new-drum case.

**A2-11b is real and it is bounded.** "Forever" is too strong: the next `Sound_PlayMusic` clears
the byte in 33 ms, because the load re-opens `Sequencer_Frame`'s `SND_SEQ_ACTIVE` gate and
`Fade_Ramp` finds the ramp at target. The stale window is *from the stop until the next song*.
It is not a live bug: `Sound_FadeOut`, `Sound_FadeIn`, `Sound_FadeCmd`, `Sound_FadeOutStop`,
`Sound_FadeOutPause` and `Sound_IsFading` have **zero** call sites across `engine/` and `games/`
— which is also why the leg needed a ROM at all.

**A2-17b: the ring-lead half of the estimate was exactly right, the storm half was 31% high, and
the conclusion stands.** 200 bytes / (3579545 / 195 = 18356 Hz) = **10.90 ms**; the seat's
"~10.9 ms" is derivable and correct. The storm is **38.17 ms**, not ~50. Since 38.17 > 10.90,
everything the estimate concluded survives: a sample streaming across the bracket drains 700 ring
bytes against a 200-byte lead, runs dry after 10.90 ms, and the R1 underrun guard then pins RD to
WR — a held DC level for the remaining **27.27 ms**. Separately the tick's DMA defer coalesces
`floor(38.17 / 16.65) = 2` Timer-A overflows, i.e. drops 2 sequencer frames per storm.

**What "costs no sound" would have to mean to be true.** Only this: *no sound is playing across
the storm*. The comment is a claim about the mechanism, and as a claim about the mechanism it is
false — the bracket is 3.5 ring leads long and the driver has no absorber past one.

Whether the weaker reading is true **in the canonical shapes was NOT established by this run**, and
is stated that way rather than assumed: those shapes cannot play music by design, but a DAC sample
from an SFX or `Sound_PlaySample` is reachable in principle, and the canonical shape carries no
`Sound_Dbg_Mirror`, so `SND_STAT_DAC_ACTIVE` cannot be read there at all. What was measured is the
bracket, not the absence of a stream across it.

## Instruments, and the two that do not exist

* **YM write stream.** `crates/oracle-core/src/z80/bus.rs` taps every **Z80-side** `$4000-$4003`
  and `$7F11` write into the same `BusEvent` sink `Watchpoints` consumes, at the raw Z80 address.
  So a v1 `bus`-space write watch over `$4000-$4003` records the driver's YM traffic with a
  per-hit mclk. This is the instrument the booking asked for. Live-check on a real run:
  `seen=852228 matched=662 dropped=0 holes=0` over 30 idle frames.
* **Z80 RAM.** `read_memory` and `emulator/read` both REFUSE `$A00000-$A0FFFF` ("only cartridge
  space ... and work RAM ... are readable in this slice") and `write_memory` refuses it too
  ("only the work-RAM window is writable"). The way in is that the **config-A profile places AND
  CALLS** `Sound_DebugMirror` (`engine/debug/sound_debug.emp`), which snapshots Z80 `$1F00..` and
  `$18F0..` into `Sound_Dbg_Mirror` at `$FFB578` in 68k RAM every VBlank. Cost, stated: it holds
  the Z80 bus once per frame, so every config-A number here is from a machine already paying that.
* **No VGM, no audio.** `capabilities.vgm: false`; the six sound methods (`vgm_start`,
  `audio_spectrum`, `get_channel_states`, `set_channel_enabled`, `vgm_status`, `vgm_stop`) are
  catalogued in the contract and **not served**. Nothing here renders a waveform. "Silent" always
  means *the DAC enable bit is off while the loop keeps writing `$2A`*.
* **No Z80 symbols in the listing.** The Z80 driver is assembled into its own blob by
  `emit_sound_blob`; `grep Snd_LoadSong cfga.lst` is empty while `Sound_PlayMusic` is at `$B740`.
  The Z80 half is reachable only through the write stream and the mirror, never by symbol.
* **No Z80 constants in the listing either.** The config-A `.lst` has 802 `EQU` lines and exactly
  **six** beginning `SND_`, all of them 68k mailbox addresses. `SND_DAC_RATE_HZ`, `SND_LOOP_CYC`,
  `Z80_CLOCK_HZ`, `SND_RING_LEAD_TARGET`, `SND_TIMERA_N` and the `SND_STATE_BASE` field offsets
  reach no listing at all, so for those the source file is the authority — `tools/emp_consts.py`.

## Four instrument errors found in these witnesses, all of which read as clean results

1. **Bounding the drum by `SND_STAT_DAC_ACTIVE`** — the exact flag `Snd_LoadSong` clears at the
   load. The bound fired on the loader's own clear and the drum's remainder came out an identical
   **133 bytes in all three targets**. A clean constant across three genuinely different songs was
   the confound telling on itself. The criterion is now `SND_DAC_PHASE == 0`, which only `.stop`
   writes.
2. **Dating `.stop` by any `$2A <- $80` in the window.** `$80` is a legitimate mid-sample silence
   byte, and the search found one ~1,000 bytes early. Only the run's **last** byte is checked now.
3. **Reading `dropped` as "did I lose hits?"** It is a whole-instrument count of drop-oldest
   evictions and rises for hits the reader already consumed, and for other watches. The
   authoritative check is a **gap in the captured `seq` run** — which `Watchpoints`' own doc says
   in as many words. A first version reported 3,182 and 6,226 "dropped" that were entirely an old
   watch left armed across a 300-frame settle.
4. **Trusting `watchpoint_hits`' own `symbol` field for attribution.** Both raisers of
   `SND_DMA_ACTIVE_SLOT` write it from inside a `with z80_stopped` block, so the nearest preceding
   label is that block's spin target: **all 1792 hits** came back as
   `$engine.vblank$asm2$wait_z80` and friends, bucketing the storm with its own control and
   reporting "the storm never ran". Attribution is now a bisect of the PC against top-level
   labels, which separates them 2 / 1790.

Also worth knowing for the next lane: a **512-hit `watchpoint_hits` page overruns the Aether
client's 64 KiB line limit and kills the connection mid-run**. 100 per page is safe, and the
`cursor` is a persistent `seq` watermark that must be carried across polls.

## ROMs

| role | build | crc32 | size |
|---|---|---|---|
| config-A (music-capable), legs 1-2 | `sigil build --aeon . --native --config-a` | `df4539a3` | 847885 |
| config-A + the Leg-2 probe patch | same, after the two added hotkeys | `3e08a50a` | 847931 |
| canonical debug, leg 3 | `DEBUG=1 ./build.sh`, `finished=0` | `9ce1c2ff` (md5 `06e50f02`) | 847533 |

Both crcs are read from this session's own artifacts, not quoted: `df4539a3 len=847885` is what
`sigil` printed on the build, and `9ce1c2ff size=847533` is the `DIGEST-ROM` row this build's own
gate lane printed against `s4.debug.lst`. `df4539a3` matches the value the controller recorded for
this tree at 19:22Z, so the tree had not moved under the parcel; `06e50f02` is the md5 the `0912 s9`
landing recorded as the control for `s4.debug.bin` on untouched `f512e228`, and `9ce1c2ff` is the
crc the previous batch's note recorded for that same ROM — so the canonical debug ROM is unchanged
across both.

## The Leg-2 probe ROM, and why one was needed

Nothing in the ROM starts a fade and the bus cannot poke the mailbox, so `FADE_BUSY` could not be
driven at all without a ROM that makes the call. `tools/fade_busy_stale_witness.py` builds one and
then puts the tree back:

1. verify `games/sonic4/debug/game_debug.emp` byte-identical to `git show HEAD:...` — a dirty file
   is a refusal, never a silent overwrite;
2. apply two hotkeys (DOWN -> `Sound_FadeOut`, LEFT -> `Sound_StopMusic`) and nothing else;
3. `sigil build --native --config-a` to a scratch dir — the canonical ROMs are never touched;
4. restore from the committed baseline, **verify** the restore, in a `finally`.

**The subject is unchanged.** Not one byte of the Z80 driver, `sound_api.emp` or the sequencer
moves; the probe supplies only the call the game does not yet make, which is the booking's own
"No callers today" condition. Leg L0 requires the patched and unpatched CRCs to DIFFER, so a patch
that failed to apply cannot masquerade as "the fade never started".

## Anti-vacuity

Both emulator witnesses carry a `--poison` mode and both fire:

* `song_load_mid_drum_witness.py --poison` aims the YM watch at `$A00000`: `seen=852228
  matched=0`, and L0 goes loud.
* `poke_storm_sound_cost_witness.py --poison` aims the flag watch at `$FF0000`: 3 writes, no
  bracket, L1 finds nothing.

Every leg count is asserted (7, 6, 6). `Unmeasurable` is never reported as a pass.

## What these witnesses are NOT

They are measurement witnesses, not gates, and they are wired into no runner. Two of the three
need an off-canonical ROM, which `build.sh` refuses to produce, so they cannot live in it. They
fail only when they could not ask their question — never on the engine's behaviour, which is the
thing being reported.

## The 19:25Z `pkill -f "sigil.*--native"` window — checked, and clean

The controller reported that another lane ran `pkill -f "sigil.*--native"` at roughly 19:25Z, a
pattern that matches this parcel's `--config-a` invocations. Checked both ways it can bite:

| what | when (UTC) | in the window? | evidence it completed |
|---|---|---|---|
| `DEBUG=1 ./build.sh` | 19:25:23 -> 19:29:21 | **YES, it started inside it** | `finished=0`; the ROM's own `DIGEST-ROM` row reads `crc=9ce1c2ff size=847533`, which is the value the previous batch recorded for this same tree, and its md5 `06e50f02` is the control the `0912 s9` landing recorded for untouched `f512e228` |
| config-A build (legs 1-2) | 19:29:30 -> 19:29:36 | no, it ran after | `finished=0` and `built: config_a native ROM, crc=df4539a3 len=847885` — the controller's own independently measured value for this tree at 19:22Z |
| leg 1 runs | 19:36 -> 19:50 | no | 7/7 legs, every run |
| leg 3 runs | 19:53 -> 19:54 | no | 6/6 legs |
| leg 2 run (incl. both probe builds) | 19:56 -> 19:58 | no | 6/6 legs; `finished`-equivalent `EXIT=0` |

**Not one build in this parcel failed, at any point.** Every `sigil` and `build.sh` invocation
returned 0 on its first attempt, so there is no failure anywhere from which a conclusion could have
been drawn — which is the amendment's sharper hazard (a killed `sigil` looks exactly like a
legitimate refusal). The one "instrument unavailable" conclusion in this parcel — no VGM, no audio
— comes from a LIVE server's handshake and its served-method list, not from a build outcome, and
was re-measured afterwards.

**Cart identity, verified rather than assumed.** The controller's check is `romBytes` against the
file length; this parcel went further and read the WHOLE cart back through the bus:

```
cfga.bin        file len=847885 crc32=df4539a3   server romBytes=847885  readback identical: True
s4.debug.bin    file len=847533 crc32=9ce1c2ff   server romBytes=847533  readback identical: True
```

`s4.debug.bin` had by then been REWRITTEN by a later `tools/landing_build.sh` run and still came
back `9ce1c2ff`, so the leg-3 ROM is reproducible as well as intact. `tools/cart_identity.py` now
carries that check and all three witnesses call it.

## A stale measured table in the instrument seam

`tools/aether_instance.py`'s docstring carries a handshake table measured 2026-08-26, and three of
its rows are now false. Measured here at 20:05Z against
`/home/volence/sonic_hacks/oracle/target/release/oracle-aether` (built 2026-09-12 14:46):

| field | the docstring says | measured today |
|---|---|---|
| `implementation` | ABSENT ("not yet on the wire") | `"oracle-rs"` |
| `serverBuild` | ABSENT | `{source: vcs, id: 781e9e08...+profile=release, dirty: false}` |
| `len(methods)` | 41 | **61** |
| `capabilities.breakpoints` | `false` (present) | **`true`** |
| `capabilities.watchpoints` | not mentioned | `{supported: true, maxWatches: 32, ringCap: 4096, spaces: [bus, vram, cram, vsram]}` |
| `capabilities.vgm` | not mentioned | `false` — and `vgm_start` / `audio_spectrum` are genuinely NOT in the 61 |

Two consequences, both live:

* The docstring states flatly that *"`breakpoint_add` / `wait_for_break` do not exist"* and to use
  `run_to` instead. Both ARE served now, and so is the whole watchpoint surface — which is the
  instrument all three witnesses in this parcel depend on. A lane reading that paragraph would not
  try a watchpoint at all.
* The same docstring says to delete rung 2 of `assert_rust_server` once oracle's release binaries
  carry `implementation`. **They now do.** Deleting it is a code change with its own test
  (`tools/test_aether_instance.py` drives both rungs) and is left for a parcel that owns it; the
  docstring is corrected to say the condition has been met rather than to keep predicting it.

## Open, deliberately not guessed

* Whether a song loaded over a half-completed fade **inherits** the faded-down master volume.
  A2-11b's L3 shows `FADE_BUSY` clearing in 2 frames, which means `MASTER_FADE == FADE_TARGET`
  right after the load, but `SND_MASTER_FADE` is not in the mirror window and this run did not
  read it. The instrument that would settle it is the YM TL (`$4x`) write stream.
* Moving Trucks loads with `SND_FM6_CHAN_PTR = $1B34` — a real FM6 music channel — yet
  `SND_FM6_ADAPTIVE = 0`, and it keys ch6 (`$28 <- $F6`). If a DAC sample ever ends while it is
  playing, `.stop`'s adaptive gate skips, so neither the `$2B <- $00` hand-back nor the FM6 re-key
  happens. Booked as its own row (`GAP12-A2-9d`) rather than folded into 9b, because it is a
  song-flag question and not a loader question.
