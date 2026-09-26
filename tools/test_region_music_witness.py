"""The region-music witness's model (tools/region_music_witness.py `model_posts`) restated as
cases, so the expectation the headless witness grades against cannot drift silently.

The model is the mechanism in engine/level/parallax.emp (the crossing records a non-zero
rg_song in Music_Want) and engine/sound/sound_api.emp (Music_Service posts when
Music_Want != Music_Current). Each case names the behaviour it pins.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from region_music_witness import model_posts  # noqa: E402


def test_no_row_names_a_song_posts_nothing():
    # every canonical shape: all rows 0
    assert model_posts(["a", "b", "a", "c"], {}) == []


def test_first_entry_posts_once_and_a_zero_row_leaves_it_alone():
    assert model_posts(["start", "song", "zero", "song", "start"], {"song": 1}) == [1]


def test_two_rows_naming_one_song_never_restart_it():
    # an L-shape / a zone split into several rows
    assert model_posts(["x", "y", "x", "y"], {"x": 2, "y": 2}) == [2]


def test_going_back_to_a_different_song_restarts_it_from_the_top():
    # the owner's ruling: back into Emerald Hill restarts Emerald Hill
    assert model_posts(["ehz", "tunnel", "cpz", "tunnel", "ehz"],
                       {"ehz": 4, "cpz": 5}) == [4, 5, 4]


def test_the_start_region_song_posts_at_act_load():
    assert model_posts(["ehz"], {"ehz": 4}) == [4]
