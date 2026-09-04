"""The fixture checks in sprite_tilt_gate.py and loop_crossover_gate.py must be blind
to RELOCATION and not one bit blinder than that.

WHY THIS FILE EXISTS. Both gates are build-fatal and both used to compare committed
cuts to the fresh ROM by absolute address equality plus raw byte equality. Neither
survives a level/act content change:

  * the address check fails the moment anything upstream grows or shrinks;
  * the byte check fails one level down, because the cut code EMBEDS absolute addresses
    -- Player_ApplyTilt ends in `jsr RefreshSpritePieceCount` with an absolute-short
    operand, Player_LoopCrossover calls Collision_GetType the same way, and
    Collision_GetType is fourteen `move.w Cache_*.w` operands and a `lea
    SolidityTable.l` deep.

So correct content work went red on gates whose subject it had not touched, and the
sprite-tilt gate reported the reason as "the tilt was edited without refreshing the
cut", which was fabricated -- the tilt had not been edited.

THE RISK THIS FILE GUARDS. The cheap way to stop those reds is to compare less, and a
gate that is relocation-insensitive because it is change-insensitive looks exactly like
a success. So every relocation-invariance test below is PAIRED with a mutation test
proving the same comparison still goes red on a real logic change.

THE EVIDENCE IS NOT SYNTHETIC. tools/fixtures/*.json each carry two cuts of two REAL
ROMs -- the release and DEBUG shapes -- whose routines are the same source placed at
genuinely different addresses (Player_ApplyTilt at $0101F4 vs $0102B6; its callee 2410
bytes apart). Those two cuts ARE a relocation, already committed, and the headline test
is simply that they normalise to the same instruction stream.
"""

import copy
import json
import pathlib
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import sprite_tilt_gate as stg           # noqa: E402
import loop_crossover_gate as lcg        # noqa: E402

TILT_FIXTURE = TOOLS / "fixtures" / "sprite_tilt_cut.json"
LOOP_FIXTURE = TOOLS / "fixtures" / "loop_crossover_cut.json"

pytest.importorskip("capstone")


# --------------------------------------------------------------------------
# helpers — a cut in, a normalised stream out
# --------------------------------------------------------------------------

def _tilt_shapes():
    return json.loads(TILT_FIXTURE.read_text())["shapes"]


def _loop_shapes():
    return json.loads(LOOP_FIXTURE.read_text())["shapes"]


def _norm_tilt(fx, override_bytes=None):
    b = bytes.fromhex(override_bytes or fx["routine"]["bytes"])
    start = fx["routine"]["addr"]
    names = {fx["refresh_addr"]: "RefreshSpritePieceCount"}
    names.update({s["addr"]: n for n, s in fx["anim_tables"].items()})
    img = bytearray(start + len(b))
    img[start:] = b
    return stg.normalize_stream(bytes(img), start, start + len(b), names)


def _norm_loop(cut, idx, override_bytes=None):
    b = bytes.fromhex(override_bytes or cut["bytes"][idx])
    start = cut["spans"][idx][0]
    names = {a: n for n, a in cut["syms"].items()}
    img = bytearray(start + len(b))
    img[start:] = b
    return stg.normalize_stream(bytes(img), start, start + len(b), names,
                                "loop_crossover_gate")


def _patch_byte(hexstr, byte_off, new):
    b = bytearray.fromhex(hexstr)
    assert b[byte_off] != new, "mutation is a no-op at +%d" % byte_off
    b[byte_off] = new
    return bytes(b).hex()


# --------------------------------------------------------------------------
# 1. The headline: two real builds, one source, identical normalised stream
# --------------------------------------------------------------------------

def test_the_two_cuts_really_are_a_relocation():
    """Guard the premise. If the committed cuts ever stop differing, every
    relocation-invariance test below becomes vacuous -- it would be comparing a thing
    to itself. Name that here rather than let it pass silently."""
    s = _tilt_shapes()
    a, b = s["s4.lst"], s["s4.debug.lst"]
    assert a["routine"]["addr"] != b["routine"]["addr"], \
        "the two cuts are at the same address — this suite is no longer testing anything"
    assert a["refresh_addr"] != b["refresh_addr"]
    assert a["routine"]["bytes"] != b["routine"]["bytes"], \
        "the two cuts' BYTES are equal — the embedded-absolute-operand hazard this " \
        "suite exists for is not present in the sample"

    ls = _loop_shapes()
    la, lb = ls["s4.lst"], ls["s4.debug.lst"]
    assert la["spans"] != lb["spans"]
    assert la["bytes"] != lb["bytes"]


def test_tilt_routine_normalises_equal_across_shapes():
    """Player_ApplyTilt, in two real ROMs 194 bytes apart with a callee 2410 bytes
    apart, is ONE routine. Raw bytes say otherwise; the normalised stream does not."""
    s = _tilt_shapes()
    rows_a, unres_a = _norm_tilt(s["s4.lst"])
    rows_b, unres_b = _norm_tilt(s["s4.debug.lst"])
    assert rows_a == rows_b, stg.stream_diff(rows_a, rows_b, "Player_ApplyTilt")
    assert stg.stream_diff(rows_a, rows_b, "Player_ApplyTilt") == []
    # No blind spot: every address-shaped operand resolved to a name or to self.
    assert unres_a == [] and unres_b == [], \
        "unresolved absolute operands remain relocation-sensitive: %s" % (unres_a + unres_b)


def test_loop_routines_normalise_equal_across_shapes():
    ls = _loop_shapes()
    for idx, name in enumerate((lcg.READ_SITE, lcg.LOOKUP)):
        rows_a, unres_a = _norm_loop(ls["s4.lst"], idx)
        rows_b, unres_b = _norm_loop(ls["s4.debug.lst"], idx)
        assert rows_a == rows_b, stg.stream_diff(rows_a, rows_b, name)
        assert unres_a == [] and unres_b == [], \
            "%s: unresolved absolute operands %s" % (name, unres_a + unres_b)


def test_a_sign_extended_absolute_short_resolves():
    """The resolver's only interesting case, pinned on its own rather than left to ride
    along inside a bigger assertion.

    `move.w $adbc.w,d2` addresses $FFFFADBC — the 68000 sign-extends an absolute-short
    operand and capstone renders it unextended. Symbol tables store the extended form
    (4294946236). Miss the extension and every RAM reference in Collision_GetType goes
    unresolved and stays relocation-sensitive, which is the whole defect back again.

    This test exists because a mutation aimed at the resolver was once absorbed by a
    redundant second lookup branch and reported green; the branch is gone and this
    names what the surviving one has to do.
    """
    cut = _loop_shapes()["s4.lst"]
    assert cut["syms"]["Cache_Left_Col"] > 0x7FFFFFFF, \
        "Cache_Left_Col is no longer a sign-extended address; this test's premise is gone"
    rows, unres = _norm_loop(cut, 1)
    assert unres == [], unres
    flat = " ".join(r[2] for r in rows)
    for name in ("Cache_Left_Col", "Cache_Head_Col", "Cache_Top_Row",
                 "Cache_Bottom_Row", "Cache_Origin_Col", "Cache_Origin_Row"):
        assert "<%s>" % name in flat, \
            "%s was not resolved — its .w operand stayed a literal" % name


def test_the_normalisation_is_what_absorbs_the_difference():
    """Establish the control the other way round: with the symbol map EMPTIED, the same
    two cuts must NOT compare equal. Otherwise the equality above could be coming from
    somewhere other than the mechanism under test."""
    s = _tilt_shapes()
    fa, fb = s["s4.lst"], s["s4.debug.lst"]
    ba, bb = bytes.fromhex(fa["routine"]["bytes"]), bytes.fromhex(fb["routine"]["bytes"])

    def bare(f, b):
        img = bytearray(f["routine"]["addr"] + len(b))
        img[f["routine"]["addr"]:] = b
        return stg.normalize_stream(bytes(img), f["routine"]["addr"],
                                    f["routine"]["addr"] + len(b), {})

    rows_a, unres_a = bare(fa, ba)
    rows_b, unres_b = bare(fb, bb)
    assert rows_a != rows_b, \
        "with no symbols to resolve, the two shapes still compared equal — the " \
        "cross-shape equality above is not being produced by the normaliser"
    assert unres_a and unres_b, "the unresolved-operand report went silent"
    assert stg.unresolved_note("Player_ApplyTilt", unres_a), \
        "an unresolved operand must never be rendered as silence"


# --------------------------------------------------------------------------
# 2. The paired half: a real logic change must still go red
# --------------------------------------------------------------------------

# Player_ApplyTilt, cut offset +0x38: `02420003  andi.w #$3,d2` — the octant mask, the
# single constant that decides how many orientations the tilt can select. Byte +0x3B is
# its immediate. Changing it is a genuine logic change with no address in sight, so a
# comparison that misses it is change-blind.
TILT_MASK_OFF = 0x3B
# Cut offset +0x36: the `ea0a  lsr.b #$5,d2` opcode word. +0x36 is the opcode byte.
TILT_OPCODE_OFF = 0x36
# Cut offset +0x0A: `1428001f  move.b $1f(a0),d2` — SST_angle. +0x0D is the displacement.
TILT_DISP_OFF = 0x0D


@pytest.mark.parametrize("off,new,what", [
    (TILT_MASK_OFF, 0x07, "an immediate (the octant mask #$3 -> #$7)"),
    (TILT_OPCODE_OFF, 0xE2, "an opcode (lsr.b #$5 -> lsr.b #$1)"),
    (TILT_DISP_OFF, 0x1E, "an SST displacement ($1f(a0) -> $1e(a0))"),
])
def test_tilt_normalisation_still_catches_a_logic_change(off, new, what):
    """Relocation-insensitive must not mean change-insensitive. Each mutation here
    changes MEANING and touches no address."""
    fx = _tilt_shapes()["s4.lst"]
    good, _ = _norm_tilt(fx)
    bad, _ = _norm_tilt(fx, _patch_byte(fx["routine"]["bytes"], off, new))
    assert good != bad, "changing %s did not change the normalised stream" % what
    d = stg.stream_diff(good, bad, "Player_ApplyTilt")
    assert d, "stream_diff reported nothing for %s" % what
    assert "differs" in d[0] and "cut offset" in d[0]


def test_tilt_normalisation_catches_a_length_change():
    """A truncated routine is an edit, and its REASON must say so rather than borrow
    the vocabulary of a byte mismatch."""
    fx = _tilt_shapes()["s4.lst"]
    good, _ = _norm_tilt(fx)
    short, _ = _norm_tilt(fx, fx["routine"]["bytes"][:-8])
    d = stg.stream_diff(good, short, "Player_ApplyTilt")
    assert d and "instruction COUNT changed" in d[0]
    assert "edited, not moved" in d[0]


def test_loop_normalisation_still_catches_a_logic_change():
    """Collision_GetType, cut offset +0x16: `0c400050  cmpi.w #$50,d0` — the
    TILE_CACHE_COLS wrap test. +0x19 is its immediate."""
    cut = _loop_shapes()["s4.lst"]
    good, _ = _norm_loop(cut, 1)
    bad, _ = _norm_loop(cut, 1, _patch_byte(cut["bytes"][1], 0x19, 0x60))
    assert good != bad
    assert stg.stream_diff(good, bad, lcg.LOOKUP)


def test_loop_normalisation_catches_a_changed_call_TARGET():
    """The one thing that MUST still be caught even though it is an address: calling a
    DIFFERENT symbol. Normalising `jsr <Collision_GetType>` must not degrade into
    `jsr <anything>` -- point the call at SolidityTable's address and it has to go red."""
    cut = copy.deepcopy(_loop_shapes()["s4.lst"])
    good, _ = _norm_loop(cut, 0)
    b = bytearray.fromhex(cut["bytes"][0])
    # `4eb8 572e` at +0x22 -> the absolute-short jsr. Retarget it at a symbol that is
    # in the cut's map but is NOT Collision_GetType.
    assert b[0x22:0x24] == b"\x4e\xb8", "the jsr is not where this test thinks it is"
    b[0x24:0x26] = (0x0000).to_bytes(2, "big")
    cut2 = dict(cut)
    cut2["syms"] = dict(cut["syms"])
    cut2["syms"]["ZeroPage"] = 0
    bad, _ = _norm_loop(cut2, 0, bytes(b).hex())
    assert good != bad, "the call target was normalised away entirely — the gate can " \
                        "no longer tell WHICH symbol is called"
    d = stg.stream_diff(good, bad, lcg.READ_SITE)
    assert d and "Collision_GetType" in d[0]


# --------------------------------------------------------------------------
# 3. The failure REASON is checkable on its own (shared-protocol bar 10)
# --------------------------------------------------------------------------

def _joined(path):
    """Source with adjacent string literals joined, so a phrase can be searched for as
    the user SEES it rather than as the formatter happened to wrap it.

    This exists because the first version of the test below searched the raw source for
    'the tilt was edited without refreshing the cut' -- a phrase the old code wrapped as
    `"...the tilt was "` / `"edited without refreshing the cut"`. The raw substring was
    therefore absent from the OLD file too, so the assertion passed against exactly the
    code it was written to forbid. A check that a mutation cannot fail is not a check.
    """
    import re as _re
    return _re.sub(r'"\s*\n\s*"', '', pathlib.Path(path).read_text())


def test_no_reason_string_claims_an_edit_for_a_move():
    """The old sprite-tilt text said 'the tilt was edited without refreshing the cut'
    whenever the bytes differed, which was false for the overwhelmingly common cause.
    That sentence must be gone, and nothing may have replaced it with the same claim."""
    src = _joined(TOOLS / "sprite_tilt_gate.py")
    # Positive control on the matcher: a phrase that IS wrapped across a line break in
    # this very file must be findable, or the absence below proves nothing.
    assert "the routine was edited, not moved" in src, \
        "the joiner is not joining — every absence assertion here would be vacuous"
    assert "the tilt was edited without refreshing the cut" not in src

    loop_src = _joined(TOOLS / "loop_crossover_gate.py")
    # The loop gate may still SAY a routine changed -- but only from a length or
    # stream difference, never from a raw byte compare of a relocatable span.
    assert "its BYTES differ in %d of %d" not in loop_src
    assert "the routines MOVED" not in loop_src


def test_moving_everything_is_not_a_failure():
    """The end-to-end statement of the parcel, on the tilt gate's real entry point:
    relocate the routine, its callee and all three script slabs by an arbitrary delta,
    rebuild the ROM image accordingly, and check_fixture must report NOTHING."""
    fx = copy.deepcopy(_tilt_shapes()["s4.lst"])
    delta = 0x2000
    b = bytearray.fromhex(fx["routine"]["bytes"])
    # Relocating the callee rewrites the routine's own bytes -- that is the whole hazard.
    new_refresh = fx["refresh_addr"] + delta
    assert b[0x68:0x6A] == b"\x4e\xb8", "the jsr is not where this test thinks it is"
    b[0x6A:0x6C] = new_refresh.to_bytes(2, "big")

    new_start = fx["routine"]["addr"] + delta
    anim = {n: (s["addr"] + delta, bytes.fromhex(s["bytes"]))
            for n, s in fx["anim_tables"].items()}
    top = max([new_start + len(b)] + [a + len(v) for a, v in anim.values()])
    rom = bytearray(top)
    rom[new_start:new_start + len(b)] = b
    for a, v in anim.values():
        rom[a:a + len(v)] = v

    syms = {"Player_ApplyTilt": new_start, "RefreshSpritePieceCount": new_refresh,
            "_sentinel_after": new_start + len(b)}
    syms.update({n: a for n, (a, _) in anim.items()})

    problems = stg.check_fixture(bytes(rom), syms, str(TILT_FIXTURE), "s4.lst")
    assert problems == [], "a pure relocation was reported as a problem: %s" % problems


def test_editing_the_routine_IS_a_failure_through_check_fixture():
    """The same entry point, same relocation, plus one changed immediate. Red."""
    fx = copy.deepcopy(_tilt_shapes()["s4.lst"])
    delta = 0x2000
    b = bytearray.fromhex(fx["routine"]["bytes"])
    new_refresh = fx["refresh_addr"] + delta
    b[0x6A:0x6C] = new_refresh.to_bytes(2, "big")
    b[TILT_MASK_OFF] = 0x07                      # #$3 -> #$7, the octant mask

    new_start = fx["routine"]["addr"] + delta
    anim = {n: (s["addr"] + delta, bytes.fromhex(s["bytes"]))
            for n, s in fx["anim_tables"].items()}
    top = max([new_start + len(b)] + [a + len(v) for a, v in anim.values()])
    rom = bytearray(top)
    rom[new_start:new_start + len(b)] = b
    for a, v in anim.values():
        rom[a:a + len(v)] = v
    syms = {"Player_ApplyTilt": new_start, "RefreshSpritePieceCount": new_refresh,
            "_sentinel_after": new_start + len(b)}
    syms.update({n: a for n, (a, _) in anim.items()})

    problems = stg.check_fixture(bytes(rom), syms, str(TILT_FIXTURE), "s4.lst")
    assert problems, "an edited immediate survived a relocation unnoticed"
    assert any("differs" in p for p in problems), problems


def test_a_vanished_symbol_reads_as_vanished_not_moved():
    fx = copy.deepcopy(_tilt_shapes()["s4.lst"])
    b = bytes.fromhex(fx["routine"]["bytes"])
    start = fx["routine"]["addr"]
    rom = bytearray(start + len(b))
    rom[start:] = b
    syms = {"Player_ApplyTilt": start, "_sentinel_after": start + len(b)}
    problems = stg.check_fixture(bytes(rom), syms, str(TILT_FIXTURE), "s4.lst")
    assert any("GONE from the listing" in p for p in problems), problems
    assert not any("moved" in p and "GONE" not in p for p in problems), problems


def _relocate(blob, base, old_syms, new_syms):
    """Do to a blob what the linker does: rewrite every ABSOLUTE operand that names a
    symbol to that symbol's new address, in place, leaving opcodes untouched.

    Done properly rather than by a global bytes.replace, because a two-byte pattern
    collides with immediates and displacements. Each rewrite is confined to the single
    instruction capstone says the operand belongs to, and every expected rewrite is
    asserted, so a silently-missed one cannot make the test pass by accident.
    """
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_M68K,
                     capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_M68K_000)
    by_addr = {a: n for n, a in old_syms.items()}
    out = bytearray(blob)
    rewrites = 0
    for insn in md.disasm(bytes(blob), base):
        pos = insn.address - base
        for tok in (stg._split_ops(insn.op_str) if insn.op_str else []):
            for rx, width in ((stg._TOK_ABSW, 2), (stg._TOK_ABSL, 4)):
                m = rx.match(tok)
                if not m:
                    continue
                raw = int(m.group(1), 16)
                ea = stg._sign_extend_w(raw) if width == 2 else raw
                name = by_addr.get(ea) or by_addr.get(ea & 0xFFFFFFFF)
                if name is None:
                    continue
                old = (raw & (0xFFFF if width == 2 else 0xFFFFFFFF)).to_bytes(width, "big")
                new = (new_syms[name] & (0xFFFF if width == 2 else 0xFFFFFFFF)) \
                    .to_bytes(width, "big")
                # search inside THIS instruction only, past the opcode word
                at = bytes(insn.bytes).find(old, 2)
                assert at >= 0, "operand %s not found in %s" % (tok, insn.bytes.hex())
                out[pos + at:pos + at + width] = new
                rewrites += 1
    assert rewrites, "nothing was relocated — this test would then be vacuous"
    return bytes(out), rewrites


def test_loop_check_cut_accepts_a_relocation_and_rejects_an_edit():
    """loop_crossover_gate.check_cut, both directions, through its real entry point.

    The delta is deliberately small: an absolute-SHORT operand sign-extends, so pushing
    Collision_GetType ($572E) past $8000 would make `jsr $xxxx.w` address RAM and the
    assembler would have widened it instead. Building that ROM would be building one
    sigil cannot emit, and the test would be measuring an impossible artifact."""
    cut = _loop_shapes()["s4.lst"]
    delta = 0x1000
    assert cut["syms"][lcg.LOOKUP] + delta < 0x8000, \
        "the delta pushes an absolute-short target out of range; that ROM cannot exist"
    syms = {n: (a + delta) & 0xFFFFFFFF for n, a in cut["syms"].items()}
    equs = dict(cut["equs"])
    total_rewrites = 0

    def build(edit=None):
        nonlocal total_rewrites
        blobs, total_rewrites = [], 0
        for i in range(2):
            b, n = _relocate(bytes.fromhex(cut["bytes"][i]), cut["spans"][i][0],
                             cut["syms"], syms)
            total_rewrites += n
            blobs.append(bytearray(b))
        if edit is not None:
            i, off, val = edit
            blobs[i][off] = val
        spans = [(cut["spans"][i][0] + delta, cut["spans"][i][1] + delta)
                 for i in range(2)]
        top = max(spans[1][1], syms["CrossoverTable"] + 256)
        rom = bytearray(top)
        for (a, bb), blob in zip(spans, blobs):
            rom[a:bb] = blob
        rom[syms["CrossoverTable"]:syms["CrossoverTable"] + 256] = \
            bytes.fromhex(cut["table"])
        return bytes(rom), spans

    rom, spans = build()
    # Show the relocation was real and substantial before claiming it was absorbed.
    assert total_rewrites >= 8, total_rewrites
    assert rom[spans[0][0]:spans[0][1]].hex() != cut["bytes"][0], \
        "the relocated bytes are identical to the cut — no hazard was reproduced"
    lcg.check_cut(rom, spans, syms, equs, str(LOOP_FIXTURE), "s4.lst")   # must not raise

    rom, spans = build(edit=(1, 0x19, 0x60))    # cmpi.w #$50 -> #$60
    with pytest.raises(SystemExit) as e:
        lcg.check_cut(rom, spans, syms, equs, str(LOOP_FIXTURE), "s4.lst")
    assert "differs" in str(e.value), str(e.value)
    assert "the ROUTINE changed" not in str(e.value)


def test_loop_check_cut_catches_equate_drift():
    """New with this parcel: the pytest lane models against the cut's equates, so an
    equate that changed under it must be named rather than silently mis-graded."""
    cut = _loop_shapes()["s4.lst"]
    syms = dict(cut["syms"])
    equs = dict(cut["equs"])
    equs["TILE_CACHE_COLS"] = 96
    spans = [tuple(s) for s in cut["spans"]]
    top = max(spans[1][1], syms["CrossoverTable"] + 256)
    rom = bytearray(top)
    for (a, b), hx in zip(spans, cut["bytes"]):
        rom[a:b] = bytes.fromhex(hx)
    rom[syms["CrossoverTable"]:syms["CrossoverTable"] + 256] = bytes.fromhex(cut["table"])
    with pytest.raises(SystemExit) as e:
        lcg.check_cut(bytes(rom), spans, syms, equs, str(LOOP_FIXTURE), "s4.lst")
    assert "TILE_CACHE_COLS" in str(e.value) and "equate" in str(e.value)
