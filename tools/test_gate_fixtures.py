"""The fixture checks in sprite_tilt_gate.py, loop_crossover_gate.py and
instashield_gate.py (both of its subjects) must be blind to RELOCATION and not one bit
blinder than that.

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
import instashield_gate as isg           # noqa: E402

TILT_FIXTURE = TOOLS / "fixtures" / "sprite_tilt_cut.json"
LOOP_FIXTURE = TOOLS / "fixtures" / "loop_crossover_cut.json"
INSTA_FIXTURE = TOOLS / "fixtures" / "instashield_cut.json"
TAILS_FIXTURE = TOOLS / "fixtures" / "tailsflight_cut.json"

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
    # The absolute-short `jsr` (opcode $4eb8), FOUND rather than pinned at an offset:
    # this used to be hard-coded at +0x22 and went red for the wrong reason the first
    # time the read site grew a sweep loop in front of the call (2026-09-04). Retarget
    # it at a symbol that is in the cut's map but is NOT Collision_GetType.
    at = [i for i in range(0, len(b) - 3, 2) if b[i:i + 2] == b"\x4e\xb8"]
    assert len(at) == 1, \
        "expected exactly one absolute-short jsr in %s, found %d at %s — this test " \
        "retargets THE call to Collision_GetType and cannot choose between several" \
        % (lcg.READ_SITE, len(at), [hex(i) for i in at])
    b[at[0] + 2:at[0] + 4] = (0x0000).to_bytes(2, "big")
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


# ==========================================================================
# 4. The other two members of the class: instashield_cut.json and
#    tailsflight_cut.json, both checked by instashield_gate.check_cut.
#
# Same defect, same fix, same paired bar. These two pinned `start`, `end` and `stubs`
# and then compared raw bytes, so every parcel that shifted player code reddened them
# for a routine it had not touched -- the *fourth* and *fifth* reds of a class whose
# first two were closed by 9332587b.
#
# The evidence here is again NOT synthetic. Each fixture carries cuts of the two real
# canonical ROMs, and the pair is a genuine relocation with a genuinely different delta
# per symbol: Ability_InstaShield sits at $01166E (release) / $01177A (DEBUG) -- $10C
# apart -- while its `Sound_PlaySFX` tail target is $0081A8 / $00B4EA, $3342 apart. That
# is the measured reason a canonical-base relocation is not available as a fix and a
# normalisation is.
# ==========================================================================

INSTA_ROUTINE = isg.ROUTINE                       # Ability_InstaShield
TAILS_ROUTINE = isg.TAILS_ROUTINE                 # Ability_TailsFlight


def _insta_shapes():
    return json.loads(INSTA_FIXTURE.read_text())["shapes"]


def _tails_shapes():
    return json.loads(TAILS_FIXTURE.read_text())["shapes"]


def _cut_names(cut):
    return {int(a, 16): n for a, n in cut["stubs"].items()}


def _norm_ability(cut, override_bytes=None, names=None):
    b = bytes.fromhex(cut["bytes"] if override_bytes is None else override_bytes)
    start = cut["start"]
    if names is None:
        names = _cut_names(cut)
    img = bytearray(start + len(b))
    img[start:] = b
    return stg.normalize_stream(bytes(img), start, start + len(b), names,
                                "instashield_gate")


def _relocate_ability(cut, routine_delta, stub_deltas):
    """Do to an ability cut what the linker does when player code shifts underneath it.

    Every symbol gets its OWN delta, because that is what actually happens -- the
    historical +8 re-stamp moved the routines and one stub while `Sound_PlaySFX` stayed
    put -- and because a single shared delta would let a rebasing fix pass a test the
    real world would fail.

    Both hazards are rewritten, and each rewrite is asserted, so a silently-missed one
    cannot make a test pass by accident:
      * an ABSOLUTE operand (`jmp $81a8.l`) takes the symbol's new address;
      * a PC-RELATIVE displacement (`bsr.w`, `bra.w`, `bcc.b`) is recomputed, which is
        exactly the byte the old raw comparison reddened on.

    Returns (rom, new_start, new_end, new_syms, rewrites).
    """
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_M68K,
                     capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_M68K_000)
    old_start, old_end = cut["start"], cut["end"]
    by_addr = _cut_names(cut)
    new_syms = {n: a + stub_deltas[n] for a, n in by_addr.items()}
    new_start, new_end = old_start + routine_delta, old_end + routine_delta

    blob = bytearray.fromhex(cut["bytes"])
    out = bytearray(blob)
    rewrites = 0
    for insn in md.disasm(bytes(blob), old_start):
        pos = insn.address - old_start
        for tok in (stg._split_ops(insn.op_str) if insn.op_str else []):
            m_w, m_l = stg._TOK_ABSW.match(tok), stg._TOK_ABSL.match(tok)
            m_t = stg._TOK_TGT.match(tok)
            if m_w or m_l:
                width = 2 if m_w else 4
                raw = int((m_w or m_l).group(1), 16)
                ea = stg._sign_extend_w(raw) if width == 2 else raw
                name = by_addr.get(ea) or by_addr.get(ea & 0xFFFFFFFF)
                assert name is not None, \
                    "absolute operand %s names nothing in the cut's stub map" % tok
                mask = 0xFFFF if width == 2 else 0xFFFFFFFF
                old = (raw & mask).to_bytes(width, "big")
                at = bytes(insn.bytes).find(old, 2)
                assert at >= 0, "operand %s not found in %s" % (tok, insn.bytes.hex())
                out[pos + at:pos + at + width] = \
                    (new_syms[name] & mask).to_bytes(width, "big")
                rewrites += 1
            elif m_t:
                ea = int(m_t.group(1), 16)
                if old_start <= ea < old_end:
                    target = ea + routine_delta       # internal: moves with the routine
                else:
                    name = by_addr.get(ea)
                    assert name is not None, \
                        "branch target $%X names nothing in the cut's stub map" % ea
                    target = new_syms[name]
                disp = target - (insn.address + routine_delta + 2)
                if insn.size == 2:
                    assert -128 <= disp <= 127, \
                        "8-bit branch at +0x%X goes out of reach (%d) -- that ROM " \
                        "cannot exist, so the test would measure an impossible artifact" \
                        % (pos, disp)
                    out[pos + 1] = disp & 0xFF
                elif insn.size == 4:
                    assert -0x8000 <= disp <= 0x7FFF, \
                        "16-bit branch at +0x%X goes out of reach (%d)" % (pos, disp)
                    out[pos + 2:pos + 4] = (disp & 0xFFFF).to_bytes(2, "big")
                else:
                    raise AssertionError(
                        "unhandled branch encoding at +0x%X (%d bytes): %s %s"
                        % (pos, insn.size, insn.mnemonic, insn.op_str))
                rewrites += 1

    top = max([new_end] + [a + 2 for a in new_syms.values()])
    rom = bytearray(top)
    rom[new_start:new_end] = out
    return bytes(rom), new_start, new_end, new_syms, rewrites


# ---------------------------------------------- 4a. the premise, guarded

def test_ability_cuts_really_are_a_relocation():
    """If the two committed cuts ever stop differing, every invariance test below
    becomes a comparison of a thing to itself. Name that here."""
    for what, shapes in (("instashield", _insta_shapes()),
                         ("tailsflight", _tails_shapes())):
        a, b = shapes["s4.lst"], shapes["s4.debug.lst"]
        assert a["start"] != b["start"], \
            "%s: the two cuts are at the same address" % what
        assert a["bytes"] != b["bytes"], \
            "%s: the two cuts' BYTES are equal -- the embedded-displacement hazard " \
            "this suite exists for is not present in the sample" % what
        assert a["stubs"] != b["stubs"], "%s: no symbol moved between shapes" % what


def test_the_two_shapes_move_by_different_deltas():
    """The measured reason a canonical-base relocation is NOT the fix. If one delta
    served every symbol, re-keying the fixture to a base would have worked and this
    whole normalisation would be over-engineering."""
    a, b = _insta_shapes()["s4.lst"], _insta_shapes()["s4.debug.lst"]
    routine_delta = b["start"] - a["start"]
    stub_deltas = {n: int(sa, 16) for sa, n in b["stubs"].items()}
    stub_deltas = {n: stub_deltas[n] - int(sa, 16)
                   for sa, n in a["stubs"].items()}
    assert len(set(stub_deltas.values()) | {routine_delta}) > 1, \
        "every symbol moved by the same delta; a single base would have sufficed"


# ------------------------------- 4b. relocation-invariance, at the unit level

def test_tailsflight_normalises_equal_across_shapes():
    """Ability_TailsFlight in two real ROMs $10C apart, whose `bra.w Player_SetState`
    displacement differs by construction, is ONE routine. Raw bytes say otherwise; the
    normalised stream does not."""
    s = _tails_shapes()
    rows_a, unres_a = _norm_ability(s["s4.lst"])
    rows_b, unres_b = _norm_ability(s["s4.debug.lst"])
    assert rows_a == rows_b, isg.classify_stream(rows_a, rows_b, TAILS_ROUTINE)
    assert unres_a == [] and unres_b == [], \
        "unresolved absolute operands stay relocation-sensitive: %s" % (unres_a + unres_b)


def test_instashield_cross_shape_difference_is_a_relaxation_not_an_edit():
    """The insta-shield's two shapes are NOT stream-identical, and that is a real
    finding rather than a gap: the release ROM's `Sound_PlaySFX` is out of `bra.w` reach
    so sigil emitted `jmp $81a8.l`, while DEBUG's fits and got `bra.w`. Same source, same
    target, different reach -- so it must classify as a RELAXATION and never as an edit.
    This is the committed, measured instance of the third failure class."""
    a = _norm_ability(_insta_shapes()["s4.lst"])[0]
    b = _norm_ability(_insta_shapes()["s4.debug.lst"])[0]
    assert a != b, "the premise is gone -- the two shapes now encode identically"
    edits, relax = isg.classify_stream(a, b, INSTA_ROUTINE)
    assert edits == [], "a reach-driven encoding change was called an edit: %s" % edits
    # One RELAXED transfer, plus the three `bne`s whose internal target SLID because the
    # widened transfer sits ahead of the `rts` they branch to. Measured, not predicted:
    # this is what the two committed cuts actually contain.
    assert len(relax) == 4, relax
    relaxed = [r for r in relax if "RELAXED" in r]
    slid = [r for r in relax if "SLID" in r]
    assert len(relaxed) == 1 and len(slid) == 3, relax
    assert "<Sound_PlaySFX>" in relaxed[0] and "was not edited" in relaxed[0], relaxed
    assert all("bne" in r and "was not edited" in r for r in slid), slid


def test_a_slide_is_not_excused_without_a_relaxation_to_explain_it():
    """The slide excuse must not be free. Take the cross-shape pair, drop the RELAXED
    transfer out of both streams, and the three surviving slides must read as EDITS —
    nothing is left to explain why an untouched instruction moved."""
    a = _norm_ability(_insta_shapes()["s4.lst"])[0]
    b = _norm_ability(_insta_shapes()["s4.debug.lst"])[0]
    keep = [i for i, (c, l) in enumerate(zip(a, b))
            if isg.xfer_class(c[1]) != "goto" or isg.xfer_class(l[1]) != "goto"]
    a2, b2 = [a[i] for i in keep], [b[i] for i in keep]
    edits, relax = isg.classify_stream(a2, b2, INSTA_ROUTINE)
    assert relax == [], relax
    assert len(edits) == 3, edits
    assert all("differs" in e for e in edits), edits


def test_the_ability_normalisation_is_what_absorbs_the_difference():
    """The control, the other way round: with the symbol map EMPTIED the same two cuts
    must NOT compare equal, or the equality above is coming from somewhere other than
    the mechanism under test."""
    s = _tails_shapes()
    rows_a, unres_a = _norm_ability(s["s4.lst"], names={})
    rows_b, unres_b = _norm_ability(s["s4.debug.lst"], names={})
    assert rows_a != rows_b, \
        "with no symbols to resolve the two shapes still compared equal -- the " \
        "cross-shape equality above is not produced by the normaliser"
    assert unres_a and unres_b, "the unresolved-operand report went silent"
    assert stg.unresolved_note(TAILS_ROUTINE, unres_a), \
        "an unresolved operand must never be rendered as silence"


# ------------------------------------- 4c. the paired half: changes still go red

# Ability_InstaShield, release cut. Every offset here is an opcode, an immediate or an
# SST displacement -- there is no address in sight, so a comparison that misses one is
# change-blind rather than relocation-blind.
#   +0x26 `02010073  andi.b #$73,d1`  -- INSTASHIELD_SUPPRESS_MASK; +0x29 is the byte
#   +0x1C `7008      moveq  #$8,d0`   -- the PSTATE_JUMP argument; +0x1C is the opcode
#   +0x10 `4a28004a  tst.b  $4a(a0)`  -- PlayerV.instashield; +0x13 is the displacement
@pytest.mark.parametrize("off,new,what", [
    (0x29, 0x33, "an immediate (INSTASHIELD_SUPPRESS_MASK #$73 -> #$33)"),
    (0x1C, 0x72, "an opcode (moveq #$8,d0 -> moveq #$8,d1)"),
    (0x13, 0x4B, "an SST displacement ($4a(a0) -> $4b(a0))"),
])
def test_instashield_normalisation_still_catches_a_logic_change(off, new, what):
    cut = _insta_shapes()["s4.lst"]
    good, _ = _norm_ability(cut)
    bad, _ = _norm_ability(cut, _patch_byte(cut["bytes"], off, new))
    assert good != bad, "changing %s did not change the normalised stream" % what
    edits, relax = isg.classify_stream(good, bad, INSTA_ROUTINE)
    assert edits, "no EDIT reported for %s (relaxations: %s)" % (what, relax)
    assert relax == [], "%s was excused as a relaxation: %s" % (what, relax)
    assert "differs" in edits[0] and "cut offset" in edits[0]


def test_tailsflight_normalisation_still_catches_a_logic_change():
    """+0x1A `117c00f00042  move.b #$f0,$42(a0)` seeds PlayerV.fly_fuel with
    FLY_FUEL_TICKS; +0x1D is that immediate. Halve it and the engagement arm means
    something different with no address touched."""
    cut = _tails_shapes()["s4.lst"]
    good, _ = _norm_ability(cut)
    bad, _ = _norm_ability(cut, _patch_byte(cut["bytes"], 0x1D, 0x78))
    edits, relax = isg.classify_stream(good, bad, TAILS_ROUTINE)
    assert edits and relax == [], (edits, relax)


def test_ability_normalisation_catches_a_length_change():
    """A truncated routine is an edit, and the REASON must say so rather than borrow the
    vocabulary of a byte mismatch."""
    cut = _insta_shapes()["s4.lst"]
    good, _ = _norm_ability(cut)
    short, _ = _norm_ability(cut, cut["bytes"][:-4])       # drop the trailing `rts`
    edits, relax = isg.classify_stream(good, short, INSTA_ROUTINE)
    assert relax == []
    assert edits and "instruction COUNT changed" in edits[0]
    assert "edited, not moved" in edits[0]


def test_a_truncated_extent_is_loud_not_vacuous():
    """A comparison over a stream the decoder could not finish is the vacuous case: it
    would silently grade a prefix. Cutting one byte off the tail leaves capstone unable
    to cover the extent, and that must RAISE."""
    cut = _insta_shapes()["s4.lst"]
    with pytest.raises(SystemExit) as e:
        _norm_ability(cut, cut["bytes"][:-2])              # 61 of 62 bytes
    assert "not a clean instruction run" in str(e.value)
    assert "instashield_gate" in str(e.value)


def test_ability_normalisation_catches_a_changed_call_TARGET():
    """The one address that MUST still be caught: transferring to a DIFFERENT symbol.
    `jmp <Sound_PlaySFX>` must not degrade into `jmp <anything>`."""
    cut = copy.deepcopy(_insta_shapes()["s4.lst"])
    good, _ = _norm_ability(cut)
    b = bytearray.fromhex(cut["bytes"])
    assert b[0x38:0x3A] == b"\x4e\xf9", "the jmp is not where this test thinks it is"
    other = int([a for a, n in cut["stubs"].items() if n == "Player_SetState"][0], 16)
    b[0x3A:0x3E] = other.to_bytes(4, "big")
    bad, _ = _norm_ability(cut, bytes(b).hex())
    assert good != bad, "the transfer target was normalised away entirely -- the gate " \
                        "can no longer tell WHICH symbol is reached"
    edits, relax = isg.classify_stream(good, bad, INSTA_ROUTINE)
    assert edits and "Sound_PlaySFX" in edits[0], (edits, relax)
    assert relax == [], "a retarget was excused as a relaxation: %s" % relax


def test_a_flipped_CONDITION_is_an_edit_not_a_relaxation():
    """The semantic hole the relaxation excuse could open. `+0x0E 662e bne.b` and
    `672e beq.b` branch to the SAME place with the same reach — the only difference is
    which way the test goes, which is the whole meaning of the instruction. It must
    classify as an EDIT."""
    cut = _insta_shapes()["s4.lst"]
    good, _ = _norm_ability(cut)
    bad, _ = _norm_ability(cut, _patch_byte(cut["bytes"], 0x0E, 0x67))
    edits, relax = isg.classify_stream(good, bad, INSTA_ROUTINE)
    assert relax == [], "a flipped condition was excused as a relaxation: %s" % relax
    assert edits and "bne" in edits[0] and "beq" in edits[0], edits


def test_xfer_class_refuses_to_excuse_a_non_transfer():
    """The relaxation excuse is the one place this gate is allowed to forgive a
    difference, so pin what it will NOT forgive. `bclr`/`bset`/`btst`/`bchg` all start
    with 'b' and must not be mistaken for conditional branches."""
    for m in ("bclr", "bset", "btst", "bchg", "move.b", "andi.b", "rts", "moveq"):
        assert isg.xfer_class(m) is None, m
    assert isg.xfer_class("bra.w") == isg.xfer_class("jmp") == "goto"
    assert isg.xfer_class("bsr.b") == isg.xfer_class("jsr") == "call"
    assert isg.xfer_class("bne.b") == isg.xfer_class("bne.w") == "bne"
    assert isg.xfer_class("bne.b") != isg.xfer_class("beq.b"), \
        "two DIFFERENT conditions must never be excused as one relaxation"


# ------------------------ 4d. the decisive pair, through the real entry point

# Deltas chosen so the resulting ROM is one sigil could actually emit: the routine and
# its adjacent `InstaShield_Spawn` move together (they are neighbours), `Player_SetState`
# moves by a DIFFERENT amount so a PC-relative displacement genuinely changes, and
# `Sound_PlaySFX` moves by a third amount that keeps the DEBUG shape's `bra.w` in reach.
RELOC = {"routine": 0x100,
         "stubs": {"InstaShield_Spawn": 0x100, "Player_SetState": 0x110,
                   "Sound_PlaySFX": 0x40}}


def _reloc_case(fixture, shape):
    cut = json.loads(pathlib.Path(fixture).read_text())["shapes"][shape]
    deltas = {n: RELOC["stubs"][n] for n in _cut_names(cut).values()}
    return cut, _relocate_ability(cut, RELOC["routine"], deltas)


ABILITY_CASES = [(INSTA_FIXTURE, "s4.lst", INSTA_ROUTINE),
                 (INSTA_FIXTURE, "s4.debug.lst", INSTA_ROUTINE),
                 (TAILS_FIXTURE, "s4.lst", TAILS_ROUTINE),
                 (TAILS_FIXTURE, "s4.debug.lst", TAILS_ROUTINE)]


@pytest.mark.parametrize("fixture,shape,routine", ABILITY_CASES)
def test_relocating_an_ability_routine_is_NOT_a_failure(fixture, shape, routine):
    """PROOF (i). Move the routine and every symbol it reaches, by different deltas,
    rewrite the ROM the way the linker would, and check_cut must not raise -- where the
    old address-and-bytes comparison went red twice over."""
    cut, (rom, start, end, syms, rewrites) = _reloc_case(fixture, shape)
    assert rewrites >= 3, rewrites
    assert rom[start:end].hex() != cut["bytes"], \
        "the relocated bytes are identical to the cut -- no hazard was reproduced, so " \
        "this test would pass against the OLD comparison too"
    notes = isg.check_cut(rom, start, end, syms, str(fixture), shape, routine)
    assert any("MOVED (not edited)" in n for n in notes), notes
    assert any("references MOVED" in n for n in notes), notes


@pytest.mark.parametrize("fixture,shape,routine,off,new", [
    (INSTA_FIXTURE, "s4.lst", INSTA_ROUTINE, 0x29, 0x33),
    (INSTA_FIXTURE, "s4.debug.lst", INSTA_ROUTINE, 0x29, 0x33),
    (TAILS_FIXTURE, "s4.lst", TAILS_ROUTINE, 0x1D, 0x78),
    (TAILS_FIXTURE, "s4.debug.lst", TAILS_ROUTINE, 0x1D, 0x78),
])
def test_editing_a_relocated_ability_routine_IS_a_failure(fixture, shape, routine,
                                                          off, new):
    """PROOF (ii). The same relocation plus ONE changed immediate. Red, and named as an
    edit. A gate that is relocation-insensitive because it is change-insensitive is the
    exact failure this parcel could produce while looking like success."""
    cut, (rom, start, end, syms, _) = _reloc_case(fixture, shape)
    rom = bytearray(rom)
    assert rom[start + off] != new, "the mutation is a no-op at +0x%X" % off
    rom[start + off] = new
    with pytest.raises(SystemExit) as e:
        isg.check_cut(bytes(rom), start, end, syms, str(fixture), shape, routine)
    msg = str(e.value)
    assert "the ROUTINE CHANGED" in msg, msg
    assert "differs" in msg, msg


def test_a_vanished_ability_symbol_reads_as_vanished_not_moved():
    cut, (rom, start, end, syms, _) = _reloc_case(INSTA_FIXTURE, "s4.lst")
    syms = {n: a for n, a in syms.items() if n != "Sound_PlaySFX"}
    with pytest.raises(SystemExit) as e:
        isg.check_cut(rom, start, end, syms, str(INSTA_FIXTURE), "s4.lst",
                      INSTA_ROUTINE)
    msg = str(e.value)
    assert "GONE from the listing" in msg and "Sound_PlaySFX" in msg, msg
    assert "renamed or removed, not moved" in msg, msg


def test_unresolved_operands_are_named_when_something_else_fails(tmp_path):
    """Never render a blind spot as silence. Empty the stub map so every transfer target
    becomes a literal, then edit an immediate: the failure must both report the edit AND
    say that N absolute operands were compared verbatim."""
    cut = copy.deepcopy(_insta_shapes()["s4.lst"])
    cut["stubs"] = {}
    tmp = tmp_path / "unresolved_cut.json"
    tmp.write_text(json.dumps({"_note": "synthetic", "shapes": {"s4.lst": cut}}))
    b = bytearray.fromhex(cut["bytes"])
    b[0x29] = 0x33
    rom = bytearray(cut["end"])
    rom[cut["start"]:cut["end"]] = b
    with pytest.raises(SystemExit) as e:
        isg.check_cut(bytes(rom), cut["start"], cut["end"], {}, str(tmp),
                      "s4.lst", INSTA_ROUTINE)
    msg = str(e.value)
    assert "differs" in msg, msg
    assert "named no symbol in the cut and were compared" in msg, msg


# --------------------- 4e. the failure REASON is checkable on its own

def test_no_ability_reason_string_claims_an_edit_for_a_move():
    """The old text said the fixture was stale because "the routine MOVED: cut $X..$Y"
    or because "its BYTES differ in N of M" -- both of which were, for the overwhelmingly
    common cause, a relocation described as a change. Those sentences must be gone and
    nothing may have replaced them with the same claim."""
    src = _joined(TOOLS / "instashield_gate.py")
    # Positive control on the matcher: a phrase that IS wrapped across a line break in
    # instashield_gate.py must be findable, or every absence below proves nothing.
    assert "the routine was edited, not moved" in src, \
        "the joiner is not joining -- every absence assertion here would be vacuous"
    assert "the routine MOVED: cut $%06X" not in src
    assert "its BYTES differ in %d of " not in src
    # And the surviving MOVED sentence must be an explanation, not a verdict.
    assert "the routine MOVED (not edited)" in src
