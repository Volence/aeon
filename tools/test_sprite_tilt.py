"""Unit tests for the ground-angle sprite tilt (Player_ApplyTilt).

Three layers, and the split matters:

1. THE MODEL. S3K's Animate_Sonic arithmetic is transcribed once, in
   sprite_tilt_gate.py, from sonic3k.asm:24808-24862. These tests do NOT re-transcribe
   it -- they assert INVARIANTS the transcription must satisfy if it is right (bands
   exactly 32 angle units wide, centred on multiples of $20; the two facings mirror
   images of each other; all eight orientations reachable; the flip pair is a genuine
   180 deg). A copy of the boundary table would prove nothing about a mis-copied `not`.

2. THE ROUTINE, executed. Over a COMMITTED CUT of a real ROM
   (tools/fixtures/sprite_tilt_cut.json), because build.sh's pytest lane runs BEFORE
   sigil and a test opening s4.debug.bin here would measure a previous build --
   documented at build.sh:61-72, where that happened twice. The same sweep runs against
   the FRESH artifact in build.sh's post-sigil block, which also fails loudly if this
   cut has gone stale.

3. THE ART. The tilt makes 36 previously-unreachable mapping frames reachable during
   ordinary running. This checks, from the shipped blobs, that every one of them exists,
   fits the 32-tile character VRAM window, and what it costs in Important DMA slots.
"""

import json
import pathlib
import struct
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import sprite_tilt_gate as stg  # noqa: E402

FIXTURE = TOOLS / "fixtures" / "sprite_tilt_cut.json"

# games/sonic4/config/constants.emp / engine/system/constants.emp. Mirrored here and
# pinned against the source by test_constants_still_match below, so a moved wall fails
# as a named mismatch rather than as a quietly weaker gate.
VRAM_TEST_SONIC = 0x03C0
VRAM_TEST_OBJ = 0x03E0
CHARACTER_WINDOW_TILES = VRAM_TEST_OBJ - VRAM_TEST_SONIC     # 32
DMA_IMPORTANT_SLOTS = 12
DPLC_ENTRY_RESERVE = 2


# ---------------------------------------------------------------- 1. the model

def test_bands_are_32_units_wide_and_centred_on_the_axes():
    """The `+$10` bias exists so the snap rounds to NEAREST. If it were dropped (or
    doubled) the bands would still be 32 wide but would start on the axes instead of
    straddling them, and the character would be drawn a whole 45 deg late on every
    slope. Assert the centring, which is what the bias buys."""
    for facing_left in (False, True):
        for k in range(8):
            centre = (k * 0x20) & 0xFF
            here = stg.model_orientation(centre, facing_left)
            # +/-15 units either side of a band centre must stay in the same band
            for d in range(-15, 16):
                assert stg.model_orientation((centre + d) & 0xFF, facing_left) == here, (
                    "band centred on $%02X breaks at offset %+d (facing %s)"
                    % (centre, d, "L" if facing_left else "R"))


def test_every_angle_lands_in_a_band_and_all_eight_orientations_are_reachable():
    for facing_left in (False, True):
        seen = {stg.model_orientation(a, facing_left) for a in range(256)}
        blocks = {b for b, _ in seen}
        assert blocks == {0, 1, 2, 3}, "not all four art blocks are selectable"
        assert len(seen) == 8, (
            "expected 8 (block, flip) orientations 45 deg apart, got %d" % len(seen))


def test_the_flip_delta_is_a_real_180_degree_rotation():
    """`moveq #3` in S3K sets BOTH of its flip bits; ours is $06 for the same reason.
    A single bit would be a mirror, not a rotation -- the bug that makes a character
    run up the far side of a loop face the wrong way.

    The half-turn relation is: angle and angle+$80 share an art block and differ in the
    flip. It holds everywhere EXCEPT the eight angles congruent to $10 mod $20, and that
    exception is not slop -- it is the exact footprint of S3K's `subq.b #1` bias, which
    applies only to the positive half of the circle and so shifts the four upper band
    edges one unit against the four lower ones. Asserting the exception set is exactly
    those eight is asserting that the bias is the ONLY asymmetry in the mapping."""
    assert bin(stg.FLIP_PAIR).count("1") == 2
    assert stg.FLIP_PAIR == (1 << stg.RF_XFLIP_BIT) | (1 << stg.RF_YFLIP_BIT)
    for facing_left in (False, True):
        exceptions = set()
        for a in range(256):
            block, flip = stg.model_orientation(a, facing_left)
            opp_block, opp_flip = stg.model_orientation((a + 0x80) & 0xFF, facing_left)
            if block != opp_block or flip == opp_flip:
                exceptions.add(a)
        assert exceptions == {a for a in range(256) if a % 0x20 == 0x10}, (
            "the half-turn relation breaks somewhere other than the bias boundaries "
            "(facing %s): %s" % ("L" if facing_left else "R",
                                 sorted("$%02X" % a for a in exceptions)))


def test_each_orientation_is_one_contiguous_45_degree_arc():
    """Eight orientations, each a single unbroken arc of the circle, together covering
    all 256 angles. A mis-ordered mask or a stray sign would show up here as a class
    split into two runs long before it showed up as a wrong-looking sprite."""
    for facing_left in (False, True):
        classes = {}
        for a in range(256):
            classes.setdefault(stg.model_orientation(a, facing_left), []).append(a)
        assert len(classes) == 8
        assert sum(len(v) for v in classes.values()) == 256
        for key, angles in classes.items():
            # contiguous modulo 256: rotate so the run does not straddle $FF -> $00
            gaps = [i for i in range(len(angles) - 1) if angles[i + 1] != angles[i] + 1]
            wraps = 1 if (angles[0] == 0 and angles[-1] == 255) else 0
            assert len(gaps) <= wraps, (
                "orientation %r is not a single arc (facing %s): %d gaps"
                % (key, "L" if facing_left else "R", len(gaps)))
            assert 31 <= len(angles) <= 33, (
                "orientation %r spans %d angle units, not ~32 (45 deg)" % (key, len(angles)))


def test_the_two_facings_are_mirror_images():
    """THE hazard the brief names: fold facing into the angle on the wrong side of the
    branch and the tilt is right running one way and mirrored running the other -- which
    looks correct in half of any test. The two facings must be exact mirrors about the
    vertical: block(angle, R) == block(-angle, L)."""
    for a in range(256):
        br, fr = stg.model_orientation(a, False)
        bl, fl = stg.model_orientation((-a) & 0xFF, True)
        assert (br, fr) == (bl, fl), (
            "facing is not folded symmetrically: angle $%02X facing R gives (block %d, "
            "flip $%02X) but angle $%02X facing L gives (block %d, flip $%02X)"
            % (a, br, fr, (-a) & 0xFF, bl, fl))


def test_flat_ground_is_the_identity():
    """Angle 0 must select block 0 with no flip, in BOTH facings -- otherwise every
    flat-ground frame in the game moves and the replay net diverges everywhere rather
    than only on slopes."""
    for facing_left in (False, True):
        assert stg.model_orientation(0, facing_left) == (0, 0)
        for anim, base in ((stg.ANIM_WALK, 0x01), (stg.ANIM_RUN, 0x21)):
            frame, flags = stg.model_apply(anim, 0, facing_left, base)
            assert frame == base
            assert flags == ((1 << stg.ST_XFLIP_BIT) if facing_left else 0)


def test_the_walk_and_run_blocks_tile_without_overlap():
    """The block geometry the routine indexes. Four walk blocks of 8 must end exactly
    where the four run blocks of 4 begin -- the same claim player_common.emp's
    comptime ensure makes, asserted here from the other side."""
    walk = {stg.TILT_WALK_BASE + b * stg.TILT_WALK_LEN + i
            for b in range(stg.TILT_SETS) for i in range(stg.TILT_WALK_LEN)}
    run = {stg.TILT_RUN_BASE + b * stg.TILT_RUN_LEN + i
           for b in range(stg.TILT_SETS) for i in range(stg.TILT_RUN_LEN)}
    assert not (walk & run)
    assert max(walk) + 1 == min(run)
    assert walk | run == set(range(0x01, 0x31))


# ------------------------------------------------- 2. the routine, executed

def _shapes():
    if not FIXTURE.exists():
        return []
    return stg.fixture_shapes(FIXTURE)


def test_both_canonical_shapes_are_committed():
    """The routine is NOT byte-identical across build shapes — its
    `jsr RefreshSpritePieceCount` is an absolute-short operand and the DEBUG island
    moves the callee. One cut would be checkable in one shape and stale in the other,
    so both are committed and build.sh checks whichever shape it just built."""
    assert set(_shapes()) == {"s4.lst", "s4.debug.lst"}, (
        "committed cuts: %s — regenerate with tools/sprite_tilt_gate.py --emit-fixture "
        "for BOTH ./build.sh and DEBUG=1 ./build.sh" % _shapes())


@pytest.fixture(scope="module", params=_shapes() or ["<missing>"])
def cut(request):
    if request.param == "<missing>":
        pytest.fail("tools/fixtures/sprite_tilt_cut.json is missing — regenerate with "
                    "tools/sprite_tilt_gate.py --emit-fixture")
    return stg.load_fixture(FIXTURE, request.param)


def test_the_cut_decodes_cleanly(cut):
    rom, syms = cut
    prog, listing = stg.decode(rom, syms["Player_ApplyTilt"], syms["_end"])
    assert listing, "the routine cut decoded to nothing"
    assert listing[-1][2] == "rts", "the cut does not end at an rts — wrong extent"


def test_rom_bytes_match_the_model_over_the_full_sweep(cut):
    """The load-bearing one: the ACTUAL instruction bytes, decoded by capstone (not by
    our own assembler's opinion of what it emitted) and executed, against the model."""
    rom, syms = cut
    checks, fails, frames, _ = stg.sweep(rom, syms)
    assert not fails, "\n".join(fails[:8])
    assert checks > 4000, "the sweep shrank to %d comparisons" % checks
    assert frames == set(range(0x01, 0x31)), (
        "the sweep did not reach every tilted frame; got %d of 48" % len(frames))


def test_the_executor_refuses_an_instruction_it_does_not_model(cut):
    """The gate's green is only worth anything because it cannot skip. Poison the cut
    with an unmodelled opcode and confirm it raises rather than passing."""
    rom, syms = cut
    poisoned = bytearray(rom)
    poisoned[syms["Player_ApplyTilt"]:syms["Player_ApplyTilt"] + 2] = b"\x48\x40"  # swap d0
    with pytest.raises((stg.UnsupportedInstruction, SystemExit)):
        stg.sweep(bytes(poisoned), syms)


def test_a_flipped_facing_branch_is_caught(cut):
    """The mirror bug, injected at the byte level: turn `bne .faced` ($6602) into
    `beq .faced` ($6702) and the tilt mirrors on one side only. The sweep must catch it."""
    rom, syms = cut
    poisoned = bytearray(rom)
    idx = poisoned.index(b"\x66\x02", syms["Player_ApplyTilt"], syms["_end"])
    poisoned[idx:idx + 2] = b"\x67\x02"
    _, fails, _, _ = stg.sweep(bytes(poisoned), syms)
    assert fails, "flipping the facing branch produced no mismatch — the sweep is vacuous"


def test_a_dropped_round_bias_is_caught(cut):
    """`addi.b #$10,d2` -> `addi.b #$00,d2`: the snap becomes floor instead of nearest,
    which moves every band boundary by 22.5 deg."""
    rom, syms = cut
    poisoned = bytearray(rom)
    idx = poisoned.index(b"\x06\x02\x00\x10", syms["Player_ApplyTilt"], syms["_end"])
    poisoned[idx:idx + 4] = b"\x06\x02\x00\x00"
    _, fails, _, _ = stg.sweep(bytes(poisoned), syms)
    assert fails, "dropping the round bias produced no mismatch"


def test_a_single_bit_flip_pair_is_caught(cut):
    """`moveq #$6` -> `moveq #$4`: a mirror instead of a 180 deg rotation."""
    rom, syms = cut
    poisoned = bytearray(rom)
    idx = poisoned.index(b"\x72\x06", syms["Player_ApplyTilt"], syms["_end"])
    poisoned[idx:idx + 2] = b"\x72\x04"
    _, fails, _, _ = stg.sweep(bytes(poisoned), syms)
    assert fails, "halving the flip pair produced no mismatch"


def test_a_missing_cache_refresh_is_caught(cut):
    """Drop the `jsr RefreshSpritePieceCount` and Sst.frame_off goes stale against the
    frame the tilt just picked — the renderer draws the pre-tilt frame's pieces."""
    rom, syms = cut
    poisoned = bytearray(rom)
    idx = poisoned.index(b"\x4e\xb8", syms["Player_ApplyTilt"], syms["_end"])
    poisoned[idx:idx + 4] = b"\x4e\x71\x4e\x71"     # nop nop
    _, fails, _, _ = stg.sweep(bytes(poisoned), syms)
    assert any("RefreshSpritePieceCount" in f for f in fails), (
        "removing the cache refresh was not noticed: %r" % fails)


# ------------------------------------------------------------------ 3. the art

def _dplc_frames(path):
    """[(entry_count, tile_count)] per frame. Format spec: engine/objects/dplc.emp."""
    data = path.read_bytes()
    first = struct.unpack_from(">H", data, 0)[0]
    out = []
    for i in range(first // 2):
        off = struct.unpack_from(">H", data, i * 2)[0]
        n = struct.unpack_from(">H", data, off)[0]
        tiles = 0
        for e in range(n):
            w = struct.unpack_from(">H", data, off + 2 + e * 2)[0]
            tiles += ((w >> 12) & 0xF) + 1
        out.append((n, tiles))
    return out


DPLCS = {
    "sonic": "games/sonic4/data/dplc/optimized/sonic.bin",
    "tails": "games/sonic4/data/dplc/optimized/tails.bin",
    "knuckles": "games/sonic4/data/dplc/knuckles.bin",
}

TILTED_FRAMES = list(range(0x01, 0x31))
UPRIGHT_FRAMES = list(range(0x01, 0x09)) + list(range(0x21, 0x25))
NEWLY_REACHABLE = [f for f in TILTED_FRAMES if f not in UPRIGHT_FRAMES]


@pytest.mark.parametrize("name", sorted(DPLCS))
def test_every_tilted_frame_exists_in_the_shipped_sheet(name):
    frames = _dplc_frames(ROOT / DPLCS[name])
    assert len(frames) > max(TILTED_FRAMES), (
        "%s's DPLC has only %d frames — the tilt would index off the end"
        % (name, len(frames)))


@pytest.mark.parametrize("name", sorted(DPLCS))
def test_every_tilted_frame_fits_the_character_vram_window(name):
    """The 32-tile DPLC streaming window is why the tilt costs zero VRAM. The build
    already guards the peak across ALL frames (collision_data.emp); this asserts it
    specifically over the set the tilt makes reachable, so the claim is measured on the
    subject rather than inherited from a wider guard."""
    frames = _dplc_frames(ROOT / DPLCS[name])
    worst = max((frames[f][1], f) for f in TILTED_FRAMES)
    assert worst[0] <= CHARACTER_WINDOW_TILES, (
        "%s frame $%02X needs %d tiles, window is %d"
        % (name, worst[1], worst[0], CHARACTER_WINDOW_TILES))


def test_the_tilt_does_not_worsen_sonics_important_queue_peak():
    """The tilt makes 36 more mapping frames selectable during ordinary running, so
    the question is whether any of them costs more Important queue slots than what was
    already reachable. Measured, not assumed.

    HISTORY, because this assertion INVERTED and the reason matters. It used to be a
    ratchet: Sonic's sheet was over budget (13 entries on two frames, neither
    script-reachable), the worst reachable was 12 on LookUp, and the tilt added a
    second 12 at $0E — so this test pinned `at_cap == [$0E]` to keep that debt from
    growing. The d-47 `targeted` re-cut (parcel/dplc-entry-recut) paid the debt: no
    frame in the sheet exceeds DMA_IMPORTANT_SLOTS - DPLC_ENTRY_RESERVE any more.
    So the pin now asserts the debt is GONE rather than bounded, and $0E going back
    over the wall fails here as well as at collision_data.emp's `ensure`."""
    frames = _dplc_frames(ROOT / DPLCS["sonic"])
    new_peak = max(frames[f][0] for f in NEWLY_REACHABLE)
    old_peak = max(frames[f][0] for f in UPRIGHT_FRAMES)
    wall = DMA_IMPORTANT_SLOTS - DPLC_ENTRY_RESERVE
    assert old_peak <= 8, "upright walk/run peak moved from 8 to %d" % old_peak
    assert new_peak <= wall, (
        "a tilted frame now costs %d Important slots, past the budget wall "
        "DMA_IMPORTANT_SLOTS - DPLC_ENTRY_RESERVE (%d - %d = %d) — the art-page "
        "landing is dropped on that frame, and at %d the DPLC drop is PERMANENT "
        "(engine/objects/dplc.emp), not one frame"
        % (new_peak, DMA_IMPORTANT_SLOTS, DPLC_ENTRY_RESERVE, wall,
           DMA_IMPORTANT_SLOTS + 1))
    # The debt is paid, and this is what says so: NO tilted frame reaches the whole
    # queue any more. $0E — the second frame of WALK TILT BLOCK 1, and the sheet's
    # tile peak — was the one that did, at exactly DMA_IMPORTANT_SLOTS.
    at_cap = [f for f in NEWLY_REACHABLE if frames[f][0] >= DMA_IMPORTANT_SLOTS]
    assert at_cap == [], (
        "a tilted frame is back at the Important-slot cap: %s. The d-47 re-cut took "
        "every frame to <= %d; re-cut the sheet (tools/dedup_art.py --entry-cap %d), "
        "do not raise DMA_IMPORTANT_SLOTS"
        % (["$%02X" % f for f in at_cap], wall, wall))
    # The peak is AT the wall, not comfortably under it: 10 == 12 - 2 exactly. Assert
    # that too, so a re-cut that silently stopped short of the wall (or a re-export
    # that crept back up to it from below) is visible here as a changed number rather
    # than as a still-passing `<=`.
    assert new_peak == wall, (
        "the worst tilted frame is %d entries, not the wall %d — the sheet's peak "
        "moved; re-derive it before adopting the new number" % (new_peak, wall))


def test_constants_still_match_their_source():
    """The three walls this file mirrors, pinned against the files that own them."""
    consts = (ROOT / "games/sonic4/config/constants.emp").read_text()
    assert "VRAM_TEST_SONIC         : VramTile = $03C0" in consts
    assert "VRAM_TEST_OBJ           : VramTile = $03E0" in consts
    eng = (ROOT / "engine/system/constants.emp").read_text()
    assert "DMA_IMPORTANT_SLOTS  = %d" % DMA_IMPORTANT_SLOTS in eng
    dplc = (ROOT / "engine/objects/dplc.emp").read_text()
    assert "DPLC_ENTRY_RESERVE = %d" % DPLC_ENTRY_RESERVE in dplc


def test_the_source_geometry_constants_match_the_gate_model():
    """player_common.emp owns the block geometry; sprite_tilt_gate.py mirrors it."""
    src = (ROOT / "games/sonic4/player/player_common.emp").read_text()
    for name, val in (("TILT_WALK_BASE", "$01"), ("TILT_WALK_LEN", "8"),
                      ("TILT_RUN_BASE", "$21"), ("TILT_RUN_LEN", "4"),
                      ("TILT_SETS", "4"), ("TILT_BIAS", "$10")):
        assert any(line.strip().startswith("const %s " % name) and val in line
                   for line in src.splitlines()), \
            "const %s = %s not found in player_common.emp" % (name, val)
