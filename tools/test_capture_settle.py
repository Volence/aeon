#!/usr/bin/env python3
"""test_capture_settle — the offline half of the night-settle capture: prove that a frame
cannot be NAMED settled unless the predicate said so from a live read, and prove it on the
real case rather than on a hypothetical.

THE REAL CASE IS `t5-f272-settled.png` (docs/captures/2026-09-13-regions-p2-night/). It was
named by hand, it is mid-fade (45.9% of its pixels decode to neither palette —
docs/superpowers/notes/2026-09-16-night-palette-mechanism.md), and the refutation was in the
capture set's OWN table one column over: `Pal_Fade_Frames` = 11.

So the rows below are not invented. `old_set_rows()` PARSES that README's table, and the
first two tests run its recorded state through the shipped predicate. If someone edits that
table these tests re-read it; if someone removes it they go red naming it. The point is not
that a made-up row with a non-zero counter is refused — it is that THE ROW THAT WAS ACTUALLY
MISNAMED is refused, by the same function the capture tool names frames with.

WHAT THE OFFLINE HALF CANNOT DO, said here rather than in a report nobody re-reads: it
never touches an emulator, so it proves the PREDICATE and the NAMING, not the reads that
feed them. That a live `Pal_Fade_Frames` read lands on the right address, that CRAM comes
back 48 words, that the screenshot is the frame the header says it is -- none of that is
here. tools/night_settle_capture.py's own refusals are what carry those, and they can only
be exercised in a foreground run against a real Oracle.
"""
from __future__ import annotations

import itertools
import os
import re
import shutil
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
AEON = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import capture_settle as cs  # noqa: E402
from pathlib import Path  # noqa: E402

OLD_SET = os.path.join(AEON, "docs", "captures", "2026-09-13-regions-p2-night", "README.md")

#: A day palette and its night transform, 48 words apiece, built by the recipe
#: games/sonic4/data/effects/ojz_effects.emp states above OJZ_Palette_Night: red -3,
#: green -2, blue 0, each channel clamped to 0..7. Any two distinct palettes would do for
#: the mechanics; these are the real pair's arithmetic so the distances are the real ones.
def _mk(word_r, word_g, word_b):
    return (word_b << 9) | (word_g << 5) | (word_r << 1)


DAY = [_mk((i * 5) % 8, (i * 3) % 8, (i * 7) % 8) for i in range(48)]
NIGHT = [_mk(max(0, ((i * 5) % 8) - 3), max(0, ((i * 3) % 8) - 2), (i * 7) % 8)
         for i in range(48)]


def facts():
    return cs.derive_engine_facts(Path(AEON))


def row(**kw):
    """A fully-measured, fully-settled row on the NIGHT palette, with overrides."""
    base = dict(k=0, tick=100, centre_x=3488, row=9, dtick=1, lag=0,
                fade_frames=0, fade_request=0, pal_active=0, pal_op=0, pal_base_dirty=0,
                buffer=list(NIGHT), target=list(NIGHT), cram=list(NIGHT))
    base.update(kw)
    return base


def settled_series(n=8, **kw):
    return [row(tick=100 + i, k=i, **kw) for i in range(n)]


def after_a_fade(rows):
    """Prepend two ticks of a fade IN FLIGHT, so `Pal_Target` is authoritative over `rows`.

    The `buf` clause only compares where the observed history says Pal_Target means
    something: a fade seen in flight, and no snap install since. A test whose subject IS
    that comparison has to establish it, exactly as a real run does by crossing the edge."""
    pre = [row(tick=90 + i, k=-9 + i, fade_frames=15 - i, buffer=list(DAY), cram=list(DAY))
           for i in range(2)]
    return pre + rows


# ------------------------------------------------------------------ the derivation

def test_n_is_three_and_carries_its_derivation():
    f = facts()
    assert f.stable_ticks == (cs.COMPOSE_TO_CRAM_TICKS + cs.CRAM_TO_CAPTURED_FRAME_TICKS + 1)
    assert f.stable_ticks == 3
    assert f.chan_mask == 0x0EEE, "the mask must come from Palette_DoFade's own arrival test"
    # every term of N names where it came from
    joined = " ".join(c[1] for c in f.citations)
    for src in ("game_loop.emp", "vblank.emp", "palette.emp"):
        assert src in joined, f"N's derivation does not cite {src}"


#: Every engine file derive_engine_facts() reads. Listed once so a new source added to the
#: derivation lands in the mutation sweep too, instead of the sweep copying a tree the
#: derivation then reads OUT OF the real repo behind its back.
DERIVATION_SOURCES = ("engine/system/game_loop.emp", "engine/system/vblank.emp",
                      "engine/effects/palette.emp", "engine/system/buffers.emp")


@pytest.mark.parametrize("rel,old,new,what", [
    ("engine/system/buffers.emp", "ensure(pal_committer_census() == 14",
     "ensure(pal_committer_census() == 15",
     "the frame-top palette committer census clauses 1-3's exhaustiveness rests on"),
    ("engine/system/game_loop.emp", "jbsr    Palette_Compose", "jbsr    Palette_Composed",
     "the compose call GameLoop's ordering term is read from"),
    ("engine/system/vblank.emp", "jbsr    Enqueue_Dirty_Buffers", "jbsr    Enqueue_Dirty_Buffer",
     "the VBlank enqueue the compose->CRAM latency is read from"),
    ("engine/effects/palette.emp", "jbsr    Palette_DoCycle", "jbsr    Palette_DoCycling",
     "the cycling layer the `layer` clause enumerates"),
    ("engine/effects/palette.emp", "beq   .arrived", "beq   .got_there",
     "Palette_DoFade's arrival test the `$0EEE` mask is read from"),
    ("engine/effects/palette.emp", "btst    #1, Pal_Active", "btst    #3, Pal_Active",
     "the cycling gate the `layer` clause reads, renumbered away from PAL_ACT_CYCLE"),
])
def test_the_derivation_refuses_when_its_source_moves(tmp_path, rel, old, new, what):
    """N may not outlive the engine ordering it is derived from. Proven by MUTATING that
    ordering on disk (in a copy: the committed tree is never written) and watching the
    derivation refuse rather than return a stale 3."""
    for f in DERIVATION_SOURCES:
        dst = tmp_path / f
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(os.path.join(AEON, f), dst)
    assert cs.derive_engine_facts(tmp_path).stable_ticks == 3, "the copy must derive first"

    target = tmp_path / rel
    text = target.read_text()
    assert old in text, f"{rel} no longer contains {old!r} — re-derive this mutation"
    target.write_text(text.replace(old, new))   # EVERY occurrence: one left behind
                                            # would leave the derivation green
    with pytest.raises(cs.DerivationError):
        cs.derive_engine_facts(tmp_path)


# ------------------------------------------------------------------ the real case

def old_set_rows():
    """The 2026-09-13 capture set's own table, parsed out of its README.

    Columns: file | frame | centre x | Pal_Fade_Frames | CRAM 1:2 | prose."""
    text = Path(OLD_SET).read_text()
    out = []
    for m in re.finditer(r"^\|\s*`(t5-[^`]+\.png)`\s*\|\s*(\d+)\s*\|\s*~?(\d+)\s*\|"
                         r"\s*(\d+)\s*\|\s*`\$([0-9A-Fa-f]{4})`\s*\|", text, re.M):
        out.append({"png": m.group(1), "frame": int(m.group(2)), "centre_x": int(m.group(3)),
                    "fade_frames": int(m.group(4)), "tracer": int(m.group(5), 16)})
    assert out, f"no state table parsed out of {OLD_SET} — the case these tests are about is gone"
    return out


def test_the_misnamed_frame_is_named_fading_by_this_tool():
    """THE PROPERTY, on the frame that actually carried the wrong word.

    The tool is given exactly what the 2026-09-13 set recorded for that frame, and asked for
    a filename. It must not be able to produce one containing `settled`."""
    rows = old_set_rows()
    f272 = next((r for r in rows if r["png"] == "t5-f272-settled.png"), None)
    assert f272 is not None, "t5-f272-settled.png is no longer in the old set's table"
    assert f272["fade_frames"] == 11, "the README's own counter column has changed"

    live = row(k=5, tick=f272["frame"], centre_x=f272["centre_x"], row=9,
               fade_frames=f272["fade_frames"])
    v = cs.assess([live], facts())
    assert not v.settled
    assert v.word == "fading"
    assert "Pal_Fade_Frames = 11" in " ".join(v.reasons)

    name = cs.frame_name("in", live, v)
    assert cs.SETTLED_WORD not in name, name
    assert name == "in-k+005-t00272-cx3488-r09-pf11-fading.png", name


def test_the_old_sets_table_cannot_support_a_settled_claim_for_any_row():
    """Not one row of that table is enough to call a frame settled -- the refutation for
    f272, and for the rest the fact that the hand method never took the reads the predicate
    needs. A tracer entry and a counter are not a palette."""
    f = facts()
    verdicts = {}
    for r in old_set_rows():
        # everything the hand method recorded, and nothing it did not
        live = {"k": 0, "tick": r["frame"], "centre_x": r["centre_x"], "row": None,
                "fade_frames": r["fade_frames"]}
        verdicts[r["png"]] = cs.assess([live], f)
    assert verdicts, "the table parsed empty"
    for png, v in verdicts.items():
        assert not v.settled, f"{png} was called settled from the hand table's columns"
        assert v.word != cs.SETTLED_WORD, png
    # f272 is REFUSED on the evidence present; the others are UNDECIDABLE for want of reads
    assert verdicts["t5-f272-settled.png"].decided is True
    assert verdicts["t5-f272-settled.png"].word == "fading"
    undecided = [p for p, v in verdicts.items() if not v.decided]
    assert "t5-f312-sec4096.png" in undecided, (
        "a row whose counter is 0 but whose only palette evidence is ONE tracer entry must "
        "be UNDECIDABLE, not settled: Palette_DoFade steps all 48 words and a near word "
        "arrives early")


def test_the_tracer_entry_reaching_night_is_not_the_palette_arriving():
    """The exact mistake, isolated: counter 0, tracer on its night value, 47 other words
    still short, and a fade genuinely observed in flight just before -- so `Pal_Target` IS
    authoritative and the comparison runs. The predicate must refuse, and on the PALETTE,
    not on the counter; clause 1 passes here."""
    mid = list(DAY)
    mid[16 + 2] = NIGHT[16 + 2]          # CRAM line 1 entry 2, the 2026-09-13 tracer
    r = row(buffer=mid, cram=mid, target=list(NIGHT))
    v = cs.assess(after_a_fade([r]), facts())
    assert not v.settled
    assert v.word == "buf", v.reasons
    assert v.target_checked
    assert "differ from it" in " ".join(v.reasons)


def test_the_same_row_without_an_observed_fade_is_not_refused_on_a_target_that_means_nothing():
    """THE LIVE DEFECT OF 2026-09-16, as a row. Identical state, minus the observed fade:
    `Pal_Target` has never been written (Palette_LoadPal's fade arm is its only writer), so
    comparing against it would refuse 48 words of $0000 and blame a cancelled fade that
    never happened. The comparison must not run, and the frame must certify."""
    r = row(buffer=list(DAY), cram=list(DAY), target=[0] * 48)
    v = cs.assess([r] * 3, facts())
    assert v.settled, v.reasons
    assert not v.target_checked
    assert "has not been written" in v.target_note
    # and the old FALSE CAUSE must appear nowhere in what it tells the reader
    assert "snap arm" not in " ".join(v.reasons)


# ------------------------------------------------------------------ the clauses

def test_a_snap_cancelled_fade_is_caught_by_the_PENDING_BASE_COPY_not_by_the_target():
    """RE-DERIVED 2026-09-16, because this test's original premise was WRONG.

    It used to assert that a snap-cancelled fade is caught by the buffer-vs-target
    comparison. It is not, and cannot be: `Palette_LoadPal`'s snap arm does not only
    `clr.b Pal_Fade_Frames`, it also loads `Pal_Base` and sets `Pal_Base_Dirty`, and the
    next `Palette_Compose` overwrites lines 1-3 wholesale from that base. So:

      * while the copy is PENDING, `Pal_Base_Dirty` is set and clause 3 refuses -- that is
        the real guard, and the only window in which an intermediate buffer is observable;
      * once it has landed the buffer is a COMPLETE palette and `Pal_Target` is stale (the
        snap arm never updates it), so comparing against it would refuse a frame that is
        genuinely settled -- the same false refusal the live run hit, by its other route."""
    f = facts()
    pending = after_a_fade([row(fade_frames=0, pal_base_dirty=1, buffer=list(DAY),
                                cram=list(DAY), target=list(NIGHT))])
    v = cs.assess(pending, f)
    assert v.word == "layer" and not v.settled
    assert "one-shot copy" in " ".join(v.reasons)

    landed = after_a_fade([row(fade_frames=0, pal_base_dirty=1, buffer=list(DAY),
                               cram=list(DAY), target=list(NIGHT))] +
                          [row(tick=200 + i, fade_frames=0, buffer=list(DAY), cram=list(DAY),
                               target=list(NIGHT)) for i in range(f.stable_ticks)])
    v = cs.assess(landed, f)
    assert v.settled, v.reasons
    assert not v.target_checked
    assert "stale" in v.target_note


def test_an_armed_request_is_not_settled():
    assert cs.assess([row(fade_request=1)], facts()).word == "armed"


@pytest.mark.parametrize("kw,word", [
    ({"pal_op": 2}, "layer"),                 # tst.b Pal_Op
    ({"pal_base_dirty": 1}, "layer"),         # tst.b Pal_Base_Dirty
    ({"pal_active": 0b00010}, "layer"),       # btst #1, Pal_Active -- PAL_ACT_CYCLE
])
def test_another_palette_layer_moving_is_not_settled(kw, word):
    """Pal_Fade_Frames == 0 settles ONE of the four layers Palette_Compose runs."""
    series = settled_series(4)
    series[-1].update(kw)
    assert cs.assess(series, facts()).word == word


def test_the_cycle_clause_reads_the_bit_and_not_the_script_pointer():
    """THE VACUOUS-CLAUSE TRAP, pinned. `Pal_Cycle_Script` holds a non-zero pointer to the
    Pal_Cycle_None sentinel whenever cycling is OFF, so a `!= 0` clause would refuse every
    frame ever captured and this tool could never emit `settled` at all. The engine's own
    gate is PAL_ACT_CYCLE; a row carrying a live sentinel pointer must still settle."""
    f = facts()
    assert f.cycle_bit == 0b00010
    series = settled_series(f.stable_ticks)
    for s in series:
        s["pal_cycle_script"] = 0x00FF1234       # a Pal_Cycle_None-shaped pointer
    assert cs.assess(series, f).settled, (
        "a non-zero Pal_Cycle_Script with PAL_ACT_CYCLE clear must NOT block settling")


def test_a_variant_derive_alone_does_not_block_settling():
    """PAL_ACT_VARIANT derives into Pal_Variant_Stage, not into lines 1-3, so it is
    deliberately NOT tested. If it ever starts writing the buffer this row is where the
    decision was made."""
    f = facts()
    assert not (f.cycle_bit & 0b10000)
    series = settled_series(4)
    for s in series:
        s["pal_active"] = 0b10000
    assert cs.assess(series, f).settled


def test_cram_behind_the_buffer_is_not_settled():
    """The compose landed; the VBlank DMA has not. One tick of latency, and the picture is
    still the old palette."""
    v = cs.assess([row(buffer=list(NIGHT), target=list(NIGHT), cram=list(DAY))], facts())
    assert v.word == "cram" and not v.settled


def test_the_derived_number_of_stable_ticks_is_enforced():
    f = facts()
    for n in range(1, f.stable_ticks):
        v = cs.assess(settled_series(n), f)
        assert not v.settled, f"{n} stable sample(s) must not settle; N = {f.stable_ticks}"
        assert v.word == "hold"
    v = cs.assess(settled_series(f.stable_ticks), f)
    assert v.settled and v.word == cs.SETTLED_WORD
    assert v.stable_run == f.stable_ticks


def test_a_cram_change_inside_the_window_restarts_the_run():
    f = facts()
    series = settled_series(f.stable_ticks)
    moved = list(NIGHT)
    moved[0] ^= 0x0002
    series[-2]["cram"] = moved
    v = cs.assess(series, f)
    assert not v.settled and v.word == "hold" and v.stable_run == 1


def test_a_lag_tick_inside_the_window_refuses():
    f = facts()
    series = settled_series(f.stable_ticks + 1)
    series[-1]["lag"] = 1
    v = cs.assess(series, f)
    assert not v.settled and v.word == "lag"
    series = settled_series(f.stable_ticks + 1)
    series[-1]["dtick"] = 2
    assert cs.assess(series, f).word == "lag"


# ------------------------------------------------------------------ the naming property

AXES = {
    "fade_frames": [0, 1, 11],
    "fade_request": [0, 1],
    "pal_op": [0, 3],
    "pal_base_dirty": [0, 1],
    "buffer": [list(NIGHT), list(DAY)],
    "cram": [list(NIGHT), list(DAY)],
}


@pytest.mark.parametrize("authoritative,expected_settled", [(True, 1), (False, 2)])
def test_no_combination_of_state_yields_a_settled_name_unless_the_predicate_settled(
        authoritative, expected_settled):
    """The property over a grid rather than over examples: the produced NAME contains
    `settled` exactly when assess() settled -- run twice, once with `Pal_Target`
    authoritative and once without, because the gating is now part of the answer.

    THE TWO COUNTS ARE THE GATING, and they are derived rather than observed. Every row's
    `target` is NIGHT. With a fade observed in flight the `buf` comparison runs, so the only
    settled corner is the one whose buffer is also NIGHT: 1 of 96. Without one the
    comparison is not applicable, so both the all-NIGHT and the all-DAY corners settle -- a
    stable day palette before the act's first fade is exactly the live 2026-09-16 case: 2 of
    96. If those two numbers are ever equal, the gate has stopped gating."""
    f = facts()
    settled_kw = []
    n = 0
    for combo in itertools.product(*(AXES[k] for k in AXES)):
        kw = dict(zip(AXES, combo))
        series = settled_series(f.stable_ticks)
        for s in series:
            s.update(kw)
        v = cs.assess(after_a_fade(series) if authoritative else series, f)
        name = cs.frame_name("in", series[-1], v)
        assert (cs.SETTLED_WORD in name) == v.settled, (kw, v.word, name)
        if v.settled:
            settled_kw.append(kw)
        n += 1
    assert n == 96, n
    # NOT VACUOUS IN EITHER DIRECTION: a grid whose every cell refused would pass the
    # assertion above while proving nothing, so both arms are counted.
    assert len(settled_kw) == expected_settled, [
        {k: ("NIGHT" if v == list(NIGHT) else "DAY" if v == list(DAY) else v)
         for k, v in kw.items()} for kw in settled_kw]
    assert n - len(settled_kw) == 96 - expected_settled
    for kw in settled_kw:
        assert kw["fade_frames"] == 0 and kw["fade_request"] == 0
        assert kw["pal_op"] == 0 and kw["pal_base_dirty"] == 0
        assert kw["buffer"] == kw["cram"]
    if authoritative:
        assert all(kw["buffer"] == list(NIGHT) for kw in settled_kw), (
            "with Pal_Target authoritative, a buffer that is not the target must refuse")


def test_frame_name_refuses_a_forged_settled_verdict():
    forged = cs.Verdict(cs.SETTLED_WORD, settled=False, decided=True)
    with pytest.raises(ValueError, match="refusing to name"):
        cs.frame_name("in", row(), forged)


def test_frame_name_refuses_a_row_missing_the_state_it_names():
    v = cs.assess(settled_series(3), facts())
    for missing in ("k", "tick", "centre_x", "fade_frames"):
        r = row()
        r[missing] = None
        with pytest.raises(ValueError, match=missing):
            cs.frame_name("in", r, v)


def test_settled_is_not_a_substring_of_any_refusal_word():
    """`unsettled` would have been -- and a glob for `*settled*` would then have swept up
    exactly the frames this whole exercise exists to keep out of an evidence base."""
    f = facts()
    words = set()
    for kw in ({"fade_frames": 9}, {"fade_request": 1}, {"pal_op": 1},
               {"buffer": list(DAY)}, {"cram": list(DAY)}):
        series = settled_series(f.stable_ticks)
        for s in series:
            s.update(kw)
        words.add(cs.assess(series, f).word)
    words.add(cs.assess([{"tick": 1}], f).word)                       # unknown
    words.add(cs.assess(settled_series(1), f).word)                   # hold
    s = settled_series(f.stable_ticks)
    s[-1]["dtick"] = 3
    words.add(cs.assess(s, f).word)                                   # lag
    assert len(words) >= 6, words
    for w in words:
        assert cs.SETTLED_WORD not in w, w
        assert w not in cs.SETTLED_WORD, w


def test_an_unmeasured_row_is_unknown_and_never_green():
    v = cs.assess([{"tick": 4, "k": 0, "centre_x": 0, "fade_frames": None}], facts())
    assert v.word == cs.UNKNOWN_WORD
    assert not v.settled and not v.decided
    assert "carries no fade_frames" in " ".join(v.reasons)


def test_a_refusal_never_names_a_mechanism_the_predicate_did_not_establish():
    """The second half of the live defect, and the worse half: the `buf` refusal asserted
    "the fade STOPPED rather than arrived" on a run where no fade had ever started. A red
    naming a wrong cause is worse than a green meaning less than it looks, because it aims
    the next person's search at a thing that is not there.

    The property: that sentence may only appear where the predicate ESTABLISHED the fade
    history it rests on, i.e. where the comparison actually ran."""
    f = facts()
    cases = []
    # a genuinely stopped fade, with the history established
    stopped = after_a_fade([row(fade_frames=0, buffer=list(DAY), cram=list(DAY),
                                target=list(NIGHT))])
    cases.append(cs.assess(stopped, f))
    # the same-looking state with no fade ever observed
    cases.append(cs.assess([row(buffer=list(DAY), cram=list(DAY), target=[0] * 48)] * 3, f))
    # and after a snap, where the target is stale
    cases.append(cs.assess(after_a_fade(
        [row(fade_frames=0, pal_base_dirty=1, buffer=list(DAY), cram=list(DAY),
             target=list(NIGHT))] +
        [row(tick=300 + i, buffer=list(DAY), cram=list(DAY), target=list(NIGHT))
         for i in range(f.stable_ticks)]), f))
    assert cases[0].word == "buf" and cases[0].target_checked
    assert cases[1].settled and cases[2].settled
    for v in cases:
        if "STOPPED rather than arrived" in " ".join(v.reasons):
            assert v.target_checked, (
                "a refusal claimed the fade stopped without having established that a fade "
                "ran at all -- this is the 2026-09-16 diagnostic defect")
    assert sum(1 for v in cases if "STOPPED rather than arrived" in " ".join(v.reasons)) == 1


def test_target_authority_needs_both_a_fade_and_no_snap_since():
    f = facts()
    assert cs.target_authority([row()])[0] is False
    assert cs.target_authority(after_a_fade([row()]))[0] is True
    assert cs.target_authority(after_a_fade([row(pal_base_dirty=1), row()]))[0] is False
    # the reasons are distinguishable, because they are different engine states
    assert "has not been written" in cs.target_authority([row()])[1]
    assert "stale" in cs.target_authority(after_a_fade([row(pal_base_dirty=1), row()]))[1]
