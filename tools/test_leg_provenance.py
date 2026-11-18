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


def test_detached_head_is_recorded_not_refused(tmp_path):
    """V2-B1-DETACHED-PROVENANCE: the land gate says to prove a push from a clean checkout of a
    SHA, and that checkout is detached. Provenance names it DETACHED_BRANCH (the commit stays
    mandatory) and the writer's gate accepts it; it does not raise MissingProvenance."""
    def g(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)
    g("init", "-q", "-b", "main")
    (tmp_path / "f").write_text("1")
    g("add", "f")
    g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c")
    sha = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], check=True,
                         capture_output=True, text=True).stdout.strip()
    g("checkout", "-q", "--detach", sha)
    a = lp.aeon_provenance(tmp_path)
    assert a["branch"] == lp.DETACHED_BRANCH == "(detached)"
    assert a["commit"] == sha and a["dirty"] is False
    C = "0" * 40
    lp.require_provenance({
        "oracle": {"commit": C, "server_build_id": "x", "source": "s", "dirty": False, "sha256": "h"},
        "aeon": a,
        "rom": {"rom": "s4.bin", "crc32": "00000000", "size": 1, "game": "sonic4", "debug": False,
                "target": "sonic4", "sigil_revision": "r"},
        "harness": {"tool_sha256": "h"},
    })


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


# ---- throwaway shapes: the declared re-bake (v2 C2, STRESS_OBJECTS) ------------------------

def _rebake_listing(tmp_path, built: bytes):
    """A digest whose one DIGEST-READ is gen/x.emp as the build read it (`built`)."""
    import artifact_provenance as ap
    rom = tmp_path / "s4.stressobj.bin"
    rom.write_bytes(b"ROMDATA")
    read = (f"DIGEST-READ crc={zlib.crc32(built) & 0xFFFFFFFF:08x} size={len(built)} "
            "origin=source path=gen/x.emp")
    agg = f"{zlib.crc32((read + chr(10)).encode()) & 0xFFFFFFFF:08x}"
    lst = tmp_path / "s4.stressobj.lst"
    lst.write_text("\n".join([
        "DIGEST-FORMAT 1", "DIGEST-ASSEMBLER sigil version=0.1 revision=abc1234 tree=clean",
        "DIGEST-SHAPE target=sonic4 game=sonic4 debug=0 extra-entries=none",
        "DIGEST-SCAN pattern=*.emp files=0 crc=00000000", read,
        f"DIGEST-AGGREGATE crc={agg} reads=1",
        f"DIGEST-ROM crc={zlib.crc32(b'ROMDATA') & 0xFFFFFFFF:08x} size=7 path=s4.stressobj.bin",
        "DIGEST-END", ""]))
    (tmp_path / "gen").mkdir()
    (tmp_path / "gen" / "x.emp").write_bytes(b"COMMITTED")      # what the EXIT trap restored
    return ap, rom, lst


def _read_problems(v):
    return [p for p in v.problems if "DIGEST-READ" in p or "rebaked path" in p]


def test_rebaked_read_is_checked_against_the_regenerated_bytes(tmp_path, monkeypatch):
    monkeypatch.setenv("SIGIL_BUILD", "/nonexistent-sigil")
    ap, rom, lst = _rebake_listing(tmp_path, b"OVERLAY-BAKE")
    v = ap.check_pair(str(rom), str(lst), root=str(tmp_path))
    assert any("gen/x.emp" in p for p in _read_problems(v)), v.problems   # restored: stale
    good = tmp_path / "regen.emp"
    good.write_bytes(b"OVERLAY-BAKE")
    v = ap.check_pair(str(rom), str(lst), root=str(tmp_path), rebaked={"gen/x.emp": str(good)})
    assert not _read_problems(v), v.problems
    assert any("throwaway re-bake" in n for n in v.notes)


def test_a_rebake_that_differs_from_what_the_build_read_is_stale(tmp_path, monkeypatch):
    monkeypatch.setenv("SIGIL_BUILD", "/nonexistent-sigil")
    ap, rom, lst = _rebake_listing(tmp_path, b"OVERLAY-BAKE")
    bad = tmp_path / "regen.emp"
    bad.write_bytes(b"OVERLAY-BAKE-EDITED")            # the overlay changed after the build
    v = ap.check_pair(str(rom), str(lst), root=str(tmp_path), rebaked={"gen/x.emp": str(bad)})
    assert any("gen/x.emp" in p and "the build read" in p for p in _read_problems(v))


def test_a_rebake_of_a_file_the_build_never_read_is_a_problem(tmp_path, monkeypatch):
    monkeypatch.setenv("SIGIL_BUILD", "/nonexistent-sigil")
    ap, rom, lst = _rebake_listing(tmp_path, b"COMMITTED")
    f = tmp_path / "regen.emp"
    f.write_bytes(b"X")
    v = ap.check_pair(str(rom), str(lst), root=str(tmp_path), rebaked={"gen/other.emp": str(f)})
    assert any("rebaked path gen/other.emp" in p for p in v.problems)


def test_only_the_declared_throwaway_shapes_rebake(tmp_path):
    for name in ("s4.bin", "s4.debug.bin", "demo.bin", "demo.debug.bin"):
        assert lp.regenerate_rebake(Path(name), tmp_path) is None, name
    assert set(lp.SHAPE_REBAKES) == {"s4.stressobj", "s4.sidekick", "s4.s2clip"}
    assert lp._shape_stem(Path("s4.stressobj.debug.bin")) == "s4.stressobj"


def test_the_stressobj_rebake_regenerates_from_committed_inputs(tmp_path):
    files, rec = lp.regenerate_rebake(Path("s4.stressobj.debug.bin"), tmp_path)
    (path, out), = files.items()
    assert path == "games/sonic4/data/generated/ojz/act1/entity_data.emp"
    assert "STRESS_OBJECTS OVERLAY" in out.read_text()
    assert rec["sha256"] == lp.sha256_file(out) and rec["inputs"]
    ins = rec["inputs"]
    for need in ("tools/ojz_entity_gen.py", "project.json", "games/sonic4/data/editor/objects.json",
                 "games/sonic4/test/fixtures/stress_objects.overlay.json",
                 "games/sonic4/data/editor/ojz/act1/section_0.objects.json"):
        assert ins[need] == lp.sha256_file(lp.AEON_ROOT / need), need
    assert sum(k.endswith(".objects.json") and "/act1/section_" in k for k in ins) >= 2


def test_a_rebake_input_that_matches_nothing_is_refused(tmp_path):
    with pytest.raises(lp.StalePair, match="matches nothing"):
        lp.rebake_inputs({"inputs": ["no/such/*.json"]}, tmp_path)


def test_the_sidekick_rebake_regenerates_both_build_reads_from_committed_inputs(tmp_path):
    """v2 C3: the patch applied to the committed files plus the regenerated VRAM map; only
    the two files sigil reads are declared (vram.toml and the map doc are inputs)."""
    files, rec = lp.regenerate_rebake(Path("s4.sidekick.debug.bin"), tmp_path)
    assert set(files) == {"games/sonic4/test/ojz_scroll_test.emp",
                          "games/sonic4/config/constants.emp"}
    assert "jbsr    Player_Main" in files["games/sonic4/test/ojz_scroll_test.emp"].read_text()
    assert "VRAM_STRESS_SIDEKICK" in files["games/sonic4/config/constants.emp"].read_text()
    for rel, f in files.items():
        assert rec["paths"][rel] == lp.sha256_file(f)
        assert f.read_bytes() != (lp.AEON_ROOT / rel).read_bytes(), rel     # tree untouched
    assert rec["inputs"]["tools/stress/sidekick.patch"] == lp.sha256_file(
        lp.AEON_ROOT / "tools/stress/sidekick.patch")


# ---- S2CLIP: the tree re-bake keyed by the build's clip (v2 C4, Task 10) ---------------------
# The bake itself needs the gitignored donor trees, so the pre-build lane checks the
# declaration and the refusals; the real re-bake is proved on a built pair (Task 10 report).

def test_the_s2clip_rebake_is_a_tree_rebake_of_the_two_baked_trees():
    spec = lp.SHAPE_REBAKES["s4.s2clip"]
    import s2clip_rebake as sr
    assert tuple(spec["trees"]) == sr.TREES
    import clip_rom_bake as crb
    assert tuple(spec["trees"]) == tuple(crb.RESTORE_PATHS)
    assert "{clip}" in spec["argv"] and "{out}" in spec["argv"]
    assert any("{clip}" in i for i in spec["inputs"])


def test_an_s2clip_rom_without_its_clip_record_is_refused(tmp_path):
    rom = tmp_path / "s4.s2clip.debug.bin"
    rom.write_bytes(b"x")
    with pytest.raises(lp.StalePair, match="clip_anchors.json"):
        lp.regenerate_rebake(rom, tmp_path / "o")
    rom.with_suffix(".clip_anchors.json").write_text(json.dumps({"clip": "../etc"}))
    with pytest.raises(lp.StalePair, match="no usable clip"):
        lp.regenerate_rebake(rom, tmp_path / "o")


def test_an_s2clip_tree_rebake_needs_the_listing_and_a_read_under_the_trees(tmp_path):
    ap, _rom, lst = _rebake_listing(tmp_path, b"OVERLAY-BAKE")
    rom = tmp_path / "s4.s2clip.bin"
    rom.write_bytes(b"x")
    rom.with_suffix(".clip_anchors.json").write_text(json.dumps({"clip": "s2_woven"}))
    with pytest.raises(lp.StalePair, match="no listing given"):
        lp.regenerate_rebake(rom, tmp_path / "o")
    with pytest.raises(lp.StalePair, match="no DIGEST-READ row under"):
        lp.regenerate_rebake(rom, tmp_path / "o", lst=lst)       # its one read is gen/x.emp
    assert lp._tree_reads(lst, ["gen"]) == ["gen/x.emp"]
