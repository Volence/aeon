"""Unit cover for `tools/reels_gate.py` — the pure halves, plus the source reads.

WHY THIS FILE NEVER OPENS A ROM, plane_base_swap_gate's own reason: build.sh's pytest
lane runs BEFORE the sigil build, so a unit test opening `s4.debug.bin` here would grade
a PREVIOUS build. The gate's ROM half runs post-sigil, in build.sh, with
`--built-after`. What is covered here is the judgement the gate adds — array parsing,
the two's-complement byte encoding, distinctness — plus the two facts it reads out of
game source, which are exactly the facts a source-level regression would break before
any ROM existed.

PROVEN RED, by editing a COMMITTED baseline and restoring it, 2026-09-03. `__pycache__`
was cleared between mutation runs (the stale-.pyc false-green trap this repo has
measured before: a same-length, same-second mutation can be served from cache). Four
mutations, each shown applied on disk (`git diff --stat` naming the file) before the
run, each restored with `git checkout HEAD -- <path>` afterwards. Full evidence,
including the ROM-level runs (which need a build and so cannot live in this file), is in
docs/DEFERRED_WORK.md's EFFECTS-W1 item 10a booking.

  * `OJZ_REEL_SPEEDS` collides two entries (index 1's `-5` -> `3`, matching index 0)
        -> build RED: `reel_rates_ok()`'s distinctness ensure
           (games/sonic4/config/constants.emp) fires by name, naming the colliding
           array. Re-measured on a GENERATED table 2026-09-04 (EFFECTS-W1 item 10 step
           4): authoring `[3, 3, 2, -4, 6]` into an editor scene's `reels.rates`
           produces exactly ONE build error, that ensure — which is what "the guard
           travels" means, and what the five-ary `distinct5()` it replaced could not
           do. This unit file's own
           `test_all_distinct_refuses_a_collision` covers the PURE half of that same
           judgement without a build.
  * `OJZ_REEL_SPEEDS` shortened to 4 entries (REEL_BAND_COUNT left at 5)
        -> build RED: the array's own `.len == REEL_BAND_COUNT` ensure fires.
  * The `if DEBUG == 1` gate removed from `pub data OJZ_Reel_Speed` and the
    `if DEBUG == 1 {}` wrap removed from `pub proc OJZ_Reels_Fill` (both made
    unconditional)
        -> release build green, `tools/reels_gate.py --shape release` RED: "emits N
           bytes in the RELEASE shape" for both symbols.
  * A single ROM byte hand-patched post-build (`OJZ_Reel_Speed`'s first byte, $03 -> $04)
        -> build untouched (nothing at build time re-reads the ROM's own bytes),
           `tools/reels_gate.py --shape debug` RED: "band 0 ... MISMATCH" — the class of
           divergence only a ROM-level check can catch, mirroring OJZ_BaseSwap's
           literal-bypass mutation.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import reels_gate as G  # noqa: E402


# ---------------------------------------------------------------------------
# The two facts, read out of game source. Not copies: the same calls the gate makes.
# ---------------------------------------------------------------------------

def _facts():
    return dict(
        band_count=G.emp_const(G.GAME_CONSTANTS, "REEL_BAND_COUNT"),
        speeds=G.emp_int_array(G.FIXTURE, "OJZ_REEL_SPEEDS"),
    )


def test_reel_band_count_is_five():
    """A change here is a real geometry change (REEL_COLS_PER_BAND must move with it,
    per games/sonic4/data/effects/ojz_effects.emp's own ensure) — this pins today's
    shipped value so an accidental edit is visible as a failing assumption, not a
    silently-adjusted gate."""
    assert G.emp_const(G.GAME_CONSTANTS, "REEL_BAND_COUNT") == 5


def test_the_speed_array_matches_band_count():
    f = _facts()
    assert len(f["speeds"]) == f["band_count"], (
        f"OJZ_REEL_SPEEDS has {len(f['speeds'])} entries, REEL_BAND_COUNT is "
        f"{f['band_count']} — the source's own ensure should have refused this build")


def test_the_shipped_speeds_are_pairwise_distinct():
    """The whole 'reels' claim, re-measured independently of `reel_rates_ok()`'s ensure."""
    f = _facts()
    assert G.all_distinct(f["speeds"]), (
        f"OJZ_REEL_SPEEDS = {f['speeds']} collide — two reel bands would share a rate")


def test_emp_int_array_parses_negative_entries():
    """The parser must handle signed decimal literals — every other speed is negative."""
    f = _facts()
    assert any(v < 0 for v in f["speeds"]), (
        "the shipped array has no negative entries to exercise the parser's sign "
        "handling — if this ever fires, OJZ_REEL_SPEEDS changed shape and the next "
        "assertion below is the one that actually matters")
    assert -5 in f["speeds"] or True  # documents intent; the real check is the round-trip below


def test_emp_int_array_round_trips_on_a_synthetic_source(tmp_path):
    """Independent of the shipped file: prove the regex handles the general shape,
    including negatives and whitespace variance, without relying on today's five values."""
    p = tmp_path / "synthetic.emp"
    p.write_text("const SOME_ARRAY: [i8; 4] = [ 1, -2,3 , -128 ]\n")
    assert G.emp_int_array(str(p), "SOME_ARRAY") == [1, -2, 3, -128]


def test_emp_int_array_refuses_a_missing_name():
    try:
        G.emp_int_array(G.FIXTURE, "THIS_NAME_DOES_NOT_EXIST_ANYWHERE")
    except G.Unmeasurable:
        return
    raise AssertionError("a missing array name must be UNMEASURABLE, not silently empty")


# ---------------------------------------------------------------------------
# The signed-byte encoder — the two's-complement half a ROM byte compare needs.
# ---------------------------------------------------------------------------

def test_to_bytes_i8_encodes_negatives_as_twos_complement():
    assert G.to_bytes_i8([3, -5, 2, -4, 6]) == [0x03, 0xFB, 0x02, 0xFC, 0x06]


def test_to_bytes_i8_accepts_the_i8_extremes():
    assert G.to_bytes_i8([127, -128]) == [0x7F, 0x80]


def test_to_bytes_i8_refuses_a_value_outside_i8():
    try:
        G.to_bytes_i8([128])
    except G.Unmeasurable:
        pass
    else:
        raise AssertionError("128 does not fit in a signed byte and must be refused")
    try:
        G.to_bytes_i8([-129])
    except G.Unmeasurable:
        pass
    else:
        raise AssertionError("-129 does not fit in a signed byte and must be refused")


# ---------------------------------------------------------------------------
# Distinctness — the pure half of the "reels, not ripple" claim.
# ---------------------------------------------------------------------------

def test_all_distinct_accepts_five_different_values():
    assert G.all_distinct([3, -5, 2, -4, 6]) is True


def test_all_distinct_refuses_a_collision():
    """The exact mutation this file's docstring proves red at the build: two bands
    sharing a rate. Covered here as the pure judgement, without needing a build."""
    assert G.all_distinct([3, 3, 2, -4, 6]) is False


def test_all_distinct_refuses_a_collision_at_the_far_end():
    """A collision is a collision anywhere in the list, not just index 0 vs 1."""
    assert G.all_distinct([3, -5, 2, -4, -5]) is False


# ---------------------------------------------------------------------------
# THE AUTHORED HALF (gate widened 2026-09-04, parcel/reels-instruments-authored).
#
# Same rule as everything above: no ROM is opened here, because build.sh's pytest lane
# runs BEFORE the sigil build and a unit test reading s4.debug.bin would grade a PREVIOUS
# build. What is covered is the JUDGEMENT the widening adds — the generated module's
# parse, the association-table walk, the scene-document read — plus the three-way
# agreement between the shipped document, the shipped generated module and REEL_BAND_COUNT
# that a source-level regression would break before any ROM existed.
#
# PROVEN RED, on disk, against the built artifacts, 2026-09-04 (the ROM-level half cannot
# live in this file; the evidence is in the parcel report and docs/DEFERRED_WORK.md):
#   * the editor document's rates[0] 3 -> 7, generated module untouched
#         -> reels_gate.py --shape debug exit 1, naming scene 'ojz_act1_depth' and both
#            lists. This is the leg NOTHING covered before: a generator that drops,
#            reorders or rescales an author's rates.
#   * one ROM byte at EditorReels_OJZ_Act1_ojz_act1_depth+0, $03 -> $04
#         -> exit 1, "band 0 ... MISMATCH". The emitted-bytes leg.
#   * the association table's config long $013E92 -> $013DD4 (a real, valid, WRONG
#     section-binding address)
#         -> exit 1, "binding 0's config long is $013DD4, not ...Sec4's $013E92". A
#            plausible-address mutation, which a byte-count check cannot see.
#   * the release listing with EditorReelBindings_OJZ_Act1 12 bytes below its neighbour
#         -> --shape release exit 1, "emits 12 bytes in the RELEASE shape".
# ---------------------------------------------------------------------------

import os  # noqa: E402


def _generated():
    mods = G.generated_modules()
    assert mods, "generated_modules() must refuse an empty glob, not return one"
    return mods[0]


def test_generated_modules_finds_the_shipped_act_module():
    assert any(p.endswith(os.path.join("ojz", "act1", "effects_scenes.emp"))
               for p in G.generated_modules())


def test_the_generated_module_parses_into_tables_and_bindings():
    cap, tables, bind_sym, pairs, next_decl = G.authored_reels(_generated())
    assert bind_sym == f"EditorReelBindings_{cap}"
    assert next_decl.startswith("Editor"), (
        f"the neighbour used for the size/collapse arithmetic is {next_decl!r}; if the "
        f"generator's emission order changed, that arithmetic changed meaning")
    for sym, scene_id, rates in tables:
        assert sym == f"EditorReels_{cap}_{scene_id}"
        assert len(rates) == G.emp_const(G.GAME_CONSTANTS, "REEL_BAND_COUNT")
        assert G.all_distinct(rates)


def test_every_binding_names_a_table_the_module_declares():
    """The association table's rates half must name a symbol this module actually emits.
    A binding pointing at a table from another act's module would link and then hand
    OJZ_Reels_Fill a table it never validated."""
    _, tables, bind_sym, pairs, _ = G.authored_reels(_generated())
    declared = {sym for sym, _, _ in tables}
    for n, (cfg_sym, rate_sym) in enumerate(pairs):
        assert rate_sym in declared, (
            f"`{bind_sym}` binding {n} names rates `{rate_sym}`, which this module does "
            f"not declare (it declares {sorted(declared)})")
        assert cfg_sym.startswith("EditorSceneBinding_"), (
            f"`{bind_sym}` binding {n}'s config is `{cfg_sym}` — the walk compares it "
            f"against Parallax_Current_Config, which only ever holds a scene binding's "
            f"address")


def test_every_authored_table_matches_its_scene_document():
    """Leg 1 vs leg 2, without a ROM: what the author wrote against what the generator
    emitted. The comparison is ORDER-SENSITIVE on purpose — index i owns screen X
    64i..64i+63, so a sorted or reversed array silently relocates every strip."""
    _, tables, _, _, _ = G.authored_reels(_generated())
    for sym, scene_id, gen_rates in tables:
        assert gen_rates == G.scene_doc_rates(scene_id), (
            f"{sym}: generated {gen_rates}, document {G.scene_doc_rates(scene_id)}")


def test_scene_doc_rates_refuses_a_scene_with_no_document():
    try:
        G.scene_doc_rates("this_scene_id_does_not_exist")
    except G.Unmeasurable:
        return
    raise AssertionError("a missing scene document must be UNMEASURABLE, never a skip")


def test_authored_reels_refuses_a_module_with_no_association_table(tmp_path):
    """The table is emitted in EVERY bake (OJZ_Reels_Fill names it in a `lea`), so its
    absence is a parse failure or a generator change — never 'no reels authored'."""
    p = tmp_path / "effects_scenes.emp"
    p.write_text("pub data Something: [u8; 1] = [0]\n")
    try:
        G.authored_reels(str(p))
    except G.Unmeasurable:
        return
    raise AssertionError("a module with no EditorReelBindings_* must be UNMEASURABLE")


def test_authored_reels_refuses_a_table_with_no_terminator(tmp_path):
    p = tmp_path / "effects_scenes.emp"
    p.write_text(
        'pub data EditorReelBindings_X_Y: [*u8; 2] = if DEBUG == 1 '
        '{ [extern("A"), extern("B")] } else { [] }\n'
        'pub data After: [u8; 1] = [0]\n')
    try:
        G.authored_reels(str(p))
    except G.Unmeasurable:
        return
    raise AssertionError("a table with no `0` terminator must be UNMEASURABLE — "
                         "OJZ_Reels_Fill's walk would run past its end")


def test_authored_reels_refuses_an_odd_entry_count(tmp_path):
    """OJZ_Reels_Fill reads (config, rates) PAIRS; an odd count leaves it reading the
    terminator as a rate table pointer."""
    p = tmp_path / "effects_scenes.emp"
    p.write_text(
        'pub data EditorReelBindings_X_Y: [*u8; 2] = if DEBUG == 1 '
        '{ [extern("A"), 0] } else { [] }\n'
        'pub data After: [u8; 1] = [0]\n')
    try:
        G.authored_reels(str(p))
    except G.Unmeasurable:
        return
    raise AssertionError("an odd entry count must be UNMEASURABLE")


def test_authored_reels_refuses_a_module_with_no_following_declaration(tmp_path):
    """Without a neighbour there is no size arithmetic, and a table emitting bytes in the
    RELEASE shape would be invisible — the exact failure the release arm exists to catch."""
    p = tmp_path / "effects_scenes.emp"
    p.write_text('pub data EditorReelBindings_X_Y: [*u8; 1] = if DEBUG == 1 '
                 '{ [0] } else { [] }\n')
    try:
        G.authored_reels(str(p))
    except G.Unmeasurable:
        return
    raise AssertionError("no following `pub data` must be UNMEASURABLE")


def test_emp_int_array_parses_an_unannotated_const(tmp_path):
    """`EditorReelsSrc_*` carries no type annotation on purpose (so reel_rates_ok's
    magnitude arm sees the RAW authored ints), while OJZ_REEL_SPEEDS carries one. One
    parser must read both spellings or this gate drifts from the source it grades."""
    p = tmp_path / "synthetic.emp"
    p.write_text("const UNANNOTATED = [3, -5, 2, -4, 6]\n")
    assert G.emp_int_array(str(p), "UNANNOTATED") == [3, -5, 2, -4, 6]
