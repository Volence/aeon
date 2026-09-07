# Aeon art & data pipeline contract — addendum

**Companion to `docs/ART_PIPELINE_CONTRACT.md`.** Same audience: an outside tool that
has never seen this engine and cannot run its build. Read the main document first; this
one answers four questions it did not.

## How to read this document

The main contract's governing rule applies here unchanged, and it is the whole job:
**every number and format below was derived from source or from a built artifact, and
the source is named beside it.** Nothing was copied out of this repo's own prose. The
main document's opening explains why in detail; the short version is that a review sweep
of this tree found a documented RAM span of 556 bytes that measured 820, a structure
documented at 66 bytes that is 34, and a tile ceiling documented as 448 that the source
says is 400.

Order of authority, unchanged: **emitted artifact → the source that produces it →
prose.** Where something could not be established, this document says **NOT ESTABLISHED
HERE** and §A5 collects those. Treat them as questions to ask, not as gaps to guess at.

One addition to the rule for §A2: that section summarises a contract that lives in a
**different repository**, so it is pinned to a named tree at a named commit and comes
with an explicit expiry note. Do not treat this repo's summary as the authority for that
schema — it is a snapshot of someone else's contract.

### The four questions

| | Question | Answered in |
|---|---|---|
| 1 | The background override format and the importer options | §A1 |
| 2 | The effects schema, at a pinned revision | §A2 |
| 3 | Can the background **tileset** be replaced between sections, or only the **nametable**? | §A3 |
| 4 | What OJZ act 1 allocates today, and what it *should* allocate | §A4 |

**§A3 is the one that changes how you author.** The short answer is at the top of it.

---

## A1. The background override format, and the three scripts around it

### A1.1 The file, and who writes it

There is exactly one override file in this tree:

```
games/sonic4/data/editor_bg_override.json
```

Verified by `find games -name "editor_bg_override*.json"` — one result. It is **one file
per act, not per section**; see §A3 for why that matters. The un-suffixed spelling is a
legacy: `tools/inject_editor_bg.py`'s `BgActNames.override_path` (`:768`) builds
`editor_bg_override_{zone_id}_{act_id}.json` for every act *except* the one act that
predates the tool taking an act parameter, which keeps the bare name
(`LEGACY_OVERRIDE_REL`, `:723`). OJZ act 1 is that act.

Three programs touch this file, and only one of them is an importer you would run:

| Program | Role | Reads | Writes |
|---|---|---|---|
| `tools/png_to_bg_override.py` (315 lines) | **the importer** — PNG in, override out | a PNG | `editor_bg_override.json` |
| `tools/inject_editor_bg.py` (1,395 lines) | the **consumer** — bakes the override into engine artifacts | `editor_bg_override.json` | `zone_bg.bin`, `bg_tiles.bin`, `bg_anim.emp`, `bg_anim_banks.bin`, and conditionally `ojz_palette.bin` |
| `tools/ojz_strip_gen.py` (2,227 lines) | the level-data generator that runs **before** the injector | out-of-repo donors + the editor tree | the whole `data/generated/ojz/act1/` tree, including a `zone_bg.bin` the injector then overwrites |

The Aurora editor is a fourth writer, from outside this repo
(`tools/bg_override_io.py:~92`: *"This file has multiple writers across two repos — this
chokepoint for aeon, Aurora's `serializeBgOverride` for the editor"*).

**If you want the scripts themselves**, they are at the three paths above. This section
is the contract they implement; it is derived from them and is what you should build
against.

### A1.2 Canonical serialization

`tools/bg_override_io.py::atomic_write_json` is aeon's single writing chokepoint. Its
whole body, quoted:

```python
data = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
```

So: **sorted keys, no separator padding, no trailing newline, one line.** Write via a
temporary sibling and `os.replace` (the function does), so a crash cannot truncate the
file. The live file is 105.6 KB on one line, consistent with this.

⚠ **This conflicts with a rule in the `empyrean` repo, and the conflict is real.**
`empyrean docs/AURORA_EFFECTS_SCHEMA.md` §8 (at the SHA pinned in §A2) rules that every
JSON file Aurora writes into aeon's tree ends in **exactly one `\n`**, and names
`editor_bg_override.json` explicitly. aeon's own writer emits no such byte, and the
on-disk file matches aeon's writer, not the rule. Measured across all 38 editor-owned
JSON files in this tree (last byte of each): **15 end in a newline, 23 do not**, and the
split does not follow file kind — `section_4.meta.json` has one, `section_0.meta.json`
does not. Whichever convention you adopt, expect the *other* writer to flip the byte back
on its next save. Do not treat a one-byte diff on this file as a content change.

### A1.3 Top-level schema, derived from the parser

Every key `tools/inject_editor_bg.py` reads from the top level of the document. Line
numbers are that file.

| Key | Type | Required | Default / absent behaviour | Read at |
|---|---|---|---|---|
| `layout` | array of int (nametable words) | **yes** | `data['layout']` — a `KeyError` if absent | `:1047` |
| `tiles` | array of arrays of int | **yes** | `data['tiles']` — a `KeyError` if absent | `:1047` |
| `anims` | array of band objects | no | absent → the injector emits the **disabled stub** (`BgAnim_Table: u16 = 0`), which is a complete, linkable module, not an error | `:1056` |
| `anim` | a single band object | no | legacy single-band spelling; used **only** when `anims` is absent *and* `anim` is truthy, and is then wrapped as `[data['anim']]` | `:1057-1058` |
| `palette` | array of exactly 16 int (CRAM words) | no | absent → `ojz_palette.bin` is left exactly as `ojz_strip_gen.py` copied it | `:1357-1359` |
| `palette_line` | int | no | **`2`**, then masked `& 3` | `:1358` |

**`layout`.** Either **2048** or **4096** words; nothing else. 2048 is the legacy 32-row
shape and is zero-padded to 4096 on read (`:1310`). Anything else is refused — see
§A1.7. The array is **row-major** as the editor writes it (`idx = row * 64 + col`) and
the injector **transposes** it to the column-major order the engine reads
(`blob[col*128 + row*2]`); that transpose is at `:1319-1328` and the engine side of the
contract is the header of `engine/level/bg.emp`. The low 11 bits of each non-zero word
are a **blob-local** tile index and are rebased by `+ BG_TILE_BASE_SLOT` on emission;
the remaining bits (palette line, priority, flips) are carried through untouched, and a
word that is exactly `0` is left as `0` rather than rebased.

**`tiles`.** A list of tiles; each tile is a flat list of **64 integers**, one per pixel,
row-major within the 8×8, and each is masked `& 0xF` when packed — so only the low nibble
of any value survives. Packing is two pixels per byte, high nibble first (`:1346-1350`).
The emitted `bg_tiles.bin` is a **2-byte big-endian byte-length header** followed by the
raw 4bpp body, and the body length is asserted to be a multiple of 4 because the runtime
blit copies it with `move.l`.

The count ceiling is **not** a literal in this tool. It imports it:

```python
from vram_map import GAME as _VRAM_MAP_GAME, BG_TILE_BASE_SLOT, BG_TILE_CAPACITY
```

`tools/vram_map.py` is generated from `games/sonic4/vram.toml`. Read today:

| Constant | Value | Where it comes from |
|---|---|---|
| `BG_TILE_BASE_SLOT` | **1024** (`$400`) | `vram.toml` `[[region]] name = "bg_region"`, `base = 1024` |
| `BG_TILE_CAPACITY` | **400** | same region, `tiles = 400` |
| `BG_BAND_RESERVE` | **80** | same region, `band_reserve = 80` |
| `BG_STATIC_TILE_BUDGET` | **320** | derived: capacity − reserve |

The injector's hard limit is `len(tiles) <= BG_TILE_CAPACITY` = **400**. The *importer's*
limit is stricter: `BG_STATIC_TILE_BUDGET` = **320**, because `band_reserve` withholds 80
tiles for animated-band art inserted at the front of the blob afterwards. **Author to 320,
not 400.**

> The main contract's §10 records that `tools/EFFECTS_CONSUMER_CONTRACT.md` §1.1 states
> this ceiling as 448 and cites the wrong line. That is still true on this tree. The
> mirror says 400. Read the mirror.

**`palette` / `palette_line`.** Present in the parser, **absent from the live file** (see
§A1.7). When `palette` is present the injector stamps 16 CRAM words over
`ojz_palette.bin` *after* `ojz_strip_gen.py` has copied that file, which is the only
ordering in which a stamped palette survives a re-bake. The mapping is
`file_line = palette_line - 1`, because the three lines in `ojz_palette.bin` load starting
at **CRAM line 1**; `palette_line` 0 is therefore refused by an assert. Exactly 16 words
or a refusal.

### A1.4 The `anims` band schema

`anims` is a list of band objects. Each is the description of a tile band that is
re-pointed at a different 32-tile bank as a scalar moves — the HCZ-pillar technique.

| Key | Type | Required | Default | Notes |
|---|---|---|---|---|
| `cols` | int | **yes** | — | band width in tiles |
| `rows` | int | **yes** | — | band height in tiles |
| `phases` | array of exactly **8** banks | **yes** | — | each bank is a list of `cols*rows` tiles, each tile 64 ints as in `tiles` |
| `pattern_px` | int | **yes** | — | the pattern period **along the axis**; asserted equal to the axis-derived period |
| `axis` | `"horizontal"` \| `"vertical"` | no | `"horizontal"` | see the power-of-two rule below |
| `driver` | `"camera_x"` \| `"camera_y"` \| `"timer"` | no | `"camera_x"` | encoded 0/1/2 (`DRIVERS`, `:1055`) |
| `rate_shift` | int | no | **2** | 1 px of pattern travel per `1 << rate_shift` driver units |
| `slot_base` | int | no | the running cursor | must equal the cursor — bands pack contiguously from slot 0 |
| `default_off` | bool | no | `false` | the band's record is still emitted, but it is not counted in the live band-count word, so it does not animate at boot |

Rules a band must satisfy, all enforced in `tools/inject_editor_bg.py`:

* **At most 4 bands** (`BGANIM_MAX_BANDS = 4`, `:70`). Raising it needs three files edited
  together — the tool, `engine/system/constants.emp`, and `engine/level/bg_anim.emp` — so
  treat 4 as fixed.
* **Exactly 8 phases per band.** Asserted twice, once on each bank's length and once on
  the emitted pointer array (`bganim_band.banks` is `[*u8; 8]`).
* **The rotation unit must be a power of two in bytes.** On a **horizontal** band the unit
  is `rows * 32` bytes; on a **vertical** band it is `cols * 32`. The engine shifts by that
  distance with `lsl`, so `rows` (horizontal) or `cols` (vertical) must be a power of two.
  `band_axis_geometry`, `:857-882`.
* **`pattern_px` is the period along the axis** — the band's *width* when horizontal and
  its *height* when vertical — and it must equal `cols*8` (horizontal) or `rows*8`
  (vertical).
* **Phase 0 must BE the static tiles it covers.** `phases[0] == tiles[slot_base :
  slot_base + cols*rows]`, asserted by `validate_band_coherence` (`:999`). Bands DMA over
  the *front* of the static blob; they are a subset of `tiles`, never an addition to it.
  This is the invariant that makes `anims`, `tiles` and `layout` **inseparable** — you
  cannot regenerate two of them and keep the third.
* **Direction is fixed, not authored.** Bank *k* is phase 0 translated *k* px toward
  decreasing coordinate, so an increasing driver scrolls a horizontal band **left** and a
  vertical band **up**. There is no `direction` key; it is booked as deferred work, not
  built (`BAND_AXES` block, `:836-845`).
* **A vertical band whose phases are exact horizontal translations is refused**
  (`validate_band_phase_axis`, `:884`). This guard exists because the reachable accident —
  a vertical band regenerated by a horizontal-only writer — bakes cleanly and ships as a
  shimmer. Composite phases (not pure rolls) are deliberately still legal.
* **ROM section ceiling.** The emitted `ojz_bg_anim` section is capped at
  `BGANIM_SECTION_CEILING` = **20480 bytes**, checked on the *total* across all bands
  before anything is written. The section arithmetic is 2 bytes of count word + 44 bytes
  per band record + the bank blob, plus the DEBUG view twins.

### A1.5 Command-line options

**`tools/png_to_bg_override.py`** — `argparse.ArgumentParser()` at `:194`, five arguments:

| Option | Type | Default | What it does |
|---|---|---|---|
| `image` | positional | — | the PNG to import |
| `--voffset` | int | `0` | vertical offset, in cells, at which the art is placed in the 64×64 plane |
| `--lines` | str | `"2,3"` | candidate CRAM lines for **lock mode**; the help text notes `1=sky` |
| `--pal-line` | int | `2` (`DEFAULT_PAL_LINE`) | the CRAM line stamped in `--new-palette` mode |
| `--new-palette` | flag | off | **extract** a fresh palette and stamp it, instead of quantising to existing lines. The tool's own header calls this *"UNSAFE: recolours shared FG art"* |
| `--out` | path | the live override file | write elsewhere — the escape hatch when the tool refuses to clobber a key it does not author |

Two palette modes, from the file's header:

* **lock (default)** — quantise each 8×8 tile to the nearest **existing** CRAM line among
  the `--lines` candidates. Shared foreground art on those lines is never recoloured.
  Multi-line: different tiles may land on different lines. Nothing is stamped.
* **`--new-palette`** — extract and stamp one palette. Single line. Recolours any
  foreground art sharing that CRAM line.

Hard gates it applies before doing work: the image is 8×8-aligned; its width divides the
512 px plane (`PLANE_W = 64` cells) so there is no seam; unique flip-canonical tiles
≤ `BG_STATIC_TILE_BUDGET`. **BG is opaque** — colour index 0 is excluded.

**`tools/inject_editor_bg.py`** — `parse_args` at `:1374`, two arguments:

| Option | Type | Default | What it does |
|---|---|---|---|
| `--zone` | int | `0` | zone **index** in `project.json` |
| `--act` | int | `0` | act **index** within that zone |

These are **indices, not ids**, deliberately: the docstring records that a free-text id
naming no declared act would resolve to a plausible directory and a missing override file,
i.e. a confusing `FileNotFoundError` instead of *"project.json has no such act"*. Every
act-dependent path — output directory, override file, emitted module name, the `embed(...)`
path — is derived from those two indices by `BgActNames`.

**`tools/ojz_strip_gen.py`** — **no `argparse` at all.** Established positively:
`grep -c argparse tools/ojz_strip_gen.py` prints `0` and exits `1`. It hand-parses
`sys.argv` in `main()` (`:2188`). One required positional mode plus one flag:

| Argument | What it does |
|---|---|
| `preflight` | validate every precondition and **write nothing**. `tools/regenerate-level.sh` runs this before its first destructive step |
| `test` | run the in-file self-tests |
| `generate` | generate the level data files |
| `--stress-uniquify N` | `generate` only. Inflate the act art pool to N distinct tiles via deterministic tile clones with re-pointed block references. A throwaway stress fixture; the tree is restored from git afterwards |

Anything else is a refusal (§A1.6).

### A1.6 Refusals, verbatim

These are quoted exactly as the code emits them, because a paraphrased error is useless
for recognising one. Bracketed `{}` are the runtime values.

**Unowned keys** — `tools/bg_override_io.py::read_existing_override`, the one an outside
tool is most likely to hit, because `png_to_bg_override.py` rewrites the file wholesale
and refuses to destroy content it does not author (`OWNED_KEYS = frozenset(("layout",
"tiles", "palette", "palette_line"))`):

```
ERROR [{tool}]: {path} contains key(s) this tool does not author: {keys}.
  {tool} rewrites this file and WOULD DESTROY them. This is exactly how
  OJZ's two BgAnim bands were lost at dd93a840 (see docs/BUGS.md TOOL-01).
  {tool} authors only: layout, palette, palette_line, tiles.
  These keys are NOT independently mergeable: bands DMA over the front of
  the static tile blob, so regenerating layout/tiles while retaining anims
  would bake cleanly and ship SILENTLY CORRUPT art. Refusing is correct.
  To generate anyway without touching this file, redirect the output
  (--out <path> / BG_OUT=<path>) and merge deliberately by hand.
```

**On the live file this refusal fires**, because the live file carries `anims`. An
importer run against OJZ act 1 today must use `--out` and merge by hand.

Malformed or non-object override, same function:

```
ERROR [{tool}]: {path} is not valid JSON ({e}). Refusing to overwrite it -- it may be hand-authored content or a truncated write. Repair or delete it deliberately, then re-run.
```
```
ERROR [{tool}]: {path} is not a JSON object. Refusing to overwrite it.
```

A **missing** file and an **empty** file are not refusals: both return `{}` and the run
proceeds as a first-ever import.

**Over the tile budget** — `tools/png_to_bg_override.py::check_tile_budget`, the
`band_reserve > 0` arm, which is the one live today:

```
ERROR: {n} unique tiles > 320 static budget.
  bg_region holds 400 tiles, of which band_reserve = 80 are withheld
  for BgAnim band art, leaving 400 - 80 = 320 for this import.
  Simplify the art by {n-320} unique tiles (flatter / more repetitive),
  or lower band_reserve in games/sonic4/vram.toml and regenerate — that is
  the animation-vs-detail trade, and spending it here costs band space.
```

Not 8×8-aligned, and the seam gate, both `sys.exit` in `main()`:

```
ERROR: {w}x{h} not tile-aligned (8x8).
```
```
ERROR: width {w} does not divide the 512px plane -> seam.
```

**Injector refusals.** Wrong layout length, and over the hard VRAM ceiling:

```
layout must be 64x32 or 64x64 words, got {n}
```
```
{n} tiles exceeds BG capacity 400
```

Band coherence — the one that catches `anims` and `tiles` regenerated separately:

```
band {i}: phases[0] != tiles[{base}:{base+n}]. The band's rest state must BE the static tiles it covers. This means anims and tiles came from different generator runs — regenerating layout/tiles while retaining anims produces a clean bake that ships CORRUPT art. Regenerate both together (tools/forest_bg_gen.py).
```

Band packing, and the band ceiling:

```
band {i}: slot_base {base} does not pack contiguously (expected {cursor}); bands must tile the front of the blob from slot 0
```
```
bands must pack contiguously from slot 0
```
```
{n} bands authored but the engine sizes BgAnim_LastStep for at most BGANIM_MAX_BANDS=4. Raising it here is NOT enough: engine/system/constants.emp (which sizes the array) and engine/level/bg_anim.emp (which bounds the runtime assert) hold the same number and must be raised together, or BgAnim_Update walks past the array in the release shape. See BGANIM_MAX_BANDS at the head of this file.
```

Axis and geometry:

```
{where}: axis {axis!r} is not one of 'horizontal' / 'vertical'. The axis names which way the band's pattern translates; it is NOT the `driver`, which names the scalar the step is read from and never an axis.
```
```
{where}: a {axis} band rotates by whole {columns|rows} of {rows|cols}*32 = {n} B, and BgAnim_Update shifts by that distance with `lsl`, so it must be a power of two — {key}={n} is not. (The power-of-two key is `rows` on a horizontal band and `cols` on a vertical one; this band is {axis}.)
```
```
band {i}: a {axis} band's pattern period is {cols|rows}*8 = {n} px, but `pattern_px` says {m}. (`pattern_px` is the period ALONG THE AXIS — it is the band's width when horizontal and its HEIGHT when vertical.)
```

Palette:

```
palette must be 16 CRAM words, got {n}
```
```
BG palette maps to CRAM line >=1
```

**`ojz_strip_gen.py` refusals.** Bad command line:

```
Usage: tools/ojz_strip_gen.py preflight | test | generate [--stress-uniquify N]
```
```
ERROR: --stress-uniquify needs an integer N
```
```
ERROR: --stress-uniquify N must be an integer, got {value!r}
```
```
ERROR: unknown argument {arg!r}
```

Missing donors — these are the ones an outsider will hit, because the donors live
**outside this repository**:

```
ojz_strip_gen: sonic_hack donor not found at {path}. This is a MANUAL re-bake (tools/regenerate-level.sh); set AEON_SONIC_HACK_DIR. The build does NOT run this — it uses the committed level tree under games/sonic4/data/generated/.
```
```
ojz_strip_gen preflight: skdisasm donor not found at {path}. import_sk_collision.py needs it for the 252-shape collision vocabulary; set AEON_SKDISASM_DIR. Stopping BEFORE anything is written — the tables under games/sonic4/data/collision/ are INTERNED build inputs, and a partial re-bake replaces them with the base S&K bank while the strips keep interned indices, so every solid surface resolves to the wrong height, angle and solidity class.
```
```
ojz_strip_gen: editor data unusable — {why}. Refusing the silent legacy-air fallback: a re-bake without real editor data emits a ~131 KB wrong level tree. Nothing has been written.
```

### A1.7 The invocation the build actually uses

**Neither script is invoked by `build.sh`.** Established positively: `grep -n
"inject_editor_bg\|ojz_strip_gen" build.sh` with comment lines filtered exits `1` — every
mention in `build.sh` is a comment. The build consumes the **committed** tree under
`games/sonic4/data/generated/` directly, and fails if that tree is stale.

Both scripts are invoked by `tools/regenerate-level.sh`. Quoted from it verbatim:

```sh
echo "Preflight: checking donors + editor data before anything is written..."
python3 "${TOOLS}/ojz_strip_gen.py" preflight
```

```sh
if [[ -n "${STRESS_UNIQUIFY:-}" ]]; then
    echo "Generating OJZ section data (STRESS uniquify N=${STRESS_UNIQUIFY})..."
    python3 "${TOOLS}/ojz_strip_gen.py" generate --stress-uniquify "${STRESS_UNIQUIFY}"
else
    echo "Generating OJZ section data..."
    python3 "${TOOLS}/ojz_strip_gen.py" generate
fi
```

```sh
# Editor-authored BG override (level editor art) — replaces the generated
# zone BG when games/sonic4/data/editor_bg_override.json exists.
if [[ -f games/sonic4/data/editor_bg_override.json ]]; then
    python3 "${TOOLS}/inject_editor_bg.py"
fi
```

So the injector runs with **no arguments** on every real re-bake — zone 0, act 0 — and
only when the override file exists. `regenerate-level.sh` is `set -euo pipefail`, and the
`preflight` call is deliberately first because it writes nothing: an earlier ordering
destroyed the collision tables before discovering a missing donor.

`build.sh` reaches `regenerate-level.sh` in exactly two places, both with `${TOOLS}`:

```sh
"${TOOLS}/regenerate-level.sh" > "${REBAKE_LOG}" 2>&1
```
(the `FAST=1` path, which re-bakes automatically when the level tree is stale)

```sh
STRESS_UNIQUIFY="${STRESS_ART_N:-2600}" "${TOOLS}/regenerate-level.sh"
```
(the `STRESS_ART` path, a throwaway re-bake whose tree is restored from git afterwards)

On the canonical (non-`FAST`) path a stale tree is a **hard failure** naming
`tools/regenerate-level.sh`, not an automatic re-bake.

### A1.8 Keys present in the file but ignored, and keys read but absent

Checked programmatically against the live file rather than by eye.

**Nothing in the live file is ignored.** Top-level keys on disk are exactly `anims`,
`layout`, `tiles`; per-band keys are exactly `cols`, `default_off`, `driver`,
`pattern_px`, `phases`, `rate_shift`, `rows`. Every one is read.

The mismatch runs the other way — **keys the parser reads that the live file does not
carry**:

* top level: `anim` (the legacy single-band spelling, superseded by `anims`), `palette`,
  `palette_line`. So **no palette is stamped from the override today**; `ojz_palette.bin`
  is whatever `ojz_strip_gen.py` copied.
* per band: `axis` (defaults to `"horizontal"`) and `slot_base` (defaults to the running
  cursor, which is `0` for the single band).

One thing an outsider *will* copy that is worth naming: the `bgLayoutRef` key in
`games/sonic4/data/editor/ojz/act1/section_0.meta.json`, which today reads
`"ingame-forest-v15-1786630615596"` and looks like a per-section background binding. **No
aeon build tool reads it.** See §A3.
