# Tools / build-and-data-generation layer — lens-panel adjudication packet

**Review SHA:** `ffe05158` (pinned; worktree `.worktrees/tools-lens`, branch `review/tools-lens-sweep`)
**Corpus:** `tools/**` (56 Python files, ~30,900 lines + `build.sh`, `test.sh`,
`regenerate-level.sh`, `prebuild.sh`), `games/sonic4/map.toml`, the generated tree under
`games/sonic4/data/generated/**`, and the authored editor data under `data/editor/**`.
**Panel:** 15 seats. The ratified roster adapted for a Python/build corpus — three seat
definitions replaced, flagged as a deliberate adaptation:
- **F (format fidelity) x2** replaces C3 (hardware timing): does what producers EMIT match
  what engine readers CONSUME (stride, width, endianness, bounds, alignment)?
- **C1** becomes bake-algorithm correctness rather than instruction perf.
- **R (reproducibility)** added: can the committed tree be re-derived at all?
Retained: A, A2, B1, C4, C5, and doubled V x2, C2 x2, B2 x2 with opposed walk orders and
mixed models.
**Adjudication:** every load-bearing citation below re-verified by the overseer against the
pinned tree. Verification status marked per finding. No seat reported BLOCKED.

---

## 1. Why this panel, and the headline

The 2026-07-16 engine-wide review scoped itself to "every engine and game SOURCE file".
`tools/` was never in it — 5 incidental mentions across 3,730 lines, all as fix venues.
Since then the layer absorbed a toolchain replacement (asl -> sigil, 2026-07-30) and the
`.asm` -> `.emp` flip, both of which invalidated path and format assumptions the tools were
built on.

**The headline is not any single bug. It is that this layer's verification is largely
decorative, and two of its three build-path gates were verified to measure nothing.**

Set against that: the genuinely good work in here is real and was confirmed by measurement,
not assumed. `verify_level_bin.py`'s ZX0 content round-trip decodes and byte-compares every
act-pool page — the single strongest gate in the layer. `art_rom_report.py` refuses to pass
on zero subjects, with a comment that says why ("silence is what a checker that analyzed
nothing produces"). `gen_compression_vectors.py` + `compression_selftest.emp` is the one
place in the whole project where a Python encoder is cross-validated against the real 68000
decoder on hardware, and it generates the consts its consumer reads rather than mirroring
them. `tile_dedupe.py` is flip-aware and was measured at the fixed point. The `f36b13ff`
DPLC repair holds.

---

## 2. Confirmed defects, ranked

### D1 — `regenerate-level.sh` is a destructive no-op: it overwrites the collision tables, then aborts · CRITICAL
**Seats:** C2a, Va, R (independently) · **Overseer-verified: YES, every link**

| Step | Effect |
|---|---|
| `:2` | `set -euo pipefail`, **no trap** (unlike `build.sh:193`'s STRESS_ART path) |
| `:35` | `import_sk_collision.py` runs FIRST |
| `import_sk_collision.py:75-76` | writes the base S&K bank to **both** `collision/base/` and the ROM-consumed `data/collision/` — unconditionally |
| `:47` | `ojz_strip_gen.py generate` -> `require_donor()` -> `SystemExit` |
| — | script aborts; tables are now base-bank, strips still carry **interned** indices |

Verified: `data/collision/{heightmaps,angles,solidity}.bin` all **DIFFER** from `base/`, so the
tree is in the interned state and one invocation of the documented re-bake destroys the
pairing. `grep -c collision tools/verify_level_bin.py` = **0** — the gate never looks.

Player result: every solid surface resolves to a different height profile, angle and
solidity class. Falls through terrain, or stopped by nothing.

`import_sk_collision.py:59-60` says these are "only DEFAULTS — `gen_collision_data.generate()`
overwrites them". That function does not exist, and the tool that actually overwrites them
cannot run. The safety story is wrong twice.

### D2 — The re-bake cannot run at all, because an editor auto-save reverted a hand fix · CRITICAL
**Seats:** C4, Va, A, R (four seats, independently) · **Overseer-verified: YES**

`project.json`'s `zones[0].tileset` points at `games/sonic4/data/editor/ojz_tiles.bin`.
Verified: **missing here**; present on the authoring checkout at 29 KB but **untracked**,
matched by `.gitignore:2 (*.bin)`. So `editor_data_available()` is False, `require_donor()`
exits, and `regenerate-level.sh` cannot run in any worktree or fresh clone. `build.sh`'s
`STRESS_ART=1` shape calls it, so that build shape is dead too.

**The provenance is the finding.** Seat A traced it:
```
2026-06-11  f2371ca0  fix(editor): project.json tileset -> chunks_tiles.bin — ojz_tiles.bin was deleted
2026-06-12  586cd3fa  chore(editor-data): save OJZ project state (BG library + section 0 assignment)
```
A deliberate fix, reverted the next day by an editor state save that the auto-commit daemon
landed unreviewed. The editor rewrites `project.json` wholesale on save, so **any repo-side
correction to an editor-owned field has a shelf life of one editing session**. That is an
active drift vector, not a stale file. Two months of a dead re-bake path followed from it.

Three sibling keys (`bgLayout`, `bgTiles`, `parallax`) are also dangling.

### D3 — The obvious repair of D2 detonates a silent blank-level bake that every gate passes · CRITICAL
**Seat:** C2a · **Overseer-verified: partial (file size confirmed; bake not executed)**

Point `project.json` at the file the docstring names (`editor/ojz/chunks_tiles.bin`) and
re-bake. That file is **0 bytes** (verified, and 0 in git since `b8f9fdbf`). Section
nametables reference tile indices up to 732, so all 589,824 cells reference past the end.
`collect_referenced_tiles` (`ojz_strip_gen.py:607-613`) substitutes a zero tile with **no
warning and no failure**: 733 referenced tiles -> 733 zero tiles -> dedupe -> **1** unique
tile -> a 1-page, 32-byte pool.

Every gate passes. `verify_act_pool`: pages==1, `pm_tiles*32 == len`, ZX0 round-trips (32
zero bytes compress fine). `verify_local_maps`: count 1 <= 2048, `map[0]==0`, nothing >=
pool_tiles. `art_rom_report`: ~0.0 KB against a 24 KB budget -> `ok`; its liveness guards
fire on *zero* pages, not on an absurdly small one. The only trace is the generator printing
**"Deduped: 1 (99.9% reduction)"** — a catastrophe rendered as a success metric.

### D4 — The "ROM Build" gate has never built the ROM it asserts about · HIGH
**Seat:** Va · **Overseer-verified: YES**

```
test.sh:182   ./build.sh -pe
build.sh:32   GAME="${1:-sonic4}"   ->  GAME=-pe, ROM_NAME=-pe, MAIN_ASM=games/-pe/game_root.asm
```
`-pe` is positional and is consumed as the game name. `build.sh:88-89` claims it "stays
accepted for CLI compatibility"; the flag loop at `:91-95` only matches `-nl|--no-lint`.

Then `test.sh:189` is `if [ -f "s4.bin" ]` — after the build fails, six sanity checks (size,
4 MB fit, evenness, SEGA magic, SSP, reset PC) run against **whatever `s4.bin` is on disk
from a previous manual build**. On any machine that has ever built by hand, `test.sh` prints
six confident PASS lines about a ROM that run did not produce.

### D5 — The build-fatal lint gate lints one file that emits no bytes, and the root cause is a path bug · HIGH
**Seats:** Vb, A2 · **Overseer-verified: YES (executed)**

`build.sh:173` runs `s4lint.py "${MAIN_ASM}"` build-fatally. `discover_files` resolves
includes against two candidates — `base_dir + inc` and `dirname(current) + inc` — but
`main()` passes `base_dir = dirname(entry_path)`, so for a top-level entry **both collapse to
the same wrong directory** and there is **no else branch**: the include is dropped silently.
Direct call returns one file. 2,386 lines of linter, 26 warning classes, **142 `.emp` files
unlinted**. `_SKIP_FILES`' `debug/debugger.asm` entry is dead code because that file is never
discovered in order to be skipped.

The comment three lines above says AS "resolves includes relative to the current working
directory (project root)" — correct, and exactly what the code fails to do.

### D6 — Two producers write `zone_bg.bin` with incompatible geometry · HIGH (latent)
**Seats:** Fa, C2a, B2a (three seats) · **Overseer-verified: YES**

```
engine        bg.emp:47         BG_LAYOUT_SIZE = 64*64*2 = 8192, column-major
producer 1    ojz_strip_gen     PLANE_B_H = 32  ->  4096 bytes, row-major
producer 2    inject_editor_bg  COLS, ROWS = 64, 64  ->  8192 bytes, column-major
committed                       8192 bytes (correct)
```
The tree is correct **only because the injector runs second**, and it is conditional on
`editor_bg_override.json` existing (`regenerate-level.sh:52-54`). Verified present, 122 KB.
Rename it, add a second act, or bake any act with no editor BG, and `BG_Init` blits 8,192
bytes from a 4,096-byte blob: transposed background over the first half, whatever the linker
placed next over the second. `act_assets.emp:12` embeds it with **no size ensure**, while
`collision_data.emp:22` two files away does exactly that. `bg.emp:142` says "No length guard
needed" — the guarantee it relies on is a shell-script `if`.

### D7 — `s4budget` has no threshold at all, and its parser is dead · HIGH
**Seats:** Va, Vb, A2, B2b · **Overseer-verified: YES**

`main()` returns 0 on every path. `_ROM_MAX` and `_OBJBANK_LIMIT` are used **only to format
percentages** — it can print "Object Bank ... 400.0% of 64 KB limit" and exit 0. The ROM, RAM
and object-bank budgets are gated by nothing; not by a broken gate, by the absence of one.

Separately its `_PAGE_BREAK_RE` keys on the AS page header, so on a real `.lst` it reports
`RAM: 0KB/64KB` and zero section rows. Wrapped in `|| true`. And its 40-test suite is why
this survived: every fixture is hand-authored to contain `AS V1.42 Beta ...` headers, so
fixture and parser were co-designed and the suite is green forever.

Its VRAM fallbacks are also the retired pre-relocation addresses: `0xD800`/`0xDC00` vs the
`ensure`d `$B800`/`$BC00` — off by `0x2000`, 256 phantom tiles of headroom.

### D8 — `./test.sh` writes committed ROM data; the "sandboxed" self-test is a producer · HIGH (armed by fixing D2)
**Seats:** Va, C2a, R · **Overseer-verified: YES (code read)**

`test_full_pipeline_runs` redirects `OUTPUT_DIR` **and `COLLISION_DIR`** to a tempdir. But
`COLLISION_DIR` is **never read anywhere in the module** — `generate()` writes the runtime
collision tables to a path recomputed from `__file__` (`:1709-1713`), and Pass 8 calls
`ojz_entity_gen.generate()`, whose `OUTPUT_PATH` is a module constant pointing at the real
tree. `test.sh` runs this, then builds the ROM from the mutated tree.

Currently masked by D2 (the abort happens first). **Fixing D2 arms it.**
`import_sk_collision.py:59-67` documents this precise incident class — "a test silently
reverted a committed bake and turned ~10 sigil port targets red" — and the bug is still live
in the sibling generator.

### D9 — DPLC `tile_start` wraps silently; the sibling field on the same line has a loud assert · HIGH (latent)
**Seats:** Fa, Fb, C1 · **Overseer-verified: YES (measured)**

`dplc_layout.py:163` — `word = ((tile_count - 1) & 0xF) << 12 | (tile_start & 0xFFF)`. The
`tile_count` nibble gets `assert 1 <= tile_count <= 16` at `:160` with a comment explaining
exactly this failure mode. `tile_start` gets a silent mask.

Measured headroom: knuckles 4,092 tiles with max referenced end **4,076** — **20 tiles** from
the `$1000` cliff. `knuckles_data.emp:13-21` records that the optimized layout already
produced 4,383 tiles and "25 of its entries across frames 234-250 silently wrapped", which is
why Knuckles ships the raw pair. The sibling `gen_characters.py:468` has the missing assert;
`dplc_layout.py` never got it.

### D10 — Committed artifacts with no producer, and 18 with no producer *and* no consumer · MEDIUM
**Seats:** R, A, C5 · **Overseer-verified: YES (measured)**

- **18 orphans**, 240 KB: `sec{0..8}_tiles.{bin,zx0}`. Zero references anywhere in the tree.
  Writer removed from `ojz_strip_gen.py`; files committed five weeks later by `b8f9fdbf`
  "TRACK the OJZ generated tree" as untracked build detritus. **45 days, nothing noticed** —
  the cleanest available proof that "review `git status` before committing" is not a gate.
- **`knuckles.bin`** (130,944 B) is md5-identical to its staging copy: no producer *and no
  input* (`art/uncompressed/characters/knuckles.bin` does not exist). Irreplaceable.
- **`bg_anim_banks.bin`** (49,152 B): the only embedder is inside `if anims:`, and the
  committed `bg_anim.emp` is the else-branch stub. `verify_level_bin` checks embed->file, never
  file->embed, so it cannot see this class.
- **Neither donor's revision is recorded anywhere.** Even the authoring machine cannot prove
  it would reproduce the committed bytes.

---

## 3. Coverage verdict

**Genuinely gated** (a real check, run by `build.sh`/`test.sh`, that can fail): act-pool
internal consistency including the **ZX0 decode-and-byte-compare** (the strongest gate here);
act-pool ROM footprint with correct zero-subject liveness; local-map well-formedness (even
size, count 1..2048, blank-first, out-of-pool bound); block-blob referential integrity; every
shipped DPLC's tile indices against its real art blob with missing-input-is-red; S4LZ
Python-internal round-trip; the compression golden vectors cross-validated on hardware.

**Gated only by something nobody runs:** all 400+ `s4lint` rules (D5); the VRAM placement
contract (`gen_vram_map.py` has zero callers and no `--check`); entity/ring data shape
(`ojz_entity_gen.py test` — which **fails today**, seat B2a ran it: it still asserts AS-era
`dc.b`/`objend` output); block-blob invariants (`ojz_block_gen.py test`); the replay stream
format; tile dedupe.

**Gated by nothing:** ROM/RAM/object-bank budgets (D7); the runtime collision tables (D1);
`entity_data.emp`; `zone_bg.bin`/`bg_tiles.bin`/`ojz_palette.bin` (`act_assets.emp` is absent
from `verify_level_bin`'s head list); 255 of every 256 blocks; `project.json`'s internal
consistency; reproducibility of the committed tree from its sources.

**945 test functions across 16 modules are invoked by nothing** — no CI, no
`pytest.ini`/`conftest.py`/`pyproject.toml`, and neither build script mentions `pytest`.
Seven of the sixteen have no `__main__` guard, so they cannot even be run by hand.

---

## 4. Convergences (independent seats, same target)

- **`project.json` tileset dead** — C4, Va, A, R (four seats).
- **`zone_bg.bin` two producers** — Fa, C2a, B2a (three seats).
- **DPLC `tile_start` wrap** — Fa, Fb, C1 (three seats).
- **`test.sh` writes committed data via the "sandboxed" test** — Va, C2a, R.
- **945 dark tests** — Va, Vb, A, R.
- **Silent-substitution family** — C1, C2a, C2b each enumerated it independently; union is
  ~10 sites where a malformed input becomes a plausible-but-wrong byte with no log line.

---

## 5. Measured reclaim (seat C5, hand-measured not estimated)

| Item | Bytes | Region |
|---|---|---|
| Run `dedup_art.py` on tails/knuckles/tails_tail (capped at 10 entries/frame) | 50,588 | ROM tail |
| Size collision tables to the interned count (20 of 256 used) | 8,024 | **data region (binding)** |
| `zone_bg.bin` column period + mask (16 unique columns of 64) | 6,144 | **data region (binding)** |
| Block index u16 cells (max offset 7,730) | 4,096 | **data region (binding)** |
| Alias `OJZ_Sec4_LocalMap` -> Sec2 (byte-identical, the sibling generator already does this) | 202 | **data region (binding)** |
| **Total** | **69,054** | of which **18,466 relieves the `$48000` wall** |

Verified independently: `dedup_art.py` was run on Sonic only. Sonic is at the fixed point
(3,046/3,046 unique, 0 B duplicated); tails/knuckles/tails_tail carry **53,824 B of literally
duplicated 32-byte tiles**, and `knuckles.bin` is md5-identical to staging.

**Measured non-win, recorded so it is not re-proposed:** flip-aware dedupe is already fully
collected — the act pool is **612/612 flip-unique** and `bg_tiles.bin` **448/448**. C5
recomputed all four orientations of every tile to check. It also declines character-art flip
dedupe on the correct grounds that a mapping piece is up to 4x4 tiles under a single H/V bit.

---

## 6. Open questions requiring something outside this tree

1. **`map.toml`'s consumer is sigil's `native.rs`.** Seat A verified name resolution and
   section coverage in both directions in-tree, but the R2 subsequence validation, the
   `append_deb2_appendix` island-last guard, the per-shape splits, and the one region with no
   matching anchor (`z80_moving_trucks_bank`) are unverifiable from here.
2. **Which tool produced the shipped character art?** `f36b13ff` disproved `dplc_layout.py`.
   Seat R's hypothesis is `dedup_art.py` (its docstring describes the smaller-than-source
   direction that matches) — cheap to falsify by running it and `cmp`.
3. **Do `rotate_profile` and S&K's authored rotated table agree?** Two producers of
   `heightmaps_rot.bin`, never compared. A 20-line test settles it permanently.

---

## 7. Seat conflicts and corrections

- **Orphan census (A vs the earlier working list)** — A is right. `gen_collision_data.py` is
  *not* callerless (imported inside one self-test) and `ojz_entity_gen.py` is reachable via
  `ojz_strip_gen.py:1970`. The real set is 13 executables, of which **6 are
  dormant-but-intended** — sole producers of committed ROM-embedded artifacts. Deleting those
  as "dead" would orphan live data.
- **`ojz_strip_gen:1364`'s discipline** ("a test function not listed here runs NOWHERE") —
  seat A checked all four sibling tools and found it **held in every one**, zero orphans. It
  was applied inside each file and never at the seam.

---

## 8. What was NOT covered

- No seat executed `regenerate-level.sh` or any generator that writes (read-only mandate), so
  D3's blank-level bake is reasoned from the code and the measured 0-byte input, not observed.
- Round-trip verification of `ojz_block_gen` sections 1-8 needs a run; only section 0 is
  covered by its own test.
- Whether the runtime block decoder agrees with `ojz_block_gen.decode_block` — that function
  is a test-only reimplementation never cross-checked against the engine.
- The sound producers were deliberately out of scope (swept 2026-08-13 by the sound panel).
