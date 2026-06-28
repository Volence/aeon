# Music Expression Engine — Phase 3: Macro/Automation Spine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 3 macro/automation spine — a complete FM+PSG volume-envelope macro target, a slot[1] register-automation stream, an inline raw-register opcode, and SSG-EG — turning the flat opcode stream into a macro engine where future effects are "add a target," not "new opcode + new struct field."

**Architecture:** Two writers feed the existing state-driven `ModUpdate` renderer: (1) **named per-target contour slots** (the unified `sc_env` slot, advanced one entry/frame in `ModUpdate`, independent loops) — the flagship FM-TL + PSG volume envelope; and (2) a **tag-prefixed slot[1] `MacroTick` register-automation stream** on the already-free `sc_mod_ptr` seam for the arbitrary-register long tail. Plus `MEV_REGWRITE` (inline raw write, `$2A/$2B`-guarded) and SSG-EG (load-time per-op patch byte). Owns opcodes `$F7`/`$F8`/`$F9`; **0 new per-channel RAM** (cursor = `sc_mod_ptr`, volume state = the reserved `sc_env` slot, reg-stream flag = `sc_pad`).

**Tech Stack:** AS Macroassembler Z80 (assembled inline under `phase 0`), 68000, Python build tools (`song_packer.py`, `gen_sound_tables.py`). Build: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`. Worktree: `/home/volence/sonic_hacks/aeon-music-expr` (branch `feat/music-expr-p1`). Spec: `docs/superpowers/specs/2026-06-27-music-expr-macro-spine-design.md`.

---

## §0 Integration & Ordering (BINDING — read before executing)

This plan has 5 components (A–E, ~18 tasks). They are mostly independent but share a few integration points. Honor these:

**Build & budget gate.** Build sound with `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` — a plain `./build.sh` EXCLUDES all sound and proves nothing. The HARD Z80 code-size gate is the build's own assert `if Z80_SOUND_SIZE > SND_STATE_BASE ($16F0) -> fatal` (`engine/z80_sound_driver.asm:1472-1474`); a green build means it passed. Wherever a step reads the size informationally, use **`python3 tools/s4budget.py s4.lst s4.bin --summary`** (a bare `s4budget.py` errors on missing args). The five components add ~266 B against ~494 B free; the **controller must run the budget read once on the FULLY-MERGED branch (A+B+C+D+E) and confirm the build assert passes there** — a per-component green proves nothing about the merged total. If the ceiling is hit, STOP and flag for sign-off — do NOT shave the reader.

**Shared-anchor inserts (apply sequentially).** A3 (`$F7 MEV_FMENV`), B1 (`$F8 MEV_REGWRITE`), and D1/D3 (`MEV_MACRO $F9` + `TAG_MAC_*`) all insert into the SAME gap in `sound_constants.asm` (after the `MEV_PSGNOISE` block, before the `MEV_PAN` comment), and A3/B1 append collision asserts after the same SPINREV assert `endif`. Apply them SEQUENTIALLY on the shared branch, re-anchoring each on the (now-extended) surrounding text rather than a fixed line number. They are distinct equates — no content conflict, only a shared insertion point. Each collision assert is FIXED-SLOT (asserts its own opcode == its literal), so every component builds independently without referencing a sibling's symbol.

**python-const ordering (E first).** `test_song_packer.py::TestConstantsSync` asserts every `sound_constants.asm` `MEV_*` / `TAG_MAC_*` equate has a matching python const. So land **E1's python consts (`MEV_FMENV`/`MEV_REGWRITE`/`MEV_MACRO`) + the `TAG_MAC_*` consts first** (they are inert standalone), or merge A–E as a unit and require the python suite green only on the integrated branch. If asm equates land before the python consts, `TestConstantsSync` goes red.

**Intra-component build units (intentional intermediate RED builds).** Run each as ONE uninterrupted unit before any green-build gate: **A1→A2** (A1's `FmEnvUpdate` references A2's `FmVolEnv_Resolve`/`FmVolEnvCtl_*`; first green build is A2) and **C1→C2→C3** (FmPatch data asserts are red until C3 regenerates the patch banks; first green build is C3). Do NOT treat these documented intermediate reds as failures.

**Cross-task wire contract (already baked into the tasks below — do not deviate).** `TAG_MAC_NEXT=$E0, TAG_MAC_REG=$E1, TAG_MAC_LOOP=$E2, TAG_MAC_END=$E3` — IDENTICAL bytes in the D asm reader and the E packer emitter. `TAG_MAC_LOOP` = the tag byte `$E2` + a **2-byte BIG-ENDIAN body-start blob offset**; the `MacroTick` reader adds `Snd_SongBase` to it (the same "BE offset, handler adds base" convention as `MEV_MACRO`). `test_song_packer.py::TestConstantsSync` is extended to assert the packer's `TAG_MAC_*` mirror the asm equates, so they can never silently drift.

**One pre-existing const (E3).** `MEV_SPINREV_RESET = 0xF1` ALREADY exists in `song_packer.py` (line 69) — E3's music-illegal gate REFERENCES it (`_MUSIC_ILLEGAL_OPCODES = frozenset({MEV_SPINREV_RESET})`), it does NOT redefine it.

**Verification division.** Implementers do edit + build + build-asserts + python unit tests + commit. The CONTROLLER runs ALL oracle/emulator verification (VGM ≤450 frames, `tools/vgm_intranote.py`) — the "controller-verify handoff" steps describe what to check and contain no emulator calls. Per the project rule, sound is verified by **rendered audio measured against S3K where applicable**, never a register proxy alone.

**Commits.** `git add` EXACT paths only (never `-A`/globs — there is unrelated untracked WIP in the tree). Messages end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Build green + tests green before each commit.

---

## Component A — FM-TL volume envelope (flagship)

### Task A1: FM-TL vol-env renderer — `Fm_SetVolume` fold + `FmEnvUpdate` + `ModUpdate` FM wiring + FM cursor reset (INERT; `sc_env`=0)

This task adds the FM carrier-TL volume-envelope renderer that mirrors the shipped PSG env (`PsgEnvUpdate`). It is INERT until a song arms `sc_env` (A3) — every `sc_env_out`/`sc_env` read has an `or a / jr z` fast path that is byte-identical to no-envelope, so Moving Trucks stays byte/spectrum-faithful.

**Dependency note (verified against the struck Group C plan, lines 789, 807):** `FmEnvUpdate` references `FmVolEnv_Resolve` and `FmVolEnvCtl_Loop/Sustain/Rest`, which are DEFINED in Task A2. Therefore **A1 commits its source edits but the first green build is in A2** — do NOT run `./build.sh` at the end of A1 (it will fail to resolve `FmVolEnv_Resolve`/`FmVolEnvCtl_*`). A1's "verify" is purely the textual edits landing; A2 builds the pair together.

**Files**
- `/home/volence/sonic_hacks/aeon-music-expr/engine/sound_fm.asm` — `Fm_SetVolume` env fold (after `ld (Fm_ScratchLog), a` at :354, BEFORE the duck block at :356); `Fm_NoteOnFreq` cursor reset (after `call Mod_ReArm` :698, before `.keyon:` :699).
- `/home/volence/sonic_hacks/aeon-music-expr/engine/sound_sequencer.asm` — `FmEnvUpdate` (after `PsgEnvUpdate`'s `.rest`/`jp Psg_NoteOff` at :359); `ModUpdate` FM-path wiring (after `.vibrato_done:` at :192).

**Steps**

1. [ ] `engine/sound_fm.asm` — fold `sc_env_out` into `Fm_ScratchLog`. The real anchor is the duck block opening: line :354 is `ld (Fm_ScratchLog), a ; stash log delta` and line :356 begins the `; --- Phase 5a music ducking` comment. Insert the fold BETWEEN them. Find the exact line:
   ```
           ld      (Fm_ScratchLog), a       ; stash log delta
   ```
   and insert immediately after it (before the `; --- Phase 5a music ducking (spec §7)` comment line):
   ```

           ; --- FM TL VOLUME ENVELOPE (spec §4 flagship): add the per-frame env
           ; attenuation delta to the carrier-TL delta (mirror of Psg_SetVolume's env
           ; fold, sound_psg.asm:317-325). Folded HERE, BEFORE the duck/master-fade fold,
           ; so env + duck compose. The per-op carrier loop (:412-481) reads Fm_ScratchLog
           ; as a positive 0..$7F delta (ld b,0 sign-assumption :446), so we clamp to $7F.
           ; sc_env_out is the unified slot (=sc_psgenv_out, +41); 0 on a no-env channel ->
           ; the or a/jr z fast path is byte-identical to no envelope (MT regression-safe).
           ; Reaches CARRIER ops only for free (Fm_ScratchLog only flows to carrier TLs).
           ld      a, (ix+sc_env_out)
           or      a
           jr      z, .env_done
           ld      hl, Fm_ScratchLog
           add     a, (hl)                  ; env delta + log delta
           jr      nc, .env_ok
           ld      a, SND_FM_TL_MAX         ; carry out of 8 bits -> clamp to $7F (silent)
   .env_ok:
           cp      SND_FM_TL_MAX+1
           jr      c, .env_store
           ld      a, SND_FM_TL_MAX         ; clamp the summed delta to $7F
   .env_store:
           ld      (hl), a                  ; env-folded carrier-TL delta
   .env_done:
   ```
   (`.env_done`/`.env_ok`/`.env_store` are unique within `Fm_SetVolume` — verified no such locals exist in `sound_fm.asm`; AS resets `.local` scope at each global label so they don't collide with the identically-named locals in `Psg_SetVolume` or `FmEnvUpdate`. `SND_FM_TL_MAX = $7F` verified at `sound_constants.asm:85`.)

2. [ ] `engine/sound_sequencer.asm` — add `FmEnvUpdate` immediately AFTER `PsgEnvUpdate`'s `.rest` tail. The real anchor is line :359 `jp Psg_NoteOff ; silence this PSG channel (tail-call, preserves ix)` (end of `PsgEnvUpdate`). Insert this complete routine right after that line (before the `; ----` banner for `Mod_ReArm` at :361):
   ```

   ; ----------------------------------------------------------------------
   ; FmEnvUpdate — advance one FM channel's carrier-TL volume-envelope contour by one
   ; frame and re-emit the channel volume so the new attenuation delta takes effect
   ; (folded into Fm_SetVolume's Fm_ScratchLog). The FM mirror of PsgEnvUpdate; the
   ; UNIFIED sc_env/sc_env_cur/sc_env_out slot (+39/+40/+41) serves FM (here) xor PSG
   ; (PsgEnvUpdate) — a channel is FM xor PSG.
   ; Body bytes (mirror PSG, sound_tables_z80.asm): plain value -> sc_env_out + advance;
   ; $80 -> loop cursor to 0 + re-read; $81 -> sustain-hold (keep last out, no advance);
   ; $83 -> TL-silence the tail (sc_env_out = $7F, park the cursor). NOTE the deliberate
   ; deviation from PSG's $83 key-off: FM has its own EG, so a key-off would cut the
   ; release tail; a TL-silence preserves it (documented in the plan's Self-review).
   ; In: ix = FM channel, sc_env != 0. Clobbers af,bc,de,hl. Preserves ix.
   ; ----------------------------------------------------------------------
   FmEnvUpdate:
           ld      a, (ix+sc_env)           ; 1-based FM env id
           call    FmVolEnv_Resolve         ; hl = body base; carry set = unknown id -> bail
           ret     c
   .reread:
           ld      a, (ix+sc_env_cur)       ; a = cursor
           ld      e, a
           ld      d, 0
           add     hl, de                   ; hl = &body[cursor]
           ld      a, (hl)                  ; a = body byte
           cp      FmVolEnvCtl_Loop         ; $80 -> loop cursor to 0
           jr      z, .loop
           cp      FmVolEnvCtl_Sustain      ; $81 -> sustain-hold (no advance, keep last out)
           jr      z, .sustain
           cp      FmVolEnvCtl_Rest         ; $83 -> TL-silence the tail
           jr      z, .rest
           ; --- plain value: store as the carrier-TL atten delta, advance the cursor ---
           ld      (ix+sc_env_out), a
           inc     (ix+sc_env_cur)
   .emit:
           ; re-emit the channel volume so the new sc_env_out delta lands this frame.
           ld      a, (ix+sc_volume)
           jp      Fm_SetVolume             ; folds sc_env_out into the carrier TLs; preserves ix
   .loop:
           ld      (ix+sc_env_cur), 0       ; cursor -> 0
           ld      a, (ix+sc_env)           ; recompute body base (hl was advanced above)
           call    FmVolEnv_Resolve
           ret     c
           jr      .reread
   .sustain:
           ; hold last sc_env_out (no advance) — re-emit so the held atten stays applied.
           jr      .emit
   .rest:
           ; FM $83 = TL-silence (NOT key-off): sc_env_out = $7F so the carrier TLs go
           ; silent while the YM EG release continues. The cursor stays parked on the rest
           ; byte so it re-silences each frame until the next attack resets sc_env_cur.
           ld      (ix+sc_env_out), SND_FM_TL_MAX
           jr      .emit
   ```
   (`FmVolEnv_Resolve` + `FmVolEnvCtl_Loop/Sustain/Rest` are defined in A2 — that is why A1 does not build alone. `sc_volume = +8` verified `sound_constants.asm:881`; `sc_env`/`sc_env_cur`/`sc_env_out` alias `sc_psgenv*` at +39/+40/+41 verified `sound_constants.asm:908-910`.)

3. [ ] `engine/sound_sequencer.asm` — wire `FmEnvUpdate` into the `ModUpdate` FM path. The real anchor is line :192 `.vibrato_done:` (immediately after the `call nz, Mod_ApplyVibrato` at :191). Insert this block right after the `.vibrato_done:` label and before the `; --- NOTE-FILL` comment at :196:
   ```
           ; --- FM TL VOLUME ENVELOPE (spec §4 flagship): advance the carrier-TL contour
           ; + re-emit volume (folds sc_env_out in Fm_SetVolume). Runs EVERY frame (held
           ; notes too) so the swell/tremolo evolves across a held note. sc_env==0 -> one
           ; test then skip (byte-identical to no envelope; MT regression-safe).
           ld      a, (ix+sc_env)
           or      a
           call    nz, FmEnvUpdate          ; advance + re-emit carrier TLs (preserves ix)
   ```
   (This is the ONLY per-frame `Fm_SetVolume` driver on the FM path — handoff correction §1.4.1: FM volume has no other per-frame renderer, so this is what introduces per-frame carrier-TL motion. Placed AFTER vibrato so pitch-mod and the vol-env both render; the existing note-fill/re-key folds below are unchanged.)

4. [ ] `engine/sound_fm.asm` — reset the FM env cursor on every FM attack. The real anchor is line :698 `call Mod_ReArm ; per-note re-arm (no-op if sc_mod_ctrl==0)` followed by `.keyon:` at :699. Insert the cursor reset BETWEEN them (after the `call Mod_ReArm` line, before `.keyon:`):
   ```
           ld      (ix+sc_env_cur), 0       ; restart the FM vol-env contour on this attack
   ```
   (Mirrors `Psg_EnvCursorReset` (`sound_psg.asm:110-112`) which the PSG note-on calls. Harmless when `sc_env==0` (the cursor is unused). `Fm_NoteOnFreq` is the single chokepoint for every FM key-on — note-on, `MEV_NOTE_RAW`, and the `ModUpdate` re-key all flow through it — so one reset here covers them all. Placed before `.keyon:` so it runs on every attack path.)

5. [ ] **Build:** DEFERRED to Task A2 (this task references the A2-defined `FmVolEnv_Resolve`/`FmVolEnvCtl_*`; building now fails on undefined symbols — this is expected and documented). Do NOT run `./build.sh` here.

6. [ ] **Commit:**
   ```
   git add engine/sound_fm.asm engine/sound_sequencer.asm
   git commit -m "$(cat <<'EOF'
   sound: FM TL vol-env renderer (FmEnvUpdate) + Fm_SetVolume fold + ModUpdate FM wiring

   Mirrors the shipped PSG vol-env on the unified sc_env slot; INERT (sc_env=0
   fast path keeps Moving Trucks byte/spectrum-faithful). Table + resolver land
   in the next commit (FmVolEnv_*), so the build is green from there.

   Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
   EOF
   )"
   ```

---

### Task A2: `FmVolEnv_*` engine table (gen_sound_tables.py) + `FmVolEnv_Resolve` + python test — FIRST GREEN BUILD

This task generates the FM vol-env id→body map (mirror of `PsgVolEnv_*`) into the banked `$8000`-window table file via `gen_sound_tables.py`, adds the `FmVolEnv_Resolve` linear-scan resolver (mirror of `PsgVolEnv_Resolve`), and lands the first green build of the A1+A2 pair. The table lives in the co-located bank (`main.asm:269` includes `engine/sound_tables_z80.asm` under `phase 08000h`), NOT the `$16F0` Z80-code budget; only `FmVolEnv_Resolve` + `FmEnvUpdate` are Z80 code.

**TDD:** write the generator test first (it exercises `emit_asm_z80()`), watch it fail, then implement.

**Files**
- `/home/volence/sonic_hacks/aeon-music-expr/tools/gen_sound_tables.py` — `_FM_VOL_ENVS` (after `_PSG_VOL_ENVS` at :327) + `_emit_fm_vol_env_z80()` (after `_emit_psg_vol_env_z80` at :377) + wire into `emit_asm_z80()` (after the PSG env append at :292).
- `/home/volence/sonic_hacks/aeon-music-expr/engine/sound_tables_z80.asm` — GENERATED output (do NOT hand-edit; regenerate via `python3 tools/gen_sound_tables.py`).
- `/home/volence/sonic_hacks/aeon-music-expr/engine/sound_psg.asm` — `FmVolEnv_Resolve` (after `PsgVolEnv_Resolve` at :140).
- `/home/volence/sonic_hacks/aeon-music-expr/tools/test_gen_sound_tables.py` — new `TestFmVolEnvTable` class.

**Steps**

1. [ ] **Write the failing test first.** In `tools/test_gen_sound_tables.py`, add a new test class after `TestEmitAsmZ80Matches68k` (before the `if __name__ == "__main__":` at :268). It imports `_FM_VOL_ENVS` from the module and asserts the emitted Z80 ASM carries the FM env map + bodies:
   ```python
   class TestFmVolEnvTable(unittest.TestCase):
       """The FM TL vol-env map mirrors PsgVolEnv_*: parallel id/ptr arrays + bodies,
       emitted into the banked sound_tables_z80.asm by emit_asm_z80()."""

       def setUp(self):
           from gen_sound_tables import _FM_VOL_ENVS
           self.envs = _FM_VOL_ENVS
           self.asmz80 = emit_asm_z80()

       def test_ids_ptrs_count_match(self):
           # parallel arrays: one id byte and one body ptr per env.
           self.assertGreaterEqual(len(self.envs), 1)
           self.assertTrue(all(0 < e[0] <= 0xFF for e in self.envs),
                           "FM env ids must be 1-based bytes")

       def test_emit_has_map_and_bodies(self):
           a = self.asmz80
           self.assertIn("FmVolEnv_Ids:", a)
           self.assertIn("FmVolEnv_Ids_End:", a)
           self.assertIn("FmVolEnv_Ptrs:", a)
           self.assertIn("FmVolEnv_Ptrs_End:", a)
           self.assertIn("FMVOLENV_COUNT = FmVolEnv_Ids_End - FmVolEnv_Ids", a)
           self.assertIn("FmVolEnvCtl_Loop    = 80h", a)
           self.assertIn("FmVolEnvCtl_Sustain = 81h", a)
           self.assertIn("FmVolEnvCtl_Rest    = 83h", a)
           for env_id, _label, _body in self.envs:
               self.assertIn("FmVolEnv_%02X:" % env_id, a,
                             "missing body label for id %#x" % env_id)

       def test_emit_count_assert_present(self):
           # the generated bank must self-check id/ptr parity at assemble time.
           self.assertIn(
               'error "FmVolEnv_Ptrs entry count mismatch vs FmVolEnv_Ids"',
               self.asmz80)

       def test_fm_block_after_psg_block(self):
           # FM env block is appended AFTER the PSG env block in the same bank.
           a = self.asmz80
           self.assertLess(a.index("PsgVolEnv_Ids:"), a.index("FmVolEnv_Ids:"))
   ```
   Run it and watch it fail (no `_FM_VOL_ENVS`):
   ```
   python3 -m pytest tools/test_gen_sound_tables.py::TestFmVolEnvTable -q
   ```
   Expected: `ImportError`/`AttributeError` on `_FM_VOL_ENVS` (red).

2. [ ] `tools/gen_sound_tables.py` — add the FM env bodies. After the `_PSG_VOL_ENVS = [ ... ]` list (closing `]` at :327), insert:
   ```python


   # --- FM TL volume-envelope table (spec §4 flagship; the Flamedriver zDoFMVolEnv
   # analogue) -------------------------------------------------------------------
   # Same byte format as the PSG vol-env: per-frame CARRIER-TL attenuation deltas
   # (higher = quieter) + control bytes $80 loop / $81 sustain-hold / $83 rest
   # (FM rest = TL-silence, not key-off). Engine id is 1-based. These are ENGINE
   # DEFAULTS for authoring (S3K has no FM vol-env to import); add more as songs
   # need them. The renderer (FmEnvUpdate) folds the delta into the CARRIER TLs.
   _FM_VOL_ENVS = [
       # id    label          body
       (0x01, "fmEnv_swell",  [0x20, 0x18, 0x12, 0x0C, 0x08, 0x05, 0x02, 0x00,
                               _CTL_SUSTAIN]),                 # swell-IN: quiet->bright, hold
       (0x02, "fmEnv_decay",  [0x00, 0x02, 0x04, 0x06, 0x08, 0x0C, 0x10, 0x18,
                               _CTL_SUSTAIN]),                 # decay: bright->quiet, hold
       (0x03, "fmEnv_trem",   [0x00, 0x02, 0x04, 0x06, 0x04, 0x02,
                               _CTL_LOOP]),                    # tremolo: oscillate, loop
   ]
   ```
   (`_CTL_LOOP`/`_CTL_SUSTAIN`/`_CTL_REST` already defined at `gen_sound_tables.py:305-307`. All body data bytes are `< 0x80` so they never collide with the control codes — the same invariant the PSG bodies hold.)

3. [ ] `tools/gen_sound_tables.py` — add the emitter. After `_emit_psg_vol_env_z80()` returns (the `return out` at :376, before `def main():` at :380), insert:
   ```python

   def _emit_fm_vol_env_z80() -> list:
       """Emit the FM vol-env id->body map + bodies (Z80 syntax, direct-addressed).

       Mirrors _emit_psg_vol_env_z80: a tiny parallel id-byte / body-ptr array the
       reader (FmVolEnv_Resolve, engine/sound_psg.asm) linearly scans, plus the
       bodies. Lands in the co-located $8000-window bank (not the Z80-code budget).
       """
       out = []
       out.append("; --- FM TL volume-envelope table (spec section 4 flagship) -------------------")
       out.append("; Same format as the PSG vol-env (atten deltas + 80h/81h/83h ctl), but the")
       out.append("; renderer (FmEnvUpdate) folds the delta into the CARRIER TLs (Fm_SetVolume).")
       out.append("; FM rest (83h) = TL-silence (the YM EG release continues), not a key-off.")
       out.append("FmVolEnvCtl_Loop    = 80h")
       out.append("FmVolEnvCtl_Sustain = 81h")
       out.append("FmVolEnvCtl_Rest    = 83h")
       out.append("")
       ids = ", ".join(_z80_byte(e[0]) for e in _FM_VOL_ENVS)
       ptrs = ", ".join("FmVolEnv_%02X" % e[0] for e in _FM_VOL_ENVS)
       out.append("FmVolEnv_Ids:    db %s" % ids)
       out.append("FmVolEnv_Ids_End:")
       out.append("FmVolEnv_Ptrs:   dw %s" % ptrs)
       out.append("FmVolEnv_Ptrs_End:")
       out.append("")
       out.append("FMVOLENV_COUNT = FmVolEnv_Ids_End - FmVolEnv_Ids")
       out.append("        if (FmVolEnv_Ptrs_End - FmVolEnv_Ptrs) <> FMVOLENV_COUNT*2")
       out.append('          error "FmVolEnv_Ptrs entry count mismatch vs FmVolEnv_Ids"')
       out.append("        endif")
       out.append("")
       for env_id, label, body in _FM_VOL_ENVS:
           body_toks = ", ".join(
               {_CTL_LOOP: "FmVolEnvCtl_Loop",
                _CTL_SUSTAIN: "FmVolEnvCtl_Sustain",
                _CTL_REST: "FmVolEnvCtl_Rest"}.get(b, _z80_byte(b))
               for b in body)
           out.append("FmVolEnv_%02X:   db %s   ; %s" % (env_id, body_toks, label))
       out.append("")
       return out
   ```

4. [ ] `tools/gen_sound_tables.py` — wire the emitter into `emit_asm_z80()`. The real anchor is line :292 `out.extend(_emit_psg_vol_env_z80())` followed by `return "\n".join(out)` at :293. Change:
   ```python
       out.extend(_emit_psg_vol_env_z80())
       return "\n".join(out)
   ```
   to:
   ```python
       out.extend(_emit_psg_vol_env_z80())
       out.extend(_emit_fm_vol_env_z80())
       return "\n".join(out)
   ```

5. [ ] **Run the generator test (now green):**
   ```
   python3 -m pytest tools/test_gen_sound_tables.py -q
   ```
   Expected: all pass (the new `TestFmVolEnvTable` 4 tests + the existing 24).

6. [ ] **Regenerate the table file:**
   ```
   cd /home/volence/sonic_hacks/aeon-music-expr && python3 tools/gen_sound_tables.py
   ```
   Expected output: `wrote .../data/sound/sound_tables.asm` and `wrote .../engine/sound_tables_z80.asm`. Confirm the FM block landed:
   ```
   grep -n "FmVolEnv_Ids:\|FmVolEnv_01:\|FMVOLENV_COUNT\|FmVolEnvCtl_Loop" engine/sound_tables_z80.asm
   ```
   Expected: `FmVolEnv_Ids:`, `FmVolEnv_01:`, `FmVolEnv_02:`, `FmVolEnv_03:`, `FMVOLENV_COUNT = ...`, and `FmVolEnvCtl_Loop = 80h` all present, AFTER the `PsgVolEnv_*` block.

7. [ ] `engine/sound_psg.asm` — add `FmVolEnv_Resolve`. The real anchor is the end of `PsgVolEnv_Resolve` at :140 (`ret` after the `or a ; carry clear` at :139), followed by the `; ----` banner for `Psg_NoteOn` at :142. Insert this complete routine between :140 and :142:
   ```

   ; ----------------------------------------------------------------------
   ; FmVolEnv_Resolve — map a 1-based FM vol-env id (a) to its body ptr (hl) via the
   ; FmVolEnv_Ids/FmVolEnv_Ptrs parallel arrays (engine/sound_tables_z80.asm, banked
   ; $8000 window). The FM mirror of PsgVolEnv_Resolve.
   ; Out: carry clear + hl = body base on a match; carry set on an unknown id.
   ; In: a = 1-based env id. Clobbers af,bc,de,hl. Preserves ix.
   ; ----------------------------------------------------------------------
   FmVolEnv_Resolve:
           ld      b, FMVOLENV_COUNT
           ld      hl, FmVolEnv_Ids         ; banked table; label = its $8000-window ptr
           ld      de, FmVolEnv_Ptrs        ; banked ptr array (entries are window ptrs)
   .scan:
           cp      (hl)
           jr      z, .found
           inc     hl                       ; next id byte
           inc     de
           inc     de                       ; next ptr (2 bytes)
           djnz    .scan
           scf                              ; not found
           ret
   .found:
           ex      de, hl                   ; hl = &ptr entry
           ld      e, (hl)
           inc     hl
           ld      d, (hl)
           ex      de, hl                   ; hl = body base
           or      a                        ; carry clear
           ret
   ```
   (Cross-file `call FmVolEnv_Resolve` from `FmEnvUpdate` in `sound_sequencer.asm` is fine — exactly how `PsgEnvUpdate` calls `PsgVolEnv_Resolve` cross-file today. `FMVOLENV_COUNT`, `FmVolEnv_Ids`, `FmVolEnv_Ptrs` are the generated symbols from step 3.)

8. [ ] **Build (first green build of the A1+A2 pair):**
   ```
   cd /home/volence/sonic_hacks/aeon-music-expr && SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh
   ```
   Expected: build succeeds (`s4.bin` produced, `s4.log` no errors). The generated `if (FmVolEnv_Ptrs_End - FmVolEnv_Ptrs) <> FMVOLENV_COUNT*2` count assert passes; the `Z80_SOUND_SIZE > SND_STATE_BASE` fatal at `z80_sound_driver.asm:1471-1473` does NOT trip.

9. [ ] **Budget check:**
   ```
   cd /home/volence/sonic_hacks/aeon-music-expr && python3 tools/s4budget.py s4.lst s4.bin --summary
   ```
   Expected: the Z80 sound size is reported `<= $16F0` ($16F0 = 5872). `FmEnvUpdate` (~50 B) + `FmVolEnv_Resolve` (~25 B) + the `Fm_SetVolume` fold (~25 B) + the `ModUpdate`/`Fm_NoteOnFreq` hooks (~15 B) is ~115 Z80-code bytes; the table is in the co-located bank, not the Z80-code budget. FLAG any overflow rather than working around it.

10. [ ] **Controller handoff:** Moving Trucks must remain byte/spectrum-faithful — all `sc_env==0` so the `Fm_SetVolume` `or a/jr z` fold and the `ModUpdate` `or a/call nz` gate are byte-identical to no envelope. (The controller verifies this in the emulator per Task A4; implementer does NOT run the emulator.)

11. [ ] **Commit:**
   ```
   git add tools/gen_sound_tables.py engine/sound_tables_z80.asm data/sound/sound_tables.asm engine/sound_psg.asm tools/test_gen_sound_tables.py
   git commit -m "$(cat <<'EOF'
   sound: FmVolEnv engine table (gen_sound_tables) + FmVolEnv_Resolve

   FM TL vol-env id->body map mirroring PsgVolEnv_* (swell/decay/tremolo engine
   defaults), generated into the banked sound_tables_z80.asm; linear-scan resolver
   mirrors PsgVolEnv_Resolve. First green build of the FmEnvUpdate renderer pair.

   Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
   EOF
   )"
   ```

---

### Task A3: `MEV_FMENV` ($F7) opcode + dispatch to shared `Seq_Op_PsgEnv` + constant/assert

This task arms the FM vol-env from a slot[0] stream. `MEV_FMENV` ($F7) sets the unified `sc_env` slot via the SHARED `Seq_Op_PsgEnv` handler (which writes `sc_psgenv`==`sc_env` + `sc_psgenv_cur`==`sc_env_cur` regardless of route); the RENDERER picks `FmVolEnv` vs `PsgVolEnv` by `SCF_IS_FM_B`. No new handler is needed.

**Files**
- `/home/volence/sonic_hacks/aeon-music-expr/sound_constants.asm` — `MEV_FMENV` equate + collision/fixed-slot asserts.
- `/home/volence/sonic_hacks/aeon-music-expr/engine/sound_sequencer.asm` — `SeqOpcodeTable` `$F7` slot (:1214) → `Seq_Op_PsgEnv`.

**Steps**

1. [ ] `sound_constants.asm` — add the `MEV_FMENV` equate. The real anchor: the `MEV_PSGNOISE = $F2` equate at :366-368 is the last expression opcode before the `; --- MEV_PAN / MEV_OPBIAS range + collision asserts` block at :370. Insert the equate immediately after the `MEV_PSGNOISE` comment lines (after line :368, before the blank line preceding :370):
   ```

   ; --- Phase 3 macro spine: FM TL vol-env arm (spec §4 flagship) -----------------
   ; $F7-$F9 are owned by Phase 3 ($F3-$F6 stay RESERVED for Phase-2 plans). MEV_FMENV
   ; sets the unified sc_env slot (shared with MEV_PSGENV via Seq_Op_PsgEnv); the
   ; ModUpdate renderer picks FmVolEnv (FM route) vs PsgVolEnv (PSG route) by SCF_IS_FM_B.
   MEV_FMENV         = $F7   ; + env_id : set the channel's FM TL vol-env id (FM route;
                             ;   1-based, 0=none; shares sc_env with MEV_PSGENV)
   ```

2. [ ] `sound_constants.asm` — add the fixed-slot + collision assert, mirroring the existing `MEV_*` assert blocks (the `if ... error` style near :370-467, e.g. the `MEV_PSGENV/MODSET/SPINREV*` block at :449-457). Place it immediately after the `MEV_PSGENV/MODSET/SPINREV*` assert block's `endif` at :467 (before the `; opcode ranges must not overlap` comment at :469):
   ```

           ; --- MEV_FMENV ($F7) range + fixed-slot + collision asserts (Phase 3 §4) ---
           ; A command opcode (> MEV_NOTE_MAX), inside the $E0-$FF coordination block,
           ; pinned to $F7, and clear of every allocated $E0-$FF opcode AND the
           ; Phase-2-reserved $F3-$F6 (so a later Phase-2 plan landing $F5/$F6 cannot
           ; alias us — a duplicate-slot would be a hard error here, not a silent override).
           if MEV_FMENV <= MEV_NOTE_MAX
             error "MEV_FMENV (\{MEV_FMENV}) must be a command opcode (> MEV_NOTE_MAX)"
           endif
           if (MEV_FMENV < MEV_VOL) || (MEV_FMENV > MEV_END)
             error "MEV_FMENV (\{MEV_FMENV}) must be inside the $E0-$FF coordination block"
           endif
           if MEV_FMENV <> $F7
             error "MEV_FMENV (\{MEV_FMENV}) must be $F7 (the Phase-3 macro-spine slot)"
           endif
           if (MEV_FMENV = MEV_VOL) || (MEV_FMENV = MEV_PATCH) || (MEV_FMENV = MEV_DAC) || (MEV_FMENV = MEV_NOTE_DUR) || (MEV_FMENV = MEV_PAN) || (MEV_FMENV = MEV_REPEAT_START) || (MEV_FMENV = MEV_REPEAT_END) || (MEV_FMENV = MEV_NOTE_RAW) || (MEV_FMENV = MEV_PITCHENV) || (MEV_FMENV = MEV_OPBIAS) || (MEV_FMENV = MEV_REGDELTA) || (MEV_FMENV = MEV_PSGENV) || (MEV_FMENV = MEV_MODSET) || (MEV_FMENV = MEV_NOTEFILL) || (MEV_FMENV = MEV_LOOP_POINT) || (MEV_FMENV = MEV_JUMP) || (MEV_FMENV = MEV_SPINREV) || (MEV_FMENV = MEV_SPINREV_RESET) || (MEV_FMENV = MEV_PSGNOISE) || (MEV_FMENV = MEV_END)
             error "MEV_FMENV (\{MEV_FMENV}) collides with an allocated $E0-$FF opcode"
           endif
   ```
   (Mirrors the `MEV_REGDELTA` fixed-slot assert at :431-433 and the `MEV_PSGENV` collision list at :459-461. All referenced `MEV_*` symbols are defined earlier in the same file — verified `MEV_VOL=$E0`…`MEV_PSGNOISE=$F2`, `MEV_END=$FF`.)

3. [ ] `engine/sound_sequencer.asm` — point the `$F7` dispatch slot at the shared handler. The real anchor is line :1214 `dw Seq_BadOpcode ; $F7 reserved` in `SeqOpcodeTable`. Replace it:
   ```
           dw      Seq_BadOpcode            ; $F7 reserved
   ```
   with:
   ```
           dw      Seq_Op_PsgEnv            ; $F7 MEV_FMENV (shared handler: sets the unified
                                            ;   sc_env slot + resets sc_env_cur; ModUpdate
                                            ;   picks FmVolEnv vs PsgVolEnv by SCF_IS_FM_B)
   ```
   (No new handler: `Seq_Op_PsgEnv` (`:678-683`) does `ld (ix+sc_psgenv),a` + `ld (ix+sc_psgenv_cur),0` — and `sc_psgenv`==`sc_env`, `sc_psgenv_cur`==`sc_env_cur` (aliases, `sound_constants.asm:903-910`) — exactly an FM-env arm. The id namespace differs (FmVolEnv ids vs PsgVolEnv ids) but the renderer resolves by route, so they never cross.)

4. [ ] **Build:**
   ```
   cd /home/volence/sonic_hacks/aeon-music-expr && SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh
   ```
   Expected: green. The new `MEV_FMENV` range/fixed-slot/collision asserts all pass; `Z80_SOUND_SIZE <= SND_STATE_BASE` holds (dispatch-slot retarget adds 0 code bytes — it reuses `Seq_Op_PsgEnv`).

5. [ ] **Budget check:**
   ```
   cd /home/volence/sonic_hacks/aeon-music-expr && python3 tools/s4budget.py s4.lst s4.bin --summary
   ```
   Expected: Z80 size unchanged from A2 (no new handler), still `<= $16F0`.

6. [ ] **Controller handoff:** the controller will poke `$F7 $01` + an FM note into a live music FM stream and confirm `sc_env` (the +39 byte of that SeqChannel) becomes `1`; the full audible swell check is Task A4. (Implementer does NOT run the emulator.)

7. [ ] **Commit:**
   ```
   git add sound_constants.asm engine/sound_sequencer.asm
   git commit -m "$(cat <<'EOF'
   sound: MEV_FMENV ($F7) opcode + dispatch to shared Seq_Op_PsgEnv

   Arms the FM TL vol-env from slot[0]; sets the unified sc_env slot via the shared
   PSG-env handler (renderer picks FmVolEnv vs PsgVolEnv by route). Fixed-slot +
   collision asserts mirror the existing MEV_* blocks; $F3-$F6 stay reserved.

   Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
   EOF
   )"
   ```

---

### Task A4: Build verification + controller-verify handoff for an FM swell

This task is the verification gate for Component A. Per the verification division, the IMPLEMENTER runs build + build-asserts + a final budget check and writes a crisp statement of what the CONTROLLER verifies in the emulator. The implementer does NOT call any emulator/oracle MCP tool.

**Steps**

1. [ ] **Full clean build with sound:**
   ```
   cd /home/volence/sonic_hacks/aeon-music-expr && SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh
   ```
   Expected: green; `s4.bin` produced; `s4.log` free of errors.

2. [ ] **All build-asserts confirmed present (grep the source, not a re-run):**
   ```
   cd /home/volence/sonic_hacks/aeon-music-expr && \
     grep -n "FmVolEnv_Ptrs entry count mismatch" engine/sound_tables_z80.asm && \
     grep -n 'MEV_FMENV (\\{MEV_FMENV}) must be \$F7' sound_constants.asm && \
     grep -n "Z80_SOUND_SIZE > SND_STATE_BASE" engine/z80_sound_driver.asm
   ```
   Expected: all three present (the FM table parity assert, the `$F7` fixed-slot assert, the Z80 budget fatal).

3. [ ] **Python tests green:**
   ```
   cd /home/volence/sonic_hacks/aeon-music-expr && python3 -m pytest tools/test_song_packer.py tools/test_gen_sound_tables.py -q
   ```
   Expected: all pass (includes the new `TestFmVolEnvTable`).

4. [ ] **Final budget check:**
   ```
   cd /home/volence/sonic_hacks/aeon-music-expr && python3 tools/s4budget.py s4.lst s4.bin --summary
   ```
   Expected: Z80 sound size `<= $16F0`. Record the exact reported size in the commit/PR.

5. [ ] **Controller-verify handoff — what the CONTROLLER checks in the oracle emulator** (NOT run by the implementer; capture all VGMs `<=450 frames`):
   - **FM carrier swell:** arm an FM volume contour on a held music FM note — either author a tiny DEBUG test phrase (one FM channel: `Patch`, the Component-E `FmEnv(1)` swell, a long held note, looping) and point the DEBUG boot at it, OR `mcp__oracle__emulator_z80_write` `sc_env=1` (the +39 byte) on a live held music FM channel mid-playback. Capture a VGM and run `tools/vgm_intranote.py`: it must report **carrier-TL movement between key-ons** tracking the `fmEnv_swell` body (TL falling = brightening across the held note). Switch to `sc_env=3` (`fmEnv_trem`) and confirm **oscillating** carrier TL at the loop period. Confirm **modulator TLs do NOT move** (carrier-only via `CarrierMaskTableZ`). Confirm by ear.
   - **Regression (the load-bearing check):** `SONG_MOVINGTRUCKS` renders byte/spectrum-faithful — all `sc_env==0` so the `Fm_SetVolume` fold + `ModUpdate` gate hit their fast paths; DEBUG golden self-test green; no new lag (`Lag_Frame_Count`).
   - **PSG unaffected:** `SONG_HCZ2` PSG vol-envs still run `PsgEnvUpdate` (the shared `sc_env` slot is FM-xor-PSG; PSG channels are untouched by the FM path).

6. [ ] **Commit (notes only — record the verification numbers in the PR after the controller reports them):**
   ```
   git add docs/superpowers/plans/2026-06-27-music-expr-macro-spine-plan.md
   git commit -m "$(cat <<'EOF'
   sound: Component A verification gate (FM TL vol-env swell handoff)

   Build green; FmVolEnv parity + MEV_FMENV $F7 + Z80 budget asserts confirmed;
   python tests green. Controller verifies the intra-note carrier-TL swell/tremolo
   (vgm_intranote) + MT byte/spectrum regression in the oracle emulator.

   Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
   EOF
   )"
   ```
   (If the controller-verify markdown lives in a different plan file, substitute that path in the `git add`. Do NOT `git add -A`; enumerate exact paths only.)

---

## Component B — MEV_REGWRITE inline opcode

### Task B1: MEV_REGWRITE ($F8) constant + assert + Seq_Op_RegWrite handler + dispatch entry

Add a new music-stream coordination opcode `MEV_REGWRITE = $F8` that writes ONE arbitrary YM2612 register for an EXPLICIT part (operands carry part/reg/val — the part is NOT derived from the channel route), guards the DAC regs `$2A`/`$2B`, and re-parks `$2A` so a racing DAC byte stays clean. Three operands consumed in stream order: `part`(0/1), `reg`, `val`. Zero command-tick (paced by surrounding WAITs, like the other zero-tick setters).

**Files** (real paths — the spec's `code/sound/` prefix is stale; the live tree is `engine/` + repo-root `sound_constants.asm`):
- `/home/volence/sonic_hacks/aeon-music-expr/sound_constants.asm` — opcode equate + collision/range assert block
- `/home/volence/sonic_hacks/aeon-music-expr/engine/sound_sequencer.asm` — `Seq_Op_RegWrite` handler + dispatch-table entry

Steps:

- [ ] **Add the `MEV_REGWRITE` equate** in `sound_constants.asm` immediately after the `MEV_PSGNOISE` block (after line 368, before the blank line at 369). Insert:

```
; --- Phase 3 (music-expr): arbitrary YM2612 register write (inline opcode) ----
; $F8 + part + reg + val : write ONE YM2612 register IMMEDIATELY for an EXPLICIT
; part (0 = part I addr/data $4000/$4001, 1 = part II $4002/$4003). Unlike
; MEV_REGDELTA ($EA), the part is carried by the operand (NOT derived from the
; channel route via Fm_RoutePart) — this is the raw escape hatch the packer uses
; for whole-part / global registers (e.g. $22 LFO, $27 timer/ch3 mode, $B4 pan on
; an arbitrary channel). The handler GUARDS reg==$2A and reg==$2B (the DAC data /
; DAC-enable regs): those writes are SKIPPED so a song can never clobber the DAC
; stream or click the enable edge. After the write it re-parks $2A on the addr
; port (Fm_ReparkDac) so a DAC byte racing in lands on $2A. Zero command-tick.
MEV_REGWRITE    = $F8    ; + part + reg + val : raw YM2612 register write (part-explicit)
```

- [ ] **Add the range + collision assert block** in `sound_constants.asm`, immediately AFTER the SFX-fidelity assert block (after the `endif` at line 467, before the blank line at 468). This mirrors the existing `MEV_REGDELTA` assert block (`:425-436`) and the `MEV_PSGENV/MODSET/SPINREV` block (`:449-467`). Insert:

```
        ; --- MEV_REGWRITE ($F8) range + collision asserts (music-expr) ---
        ; A command opcode (> MEV_NOTE_MAX), inside the $E0-$FF coordination block,
        ; landing on the fixed slot $F8, clear of every allocated opcode. $F3-$F6 are
        ; RESERVED for Phase-2 plans, so $F8 must also stay clear of $F7/$F9 (the
        ; sibling music-expr opcodes MEV_FMENV/MEV_MACRO).
        if MEV_REGWRITE <= MEV_NOTE_MAX
          error "MEV_REGWRITE (\{MEV_REGWRITE}) must be a command opcode (> MEV_NOTE_MAX)"
        endif
        if (MEV_REGWRITE < MEV_VOL) || (MEV_REGWRITE > MEV_END)
          error "MEV_REGWRITE (\{MEV_REGWRITE}) must be inside the $E0-$FF coordination block"
        endif
        if MEV_REGWRITE <> $F8
          error "MEV_REGWRITE (\{MEV_REGWRITE}) must be $F8 (the fixed music-expr slot)"
        endif
        if (MEV_REGWRITE = MEV_VOL) || (MEV_REGWRITE = MEV_PATCH) || (MEV_REGWRITE = MEV_DAC) || (MEV_REGWRITE = MEV_NOTE_DUR) || (MEV_REGWRITE = MEV_PAN) || (MEV_REGWRITE = MEV_REPEAT_START) || (MEV_REGWRITE = MEV_REPEAT_END) || (MEV_REGWRITE = MEV_NOTE_RAW) || (MEV_REGWRITE = MEV_PITCHENV) || (MEV_REGWRITE = MEV_OPBIAS) || (MEV_REGWRITE = MEV_REGDELTA) || (MEV_REGWRITE = MEV_PSGENV) || (MEV_REGWRITE = MEV_MODSET) || (MEV_REGWRITE = MEV_NOTEFILL) || (MEV_REGWRITE = MEV_LOOP_POINT) || (MEV_REGWRITE = MEV_JUMP) || (MEV_REGWRITE = MEV_SPINREV) || (MEV_REGWRITE = MEV_PSGNOISE) || (MEV_REGWRITE = MEV_END)
          error "MEV_REGWRITE (\{MEV_REGWRITE}) collides with an allocated $E0-$FF opcode"
        endif
```

- [ ] **Add the `Seq_Op_RegWrite` handler** in `engine/sound_sequencer.asm`, inserted right after `Seq_Op_RegDelta` ends (after the `jp Seq_ContinueFetch` at line 1067) and BEFORE the `; $E5 MEV_REPEAT_START` comment block at line 1069. The template is `Fm_RegDelta`/`Fm_YmWrite`/`Fm_ReparkDac` (`engine/sound_fm.asm:520-561`, `:57-70`, `:79-82`) and the operand-consume + hl-rule pattern of `Seq_Op_PsgNoise`/`Seq_Op_ModSet`. On entry `hl` = live stream ptr (opcode already consumed), `ix` = SeqChannel. `Fm_YmWrite` and `Fm_ReparkDac` both document "Preserves bc, de, hl, ix" — so once all three operands are consumed (hl advanced past them), hl is the correct resume ptr and the two calls leave it intact; we still keep a defensive `push hl`/`pop hl` around the writing pair per the hl-PRESERVATION RULE (any call that touches the YM addr port is treated as stream-ptr-fragile). Insert:

```
; $F8 MEV_REGWRITE + part + reg + val : write ONE arbitrary YM2612 register for an
; EXPLICIT part (0/1), IMMEDIATELY. Zero command-tick. The part is carried by the
; operand (NOT Fm_RoutePart-derived) — this is the raw register escape hatch for
; whole-part / global regs. GUARD: reg==$2A (DAC data) and reg==$2B (DAC enable)
; are SKIPPED (the operands are still consumed) so a song can never clobber the DAC
; stream or click the enable edge. After the write, Fm_ReparkDac re-selects $2A on
; the addr port so a racing DAC byte lands on $2A. de=$4001 is preserved BY
; CONSTRUCTION (Fm_YmWrite/Fm_ReparkDac use absolute YM addressing). hl-rule: load
; all 3 operands first (hl ends past them = the resume ptr), then push/pop hl around
; the YM-write pair (defensive, the YmWrite/Repark calls already preserve hl).
; Clobbers: af, bc. Manipulates: hl (kept live). Uses ix.
Seq_Op_RegWrite:
        ld      a, (hl)
        inc     hl                       ; a = part (0/1); hl past part byte
        and     1                        ; mask to part bit (Fm_YmWrite tests bit 0)
        ld      b, a                     ; b = part
        ld      a, (hl)
        inc     hl                       ; a = reg; hl past reg byte
        ld      e, a                     ; e = reg (preserve across the val read)
        ld      a, (hl)
        inc     hl                       ; a = val; hl now PAST all 3 operands
        ld      c, a                     ; c = val
        ; --- DAC-reg guard: refuse $2A / $2B (skip the write, operands consumed) ---
        ld      a, e                     ; a = reg
        cp      SND_REG_DAC_DATA         ; $2A ?
        jr      z, .skip
        cp      SND_REG_DAC_ENABLE       ; $2B ?
        jr      z, .skip
        ld      a, e                     ; a = reg (Fm_YmWrite wants reg in a)
        push    hl                       ; defensive: keep the live stream ptr across the write
        call    Fm_YmWrite               ; a=reg, c=val, b=part (absolute addr; de untouched)
        call    Fm_ReparkDac             ; re-select $2A on the addr port
        pop     hl
.skip:
        jp      Seq_ContinueFetch        ; zero tick (jp: out of jr range to the tail)
```

- [ ] **Wire the dispatch entry** in `engine/sound_sequencer.asm`: replace the `$F8` slot in `SeqOpcodeTable`. Change line 1215 from `        dw      Seq_BadOpcode            ; $F8 reserved` to:

```
        dw      Seq_Op_RegWrite          ; $F8 MEV_REGWRITE (raw YM2612 register write)
```

- [ ] **Build** (sound MUST be enabled — a plain `./build.sh` excludes all sound):

```bash
cd /home/volence/sonic_hacks/aeon-music-expr && SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh 2>&1 | tail -20
```

Expected: build completes, `s4.bin` produced, no `error`/`fatal` lines. In particular the new `MEV_REGWRITE` assert block emits nothing (all `if` conditions false), and the Z80 budget assert at `engine/z80_sound_driver.asm:1472-1473` (`Z80_SOUND_SIZE > SND_STATE_BASE` $16F0) does NOT fire — the handler is ~30 bytes, well under headroom for one opcode.

- [ ] **Confirm the budget headroom explicitly** with the budget tool:

```bash
cd /home/volence/sonic_hacks/aeon-music-expr && python3 tools/s4budget.py s4.lst s4.bin --summary 2>&1 | tail -20
```

Expected: reports `Z80_SOUND_SIZE` <= `SND_STATE_BASE` ($16F0) with non-negative headroom; no overflow/FAIL line.

- [ ] **Commit** (exact paths only — never `-A`/globs; `data/editor/**` and `tools/ojz_strip_gen.py` are daemon-watched, untouched here):

```bash
cd /home/volence/sonic_hacks/aeon-music-expr && git add sound_constants.asm engine/sound_sequencer.asm && git commit -m "feat(sound): MEV_REGWRITE (\$F8) inline raw YM2612 register write

Part-explicit arbitrary YM2612 register write opcode + Seq_Op_RegWrite
handler: consume part/reg/val, guard \$2A/\$2B (DAC data/enable), write
via Fm_YmWrite, re-park \$2A via Fm_ReparkDac. Dispatch \$F8 slot wired;
range/collision asserts mirror the MEV_REGDELTA block.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task B2: Build green + controller emulator-verify handoff (a reg changes + DAC stays clean)

This task is the verification handoff. No code edits. The implementer confirms the build/asserts; the CONTROLLER runs all oracle/emulator verification (no emulator MCP calls in implementer steps).

**Files**: none edited.

Steps:

- [ ] **Re-confirm the sound build is green** (idempotent re-run; proves B1 still assembles after any sibling-task merges):

```bash
cd /home/volence/sonic_hacks/aeon-music-expr && SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh 2>&1 | tail -8
```

Expected: no `error`/`fatal`; `s4.bin` produced.

- [ ] **Re-confirm the Z80 budget assert passed** (the only build assert this component can move): the build above did not print the `Z80 sound driver code (... bytes) overruns state region at ...` fatal from `engine/z80_sound_driver.asm:1473`, and:

```bash
cd /home/volence/sonic_hacks/aeon-music-expr && python3 tools/s4budget.py s4.lst s4.bin --summary 2>&1 | tail -6
```

Expected: `Z80_SOUND_SIZE` within `SND_STATE_BASE` ($16F0), non-negative headroom.

- [ ] **Write the CONTROLLER verification handoff** (the implementer does NOT run these — they are what the controller will check in the emulator, alongside Component E's packer emitting a test song that fires `MEV_REGWRITE`):
  - **Reg actually changes**: with a music song that emits `MEV_REGWRITE part=0 reg=$22 val=$08` (LFO enable) and later `val=$00`, capture a VGM (<= 450 frames) via the oracle, then confirm the YM `$22` register write appears in the stream at the expected frame with the expected value (and reverts). A direct alternative: pause after the opcode frame and read the YM shadow / use `tools/vgm_intranote.py` to confirm a `$22`-class write landed.
  - **DAC stays clean ($2A re-park survived)**: the same test song must keep a DAC drum hit running across the `MEV_REGWRITE` frame. Capture the VGM and run `tools/vgm_intranote.py` — the DAC ($2A) sample stream must show NO dropout/garble at the register-write frame (the histogram baseline stays >= 95% steady, max inter-sample interval unchanged from the no-REGWRITE baseline). This is the direct proof that `Fm_ReparkDac` re-selected $2A after the write and the guard skipped any $2A/$2B write.
  - **Guard proof**: a song that (illegally for the engine, but as a robustness probe) targets `reg=$2A`/`reg=$2B` must produce NO change to the DAC data/enable behavior — the handler skipped the write. (The packer in Component E rejects $2A/$2B at validate(), so this probe is constructed by hand/test fixture, not a normal song.)

- [ ] **No commit** (verification-only task; nothing to add).

---

## Component C — SSG-EG (FmPatch 26→32, load-time)

### Task C1: FmPatch struct grows 26 → 32 (fp_ssg_eg + reserved pad) and Fm_PatchPtr becomes a pure ×32 shift

**Goal.** Append a 4-byte `fp_ssg_eg` per-operator group plus a 2-byte reserved pad to the `FmPatch` struct so `FmPatch_len` becomes 32 (a power of two), then rewrite `Fm_PatchPtr`'s `patch*26` shift/add chain into a pure `add hl,hl` ×5 (`patch*32`). This is asm-only (struct + one routine); the data files are NOT touched yet, so the build will FAIL its patch-bank size asserts after this task — that is expected and is resolved in C3. **Do C1, C2, C3 as one uninterrupted sequence; only the C3 build is green.** (Grounded: `sound_constants.asm:627-640`, `engine/sound_fm.asm:128-156`. Baseline `Z80_SOUND_SIZE=$1502=5378`, ceiling `SND_STATE_BASE=$16F0=5872`, headroom 494 B; the inline table grows by 2×6=12 B.)

**Files**
- `/home/volence/sonic_hacks/aeon-music-expr/sound_constants.asm` (FmPatch struct + size assert, lines 627-640)
- `/home/volence/sonic_hacks/aeon-music-expr/engine/sound_fm.asm` (Fm_PatchPtr, lines 103-156)

**Steps**

- [ ] 1. In `sound_constants.asm`, append the SSG-EG group and a reserved pad to the struct. Replace the exact block (lines 635-636):
```
fp_d1l_rr     ds.b 4          ; $80+ : D1L/RR per operator
FmPatch endstruct             ; = 2 + 6*4 = 26 bytes
```
with:
```
fp_d1l_rr     ds.b 4          ; $80+ : D1L/RR per operator
fp_ssg_eg     ds.b 4          ; $90+ : SSG-EG mode per operator (bit3 enable | bits0-2 mode);
                              ;        $00 = off. Loaded via SND_REG_OP_SSG_EG in Fm_PatchLoad.
fp_reserved   ds.b 2          ; pad the record to 32 bytes (a power of two) so Fm_PatchPtr
                              ;        addresses it with five `add hl,hl` shifts (no mulu).
FmPatch endstruct             ; = 2 + 6*4 + 4 + 2 = 32 bytes
```

- [ ] 2. In `sound_constants.asm`, update the size assert (lines 638-640) from 26 to 32. Replace:
```
        if FmPatch_len <> 26
          error "FmPatch struct is \{FmPatch_len} bytes, expected 26"
        endif
```
with:
```
        if FmPatch_len <> 32
          error "FmPatch struct is \{FmPatch_len} bytes, expected 32"
        endif
```

- [ ] 3. In `engine/sound_fm.asm`, rewrite the `Fm_PatchPtr` header comment math note. Replace lines 110-112:
```
; FmPatch_len = 26. Multiply by shift/add (NO mulu): keep P2 = patch*2 in de,
; then accumulate in hl by doubling and adding P2 — the running products are
;   *2 (=P2) -> *4 -> *8 -> +P2=*10 -> *20 -> +P2=*22 -> +P2=*24 -> +P2=*26.
```
with:
```
; FmPatch_len = 32 (a power of two). Multiply by FIVE `add hl,hl` shifts (NO mulu,
; NO add-chain): patch -> *2 -> *4 -> *8 -> *16 -> *32. de is no longer needed
; (the old 26-byte add-chain kept P2=patch*2 in de; 32 is a pure shift).
```

- [ ] 4. In `engine/sound_fm.asm`, replace the `.music` shift/add body (lines 140-156) with the pure ×32 shift. Replace:
```
.music:
        ld      a, (ix+sc_patch)
        ld      l, a
        ld      h, 0                     ; hl = patch
        add     hl, hl                   ; hl = patch*2  (call it P2)
        ld      e, l
        ld      d, h                     ; de = P2
        add     hl, hl                   ; hl = P2*2  = patch*4
        add     hl, hl                   ; hl = P2*4  = patch*8
        add     hl, de                   ; hl = patch*8 + patch*2 = patch*10
        add     hl, hl                   ; hl = patch*20
        add     hl, de                   ; hl = patch*20 + patch*2 = patch*22
        add     hl, de                   ; hl = patch*24
        add     hl, de                   ; hl = patch*26  (= patch*FmPatch_len)
        ld      de, (SND_SEQ_PATCHTAB)   ; base = loaded patch-table ptr (RAM or window)
        add     hl, de                   ; hl = table base + patch*26
        ret
```
with:
```
.music:
        ld      a, (ix+sc_patch)
        ld      l, a
        ld      h, 0                     ; hl = patch
        add     hl, hl                   ; hl = patch*2
        add     hl, hl                   ; hl = patch*4
        add     hl, hl                   ; hl = patch*8
        add     hl, hl                   ; hl = patch*16
        add     hl, hl                   ; hl = patch*32  (= patch*FmPatch_len)
        ld      de, (SND_SEQ_PATCHTAB)   ; base = loaded patch-table ptr (RAM or window)
        add     hl, de                   ; hl = table base + patch*32
        ret
```

- [ ] 5. Stage and commit. The build is intentionally NOT run here (the data asserts fail until C3); the C2/C3 sequence finishes the change:
```
git -C /home/volence/sonic_hacks/aeon-music-expr add sound_constants.asm engine/sound_fm.asm
git -C /home/volence/sonic_hacks/aeon-music-expr commit -m "feat(sound): FmPatch 26->32 (fp_ssg_eg + pad); Fm_PatchPtr pure x32 shift

Append a 4-byte SSG-EG per-operator group + 2 reserved bytes so FmPatch_len is
a power of two (32). Rewrite Fm_PatchPtr's patch*26 shift/add chain into five
add,hl shifts (patch*32, no mulu, no de). Data-file re-export follows in C3.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

**Verify (implementer).** No build in this task (data asserts fail until C3). Confirm by inspection that `FmPatch_len` resolves to 32 and `Fm_PatchPtr` has exactly five `add hl,hl` in the `.music` path and no remaining `ld de,(... ) ; add hl,de` add-chain except the final `SND_SEQ_PATCHTAB` base add. `git show --stat HEAD` lists exactly the two files.

---

### Task C2: SND_REG_OP_SSG_EG=$90 and the $90-group (4-operator) write in Fm_PatchLoad

**Goal.** Define the YM2612 SSG-EG register base `$90` and upload the patch's `fp_ssg_eg` group as a 6th operator-group write inside `Fm_PatchLoad`, reusing the existing `Fm_PatchOpGroup` helper (it already does `base + op*4 + ch` for 4 operators). Defaulting `$00` in every patch record (C1/C3) means a song that never sets SSG-EG writes `$90+ch+op*4 = $00` = SSG-EG OFF on every operator — a no-op vs hardware reset. (Grounded: `sound_constants.asm:78-83` reg-base block; `engine/sound_fm.asm:166-209` Fm_PatchLoad; `Fm_PatchOpGroup` at :217-244 takes `a=base, hl=ptr to 4 patch bytes` and advances `hl` by 4.) Still asm-only; build still fails the data asserts until C3.

**Files**
- `/home/volence/sonic_hacks/aeon-music-expr/sound_constants.asm` (SND_REG_OP_* block, after line 83)
- `/home/volence/sonic_hacks/aeon-music-expr/engine/sound_fm.asm` (Fm_PatchLoad group sequence, lines 206-209)

**Steps**

- [ ] 1. In `sound_constants.asm`, add the SSG-EG register base immediately after the `fp_d1l_rr`/`$80` line (line 83). Replace:
```
SND_REG_OP_D1L_RR       = $80                    ; +(op*4)+ch : decay level | release rate
```
with:
```
SND_REG_OP_D1L_RR       = $80                    ; +(op*4)+ch : decay level | release rate
SND_REG_OP_SSG_EG       = $90                    ; +(op*4)+ch : SSG-EG (bit3 enable | bits0-2 mode); $00 = off
```

- [ ] 2. In `engine/sound_fm.asm`, add the `$90` group write to `Fm_PatchLoad` after the `$80` (D1L/RR) group and BEFORE the final `Fm_ReparkDac`. Replace lines 206-209:
```
        ld      a, SND_REG_OP_D1L_RR     ; $80
        call    Fm_PatchOpGroup

        jp      Fm_ReparkDac             ; defensive end-of-batch re-park ($2A)
```
with:
```
        ld      a, SND_REG_OP_D1L_RR     ; $80
        call    Fm_PatchOpGroup
        ld      a, SND_REG_OP_SSG_EG     ; $90 (SSG-EG group; hl now points at fp_ssg_eg[0])
        call    Fm_PatchOpGroup          ; writes $90+ch+op*4 = fp_ssg_eg[op] for op 0..3

        jp      Fm_ReparkDac             ; defensive end-of-batch re-park ($2A)
```

- [ ] 3. (No code change — note in plan.) `hl` enters the group sequence at `fp_dt_mul[0]` (the contiguous 6+1 groups follow in record order). Each `Fm_PatchOpGroup` advances `hl` by 4, so after the `$80` group `hl` points exactly at `fp_ssg_eg[0]` — the new `$90` call consumes the appended 4-byte group with no extra pointer math. The 2-byte `fp_reserved` pad is NOT written to any register (it is record-alignment only).

- [ ] 4. Stage and commit (still no green build — C3 finishes it):
```
git -C /home/volence/sonic_hacks/aeon-music-expr add sound_constants.asm engine/sound_fm.asm
git -C /home/volence/sonic_hacks/aeon-music-expr commit -m "feat(sound): SND_REG_OP_SSG_EG=\$90; upload fp_ssg_eg group in Fm_PatchLoad

Define the YM2612 SSG-EG register base and add a 6th operator-group write
(reusing Fm_PatchOpGroup) so the patch's fp_ssg_eg[op] uploads to \$90+ch+op*4.
Default \$00 in every record = SSG-EG off (no-op). Data re-export follows in C3.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

**Verify (implementer).** No build yet (data asserts still fail). Confirm by inspection that `Fm_PatchLoad` now has SEVEN `call Fm_PatchOpGroup`/`Fm_PatchTlGroup` invocations covering bases `$30,$40,$50,$60,$70,$80,$90` (note `$40` is `Fm_PatchTlGroup`, the other six are `Fm_PatchOpGroup`), in that order, terminated by `jp Fm_ReparkDac`. `git show --stat HEAD` lists exactly the two files.

---

### Task C3: re-export every FmPatch consumer to 32-byte records (default $00 SSG-EG) + python record-length test; build green

**Goal.** Update all three Python emitters and the one hand-authored byte source so every emitted FmPatch record is 32 bytes (the 6 trailing bytes = SSG-EG group `$00,$00,$00,$00` + reserved pad `$00,$00`), then regenerate / migrate every checked-in patch bank so the `FmPatch_len`-relative size asserts pass with `FmPatch_len=32`. The build goes GREEN here. (Grounded — three independent per-record emitters, none shared: `tools/zyrinx_port.py` `translate_voice` :93-139 (`FMPATCH_LEN=26` :74) + `emit_patch_bank_asm` :196-265 [MT]; `tools/sfx_transcode.py` `emit_sfx_patches_asm` :1462-1539 [SFX, its own loop], reuses `FMPATCH_LEN`/`translate_voice` from zyrinx_port; `tools/smps_import.py` `emit_hcz2_patches_asm` :1413-1452 [HCZ2, raw `dc.b` rows]. Hand source: `data/sound/fm_patches.inc` (2 records). Checked-in generated banks: `data/sound/movingtrucks_patches.asm` (25 records), `data/sound/hcz2_patches.asm` (4 records), `data/sound/sfx/sfx_{33,34,35,36,3C,62,AB,B6,B9}_patches.asm`. The `OP_REORDER`/local-count header comments in the MT file are pre-existing stale text — do NOT chase them; out of scope.)

**Sequencing note (no missing inputs).** The SFX corpus has a no-arg regenerator (`python3 tools/sfx_transcode.py generate`) and its skdisasm source is present (verified at `/home/volence/sonic_hacks/skdisasm/Sound/SFX`). The MT (`movingtrucks`) and HCZ2 source JSONs are NOT present in this worktree, so their generators cannot be re-run here. Since SSG-EG is `$00` for every existing record, those two checked-in banks are migrated by appending the fixed 6-zero-byte group per record with a small, format-aware one-shot script that this task adds and runs.

**Files**
- `/home/volence/sonic_hacks/aeon-music-expr/tools/zyrinx_port.py` (`FMPATCH_LEN`, `translate_voice`, `emit_patch_bank_asm`)
- `/home/volence/sonic_hacks/aeon-music-expr/tools/sfx_transcode.py` (`emit_sfx_patches_asm` per-record loop)
- `/home/volence/sonic_hacks/aeon-music-expr/tools/smps_import.py` (`emit_hcz2_patches_asm` per-record loop)
- `/home/volence/sonic_hacks/aeon-music-expr/data/sound/fm_patches.inc` (hand source, 2 records)
- `/home/volence/sonic_hacks/aeon-music-expr/tools/ssg_eg_pad.py` (NEW one-shot migration for MT + HCZ2)
- `/home/volence/sonic_hacks/aeon-music-expr/tools/test_zyrinx_port.py`, `/home/volence/sonic_hacks/aeon-music-expr/tools/test_sfx_transcode.py` (update `26` → `32` length asserts + add zero-tail check)
- Regenerated: `data/sound/sfx/*_patches.asm` (via CLI), `data/sound/movingtrucks_patches.asm`, `data/sound/hcz2_patches.asm` (via the one-shot script)

**Steps**

- [ ] 1. In `tools/zyrinx_port.py`, bump the record length and document the SSG-EG tail. Replace lines 74:
```
FMPATCH_LEN = 26
```
with:
```
FMPATCH_LEN = 32
# Record layout: 26 legacy bytes (fp_alg_fb, fp_lr_ams_fms, 6 four-byte per-op
# groups $30..$80) + a 4-byte fp_ssg_eg group ($90, default $00 = SSG-EG off) +
# 2 reserved pad bytes = 32 (a power of two; FmPatch struct in sound_constants.asm).
```

- [ ] 2. In `tools/zyrinx_port.py` `translate_voice`, append the SSG-EG group + pad before the final length assert. Replace lines 135-139:
```
        else:
            out.extend((g[OP_REORDER[0]] & 0xFF, g[OP_REORDER[1]] & 0xFF,
                        g[OP_REORDER[2]] & 0xFF, g[OP_REORDER[3]] & 0xFF))
    assert len(out) == FMPATCH_LEN
    return bytes(out)
```
with:
```
        else:
            out.extend((g[OP_REORDER[0]] & 0xFF, g[OP_REORDER[1]] & 0xFF,
                        g[OP_REORDER[2]] & 0xFF, g[OP_REORDER[3]] & 0xFF))
    # fp_ssg_eg group ($90, 4 ops) defaults to $00 (SSG-EG off) + 2 reserved pad
    # bytes -> 32-byte record. Zyrinx/S3K voices carry no SSG-EG data, so $00.
    out.extend((0x00, 0x00, 0x00, 0x00, 0x00, 0x00))
    assert len(out) == FMPATCH_LEN
    return bytes(out)
```

- [ ] 3. In `tools/zyrinx_port.py` `emit_patch_bank_asm`, emit the SSG-EG group + pad row per record. After the existing 6-group loop (lines 251-255), insert two `pbyte` rows. Replace:
```
        for gi, glabel in enumerate(_PATCH_GROUP_LABELS):
            off = 2 + gi * 4
            g = rec[off:off + 4]
            L.append("        pbyte   %3d, %3d, %3d, %3d   ; %s  [S1,S3,S2,S4]"
                     % (g[0], g[1], g[2], g[3], glabel))
    L.append("%s_End:" % label)
```
with:
```
        for gi, glabel in enumerate(_PATCH_GROUP_LABELS):
            off = 2 + gi * 4
            g = rec[off:off + 4]
            L.append("        pbyte   %3d, %3d, %3d, %3d   ; %s  [S1,S3,S2,S4]"
                     % (g[0], g[1], g[2], g[3], glabel))
        ssg = rec[26:30]
        L.append("        pbyte   %3d, %3d, %3d, %3d   ; fp_ssg_eg  $90  [S1,S3,S2,S4]"
                 % (ssg[0], ssg[1], ssg[2], ssg[3]))
        L.append("        pbyte   %3d, %3d                ; fp_reserved (pad to 32)"
                 % (rec[30], rec[31]))
    L.append("%s_End:" % label)
```

- [ ] 4. In `tools/sfx_transcode.py` `emit_sfx_patches_asm`, append the SSG-EG group + pad row per record. After the 6-group loop (lines 1533-1538), before `_End`. Replace:
```
        for gi, (glbl, greg) in enumerate(group_labels):
            off = 2 + gi * 4
            g = rec[off:off + 4]
            lines.append(f"        pbyte   {g[0]:3}, {g[1]:3}, {g[2]:3}, {g[3]:3}"
                         f"   ; {glbl}  {greg}  [S1,S3,S2,S4]")
    lines.append(f"{patches_label}_End:")
```
with:
```
        for gi, (glbl, greg) in enumerate(group_labels):
            off = 2 + gi * 4
            g = rec[off:off + 4]
            lines.append(f"        pbyte   {g[0]:3}, {g[1]:3}, {g[2]:3}, {g[3]:3}"
                         f"   ; {glbl}  {greg}  [S1,S3,S2,S4]")
        ssg = rec[26:30]
        lines.append(f"        pbyte   {ssg[0]:3}, {ssg[1]:3}, {ssg[2]:3}, {ssg[3]:3}"
                     f"   ; fp_ssg_eg  $90  [S1,S3,S2,S4]")
        lines.append(f"        pbyte   {rec[30]:3}, {rec[31]:3}"
                     f"                ; fp_reserved (pad to 32)")
    lines.append(f"{patches_label}_End:")
```

- [ ] 5. In `tools/smps_import.py` `emit_hcz2_patches_asm`, extend each raw `dc.b` row to 32 bytes. The HCZ2 emitter writes one `dc.b` of `rec` bytes; the upstream `smps_voice_to_fmpatch` returns 26 bytes (it `assert len(patch) == FMPATCH_LEN`, now 32 after step 1, so it must also be padded — verify and pad there). First update the row emit (line 1444). Replace:
```
        rec = voices[vid]
        byte_str = ", ".join("$%02X" % x for x in rec)
        L.append("        dc.b    %s  ; [%d] S3K voice $%02X" % (byte_str, i, vid))
```
with:
```
        rec = voices[vid]
        # Pad to FMPATCH_LEN (32): fp_ssg_eg group ($90, 4 ops) + 2 reserved bytes,
        # all $00 (SSG-EG off). S3K UVB voices carry no SSG-EG data.
        rec = bytes(rec) + b"\x00" * (FMPATCH_LEN - len(rec))
        byte_str = ", ".join("$%02X" % x for x in rec)
        L.append("        dc.b    %s  ; [%d] S3K voice $%02X (+SSG-EG/pad $00)" % (byte_str, i, vid))
```

- [ ] 6. In `tools/smps_import.py`, fix the HCZ2 size-assert comment text (line ~1450) so it does not claim 26. Replace:
```
        L.append("          error \"%s size mismatch (expected %d voices * 26 bytes)\""
                 % (label, count))
```
with:
```
        L.append("          error \"%s size mismatch (expected %d voices * FmPatch_len bytes)\""
                 % (label, count))
```

- [ ] 7. In `data/sound/fm_patches.inc` (the hand source), append the SSG-EG group + pad to BOTH records. After the PATCH_BASS `fp_d1l_rr` line (line 63):
```
        pbyte   24,  24,  24,  24       ; fp_d1l_rr  $80  D1L=1,RR=8 ($18) clean release
```
replace with:
```
        pbyte   24,  24,  24,  24       ; fp_d1l_rr  $80  D1L=1,RR=8 ($18) clean release
        pbyte   0,   0,   0,   0        ; fp_ssg_eg  $90  SSG-EG off (all operators)
        pbyte   0,   0                  ; fp_reserved      pad to 32 bytes
```
and after the PATCH_LEAD `fp_d1l_rr` line (line 75):
```
        pbyte   10,  10,  10,  10       ; fp_d1l_rr  $80  D1L=0,RR=$0A clean release
```
replace with:
```
        pbyte   10,  10,  10,  10       ; fp_d1l_rr  $80  D1L=0,RR=$0A clean release
        pbyte   0,   0,   0,   0        ; fp_ssg_eg  $90  SSG-EG off (all operators)
        pbyte   0,   0                  ; fp_reserved      pad to 32 bytes
```

- [ ] 8. Create the one-shot migration `tools/ssg_eg_pad.py` for the two banks whose source JSON is absent (MT + HCZ2). It appends one SSG-EG+pad group per record by inserting after each record's last group row, format-aware (`pbyte`-grouped for MT, single `dc.b` row for HCZ2). Write the COMPLETE file:
```python
#!/usr/bin/env python3
"""One-shot migration: append the 4-byte SSG-EG group + 2 reserved pad bytes
(all $00) to every FmPatch record in the two checked-in patch banks whose source
JSON is NOT in this worktree (Moving Trucks, HCZ2), so their FmPatch_len-relative
size asserts pass after FmPatch grew 26 -> 32 (SSG-EG, Task C1).

SSG-EG is $00 (off) for every existing record (no source carries SSG-EG data),
so this only appends 6 zero bytes per record; the first 26 bytes are untouched.
Idempotent: refuses to run on a file already at 32-byte records.

Formats handled:
  - Moving Trucks: `pbyte`-grouped records (fp_alg_fb, fp_lr_ams_fms, then 6
    four-byte `pbyte` rows). Insert two `pbyte` rows after each record's last
    group row (the `fp_d1l_rr  $80` row).
  - HCZ2: one `dc.b` row of 26 hex bytes per record. Rewrite the row with 6
    trailing `, $00`.
"""
import re
import sys

MT_PATH = "data/sound/movingtrucks_patches.asm"
HCZ2_PATH = "data/sound/hcz2_patches.asm"

SSG_ROW = "        pbyte     0,   0,   0,   0   ; fp_ssg_eg  $90  [S1,S3,S2,S4]"
PAD_ROW = "        pbyte     0,   0                ; fp_reserved (pad to 32)"


def migrate_mt(text: str) -> str:
    """Insert SSG-EG + pad rows after every `fp_d1l_rr  $80` pbyte row."""
    out = []
    inserted = 0
    for line in text.splitlines():
        out.append(line)
        if "fp_d1l_rr" in line and line.lstrip().startswith("pbyte"):
            out.append(SSG_ROW)
            out.append(PAD_ROW)
            inserted += 1
    if inserted == 0:
        raise SystemExit("MT: no fp_d1l_rr pbyte rows found (already migrated?)")
    return "\n".join(out) + "\n"


def migrate_hcz2(text: str) -> str:
    """Append 6 `, $00` to every `dc.b` record row that is exactly 26 bytes."""
    out = []
    inserted = 0
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("dc.b") and ";" in line:
            data, comment = line.split(";", 1)
            vals = [v.strip() for v in data.split("dc.b", 1)[1].split(",")]
            vals = [v for v in vals if v]
            if len(vals) == 26:
                vals = vals + ["$00"] * 6
                line = "        dc.b    %s  ;%s" % (", ".join(vals), comment.rstrip("\n"))
                inserted += 1
        out.append(line)
    if inserted == 0:
        raise SystemExit("HCZ2: no 26-byte dc.b record rows found (already migrated?)")
    return "\n".join(out) + "\n"


def main():
    with open(MT_PATH) as f:
        mt = f.read()
    with open(HCZ2_PATH) as f:
        hz = f.read()
    with open(MT_PATH, "w") as f:
        f.write(migrate_mt(mt))
    with open(HCZ2_PATH, "w") as f:
        f.write(migrate_hcz2(hz))
    print("migrated MT + HCZ2 patch banks to 32-byte records (SSG-EG $00).",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] 9. Regenerate the SFX corpus (CLI, skdisasm present) and run the MT/HCZ2 migration. From the worktree root:
```
cd /home/volence/sonic_hacks/aeon-music-expr && python3 tools/sfx_transcode.py generate && python3 tools/ssg_eg_pad.py
```
Expected: `wrote .../sfx_33_patches.asm` … through `sfx_B9_patches.asm` + `sfx_table.asm`, then `migrated MT + HCZ2 patch banks to 32-byte records (SSG-EG $00).`

- [ ] 10. Sanity-check every checked-in bank is now 32-byte records (deterministic, no build needed):
```
cd /home/volence/sonic_hacks/aeon-music-expr && python3 - <<'PY'
import re
def nbytes(path):
    n = 0
    for ln in open(path):
        s = ln.strip()
        if s.startswith("dc.b"):
            body = s.split("dc.b",1)[1].split(";",1)[0]
            n += len([v for v in body.split(",") if v.strip()])
        elif s.startswith("pbyte"):
            body = s.split("pbyte",1)[1].split(";",1)[0].strip()
            if not body: continue
            try: vals=[int(v) for v in body.split(",") if v.strip()]
            except ValueError: continue
            n += len(vals)
    return n
import glob
for p in ["data/sound/fm_patches.inc","data/sound/movingtrucks_patches.asm",
          "data/sound/hcz2_patches.asm"]+sorted(glob.glob("data/sound/sfx/*_patches.asm")):
    b = nbytes(p)
    print(f"{b%32==0 and 'OK ' or 'BAD'} {b:5d} ({b/32:.1f} recs)  {p}")
PY
```
Expected: every line begins `OK` and the record count is integral (PSG-only SFX banks have 0 bytes — also OK). If any line is `BAD`, fix that emitter/migration before proceeding.

- [ ] 11. Update `tools/test_zyrinx_port.py` length asserts. (a) `test_record_layout` `expected` (lines 292-301): append the SSG-EG + pad bytes. Replace the closing of the `expected` literal:
```
            7, 10, 7, 58,           # fp_d1l_rr   ($80) <- sl_rr
        ])
        out = translate_voice(v)
        self.assertEqual(len(out), 26)
        self.assertEqual(len(out), FMPATCH_LEN)
        self.assertEqual(out, expected)
```
with:
```
            7, 10, 7, 58,           # fp_d1l_rr   ($80) <- sl_rr
            0, 0, 0, 0,             # fp_ssg_eg   ($90) default off
            0, 0,                   # fp_reserved (pad to 32)
        ])
        out = translate_voice(v)
        self.assertEqual(len(out), 32)
        self.assertEqual(len(out), FMPATCH_LEN)
        self.assertEqual(out, expected)
        # SSG-EG group + pad default to $00 (off) for translated voices.
        self.assertEqual(list(out[26:32]), [0, 0, 0, 0, 0, 0])
```
(b) `test_ext_dropped` (line 358):
```
        self.assertEqual(len(translate_voice(self._neutral())), 26)
```
with:
```
        self.assertEqual(len(translate_voice(self._neutral())), 32)
```
(c) `TestBuildPatchBank.test_bank_is_n_records_of_26` (lines 383-385) — rename + retarget the stride. Replace:
```
    def test_bank_is_n_records_of_26(self):
```
with:
```
    def test_bank_is_n_records_of_32(self):
```
and the `* 26` / `* 26` / `[off:off+26]` / `off = local_idx * 26` occurrences at lines 385, 415, 416 → `* 32`, `* 32`, `[off:off+32]`, `* 32` respectively (use `FMPATCH_LEN` where the symbol is imported; the file imports `FMPATCH_LEN` at line 28). For lines 415-417 replace:
```
            off = local_idx * 26
            rec = self.bank_bytes[off:off + 26]
```
with:
```
            off = local_idx * FMPATCH_LEN
            rec = self.bank_bytes[off:off + FMPATCH_LEN]
```
and line 385 `self.assertEqual(len(self.bank_bytes), self.count * 26)` → `self.count * FMPATCH_LEN`.

- [ ] 12. Update `tools/test_sfx_transcode.py` length asserts. (a) line 195-196:
```
        self.assertEqual(len(self.desc['voices'][0]), 26,
                         "FmPatch must be exactly 26 bytes")
```
with:
```
        self.assertEqual(len(self.desc['voices'][0]), 32,
                         "FmPatch must be exactly 32 bytes (incl. SSG-EG group + pad)")
```
(b) `test_operator_reorder` length + sl_rr slice (lines 918, 929):
```
        self.assertEqual(len(out), 26)
```
→
```
        self.assertEqual(len(out), 32)
```
and after line 929 (the `out[22:26]` sl_rr assert), append:
```
        self.assertEqual(list(out[26:30]), [0, 0, 0, 0], "fp_ssg_eg default off")
        self.assertEqual(list(out[30:32]), [0, 0], "fp_reserved pad")
```
(The `[2:6]`…`[22:26]` slices are unchanged — SSG-EG is appended at the end, so all legacy offsets stay valid.)

- [ ] 13. Run the canonical python tests + the two consumer test files:
```
cd /home/volence/sonic_hacks/aeon-music-expr && python3 -m pytest tools/test_song_packer.py tools/test_gen_sound_tables.py tools/test_zyrinx_port.py tools/test_sfx_transcode.py -q
```
Expected: all pass (baseline was 85 + 129; the slice/length updates keep them green).

- [ ] 14. Build the sound ROM — this is the first GREEN build of the C-series (it proves the C1 struct, C2 register write, and all regenerated banks agree on `FmPatch_len=32`):
```
cd /home/volence/sonic_hacks/aeon-music-expr && SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh
```
Expected tail: `Build complete: s4.bin` with NO `FM patch table size`/`patch bank size mismatch`/`HCZ2_Patches size mismatch`/`inline FM patch table wrong size`/`FmPatch struct is … bytes` errors, and NO `Z80 sound driver code … overruns state region` fatal.

- [ ] 15. Confirm the budget after the inline-table growth (the inline FmPatch table grew 52→64 B; headroom was 494 B):
```
cd /home/volence/sonic_hacks/aeon-music-expr && python3 tools/s4budget.py s4.lst s4.bin --summary 2>&1 | head; grep -i 'Z80_SOUND_SIZE *:' s4.lst | head -1
```
Expected: `Z80_SOUND_SIZE` value (hex) is ≤ `$16F0` (i.e. ≤ 5872); after C1+C2+C3 it is roughly `$1502 + 12 (inline table) + ~14 (one extra Fm_PatchOpGroup call setup) ≈ $1520`, comfortably under ceiling. If it ever exceeds, that is a hard build fatal (already asserted) — but it will not at this size.

- [ ] 16. Stage exact paths and commit (the build was verified green in step 14):
```
git -C /home/volence/sonic_hacks/aeon-music-expr add tools/zyrinx_port.py tools/sfx_transcode.py tools/smps_import.py tools/ssg_eg_pad.py tools/test_zyrinx_port.py tools/test_sfx_transcode.py data/sound/fm_patches.inc data/sound/movingtrucks_patches.asm data/sound/hcz2_patches.asm data/sound/sfx/sfx_33_patches.asm data/sound/sfx/sfx_34_patches.asm data/sound/sfx/sfx_35_patches.asm data/sound/sfx/sfx_36_patches.asm data/sound/sfx/sfx_3C_patches.asm data/sound/sfx/sfx_62_patches.asm data/sound/sfx/sfx_AB_patches.asm data/sound/sfx/sfx_B6_patches.asm data/sound/sfx/sfx_B9_patches.asm
git -C /home/volence/sonic_hacks/aeon-music-expr commit -m "feat(sound): re-export all FmPatch banks to 32-byte records (SSG-EG \$00)

translate_voice + all three patch-bank emitters (zyrinx_port MT, sfx_transcode
SFX, smps_import HCZ2) now append the 4-byte fp_ssg_eg group + 2 reserved pad
bytes (all \$00 = SSG-EG off). Regenerated the SFX corpus via the CLI; migrated
the MT + HCZ2 banks (no source JSON in-tree) via tools/ssg_eg_pad.py. Hand source
data/sound/fm_patches.inc extended likewise. Sound build green; budget under \$16F0.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
Note: only `*_patches.asm` SFX files change (the `sfx_NN.asm` blobs' voice_ptr offsets are unaffected because the patch bank is at the END of each blob — but `sfx_transcode.py generate` rewrites the `sfx_NN.asm` blobs too; run `git -C … status --short data/sound/sfx/` after step 9 and if any `sfx_NN.asm` (non-patches) blob changed, add those exact paths to the commit as well — they must NOT be left dirty).

**Verify (implementer).** Steps 10, 13, 14, 15 are the verification: every bank is an integral multiple of 32 bytes; all python tests pass; the sound build completes with none of the five size asserts firing and no budget fatal; `Z80_SOUND_SIZE ≤ $16F0`. `git -C … status --short` is clean after the commit.

---

### Task C4: build + controller verification handoff — SSG-EG on/off timbre

**Goal.** Hand the on-device verification of the SSG-EG path to the controller. Implementer work is already done and committed (C1-C3); this task is the explicit handoff describing exactly what the controller checks. No implementer edits.

**Implementer pre-handoff checks (re-confirm, no new code).**
- [ ] 1. Re-run the green sound build to confirm the branch tip builds:
```
cd /home/volence/sonic_hacks/aeon-music-expr && SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh
```
Expected: `Build complete: s4.bin`, no patch-bank/struct/budget errors.
- [ ] 2. Confirm `s4.bin` exists and the worktree is clean:
```
cd /home/volence/sonic_hacks/aeon-music-expr && ls -la s4.bin && git status --short
```
Expected: `s4.bin` present, `git status` empty.

**Controller verification (emulator — NOT run by the implementer).**
The controller loads `s4.bin` in the oracle emulator and verifies the SSG-EG register path:
1. **Off-path regression (every current song):** play Moving Trucks (stream song) and DrumTest; capture a VGM (≤ 450 frames) and confirm the song still renders identically to the pre-C baseline — because every regenerated record has `fp_ssg_eg = $00`, `Fm_PatchLoad` now writes `$90+ch+op*4 = $00` (SSG-EG off) on each patch load. Confirm via `tools/vgm_intranote.py` / spectrum overlay that timbre and onsets are unchanged from the C-series baseline (no regression from the extra register writes).
2. **YM register-write presence:** with a YM2612 register-write log (Exodus/oracle VGM `$90`-`$9F` writes), confirm that on each FM patch load the driver now emits four `$90`-group writes (`$90/$94/$98/$9C` for part-I channels, `$90/$94/$98` on part II + FM6) all with data `$00`. (This proves C2's group write fires; today there are zero `$90`-`$9F` writes.)
3. **On-path timbre (manual authored test, controller's discretion):** if the controller wants a positive SSG-EG demo, it can hand-patch one inline record's `fp_ssg_eg[carrier]` to `$08` (enable, mode 0) in `data/sound/fm_patches.inc`, rebuild, and confirm an audible "buzzy"/mirror-folded timbre change vs `$00` on that voice — then revert. This is optional and controller-driven; the implementer does NOT author it.

**Done when:** the controller confirms (1) no off-path regression on existing songs and (2) the `$90`-group writes are present at patch load. The branch `feat/music-expr-p1` SSG-EG component is then complete.

---

## Component D — slot[1] MacroTick + MEV_MACRO

### Task D1: TAG_MAC_* constants + the MacroTick slot[1] reader

Make `sc_mod_ptr` real: a per-channel reg-automation reader that walks a tag-prefixed event stream, executes events until it yields one frame, and commits the cursor. This task adds the constants, the `sc_macro_active` alias, and the `MacroTick` routine — but does NOT yet wire it into the frame loop (D2) nor arm it from a stream opcode (D3). It is dead code until D2.

**Grounding (verified against live source on `feat/music-expr-p1`):**
- `sc_mod_ptr` = `SeqChannel` +2, a word (`sound_constants.asm:782`, alias `:876`). Loader rebases it `base+offset` BE, leaves 0 on a NULL offset (`engine/z80_sound_driver.asm:1185-1196`); the whole seq region is zero-cleared at load (`:1029-1037`), so an un-armed channel has `sc_mod_ptr == 0`.
- `sc_pad` = `SeqChannel` +57 (`sound_constants.asm:855`); only `SeqChannel_sc_pad` exists — **no short `sc_pad` alias is defined** (verified: the alias block `:875-926` stops at `sc_detune`). I add both `sc_pad` and `sc_macro_active = sc_pad`.
- `Snd_SongBase` = the 2-byte song base ptr in Z80 RAM (`sound_constants.asm:1030`), set by the loader for RAM-copy and stream paths (`engine/z80_sound_driver.asm:1086/1110`). Macro-body blob offsets are rebased the same way the loader rebases `mod_ptr`: `absolute = Snd_SongBase + offset`.
- The reg-write primitive (reused by the `.reg` event) is `Fm_YmWrite` (in: `a=reg, c=val, b=part`; `engine/sound_fm.asm:57-70`) then `jp/call Fm_ReparkDac` (re-parks `$2A`; `:79-82`). `$2A`/`$2B` are `SND_REG_DAC_DATA`/`SND_REG_DAC_ENABLE` (`sound_constants.asm:64-65`).
- BINDING tag values (locked cross-task with Component E): `TAG_MAC_NEXT=$E0`, `TAG_MAC_REG=$E1`, `TAG_MAC_LOOP=$E2`, `TAG_MAC_END=$E3`. `TAG_MAC_LOOP` is `$E2` FOLLOWED BY a 2-byte BIG-ENDIAN blob offset (the channel macro-body start); the handler reads those 2 BE bytes and ADDS `Snd_SongBase` (same convention as `MEV_MACRO`) — it is NOT operand-less.
- `MacroTick` must preserve `ix` (the frame loop relies on it). It may clobber `af,bc,de,hl` — the loop saves `bc` across calls (`sound_sequencer.asm:65/81`) and ModUpdate already clobbers `af,bc,de,hl`. There is no live `hl` stream ptr across `MacroTick` (it owns the cursor in `hl` locally and commits it before returning), so the slot[0] hl-preservation rule does not bind here, but `MacroTick`'s `.reg` event still calls `Fm_YmWrite`/`Fm_ReparkDac` which preserve `bc,de,hl,ix` / `bc,de,hl,ix` respectively (verified `:55`/`:77`), so the live cursor in `hl` survives the write.

**Files:**
- `sound_constants.asm` (TAG_MAC_* equates + `sc_pad`/`sc_macro_active` aliases + a fixed-slot assert block)
- `engine/sound_sequencer.asm` (the `MacroTick` routine; placed immediately after `Seq_ContinueFetch` at `:1184`, before `SeqOpcodeTable` at `:1186`)

**Steps:**

1. [ ] Add the `sc_pad` + `sc_macro_active` aliases. In `sound_constants.asm`, immediately after the `sc_detune = SeqChannel_sc_detune` line (`:926`), insert:
```
sc_detune       = SeqChannel_sc_detune
sc_pad          = SeqChannel_sc_pad
; slot[1] macro-stream "active" flag (Component D): reuse the even-alignment pad
; byte (+57). Nonzero = a MacroTick reg-automation stream is running on this
; channel. On SfxChannel, +57 is sx_patch_base's LOW byte, but MacroTick + this
; flag are ONLY ever read with a MUSIC SeqChannel ix (Sequencer_Frame walks
; SeqChannels), so the SFX aliasing is never exercised — same discipline as
; sc_noise_mode/sx_priority at +55.
sc_macro_active = SeqChannel_sc_pad
```
(The first line is the existing anchor; the three new lines follow it.)

2. [ ] Add the TAG_MAC_* equates + a fixed-slot collision assert. In `sound_constants.asm`, immediately after the `MEV_PSGNOISE = $F2 ...` block ending at `:368` (the line `; the noise note then carries PITCH for the rate-3 tone-2 clock.`), and BEFORE the `; --- MEV_PAN / MEV_OPBIAS range + collision asserts (Task 6) ---` comment at `:370`, insert:
```
; --- slot[1] macro-stream PRIVATE tag namespace (Component D) -------------------
; These are NOT slot[0] MEV_* opcodes and NOT YM register values — they live only
; inside a macro body walked by MacroTick over sc_mod_ptr. Distinct low bytes,
; documented here as the single source of truth (Component E's packer emits the
; identical byte values; the sync guard in E asserts on these symbols).
;   TAG_MAC_NEXT  : advance exactly one frame (yield to the next MacroTick call)
;   TAG_MAC_REG   : + part(0/1) + reg + val : immediate YM write (repark $2A; $2A/$2B guarded)
;   TAG_MAC_LOOP  : + dw blob_offset (BE) : cursor = Snd_SongBase + offset, re-read
;   TAG_MAC_END   : disable this channel's macro stream (sc_mod_ptr = 0, mark inert)
TAG_MAC_NEXT    = $E0
TAG_MAC_REG     = $E1
TAG_MAC_LOOP    = $E2
TAG_MAC_END     = $E3
        ; the four tags must be distinct and contiguous in the $E0-$E3 PRIVATE block.
        if (TAG_MAC_NEXT <> $E0) || (TAG_MAC_REG <> $E1) || (TAG_MAC_LOOP <> $E2) || (TAG_MAC_END <> $E3)
          error "TAG_MAC_* must be the contiguous $E0-$E3 macro-stream tags"
        endif
```
(These share byte VALUES with the slot[0] `$E0-$E3` opcodes, which is intentional and harmless — they live in a disjoint namespace, never dispatched through `SeqOpcodeTable`.)

3. [ ] Add the `MacroTick` routine. In `engine/sound_sequencer.asm`, immediately after the `Seq_ContinueFetch` block (the `jp Sequencer_NextOpcode.fetch` at `:1184`) and BEFORE the `; ====...` banner for `SeqOpcodeTable` at `:1186`, insert:
```

; ======================================================================
; MacroTick — the slot[1] register-automation reader (Component D). Walks
; sc_mod_ptr executing tag-prefixed events until ONE frame is yielded
; (TAG_MAC_NEXT), then commits the cursor. Runs once/frame per active music
; channel, AFTER ModUpdate, BEFORE Sequencer_Channel (the arbitration order:
; named-slot contours render in ModUpdate -> slot[1] reg-writes here -> slot[0]
; opcodes in Sequencer_Channel). Gated by the caller on sc_mod_ptr != 0.
;
; In:  ix = SeqChannel (a MUSIC channel; the caller only walks SeqChannels).
; hl = the live cursor (local to this call): loaded from sc_mod_ptr, advanced
; over each event, committed back to sc_mod_ptr before every return/yield.
; Fm_YmWrite/Fm_ReparkDac preserve bc,de,hl,ix, so the cursor in hl survives a
; reg-write. TAG_MAC_END disables the stream (sc_mod_ptr = 0) so the caller's
; gate skips it next frame.
; Clobbers: af,bc,de,hl. Preserves ix.
; ======================================================================
MacroTick:
        ld      l, (ix+sc_mod_ptr)
        ld      h, (ix+sc_mod_ptr+1)     ; hl = macro-stream cursor
.fetch:
        ld      a, (hl)
        inc     hl                       ; consume the tag byte
        cp      TAG_MAC_NEXT             ; $E0 -> yield one frame
        jr      z, .next
        cp      TAG_MAC_REG              ; $E1 -> immediate reg write
        jr      z, .reg
        cp      TAG_MAC_LOOP             ; $E2 -> cursor = base + BE offset
        jr      z, .loop
        cp      TAG_MAC_END              ; $E3 -> disable the stream
        jr      z, .end
        ; unknown tag (defense-in-depth; the packer forbids these) -> disable the
        ; stream so a stray byte can't be re-walked forever.
        jr      .end

.next:
        ; yield: commit the cursor (pointing at the byte AFTER this tag) and return.
        ; Next frame resumes here. (Mirror the slot[0] commit-before-return at
        ; Sequencer_NextOpcode :590-591.)
        ld      (ix+sc_mod_ptr), l
        ld      (ix+sc_mod_ptr+1), h
        ret

.reg:
        ; TAG_MAC_REG + part + reg + val : immediate YM write + repark $2A. Reads
        ; three operand bytes (advancing hl), then writes via the Component-B
        ; primitive Fm_YmWrite (a=reg, c=val, b=part) and Fm_ReparkDac. GUARD:
        ; refuse reg == $2A and reg == $2B (the DAC data/enable regs) — a raw poke
        ; there would corrupt/silence the DAC stream; skip the write, keep walking.
        ld      c, (hl)
        inc     hl                       ; c = part (0/1)
        ld      b, c                     ; stash part in b (Fm_YmWrite wants part in b)
        ld      a, (hl)
        inc     hl                       ; a = reg
        ld      e, a                     ; e = reg (saved across the guard test)
        ld      c, (hl)
        inc     hl                       ; c = val
        cp      SND_REG_DAC_DATA         ; $2A?
        jr      z, .reg_skip
        cp      SND_REG_DAC_ENABLE       ; $2B?
        jr      z, .reg_skip
        ld      a, e                     ; a = reg (b=part, c=val already set)
        call    Fm_YmWrite               ; a=reg, c=val, b=part (preserves bc,de,hl,ix)
        call    Fm_ReparkDac             ; re-park $2A (preserves bc,de,hl,ix)
.reg_skip:
        jr      .fetch                   ; multiple regs per frame: keep walking

.loop:
        ; TAG_MAC_LOOP + dw blob_offset (BE) : cursor = Snd_SongBase + offset.
        ; Same "BE offset, handler adds base" convention as MEV_MACRO/the loader's
        ; mod_ptr rebase. Re-read in the same frame (no implicit yield) so a body
        ; that is pure REG..LOOP would spin — the packer guarantees every loop body
        ; contains a TAG_MAC_NEXT, exactly like slot[0]'s loop-body validation.
        ld      d, (hl)
        inc     hl                       ; d = offset hi (big-endian)
        ld      e, (hl)
        inc     hl                       ; e = offset lo
        ld      hl, (Snd_SongBase)       ; hl = song base
        add     hl, de                   ; hl = base + offset = absolute cursor
        jr      .fetch

.end:
        ; disable the stream: NULL sc_mod_ptr + clear the active flag so the caller's
        ; gate skips this channel next frame. (No cursor commit needed — it's inert.)
        xor     a
        ld      (ix+sc_mod_ptr), a
        ld      (ix+sc_mod_ptr+1), a
        ld      (ix+sc_macro_active), a
        ret
```

4. [ ] Build green + budget assert. Run:
```
cd /home/volence/sonic_hacks/aeon-music-expr && SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe
```
Expected: build completes, `s4.bin` produced, NO `fatal "Z80 sound driver code ... overruns state region"` (the `Z80_SOUND_SIZE <= SND_STATE_BASE ($16F0)` assert at `engine/z80_sound_driver.asm:1472-1474` holds — Phase-1 baseline left ~494 bytes free; this routine is ~70 bytes), and NO `error "TAG_MAC_* must be ..."`. Also run the budget tool:
```
cd /home/volence/sonic_hacks/aeon-music-expr && python3 tools/s4budget.py s4.lst s4.bin --summary
```
Expected: Z80 sound region reported under `$16F0` with headroom.

5. [ ] Commit.
```
cd /home/volence/sonic_hacks/aeon-music-expr && git add sound_constants.asm engine/sound_sequencer.asm && git commit -m "feat(sound): slot[1] MacroTick reader + TAG_MAC_* tags ($E0-$E3)

Walk sc_mod_ptr executing tag-prefixed reg-automation events (NEXT/REG/LOOP/
END) until one frame yields, committing the cursor. REG reuses Fm_YmWrite +
Fm_ReparkDac with a \$2A/\$2B DAC guard; LOOP rebases a BE blob offset via
Snd_SongBase. sc_macro_active aliases sc_pad (+57). Dead until D2 wires it in.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

**Controller verifies (emulator, not in this task):** N/A for D1 alone — it is unreachable code. The behavioral verification lands at D4.

---

### Task D2: wire MacroTick into the Sequencer_Frame channel loop

Call `MacroTick` once per active music channel, AFTER `ModUpdate` (named-slot contours) and BEFORE the tempo-gated `Sequencer_Channel` (slot[0]) — the arbitration order from the spec. Gate the call on `sc_mod_ptr != 0` so a single-stream song (every `sc_mod_ptr == 0`, the Moving Trucks baseline) pays only one cheap test per channel and runs byte-identically.

**Grounding (verified):**
- The channel loop is `Sequencer_Frame.chan_loop` (`engine/sound_sequencer.asm:62-85`): per active channel it `push bc` (`:65`), `call ModUpdate` (`:69`), runs the tempo accumulator (`:71-78`), `call Sequencer_Channel` on borrow (`:79`), `.chan_done: pop bc` (`:81`), then `add ix,de` / `djnz` (`:83-85`). `bc` (the `djnz` channel counter in `b`) is preserved across the calls by that `push/pop`. `ix` is preserved by both callees.
- Inserting `MacroTick` between `ModUpdate` (`:69`) and the tempo block (`:71`) places it after the named-slot contour render and before the slot[0] reader — exactly the spec arbitration order. It is inside the `push bc`/`pop bc` span, so `MacroTick`'s `bc` clobber is already covered.

**Files:**
- `engine/sound_sequencer.asm` (the `MacroTick` call site, inside `.chan_loop`)

**Steps:**

1. [ ] Insert the gated `MacroTick` call. In `engine/sound_sequencer.asm`, find the existing block (`:68-72`):
```
        ; (1) modulation layer — render state -> YM (write-on-change). ix preserved.
        call    ModUpdate

        ; (2) tempo accumulator: subtract 16 each frame; borrow => event-tick due.
```
Replace it with:
```
        ; (1) modulation layer — render state -> YM (write-on-change). ix preserved.
        call    ModUpdate

        ; (1b) slot[1] macro/reg-automation (Component D). ARBITRATION: after the
        ; named-slot contours (ModUpdate) and BEFORE the slot[0] reader below. Gated
        ; on sc_mod_ptr != 0 so a single-stream song (every channel NULL — the
        ; Moving Trucks baseline) pays one word-test per channel and is byte-identical.
        ; bc is already saved by the push above; ix is preserved by MacroTick.
        ld      a, (ix+sc_mod_ptr)
        or      (ix+sc_mod_ptr+1)
        call    nz, MacroTick

        ; (2) tempo accumulator: subtract 16 each frame; borrow => event-tick due.
```

2. [ ] Build green + budget assert.
```
cd /home/volence/sonic_hacks/aeon-music-expr && SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe
```
Expected: build completes; `Z80_SOUND_SIZE <= $16F0` assert holds (the call site adds ~9 bytes). No errors.

3. [ ] Commit.
```
cd /home/volence/sonic_hacks/aeon-music-expr && git add engine/sound_sequencer.asm && git commit -m "feat(sound): call MacroTick per channel after ModUpdate, before Sequencer_Channel

Arbitration order: named-slot contours (ModUpdate) -> slot[1] reg-automation
(MacroTick) -> slot[0] opcodes (Sequencer_Channel). Gated on sc_mod_ptr != 0,
so single-stream songs (all-NULL mod_ptr) pay one word-test and stay
byte-identical.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

**Controller verifies (emulator, not in this task):** Moving Trucks (all `sc_mod_ptr == 0`) renders byte/spectrum-faithful vs the prior baseline (no MacroTick ever runs); DEBUG golden self-test green. Full automation behavior is checked at D4.

---

### Task D3: MEV_MACRO ($F9) opcode + Seq_Op_Macro handler (slot[0] arm)

Add the slot[0] opcode that (re)arms a channel's slot[1] macro stream: consume a 2-byte rebased blob-ptr operand (BE, same convention as the loader's `mod_ptr`), set `sc_mod_ptr` + `sc_macro_active`, and reset. Header-armed streams (Component E emits a non-NULL header `mod_ptr`) already run via D2; this gives the musically-triggered retrigger.

**Grounding (verified):**
- `MEV_MACRO = $F9` is currently the `dw Seq_BadOpcode ; $F9 reserved` slot in `SeqOpcodeTable` (`engine/sound_sequencer.asm:1216`), index `($F9-$E0)=$19`. `$F7`/`$F8` are Components A/B; `$F9` is mine and is disjoint from the `$F3-$F6` Phase-2 reservations (`:1210-1213`).
- Handlers are entered with `hl` = stream ptr just past the opcode byte; they read operands advancing `hl`, then a zero-tick handler ends with `jp Seq_ContinueFetch` (`:683`) — NOT `jr` (the 1D repeat handlers pushed `Seq_ContinueFetch` out of `jr` range; verified at `:661`). The opcode equate + collision-assert style is the `if ... error` blocks near `sound_constants.asm:370-440` (e.g. the `MEV_PAN` assert at `:386`).
- The operand is a 2-byte BIG-ENDIAN blob offset; `absolute = Snd_SongBase + offset` (same as `engine/z80_sound_driver.asm:1188-1196`). This is a zero-tick state setter (no writer hook), so `hl` stays the live slot[0] stream ptr through the handler — no `push/pop hl` is needed around the body since nothing here calls a routine that clobbers `hl`; `jp Seq_ContinueFetch` keeps `hl` as the cursor (verified the handler convention at `:637-639`).

**Files:**
- `sound_constants.asm` (the `MEV_MACRO = $F9` equate + a fixed-slot collision-assert block mirroring the existing MEV_* asserts)
- `engine/sound_sequencer.asm` (the `Seq_Op_Macro` handler + the `SeqOpcodeTable` slot)

**Steps:**

1. [ ] Add the `MEV_MACRO` equate. In `sound_constants.asm`, immediately after the `TAG_MAC_END = $E3` block added in D1 step 2 (and after its closing `endif`), insert:
```
; --- Phase 3 Component D: slot[0] MEV_MACRO ($F9) — (re)arm the channel's slot[1]
; macro stream. + dw blob_offset (BE) : sc_mod_ptr = Snd_SongBase + offset, mark
; active, reset. Zero-tick. ($F7=MEV_FMENV, $F8=MEV_REGWRITE are sibling Phase-3
; opcodes; $F3-$F6 are Phase-2 reservations.)
MEV_MACRO       = $F9
        ; MEV_MACRO must be a command opcode (> MEV_NOTE_MAX), inside the $E0-$FF
        ; coordination block, on its assigned slot $F9, and clear of every allocated
        ; opcode AND the Phase-2 reservations $F3-$F6.
        if MEV_MACRO <= MEV_NOTE_MAX
          error "MEV_MACRO (\{MEV_MACRO}) must be a command opcode (> MEV_NOTE_MAX)"
        endif
        if (MEV_MACRO < MEV_VOL) || (MEV_MACRO > MEV_END)
          error "MEV_MACRO (\{MEV_MACRO}) must be inside the $E0-$FF coordination block"
        endif
        if MEV_MACRO <> $F9
          error "MEV_MACRO (\{MEV_MACRO}) must be $F9 (its assigned Phase-3 slot)"
        endif
        if (MEV_MACRO = MEV_VOL) || (MEV_MACRO = MEV_PATCH) || (MEV_MACRO = MEV_DAC) || (MEV_MACRO = MEV_NOTE_DUR) || (MEV_MACRO = MEV_PAN) || (MEV_MACRO = MEV_REPEAT_START) || (MEV_MACRO = MEV_REPEAT_END) || (MEV_MACRO = MEV_NOTE_RAW) || (MEV_MACRO = MEV_PITCHENV) || (MEV_MACRO = MEV_OPBIAS) || (MEV_MACRO = MEV_REGDELTA) || (MEV_MACRO = MEV_PSGENV) || (MEV_MACRO = MEV_MODSET) || (MEV_MACRO = MEV_NOTEFILL) || (MEV_MACRO = MEV_LOOP_POINT) || (MEV_MACRO = MEV_JUMP) || (MEV_MACRO = MEV_SPINREV) || (MEV_MACRO = MEV_SPINREV_RESET) || (MEV_MACRO = MEV_PSGNOISE) || (MEV_MACRO = MEV_END)
          error "MEV_MACRO (\{MEV_MACRO}) collides with an allocated $E0-$FF opcode"
        endif
```
(If Components A/B have already added `MEV_FMENV=$F7`/`MEV_REGWRITE=$F8` equates by the time this lands, also add `|| (MEV_MACRO = MEV_FMENV) || (MEV_MACRO = MEV_REGWRITE)` to the final collision `if`. They are disjoint by value, so omitting them only weakens the assert, never breaks the build — note for the controller.)

2. [ ] Add the `Seq_Op_Macro` handler. In `engine/sound_sequencer.asm`, immediately after the `Seq_Op_PsgEnv` handler (it ends with `jp Seq_ContinueFetch` at `:683`) and before the `; $F2 MEV_PSGNOISE ...` comment at `:685`, insert:
```

; $F9 MEV_MACRO + dw blob_offset (BE) : (re)arm the channel's slot[1] macro stream.
; sc_mod_ptr = Snd_SongBase + offset; mark active; reset to the body start. Zero-tick
; state setter (mirror of Seq_Op_PsgEnv) — no writer hook, so hl stays the live
; slot[0] stream ptr through the handler. The offset is BIG-ENDIAN, rebased to an
; absolute Z80 address exactly like the loader's mod_ptr parse (z80_sound_driver.asm
; :1188-1196) and TAG_MAC_LOOP. The packer (Component E) back-patches the offset to a
; macro-body blob it emits in the same song.
Seq_Op_Macro:
        ld      d, (hl)
        inc     hl                       ; d = offset hi (big-endian)
        ld      e, (hl)
        inc     hl                       ; e = offset lo  (hl now past the operand)
        push    hl                       ; save the live slot[0] stream ptr
        ld      hl, (Snd_SongBase)
        add     hl, de                   ; hl = base + offset = absolute body ptr
        ld      (ix+sc_mod_ptr), l
        ld      (ix+sc_mod_ptr+1), h     ; arm slot[1] cursor at the body start
        ld      a, 1
        ld      (ix+sc_macro_active), a  ; mark active (sc_pad alias)
        pop     hl                       ; restore the slot[0] stream ptr
        jp      Seq_ContinueFetch        ; jp (not jr): out of jr range, like the others
```
(The `push/pop hl` brackets the `Snd_SongBase` math which reuses `hl`; the slot[0] cursor is restored before `Seq_ContinueFetch` — obeys the hl-preservation rule.)

3. [ ] Wire the dispatch slot. In `engine/sound_sequencer.asm`, change the `SeqOpcodeTable` `$F9` entry (`:1216`) from:
```
        dw      Seq_BadOpcode            ; $F9 reserved
```
to:
```
        dw      Seq_Op_Macro             ; $F9 MEV_MACRO (arm slot[1])
```

4. [ ] Build green + budget assert.
```
cd /home/volence/sonic_hacks/aeon-music-expr && SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe
```
Expected: build completes; no `error "MEV_MACRO ... collides"` / `... must be $F9`; `Z80_SOUND_SIZE <= $16F0` holds (~25 bytes added). `s4.bin` produced.

5. [ ] Commit.
```
cd /home/volence/sonic_hacks/aeon-music-expr && git add sound_constants.asm engine/sound_sequencer.asm && git commit -m "feat(sound): MEV_MACRO (\$F9) + Seq_Op_Macro — arm slot[1] from the stream

2-byte BE blob-offset operand rebased via Snd_SongBase (same as the loader's
mod_ptr parse); sets sc_mod_ptr + sc_macro_active, resets to the body start.
Replaces the \$F9 Seq_BadOpcode dispatch slot. Fixed-slot collision asserts
mirror the existing MEV_* assert blocks.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

**Controller verifies (emulator, not in this task):** combined with D4's test song — a `MEV_MACRO` in a channel's slot[0] stream re-points `sc_mod_ptr` to a fresh body and the automation restarts from that body.

---

### Task D4: build + controller-verify handoff (looping reg-automation + DAC safety + MT regression)

No new engine code. This task is the integration build and the precise statement of what the CONTROLLER verifies in the emulator. It depends on D1-D3 (engine) and on Component E (the packer emitting a non-NULL header `mod_ptr` + a `TAG_MAC_*` macro body + `MEV_MACRO`). It produces a clean DEBUG build and hands the emulator checks to the controller.

**Files:** none (build + verification spec only).

**Steps:**

1. [ ] Full clean DEBUG sound build.
```
cd /home/volence/sonic_hacks/aeon-music-expr && SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh
```
Expected: build completes, `s4.bin` produced, `s4.log` shows no errors; the `Z80_SOUND_SIZE <= SND_STATE_BASE ($16F0)` assert (`engine/z80_sound_driver.asm:1472`) holds; the TAG_MAC_* and MEV_MACRO fixed-slot asserts pass.

2. [ ] Python suite green (the packer side, owned by E, must agree on the wire format this component reads).
```
cd /home/volence/sonic_hacks/aeon-music-expr && python3 -m pytest tools/test_song_packer.py tools/test_gen_sound_tables.py -q
```
Expected: all pass — in particular E's `TAG_MAC_*` byte values (`$E0/$E1/$E2/$E3`) and the BE `MEV_MACRO`/`TAG_MAC_LOOP` offset encoding match this component's asm (the cross-file sync guard).

3. [ ] Commit (build-marker / no-op tree change is expected to be empty; commit only if E added a test fixture this task references — otherwise skip). If there is nothing to stage, record the verification handoff in the PR body instead and proceed. (No `git add` of generated `s4.bin`.)

**Controller verifies (emulator — `oracle` MCP, captures ≤450 frames; NOT in implementer steps):**
- **Looping reg-automation:** a song whose channel header arms a non-NULL `mod_ptr` to a body `[TAG_MAC_REG, part, reg=$B0 (a non-critical FB/algorithm reg on an idle test channel), v0, TAG_MAC_NEXT, TAG_MAC_REG, part, reg=$B0, v1, TAG_MAC_NEXT, TAG_MAC_LOOP, <BE offset of body start>]`. Confirm via `tools/vgm_intranote.py` / the YM register stream that reg `$B0+ch` tracks `v0 → v1 → v0 …` once per frame and the loop wraps (cursor returns to body start, not running off the blob).
- **MEV_MACRO retrigger:** the same channel issues `MEV_MACRO` in slot[0] mid-song pointing at a second body; confirm `sc_mod_ptr` re-points and the automation restarts from the new body (read `sc_mod_ptr` via `emulator_z80_read` at the channel's SeqChannel; confirm the register stream switches).
- **DAC park safety (the load-bearing check):** a DAC drum hit immediately after a `TAG_MAC_REG` write — the drum plays cleanly (the `$2A` re-park via `Fm_ReparkDac` survived). Additionally confirm a body containing a `TAG_MAC_REG` with `reg=$2A` or `reg=$2B` is a NO-OP (guard skips the write; DAC stream uncorrupted).
- **MT regression:** Moving Trucks (every `sc_mod_ptr == 0`) renders byte/spectrum-faithful vs the pre-D baseline (MacroTick never runs — the D2 gate is a pure pass-through); DEBUG golden self-test green; no new lag (`Lag_Frame_Count` unchanged).

---

## Component E — Packer macro authoring + D8 route gate

### Task E1: Packer event classes — `FmEnv`/`RegWrite`/`Macro` + three MEV_* consts + `$2A/$2B` reject

**Files**
- `/home/volence/sonic_hacks/aeon-music-expr/tools/song_packer.py`
- `/home/volence/sonic_hacks/aeon-music-expr/tools/test_song_packer.py`

Grounding (verified against live source on `feat/music-expr-p1`):
- `song_packer.py` MEV_* consts live at lines 40–71; the last one is `MEV_END = 0xFF` (`:71`). `$F7/$F8/$F9` are NOT yet defined anywhere in `song_packer.py` or `sound_constants.asm` (grepped — only `MEV_PSGENV=$EB` and `MEV_PSGNOISE=$F2` use the F-range so far). The A/B/D asm components add the asm equates; this task adds the **Python** mirror as an inert standalone commit so `TestConstantsSync` (`test_song_packer.py:469-508`) stays green regardless of asm-vs-packer landing order (binding resolution (4)).
- `Event` base class is at `song_packer.py:108-114` (`encode()` raises `NotImplementedError`; `validate(route)` is a no-op). Existing zero-tick setter pattern to mirror: `PsgEnv` (`:211-227`), `Pan` (`:188-208`), `OpBias` (`:287-308`).
- `_FM_ROUTES`/`_PSG_ROUTES` sets are at `song_packer.py:92-94`.
- The test import block is `test_song_packer.py:15-29`.

Steps:

1. [ ] Add a **failing** test for the three new MEV consts + `FmEnv` encode. Append this class to `test_song_packer.py` immediately before the final `class TestConstantsSync` (`:469`):
   ```python
   class TestMacroEvents(unittest.TestCase):

       def test_new_mev_consts(self):
           self.assertEqual(song_packer.MEV_FMENV, 0xF7)
           self.assertEqual(song_packer.MEV_REGWRITE, 0xF8)
           self.assertEqual(song_packer.MEV_MACRO, 0xF9)

       def test_fmenv_encode(self):
           from song_packer import FmEnv
           self.assertEqual(FmEnv(3).encode(), bytes([0xF7, 0x03]))

       def test_fmenv_on_psg_route_rejected(self):
           from song_packer import FmEnv
           with self.assertRaises(PackError):
               FmEnv(3).validate(CHROUTE_PSG1)

       def test_fmenv_id_out_of_range(self):
           from song_packer import FmEnv
           with self.assertRaises(PackError):
               FmEnv(256).validate(CHROUTE_FM1)

       def test_regwrite_encode(self):
           from song_packer import RegWrite
           self.assertEqual(RegWrite(0, 0x90, 0x08).encode(),
                            bytes([0xF8, 0x00, 0x90, 0x08]))

       def test_regwrite_part_range(self):
           from song_packer import RegWrite
           with self.assertRaises(PackError):
               RegWrite(2, 0x90, 0x00).validate(CHROUTE_FM1)

       def test_regwrite_rejects_dac_regs(self):
           # $2A (DAC data) and $2B (DAC enable) corrupt/silence the DAC stream.
           from song_packer import RegWrite
           with self.assertRaises(PackError):
               RegWrite(0, 0x2A, 0x00).validate(CHROUTE_FM1)
           with self.assertRaises(PackError):
               RegWrite(0, 0x2B, 0x80).validate(CHROUTE_FM1)

       def test_regwrite_on_non_fm_route_rejected(self):
           from song_packer import RegWrite
           with self.assertRaises(PackError):
               RegWrite(0, 0x90, 0x00).validate(CHROUTE_PSG1)

       def test_macro_encode_default_ptr(self):
           # Macro encodes a 2-byte BE blob-offset operand; the offset is
           # back-patched by pack_song. The bare event encodes a placeholder 0.
           from song_packer import Macro
           self.assertEqual(Macro().encode(), bytes([0xF9, 0x00, 0x00]))
   ```

2. [ ] Run the test — it MUST fail (consts + classes absent):
   ```bash
   cd /home/volence/sonic_hacks/aeon-music-expr && python3 -m pytest tools/test_song_packer.py::TestMacroEvents -q
   ```
   Expected: errors/failures (e.g. `AttributeError: module 'song_packer' has no attribute 'MEV_FMENV'`).

3. [ ] Add the three MEV consts. In `song_packer.py`, immediately after `MEV_END = 0xFF` (`:71`), insert:
   ```python
   # Phase-3 macro/automation-spine opcodes (mirror of sound_constants.asm;
   # added by Components A/B/D on the asm side). Music-legal (see _validate_channel).
   MEV_FMENV = 0xF7            # + env_id: arm the FM carrier-TL volume envelope (1-based; 0=off)
   MEV_REGWRITE = 0xF8         # + part(0/1) + reg + val: inline raw YM2612 register write
   MEV_MACRO = 0xF9            # + ptr_hi + ptr_lo: (re)arm the slot[1] macro stream at a blob offset
   ```

4. [ ] Add the three event classes. In `song_packer.py`, insert immediately after the `PsgEnv` class (after its last line `:227`, before `class PsgNoise` at `:230`):
   ```python
   class FmEnv(Event):
       """Phase-3 FM carrier-TL volume envelope: arm the channel's 1-based env id
       (0=off). Mirrors PsgEnv but routes to the FM-TL renderer (FmEnvUpdate); the
       engine resets the contour cursor on each attack and folds sc_env_out into the
       carrier-TL delta in Fm_SetVolume. FM routes only. Zero-tick. The shared
       MEV_FMENV dispatch entry points at the same Seq_Op_PsgEnv handler (it sets
       sc_env + cursor regardless of route); the RENDERER picks FM vs PSG by route."""
       def __init__(self, env_id: int):
           self.env_id = env_id

       def encode(self) -> bytes:
           return bytes([MEV_FMENV, self.env_id & 0xFF])

       def validate(self, route):
           if route not in _FM_ROUTES:
               raise PackError(f"FmEnv on non-FM route {route}")
           if not (0 <= self.env_id <= 0xFF):
               raise PackError(f"FmEnv env_id {self.env_id} out of byte range")


   class RegWrite(Event):
       """Phase-3 inline raw YM2612 register write (slot[0]). Operands in stream
       order: part (0/1 — the explicit YM part, NOT derived from the channel), reg,
       val. The engine writes reg->addr port + val->data port for that part, then
       re-parks $2A. REFUSES reg $2A (DAC data) and $2B (DAC enable): an authored
       poke to those corrupts/silences the DAC stream. Zero-tick. FM routes only
       (the writer is the FM part-router)."""
       def __init__(self, part: int, reg: int, val: int):
           self.part = part
           self.reg = reg
           self.val = val

       def encode(self) -> bytes:
           return bytes([MEV_REGWRITE, self.part & 0xFF, self.reg & 0xFF,
                         self.val & 0xFF])

       def validate(self, route):
           if route not in _FM_ROUTES:
               raise PackError(f"RegWrite on non-FM route {route}")
           if self.part not in (0, 1):
               raise PackError(f"RegWrite part {self.part} must be 0 or 1")
           if self.reg in (0x2A, 0x2B):
               raise PackError(
                   f"RegWrite reg {self.reg:#x} is a DAC register ($2A/$2B) — "
                   f"refused (would corrupt the DAC stream)")
           if not (0 <= self.reg <= 0xFF):
               raise PackError(f"RegWrite reg {self.reg} out of byte range")
           if not (0 <= self.val <= 0xFF):
               raise PackError(f"RegWrite val {self.val} out of byte range")


   class Macro(Event):
       """Phase-3 (re)arm the slot[1] macro/automation stream (MacroTick) from
       slot[0]. Encodes a 2-byte BIG-ENDIAN blob-offset operand pointing at this
       channel's macro body; the offset is resolved (back-patched) by pack_song
       once body layout is known. The Z80 handler rebases it (base+offset, same
       convention as the loader's mod_ptr) into sc_mod_ptr + marks the stream
       active + resets. The bare event carries a placeholder 0 until packed."""
       def __init__(self):
           self.body_offset = 0     # back-patched by pack_song

       def encode(self) -> bytes:
           return bytes([MEV_MACRO, (self.body_offset >> 8) & 0xFF,
                         self.body_offset & 0xFF])
   ```

5. [ ] Run the test — it MUST pass:
   ```bash
   cd /home/volence/sonic_hacks/aeon-music-expr && python3 -m pytest tools/test_song_packer.py::TestMacroEvents -q
   ```
   Expected: all `TestMacroEvents` tests pass.

6. [ ] Run the full packer + tables suite — all green (TestConstantsSync must still pass: the new Python consts have no asm equate yet, and TestConstantsSync only iterates the **asm** equates, so unmatched Python consts are fine):
   ```bash
   cd /home/volence/sonic_hacks/aeon-music-expr && python3 -m pytest tools/test_song_packer.py tools/test_gen_sound_tables.py -q
   ```
   Expected: all tests pass (62+ passed).

7. [ ] Commit:
   ```bash
   cd /home/volence/sonic_hacks/aeon-music-expr && git add tools/song_packer.py tools/test_song_packer.py && git commit -m "feat(packer): FmEnv/RegWrite/Macro event classes + \$F7/\$F8/\$F9 consts

Add the three Phase-3 macro-spine MEV_* Python consts (inert, mirror the
A/B/D asm equates) and their event classes. RegWrite.validate refuses
reg \$2A/\$2B (DAC data/enable) and non-FM routes; Macro encodes a 2-byte
BE placeholder operand that pack_song back-patches to the body offset.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
   ```

---

### Task E2: Macro-body emitter (tag grammar) + back-patched header `mod_ptr` + `MEV_MACRO`/`TAG_MAC_LOOP` offset resolution

**Files**
- `/home/volence/sonic_hacks/aeon-music-expr/tools/song_packer.py`
- `/home/volence/sonic_hacks/aeon-music-expr/tools/test_song_packer.py`

Grounding:
- `ChannelDesc` is at `song_packer.py:508-511` (`__init__(self, route, events)`).
- `pack_song` is at `:625-688`. The header `mod_ptr` is hard-NULL at `:682-683` (`out.append(0x00)` ×2). `header_len = 4 + 2 + 5*n + 2` (`:662`). Command-stream offsets start at `header_len` and accumulate (`:665-669`). The `cmd_ptr` BE emit is at `:680-681`.
- Binding cross-task resolution (1)/(2): the TAG bytes the D-side reader expects are `TAG_MAC_NEXT=0xE0`, `TAG_MAC_REG=0xE1`, `TAG_MAC_LOOP=0xE2`, `TAG_MAC_END=0xE3`. `TAG_MAC_REG` carries `part, reg, val` (3 operands); `TAG_MAC_LOOP` carries a **2-byte BIG-ENDIAN body-start offset** (the D reader adds `Snd_SongBase`); `TAG_MAC_NEXT`/`TAG_MAC_END` are bare 1-byte tags. The `$2A/$2B` reg reject + control-code-valued-data reject apply to `TAG_MAC_REG` operands.

Steps:

1. [ ] Add a **failing** test for the body emitter + non-NULL header `mod_ptr`. Append to `class TestMacroEvents` in `test_song_packer.py`:
   ```python
       def test_tag_consts(self):
           self.assertEqual(song_packer.TAG_MAC_NEXT, 0xE0)
           self.assertEqual(song_packer.TAG_MAC_REG, 0xE1)
           self.assertEqual(song_packer.TAG_MAC_LOOP, 0xE2)
           self.assertEqual(song_packer.TAG_MAC_END, 0xE3)

       def test_emit_macro_body_basic(self):
           # A reg write, a frame yield, then end.
           from song_packer import emit_macro_body, MacReg, MacNext, MacEnd
           body = emit_macro_body([MacReg(0, 0x90, 0x08), MacNext(), MacEnd()],
                                  body_base=0)
           self.assertEqual(body, bytes([0xE1, 0x00, 0x90, 0x08, 0xE0, 0xE3]))

       def test_emit_macro_body_loop_target_is_be_body_base(self):
           # TAG_MAC_LOOP carries a 2-byte BE offset = the body's start in the blob.
           from song_packer import emit_macro_body, MacReg, MacNext, MacLoop
           body = emit_macro_body([MacReg(0, 0x90, 0x08), MacNext(), MacLoop()],
                                  body_base=0x0140)
           # ...E0 then E2 01 40 (loop -> body_base 0x0140, big-endian).
           self.assertEqual(body[-3:], bytes([0xE2, 0x01, 0x40]))

       def test_emit_macro_body_rejects_dac_reg(self):
           from song_packer import emit_macro_body, MacReg, MacEnd, PackError
           with self.assertRaises(PackError):
               emit_macro_body([MacReg(0, 0x2A, 0x00), MacEnd()], body_base=0)

       def test_emit_macro_body_rejects_part(self):
           from song_packer import emit_macro_body, MacReg, MacEnd
           with self.assertRaises(PackError):
               emit_macro_body([MacReg(2, 0x90, 0x00), MacEnd()], body_base=0)

       def test_channel_with_macro_body_emits_nonnull_mod_ptr_and_blob(self):
           # A channel that carries a macro body: pack_song must (a) emit a
           # non-NULL header mod_ptr at the channel's +3/+4, pointing at the
           # body's blob offset, and (b) append the body bytes at that offset.
           from song_packer import MacReg, MacNext, MacEnd
           ch = ChannelDesc(CHROUTE_FM1,
                            [Patch(0), Vol(100), SetDur(0x10),
                             LoopPoint(), Note(57), Jump()])
           ch.macro_body = [MacReg(0, 0x90, 0x08), MacNext(), MacEnd()]
           song = SongDesc(tempo=16, channels=[ch])
           blob = pack_song(song)
           # header: flags,tempo,tempo_base,count, dw pitchtab, then ch record at +6.
           mod_ptr = (blob[6 + 3] << 8) | blob[6 + 4]
           self.assertNotEqual(mod_ptr, 0)
           self.assertEqual(blob[mod_ptr:mod_ptr + 6],
                            bytes([0xE1, 0x00, 0x90, 0x08, 0xE0, 0xE3]))

       def test_channel_without_macro_body_keeps_null_mod_ptr(self):
           # Regression: a normal channel still emits mod_ptr = 0.
           song = _simple_song()
           blob = pack_song(song)
           self.assertEqual((blob[6 + 3] << 8) | blob[6 + 4], 0)

       def test_macro_event_operand_backpatched_to_body(self):
           # A slot[0] Macro() event resolves its 2-byte operand to the same blob
           # offset as the channel's macro body.
           from song_packer import Macro, MacReg, MacNext, MacEnd
           ch = ChannelDesc(CHROUTE_FM1,
                            [Patch(0), Vol(100), SetDur(0x10),
                             LoopPoint(), Macro(), Note(57), Jump()])
           ch.macro_body = [MacReg(0, 0x90, 0x08), MacNext(), MacEnd()]
           song = SongDesc(tempo=16, channels=[ch])
           blob = pack_song(song)
           mod_ptr = (blob[6 + 3] << 8) | blob[6 + 4]
           # find the MEV_MACRO ($F9) byte in the command stream and read its operand.
           cmd_ptr = (blob[6 + 1] << 8) | blob[6 + 2]
           i = blob.index(0xF9, cmd_ptr)
           operand = (blob[i + 1] << 8) | blob[i + 2]
           self.assertEqual(operand, mod_ptr)
   ```

2. [ ] Run the test — it MUST fail (tags/classes/`emit_macro_body`/`macro_body` plumbing absent):
   ```bash
   cd /home/volence/sonic_hacks/aeon-music-expr && python3 -m pytest tools/test_song_packer.py::TestMacroEvents -q
   ```
   Expected: failures (e.g. `AttributeError: ... 'TAG_MAC_NEXT'`).

3. [ ] Add the TAG consts + macro-event classes + `emit_macro_body`. In `song_packer.py`, insert immediately after the `Macro` class (added in E1, before `class PsgNoise`):
   ```python
   # --- slot[1] macro-stream PRIVATE tag namespace (mirror of sound_constants.asm
   # TAG_MAC_*; the D-side MacroTick reader consumes these EXACT bytes). These are
   # NOT slot[0] MEV opcodes and NOT YM register values — a distinct namespace. ---
   TAG_MAC_NEXT = 0xE0     # yield: advance exactly one frame
   TAG_MAC_REG = 0xE1      # + part(0/1) + reg + val: immediate YM write + repark ($2A/$2B guarded)
   TAG_MAC_LOOP = 0xE2     # + body_base_hi + body_base_lo (BE): cursor = body start (reader adds Snd_SongBase)
   TAG_MAC_END = 0xE3      # disable the stream (mark inert)


   class MacEvent:
       """Base slot[1] macro-stream event. encode(body_base) -> bytes."""
       def encode(self, body_base: int) -> bytes:
           raise NotImplementedError


   class MacNext(MacEvent):
       """Yield: advance exactly one frame."""
       def encode(self, body_base: int) -> bytes:
           return bytes([TAG_MAC_NEXT])


   class MacReg(MacEvent):
       """Immediate YM2612 register write in the macro stream: part(0/1), reg, val.
       Refuses reg $2A/$2B (DAC data/enable) and a control-code-valued data byte
       (a val that collides with a TAG_MAC_* byte would be safe here because tags
       are operand-position-decoded, but we reject it to match the spec's
       control-code-as-data guard and keep bodies inspectable)."""
       def __init__(self, part: int, reg: int, val: int):
           self.part = part
           self.reg = reg
           self.val = val

       def encode(self, body_base: int) -> bytes:
           if self.part not in (0, 1):
               raise PackError(f"MacReg part {self.part} must be 0 or 1")
           if self.reg in (0x2A, 0x2B):
               raise PackError(
                   f"MacReg reg {self.reg:#x} is a DAC register ($2A/$2B) — refused")
           if not (0 <= self.reg <= 0xFF):
               raise PackError(f"MacReg reg {self.reg} out of byte range")
           if not (0 <= self.val <= 0xFF):
               raise PackError(f"MacReg val {self.val} out of byte range")
           if TAG_MAC_NEXT <= self.val <= TAG_MAC_END:
               raise PackError(
                   f"MacReg val {self.val:#x} collides with a TAG_MAC_* control "
                   f"byte (${TAG_MAC_NEXT:02X}..${TAG_MAC_END:02X}) — reject "
                   f"control-code-valued data")
           return bytes([TAG_MAC_REG, self.part & 0xFF, self.reg & 0xFF,
                         self.val & 0xFF])


   class MacLoop(MacEvent):
       """Loop to the body start: emits TAG_MAC_LOOP + a 2-byte BIG-ENDIAN
       body_base offset (where this channel's macro body begins in the blob).
       The D-side reader adds Snd_SongBase to rebase it."""
       def encode(self, body_base: int) -> bytes:
           return bytes([TAG_MAC_LOOP, (body_base >> 8) & 0xFF, body_base & 0xFF])


   class MacEnd(MacEvent):
       """Disable the stream (mark inert)."""
       def encode(self, body_base: int) -> bytes:
           return bytes([TAG_MAC_END])


   def emit_macro_body(events, body_base: int) -> bytes:
       """Pack a slot[1] macro body (a list of MacEvent) to bytes. body_base is the
       blob offset where this body begins (known at body-layout time); it is the
       value a MacLoop encodes for its 2-byte BE loop target. Validates the
       $2A/$2B reg reject + control-code-as-data via each MacReg.encode()."""
       if not events:
           raise PackError("empty macro body")
       if not isinstance(events[-1], (MacEnd, MacLoop)):
           raise PackError("macro body not terminated by MacEnd or MacLoop")
       out = bytearray()
       for ev in events:
           out += ev.encode(body_base)
       return bytes(out)
   ```

4. [ ] Add an optional `macro_body` attribute on `ChannelDesc`. Replace the `ChannelDesc.__init__` body at `song_packer.py:508-511`:
   ```python
   class ChannelDesc:
       def __init__(self, route: int, events: list, macro_body=None):
           self.route = route
           self.events = events
           # Optional slot[1] macro stream (a list of MacEvent). None/[] = NULL
           # mod_ptr (single-stream). When present, pack_song lays the body out
           # after the slot[0] command streams and emits a non-NULL header mod_ptr.
           self.macro_body = macro_body
   ```

5. [ ] Rewrite `pack_song`'s layout + header emit to (a) lay macro bodies after command streams, (b) back-patch `Macro` operands + `MacLoop` targets, (c) emit the header `mod_ptr`. Replace the block from `streams = [_validate_channel(ch) for ch in song.channels]` (`song_packer.py:656`) through the end of the function (`:688`) with:
   ```python
       streams = [_validate_channel(ch) for ch in song.channels]

       n = len(song.channels)
       # Phase 3 C-ready header:
       #   flags, tempo, tempo_base, count, dw pitchtable_ptr,
       #   (route + dw cmd_ptr + dw mod_ptr)*n, dw patch_table_ptr.
       header_len = 4 + 2 + 5 * n + 2

       # Command-stream (slot[0]) offsets relative to blob start.
       offsets = []
       cur = header_len
       for s in streams:
           offsets.append(cur)
           cur += len(s)

       # Macro bodies (slot[1]) lay out AFTER all command streams. Each body's
       # base offset is known here, so MacLoop targets + the Macro() slot[0]
       # operand + the header mod_ptr all resolve to it (back-patch).
       mod_offsets = [0] * n                # 0 = NULL (single-stream channel)
       macro_bodies = [b""] * n
       for i, ch in enumerate(song.channels):
           body_evs = getattr(ch, "macro_body", None)
           if not body_evs:
               continue
           body_base = cur
           body = emit_macro_body(body_evs, body_base)
           # Back-patch every Macro() event in this channel's slot[0] stream to
           # point at this body. (Multiple Macro() arms re-point the same body.)
           for ev in ch.events:
               if isinstance(ev, Macro):
                   ev.body_offset = body_base
           mod_offsets[i] = body_base
           macro_bodies[i] = body
           cur += len(body)

       # Re-encode the command streams AFTER back-patching Macro operands (the
       # first pass above encoded Macro() with body_offset=0).
       streams = [_validate_channel(ch) for ch in song.channels]

       out = bytearray()
       out.append(song.flags & 0xFF)
       out.append(song.tempo & 0xFF)
       out.append(song.tempo_base & 0xFF)
       out.append(n & 0xFF)
       out.append((pitchtable_offset >> 8) & 0xFF)   # pitchtable_ptr hi (BE)
       out.append(pitchtable_offset & 0xFF)          # pitchtable_ptr lo (0 = default)
       for ch, off, mod in zip(song.channels, offsets, mod_offsets):
           out.append(ch.route & 0xFF)
           out.append((off >> 8) & 0xFF)   # cmd_ptr big-endian
           out.append(off & 0xFF)
           out.append((mod >> 8) & 0xFF)   # mod_ptr big-endian (0 = NULL slot[1])
           out.append(mod & 0xFF)
       out.append(0x00)                    # patch_table_ptr hi (wired by loader)
       out.append(0x00)                    # patch_table_ptr lo
       for s in streams:
           out += s
       for body in macro_bodies:
           out += body
       return bytes(out)
   ```
   Note for the controller: `_validate_channel` is pure (it re-encodes `ch.events` each call), so calling it twice is safe; the second pass picks up the back-patched `Macro.body_offset`. `_validate_channel` does not validate `Macro`/`FmEnv`/`RegWrite` route legality yet — that gate lands in E3. (This task only needs the layout + back-patch; the E2 tests use FM channels so no gate is required to make them pass.)

6. [ ] Run the test — it MUST pass:
   ```bash
   cd /home/volence/sonic_hacks/aeon-music-expr && python3 -m pytest tools/test_song_packer.py::TestMacroEvents -q
   ```
   Expected: all `TestMacroEvents` tests pass.

7. [ ] Run the full suite — all green (the existing `TestHeader` tests read `mod_ptr` at `off+3/+4` and assert 0 for `_simple_song`, which carries no `macro_body`, so they still pass):
   ```bash
   cd /home/volence/sonic_hacks/aeon-music-expr && python3 -m pytest tools/test_song_packer.py tools/test_gen_sound_tables.py -q
   ```
   Expected: all tests pass.

8. [ ] Commit:
   ```bash
   cd /home/volence/sonic_hacks/aeon-music-expr && git add tools/song_packer.py tools/test_song_packer.py && git commit -m "feat(packer): slot[1] macro-body emitter + back-patched mod_ptr

emit_macro_body packs a tag-prefixed slot[1] stream (TAG_MAC_NEXT=\$E0/
REG=\$E1/LOOP=\$E2/END=\$E3) matching the D-side MacroTick reader.
MacReg refuses reg \$2A/\$2B + control-code-valued data; MacLoop carries
a 2-byte BE body-start target. ChannelDesc.macro_body lays the body out
after the command streams; pack_song back-patches the header mod_ptr and
every slot[0] Macro() operand to the body offset.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
   ```

---

### Task E3: D8 music-legal route gate + TAG_MAC_* cross-file sync guard

**Files**
- `/home/volence/sonic_hacks/aeon-music-expr/tools/song_packer.py`
- `/home/volence/sonic_hacks/aeon-music-expr/tools/test_song_packer.py`

Grounding:
- `_validate_channel` is at `song_packer.py:542-622`. It calls `ev.validate(ch.route)` per event (`:554`) but has **no** music-legal/reject-by-route construct — only init-ordering (`:567-612`). This is the D8 gap (spec §9). The new expression events validate their own route legality (FM-only for `FmEnv`/`RegWrite`; `Macro` is FM-armed), so they are already accepted on a music (any-route) channel — the gate here is the **explicit whitelist + a per-event allow check** so a future "music-illegal" classification can reject by route without silently dropping. Because `song_packer.py` IS the music-song builder, the gate is: confirm `$F7/$F8/$F9`/`MEV_PSGENV` are NOT rejected on a music channel (and are emitted), and document them music-legal.
- `TestConstantsSync` is at `test_song_packer.py:469-508`; `_parse_asm_equates` (`:476-494`) parses `MEV_*` + `CHROUTE_*` equates with `mev_re`/`chr_re`. The D-component adds `TAG_MAC_*` equates to `sound_constants.asm`. Binding resolution (3): extend `TestConstantsSync` to ALSO parse `TAG_MAC_*` and assert `song_packer.py` mirrors them, so the tag bytes can never drift.

Steps:

1. [ ] Add a **failing** test: the music-legal gate accepts the expression opcodes on a music channel, and the TAG sync guard parses `TAG_MAC_*` from the asm. Append to `class TestMacroEvents` (the gate tests) and extend `TestConstantsSync` (the guard):
   ```python
       def test_music_song_accepts_expression_opcodes(self):
           # A music channel emitting MEV_PSGENV/$F7/$F8/$F9 must NOT be rejected
           # or silently dropped (D8 music-legal route gate).
           from song_packer import FmEnv, RegWrite, Macro, PsgEnv
           fm = ChannelDesc(CHROUTE_FM1, [
               Patch(0), Vol(100), SetDur(0x10), LoopPoint(),
               FmEnv(2), RegWrite(0, 0x90, 0x08), Macro(),
               Note(57), Jump()])
           fm.macro_body = None
           psg = ChannelDesc(CHROUTE_PSG1, [
               Vol(90), PsgEnv(3), SetDur(0x10), LoopPoint(), Note(57), Jump()])
           blob = pack_song(SongDesc(tempo=16, channels=[fm, psg]))
           self.assertIn(0xF7, blob)    # MEV_FMENV present, not dropped
           self.assertIn(0xF8, blob)    # MEV_REGWRITE
           self.assertIn(0xF9, blob)    # MEV_MACRO
           self.assertIn(0xEB, blob)    # MEV_PSGENV

       def test_music_illegal_opcode_is_rejected_not_dropped(self):
           # The gate must REJECT (not silently emit) an opcode flagged
           # music-illegal. MEV_SPINREV_RESET ($F1) is dispatch-folded and must
           # never appear in a stream; assert the gate rejects a raw event for it.
           from song_packer import _MUSIC_ILLEGAL_OPCODES
           self.assertIn(0xF1, _MUSIC_ILLEGAL_OPCODES)
   ```
   And REPLACE the body of `TestConstantsSync._parse_asm_equates` (`test_song_packer.py:476-494`) and `test_mev_and_chroute_in_sync` (`:496-508`) with:
   ```python
       @staticmethod
       def _parse_asm_equates():
           # sound_constants.asm sits at the repo root; tests live in <repo>/tools/.
           repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
           asm_path = os.path.join(repo_root, "sound_constants.asm")
           mev, chroute, tag = {}, {}, {}
           # e.g. "MEV_REST = $80 ; ..."  /  "CHROUTE_FM1 = 0"  /  "TAG_MAC_NEXT = $E0"
           mev_re = re.compile(r"^\s*(MEV_[A-Z0-9_]+)\s*=\s*\$([0-9A-Fa-f]+)")
           chr_re = re.compile(r"^\s*(CHROUTE_[A-Z0-9_]+)\s*=\s*(\d+)")
           tag_re = re.compile(r"^\s*(TAG_MAC_[A-Z0-9_]+)\s*=\s*\$([0-9A-Fa-f]+)")
           with open(asm_path) as f:
               for line in f:
                   m = mev_re.match(line)
                   if m:
                       mev[m.group(1)] = int(m.group(2), 16)
                       continue
                   c = chr_re.match(line)
                   if c:
                       chroute[c.group(1)] = int(c.group(2), 10)
                       continue
                   t = tag_re.match(line)
                   if t:
                       tag[t.group(1)] = int(t.group(2), 16)
           return mev, chroute, tag

       def test_mev_and_chroute_in_sync(self):
           mev, chroute, tag = self._parse_asm_equates()
           # Sanity: the parse actually found the equates (guards against a moved
           # file or a regex that silently matches nothing).
           self.assertIn("MEV_REST", mev)
           self.assertIn("CHROUTE_DAC", chroute)
           for name, asm_val in {**mev, **chroute}.items():
               py_val = getattr(song_packer, name, None)
               self.assertIsNotNone(
                   py_val, f"{name} present in sound_constants.asm but not song_packer.py")
               self.assertEqual(
                   py_val, asm_val,
                   f"{name}: song_packer.py={py_val} != sound_constants.asm={asm_val}")

       def test_tag_mac_in_sync(self):
           # The slot[1] macro tag bytes must match between the packer emitter and
           # the D-side MacroTick reader (sound_constants.asm TAG_MAC_*), so the
           # bytes can never silently drift. Skip cleanly until the asm equates
           # land (D component) — but once present, every one must mirror.
           _, _, tag = self._parse_asm_equates()
           if not tag:
               self.skipTest("TAG_MAC_* equates not yet in sound_constants.asm "
                             "(added by the MacroTick / Component D task)")
           for name, asm_val in tag.items():
               py_val = getattr(song_packer, name, None)
               self.assertIsNotNone(
                   py_val, f"{name} in sound_constants.asm but not song_packer.py")
               self.assertEqual(
                   py_val, asm_val,
                   f"{name}: song_packer.py={py_val} != sound_constants.asm={asm_val}")
   ```

2. [ ] Run the test — it MUST fail (`_MUSIC_ILLEGAL_OPCODES` absent; the gate not wired):
   ```bash
   cd /home/volence/sonic_hacks/aeon-music-expr && python3 -m pytest tools/test_song_packer.py::TestMacroEvents::test_music_illegal_opcode_is_rejected_not_dropped tools/test_song_packer.py::TestMacroEvents::test_music_song_accepts_expression_opcodes -q
   ```
   Expected: failure (`ImportError`/`AttributeError` for `_MUSIC_ILLEGAL_OPCODES`).

3. [ ] Add the music-legal gate. In `song_packer.py`, immediately after the `_PSG_ROUTES` set (`:94`), insert:
   ```python
   # --- D8 music-legal opcode gate ---------------------------------------
   # song_packer IS the music-song builder, so every opcode it can emit is
   # music-legal BY CONSTRUCTION except the dispatch-folded ones that must never
   # appear in a stream (the engine maps them to Seq_BadOpcode). $F1
   # (MEV_SPINREV_RESET) is reset-by-dispatch (Sfx_BeginSound zeroes the rev), so
   # a raw event encoding it is music-ILLEGAL — reject, never silently emit. The
   # Phase-3 expression opcodes ($F7/$F8/$F9) + MEV_PSGENV ($EB) are explicitly
   # music-LEGAL (this set documents that intent for D8 traceability).
   # MEV_SPINREV_RESET already exists at song_packer.py:69 — reference it, do NOT redefine
   _MUSIC_ILLEGAL_OPCODES = frozenset({MEV_SPINREV_RESET})
   _MUSIC_LEGAL_EXPRESSION_OPCODES = frozenset({
       MEV_PSGENV, MEV_FMENV, MEV_REGWRITE, MEV_MACRO})
   ```
   Note: `MEV_PSGENV` is defined at `:66`, so this block (after `:94`) sees it. `MEV_FMENV/REGWRITE/MACRO` are defined in E1 (after `:71`), also before `:94`'s successor lines — confirm order (these consts precede the `_PSG_ROUTES` set, which is at the original `:92-94`; the E1 inserts are at ~`:72`, so the ordering holds).

4. [ ] Wire the gate into `_validate_channel`. In `song_packer.py`, inside the `for ev in ch.events:` loop, immediately after `ev.validate(ch.route)` (`:554`), insert:
   ```python
           first = ev.encode()[:1]
           if first and first[0] in _MUSIC_ILLEGAL_OPCODES:
               raise PackError(
                   f"opcode {first[0]:#x} is music-illegal (dispatch-folded; the "
                   f"engine maps it to Seq_BadOpcode) — must not appear in a "
                   f"music stream")
   ```
   Note: every `Event.encode()` returns a non-empty `bytes` whose first byte is the opcode (verified for all classes: `Note`/`Rest` are `$80+`, the rest are `$E0-$FF`); `encode()` is pure, so calling it for the gate check is side-effect-free. There is no event class for `$F1` today (the spec deliberately omits one), so this gate is a guard against a future raw-opcode event — the test asserts membership of the set, which is the contract D8 closes.

5. [ ] Run the test — it MUST pass:
   ```bash
   cd /home/volence/sonic_hacks/aeon-music-expr && python3 -m pytest tools/test_song_packer.py::TestMacroEvents tools/test_song_packer.py::TestConstantsSync -q
   ```
   Expected: `test_music_song_accepts_expression_opcodes`, `test_music_illegal_opcode_is_rejected_not_dropped` pass; `test_tag_mac_in_sync` SKIPS (asm equates not landed in this worktree yet) and `test_mev_and_chroute_in_sync` passes.

6. [ ] Run the full suite — all green (skips allowed):
   ```bash
   cd /home/volence/sonic_hacks/aeon-music-expr && python3 -m pytest tools/test_song_packer.py tools/test_gen_sound_tables.py -q
   ```
   Expected: all tests pass or skip (no failures/errors).

7. [ ] Commit:
   ```bash
   cd /home/volence/sonic_hacks/aeon-music-expr && git add tools/song_packer.py tools/test_song_packer.py && git commit -m "feat(packer): D8 music-legal opcode gate + TAG_MAC_* sync guard

Add _MUSIC_ILLEGAL_OPCODES (\$F1 dispatch-folded) + _validate_channel
rejection so a music stream can never silently carry a music-illegal
opcode (D8). Document \$F7/\$F8/\$F9/\$EB music-legal. Extend
TestConstantsSync to parse TAG_MAC_* from sound_constants.asm and assert
song_packer mirrors them (skips until the D component lands the asm
equates), so the slot[1] tag bytes can never drift between packer + reader.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
   ```

---

**CONTROLLER VERIFICATION (after E1–E3 and the asm-side A/B/D components have landed):** once `sound_constants.asm` carries `MEV_FMENV/REGWRITE/MACRO` and `TAG_MAC_NEXT/REG/LOOP/END`, re-run `python3 -m pytest tools/test_song_packer.py tools/test_gen_sound_tables.py -q` — `TestConstantsSync::test_tag_mac_in_sync` and `test_mev_and_chroute_in_sync` will then ACTIVELY assert the Python consts equal the asm equates (no longer skip), proving D and E agree on every byte. This is the cross-file drift guard; it is the gate the controller checks that the packer bytes match the D asm reader.

---


---

## Self-Review — spec coverage

| Spec section | Implemented by |
|---|---|
| §3.3 named contour slots + §4 FM-TL vol-env (flagship volume macro, FM+PSG) | Component A (A1 renderer+fold+wiring, A2 table+resolver, A3 `MEV_FMENV $F7` arm, A4 verify) |
| §5 `MEV_REGWRITE` (inline raw write, `$2A/$2B` guard, re-park) | Component B (B1 opcode+handler, B2 verify) |
| §6 SSG-EG (FmPatch 26→32, `$90` group, re-export, load-time) | Component C (C1 struct+`Fm_PatchPtr` shift, C2 `$90` group, C3 re-export, C4 verify) |
| §3.4 slot[1] `MacroTick` reg-automation + `MEV_MACRO $F9` | Component D (D1 grammar+reader, D2 `Sequencer_Frame` wiring, D3 `MEV_MACRO`, D4 verify) |
| §9 packer authoring (`FmEnv`/`RegWrite`/`Macro` + body emitter + header `mod_ptr`) + D8 route gate | Component E (E1 events+consts, E2 body emitter+`mod_ptr` back-patch, E3 D8 gate) |
| §7 reserved pitch/pan slots | RESERVED by documentation only — no task, no RAM until a future phase makes them live (the `{id,cursor,out}` convention + slot-id allocation are recorded in the spec; making one live later is +3→+4 even bytes + a renderer hook, non-breaking). |
| §8 RAM plan (0 new per-channel bytes; struct stays 58/even) | Cursor = `sc_mod_ptr` (existing); volume state = `sc_env` (existing); reg-stream flag = `sc_pad` alias (D1, 0 new); `sc_detune` left for Phase-2. |
| §10 build asserts | `FmPatch_len==32` (C1), opcode fixed-slot asserts (A3/B1/D3), `TAG_MAC_*` distinctness + sync (D1/E), the `$16F0` ceiling (every build). |
| §11 verification | Controller-verify handoffs A4/B2/C4/D4 (FM swell, reg+DAC-safety, SSG-EG timbre, looping reg-automation) + Moving Trucks byte/spectrum regression on every component (fast paths when `sc_env=0`/`sc_mod_ptr=NULL`). |
| §12 phasing | A → B → C → D → E (matches the spec's FM-env → REGWRITE → SSG-EG → MacroTick → packer order). |

**Placeholder scan:** no TBD/TODO; every code step carries complete asm/python in fenced blocks; the only intentional "no build here" steps (A1, C1, C2) are the documented intra-component red-build units (§0). **Type/symbol consistency:** the cross-task symbol set (`FmEnvUpdate`/`FmVolEnv_Resolve`/`FmVolEnvCtl_*`, `Seq_Op_RegWrite`, `Seq_Op_Macro`, `MacroTick`, `sc_macro_active`, `MEV_FMENV/REGWRITE/MACRO=$F7/$F8/$F9`, `TAG_MAC_*=$E0–$E3`, `Fm_YmWrite`/`Fm_ReparkDac` reuse, `SND_REG_OP_SSG_EG=$90`, `FmPatch_len=32`) was adversarially cross-checked across all five components — defined once, consumed consistently.
