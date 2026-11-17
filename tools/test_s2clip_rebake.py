"""Pre-build lane tests for tools/s2clip_rebake.py and leg_run.StreamLoad (v2 C4 fix 1, M4).
No donors, no emulator: a throwaway git repo stands in for the aeon root, and the bake
subprocess is stubbed, so the refusal paths and the sandbox guard are exercised directly."""
import asyncio
import subprocess
from pathlib import Path

import pytest

import s2clip_rebake as sr

GEN, COLL = sr.TREES


def _repo(tmp_path, donors=True, manifest=True):
    root = tmp_path / "aeon"
    for t in (GEN, COLL):
        (root / t).mkdir(parents=True)
        (root / t / "committed.bin").write_bytes(b"COMMITTED")
    (root / "tools").mkdir()
    (root / "tools" / "clip_rom_bake.py").write_text("# stub\n")
    if manifest:
        m = root / "games/sonic4/data/clips/s2_test/clips.json"
        m.parent.mkdir(parents=True)
        m.write_text("{}")
    g = lambda *a: subprocess.run(["git", "-C", str(root), *a], check=True,  # noqa: E731
                                  capture_output=True)
    g("init", "-q")
    g("add", "-A")
    g("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")
    if donors:                                    # gitignored in the real tree; untracked here
        (root / sr.DONORS / "s2disasm" / "EHZ").mkdir(parents=True)
        (root / sr.DONORS / "s2disasm" / "EHZ" / "tileset.bin").write_bytes(b"D")
        (root / ".git" / "info" / "exclude").write_text("games/sonic4/data/donors/\n")
    return root


@pytest.fixture
def at(monkeypatch):
    def point(root):
        monkeypatch.setattr(sr, "AEON", root)
        monkeypatch.setattr(sr, "CACHE", root / "tools" / ".cache")
        (root / ".git" / "info" / "exclude").open("a").write("tools/.cache/\n")
    return point


def _stub_bake(monkeypatch, effect):
    real = subprocess.run

    def run(argv, *a, **kw):
        if argv[:2] == [sr.sys.executable, "tools/clip_rom_bake.py"]:
            effect(Path(kw["cwd"]))
            return subprocess.CompletedProcess(argv, 0, "", "")
        return real(argv, *a, **kw)
    monkeypatch.setattr(sr.subprocess, "run", run)


def test_refuses_a_clip_with_no_manifest(tmp_path, at):
    at(_repo(tmp_path, manifest=False))
    with pytest.raises(sr.Refused, match="no clip manifest"):
        sr.rebake("s2_test", tmp_path / "out")


def test_refuses_without_the_converted_donors(tmp_path, at):
    at(_repo(tmp_path, donors=False))
    with pytest.raises(sr.Refused, match="convert the donors first"):
        sr.rebake("s2_test", tmp_path / "out")


def test_refuses_a_dirty_baked_tree(tmp_path, at):
    root = _repo(tmp_path)
    at(root)
    (root / GEN / "committed.bin").write_bytes(b"IN-PLACE BAKE")
    with pytest.raises(sr.Refused, match="not clean"):
        sr.rebake("s2_test", tmp_path / "out")


def test_copies_the_sandbox_bake_out_and_leaves_no_sandbox(tmp_path, at, monkeypatch):
    root = _repo(tmp_path)
    at(root)
    _stub_bake(monkeypatch, lambda box: (box / GEN / "committed.bin").write_bytes(b"CLIP"))
    got = sr.rebake("s2_test", tmp_path / "out")
    assert f"{GEN}/committed.bin" in got and f"{COLL}/committed.bin" in got
    assert (tmp_path / "out" / GEN / "committed.bin").read_bytes() == b"CLIP"
    assert (root / GEN / "committed.bin").read_bytes() == b"COMMITTED"    # tree untouched
    assert not any((root / "tools" / ".cache").iterdir())                  # sandbox removed


def test_refuses_a_bake_that_escaped_its_sandbox(tmp_path, at, monkeypatch):
    root = _repo(tmp_path)
    at(root)
    _stub_bake(monkeypatch, lambda box: (root / GEN / "committed.bin").write_bytes(b"ESCAPED"))
    with pytest.raises(sr.Refused, match="escaped its sandbox"):
        sr.rebake("s2_test", tmp_path / "out")


def test_a_failing_bake_is_refused_with_its_output(tmp_path, at, monkeypatch):
    root = _repo(tmp_path)
    at(root)
    real = subprocess.run

    def run(argv, *a, **kw):
        if argv[:2] == [sr.sys.executable, "tools/clip_rom_bake.py"]:
            return subprocess.CompletedProcess(argv, 1, "", "R20 refused")
        return real(argv, *a, **kw)
    monkeypatch.setattr(sr.subprocess, "run", run)
    with pytest.raises(sr.Refused, match="R20 refused"):
        sr.rebake("s2_test", tmp_path / "out")
    assert not any((root / "tools" / ".cache").iterdir())


# ---- StreamLoad: breakpoint counting and the per-row RAM read --------------------------------

class _Syms:
    addr = {"ZX0R_Decompress": 0x1000, "PageIn_EnqueueLanding": 0x2000,
            "PageCache_PickVictim": 0x3000, "Page_Evict_Gen": 0xFF8000,
            "PageCache_Direct_Map": 0xFF8002}


class _Client:
    def __init__(self):
        self.bps, self.cleared = [], []

    async def call(self, method, params):
        if method == "emulator/breakpoint_add":
            self.bps.append(params["symbol"])
            return {"breakpoint": len(self.bps)}
        if method == "emulator/breakpoint_clear":
            self.cleared.append(params["breakpoint"])
            return {}
        if method == "emulator/read_memory":
            a = int(params["addr"], 16)
            return {"bytes": "0x0007" if a == 0xFF8000 else "0x00", "mclk": "0"}
        raise AssertionError(method)


def test_streamload_counts_only_its_own_stops_and_reads_each_row():
    import leg_run
    sl, c = leg_run.StreamLoad(_Syms()), _Client()

    async def go():
        await sl.arm(c)
        claimed = [await sl.on_break(c, pc, {}) for pc in
                   (0x1000, 0x1000, 0x2000, 0x3000, 0x4444)]
        row = {}
        await sl.on_tick(c, None, row)
        await sl.disarm(c)
        return claimed, row
    claimed, row = asyncio.run(go())
    assert c.bps == list(sr_hit_syms()) and c.cleared == [1, 2, 3]
    assert claimed == [True, True, True, True, False]       # a foreign stop is not claimed
    assert sl.hits == {"ZX0R_Decompress": 2, "PageIn_EnqueueLanding": 1,
                       "PageCache_PickVictim": 1}
    assert row == {"eg": 7, "dm": 0}


def sr_hit_syms():
    import leg_drive
    return leg_drive.STREAM_HIT_SYMS
