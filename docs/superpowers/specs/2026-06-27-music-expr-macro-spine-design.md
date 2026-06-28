# Music Expression Engine — Phase 3: Macro/Automation Spine (+ FM-TL Vol-Env, SSG-EG, MEV_REGWRITE)

**Date:** 2026-06-27
**Status:** Design — pending user review → writing-plans
**Branch:** `feat/music-expr-p1` (worktree `/home/volence/sonic_hacks/aeon-music-expr`; Phase 1 implemented, not merged)
**Spec lineage:** generalizes the macro spine from `docs/superpowers/specs/2026-06-23-music-expression-engine-design.md` §3.2–§3.3 (§3.3's macro body + §8 add-ons folded in here). Phase-2 plans (`2026-06-27-music-expression-phase2-global.md`, `…-pernote.md`) remain independent; this spec **absorbs the FM-TL vol-env** out of the per-note plan (see §0.3).
**Scope owner:** engine (mechanism/format/architecture). Content (songs, instrument banks, macro libraries) is downstream/user-driven; this spec defines the format the content targets.

---

## 0. Why this is the format-defining lift

### 0.1 Intent
Phase 3 turns the flat per-channel opcode stream into a **macro/automation engine**: a general path where every future expressive effect is "add a macro target," not "new opcode + new struct field." It is maximal on the **data format + per-channel state** now — those are the only things a later change forces a re-author of (including via MegaDAW, which can only expose what the format supports). Rendering code may land incrementally, but every increment plugs into the *end-state* format. ("Design for C, build for A.")

### 0.2 The two design bets (user-ratified 2026-06-27)
1. **Topology = Hybrid (C):** named per-target contour slots (independent loops) **+** a raw-register automation stream on the already-free `sc_mod_ptr` seam for the long tail. This is the only topology with **both** independent per-target looping **and** arbitrary-register coverage.
2. **Scope = self-contained + FM swells:** Phase 3 ships a **complete** volume macro on **FM (carrier-TL) and PSG**, building the reserved FM-TL vol-env renderer; reg-automation + `MEV_REGWRITE` + SSG-EG; pitch/pan reserved non-breaking. The other Phase-2 one-offs (porta/detune/tempo/LFO/fade) stay independent and are **not** prerequisites.

### 0.3 Relationship to the unbuilt Phase-2 plans
- The FM-TL vol-env (Phase-2-per-note **Group C**) is **moved into this spec** — it is the renderer the *volume* macro target needs, it uses the reserved `sc_env` slot, and building it once here avoids duplicate work. **This transfer is conditional and must be made real in the per-note plan:** Phase-2-per-note MUST be re-scoped to porta + detune (`$F5`/`$F6`) only — its Group C (Tasks C1–C4), `MEV_FMENV=$F7`, the `FmVolEnv_*` table, and the packer `FmEnv` event are deleted and re-homed here. Group C is field- and dependency-disjoint from porta (`sc_porta_*`) and detune (`sc_detune`) — it touches only the unified `sc_env` slot — so the transfer is clean, but if **both** plans build `$F7` the second to land hits the per-note fixed-slot assert (a hard duplicate-symbol break, not a silent override). *(The per-note plan doc has been struck accordingly — see §0.3 follow-up commit.)*
- Opcode reservations are honored: `$F3`/`$F4` (tempo/LFO, Phase-2-global) and `$F5`/`$F6` (porta/detune, Phase-2-per-note) are **locked with placeholder asserts**. Phase 3 owns **`$F7` (MEV_FMENV)**, **`$F8` (MEV_REGWRITE)**, **`$F9` (MEV_MACRO)**.
- Merge discipline (per handoff): stay on `feat/music-expr-p1`; **do not merge to master until the gold-standard S3K HCZ2 audio A/B is done.**

---

## 1. Grounding — verified facts this design rests on

All anchors verified against real source on `feat/music-expr-p1` (a 73-agent + direct read pass; the handoff's paraphrases were corrected where wrong — see §1.4).

### 1.1 The slot[1] seam is real and free
- `sc_mod_ptr` lives at **struct +2** (2-byte word) on **both** `SfxChannel` and `SeqChannel` (`sound_constants.asm:684` (SfxChannel), `:782` (SeqChannel); alias `:876`). It is the second per-channel stream cursor.
- The `SongHeader` commits a per-channel **5-byte record** `{SHC_ROUTE +0, SHC_CMD_HI/LO +1/+2 (slot[0]), SHC_MOD_HI/LO +3/+4 (slot[1])}` (`sound_constants.asm:1184-1189`); fixed 6-byte prefix `SH_FLAGS…SH_CHANNELS=6` (`:1174-1180`).
- The loader **already parses + rebases** `mod_ptr` (`base+offset`, big-endian; `0 ⇒ NULL`, `jr z,.mod_null` leaves it zero) (`z80_sound_driver.asm:1185-1196`). The seq region is zero-cleared at load (`:1029-1037`).
- **Nothing reads `sc_mod_ptr` at runtime today**, and the packer **always emits `0x00,0x00`** for it (`song_packer.py:679-683`; `header_len = 4+2+5*n+2`, `:662`) → the loader's store path is currently dead. **Making slot[1] real is purely additive — 0 new RAM for the cursor.**

### 1.2 The "macro in miniature" to generalize (PSG vol-env)
- Per-channel state = exactly **3 bytes**: `sc_psgenv` (+39, 1-based id, `0`=off), `sc_psgenv_cur` (+40, cursor), `sc_psgenv_out` (+41, last output, write-on-change). **Same offsets on `SeqChannel` + `SfxChannel`** → one code path serves music + SFX (`sound_constants.asm:832-834`).
- This slot is **already aliased as the unified `sc_env`/`sc_env_cur`/`sc_env_out`** slot, documented "FM TL vol-env (later phase) + PSG vol-env share ONE 3-byte slot (a channel is FM xor PSG)" (`sound_constants.asm:906-910`). **The literal seed for the spine.**
- State machine `PsgEnvUpdate` is in `engine/sound_sequencer.asm:317-359` (reached as a tail-call from `ModUpdate`, gated on `sc_psgenv!=0`); resolver `PsgVolEnv_Resolve` is in `engine/sound_psg.asm:120-140`.
- **Body grammar (verified):** a **plain byte is an ABSOLUTE per-frame value** stored into `sc_psgenv_out` then `cursor++` then re-emit — **not** a running delta. Three control codes carved from value space: `$80` loop (`cursor=0`, re-resolve, re-read same frame), `$81` sustain (hold output, no advance, never silences), `$83` rest (`Psg_NoteOff`, no advance, **id persists** so the next attack replays). `$82`/`$84…$FF` currently fall through to "plain."
- Output composition: `sc_psgenv_out` is **added** to the computed attenuation in `Psg_SetVolume` (higher = quieter; `or a` fast path when 0) (`sound_psg.asm:317-325`).
- id→ptr is an **O(N) linear scan** of parallel `PsgVolEnv_Ids` (db) + `PsgVolEnv_Ptrs` (dw) arrays, re-run every frame + every loop wrap (`sound_tables_z80.asm:74-82`); build-time source `tools/gen_sound_tables.py` `_PSG_VOL_ENVS`.

### 1.3 Which targets render continuously *today*
- **PAN:** `ModUpdate` compares `sc_pan` vs `sc_last_pan` → `Fm_SetPan` (`$B4`, **FM-only**) (`sound_sequencer.asm:177-191`).
- **PITCH-offset:** **only** via the `sc_mod_*` triangle — `ModUpdate` calls `Mod_ApplyVibrato`/`Psg_ApplyMod` when `sc_mod_ctrl!=0`; final pitch = `sc_base_freq + sc_mod_accum` (`sound_sequencer.asm:177-191/444-509`). (Music-legal since Phase 1.)
- **PSG volume:** `sc_psgenv` contour (§1.2).
- Opcode dispatch is a **32-entry word jump table** `SeqOpcodeTable` indexed by `(opcode-$E0)` after a range ladder (`sound_sequencer.asm:1190-1222`); a new opcode = replace a `dw Seq_BadOpcode` + a fixed-slot collision assert. Zero-tick setter template = `Seq_Op_PsgEnv` ($EB, `:678-710`), `Seq_Op_ModSet` ($EC, `:711-739`).
- Per-frame order: `Sequencer_Frame` calls `ModUpdate` (renderer, stream-agnostic — "never parses a stream") then tempo-gated `Sequencer_Channel` (slot[0] reader, commits `sc_stream_ptr` back at `:590-591`) (`:62-97`).

### 1.4 Handoff corrections that shape the design
1. **FM volume has NO per-frame renderer.** `ModUpdate` never calls `Fm_SetVolume`; FM volume only updates on `MEV_VOL`/`MEV_PATCH`, and per-frame re-assert is **explicitly forbidden** (`sound_sequencer.asm:99-102/659`). ⇒ FM volume automation **requires** the reserved FM-TL vol-env on `sc_env` (this spec builds it); it is *not* "just write `sc_volume`."
2. **Arbitrary-register has no shadow state.** `MEV_REGDELTA` writes the chip **immediately**, never re-rendered (`sound_constants.asm:327-335`, `sound_fm.asm:520`). ⇒ `MEV_REGWRITE`/reg-automation = **immediate writes**, not "another writer of rendered state."
3. **The re-park template is `Fm_RegDelta`/`Fm_SetPan`** (`Fm_RoutePart(b=part,c=ch) → Fm_YmWrite(a=reg,c=val,b=part) → jp Fm_ReparkDac`; ports `$4000/1`=part I, `$4002/3`=part II) (`sound_fm.asm:57-100/494-561/79-82`) — **not** the one-time LFO init write (which runs *before* `$2A` is parked and never re-parks).
4. **`sc_detune` (+56) is reserved with NO renderer** (only zeroed at init). A detune/pitch macro must drive `sc_mod_accum` (keeping `sc_mod_ctrl!=0`), not `sc_detune`.
5. **The body's `$80/$81/$83` numbers are THIS engine's convention**, not literal SMPS — only the value bytes were imported from S3K VolEnv tables. Treat the grammar as ours to extend.
6. `PsgEnvUpdate` is in `sound_sequencer.asm` (not `sound_psg.asm`); the opcode **definitions + collision asserts** are in `sound_constants.asm` while the **dispatch jump table** (`SeqOpcodeTable`) is in `sound_sequencer.asm:1190`; the FM writer primitives are in `sound_fm.asm`. The Z80 RAM map uses **constant arithmetic + struct/endstruct + if/error**, **not** phase/dephase — **deliberate, not a convention miss**: a `phase`/`dephase` over Z80 RAM would collide with the `phase 0` code-blob relocation, so constant-arithmetic is the correct pattern for this subsystem (CLAUDE.md L25's "phase/dephase for RAM layout" is stale for the Z80 sound driver).

### 1.5 RAM + budget (Phase-1 baseline)
- `SeqChannel = 58` bytes (asserted `sound_constants.asm:856-860`); `CHROUTE_COUNT = 11`; `SND_SEQ_CHANNELS = $1808`. *(These baselines supersede the seed spec's §9.1 `39→56` projection — the struct landed at 58 with the Phase-1 mod block + `sc_noise_mode` + `sc_detune` + `sc_pad` — and its §10 "`$F1–$FE` = 13 free" count, now reduced by the shipped `$F2 MEV_PSGNOISE`.)*
- **Struct slack = 2 bytes/channel:** `sc_detune` (+56, reserved) + `sc_pad` (+57). `sc_noise_mode` (+55) overlaps `SfxChannel sx_priority` (+55) — safe only because each is read with the matching `ix`; a slot[1] reader must respect that aliasing.
- **~73-byte free gap** below `SND_SONG_BUF = $1B00` (the song buffer is **512 B, copy-path songs ONLY** — stream songs never touch it). Everything above `SND_SEQ_END` is derived → auto-tracks struct growth.
- **Z80 code ceiling `SND_STATE_BASE = $16F0`**, build-asserted (`z80_sound_driver.asm:1469-1474`). Phase-1 baseline `Z80_SOUND_SIZE = $1502` → **494 bytes free** (build-measured).

### 1.6 SSG-EG reality
`FmPatch = 26 bytes` (2 header + 6×4 per-op arrays for regs `$30/$40/$50/$60/$70/$80`; op order S1,S3,S2,S4) (`sound_constants.asm:627-640`). Adding SSG-EG = append a 4-byte per-op array, change `FmPatch_len`, rewrite `Fm_PatchPtr`'s hand-unrolled `patch*26` add-chain, add `SND_REG_OP_SSG_EG=$90`, add a group write in `Fm_PatchLoad`, re-export every record + the 68k ROM copy + `sfx_transcode.py` (default `$00`). The `RegDelta` group table is 6 groups `$30–$80`; mask `$0F` already holds a 7th (`sound_fm.asm:143-209/567-578`).

---

## 2. Scope

### In scope (build this effort)
- **The macro spine** — two coordinated mechanisms sharing one body format (§3): named contour slots (independent loops) + the slot[1] register-automation stream (`MacroTick` on `sc_mod_ptr`).
- **Volume macro target — COMPLETE on FM + PSG** (the flagship). Includes building the **FM-TL carrier vol-env renderer** on the unified `sc_env` slot (§4).
- **`MEV_REGWRITE`** ($F8) — inline single raw-register write + the reg-automation event in the slot[1] stream; `$2A/$2B` park-guarded (§5).
- **SSG-EG** ($90–$9E) — load-time per-op patch byte; `FmPatch` padded 26→**32** (§6).
- **Pitch + Pan macro targets — RESERVED** (slot-ids + format allocation; renderers exist but arming/arbitration deferred non-breaking) (§7).
- **Authoring** — `song_packer.py` macro-body + bind support, header `mod_ptr` emission; `gen_sound_tables.py` `FmVolEnv_*` table (§9).

### Out of scope / deferred (with reason)
- **Pitch/pan macro slots LIVE** — reserved this phase. A pitch contour and vibrato both target `sc_mod_accum`; the arbitration rule deserves its own careful pass (§7). Pan is FM-only and lower-priority.
- **The other Phase-2 one-offs** (fade/tempo/LFO/porta/detune) — independent plans; not prerequisites.
- **Release-point grammar (`$82`)** — blocked on the engine having a distinct note-off/release event (it has rest-as-end, no release jump). The format **reserves** `$82` so it is a non-breaking later add (§3.2).
- **Mid-note SSG-EG via a 7th `RegDelta` group** — reachable via reg-automation / `MEV_REGWRITE` already; the dedicated group is a later micro-opt (§6).
- **Per-step macro duration / sub-frame rate** — one value/frame is the proven model; a duration prefix is a reserved future grammar extension.

### Closes (DEFERRED_WORK.md traceability)
On ship this spec closes/advances these cataloged gaps (marking them done in `DEFERRED_WORK.md` is a post-ship follow-up): **E4** (dual-stream / `sc_mod_ptr` slot[1] seam) via §3.4; **E-now-2** (per-frame FM TL vol-env, the Flamedriver `zDoFMVolEnv` analogue) via §4; **E5** (SSG-EG `$90–$9E`) via §6 — the per-op-patch half only, its dedicated 7th-`RegDelta`-group half stays open; **E3 / Phase-3b** (raw-register escape hatch) via §5. **D8** (packer drops music-illegal expression opcodes) is addressed by the §9 route-gate work.

---

## 3. Architecture — two mechanisms, one body format

### 3.1 Reader → state → renderer (unchanged spine principle)
`ModUpdate` is the renderer: it turns per-channel `sc_*` **state** into chip writes once/frame, write-on-change, and **never parses a stream**. Phase 3 adds writers of that state; it does **not** rewrite `ModUpdate`'s existing folds. Two writers feed the renderers:

- **Named contour slots** (§3.3) — advanced inside `ModUpdate` from `{id,cursor,out}` state; each has its **own cursor ⇒ independent loop**. Armed by a slot[0] zero-tick opcode (the ergonomic fast-path).
- **The slot[1] `MacroTick` stream** (§3.4) — a new per-frame pass over `sc_mod_ptr`; an **interleaved event program** for the long tail (raw registers + arbitrary fields), one shared cursor.

Both write the same `sc_*` state the dedicated one-off opcodes write, so they compose (spec §3.3).

### 3.2 The generalized macro body format
The body is the proven PSG-vol-env grammar, generalized and bound to a **target** when armed:

```
contour body := { value | control }*
  value   : one byte, ABSOLUTE, applied to the bound target's output this frame, cursor++
  control : $80 LOOP      ; cursor = 0, re-resolve, re-read same frame (loops forever / until release)
            $81 SUSTAIN    ; hold current output, no advance (until re-arm / note-off)
            $83 END/REST   ; stop; for a volume target = note-off semantics (id persists for replay)
  reserved: $82 RELEASE    ; (FUTURE, non-breaking) jump-on-note-off target; needs a release event first
            $84..$FF       ; reserved (today fall through to "value"; the spine must NOT rely on that)
```

- **Encoding is hard-coded per target** (no per-macro flag byte in v1): volume = absolute attenuation delta (proven). A future `ex`-style escape target may add a flag — reserved, not built.
- The **value range** for control-code safety: a volume body must not emit `$80–$83` as data (matches the shipped PSG envs — their attenuation values stay below `$80`). The packer enforces this (§9).
- **Corrections vs the seed §3.3 grammar:** `$80 LOOP` is **operand-less** (loops to cursor 0; the seed's `$80 LOOP <to>` operand does not exist in the shipped engine), and `$82 RELEASE` is **reserved/unused** (the engine has rest-as-end, no release jump). Phase 3 matches the shipped `PsgEnvUpdate`, not the stale seed text.

### 3.3 Named contour slots (the volume flagship)
A named slot is the existing 3-byte `{id, cursor, out}` model, generalized so the **renderer picks the fold by route**:

- **Volume slot = the unified `sc_env`/`sc_env_cur`/`sc_env_out` (+39/+40/+41).** A channel is FM xor PSG:
  - **PSG route:** the existing `PsgEnvUpdate` + fold into `Psg_SetVolume` (unchanged).
  - **FM route:** a new `FmEnvUpdate` (mirrors `PsgEnvUpdate`) folds `sc_env_out` into the carrier-TL delta in `Fm_SetVolume` (§4).
- **Arming:** PSG = existing `MEV_PSGENV` ($EB); FM = **`MEV_FMENV` ($F7)** — both set `sc_env` (id) + reset cursor; the renderer branches on `SCF_IS_FM_B`. Cursor resets on every attack (retrigger), exactly like the PSG env's `Psg_EnvCursorReset`.
- **Independent loop:** each slot has its own cursor, so a volume contour loops on its own schedule regardless of any reg-automation running on slot[1].
- **Reserved slots (pitch, pan):** the format allocates slot-ids and the `{id,cursor,out}` convention; renderers exist (`sc_mod_accum`, `sc_pan`) but arming + arbitration are deferred (§7). **RAM cost is paid only when a slot goes live** (each new slot = +3 B/channel into the §8 gap).

### 3.4 The slot[1] register-automation stream (`MacroTick`)
Make `sc_mod_ptr` real. A new `MacroTick` runs once/frame per active channel (after the named-slot contours render, before the slot[0] reader — see arbitration below), walking a **tag-prefixed interleaved event program** for the long tail:

```
mac event := <TAG> [operands]          ; macro-stream PRIVATE namespace — tags are NOT YM
                                       ; register values and NOT slot[0] MEV opcodes
  TAG_REGWRITE part reg val ; immediate YM write via Fm_RoutePart→Fm_YmWrite→Fm_ReparkDac (§1.4)
  TAG_NEXTFRAME             ; yield: advance exactly one frame (stop until next frame)
  TAG_LOOP                  ; cursor = stream base (header mod_ptr), re-read
  TAG_END                  ; disable the stream (mark inert)
```

Because every event is **tag-prefixed and operands follow the tag**, an operand value (e.g. `reg = $90` for SSG-EG, or a `val` of `$80`) can never be mis-parsed as a control event — this is why the reg-stream is unambiguous where a bare value/control grammar (§3.2) would not be. Exact tag byte values are finalized in the plan (a small distinct set).

- **Execution model:** on each frame, execute events until `TAG_NEXTFRAME`, then commit the cursor (mirror `sc_stream_ptr`'s commit-before-hooks discipline, `:590-591`). Multiple `REGWRITE`s before one `EOF` = multiple registers automated in the same frame. One shared cursor ⇒ shared loop (acceptable for the long tail, which is simple/one-shot).
- **Arming:** **header-armed** (the packer emits a non-NULL `mod_ptr`; runs continuously when present) **and** retriggerable via **`MEV_MACRO` ($F9)** from slot[0] (re-point `sc_mod_ptr` to a body + reset) — gives both ambient per-channel automation and musically-triggered automation.
- **DAC safety:** every `TAG_REGWRITE` re-parks `$2A` and refuses `$2A`/`$2B` targets (§5). The macro-stream tags are a private namespace, distinct from slot[0]'s `MEV_*` opcodes and from YM register values.
- **Arbitration (slot[0] vs slot[1] vs named slots) — the rule:** order within a frame is **(1) named-slot contours render in `ModUpdate` → (2) slot[1] `MacroTick` reg-writes → (3) slot[0] opcodes via `Sequencer_Channel`.** A raw `REGWRITE` to a register a named slot also drives (e.g. a carrier TL) is the **author's responsibility** (documented footgun, like overlapping automation in any DAW); the engine does not arbitrate field-level conflicts beyond this deterministic ordering. `sc_mod_ptr` aliasing with `SfxChannel sx_priority` (+55 note, §1.5) is respected by only running `MacroTick` on the matching `ix`.

---

## 4. The FM-TL volume envelope (flagship renderer)
Mirror the shipped PSG env exactly, but write FM **carrier** TLs.

- **State:** the unified `sc_env`/`sc_env_cur`/`sc_env_out` slot (0 new RAM).
- **Render (`FmEnvUpdate`, new):** advance one body entry/frame; fold `sc_env_out` into the existing carrier-TL delta `Fm_ScratchLog` in `Fm_SetVolume` as a **positive attenuation delta** (exactly like the PSG fold and the duck fold). This preserves the carrier-only selection (`CarrierMaskTableZ`, algorithm-aware) and the `b=0` sign-assumption, and composes additively with the duck (and the master fade, if/when the global slice lands). **Swell-in** = a high→0 contour; **tremolo** = an oscillating contour.
- **Resolve:** new `FmVolEnv_Ids`/`FmVolEnv_Ptrs` map mirroring `PsgVolEnv_*`, generated by `gen_sound_tables.py` into `sound_tables_z80.asm` (lands in the co-located `$8000`-window bank, **not** the `$16F0` Z80-code budget — note the per-table `phase 0` comments at `sound_tables_z80.asm:5-8` are stale post-F5; the file is included under `phase 08000h` in `main.asm:266-274`).
- **Composition with FM volume:** because there is no per-frame `Fm_SetVolume` in `ModUpdate` today (§1.4), `FmEnvUpdate` is the path that *introduces* per-frame carrier-TL motion — it calls the carrier-TL fold itself (write-on-change via `sc_env_out`), staying within the cycle budget (only keyed FM channels with `sc_env!=0` pay).

---

## 5. `MEV_REGWRITE` + the reg-escape
- **`MEV_REGWRITE` ($F8)** — slot[0] inline opcode; operands `part (0/1)`, `reg`, `value`. Immediate write modeled on `Fm_RegDelta`/`Fm_SetPan`: `Fm_RoutePart → Fm_YmWrite → jp Fm_ReparkDac`. Obeys the hl-preservation rule (the live stream ptr).
- **Reg-automation event** (slot[1] `MacroTick`, §3.4) — the same write primitive, sequenced over frames.
- **`$2A`/`$2B` guard (DAC park):** the YM address port is parked on `$2A` during DAC playback. Both paths **re-park `$2A`** after writing. Additionally, `MEV_REGWRITE`/reg-automation **must refuse to write `$2A` and `$2B`** (the DAC data/enable registers) — an authoring-exposed raw poke to those would corrupt/silence the DAC stream. The packer rejects `$2A`/`$2B` targets at build time, and the handler guards them at runtime (cheap range check).
- **Anti-pigeonhole:** with `MEV_REGWRITE` + reg-automation, any present/future YM2612 register (`$22`, `$27`, `$28`, `$90`, CH3 special mode, …) is reachable without a format break.

---

## 6. SSG-EG
- **Load-time per-op patch byte** (realizes DEFERRED_WORK **E5**'s per-op-patch half; E5's mid-note dedicated-group half stays deferred — see below). Append a 4-byte `fp_ssg_eg` per-op array to `FmPatch`; **pad the record to 32 bytes (power of two)** so `Fm_PatchPtr` becomes a shift-only `add hl,hl` chain instead of the current `mulu`-banned `patch*26` add-chain (+2 ROM bytes/record, smaller+faster hot path). Add `SND_REG_OP_SSG_EG = $90`; add the `$90`-group write in `Fm_PatchLoad`; default `$00` (off) for every existing patch; re-export `fm_patches.inc`, the 68k ROM copy, `sfx_transcode.py`, **and `zyrinx_port.py`** (it hard-codes a 26-byte record).
- **Mid-note SSG-EG** is reachable **now** via `MEV_REGWRITE`/reg-automation (write `$90+op`), so the dedicated 7th `RegDelta` group is **deferred** (mask `$0F` already holds 7 — a cheap later add if a song wants voice-step SSG-EG).
- Provides metallic/buzzy/AY timbres at **zero per-frame cost** (pure hardware once written).

---

## 7. Reserved targets (pitch, pan) — non-breaking allocation
- **Pitch slot (reserved):** would write a contour into `sc_mod_accum` (renderer exists). **Deferred because** a pitch contour and software vibrato both own `sc_mod_accum`; they need an explicit arbitration rule (likely "contour owns the accum while active, vibrato suppressed," mirroring the porta↔vibrato decision in Phase-2-per-note). Designing that correctly is its own small pass.
- **Pan slot (reserved):** would write `sc_pan` (renderer exists, FM-only). Lower musical priority; auto-pan/AMS-FMS depth automation.
- **Format reservation:** allocate the slot-ids and the `{id,cursor,out}` layout in the spec/packer so going live later is +3 B/channel + a renderer hook, no format change.

---

## 8. RAM plan
| Need | Source | Bytes |
|---|---|---|
| slot[1] reg-stream cursor | `sc_mod_ptr` (+2, already allocated, read by nothing) | **0 new** |
| volume contour state | unified `sc_env`/`_cur`/`_out` (+39/40/41, reserved) | **0 new** |
| reg-stream per-frame state (e.g. an "active/disabled" flag) | `sc_pad` (+57) | ≤1 |
| (left for Phase-2 detune) | `sc_detune` (+56) — **untouched** | — |
| reserved pitch/pan slots (when live) | struct growth into the ~73 B gap below `$1B00`, **rounded to keep `SeqChannel` even** (a bare +3 makes it odd → re-misaligns the existing `ds.w` `sc_mod_accum`/`sc_base_freq`/`sc_last_freq`; add a pad byte or grow slots in even pairs) | +3 → +4 |

- Struct stays **58 / even**. No song-buffer reclaim (that would force copy-path songs onto the stream path — an architectural commitment we are not making here).
- Any RAM-layout change ⇒ runtime boot-verify (build asserts alone are insufficient; AS does not auto-align `ds.w`).

---

## 9. Opcode allocation + authoring/tooling
- **Opcodes:** lock `$F3` (MEV_TEMPO), `$F4` (MEV_LFO), `$F5` (MEV_PORTA), `$F6` (MEV_DETUNE) with placeholder/fixed-slot asserts (reserved for Phase-2). **Phase 3 owns `$F7` MEV_FMENV, `$F8` MEV_REGWRITE, `$F9` MEV_MACRO.** Mirror the existing `MEV_*` collision-assert style (the assert `if` blocks near `sound_constants.asm:370-440`, e.g. the `MEV_PAN` collision assert at `:386` — **not** the opcode-equate block at `:356-366`). Each handler obeys the hl-preservation rule.
- **`tools/song_packer.py`:** event classes `FmEnv`, `RegWrite`, `Macro` (arm slot[1]); a **macro-body emitter** (value bytes + `$80/$81/$83`, with `$2A/$2B` reg rejection and control-code-as-data validation); **emit the header `mod_ptr`** (currently hard-NULL at `:679-683`) as a back-patched blob offset (same convention as `cmd_ptr`).
- **Music-legal route gate (DEFERRED_WORK D8):** `$F7 MEV_FMENV` / `$F8 MEV_REGWRITE` / `$F9 MEV_MACRO` (and `MEV_PSGENV`) must be **music-legal** in `song_packer.py`'s route validation. D8's gate is **still unimplemented** — `song_packer.py` has no music-legal/reject-by-route construct today, only `_validate_channel` init-ordering (`:555-610`) — so this phase either implements that gate and whitelists these opcodes, **or** explicitly re-scopes D8. A music song emitting them must NOT silently no-op pre-render.
- **`tools/gen_sound_tables.py`:** `_emit_fm_vol_env_z80` + `_FM_VOL_ENVS`, wired into `emit_asm_z80` alongside `_PSG_VOL_ENVS` → `FmVolEnv_*` in `sound_tables_z80.asm`.
- **Daemon-watched, do NOT touch:** `data/editor/**`, `tools/ojz_strip_gen.py`. `song_packer.py`/`smps_import.py`/`gen_sound_tables.py` are fair game.

---

## 10. Build-time validation (AS asserts)
- `FmPatch_len == 32`; `SeqChannel_len == 58` (even); `SND_SEQ_END` + scratch + trace-ring < `$1B00`.
- `Z80_SOUND_SIZE <= $16F0` after every Z80-code task (flag overflow, don't work around it).
- New opcodes in `$E0–$FF`, no collisions; `$F3–$F6` locked to their reserved values; `$F7/$F8/$F9` distinct.
- `FmVolEnv` map/body bank alignment + size; carrier-mask covers all 8 algorithms.
- Packer: macro bodies reject `$2A`/`$2B` reg targets and control-code-valued data bytes.

---

## 11. Verification (NON-NEGOTIABLE — rendered audio vs S3K where applicable)
Build `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` (plain build excludes all sound). Captures **≤450 frames** (longer freezes the emulator). Oracle MCP = `oracle`.

- **FM carrier swell:** arm an FM volume contour; `tools/vgm_intranote.py` shows the carrier-TL contour move across a held note (high→0 swell-in; oscillating tremolo). Confirm by ear.
- **PSG tremolo:** music PSG volume contour — `sc_psgenv_out`-driven attenuation oscillates.
- **SSG-EG timbre:** a patch with SSG-EG on vs off — audible/spectral metallic difference; zero per-frame cost.
- **Reg-automation:** a slot[1] stream automating a non-critical register (e.g. FB) — confirm the register tracks the body; loop wraps correctly.
- **DAC park safety:** a DAC drum hit **immediately after** a `MEV_REGWRITE`/reg-write — clean playback (the `$2A` re-park survived). The load-bearing check.
- **Regression:** Moving Trucks renders byte/spectrum-faithful (all `sc_mod_ptr`=NULL, `sc_env`=0 → fast paths); DEBUG golden self-test green.
- **Budget:** worst-frame `Sequencer_Frame` cost << DAC ring lead; no new lag (`Lag_Frame_Count`).
- Runtime-boot-verify after any RAM-layout change.

---

## 12. Implementation phasing (each step audible + verifiable, build green)
1. **FM-TL vol-env renderer** — `FmEnvUpdate` + `FmVolEnv_*` table + `gen_sound_tables.py` + `MEV_FMENV` ($F7) arm + `Fm_SetVolume` fold. *Verify: FM swell.* (Completes the volume macro target FM+PSG.)
2. **`MEV_REGWRITE` ($F8)** — inline immediate write + `$2A/$2B` guard + re-park. *Verify: register changes + DAC hit clean.*
3. **SSG-EG** — `FmPatch` 26→32 + `Fm_PatchPtr` shift rewrite + `$90` group in `Fm_PatchLoad` + re-export. *Verify: timbre.*
4. **slot[1] `MacroTick` reg-automation** — make `sc_mod_ptr` real (reader + grammar + commit discipline + arbitration order) + packer `mod_ptr` emission + `MEV_MACRO` ($F9) retrigger. *Verify: looping reg-automation + DAC safety + MT regression.*
5. **Packer macro authoring** — `FmEnv`/`RegWrite`/`Macro` event classes + body emitter + validation + tests. *Verify: a hand-authored test song exercising a swell + a reg-automation renders as authored.*

(Steps 1–3 are independent and each self-contained; 4 depends on nothing but lands the spine; 5 is authoring. Pitch/pan slots reserved throughout.)

---

## 13. Open questions (resolve in writing-plans)
- Exact `sc_pad` use for the reg-stream "active" flag vs encoding "disabled" as `sc_mod_ptr==0`.
- Final `MacroTick` placement: a separate channel pass vs interleaved in the existing `Sequencer_Frame` loop (cost vs simplicity).
- Whether `MEV_MACRO` ($F9) points `sc_mod_ptr` at an absolute (rebased) blob offset operand (2 bytes) — confirm the packer back-patch path matches `cmd_ptr`.
- Re-verify the `$80/$81/$83` grammar against S3K VolEnv tables before treating it as canonical for the generalized format (handoff correction §1.4.5).
- Confirm `FmPatch`→32 re-export covers every consumer (`fm_patches.inc`, the 68k ROM copy, `sfx_transcode.py`, `zyrinx_port.py`).
