# MDSDRV sequence format + toolchain — findings vs Aeon's music format

Research date: 2026-08-07. Read-only. Source tree:
`/home/volence/sonic_hacks/aeon/docs/research/external/mdsdrv/` (superctr, zlib, v0006).

Our side: `engine/sound/seq_opcode_tab.emp`, `engine/sound/sound_sequencer.emp`,
`engine/sound/sound_constants.emp`, `tools/song_packer.py`, `tools/smps_import.py`,
`tools/zyrinx_port.py`, `games/sonic4/data/sound/*.bin`,
`docs/superpowers/specs/2026-06-23-music-expression-engine-design.md`.

Everything under **VERIFIED** was read out of the files or computed by decoding the actual
shipped binaries. **INFERRED** is marked inline.

---

## 0. Executive numbers (VERIFIED — measured, not quoted)

I decoded the five real MDSDRV songs (`data/bgm/*.mds`, RIFF `seq ` chunk) and our two real
songs (`games/sonic4/data/sound/*.bin`) with matching decoders, then simulated one pass of
each track's loop structure to get musical duration.

MDSDRV tick rate = `60 * tempo / gtempo`, `gtempo` = 128 NTSC (`src/mdsdrv.68k:87-92`,
tick catch-up loop `:497-509`). Our tick rate = `60 * (256 - tempo_mod) / 256`
(`song_packer.py` header +2; `sound_sequencer.emp:71-79` accumulator).

| Song | driver | seq bytes | instr/env bytes | tracks | one loop pass | **bytes/sec of music** |
|---|---|---|---|---|---|---|
| sand_light | MDSDRV | 1 505 | 540 | 9 | 56.9 s | **26.5** |
| passport | MDSDRV | 2 882 | 464 | 9 | 120.6 s | **23.9** |
| junkers_high | MDSDRV | 3 738 | 380 | 9 | 187.9 s | **19.9** |
| midnight | MDSDRV | 1 813 | 352 | 10 | 111.9 s | **16.2** |
| idk | MDSDRV | 1 921 | 175 | 9 | 126.0 s | **15.2** |
| HCZ2 | Aeon | 6 511 | 128 | 9 | 52.5 s | **124.0** |
| Moving Trucks | Aeon | 12 465 | 800 | 6 | 157.1 s | **79.3** |

**MDSDRV is 3-8x denser per second of music.** Confounders (state them when quoting this):
the music is different; MDSDRV's jazz arrangements are long-form and highly repetitive;
our two songs are both *machine ports* (S3K SMPS and Batman&Robin/Zyrinx) whose converters
flatten structure. But the mechanisms behind the gap are individually measurable, and I
measured the three biggest below.

**Structural (loop) expansion factor** — raw stream events vs events actually executed in
one pass:

| Song | raw events | expanded events | ratio |
|---|---|---|---|
| midnight (MDSDRV) | 1 155 | 7 008 | **6.07x** |
| junkers_high (MDSDRV) | 2 420 | 9 409 | **3.89x** |
| sand_light (MDSDRV) | 869 | 3 130 | **3.60x** |
| passport (MDSDRV) | 1 821 | 5 289 | **2.90x** |
| idk (MDSDRV) | 1 228 | 3 390 | **2.76x** |
| Moving Trucks (Aeon) | 5 920 | 10 654 | **1.80x** |
| HCZ2 (Aeon) | 6 000 | 6 000 | **1.00x** |

HCZ2 contains **zero** `MEV_REPEAT_START` — `smps_import.py` flattens every S3K loop.
MT gets 1.8x from 103 flat (non-nested) repeats.

---

## 1. VERIFIED format facts — MDSDRV

### 1.1 Opcode space (`doc/mdsseq.md:295-464`, `tools/seqdef.h:31-76`)

```
00..7f          duration byte. Standalone = REST of that length (and latches rest length).
                As the argument of a note/tie = that note's length.
80  rst         rest, reusing the previous rest length
81 [00..7f] tie tie; length optional
82..df [len]    note, number = byte-0x82 (C1 up); length optional
e0  slr         slur/legato — suppress key-off before the next note
e1 dd  ins      instrument (index into the per-song data table)
e2 dd  vol      set volume (dual scale: 80..8f = MML 2 dB steps; 00..7f = FM 0.75 dB steps)
e3 dd  volm     MODIFY volume, signed
e4/e5  trs/trsm set / modify transpose (signed)
e6 dd  dtn      set detune (1/256 semitone — equal-temperament key fraction)
e7 dd  pta      portamento speed
e8 dd  peg      pitch envelope by data-table id (0 = off; bit15 of the ptr = extended format)
e9 dd  pan      panning
ea dd  lfo      FM: PMS/AMS sensitivity;  PSG: noise mode
eb dd  mtab     arm macro table by data-table id
ec dd  flg      drum mode / FM3 special mode
ed rr dd fmcreg per-channel FM register write
ee/ef oo dd     fmtl / fmtlm — set / modify instrument base TL per operator
f0 dd  pcm      PCM instrument;  f1 pcmrate;  f2 pcmmode (2ch@17.5k / 3ch@13k)
f5 ww  jump     relative jump (loop point)
f6 rr dd fmreg  raw YM register write (always applied even under SFX suppression)
f7 dd  dmfinish drum-mode subroutine terminator, sets the note
f8 dd  comm     communication byte — sync game events to the music
f9 dd  tempo    tempo = dd*300/256 BPM
fa     lp       loop start   (4 bytes of stack)
fb dd  lpf      loop finish, count; 0 = infinite
fc dd  lpb      loop BREAK — on the last iteration skip dd bytes
fd ww  lpbl     loop break, 16-bit displacement
fe dd  pat      subroutine call by data-table id (2 bytes of stack)
ff     finish   end / return from subroutine
```

Opcode layout is generated from one C table (`tools/seqdef.h:38-76`), and the assembler
`.inc` (`src/mdsseq.inc`) plus the disassembler `mds2asm.c` are both generated from it —
**one source of truth for the opcode space, three consumers**. `gendef.c:20-32` also
generates the MML duration constants from a single `interval = 96` ticks-per-whole-note.

### 1.2 Duration model (`tools/gendef.c:20-32`, `src/mdsdrv.inc:139-140`)

96 ticks per whole note, 24 per quarter. `l4 equ $17` (23), `t4 equ $18` (24): a **note**
length is one tick short of the grid (the key-off gap is baked into the constant); a **tie**
length is exact. Composer types `l4`, the assembler substitutes the right constant.

The decisive detail:

```
; src/mdsdrv.inc:139-140
t_rest_time		rs.b	1			; length of last rest
t_note_time		rs.b	1			; length of last note or tie
```

**Two independent running-length registers.** Ours has one
(`sound_constants.emp:622  sc_dur_default: u8  // +5 default duration for bare notes`).

### 1.3 Per-song data table (`doc/mdsseq.md:271-284`)

Every song has a `tbase` indirection table of 16-bit offsets. FM voices, PSG envelopes,
pitch envelopes, PCM headers, `pat` subroutines, drum-mode subroutines and macro tables are
**all referenced by a 1-byte id** through it, with the base offset chosen by type
(`sdtop` for global data, `tbase` for song-local code). Instruments/envelopes live in a
**global bank shared across all songs** (`doc/mdsseq.md:140-160`, "inserted into the global
data bank during .MDS to ROM compilation"), and identical blocks are detected by FNV-1a hash
(`tools/mds2asm.c:122-131`, `:540-547`).

### 1.4 Loop machinery (`src/mdsdrv.68k:1480-1560`, stack `mdsdrv.inc:32,168`)

`TSTACK_COUNT equ 8` words = 16 bytes/track. `lp` pushes `[count=$ff, position]` (4 B);
`lpf` initialises the count on first arrival, decrements, jumps back or pops. `pat` pushes
just the return address (2 B). `lpb`/`lpbl` test `t_stack-4(twork,sp)` == 1 — i.e. *the
enclosing loop's remaining count* — and skip forward on the final pass. That is the
first-ending/second-ending idiom, and it is what the MML `/` inside `[...]` compiles to.

Loop usage in the real songs (VERIFIED by decoding): `lp`/`lpf` pairs 33-106 per song,
`lpb` 13-43 per song, `pat` 0-42 per song. Loops carry the compression; subroutines are
secondary.

### 1.5 Tempo (`src/mdsdrv.68k:87-92, 497-509, 703-705`)

Per-track 16-bit accumulator `w_tempo` += each frame, compared against the global
`w_gtempo`; a **`while` loop** fires as many sequence ticks per frame as the accumulator
allows. `gtempo` is 128 on NTSC and 107 on PAL, so PAL/NTSC tempo compensation is one
constant. Song tempo and global tempo are both settable at runtime
(`mds_command 0x05/0x0f`, `doc/api.md`).

### 1.6 Expression data formats

- **FM voice** (`doc/mdsseq.md:505-526`): 30 bytes — 7 groups of 4 operator bytes in
  register order (DT/MUL, KS/AR, AM/DR, SR, SL/RR, SSG-EG, TL), then FB/ALG, then a
  **per-instrument transpose byte** (0..31, ×2) that shifts which fnum region the scale
  uses, trading pitch accuracy for detune resolution and less key-scaling.
- **PSG envelope** (`doc/mdsseq.md:528-540`): `xy` = "set volume y, hold x frames" — a
  **run-length byte**; plus `00` stop, `01` sustain-until-key-off, `02 nn` jump.
- **Pitch envelope** (`:544-561`): 4-byte nodes `{init_mod:sw, delta:sb, length:ub}` +
  `7fxx` jump. Extended form (`:562-581`) is 6 bytes with a 16-bit delta and an explicit
  per-node "next node" pointer (arbitrary graphs, not just a tail jump).
- **Macro table** (`:583-633`): 2-byte `{cmd, arg}` nodes. Targets: detune, transpose,
  portamento, volume, per-operator TL — each with both a *set* ($1x/$3x) and an *add*
  ($5x/$7x) form. Control: `$80` reset/jump, `$81` wait, `$82` retrigger+wait, `$83` carry
  (don't reset on key-on), `$84/$85/$86` loop count / loop-break / loop-finish, `$87` pan,
  `$88` LFO sens, `$89` PSG noise, `$8A/$8B` detune-with-carry-into-transpose.
  **`$C0-$FF` writes `arg` to FM register `cmd<<2`** — every per-channel/per-operator
  YM2612 register is a multiple of 4, so arbitrary register automation costs 2 bytes.

### 1.7 Drum mode (`doc/mdsseq.md:465-476`)

`flg 08` turns note numbers into **subroutine ids**. A "note" jumps into a mini-program that
can set pan/patch/TL/whatever, then `dmfinish dd` supplies the actual pitch and returns to
read the duration from the *original* note event. A drum kit becomes 1 byte per hit on any
channel, FM or PSG, with per-drum parameter setup for free.

### 1.8 MML surface (`data/bgm/jazzy_nyc_99.mml`, `data/se/*.mml`)

The MML compiler is `mdslink` from the separate **ctrmml** project (`README.md:44-58`); it
is *not* in this repo (`tools/mds2asm.c` is only the .MDS **dis**assembler). Notation seen
in the real files:

```mml
@1 fm 3 0                        ; FM patch: algorithm 3, feedback 0, then 4 operator rows
 31 0 19 5 0 23 0 0 0 0          ; ar dr sr rr sl tl ks mul dt ssg   (one row per operator)
@5 psg 15>10:5 / 10>0:20         ; PSG env as RAMPS: 15->10 over 5 frames, then 10->0 over 20
@M1 | -36 -24 -12 0              ; macro table = arpeggio list
*30 v12@30o1c                    ; drum-mode instrument #30 = a one-line mini-sequence
A t120                           ; track A: tempo
ABC @3 v6Q7 {p2)/p3/p1)}         ; assign 3 tracks at once; {x/y/z} fans out across the group
ABC L l4. [o4{g/b/>d}{a/>c/e}]4  ; L = loop point; [..]4 = counted loop; {..} = chord fan-out
D l16 [[b^>de^de^/g^]2d^]4       ; NESTED loops; '/' inside a loop = loop break (lpb)
D ... V+20 ... (p1 ... )3        ; relative volume; portamento/pan groupings
F l16 [a^^ab^ab^b^a/ba^^]8       ; '^' = tie, '&' = slur, ':60' = explicit tick count
```

Ergonomics worth naming: (a) `{a/b/c}` writes a chord once and distributes voices across a
*track group* — this is why 3-voice pad writing costs one line; (b) `/` inside `[...]` is
the loop-break, so "play it 4 times, but the last time end differently" is one character;
(c) instruments, PSG envelopes, macro tables and drum kits are declared **inline in the song
file** with domain notation (ramps, arpeggio lists), not as separate binary assets;
(d) `Q7` = gate/quantize, `V+20` = relative volume, `:n` = raw tick length escape hatch.

SFX are written in exactly the same language (`data/se/beep1.mml` is 6 lines) with
`#group se`, so BGM and SFX share one authoring surface and one compiler.

### 1.9 Pipeline (`Makefile`, `README.md:51-96`, `doc/mdsseq.md:61-224`)

`.mml` / `.mds` --`mdslink`--> `mdsseq.bin` + `mdspcm.bin` + `mdsseq.inc` + `mdsseq.h`.
`.MDS` is a RIFF container: `ver `, `seq `, `LIST/dblk` (`glob` data blocks by id, `pcmh`
sample headers), `pcmd` (sample data). Relocation is "patch a 16-bit word at
`tbase + data_id*2` once the ROM address is known" (`doc/mdsseq.md:157-160`) — a tiny,
explicit fixup model. The driver blob is fully position-independent
(`README.md:32-33`), the Z80 half is ZX0-compressed in ROM (`Makefile:36-40`, salvador),
and the data carries a semantic version (`sdver`, `MDSDRV_MIN_VER equ $0003`,
`src/mdsdrv.inc:28-29`) so a stale blob is rejected rather than mis-parsed.

---

## 2. VERIFIED format facts — ours (for the comparison)

- Opcode space: `engine/sound/seq_opcode_tab.emp:43-78` (32-entry `$E0..$FF` jump table,
  6 slots reserved) + range dispatch `$00-$7F` SetDur / `$80` Rest / `$81-$DF` Note
  (`sound_constants.emp:253-330`).
- Single running duration: `sound_constants.emp:622 sc_dur_default`, reloaded at
  `sound_sequencer.emp:982-983, 996-997, 1358-1359`; set by the bare `$00-$7F` byte at
  `:1007`.
- Repeats: `Seq_Op_RepeatStart` / `Seq_Op_RepeatEnd`, `sound_sequencer.emp:1501-1548`.
  ONE `sc_repeat_ptr` + `sc_repeat_count` per channel → **nesting is illegal**
  (`song_packer.py:853-859`; design spec "Format validity rules" §(c)1).
- No subroutine opcode; no tie; no slur; no transpose opcode; no song->game cue byte.
  (`sc_transpose` exists at `sound_constants.emp:637` and IS applied in
  `sound_fm.emp:778-790, 825, 944-950`, but the only writer is `Seq_Op_SpinRev`,
  `sound_sequencer.emp:1213-1222`.)
- Song header: `flags, tempo, tempo_mod, channel_count, pitchtable_ptr, {route, cmd_ptr,
  mod_ptr} * n, patch_table_ptr` — all 16-bit BE blob-relative
  (`song_packer.py:979-1045`; mirror `sound_constants.emp:942-968`). **No version field.**
- Macro (slot[1]) grammar: `TAG_MAC_NEXT $E0`, `TAG_MAC_REG $E1 part reg val`,
  `TAG_MAC_LOOP $E2 hi lo`, `TAG_MAC_END $E3` (`sound_constants.emp:482-501`).
- Authoring: **a Python DSL** (`song_packer.py` `SongDesc`/`ChannelDesc`/`Event`), driven by
  per-song build scripts. Seraph (our DAW) has **no Aeon/MEMRA export profile** — the S0/S1
  packages are banked but unexecuted (`seraph/docs/superpowers/2026-07-03-seraph-banking-queue.md`);
  Seraph today emits SMPS `.asm` + VGM only, with 25-byte SMPS voices, and its model has no
  representation for repeats, loop points, macros, envelopes, portamento or register writes.

---

## 3. Ranked candidates

Effort = engine work + packer work + re-pack of existing songs. Any item marked
**format-semantic** forces a re-pack of `song_movingtrucks.bin` / `song_hcz2.bin` and a
byte-parity re-pin, so batch them into one format revision.

---

### #1 — Two running-duration registers + bare-duration-byte-as-rest — **[WORTH TAKING]**

**MDSDRV:** `t_rest_time` / `t_note_time` (`src/mdsdrv.inc:139-140`); a standalone
`00..7f` byte is *itself* a rest of that length (`doc/mdsseq.md:301-302`), so a rest is
**always 1 byte** regardless of length change.

**Ours:** one `sc_dur_default` (`sound_constants.emp:622`), and `$00-$7F` is a zero-tick
SetDur so a length-changing rest costs 2 bytes.

**Measured on our real HCZ2 blob** (decoder + re-encode, both written for this task):

| encoding of note/rest/duration bytes | bytes |
|---|---|
| ours today | 5 576 |
| split note/rest registers only | 4 524 (−1 052, **−16.2 % of the whole 6 511 B blob**) |
| MDSDRV semantics (split registers + bare-byte rest) | **3 871 (−1 705, −26.2 % of the blob)** |

(HCZ2 has 1 796 notes / 1 347 rests; 1 267 of its 2 433 SetDurs sit immediately before a
Rest.) Moving Trucks gains 0 from this — it has no Rest events at all.

**Effort:** small. Engine: one extra channel byte (`sc_rest_dur`) and a branch in the
Rest/Note paths (`sound_sequencer.emp:982-997`), plus making the `$00-$7F` range-dispatch
arm a pending length that the *next* Note consumes while a *standalone* one rests. Packer:
change `st.cur_dur` into two registers. **Risk:** format-semantic — every existing blob
re-packs, and `$00-$7F` changes from zero-tick to time-advancing, which touches the
"time-advancing event set" in the validity rules (§(a)4). Do it once, early.

---

### #2 — Nested counted loops + loop-break (`lp`/`lpf`/`lpb`/`lpbl`) — **[WORTH TAKING]**

**MDSDRV:** `doc/mdsseq.md:443-457`; `src/mdsdrv.68k:1480-1537`; per-track stack
`TSTACK_COUNT equ 8` words (`mdsdrv.inc:32`), 4 bytes per loop level. `lpb` tests the
*enclosing* loop's count (`:1511 cmpi.b #1,t_stack-4(twork,@sp)`) and skips forward on the
last pass — first/second endings for 2 bytes.

**Ours:** single-level, no break (`sound_sequencer.emp:1501-1548`; nesting rejected at
`song_packer.py:853-859`).

**Why it matters (measured):** MDSDRV songs execute 2.8-6.1x more events than they store;
MT 1.8x, HCZ2 1.0x. Their songs use 33-106 `lp/lpf` pairs and 13-43 `lpb` each. Almost the
entire per-second density gap traces here.

**Effort:** medium. Needs a per-channel loop stack in Z80 channel RAM — 2 levels = +8 B/ch
× 11 channels = 88 B; 3 levels = 132 B. That is the real cost and it lands against the
already-tight Z80 RAM/code budget (memory: headroom ~316 B after the wave-4 reclaim).
An alternative that costs 0 RAM: keep one hardware level and let the *packer* express
nesting by emitting a subroutine (#3) for the inner body. **Risk:** medium (new stack
discipline; a mis-encoded blob hangs — we are trust-the-packer).

**Sub-item, cheap on its own:** `lpb` (loop break) even at single-level depth is a 2-byte
opcode that removes the duplicated "last time round" tail. Worth taking independently.

---

### #3 — `pat` subroutines — **[WORTH TAKING]**

**MDSDRV:** `doc/mdsseq.md:458-460`; `src/mdsdrv.68k:1538-1560`; 2 bytes of stack, 1-byte
operand (id through the per-song data table), `finish` doubles as `return`. Used 42x in
`passport`, 6x in `junkers_high`, 0 elsewhere — real but secondary to loops.

**Ours:** none.

**Effort:** small-medium (a 2-byte return slot per channel, or reuse of the loop stack from
#2). **Risk:** low. Big payoff for hand-authored music and for a future Seraph exporter that
can hash-dedupe identical bars across tracks — note MDSDRV's `pat` ids are *shared across
tracks*, which is where most of the win is (`data/mdsseq.68k:305-336` shows one `@PAT_2`
called ~50 times from two different tracks).

---

### #4 — Reference pitch-envelopes / repeated payloads by 1-byte id — **[WORTH TAKING]**

**MDSDRV:** every instrument, envelope, macro table and subroutine is a **1-byte id** into
the per-song `tbase` table (`doc/mdsseq.md:271-284`), and the blocks themselves live in a
**global, hash-deduped bank** (`:140-160`; `mds2asm.c:122-131,540-547`).

**Ours:** `MEV_PITCHENV $E8` carries its point list **inline, every time**
(`song_packer.py:656,674-683`).

**Measured on Moving Trucks:** 1 824 `PitchEnv` events, **only 29 distinct payloads**,
5 472 bytes. Referencing them by id would cost 1 824x2 + 29x2 = 3 706 B → **saves 1 766 B
(14 % of the 12 465 B blob)**. Similarly `OpBias`: 658 events, 11 distinct payloads,
1 974 B.

Related, and bigger: **all 1 824 of MT's PitchEnv payloads are `count=1`** — i.e. they are
single notes encoded as `$E8 01 idx` (3 bytes) because MT uses a 132-entry custom pitch
table and our `Note` opcode only spans 95 pitches (`$81-$DF`). That is **3 648 bytes (29 %
of MT) spent purely on the note-range shortfall.** MDSDRV solves the same problem with
`trs` transpose + a per-instrument transpose byte rather than a wider note opcode.
See #5 and #10.

**Effort:** small (packer-side dedupe + a table; engine reads one indirection).
**Risk:** low. **Highest measured single win on MT.**

---

### #5 — `trs` / `trsm` transpose opcodes — **[WORTH TAKING — nearly free]**

**MDSDRV:** `doc/mdsseq.md:341-345`, set and modify, signed, 2 bytes each. Used 4-20x per
song. Combined with the per-instrument transpose byte this is how MDSDRV keeps notes inside
a 94-value opcode range.

**Ours:** `sc_transpose` **already exists and is already applied** at
`sound_fm.emp:778-790, 825, 944-950` — but nothing writes it except `Seq_Op_SpinRev`
(`sound_sequencer.emp:1213-1222`). Two opcodes on reserved slots ($FA-$FE are free) and a
two-instruction handler each.

**Effort:** trivial. **Risk:** trivial (verify PSG honours `sc_transpose` too — I only
verified the FM path). Directly relieves #4's note-range problem for future songs.

---

### #6 — `volm` relative volume — **[WORTH TAKING — nearly free]**

**MDSDRV:** `e3 dd(sb)` (`doc/mdsseq.md:338-340`). Used **45-69 times per song** in
`midnight`/`sand_light`/`passport` — the main crescendo/accent tool, and the reason
`data/mdsseq.68k:339` can express a swell as `volm,8, tie, volm,-8`.

**Ours:** absolute `Vol $E0` only (`song_packer.py:185-187`).

**Effort:** trivial (one opcode, `add a,(ix+sc_vol)` + clamp + the existing set-vol hook).
**Risk:** trivial. Note MDSDRV deliberately does **no** overflow checking; we should clamp.

---

### #7 — `slr` slur/legato and `tie` — **[WORTH TAKING]**

**MDSDRV:** `e0 slr` (1 byte) suppresses the key-off before the next note
(`doc/mdsseq.md:318-319`); `81 [len] tie` extends without retrigger (`:307-310`).

**Ours:** neither. `MEV_NOTEFILL $ED` (`sound_sequencer.emp:1065-1072`) sets an *early*
key-off (gate shortening) — the opposite direction; `0 = legato/off` disables the early
key-off but does not suppress the re-attack. `smps_import.py:670-676` handles
`smpsNoAttack` by merging **same-pitch** notes and records an **"accepted v1 fidelity
gap"** for the different-pitch case — that gap is exactly what `slr` closes.

**Effort:** small (a channel flag consumed by the note-on path to skip the key-off/re-key).
**Risk:** low. Also a byte win: a tie is 1-2 bytes vs re-emitting a note.

---

### #8 — `comm` song-to-game cue byte — **[WORTH TAKING]**

**MDSDRV:** `f8 dd comm` (`doc/mdsseq.md:436-438`), read back with `mds_command 0x0e`
(`doc/api.md`). Sync lighting/cutscene/boss beats to the music with 2 bytes.

**Ours:** nothing in the stream. `SND_REQ_*` (`sound_constants.emp:42-43`) is 68k->driver
only. (INFERRED that no reverse channel exists — I grepped for `comm`/cue and found only the
request block; there *is* a driver->68k status area, so the transport may already exist.)

**Effort:** trivial (write a byte into the shared Z80 RAM mailbox the 68k already polls).
**Risk:** trivial. Our design spec §2 deliberately deferred "echo-style live event
injection" *into* the driver; this is the cheap opposite direction and is not covered.

---

### #9 — PSG envelope run-length byte (`xy` = volume y for x frames) — **[WORTH TAKING]**

**MDSDRV:** `doc/mdsseq.md:538-539` — one byte carries both value and dwell (1-15 frames),
plus `01` sustain-until-key-off and `02 nn` jump.

**Ours:** `PsgVolEnv_*` (`engine/sound/sound_tables_z80.emp:76-110`) is **one entry per
frame** with `$80` loop / `$81` sustain / `$83` rest controls, and the design spec §3.3
generalises exactly that (per-frame) shape.

Slow envelopes are where this bites: MDSDRV's own sample `@1 psg 15:2 8:3 0`
(`data/se/beep1.mml:5`) is 3 bytes for a 5-frame envelope, and
`@1 psg 15 14>8:24 7>0:12` (`data/se/noise1.mml:5`) is a 37-frame envelope written as
ramps. Our equivalents are one byte per frame.

**Effort:** small-medium (env renderer gains a dwell counter; the id->ptr map is unchanged).
**Risk:** medium-ish — it changes the shared envelope grammar that our spec §3.3 wants to
use for *all* macro targets, so decide it at spec level, not ad hoc. Alternatively adopt
only the *authoring* notation (ramps) and keep the expanded per-frame runtime format.

---

### #10 — Per-instrument transpose byte in the FM voice — **[WORTH TAKING — free]**

**MDSDRV:** `doc/mdsseq.md:519-526` — voice byte +29, values 0..31 (×2), suggested default
24 (`$30`). Shifts which fnum region the whole scale sits in: lower value = lower fnums =
finer detune resolution and less key-scaling, at the cost of pitch accuracy. Visible in
every voice in `data/mdsseq.68k:43` (`dc.b $3a,$30 ;fb/alg,transpose`).

**Ours:** `FmPatch` is 32 bytes with `fp_reserved[2]` (`sound_constants.emp:472-487`) — the
byte is already there.

**Effort:** trivial (fold into the existing transpose clamp at `sound_fm.emp:778-790`).
**Risk:** trivial. Pairs with #5 to fix MT's note-range problem structurally.

---

### #11 — Multi-tick-per-frame tempo catch-up — **[WORTH TAKING]**

**MDSDRV:** `src/mdsdrv.68k:504-509` is a `while (counter >= gtempo) { counter -= gtempo;
tick(); }` — the tick rate is unbounded above the frame rate, so fine duration grids
(96/whole) work at any BPM.

**Ours:** `sc_tempo_accum -= 16` / reload (`sound_sequencer.emp:71-79`), rate
`(256-mod)/256` — **hard-capped at 1 tick per frame**. HCZ2 runs at 51.3 ticks/s; the ceiling
is 60. Fast music on a fine grid is unreachable.

**Effort:** small (wrap the tick in a loop). **Risk:** low but real — a multi-tick frame
runs several note-ons in one frame, so the worst-case `Sequencer_Frame` cost rises against
the DAC ring lead. Needs the profiler check the design spec §12 already prescribes.

**Sub-item [REJECT]:** their PAL `gtempo` = 107 compensation — we have no PAL path
(PAL-delete parcel, engine-debts era).

---

### #12 — Drum mode — **[WORTH TAKING]**

**MDSDRV:** `doc/mdsseq.md:390-396, 465-476` (`flg 08`) + `f7 dmfinish`. Note numbers become
subroutine ids; the subroutine sets pan/patch/TL, `dmfinish` supplies the pitch and returns
to read the duration from the original event. `data/bgm/jazzy_nyc_99.mml:33-55` shows a
whole FM kit and a whole PSG hi-hat kit declared as `*30 v12@30o1c` one-liners.

**Ours:** DAC-route `Dac $E2` samples only; an FM or PSG drum track has to inline
`Patch`/`Pan`/`OpBias` before every hit — which is a visible chunk of MT's `OpBias` 658 /
`Patch` 653 / `Pan` 381 events (≈ 3.9 KB combined).

**Effort:** medium (rides on #3's subroutine mechanism + a channel flag).
**Risk:** low. Strong candidate *after* #3.

---

### #13 — Macro `$C0-$FF` = write arg to FM register `cmd<<2` — **[WORTH TAKING — small]**

**MDSDRV:** `doc/mdsseq.md:628-629`. Every per-channel/per-operator YM2612 register is a
multiple of 4, so arbitrary register automation is **2 bytes per node**.

**Ours:** `TAG_MAC_REG $E1 part reg val` = **4 bytes** (`sound_constants.emp:482-501`).

**Effort:** trivial (a second tag, or fold into the tag range). **Risk:** trivial. Also
worth stealing: MDSDRV's macro tables have their own `$84/$85/$86` **loop count / break /
finish** (`src/mdsdrv.68k:1740-1765`) — ours only has an unconditional `TAG_MAC_LOOP`.

---

### #14 — Extended pitch-envelope node with an explicit "next node" pointer — **[WORTH TAKING — small]**

**MDSDRV:** `doc/mdsseq.md:562-581` — 6-byte node `{init:sw, delta:sw, length:ub,
next:ub}`. Arbitrary graphs (attack->sustain-loop->decay) instead of a tail jump, and a
16-bit delta for fine slides.

**Ours:** design spec §3.3 gives loop/hold/release/end control codes — expressive enough for
ADSR-shaped bodies, but the *per-node* next-pointer is strictly more general and costs one
byte. Marginal; list it as a design input, not a must.

---

### #15 — Global, hash-deduped instrument/envelope bank across songs — **[WORTH TAKING — pipeline]**

**MDSDRV:** data blocks are global with per-block ids and a single link-time fixup
(`doc/mdsseq.md:140-160`); identical blocks are detected by FNV-1a
(`tools/mds2asm.c:122-131, 540-547`).

**Ours:** patch banks are **per song** — `movingtrucks_patches.bin` 800 B (25 voices),
`hcz2_patches.bin` 128 B (4 voices), plus 0-32 B per SFX blob. Duplication across songs is
unmeasured today but structurally guaranteed once a real soundtrack exists.

**Effort:** small (do it in `sigil emit_sound_blob` / `song_packer`; the `Patch $E1` operand
is already a 1-byte id). **Risk:** low. Do it before the soundtrack grows, not after.

---

### #16 — MML-style text authoring surface — **[WORTH TAKING — tooling]**

**MDSDRV/ctrmml:** see §1.8. Track-group assignment + `{a/b/c}` chord fan-out + `[...]n`
with `/` break + inline `@n fm/psg/pcm` declarations + `*n` drum definitions + `@Mn |` macro
lists. A 130-line text file is a complete multi-track arrangement
(`data/bgm/jazzy_nyc_99.mml`); a 6-line file is a complete SFX (`data/se/beep1.mml`).

**Ours:** a Python DSL (`song_packer.py` `SongDesc`) where a 4-bar loop is ~10 lines of
`Note(C4), Note(E4), ...` (`games/sonic4/data/sound/song_drumtest.py:79-119`). Seraph has no
Aeon exporter at all.

**Verdict:** take the *notation ideas*, not the language. Specifically: (a) chord fan-out
across a channel group and (b) `/` loop-break inside a repeat are the two constructs that
change how much a composer types, and they are pure front-end sugar over #2/#3.
**Effort:** medium (a new front end, or Seraph S1). **Risk:** none to the engine.

---

### #17 — Data version field in the song header — **[WORTH TAKING — trivial]**

**MDSDRV:** `sdver` in the sound-data header + `MDSDRV_MIN_VER equ $0003`
(`doc/mdsseq.md:233-236`, `src/mdsdrv.inc:28-29`) — a stale blob is rejected, not
mis-parsed.

**Ours:** the song header (`song_packer.py:979-1045`) has no version. We are
trust-the-packer with **no runtime defence** — a stale blob "hangs or corrupts the driver,
it does not error" (our own spec, Format validity rules preamble). One byte in the header +
one compare in the loader converts a hang into a diagnosable stop.

**Effort:** trivial. **Risk:** trivial. Fold into the same format revision as #1.

---

### #18 — 2/3-channel PCM mixing modes selectable from the stream — **[WORTH TAKING — large, out of band]**

**MDSDRV:** `f1 pcmrate` / `f2 pcmmode` (`doc/mdsseq.md:412-418`), 2ch@17.5 kHz or
3ch@13.3 kHz with per-channel volume, 8 sample rates independent of the mix rate
(`README.md:13-18`).

**Ours:** single DAC route, one sample at a time (`Dac $E2`). Our own reference note already
flags "polyphonic PCM is the real gap" vs MegaPCM-2.

**Verdict:** real and significant, but it is a Z80 DAC-engine project, not a sequence-format
change. Flag it; don't fold it into a format revision.

---

## 4. [ALREADY HAVE] / [ALREADY SPECIFIED] — do not propose these

| MDSDRV feature | ours |
|---|---|
| Note = 1 byte when duration unchanged | **[ALREADY HAVE]** — `$81-$DF` + running `sc_dur_default` (`sound_constants.emp:622`). Byte-identical in the common case; ours only loses on rests (#1). |
| Raw FM register write from the stream (`f6 fmreg`, `ed fmcreg`) | **[ALREADY HAVE]** — `MEV_REGWRITE $F8` (`seq_opcode_tab.emp:70`), with a stronger `$2A`/`$24-$27` guard than theirs. |
| Per-operator TL set/modify (`ee/ef fmtl/fmtlm`) | **[ALREADY HAVE]** — `MEV_OPBIAS $E9` (signed per-op TL bias, `seq_opcode_tab.emp:53`). Theirs has a *modify* form; ours is set-only — a 2-line addition if wanted. |
| Portamento (`e7 pta`) | **[ALREADY HAVE]** — `MEV_PORTA $F5` (`seq_opcode_tab.emp:65`), landed 07-08. |
| Detune (`e6 dtn`) | **[ALREADY HAVE]** — `MEV_DETUNE $F6`. MDSDRV's is a true 1/256-semitone key fraction (`t_dtn`, README:29-30); ours is a signed fnum addend (design spec §4.1). Semantically coarser, functionally equivalent for chorus/unison. |
| Pan (`e9`), LFO sens (`ea`), PSG noise mode (`ea` PSG) | **[ALREADY HAVE]** — `MEV_PAN $E4`, `MEV_LFO $F4`, `MEV_PSGNOISE $F2`. |
| Macro tables (`eb mtab`) | **[ALREADY HAVE]** — `MEV_MACRO $F9` + slot[1] `MacroTick` (design spec §3.2-3.3; `sound_sequencer.emp:1087-1104`). Deltas in #13. |
| PSG volume envelopes, FM TL envelopes | **[ALREADY HAVE]** — `MEV_PSGENV $EB` / `MEV_FMENV $F7`. |
| Loop point / infinite loop (`f5 jump`) | **[ALREADY HAVE]** — `MEV_LOOP_POINT $EE` / `MEV_JUMP $EF`. |
| Song volume + runtime tempo + fade in/out | **[ALREADY SPECIFIED — not yet built]** — design spec §7 T4 (master fade state machine + global tempo scalar + mailbox triggers). MDSDRV's fade-rate lookup table (`src/mdsdrv.68k:302-309`) and fade-in-on-request (`:668-685`) are worth copying as *implementation* detail when T4 lands. |
| Pitch envelopes (`e8 peg`) | **[ALREADY HAVE]** in kind — `MEV_PITCHENV $E8`. Ours is an absolute-index arpeggio list; theirs is a slide/ramp node list. Different tools; ours + `MEV_PORTA` + `MEV_MODSET` cover the same ground. The *by-id referencing* is the takeaway (#4), not the node format. |
| FM3 special mode (`ec flg 8x`) | **[REJECT]** — explicitly out of scope in our design spec §2 ("complicates FM3 SFX voice arbitration; CSM contends with our ~59 Hz Timer-A"). Reachable via `MEV_REGWRITE` if ever needed. |
| PSG-noise-uses-PSG3-frequency mode | **[ALREADY HAVE]** — `MEV_PSGNOISE $F2` ctrl `$E0..$EF`. Their doc's SFX/BGM channel-clash precautions (`doc/mdsseq.md:484-503`) are worth reading against our SFX arbiter, but that is a behaviour audit, not a format change. |
| ZX0-compressed Z80 blob in ROM | **[ALREADY HAVE]** — ZX0 is our act-art codec; the Z80 driver is resident by necessity (banked in-frame code is unsound, design spec amendment §9.3). **[REJECT]** for the driver. |
| Position-independent driver blob | **[REJECT — different model]** — we build one ROM from one source tree; PIC buys us nothing. |

---

## 5. Suggested batching

One **format revision v1** containing the format-semantic items, packed and re-pinned once:

1. #1 duration encoding (−26 % on HCZ2, measured)
2. #4 id-referenced PitchEnv payloads (−14 % on MT, measured)
3. #5 transpose opcodes + #10 per-instrument transpose (fixes MT's note-range tax
   structurally: 3 648 B / 29 % of MT is the shortfall)
4. #6 `volm`, #7 `slr`/tie, #8 `comm`, #17 version byte — all trivial, all opcode-space
   additions on the six free slots ($FA-$FE) plus the reserved $F1

Then a **structure phase**: #2 nested loops / #3 subroutines / #12 drum mode, which need a
per-channel stack and are the only items with a real RAM cost. Do #3 first if RAM is tight —
subroutines give the packer a way to express nesting with 2 bytes of state instead of 4.

Then **pipeline**: #15 global patch dedupe, #16 authoring notation (feeds Seraph S1, which
is banked but unstarted).

---

## 6. Method notes / reproducibility

- MDSDRV song sizes: parsed the RIFF chunks of `data/bgm/*.mds` (`seq ` = sequence bytes,
  `LIST/dblk` `glob` = instrument/envelope bytes, `pcmd` = samples, excluded).
- Opcode histograms and expansion counts: decoders written for this task from
  `tools/seqdef.h` (MDSDRV) and `tools/song_packer.py` opcode table (ours); loop simulation
  honours `lp/lpf/lpb/lpbl/pat/finish` and `RepeatStart/RepeatEnd`, one pass to
  `jump`/`finish`.
- Musical duration: sum of tick-advancing lengths on the longest track, divided by the
  driver's ticks/second.
- Duration re-encoding experiment: replayed HCZ2's decoded event list under MDSDRV
  duration semantics and counted bytes.
- All numbers here are from the committed binaries; nothing was rebuilt and nothing outside
  this scratchpad was modified. No emulator was used.
