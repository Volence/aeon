"""Gate: `clip_manifest.py validate --json` names the refused clip and the rule, and agrees
with the human mode about everything the human mode says.

RUNNER: build.sh's PRE-build tool-suite lane (`pytest tools -m "not needs_build"`), which
`tools/landing_build.sh` runs once per landing. Nothing here reads a build artifact. Rows
convert their own donors into pytest's tmp tree (the test_clip_manifest pattern) and SKIP
SAYING SO when the donor checkout cannot be resolved.

WHY THIS EXISTS. Aurora's Sonic 2 donor page asked for a machine-readable refusal that says
WHICH clip (id and index) and WHICH rule (design §8, RULED 2026-09-25 block, row-8 work).
The document shape is in clip_manifest.py's header ("`validate --json`").

HOW EACH ROW IS BUILT, and why that is not circular:
  * one mutation of a COMMITTED fixture per rule family the loader can reach (R1-R12, K1-K3,
    the untagged top-level refusal, W2, W3), run through `main()` in BOTH modes;
  * the rule each row expects is the tag the mutation was designed to trip, and the subjects
    it expects are the (kind, index) the mutation touched, with the id READ from the mutated
    document — so the expectation is derived from the input, not copied from the output;
  * the human line must equal "clips.json REFUSED — " + the JSON message, after the JSON's
    warnings rendered as the human mode renders them, and the exit codes must be equal. That
    is the "same sentence" promise, checked on every row.
The byte-identity of the human mode against the pre-`--json` tool was a one-time before/after
proof (report: docs/research/2026-09-25-clip-tooling-aurora-asks.md); a permanent row cannot
hold the old code, so it holds the two modes to each other instead.
"""

import copy
import json
import os
import subprocess
import sys

import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import clip_manifest as CM                  # noqa: E402
import s2_donor as S                        # noqa: E402
import s2_zone_convert as C                 # noqa: E402
from suite_paths import SuitePathError      # noqa: E402

REPO = os.path.dirname(TOOLS)
FIXTURE_DIR = os.path.join(REPO, "games", "sonic4", "data", "clips")
CASES = [(S.S2_FINAL, "EHZ"), (S.S2_FINAL, "CPZ")]
FIXTURES = ("s2_two_clip", "s2_two_clip_pins", "s2_ehz_cpz", "s2_ehz_boot")
REFUSED = "clips.json REFUSED — "


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
    root = str(tmp_path_factory.mktemp("jsondonors"))
    for donor, zone in CASES:
        C.convert_zone(zone, donor, os.path.join(root, donor, zone), quiet=True)
    return root


def _fixture(name):
    with open(os.path.join(FIXTURE_DIR, name, "clips.json")) as fh:
        return json.load(fh)


def _run(capsys, path, donors, as_json):
    argv = ["validate", path, "--donor-root", donors] + (["--json"] if as_json else [])
    rc = CM.main(argv)
    return rc, capsys.readouterr().out


def _both(capsys, tmp_path, donors, doc):
    p = tmp_path / "clips.json"
    p.write_text(json.dumps(doc))
    rc_h, out_h = _run(capsys, str(p), donors, False)
    rc_j, out_j = _run(capsys, str(p), donors, True)
    return rc_h, out_h, rc_j, json.loads(out_j)


def _subjects(doc, want):
    """[(kind, index)] -> the subject dicts, ids READ from the mutated document."""
    out = []
    for kind, i in want:
        entry = doc["clips" if kind == "clip" else "corridors"][i]
        ident = entry.get("id") if isinstance(entry, dict) else None
        out.append({"kind": kind, "index": i, "id": ident if isinstance(ident, str) else None})
    return out


# (tag, base fixture, mutation, [(kind, index)] the mutation touched)
REFUSAL_ROWS = [
    ("R1", "s2_two_clip", lambda d: d.update(schema=2), []),
    ("R2", "s2_two_clip", lambda d: d["act"].update(grid_w=0), []),
    ("R3", "s2_two_clip", lambda d: d.update(id="S2_Two_Clip"), []),
    ("R3", "s2_two_clip", lambda d: d["clips"][0].update(id="EHZ"), [("clip", 0)]),
    ("R3", "s2_two_clip", lambda d: d["clips"][1].update(id=d["clips"][0]["id"]),
     [("clip", 0), ("clip", 1)]),
    ("R3", "s2_two_clip", lambda d: [c.update(region_id="same_region") for c in d["clips"]],
     [("clip", 0), ("clip", 1)]),
    ("R3", "s2_two_clip", lambda d: d["clips"].__setitem__(1, 5), [("clip", 1)]),
    ("R3", "s2_two_clip", lambda d: d["clips"][0].pop("donor"), [("clip", 0)]),
    ("R4", "s2_two_clip", lambda d: d["clips"][0].update(zone="NOT_A_ZONE"), [("clip", 0)]),
    ("R5", "s2_two_clip", lambda d: d["clips"][1]["src_rect"].update(w=0), [("clip", 1)]),
    ("R6", "s2_two_clip", lambda d: (d["clips"][0]["src_rect"].update(x=4100),
                                     d["clips"][0]["dst_rect"].update(x=4)), [("clip", 0)]),
    ("R7", "s2_two_clip", lambda d: d["clips"][1]["dst_rect"].update(w=1024), [("clip", 1)]),
    ("R8", "s2_two_clip", lambda d: d["clips"][1]["dst_rect"].update(x=4096), [("clip", 1)]),
    ("R9", "s2_two_clip", lambda d: d["clips"][0]["src_rect"].update(x=1372 * 8 - 1024),
     [("clip", 0)]),
    ("R10", "s2_two_clip", lambda d: (d["clips"][1]["dst_rect"].update(x=1024),
                                      d["clips"][1].update(unaligned_dst_reason="probe")),
     [("clip", 0), ("clip", 1)]),
    ("R11", "s2_two_clip", lambda d: (d["clips"][1]["dst_rect"].update(x=1024 + 2048),
                                      d["act"].update(grid_w=3)), [("clip", 1)]),
    ("R12", "s2_two_clip", lambda d: d["clips"][0]["src_rect"].update(x=4096 + 8),
     [("clip", 0)]),
    ("K1", "s2_ehz_cpz", lambda d: d["corridors"][0].update(id="Corridor"), [("corridor", 0)]),
    ("K1", "s2_ehz_cpz", lambda d: d["corridors"][0].update(id="ehz_act1"),
     [("clip", 0), ("corridor", 0)]),
    ("K2", "s2_ehz_cpz", lambda d: d["corridors"][0]["dst_rect"].update(w=1300),
     [("corridor", 0)]),
    ("K3", "s2_ehz_cpz", lambda d: d["corridors"][0].update(floor_y=770), [("corridor", 0)]),
    ("R10", "s2_ehz_cpz", lambda d: d["corridors"][0]["dst_rect"].update(x=10960),
     [("clip", 0), ("corridor", 0)]),
]


@pytest.mark.parametrize("tag,base,mutate,touched", REFUSAL_ROWS,
                         ids=[f"{r[0]}-{i}" for i, r in enumerate(REFUSAL_ROWS)])
def test_json_names_the_rule_and_the_clip(capsys, tmp_path, donors, tag, base, mutate, touched):
    doc = copy.deepcopy(_fixture(base))
    mutate(doc)
    rc_h, out_h, rc_j, j = _both(capsys, tmp_path, donors, doc)
    assert rc_h == rc_j == 1, (rc_h, rc_j, out_h[-400:])
    assert set(j) == {"schema", "ok", "refusals", "warnings"}, j
    assert j["schema"] == CM.VALIDATE_JSON_SCHEMA and j["ok"] is False
    assert len(j["refusals"]) == 1, j["refusals"]
    r = j["refusals"][0]
    assert set(r) == {"rule", "subjects", "message"}
    assert r["rule"] == tag, (tag, r["message"][:200])
    assert r["message"].startswith(tag + " ")
    assert r["subjects"] == _subjects(doc, touched), (r["subjects"], touched)
    human = "".join(f"  WARNING: {w['message']}\n" for w in j["warnings"])
    assert out_h == human + REFUSED + r["message"] + "\n"


def test_an_untagged_refusal_has_a_null_rule_and_no_subjects(capsys, tmp_path, donors):
    rc_h, out_h, rc_j, j = _both(capsys, tmp_path, donors, [1, 2, 3])
    assert rc_h == rc_j == 1
    r = j["refusals"][0]
    assert r["rule"] is None and r["subjects"] == []
    assert out_h == REFUSED + r["message"] + "\n"


@pytest.mark.parametrize("name", FIXTURES)
def test_an_accepted_manifest_has_the_same_shape_and_no_refusals(capsys, tmp_path, donors, name):
    rc_h, out_h, rc_j, j = _both(capsys, tmp_path, donors, _fixture(name))
    assert rc_h == rc_j == 0, out_h[-400:]
    assert j == {"schema": CM.VALIDATE_JSON_SCHEMA, "ok": True, "refusals": [],
                 "warnings": j["warnings"]}
    assert out_h.startswith("clips.json OK — ")
    assert out_h.endswith(f"  {len(j['warnings'])} warning(s)\n")


@pytest.mark.parametrize("tag,mutate,touched", [
    # EHZ's painted bbox starts at tile row 1 (zone.json painted_bbox_tiles), so an
    # 8-px-tall rect at y=0 is inside the crop and entirely blank.
    ("W2", lambda d: (d["clips"][0]["src_rect"].update(h=8), d["clips"][0]["dst_rect"].update(h=8)),
     [("clip", 0)]),
    ("W3", lambda d: [(c.update(src_rect=dict(c["src_rect"], w=1024, h=1024),
                                dst_rect={"x": x, "y": 0, "w": 1024, "h": 1024},
                                unaligned_dst_reason="mixed-section probe"))
                      for c, x in zip(d["clips"], (0, 1024))],
     [("clip", 0), ("clip", 1)]),
])
def test_warnings_carry_rule_and_subjects(capsys, tmp_path, donors, tag, mutate, touched):
    doc = copy.deepcopy(_fixture("s2_two_clip"))
    mutate(doc)
    rc_h, out_h, rc_j, j = _both(capsys, tmp_path, donors, doc)
    assert rc_h == rc_j == 0, out_h[-400:]
    assert j["ok"] is True and j["refusals"] == []
    assert [(w["rule"], w["subjects"]) for w in j["warnings"]] == [(tag, _subjects(doc, touched))]
    assert out_h.startswith(f"  WARNING: {j['warnings'][0]['message']}\n")


def test_a_warning_survives_a_later_refusal(capsys, tmp_path, donors):
    """W2 is raised inside the per-clip loop; a later clip's R12 must not lose it."""
    doc = copy.deepcopy(_fixture("s2_two_clip"))
    doc["clips"][0]["src_rect"]["h"] = doc["clips"][0]["dst_rect"]["h"] = 8
    doc["clips"][1]["src_rect"]["x"] = 4096 + 8
    rc_h, out_h, rc_j, j = _both(capsys, tmp_path, donors, doc)
    assert rc_h == rc_j == 1
    assert [w["rule"] for w in j["warnings"]] == ["W2"]
    assert j["refusals"][0]["rule"] == "R12"
    assert j["refusals"][0]["subjects"] == _subjects(doc, [("clip", 1)])
    assert out_h == (f"  WARNING: {j['warnings'][0]['message']}\n"
                     + REFUSED + j["refusals"][0]["message"] + "\n")


def test_the_real_cli_keeps_its_exit_codes(tmp_path, donors):
    """One subprocess pair per outcome: `main()`'s return is what reaches the shell."""
    ok = os.path.join(FIXTURE_DIR, "s2_two_clip", "clips.json")
    bad = tmp_path / "clips.json"
    d = _fixture("s2_two_clip")
    d["schema"] = 2
    bad.write_text(json.dumps(d))
    tool = os.path.join(TOOLS, "clip_manifest.py")
    for path, want in ((ok, 0), (str(bad), 1)):
        for extra in ([], ["--json"]):
            p = subprocess.run([sys.executable, tool, "validate", path, "--donor-root", donors]
                               + extra, capture_output=True, text=True)
            assert p.returncode == want, (path, extra, p.stdout[-300:], p.stderr[-300:])
            if extra:
                assert json.loads(p.stdout)["ok"] is (want == 0)
