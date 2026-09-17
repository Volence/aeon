"""S2-COMPRESSED-ACT row 6: the clip-act ROM bake's own rules, and the arithmetic the
parcel's ground claim rests on.

Runner: build.sh's pre-build `pytest tools -m "not needs_build"` lane
(tools/landing_build.sh runs it once, inside the first shape). DONOR-FREE and BUILD-FREE
by construction — every row builds its own inputs, so these pass on a checkout that has
never run tools/s2_zone_convert.py and has no games/sonic4/data/donors/ at all. The
end-to-end half (a real clip act baked out of a real donor tree and linked into a ROM) is
evidenced by `S2CLIP=s2_ehz_boot ./build.sh`, which no canonical lane runs.

WHAT IS AND IS NOT ASSERTED HERE. The `ground` rows drive the arithmetic against
SYNTHETIC strips and tables whose answer is derived in the row, not copied from a run:
the point is that the reader indexes the ROM's own bytes the way `probe_core` and
`collision_lookup` do, so a paste shifted by 8 or 16 px is visible. Whether a picture
appears is a RUNTIME claim and is tagged for the foreground, not asserted anywhere.
"""

import json
import os
import random
import struct
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import clip_rom_bake as CRB        # noqa: E402
import elect_pool_pages as EPP     # noqa: E402

REPO = os.path.normpath(os.path.join(HERE, ".."))
TILE = 32


# ---------------------------------------------------------------------------
# elect_pool_pages — the election that moved out of regenerate-level.sh's bash
# ---------------------------------------------------------------------------

def _pool(tmp_path, pages, page_bytes=2048, pinned=None, compressible=True):
    """A pool directory shaped like a generated act: N page .bin files + the two
    manifests the election reads. `compressible` decides what salvador can do with the
    bytes, which is what the election is ABOUT."""
    d = tmp_path / "gen"
    d.mkdir(parents=True, exist_ok=True)
    for k in range(pages):
        # `(i * 37 + k) & 0xFF` LOOKS incompressible and is not — it is a short repeating
        # cycle and salvador packs it to nothing, so the first version of this row's raw
        # arm elected ZX0 and the row could not tell the two forms apart. A seeded PRNG is
        # incompressible in the way the election is about, and stays deterministic.
        body = (bytes(page_bytes) if compressible
                else random.Random(1234 + k).randbytes(page_bytes))
        (d / f"act_pool_page{k}.bin").write_bytes(body)
    (d / "ojz_act_pool_manifest.emp").write_text(
        f"pub const OJZ_ACT_POOL_PAGES = {pages}\n")
    (d / "ojz_act_pool_manifest.json").write_text(json.dumps({
        "pages": [{"index": k, "tiles": page_bytes // TILE,
                   "pinned": bool((pinned or [0])[0] == k or k in (pinned or [0]))}
                  for k in range(pages)]}))
    return d


def _elect(d, page_bytes=2048):
    return EPP.elect(str(d), page_bytes, os.path.join(REPO, "tools", "bin", "salvador"),
                     module="m", section="s", symbol_prefix="P", table_symbol="T",
                     emp_name="pool.emp", embed_prefix="gen", log=None)


@pytest.fixture(scope="module", autouse=True)
def _salvador():
    p = os.path.join(REPO, "tools", "bin", "salvador")
    if not os.path.isfile(p) or not os.access(p, os.X_OK):
        subprocess.run(["make", "-C", os.path.join(REPO, "tools", "salvador"), "-s"],
                       check=True)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        subprocess.run(["cp", os.path.join(REPO, "tools", "salvador", "salvador"), p],
                       check=True)


def test_a_compressible_page_elects_zx0_and_an_incompressible_one_elects_raw(tmp_path):
    """The election rule itself: keep ZX0 only for at least a 10% saving.

    Both arms in ONE row and from ONE generator, so "it elected ZX0" cannot be a property
    of the harness. A page of 2048 zero bytes compresses to nothing; a page of a
    pseudo-random byte walk does not, and ZX0's own stream is LONGER than the payload.
    """
    z = _elect(_pool(tmp_path / "a", 1, compressible=True))
    r = _elect(_pool(tmp_path / "b", 1, compressible=False))
    assert z["forms"] == [EPP.FORM_ZX0], "an all-zero page must elect ZX0"
    assert r["forms"] == [EPP.FORM_RAW], "an incompressible page must elect raw"
    assert (tmp_path / "a" / "gen" / "act_pool_page0.zx0").exists()
    assert (tmp_path / "b" / "gen" / "act_pool_page0.raw").exists()
    assert not (tmp_path / "b" / "gen" / "act_pool_page0.zx0").exists()


def test_the_zx0_wrapper_is_the_four_bytes_the_loader_reads(tmp_path):
    """[u16 BE uncompressed size][u8 flags=0][u8 version=2], derived from the page size
    this row chose — not read back out of the file it is checking."""
    d = _pool(tmp_path, 1, page_bytes=1024, compressible=True)
    _elect(d, page_bytes=2048)
    blob = (d / "act_pool_page0.zx0").read_bytes()
    assert struct.unpack(">H", blob[:2])[0] == 1024
    assert blob[2] == 0 and blob[3] == 2


def test_every_elected_blob_is_even_length(tmp_path):
    """The 2026-08-12 boot AddressError: an odd blob lands the successor symbol odd.

    ⚠ THE FIRST VERSION OF THIS ROW COULD NOT SEE ITS OWN SUBJECT. It swept page sizes
    992..2048 of PRNG bytes and asserted evenness; every one of those elected RAW, whose
    length is the page size and is therefore always even, so deleting the padding left
    the row GREEN. The fixture has to PRODUCE an odd ZX0 stream, and which pages do is a
    measurement, not a guess: a low-entropy page (the `i // 7` ramp) at 48, 96, 112 or
    128 bytes packs to 17/31/35/37 bytes, +4 of wrapper = 21/35/39/41 — odd, and each
    saves far more than the election's 10%. The anti-vacuity assertion below is what
    keeps that true: if no elected blob in the sweep is odd BEFORE padding, the row says
    so rather than passing.
    """
    odd_seen = 0
    for n in (48, 96, 112, 128):
        d = tmp_path / f"s{n}" / "gen"
        d.mkdir(parents=True)
        (d / "act_pool_page0.bin").write_bytes(bytes((i // 7) & 0x0F for i in range(n)))
        (d / "ojz_act_pool_manifest.emp").write_text("pub const OJZ_ACT_POOL_PAGES = 1\n")
        (d / "ojz_act_pool_manifest.json").write_text(json.dumps(
            {"pages": [{"tiles": max(1, n // TILE), "pinned": True}]}))
        res = _elect(d, page_bytes=2048)
        assert res["forms"] == [EPP.FORM_ZX0], f"page size {n} did not elect ZX0"
        blob = (d / "act_pool_page0.zx0")
        assert blob.stat().st_size % 2 == 0, f"{blob} is odd at page size {n}"
        # was it odd BEFORE the padding? the padding appends exactly one byte, so an
        # even result whose stream+wrapper was odd is the padding doing its job.
        stream = blob.read_bytes()
        if stream[-1:] == b"\x00" and (len(stream) - 1) % 2 == 1:
            odd_seen += 1
    assert odd_seen, ("no page in this sweep produced an odd elected blob, so this row "
                      "cannot see the padding it exists to check — re-measure the page "
                      "sizes rather than trusting this list")


def test_a_shrinking_pool_leaves_no_stale_page_behind(tmp_path):
    """A clip act's pool is smaller than the shipped act's, and the leftovers are not
    inert: the elected blobs would be EMBEDDED and the .bin payloads would be read by a
    later run that believed them."""
    d = _pool(tmp_path, 4)
    _elect(d)
    assert sorted(p.name for p in d.glob("act_pool_page*.zx0")) == \
        [f"act_pool_page{k}.zx0" for k in range(4)]
    d2 = _pool(tmp_path, 2)          # same directory, fewer pages
    _elect(d2)
    left = sorted(p.name for p in d.glob("act_pool_page*"))
    assert left == ["act_pool_page0.bin", "act_pool_page0.zx0",
                    "act_pool_page1.bin", "act_pool_page1.zx0"], left


def test_a_page_bigger_than_one_vram_page_is_refused_by_name(tmp_path):
    d = _pool(tmp_path, 1, page_bytes=4096)
    with pytest.raises(EPP.ElectError) as exc:
        _elect(d, page_bytes=2048)
    assert "exceeds one page (2048)" in str(exc.value)


def test_the_emitted_emp_embeds_the_elected_extension_for_each_page(tmp_path):
    """Mixed forms in one pool: the embed list must follow the ELECTION, per page."""
    d = tmp_path / "gen"
    d.mkdir()
    (d / "act_pool_page0.bin").write_bytes(bytes(512))                       # -> zx0
    (d / "act_pool_page1.bin").write_bytes(
        random.Random(99).randbytes(512))                                    # -> raw
    (d / "ojz_act_pool_manifest.emp").write_text("pub const OJZ_ACT_POOL_PAGES = 2\n")
    (d / "ojz_act_pool_manifest.json").write_text(json.dumps(
        {"pages": [{"tiles": 16, "pinned": True}, {"tiles": 16, "pinned": False}]}))
    res = _elect(d, page_bytes=2048)
    emp = (d / "pool.emp").read_text()
    exts = ["zx0" if f == EPP.FORM_ZX0 else "raw" for f in res["forms"]]
    for k, ext in enumerate(exts):
        assert f'pub data P{k} = embed("gen/act_pool_page{k}.{ext}")' in emp
    assert "pm_form: 0" in emp and "pm_form: 1" in emp, exts
    assert "pm_flags: 1" in emp and "pm_flags: 0" in emp


# ---------------------------------------------------------------------------
# clip_rom_bake's refusals
# ---------------------------------------------------------------------------

class _Clip:
    def __init__(self, cid):
        self.id = cid


class _Act:
    def __init__(self, n_clips, grid):
        self.clips = [_Clip(f"c{i}") for i in range(n_clips)]
        self.grid_w, self.grid_h = grid


def test_r20_refuses_a_two_clip_act_and_admits_a_one_clip_act():
    """The ROM path reads ONE tileset. Both arms, so the refusal is not vacuous."""
    CRB.check_single_clip(_Act(1, (3, 3)))                 # control: admitted
    with pytest.raises(CRB.ClipRomError) as exc:
        CRB.check_single_clip(_Act(2, (3, 3)))
    assert "R20" in str(exc.value) and "row 7" in str(exc.value)


def _descriptor(tmp_path, w, h):
    p = tmp_path / "act_descriptor.emp"
    p.write_text(f"const GRID_W = {w}\nconst GRID_H = {h}\n")
    return str(p)


def test_r21_holds_the_manifest_grid_to_the_ENGINE_descriptor(tmp_path):
    """DERIVED from the descriptor, not typed: the row reads whatever the engine says.

    A clip act is baked into the SHIPPED act's slot, whose section table and map.toml
    placement rows are fixed by that descriptor, so a mismatched grid writes a local-map
    table of the wrong length for the grid the engine indexes by flat id.
    """
    import act_grid
    gw, gh = act_grid.descriptor_grid()
    CRB.check_act_grid_matches_engine(_Act(1, (gw, gh)))              # control
    with pytest.raises(CRB.ClipRomError) as exc:
        CRB.check_act_grid_matches_engine(_Act(1, (gw + 1, gh)))
    assert "R21" in str(exc.value) and f"{gw}x{gh}" in str(exc.value)
    # and it reads the descriptor it is HANDED, so a different engine grid moves it
    d = _descriptor(tmp_path, gw + 2, gh + 2)
    CRB.check_act_grid_matches_engine(_Act(1, (gw + 2, gh + 2)), descriptor=d)
    with pytest.raises(CRB.ClipRomError):
        CRB.check_act_grid_matches_engine(_Act(1, (gw, gh)), descriptor=d)


def test_r22_refuses_a_dirty_tree_and_admits_a_clean_one(tmp_path, monkeypatch):
    """The restore is `git checkout`, so uncommitted work under what this OVERWRITES
    would be discarded.

    Driven in a scratch git repository rather than against THIS one: the real tree's
    cleanliness is a property of whoever is running the lane, so a row keyed to it
    passes or fails for reasons that have nothing to do with the rule.
    """
    repo = tmp_path / "repo"
    (repo / "sub").mkdir(parents=True)
    (repo / "sub" / "tracked.bin").write_bytes(b"x")
    for cmd in (["git", "init", "-q", "."],
                ["git", "-c", "user.name=t", "-c", "user.email=t@t",
                 "add", "sub/tracked.bin"],
                ["git", "-c", "user.name=t", "-c", "user.email=t@t",
                 "commit", "-qm", "seed"]):
        subprocess.run(cmd, cwd=repo, check=True)
    monkeypatch.setattr(CRB, "REPO", str(repo))
    CRB.check_tree_is_clean(["sub"])                       # control: clean
    (repo / "sub" / "tracked.bin").write_bytes(b"edited")  # the subject
    with pytest.raises(CRB.ClipRomError) as exc:
        CRB.check_tree_is_clean(["sub"])
    assert "R22" in str(exc.value) and "THROWAWAY" in str(exc.value)
    assert "sub/tracked.bin" in str(exc.value)


def test_r22_is_unmeasurable_rather_than_optimistic_without_git():
    """"I could not look" is a refusal, not "it is clean"."""
    with pytest.raises(CRB.ClipRomError) as exc:
        CRB.check_tree_is_clean(["tools"], git="definitely-not-git-on-this-box")
    assert "R22" in str(exc.value) and "could not read" in str(exc.value)


# ---------------------------------------------------------------------------
# the `ground` arithmetic — the static half of row 6's check
# ---------------------------------------------------------------------------

STRIDE, NT_BYTES, COLL_ROWS = 776, 512, 128


def _strips(d, grid_w, n_sections, marks):
    """n_sections strip files, air everywhere but the (section, col, cell_row) in `marks`.

    The layout is `ojz_strip_gen.write_strips_to_file`'s, re-spelled here from the format
    rather than imported, so a row that agrees is two implementations agreeing.
    """
    for n in range(n_sections):
        buf = bytearray(STRIDE * 256)
        for (sec, col, cell_row), attr in marks.items():
            if sec == n:
                buf[STRIDE * col + NT_BYTES + cell_row] = attr
        (d / f"sec{n}_strips_a.bin").write_bytes(bytes(buf))


def test_attr_byte_at_reads_the_cell_probe_core_would_read(tmp_path):
    """The 16-px collision row and the 8-px column, at a world pixel.

    A 16-px world shift must land on a DIFFERENT cell row and an 8-px one on a different
    COLUMN — that is the whole failure R12 guards, and it is invisible in art.
    """
    d = tmp_path / "gen"
    d.mkdir()
    # section 1 of a 3-wide grid, tile column 5 (world x 2048+40..47), cell row 7
    # (world y 112..127): world (2088, 120).
    _strips(d, 3, 9, {(1, 5, 7): 0x2A})
    at = lambda x, y: CRB.attr_byte_at(str(d), 3, 2048, x, y)      # noqa: E731
    assert at(2088, 120) == 0x2A
    assert at(2088, 112) == 0x2A and at(2088, 127) == 0x2A   # same 16-px row
    assert at(2088, 128) == 0                                # next row: the 16-px shift
    assert at(2088, 111) == 0
    assert at(2080, 120) == 0                                # 8 px left: the other column
    assert at(2096, 120) == 0
    assert at(40, 120) == 0                                  # the same offset in section 0


def _tables(tmp_path, entries):
    """heightmaps/angles/solidity, in emit_tables' layout (attr*16, attr, attr)."""
    d = tmp_path / "coll"
    d.mkdir(parents=True, exist_ok=True)
    hm, an, so = bytearray(256 * 16), bytearray(256), bytearray(256)
    for attr, (heights, angle, sol) in entries.items():
        hm[attr * 16:(attr + 1) * 16] = bytes(heights)
        an[attr] = angle
        so[attr] = sol
    (d / "heightmaps.bin").write_bytes(bytes(hm))
    (d / "angles.bin").write_bytes(bytes(an))
    (d / "solidity.bin").write_bytes(bytes(so))
    return d


class _GroundAct:
    section_px = 2048

    def __init__(self, clips=()):
        self.clips = list(clips)


def _ground(tmp_path, gen, coll, monkeypatch, spawn):
    monkeypatch.setattr(CRB, "engine_spawn", lambda *a, **k: spawn)
    monkeypatch.setattr(CRB, "donor_corroboration",
                        lambda *a, **k: {"measured": False, "why": "not this row"})
    monkeypatch.setattr(CRB.clip_manifest, "load", lambda *a, **k: _GroundAct())
    return CRB.ground("unused.json", gen_dir=str(gen), coll_dir=str(coll), log=None)


def test_ground_finds_the_first_solid_cell_and_places_the_surface(tmp_path, monkeypatch):
    """A height byte is solid pixels measured UP from the cell's bottom.

    Derived expectation: a height of 6 in a cell whose top is world y=304 puts the
    surface at 304 + 16 - 6 = 314.
    """
    d = tmp_path / "gen"
    d.mkdir()
    _strips(d, 3, 9, {(0, 32, 19): 7})          # tile col 32 -> world x 256..263
    coll = _tables(tmp_path, {7: ([6] * 16, 0x00, 1)})
    r = _ground(tmp_path, d, coll, monkeypatch, (256, 256))
    assert r["cell_y"] == 19 * 16 == 304
    assert r["height"] == 6
    assert r["surface_y"] == 314
    assert r["fall_px"] == 314 - 256


def test_ground_applies_the_SOLIDITY_CLASS_gate_a_floor_sensor_applies(tmp_path,
                                                                       monkeypatch):
    """parcel 4's own check omitted `and.b d6,d0` and answered solid for 158,442 probes
    Sonic 2 answers air. A cell that is LRB-only is not a floor."""
    d = tmp_path / "gen"
    d.mkdir()
    _strips(d, 3, 9, {(0, 32, 19): 7, (0, 32, 25): 8})
    # attr 7: solidity 2 (SOLID_LRB) -> not a floor; attr 8: 3 (SOLID_ALL) -> a floor
    coll = _tables(tmp_path, {7: ([16] * 16, 0, 2), 8: ([16] * 16, 0, 3)})
    r = _ground(tmp_path, d, coll, monkeypatch, (256, 256))
    assert r["attr"] == 8, "the LRB-only cell must not be the floor a falling sensor finds"
    assert r["cell_y"] == 25 * 16


def test_ground_refuses_when_nothing_solid_is_under_the_spawn(tmp_path, monkeypatch):
    d = tmp_path / "gen"
    d.mkdir()
    _strips(d, 3, 9, {})
    coll = _tables(tmp_path, {})
    with pytest.raises(CRB.ClipRomError) as exc:
        _ground(tmp_path, d, coll, monkeypatch, (256, 256))
    assert "NOTHING SOLID" in str(exc.value) and "falls forever" in str(exc.value)


def test_ground_does_not_land_on_a_hanging_run(tmp_path, monkeypatch):
    """A negative height byte is a near-edge-anchored run, not a floor under a falling
    sensor (`bmi .cl_hanging`). It is reported, not counted as the landing."""
    d = tmp_path / "gen"
    d.mkdir()
    _strips(d, 3, 9, {(0, 32, 19): 7, (0, 32, 30): 8})
    coll = _tables(tmp_path, {7: ([0xF8] * 16, 0, 3),      # -8: hanging
                              8: ([16] * 16, 0, 3)})
    r = _ground(tmp_path, d, coll, monkeypatch, (256, 256))
    assert r["attr"] == 8 and r["cell_y"] == 30 * 16
    assert [y for y, _a, _h in r["hanging_passed"]] == [19 * 16]


def test_engine_spawn_is_derived_from_the_engine_and_the_clamp_can_bite(tmp_path):
    """Camera_Init seeds the camera at start - half a screen and CLAMPS it; the boot
    state then places the player at camera + half a screen. The halves cancel EXCEPT
    where the clamp bites, which is why this is computed and not read off start_local.
    """
    from fg_working_set import ConstantSource
    src = ConstantSource()
    src.load_file(os.path.join(REPO, "engine", "system", "constants.emp"))
    shift = int(src.get("SECTION_SIZE_SHIFT"))
    half_w = int(src.get("CAM_SCREEN_HALF_W"))
    half_h = int(src.get("CAM_SCREEN_HALF_H"))

    def desc(sx, sy, lx, ly, w=3, h=3):
        p = tmp_path / f"d_{sx}_{sy}_{lx}_{ly}.emp"
        p.write_text(
            f"const GRID_W = {w}\nconst GRID_H = {h}\n"
            f"    start_local_x:       ${lx:04X},\n"
            f"    start_local_y:       ${ly:04X},\n"
            f"    start_sec_x:         {sx},\n"
            f"    start_sec_y:         {sy},\n")
        return str(p)

    # well inside the act: the half-screens cancel exactly
    assert CRB.engine_spawn(desc(1, 1, 0x0400, 0x0400)) == \
        ((1 << shift) + 0x400, (1 << shift) + 0x400)
    # at the world origin: the seed would be negative, the clamp holds it at 0, and the
    # player lands half a screen INTO the act rather than at start_local
    assert CRB.engine_spawn(desc(0, 0, 0x0010, 0x0010)) == (half_w, half_h)


def test_the_donor_corroboration_window_is_derived_and_both_sides_of_it_bite(tmp_path,
                                                                            monkeypatch):
    """The window is "at or below the feet, within one 16-px cell" — above would spawn
    the player INSIDE the ground, further than a cell is a fall and not a stand.

    Driven at the boundary and one px outside it on each side, with the donor start and
    PLAYER_Y_RADIUS held fixed, so the row measures the WINDOW and not the geometry.
    """
    from fg_working_set import ConstantSource
    src = ConstantSource()
    src.load_file(os.path.join(REPO, "engine", "system", "constants.emp"))
    radius = int(src.get("PLAYER_Y_RADIUS"))

    donor = tmp_path / "donor"
    (donor / "startpos").mkdir(parents=True)
    start_x, start_y = 96, 640
    (donor / "startpos" / "ZZZ_1.bin").write_bytes(struct.pack(">HH", start_x, start_y))

    import s2_donor
    monkeypatch.setattr(s2_donor, "donor_root", lambda d: str(donor))

    class _C:
        id, donor, zone = "c", "dnr", "ZZZ"
        src = (0, 0, 4096, 1024)
        dst = (0, 0, 4096, 1024)

    feet = start_y + radius                                   # 640 + 19 = 659
    # A FULL-HEIGHT (16) cell's surface IS its top, so the cell top chosen here is the
    # surface the corroboration will read. The window is [feet, feet + 16]:
    #   672  -> delta 13   INSIDE  (the player stands 13 px above the floor and falls)
    #   656  -> delta -3   ABOVE the feet: the player would spawn INSIDE the ground
    #   704  -> delta 45   further than one collision cell: that is a fall, not a stand
    # A 16-px paste shift moves the surface by exactly one cell, which is why 656 and 704
    # are the two arms that matter — they are the shift, one cell each way, from 672.
    for cell_top, expect_ok in ((672, True), (656, False), (704, False)):
        d = tmp_path / f"gen{cell_top}"
        d.mkdir()
        _strips(d, 3, 9, {(0, start_x // 8, cell_top // 16): 9})
        coll = _tables(tmp_path / f"c{cell_top}", {9: ([16] * 16, 0, 3)})
        act = _GroundAct([_C()])
        if expect_ok:
            r = CRB.donor_corroboration(act, str(d), str(coll), 3, 3, 2048, log=None)
            assert r["measured"] and r["ok"], r
            assert r["surface_y"] == cell_top and r["feet_y"] == feet
            assert 0 <= r["delta"] <= 16, r
        else:
            with pytest.raises(CRB.ClipRomError) as exc:
                CRB.donor_corroboration(act, str(d), str(coll), 3, 3, 2048, log=None)
            assert "PASTE SHIFT" in str(exc.value)


def test_the_donor_corroboration_says_so_LOUDLY_when_it_cannot_measure(tmp_path,
                                                                       monkeypatch):
    """A donor with no start position, and a start outside the clip, are both REASONS,
    never quiet passes — the whole value of a second witness is that its absence shows."""
    donor = tmp_path / "donor"
    donor.mkdir()
    import s2_donor
    monkeypatch.setattr(s2_donor, "donor_root", lambda d: str(donor))

    class _C:
        id, donor, zone = "c", "dnr", "ZZZ"
        src = (0, 0, 4096, 1024)
        dst = (0, 0, 4096, 1024)

    r = CRB.donor_corroboration(_GroundAct([_C()]), str(tmp_path), str(tmp_path),
                                3, 3, 2048, log=None)
    assert r["measured"] is False and "no donor start position" in r["why"]

    (donor / "startpos").mkdir()
    (donor / "startpos" / "ZZZ_1.bin").write_bytes(struct.pack(">HH", 9000, 640))
    r = CRB.donor_corroboration(_GroundAct([_C()]), str(tmp_path), str(tmp_path),
                                3, 3, 2048, log=None)
    assert r["measured"] is False and "outside this clip's source rectangle" in r["why"]
