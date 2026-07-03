# SFX Fidelity Stage A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make our SFX S3K-faithful by fixing the two confirmed root causes (PSG +2-octave transcoder fixup, same-SFX retrigger stacking), adding the two cheap guards (PSG sweep floor, TL-clamp coverage), and reserving the Stage B/C header format — then verify against a real S3K capture.

**Architecture:** Spec: `docs/superpowers/specs/2026-07-02-sfx-fidelity-and-mixing-design.md` (approved, "design C build A"). Fixes 1/3 are build-PC Python (transcoder + regenerated blobs); fixes 2/4 are small resident Z80 additions (406 bytes free at `$175A/$18F0`, DEBUG=1 — these tasks add ~70). Task 5 grows `SfxHeader` 4→8 bytes with inert Stage-B fields so Stage B is pure engine work. Task 6 is the oracle A/B protocol.

**Tech Stack:** Python 3 + pytest (transcoder), Z80 assembly under AS (`tools/asl`), oracle emulator MCP + VGM capture + vgm2wav.

---

## Session-wide rules (read first)

- **Branch:** work on `feat/sfx-fidelity`, cut from a clean, up-to-date `master`. Merge back to master only after Task 6's user by-ear gate passes.
- **Build command:** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` — a plain `./build.sh` EXCLUDES all sound code and proves nothing. Every build step below means this command.
- **Budget:** the build prints `Z80_SOUND_SIZE`. Phase-start baseline: `$175A / $18F0` (406 bytes free). If any task overflows the ceiling, stop and report — do not start banking code (in-frame banked CODE is a known-unsafe pattern here).
- **`git add` exact paths only.** The working tree has unrelated editor/sprite WIP (`games/sonic4/data/editor/...`, `games/sonic4/data/sprites/`, `tools/forest_bg_gen.py`, `games/sonic4/data/editor_bg_override.json`, `docs/research/s3k_art_style_demo.html`). Never `git add -A` or glob. Verify each commit with `git show --stat HEAD`.
- **Do not touch** `tools/ojz_strip_gen.py` or `games/sonic4/data/editor/ojz/**` (daemon-watched).
- **No emulator work in subagents.** Task 6 is controller-foreground only, and only after the user's explicit go-ahead (spec constraint — another session may own the emulator). Tasks 1–5 need no emulator.
- **Tests:** `python3 -m pytest tools/test_sfx_transcode.py -q` for the fast loop; `python3 -m pytest tools/ -q` before each commit that touches `tools/`.

### File structure (what changes where)

| File | Change |
|---|---|
| `tools/sfx_transcode.py` | Fix 1: `PSG_OCTAVE_FIXUP = 0` + comment rewrite. Task 5: 8-byte header emit. |
| `tools/test_sfx_transcode.py` | New convention-tie tests, literalize one stale expectation, bake-saturation test, header-layout test updates. |
| `games/sonic4/data/sound/sfx/*.asm` | Regenerated blobs (Task 1 changes PSG-bearing ones; Task 5 changes all). |
| `engine/sound/sound_sfx.asm` | Fix 2: dispatch-scratch `SND_SFX_DISP_ID` + `SND_SFX_ID_TAB`, entry stash, retrigger kill-scan, per-slot id write. |
| `engine/sound/sound_psg.asm` | Fix 4: divisor floor clamp in `Psg_ApplyMod`. |
| `sound_constants.asm` | Task 5: `SfxHeader` grows 4→8 (sfh_gain/sfh_duck/sfh_cap/sfh_rsvd). |
| `docs/ENGINE_ARCHITECTURE.md`, `docs/DEFERRED_WORK.md`, spec | Task 7: doc sync + outcome header. |

---

### Task 0: Branch setup

- [ ] **Step 1: Cut the branch and confirm a green baseline**

```bash
cd /home/volence/sonic_hacks/aeon
git checkout master && git pull --ff-only 2>/dev/null; git checkout -b feat/sfx-fidelity
SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh
python3 -m pytest tools/ -q
```

Expected: build succeeds (note the printed `Z80_SOUND_SIZE` — should be `$175A / $18F0`), pytest all green. If the baseline is red, stop and report before changing anything.

---

### Task 1: Fix 1 — remove the stale PSG +2-octave fixup

The transcoder still applies `PSG_OCTAVE_FIXUP = 24` (`tools/sfx_transcode.py:137`), a correction for a scientific-numbered PSG table that stopped existing on 2026-06-26 when `PsgDivisorTableZ` was re-based to S3K's own `zPSGFrequencies` numbering. Result: every PSG SFX note plays +2 octaves high (jump nF2 should hit divisor `$140`; today it hits `$50`).

**Files:**
- Modify: `tools/sfx_transcode.py:122-137` (constant + comment), `:267-292` (`_smps_note_to_pitch` docstring)
- Modify: `tools/test_sfx_transcode.py` (new test class; fix `test_psg_note_not_shifted_by_fm_knob` at `:429-433`)
- Regenerate: `games/sonic4/data/sound/sfx/` (PSG-bearing blobs)

- [ ] **Step 1: Write the failing convention-tie test**

Add to `tools/test_sfx_transcode.py` (after `TestFmSfxOctaveKnob`). It transcodes the real jump/skid note bytes end-to-end and asserts the pitch index lands on S3K's exact divisor in `gen_sound_tables.psg_divisor_table()` — so it breaks if EITHER the fixup OR the table numbering convention changes alone (the desync guard the spec asks for):

```python
class TestPsgPitchMatchesS3KDivisors(unittest.TestCase):
    """END-TO-END convention tie (SFX fidelity Stage A, fix 1).

    A transcoded PSG note's pitch index must look up the SAME 10-bit divisor
    that S3K's zPSGFrequencies table yields for that note. PsgDivisorTableZ
    was re-based to S3K numbering on 2026-06-26 (gen_sound_tables
    psg_divisor_table), which made the old scientific-pitch +24 fixup a
    +2-octave bug. This test ties PSG_OCTAVE_FIXUP to the table convention:
    if either side changes alone, it fails.
    Reference divisors (skdisasm zPSGFrequencies): jump $62 nF2 -> $140,
    nBb2 -> $0EF; skid $36 nBb3 -> $078.
    """

    def test_fixup_is_zero_while_table_is_s3k_numbered(self):
        self.assertEqual(PSG_OCTAVE_FIXUP, 0,
                         "PsgDivisorTableZ uses S3K zPSGFrequencies numbering; "
                         "raw S3K note indices are already correct")

    def test_jump_nF2_hits_s3k_divisor(self):
        from gen_sound_tables import psg_divisor_table
        # nF2 = $81 + 2*12 + 5 = $9E
        idx = _smps_note_to_pitch(0x9E, is_psg=True)
        self.assertEqual(psg_divisor_table()[idx], 0x140,
                         "jump's first PSG note must program S3K's $140 divisor (349.6 Hz)")

    def test_jump_nBb2_hits_s3k_divisor(self):
        from gen_sound_tables import psg_divisor_table
        # nBb2 = $81 + 2*12 + 10 = $A3
        idx = _smps_note_to_pitch(0xA3, is_psg=True)
        self.assertEqual(psg_divisor_table()[idx], 0x0EF)

    def test_skid_nBb3_hits_s3k_divisor(self):
        from gen_sound_tables import psg_divisor_table
        # nBb3 = $81 + 3*12 + 10 = $AF
        idx = _smps_note_to_pitch(0xAF, is_psg=True)
        self.assertEqual(psg_divisor_table()[idx], 0x078,
                         "skid's note must program S3K's $078 divisor (932.2 Hz)")
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python3 -m pytest tools/test_sfx_transcode.py::TestPsgPitchMatchesS3KDivisors -q`
Expected: 4 FAILs (fixup is 24; jump nF2 currently lands on divisor `$50`).

- [ ] **Step 3: Set the fixup to 0 and rewrite the stale comment**

In `tools/sfx_transcode.py`, replace the comment block + constant at lines 130-137 with:

```python
# PSG note numbering: our PsgDivisorTableZ is generated by
# gen_sound_tables.psg_divisor_table() in S3K's OWN zPSGFrequencies numbering
# (re-based 2026-06-26, commit 5e98f80 — entry-for-entry identical to skdisasm).
# Raw S3K PSG note indices therefore index our table directly; NO octave shift
# is needed or permitted. The old +24 was a correction for the earlier
# scientific-numbered table and became a +2-octave bug when the table was
# re-based (SFX fidelity spec 2026-07-02 §2). CONVENTION TIE: if either this
# value or the table numbering ever changes alone,
# test_sfx_transcode.TestPsgPitchMatchesS3KDivisors fails the build.
PSG_OCTAVE_FIXUP = 0
```

Also update the `_smps_note_to_pitch` docstring (lines 274-279): replace the four "For PSG: ... +24 is the complete correction." lines with:

```python
    For PSG: PsgDivisorTableZ uses S3K's own zPSGFrequencies numbering, so the
    raw S3K note index maps 1:1 (PSG_OCTAVE_FIXUP = 0; see the convention-tie
    comment at its definition).
```

- [ ] **Step 4: Literalize the stale self-adjusting expectation**

In `tools/test_sfx_transcode.py:429-433`, `test_psg_note_not_shifted_by_fm_knob` computes its expectation *from* `PSG_OCTAVE_FIXUP`, so it guards nothing. Replace the method body:

```python
    def test_psg_note_not_shifted_by_fm_knob(self):
        # PSG is NOT affected by the FM taste knob, and maps 1:1 to the
        # S3K-numbered table (no fixup): nC5 = $BD -> index $3C.
        raw = 0xBD
        got = _smps_note_to_pitch(raw, is_psg=True, transpose=0)
        self.assertEqual(got, raw - S3K_NOTE_BASE)
```

- [ ] **Step 5: Run the full transcoder suite; fix any other +24-coupled expectations**

Run: `python3 -m pytest tools/test_sfx_transcode.py -q`
Expected: all PASS. If any other test still encodes the +24 (grep `PSG_OCTAVE_FIXUP` — after this task only the import line and the new test class should reference it), rewrite it to the literal S3K-numbered value the same way as Step 4.

- [ ] **Step 6: Regenerate the SFX blobs**

```bash
python3 tools/sfx_transcode.py generate
git diff --stat games/sonic4/data/sound/sfx/
```

Expected: only PSG-bearing blobs change (jump `sfx_62.asm`, skid `sfx_36.asm`, dash `sfx_B6.asm`; possibly others with PSG channels — death `sfx_35.asm`). FM-only blobs (rings `sfx_33/34.asm`, roll `sfx_3C.asm`, spindash `sfx_AB.asm`) must be byte-identical. If an FM-only blob changed, something is wrong — stop and investigate.

- [ ] **Step 7: Build + full pytest**

```bash
SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh && python3 -m pytest tools/ -q
```

Expected: green build (Z80 size unchanged — data-only change), all tests pass.

- [ ] **Step 8: Commit**

```bash
git add tools/sfx_transcode.py tools/test_sfx_transcode.py games/sonic4/data/sound/sfx/
git commit -m "fix(sound): remove stale PSG +24 octave fixup — PSG SFX were +2 octaves high (spec fix 1)"
git show --stat HEAD   # verify no stray files swept in
```

---

### Task 2: Fix 2 — same-SFX retrigger = replace-in-place

`Sfx_BeginSound` never checks for a running instance of the same id, so rapid retriggers (spindash rev) stack up to 3 concurrent copies (+5 to +9.5 dB, stale upward mod-sweeps). S3K structurally re-inits the same track. Fix: before allocating, kill every ACTIVE slot already running this id via the existing `Sfx_Restore` end-path, then let the normal allocation ladder run — the just-freed voice is the preferred route, so this is replace-in-place with zero new teardown code.

**Design constraints discovered during research (do not "simplify" these away):**
- The per-slot id CANNOT live in `SfxChannel.sx_pad` (+58): SeqChannel aliases +58 as `sc_detune`, which `Fm_NoteOnFreq` (sound_fm.asm:789) reads with an SFX `ix` and relies on being 0. A nonzero id there would detune every SFX FM note. The id lives in a parallel 7-byte RAM table instead.
- `Sfx_Restore` is safe to call on a still-ACTIVE slot (its deactivate is defensive: `res SCF_ACTIVE_B`) and preserves `ix`; it clobbers `af,bc,de,hl,iy`.
- The kill may momentarily zero `SND_SFX_DUCK_TARGET` (duck release); the re-arm after the channel loop re-raises it in the same frame, before `Sfx_DuckRamp` ever runs — no audible dip.
- Spindash rev escalation is untouched: the rev reset/keep logic runs at `Sfx_BeginSound` entry BEFORE the kill-scan, and killing the old instance does not touch `Snd_SpindashRev`.

**Files:**
- Modify: `engine/sound/sound_sfx.asm:73-82` (dispatch scratch), `:674+` (`Sfx_BeginSound`)

- [ ] **Step 1: Add the id scratch + per-slot id table to the dispatch scratch block**

In `engine/sound/sound_sfx.asm`, the block at lines 73-82 currently ends:

```asm
SND_SFX_DISP_ROUTE = SND_SFX_DISP_SLOT + 1             ; physical route the slot owns
SND_SFX_DISP_END   = SND_SFX_DISP_ROUTE + 1
```

Replace with:

```asm
SND_SFX_DISP_ROUTE = SND_SFX_DISP_SLOT + 1             ; physical route the slot owns
SND_SFX_DISP_ID    = SND_SFX_DISP_ROUTE + 1            ; raw id of the SFX being dispatched
; Per-slot raw SFX id, parallel to the SfxChannel array (index = slot 0..6).
; Lives HERE and not in the struct: SfxChannel_len must stay 64 (shift-free slot
; addressing) and the only free struct byte (+58 sx_pad) aliases SeqChannel's
; sc_detune, which Fm_NoteOnFreq reads with an SFX ix and requires to be 0.
; Entries are only meaningful while the slot is ACTIVE (scan gates on SCF_ACTIVE;
; stale ids in inactive slots are harmless and get overwritten at init).
SND_SFX_ID_TAB     = SND_SFX_DISP_ID + 1               ; 7 bytes
SND_SFX_DISP_END   = SND_SFX_ID_TAB + SFX_VOICE_COUNT
```

The existing `fatal` assert right below (scratch vs the `$1F00` mailbox) catches any overrun at build time.

- [ ] **Step 2: Stash the raw id at Sfx_BeginSound entry**

At `Sfx_BeginSound:` (line ~674), the first instruction is `cp SFXID_SPINDASH`. Insert one line above it, directly under the `Sfx_BeginSound:` label:

```asm
Sfx_BeginSound:
        ld      (SND_SFX_DISP_ID), a     ; raw id — keys the retrigger scan + per-slot id table
```

(`ld (nn),a` preserves `a`; the spindash-rev compare below is unaffected. Invalid ids also get stashed, but the scan only runs after the id validates.)

- [ ] **Step 3: Insert the retrigger kill-scan before the channel loop**

At line ~720, after the dispatch state is fully stashed:

```asm
        xor     a
        ld      (SND_SFX_DISP_IDX), a    ; current channel record index (0-based)
```

and before `.chan_loop:`, insert:

```asm
        ; --- RETRIGGER REPLACE-IN-PLACE (spec fix 2, S3K-faithful) -----------------
        ; S3K cannot stack the same SFX: a retrigger re-inits the same fixed track
        ; (skdisasm Z80 Sound Driver.asm:1935-1975). Our dynamic allocator happily
        ; placed a retrigger on a FREE same-kind voice, stacking up to 3 copies
        ; (+5..+9.5 dB and runaway spindash mod-sweeps). Kill every ACTIVE slot
        ; already running THIS id via the full Sfx_Restore end-path (music voice
        ; restored / orphan voice silenced, slot deactivated, duck re-evaluated),
        ; then fall into the normal allocation ladder: the just-freed voice is the
        ; preferred route again, so the net effect is replace-in-place. Instance
        ; cap = 1 (the Stage-B sfh_cap header byte may later author more).
        ; Duck note: a kill may zero SND_SFX_DUCK_TARGET; the arm after .chan_loop
        ; re-raises it this same frame, before Sfx_DuckRamp runs — no audible dip.
        ld      ix, SND_SFX_CHANNELS     ; slot cursor (stride = SfxChannel_len)
        ld      hl, SND_SFX_ID_TAB       ; parallel id cursor
        ld      b, SFX_VOICE_COUNT
.retrig_scan:
        bit     SCF_ACTIVE_B, (ix+sc_flags)
        jr      z, .retrig_next          ; inactive slot -> id entry is stale, skip
        ld      a, (SND_SFX_DISP_ID)
        cp      (hl)
        jr      nz, .retrig_next         ; different SFX -> leave it playing
        push    hl                       ; Sfx_Restore clobbers hl/bc (preserves ix)
        push    bc
        call    Sfx_Restore              ; full end path: restore/silence + deactivate
        pop     bc
        pop     hl
.retrig_next:
        inc     hl
        ld      de, SfxChannel_len       ; reload each pass (Sfx_Restore clobbers de)
        add     ix, de
        djnz    .retrig_scan
```

- [ ] **Step 4: Record the id when a slot is claimed**

In the slot-init sequence (line ~748), after:

```asm
        ld      a, d
        ld      (SND_SFX_DISP_ROUTE), a  ; physical route the slot will own
```

and before `; ix = &SfxChannel[chosen slot]`, insert:

```asm
        ; record this slot's raw SFX id (the retrigger scan's key)
        ld      a, (SND_SFX_DISP_SLOT)
        ld      e, a
        ld      d, 0
        ld      hl, SND_SFX_ID_TAB
        add     hl, de
        ld      a, (SND_SFX_DISP_ID)
        ld      (hl), a
```

- [ ] **Step 5: Build and check the budget**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`
Expected: green; `Z80_SOUND_SIZE` grows by roughly `$40`–`$50` (scan + id write) — well inside the 406-byte headroom. The dispatch-scratch fatal assert passing confirms the 8 new RAM bytes fit under the mailbox.

- [ ] **Step 6: Commit**

```bash
git add engine/sound/sound_sfx.asm
git commit -m "fix(sound): same-SFX retrigger kills the running instance first — replace-in-place, cap 1 (spec fix 2)"
git show --stat HEAD
```

---

### Task 3: Fix 4 — PSG mod-sweep divisor floor guard

A downward divisor sweep can drive `sc_base_freq + sc_mod_accum` 16-bit negative; `Psg_EmitDivisorTo` then masks the wrapped value into garbage divisor bits (the jump-sweep wrap in spec §2). After fix 1 the starting divisors are 4× larger so this no longer triggers in the core set — this is cheap insurance, per spec fix 4.

**Files:**
- Modify: `engine/sound/sound_psg.asm:294-297` (`Psg_ApplyMod`)

- [ ] **Step 1: Add the clamp**

Current code:

```asm
Psg_ApplyMod:
        call    Mod_Advance              ; advance triangle; CF set => no write this frame
        ret     c
        ; de = modulated divisor (d=hi, e=lo). Re-latch via the shared emit helper
```

Insert the clamp between `ret c` and the comment line:

```asm
Psg_ApplyMod:
        call    Mod_Advance              ; advance triangle; CF set => no write this frame
        ret     c
        ; FLOOR GUARD (spec fix 4): a downward sweep can drive base+accum 16-bit
        ; negative; the emit path masks the wrapped word into garbage divisor bits.
        ; Clamp to 1, not 0 — divisor 0 is chip-ambiguous on the SN76489 family
        ; (DC output or /1024 depending on variant; Psg_EmitNoiseClock makes the
        ; same 0->1 clamp). Divisor 1 = ~55.9 kHz, inaudible: a floored sweep goes
        ; silent-high instead of wrapping to a wrong low note. (The UPWARD overflow
        ; past $3FF is left as-is — S3K's zDoModulation wraps identically there,
        ; and matching S3K is the spec target.)
        bit     7, d                     ; negative 16-bit sum = the sweep underflowed
        jr      z, .div_ok
        ld      de, 1                    ; clamp at the divisor floor
.div_ok:
        ; de = modulated divisor (d=hi, e=lo). Re-latch via the shared emit helper
```

- [ ] **Step 2: Build**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`
Expected: green; +9 bytes.

- [ ] **Step 3: Commit**

```bash
git add engine/sound/sound_psg.asm
git commit -m "fix(sound): PSG mod-sweep divisor floor clamp — underflow can't wrap to a wrong note (spec fix 4)"
git show --stat HEAD
```

---

### Task 4: Fix 3 — TL-overflow clamp coverage (audit + missing test)

Research finding: the engine-side volume→carrier-TL adds ALREADY saturate at `$7F` (`SND_FM_TL_MAX`) at every site — `Fm_PatchOpGroup` op-bias (`sound_fm.asm:267-305`), the TL vol-env folds (`:353-406`), and the log-volume carrier path (`:445+`). The transcoder bake `_bake_channel_volume` also clamps (`min(0x7F, ...)`, `sfx_transcode.py:350`). What's missing is a TEST pinning the bake's saturation (the engine sites are covered by the driver's own build-time/self-test discipline). This task closes spec fix 3 as verify-plus-pin rather than new engine code.

**Files:**
- Modify: `tools/test_sfx_transcode.py`

- [ ] **Step 1: Re-verify the engine clamp sites (read-only)**

Read `engine/sound/sound_fm.asm` around lines 244-310, 350-410, and 430-460 and confirm every path that adds to a TL byte clamps at `SND_FM_TL_MAX` before writing the register. Expected: all clamped (this was true at plan-writing time). If you find an unclamped add, STOP and report — that becomes a new engine fix, not a silent addition.

- [ ] **Step 2: Write the bake-saturation test**

Add to `tools/test_sfx_transcode.py` (after `TestPsgPitchMatchesS3KDivisors`):

```python
class TestBakeChannelVolumeSaturates(unittest.TestCase):
    """Spec fix 3: every volume->carrier-TL add must saturate at $7F, never
    wrap quiet->loud (stock S3K wraps; Flamedriver/fix_sndbugs clamp)."""

    def _patch(self, alg, tls):
        # minimal 32-byte FmPatch: [0]=alg_fb, [1]=lr, [2:6]=dt_mul, [6:10]=tl
        p = bytearray(32)
        p[0] = alg
        p[6:10] = bytes(tls)
        return bytes(p)

    def test_carrier_tl_saturates_at_7f(self):
        from sfx_transcode import _bake_channel_volume
        # alg 7: all four operators are carriers
        p = self._patch(7, [0x70, 0x7F, 0x00, 0x60])
        out = _bake_channel_volume(p, 0x30)
        self.assertEqual(list(out[6:10]), [0x7F, 0x7F, 0x30, 0x7F],
                         "TL adds must clamp at $7F, never wrap")

    def test_modulators_untouched(self):
        from sfx_transcode import _bake_channel_volume
        # alg 0: only operator index 3 (S4) is a carrier
        p = self._patch(0, [0x10, 0x20, 0x30, 0x40])
        out = _bake_channel_volume(p, 0x50)
        self.assertEqual(list(out[6:10]), [0x10, 0x20, 0x30, 0x7F],
                         "modulator TLs must not be volume-baked (timbre, not loudness)")
```

Note: if `test_modulators_untouched` fails on the expected carrier set, check `_CARRIER_MASK` in `sfx_transcode.py` for algorithm 0's actual mask and fix the TEST to the verified mask semantics (mask bit i selects register-order operator i; algorithm 0's sole carrier is the last operator in register order). Do not change `_bake_channel_volume` — it was chip-verified against S&K ring captures.

- [ ] **Step 3: Run the tests**

Run: `python3 -m pytest tools/test_sfx_transcode.py -q`
Expected: PASS (these pin existing behavior; a failure means the audit found a real bug — report it).

- [ ] **Step 4: Commit**

```bash
git add tools/test_sfx_transcode.py
git commit -m "test(sound): pin TL-bake saturation + record engine clamp audit (spec fix 3)"
git show --stat HEAD
```

---

### Task 5: Design-for-C — reserve the Stage B/C SfxHeader fields

Grow `SfxHeader` from 4 to 8 bytes so Stage B (per-SFX gain, per-SFX duck depth, instance cap) is pure engine work with no format churn. All new fields are INERT in Stage A: the transcoder writes defaults, the engine reads none of them (`SFXH_CHANNELS = SfxHeader_len` shifts the record array automatically on the engine side). Spec §5 mandates reserving this now; §6 mandates keeping the two constant copies (asm + Python) in sync with test coverage.

**Files:**
- Modify: `sound_constants.asm:861-867` (SfxHeader struct)
- Modify: `tools/sfx_transcode.py` (`pack_sfx` header emit + `header_len`)
- Modify: `tools/test_sfx_transcode.py` (header-layout tests)
- Regenerate: `games/sonic4/data/sound/sfx/*.asm` (all blobs)

- [ ] **Step 1: Update the failing header-layout tests FIRST (TDD on the format)**

In `tools/test_sfx_transcode.py`:

`test_blob_header_layout` (`TestRoundtripRoll`, line ~235): the roll blob is 1 channel, so the stream now starts at `8 + 1*6 = 14`. Update the prefix asserts and `cmd_ptr`:

```python
    def test_blob_header_layout(self):
        desc = transcode_sfx_source(ROLL_SRC, 0x3C)
        blob = pack_sfx(desc, SFXPRI_ROLL)
        # 8-byte prefix (Stage B fields inert: gain=0, duck=0, cap=1, rsvd=0)
        self.assertEqual(blob[0], SFXPRI_ROLL)          # sfh_priority
        self.assertEqual(blob[1], desc['flags'])         # sfh_flags
        self.assertEqual(blob[2], 1)                     # sfh_chcount
        self.assertEqual(blob[3], 0)                     # sfh_gain (inert Stage A)
        self.assertEqual(blob[4], 0)                     # sfh_duck (inert Stage A)
        self.assertEqual(blob[5], 1)                     # sfh_cap  (inert; engine hard-caps 1)
        self.assertEqual(blob[6], 0)                     # sfh_rsvd
        self.assertEqual(blob[7], 0)                     # sfh_rsvd+1
        # 6-byte per-channel record at offset 8
        self.assertEqual(blob[8], CHROUTE_FM4)           # route
        self.assertEqual(blob[9], SFXEL_FM)              # kind
        cmd_ptr = (blob[10] << 8) | blob[11]
        self.assertEqual(cmd_ptr, 14)                    # header 8 + 1 record*6
        voice_ptr = (blob[12] << 8) | blob[13]
        self.assertGreater(voice_ptr, 14,
                           "FM channel voice_ptr must point past the stream data")
```

`test_skid_blob_header` (line ~400 region): records now start at 8; channel 0's voice_ptr at bytes 12/13, channel 1's record at 14 with voice_ptr at 18/19:

```python
    def test_skid_blob_header(self):
        desc = transcode_sfx_source(SKID_SRC, 0x36)
        blob = pack_sfx(desc, SFXPRI_SKID)
        self.assertEqual(blob[0], SFXPRI_SKID)
        self.assertEqual(blob[2], 2)           # 2 channels
        self.assertEqual(blob[5], 1)           # sfh_cap default
        voice_ptr_0 = (blob[12] << 8) | blob[13]
        self.assertEqual(voice_ptr_0, 0)
        voice_ptr_1 = (blob[18] << 8) | blob[19]
        self.assertEqual(voice_ptr_1, 0)
```

`test_blob_stream_ends_with_mev_end`: update the record offsets the same way (`cmd_ptr` from bytes 10/11, `voice_ptr` from 12/13):

```python
    def test_blob_stream_ends_with_mev_end(self):
        """The packed stream for each channel must end with MEV_END ($FF)."""
        desc = transcode_sfx_source(ROLL_SRC, 0x3C)
        blob = pack_sfx(desc, SFXPRI_ROLL)
        cmd_ptr = (blob[10] << 8) | blob[11]
        voice_ptr = (blob[12] << 8) | blob[13]
        stream = blob[cmd_ptr:voice_ptr]
        self.assertEqual(stream[-1], MEV_END,
                         f"Stream must end with MEV_END ($FF); got ${stream[-1]:02X}")
```

Search the test file for any OTHER hardcoded record offsets (`grep -n "blob\[" tools/test_sfx_transcode.py`) and shift them by +4 with the same pattern.

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tools/test_sfx_transcode.py -q`
Expected: the updated layout tests FAIL against the current 4-byte header.

- [ ] **Step 3: Grow the header in pack_sfx**

In `tools/sfx_transcode.py` `pack_sfx` (line ~1372): update the docstring layout table (`[3] gain, [4] duck, [5] cap=1, [6:8] rsvd; records at +8`), then:

```python
    # Header: 8 bytes + chcount*6 bytes
    header_len = 8 + chcount * 6
```

and replace the prefix emit:

```python
    out = bytearray()
    out.append(priority & 0xFF)        # sfh_priority
    out.append(flags & 0xFF)           # sfh_flags
    out.append(chcount & 0xFF)         # sfh_chcount
    out.append(0x00)                   # sfh_gain (Stage B: authored master attenuation; inert)
    out.append(0x00)                   # sfh_duck (Stage B: per-SFX duck depth; inert)
    out.append(0x01)                   # sfh_cap  (Stage B: instance cap; engine hard-caps 1 in Stage A)
    out.append(0x00)                   # sfh_rsvd (keeps records even-aligned)
    out.append(0x00)                   # sfh_rsvd+1
```

- [ ] **Step 4: Grow the struct in sound_constants.asm (the synced copy)**

Replace the `SfxHeader` struct at `sound_constants.asm:861-867`:

```asm
SfxHeader struct
sfh_priority    ds.b 1   ; +0  authored priority byte (SFXPRI_*); higher wins.
                         ;     bit 7 RESERVED (Stage B): non-latching "plays but never
                         ;     raises the priority floor" flag (S2's trick) — keep
                         ;     authored priorities < $80 until Stage B lands.
sfh_flags       ds.b 1   ; +1  SHF_* (continuous / stereo-alt / loop)
sfh_chcount     ds.b 1   ; +2  number of SFX channels (1 or 2 for the core set)
sfh_gain        ds.b 1   ; +3  Stage B: authored master attenuation (FM: +carrier TL
                         ;     in 0.75 dB steps; PSG: +atten in 2 dB steps). INERT in
                         ;     Stage A (engine never reads it; transcoder writes 0).
sfh_duck        ds.b 1   ; +4  Stage B: per-SFX duck depth (replaces the global
                         ;     SFX_DUCK_DEPTH). INERT in Stage A (transcoder writes 0).
sfh_cap         ds.b 1   ; +5  Stage B: instance cap. INERT in Stage A: the engine
                         ;     hard-caps at 1 (retrigger replace-in-place); transcoder
                         ;     writes 1.
sfh_rsvd        ds.b 2   ; +6  keep the per-channel records even-aligned
; per channel: route(.b) + kind(.b) + cmd_ptr(.w BE off) + voice_ptr(.w BE off)
SfxHeader endstruct      ; = 8 bytes (fixed prefix; per-channel array follows)

        if SfxHeader_len <> 8
          error "SfxHeader struct is \{SfxHeader_len} bytes, expected 8 (transcoder pack_sfx must match)"
        endif
```

(The engine reads records via `SFXH_CHANNELS = SfxHeader_len`, so no engine code changes; `SFXH_PRIORITY`/`SFXH_FLAGS`/`SFXH_CHCOUNT` offsets are unchanged.)

- [ ] **Step 5: Regenerate all blobs, build, full pytest**

```bash
python3 tools/sfx_transcode.py generate
SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh
python3 -m pytest tools/ -q
```

Expected: all 9 blobs change (+4 bytes each), build green (the new struct assert passes), all tests green.

- [ ] **Step 6: Commit**

```bash
git add sound_constants.asm tools/sfx_transcode.py tools/test_sfx_transcode.py games/sonic4/data/sound/sfx/
git commit -m "feat(sound): SfxHeader 4->8 — reserve Stage-B gain/duck/cap fields (design-for-C, spec §5)"
git show --stat HEAD
```

---

### Task 6: Verification protocol (oracle — FOREGROUND ONLY, user go-ahead REQUIRED)

**Gate: do not start this task until the user has explicitly approved emulator use in this session.** All oracle MCP calls are made by the controller directly — never from a subagent (they deadlock). Health-check `mcp__oracle__emulator_status` first; one `oracle_gui` instance only (`pgrep -x oracle_gui`). Oracle Z80 addresses need a `0x` prefix; symbols go stale after `reload_rom` (use `s4.lst`). VGM capture is realtime-only (`run_frames` waits 2×).

Reference ROM: `/home/volence/sonic_hacks/skdisasm/sonic3k.bin` already exists (verify: `ls -la`, ~4 MB). Both sides are captured in the SAME oracle core, which satisfies the spec's matched-YM2612-settings requirement. Oracle loads one ROM at a time — capture ours, then S3K, then reload ours.

Existing tooling: `tools/vgm_onsets.py` (onset extraction), vgm2wav (rendered-audio A/B — the established "verify real output, not a proxy" procedure from the MT port).

- [ ] **Step 1: Register-level asserts (ours)** — load the freshly built `s4.bin`, start VGM capture, trigger jump / skid / spindash / dash in gameplay (`emulator_press`), stop capture. Parse the VGM PSG writes and assert the programmed divisors: jump first note `$140` then sweep, second note `$0EF`; skid `$078`. Assert jump's sweep never underflows (no wrapped divisor bytes). Assert FM F-num/block writes for ring/roll/spindash match the S3K-computed values (static table comparison already proved ≤5 cents; this is the on-device confirmation).
- [ ] **Step 2: Spindash spam test** — hold the spindash retrigger (repeated presses, ~10 in 2 s) while capturing. Count concurrent SFX-channel key-ons (`$28` writes with the SFX FM channel bits): must be exactly 1 SFX instance keyed at any moment (S3K = 1 always). Also assert the rev escalation survives: successive retriggers' F-num climbs +1 semitone per press, capped at +$10, and a normal SFX (jump) resets it.
- [ ] **Step 3: Rendered-audio A/B per SFX** — capture each core SFX from S3K's sound test (`sonic3k.bin`) and from ours; render both via vgm2wav; compare energy + spectrum per SFX (procedure: `docs/superpowers/` MT-port notes). Pass = pitch match (no octave offset) and level within ~±2 dB.
- [ ] **Step 4: H3 decision (music-relative level)** — capture a full music+SFX gameplay mix (HCZ2 bed + jump/spindash) both sides; compare RMS/spectrum. If our SFX still read hot vs music at matched SFX levels, the finding is a MUSIC-converter volume follow-up: record it in `docs/DEFERRED_WORK.md` with the measured delta — do NOT tune SFX to compensate. Separately audition the death/ring-loss duck depth ($18) and note taste feedback for Stage B.
- [ ] **Step 5: User by-ear gate** — user plays the build and confirms spindash rev, jump, skid, rings against S3K feel. This is the merge gate.

---

### Task 7: Doc sync + merge

- [ ] **Step 1: Docs** — update `docs/ENGINE_ARCHITECTURE.md` §6 (sound): SFX retrigger policy = replace-in-place cap 1; SfxHeader = 8 bytes with reserved Stage-B fields; PSG SFX numbering convention tie. Add/close `docs/DEFERRED_WORK.md` items: close the retrigger policy decision (was open in `2026-07-01-sound-engine-review-findings.md:97,113`); add Stage B/C (gain/duck/cap/continuous wiring) as the follow-on phase; add the H3 outcome from Task 6. Add the outcome header to the spec (`docs/superpowers/specs/2026-07-02-sfx-fidelity-and-mixing-design.md`), matching the house pattern.
- [ ] **Step 2: Commit docs**

```bash
git add docs/ENGINE_ARCHITECTURE.md docs/DEFERRED_WORK.md docs/superpowers/specs/2026-07-02-sfx-fidelity-and-mixing-design.md
git commit -m "docs(sound): SFX fidelity Stage A outcomes — retrigger policy closed, Stage B/C deferred items"
```

- [ ] **Step 3: Merge** — only after Task 6 Step 5 (user by-ear PASS): fast-forward merge `feat/sfx-fidelity` to `master` per the finishing-a-development-branch flow. Never leave master broken.

---

## Self-review record

- **Spec coverage:** fix 1 → Task 1; fix 2 → Task 2; fix 3 → Task 4 (audit found engine+transcoder already clamp; task pins it); fix 4 → Task 3; §4 protocol → Task 6 (all four numbered checks); §5 reservation → Task 5 (gain/duck/cap bytes, bit-7 priority reservation comment, SHF_CONTINUOUS already existed); §6 dual-copy sync → Task 5 touches both copies + layout tests. Stage B/C implementation itself is explicitly OUT of scope ("build A-first") and lands in DEFERRED_WORK via Task 7.
- **Acceptance criteria (spec §3):** protocol pass = Task 6 steps 1-3; spindash rev escalation preserved = Task 6 step 2.
- **Type/name consistency:** `SND_SFX_DISP_ID`/`SND_SFX_ID_TAB` used identically in Task 2 steps 1-4; `sfh_gain/sfh_duck/sfh_cap/sfh_rsvd` identical between Task 5 steps 3-4; divisor literals (`$140/$0EF/$078`) verified by running `gen_sound_tables.psg_divisor_table()` at plan time (indices 29/34/46).
- **Known hazards encoded:** sx_pad/sc_detune aliasing (Task 2 preamble), banked-code prohibition (session rules), sound build flag, emulator foreground-only, exact-path git adds, daemon-watched files.
