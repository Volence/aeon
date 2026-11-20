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
