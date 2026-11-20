"""tools/game_shape_feature.py: build.sh's reader of a game description's shape features
(G0b Task 8: demo's sound axis moved from games/demo/build.conf into game.toml).

Build-free: runs in the pre-build pytest lane.
"""

import pathlib
import subprocess
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import game_shape_feature as gsf  # noqa: E402


def test_demo_ships_without_sound_in_both_shapes():
    """The fact games/demo/build.conf used to carry (`SOUND_DRIVER_ENABLED:=0`)."""
    assert gsf.feature("demo", "release", "sound") is False
    assert gsf.feature("demo", "debug", "sound") is False


def test_the_build_conf_is_gone():
    """Folded, not duplicated: the description is the one authority."""
    assert not (gsf.AEON / "games" / "demo" / "build.conf").exists()


def test_an_extends_chain_inherits_and_overrides(tmp_path):
    g = tmp_path / "games" / "g"
    g.mkdir(parents=True)
    (g / "game.toml").write_text(
        "[shapes.release]\nfeatures = { debug = false, sound = true }\n"
        "[shapes.quiet]\nextends = \"release\"\nfeatures = { sound = false }\n"
        "[shapes.child]\nextends = \"quiet\"\n"
        "[shapes.a]\nextends = \"b\"\n[shapes.b]\nextends = \"a\"\n")
    assert gsf.feature("g", "release", "sound", aeon=tmp_path) is True
    assert gsf.feature("g", "child", "sound", aeon=tmp_path) is False
    assert gsf.feature("g", "child", "debug", aeon=tmp_path) is False
    with pytest.raises(ValueError, match="extends cycle"):
        gsf.feature("g", "a", "sound", aeon=tmp_path)
    with pytest.raises(ValueError, match="no boolean `crash_report`"):
        gsf.feature("g", "release", "crash_report", aeon=tmp_path)
    with pytest.raises(ValueError, match="no \\[shapes.gone\\]"):
        gsf.feature("g", "gone", "sound", aeon=tmp_path)


def test_the_cli_prints_the_value_or_refuses():
    run = lambda *a: subprocess.run([sys.executable, str(TOOLS / "game_shape_feature.py"), *a],
                                    capture_output=True, text=True)
    ok = run("--game", "demo", "--shape", "debug", "--feature", "sound")
    assert (ok.returncode, ok.stdout) == (0, "0\n"), ok.stderr
    bad = run("--game", "demo", "--shape", "nope", "--feature", "sound")
    assert bad.returncode == 1 and "no [shapes.nope]" in bad.stderr


def test_shell_facts_follow_the_chain_defines_fixture_and_stem(tmp_path):
    """`--shell` (G0b Task 10): the features, the two sound dev opt-in defines (0 when no
    row sets them), fixture sticky down `extends` (sigil's resolve_shape) and the stem."""
    g = tmp_path / "games" / "g"
    g.mkdir(parents=True)
    (g / "game.toml").write_text(
        "[defines]\nSOUND_DBG_MIRROR = 0\n"
        "[shapes.debug]\nfeatures = { debug = true, crash_report = true, sound = true }\n"
        "[shapes.a]\nextends = \"debug\"\ndefines = { SOUND_DEBUG_HOTKEYS = 1, SOUND_DBG_MIRROR = 1 }\n"
        "[shapes.fx]\nextends = \"a\"\nfixture = true\n"
        "[shapes.fxchild]\nextends = \"fx\"\n"
        "[outputs]\ndebug = \"g.debug\"\na = \"g.a\"\n")
    f = dict(gsf.shell_facts("g", "a", aeon=tmp_path))
    assert f == {"DESC_DEBUG": 1, "DESC_CRASH_REPORT": 1, "DESC_SOUND": 1,
                 "DESC_SOUND_DEBUG_HOTKEYS": 1, "DESC_SOUND_DBG_MIRROR": 1,
                 "DESC_FIXTURE": 0, "DESC_STEM": "g.a"}
    d = dict(gsf.shell_facts("g", "debug", aeon=tmp_path))
    assert (d["DESC_SOUND_DEBUG_HOTKEYS"], d["DESC_SOUND_DBG_MIRROR"], d["DESC_STEM"]) == (0, 0, "g.debug")
    assert dict(gsf.shell_facts("g", "fxchild", aeon=tmp_path))["DESC_FIXTURE"] == 1
    assert dict(gsf.shell_facts("g", "fx", aeon=tmp_path))["DESC_STEM"] == ""
    (g / "game.toml").write_text(
        "[shapes.r]\nfeatures = { debug = false, crash_report = true, sound = true }\n"
        "[outputs]\nr = \"../evil\"\n")
    with pytest.raises(ValueError, match="not a plain file stem"):
        gsf.shell_facts("g", "r", aeon=tmp_path)


def test_sonic4_config_rows_are_build_sh_shapes():
    """The rows build.sh writes under SHAPE=: a stem, not a fixture; lean is not one."""
    for row, stem in (("config-a", "s4.configa"), ("config-b", "s4.configb")):
        f = dict(gsf.shell_facts("sonic4", row))
        assert (f["DESC_STEM"], f["DESC_FIXTURE"]) == (stem, 0), f
    assert dict(gsf.shell_facts("sonic4", "lean"))["DESC_STEM"] == ""
