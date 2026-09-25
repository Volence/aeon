"""Gate: `clip_act_bake.py bake --json` tells a REFUSAL (rule + which clip) from a CRASH, in
`clip_manifest.py validate --json`'s shape, and agrees with the human mode about everything
the human mode says.

RUNNER: build.sh's PRE-build tool-suite lane (`pytest tools -m "not needs_build"`), which
`tools/landing_build.sh` runs once per landing. Nothing here reads a build artifact. Rows
convert their own donors into pytest's tmp tree (the test_clip_manifest pattern) and SKIP
SAYING SO when the donor checkout cannot be resolved.

WHY THIS EXISTS. Aurora's Sonic 2 donor page (aurora ROADMAP row 213, open item (a)) could not
tell the bake crashing from the bake refusing a paste: a traceback read as "aeon's bake
refused". Booked here as CLIP-BAKE-JSON. The document shape is in clip_act_bake.py's header
("`bake --json`").

WHAT A REFUSAL IS. Exactly what the human mode reports as REFUSED, and nothing else:
  * a ClipManifestError (the manifest loader; human stdout "clip act REFUSED — ..."),
  * a ClipBakeError or subclass (the bake's own; same human line),
  * the FG page budget (fg_page_order's SystemExit; human stderr "REFUSED — FG page budget").
Anything else is a crash in both modes: traceback, exit 1, and no JSON on stdout.

HOW EACH ROW IS BUILT, and why that is not circular:
  * refusals are REAL: a committed fixture mutated to trip one manifest rule, a donor tree
    PAINTED to trip a collision rule (the test_s2_clip_collision method), or the budget
    lowered below a worst window the row first MEASURES unpatched;
  * the rule each row expects is the tag its input was built to trip, and the subjects are
    the (kind, index) it touched, with the id READ from the input;
  * every refusal row runs BOTH modes and requires the human sentence to be the JSON message
    behind the human prefix, and the exit codes to be equal.
The byte-identity of the human mode against the pre-`--json` tool was a one-time before/after
proof (docs/research/2026-09-25-clip-tooling-aurora-asks.md, "Ask 3"); a permanent row cannot
hold the old code, so it holds the two modes to each other instead.
"""

import copy
import json
import os
import shutil
import subprocess
import sys

import numpy as np
import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import clip_act_bake as BAKE                # noqa: E402
import clip_manifest as CM                  # noqa: E402
import collision_pipeline as CP             # noqa: E402
import fg_page_order as fpo                 # noqa: E402
import s2_donor as S                        # noqa: E402
import s2_zone_convert as C                 # noqa: E402
from suite_paths import SuitePathError      # noqa: E402

REPO = os.path.dirname(TOOLS)
FIXTURE_DIR = os.path.join(REPO, "games", "sonic4", "data", "clips")
CASES = [(S.S2_FINAL, "EHZ"), (S.S2_FINAL, "CPZ")]
REFUSED = "clip act REFUSED — "
DOC_KEYS = {"schema", "ok", "refusals", "warnings"}

#: Runs the CLI exactly as `python3 tools/clip_act_bake.py ...` does, with the donor root
#: pointed at this gate's tmp tree (the CLI has no --donor-root, and no row may read the
#: repo's own gitignored donors).
_CLI = ("import sys; sys.path.insert(0, sys.argv[1]); import clip_manifest as CM; "
        "CM.DEFAULT_DONOR_ROOT = sys.argv[2]; import clip_act_bake as B; "
        "sys.argv = [B.__file__] + sys.argv[3:]; sys.exit(B.main())")


def _need(donor):
    try:
        return S.donor_root(donor)
    except (SystemExit, SuitePathError) as e:
        pytest.skip(f"the {donor} donor could not be resolved, so NOTHING in this row "
                    f"is checked: {e}")


@pytest.fixture(autouse=True, scope="module")
def no_working_tree_donors():
    """No row may read the repo's own (gitignored) converted donor trees — see
    test_clip_manifest's fixture of the same name for the incident it prevents."""
    real = CM.DEFAULT_DONOR_ROOT
    CM.DEFAULT_DONOR_ROOT = os.path.join(
        REPO, "tools", "__no_donor_root_for_tests__", "this-path-must-not-exist")
    assert not os.path.exists(CM.DEFAULT_DONOR_ROOT)
    yield
    CM.DEFAULT_DONOR_ROOT = real


@pytest.fixture(scope="module")
def donors(tmp_path_factory):
    for donor, _zone in CASES:
        _need(donor)
    root = str(tmp_path_factory.mktemp("bakejsondonors"))
    for donor, zone in CASES:
        C.convert_zone(zone, donor, os.path.join(root, donor, zone), quiet=True)
    return root


def _fixture(name):
    with open(os.path.join(FIXTURE_DIR, name, "clips.json")) as fh:
        return json.load(fh)


def _write(tmp_path, doc, name="clips.json"):
    p = tmp_path / name
    p.write_text(doc if isinstance(doc, str) else json.dumps(doc))
    return str(p)


def _run(capsys, monkeypatch, root, path, out, as_json, extra=()):
    """main() in-process, as the CLI calls it, with the donor root set for this call only."""
    monkeypatch.setattr(CM, "DEFAULT_DONOR_ROOT", root)
    argv = ["bake", path, "--out", str(out)] + list(extra) + (["--json"] if as_json else [])
    rc = BAKE.main(argv)
    return rc, capsys.readouterr().out


def _both(capsys, monkeypatch, tmp_path, root, path, extra=()):
    rc_h, out_h = _run(capsys, monkeypatch, root, path, tmp_path / "human", False, extra)
    rc_j, out_j = _run(capsys, monkeypatch, root, path, tmp_path / "json", True, extra)
    return rc_h, out_h, rc_j, json.loads(out_j)


def _subjects(doc, want):
    """[(kind, index)] -> the subject dicts, ids READ from the input document."""
    return [{"kind": k, "index": i, "id": doc["clips" if k == "clip" else "corridors"][i]["id"]}
            for k, i in want]


def _one_refusal(j):
    assert set(j) == DOC_KEYS, j
    assert j["schema"] == BAKE.BAKE_JSON_SCHEMA and j["ok"] is False
    assert len(j["refusals"]) == 1, j["refusals"]
    r = j["refusals"][0]
    assert set(r) == {"rule", "subjects", "message"}
    return r


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------

def test_a_manifest_refusal_through_the_bake_names_the_rule_and_the_clip(
        capsys, monkeypatch, tmp_path, donors):
    """A ClipManifestError surfaces through `bake` (load() is its first call) and the human
    mode already calls it REFUSED, so it is a refusal here, with validate --json's record."""
    doc = _fixture("s2_two_clip")
    doc["clips"][1]["dst_rect"]["w"] //= 2                      # R7: dst w != src w
    rc_h, out_h, rc_j, j = _both(capsys, monkeypatch, tmp_path, donors, _write(tmp_path, doc))
    assert rc_h == rc_j == 1
    r = _one_refusal(j)
    assert r["rule"] == "R7" and r["message"].startswith("R7 ")
    assert r["subjects"] == _subjects(doc, [("clip", 1)])
    assert out_h == REFUSED + r["message"] + "\n"
    # and it is validate --json's own record for the same file, not a second spelling of it
    vdoc, vrc = CM.validate_json(str(tmp_path / "clips.json"), donors)
    assert (vrc, vdoc["refusals"], vdoc["warnings"]) == (rc_j, j["refusals"], j["warnings"])


def test_a_warning_before_a_refusal_is_kept_with_its_subjects(
        capsys, monkeypatch, tmp_path, donors):
    doc = _fixture("s2_two_clip")
    doc["clips"][0]["src_rect"]["h"] = doc["clips"][0]["dst_rect"]["h"] = 8    # W2: blank clip
    doc["clips"][1]["src_rect"]["x"] += CM.TILE_PX                                # R12: 8-px shift
    rc_h, out_h, rc_j, j = _both(capsys, monkeypatch, tmp_path, donors, _write(tmp_path, doc))
    assert rc_h == rc_j == 1
    r = _one_refusal(j)
    assert r["rule"] == "R12" and r["subjects"] == _subjects(doc, [("clip", 1)])
    assert [(w["rule"], w["subjects"]) for w in j["warnings"]] == \
        [("W2", _subjects(doc, [("clip", 0)]))]
    assert out_h == f"  WARNING: {j['warnings'][0]['message']}\n" + REFUSED + r["message"] + "\n"


def _paint(tree_dir, cells_by_suffix):
    """Write cell words into a converted tree's plane files: {suffix: {(row, col): word}}.
    test_s2_clip_collision._paint's method, for a tree the row owns."""
    with open(os.path.join(tree_dir, "zone.json")) as fh:
        m = json.load(fh)
    st = CM.geometry_constants()["SECTION_SIZE"] // CM.TILE_PX
    gw = m["grid"]["w"]
    for suffix, cells in cells_by_suffix.items():
        by = {}
        for (r, c), w in cells.items():
            by.setdefault((r // st) * gw + c // st, []).append((r % st, c % st, w))
        for n, items in by.items():
            p = os.path.join(tree_dir, f"section_{n}.{suffix}.bin")
            with open(p, "rb") as fh:
                g = np.frombuffer(fh.read(), dtype=">u2").reshape(st, st).copy()
            for r, c, w in items:
                g[r, c] = w
            with open(p, "wb") as fh:
                fh.write(g.astype(">u2").tobytes())


@pytest.fixture
def paintable(donors, tmp_path):
    """(donor root, EHZ tree dir): a private copy a row may paint into."""
    donor, zone = CASES[0]
    root = str(tmp_path / "painted")
    dst = os.path.join(root, donor, zone)
    shutil.copytree(os.path.join(donors, donor, zone), dst)
    return root, dst


def _one_clip_doc(src):
    donor, zone = CASES[0]
    return {"schema": 1, "units": "world_px", "id": "xover_cut",
            "act": {"grid_w": 1, "grid_h": 1},
            "clips": [{"id": "ehz_cut", "donor": donor, "zone": zone,
                       "src_rect": dict(zip(("x", "y", "w", "h"), src)),
                       "dst_rect": {"x": 0, "y": 0, "w": src[2], "h": src[3]}}]}


def test_a_bake_refusal_names_its_rule_and_the_clip(capsys, monkeypatch, tmp_path, paintable):
    """C1, a ClipBakeError subclass raised by the BAKE (the manifest is valid): the clip's
    source rectangle takes one end of a painted loop and leaves the other behind."""
    root, tree = paintable
    cells = ((40, 100), (100, 100))
    _paint(tree, {"collattr": {c: CP.XOVER_TO_B << CP.XOVER_SHIFT for c in cells},
                  "collattrb": {c: CP.XOVER_TO_A << CP.XOVER_SHIFT for c in cells}})
    doc = _one_clip_doc((0, 0, 2048, 512))          # takes tile row 40, leaves row 100
    path = _write(tmp_path, doc)
    assert CM.validate_json(path, root)[1] == 0      # the MANIFEST is fine: the bake refuses
    rc_h, out_h, rc_j, j = _both(capsys, monkeypatch, tmp_path, root, path)
    assert rc_h == rc_j == 1
    r = _one_refusal(j)
    assert r["rule"] == "C1" and r["message"].startswith("C1 ")
    assert r["subjects"] == _subjects(doc, [("clip", 0)])
    assert out_h.endswith("\n" + REFUSED + r["message"] + "\n")


def test_an_act_level_bake_refusal_has_no_subjects(capsys, monkeypatch, tmp_path, paintable):
    """C3: a height profile rotate_profile refuses, interned by the act. It is found in the
    act's attr set after the clips are merged, so it is about the act, not a clip."""
    root, tree = paintable
    _paint(tree, {"collattr": {(10, 10): 0x18 | (CP.SOL_ALL << CP.PLANE_SOL_SHIFT)}})
    path = _write(tmp_path, _one_clip_doc((0, 0, 2048, 1024)))
    rc_h, out_h, rc_j, j = _both(capsys, monkeypatch, tmp_path, root, path)
    assert rc_h == rc_j == 1
    r = _one_refusal(j)
    assert r["rule"] == "C3" and r["subjects"] == []
    assert out_h.endswith("\n" + REFUSED + r["message"] + "\n")


def test_an_untagged_bake_refusal_has_a_null_rule(capsys, monkeypatch, tmp_path, donors):
    """--expect-worst that the act does not meet: a ClipBakeError with no tag."""
    path = os.path.join(FIXTURE_DIR, "s2_ehz_boot", "clips.json")
    want = fpo.load_budget_constants()["PAGE_FRAMES"] + 1   # no act's worst window can be it
    rc_h, out_h, rc_j, j = _both(capsys, monkeypatch, tmp_path, donors, path,
                                 extra=["--expect-worst", str(want)])
    assert rc_h == rc_j == 1
    r = _one_refusal(j)
    assert r["rule"] is None and r["subjects"] == []
    assert r["message"].startswith(f"--expect-worst {want} ")
    assert out_h.endswith("\n" + REFUSED + r["message"] + "\n")


def test_the_page_budget_is_a_refusal_not_a_crash(capsys, monkeypatch, tmp_path, donors):
    """The FG page budget refuses by SystemExit (fg_page_order's, shared with the OJZ
    generator), not by ClipBakeError. It is still a refusal: the human mode says REFUSED.

    The budget is lowered to one frame below the act's worst window, which the row MEASURES
    unpatched first, so the act really is over and by the smallest possible margin."""
    path = os.path.join(FIXTURE_DIR, "s2_ehz_boot", "clips.json")
    _act, _st, _m, v1, _v2 = BAKE.bake(path, out_dir=str(tmp_path / "measure"),
                                       donor_root=donors, log=None)
    assert v1["ok"], v1                                       # it fits at the real budget
    real = fpo.load_budget_constants

    def lowered(*a, **k):
        c = dict(real(*a, **k))
        c["PAGE_FRAMES"] = v1["worst"] - 1
        return c
    monkeypatch.setattr(fpo, "load_budget_constants", lowered)
    rc_j, out_j = _run(capsys, monkeypatch, donors, path, tmp_path / "json", True)
    j = json.loads(out_j)
    assert rc_j == 1
    r = _one_refusal(j)
    assert r["rule"] == BAKE.BUDGET_RULE and r["subjects"] == []
    # the human mode: fg_page_order's SystemExit, whose text is the prefix + this message
    with pytest.raises(SystemExit) as e:
        _run(capsys, monkeypatch, donors, path, tmp_path / "human", False)
    assert e.value.code == BAKE._BUDGET_PREFIX + r["message"]
    assert r["message"].startswith("FG page budget: ")


# ---------------------------------------------------------------------------
# Success
# ---------------------------------------------------------------------------

def _strip_seconds(x):
    if isinstance(x, dict):
        return {k: _strip_seconds(v) for k, v in x.items() if k != "seconds"}
    if isinstance(x, list):
        return [_strip_seconds(v) for v in x]
    return x


def test_success_is_the_same_shape_and_bakes_the_same_tree(capsys, monkeypatch, tmp_path, donors):
    """s2_ehz_cpz: two clips and a corridor. --json writes the same tree the human mode
    writes; only the report on stdout differs."""
    path = os.path.join(FIXTURE_DIR, "s2_ehz_cpz", "clips.json")
    rc_h, out_h, rc_j, j = _both(capsys, monkeypatch, tmp_path, donors, path)
    assert rc_h == rc_j == 0, out_h[-400:]
    assert j == {"schema": BAKE.BAKE_JSON_SCHEMA, "ok": True, "refusals": [], "warnings": []}
    assert out_h.splitlines()[-1].startswith("clip act baked: ")
    h, js = tmp_path / "human", tmp_path / "json"
    names = sorted(os.listdir(h))
    assert names == sorted(os.listdir(js)) and "clipact.json" in names
    for n in names:
        a, b = (h / n).read_bytes(), (js / n).read_bytes()
        if n == "clipact.json":
            # wall clock, and the corridor sheet's path, which names the out dir it is in
            a, b = (_strip_seconds(json.loads(x.replace(d, b"OUT")))
                    for x, d in ((a, b"/human/"), (b, b"/json/")))
        assert a == b, n


def test_success_carries_warnings(capsys, monkeypatch, tmp_path, donors):
    doc = _fixture("s2_two_clip")
    doc["clips"][0]["src_rect"]["h"] = doc["clips"][0]["dst_rect"]["h"] = 8    # W2 only
    rc_h, out_h, rc_j, j = _both(capsys, monkeypatch, tmp_path, donors, _write(tmp_path, doc))
    assert rc_h == rc_j == 0
    assert j["ok"] is True and j["refusals"] == []
    assert [(w["rule"], w["subjects"]) for w in j["warnings"]] == \
        [("W2", _subjects(doc, [("clip", 0)]))]
    assert out_h.startswith(f"  WARNING: {j['warnings'][0]['message']}\n")


# ---------------------------------------------------------------------------
# Crashes and usage errors
# ---------------------------------------------------------------------------

def _cli(donors, *args):
    return subprocess.run([sys.executable, "-c", _CLI, TOOLS, donors] + list(args),
                          capture_output=True, text=True)


@pytest.mark.parametrize("case", ["not_json", "missing_path"])
def test_a_crash_is_exit_1_with_no_json(tmp_path, donors, case):
    """Not a refusal: the manifest was never judged. Both modes give a traceback, exit 1 and
    an EMPTY stdout, so a reader that finds no JSON document knows it is a crash."""
    path = _write(tmp_path, "{not json") if case == "not_json" else str(tmp_path / "absent.json")
    for extra in ([], ["--json"]):
        p = _cli(donors, "bake", path, "--out", str(tmp_path / "out"), *extra)
        assert p.returncode == 1, (extra, p.stdout[-300:], p.stderr[-300:])
        assert p.stdout == "", (extra, p.stdout[-300:])
        assert "Traceback" in p.stderr
        with pytest.raises(json.JSONDecodeError):
            json.loads(p.stdout)


def test_a_crash_is_not_wrapped_in_process(monkeypatch, tmp_path, donors):
    """The exception reaches the caller unchanged: --json catches refusals only."""
    monkeypatch.setattr(CM, "DEFAULT_DONOR_ROOT", donors)
    with pytest.raises(json.JSONDecodeError):
        BAKE.main(["bake", _write(tmp_path, "{not json"), "--json"])


def test_a_usage_error_under_json_prints_the_human_usage(capsys, tmp_path):
    path = os.path.join(FIXTURE_DIR, "s2_ehz_boot", "clips.json")
    rc = BAKE.main(["bake", path, "--json", "--frob"])
    assert rc == 1
    assert capsys.readouterr().out == f"ERROR: unknown argument '--frob'\n{BAKE.USAGE}\n"


def test_the_real_cli_keeps_its_exit_codes(tmp_path, donors):
    """One subprocess pair per outcome: what main() returns is what reaches the shell."""
    ok = os.path.join(FIXTURE_DIR, "s2_ehz_boot", "clips.json")
    d = copy.deepcopy(_fixture("s2_ehz_boot"))
    d["schema"] = CM.SCHEMA + 1
    bad = _write(tmp_path, d)
    for path, want in ((ok, 0), (bad, 1)):
        for extra in ([], ["--json"]):
            p = _cli(donors, "bake", path, "--out", str(tmp_path / "out"), *extra)
            assert p.returncode == want, (path, extra, p.stdout[-300:], p.stderr[-300:])
            if extra:
                j = json.loads(p.stdout)
                assert j["ok"] is (want == 0)
                assert [r["rule"] for r in j["refusals"]] == ([] if want == 0 else ["R1"])
