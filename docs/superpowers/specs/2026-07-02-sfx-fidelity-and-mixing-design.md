# SFX Fidelity + Best-in-Class Mixing — Design

**Date:** 2026-07-02
**Status:** STAGE B/C SHIPPED (2026-07-07, `feat/sfx-fidelity-stage-bc` — plan `2026-07-03-sfx-fidelity-stage-bc.md`).
All §5/§7 features landed + oracle-verified: per-SFX `sfh_gain` fold (FM TL + PSG atten), per-SFX
`sfh_duck` (deepest-active wins; global threshold/depth retired), non-latching priority (bit 7),
authored instance caps (oldest-slot kill), continuous-SFX class (tri-state `sx_extend` re-ping).
`SfxChannel` grew 64→68 (`sx_gain`+64/`sx_duck`+65/`sx_extend`+66; `sx_pad`@+58 kept 0 — it aliases
`SeqChannel.sc_detune`, read on SFX ix). Two plan defects were caught in review/verification and fixed:
(1) `sx_gain` must NOT reuse +58 (detune aliasing); (2) **the bit-7 non-latching flag collided with the
8-bit priority scale — `SFXPRI_*` rescaled to 7-bit ($10/$20/$30/$40/$60), bit 7 now reserved as the
flag, guarded by a build-time fatal + pytest.** Oracle: spindash stores correct `sx_priority=$40` (was
$00), 4-FM-SFX contention steals lowest (roll $30) leaving death $60 + spindash $40, cap=1, no duck at
default. NOTE: blobs are no longer byte-identical to Stage A — header byte[0] (priority) intentionally
rescaled; behavior/ordering preserved. Jingle cross-rule deferred to package 1 (introduces the class).
Defaults (gain/duck 0, cap 1, no continuous) keep audible behavior == Stage A; taste values are by-ear.
**Stage A status (2026-07-03, `feat/sfx-fidelity` — plan `2026-07-03-sfx-fidelity-stage-a.md`).**
All four §3 fixes landed + register-verified in oracle (§4 checks 1-3: jump `$140/$0EF`, skid `$078`,
spindash spam = 1 instance with rev escalation intact, clean tails). Fix 3 was audit-only (engine +
transcoder already clamped; pinned by test). PLUS one field-found fix beyond the spec: `Sfx_Restore`
now gates on `SND_SEQ_ACTIVE` — an SFX ending over STOPPED music re-keyed the dead song's stale-KEYED
note into an unkillable PSG drone (user-reported "lingering sine"; forced-condition verified fixed).
`SfxHeader` grew 4→8 with inert `sfh_gain`/`sfh_duck`/`sfh_cap` (§5 reservation). §4 check 4 (H3) and
the full rendered A/B are deferred pending by-ear — see DEFERRED_WORK "SFX Fidelity Stage B/C".
**Original status:** APPROVED by user (scope: "Design C, build A-first" — design the full best-in-class end-state, implement the confirmed fixes as stage 1)
**Sequencing constraint:** implementation MUST wait until `feat/sound-perf-budget` merges — it touches the same files (`sound_sfx.asm`, `sound_fm.asm`, `sound_psg.asm`, `z80_sound_driver.asm`, `sound_constants.asm`, `tools/sfx_transcode.py`). This spec is docs-only and safe on master.
**Emulator constraint:** oracle A/B work needs an explicit go-ahead from the user first (another session may be using the emulator).

## 1. Problem

User report (2026-07-02): vs real S3K, our SFX sound **too loud and too high-pitched** — spindash rev, jump, "most of them". Rings sound correct. Target is **S3K-faithful** (user-confirmed), with a best-in-class SFX-over-music policy on top.

## 2. Root causes (from the 4-stream research pass, 2026-07-02)

### CONFIRMED — PSG SFX play exactly +2 octaves
`tools/sfx_transcode.py:137` still applies `PSG_OCTAVE_FIXUP = 24`. Its premise ("our PsgDivisorTableZ uses scientific numbering") died on 2026-06-26 when commit `5e98f80` re-based the table to S3K's own `zPSGFrequencies` numbering (verified entry-for-entry identical, `engine/sound/sound_tables_z80.asm:26-39` vs skdisasm) without removing the SFX fixup (added in `d66c7d3` when it was correct).

Numeric proof (S3K → ours): jump $62 first note 349.6 Hz → 1398.3 Hz (+2400 cents); skid $36 932.2 Hz → 3608.4 Hz. Affects all PSG-bearing SFX: jump $62, skid $36, dash $B6's PSG channel. Rings are FM-only — exactly why they sound right. Secondary damage: jump's downward `smpsModSet` sweep (−8/frame) hits the divisor floor from the too-small starting divisor and wraps 16-bit negative in `Psg_ApplyMod` (`engine/sound/sound_psg.asm:276+`). Perceptual bonus: 1.4–3.6 kHz sits at peak ear sensitivity (+5–10 phon), so the pitch bug also reads as "too loud".

### CONFIRMED — same-SFX retrigger stacks up to 3 concurrent instances
`Sfx_BeginSound` (`engine/sound/sound_sfx.asm:672+`) never checks for a running instance of the same id; `Sfx_SelectVoice` tier (b) deliberately places the retrigger on a free same-kind voice (3 FM + 3 PSG stealable). S3K structurally cannot stack: fixed channels per SFX, retrigger re-inits the same track (skdisasm `Z80 Sound Driver.asm:1935-1975`). 2–3 stacked copies ≈ +5 to +9.5 dB, and stale spindash instances keep their upward mod-sweep running to sweep-tops S3K never exposes → this one bug is both "spindash too loud" AND "spindash too high". A *single* instance of our spindash is chip-exact to S3K (TL bytes verified). Already logged as an open policy decision in `docs/superpowers/2026-07-01-sound-engine-review-findings.md:97,113`; the dormant "5b seam" for the dedupe already exists (`sound_sfx.asm:119-124, 558-565`).

### RULED OUT (numerically, static)
- FM note→F-num/block mapping: ours vs S3K ≤5 cents across all 95 entries; header transposes baked correctly (roll +$0C, death −$0C carried exactly).
- Channel-volume→carrier-TL bake: chip-exact (ring `[35,35,5,5]`, spindash carriers `[0,0]` = S3K writes). Carrier masks match YM2612 algorithms; `_s3k_op_reorder` verified correct.
- SpinRev escalation/reset: exact port of `cfSpindashRev` (+1 semitone/retrigger, cap +$10, reset on any normal SFX; `sound_sequencer.asm:1050-1061`, `sound_sfx.asm:673-681`).
- Modulation units: faithful port; no octave error.

### PLAUSIBLE, UNVERIFIED (needs emulator) — music-relative level (H3)
SFX correctly play at raw authored TL. If SFX still feel loud after the two fixes, our MUSIC may be quieter than S3K's (music converter volume round-trip) — that would be a separate music-converter follow-up, decided by the A/B in §4.

## 3. Stage A — confirmed fixes (implement first, small)

1. **`PSG_OCTAVE_FIXUP = 24 → 0`** in `tools/sfx_transcode.py`; regenerate all SFX blobs (only PSG-bearing ones change). Add a build-time assert/comment tying the fixup value to the PSG table's numbering convention (generated by `tools/gen_sound_tables.py:97-111`) so they cannot silently desync again.
2. **Retrigger = replace-in-place**: on `Sfx_BeginSound`, scan active `SfxChannel` slots for the same SFX id; if found, key-off + re-init that slot in place instead of allocating (~25–35 B at the existing 5b seam). S3K-faithful; default instance cap = 1.
3. **TL-overflow clamp** on every volume→carrier-TL add (engine + transcoder bake): saturate at $7F, never wrap quiet→loud. Precedent: Flamedriver/`fix_sndbugs` (stock S3K wraps; skdisasm `:3190-3194`).
4. **PSG mod-sweep floor guard** in `Psg_ApplyMod`: clamp divisor at 0 on downward sweeps (cheap insurance even after fix 1).

Acceptance: verification protocol §4 passes; spindash rev still escalates +1 semitone/press capped +$10.

## 4. Verification protocol (oracle, foreground only, user go-ahead first)

Reference: build skdisasm's S3K ROM (`lua buildSK.lua`). Both sides captured with **matched YM2612 core settings** — the ladder effect shifts quiet-FM loudness/brightness ~2–3 dB between cores/models; mismatched settings would bake emulator artifacts into tuning.

1. Per SFX: VGM-capture ours vs S3K sound test; assert programmed PSG divisors (jump $140/$0EF, skid $078) and FM F-num/block match; assert jump's sweep never underflows.
2. **Rendered-audio A/B** via vgm2wav (per the "verify real output, not a proxy" rule): energy + spectrum comparison per SFX.
3. Spindash spam test: count concurrent FM key-ons ($28 writes) — S3K = 1 always; ours must be 1 after fix.
4. H3: RMS/spectrum of full music+SFX mix vs S3K (music bed: HCZ2) to decide whether the music converter needs a volume pass; separately audition the death/ring-loss duck depth ($18 ≈ 18 dB — a feature S3K doesn't have).

## 5. Stage B/C — best-in-class mixing policy (the designed end-state)

Research grounding: S3K has NO priority system (removed to save RAM) and NO ducking; arbitration is structural (fixed channels, replace-on-retrigger, continuous-SFX class). No classic Genesis driver ducks music (survey: SMPS S1/S2/S3K, GEMS, Echo, XGM/XGM2, MDSDRV). Our priority queue + duck ramp already exceed the field; modern practice (Wwise/FMOD) says the missing pieces are instance limiting and per-sound depths. Full survey evidence lives in the research transcripts; key skdisasm anchors: continuous SFX `:1937-1957, 3712-3736`; non-latching priority (S2) `s2.sounddriver.asm:1533-1534`.

- **Per-SFX gain byte** in `SfxHeader` (use `sfh_pad`): authored master attenuation applied at init — FM: add to carrier TLs (0.75 dB steps); PSG: add to attenuation (2 dB steps). The correct taste-tuning surface; no stream re-authoring.
- **Per-SFX duck depth** replacing global `SFX_DUCK_DEPTH`: 0 for bread-and-butter SFX (classic-faithful default), deep (~$0C–$18 TL) only for death/ring-loss-class events. Keep the event-driven ramp, fast attack (1–4 frames) / slow release (~30–60 frames).
- **Non-blocking priority flag** (bit 7 of `sfh_priority`, S2's trick): plays when it wins arbitration but never latches the priority floor — for transients (jump-class) so they never starve later sounds.
- **Per-SFX instance cap byte** (default 1 = replace-in-place; rare sounds may author 2).
- **Continuous-SFX class** with S3K extend semantics: header flag; game re-pings the id every N frames; if already playing, refresh a loop counter instead of restarting; script loops (`cfLoopContinuousSFX` analogue) while pinged and runs out ~one loop after pings stop. None of the current 9 SFX need it; ~30 S3K sounds (wind, fans, rumbles, sirens, conveyors) are unportable without it. This is the "design for C" piece — the header/flag space is reserved NOW so stage A doesn't pigeonhole the format.
- Keep: log volume LUT routing (already built, Zyrinx-class), voice + PSG-noise restore on SFX end (already built), ring L/R alternation (already built).

Explicitly NOT doing: real signal metering/HDR (priority byte IS the HDR window on this hardware), per-frame loudness estimation, more than one duck bus, positional panning (defer).

## 6. Constants hygiene

`SFXPRI_*`/`SFXEL_*`/`SHF_*`/duck constants exist in TWO synced copies (`sound_constants.asm` + `tools/sfx_transcode.py`). Any new header fields (gain, duck depth, instance cap, continuous flag) must be added to both, with the existing test-suite byte-equality pattern extended to cover them.

---

## 7. STAGE B/C ADDENDUM (2026-07-03, sound design-banking session) — implementation-grade decisions

Seam-verified against the post-Stage-A engine (all citations current as of `feat/sound-design-banking`).
This addendum + §5 together are the full Stage B/C design; the banked implementation plan executes it.

### 7.1 Stage B hook points (verified)

- **`sfh_gain` folds** into the two existing single volume paths, immediately after each LUT read
  and BEFORE the env/fade/duck folds so all existing clamps cover it: FM at `Fm_SetVolume`
  (`engine/sound/sound_fm.asm:344-510`, fold after the log-LUT read ~:350, `SND_FM_TL_MAX`
  clamps at :366-371/:393-406 already downstream); PSG at `Psg_SetVolume`
  (`engine/sound/sound_psg.asm:387-450`, fold after `Psg_VolToAtten` ~:388, $0F clamp downstream).
  One byte serves both units: FM adds it directly (0.75 dB TL steps); PSG adds `sfh_gain >> 3`
  (TL→atten conversion, the same ÷8 the existing fade/duck fold uses at :427-429). Encoding
  therefore: **sfh_gain is authored in FM-TL units** (0..~$30 useful range).
- **`sfh_duck`** replaces the global constant at the single duck-arm site
  (`sound_sfx.asm:903-912`: write `sfh_duck` instead of `SFX_DUCK_DEPTH` at :911). Threshold
  test changes from priority-based to `sfh_duck != 0` (the per-SFX byte IS the eligibility).
  Un-duck release (`Sfx_Restore:1123-1132` → `Sfx_AnyDuckActive`) scans for any active slot
  with a nonzero armed duck — the scan reads a new per-slot copy (`sx_duck`, stashed at init)
  so mixed-depth overlaps resolve to the DEEPEST active duck.
- **Non-latching priority (bit 7)**: `Sfx_SelectVoice` (`sound_sfx.asm:1330-1503`) already
  computes the min-priority victim scan; a bit-7 incoming writes `sx_priority = <min-of-active>`
  instead of its own value at the init store (:876) — plays now, never raises the floor. Bit 7
  is masked OFF for all arbitration comparisons.
- **`sfh_cap` semantics RESOLVED (was the open discriminator question, DEFERRED_WORK ~:1178):**
  `sfh_cap > 1` is legal ONLY for single-channel blobs (`sfh_chcount == 1`) — a
  **packer-enforced validity rule** in `sfx_transcode.py`. Per-slot `SND_SFX_ID_TAB`
  (`sound_constants.asm:1360`) counts instances exactly for single-channel SFX; the
  kill-scan (`Sfx_BeginSound:731-761`) kills the LOWEST-slot match when count == cap
  (oldest-by-slot approximation, documented). Multi-channel SFX stay cap=1 (replace-in-place,
  Stage A behavior) until a real generation-tag need appears. No current or planned SFX needs
  cap>1 multi-channel; the format door stays open via the reserved header bytes.

### 7.2 Stage C — continuous-SFX class (S3K-exact semantics, simplified state)

Reference verified: skdisasm `Z80 Sound Driver.asm` — re-ping detection
`zPlaySound_NotContinuous:1937-1965` (same-id re-request sets `zContinuousSFXFlag=$80`,
reloads `zContSFXLoopCnt`), loop opcode `cfLoopContinuousSFX:3712-3736` (flag set →
decrement + re-loop; pings stopped → one final pass then end).

Aeon shape (simpler than S3K's dual flag+count):
- `SHF_CONTINUOUS` (bit 0, already reserved at `sound_constants.asm:899-905`) **requires
  `SHF_LOOP`** (packer validity rule). Jingle-class blobs (package 1) forbid BOTH.
- New per-slot byte `sx_extend` (SfxChannel has pad space): **re-ping countdown**. On
  `Sfx_BeginSound` with a matching active continuous id: instead of the retrigger kill-scan,
  reload `sx_extend = SFX_EXTEND_FRAMES` (constant, ~10) and return — the ping is free
  (no re-key, rev escalation state untouched, so spindash `MEV_SPINREV` keeps building —
  the Stage-A rev behavior is preserved by construction).
- `Sfx_Frame` decrements `sx_extend` per active continuous slot; at the blob's `MEV_JUMP`
  loop boundary: `sx_extend != 0` → take the loop; `== 0` → fall through to the existing
  looped-SFX **fade tail** (the shipped B4 machinery, 0ac3403's modSet-riding fade) → end.
- Game side: the call sites already re-ping every frame (`player_spindash.asm:60-61`);
  the drowning-warning cadence lands with package 1's §7 drowning flow.
- Existing 9 SFX: unchanged (none set the flag). Dash/spindash MAY be re-authored
  continuous later as a taste pass — not part of this plan's gates.

### 7.3 Budget + verification notes

Stage B folds are one `ld`+`add`(+clamp already present) per path; Stage C is the countdown
+ boundary branch (~35-50 B total; headroom 792 B). Verification: register gates per §4
pattern (gain: exact TL/atten deltas vs authored bytes; duck: ramp target per-SFX; cap:
spam N+1 → N instances; continuous: ping-stop → fade within one loop + `SFX_EXTEND_FRAMES`),
plus a rendered spindash-charge capture A/B against S3K (hold-charge timbre continuity).
