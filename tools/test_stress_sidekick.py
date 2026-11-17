"""Tests for the STRESS_SIDEKICK=1 shape (v2 C3): tools/stress_sidekick.py, the build.sh
shape block, and the emulator-backed gate `test_sidekick_slot_live` (needs_build: it runs in
the post-sigil lane of every STRESS_SIDEKICK build, where the pair is this build's)."""
import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import leg_drive as ld
import stress_sidekick as sk

AEON = Path(__file__).resolve().parent.parent


def _copy_tree(dst: Path):
    for rel in sk.RESTORE_PATHS + (sk.PATCH, "tools/gen_vram_map.py"):
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(AEON / rel, dst / rel)


def test_the_patch_applies_to_the_committed_tree():
    """Patch rot is caught in the pre-build lane, not first by a stress build."""
    p = subprocess.run(["git", "apply", "--check", sk.PATCH], cwd=AEON, capture_output=True,
                       text=True)
    assert p.returncode == 0, p.stderr


def test_the_patch_touches_exactly_the_declared_files():
    text = (AEON / sk.PATCH).read_text()
    touched = {ln.split(" b/", 1)[1].strip() for ln in text.splitlines()
               if ln.startswith("diff --git ")}
    assert touched == set(sk.PATCHED)


def test_canonical_tree_passes_the_guard():
    assert sk.leftovers(AEON) == []
    assert sk.guard(AEON) == 0


def test_an_applied_patch_is_refused_by_the_guard(tmp_path, capsys):
    _copy_tree(tmp_path)
    assert subprocess.run(["git", "apply", sk.PATCH], cwd=tmp_path).returncode == 0
    assert sk.guard(tmp_path) == 1
    assert "ojz_scroll_test.emp" in capsys.readouterr().out


def test_a_regenerated_map_alone_is_refused_by_the_guard(tmp_path):
    """The trap restores all five files; a half-restored tree (constants only) still refuses."""
    _copy_tree(tmp_path)
    out = sk.rebake(tmp_path / "rb", tmp_path)
    shutil.copyfile(out["games/sonic4/config/constants.emp"],
                    tmp_path / "games/sonic4/config/constants.emp")
    assert sk.guard(tmp_path) == 1


def test_rebake_writes_the_patched_files_and_leaves_the_tree(tmp_path):
    before = {rel: (AEON / rel).read_bytes() for rel in sk.RESTORE_PATHS}
    out = sk.rebake(tmp_path)
    assert set(out) == set(sk.RESTORE_PATHS)
    assert "VRAM_STRESS_SIDEKICK" in out["games/sonic4/config/constants.emp"].read_text()
    assert "stress_sidekick_body" in out["games/sonic4/vram.toml"].read_text()
    assert {rel: (AEON / rel).read_bytes() for rel in sk.RESTORE_PATHS} == before


def test_rebake_refuses_a_tree_that_already_carries_the_patch(tmp_path):
    _copy_tree(tmp_path)
    subprocess.run(["git", "apply", sk.PATCH], cwd=tmp_path, check=True)
    with pytest.raises(sk.Refused, match="already carries"):
        sk.rebake(tmp_path / "rb", tmp_path)


def test_the_replay_delay_is_read_from_the_patch(tmp_path):
    assert ld.sidekick_delay() == 16
    bad = tmp_path / "p.patch"
    bad.write_text("+        subi.w  #4*(16+1), d0\n+        subi.w  #4*(8+1), d0\n")
    with pytest.raises(ld.DriveError, match="found 2"):
        ld.sidekick_delay(bad)


# ---- build.sh refusals (all above the sigil-binary check: nothing is built) -----------------

def _build_sh(**env_over):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("STRESS_", "S2CLIP", "FAST", "DEBUG"))}
    env.update(SIGIL_BUILD="/nonexistent/sigil", **env_over)
    p = subprocess.run(["bash", "build.sh"], cwd=AEON, env=env, capture_output=True,
                       text=True, timeout=120)
    return p.returncode, p.stdout + p.stderr


@pytest.mark.parametrize("other", [{"S2CLIP": "s2_ehz_cpz"}, {"STRESS_ART": "1"},
                                   {"STRESS_EVICT": "1"}, {"STRESS_OBJECTS": "1"}])
def test_stress_sidekick_refuses_another_offcanonical_shape(other):
    rc, out = _build_sh(STRESS_SIDEKICK="1", **other)
    assert rc == 1 and "mutually exclusive" in out, out[-2000:]
    assert "needs the sigil build binary" not in out


def test_stress_sidekick_refuses_fast():
    rc, out = _build_sh(STRESS_SIDEKICK="1", FAST="1")
    assert rc == 1 and "FAST=1 is refused on the STRESS_* fixture shapes" in out, out[-2000:]


def test_stress_sidekick_refuses_another_game():
    env = {k: v for k, v in os.environ.items() if not k.startswith(("STRESS_", "FAST"))}
    env.update(SIGIL_BUILD="/nonexistent/sigil", STRESS_SIDEKICK="1")
    p = subprocess.run(["bash", "build.sh", "demo"], cwd=AEON, env=env, capture_output=True,
                       text=True, timeout=120)
    assert p.returncode == 1 and "sonic4-only" in p.stdout + p.stderr


def test_stress_sidekick_alone_passes_the_refusals():
    rc, out = _build_sh(STRESS_SIDEKICK="1")
    assert rc == 1 and "needs the sigil build binary" in out, out[-2000:]
    assert "mutually exclusive" not in out and "FAST=1 is refused" not in out
    assert "stress_sidekick guard: OK" in out


def test_stress_sidekick_rom_names_are_standalone_literals():
    import gate_cut_shape as gcs
    assert {"s4.sidekick.lst", "s4.sidekick.debug.lst"} <= gcs.off_canonical_listings()


def test_the_build_restores_every_file_the_patch_changes():
    """build.sh's EXIT-trap list is the tool's RESTORE_PATHS (read from `paths`, not retyped),
    and RESTORE_PATHS covers every file the patch or the map regeneration writes."""
    text = (AEON / "build.sh").read_text()
    assert 'mapfile -t STRESSSK_PATHS < <(python3 "${TOOLS}/stress_sidekick.py" paths)' in text
    p = subprocess.run([sys.executable, str(AEON / "tools/stress_sidekick.py"), "paths"],
                       capture_output=True, text=True, check=True)
    assert tuple(p.stdout.split()) == sk.RESTORE_PATHS
    assert set(sk.PATCHED) | {"games/sonic4/config/constants.emp", "tools/vram_map.py"} <= \
        set(sk.RESTORE_PATHS)
    regen = " ".join(sk._regen_argv(Path("/R")))
    for rel in sk.REGENERATED:
        assert "/R/" + rel in regen, rel


# ---- the gate: Player_2 is live and near Player_1 after 300 ticks ---------------------------

SK_TICKS = 300
SK_NEAR_PX = 256


def _p2_after(rom: Path, lst: Path):
    """Spawn the pinned oracle (outside any event loop: spawn_pinned runs its own), drive
    SK_TICKS ticks of the run policy, read Player_2 and Player_1."""
    import leg_provenance as lp
    from suite_paths import add_client_path
    add_client_path()
    from aether import BusClient
    syms = ld.resolve_syms(lst, aeon=AEON)
    inst = lp.spawn_pinned(rom, lst)
    try:
        async def go():
            c = BusClient(socket_path=inst.socket_path, client_id=f"sk-gate-{os.getpid()}",
                          client_name="test_sidekick_slot_live")
            await c.connect()
            try:
                await c.call("emulator/reset", {})
                pol = ld.POLICIES["sidekick"](syms.buttons, syms.equ)
                tr = await ld.drive_leg(c, syms, pol, t0=ld.T0, cap_ticks=SK_TICKS)
                p2 = await ld.read_sidekick(c, syms)
                s, _ps, _lag = await ld.read_tick_state(c, syms)
                return tr, p2, s
            finally:
                await c.close()
        return asyncio.run(go())
    finally:
        inst.reap()


@pytest.mark.parametrize("rom,lst", [
    pytest.param("s4.sidekick.bin", "s4.sidekick.lst",
                 marks=pytest.mark.needs_build("s4.sidekick.bin", "s4.sidekick.lst")),
    pytest.param("s4.sidekick.debug.bin", "s4.sidekick.debug.lst",
                 marks=pytest.mark.needs_build("s4.sidekick.debug.bin",
                                               "s4.sidekick.debug.lst")),
])
def test_sidekick_slot_live(rom, lst):
    """Boot, drive 300 ticks of the run policy: Player_2's code word is non-zero and its x is
    within 256 px of Player_1's."""
    tr, p2, s = _p2_after(AEON / rom, AEON / lst)
    assert len(tr.rows) >= SK_TICKS - 1, (tr.status, tr.reason, len(tr.rows))
    assert p2["p2c"] != 0, f"Player_2's code word is 0 after {len(tr.rows)} ticks: no sidekick"
    assert abs(p2["p2x"] - s.px) <= SK_NEAR_PX, (p2, s.px, s.py)
