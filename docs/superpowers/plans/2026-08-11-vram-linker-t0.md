# VRAM Linker T0 (the registry) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One declared authority for every VRAM tile — `vram.toml` per game, a deterministic generator emitting the constants, the Python mirror, and the human map — captured byte-identically first, then the dust pool carve re-landed as a TOML edit.

**Architecture:** `games/<game>/vram.toml` is the placement contract (peer of `map.toml`). `tools/gen_vram_map.py` verifies it (full coverage of tiles 0..2047, overlap-unless-declared-overlay, quantum fit, intentional free list) and rewrites a `// >>> GENERATED` marker block inside the existing `games/<game>/config/constants.emp` — NOT a new module (const-only modules are not `m!()`-placed; the marker block keeps the `game_constants_rel` harvest path and every consumer import unchanged). It also emits `tools/vram_map.py` (killing the four independent Python copies of the BG budget) and `docs/generated/vram-map-<game>.md`.

**Tech Stack:** Python 3.14 (`tomllib` stdlib) + pytest for the generator; sigil `.emp` comptime `ensure`s as the build-side net; Oracle emulator (controller-only) for the carve's replay gates.

**Spec:** `docs/superpowers/specs/2026-08-11-vram-linker-design.md` §5 + §8 steps 1-3 (as amended `bd51da2b`: marker block, not new module). Ground truth: `docs/research/2026-08-11-vram-linker-internal-audit.md`.

**Branch:** `feat/character-dispatch`. **Verify `git branch --show-current` before every commit** — parallel sessions share this tree.

---

## Orientation: things that will bite you

1. **Byte-identity is the whole point of Tasks 1-4.** The verbatim capture must not move a single ROM byte in any shape. Task 0 captures YOUR baseline CRCs — do not trust any CRC written in a doc (including this one); stale artifacts on disk have already fooled one session today.
2. **Task 5 (the carve) moves bytes** and owes the ritual: `SIGIL_BLOB_LEN_DRIFT=warn` builds, rebuild BOTH sigil release binaries after any sigil edit, repin → refreeze (`--freeze NAME --ab "<evidence>"` — the `ab` is prose citing emulator results). `refreeze --check` passing does NOT mean the goldens are current — they are different artifacts.
3. **Emulator work is CONTROLLER-ONLY.** Subagents never call Oracle MCP tools (deadlocks the arbiter). Task 5's replay gates are the controller's steps; a subagent implementing Task 5 stops at the build and reports ready-for-gates.
4. **The auto-commit daemon** watches `tools/ojz_strip_gen.py` (touched in Task 4) and commits it to the current branch ~every 60 s. Check `git log --oneline -3` before staging; if the daemon committed it first, reference that commit — **never `--amend`** on this branch. `git add` exact paths only.
5. **Required env** for any build:
```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
```
6. **Generator tests write to `tmp_path` only** — never default output into the repo (`tools/test_import_sk_collision.py:14` documents the incident). The generator itself takes explicit output paths so tests can redirect everything.
7. **Never `tail` a `--no-fail-fast` test run** — aggregate totals (the awk recipe in Task 6).

## Ground truth (verify, don't trust)

The current map, from the audit (`docs/research/2026-08-11-vram-linker-internal-audit.md` §1, PRE-carve state — the carve was reverted and re-lands in Task 5):

| Tiles | Owner | Constant (authority) |
|---|---|---|
| 0-959 | FG art pool (arena, 15×64 pages) | `POOL_TILE_CEILING` (engine, `engine/system/constants.emp:595`) |
| 960-991 | character DPLC window (32) | `VRAM_TEST_SONIC = $03C0` (game) |
| 992-999 | test-object art (8) | `VRAM_TEST_OBJ = $03E0` (game) |
| 1000-1015 | ring art (16) | `VRAM_RING_PLACEHOLDER = 0x3E8` (**sigil `-D`**, `native.rs`, 4 profiles) |
| 1016-1019 | debug-fly marker (4) | `VRAM_TEST_MARKER = VRAM_TEST_OBJ + $18` (game) |
| 1020-1023 | **FREE** (4) | — |
| 1024-1471 | BG tile region (448) | `BG_TILE_BASE_VRAM`/`BG_TILE_CAPACITY` (engine) + **3 Python copies** |
| 1472-1491 | SAT (20) | `VRAM_SPRITE_TABLE = $B800` (engine; VDP reg $05) |
| 1492-1500 | Tails appendage window (9) | `VRAM_TAILS_APPENDAGE = $05D4` (game) |
| 1501-1503 | **FREE** (3) | — |
| 1504-1531 | HScroll table (28) | `VRAM_HSCROLL_TABLE = $BC00` (engine; VDP reg $0D) |
| 1532-1535 | **FREE** (4) | — |
| 1536-1791 | Plane A (256) | `VRAM_PLANE_A = $C000` (engine; VDP reg $02) |
| 1792-2047 | Plane B (256) | `VRAM_PLANE_B = $E000` (engine; VDP reg $04) |
| 1920-2047 | Window plane (128) — **deliberate overlay** of Plane B (disabled feature, regs $11/$12=0) | `VRAM_WINDOW = $F000` (engine; VDP reg $03) |

Demo (`games/demo/config/constants.emp:34`, audit §6): `VRAM_DEMO_OBJ = $03E0` (992, 4 tiles) + demo ring placeholder `0x3E4` (996, 1 blank tile); no character window, no test objects, no appendage; engine regions identical.

## File Structure

**Create:**
- `games/sonic4/vram.toml`, `games/demo/vram.toml` — the contracts
- `tools/gen_vram_map.py` — the generator (verify + emit; deterministic)
- `tools/test_gen_vram_map.py` — pytest suite
- `tools/vram_map.py` — GENERATED Python mirror (committed)
- `docs/generated/vram-map-sonic4.md`, `docs/generated/vram-map-demo.md` — GENERATED maps (committed)

**Modify:**
- `games/sonic4/config/constants.emp` — VRAM consts move inside a marker block (+ one `use` addition)
- `games/demo/config/constants.emp` — same treatment for `VRAM_DEMO_OBJ`
- `tools/ojz_strip_gen.py:124,263-264`, `tools/inject_editor_bg.py:18,21`, `tools/png_to_bg_override.py:33` — literals → imports (Task 4)
- Task 5 only: `games/sonic4/vram.toml` (the carve), `engine/system/constants.emp:595` (960→896)

---

## Task 0: Baseline capture

**Files:** none (scratchpad only)

- [ ] **Step 1: Build all three shapes and record the baseline**

```bash
cd /home/volence/sonic_hacks/aeon
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
git branch --show-current   # must be feat/character-dispatch, clean tree
./build.sh && DEBUG=1 ./build.sh && DEBUG=1 ./build.sh demo
S=$(ls -d /tmp/claude-1000/*/*/scratchpad 2>/dev/null | head -1)
for f in s4.bin s4.debug.bin demo.debug.bin; do
  python3 -c "import zlib;print('$f', format(zlib.crc32(open('$f','rb').read()),'08x'))"
done | tee "$S/vram-t0-baseline.txt"
```
Expected: three lines. These are THE baseline for Tasks 3-4's byte-identity gates.

---

## Task 1: Author the two contracts

**Files:**
- Create: `games/sonic4/vram.toml`
- Create: `games/demo/vram.toml`

- [ ] **Step 1: Write `games/sonic4/vram.toml`**

```toml
# games/sonic4/vram.toml — the DECLARED VRAM placement contract (peer of map.toml).
# Spec: docs/superpowers/specs/2026-08-11-vram-linker-design.md §4.1/§5.
# T0: every region is PINNED (base required); the T1 solver introduces floating.
# Sizes in tiles (1 tile = 32 bytes). Consumed by tools/gen_vram_map.py, which
# rewrites the GENERATED block in config/constants.emp, tools/vram_map.py, and
# docs/generated/vram-map-sonic4.md. Full coverage of tiles 0..2047 is enforced:
# every tile is a region or a declared [[free]] run.

[[region]]
name = "fg_art_pool"
owner = "engine.level.page_cache"
kind = "arena"
base = 0
tiles = 960                      # AUTHORITY stays engine-side (POOL_TILE_CEILING);
quantum = 64                     # the generated block cross-checks equality.
lifetime = "act"
authority = "engine:POOL_TILE_CEILING"

[[region]]
name = "character_window"
owner = "games.sonic4.player"
kind = "window"
base = 960
tiles = 32
lifetime = "act"
const = "VRAM_TEST_SONIC"
# PINNED, deliberately: the base is baked into the player's art_tile word,
# which the replay hash covers — MOVING it re-stamps both fixtures. GROWING it
# is not moving it (spec §4.1): raise `tiles` with the base held.

[[region]]
name = "test_obj"
owner = "games.sonic4.test_objects"
kind = "window"
base = 992
tiles = 8
lifetime = "mode"
const = "VRAM_TEST_OBJ"

[[region]]
name = "ring_placeholder"
owner = "engine.objects.rings"
kind = "window"
base = 1000
tiles = 16
lifetime = "act"
authority = "sigil-D:VRAM_RING_PLACEHOLDER"   # -D define, native.rs; T1 feeds it
                                              # from this file. T0: soft-checked.

[[region]]
name = "test_marker"
owner = "games.sonic4.player_common"
kind = "window"
base = 1016
tiles = 4
lifetime = "mode"
const = "VRAM_TEST_MARKER"

[[free]]
base = 1020
tiles = 4

[[region]]
name = "bg_region"
owner = "engine.bg"
kind = "arena"
base = 1024
tiles = 448
lifetime = "act"
authority = "engine:BG_TILE_CAPACITY"

[[region]]
name = "sprite_table"
owner = "engine.system.buffers"
kind = "table"
base = 1472
tiles = 20
lifetime = "boot"
register = "vdp:0x05"
authority = "engine:VRAM_SPRITE_TABLE"

[[region]]
name = "tails_appendage"
owner = "games.sonic4.tails_appendage"
kind = "window"
base = 1492
tiles = 9
lifetime = "act"
const = "VRAM_TAILS_APPENDAGE"

[[free]]
base = 1501
tiles = 3

[[region]]
name = "hscroll_table"
owner = "engine.system.buffers"
kind = "table"
base = 1504
tiles = 28
lifetime = "boot"
register = "vdp:0x0D"
authority = "engine:VRAM_HSCROLL_TABLE"

[[free]]
base = 1532
tiles = 4

[[region]]
name = "plane_a"
owner = "engine.system.boot"
kind = "plane"
base = 1536
tiles = 256
lifetime = "boot"
register = "vdp:0x02"
authority = "engine:VRAM_PLANE_A"

[[region]]
name = "plane_b"
owner = "engine.system.boot"
kind = "plane"
base = 1792
tiles = 256
lifetime = "boot"
register = "vdp:0x04"
authority = "engine:VRAM_PLANE_B"

[[region]]
name = "window_plane"
owner = "engine.system.boot"
kind = "plane"
base = 1920
tiles = 128
lifetime = "boot"
register = "vdp:0x03"
overlay_with = ["plane_b"]      # the one overlay the tree already contains:
authority = "engine:VRAM_WINDOW" # the window feature is DISABLED (regs $11/$12
                                 # = 0) and deliberately aliases Plane B's tail
```

- [ ] **Step 2: Write `games/demo/vram.toml`**

```toml
# games/demo/vram.toml — the demo game's VRAM contract. The engine regions are
# identical to sonic4's by construction (same engine); the game-side band
# differs, ON PURPOSE now instead of by coincidence.

[[region]]
name = "fg_art_pool"
owner = "engine.level.page_cache"
kind = "arena"
base = 0
tiles = 960
quantum = 64
lifetime = "act"
authority = "engine:POOL_TILE_CEILING"
# demo ships HAS_ACT_ART_POOL=0 — the range exists, unpopulated.

[[region]]
name = "demo_obj"
owner = "games.demo.demo_state"
kind = "window"
base = 992
tiles = 4
lifetime = "boot"
const = "VRAM_DEMO_OBJ"

[[region]]
name = "ring_placeholder"
owner = "engine.objects.rings"
kind = "window"
base = 996
tiles = 1
lifetime = "boot"
authority = "sigil-D:VRAM_RING_PLACEHOLDER"

[[free]]
base = 997
tiles = 27

[[free]]
base = 960
tiles = 32
# no character window in demo — the band sonic4 uses for the player is free here

[[region]]
name = "bg_region"
owner = "engine.bg"
kind = "arena"
base = 1024
tiles = 448
lifetime = "act"
authority = "engine:BG_TILE_CAPACITY"

[[region]]
name = "sprite_table"
owner = "engine.system.buffers"
kind = "table"
base = 1472
tiles = 20
lifetime = "boot"
register = "vdp:0x05"
authority = "engine:VRAM_SPRITE_TABLE"

[[free]]
base = 1492
tiles = 12

[[region]]
name = "hscroll_table"
owner = "engine.system.buffers"
kind = "table"
base = 1504
tiles = 28
lifetime = "boot"
register = "vdp:0x0D"
authority = "engine:VRAM_HSCROLL_TABLE"

[[free]]
base = 1532
tiles = 4

[[region]]
name = "plane_a"
owner = "engine.system.boot"
kind = "plane"
base = 1536
tiles = 256
lifetime = "boot"
register = "vdp:0x02"
authority = "engine:VRAM_PLANE_A"

[[region]]
name = "plane_b"
owner = "engine.system.boot"
kind = "plane"
base = 1792
tiles = 256
lifetime = "boot"
register = "vdp:0x04"
authority = "engine:VRAM_PLANE_B"

[[region]]
name = "window_plane"
owner = "engine.system.boot"
kind = "plane"
base = 1920
tiles = 128
lifetime = "boot"
register = "vdp:0x03"
overlay_with = ["plane_b"]
authority = "engine:VRAM_WINDOW"
```

- [ ] **Step 3: Verify the demo values against the tree** (the audit is the source, but check the two demo facts directly): `rg -n "VRAM_DEMO_OBJ" games/demo/config/constants.emp` (expect `$03E0`) and the demo ring define `rg -n "0x3E4" /home/volence/sonic_hacks/sigil/crates/sigil-harness/src/native.rs` (expect the `demo_profile` block). If either disagrees, fix the TOML to match reality and note it in the commit.

- [ ] **Step 4: Commit**

```bash
git branch --show-current
git add games/sonic4/vram.toml games/demo/vram.toml
git commit -m "feat(vram): the declared VRAM contracts — verbatim capture of today's map

T0 of the VRAM linker (spec cc053a64/bd51da2b): every region pinned at its
current base, every free run declared, the one existing overlay (the disabled
window plane aliasing Plane B) declared instead of implicit. Nothing consumes
these yet — zero ROM delta."
```

---

## Task 2: The generator, TDD

**Files:**
- Create: `tools/test_gen_vram_map.py`
- Create: `tools/gen_vram_map.py`

- [ ] **Step 1: Write the failing tests**

Create `tools/test_gen_vram_map.py`:

```python
import os, subprocess, sys, textwrap

HERE = os.path.dirname(__file__)
GEN = os.path.join(HERE, "gen_vram_map.py")
REPO = os.path.normpath(os.path.join(HERE, ".."))

# NOTE: every test writes to tmp_path. NEVER default generator output into the
# repo — tools/test_import_sk_collision.py:14 records the incident this rule
# comes from.

GOOD = """
[[region]]
name = "pool"
owner = "engine.pool"
kind = "arena"
base = 0
tiles = 1984
quantum = 64
lifetime = "act"

[[region]]
name = "win"
owner = "game.win"
kind = "window"
base = 1984
tiles = 32
lifetime = "act"
const = "VRAM_WIN"

[[free]]
base = 2016
tiles = 32
"""

EMP_WITH_MARKERS = textwrap.dedent("""\
    // hand content above
    // >>> GENERATED: vram map (tools/gen_vram_map.py) — DO NOT HAND-EDIT <<<
    stale old content
    // <<< GENERATED: vram map END >>>
    // hand content below
    """)


def run(tmp, toml_text, emp_text=EMP_WITH_MARKERS, extra=None):
    toml = tmp / "vram.toml"; toml.write_text(toml_text)
    emp = tmp / "constants.emp"; emp.write_text(emp_text)
    args = [sys.executable, GEN, "--toml", str(toml), "--emp", str(emp),
            "--map-doc", str(tmp / "map.md"), "--game", "testgame"]
    if extra: args += extra
    return subprocess.run(args, capture_output=True, text=True)


def test_good_map_emits_block_and_doc(tmp_path):
    r = run(tmp_path, GOOD)
    assert r.returncode == 0, r.stderr
    emp = (tmp_path / "constants.emp").read_text()
    assert "pub const VRAM_WIN" in emp and "$07C0" in emp        # 1984 = $7C0
    assert "stale old content" not in emp
    assert "hand content above" in emp and "hand content below" in emp
    doc = (tmp_path / "map.md").read_text()
    assert "pool" in doc and "FREE" in doc and "2016" in doc


def test_gap_is_an_error_naming_the_run(tmp_path):
    bad = GOOD.replace('base = 2016\ntiles = 32', 'base = 2016\ntiles = 16')
    r = run(tmp_path, bad)
    assert r.returncode != 0
    assert "2032" in r.stderr and "2047" in r.stderr   # the undeclared run


def test_overlap_is_an_error_naming_both_owners(tmp_path):
    bad = GOOD.replace('base = 1984\ntiles = 32', 'base = 1980\ntiles = 36')
    r = run(tmp_path, bad)
    assert r.returncode != 0
    assert "pool" in r.stderr and "win" in r.stderr


def test_declared_overlay_is_allowed(tmp_path):
    over = GOOD + textwrap.dedent("""
        [[region]]
        name = "shadow"
        owner = "game.shadow"
        kind = "plane"
        base = 1984
        tiles = 32
        lifetime = "boot"
        overlay_with = ["win"]
        """)
    r = run(tmp_path, over)
    assert r.returncode == 0, r.stderr


def test_quantum_violation_is_an_error(tmp_path):
    bad = GOOD.replace('tiles = 1984\nquantum = 64', 'tiles = 1985\nquantum = 64')
    # keep coverage consistent for the changed size
    bad = bad.replace('base = 1984\ntiles = 32\nlifetime = "act"\nconst = "VRAM_WIN"',
                      'base = 1985\ntiles = 31\nlifetime = "act"\nconst = "VRAM_WIN"')
    r = run(tmp_path, bad)
    assert r.returncode != 0
    assert "quantum" in r.stderr


def test_missing_markers_is_an_error(tmp_path):
    r = run(tmp_path, GOOD, emp_text="// a file with no markers\n")
    assert r.returncode != 0
    assert "marker" in r.stderr.lower()


def test_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    for d in (a, b):
        r = run(d, GOOD)
        assert r.returncode == 0, r.stderr
    assert (a / "constants.emp").read_text() == (b / "constants.emp").read_text()
    assert (a / "map.md").read_text() == (b / "map.md").read_text()


def test_py_mirror_emits_constants(tmp_path):
    r = run(tmp_path, GOOD, extra=["--py", str(tmp_path / "vram_map.py")])
    assert r.returncode == 0, r.stderr
    ns = {}
    exec((tmp_path / "vram_map.py").read_text(), ns)
    assert ns["REGIONS"]["win"]["base"] == 1984
    assert ns["VRAM_WIN"] == 1984


def test_real_sonic4_map_verifies_and_matches_reality(tmp_path):
    """The committed contract must verify AND reproduce today's constants."""
    import shutil
    emp_src = os.path.join(REPO, "games/sonic4/config/constants.emp")
    # run against a COPY so the repo is never written by tests
    shutil.copy(emp_src, tmp_path / "constants.emp")
    toml = os.path.join(REPO, "games/sonic4/vram.toml")
    r = subprocess.run([sys.executable, GEN, "--toml", toml,
                        "--emp", str(tmp_path / "constants.emp"),
                        "--map-doc", str(tmp_path / "map.md"),
                        "--game", "sonic4"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    emp = (tmp_path / "constants.emp").read_text()
    for expected in ("pub const VRAM_TEST_SONIC", "$03C0",
                     "pub const VRAM_TEST_OBJ", "$03E0",
                     "pub const VRAM_TEST_MARKER", "$03F8",
                     "pub const VRAM_TAILS_APPENDAGE", "$05D4"):
        assert expected in emp, expected
```

Note for the implementer: this last test requires Task 3's markers to exist in the real `constants.emp`; until then it fails on the marker check — that ordering is intentional (it goes green during Task 3).

- [ ] **Step 2: Run to verify failure**

```bash
python3 -m pytest tools/test_gen_vram_map.py -q
```
Expected: ERRORs — `gen_vram_map.py` does not exist.

- [ ] **Step 3: Write the generator**

Create `tools/gen_vram_map.py`:

```python
#!/usr/bin/env python3
"""gen_vram_map.py — the VRAM registry generator (linker T0, spec 2026-08-11).

Reads a game's vram.toml (the declared placement contract), VERIFIES it, and
EMITS:
  --emp      rewrite the GENERATED marker block inside the game's constants.emp
  --map-doc  the human-readable occupancy map (markdown)
  --py       the Python mirror (tools/vram_map.py) — sonic4 only; the build
             tools import their budget constants from it instead of restating
             them (this retires the four independent copies of the BG '448')

Checks (all build-stopping):
  * bounds     — every region/free run inside tiles 0..2047
  * coverage   — every tile is a region or a DECLARED [[free]] run; gaps are
                 errors naming the exact run, so free space is intentional
  * overlap    — two regions may not share tiles unless one names the other in
                 overlay_with (T0 accepts only statically-safe overlays; T2
                 adds lifetime checking)
  * quantum    — a region with quantum = N must have tiles % N == 0

Deterministic: no timestamps, sorted iteration; two runs are byte-identical.
Region bases are REQUIRED at T0 (everything pinned); the T1 solver in sigil's
chainer introduces floating regions.
"""

import argparse
import sys
import tomllib

TOTAL_TILES = 2048
MARK_BEGIN = "// >>> GENERATED: vram map (tools/gen_vram_map.py) — DO NOT HAND-EDIT <<<"
MARK_END = "// <<< GENERATED: vram map END >>>"


def fail(msg):
    print(f"gen_vram_map: {msg}", file=sys.stderr)
    sys.exit(1)


def load(toml_path):
    with open(toml_path, "rb") as f:
        data = tomllib.load(f)
    regions = data.get("region", [])
    frees = data.get("free", [])
    for r in regions:
        for k in ("name", "owner", "kind", "base", "tiles", "lifetime"):
            if k not in r:
                fail(f"region {r.get('name','<unnamed>')!r} missing field {k!r}")
    for fr in frees:
        for k in ("base", "tiles"):
            if k not in fr:
                fail(f"[[free]] entry missing field {k!r}")
    return regions, frees


def verify(regions, frees):
    for r in regions:
        if not (0 <= r["base"] and r["base"] + r["tiles"] <= TOTAL_TILES):
            fail(f"region {r['name']!r} [{r['base']}..{r['base']+r['tiles']-1}] "
                 f"leaves 0..{TOTAL_TILES-1}")
        q = r.get("quantum")
        if q and r["tiles"] % q != 0:
            fail(f"region {r['name']!r}: tiles={r['tiles']} violates quantum {q}")

    # overlap: pairwise interval check, exempting declared overlays (either way)
    def overlaid(a, b):
        return b["name"] in a.get("overlay_with", []) or \
               a["name"] in b.get("overlay_with", [])
    rs = sorted(regions, key=lambda r: (r["base"], r["name"]))
    for i, a in enumerate(rs):
        for b in rs[i + 1:]:
            if b["base"] >= a["base"] + a["tiles"]:
                break
            if not overlaid(a, b):
                fail(f"regions {a['name']!r} and {b['name']!r} overlap at "
                     f"tile {b['base']} and neither declares overlay_with the other")

    # coverage: non-overlay occupancy + declared frees must tile 0..2047 exactly
    owned = [False] * TOTAL_TILES
    for r in rs:
        for t in range(r["base"], r["base"] + r["tiles"]):
            owned[t] = True
    for fr in frees:
        for t in range(fr["base"], fr["base"] + fr["tiles"]):
            if owned[t]:
                fail(f"[[free]] run at {fr['base']} overlaps a region at tile {t}")
            owned[t] = True
    t = 0
    while t < TOTAL_TILES:
        if not owned[t]:
            start = t
            while t < TOTAL_TILES and not owned[t]:
                t += 1
            fail(f"tiles {start}..{t-1} are neither a region nor a declared "
                 f"[[free]] run — declare them (free space must be intentional)")
        t += 1


def emit_emp_block(regions, game):
    lines = [MARK_BEGIN,
             f"// Emitted from games/{game}/vram.toml — edit THAT, then run:",
             f"//   python3 tools/gen_vram_map.py --game {game}",
             "// The map doc: docs/generated/vram-map-" + game + ".md"]
    for r in sorted(regions, key=lambda r: (r["base"], r["name"])):
        c = r.get("const")
        if c:
            lines.append(
                f"pub const {c:<24}: VramTile = ${r['base']:04X}"
                f"   // {r['name']}: tiles {r['base']}..{r['base']+r['tiles']-1}"
                f" ({r['tiles']}), {r['lifetime']}, owner {r['owner']}")
    # walls: each const-emitting region must end at or before its successor
    lines.append("// Walls — regeneration re-checks every adjacency:")
    rs = sorted((r for r in regions if not r.get("overlay_with")),
                key=lambda r: r["base"])
    for a, b in zip(rs, rs[1:]):
        ca = a.get("const")
        if ca:
            lines.append(
                f"ensure({ca} + {a['tiles']} <= ${b['base']:04X},"
                f" \"{a['name']} runs into {b['name']}\")")
    lines.append(MARK_END)
    return "\n".join(lines) + "\n"


def splice(emp_path, block):
    src = open(emp_path).read()
    b, e = src.find(MARK_BEGIN), src.find(MARK_END)
    if b < 0 or e < 0:
        fail(f"{emp_path}: GENERATED markers not found — add the two marker "
             f"lines by hand once (see the plan, Task 3)")
    open(emp_path, "w").write(src[:b] + block + src[e + len(MARK_END) + 1:])


def emit_map_doc(regions, frees, game, path):
    rows = []
    for r in regions:
        rows.append((r["base"], r["base"] + r["tiles"] - 1, r["name"],
                     r["kind"], r["lifetime"], r["owner"],
                     r.get("const") or r.get("authority", ""),
                     "overlay: " + ",".join(r["overlay_with"]) if r.get("overlay_with") else ""))
    for fr in frees:
        rows.append((fr["base"], fr["base"] + fr["tiles"] - 1, "FREE",
                     "", "", "", "", ""))
    rows.sort()
    out = [f"# VRAM map — {game}", "",
           f"GENERATED by tools/gen_vram_map.py from games/{game}/vram.toml.",
           "Do not edit; edit the TOML and regenerate.", "",
           "| tiles | name | kind | lifetime | owner | constant / authority | notes |",
           "|---|---|---|---|---|---|---|"]
    for (a, b, name, kind, life, owner, const, note) in rows:
        out.append(f"| {a}-{b} | {name} | {kind} | {life} | {owner} | {const} | {note} |")
    free_total = sum(fr["tiles"] for fr in frees)
    out += ["", f"Free: {free_total} tiles across {len(frees)} runs."]
    open(path, "w").write("\n".join(out) + "\n")


def emit_py(regions, frees, game, path):
    out = ["# GENERATED by tools/gen_vram_map.py from games/%s/vram.toml — do not edit." % game,
           "# Build tools import budget constants from HERE (one authority),",
           "# instead of restating them (the four-copies-of-448 incident).",
           "REGIONS = {"]
    for r in sorted(regions, key=lambda r: (r["base"], r["name"])):
        out.append(f"    {r['name']!r}: {{'base': {r['base']}, 'tiles': {r['tiles']}, "
                   f"'lifetime': {r['lifetime']!r}}},")
    out.append("}")
    by = {r["name"]: r for r in regions}
    out.append(f"POOL_TILE_CEILING = {by['fg_art_pool']['base'] + by['fg_art_pool']['tiles']}"
               if "fg_art_pool" in by else "")
    if "bg_region" in by:
        out.append(f"BG_TILE_BASE_SLOT = {by['bg_region']['base']}")
        out.append(f"BG_TILE_CAPACITY = {by['bg_region']['tiles']}")
    for r in regions:
        if r.get("const"):
            out.append(f"{r['const']} = {r['base']}")
    open(path, "w").write("\n".join(x for x in out if x) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--toml")
    ap.add_argument("--emp")
    ap.add_argument("--map-doc")
    ap.add_argument("--py")
    a = ap.parse_args()
    toml = a.toml or f"games/{a.game}/vram.toml"
    regions, frees = load(toml)
    verify(regions, frees)
    if a.emp:
        splice(a.emp, emit_emp_block(regions, a.game))
    if a.map_doc:
        emit_map_doc(regions, frees, a.game, a.map_doc)
    if a.py:
        emit_py(regions, frees, a.game, a.py)
    print(f"gen_vram_map: {a.game} OK — {len(regions)} regions, "
          f"{sum(f['tiles'] for f in frees)} free tiles")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests**

```bash
python3 -m pytest tools/test_gen_vram_map.py -q
```
Expected: all pass EXCEPT `test_real_sonic4_map_verifies_and_matches_reality` (markers not yet in the real file — goes green in Task 3). If others fail, fix the generator, not the tests.

- [ ] **Step 5: Commit**

```bash
git branch --show-current
git add tools/gen_vram_map.py tools/test_gen_vram_map.py
git commit -m "feat(tools): the VRAM registry generator — verify + emit, deterministic

Full-coverage (gaps are errors naming the run), overlap-unless-declared-overlay,
quantum fit, intentional free list. Emits the constants marker block, the map
doc, and the Python mirror. Tests write to tmp_path only; the real-map test
goes green when Task 3 lands the markers."
```

---

## Task 3: Markers in, generated outputs committed, byte-identity gate #1

**Files:**
- Modify: `games/sonic4/config/constants.emp` (the four `VRAM_*` consts + their walls move inside markers; one `use` addition)
- Modify: `games/demo/config/constants.emp` (`VRAM_DEMO_OBJ` inside markers)
- Create (generated): `docs/generated/vram-map-sonic4.md`, `docs/generated/vram-map-demo.md`, `tools/vram_map.py`

- [ ] **Step 1: Place the markers in `games/sonic4/config/constants.emp`**

Delete the hand `VRAM_TEST_SONIC`, `VRAM_TEST_OBJ`, `VRAM_TEST_MARKER`, `VRAM_TAILS_APPENDAGE` declarations *and* the two appendage `ensure`s (the generator re-emits walls), replacing that whole span with exactly:

```
// >>> GENERATED: vram map (tools/gen_vram_map.py) — DO NOT HAND-EDIT <<<
// <<< GENERATED: vram map END >>>
```

Keep every surrounding comment that explains WHY (the window-sizing prose, the SAT-gap prose) ABOVE the markers — the generator owns values and walls, not rationale. The existing file's `use engine.constants` imports already cover the names the walls reference (`VRAM_SPRITE_TABLE`, `MAX_VDP_SPRITES`, `VRAM_HSCROLL_TABLE`, `TILE_SIZE`); if the compiler reports a missing name after generation, add it to that `use` list — a hand edit outside the markers.

- [ ] **Step 2: Same for `games/demo/config/constants.emp`** — `VRAM_DEMO_OBJ` moves inside a marker pair.

- [ ] **Step 3: Generate everything**

```bash
mkdir -p docs/generated
python3 tools/gen_vram_map.py --game sonic4 \
  --toml games/sonic4/vram.toml \
  --emp games/sonic4/config/constants.emp \
  --map-doc docs/generated/vram-map-sonic4.md \
  --py tools/vram_map.py
python3 tools/gen_vram_map.py --game demo \
  --toml games/demo/vram.toml \
  --emp games/demo/config/constants.emp \
  --map-doc docs/generated/vram-map-demo.md
python3 -m pytest tools/test_gen_vram_map.py -q
```
Expected: both `OK`; the full pytest suite now 9/9 including the real-map test.

- [ ] **Step 4: THE GATE — byte-identical builds**

```bash
./build.sh && DEBUG=1 ./build.sh && DEBUG=1 ./build.sh demo
S=$(ls -d /tmp/claude-1000/*/*/scratchpad 2>/dev/null | head -1)
for f in s4.bin s4.debug.bin demo.debug.bin; do
  python3 -c "import zlib;print('$f', format(zlib.crc32(open('$f','rb').read()),'08x'))"
done | diff - "$S/vram-t0-baseline.txt" && echo "BYTE-IDENTICAL" || echo "MOVED — STOP"
```
Expected: `BYTE-IDENTICAL`. If MOVED: a generated value differs from the hand value it replaced — diff the constants block against `git show HEAD:games/sonic4/config/constants.emp`, fix the TOML (never the generator output), regenerate. **Do not proceed with moved bytes.**

- [ ] **Step 5: Commit**

```bash
git branch --show-current
git add games/sonic4/config/constants.emp games/demo/config/constants.emp \
        docs/generated/vram-map-sonic4.md docs/generated/vram-map-demo.md \
        tools/vram_map.py
git commit -m "feat(vram): constants generated from the contract — byte-identical capture

The game-side VRAM_* values now live in a GENERATED marker block emitted from
vram.toml (values + adjacency walls); the rationale prose stays hand-owned
above the markers. The map doc that never existed now exists and cannot rot.
Gate: all three shapes byte-identical to the Task-0 baseline."
```

---

## Task 4: Collapse the Python copies

**Files:**
- Modify: `tools/ojz_strip_gen.py:123-124` and `:263-264`
- Modify: `tools/inject_editor_bg.py:18,21`
- Modify: `tools/png_to_bg_override.py:33`

- [ ] **Step 1: Repoint `ojz_strip_gen.py`** — replace the two literal blocks with imports (it already does `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` at line 48, so a bare import works):

```python
# POOL_TILE_CEILING / BG_* now come from the generated registry mirror —
# ONE authority (tools/vram_map.py <- games/sonic4/vram.toml). The engine-side
# constant is cross-checked by the generated ensure in config/constants.emp.
from vram_map import POOL_TILE_CEILING, BG_TILE_BASE_SLOT, BG_TILE_CAPACITY
```
Delete the local `POOL_TILE_CEILING = 960` (line 124) and `BG_TILE_BASE_SLOT_PY`/`BG_TILE_CAPACITY_PY` literals (lines 263-264), renaming their uses to the imported names (the `_PY` suffix dies).

- [ ] **Step 2: Repoint `inject_editor_bg.py` and `png_to_bg_override.py`** the same way (both need the `sys.path.insert` line added first if absent — copy it from `ojz_strip_gen.py:48`).

- [ ] **Step 3: Prove behavior is unchanged**

```bash
python3 -m pytest tools/test_bg_emit.py tools/test_s4budget.py -q  # nearest suites
python3 tools/gen_vram_map.py --game sonic4 --toml games/sonic4/vram.toml --py tools/vram_map.py
./build.sh && DEBUG=1 ./build.sh
git status --short   # generated OJZ data must NOT be dirty
```
Expected: tests pass, builds byte-identical to baseline again (compare as in Task 3 Step 4), no generated data dirtied. The daemon may auto-commit `ojz_strip_gen.py` mid-task — check `git log --oneline -3` and adapt (reference its commit; never `--amend`).

- [ ] **Step 4: Commit**

```bash
git branch --show-current
git add tools/ojz_strip_gen.py tools/inject_editor_bg.py tools/png_to_bg_override.py
git commit -m "fix(tools): budget constants imported from the registry mirror

Kills the four independent hand-copies of the BG '448' (one .emp + three
Python literals) and ojz_strip_gen's POOL_TILE_CEILING copy: the tools now
import from the generated tools/vram_map.py. Byte-identical builds; no
generated data moved."
```

---

## Task 5: The carve — the first deliberate layout change (CONTROLLER runs the gates)

This re-lands the dust VRAM decision that broke as Task 2 of the dust plan — now safe: the prep parcel (`5129060c`) made pool resizes RAM-neutral and the replay hash layout-proof.

**Files:**
- Modify: `games/sonic4/vram.toml` (pool 960→896; dust regions; the freed spare)
- Modify: `engine/system/constants.emp:595` (`POOL_TILE_CEILING` 960→896 — authority stays engine-side; the generated walls make a mismatch loud)
- Regenerated: the sonic4 constants block, map doc, `tools/vram_map.py`

- [ ] **Step 1: Edit `games/sonic4/vram.toml`** — change `fg_art_pool` to `tiles = 896`, then insert after it:

```toml
[[region]]
name = "dust_puff"
owner = "games.sonic4.dust_puff"
kind = "window"
base = 896
tiles = 16
lifetime = "act"
const = "VRAM_DUST_PUFF"
# resident block: concurrent puffs sit on DIFFERENT anim frames, so all four
# frames must be live at once, addressed 0/4/8/$C from this base (dust spec §4)

[[region]]
name = "dust_spindash"
owner = "games.sonic4.dust_spindash"
kind = "window"
base = 912
tiles = 12
lifetime = "act"
const = "VRAM_DUST_SPINDASH"

[[free]]
base = 924
tiles = 36
# the page-quantised carve's remainder — future sprite art
```

- [ ] **Step 2: Edit `engine/system/constants.emp:595`** — `POOL_TILE_CEILING` 960 → 896, updating its comment to note tiles 896-923 are the dust windows and 924-959 spare, per the map doc. (`PAGE_FRAMES` derives to 14; the arrays are `PAGE_FRAMES_MAX`-sized, so **RAM does not move** — that is the prep parcel's guarantee.)

- [ ] **Step 3: Regenerate + build**

```bash
python3 tools/gen_vram_map.py --game sonic4 --toml games/sonic4/vram.toml \
  --emp games/sonic4/config/constants.emp \
  --map-doc docs/generated/vram-map-sonic4.md --py tools/vram_map.py
SIGIL_BLOB_LEN_DRIFT=warn ./build.sh && SIGIL_BLOB_LEN_DRIFT=warn DEBUG=1 ./build.sh && DEBUG=1 ./build.sh demo
```
Expected: builds green, no blob warning. ROM bytes move (the `PAGE_FRAMES` loop immediates) — that is this task's point. `ojz_strip_gen.py` needs no edit: it imports the ceiling now.

- [ ] **Step 4 (CONTROLLER ONLY): the replay gates.** Both fixtures on debug, standing on release, per the standing recipe (bp `GameState_OJZScroll_Init` BEFORE reset; arm `0xFF803A=1`, `Replay_Ptr` = fixture+20 as hex bytes; re-derive fixture addresses from the FRESH `.lst`, 24-bit masked; read back before resume). Expected: **PASS with no fixture re-stamp** — the payoff of the prep parcel, and the end-to-end proof the spec names in §11. A desync here is a STOP-and-investigate, not a re-stamp.

- [ ] **Step 5 (CONTROLLER): the sigil ritual**

```bash
cd /home/volence/sonic_hacks/sigil && cargo build --release
export SIGIL_EMIT=$PWD/target/release/emit_sound_blob SIGIL_BUILD=$PWD/target/release/sigil
cargo run -q -p sigil-harness --bin repin        # expect: PAGE_FRAMES-immediate ROM shifts, ZERO RAM pins
cargo run -q -p sigil-harness --bin refreeze -- --freeze vram-t0-carve \
  --ab "aeon@<carve sha> — all three replay gates PASS with NO fixture re-stamp (the layout-proof hash doing its job); RAM byte-identical (PAGE_FRAMES_MAX); movement = PAGE_FRAMES immediates only, map diff in docs/generated/vram-map-sonic4.md" \
  --note "the dust pool carve re-landed as a vram.toml edit: pool 960->896, dust windows at 896/912, 36 spare"
```
Then the aggregate suite (Task 6 Step 2's awk recipe) and the `repin_pins` acceptance baseline: advance its LIVE literals with the parcel tag (the retired/ignored `secondary_pin_classes` test's stale literals stay untouched — precedent `3d1c7f7e`).

- [ ] **Step 6: Commit** (aeon: the TOML, engine constant, regenerated three files; sigil: pins + goldens + provenance + baseline — separate commits, exact paths, message citing the gate results).

---

## Task 6: Docs sync, riders, final sweep

- [ ] **Step 1: Sync `docs/ENGINE_ARCHITECTURE.md`** — the VRAM layout section now defers to the generated maps (`docs/generated/vram-map-<game>.md`) as the living truth, keeping only the design rationale; note the registry (spec `cc053a64`) as the placement mechanism and the 896/dust state as current.

- [ ] **Step 2: Full gate sweep**

```bash
cd /home/volence/sonic_hacks/aeon
./build.sh && DEBUG=1 ./build.sh && DEBUG=1 ./build.sh demo
python3 -m pytest tools/ -q 2>&1 | tail -3
cd /home/volence/sonic_hacks/sigil && export SIGIL_EMIT=$PWD/target/release/emit_sound_blob SIGIL_BUILD=$PWD/target/release/sigil
cargo test -q --release --workspace --no-fail-fast 2>&1 | awk '
/^test result/ { for(i=1;i<=NF;i++){ if($i=="passed;") p+=$(i-1); if($i=="failed;") f+=$(i-1) } }
/^error: test failed, to rerun pass/ { print "FAILING: " $0 }
END { printf "\nTOTAL: %d passed, %d FAILED\n", p, f }'
```
Expected: 0 FAILED (known exception: the 3 `seam2_*` targets under `SIGIL_STRICT_GATE=1` only — inherited sound-bank drift, not this parcel).

- [ ] **Step 3: Ledger the T1 handoff in `docs/DEFERRED_WORK.md`** — the six sigil asks (spec §6), noting S-3 (define emission, replacing the hand ring-placeholder values across native.rs profiles) must land value-neutral; and the rider that `vram.toml` + `map.toml` may merge into one placement contract when the user's broader TOML review happens (their stated intent, 2026-08-11).

- [ ] **Step 4: Commit docs; update the dust plan** — a one-line note at the top of `docs/superpowers/plans/2026-08-11-dust-effect.md`: Task 2 is superseded by the registry carve (this plan's Task 5); dust Tasks 3-6 resume unchanged with `VRAM_DUST_PUFF`/`VRAM_DUST_SPINDASH` now provided by the registry.

---

## Notes for whoever executes this

- **Byte-identity failures in Tasks 3-4 are always a wrong VALUE, never a wrong mechanism** — the marker block emits constants with identical names/types/values; if bytes move, diff the block against git and fix the TOML.
- The generator's `verify()` walks per-tile arrays (2048 booleans); do not "optimize" it — clarity is the point at this size.
- If the sonic4 `constants.emp` `use` list lacks a name a generated wall references, add the import by hand ABOVE the markers; the generator never touches imports.
- `POOL_TILE_CEILING` authority stays engine-side at T0 (the generated block cross-checks it). Moving authority into the registry is T1/T2 business — do not do it opportunistically.
- If a comptime `ensure` fires, fix the cause, never the ensure.
