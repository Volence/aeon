"""Pre-build lane tests for tools/leg_provenance.py (v2 B1). No emulator, no build needed."""
import json
import subprocess
import zlib
from pathlib import Path

import pytest

import artifact_provenance as ap
import leg_provenance as lp

C = "a" * 40
GOOD = {"implementation": "oracle-rs",
        "serverBuild": {"id": C + "+profile=release", "source": "vcs", "dirty": False}}
PIN = lp.OraclePin(C, Path("/nonexistent"), "0" * 64)


def hs(**over):
    sb = dict(GOOD["serverBuild"]); sb.update(over)
    return {"implementation": "oracle-rs", "serverBuild": sb}


def test_verify_pin_accepts_matching_handshake():
    lp.verify_pin(PIN, GOOD)


def test_verify_pin_refuses_other_commit():
    with pytest.raises(lp.PinMismatch, match="serverBuild.id"):
        lp.verify_pin(PIN, hs(id="b" * 40 + "+profile=release"))


def test_verify_pin_accepts_real_id_with_target_suffix():
    lp.verify_pin(PIN, hs(id=C + "+profile=release+target=x86_64-unknown-linux-gnu+features="))


@pytest.mark.parametrize("sid", [C + "+profile=debug", C + "+profile=release+features=jit",
                                 C[:-1] + "b+profile=release+target=t+features=", None, ""])
def test_verify_pin_refuses_other_profile_features_or_missing_id(sid):
    with pytest.raises(lp.PinMismatch, match="serverBuild.id"):
        lp.verify_pin(PIN, hs(id=sid))


def test_verify_pin_refuses_dirty():
    with pytest.raises(lp.PinMismatch, match="serverBuild.dirty"):
        lp.verify_pin(PIN, hs(dirty=True))


def test_verify_pin_refuses_declared_source():
    with pytest.raises(lp.PinMismatch, match="serverBuild.source"):
        lp.verify_pin(PIN, hs(source="declared"))


def test_verify_pin_refuses_missing_server_build():
    with pytest.raises(lp.PinMismatch, match="serverBuild"):
        lp.verify_pin(PIN, {"implementation": "oracle-rs"})


def test_refuses_binary_sha_mismatch(tmp_path):
    b = tmp_path / "oracle-aether"
    b.write_bytes(b"not the pinned binary")
    with pytest.raises(lp.PinMismatch, match="sha256"):
        lp.verify_binary(lp.OraclePin(C, b, "0" * 64))


def test_spawn_pinned_checks_sha_before_spawn(tmp_path, monkeypatch):
    b = tmp_path / "oracle-aether"
    b.write_bytes(b"x")
    monkeypatch.setattr(lp, "load_pin", lambda: lp.OraclePin(C, b, "0" * 64))
    with pytest.raises(lp.PinMismatch, match="sha256"):
        lp.spawn_pinned(tmp_path / "r.bin", tmp_path / "r.lst")


def test_committed_pin_shape_and_self_consistency():
    """PURE (no archive): the toml's shape, and a handshake built from ITS commit verifies
    while one digit off is refused. Commit/binary truth is the needs_build test below."""
    import re
    import tomllib
    raw = tomllib.loads(lp.PIN_FILE.read_text())
    assert re.fullmatch(r"[0-9a-f]{40}", raw["commit"])
    assert re.fullmatch(r"[0-9a-f]{64}", raw["sha256"])
    assert raw["binary"].startswith(".oracle-bin-archive/")
    pin = lp.load_pin()
    good = hs(id=pin.commit + "+profile=release+target=t+features=")
    lp.verify_pin(pin, good)
    d = pin.commit[0]
    bad = ("0" if d != "0" else "1") + pin.commit[1:]
    with pytest.raises(lp.PinMismatch, match="serverBuild.id"):
        lp.verify_pin(pin, hs(id=bad + "+profile=release+target=t+features="))


@pytest.mark.needs_build("s4.bin", "s4.lst")
def test_committed_pin_is_the_archived_binary_and_the_live_handshake():
    """ARCHIVE-BACKED (post-sigil needs_build lane, tools/needs_build_lane.py): the pinned
    binary exists (a missing one FAILS naming the path, never skips), has the pinned sha256,
    its BUILD_INFO.json names the toml's commit, and a real spawn handshakes as that commit."""
    pin = lp.load_pin()
    lp.verify_binary(pin)  # PinMismatch naming the path when absent or the sha differs
    info = json.loads((pin.binary.parent / "BUILD_INFO.json").read_text())
    assert info["commit"] == pin.commit, "oracle_pin.toml commit != archived BUILD_INFO.json"
    assert info["sha256"] == pin.sha256
    aeon = Path(__file__).resolve().parent.parent
    inst = lp.spawn_pinned(aeon / "s4.bin", aeon / "s4.lst")  # verify_pin on the live handshake
    inst.reap()


def _synthetic(tmp_path, rom_bytes=b"ROMDATA", digest_crc=None, debug=1):
    rom = tmp_path / "s4.debug.bin"
    rom.write_bytes(rom_bytes)
    read = "DIGEST-READ crc=00000001 size=1 origin=source path=x.asm"
    agg = f"{zlib.crc32((read + chr(10)).encode()) & 0xFFFFFFFF:08x}"
    crc = zlib.crc32(rom_bytes) & 0xFFFFFFFF if digest_crc is None else digest_crc
    lst = tmp_path / "s4.debug.lst"
    lst.write_text("\n".join([
        "DIGEST-FORMAT 1",
        "DIGEST-ASSEMBLER sigil version=0.1 revision=abc1234 tree=clean",
        f"DIGEST-SHAPE target=sonic4 game=sonic4 debug={debug} extra-entries=none",
        "DIGEST-SCAN pattern=*.emp files=0 crc=00000000",
        read, f"DIGEST-AGGREGATE crc={agg} reads=1",
        f"DIGEST-ROM crc={crc:08x} size={len(rom_bytes)} path=s4.debug.bin",
        "DIGEST-END", ""]))
    return rom, lst


def _fresh(monkeypatch):
    def fake(rom, lst, **kw):
        v = ap.Verdict(rom, lst)
        return v
    monkeypatch.setattr(lp, "check_pair", fake)


def test_rom_provenance_reads_digest_shape(tmp_path, monkeypatch):
    rom, lst = _synthetic(tmp_path)
    _fresh(monkeypatch)  # freshness itself is check_pair's; this reads the digest fields
    p = lp.rom_provenance(rom, lst)
    assert p["debug"] == 1 and p["sigil_revision"] == "abc1234"
    assert p["game"] == "sonic4" and p["target"] == "sonic4" and p["extra_entries"] == "none"
    assert p["size"] == 7 and p["rom"] == "s4.debug.bin" and p["tree"] == "clean"
    assert p["crc32"] == f"{zlib.crc32(b'ROMDATA') & 0xFFFFFFFF:08x}"


def test_refuses_stale_pair(tmp_path, monkeypatch):
    # A listing whose DIGEST-ROM crc differs from the .bin: the REAL check_pair must refuse.
    # root=tmp_path keeps its module walk off the aeon docs/ tree (land_gate_audit).
    monkeypatch.setenv("SIGIL_BUILD", "/nonexistent-sigil")
    rom, lst = _synthetic(tmp_path, digest_crc=0xDEADBEEF)
    with pytest.raises(lp.StalePair, match="DIGEST-ROM says crc="):
        lp.rom_provenance(rom, lst, root=tmp_path)


def test_records_dirty_tree(tmp_path):
    def g(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)
    g("init", "-q", "-b", "main")
    (tmp_path / "f").write_text("1")
    g("add", "f")
    g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c")
    assert lp.aeon_provenance(tmp_path)["dirty"] is False
    (tmp_path / "untracked").write_text("x")
    a = lp.aeon_provenance(tmp_path)
    assert a["dirty"] is True and len(a["commit"]) == 40 and a["branch"] == "main"


def test_dirty_paths_are_recorded_and_capped(tmp_path, monkeypatch):
    """The porcelain lines behind `dirty` are in the provenance (auditable), capped at
    DIRTY_PATHS_MAX with the full count beside them. Untracked files still count."""
    def g(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)
    g("init", "-q", "-b", "main")
    (tmp_path / "f").write_text("1")
    g("add", "f")
    g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c")
    a = lp.aeon_provenance(tmp_path)
    assert a["dirty_paths"] == [] and a["dirty_count"] == 0
    (tmp_path / "f").write_text("2")
    (tmp_path / "new.emp").write_text("x")
    a = lp.aeon_provenance(tmp_path)
    assert a["dirty"] is True and a["dirty_count"] == 2
    assert sorted(a["dirty_paths"]) == [" M f", "?? new.emp"]
    monkeypatch.setattr(lp, "DIRTY_PATHS_MAX", 1)
    a = lp.aeon_provenance(tmp_path)
    assert len(a["dirty_paths"]) == 1 and a["dirty_count"] == 2


def _full():
    return {"oracle": {"commit": C, "server_build_id": C + "+profile=release", "source": "vcs",
                       "dirty": False, "sha256": "0" * 64},
            "aeon": {"commit": C, "dirty": False, "branch": "b"},
            "rom": {"rom": "s4.bin", "crc32": "00000000", "size": 0, "game": "sonic4",
                    "debug": 0, "target": "sonic4", "sigil_revision": "r",
                    "extra_entries": "none"},
            "harness": {"tool_sha256": "f" * 64}}


def test_require_provenance_accepts_full_with_false_zero_none_values():
    lp.require_provenance(_full())  # dirty False, debug 0, size 0, extra_entries "none"


@pytest.mark.parametrize("key", list(lp.REQUIRED))
def test_require_provenance_refuses_each_missing_key(key):
    r = _full(); del r[key]
    with pytest.raises(lp.MissingProvenance, match=key):
        lp.require_provenance(r)


@pytest.mark.parametrize("blk,leaf", [(b, l) for b, ls in lp.REQUIRED.items() for l in ls])
def test_require_provenance_refuses_each_missing_leaf_by_name(blk, leaf):
    r = _full(); del r[blk][leaf]
    with pytest.raises(lp.MissingProvenance, match=f"{blk}.{leaf}"):
        lp.require_provenance(r)
    r = _full(); r[blk][leaf] = None
    with pytest.raises(lp.MissingProvenance, match=f"{blk}.{leaf}"):
        lp.require_provenance(r)


def test_require_provenance_partial_block_is_refused():
    r = _full(); r["oracle"] = {"commit": C}
    with pytest.raises(lp.MissingProvenance, match="oracle.server_build_id"):
        lp.require_provenance(r)
