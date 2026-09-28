"""Unit tests for tools/pstate_writers.py — the walk-off writer derivation behind
instashield_gate's third pass (GPP-INSTASHIELD-WALKOFF, 2026-09-28).

NO LISTING OR ROM FROM A BUILD IS OPENED HERE: build.sh's pytest lane runs before sigil,
so a test reading s4.debug.bin would grade a PREVIOUS build (test_dplc_straddle.py's
header rule). The real ROM is graded by the post-sigil gate. These tests hand-assemble
68000 bytes whose encodings are spelled out beside them, so each one pins a behaviour
of the scan, the dataflow and the source reader on inputs whose answer is known.
"""

import pathlib
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import pstate_writers as pw  # noqa: E402

T = 0x0200          # the synthetic Player_SetState
W = 0x0100          # the writer routine under test
NEXT = 0x0180       # the routine after it (its extent end)
HELPER = 0x0300     # a callee
NORET = 0x0340      # a callee the source marks @noreturn


def w16(v):
    return [(v >> 8) & 0xFF, v & 0xFF]


def rel(at, target):
    """The 16-bit displacement of a Bcc.w / bsr.w / jsr d16(pc) at `at`."""
    return (target - (at + 2)) & 0xFFFF


def rom_with(code, at=W, extra=()):
    rom = bytearray(0x400)
    rom[T:T + 2] = bytes(w16(0x4E75))                  # SetState: rts (never entered)
    rom[at:at + len(code)] = bytes(code)
    for addr, blob in extra:
        rom[addr:addr + len(blob)] = bytes(blob)
    return bytes(rom)


def ext(extra_syms=None):
    syms = {"W": W, "Next": NEXT, "Player_SetState": T, "SetState_End": T + 2,
            "Helper": HELPER, "Helper_End": HELPER + 0x20, "NoRet": NORET,
            "NoRet_End": NORET + 0x10}
    syms.update(extra_syms or {})
    return pw.Extents(syms, phased=())


def detach(first_state):
    """Ground_DetachState's shape: moveq #first,d0 / cmpi.b #2,$32(a0) / bne.s .set /
    moveq #12,d0 / .set: bra.w SetState."""
    code = [0x70, first_state]                      # moveq #first, d0
    code += [0x0C, 0x28, 0x00, 0x02, 0x00, 0x32]    # cmpi.b #2, $32(a0)
    code += [0x66, 0x02]                            # bne.s +2
    code += [0x70, 0x0C]                            # moveq #12, d0
    at = W + len(code)
    code += [0x60, 0x00] + w16(rel(at, T))          # bra.w SetState
    return code, at


def site_values(rom, extents, noreturn=()):
    flow = pw.Flow(rom, extents, T, noreturn)
    res = flow.analyse(W, NEXT)
    return res


# ---------------------------------------------------------------- the scan

def test_scan_finds_every_transfer_form_and_nothing_else():
    code = []
    forms = {}

    def put(bytes_, form):
        forms[W + len(code)] = form
        code.extend(bytes_)

    put([0x61, 0x00] + w16(rel(W + len(code), T)), "bsr.w")
    put([0x67, 0x00] + w16(rel(W + len(code), T)), "bcc.w")
    put([0x4E, 0xB9, 0x00, 0x00] + w16(T), "jsr.l")
    put([0x4E, 0xF8] + w16(T), "jmp.w")
    put([0x4E, 0xBA] + w16(rel(W + len(code), T)), "jsr.pc")
    code += [0x61, 0x00] + w16(rel(W + len(code), HELPER))   # a bsr.w ELSEWHERE
    rom = bytearray(rom_with(code))
    # a bra.s reaches only +-128 bytes: plant it just below SetState
    rom[T - 0x10:T - 0x0E] = bytes([0x60, 0x0E])
    forms[T - 0x10] = "bra.s"
    got = dict(pw.scan_transfers(bytes(rom), T))
    assert got == forms


# ---------------------------------------------------------------- the dataflow

def test_detach_shape_installs_air_or_airball():
    code, at = detach(6)
    res = site_values(rom_with(code), ext())
    assert res["sites"] == {at: frozenset({6, 12})}


def test_the_audits_mutation_is_visible_as_a_different_installed_state():
    """moveq #PSTATE_AIR -> #PSTATE_JUMP: the gate this module feeds must see 8."""
    code, at = detach(8)
    res = site_values(rom_with(code), ext())
    assert res["sites"][at] == frozenset({8, 12})


def test_a_non_constant_d0_is_TOP_never_a_guess():
    code = [0x10, 0x28, 0x00, 0x32]                 # move.b $32(a0), d0
    at = W + len(code)
    code += [0x60, 0x00] + w16(rel(at, T))
    res = site_values(rom_with(code), ext())
    assert res["sites"][at] == pw.TOP


def test_movem_save_restore_survives_a_clobbering_call():
    """PState_Spindash's `.release`: moveq #ROLL,d0 / movem.l d0,-(sp) / jbsr SFX /
    movem.l (sp)+,d0 / jbsr SetState."""
    code = [0x70, 0x02]                             # moveq #2, d0
    code += [0x48, 0xE7, 0x80, 0x00]                # movem.l d0, -(a7)
    at_call = W + len(code)
    code += [0x61, 0x00] + w16(rel(at_call, HELPER))   # bsr.w Helper (clobbers d0)
    code += [0x4C, 0xDF, 0x00, 0x01]                # movem.l (a7)+, d0
    at = W + len(code)
    code += [0x61, 0x00] + w16(rel(at, T))          # bsr.w SetState
    code += [0x4E, 0x75]
    helper = [0x70, 0x55, 0x4E, 0x75]               # moveq #$55, d0 / rts
    res = site_values(rom_with(code, extra=[(HELPER, helper)]), ext())
    assert res["sites"][at] == frozenset({2})


def test_without_the_restore_the_clobber_is_what_reaches_the_site():
    """The control for the test above: the same call without movem hands the callee's
    d0 on — so the restore is doing the work, not an accident of the lattice."""
    code = [0x70, 0x02]
    at_call = W + len(code)
    code += [0x61, 0x00] + w16(rel(at_call, HELPER))
    at = W + len(code)
    code += [0x61, 0x00] + w16(rel(at, T)) + [0x4E, 0x75]
    helper = [0x70, 0x55, 0x4E, 0x75]
    res = site_values(rom_with(code, extra=[(HELPER, helper)]), ext())
    assert res["sites"][at] == frozenset({0x55})


def test_a_callee_that_returns_d0_is_summarised():
    """Air_LandOnObject's shape: jbsr Air_LandState (out d0) / jbra SetState."""
    code = [0x61, 0x00] + w16(rel(W, HELPER))
    at = W + len(code)
    code += [0x60, 0x00] + w16(rel(at, T))
    # Helper: tst.w d1 / beq.s +4 / moveq #2,d0 / rts / moveq #0,d0 / rts
    helper = [0x4A, 0x41, 0x67, 0x04, 0x70, 0x02, 0x4E, 0x75, 0x70, 0x00, 0x4E, 0x75]
    res = site_values(rom_with(code, extra=[(HELPER, helper)]), ext())
    assert res["sites"][at] == frozenset({0, 2})


def test_a_callee_that_leaves_d0_alone_passes_the_callers_value_through():
    code = [0x70, 0x06]
    code += [0x61, 0x00] + w16(rel(W + 2, HELPER))
    at = W + len(code)
    code += [0x60, 0x00] + w16(rel(at, T))
    helper = [0x72, 0x01, 0x4E, 0x75]               # moveq #1, d1 / rts
    res = site_values(rom_with(code, extra=[(HELPER, helper)]), ext())
    assert res["sites"][at] == frozenset({6})


def test_a_callee_that_TAIL_CALLS_hands_back_unknown_not_nothing():
    """A callee whose only exit is `bra Elsewhere` returns whatever Elsewhere does. If
    the summary read "no rts reached" as "never returns", the caller's path after the
    call would vanish and its d0 with it — here the 8 that must reach the site."""
    code = [0x70, 0x08]                             # moveq #8, d0
    code += [0x61, 0x00] + w16(rel(W + 2, HELPER))  # bsr.w Helper
    at = W + len(code)
    code += [0x60, 0x00] + w16(rel(at, T))
    helper = [0x60, 0x00] + w16(rel(HELPER, NORET))    # bra.w NoRet (a tail call)
    res = site_values(rom_with(code, extra=[(HELPER, helper)]), ext())
    assert res["sites"][at] == pw.TOP


def test_noreturn_stops_the_path_instead_of_decoding_its_message_as_code():
    """The `assert` macro's failure arm: jsr ErrorHandlerBlob followed by its message.
    The "message" here is chosen to DECODE as `moveq #8,d0`, so following it past the
    call is observable: without the @noreturn knowledge 8 reaches the site."""
    code = [0x70, 0x06]                             # moveq #6, d0
    code += [0x67, 0x08]                            # beq.s +8 (the assert passes)
    code += [0x4E, 0xB9, 0x00, 0x00] + w16(NORET)   # jsr NoRet.l
    code += [0x70, 0x08]                            # the message bytes
    at = W + len(code)
    code += [0x60, 0x00] + w16(rel(at, T))
    rom = rom_with(code)
    assert site_values(rom, ext())["sites"][at] == frozenset({6, 8})     # the control
    assert site_values(rom, ext(), noreturn={NORET})["sites"][at] == frozenset({6})


def test_flow_never_reaching_a_scanned_site_is_visible():
    """A site after an unconditional bra is not visited — the caller turns that into
    UNMEASURABLE; this pins that `visited` really omits it."""
    code = [0x60, 0x06]                             # bra.s +6 (over the dead site)
    dead = W + len(code)
    code += [0x70, 0x08, 0x60, 0x00] + w16(rel(dead + 2, T))
    code += [0x4E, 0x75]
    res = site_values(rom_with(code), ext())
    assert (dead + 2) not in res["visited"]
    assert res["sites"] == {}


# ---------------------------------------------------------------- the extents

def test_macro_minted_locals_do_not_end_a_routine():
    """abs_w mints `$module$asmN$abs` inside the routine; it is a local, not a head."""
    e = ext({"$m$asm6$abs": W + 4})
    assert e.extent("W") == (W, NEXT)
    e = ext({"Ordinary": W + 4})
    assert e.extent("W") == (W, W + 4)


def test_a_zero_byte_routine_is_recognised_and_a_real_one_is_not():
    """Debug_Warp_Consume in the release shape: its whole body is under `if DEBUG == 1`,
    so its head shares an address with the next routine's."""
    e = ext({"Empty": NEXT, "$m$Empty$x": NEXT})
    assert e.emits_nothing("Empty") and e.emits_nothing("Next")
    assert not e.emits_nothing("W")


# ---------------------------------------------------------------- the source side

SRC = """\
module games.test_mod in test_mod
use games.sonic4.player_common.{Player_SetState,
                                PlayerV}

@noreturn
pub proc Crash () clobbers() {
        bra     Crash
}

proc Walker (a0: *Sst) clobbers(d0-d2/a1-a2) {
        cmpi.b  #PSTATE_ROLL, PlayerV.player_state(a0)   // a read
        move.b  PlayerV.player_state(a0), d1              // a read
        moveq   #PSTATE_AIR, d0
        jbra    Player_SetState                 // Player_SetState in a comment
}

proc Initer (a0: *Sst) clobbers(d0) {
        clr.b   PlayerV.player_state(a0)
.again: jbsr    Player_SetState
        rts
}

proc Sneaky () clobbers(a1) {
        lea     Player_SetState, a1
        rts
}
"""


@pytest.fixture
def src_file(tmp_path):
    p = tmp_path / "mod.emp"
    p.write_text(SRC)
    return p


def test_source_scan_attributes_transfers_to_their_procs(src_file):
    sites, refused, writes = pw.source_scan([src_file])
    assert {k: [l for _, l in v] for k, v in sites.items()} == {"Walker": [14],
                                                               "Initer": [19]}


def test_source_scan_refuses_a_reference_it_cannot_follow(src_file):
    _, refused, _ = pw.source_scan([src_file])
    assert len(refused) == 1 and ":24:" in refused[0] and "lea" in refused[0]


def test_source_scan_finds_the_direct_write_and_not_the_reads(src_file):
    _, _, writes = pw.source_scan([src_file])
    assert [(w[1], w[2], w[3], w[4]) for w in writes] == [(18, "Initer", "clr", "b")]


def test_source_noreturn(src_file):
    assert pw.source_noreturn([src_file]) == {"Crash"}


def test_digest_sources_reads_only_source_emp_rows(tmp_path):
    lst = tmp_path / "x.lst"
    lst.write_text(
        "DIGEST-READ crc=1 size=2 origin=source path=games/a.emp\n"
        "DIGEST-READ crc=1 size=2 origin=generated path=games/b.emp\n"
        "DIGEST-READ crc=1 size=2 origin=source path=art/c.bin\n")
    assert pw.digest_sources(lst, tmp_path) == [tmp_path / "games" / "a.emp"]
