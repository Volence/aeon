#!/usr/bin/env python3
"""The System pool is unreachable in a RELEASE shape — checked against the shipped ROM.

WHY THIS EXISTS (LS-10, 2026-09-07)

`engine/objects/core.emp` (RunObjects, RunObjects_Frozen) and
`engine/objects/collision.emp` (TouchResponse) stopped sweeping the eight
`System_Slots` in a release shape. That is sound only while the claim underneath it
holds:

    In a release build nothing ever writes a non-zero `Sst.code_addr` into a
    System slot, so every one of those eight slots is permanently the zero
    `boot.emp .clear_ram` left and dispatching them could never do anything.

If that claim ever stops being true the symptom is an object that silently never
runs, arbitrarily far from the edit that broke it. The claim is about the FUTURE as
much as the present, and before this file nothing checked it at all.

HOW IT IS CHECKED — the artifact, not the source text

The source route (grep for `System_Slots`, check each hit is inside `if DEBUG == 1`)
is the route the finding was originally established by, and it cannot see an address
that arrives some other way: a hardcoded literal, arithmetic off `Effect_Slots`, a
constant `equ`'d two hops away. So this file asks the shipped ROM instead.

A 68000 instruction cannot store into a slot without either loading the slot's
address into an address register (`lea` / `movea`) or naming it as an absolute
destination (`move`/`clr` to `abs.w`/`abs.l`). Every such encoding carries the
address as a literal operand word. So: scan the release ROM for every instruction
whose operand resolves into `[System_Slots, Effect_Slots)`, and require that every
one of them is a COMPARE — `cmpa`, which cannot write.

Measured when this landed: the release ROM contains exactly ONE reference to the
range, `cmpa.w #System_Slots, a0` at ROM $2DAC, which is `DeleteObject`'s pool
classification (RAM order Player | Dynamic | System | Effect — it decides which free
stack a dying slot returns to, and a System slot returns to none). The DEBUG ROM
contains ELEVEN: that same compare, the three pool sweeps, and the seven
`movea.l #DEBUG_*_SST, a0` writers in `games/sonic4/test/ojz_scroll_test.emp` — all
seven inside the `if DEBUG == 1` bodies of `Debug_PresetReadout_Show`,
`Debug_WaterlineStamp_Show` and `Debug_TierTags_Update`, three procs the release
listing places at ONE shared address with zero bytes between them.

The DEBUG side is not decoration: it is this file's anti-vacuity control. A scanner
with a wrong opcode table, a wrong address range, or an off-by-one would report the
release ROM clear for the wrong reason. It has to FIND the eleven it should find in
the shape where they exist before its silence about the release shape means anything.

WHAT THIS FILE DOES **NOT** COVER — read this before adding a System-slot writer

  * A RUNTIME address. Only literal operands are visible here. An address computed
    into a register at runtime (`lea Effect_Slots, a0` then `suba.w #k, a0`; an SST
    pointer walked backwards past `Effect_Slots`; a wild pointer from a corrupted
    free stack) writes a System slot without any instruction naming one. Nothing
    static can see that. The standing check for it is a RUNTIME one and it is NOT
    written: read the eight slots' `code_addr` in a release build over a play
    session and require them all zero. That is emulator work.

  * Opcode encodings outside `_PATTERNS` below. The table covers the address-into-a-
    register forms (`lea`, `movea.w/l #`) and the common absolute destinations. It
    is not the whole ISA. A `movep`, an indexed absolute (`d8(An,Xn)`), or a byte
    store through a form not listed would pass unseen. `_PATTERNS` is the honest
    extent and adding to it is cheap.

  * The DEMO game. Only sonic4 shapes are scanned. `games/demo` has no System-slot
    code at all today; if it ever gains some this file will not notice.

  * Whether skipping the sweep is CORRECT — only whether the pool is written. If a
    future design wants a live System object in release, the fix is to restore the
    sweeps in `core.emp`/`collision.emp`, not to add an entry here.
"""

import os
import re

import pytest

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ROM_LIMIT = 0x400000  # a 4 MB cart: anything at or above this in the .lst is RAM


class Unmeasurable(Exception):
    """The question could not be asked. Never silently a pass."""


# ---------------------------------------------------------------------------
# The opcode table.
#
# Each row is (mask, value, operand_word_index, long_prefix, name). A match needs
# `word & mask == value`; the operand is the word `operand_word_index` words past
# the opcode, except when `long_prefix` is set, where the operand is a 32-bit
# absolute whose high word must equal `long_prefix` ($FFFF for Work RAM) and whose
# low word is the one after that.
#
# `kind` splits the table into what matters:
#   WRITE_KINDS  — this instruction puts the address somewhere it can be written
#                  through, or writes the address directly.
#   COMPARE_KINDS— cmpa. It reads a register against a literal and cannot write.
# ---------------------------------------------------------------------------
_PATTERNS = (
    # (mask,   value,  operand word idx, long prefix, name)
    (0xF1FF, 0x41F8, 1, None, "lea abs.w"),
    (0xF1FF, 0x41F9, 1, 0xFFFF, "lea abs.l"),
    (0xF1FF, 0x207C, 1, 0xFFFF, "movea.l #"),
    (0xF1FF, 0x307C, 1, None, "movea.w #"),
    (0xF1FF, 0xB0FC, 1, None, "cmpa.w #"),
    (0xF1FF, 0xB1FC, 1, 0xFFFF, "cmpa.l #"),
    (0xFFFF, 0x4278, 1, None, "clr.w abs.w"),
    (0xFFFF, 0x4238, 1, None, "clr.b abs.w"),
    (0xFFFF, 0x4A78, 1, None, "tst.w abs.w"),
    (0xFFFF, 0x31FC, 2, None, "move.w #,abs.w"),
    (0xFFFF, 0x21FC, 3, None, "move.l #,abs.w"),
    (0xFFF8, 0x31C0, 1, None, "move.w dn,abs.w"),
    (0xFFF8, 0x33C0, 1, 0xFFFF, "move.w dn,abs.l"),
    (0xFFF8, 0x11C0, 1, None, "move.b dn,abs.w"),
    (0xFFF8, 0x21C0, 1, None, "move.l dn,abs.w"),
    (0xFFF8, 0x23C0, 1, 0xFFFF, "move.l dn,abs.l"),
)

COMPARE_KINDS = frozenset({"cmpa.w #", "cmpa.l #"})
#: The address-into-a-register forms specifically. A shape that writes a System slot
#: has one of these; the anti-vacuity control counts them in the DEBUG ROM.
LOAD_KINDS = frozenset({"lea abs.w", "lea abs.l", "movea.l #", "movea.w #"})


def scan_pool_refs(rom, lo, hi):
    """Every instruction in `rom` whose literal operand lands in [lo, hi].

    `lo`/`hi` are LOW WORDS of Work RAM addresses (the form absolute-short carries).
    Returns a list of (rom_offset, kind, target_word), ROM order.
    """
    if not (0 <= lo <= hi <= 0xFFFF):
        raise Unmeasurable("nonsensical pool range $%X..$%X" % (lo, hi))
    if hi < lo:
        raise Unmeasurable("empty pool range — a scan over nothing reports every "
                           "ROM clear")

    def w(o):
        return (rom[o] << 8) | rom[o + 1]

    out = []
    for off in range(0, len(rom) - 7, 2):
        op = w(off)
        for mask, val, idx, prefix, name in _PATTERNS:
            if (op & mask) != val:
                continue
            if prefix is not None:
                if w(off + 2) != prefix:
                    break
                target = w(off + 4)
            else:
                target = w(off + 2 * idx)
            if lo <= target <= hi:
                out.append((off, name, target))
            break
    return out


def _lst_symbols(lst_path):
    """{name: address} from a sigil listing's symbol block."""
    syms = {}
    pat = re.compile(r"^\(\d+\)\s+\d+/([0-9A-Fa-f]+)\s+:\s+(\S+):\s*$")
    with open(lst_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = pat.match(line)
            if m:
                syms.setdefault(m.group(2), int(m.group(1), 16))
    if not syms:
        raise Unmeasurable("no symbols parsed out of %s — the listing format moved "
                           "and every derived expectation below is meaningless"
                           % lst_path)
    return syms


def pool_range(lst_path):
    """(lo, hi) low words of [System_Slots, Effect_Slots), from THIS shape's listing.

    Derived, never hardcoded: the debug shape's `ram.emp` carries
    `if DEBUG == 1 @shape_divergent` regions above the object pools, so the two
    shapes place `System_Slots` at DIFFERENT addresses ($FFFF9C90 release,
    $FFFF9D1E debug when this landed). A hardcoded range clipped the debug shape's
    top slot and hid a writer.
    """
    syms = _lst_symbols(lst_path)
    for need in ("System_Slots", "Effect_Slots"):
        if need not in syms:
            raise Unmeasurable(
                "%s is not in %s. The pool range cannot be derived, so this gate "
                "cannot answer — it must not report the ROM clear."
                % (need, os.path.basename(lst_path)))
    lo, hi = syms["System_Slots"] & 0xFFFF, (syms["Effect_Slots"] & 0xFFFF) - 1
    if hi <= lo:
        raise Unmeasurable("Effect_Slots ($%X) is not above System_Slots ($%X) — "
                           "the RAM order this gate assumes has changed"
                           % (syms["Effect_Slots"], syms["System_Slots"]))
    return lo, hi


def rom_symbol_at(lst_path, off):
    """The nearest preceding ROM symbol, so a failure names code and not an offset."""
    best, best_addr = "<before the first symbol>", -1
    for name, addr in _lst_symbols(lst_path).items():
        if addr < ROM_LIMIT and best_addr <= addr <= off:
            best, best_addr = name, addr
    return "%s+$%X" % (best, off - best_addr) if best_addr >= 0 else best


# ---------------------------------------------------------------------------
# Source-derived expectations. Derived from the .emp text, not copied from a run.
# ---------------------------------------------------------------------------

def _emp_sources():
    out = []
    for root, dirs, files in os.walk(AEON):
        dirs[:] = [d for d in dirs
                   if d not in (".git", ".claude", "docs", "tools", "emulators")]
        for f in files:
            if f.endswith((".emp", ".asm")):
                out.append(os.path.join(root, f))
    return sorted(out)


def _strip_comment(line):
    return line.split("//", 1)[0]


def system_slot_constants():
    """Names `equ`'d from `extern("System_Slots")` anywhere in the source."""
    pat = re.compile(r'^\s*equ\s+(\w+)\s*=.*extern\("System_Slots"\)')
    names = set()
    for path in _emp_sources():
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = pat.match(_strip_comment(line))
                if m:
                    names.add(m.group(1))
    return names


def source_writer_sites():
    """(path, lineno, text) for every `movea.l #<System-derived const>` in source.

    These are the writers. Enumerated over the CONSTANTS, not over hand-listed
    procs, so a new constant with a new writer is picked up without editing this.
    """
    consts = system_slot_constants()
    if not consts:
        raise Unmeasurable(
            "no `equ NAME = ... extern(\"System_Slots\")` constants found. Either "
            "the debug lab stopped using them (fine — say so here) or this regex "
            "stopped matching (not fine: every count below would read zero and the "
            "gate would pass by finding nothing).")
    pat = re.compile(r"movea\.l\s+#(%s)\b" % "|".join(sorted(consts)))
    sites = []
    for path in _emp_sources():
        with open(path, encoding="utf-8", errors="replace") as fh:
            for n, line in enumerate(fh, 1):
                if pat.search(_strip_comment(line)):
                    sites.append((os.path.relpath(path, AEON), n, line.strip()))
    return sites


def source_compare_sites():
    """(path, lineno) for every `cmpa` against `System_Slots` in source.

    These are the release shape's ONLY legitimate references: `DeleteObject`'s
    pool classification.
    """
    pat = re.compile(r'cmpa\.[wl]\s+#\s*extern\("System_Slots"\)')
    sites = []
    for path in _emp_sources():
        with open(path, encoding="utf-8", errors="replace") as fh:
            for n, line in enumerate(fh, 1):
                if pat.search(_strip_comment(line)):
                    sites.append((os.path.relpath(path, AEON), n))
    return sites


# ---------------------------------------------------------------------------
# Hermetic tests — the scanner's own mechanism, no build artifact needed.
# ---------------------------------------------------------------------------

class TestScannerMechanism:

    def test_it_finds_a_planted_lea(self):
        rom = b"\x4e\x71" * 4 + bytes.fromhex("41F89C90") + b"\x4e\x71" * 4
        hits = scan_pool_refs(rom, 0x9C90, 0x9F0F)
        assert [(h[1], h[2]) for h in hits] == [("lea abs.w", 0x9C90)]

    def test_it_finds_a_planted_movea_l_immediate(self):
        rom = b"\x4e\x71" * 4 + bytes.fromhex("207CFFFF9CE0") + b"\x4e\x71" * 4
        hits = scan_pool_refs(rom, 0x9C90, 0x9F0F)
        assert [(h[1], h[2]) for h in hits] == [("movea.l #", 0x9CE0)]

    def test_it_finds_a_planted_movea_w_immediate(self):
        """`movea.w #$9C90, a0` sign-extends to $FFFF9C90 — a real route in."""
        rom = b"\x4e\x71" * 4 + bytes.fromhex("307C9C90") + b"\x4e\x71" * 4
        assert [h[1] for h in scan_pool_refs(rom, 0x9C90, 0x9F0F)] == ["movea.w #"]

    def test_an_address_one_past_the_pool_is_not_a_hit(self):
        """The boundary is Effect_Slots exclusive; an Effect slot is not a hit."""
        rom = b"\x4e\x71" * 4 + bytes.fromhex("41F89F10") + b"\x4e\x71" * 4
        assert scan_pool_refs(rom, 0x9C90, 0x9F0F) == []

    def test_a_matching_word_that_is_not_the_operand_is_not_a_hit(self):
        """Bare data words in range must not register — that is why the opcode
        prefix is required, and the reason a raw word scan was rejected (557 raw
        even-aligned hits in the release ROM, 1 with the prefixes)."""
        rom = b"\x9c\x90" * 16
        assert scan_pool_refs(rom, 0x9C90, 0x9F0F) == []

    def test_an_inverted_range_refuses_rather_than_reporting_clear(self):
        with pytest.raises(Unmeasurable):
            scan_pool_refs(b"\x4e\x71" * 8, 0x9F0F, 0x9C90)

    def test_a_listing_without_the_pool_symbols_refuses(self, tmp_path):
        lst = tmp_path / "x.lst"
        lst.write_text("(0) 1/0 :        Vectors:\n")
        with pytest.raises(Unmeasurable) as e:
            pool_range(str(lst))
        assert "cannot answer" in str(e.value)

    def test_a_listing_with_no_symbols_at_all_refuses(self, tmp_path):
        lst = tmp_path / "empty.lst"
        lst.write_text("nothing that parses\n")
        with pytest.raises(Unmeasurable):
            pool_range(str(lst))


class TestSourceDerivation:

    def test_the_writer_constants_are_still_findable(self):
        """If this regex stops matching, every count below reads zero and the gate
        passes by finding nothing. So the population is asserted non-empty first."""
        assert system_slot_constants(), (
            "no System_Slots-derived constants in source — see Unmeasurable in "
            "source_writer_sites() for why that is a gate failure, not a pass")

    def test_the_pool_classification_compare_still_exists(self):
        sites = source_compare_sites()
        assert sites, ("no `cmpa #extern(\"System_Slots\")` in source. DeleteObject's "
                       "pool classification is what the release ROM's single "
                       "surviving reference IS; without it the release expectation "
                       "below is derived from an empty set.")


# ---------------------------------------------------------------------------
# The artifact tests. These are the gate.
# ---------------------------------------------------------------------------

@pytest.mark.needs_build("s4.bin", "s4.lst")
def test_release_rom_never_loads_a_system_slot_address():
    """RELEASE: every reference to the System pool must be a COMPARE.

    This is the standing form of "the 8 System slots are never filled in a release
    build". A `cmpa` cannot write; a `lea`/`movea`/absolute store is how a write
    begins. One appearing here means the sweep-skip in `RunObjects`,
    `RunObjects_Frozen` and `TouchResponse` may now be skipping a LIVE object, and
    the symptom would be an object that silently never runs.
    """
    rom_path, lst_path = os.path.join(AEON, "s4.bin"), os.path.join(AEON, "s4.lst")
    lo, hi = pool_range(lst_path)
    rom = open(rom_path, "rb").read()
    hits = scan_pool_refs(rom, lo, hi)

    offenders = [h for h in hits if h[1] not in COMPARE_KINDS]
    assert not offenders, (
        "the release ROM references the System pool ($%04X..$%04X) with an "
        "instruction that is not a compare:\n%s\n\n"
        "The release shape does not sweep those eight slots (LS-10), so a slot this "
        "reference fills would silently never run. Two ways out, and they are NOT "
        "interchangeable: (a) the reference provably cannot fill a slot — extend "
        "COMPARE_KINDS and write down why; (b) it can, so release now wants a live "
        "System object — restore the sweeps in engine/objects/core.emp "
        "(RunObjects, RunObjects_Frozen) and engine/objects/collision.emp "
        "(TouchResponse) out of their `if DEBUG == 1`, and update this test "
        "deliberately rather than deleting it."
        % (lo, hi, "\n".join("  ROM $%06X  %-16s $%04X   %s"
                             % (o, k, t, rom_symbol_at(lst_path, o))
                             for o, k, t in hits if (o, k, t) in offenders)))

    expected = len(source_compare_sites())
    actual = len([h for h in hits if h[1] in COMPARE_KINDS])
    assert actual == expected, (
        "expected %d System-pool compare(s) in the release ROM — one per "
        "`cmpa #extern(\"System_Slots\")` in source (%s) — but found %d. A compare "
        "cannot fill a slot, so this is not a correctness failure; it means the "
        "derivation and the artifact have drifted apart and one of them is stale."
        % (expected, ", ".join("%s:%d" % s for s in source_compare_sites()), actual))


@pytest.mark.needs_build("s4.debug.bin", "s4.debug.lst")
def test_debug_rom_still_contains_the_writers_the_release_rom_lacks():
    """DEBUG: the anti-vacuity control, and the SAME question answered the other way.

    A scanner with a wrong opcode table or a wrong range would call the release ROM
    clear for the wrong reason. This asserts it FINDS things where they are known to
    be — and pins the writer count to the source enumeration, so a writer that
    escapes its `if DEBUG == 1` and lands in release shows up here as a SHORTFALL
    even before the release test above sees it.
    """
    rom_path = os.path.join(AEON, "s4.debug.bin")
    lst_path = os.path.join(AEON, "s4.debug.lst")
    lo, hi = pool_range(lst_path)
    hits = scan_pool_refs(open(rom_path, "rb").read(), lo, hi)

    loads = [h for h in hits if h[1] in LOAD_KINDS]
    assert loads, (
        "the DEBUG ROM contains NO address-loading reference to the System pool "
        "($%04X..$%04X). The debug shape sweeps those slots and its effects lab "
        "builds objects in them, so zero here means this scanner is not looking "
        "where it thinks it is — and its silence about the release ROM means "
        "nothing." % (lo, hi))

    writers = source_writer_sites()
    movea = [h for h in hits if h[1] == "movea.l #"]
    assert len(movea) == len(writers), (
        "the DEBUG ROM has %d `movea.l #<System slot>` writer(s) but source has "
        "%d:\n%s\n\nFewer in the ROM than in source means a writer did not compile "
        "into the debug shape; MORE means a writer this file's source enumeration "
        "cannot see, which is exactly the blind spot the release test exists to "
        "catch. Re-derive both before changing this number."
        % (len(movea), len(writers),
           "\n".join("  %s:%d  %s" % w for w in writers)))
