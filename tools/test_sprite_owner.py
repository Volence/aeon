#!/usr/bin/env python3
"""SPRITE-OWNER source gates — the ownership map's bound, its DEBUG-only-ness, and the
"every SAT writer stamps an owner" invariant.

WHY THIS EXISTS. `Sprite_Owner` (engine/ram.emp, DEBUG only) records, per hardware
sprite, the SST address of the object that emitted it, so the emulator can name the
object behind a clicked sprite. The whole point of the feature is that the name is
RIGHT: oracle's stated bar was that they would rather ship nothing than ship a
confident wrong name. Two defects that would have produced exactly that were caught in
review before any code existed (docs/DEFERRED_WORK.md, "## SPRITE-OWNER"), and this
file gates the two of them that a source check can still see.

WHAT IS GATED, and each is a real way this feature goes silently wrong:

  1. THE ARRAY'S LENGTH IS THE SAT BOUND, spelled as the constant. A literal `80`
     agrees with `MAX_VDP_SPRITES` today and stops agreeing the day the bound moves,
     in EITHER direction: raised, the writers run off the end of the array into
     whatever RAM follows; lowered, the tail is dead but the gate would still be
     green if it only compared against a number typed in here. So this file never
     types the bound in — it reads MAX_VDP_SPRITES out of engine/system/constants.emp
     and requires ram.emp to spell that same NAME.

  2. THE ENTRY CLEAR COVERS THE WHOLE ARRAY. Render_Sprites clears long-wise, so its
     loop bound is `MAX_VDP_SPRITES/2-1`. Two independent things can rot here: the
     expression can stop mentioning the constant (a typed-in `#39`), and the constant
     can go odd, which would clear one entry short AND run two bytes past the end.
     Both are checked, the second by evaluating the parsed expression against the
     parsed constant rather than against a remembered answer. (An `ensure` in
     sprites.emp fails the BUILD on an odd bound; this is the same fact asserted where
     a reader can see the arithmetic.)

  3. EVERY SAT WRITER STAMPS AN OWNER. This is defect 1's shape. The SAT is written on
     three paths — the piece loop's `size_link` (two flip forms), InsertSpriteMasks,
     and DrawRings — and rings NEVER go through size_link. A design that advanced a
     cursor inside size_link would have fallen one entry behind at the first ring and
     misattributed every later sprite, while leaving the SAT itself perfectly correct,
     so a VRAM-vs-buffer proof would have CERTIFIED the wrong name. The fix is that the
     stamp is written at the entry INDEX; the invariant that makes that work is that
     every writer claims its slot with the same `d5` increment and stamps before it.
     This gate walks every `d5` increment in the two SAT-owning modules and requires an
     owner stamp above it.

WHAT THIS GATE CANNOT SEE, stated rather than papered over: a SAT writer added in a
THIRD module is outside the census below. That case is not left to chance either — it
is why Render_Sprites clears the WHOLE array every frame instead of `[0..Sprites_Rendered)`.
An unstamped entry then reads $0000, which the emulator renders as an honest "unknown",
not as the previous frame's still-valid SST address.
"""
import re
from pathlib import Path

import pytest

AEON = Path(__file__).resolve().parent.parent
CONSTANTS = AEON / "engine" / "system" / "constants.emp"
RAM = AEON / "engine" / "ram.emp"
SPRITES = AEON / "engine" / "objects" / "sprites.emp"
RINGS = AEON / "engine" / "objects" / "rings.emp"

# The two modules that own the VDP sprite attribute table. Scoped deliberately — see
# "WHAT THIS GATE CANNOT SEE" above.
SAT_MODULES = (SPRITES, RINGS)

# A slot claim: the running SAT index d5 being advanced. Every writer does this and then
# stamps d5 as the link byte, which is precisely why PRE-increment d5 is the entry's own
# index on every path.
D5_CLAIM = re.compile(r"^\s*(?:addq|addi|add)\.[wl]\s+#[^,]+,\s*d5\b")
# The owner stamp, in any of its three spellings (a1 = SST, #1 = ring, #2 = mask).
OWNER_STAMP = re.compile(r"move\.w\s+(?:a1|#\d+),\s*\(a6,\s*d0\.w\)")
# How far above a claim the stamp may sit. The longest real gap today is
# InsertSpriteMasks' stack-borrowed form (stamp, restore, then four SAT field writes).
STAMP_LOOKBACK = 15


def _read(path):
    assert path.exists(), f"{path} is missing — this gate cannot measure anything"
    return path.read_text().splitlines()


def max_vdp_sprites():
    """The SAT bound, read from its declaring module. Never typed in here."""
    for line in _read(CONSTANTS):
        m = re.match(r"\s*pub const\s+MAX_VDP_SPRITES\s*=\s*(\d+)\s*(?://.*)?$", line)
        if m:
            return int(m.group(1))
    pytest.fail(f"MAX_VDP_SPRITES not found in {CONSTANTS} — the gate cannot measure")


def sprite_owner_decl():
    """(line index, element type, length expression, enclosing `if` header) for
    Sprite_Owner in engine/ram.emp."""
    lines = _read(RAM)
    for i, line in enumerate(lines):
        m = re.match(r"\s*Sprite_Owner:\s*\[\s*(\w+)\s*;\s*([^\]]+?)\s*\]\s*,", line)
        if not m:
            continue
        # Walk back to the nearest unclosed `{` header — the block this field sits in.
        depth = 0
        for j in range(i - 1, -1, -1):
            code = lines[j].split("//")[0]
            depth += code.count("}") - code.count("{")
            if depth < 0:
                return i, m.group(1), m.group(2), lines[j].split("//")[0].strip()
        pytest.fail("Sprite_Owner is not inside any block in engine/ram.emp")
    pytest.fail(f"Sprite_Owner not declared in {RAM} — the gate cannot measure")


def clear_bound_expr():
    """The `move.w #<expr>, d1` loop bound of Render_Sprites' Sprite_Owner clear."""
    lines = _read(SPRITES)
    for i, line in enumerate(lines):
        if ".owner_clear:" not in line:
            continue
        for j in range(i - 1, max(i - 8, -1), -1):
            m = re.match(r"\s*move\.w\s+#([^,]+),\s*d1\b", lines[j])
            if m:
                return m.group(1).strip()
        pytest.fail("no `move.w #<bound>, d1` above .owner_clear in sprites.emp")
    pytest.fail(f".owner_clear not found in {SPRITES} — the gate cannot measure")


def test_sprite_owner_length_is_the_sat_bound_by_name():
    """Pin 1. The array length must BE MAX_VDP_SPRITES, not a number equal to it."""
    _, elem, length, _ = sprite_owner_decl()
    assert elem == "u16", (
        f"Sprite_Owner holds SST address words; element type is {elem!r}. A byte "
        "element cannot hold an address and a long doubles the cost for nothing."
    )
    assert length == "MAX_VDP_SPRITES", (
        f"Sprite_Owner is declared [{elem}; {length}]. It must be sized by the NAME "
        "MAX_VDP_SPRITES so it tracks the SAT bound in both directions; a literal "
        "that happens to equal today's bound goes silently wrong when the bound moves."
    )


def test_sprite_owner_is_debug_only():
    """Pin 1b. Release must pay nothing — structurally, not by intention."""
    _, _, _, header = sprite_owner_decl()
    assert re.match(r"if\s+DEBUG\s*==\s*1\b", header), (
        f"Sprite_Owner's enclosing block header is {header!r}; it must be a "
        "`if DEBUG == 1` block so release allocates no RAM for it. (The ROMs being "
        "byte-identical is the real proof; this is the structural one.)"
    )
    assert "@shape_divergent" in header, (
        f"Sprite_Owner's block header is {header!r}. A DEBUG-only size-varying vars "
        "group must carry @shape_divergent or the region lowerer rejects it."
    )


def test_owner_clear_covers_exactly_the_whole_array():
    """Pin 2. Derived from the parsed constant, and it bites in both directions."""
    bound = max_vdp_sprites()
    expr = clear_bound_expr()
    assert "MAX_VDP_SPRITES" in expr, (
        f"the Sprite_Owner clear's loop bound is spelled {expr!r}. It must be derived "
        "from MAX_VDP_SPRITES; a typed-in count stops covering the array the day the "
        "bound moves, and an under-clear leaves a stale VALID SST address in range — "
        "a confident wrong object name, the exact failure this feature exists to avoid."
    )
    # Evaluate the source expression with the source constant. `dbf` runs bound+1 times,
    # each pass clearing one long = 2 u16 entries.
    #
    # `/` is TRUNCATING in .emp/68000 and FLOAT in Python — evaluated with Python's `/`
    # an odd bound gives 39.5 iterations covering "79.0" entries and the pin passes,
    # which is exactly the under-clear it exists to catch. (Measured: this file's first
    # draft did that. Poisoning MAX_VDP_SPRITES to 79 is what found it.)
    py_expr = expr.replace("/", "//")
    iterations = eval(py_expr, {"__builtins__": {}}, {"MAX_VDP_SPRITES": bound}) + 1
    assert isinstance(iterations, int), (
        f"the clear bound {expr!r} did not evaluate to an integer — the gate cannot "
        "measure the coverage it is supposed to check")
    assert iterations * 2 == bound, (
        f"the clear covers {iterations * 2} entries but the SAT holds {bound}. With "
        f"MAX_VDP_SPRITES={bound} an even bound is required: an odd one clears one "
        "entry short AND writes two bytes past the end of the array."
    )


def _enclosing_symbol(lines, i):
    """Name of the `proc` / `comptime fn` the line at index i sits in ('' if none)."""
    for j in range(i, -1, -1):
        m = re.match(r"\s*(?:pub\s+)?(?:comptime\s+fn|proc)\s+(\w+)", lines[j])
        if m:
            return m.group(1)
    return ""


def test_the_piece_loop_splices_the_stamp_above_its_slot_claim():
    """Pin 3a. The piece loop's stamp is not textually adjacent to its `addq` — both
    are Code returned by separate comptime fns and joined by the emit_piece_loop
    skeleton. What has to hold is the SPLICE ORDER: `{owner_term()}` immediately
    before `{size_link(...)}`. Swap them and the stamp indexes the NEXT slot; delete
    it and four unrolled variants stop recording an owner at all. Neither shows up as
    a textual change anywhere near `size_link`."""
    lines = _read(SPRITES)
    holes = [ln.split("//")[0].strip() for i, ln in enumerate(lines)
             if _enclosing_symbol(lines, i) == "emit_piece_loop"
             and ln.split("//")[0].strip().startswith("{")
             and ln.split("//")[0].strip().endswith("}")]
    assert holes, (
        f"emit_piece_loop's splice holes were not found in {SPRITES} — the gate "
        "cannot measure")
    assert "{owner_term()}" in holes, (
        f"emit_piece_loop's splice holes are {holes}; the piece loop no longer stamps "
        "an owner, so every object-piece sprite would report whoever used the slot last."
    )
    owner_at = holes.index("{owner_term()}")
    size_at = next((k for k, h in enumerate(holes) if h.startswith("{size_link(")), None)
    assert size_at is not None, "emit_piece_loop no longer splices size_link"
    assert owner_at == size_at - 1, (
        f"splice order is {holes}. owner_term() must sit IMMEDIATELY before "
        "size_link(): it reads d5 pre-increment (size_link does the increment), and it "
        "uses d0, which is dead only between y_term's final store and tile_term's "
        "opening load. Either move breaks it silently."
    )
    assert OWNER_STAMP.search("\n".join(lines)), "owner_term no longer emits a stamp"


def test_every_sat_slot_claim_stamps_an_owner():
    """Pin 3. Defect 1's shape: a writer that claims a SAT slot without recording who
    owns it leaves a stale entry that reads as somebody else's object.

    `size_link`'s two claims are covered by the splice-order pin above, not by a
    textual lookback — its stamp arrives from a sibling comptime fn."""
    claims = []
    for path in SAT_MODULES:
        lines = _read(path)
        for i, line in enumerate(lines):
            if D5_CLAIM.match(line):
                claims.append((path, i, lines))

    assert len(claims) >= 4, (
        f"found {len(claims)} SAT slot claims across {[p.name for p in SAT_MODULES]}; "
        "there are at least four (size_link's two flip forms, InsertSpriteMasks, "
        "DrawRings). Fewer means the idiom moved and this gate is measuring nothing."
    )

    unstamped = []
    spliced = 0
    for path, i, lines in claims:
        if _enclosing_symbol(lines, i) == "size_link":
            spliced += 1
            continue
        window = lines[max(0, i - STAMP_LOOKBACK):i]
        if not any(OWNER_STAMP.search(w) for w in window):
            unstamped.append(f"{path.relative_to(AEON)}:{i + 1}: {lines[i].strip()}")

    assert spliced == 2, (
        f"expected size_link's two flip forms to claim a slot each, found {spliced}. "
        "If that changed, re-derive which claims the emit_piece_loop splice covers."
    )
    assert not unstamped, (
        "SAT slot claims with no Sprite_Owner stamp above them:\n  "
        + "\n  ".join(unstamped)
        + "\n\nEvery writer that advances d5 claims a hardware sprite and must record "
        "its owner at the PRE-increment index. Skipping one does not corrupt the SAT — "
        "which is why a VRAM-vs-buffer proof cannot catch it — it silently attributes "
        "that sprite to whatever object last used the slot."
    )


def test_owner_stamp_precedes_the_slot_claim_it_indexes():
    """Pin 3b. The stamp reads d5 PRE-increment. A stamp placed after the `addq` would
    index the NEXT slot — assembles cleanly, names the wrong object, every sprite."""
    misordered = []
    for path in SAT_MODULES:
        lines = _read(path)
        for i, line in enumerate(lines):
            if not OWNER_STAMP.search(line) or line.lstrip().startswith("//"):
                continue
            claim_above = any(
                D5_CLAIM.match(lines[j]) for j in range(max(0, i - 4), i)
            )
            if claim_above:
                misordered.append(f"{path.relative_to(AEON)}:{i + 1}: {line.strip()}")
    assert not misordered, (
        "Sprite_Owner stamps sitting immediately BELOW a d5 increment:\n  "
        + "\n  ".join(misordered)
        + "\n\nd5 is stamped as the link byte AFTER being incremented, so pre-increment "
        "d5 is this entry's index and post-increment d5 is the next one's."
    )
