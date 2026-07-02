# Z80 RAM Memory Map — Sound Driver

**Date:** 2026-06-16 · **Rewritten:** 2026-07-02 (sound performance & budget phase, Task A.3 repack)
**Status:** LIVE — this rewrite supersedes the stale Phase-1 map (and its two staleness banners) in full.
The authoritative *values* remain `sound_constants.asm` (self-asserting at build time); this doc is the
design record of the layout, its invariants, and which build assert guards which seam. If this doc and
`sound_constants.asm` disagree, the constants file is right and this doc has a bug.
**Parent spec:** `docs/superpowers/specs/2026-06-16-sound-driver-design.md`
**History:** the original Phase-1 research/layout (reference-driver survey, `$1600` state block, spare-page
budget) is in git history of this file; it was fully superseded by the A.3 repack.

## 0. Headroom history (resident-code budget)

The resident Z80 code blob is the binding sound constraint. Free-bytes lineage
(`SND_STATE_BASE − Z80_SOUND_SIZE`, the build's "Z80 sound budget" message):

| Date | Free | Event |
|---|---|---|
| 2026-06-24 | ~2 B | pre music-expr Task 0 |
| 2026-06-24 | ~1016 B | Task 0: engine lookup tables banked into the song bank |
| 2026-06-27 | 216 B | music-expr Phases 1/3 spent the recovery |
| 2026-06-28 | ~138 B | `SfxBlobWinTab` banked, Phase-2 features landed |
| 2026-07-01 | 10 B | music-expr Phase 2 complete + quality-review fix pass |
| 2026-07-02 | 280 B | budget A.1 (copy-path song buffer deleted) + A.2 (`DacSampleTable`/`SeqOpcodeTable` banked) |
| **2026-07-02** | **792 B** | **A.3: ceiling raised `$16F0` → `$18F0` (+512) by this repack; `Z80_SOUND_SIZE` = `$15D8`** |

Recovery rule standing since the banked-code crash investigation: **only DATA tables may be banked
into the `$8000` window; ALL in-frame CODE must stay resident** (banked code fetches corrupt under
68k bus contention).

## 1. The map (A.3 repack, 2026-07-02)

Z80 addresses; the 68k sees each byte at `$A00000 + addr`. "Derivation" says how the base is
computed — *pinned* bases are deliberate anchors, everything else chains from its neighbor and
auto-tracks growth.

| Z80 range | Size | Region | Constant / derivation | Owner |
|---|---|---|---|---|
| `$0000–$15D7` | 5592 B live | **Driver code blob** (vectors at `$0000`/`$0038` inside it) | grows up from 0; ceiling = `SND_STATE_BASE` | `z80_sound_driver.asm` + includes |
| `$15D8–$18EF` | 792 B live | Code headroom (shrinks as code grows) | — | — |
| `$18F0–$18FC` | 13 B | **DAC playback state** (`SND_DAC_PHASE`…`SND_FM6_ADAPTIVE`; words at even absolute offsets) | `SND_STATE_BASE = $18F0` (pinned; **is** the code ceiling) | DAC streamer / loader |
| `$18FD–$18FF` | 3 B | slack | — | — |
| `$1900–$19FF` | 256 B | **DAC read-ahead ring** (one full page; `h = SND_RING_PAGE`, wrap by `inc l`) | `SND_RING_BASE = $1900` (pinned, 256-aligned); `SND_RING_PAGE = base>>8 = $19` | DAC streamer |
| `$1A00–$1A07` | 8 B | **Sequencer header** (`SND_SEQ_TEMPO`…`SND_SEQ_TEMPO_BASE`) | `SND_SEQ_BASE = $1A00` (pinned) | sequencer |
| `$1A08–$1C9B` | 660 B | **Music SeqChannels** — `CHROUTE_COUNT` (11) × `SeqChannel_len` (60) | `SND_SEQ_CHANNELS = SND_SEQ_BASE+8`; `SND_SEQ_END = $1C9C` | sequencer |
| `$1C9C–$1CA0` | 5 B | FM voice-writer scratch | `SND_FM_SCRATCH = SND_SEQ_END` | FM writer |
| `$1CA1–$1CA5` | 5 B | Loader scratch: `Snd_SongBase` (2) · `Snd_PitchTabPtr` (2) · `Snd_SpindashRev` (1) | chained | loader / SFX |
| `$1CA6–$1CAB` | 6 B | **Music-load param block** (`SND_MUSIC_PARAM`: bank, ptr, flags, patch ptr) | `= Snd_SpindashRev+1` | 68k writes, Z80 loader reads |
| `$1CAC–$1CCB` | 32 B | Sequencer opcode **trace ring** (DEBUG; not page-aligned — `Seq_Trace` does a carry-correct 16-bit add) | `SND_SEQ_TRACE = SND_MUSIC_PARAM+6` | sequencer / debug mirror |
| `$1CCC–$1CD2` | 7 B | **Global expression** (`SND_MASTER_FADE`… `SND_TEMPO_BASE`) | `SND_GLOBAL_EXPR = trace+32` | fade/tempo engine |
| `$1CD3–$1CFF` | 45 B | Alignment slack = the map's growth headroom (absorbed before `SND_SFX_BASE` moves) | — | — |
| `$1D00–$1EBF` | 448 B | **SfxChannels** — `SFX_VOICE_COUNT` (7) × `SfxChannel_len` (64) | `SND_SFX_BASE = align256_up(SND_GLOBAL_EXPR+7)` (**derived**, must stay page-aligned) | SFX engine |
| `$1EC0–$1ECA` | 11 B | SFX queue (3×2) + head/tail/count + duck level/target | chained; `SND_SFX_RAM_END = $1ECB` | SFX engine |
| `$1ECB–$1ED1` | 7 B | SFX dispatch scratch (`SND_SFX_DISP_*`, defined in `sound_sfx.asm`) | `= SND_SFX_DUCK_TARGET+1` | SFX dispatch |
| `$1ED2–$1EFF` | 46 B | Free (last movable byte is `$1ED1`) | — | — |
| `$1F00–$1F06` | 7 B | **Mailbox** (`SND_REQ_*` + `SND_CTRL_DMA_ACTIVE` at `$1F04`) | `SND_REQ_BASE = $1F00` — **FROZEN** | 68k writes, Z80 consumes |
| `$1F10–$1F14` | 5 B | **Status block** (`SND_STAT_*`) | `SND_STAT_BASE = $1F10` — **FROZEN** | Z80 writes, 68k reads |
| `$1F15–$1FFD` | 233 B | Stack headroom (grows **down** from the top) | — | — |
| `$1FFC–$1FFF` | top word | **Stack top** — `ld sp, SND_STACK_TOP` at init; first push lands `$1FFC/$1FFD` | `SND_STACK_TOP = $1FFE` (pinned) | init |

Note the deliberate geometry: the stack sits **above** the frozen mailbox/status block and grows
down toward it; the movable map grows up toward `$1F00` from below. Nothing may cross `$1F00`.

## 2. Struct sizes (A.3)

- **`SeqChannel` = 60 bytes** (was 58). **`SfxChannel` = 64 bytes** (was 62). Both even.
- A.3 added two 1-byte fields to BOTH structs, immediately after `sc_mod_step_raw`:
  `sc_mod_wait_raw` (+49) and `sc_mod_delta_raw` (+50) — raw `smpsModSet` operand latches, the
  reload sources for the per-note vibrato re-arm task. **Dead space until that task wires them.**
  `sc_mod_accum`/`sc_base_freq`/`sc_last_freq` shifted +2 (now +51/+53/+55).
- **Shared-prefix rule:** `SfxChannel` +0..+56 is a byte-for-byte offset clone of `SeqChannel`
  (through `sc_last_freq`); the structs diverge at +57 (`sc_noise_mode` vs `sx_priority`). The
  shared interpreter (`ModUpdate`/`Sequencer_Channel`) walks both with the same `(ix+sc_*)`
  displacements. Guarded by the shared-prefix assert (extended with both new fields).
- All field offsets must stay ≤ +127 (`(ix+d)` signed displacement) — asserted on the deepest
  field of each struct (`sc_detune` +58, `sx_kind` +63).

## 3. Layout invariants

1. **Ring is one 256-aligned page.** The streaming loop holds `h = SND_RING_PAGE` for the whole
   sample and wraps with `inc l`; `SND_RING_PAGE` is derived (`base>>8`), so the pair cannot drift.
2. **`$1F00+` is FROZEN** (68k contract). `SND_REQ_BASE`/`SND_STAT_BASE` are shared with 68k code
   (`sound_api.asm`, debug mirror) and cited as raw addresses by oracle debug workflows and docs.
   The movable map must end at or below `$1F00`; the repack moved *nothing* at/above it.
3. **`SND_SFX_BASE` is derived but MUST stay 256-aligned**, and every music `SeqChannel` byte must
   sit strictly below it: `Snd_ChanClass` classifies music-vs-SFX by comparing ix's HIGH BYTE
   against `SND_SFX_BASE>>8` (one-byte compare, 12 call sites). Alignment + ordering are both
   asserted; break either and SFX ducking/patch/restore dispatch misclassifies channels.
4. **The code ceiling IS `SND_STATE_BASE`.** Raising the ceiling again means sliding the whole
   movable map up — this repack is the template (state → ring → seq → tail all chain; re-derive,
   re-assert, boot-test).
5. **Resident-code rule:** in-frame CODE may never be banked; only DATA tables ride the `$8000`
   window (A.2: `DacSampleTable`, `SeqOpcodeTable`, `SfxBlobWinTab`).
6. **Even sizes:** the Z80 blob byte count must stay even (the 68k boot copy is word-based), and
   both channel structs are even so array walks (`add ix,de`) keep parity.
7. AS does **not** auto-align `ds.w` — the state block keeps its word fields at even absolute
   offsets by construction; struct pads (`sc_pad`, `sx_pad`) keep the struct lengths even.

## 4. Assert inventory (which build assert guards which seam)

All in `sound_constants.asm` unless noted. Every region pair on the map has a guard:

| Seam / contract | Assert |
|---|---|
| code ≤ ceiling | `Z80_SOUND_SIZE > SND_STATE_BASE` → fatal + the "Z80 sound budget" message (`z80_sound_driver.asm`) |
| state block ≤ ring | `SND_STATE_END > SND_RING_BASE` → fatal |
| ring 256-aligned | `SND_RING_BASE & $FF ≠ 0` → fatal (page-byte is derived, can't drift) |
| ring ≤ sequencer | `SND_RING_BASE + SND_RING_LEN > SND_SEQ_BASE` → fatal |
| seq header+channels ≤ mailbox | `SND_SEQ_BASE + hdr + 11*SeqChannel_len > SND_REQ_BASE` → error; plus `SND_SEQ_END > SND_REQ_BASE` → fatal |
| FM scratch ≥ seq end | `SND_FM_SCRATCH < SND_SEQ_END` → fatal |
| scratch ≤ music param | `SND_FM_SCRATCH + 5 > SND_MUSIC_PARAM` → fatal |
| music param ≤ trace | `SND_MUSIC_PARAM + 6 > SND_SEQ_TRACE` → fatal |
| trace ≤ global expr | `SND_SEQ_TRACE + 32 > SND_GLOBAL_EXPR` → fatal |
| global expr ≤ SFX base | `SND_GLOBAL_EXPR + 7 > SND_SFX_BASE` → fatal |
| SFX base page-aligned (classifier) | `SND_SFX_BASE & $FF ≠ 0` → fatal |
| music channels below SFX page (classifier) | `SND_SEQ_END > SND_SFX_BASE` → fatal |
| SFX RAM ≤ mailbox | `SND_SFX_RAM_END > SND_REQ_BASE` → fatal |
| SFX dispatch scratch ≤ mailbox | `SND_SFX_DISP_END > SND_REQ_BASE` → fatal (`sound_sfx.asm`) |
| mailbox tail below status | `SND_REQ_TEMPO >= SND_STAT_BASE` → error |
| stack pin | `SND_STACK_TOP ≠ $1FFE` → error (spec + debug docs cite the raw value) |
| struct sizes | `SeqChannel_len ≠ 60` / `SfxChannel_len ≠ 64` → error |
| `(ix+d)` range | `SeqChannel_sc_detune > 127` / `SfxChannel_sx_kind > 127` → error |
| shared prefix | offset-equality chain over `sc_flags…sc_last_freq` **including `sc_mod_wait_raw`/`sc_mod_delta_raw`** → error |
| debug mirror fits | `64 + SEQ_MIRROR_HDRCH + SND_SEQ_TRACE_LEN > 176` → fatal (`engine/debug/sound_debug.asm`) |
| Timer-A frame clock | `SND_TIMERA_N ≠ 136` → error (unrelated to the map but part of the same "pinned by design" family) |

**Coverage rule going forward:** any new Z80 RAM region must chain from its neighbor (no fresh
pins below `$1F00` except the three anchors `SND_STATE_BASE`/`SND_RING_BASE`/`SND_SEQ_BASE`) and
add a fatal against the region above it.
