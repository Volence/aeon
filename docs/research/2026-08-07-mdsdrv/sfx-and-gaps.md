# MDSDRV pass 2 — SFX arbitration, the game-facing API, and the leftover sweep

Repo: `/home/volence/sonic_hacks/aeon/docs/research/external/mdsdrv/` (MDSDRV 0.6, `version_str` = `"MDSDRV0.6 230612"`, `src/mdsdrv.68k:37`).
Prior passes: `docs/research/2026-08-07-mdsdrv/{core,z80-dma,format-toolchain}.md`. Read first; this document deliberately does not re-derive what they already established (core.md §0.2 covers `mds_update_priority` correctly and in detail — I re-read the source and confirm their reading is accurate).

Legend: **[V]** verified by reading the cited source. **[I]** inferred/reasoned.

---

## 1. VERDICT on the priority question

### Short answer

**Partially refute the framing, but the practical conclusion stands.**

MDSDRV *does* have built-in arbitration — it is real, per-frame and channel-granular — but it is **a fixed 4-level slot lattice supplied by the caller, not a priority attached to a sound**. There is:

* **no per-sound priority datum anywhere** — not in the song header, not in the sequence stream, not in the driver **[V]**;
* **no "don't interrupt a more important sound" logic at request time** — `mds_request` is an unconditional store **[V]**;
* **only 3 SFX slots**, so the game must collapse its entire SFX vocabulary onto three levels **[V]**.

So MDTravis's tiered `.hiPri` / `.midPri` / `.loPri` ID lists are **not** replacing a priority feature MDSDRV has and he missed. They are the **game-side ID→slot mapping table that MDSDRV structurally requires every integrator to write**. Three tiers is exactly three SFX slots — the shape is forced by the driver, not chosen. **[I** on his intent — I have not seen his code, only your quote; but three tiers mapping onto exactly `MDS_SE3=0 / MDS_SE2=1 / MDS_SE1=2` (`sample/sgdk/inc/mdsdrv.h:34-37`) is not a coincidence.**]**

Calling it a "workaround" is fair in the sense that MDSDRV delegates a job most Sonic-lineage drivers do internally. Calling it "MDSDRV lacks priority" is imprecise: it lacks *sound-intrinsic* priority; it has *caller-declared* priority.

### 1.1 Is there ANY built-in priority / stealing / arbitration? — YES, but only between slots

**The mechanism (`src/mdsdrv.68k:878-932`, `mds_update_priority`) [V]:**

Per request slot the driver keeps `w_chmask` = a 16-bit mask of physical channels that slot currently claims (`src/mdsdrv.inc:228`). Once per frame, for every track:

```
	lea	w_chmask(work),tmpa0
	move.b	t_channel_id(twork),chnid	; my physical channel
	move.b	t_request_id(twork),d0		; my slot, as a word offset (0,2,4,6)
	rept	RCOUNT-1
		beq.s	@has_priority		; reached my own slot first -> I win
		move.w	(tmpa0)+,d1		; a lower-numbered slot's chmask
		btst	chnid,d1		; does it claim MY channel?
		bne.s	@no_priority		; yes -> I lose
		subq.b	#2,d0
	endr
```
(`:890-899`)

Lower slot index = higher priority. **Slot 3 is BGM**, hardcoded — `mds_update_fade` addresses `w_volume+6` / `w_tmask+6` / `w_request+6` literally (`:945, :964, :971`), and `@stop_song` special-cases `cmpi.w #6,rnum` to clear fade state (`:864-870`). Slots 0-2 are SFX (`doc/api.md:103-106`; `sample/sgdk/inc/mdsdrv.h:34-37`).

**Loser handling is suppression, not eviction (`:926-929`) [V]:**
```
@no_priority
	st	t_last_pitch(twork)			; force a pitch rewrite on return
	ori.w	#(nm_restore<<@nf)|(1<<(@cf+cf_background)),flag
```
`cf_background` = "track is deprioritized and plays in the background" (`mdsdrv.inc:98-99`). `mds_update` tests it **after** `mds_update_seq` (`:546-549`), so the sequence cursor keeps advancing at full tempo and only the chip-write half is skipped. No desync, no state snapshot needed.

**Regain (`:908-925`) [V]:** `bclr #cf_background`; if it actually changed, mask the pending key-on — unconditionally for drum-mode tracks, and otherwise only when `t_counter < 5` ticks remain, i.e. don't re-attack a note that is about to end anyway.

### 1.2 What is NOT there (the actual gaps) [V]

**(a) `mds_request` never compares against what is playing.** `src/mdsdrv.68k:140-145` in full:
```
mds_request
	ori.w	#(1<<rf_active)+(1<<rf_stop),d0
	andi.w	#3,d1
	add.w	d1,d1
	move.w	d0,w_request(a0,d1)
	rts
```
Five instructions. No read of the slot's current contents, no priority compare, no queue. `doc/api.md:39-41` states the consequence plainly: *"Calling this function will stop all already playing tracks with that priority level."* Unconditionally, every time.

**(b) A same-frame double request silently loses the first sound.** `w_request` is a single word per slot, consumed at the next `mds_update` (`:486-489`). Two `mds_request` calls to the same slot in one frame → the second overwrites the first, and the first never plays at all. There is no pending flag, no ring, no ack. **[V]**

**(c) Every request costs a full stop and takes two frames.** `mds_handle_request` runs `bclr #rf_stop,@reqdata / bne @stop_song` (`:649-650`). Frame 1 takes `@stop_song` (`:845-871`): sets `cf_stop` on every track in the slot, sets `t_request_id = RCOUNT<<1` (= "free, do not grant priority"), clears `w_tmask`/`w_chmask`, and writes the request back **with `rf_active` still set**. Frame 2 sees `rf_active`, falls through to the start path. So a retrigger of the *same* SFX is a hard stop plus a one-frame silence, always. **[V]**

**(d) Only 3 SFX slots exist.** A 4th concurrent SFX is impossible without evicting one of the three, no matter how many FM/PSG channels happen to be free. `RCOUNT equ 4` (`mdsdrv.inc:30`) is a build constant, not a runtime pool. **[V]**

**(e) Physical channels are baked into the sound data, not allocated.** `@use_track` reads the channel id straight from the song header and stores it (`:783-784`); `doc/mdsseq.md:264-270` documents the per-track record as `{channel_id, flags, position}`. There is **no dynamic voice allocation** — two SFX authored on FM4 will always collide on FM4 even if FM5 is idle. **[V]**

**(f) Two SFX on different slots do NOT kill each other — the loser runs silently to completion.** `mds_update_priority` is generic over all four slots, so a slot-1 SFX losing FM4 to a slot-0 SFX gets `cf_background`, keeps burning its sequence, and un-mutes mid-way if the slot-0 SFX ends first. For music that is the *right* behaviour; for a short SFX it means a partial, phase-shifted tail. **[V** on mechanism; **I** on it being undesirable.**]**

**(g) `@next_track` fails partially and silently.** If fewer free track slots remain than the song needs, the loop just exits (`:774-775`) after loading however many fit. A song can start with half its tracks missing, with no error and no way to detect it. **[V]**

### 1.3 What MDSDRV gives the game to arbitrate with

Read `doc/api.md` in full plus `mds_command`'s table (`src/mdsdrv.68k:161-189`). The complete arbitration surface is:

| Affordance | Where | Notes |
|---|---|---|
| Caller-declared slot 0-3 | `mds_request` d1 | the *entire* priority model |
| "Is anything on slot N?" | `mds_command` `get_status` (0x02) → `w_tmask[N]` | **[V]** `:209-212`. A 16-bit *track* mask; non-zero = busy. Does **not** tell you *which sound*. |
| Stop slot N | `mds_request(id=0, slot=N)` | `doc/api.md:42-43` |
| Pause/resume slot N | `set_pause` (0x0B) | `:315-339` |
| Per-slot volume get/set | 0x0C / 0x0D | `:344-378` |
| Per-slot tempo get/set | 0x0E / 0x0F | `:380-394` |
| Song→game cue byte | `get_comm` (0x10) | `:396`; set by the `comm` sequence opcode |

**Notably absent from the API but present in RAM [V]:** after the start path clears `rf_active`, `w_request[slot]` retains the **currently-playing sound ID** (`:655-656`). The game can read it directly out of the work area, but no `mds_command` exposes it — so "is *this specific* sound playing?" requires poking driver internals.

**`src/mdlib.68k` is not a sound library.** Your brief listed it as "the 68k-side game-facing library" — it is not. It is the *demo ROM's* generic MD helper library: VDP register init, VRAM/CRAM clear, a 1bpp font blitter, `vdp_print`/`vdp_print_hex`, a tiny bytecode "print command list" interpreter, and Chilly Willy's 6-button joypad reader. Zero sound content. The game-facing surface is exactly the four `bra.w` entries at `mds_top` (`mdsdrv.68k:27-31`). **[V]**

### 1.4 Is a tiered list better than a numeric priority byte? — Honest verdict

**Within MDSDRV: yes, it is the correct shape.** The driver accepts exactly one of three SFX levels. A numeric byte would have to be quantised down to three buckets anyway, so the buckets *are* the data. Three lists is the most direct encoding of "which of the three slots does this ID go in".

**Cost:** a tiered list is genuinely *smaller* when the set is sparse. Unlisted IDs fall through to the bottom tier and cost zero bytes; a dense `dc.b priority` table indexed by ID costs one byte for all N sounds whether or not they are special. For a hack with 200 sound IDs of which 15 are "important", tiers win on ROM. The counter is **time**: a null-terminated linear scan is O(n) with a ROM read per entry per trigger, vs. one indexed byte load. At ~60 IDs across three lists that is several hundred cycles per SFX request, on the 68k, at trigger time — small in absolute terms, but strictly worse than constant, and it grows.

**Ease of authoring:** tiers are pleasant to *re-tier* (move an ID between lists) and awful to *keep correct*. They are a **second source of truth keyed on ID values, stored away from the ID definitions**. Renumber or delete a sound and the lists silently rot — a stale entry is a valid `dc.w`, so nothing fails to assemble and nothing fails at runtime; the sound just gets the wrong priority forever. That is the real flaw, and it is not fixable by making the lists nicer. A priority *field declared next to the ID*, with a build-time assertion, cannot rot. Ours is `SFXPRI_*` in `games/sonic4/config/sound_ids.emp:86-93` with a build-fatal `ensure` at `:98-99`.

**"Same tier retriggers":** tiers handle this *badly* by construction. Two same-tier SFX map to the same slot, so the second unconditionally hard-stops the first with a one-frame gap (§1.2c) — no possibility of both playing even when voices are free. A numeric priority plus a `>=` steal gate expresses the same "newest wins" default while still permitting concurrency, which is what we do (`sound_sfx.emp:1723-1728`: `cp h / jr c, .drop` — incoming **>=** occupant steals).

**Stable ordering:** lists carry an implicit order that MDSDRV completely ignores (arbitration reads `w_chmask`, never list position), so the ordering is decorative. Numeric priorities give a genuine total order that the driver actually consults.

**Verdict:** correct-for-MDSDRV, inferior in general, and **nothing to take**. The one idea worth stealing in the abstract — sparse tables cost less than dense ones — does not apply to us: our priority is one byte in the per-SFX blob header (`sfh_priority`, `sound_constants.emp:493`), which is already the sparse encoding.

### 1.5 Comparison against ours — verified from the code, not the summary

Your summary of our design is **correct on all three points**, and understates it:

| | MDSDRV | Aeon |
|---|---|---|
| Priority source | caller-supplied slot 0-3 | authored per-SFX byte `sfh_priority` (`sound_constants.emp:493`, `SFXH_PRIORITY` `:512`) |
| Priority range | 4 levels, 3 usable for SFX | 7-bit `$00-$7F`; bit 7 = non-latching flag, split at `sound_sfx.emp:810-813` into `SND_SFX_DISP_PRIO_RAW` / masked `SND_SFX_DISP_PRIO` |
| Build guard | none | `ensure(... & $80) == 0` build-fatal, `games/sonic4/config/sound_ids.emp:98-99` — **verified present** |
| Concurrent SFX | 3 (slot-bound) | 7 (`SFX_VOICE_COUNT = 7`, `sound_constants.emp:447` — FM3/4/5, PSG1/2/3, PSGN) |
| Voice selection | none — channel baked into data | 3-tier ladder in `Sfx_SelectVoice` (`sound_sfx.emp:1609`): (a) preferred route if free `:1620`, (b) first free slot of the same *kind* `:1642`, (c) lowest-priority same-kind occupant `:1682` |
| Steal gate | n/a (unconditional slot overwrite) | `incoming >= occupant` or drop (`:1723-1728`) |
| Request buffering | one word, latest-wins, **lost on same-frame double-post** | 68k 8-entry ring with same-id dedup (`sound_api.emp:285-332`) + drain-one-per-frame with mailbox handshake (`:349-372`) + Z80-side 3-deep priority-gated queue (`SFX_QUEUE_DEPTH = 3`, `sound_constants.emp:907`; enqueue/overflow-replace `sound_sfx.emp:680-740`) |
| Retrigger of the same id | hard stop + 1 frame silence, always | per-SFX instance cap `sfh_cap` (`sound_constants.emp:504`); under cap → allocate a *new* voice, at cap → kill the lowest-slot instance (`sound_sfx.emp:856-897`) |
| Music restore | `nm_restore` bitmask, re-materialised over 1 frame | `Sfx_Restore` (`sound_sfx.emp:1123`) — patch re-upload, pan shadow resync, exact re-key from `sc_base_freq`, stopped-sequencer guard, no-music-underneath silencing |
| Ducking | **none at all** | `Sfx_DuckRamp` (`:313`) — per-SFX depth `sfh_duck` (`sound_constants.emp:503`), `Sfx_DeepestDuck` (`:1297`) min-of-active, linear ±4/frame ramp, folded into `Fm_SetVolume`/`Psg_SetVolume`, write-on-change, held notes re-asserted |
| Non-latching priority | none | bit-7 SFX store the same-kind active *floor* via `Sfx_MinActiveKind` (`:1001-1007, :1322`) so they play now without latching a high floor |

**Does MDSDRV have anything here we lack? No.** Every arbitration behaviour it has, we have a strict superset of. The two things it does that we do differently rather than worse — `cf_background` (== our `SCF_SFX_OVERRIDE`) and `nm_restore` (== our `Sfx_Restore`) — were already ruled `[ALREADY HAVE]` by core.md #18, and I confirm that ruling from the source.

The one thing MDSDRV has that we structurally do not is **unification**: one interpreter, one track pool, one priority rule for BGM and SFX alike. That is an architecture, not a feature, and core.md #12 already rejected adopting it. I concur.

---

## 2. Complete `doc/api.md` call inventory

Four ABI entries at `mds_top` (`mdsdrv.68k:27-31`), plus 19 `mds_command` sub-commands (`:169-189`). `mds_command` sub-commands **0x11 / 0x12 are implemented but undocumented in the command-count sense** — `@cmd_max` is derived from the table, so `get_cmd_count` returns 0x13.

| # | Call | What it does | Aeon status |
|---|---|---|---|
| — | `mds_init` (`mdsdrv+0`) | validate magic+version, zero work area, PAL/NTSC tempo, upload Z80 blob | **[WE HAVE]** `Sound_Init` (`sound_api.emp:135`) |
| — | `mds_update` (`mdsdrv+4`) | per-VBlank tick of all 4 slots and 16 tracks | **[WE HAVE — better]** the Z80 self-ticks off Timer-A; no 68k per-frame cost at all |
| — | `mds_request` (`mdsdrv+8`) | start/stop a sound on a slot | **[WE HAVE — better]** `Sound_PlayMusic` (`:193`) / `Sound_PlaySFX` (`:285`), ring-buffered + deduped |
| — | `mds_command` (`mdsdrv+12`) | command dispatcher | **[WE LACK — by design]** we use one mailbox byte per command type (`SND_REQ_*`, `sound_constants.emp:35-49`) rather than a dispatcher |
| 0x00 | `get_cmd_count` | number of commands | **[WE LACK — n/a]** no dispatcher to enumerate |
| 0x01 | `get_sound_count` | number of defined sounds | **[WE LACK — n/a]** `SONG_COUNT` is a comptime const with an `ensure` (`sound_ids.emp:55`); nothing to query |
| 0x02 | `get_status` | per-slot busy bitmask | **[WE LACK — real gap, small]** we have no 68k "is music/SFX playing?" query. `SND_SEQ_ACTIVE` and the SFX `SCF_ACTIVE` flags exist in Z80 RAM but are only readable through the DEBUG-only mirror (`engine/debug/sound_debug.emp`, off by default) |
| 0x03 | `get_version` | driver version string + hex | **[WE LACK — partial]** `SND_ALIVE_MARKER = $5A` (`sound_constants.emp:63`) is a liveness handshake, not a version |
| 0x04 | `get_gtempo` | global tempo | **[WE LACK]** write-only on our side |
| 0x05 | `set_gtempo` | set global tempo | **[WE HAVE]** `Sound_SetTempo` (`sound_api.emp:417`) → `SND_REQ_TEMPO` |
| 0x06 | `get_gvolume` | initial BGM+SFX volume | **[WE LACK]** |
| 0x07 | `set_gvolume` | set initial BGM+SFX volume | **[WE LACK]** we have per-SFX duck depth instead of a global SFX trim |
| 0x08 | `write_fm_port0` | raw YM write, port 0 | **[WE LACK — reject]** `sound_sfx.emp:44-47` documents the `de=$4001` invariant: **all** YM writes go through `Fm_*`. A raw 68k poke would break `$2A` re-park and the DMA bracket |
| 0x09 | `write_fm_port1` | raw YM write, port 1 | same |
| 0x0A | `fade_bgm` | fade to a target level at 1 of 8 rates, optional stop | **[WE HAVE — partially]** `Sound_FadeOut`/`Sound_FadeIn` (`:427`, `:437`) are fixed-shape commands. We lack **arbitrary target level** and **selectable rate** |
| 0x0B | `set_pause` | pause/resume a slot | **[WE LACK — real gap]** verified: no pause path anywhere in `engine/sound/*.emp`. Relevant if a pause menu or death freeze ever wants music held rather than stopped |
| 0x0C | `get_volume` | current per-slot volume | **[WE LACK]** |
| 0x0D | `set_volume` | set per-slot volume | **[WE LACK]** we have fade + duck, but no direct "set music to level X" |
| 0x0E | `get_tempo` | current per-slot tempo | **[WE LACK]** |
| 0x0F | `set_tempo` | set per-slot tempo | **[WE HAVE]** `Sound_SetTempo`, incl. `SND_TEMPO_RESTORE = $FF` (`sound_constants.emp:466`) |
| 0x10 | `get_comm` | song→game cue byte set by the `comm` opcode | **[WE LACK]** already flagged `[WORTH TAKING]` by format-toolchain.md #8 |
| 0x11 | `set_pcmmode` | 2/3-channel PCM mix mode + DMA buffer depth | **[WE LACK — n/a]** single-channel DAC; already covered by z80-dma.md |
| 0x12 | `get_pcmmode` | read PCM mode (0 = Z80 still booting) | **[WE LACK — n/a]** our equivalent is `SND_STAT_ALIVE` |

**API doc is stale in one place [V]:** `doc/api.md:14-17` documents `mds_init` as taking `a0`, `a1` only. The code takes **`a2` = PCM data pointer** as well (`mdsdrv.68k:48`, and both callers pass it — `main.68k:59`, `sample/sgdk/src/mdsdrv.c:44`). Worth knowing if we ever cite api.md as authoritative.

---

## 3. The leftover sweep — ranked

I checked what the three prior docs cite and went after what they never opened. Never cited by any of them: `src/mdbug.68k`, `src/mdinit.68k`, `src/main.68k`, `build.bat`, `quickrom.bat`, `tools/frqtab.c`, the entire `sample/sgdk/` tree, `data/pcm/*.wav`. Cited once and only in passing: `src/mdlib.68k`, `src/blob.68k`, `Makefile`, `tools/gendef.c`.

**Bottom line up front: not much. Two items worth acting on, both small, both about observability rather than the driver.** Everything else is either already ours, better on our side, or inapplicable. That is a clean negative result and I am not going to dress it up.

### #1 [WORTH TAKING — Oracle requirements input] The live per-track state table
`src/main.68k:241-290`. The test ROM renders, **every frame**, a 10-row table of the driver's track array straight out of RAM: `t_request_id`, `t_channel_id`, `t_base_addr`, `t_position`, `t_stack_pos`, `t_note_flag`, `t_counter`, `t_note`, `t_ins`, `t_vol`, `t_peg_pos`, `t_trs`, `t_dtn`, `t_pta`. It is driven by a tiny bytecode print interpreter (`mdlib.68k:325-428`) so adding a field costs one `p_hex_b` line.

Ours: `engine/debug/sound_debug.emp` mirrors only a **20-byte prefix of 3 music channels** (`SEQ_MIRROR_CHANNELS = 3`, `:52-53`) and **zero SFX channels** — the 176-byte `Sound_Dbg_Mirror` budget is the binding constraint, and the whole thing is off by default (triple gate, `:1-5`) because the bus hold is an audible 60 Hz tick.

The gap that matters for the work in §1: **when an SFX steals, drops, or gets queued, nothing is observable.** `sx_priority`, `SND_SFX_ID_TAB`, the 3-entry queue, `SND_SFX_DUCK_LEVEL`/`_TARGET` — none reach the mirror. Concretely: mirror the 7 `SfxChannel` slots' `{sc_flags, sc_route, sx_priority, id}` (4 bytes × 7 = 28 B) plus the 8-byte queue block. Requires either a larger `Sound_Dbg_Mirror` or dropping music-channel prefix bytes. **[V]** on both sides.

### #2 [WORTH TAKING — cheap] Driver cost meter from the raw H/V counter
`src/main.68k:330-335`: read `$C00008` immediately after `mds_update` returns, and compare against a threshold to colour the display red when the driver overruns VBlank (`:298-300`). Two `move.w` and a `sub.w`. We measure sound cost by `Lag_Frame_Count` and the profiler, which are frame-granular; this is a direct "did the sound update fit in the window" readout with no profiler infrastructure. Trivially portable to our VBlank. **[V]**

*(Caveat, verified: their own `r_z80_load` display is dead — `r_z80_load` is declared at `main.68k:32` and printed at `:307`, but **nothing ever writes it**; the Z80's `z_load` (`mdssub.inc:29`) is never copied to the 68k. The z80-dma agent's #4 "ring-lead telemetry" recommendation is about the Z80-side byte and stands on its own; the 68k display of it was never wired up.)*

### #3 [ALREADY HAVE — and better] The crash debugger
`src/mdbug.68k` (all 312 lines). It is a **crash screen, not a sound monitor** — despite the brief's framing there is **zero sound-debugging content** in it. It installs handlers for bus/address/illegal/div0/CHK/TRAPV/line-A/line-F, prints d0-d7/a0-a6/sp/sr/pc plus the address-error frame decoded as read-vs-write and data-vs-code (`:161-186`), and drops into a **joypad-scrollable memory viewer** (`:224-291`: up/down ±$10, left/right ±$60, Start = reset through the vector table). It PSG-mutes and holds the Z80 in reset before touching the VDP (`:127-134`). Compiled out entirely to `stop $2700` when `DEBUG_SCREEN` is undefined (`:297-308`).

Ours (`project_crash_report_shapes`, chain 40): `ReleaseFault` red-screen halt plus the full `CRASH_REPORT` shape with the MDDBG blob and symbol locator. The one thing theirs has that ours does not is the **interactive memory browser** — of near-zero value to us given Oracle reads memory directly. **No action.**

### #4 [REJECT — inapplicable] Init sequence and blob handling
`src/mdinit.68k` is the *demo ROM's* boot: TMSS, CRAM/RAM clear, the standard 26-word Z80 init stub, then `bra main`. `src/blob.68k` is 8 lines — five `include`s and nothing else, the entire mechanism by which the driver is assembled standalone as a position-independent binary. Both are the direct consequence of MDSDRV shipping as a *redistributable blob*; core.md #13 already rejected PIC for us on Z80 grounds. Our `engine/engine.inc` owns the whole ROM layout by design. **Nothing here.**

### #5 [REJECT — inapplicable] The build pipeline
`Makefile` + `build.bat` + `quickrom.bat`. Chain: `mdslink` (external, ctrmml) → `mdsseq.bin`/`mdspcm.bin`/`mdsseq.inc`/`mdsseq.h`; `sjasmplus` → `mdssub.bin`; `salvador` → ZX0-compress the Z80 blob (**note: same compressor family we use for the act art pool**); `asm68k.exe` under Wine → `mdsdrv.bin`. `tools/gendef.c` generates the MML/asm symbol header from `tools/seqdef.h` so the C tool and the assembler cannot disagree about opcode numbers — a single-source-of-truth generator, which is a pattern we already apply far more aggressively (comptime `ensure`, `offsetof`, seam-1 link).

The one genuinely nice affordance: **`quickrom.bat` is drag-and-drop** — drop a `.mml`/`.mds` on it and get a bootable single-song test ROM. Our `SOUND_DEBUG_HOTKEYS=1` sound-test path already covers the need without a separate ROM. **[V]** Note also they still require Wine for `asm68k.exe` even on the Make path — we left that world deliberately.

### #6 [ALREADY HAVE] `tools/frqtab.c`
34 lines: generates the 48-entry FM f-num table and the 12-entry PSG divisor table from first principles (`ym2612_clk / 144 / 2048 / 32`, A=440, `pow(2, n/12)`), breaking out of the loop when f-num exceeds 2047 so the octave-offset comment is emitted automatically. Never cited by any prior agent. It is textbook and adds nothing over what core.md #1/#11 already extracted about the pitch model. **No action.**

### #7 [ALREADY HAVE — worth one glance] The SGDK integration
`sample/sgdk/` — never opened by any prior agent. `inc/mdsdrv.h` + `src/mdsdrv.c` are a thin GCC-inline-asm wrapper pinning registers with `register u16* a0 asm ("a0")`, plus `MDS_pause` / `MDS_fade` convenience wrappers. `src/menu.c` + `src/main.c` are a scrolling sound-test menu with live volume/tempo readback via `MDS_command(MDS_CMD_GET_*, ...)`.

Two small observations: (a) `MDS_WORK_SIZE 512` **words** = 1 KB, corroborating the README's RAM claim that core.md §0.4 examined; (b) `MDS_update()` has to declare `a6` as an output to stop GCC clobbering the frame pointer (`mdsdrv.c:118-119`) — a C-ABI wart with no analogue for us. **No action.**

### #8 [no action] Small confirmations picked up in passing
* `mds_init_error` returns `d0 != 0` **and** zeroes `w_sdtop` so a later `mds_request` cannot dereference garbage (`mdsdrv.68k:125-129`) — a defensive touch our `Sound_Init` matches with its `SND_ALIVE_MARKER` spin + `SPIN_WATCHDOG_LIMIT` (`sound_api.emp:38-45`).
* `mds_update` is re-entrancy-guarded by `bset #7,(work)` on the top byte of the `sdtop` pointer (`:478-479`) — the "field packing into pointer spare bytes" trick core.md #14 rejected, used a second time.
* `mds_halt` (`:111-123`) is reachable as a fallthrough from `mds_init` **and** as a label, but is not in the ABI table — dead as a public entry point.
* `mds_request`'s `andi.w #3,d1` (`:142`) means an out-of-range slot silently aliases rather than erroring. Ours would `ensure` it.

---

## 4. VERIFIED vs INFERRED

**VERIFIED (read in source this session):**
`doc/api.md` complete; `src/mdsdrv.68k:1-130` (ABI, init), `:131-460` (request + all 19 commands), `:460-640` (update loop, background gating, channel dispatch), `:637-932` (request handling, track allocation, stop, priority), `:938-985` (fade), `:1155-1184` (track end / channel deallocation); `src/mdsdrv.inc` complete; `src/mdlib.68k` complete; `src/mdbug.68k` complete; `src/mdinit.68k` complete; `src/main.68k` complete; `src/blob.68k` complete; `Makefile`, `build.bat`, `quickrom.bat`, `tools/gendef.c`, `tools/frqtab.c`, `README.md`, `doc/mdsseq.md:255-300`, `sample/sgdk/{inc/mdsdrv.h,src/mdsdrv.c,src/main.c}` complete. Repo-wide grep for `priorit` (case-insensitive) across `doc/`, `README.md`, `tools/*.c|h`, `data/`, `sample/` — every hit accounted for above.
Ours: `engine/sound/sound_api.emp` (headers + `Sound_PlaySFX`/`Sound_DrainSfxRing`/`Sound_PlayRing`, proc inventory); `engine/sound/sound_sfx.emp` (`Sfx_DuckRamp`, the instance-cap scan, `SfxDispatch` priority read, `Sfx_QueueEnqueue`, `Sfx_SelectVoice` in full, proc inventory); `engine/sound/sound_constants.emp` (SFX section, `SfxHeader`/`SfxChannel`, aliasing `ensure`); `games/sonic4/config/sound_ids.emp:55, 86-99`; `engine/debug/sound_debug.emp` complete. Greps confirming absence of pause / per-slot volume / status-query paths in `engine/sound/*.emp`.

**INFERRED (reasoned, not stated by either source):**
* That MDTravis's three tiers map to MDSDRV's three SFX slots. Strongly implied by the shape but I have not read his code.
* That a slot-1 SFX running muted-then-unmuting under a slot-0 SFX (§1.2f) is undesirable. The mechanism is verified; the value judgement is mine.
* The cycle-cost comparison between a null-terminated tier scan and an indexed byte load (§1.4) is arithmetic, not measurement.
* That mirroring `{sc_flags, sc_route, sx_priority, id}` × 7 is the right SFX observability slice (§3 #1) — a proposal, not a verified fit against the 176-byte budget.
