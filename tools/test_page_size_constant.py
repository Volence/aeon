"""PAGE-SIZE-CONSTANT-ONLY (2026-09-17): the bake/verify path takes the act art pool's
page size from the ENGINE, so a page-size change (the owner's open card FG-CACHE-10-HOW:
12 frames x 64-tile pages or 20 frames x 32-tile pages) is a constant change on the
tooling side.

What is proved here, and how:

  * verify_level_bin.py is loaded FRESH from a copy whose ROOT is a scratch tree holding
    the real engine/system/constants.emp with ONE line changed (ART_POOL_PAGE_TILES), and
    its act-pool and local-map checks run on a small synthetic pool baked at a chosen page
    size. Under a 32-tile constant a 32-tile tree passes; under the real constant (64) the
    same tree fails, and under a 32-tile constant a 64-tile tree fails. The page size is
    never typed into the verifier's side of this test: it comes out of the constants file
    through the module's own module-level derivation.
  * regenerate-level.sh's page-size guard is driven for real in a scratch git repository
    with stub tools (the test_baker_refusals.py pattern): a 2048-byte page is refused under
    a 32-tile constant and admitted under the real one.

Runner: build.sh's pre-build `pytest tools -m "not needs_build"` lane (tools/landing_build.sh
runs it once, inside the first shape). Needs no build and no donor.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from fg_working_set import ConstantSource  # noqa: E402

REAL_CONSTANTS = os.path.join(HERE, "..", "engine", "system", "constants.emp")
PAGE_LINE = re.compile(r"^(pub const ART_POOL_PAGE_TILES\s*=\s*)(\d+)", re.M)


def _real_constant(name):
    src = ConstantSource()
    src.load_file(REAL_CONSTANTS)
    return src.get(name)


REAL_PAGE_TILES = _real_constant("ART_POOL_PAGE_TILES")
TILE_SIZE = _real_constant("TILE_SIZE")
ALT_PAGE_TILES = 32     # the card's other option; the test's own subject, not a restated pin


def _write_constants(root, page_tiles):
    """The real constants.emp with the ART_POOL_PAGE_TILES line set to page_tiles."""
    text = open(REAL_CONSTANTS).read()
    new, n = PAGE_LINE.subn(lambda m: f"{m.group(1)}{page_tiles}", text)
    assert n == 1, "constants.emp no longer defines ART_POOL_PAGE_TILES on one literal line"
    dst = root / "engine" / "system" / "constants.emp"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(new)
    return dst


def _load_verifier(root, page_tiles):
    """A fresh verify_level_bin whose ROOT (and therefore constants.emp) is `root`."""
    _write_constants(root, page_tiles)
    tools = root / "tools"
    tools.mkdir(exist_ok=True)
    shutil.copy(os.path.join(HERE, "verify_level_bin.py"), tools / "verify_level_bin.py")
    name = f"_vlb_page_size_{page_tiles}_{abs(hash(str(root)))}"
    spec = importlib.util.spec_from_file_location(name, tools / "verify_level_bin.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _bake_pool(gen, page_tiles, last_page_tiles):
    """A two-page raw-form pool as regenerate-level.sh + ojz_strip_gen emit it, baked at
    `page_tiles`, plus a one-section local map whose third entry is a slot in page 1."""
    gen.mkdir(parents=True, exist_ok=True)
    tiles = [page_tiles, last_page_tiles]
    (gen / "ojz_act_pool_manifest.emp").write_text("pub const OJZ_ACT_POOL_PAGES = 2\n")
    lines = ["module games.sonic4.ojz_act_pool_act1 in ojz_act_pool", ""]
    for k in range(2):
        payload = bytes((k * 37 + i) & 0xFF for i in range(tiles[k] * TILE_SIZE))
        (gen / f"act_pool_page{k}.bin").write_bytes(payload)
        (gen / f"act_pool_page{k}.raw").write_bytes(payload)
        lines.append(f'pub data OJZ_Act_Pool_Page{k} = embed("{gen}/act_pool_page{k}.raw")')
    lines.append("pub data OJZ_Act_Pool_PageTable: [PageManifest; 2] = [")
    for k in range(2):
        lines.append(f'  PageManifest{{ pm_source: extern("OJZ_Act_Pool_Page{k}"), '
                     f'pm_tiles: {tiles[k]}, pm_form: 1, pm_flags: {1 if k == 0 else 0} }},')
    lines.append("]")
    (gen / "ojz_act_pool.emp").write_text("\n".join(lines) + "\n")
    (gen / "ojz_act_pool_manifest.json").write_text(json.dumps({
        "version": 2, "page_tiles": page_tiles, "page_bytes": page_tiles * TILE_SIZE,
        "pages": [{"index": k, "tiles": tiles[k], "pinned": k == 0} for k in range(2)]}))
    (gen / "sec_local_maps.emp").write_text(
        'pub data OJZ_Sec0_LocalMap = embed("sec0_local_map.bin")\n'
        'pub data OJZ_Sec_LocalMaps: [*u8; 1] = [extern("OJZ_Sec0_LocalMap")]\n')
    # global slot = page * page_tiles + index; page 1, index 3 is inside its last_page_tiles
    slots = [0, 1, page_tiles + 3]
    (gen / "sec0_local_map.bin").write_bytes(b"".join(s.to_bytes(2, "big") for s in slots))


def _verify(mod, gen):
    mod.GEN = str(gen)
    mod._fail = []
    mod._section_count = lambda: 1
    mod.verify_act_pool()
    mod.verify_local_maps()
    return list(mod._fail)


def test_the_verifier_reads_the_page_size_from_the_engine(tmp_path):
    """Converse control: the unmodified constant loads as the engine's own value."""
    mod = _load_verifier(tmp_path, REAL_PAGE_TILES)
    assert (mod.ART_POOL_PAGE_TILES, mod.ART_POOL_PAGE_BYTES) == (
        REAL_PAGE_TILES, _real_constant("ART_POOL_PAGE_BYTES"))


def test_a_tree_baked_at_the_engine_page_size_passes(tmp_path):
    """Control for the fixture itself, at the shipped page size."""
    mod = _load_verifier(tmp_path, REAL_PAGE_TILES)
    gen = tmp_path / "gen"
    _bake_pool(gen, REAL_PAGE_TILES, REAL_PAGE_TILES // 2)
    assert _verify(mod, gen) == []


def test_a_32_tile_tree_passes_under_a_32_tile_constant(tmp_path):
    mod = _load_verifier(tmp_path, ALT_PAGE_TILES)
    assert mod.ART_POOL_PAGE_BYTES == ALT_PAGE_TILES * TILE_SIZE
    gen = tmp_path / "gen"
    _bake_pool(gen, ALT_PAGE_TILES, ALT_PAGE_TILES // 2)
    assert _verify(mod, gen) == []


def test_a_32_tile_tree_fails_under_the_real_constant(tmp_path):
    assert REAL_PAGE_TILES != ALT_PAGE_TILES, "the engine already ships the alternative"
    mod = _load_verifier(tmp_path, REAL_PAGE_TILES)
    gen = tmp_path / "gen"
    _bake_pool(gen, ALT_PAGE_TILES, ALT_PAGE_TILES // 2)
    fails = _verify(mod, gen)
    assert any("sidecar page_bytes" in f for f in fails), fails
    # the page-1 slot reads as an index past page 0's pm_tiles under the wrong page size
    assert any("outside the pool's pages" in f for f in fails), fails


def test_a_real_size_tree_fails_under_a_32_tile_constant(tmp_path):
    mod = _load_verifier(tmp_path, ALT_PAGE_TILES)
    gen = tmp_path / "gen"
    _bake_pool(gen, REAL_PAGE_TILES, REAL_PAGE_TILES // 2)
    fails = _verify(mod, gen)
    assert any("page0.bin is" in f and "> one page" in f for f in fails), fails
    assert any("sidecar page_bytes" in f for f in fails), fails


# ---------------------------------------------------------------------------
# regenerate-level.sh's page-size guard, run for real with stub tools
# ---------------------------------------------------------------------------

_GEN_STUB = r'''
import json, os, sys
if sys.argv[1] == "preflight":
    sys.exit(0)
gen = "games/sonic4/data/generated/ojz/act1"
os.makedirs(gen, exist_ok=True)
n = int(os.environ["STUB_PAGE_BYTES"])
open(f"{gen}/act_pool_page0.bin", "wb").write(bytes(i & 0xFF for i in range(n)))
open(f"{gen}/ojz_act_pool_manifest.emp", "w").write("pub const OJZ_ACT_POOL_PAGES = 1\n")
json.dump({"pages": [{"index": 0, "tiles": n // 32, "pinned": True}]},
          open(f"{gen}/ojz_act_pool_manifest.json", "w"))
'''


def _rebake(tmp_path, page_tiles, page_bytes):
    repo = tmp_path / "repo"
    (repo / "tools").mkdir(parents=True)
    shutil.copy(os.path.join(HERE, "regenerate-level.sh"), repo / "tools" / "regenerate-level.sh")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    stubs = repo / "stubs"
    (stubs / "bin").mkdir(parents=True)
    salv = stubs / "bin" / "salvador"
    salv.write_text("#!/bin/sh\ncp \"$1\" \"$2\"\n")
    salv.chmod(0o755)
    (stubs / "ojz_strip_gen.py").write_text(_GEN_STUB)
    for name in ("import_sk_collision.py", "effects_gen.py", "ojz_block_gen.py",
                 "verify_level_bin.py", "fg_page_order.py", "level_staleness.py"):
        (stubs / name).write_text("")
    # NOT a stub: the page-size guard this file exists to drive MOVED out of
    # regenerate-level.sh's bash into tools/elect_pool_pages.py on 2026-09-17 (so a clip
    # act could elect its pages through the same emitter). Stubbing it would make these
    # three rows test nothing at all — the subject has to be the real one.
    shutil.copy(os.path.join(HERE, "elect_pool_pages.py"), stubs / "elect_pool_pages.py")
    shutil.copy(os.path.join(HERE, "fg_working_set.py"), stubs / "fg_working_set.py")
    _write_constants(repo, page_tiles)
    for sub in ("collision", "generated"):
        (repo / "games" / "sonic4" / "data" / sub).mkdir(parents=True, exist_ok=True)
    snap = tmp_path / "tmpdir"
    snap.mkdir()
    env = dict(os.environ, TOOLS="stubs", STUB_PAGE_BYTES=str(page_bytes), TMPDIR=str(snap))
    return subprocess.run(["bash", "tools/regenerate-level.sh"], cwd=repo, env=env,
                          capture_output=True, text=True)


def test_rebake_admits_a_full_page_at_the_engine_page_size(tmp_path):
    """Control: the stub harness completes when the page fits."""
    p = _rebake(tmp_path, REAL_PAGE_TILES, REAL_PAGE_TILES * TILE_SIZE)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "exceeds one page" not in p.stdout + p.stderr


def test_rebake_refuses_a_real_size_page_under_a_32_tile_constant(tmp_path):
    p = _rebake(tmp_path, ALT_PAGE_TILES, REAL_PAGE_TILES * TILE_SIZE)
    assert p.returncode != 0, p.stdout + p.stderr
    # stdout + stderr: the guard now refuses from a Python tool, which prints its
    # refusal on stderr; the bash it replaced echoed on stdout. The subject is the
    # guard, not the stream it speaks through.
    assert f"exceeds one page ({ALT_PAGE_TILES * TILE_SIZE})" in p.stdout + p.stderr, \
        p.stdout + p.stderr


def test_rebake_admits_a_full_32_tile_page_under_a_32_tile_constant(tmp_path):
    p = _rebake(tmp_path, ALT_PAGE_TILES, ALT_PAGE_TILES * TILE_SIZE)
    assert p.returncode == 0, p.stdout + p.stderr
