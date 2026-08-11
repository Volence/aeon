# Dust Effect Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the player visible dust — the puff cycling behind a spindash charge and the puffs kicked up by a skid — as two objects on the existing Effect pool.

**Architecture:** Two Effect-pool objects. `Dust_Spindash` is a follower created by `PHook_SpindashEnter` that re-reads the player each frame and self-retires when `player_state` leaves `PSTATE_SPINDASH`; it streams its 12-tile frame via `Perform_DPLC_Deferrable`. `Dust_Puff` is fire-and-forget with all four frames permanently VRAM-resident (zero DMA), spawned on a 4-frame cadence by `Dust_Tick` and self-deleting via `AF_DELETE` at 16 frames. S3K's invisible routine-6 emitter object is deliberately NOT ported — it exists only to pump DPLC for the puff frames, which residency makes unnecessary.

**Tech Stack:** 68000 assembly in sigil `.emp`; Python 3 + pytest for the asset importer; `tools/asl`-free sigil build (`./build.sh`); Oracle emulator via MCP for visual verification.

**Spec:** `docs/superpowers/specs/2026-08-11-dust-effect-design.md` (commits `dfb6c5b0`, `48009189`). Read §2 (architecture), §4 (VRAM, including §4.0 on why NOT the BG region) and §5.3 (the measured palette permutation) before starting.

**Branch:** work on `feat/character-dispatch` (the design consumes `CharacterDef.cd_stand_wh`, which exists only on that line). **Verify `git branch --show-current` before every commit** — parallel sessions share this tree.

---

## Orientation: things that will bite you

Read these five before Task 1. Each cost real debugging time previously.

1. **This is a byte-changing parcel.** Tasks 2-5 move ROM bytes, so each owes the ritual: build with `SIGIL_BLOB_LEN_DRIFT=warn`, rebuild **both** sigil release binaries after any sigil edit, then repin → refreeze. A new `.emp` module needs a `map.toml` `order` entry **plus** a sigil `ModuleSpec` with a **REAL PIN** (never `DUMMY_REGION` — it collapses the section onto base 0 where it collides with `vectors`), landed in the same change as the file.

2. **Importer tests must write to `tmp_path`, never the repo.** `tools/test_import_sk_collision.py:14-22` documents why: a test that defaulted its output into the tree silently reverted a committed bake, turned ~10 sigil port targets red, and looked like a stray background process rewriting the repo. Fixed on 2026-08-11 (`4c784e35`). Do not regress it.

3. **An auto-commit daemon** watches `ojz_strip_gen.py` and `data/editor/ojz` and commits to the *current* branch about every 60 s. Never `--amend` on this branch. Task 2 touches `ojz_strip_gen.py`, so expect the daemon may commit it out from under you — check `git log` before assuming your staging is intact.

4. **Environment.** Both are required; `build.sh` hard-errors without them.
```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
```

5. **The Effect sweep runs AFTER the Player sweep** (`tails_appendage.emp:200-203`). Every player field a dust object reads is therefore that frame's final value — position after physics, `anim` after `Player_Animate`, `status` after the state hooks. This is why the follower needs no ordering tricks.

---

## File Structure

**Create:**

| Path | Responsibility |
|---|---|
| `games/sonic4/data/dust_staging/gen_dust.py` | Deterministic S3K dust asset importer: art re-index, mappings, DPLC |
| `games/sonic4/data/dust_staging/README.md` | Provenance + the measured palette facts |
| `tools/test_gen_dust.py` | Importer tests (structural + palette + determinism) |
| `games/sonic4/data/generated/dust/art_dust.bin` | 88 tiles, re-indexed (generated) |
| `games/sonic4/data/generated/dust/dplc_dust.bin` | 7 charge frames (generated) |
| `games/sonic4/data/generated/dust/map_dust_spindash.bin` | 7 charge frames (generated) |
| `games/sonic4/data/generated/dust/map_dust_puff.bin` | 4 puff frames (generated) |
| `games/sonic4/data/dust_data.emp` | `Art_Dust` / `DPLC_Dust` / `Map_DustSpindash` / `Map_DustPuff` blobs |
| `games/sonic4/data/animations/dust_anims.emp` | `Ani_DustSpindash`, `Ani_DustPuff` |
| `games/sonic4/objects/dust_puff.emp` | The fire-and-forget puff object |
| `games/sonic4/objects/dust_spindash.emp` | The charge-dust follower + `Dust_Tick` |

**Modify:**

| Path | Change |
|---|---|
| `engine/system/constants.emp:580` | `POOL_TILE_CEILING` 960 -> 896 |
| `tools/ojz_strip_gen.py:124` | `POOL_TILE_CEILING` 960 -> 896 (indivisible with the line above) |
| `games/sonic4/config/constants.emp` | `VRAM_DUST_PUFF`, `VRAM_DUST_SPINDASH` + walls |
| `games/sonic4/config/ram.emp:37-48` | append `dust_timer: u8` to `PlayerBlock` |
| `games/sonic4/player/player_common.emp` | `PBLK_DUSTTIMER` const + `ensure`; `Dust_Tick` call in `Player_Display`; spawn in `PHook_SpindashEnter` |
| `games/sonic4/test/ojz_scroll_test.emp` | resident puff-art DMA at level init |
| `games/sonic4/map.toml` | `order` entries for the four new sections |
| `sigil crates/sigil-harness/repin.toml` | `[[region]]` per new section |
| `sigil crates/sigil-harness/src/native.rs` | `m!()` ModuleSpec per new module |

**Why `gen_dust.py` duplicates ~60 lines of S3K-to-S4 conversion instead of sharing with `gen_characters.py`:** the shared-helper hoist would edit `games/sonic4/data/characters_staging/gen_characters.py`, which is load-bearing for Tails art on this branch and Knuckles art on `wip/knuckles-task9`. Coupling a dust parcel to a generator in flight on two branches is the worse trade. The hoist into a shared `tools/s3k_sprites.py` is ledgered as a rider (Task 6).

---

## Data formats (authoritative — do not guess)

**Art:** raw 4bpp tiles, 32 B each, two pixels per byte, high nibble first.

**Mappings** (`tools/convert_s2_mappings.py:96-148`): a `u16` offset per frame at the head (frame count = `offsets[0] / 2`), then per frame:
```
+0  i8 x_min, i8 x_max, i8 y_min, i8 y_max   ; flip-invariant, signed
+4  u16 piece_count
+6  pieces, 8 B each: u16 y_off, u8 size_code, u8 pad(0), u16 tile_attrs, u16 x_off
```
`size_code` bits 3-2 = width-1 in tiles, bits 1-0 = height-1. `x_max`/`y_max` are far edges. Extents are symmetrized (`x_min = min(x_min, -x_max)`, etc.) so the unflipped bbox test is correct under any flip. Hard-fail if any extent leaves `[-128, 127]`.

**DPLC** (`engine/objects/dplc.emp:4-8`): a `u16` offset per frame at the head, then per frame `u16 entry_count` followed by that many `u16` entries; entry = `(tile_count-1) << 12 | tile_start`. A zero `entry_count` is legal and means zero DMA (`dplc.emp:91-93`).

**S3K source pieces are 6 bytes** (`Y.b, size.b, tile.w, X.w`), not S2's 8 — see `gen_characters.py`'s `S3K_MAP_PIECE = 6`.

**The blob layout we emit.** One `Art_Dust` of 88 tiles = donor tiles `$062..$0B9` in order:

| Blob tiles | Donor tiles | Use |
|---|---|---|
| 0-71 | `$062`-`$0A9` | charge frames `$0A`-`$10`, streamed by DPLC |
| 72-87 | `$0AA`-`$0B9` | the puff block, DMA'd resident once |

Charge DPLC `tile_start` values are the donor values minus `$62`. No entry exceeds 16 tiles (max is 12), so no splitting is needed.

---

## Task 1: Dust asset importer

Pure tooling. Emits generated data that nothing references yet, so **this task changes zero ROM bytes** and owes no sigil ritual.

**Files:**
- Create: `games/sonic4/data/dust_staging/gen_dust.py`
- Create: `games/sonic4/data/dust_staging/README.md`
- Test: `tools/test_gen_dust.py`

- [ ] **Step 1: Write the failing test**

Create `tools/test_gen_dust.py`:

```python
import os, subprocess, sys, struct

HERE = os.path.dirname(__file__)
GEN = os.path.join(HERE, "..", "games", "sonic4", "data", "dust_staging", "gen_dust.py")
_SK_ROOT = os.environ.get(
    "AEON_SKDISASM_DIR",
    os.path.normpath(os.path.join(HERE, "..", "..", "skdisasm")))

# NOTE: every test here writes to tmp_path. NEVER default the importer's output
# into the repo — see tools/test_import_sk_collision.py:14 for the incident that
# rule comes from (a test silently reverted a committed bake and turned ~10
# sigil port targets red).


def run(out_dir):
    subprocess.run([sys.executable, GEN, "--out", str(out_dir),
                    "--skdisasm", _SK_ROOT], check=True)


def _tiles(path):
    return os.path.getsize(path) // 32


def test_art_is_88_tiles(tmp_path):
    run(tmp_path)
    assert _tiles(os.path.join(tmp_path, "art_dust.bin")) == 88


def test_art_uses_only_remapped_indices(tmp_path):
    """S3K indices 1/12/13 must become 6/4/7; nothing else may appear."""
    run(tmp_path)
    data = open(os.path.join(tmp_path, "art_dust.bin"), "rb").read()
    seen = set()
    for b in data:
        seen.add(b >> 4)
        seen.add(b & 0xF)
    assert seen <= {0, 6, 4, 7}, f"unexpected palette indices: {sorted(seen)}"
    # and the three non-transparent ones must all be present
    assert {6, 4, 7} <= seen


def test_charge_dplc_frames_and_peak(tmp_path):
    run(tmp_path)
    d = open(os.path.join(tmp_path, "dplc_dust.bin"), "rb").read()
    n_frames = struct.unpack_from(">H", d, 0)[0] // 2
    assert n_frames == 7
    counts = []
    for f in range(n_frames):
        off = struct.unpack_from(">H", d, f * 2)[0]
        n_entries = struct.unpack_from(">H", d, off)[0]
        total = 0
        for e in range(n_entries):
            word = struct.unpack_from(">H", d, off + 2 + e * 2)[0]
            tile_count = ((word >> 12) & 0xF) + 1
            assert tile_count <= 16
            assert (word & 0x0FFF) + tile_count <= 72, "charge DPLC ran past its 72 tiles"
            total += tile_count
        counts.append(total)
    assert counts == [8, 8, 8, 12, 12, 12, 12]
    assert max(counts) == 12, "charge DPLC peak must fit the 12-tile window"


def test_puff_mappings_are_four_2x2_frames(tmp_path):
    run(tmp_path)
    d = open(os.path.join(tmp_path, "map_dust_puff.bin"), "rb").read()
    assert struct.unpack_from(">H", d, 0)[0] // 2 == 4
    for f in range(4):
        off = struct.unpack_from(">H", d, f * 2)[0]
        assert struct.unpack_from(">H", d, off + 4)[0] == 1, "puff frame must be one piece"
        size = d[off + 6 + 2]
        assert size == 0b0101, "puff piece must be 2x2 tiles"
        tile = struct.unpack_from(">H", d, off + 6 + 4)[0] & 0x07FF
        assert tile == f * 4, f"puff frame {f} must address tile {f * 4}"


def test_spindash_mappings_are_seven_frames(tmp_path):
    run(tmp_path)
    d = open(os.path.join(tmp_path, "map_dust_spindash.bin"), "rb").read()
    assert struct.unpack_from(">H", d, 0)[0] // 2 == 7


def test_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    run(a); run(b)
    for name in ("art_dust.bin", "dplc_dust.bin",
                 "map_dust_spindash.bin", "map_dust_puff.bin"):
        assert open(a / name, "rb").read() == open(b / name, "rb").read(), name
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python3 -m pytest tools/test_gen_dust.py -q
```
Expected: every test ERRORs — `gen_dust.py` does not exist, so `subprocess.run` raises `FileNotFoundError`.

- [ ] **Step 3: Write the importer**

Create `games/sonic4/data/dust_staging/gen_dust.py`:

```python
#!/usr/bin/env python3
"""Deterministic S3K dust (Obj_DashDust) asset extractor for Aeon.

Ships two of the donor's four frame groups — the spindash charge dust (mapping
frames $0A-$10) and the 16-tile skid/slide puff block (loaded by frame $15).
The splash/drown set ($16-$1D) indexes a DIFFERENT art base and is out of scope
(no water system — see the design spec §1).

THE ART IS RE-INDEXED, NOT COPIED. The dust draws on CRAM line 0, the character
palette. Measured over the 88 shipped tiles, the art touches only palette
indices 0, 1, 12 and 13, and under Aeon's art/palettes/SonicAndTails.bin all
three non-transparent ones are WRONG (index 1 is $0EEE white in S3K but $0222
near-black here; 12 is $0ECC vs $000E red; 13 is $0CAA vs $0008 dark red). The
colour-lossless permutation is 1->6, 12->4, 13->7, a strict subset of the remap
table already pinned for Tails. See README.md.

Deterministic: no timestamps, no RNG. Running twice is byte-identical.

Usage:
  ./gen_dust.py --out <dir> [--skdisasm /home/volence/sonic_hacks/skdisasm]
"""

import argparse
import re
import struct
from pathlib import Path

TILE_SIZE = 32
ART_FIRST, ART_LAST = 0x062, 0x0B9          # donor tile span we ship (inclusive)
CHARGE_FRAMES = range(0x0A, 0x11)           # $0A..$10, the charge cycle
PUFF_FRAMES = range(0x11, 0x15)             # $11..$14, the puff cycle
PUFF_LOADER_FRAME = 0x15                    # the frame whose DPLC loads the puff block
S3K_MAP_PIECE = 6                           # S3K 1P piece: Y.b size.b tile.w X.w

# The measured colour-lossless permutation into Aeon's SonicAndTails line 0.
# Identity for every index the art does not touch.
REMAP = {1: 6, 12: 4, 13: 7}
ART_ALLOWED_SRC = {0, 1, 12, 13}


def parse_asm_words(path):
    """Return the flat list of dc.w words in an S3K mapping/DPLC .asm file.

    Handles `dc.w $XXXX, $YYYY`, label lines, and comments. Byte directives are
    rejected loudly: these two donor files are word-only, and a silent skip
    would shift every subsequent offset.
    """
    words = []
    for raw in Path(path).read_text().splitlines():
        line = raw.split(';')[0].strip()
        if not line:
            continue
        m = re.match(r'^(?:\S+:\s*)?dc\.(\w)\s+(.*)$', line)
        if not m:
            continue
        if m.group(1) != 'w':
            raise ValueError(f"{path}: unexpected dc.{m.group(1)} — parser assumes word-only")
        for tok in m.group(2).split(','):
            tok = tok.strip()
            if tok.startswith('$'):
                words.append(int(tok[1:], 16))
            else:
                raise ValueError(f"{path}: non-hex word {tok!r}")
    return words


def split_frames(words):
    """Split a donor word list into per-frame word lists via its offset table.

    The head is one word per frame (byte offset from file start); frame count is
    offsets[0] / 2. Returns a list of (byte_offset, words_from_there).
    """
    n_frames = words[0] // 2
    offsets = words[:n_frames]
    out = []
    for i, off in enumerate(offsets):
        end = min((o for o in offsets if o > off), default=len(words) * 2)
        out.append((off, words[off // 2: end // 2]))
    return out


def build_dplc(donor_words):
    """Rebase the charge frames' DPLC into our 88-tile blob.

    Donor entry = (count-1) << 12 | tile_start, absolute into Dash Dust.bin.
    Ours is the same encoding with tile_start - ART_FIRST.
    """
    frames = split_frames(donor_words)
    bodies = []
    for fi in CHARGE_FRAMES:
        _, fw = frames[fi]
        n_entries = fw[0]
        entries = []
        for e in range(n_entries):
            word = fw[1 + e]
            count = ((word >> 12) & 0xF) + 1
            start = word & 0x0FFF
            if not (ART_FIRST <= start and start + count - 1 <= ART_LAST):
                raise ValueError(f"frame ${fi:02X} entry {e} leaves the shipped span")
            entries.append(((count - 1) << 12) | (start - ART_FIRST))
        bodies.append(entries)

    header = 2 * len(bodies)
    out = bytearray()
    cursor = header
    for entries in bodies:
        out += struct.pack('>H', cursor)
        cursor += 2 + 2 * len(entries)
    for entries in bodies:
        out += struct.pack('>H', len(entries))
        for e in entries:
            out += struct.pack('>H', e)
    return bytes(out)


def _cell_px(size_byte):
    return (((size_byte >> 2) & 3) + 1) * 8, ((size_byte & 3) + 1) * 8


def build_mappings(donor_words, frame_ids, tile_rebase):
    """Convert donor frames to the S4 VDP-order mapping format.

    tile_rebase(donor_tile) -> our tile index, relative to the frame's art_tile
    base. Bboxes are flip-invariant (symmetrized), matching
    tools/convert_s2_mappings.py.
    """
    frames = split_frames(donor_words)
    bodies = []
    for fi in frame_ids:
        _, fw = frames[fi]
        n_pieces = fw[0]
        raw = bytearray()
        for w in fw[1:]:
            raw += struct.pack('>H', w)
        pieces = []
        for p in range(n_pieces):
            base = p * S3K_MAP_PIECE
            y = struct.unpack_from('>b', raw, base)[0]
            size = raw[base + 1]
            tile_attrs = struct.unpack_from('>H', raw, base + 2)[0]
            x = struct.unpack_from('>h', raw, base + 4)[0]
            tile = tile_rebase(tile_attrs & 0x07FF)
            pieces.append((y, size, (tile_attrs & 0xF800) | tile, x))

        x_min = min(p[3] for p in pieces)
        x_max = max(p[3] + _cell_px(p[1])[0] for p in pieces)
        y_min = min(p[0] for p in pieces)
        y_max = max(p[0] + _cell_px(p[1])[1] for p in pieces)
        x_min, x_max = min(x_min, -x_max), max(x_max, -x_min)
        y_min, y_max = min(y_min, -y_max), max(y_max, -y_min)
        for v in (x_min, x_max, y_min, y_max):
            if not (-128 <= v <= 127):
                raise ValueError(f"frame ${fi:02X}: bbox extent {v} leaves signed byte range")

        body = struct.pack('>bbbb', x_min, x_max, y_min, y_max)
        body += struct.pack('>H', len(pieces))
        for (y, size, attrs, x) in pieces:
            body += struct.pack('>hBBHh', y, size, 0, attrs, x)
        bodies.append(body)

    header = 2 * len(bodies)
    out = bytearray()
    cursor = header
    for b in bodies:
        out += struct.pack('>H', cursor)
        cursor += len(b)
    for b in bodies:
        out += b
    return bytes(out)


def remap_art(raw):
    """Apply the palette permutation to every nibble, asserting the source set."""
    out = bytearray(len(raw))
    for i, b in enumerate(raw):
        hi, lo = b >> 4, b & 0xF
        for nib in (hi, lo):
            if nib not in ART_ALLOWED_SRC:
                raise ValueError(
                    f"byte {i}: source index {nib} outside the measured set "
                    f"{sorted(ART_ALLOWED_SRC)} — the donor art changed, re-measure")
        out[i] = (REMAP.get(hi, hi) << 4) | REMAP.get(lo, lo)
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--skdisasm', default='/home/volence/sonic_hacks/skdisasm')
    args = ap.parse_args()

    src = Path(args.skdisasm) / 'General' / 'Sprites' / 'Dash Dust'
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    art = (src / 'Dash Dust.bin').read_bytes()
    expect = 186 * TILE_SIZE
    if len(art) != expect:
        raise ValueError(f"Dash Dust.bin is {len(art)} B, expected {expect}")

    shipped = art[ART_FIRST * TILE_SIZE:(ART_LAST + 1) * TILE_SIZE]
    (out / 'art_dust.bin').write_bytes(remap_art(shipped))

    dplc_words = parse_asm_words(src / 'DPLC - Dash Dust.asm')
    (out / 'dplc_dust.bin').write_bytes(build_dplc(dplc_words))

    # Sanity-check the puff loader frame really loads the 16 tiles we ship.
    loader = split_frames(dplc_words)[PUFF_LOADER_FRAME][1]
    if loader[0] != 1:
        raise ValueError(f"frame ${PUFF_LOADER_FRAME:02X} has {loader[0]} DPLC entries, expected 1")
    lw = loader[1]
    if (((lw >> 12) & 0xF) + 1, lw & 0x0FFF) != (16, ART_LAST - 15):
        raise ValueError(f"frame ${PUFF_LOADER_FRAME:02X} entry ${lw:04X} is not the 16-tile puff block")

    map_words = parse_asm_words(src / 'Map - Dash Dust.asm')
    # Charge frames each load at window+0, so their pieces address 0..count-1
    # already; rebase is identity. Puff pieces address 0/4/8/$C of their own
    # resident window, also identity. Both are asserted by the tests.
    (out / 'map_dust_spindash.bin').write_bytes(
        build_mappings(map_words, CHARGE_FRAMES, lambda t: t))
    (out / 'map_dust_puff.bin').write_bytes(
        build_mappings(map_words, PUFF_FRAMES, lambda t: t))


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python3 -m pytest tools/test_gen_dust.py -q
```
Expected: `6 passed`.

If `test_puff_mappings_are_four_2x2_frames` fails on the tile assertion, the donor's puff pieces are not window-relative after all — read the four frames' raw tile words and make `tile_rebase` subtract the frame's own base. Do **not** weaken the assertion.

- [ ] **Step 5: Generate the committed data**

```bash
python3 games/sonic4/data/dust_staging/gen_dust.py \
  --out games/sonic4/data/generated/dust
ls -l games/sonic4/data/generated/dust/
```
Expected: `art_dust.bin` 2816 B, plus three small tables.

- [ ] **Step 6: Write the provenance README**

Create `games/sonic4/data/dust_staging/README.md` recording: donor path and byte size (`Dash Dust.bin`, 5952 B = 186 tiles); the shipped span `$062`-`$0B9`; that frames `$16`-`$1D` are the splash set on a different art base and are out of scope; the measured index usage (0/1/12/13 only, with pixel counts 4286/1244/81/21); the permutation `1->6, 12->4, 13->7` and that it is a subset of the pinned Tails table; and that Knuckles needs a **second, raw** variant because `knuckles_main.bin` is byte-identical to S3K's palette and no single variant can serve both lines (the three colours sit at disjoint indices; the lines agree only at 0/10/11, none of them a colour the dust uses).

- [ ] **Step 7: Commit**

```bash
git branch --show-current   # must be feat/character-dispatch
git add games/sonic4/data/dust_staging/gen_dust.py \
        games/sonic4/data/dust_staging/README.md \
        tools/test_gen_dust.py \
        games/sonic4/data/generated/dust/art_dust.bin \
        games/sonic4/data/generated/dust/dplc_dust.bin \
        games/sonic4/data/generated/dust/map_dust_spindash.bin \
        games/sonic4/data/generated/dust/map_dust_puff.bin
git commit -m "feat(tools): S3K dust asset importer — 88 tiles, palette re-indexed

Ships charge frames \$0A-\$10 (72 tiles) + the 16-tile puff block as one blob.
The art is re-indexed 1->6, 12->4, 13->7: measured, the dust touches only
palette indices 0/1/12/13, and under our SonicAndTails line 0 all 1346
non-transparent pixels would otherwise render near-black with red highlights.
Nothing references this data yet — zero ROM delta."
git show --stat HEAD
```

---

## Task 2: FG art pool ceiling + dust VRAM symbols

Byte-changing. The engine constant and the generator constant are **one indivisible step** — the engine at 896 while `ojz_strip_gen.py` still says 960 is a quiet mismatch, not a loud one.

**Files:**
- Modify: `engine/system/constants.emp:580`
- Modify: `tools/ojz_strip_gen.py:124`
- Modify: `games/sonic4/config/constants.emp` (after the `VRAM_TAILS_APPENDAGE` block)

- [ ] **Step 1: Lower the pool ceiling in the engine**

In `engine/system/constants.emp`, change line 580 from `pub const POOL_TILE_CEILING = 960` to:

```
// 896 = 14 pages of 64, NOT 960 (15). The top page was surrendered to the dust
// windows below the character region (games/sonic4/config/constants.emp:
// VRAM_DUST_PUFF / VRAM_DUST_SPINDASH). The carve is page-quantised because
// PAGE_FRAMES*ART_POOL_PAGE_TILES == POOL_TILE_CEILING is enforced below, so 28
// tiles of dust cost a whole 64-tile page and leave 36 spare at 924-959.
// Affordable because the pool is over-provisioned: OJZ act 1 needs 10 pages
// (612 tiles) of the remaining 14, so it stays fully resident
// (PageIn_Fully_Resident still latches). An act wanting >896 resident FG tiles
// streams per §9.7 rather than failing. LOCKSTEP: tools/ojz_strip_gen.py
// carries the same constant and must move with it.
pub const POOL_TILE_CEILING = 896       // pool loads to tiles 0..N-1; dust at 896, DPLC region at 960
```

`PAGE_FRAMES` derives to 14 and the existing `ensure` at line 253 still holds (14 x 64 = 896).

- [ ] **Step 2: Lower it in the generator, same step**

In `tools/ojz_strip_gen.py`, change line 124 to `POOL_TILE_CEILING = 896` and extend the line 123 comment to read:

```python
# POOL_TILE_CEILING in engine/system/constants.emp — keep in sync. 896 (14 pages
# of 64), lowered from 960 when the dust windows took the top page.
```

- [ ] **Step 3: Add the dust VRAM symbols**

Append to `games/sonic4/config/constants.emp` after the `VRAM_TAILS_APPENDAGE` `ensure` block:

```
// -----------------------------------------------
// Dust windows — tiles 896-923, the top page surrendered by POOL_TILE_CEILING
// (960 -> 896). See docs/superpowers/specs/2026-08-11-dust-effect-design.md §4,
// including §4.0 on why these are NOT carved from the BG region (its blob is
// exactly 448 tiles — the cap is spent to the byte, so lowering it would make
// BG_Init's clamp silently truncate the background art).
// -----------------------------------------------
// The four puff frames, RESIDENT for the whole act: concurrent puffs are always
// on DIFFERENT animation frames (spawn cadence 4, frame hold 4), so every frame
// must be in VRAM simultaneously — and they are addressed as tile offsets
// 0/4/8/$C from this one base, so the block must be contiguous. 16 is a floor.
// Loaded once at level init; this object NEVER streams.
pub const VRAM_DUST_PUFF          : VramTile = POOL_TILE_CEILING
// The charge dust's DPLC target. Deliberately NOT shared with the puff block
// (S3K shares one 16-tile window and has a visible artifact: charge frames write
// window tiles 0-11, live puffs address 0-15, and the two overlap for ~10 frames
// on a skid-to-stop-then-charge, which is an ordinary input).
pub const VRAM_DUST_SPINDASH      : VramTile = VRAM_DUST_PUFF + 16
const DUST_PUFF_TILES  = 16
const DUST_SPINDASH_TILES = 12
ensure(VRAM_DUST_PUFF >= POOL_TILE_CEILING,
       "VRAM_DUST_PUFF overlaps the FG art pool")
ensure(VRAM_DUST_SPINDASH == VRAM_DUST_PUFF + DUST_PUFF_TILES,
       "the dust windows must abut — the puff block is exactly 16 tiles")
ensure(VRAM_DUST_SPINDASH + DUST_SPINDASH_TILES <= VRAM_TEST_SONIC,
       "the dust windows run into the character DPLC window at VRAM_TEST_SONIC")
```

- [ ] **Step 4: Build both shapes**

```bash
SIGIL_BLOB_LEN_DRIFT=warn ./build.sh
SIGIL_BLOB_LEN_DRIFT=warn DEBUG=1 ./build.sh
```
Expected: both succeed, no blob-length warning. A failure naming `PAGE_FRAMES` means the ceiling is not a multiple of 64.

- [ ] **Step 5: Confirm the act still fits fully resident**

```bash
grep -n "= 10\|= 612" games/sonic4/data/generated/ojz/act1/ojz_act_pool_manifest.emp
```
Expected: 10 pages / 612 tiles, i.e. `<= 14` frames, so `PageIn_Fully_Resident` still latches. If the generator was re-run and now reports more than 14 pages, stop — the act no longer fits and the VRAM decision needs revisiting.

- [ ] **Step 6: Run the replay regression gate**

Follow the gate in the 2026-08-11 handoff §2: set the breakpoint on `GameState_OJZScroll_Init` **before** `reset`, reset, `wait_for_break`, write `Input_Source = INPUT_PLAYBACK` at `0xFF803A` and the fixture address at `0xFF8040`, clear breakpoints, resume, wait ~40 s. **Re-derive the fixture address from `s4.debug.lst` for this build — it moves — and mask `.lst` addresses to 24 bits** or oracle rejects them.

Expected: PASS = `Replay_Done` (`$FF803C`) == `$FF`, no fault screen. A failure here means the pool change perturbed player-visible behaviour, which it must not.

- [ ] **Step 7: Complete the ritual and commit**

Rebuild both sigil release binaries, then repin and refreeze:
```bash
cd /home/volence/sonic_hacks/sigil && cargo build --release
cargo run -q -p sigil-harness --bin repin
cargo run -q -p sigil-harness --bin refreeze -- --check
```
Then commit in aeon:
```bash
cd /home/volence/sonic_hacks/aeon
git branch --show-current
git add engine/system/constants.emp tools/ojz_strip_gen.py games/sonic4/config/constants.emp
git commit -m "feat(vram): surrender the top FG pool page to the dust windows

POOL_TILE_CEILING 960->896 (PAGE_FRAMES 15->14, the page-tiling ensure still
holds), VRAM_DUST_PUFF at 896 (16 resident) and VRAM_DUST_SPINDASH at 912 (12,
DPLC), 36 tiles spare at 924-959, character window at 960 untouched.

Costs nothing measurable: OJZ act 1 needs 10 of the remaining 14 pages, so it
stays fully resident. NOT taken from the BG region — its blob is exactly 448
tiles, so lowering that cap would make BG_Init's clamp truncate the art.

tools/ojz_strip_gen.py moves in the SAME commit: engine at 896 with the
generator at 960 is a silent mismatch."
```
Note the auto-commit daemon may have already committed `ojz_strip_gen.py`; check `git log --oneline -3` and, if so, commit the remaining two files and reference the daemon commit in the message rather than amending.

---

## Task 3: Dust data modules + resident puff art

Byte-changing. After this task the puff art is in VRAM and inspectable, with no object drawing it yet.

**Files:**
- Create: `games/sonic4/data/dust_data.emp`
- Create: `games/sonic4/data/animations/dust_anims.emp`
- Modify: `games/sonic4/test/ojz_scroll_test.emp` (the art load, near the `TestArt` DMA at ~line 127)
- Modify: `games/sonic4/map.toml`
- Modify: `sigil crates/sigil-harness/repin.toml`, `sigil crates/sigil-harness/src/native.rs`

- [ ] **Step 1: Create the data module**

Create `games/sonic4/data/dust_data.emp`:

```
// Dust sprite data — S3K Obj_DashDust's charge cycle + skid/slide puff block.
//
// ONE art blob, two consumers with different loading strategies:
//   tiles  0-71  charge frames, STREAMED by DPLC_Dust into VRAM_DUST_SPINDASH
//   tiles 72-87  the puff block, DMA'd RESIDENT once into VRAM_DUST_PUFF
// The split is a byte offset into this blob, asserted below.
//
// Generated by games/sonic4/data/dust_staging/gen_dust.py (deterministic; see
// its README for donor provenance and the palette re-index). Do not hand-edit.
module games.sonic4.dust_data in dust_data

pub data Map_DustSpindash = embed("games/sonic4/data/generated/dust/map_dust_spindash.bin")
pub data Map_DustPuff     = embed("games/sonic4/data/generated/dust/map_dust_puff.bin")
pub data DPLC_Dust        = embed("games/sonic4/data/generated/dust/dplc_dust.bin")
pub data Art_Dust         = embed("games/sonic4/data/generated/dust/art_dust.bin")

// The puff block's byte offset into Art_Dust, and its length — the resident
// DMA's source and size. Named here (the format owner) rather than at the load
// site, so a re-export that moved the split is one edit.
pub const DUST_PUFF_ART_OFF = 72 * 32   // 2304
pub const DUST_PUFF_ART_LEN = 16 * 32   // 512

ensure(sizeof(Art_Dust) == 88 * 32, "Art_Dust must be 88 tiles — 72 charge + 16 puff")
ensure(DUST_PUFF_ART_OFF + DUST_PUFF_ART_LEN == sizeof(Art_Dust),
       "the puff block must be the TAIL of Art_Dust")
ensure(dplc_peak_tiles(DPLC_Dust) <= 12,
       "the charge DPLC's peak frame exceeds its 12-tile window (VRAM_DUST_SPINDASH)")
```

`dplc_peak_tiles` is the comptime parser in `engine/objects/dplc.emp:60`; import it the way `tails_data.emp` does.

- [ ] **Step 2: Create the animation scripts**

Create `games/sonic4/data/animations/dust_anims.emp`:

```
// Dust animation scripts.
//
// Duration semantics: AnimateSprite reloads anim_timer with the duration byte
// and ticks `subq.b #1 / bpl`, so byte N holds a frame for N+1 display frames
// (engine/objects/animate.emp:91). These are therefore the S3K timings exactly:
// duration 1 x 7 frames = a 14-frame charge loop; duration 3 x 4 frames = a
// 16-frame puff life.
module games.sonic4.dust_anims in dust_anims

use engine.constants.{AF_DELETE, AF_END}

offsets Ani_DustSpindash {
    // The charge cycle. Loops forever — the follower's own state check ends it,
    // not the script (S3K: `dc.b 1, $A..$10, $FF`).
    Charge: [u8; 9] = [1, 0, 1, 2, 3, 4, 5, 6, AF_END],
}
align 2

offsets Ani_DustPuff {
    // One puff, then gone. The script OWNS the lifetime: there is no timer field
    // (S3K: `dc.b 3, $11..$14, $FC` into a routine bump that deletes).
    Puff: [u8; 6] = [3, 0, 1, 2, 3, AF_DELETE],
}
align 2
```

- [ ] **Step 3: Load the puff block at level init**

In `games/sonic4/test/ojz_scroll_test.emp`, immediately after the `TestArt` DMA block (the `QueueDMA_Critical @discards(dropped)` at ~line 131), add:

```
        // -- dust puff block: 16 tiles RESIDENT at VRAM_DUST_PUFF for the whole
        //    act. Every puff frame must be live simultaneously (concurrent puffs
        //    sit on different frames), so this object never streams — this one
        //    DMA is its entire art cost. Source is the TAIL of Art_Dust; the
        //    leading 72 tiles are the charge dust's DPLC source. --
        move.l  #Art_Dust + DUST_PUFF_ART_OFF, d1
        move.w  #vram_bytes(VRAM_DUST_PUFF), d2
        move.w  #DUST_PUFF_ART_LEN, d3
        jbsr    QueueDMA_Critical @discards(dropped)   // level init: a dropped DMA is
                                                       // acceptable here exactly as for
                                                       // TestArt above
```

Add `VRAM_DUST_PUFF` to the module's `use games.sonic4.constants.{...}` list and `DUST_PUFF_ART_OFF, DUST_PUFF_ART_LEN` to a `use games.sonic4.dust_data.{...}`.

- [ ] **Step 4: Register the two sections**

In `games/sonic4/map.toml`, add `"Ani_DustSpindash",` to the `order` array immediately after `"Ani_Particle",`, and `"Map_DustSpindash",` immediately after `"Map_TestObj",`. Both are data; the dust art is 2816 B and fits the data region's headroom (`Art_Sonic` ends at `$4277E` against the `dac_banks` anchor at `$48000` — about 22,658 B free), so unlike Tails' 132 KB it does **not** need exiling to the ROM tail.

In `sigil crates/sigil-harness/repin.toml`, append two `[[region]]` entries following the shape of the existing `particle_anims` / `test_mappings` entries:
```toml
[[region]]
# Dust animation scripts (dust_anims.emp) — the charge loop + the puff one-shot.
name = "dust_anims"
start = "Ani_DustSpindash"
gate = "SIGIL_EMP_DUST_ANIMS"
tests = ["dust_anims_port"]

[[region]]
# Dust sprite data (dust_data.emp): mappings x2, the charge DPLC, and the 88-tile
# art blob whose tail 16 tiles are the resident puff block.
name = "dust_data"
start = "Map_DustSpindash"
gate = "SIGIL_EMP_DUST_DATA"
tests = ["dust_data_port"]
```

In `sigil crates/sigil-harness/src/native.rs`, add beside the other game-data specs (near line 402):
```rust
        m!("games.sonic4.dust_anims", "dust_anims", pins::DUST_ANIMS),
        m!("games.sonic4.dust_data", "dust_data", pins::DUST_DATA),
```

**Use real pins.** `pins.rs` is generated by `repin`, so do not hand-write values: add the manifest entries, run `repin`, and let it resolve them from the listings. Never substitute `DUMMY_REGION` — it collapses the section onto base 0 where it collides with `vectors`.

- [ ] **Step 5: Rebuild sigil, repin, build aeon**

```bash
cd /home/volence/sonic_hacks/sigil && cargo build --release
cargo run -q -p sigil-harness --bin repin
cd /home/volence/sonic_hacks/aeon
SIGIL_BLOB_LEN_DRIFT=warn ./build.sh && SIGIL_BLOB_LEN_DRIFT=warn DEBUG=1 ./build.sh
```
Expected: both build. A comptime failure naming `dplc_peak_tiles` means the charge DPLC does not fit 12 tiles — fix the importer, not the `ensure`.

- [ ] **Step 6: Verify the resident art landed in VRAM**

Boot `s4.debug.bin` in Oracle and read VRAM at `VRAM_DUST_PUFF`:
```
tile 896 -> byte address 896 * 32 = 0x7000, length 512
```
Expected: 512 non-zero bytes matching `art_dust.bin`'s last 512, and the pixels use only nibble values 0/4/6/7. All-zero means the DMA was dropped or the source offset is wrong.

- [ ] **Step 7: Commit**

```bash
git branch --show-current
git add games/sonic4/data/dust_data.emp \
        games/sonic4/data/animations/dust_anims.emp \
        games/sonic4/test/ojz_scroll_test.emp \
        games/sonic4/map.toml
git commit -m "feat(data): dust sprite data + scripts, puff block resident in VRAM

One 88-tile art blob: leading 72 tiles are the charge dust's DPLC source, the
tail 16 are the puff block, DMA'd once at level init to VRAM_DUST_PUFF and never
streamed (concurrent puffs sit on different animation frames, so every frame
must be live at once).

Scripts carry the S3K timings exactly under animate.emp's N+1 duration rule:
14-frame charge loop, 16-frame puff life owned by AF_DELETE.

Art is 2816 B and fits the data region's ~22.6 KB headroom, so unlike Tails'
132 KB it needs no exile past the sound banks."
```
Commit the sigil side separately in the sigil repo (`repin.toml`, `native.rs`, regenerated `pins.rs`).

---

## Task 4: The puff object, its cadence, and the skid spawner

Byte-changing. End of this task: skidding produces dust on screen.

**Files:**
- Create: `games/sonic4/objects/dust_puff.emp`
- Modify: `games/sonic4/config/ram.emp:37-48` (`PlayerBlock`)
- Modify: `games/sonic4/player/player_common.emp` (`PBLK_DUSTTIMER`, `Player_Display`)
- Modify: `games/sonic4/map.toml`, sigil `repin.toml` + `native.rs`

- [ ] **Step 1: Append the cadence byte to PlayerBlock**

In `games/sonic4/config/ram.emp`, add to `PlayerBlock` after `jump_buffer`:

```
    dust_timer:     u8,     // frames until the next dust puff (4-frame cadence);
                            // 0 while not emitting so the first puff of a skid
                            // lands on the arming frame, as in S3K
    pad:            u8,     // KEEPS sizeof(PlayerBlock) EVEN. The struct is the
                            // per-slot ARRAY STRIDE (`lea sizeof(PlayerBlock)(dst),
                            // dst`), and every field from accel down is a u16 at
                            // even offset 0..15 — an odd stride would put slot 1's
                            // accel on an odd address and `move.w` would ADDRESS
                            // ERROR. 8 words + quadrant + jump_buffer was exactly
                            // 18; dust_timer makes 19, so this pads back to 20.
```

**Append at the end** so no existing `PBLK_*` offset shifts. It lives here and not in `PlayerV` deliberately: `Replay_Hash` covers `PlayerV` `$30..$4C` (`engine/system/replay.emp:8-46`), so a gameplay-written field there would change every recorded fixture hash. The PlayerBlock is not hashed.

**The pad is not optional.** If sigil's region checker catches the odd stride it fails the build; if it does not, the failure mode is a runtime address error on the second player slot, which is far worse. Either way the pad is correct — do not drop it as "unused".

- [ ] **Step 2: Add the offset mirror and its guard**

In `games/sonic4/player/player_common.emp`, beside `PBLK_QUADRANT` / `PBLK_JUMPBUF` (lines 174-175):

```
const PBLK_DUSTTIMER = 18
```
and beside the existing offset `ensure`s (lines 232-235):
```
ensure(PBLK_DUSTTIMER == offsetof(PlayerBlock, dust_timer),
       "PBLK_DUSTTIMER out of sync with PlayerBlock.dust_timer (config/ram.emp)")
```

- [ ] **Step 3: Create the puff object**

Create `games/sonic4/objects/dust_puff.emp`:

```
// Skid / slide dust puff — a fire-and-forget effect.
//
// The cheapest object in the engine: no velocity, no DPLC, no parent link, no
// timer field. It is dropped at a world position, animates four frames, and
// deletes itself via AF_DELETE. Its art is permanently resident at
// VRAM_DUST_PUFF (games/sonic4/data/dust_data.emp), so it queues no DMA in its
// entire life — which is what lets several puffs at DIFFERENT animation frames
// coexist. S3K achieves the same thing with an invisible emitter object that
// pumps a 16-tile DPLC every frame plus four empty DPLC lists; residency
// deletes that whole mechanism.
//
// NOT screen-space: render_flags leaves RF_COORDMODE CLEAR (level-relative), so
// the puff stays where it was dropped and scrolls with the level. The slot
// arrives freshly zeroed from DeleteObject, so "clear" is the default and the
// band write below is the only render_flags write.
module games.sonic4.dust_puff in dust_puff

use engine.objects.sst.{Sst}
use engine.constants.{RF_PRIORITY_SHIFT}

// Band 2: BEHIND the player (4) and Tails' appendage (3), and low enough that
// dust is the first thing dropped when Render_Sprites hits MAX_VDP_SPRITES — it
// walks bands 7 down to 0 and truncates the tail (engine/objects/sprites.emp:225).
// This is a deliberate DEVIATION from the reference: S2/S3K/S.C.E. all put dust
// at priority 1-of-8-FRONT, protecting a cosmetic at the expense of gameplay
// sprites. Whole-byte write, not set_priority_band: nothing is inherited into a
// freshly zeroed slot, so a plain move is exact (the C1c union hazard needs an
// inherited band).
const DUST_PUFF_BAND          = 2
const DUST_PUFF_RENDER_FLAGS  = DUST_PUFF_BAND << RF_PRIORITY_SHIFT

equ MAP_DUST_PUFF = extern("Map_DustPuff")
equ ANI_DUST_PUFF = extern("Ani_DustPuff")

// -----------------------------------------------
// DustPuff_Spawn — drop one puff at (d0.l, d1.l) in world coords.
//
// In:  d0.l = x_pos (16.16), d1.l = y_pos (16.16)
// Out: a puff allocated, or NOTHING if the effect pool is exhausted — the
//      silent skip every creator uses (children.emp:604). Dropping the NEW
//      spawn is the right policy for a cosmetic and is unanimous across the
//      reference corpus; do not add eviction.
// Clobbers: d2, a1
// Preserves: a0 (the caller's player SST), d0-d1
// -----------------------------------------------
pub proc DustPuff_Spawn (d0: u32, d1: u32) clobbers(d2/a1) preserves(a0, d0, d1) {
        jbsr    AllocEffect             // a1 = slot on the eq edge; a1 survives the
        bne     .done                   //   pool-empty edge untouched

        move.w  #DustPuff_Main - ObjCodeBase, Sst.code_addr(a1)
        move.l  d0, Sst.x_pos(a1)
        move.l  d1, Sst.y_pos(a1)
        move.l  #MAP_DUST_PUFF, Sst.mappings(a1)
        move.w  #VRAM_DUST_PUFF, Sst.art_tile(a1)   // vram_art(tile,0,0) == tile:
                                                    // palette 0, low priority
        move.l  #ANI_DUST_PUFF, Sst.anim_table(a1)
        move.b  #$FF, Sst.prev_anim(a1)             // force AnimateSprite's
        move.b  #$FF, Sst.prev_frame(a1)            // .anim_changed path, which
                                                    // tail-calls RefreshSpritePieceCount
                                                    // and populates the piece count +
                                                    // frame_off cache before the first
                                                    // render (so no
                                                    // PopulateSpawnedPieceCount call)
        move.b  #DUST_PUFF_RENDER_FLAGS, Sst.render_flags(a1)
    .done:
        rts
}

// -----------------------------------------------
// DustPuff_Main — animate, draw, and eventually delete itself.
//
// No ObjectMove (no velocity — the puff is static in world space, exactly as in
// S2/S3K) and no Perform_DPLC (resident art). AF_DELETE at the end of the script
// is the entire retirement path.
//
// In:  a0 = own SST
// Clobbers: d0-d3, a1-a2 — the callee union: AnimateSprite (d0-d2/a1-a2) union
//           Draw_Sprite (d0-d3/a1). a0/d7.w preserved per the dispatch contract.
// -----------------------------------------------
pub proc DustPuff_Main (a0: *Sst) clobbers(d0-d3/a1-a2) preserves(a0) {
        jbsr    AnimateSprite
        jbra    Draw_Sprite
}
```

Add `VRAM_DUST_PUFF` to a `use games.sonic4.constants.{VRAM_DUST_PUFF}`.

- [ ] **Step 4: Call the cadence from the player's display tail**

In `games/sonic4/player/player_common.emp`, change `Player_Display` (line 594-598) to:

```
pub proc Player_Display (a0: *Sst) clobbers(d0-d6/a1-a3) {
        jbsr    Player_Animate                  // sets SST_anim + d3 (dyn hold)
        jbsr    Dust_Tick                       // AFTER Player_Animate: the
                                                // classifier is what sets and clears
                                                // skid_latch, so reading it earlier
                                                // in the frame reads LAST frame's
                                                // value. a4 is still the slot's block
                                                // (Player_Main holds it for the whole
                                                // frame) and d3 must survive for
                                                // AnimateSprite, so Dust_Tick
                                                // preserves it.
        jbsr    AnimateSprite
        jbra    Player_LoadArt
}
```

`Player_Display` is entered by `falls_into` from `Player_Main`, which resolves `a4` via `player_block(a0, a4)` and holds it all frame, so `a4` is live here. Note `Player_DebugMove` bypasses this tail entirely, so debug-fly correctly produces no dust.

- [ ] **Step 5: Write the cadence in the spindash module**

Append to `games/sonic4/objects/dust_spindash.emp` — create the file now with just this proc; the follower lands in Task 5:

```
// Dust spawning — the per-frame cadence and (Task 5) the charge-dust follower.
module games.sonic4.dust_spindash in dust_spindash

use engine.objects.sst.{Sst}
use engine.coords.{pixels_to_coord}
use engine.structs.{CharacterDef, cd_stand_h_off}
use games.sonic4.player_common.{PlayerV}

const PBLK_DUSTTIMER = 18
ensure(PBLK_DUSTTIMER == extern("PBLK_DUSTTIMER"),
       "PBLK_DUSTTIMER diverged from player_common's mirror")

// One puff every 4 frames — S2, S3K and S.C.E. all use a plain countdown
// reloaded with 3, no mask and no randomisation (the reference dust uses no RNG
// at all, which suits an engine that has none).
const DUST_CADENCE_RELOAD = 3

// The skid puff sits 3 px above the character's FEET, derived from the record
// rather than from S3K's magic "short character" flag byte.
//
// cd_stand_wh's height half is the FULL box (2r+1, always odd), so `>> 1`
// recovers the y_radius exactly. y_off = y_radius - 3 reproduces S3K's numbers
// for free: Sonic (r=19) -> 16, which is S3K's literal +$10; Tails (r=15) -> 12,
// which is S3K's $10 MINUS the 4 px its short-character flag subtracts. The
// per-character delta S3K encodes as a flag is simply the radius difference, so
// deriving it needs no per-character dust data at all.
const DUST_FEET_RISE = 3

// -----------------------------------------------
// Dust_Tick — emit skid/slide dust on the cadence, or disarm.
//
// Reads PlayerV.skid_latch, the authoritative latch the animation classifier
// already maintains (player_common.emp:699-733) — the alternative, re-deriving
// "is skidding" from grounded + opposing input + |gsp| >= PHYS_SKID_MIN, would
// duplicate a four-term condition that has exactly one home and would drift.
//
// The Y offset is derived from the active character's standing height rather
// than S3K's flag byte, so a shorter character's puff rides correspondingly
// higher with no per-character data of its own.
//
// In:  a0 = player SST; a4 = the slot's player block (an IMPLICIT input, matching
//      PState_Spindash's convention — a4 is held by Player_Main for the whole
//      frame and documented rather than declared)
// Out: at most one puff spawned
// Clobbers: d0-d2, a1-a2
// Preserves: a0, d3 (Player_Display's dynamic animation hold, live across this
//            call into AnimateSprite)
// -----------------------------------------------
pub proc Dust_Tick (a0: *Sst) clobbers(d0-d2/a1-a2) preserves(a0, d3) {
        tst.b   PlayerV.skid_latch(a0)
        beq     .disarm
        subq.b  #1, PBLK_DUSTTIMER(a4)
        bpl     .done                           // not this frame
        move.b  #DUST_CADENCE_RELOAD, PBLK_DUSTTIMER(a4)

        // y = feet - 3 px, where feet = origin + y_radius and y_radius is the
        // record's full height >> 1 (the box is 2r+1, so the shift is exact).
        movea.l Player_Chardef, a1
        moveq   #0, d0
        move.b  cd_stand_h_off()(a1), d0        // full standing height (2r+1)
        lsr.w   #1, d0                          // d0 = y_radius
        subq.w  #DUST_FEET_RISE, d0             // Sonic -> 16, Tails -> 12
        pixels_to_coord(d0)
        move.l  Sst.y_pos(a0), d1
        add.l   d0, d1
        move.l  Sst.x_pos(a0), d0
        jbra    DustPuff_Spawn                  // tail call: its clobbers (d2/a1) are
                                                // inside ours, and it preserves a0/d0/d1
    .disarm:
        // Zeroed while not emitting, so the FIRST puff of the next skid lands on
        // the frame the skid arms — the reference behaviour, which falls out of
        // the countdown starting at 0.
        clr.b   PBLK_DUSTTIMER(a4)
    .done:
        rts
}
```

`Player_Chardef` is the resolved active `CharacterDef` pointer — confirmed as that exact symbol, read the same way at `player_ground.emp:478` (`movea.l Player_Chardef, a1`). It is a single global, not per-slot, which is fine for one player and is already tracked as a pre-C3 fix.

**The Knuckles slide seam (spec §3.2).** `Dust_Tick` reads only `skid_latch` today. Task 10 adds the slide by extending the arming test and the offset, and nothing else:
```
        tst.b   PlayerV.skid_latch(a0)
        bne     .emit
        cmpi.b  #PSTATE_SLIDE, PlayerV.player_state(a0)   // Task 10
        bne     .disarm
    .emit:
```
plus S3K's smaller slide offset (it drops the slide puff 6 px below the origin rather than 16, i.e. `DUST_FEET_RISE` becomes a slide-specific 13 against Knuckles' radius). Leave both out now — `PSTATE_SLIDE` does not exist yet and a branch on a nonexistent constant will not compile. The seam is named here so Task 10 does not redesign it.

- [ ] **Step 6: Register the two modules**

In `games/sonic4/map.toml` `order`, add `"DustPuff_Spawn",` and `"Dust_Tick",` immediately after `"TailsAppendage_Refresh",` (player-side game content, before the test objects). Add matching `[[region]]` entries to sigil `repin.toml` (`name = "dust_puff"` / `start = "DustPuff_Spawn"` / `gate = "SIGIL_EMP_DUST_PUFF"`; `name = "dust_spindash"` / `start = "Dust_Tick"` / `gate = "SIGIL_EMP_DUST_SPINDASH"`) and the `m!()` lines to `native.rs` beside `tails_appendage`.

- [ ] **Step 7: Build, repin, and verify on hardware-emulation**

```bash
cd /home/volence/sonic_hacks/sigil && cargo build --release
cargo run -q -p sigil-harness --bin repin
cd /home/volence/sonic_hacks/aeon
SIGIL_BLOB_LEN_DRIFT=warn ./build.sh && SIGIL_BLOB_LEN_DRIFT=warn DEBUG=1 ./build.sh
```
Then in Oracle with `s4.debug.bin`: leave debug-fly (**B**), run to speed, then hold the opposite direction to skid.

Expected: a puff appears on the frame the skid arms, another every 4 frames, each living 16 frames and **staying put in world space** while the camera scrolls. Capture **during** motion — at-rest screenshots hide scroll artifacts. Remember consecutive oracle `press` calls need a released frame between them or the fresh-press edge never re-arms.

- [ ] **Step 8: Re-run the replay gate**

Repeat Task 2 Step 6. Expected: PASS, still with **no fixture re-record** — the proof that the cadence byte stayed out of the hashed window.

- [ ] **Step 9: Commit**

```bash
git branch --show-current
git add games/sonic4/objects/dust_puff.emp \
        games/sonic4/objects/dust_spindash.emp \
        games/sonic4/config/ram.emp \
        games/sonic4/player/player_common.emp \
        games/sonic4/map.toml
git commit -m "feat(player): skid dust — a fire-and-forget puff on the Effect pool

DustPuff is the cheapest object in the engine: no velocity, no DPLC, no parent
link, no timer field. Resident art means it queues no DMA in its whole life,
which is what lets several puffs at DIFFERENT animation frames coexist; S3K
needs an invisible emitter object plus four empty DPLC lists for the same
result.

Dust_Tick runs from Player_Display AFTER Player_Animate, reading the skid_latch
the classifier already owns rather than re-deriving a four-term condition. The
4-frame cadence counter is appended to PlayerBlock, NOT PlayerV: Replay_Hash
covers PlayerV \$30..\$4C, so this keeps dust hash-neutral and the replay
fixtures valid.

Band 2 deliberately deviates from the reference (which puts dust at
priority-1-of-8-front): bands truncate 0-first, so a cosmetic should degrade
before gameplay sprites do."
```

---

## Task 5: The charge-dust follower

Byte-changing. End of this task: charging a spindash produces dust.

**Files:**
- Modify: `games/sonic4/objects/dust_spindash.emp`
- Modify: `games/sonic4/player/player_common.emp` (`PHook_SpindashEnter`)

- [ ] **Step 1: Add the follower to the dust module**

Append to `games/sonic4/objects/dust_spindash.emp`:

```
// The follower's own sst_custom overlay — just the player it tracks.
//
// NOT parent_ptr, deliberately: children.emp:630-635 records that a non-zero
// parent_ptr makes Draw_Sprite dereference the parent every frame to test
// RF_MULTISPRITE, and that an effect spawned by a multisprite parent was then
// skipped as batch-rendered while absent from the sibling chain — i.e. never
// drawn at all. Holding the pointer here also keeps this 2P-ready without
// reading the Player_1 label, and keeps the object out of the sibling chain
// entirely (no chain contract, no cascade interaction).
vars DustV: Sst.sst_custom {
        player: u16,            // the player SST this follower tracks
}

const DUST_SPINDASH_BAND         = 2
const DUST_SPINDASH_RENDER_FLAGS = DUST_SPINDASH_BAND << RF_PRIORITY_SHIFT

equ MAP_DUST_SPINDASH = extern("Map_DustSpindash")
equ ANI_DUST_SPINDASH = extern("Ani_DustSpindash")
equ DPLC_DUST         = extern("DPLC_Dust")
equ ART_DUST          = extern("Art_Dust")

// -----------------------------------------------
// DustSpindash_Spawn — create the charge-dust follower.
// Called from PHook_SpindashEnter, i.e. exactly once per charge.
//
// In:  a0 = player SST
// Out: follower allocated, or nothing (silent skip) if the pool is exhausted —
//      a charge with no dust is the correct degradation for a cosmetic
// Clobbers: d0, a1
// Preserves: a0
// -----------------------------------------------
pub proc DustSpindash_Spawn (a0: *Sst) clobbers(d0/a1) preserves(a0) {
        jbsr    AllocEffect
        bne     .done

        move.w  #DustSpindash_Main - ObjCodeBase, Sst.code_addr(a1)
        move.l  Sst.x_pos(a0), Sst.x_pos(a1)    // placed NOW, not left at 0: the
        move.l  Sst.y_pos(a0), Sst.y_pos(a1)    //   Effect sweep may render this slot
                                                //   before its first Main runs
        move.l  #MAP_DUST_SPINDASH, Sst.mappings(a1)
        move.w  #VRAM_DUST_SPINDASH, Sst.art_tile(a1)
        move.l  #ANI_DUST_SPINDASH, Sst.anim_table(a1)
        move.b  #$FF, Sst.prev_anim(a1)
        move.b  #$FF, Sst.prev_frame(a1)
        move.b  #DUST_SPINDASH_RENDER_FLAGS, Sst.render_flags(a1)
        move.w  a0, DustV.player(a1)
    .done:
        rts
}

// -----------------------------------------------
// DustSpindash_Main — follow the player, animate, stream, draw, and retire.
//
// RETIREMENT IS A STATE POLL, NOT A HOOK, and that is deliberate. Deleting this
// object from PHook_SpindashExit would need a cached slot pointer, and that
// pointer can be invalidated behind the hook's back — DeleteChildren runs on a
// character switch and DeleteObject's cascade runs on death, either of which
// frees this slot while the hook still believes it owns it. A stale pointer plus
// a delete is the classic double-delete that corrupts the free stack. The poll
// has no such surface and self-heals: if the player slot is zeroed under us,
// player_state reads 0 (PSTATE_GROUND), the compare fails, and we retire.
//
// This is NOT the S2 floating-dust bug. That dust polled spin_dash_flag, which a
// grab leaves set; we poll the state byte, which Player_SetState writes on every
// transition and which has no stale path.
//
// Runs from the Effect sweep, AFTER the Player sweep, so the position and status
// read here are this frame's final values.
//
// In:  a0 = own SST
// Clobbers: d0-d4, a1-a3 — the callee union: AnimateSprite (d0-d2/a1-a2) union
//           Perform_DPLC_Deferrable (d0-d4/a1-a2, a3 an input it preserves)
//           union Draw_Sprite (d0-d3/a1).
// -----------------------------------------------
pub proc DustSpindash_Main (a0: *Sst) clobbers(d0-d4/a1-a3) preserves(a0) {
        movea.w DustV.player(a0), a1
        cmpi.b  #PSTATE_SPINDASH, PlayerV.player_state(a1)
        bne     DeleteObject                    // tail call — the charge ended by ANY
                                                // path, including death and a
                                                // character switch

        move.l  Sst.x_pos(a1), Sst.x_pos(a0)
        move.l  Sst.y_pos(a1), Sst.y_pos(a0)

        // Mirror the facing only. AnimateSprite propagates status bits 1-2 into
        // render_flags itself, so copying the whole status byte would also drag
        // across bits this object has no business carrying. Spelled as
        // bclr/btst/bset rather than a mask pair: no complement operator is
        // assumed, and the bit index is the same ST_XFLIP the player uses.
        bclr    #ST_XFLIP, Sst.status(a0)
        btst    #ST_XFLIP, Sst.status(a1)
        beq     .no_flip
        bset    #ST_XFLIP, Sst.status(a0)
    .no_flip:

        jbsr    AnimateSprite
        lea     DPLC_DUST, a2
        lea     ART_DUST, a3
        move.w  #vram_bytes(VRAM_DUST_SPINDASH), d1
        jbsr    Perform_DPLC_Deferrable         // Deferrable, not Important: this is
                                                // cosmetic non-player art and may slip
                                                // a frame. perform_dplc leaves
                                                // prev_frame stale on a dropped
                                                // enqueue, so the next frame RETRIES
                                                // rather than showing stale tiles.
        jbra    Draw_Sprite
}
```

Add `ST_XFLIP`, `PSTATE_SPINDASH`, `RF_PRIORITY_SHIFT`, `VRAM_DUST_SPINDASH` and `vram_bytes` to the module's `use` lists.

- [ ] **Step 2: Spawn it from the enter hook**

In `games/sonic4/player/player_common.emp`, add to `PHook_SpindashEnter` (line 906) as the last statement before `rts`:

```
        jbsr    DustSpindash_Spawn              // one follower per charge; it retires
                                                // itself on the state byte, so there is
                                                // deliberately no teardown in
                                                // PHook_SpindashExit (a cached slot
                                                // pointer there could be freed behind
                                                // the hook's back by DeleteChildren or
                                                // the death cascade)
```

Widen the hook's contract from `clobbers(d1/a1)` to `clobbers(d0-d1/a1)` to cover `AllocEffect`.

- [ ] **Step 3: Build**

```bash
cd /home/volence/sonic_hacks/aeon
SIGIL_BLOB_LEN_DRIFT=warn ./build.sh && SIGIL_BLOB_LEN_DRIFT=warn DEBUG=1 ./build.sh
```
Expected: both build clean. No new module here, so no `map.toml`/pin work — both procs live in already-registered sections.

- [ ] **Step 4: Verify the charge dust**

In Oracle with `s4.debug.bin`: leave debug-fly, stand still, hold Down and press Jump to charge.

Expected: dust appears at the player on the charge frame and cycles continuously (14-frame loop); it faces the way the player faces; it disappears the frame the charge releases into a roll. Verify VRAM at `VRAM_DUST_SPINDASH` (tile 912 -> byte `0x7200`) changes as the animation cycles.

- [ ] **Step 5: Verify the teardown paths explicitly**

Three cases, all of which must leave no dust behind:
1. Release the charge into a roll.
2. Abort the charge by walking off a ledge mid-charge (floor loss -> `PSTATE_AIRBALL`).
3. Switch character mid-charge (**B** to enter debug mode, **A** to cycle, **B** to leave) — the case that would have double-deleted under a hook-based teardown.

Expected: dust gone within one frame in all three; no fault screen; no red screen. A red screen here is a fault halt, not BUG-001 — the discriminator is display-OFF versus planes-still-drawing.

- [ ] **Step 6: Re-run the replay gate**

Repeat Task 2 Step 6. Expected: PASS, no fixture re-record.

- [ ] **Step 7: Commit**

```bash
git branch --show-current
git add games/sonic4/objects/dust_spindash.emp games/sonic4/player/player_common.emp
git commit -m "feat(player): spindash charge dust — an Effect-pool follower

Created once by PHook_SpindashEnter, re-reads the player every frame (the Effect
sweep runs after the Player sweep, so those are final values), streams its
12-tile frame at Deferrable priority, and RETIRES ON THE STATE BYTE rather than
from PHook_SpindashExit.

The poll is the point: a hook-based teardown needs a cached slot pointer, and
DeleteChildren (character switch) or the death cascade can free that slot behind
the hook's back — a double-delete on the free stack. The poll self-heals and
covers every exit path. It is also not the S2 floating-dust bug, which polled a
spin_dash_flag a grab could leave stale; the state byte has no stale path.

The player pointer rides sst_custom, not parent_ptr: a non-zero parent_ptr drags
Draw_Sprite into a per-frame multisprite dereference that can make an effect
never draw at all (children.emp:630)."
```

---

## Task 6: The overlap case, docs, and riders

- [ ] **Step 1: Verify the case the 28-tile split exists for**

In Oracle: run to full speed, hold the opposite direction to skid to a stop, then **immediately** press Down+Jump to charge.

Expected: the lingering puffs finish their own 16-frame fade **while** the charge dust runs, with **no shimmer and no pop**. This is the case S3K gets wrong (its charge DPLC overwrites tiles 0-11 of a window live puffs address 0-15 of), and the only direct proof the separate windows work. Capture mid-motion.

- [ ] **Step 2: Sync the architecture doc's VRAM map**

Update the VRAM layout section of `docs/ENGINE_ARCHITECTURE.md` so the FG art pool reads 896 tiles / 14 pages and the dust windows at 896-923 appear, with 924-959 marked spare. The architecture doc is the source of truth — if code and doc disagree, one of them is wrong.

- [ ] **Step 3: Ledger the riders**

Add to `docs/DEFERRED_WORK.md`:
1. **Knuckles dust art variant** — a second, raw (unpermuted) 2816 B blob, selected at `Player_RefreshPhysics` alongside his palette swap, which must also re-DMA the resident puff block since it is palette-specific. Include the measurement: no single variant can serve both lines because the three colours sit at disjoint indices and the lines agree only at 0/10/11.
2. **Water splash / water-run dust** — gated on a water system existing at all.
3. **Hoist the shared S3K-to-S4 sprite conversion** out of `gen_characters.py` and `gen_dust.py` into `tools/s3k_sprites.py`. Deferred deliberately: `gen_characters.py` is load-bearing on two branches right now.
4. **TF4 misattribution** — `docs/ENGINE_ARCHITECTURE.md` (~lines 1118, 1165, 1955, §3.5) and `docs/research/children-particles.md:166` credit Thunder Force IV with "round-robin sprite flicker" at `$F29A`. That address is a global Y-drift accumulator added to every projectile's Y accumulator (`thunderforce4_disasm/code/disasm.asm:7206`, `:7231`); TF4 has no such mechanism, and the same doc's claimed TF4 RAM pools are palette/tilemap staging. Our own per-frame intra-band link-order cycling (`sprites.emp:242-255`) is real — only the provenance is wrong.
5. **`particle_anims.emp:17`** comment says "duration 4 frames/frame"; under `animate.emp:91`'s N+1 rule a duration byte of 4 holds for 5 frames.

- [ ] **Step 4: Full gate sweep**

```bash
cd /home/volence/sonic_hacks/aeon
./build.sh && DEBUG=1 ./build.sh && DEBUG=1 ./build.sh demo
```
All three must build; `demo` must be byte-unaffected by dust, proving the work stayed game-side.

Then the sigil suite, **aggregated — never `tail` a `--no-fail-fast` run** (a `tail -45` once hid 16 failures and a merge was claimed green on it):
```bash
cd /home/volence/sonic_hacks/sigil
cargo test -q --release --workspace --no-fail-fast 2>&1 | awk '
/^test result/ { for(i=1;i<=NF;i++){ if($i=="passed;") p+=$(i-1); if($i=="failed;") f+=$(i-1) } }
/^error: test failed, to rerun pass/ { print "FAILING: " $0 }
END { printf "\nTOTAL: %d passed, %d FAILED\n", p, f }'
```
Expected: 0 failed. **Known inherited exception:** 4 failures across 3 `seam2_*` targets appear only under `SIGIL_STRICT_GATE=1` (they skip-green otherwise) and are pre-existing sound-bank drift, not dust. Anything else is yours.

- [ ] **Step 5: Commit and finish the branch**

```bash
git branch --show-current
git add docs/ENGINE_ARCHITECTURE.md docs/DEFERRED_WORK.md
git commit -m "docs: sync the VRAM map to 896 tiles, ledger the dust riders"
```

Then follow superpowers:finishing-a-development-branch. **Do not leave master broken**, and lead any summary with what merged.

---

## Notes for whoever executes this

- **`Player_Chardef` is a single global, not per-slot** (pre-existing, tracked). With a real follower both slots would resolve the leader's character. Fine for one player; it must be fixed before C3, not after.
- **Oracle wedges intermittently** on heavy `press` use (`PC=SP=0xFFFFFFFF`). `breakpoint_clear` + `reset` do **not** recover — `pkill -x oracle_gui`, then relaunch from `/home/volence/sonic_hacks/oracle/linux-port/build`. One instance only; verify with `pgrep -a oracle_gui`.
- **Do not shave bytes to fit a stale pin.** Re-derive the tables via `repin`. This has been refused twice, correctly, on this branch.
- If a comptime `ensure` from this plan fires, **fix the cause, not the `ensure`**. Every one of them encodes a measured fact.
