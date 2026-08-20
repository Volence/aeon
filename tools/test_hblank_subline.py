"""The sweep driver's SUB-LINE analysis — mode detection, the bracket, the window fit.

None of this touches an emulator, a ROM or a server. `hblank_window_sweep` was one long
capture loop with its arithmetic wound through it; the sub-line mode split the two, and this
file tests the half that gets revised. Every case below FABRICATES landings from a window it
chose, hands them to the analysis, and asks whether the window comes back — which is the only
form of test that can fail when the estimator is wrong rather than merely different.

The load-bearing ones are the two the parcel's own numbers rest on:

  * `test_fit_recovers_a_window_it_was_never_told` -- the fit is given landings generated from
    a chosen blanking width and pixel clock and must recover both. This is what stops a fit
    that is merely self-consistent from passing for one that is right.
  * `test_bracket_correction_removes_the_art_sampling_bias` -- the same landings, sampled
    through a sparse column set exactly as the art samples them, must still recover the
    window. Reading `flipX` as the landing instead of bracketing it is a ~1-cycle bias, and a
    1-cycle bias is the whole margin the 4-word ceiling question turns on.
"""
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hblank_window_sweep as H  # noqa: E402


# --------------------------------------------------------------------------- the generator
def synth(n_lo=0, n_hi=200, edge_row=101, px_per_spin=8.75, period_n=48.857,
          n_open_first=16.0, sens_step=1, sens_last=319, words=1):
    """A sweep record built from a KNOWN window, sampled the way the art samples one.

    The generator is the ground truth: it places the landing at `px_per_spin * (N - N0)`
    pixels into whichever row the spin has reached, blanks it between rows, and then reports
    only the columns a sparse `sens_step` column set can see. Nothing here reads the analysis;
    the analysis has to re-derive `period_n`, `px_per_spin` and the implied window from the
    landings alone.
    """
    active_n = 320.0 / px_per_spin
    width_n = period_n - active_n
    # N at which the landing sits at pixel 0 of `edge_row`
    n0_edge = n_open_first + width_n
    sweep = []
    for n in range(n_lo, n_hi + 1):
        # which row is the landing in, and at what pixel
        t = n - n0_edge                       # spins since edge_row's active start
        k = math.floor(t / period_n) if t >= 0 else -int(math.ceil(-t / period_n))
        row = edge_row + k
        off = t - k * period_n                # spins into row `row`'s line
        x = off * px_per_spin
        if x >= 320.0:                        # in the blanking before row+1
            row, x = row + 1, -1.0
        sens = list(range(0, sens_last + 1, sens_step))
        if x <= 0:                            # whole row recoloured from its first column
            fx, fprev, at_left = sens[0], -1, True
        else:
            cand = [c for c in sens if c >= x]
            if not cand:                      # past the art's last observable column
                row, fx, fprev, at_left = row + 1, sens[0], -1, True
            else:
                fx = cand[0]
                below = [c for c in sens if c < fx]
                fprev = below[-1] if below else -1
                at_left = (fx == sens[0])
        rows = {}
        for ln in range(edge_row - 4, edge_row + 8):
            rows[str(ln)] = {"sens": len(sens), "sens_first": sens[0], "sens_last": sens[-1],
                             "new": len(sens) if ln > row else (0 if ln < row else 1),
                             "old": 0 if ln >= row else len(sens), "neither": 0,
                             "first_new_x": fx if ln == row else None}
        sweep.append({"n": n, "flip_row": row, "flip_x": fx, "flip_x_prev": fprev,
                      "flip_at_left": at_left, "rows": rows,
                      "verdicts": {}, "verdicts_subline": {}})
    return {"sweep": sweep, "edge_row": edge_row, "cram_addr": 0x50, "burst_words": words,
            "sensitivity": {str(ln): {"count": len(range(0, sens_last + 1, sens_step)),
                                      "first": 0, "last": sens_last, "max_gap": sens_step}
                            for ln in range(edge_row - 4, edge_row + 8)},
            "_truth": {"px_per_spin": px_per_spin, "period_n": period_n,
                       "width_n": width_n, "n_open": n_open_first, "n_close": n0_edge}}


# --------------------------------------------------------------------------- mode detection
def test_detects_subline_when_the_landing_pixel_moves():
    r = synth()
    assert H.subline_detect(r)["subline"] is True
    assert r["instrument_mode"] == "subline"


def test_detects_line_atomic_when_the_landing_pixel_never_moves():
    """A line-atomic server's whole signature is flipX pinned to one value.

    This is the poison on the detector: if it answered "sub-line" here, the driver would run
    the sub-line fit over an atomic server's captures and report a window from a slope that
    does not exist.
    """
    r = synth()
    for e in r["sweep"]:
        e["flip_x"], e["flip_x_prev"], e["flip_at_left"] = 0, -1, True
    assert H.subline_detect(r)["subline"] is False
    assert r["instrument_mode"] == "atomic"


# --------------------------------------------------------------------------- the fit
@pytest.mark.parametrize("width_target,px", [(122.86, 8.75), (98.0, 8.75), (122.86, 8.60)])
def test_fit_recovers_a_window_it_was_never_told(width_target, px):
    """Generate landings from a chosen blanking width and clock; the fit must find both.

    The three parameter sets are not decoration. A fit that quietly hard-coded the H40
    arithmetic would pass the first and fail the other two, and that is precisely the failure
    the RESULTS doc's "a disagreement is a FINDING, not a tuning knob" clause exists to catch.
    `width_target` is in CYCLES and the period is in spin iterations, hence the /10.
    """
    period = 320.0 / px + width_target / 10.0
    r = synth(px_per_spin=px, period_n=period)
    w = H.subline_fit(r, words=1)
    assert w is not None
    assert w["px_per_spin"] == pytest.approx(px, abs=0.05)
    assert w["period_n"] == pytest.approx(period, abs=0.05)
    assert w["width_cyc"] == pytest.approx(width_target, abs=1.5)
    assert w["n_open"] == pytest.approx(r["_truth"]["n_open"], abs=0.3)
    assert w["n_close"] == pytest.approx(r["_truth"]["n_close"], abs=0.3)


def test_bracket_correction_removes_the_art_sampling_bias():
    """Sparse art must not move the answer, and reading flipX raw must be shown to move it.

    `flipX` is the first column the ART can report, so it always OVERSTATES the landing. The
    bracket midpoint takes that out. Here the same landings are sampled through a 1-in-6
    column set: the bracketed fit must still find the window, and the same fit fed raw flipX
    must land measurably later -- the bias being real is half of why the correction is there.
    """
    r = synth(sens_step=6)
    w = H.subline_fit(r, words=1)
    assert w["n_open"] == pytest.approx(r["_truth"]["n_open"], abs=0.35)
    assert w["width_cyc"] == pytest.approx(10 * r["_truth"]["width_n"], abs=2.0)
    raw = {k: v for k, v in r.items()}
    raw["sweep"] = [dict(e, flip_x_prev=e["flip_x"] - 1) for e in r["sweep"]]
    w_raw = H.subline_fit(raw, words=1)
    # raw flipX overstates the landing pixel, which drags the recovered edge EARLIER
    assert w_raw["n_open"] < w["n_open"] - 0.15


def test_censored_plateau_captures_are_excluded_from_the_fit():
    """A capture flipping at the row's leftmost column says only "at or before pixel 0".

    Those are every spin in the whole blanking window. Folding them in as x = 0 would flatten
    the slope toward zero, so `subline_segments` must drop them -- and it must keep exactly
    the ones that locate a landing.
    """
    r = synth()
    segs = H.subline_segments(r)
    used = {(p["n"]) for s in segs for p in s["pts"]}
    censored = {e["n"] for e in r["sweep"] if e["flip_at_left"]}
    assert used & censored == set()
    assert used | censored == {e["n"] for e in r["sweep"]}


def test_plateaus_are_one_run_per_blanking_window():
    r = synth()
    pl = H.subline_plateaus(r)
    assert len(pl) >= 3
    assert all(p["len"] > 0 for p in pl)
    # every plateau must be about the same width, and about the window the generator chose
    lens = [p["len"] for p in pl]
    assert max(lens) - min(lens) <= 1
    assert sum(lens) / len(lens) == pytest.approx(r["_truth"]["width_n"], abs=1.2)


# --------------------------------------------------------------------------- the verdicts
def _v(flip_row, flip_x, at_left, edge=101, old=0, neither=0, sens=100, sens_first=0):
    out = {"rows": {edge: {"sens": sens, "sens_first": sens_first, "sens_last": 319,
                           "new": sens - old, "old": old, "neither": neither,
                           "first_new_x": flip_x}},
           "flip_row": flip_row, "flip_x": flip_x, "flip_at_left": at_left}
    if flip_row is not None and flip_row != edge:
        out["rows"][flip_row] = {"sens": sens, "sens_first": sens_first, "sens_last": 319,
                                 "new": 1, "old": old, "neither": neither,
                                 "first_new_x": flip_x}
    return H._verdict_subline(out, edge)[0]


def test_a_split_authored_row_is_TOO_EARLY():
    """The defect class the whole substrate item exists to see, and the one the atomic
    convention could not express: the write landed mid-row in the AUTHORED line."""
    assert _v(100, 214, False, old=50) == "TOO EARLY"


def test_a_wholly_recoloured_edge_row_is_CLEAN():
    assert _v(101, 0, True) == "CLEAN"


def test_a_split_edge_row_is_TOO_LATE():
    assert _v(101, 137, False, old=40) == "TOO LATE"


def test_an_edge_row_with_a_trailing_word_left_behind_is_TOO_LATE():
    """First word in blanking, a later word past the active start: the row starts new at its
    leftmost column but columns drawn from the un-written entries still read base. Calling
    that CLEAN is the mistake the atomic classifier made a whole line higher up."""
    assert _v(101, 0, True, old=19) == "TOO LATE"


def test_a_landing_a_whole_row_late_is_TOO_LATE():
    assert _v(102, 0, True) == "TOO LATE"


def test_no_sensitive_columns_on_the_edge_row_is_VACUOUS():
    assert _v(101, 0, True, sens=0) == "VACUOUS"
