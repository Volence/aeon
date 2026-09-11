# Lens comments parcel, 2026-09-11: B2b-6, B2a-3, CTRL-10, and two side findings

Branch `parcel/lens-comments-0911`, cut from `origin/master` = `3492ce3a`. Zero bytes, proved below.
No emulator was touched. `docs/DEFERRED_WORK.md` and `docs/lens-findings.jsonl` were NOT edited:
the proposed ledger lines are at the end of this note, for the controller to append.

## Commits, in order

| commit | what |
|---|---|
| `c99983d0` | B2b-6: the dead `.asm` citations LS-24 left, `engine/sound` and `parallax.emp` first |
| `b9dc6162` | side finding (a): three live citations that pointed at the wrong text, respelled by name |
| `df298d40` | CTRL-10: dated amendment to the 09-06 packet |
| `45b5fdee` | B2a-3: the scene equivalence oracle's decode re-spelled independently |
| `77434635` | side finding (c): `engine/level/bg.emp` plane-geometry pins, first version |
| `88076c90` | the same pins split, after the first red run showed a message that blamed the wrong axis |
| this note | evidence and proposed ledger lines |

## Zero bytes

**Base**, before the first edit: `./tools/landing_build.sh` at `3492ce3a`, detached, `finished=0`,
`REAL_EXIT=0`. All four ROMs carry mtimes after the run started (16:21:38; ROMs 16:25 to 16:35).

```
3697579482 821103 s4.bin
394963879 847367 s4.debug.bin
755353563 97051 demo.bin
4271321717 103335 demo.debug.bin
```

Base pytest summary lines, in log order: `2428 passed, 2 skipped, 14 deselected, 5 warnings, 112
subtests passed` (x4, one per shape), `5 passed, 9 skipped, 2430 deselected`, `6 passed, 8 skipped,
2430 deselected`, `1 passed, 13 skipped, 2430 deselected` (x2), `14 passed, 2430 deselected`, then
`pytest exit 0 -- 14 case(s) in the report: 14 ran, 0 deferred, 0 failed`.

**Mid-parcel**, canonical `DEBUG=1 ./build.sh` over the tree carrying items 1 to 4 and the first bg
pins: exit 0, sigil `crc=18dfb704 len=847367`, `s4.debug.bin` cksum `394963879 847367`, equal to base.

**Tip**: `./tools/landing_build.sh` at this note's own commit. Its totals and the four tip CRCs are
in the handoff message, not here, because a file cannot record the build of the commit that adds it.

## Item 1: B2b-6, the dead `.asm` citations

**Method, re-derivable.** A script that prints its pattern: LS-24's P1 token (a path or basename
ending `.asm`) over every tracked `engine/**/*.emp` and `games/**/*.emp` (197 files). Each
occurrence is classed in order: EXISTS (names a `.asm` tracked at HEAD), BARE (`.asm` with no
basename), DEAD (the basename of a `.asm` this repo DELETED, taken from
`git log --diff-filter=D --name-only -- '*.asm'`), otherwise EXTERNAL. DEAD is split by a word test
(deleted, retired, former, gone, port, once, was, ...) over the line and the two above it, and
every row was then read by hand, because a word test is a filter and not a verdict.

| | base `3492ce3a` | tip |
|---|---|---|
| occurrences (lines) | 229 (225) | 210 (206) |
| EXISTS | 3 | 3 |
| BARE | 32 | 30 |
| EXTERNAL | 137 | 137 |
| DEAD, word test says historical | 34 | 33 |
| DEAD, word test says live | 23 | 7 |

**Repointed by symbol**, each to the `.emp` that holds the fact now:

- `engine/sound`, 24 occurrences over 7 files (18 dead basenames, 6 bare `.asm`-twin prose):
  `dac_sample_tab.emp` x3, `seq_opcode_tab.emp` x6, `sound_api.emp` x2, `sound_fm.emp` x4,
  `sound_psg.emp` x1, `sound_sfx.emp` x5, `z80_sound_driver.emp` x3.
- `engine/level/parallax.emp` x3, one of them the `Parallax_State` span ensure's MESSAGE.
- `engine/system/buffers.emp` x1 (it cited an "engine.structs .emp == .asm wall"; `git grep`
  finds that phrase nowhere else, and `engine/structs.asm` is deleted), `engine/objects/children.emp`
  x1, `games/sonic4/data/sound/dac_samples.emp` x2, `games/sonic4/config/sound_ids.emp` x1 (no
  `.asm` residual reads `SONG_COUNT`: `git grep SONG_COUNT -- '*.asm'` is empty).

**Marked historical, no successor:** `seq_opcode_tab.emp`'s replicate-per-bank rule was stated at
the deleted `main.asm` phase block. `git grep "replicat|identical-layout|per-bank"` over `engine/`
and `games/` finds it nowhere else, so the comment now says it is the rule's only statement.

**Kept, each read:** the 33 historical rows already say deleted, retired, ported or former. Of the
7 the word test still calls live, 6 are `mt_bank.emp` provenance lines under its "READING THE
`.asm` CITATIONS BELOW" banner with a `git show 19fce50b^:` recovery pointer, which LS-24 kept on
purpose, and the 7th is `buffers.emp`'s own new wording ("left with engine/structs.asm"), which the
word test does not recognise. The 137 EXTERNAL rows are S3K, S2, S.C.E., sonic_hack and the Batman &
Robin disasm (`code/effects/effects.asm`, twice in `parallax.emp` and twice in `ojz_scenes.emp`).

## Item 2: B2a-3, the oracle that shared its subject's spelling

`games/sonic4/test/scene_equiv_proof.emp` `cfg_band` now decodes all five packed fields
(`band_factor_a_s1`, `_a_s2`, `_b_s1`, `_b_s2`, `band_factor_ops`) by division and remainder and
SUMS the op byte, where `engine/level/scene_dsl.emp` `scene_band()` shifts, masks and ORs. The two
forms agree for every non-negative value, and `packed()` in `parallax_dsl.emp` only makes 0..$1FF.
The file header's "moved, not re-typed" now names the exception.

**Red proof** (a re-spelling, not a new guard, but it had to be shown live): committed-clean tree;
the ORACLE's `band_factor_a_s2: (fa / 16) % 16` mutated on disk to `(fa / 8) % 16`, read back as
`games/sonic4/test/scene_equiv_proof.emp:184`; canonical `DEBUG=1 ./build.sh` exit **1**, with
`scene equivalence: Scene_OJZ_LockedClouds BAND 2 differs at band field 2` and siblings (Caves BAND
4, LockedClouds BAND 0 to 4) in the sonic4 plain, sonic4 debug and config_a shapes. Band field 2 is
`band_factor_a_s2`, the mutated field. Restored by `git checkout --` of that one path; tree clean.

## Item 3 (side finding c): `engine/level/bg.emp` plane-geometry pins

**Sites**, enumerated by what TOUCHES the plane size over the whole file, not by one grep:

| site | axis |
|---|---|
| `pub const BG_LAYOUT_SIZE = 64*64*2` | both |
| BG_Init `move.w #$8F80, VDP_CTRL` (row bytes = PLANE_H_CELLS*2) | H |
| BG_Init `cmpi.w #64, d1` (.nt_col column count) | H |
| BG_Init `moveq #32-1, d0` (PLANE_V_CELLS/2 - 1 longwords per column) | V |

Read and rejected: `add.w d0, d0` (the 2-byte cell), the tile blit's `$8F02` (autoincrement 2),
`VRAM_PLANE_B_BYTES` (already a constant).

**Final form (`88076c90`):** three ensures at the end of the file. H: `PLANE_H_CELLS == 64 &&
PLANE_H_CELLS * 2 == $80`. V: `PLANE_V_CELLS == 64 && PLANE_V_CELLS / 2 - 1 == 32 - 1`. LAYOUT:
`BG_LAYOUT_SIZE == PLANE_H_CELLS * PLANE_V_CELLS * 2`. Each message names its sites and what it does
not cover. The sibling messages that said bg.emp was "NOT pinned" (`section.emp` x2,
`plane_buffer.emp` x2, `constants.emp`'s reg $10 pin) now say where it is.

**Runner:** `sigil build` via `./build.sh`, build-fatal. **Harness:** `tools/ls8_pin_redproof.py`,
keys P14/P15/P16 and mutations M24/M25/M26, all three in its CANONICAL set, so each red run is a
real `DEBUG=1 ./build.sh`, not FAST. Run with `LS8_OUT` outside the tree (see the last section).
Every mutation was applied only after the guard was committed, quoted back from disk before the
build, and restored with `git checkout --` of the exact mutated paths; the tree was clean after each.

**First red run, against `77434635` (both axis pins carrying the layout term):**

| mutation (read back from disk) | exit | guards |
|---|---|---|
| M24 `PLANE_H_CELLS = 128`, `VDP_REG_PLANE_SIZE = $13` | 1 | P9 P11 P14 P15 |
| M25 `PLANE_V_CELLS = 32`, `VDP_REG_PLANE_SIZE = $01` | 1 | P10 P12 P14 P15 |
| M26 `BG_LAYOUT_SIZE = 64*32*2` | 1 | P14 P15 |

All red, and it exposed a defect: in M25 and M26 the HORIZONTAL pin fired with `PLANE_H_CELLS is now
64, but engine/level/bg.emp hand-spells a 64-column plane`, a false sentence about the build it
failed. M26 also showed `[emit.size-mismatch] data OJZ_Act1_BG_Layout: declared type is 4096 byte(s),
initializer produced 8192` from `act_assets.emp`'s typed embed. Hence `88076c90`.

**Re-run against `88076c90`.** The expectations were written into the harness BEFORE the run
(M24 -> P9 P11 P14 P16; M25 -> P10 P12 P15 P16; M26 -> P16 only, plus the embed refusal). Each was
met exactly. The raw-log columns count lines containing each message in that mutation's build log:

| mutation | exit | guards (harness) | bg H | bg V | bg LAYOUT | embed refusal | reg $10 (P13) |
|---|---|---|---|---|---|---|---|
| M24 | 1 | P9 P11 P14 P16 | 7 | 0 | 6 | 0 | 0 |
| M25 | 1 | P10 P12 P15 P16 | 0 | 6 | 6 | 0 | 0 |
| M26 | 1 | P16 | 0 | 0 | 6 | 6 | 0 |

The horizontal bg pin no longer fires when `PLANE_H_CELLS` has not moved. P13 is silent in all three
because each mutation re-encodes the reg $10 byte, and that is the point: the bg pins are what a reader
meets after doing what P13 says. Harness summary: `guards seen RED in THIS invocation: 7/32`
(a partial run by design; P9 to P12 are LS-8a's, re-seen here alongside the new three).

## Item 4 (side finding a): three live citations that pointed at the wrong text

| citer | cited | text there at base | now |
|---|---|---|---|
| `docs/EFFECTS_AUTHORING.md` (reg_sh_on row) | `boot_data.emp:140` | a `// ----` rule line | `VDP_REG_0C_BOOT`, the `$0C` row of `BootData_VDPRegs` in `engine/system/boot_data.emp` |
| `engine/effects/raster_dsl.emp` (reg_sh_on header) | `boot_data.emp:140` | same | same |
| `tools/dma_straddle_exercise.py` (docstring) | `dma_queue.emp:170` | `lea ENTRY_LEN(a1), a1` | `engine/system/dma_queue.emp`, `.full` vs `.split_reject` in the shared `.transfer` core |

## Item 5: CTRL-10

The packet gets a dated amendment after its summary: the B2a section and B2b items 6 and 7 were never
written, not deleted, and they are NOT reconstructed. It names the ledger rows that cite the packet
without evidence (B2a-1 to B2a-4) and says ledger B2b-6 is the body's B2b-8. Append-only (26 added, 0
removed), so no coordinate into the packet moves. `git grep B2b-7` over the ledger,
`docs/superpowers/notes/` and `docs/DEFERRED_WORK.md` returned nothing.

## Citation gate: base versus tip text at every cited line

Every `X.emp:N` in the tree (LIVE and RECORDS) that resolves into one of the 20 files this parcel
touched or re-points, snapshotted at base and at `88076c90` with `tools/test_citation_form.py`'s own
regex and resolver: **1192 at base, 1189 at tip, and the cited text changed at 9**, every one of them
on a line this parcel edited, each keeping its referent:

- 3 are the wrong citations above, now respelled by name, so they no longer parse as citations.
- 4 are `poison_extern_span.emp` citing `parallax.emp`'s `Parallax_State` span ensure, whose MESSAGE
  changed ("drifted from ram.asm" became the `engine/ram.emp` span). That poison's EXPECTED FRAGMENT is
  its own message, not this one.
- 2 are dated RECORDS (the 2026-09-09 ledger sift B and the 2026-09-11 open sift) quoting the old text
  of `seq_opcode_tab.emp`'s banked line and of `cfg_band`'s `fa & 15` as their finding.

No citation moved onto other text. Every edit was in-line except the bg.emp pins, appended below the
file's last line, and the packet amendment, appended at its end.

## Effects-gate files touched

`engine/effects/raster_dsl.emp` (one comment line, item 4) and `engine/system/buffers.emp` (one
comment line, item 1). Both are effects-gate files. `tools/effects_gates.py` was NOT run: it boots
an emulator, and the controller runs it at landing.

## What in the brief was wrong or weaker than stated

- `scene_equiv_proof.emp` lives at `games/sonic4/test/`, not `engine/level/`.
- "About 62" dead citations: this census measures 57 dead-basename occurrences plus 32 bare `.asm`
  mentions at base. The sift's token counts include externals (its "constants.asm 5" is 2 in-repo, both
  already historical, plus 3 `sonic3k.constants.asm`).
- `parallax.emp` had 3 live dead citations, not LS-24's 4: its other two `.asm` tokens are the
  Batman & Robin disasm, which is external.
- The brief named `raster_dsl.emp` as the one effects-gate file. B2b-6 also needed `buffers.emp`,
  which is on the same list.
- `tools/ls8_pin_redproof.py`'s default output directory `.ls8-redproof` is not gitignored, so the
  harness's own `clean_check()` would refuse its second mutation. The runs here used `LS8_OUT`, and
  the harness docstring now says so.
- The harness's "first line" print picks the first log line containing a key, and sigil's
  per-shape summary lines concatenate several errors, so a key's "first line" can show another pin's
  message (M25's P14 printed a `section.emp` line in the first run). Read the raw log per mutation.
- `docs/EFFECTS_AUTHORING.md` row `reg_sh_on()` keeps one em-dash that predates this parcel. Only the
  citation later in that row was edited.
- DEFERRED_WORK's "Side findings of the 2026-09-11 lens-pins parcel" (a) and (c) are closed by this
  parcel; (b), (d) and (e) are untouched. The strike is the controller's, since this parcel may not
  edit that file.

## Proposed ledger lines (append; `fixedAt` is the merge)

Each is the id's latest ledger line (B2a-3 line 18, B2b-6 line 102, CTRL-10 line 122) with only `at`,
`state`, `fixedAt` and `detail` changed.

```json
{"id": "B2b-6", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "B2b", "severity": "low", "title": "Comments across the engine cite assembler files that no longer exist", "state": "fixed", "fixedAt": "<merge>", "detail": "FIXED by parcel/lens-comments-0911, commit c99983d0, finishing LS-24's residual. Re-enumerated at 3492ce3a by a census that prints its pattern (LS-24's P1 token, a path or basename ending .asm, over the 197 tracked engine/ and games/ .emp files; DEAD = the basename of a .asm this repo deleted, per git log --diff-filter=D): 229 occurrences, 57 DEAD (34 already historical by a word test, 23 live) plus 32 bare .asm mentions. Repointed by symbol to the .emp that now holds each fact: all 24 live occurrences in engine/sound (18 dead basenames and 6 bare twin prose, over 7 files) and 3 in engine/level/parallax.emp (one the Parallax_State span ensure's message), plus buffers.emp, children.emp, dac_samples.emp x2 and sound_ids.emp. seq_opcode_tab.emp's replicate-per-bank rule has no live successor and is now marked as its only statement. After: 210 occurrences, DEAD 40, of which the word test calls 7 live: 6 are mt_bank.emp provenance lines under its git-show recovery banner (kept, as LS-24 ruled) and 1 is buffers.emp's new historical wording. Zero-byte and line-neutral; four-shape CRCs at the tip equal to base (tools/landing_build.sh).", "batch": "LS-24"}
{"id": "B2a-3", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "B2a", "severity": "medium", "title": "A proof described as an independent oracle transcribes the code it is checking for most of its fields", "state": "fixed", "fixedAt": "<merge>", "where": {"path": "games/sonic4/test/scene_equiv_proof.emp", "line": 170}, "detail": "FIXED by parcel/lens-comments-0911, commit 45b5fdee. cfg_band now decodes the five packed band fields (band_factor_a_s1, _a_s2, _b_s1, _b_s2, band_factor_ops) by division and remainder and sums the op byte, where engine/level/scene_dsl.emp scene_band() shifts, masks and ORs, so the two sides share no spelling and a wrong decode cannot be copied from one into the other. Equal for every non-negative value; packed() only produces 0..$1FF, and the comment says both. Zero-byte (the module emits nothing). Red proof through a canonical DEBUG=1 ./build.sh: the ORACLE's band_factor_a_s2 mutated to (fa / 8) % 16 gave exit 1 with 'scene equivalence: Scene_OJZ_LockedClouds BAND 2 differs at band field 2' and siblings, so the re-spelled line is the one compared; restored from the committed file."}
{"id": "CTRL-10", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "controller", "severity": "low", "title": "The packet is missing a whole seat's write-up and two of another seat's items, while the summary and the ledger both count them", "state": "fixed", "fixedAt": "<merge>", "where": {"path": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md"}, "detail": "FIXED by parcel/lens-comments-0911, commit df298d40, by the row's second admissible close: the packet now ends with a dated amendment recording that the Seat B2a section and Seat B2b items 6 and 7 were never written, not deleted. It is not a reconstruction. It names the ledger rows that cite the packet without evidence (B2a-1 to B2a-4) and says ledger B2b-6 is the body's B2b-8. git grep B2b-7 over the ledger, docs/superpowers/notes/ and docs/DEFERRED_WORK.md returned nothing. Append-only (26 lines added, 0 removed), so no coordinate into the packet moved.", "batch": "Tier 3"}
```

The bg.emp pins and the citation respells are side findings, not ledger ids.
