# DAC Drum-Library Readiness Implementation Plan (Banking Package 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clear every blocker for authoring a real drum library against the RATIFIED single-voice DAC format — descriptor insurance bytes, the Bank-D table-twin generator, and the authoring runbook.

**Architecture:** The 2026-06-24 DAC spec (single voice + pre-mixed composites) was ratified by the user 2026-07-03. This plan adds the ratification-time descriptor insurance (`ds_vol` + 2 reserved mix-cursor bytes, appended so no existing field offset moves), the `gen_sound_tables.py` data-only twin emitter (tested, activation documented, NOT wired into ROM until the first FM6=DAC drum song exists — no dormant data), and the authoring runbook in the DAC spec. The dead-68k-tables item from the queue doc is ALREADY RESOLVED (verified 2026-07-03: `data/sound/fm_patches.asm`/`sound_tables.asm` were removed earlier; `games/sonic4/main.asm:241-248` records why) — no task for it.

**Tech Stack:** AS Macro Assembler (Z80 in-project), Python 3 build tools, `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`.

**Worktree note:** branch off master AFTER `feat/sfx-fidelity` and `feat/sound-design-banking` merge (this plan cites line numbers as of `feat/sound-design-banking`; re-grep labels if drifted).

**Verification ground rules:** build gates + Python tests are the executable gates. Emulator checks are FOREGROUND-ONLY (controller session, oracle MCP) — never from subagents.

---

### Task 1: Grow `DacSample` 9→12 bytes (append-only)

**Files:**
- Modify: `sound_constants.asm:259-272` (struct + assert)

- [ ] **Step 1: Append the new fields to the struct**

In `sound_constants.asm`, replace the struct block (currently ending `DacSample endstruct ; = 9 bytes` with the `<> 9` assert) with:

```asm
; --- 12-byte ROM-resident sample descriptor (grown 9->12, ratification
; insurance 2026-07-03: ds_vol + mix-cursor reserve appended so no existing
; offset moves; v1 engine IGNORES all three new bytes — zero code) ---
DacSample struct
ds_bank         ds.b 1          ; +0  sample bank id = (addr & $7F8000) >> 15
ds_rate         ds.b 1          ; +1  RESERVED forward-compat (per-sample rate); v1 ignores it
ds_codec        ds.b 1          ; +2  codec selector (0 = raw 8-bit PCM; reserved for a future compressed codec)
ds_ptr          ds.w 1          ; +3  Z80-window ptr (addr & $7FFF)|$8000, little-endian
ds_length       ds.w 1          ; +5  raw byte count = sample count; < $8000
ds_loop_ofs     ds.w 1          ; +7  RESERVED forward-compat (loop restart); v1 = 0, ignored
ds_vol          ds.b 1          ; +9  RESERVED (per-voice volume for a future mixer; v1 = 0, ignored)
ds_mix_rsvd     ds.w 1          ; +10 RESERVED (mix-cursor pair for a future mixer; v1 = 0, ignored)
DacSample endstruct             ; = 12 bytes

        if DacSample_len <> 12
          error "DacSample struct is \{DacSample_len} bytes, expected 12"
        endif
```

- [ ] **Step 2: Build to see the EXPECTED failure (table-size assert fires)**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh 2>&1 | tail -20`
Expected: FATAL `"DacSampleTable wrong size for DAC_SAMPLE_COUNT"` (dac_sample_tab.asm:~109). This proves the guard works; Tasks 2-3 fix the consumers.

### Task 2: Fix the ×9 stride math in `Snd_DacLookup`

**Files:**
- Modify: `engine/sound/z80_sound_driver.asm:696` (comment) and `:711-721` (math)

- [ ] **Step 1: Replace the index×9 sequence with index×12**

Current code (z80_sound_driver.asm:711-721):

```asm
        dec     a                        ; index = id-1
        ; hl = DacSampleTable + index*DacSample_len (9). index*9 = index*8 + index.
        ld      l, a
        ld      h, 0
        ld      e, l                     ; save index
        ld      d, h
        add     hl, hl
        add     hl, hl
        add     hl, hl                   ; hl = index*8
        add     hl, de                   ; hl = index*9
        ld      de, DacSampleTable
        add     hl, de                   ; hl = &DacSampleTable[index]
```

Replace the math body with (same register/flag contract, same instruction count):

```asm
        dec     a                        ; index = id-1
        ; hl = DacSampleTable + index*DacSample_len (12). index*12 = (index*3)*4.
        ld      l, a
        ld      h, 0
        ld      e, l                     ; save index
        ld      d, h
        add     hl, hl                   ; hl = index*2
        add     hl, de                   ; hl = index*3
        add     hl, hl                   ; hl = index*6
        add     hl, hl                   ; hl = index*12
        ld      de, DacSampleTable
        add     hl, de                   ; hl = &DacSampleTable[index]
```

Also update the routine-header comment at `:696` from
`(Stride is DacSample_len = 9; index*9 computed as index*8 + index.)` to
`(Stride is DacSample_len = 12; index*12 computed as (index*3)*4.)`

- [ ] **Step 2: Commit (still red — table not grown yet; commit sequenced with Task 3)**

Hold the commit until Task 3 Step 3 (a red build must not land on the branch — CLAUDE.md never-leave-broken rule).

### Task 3: Grow the 10 `DacSampleTable` entries

**Files:**
- Modify: `engine/sound/dac_sample_tab.asm:34-106` (all 10 entries)

- [ ] **Step 1: Append the two reserved lines to every entry**

Each of the 10 entries ends with `        dw      0                        ; ds_loop_ofs (reserved; 0 = one-shot)`. Append after EACH such line:

```asm
        db      0                        ; ds_vol (reserved; v1 ignored)
        dw      0                        ; ds_mix_rsvd (reserved; v1 ignored)
```

Deterministic edit (run from repo root; makes all 10 insertions):

```bash
python3 - <<'EOF'
p = 'engine/sound/dac_sample_tab.asm'
s = open(p).read()
needle = "        dw      0                        ; ds_loop_ofs (reserved; 0 = one-shot)\n"
add = ("        db      0                        ; ds_vol (reserved; v1 ignored)\n"
       "        dw      0                        ; ds_mix_rsvd (reserved; v1 ignored)\n")
n = s.count(needle)
assert n == 10, f"expected 10 entries, found {n}"
s = s.replace(needle, needle + add)
open(p, 'w').write(s)
EOF
```

- [ ] **Step 2: Build green**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh 2>&1 | tail -8`
Expected: `Build complete: s4.bin` and the Z80 budget message unchanged from baseline (this is data in the banked table, not resident code — resident free bytes must NOT change; record the number).

- [ ] **Step 3: Commit Tasks 1-3 together**

```bash
git add sound_constants.asm engine/sound/z80_sound_driver.asm engine/sound/dac_sample_tab.asm
git commit -m "feat(sound): DacSample 9->12 — ds_vol + mix-cursor reserve appended (DAC ratification insurance, zero engine reads)"
```

- [ ] **Step 4 (controller session only): oracle sanity — one drum trigger**

Foreground: load `s4.bin` in oracle, trigger a DAC sample (boot auto-plays MT which uses drums, or `Sound_PlaySample` via debug). Verify a drum sounds and `SND_STAT_DAC_ACTIVE` pulses (z80_read `0x1F14`). This pins the stride math against a live descriptor.

### Task 4: Bank-D data-only twin emitter in `gen_sound_tables.py`

**Files:**
- Modify: `tools/gen_sound_tables.py` (add `emit_asm_z80_data_only()` beside `emit_asm_z80()` ~line 260-307)
- Test: `tools/test_gen_sound_tables.py` (create if absent; follow `tools/test_song_packer.py` pytest style)

- [ ] **Step 1: Write the failing test (byte-equality, labels ignored)**

```python
# tools/test_gen_sound_tables.py
import re
import gen_sound_tables as g

def _data_bytes(asm_text):
    """Collapse an emitted asm blob to its raw db/dw payload tokens, ignoring
    labels, comments, and blank lines — the twin must be byte-identical."""
    out = []
    for line in asm_text.splitlines():
        line = line.split(';', 1)[0].strip()
        if not line or line.endswith(':'):
            continue
        m = re.match(r'(db|dw)\s+(.*)', line)
        assert m, f"unexpected line in table asm: {line!r}"
        out.append((m.group(1), [t.strip() for t in m.group(2).split(',')]))
    return out

def test_data_only_twin_is_byte_identical():
    labeled = g.emit_asm_z80()
    twin = g.emit_asm_z80_data_only()
    assert _data_bytes(labeled) == _data_bytes(twin)

def test_data_only_twin_defines_no_labels():
    twin = g.emit_asm_z80_data_only()
    assert not re.search(r'^\w+:', twin, re.M)
```

(If `emit_asm_z80()` takes arguments or writes files instead of returning text, adapt BOTH the test and the new function to the existing signature — the invariant under test is unchanged: same payload tokens, zero label definitions.)

- [ ] **Step 2: Run it to fail**

Run: `cd tools && python3 -m pytest test_gen_sound_tables.py -v`
Expected: FAIL — `AttributeError: ... no attribute 'emit_asm_z80_data_only'`

- [ ] **Step 3: Implement `emit_asm_z80_data_only()`**

The function reuses `emit_asm_z80()`'s payload emission verbatim and strips label lines. Cheapest correct implementation — derive, don't duplicate:

```python
def emit_asm_z80_data_only():
    """Label-free twin of emit_asm_z80() for REPLICATE-PER-BANK co-location
    (DEFERRED_WORK 'Bank-D co-location hook'): identical bytes, no symbol
    definitions, so the same tables can be emitted at the head of a second
    bank (the DAC sample bank) without duplicate-label errors. ACTIVATION:
    include the generated file in games/sonic4/main.asm inside a
    `cpu z80`/`phase 08000h` block immediately after dac_samples.asm's
    `align $8000` — ONLY when the first FM6=DAC-drum (COPY-class) song
    ships; until then nothing includes it (no dead ROM)."""
    import re
    labeled = emit_asm_z80()
    return re.sub(r'^\w+:\s*\n', '', labeled, flags=re.M)
```

- [ ] **Step 4: Run tests to pass**

Run: `cd tools && python3 -m pytest test_gen_sound_tables.py -v`
Expected: 2 PASS. Also run the full tool suite: `python3 -m pytest tools/ -q` — no regressions.

- [ ] **Step 5: Commit**

```bash
git add tools/gen_sound_tables.py tools/test_gen_sound_tables.py
git commit -m "feat(tools): data-only Z80 table twin emitter (Bank-D co-location hook, byte-equality tested; ROM activation deferred to first drum song)"
```

### Task 5: Authoring runbook + pre-mix decision in the DAC spec

**Files:**
- Modify: `docs/superpowers/specs/2026-06-24-dac-drum-format-revision-design.md` (append section)

- [ ] **Step 1: Append the runbook section**

```markdown
## Drum-library authoring runbook (added 2026-07-03, package 3)

Prereqs now in place: 12-byte descriptor (`ds_vol`/`ds_mix_rsvd` reserved), Bank-D
twin emitter tested (`tools/gen_sound_tables.py::emit_asm_z80_data_only`, activation
documented in its docstring). Steps for a future drum-kit session:

1. Prepare mono WAVs (16-bit signed or 8-bit unsigned).
2. Convert: `tools/import_s3k_dac.py::wav_to_raw8(path, pitch_ratio=...)` — bakes
   pitch at the fixed ~18356 Hz engine rate; output raw 8-bit unsigned, $80-centered.
3. Drop `.pcm` files in `games/sonic4/data/sound/dac/`; BINCLUDE + derive
   `SND_*_BANK/PTR/LEN` in `games/sonic4/data/sound/dac_samples.asm` (S3K entries
   at :63-83 are the template; single-bank guard at :87-89 — add per-bank guards
   if the kit spans banks, the per-sample `ds_bank` supports it).
4. Add 12-byte descriptors in `engine/sound/dac_sample_tab.asm`; bump
   `DAC_SAMPLE_COUNT`; the size assert self-checks.
5. **Overlapping drums** (kick+snare on one tick): author a pre-mixed composite
   sample — the ratified model. Build-time mixer tool (`tools/mix_dac_samples.py`:
   read N raw8 + per-source gain → clipped sum → composite `.pcm`) is DEFERRED to
   the first song that needs a composite (clean-not-bolted-on); interface sketched
   here so the session can build it cold.
6. First COPY-class (FM6=DAC) song additionally activates the Bank-D twin: emit
   `emit_asm_z80_data_only()` output to a generated include and add it in
   `games/sonic4/main.asm` after `dac_samples.asm`'s `align $8000` under
   `cpu z80`/`phase 08000h` (see main.asm:272-282 REPLICATE-PER-BANK comment).
7. Verify: build green → oracle foreground: trigger each sample id, confirm
   `SND_STAT_DAC_ACTIVE` pulse + rendered capture (vgm2wav) per drum; A/B the kit
   against its source (feedback rule: rendered audio, not registers).
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-06-24-dac-drum-format-revision-design.md
git commit -m "docs(sound): DAC spec — drum-library authoring runbook (package 3)"
```

### Task 6: Close the loop in tracking docs

**Files:**
- Modify: `docs/DEFERRED_WORK.md` (E2 ratification entry: insurance DONE; Bank-D entry: generator DONE, activation pending first drum song)
- Modify: `docs/superpowers/2026-07-03-sound-banking-queue.md` (package 3 row → EXECUTED)

- [ ] **Step 1: Annotate both docs** — in DEFERRED_WORK's E2 entry (~:1358) append `*(Descriptor insurance LANDED <commit> — ds_vol + ds_mix_rsvd shipped, 12-byte descriptor.)*`; in the Bank-D follow-up entry (~:1141) append `*(Generator twin LANDED <commit>, byte-equality tested; ROM activation still rides the first COPY song.)*`. Update the queue-doc package 3 row status.

- [ ] **Step 2: Build one final time + commit**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh 2>&1 | tail -4` → green.

```bash
git add docs/DEFERRED_WORK.md docs/superpowers/2026-07-03-sound-banking-queue.md
git commit -m "docs(sound): package 3 executed — tracking sync"
```

---

## Self-review notes (spec coverage)

- Ratified-bet insurance (`ds_vol` + mix-cursor bytes) → Tasks 1-3. Appended, offsets stable, v1 zero engine reads (spec-conform).
- Bank-D co-location hook → Task 4 (tool + test now; no dormant ROM data — activation is runbook step 6).
- Dead 68k tables → verified already removed; recorded in header, no task.
- Authoring guidance + pre-mix tool decision → Task 5 (mixer deferred with a cold interface sketch).
- Doc sync → Task 6.
