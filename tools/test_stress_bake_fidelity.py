"""STRESS-UNIQUIFY-REBAKE (2026-09-17): the editor-bake fidelity check verifies a
STRESS_ART bake as a stress bake, and still refuses a wrong pixel in it.

WHY THIS EXISTS. `STRESS_UNIQUIFY=2600 tools/regenerate-level.sh` exited 1 from
2026-09-05 (8706d8f2, the editor-bake fidelity check) until this parcel: the stress
fixture's clones are deliberately one byte off their parent tile, and the check held
them to the editor's pixels as-is. MEASURED on the real stress bake: 1988 mismatched
word shapes, all on the 1988 clone slots, each exactly one byte off, none on a real slot.
Nothing ran the stress re-bake, so nothing saw it for twelve days.

THE RULE UNDER TEST (verify_level_bin._stress_clone_scratch). ojz_strip_gen declares each
clone [slot, parent, byte_offset, xor] in stress_clones.json; under --stress the verifier
checks that declaration against the pool bytes, undoes that one byte, and still compares
with the editor. Both keys are required: --stress without the sidecar fails, the sidecar
on a canonical verify fails.

THE FIXTURE, donor-free. The committed canonical tree (editor tileset + section
nametables, generated strips / local maps / pool pages) is copied to a scratch root, and a
stress bake is SYNTHESISED on it the way ojz_strip_gen's Pass 4b does: for a spread of
non-blank word positions, the position's own tile is cloned with one byte XORed, the clone
is appended to the pool, the section's local map gains an entry for it, and the strips_a
word is re-pointed at that entry with its flip/attribute bits kept. Every expectation is
derived from that tree (which slot, which byte), never pinned.

Red-first: against the pre-fix verifier (5608170e^) the stress control fails with
"resolves N distinct word shape(s) to DIFFERENT pixels", N = the clones synthesised.

Runner: build.sh's pre-build `pytest tools -m "not needs_build"` lane (tools/landing_build.sh
runs it once, inside the first shape). Needs no build and no donor.
"""
import json
import os
import shutil
import struct
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import verify_level_bin as vlb  # noqa: E402  (donor-free by contract)

REAL_GEN = vlb.GEN
REL_GEN = os.path.relpath(vlb.GEN, vlb.ROOT)
TS = vlb.TILE_SIZE
N_CLONES = 24


def _generator_sidecar_name():
    """The sidecar name from the GENERATOR's source (ojz_strip_gen imports the donor, so it
    is parsed, not imported, as verify_level_bin._strip_gen_int does)."""
    import re
    m = re.search(r'^STRESS_CLONES_SIDECAR\s*=\s*"([^"]+)"',
                  open(os.path.join(HERE, "ojz_strip_gen.py")).read(), re.M)
    assert m, "ojz_strip_gen.py no longer defines STRESS_CLONES_SIDECAR as a string literal"
    return m.group(1)


SIDECAR = _generator_sidecar_name()


def test_verifier_reads_the_sidecar_the_generator_writes():
    assert getattr(vlb, "STRESS_CLONES_SIDECAR", None) == SIDECAR


def _stride():
    rows = vlb._strip_gen_int("STRIP_TILE_HEIGHT")
    pad = vlb._strip_gen_int("STRIP_COLLISION_PAD")
    assert rows is not None and pad is not None, "strip layout unreadable from ojz_strip_gen"
    return rows, rows * 2 + 2 * (rows // 2) + pad


def _canonical_tree(tmp_path):
    with open(os.path.join(REPO, "project.json")) as f:
        zone = json.load(f)["zones"][0]
    act = zone["acts"][0]
    n = act["gridWidth"] * act["gridHeight"]
    root = tmp_path / "tree"
    root.mkdir()
    shutil.copy(os.path.join(REPO, "project.json"), root / "project.json")
    ts = root / zone["tileset"]
    ts.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(os.path.join(REPO, zone["tileset"]), ts)
    ed = root / act["dataPath"]
    ed.mkdir(parents=True, exist_ok=True)
    gen = root / REL_GEN
    gen.mkdir(parents=True)
    for i in range(n):
        shutil.copy(os.path.join(REPO, act["dataPath"], f"section_{i}.tiles.bin"), ed)
        for stem in ("strips_source", "strips_a", "local_map"):
            shutil.copy(os.path.join(REAL_GEN, f"sec{i}_{stem}.bin"), gen)
    pages = sorted((fn for fn in os.listdir(REAL_GEN)
                    if fn.startswith("act_pool_page") and fn.endswith(".bin")),
                   key=lambda fn: int(fn[len("act_pool_page"):-len(".bin")]))
    assert pages, "committed tree has no act_pool_page*.bin"
    for fn in pages:
        shutil.copy(os.path.join(REAL_GEN, fn), gen)
    assert not os.path.exists(os.path.join(REAL_GEN, SIDECAR)), (
        f"the COMMITTED tree carries {SIDECAR}: a stress bake was committed")
    return root, gen, n, pages


def _synthesise_stress(gen, n, pages):
    """Pass 4b on the scratch tree. Returns the clone rows [slot, parent, off, xor] and
    the list of (section, column, row) positions re-pointed."""
    rows, stride = _stride()
    last = gen / pages[-1]
    pool = b"".join((gen / p).read_bytes() for p in pages)
    base = len(pool) // TS
    clones, positions, appended = [], [], bytearray()
    j = 0
    for sec in range(n):
        if j >= N_CLONES:
            break
        rem = bytearray((gen / f"sec{sec}_strips_a.bin").read_bytes())
        lm_raw = (gen / f"sec{sec}_local_map.bin").read_bytes()
        lmap = list(struct.unpack(f">{len(lm_raw) // 2}H", lm_raw))
        # a spread of columns, the first non-blank word in each
        for col in range(0, rows, rows // 3):
            if j >= N_CLONES:
                break
            for row in range(rows):
                off = col * stride + row * 2
                word = struct.unpack_from(">H", rem, off)[0]
                parent = lmap[word & vlb.NAMETABLE_TILE_MASK]
                if parent == 0:
                    continue
                slot = base + j
                byte_off = (j * 4) % TS
                xor = (j & 0xFF) or 0xA5
                tile = bytearray(pool[parent * TS:(parent + 1) * TS])
                tile[byte_off] ^= xor
                appended += tile
                lmap.append(slot)
                struct.pack_into(">H", rem, off,
                                 (word & ~vlb.NAMETABLE_TILE_MASK & 0xFFFF) | (len(lmap) - 1))
                clones.append([slot, parent, byte_off, xor])
                positions.append((sec, col, row))
                j += 1
                break
        (gen / f"sec{sec}_strips_a.bin").write_bytes(bytes(rem))
        (gen / f"sec{sec}_local_map.bin").write_bytes(
            b"".join(v.to_bytes(2, "big") for v in lmap))
    assert j == N_CLONES, f"fixture found only {j} re-pointable positions"
    last.write_bytes(last.read_bytes() + bytes(appended))
    (gen / SIDECAR).write_text(json.dumps({
        "version": 1, "target_tiles": base + j, "base_pool_tiles": base,
        "pool_tiles": base + j, "clones": clones}))
    return clones, positions, pages


def _run(monkeypatch, root, stress):
    monkeypatch.setattr(vlb, "ROOT", str(root))
    monkeypatch.setattr(vlb, "GEN", str(root / REL_GEN))
    monkeypatch.setattr(vlb, "PROJECT_JSON", str(root / "project.json"))
    monkeypatch.setattr(vlb, "STRESS_MODE", stress, raising=False)
    monkeypatch.setattr(vlb, "_fail", [])
    vlb.verify_editor_bake_fidelity()
    return list(vlb._fail)


def _slot_file(gen, pages, slot):
    """(page path, byte offset) of pool slot `slot` in the concatenated pages."""
    at = 0
    for p in pages:
        size = (gen / p).stat().st_size
        if slot * TS < at + size:
            return gen / p, slot * TS - at
        at += size
    raise AssertionError(f"slot {slot} past the pool")


def _xor_byte(path, off, x):
    b = bytearray(path.read_bytes())
    b[off] ^= x
    path.write_bytes(bytes(b))


@pytest.fixture
def stress_tree(tmp_path):
    root, gen, n, pages = _canonical_tree(tmp_path)
    clones, positions, pages = _synthesise_stress(gen, n, pages)
    return root, gen, pages, clones, positions


def test_canonical_tree_passes_canonically(tmp_path, monkeypatch):
    """Control for the scratch copy itself: the committed tree, no flag, no failures."""
    root, _gen, _n, _pages = _canonical_tree(tmp_path)
    assert _run(monkeypatch, root, False) == []


def test_stress_bake_passes_under_stress(stress_tree, monkeypatch):
    """The bug: a faithful stress bake must verify. Red before the fix (every clone was
    reported as wrong art)."""
    root, *_ = stress_tree
    assert _run(monkeypatch, root, True) == []


def test_stress_bake_is_refused_canonically(stress_tree, monkeypatch):
    root, *_ = stress_tree
    fails = _run(monkeypatch, root, False)
    assert any(SIDECAR in f and "CANONICAL verify" in f for f in fails), fails
    assert any("DIFFERENT pixels" in f for f in fails), fails


def test_stress_without_declaration_is_refused(stress_tree, monkeypatch):
    root, gen, *_ = stress_tree
    (gen / SIDECAR).unlink()
    fails = _run(monkeypatch, root, True)
    assert any("no " + SIDECAR in f for f in fails), fails
    assert sum("DIFFERENT pixels" in f for f in fails) > 0, fails


def test_planted_wrong_real_tile_is_refused_under_stress(stress_tree, monkeypatch):
    """A wrong byte in a REAL pool tile a word renders (not a clone parent, so only the
    pixel comparison can see it) is still refused."""
    root, gen, pages, clones, positions = stress_tree
    parents = {c[1] for c in clones}
    base = clones[0][0]
    rows, stride = _stride()
    # a real slot rendered by some sec0 word, not a clone parent
    rem = (gen / "sec0_strips_a.bin").read_bytes()
    lm_raw = (gen / "sec0_local_map.bin").read_bytes()
    lmap = struct.unpack(f">{len(lm_raw) // 2}H", lm_raw)
    target = next(g for g in (lmap[struct.unpack_from(">H", rem, c * stride + r * 2)[0]
                                   & vlb.NAMETABLE_TILE_MASK]
                              for c in range(rows) for r in range(rows))
                  if 0 < g < base and g not in parents)
    path, off = _slot_file(gen, pages, target)
    _xor_byte(path, off + 7, 0x0F)
    fails = _run(monkeypatch, root, True)
    assert any("sec0 resolves" in f and "DIFFERENT pixels" in f for f in fails), fails
    assert not any("NOT their parent" in f for f in fails), fails


def test_clone_with_a_second_wrong_byte_is_refused(stress_tree, monkeypatch):
    root, gen, pages, clones, _pos = stress_tree
    slot, _parent, byte_off, _xor = clones[3]
    path, off = _slot_file(gen, pages, slot)
    _xor_byte(path, off + (byte_off + 9) % TS, 0x11)
    fails = _run(monkeypatch, root, True)
    assert any("NOT their parent" in f and f"[{slot}," in f for f in fails), fails
    assert any("DIFFERENT pixels" in f for f in fails), fails


def test_clone_swapped_for_another_tile_is_refused(stress_tree, monkeypatch):
    root, gen, pages, clones, _pos = stress_tree
    slot, parent = clones[5][0], clones[5][1]
    other = next(c[1] for c in clones if c[1] != parent)
    path, off = _slot_file(gen, pages, slot)
    opath, ooff = _slot_file(gen, pages, other)
    src = opath.read_bytes()[ooff:ooff + TS]
    b = bytearray(path.read_bytes())
    b[off:off + TS] = src
    path.write_bytes(bytes(b))
    fails = _run(monkeypatch, root, True)
    assert any("DIFFERENT pixels" in f for f in fails), fails


def test_unscratched_clone_is_refused(stress_tree, monkeypatch):
    """The clone's raw bytes equal its parent (pixels right, declaration false)."""
    root, gen, pages, clones, _pos = stress_tree
    slot, _parent, byte_off, xor = clones[7]
    path, off = _slot_file(gen, pages, slot)
    _xor_byte(path, off + byte_off, xor)
    fails = _run(monkeypatch, root, True)
    assert any("NOT their parent" in f and f"[{slot}," in f for f in fails), fails


def test_declaration_naming_the_wrong_byte_is_refused(stress_tree, monkeypatch):
    root, gen, _pages, clones, _pos = stress_tree
    decl = json.loads((gen / SIDECAR).read_text())
    decl["clones"][9][2] = (decl["clones"][9][2] + 1) % TS
    (gen / SIDECAR).write_text(json.dumps(decl))
    fails = _run(monkeypatch, root, True)
    assert any("NOT their parent" in f and f"[{clones[9][0]}," in f for f in fails), fails
    assert any("DIFFERENT pixels" in f for f in fails), fails


def test_declared_clone_nothing_renders_is_refused(stress_tree, monkeypatch):
    """Point one re-pointed word back at its parent: the clone stays declared and valid,
    but no word renders it, so the declaration covers art the check never compared."""
    root, gen, _pages, clones, positions = stress_tree
    sec, col, row = positions[0]
    parent = clones[0][1]
    _rows, stride = _stride()
    rem = bytearray((gen / f"sec{sec}_strips_a.bin").read_bytes())
    lm_raw = (gen / f"sec{sec}_local_map.bin").read_bytes()
    lmap = struct.unpack(f">{len(lm_raw) // 2}H", lm_raw)
    off = col * stride + row * 2
    word = struct.unpack_from(">H", rem, off)[0]
    struct.pack_into(">H", rem, off,
                     (word & ~vlb.NAMETABLE_TILE_MASK & 0xFFFF) | lmap.index(parent))
    (gen / f"sec{sec}_strips_a.bin").write_bytes(bytes(rem))
    fails = _run(monkeypatch, root, True)
    assert any("rendered by no" in f and f"first slot {clones[0][0]}" in f for f in fails), fails
    assert not any("DIFFERENT pixels" in f for f in fails), fails
