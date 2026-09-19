#!/usr/bin/env python3
"""fg_left_edge_gate — the column-19 borrow, asserted against the running machine.

WHAT IT GATES. With per-column V-scroll on (VDP reg $0B bit 2) and a plane's HScroll off
the 16-px grain, that plane's leading sliver renders at `VSRAM[$4C] & VSRAM[$4E]` — the
bitwise AND of column-pair 19's two words, the same value for both planes, H40 only.
That is Eke-Eke's hardware test (PAL MD2, 2010), and it is what Genesis Plus GX and Oracle
both implement. `Parallax_Step5_Vscroll`'s column-19 borrow exists to make that AND come
out equal to the FOREGROUND's V-scroll. So the gate asks TWO questions on every scene that
raises the mode bit and ACCEPTS the borrow:

    (VSRAM[$4C] & VSRAM[$4E]) & $7FF  ==  (Camera_Y >> 16) & $7FF      # the screen
     VSRAM[$4E]               & $7FF  ==  (Camera_Y >> 16) & $7FF      # the store

The first is what the VDP consumes at that sliver, so a tree failing it renders wrong
whatever the cause. The second is what the borrow's one instruction does, and it exists
because the first does NOT imply it: plane A's word is camY (asserted separately), so the
AND reduces to "plane B's bits COVER the foreground's" — satisfied by any superset, which a
deform sample near $7FF supplies for free. That blind spot was measured and closed on
2026-09-18; the POISON section below carries both the measurement and the closure. Neither
question is a pinned number: both sides of both are read out of the SAME frame of the SAME
running machine, so they re-derive at whatever camera position the run happens to reach.

WHY THIS AND NOT PIXELS. Reading the pixels back would put Oracle's renderer between the
subject and the verdict, and Oracle's model of this quirk carries a KNOWN interim
divergence (its partial-column extent is a flat 16 px where hardware and GPGX say
`hscroll & 15`; oracle's own `plane_vscroll` comment and its divergence ledger P4 both say
so). The VSRAM half of the rule has no such divergence: it is `vsram_word(38) &
vsram_word(39)` in Oracle and `vs[19] & (vs[19] >> 16)` in GPGX, character for character
the same arithmetic. Asserting the value the rule consumes is therefore a stricter test of
OUR code than asserting the pixels the rule produces.

It still reads the machine, not the source: the path it covers is producer -> column
buffer -> `Vscroll_Write` -> VSRAM, end to end. A fix that filled the buffer correctly and
never shipped it would be red here.

WHAT IT CANNOT SEE, stated because a gate that hides its blind spot is worse than none.
If the AND rule is wrong about real silicon, this gate is green while the screen is still
broken. There is exactly one controlled hardware test on that rule in the public record,
it is sixteen years old, and it was run on a PAL Model 2. See
docs/research/2026-08-29-vsram-column19-borrow.md §2. The pixel table this gate prints
alongside its verdict is a MEASUREMENT, not an assertion, for exactly that reason —
terrain makes left-edge occupancy noisy (the 2026-08-27 run found transient one-row
shortfalls at x=24 and x=32 that are terrain, not the defect), so encoding it as pass/fail
would be a tripwire with a false-red every time the camera stops somewhere awkward.

LOUD ON UNMEASURABLE. Every way this run can fail to reach its subject is a FAILURE, never
a zero and never a green: the scene cursor not landing where it was driven, reg $0B bit 2
clear at the sample point, the server serving a different ROM, a symbol that will not
resolve. Two of those manufactured a false negative on 2026-08-27 — the DEBUG warp clears
bit 2, and travelling re-applies the section's own scene while `Debug_Lab_Index` still
reads 10 — so the mode bit is re-read at every sample point and never inferred from the
cursor.

POISON (what must make it red). Delete the one instruction the borrow is:

    engine/level/parallax.emp, Parallax_Step5_Vscroll, end of the Step-5b fill:
        move.w  d1, Parallax_Vscroll_Column_Buf + VSCROLL_COL19_BG_OFF

Rebuild `DEBUG=1 ./build.sh` and re-run. Every sampled ACCEPT scene must fail, with either

    FAIL scene NN: the leftmost partial column will render at V-scroll $XXX, not $YYY

where `$YYY` is `(Camera_Y >> 16) & $7FF` and `$XXX` is the AND, or — when plane B's own word
happens to cover the foreground's bits and the AND comes out right anyway — with

    FAIL scene NN: ... column-pair 19's plane-B word is $XXX, not the foreground's
    V-scroll $YYY — the borrow's store did not land

which is the assertion added when that second case was measured; see CLOSED, below. The two
DECLINING scenes stay green, since the store this poison deletes is the one they skip. With
the borrow gone,
VSRAM[$4E] carries plane B's own scroll, and on all six shipped per-column scenes plane B
is vertically LOCKED (`v_factor: 15, v_offset: 0`), so that word is 0 or a small deform
sample — which makes the AND collapse to near zero while `expected` is the live camera Y.
Expect `and=$0000..$00xx` against a three-digit `expected`. The gate prints all four
numbers (`vsram4C`, `vsram4E`, `and`, `expected`) on the failing line so the poison's
signature is visible rather than inferred.

MEASURED 2026-09-18 (first run). "Every sampled scene must fail" was TOO STRONG, and the row
it was wrong about is the interesting one. The poison was built and run (`s4.debug.bin`
848043 B, crc32 e8308fe3): scenes 10, 12 and 15 failed exactly as written; 13 and 14
correctly stayed GREEN on the declining arm, since the store this poison deletes is the one
they already skip; and SCENE 11 PASSED. Plane B's own word read $07FA there, and
$07FA & $0090 == $0090. The AND rule passes on any plane-B word whose bits are a SUPERSET of
the foreground's, so a deform sample near $7FF launders a missing borrow. That was a blind
spot in the ACCEPT arm — camera-dependent, not an engine defect. The reading at the time was
"never conclude a borrow is present from one green accept row".

CLOSED 2026-09-18 (same day, second run), and the paragraph above is kept because deleting it
would leave the next reader to rediscover why the arm has two assertions. The accept arm now
asserts BOTH the AND (what the screen renders) and `VSRAM[$4E] == camY` directly (what the
store did), each with its own message; the AND alone reduces, given plane A's word already
checked equal to camY, to "plane B's bits cover the foreground's", which is not injective.
Re-run against the SAME poison ROM (848043 B, e8308fe3): scene 11 now FAILS with "the
borrow's store did not land ... vsram4E=$07FA", the laundering value printed on the failing
line, and all four accept scenes are red. A third refusal backs it up, so the closure does
not depend on the camera being lucky either: when Camera_Y masks INTO the interval plane B's
own words occupy in that frame (measured from column pairs 0..18 of the same VSRAM read, not
pinned), a missing store would leave pair 19 carrying a word indistinguishable from the
borrow, and the run says UNMEASURABLE instead of green. So "every sampled ACCEPT scene must
fail" is true now — at any camera Y, either as a FAIL or as a refusal, never as a pass.

The widening in that interval EARNED ITS KEEP on the very run that closed this, which is the
only reason to trust it: on scene 11 the nineteen sampled plane-B words spanned -4..20 raw,
and pair 19's own word was -6 — OUTSIDE the first nineteen, INSIDE the interval only because
it is widened by the largest column-to-column step observed. An unwidened min/max would have
called that camera Y measurable and been wrong about the one column it was extrapolating to.

TWO ARMS SINCE d-50 (2026-09-02), PICKED PER SCENE FROM THE ROM. The column-19 borrow is
per scene now, default on. This gate reads `Parallax_Current_Config`'s
`pcfg_v_deform_shift_bg` and branches on PCFG_VDS_DECLINE_BORROW, so it grades each scene
against the expectation that scene actually authored instead of against a list of indices
that would rot silently. A scene that KEEPS the borrow is graded exactly as before. A scene
that DECLINES it must show column-pair 19's plane-B word NOT carrying the foreground's
V-scroll, and the run refuses to grade at all when the camera sits where the two hypotheses
predict the same word. Registry 13 and 14 (Perspective_Subtle, Perspective) decline today;
10, 11, 12 and 15 do not.

THE ARM SELECTION SAMPLES A SETTLED FRAME, AND THAT IS WHY IT WORKS (2026-09-18). Between
d-50 and today the declining arm had executed ZERO times: every scene took the accept arm
and two of them (13, 14 — the two that DECLINE) were reported RED. Both halves were one
bug, and it was in the gate's clock, not in its rule. Every scene in the tree authors
`pcfg_transition == 0`, so `Parallax_StartTransition` takes its CAP_TRANSITIONS staging arm
— it writes `Parallax_Target_Config` and `Parallax_Transition_Frames = PARALLAX_TRANS_DEFAULT`
and DELIBERATELY LEAVES `Parallax_Current_Config` ALONE; `Parallax_Update` promotes Target
into Current only on the frame the counter reaches 0 (engine/level/parallax.emp:1784-1800).
`drive_cursor`'s `step_scene` advances 12 frames per step against a 16-frame transition, so
every step re-staged before the previous promoted and the raw cell still held the BOOT
section's binding — the read was 9 of 16 frames early, on all six scenes. See
docs/research/2026-09-18-parallax-current-config-identity.md.

So this gate now RUNS THE MACHINE UNTIL THE ENGINE HAS PROMOTED — `settle_transition()`
polls `Parallax_Transition_Frames` to 0 — and `check_scene` re-reads that counter at the
sample point and REFUSES to grade a frame where a transition is in flight. At
`Transition_Frames == 0` the raw `Parallax_Current_Config` cell IS the active config, by the
engine's own promotion, in both the CAP_TRANSITIONS and the cap-elided shape.

THE ALTERNATIVE, AND WHY NOT IT. `Parallax_Active_Config` (parallax.emp:1480) is the
engine's selector: `Frames != 0 -> Target, else Current`. The gate could have restated that
rule in Python and sampled mid-transition. Rejected for two reasons. (1) It would put a
SECOND COPY of an engine rule in a test — the exact shape of staleness the per-scene read
was introduced to avoid, and it would go stale GREEN. (2) It fixes only the arm, not the
subject: mid-transition the plane-B word this gate asserts on is a LERP between two scenes'
configs (`Parallax_Current_Vscroll_BG` easing toward the target), so the declining arm would
still be grading a half-crossfaded value against a steady-state expectation. Settling fixes
both with no restatement.

BOTH ARMS ARE NOW ATTESTED, each against a mutation it had to answer (2026-09-18,
s4.debug.bin 848075 B crc32 62238a15, one oracle-aether per run on its own socket):
  * clean tree — ACCEPT on 10/11/12/15 (cfg $13E14/$13E52/$13E90/$1414A, vds $00), DECLINING
    on 13/14 (cfg $13FCE/$1408C, vds $82/$80), GREEN 6 of 6, rc=0;
  * flip scene 13's authored bit (`perspective_scene_declined` -> `perspective_scene`, plus
    the matching expectation in games/sonic4/test/scene_equiv_proof.emp, which refuses the
    build otherwise): scene 13 MOVES to the accept arm (vds $02, plane-B word $0005 -> $0090)
    while 14 stays declining. The selection responds to the authored bit, per scene;
  * delete the `bmi .col19_borrow_declined` skip in Step 5b so the store runs on a declining
    scene: the declining arm's own FAIL branch fires on 13 AND 14 ("the store ran anyway",
    b19 == $090), accept scenes untouched, rc=1. The arm is not vacuously green.
  * delete the accept arm's own store (the POISON below, s4.debug.bin 848043 B crc32
    e8308fe3): BEFORE the direct assertion, 10/12/15 red and 11 GREEN on $07FA; AFTER it,
    10/11/12/15 all red, rc=1, with 13/14 still green on the declining arm and the clean tree
    back to GREEN 6 of 6 at crc32 62238a15. The accept arm is not vacuously green either, and
    it is no longer green on a laundering plane-B word.
  * the `bmi` mutation above RE-RUN under the replacement ambiguity guard (2026-09-18,
    s4.debug.bin 848075 B crc32 1f02fe01), because that guard is what the declining arm
    refuses on and it was rewritten in the same edit: 13 and 14 red on "the store ran anyway"
    (b19 == $090), 10/11/12/15 untouched and green, rc=1. Replacing the typed `<= 0x1F` with
    the measured interval did NOT make the declining arm stop discriminating.
Nothing in `./build.sh`'s lanes noticed any of these engine mutations — every tree built rc=0.

USAGE
    python3 tools/fg_left_edge_gate.py                       # all six per-column scenes
    python3 tools/fg_left_edge_gate.py --scenes 12           # one
    python3 tools/fg_left_edge_gate.py --travel 240          # hold RIGHT first (pixel table)
    python3 tools/fg_left_edge_gate.py --rom s4.debug.bin --settle 240

RUN IT FOREGROUND. It boots a headless emulator; oracle from a background agent deadlocks.
"""

# ---------------------------------------------------------------------------
# THE CURSOR THIS FILE DRIVES CHANGED SHAPE ON 2026-09-05, and the rename is the
# small half of it. `Debug_Scene_Index` became `Debug_Lab_Index` when the effects
# lab's three selection chords collapsed into ONE list walked by START+LEFT/RIGHT
# (games/sonic4/test/ojz_scroll_test.emp, Debug_LabCycleHotkey).
#
# THE SCENE INDICES DID NOT MOVE: rows 0..SCENE_CYCLE_COUNT-1 of the one list are
# the same twenty-one scenes in the same registry order, so every scene number in
# this file still names the same scene. What DID change is what lies past them:
# rows 21..27 install RASTER programs and rows 28..36 install whole per-section
# PRESETS. Stepping the cursor forward off the end of the scene block therefore
# has SIDE EFFECTS a scene walk never used to have, and wrapping round from the
# last scene to the first now walks through all sixteen of them.
#
# So stepping is DIRECTIONAL here now, and that is not a tidiness change: it is
# what keeps this gate's subject uncontaminated. `drive_cursor` presses RIGHT to
# go up and LEFT to go down, so a walk between two scene rows stays inside the
# scene block by construction and never installs a raster program or a preset on
# its way.
# ---------------------------------------------------------------------------
import argparse
import asyncio
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/, for suite_paths
from suite_paths import add_client_path  # noqa: E402
add_client_path()  # the Aether client, resolved from the suite root; loud if absent
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

from aether import BusClient  # noqa: E402
from aether_instance import AetherInstance  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pcfg_vds_offset() -> int:
    """Byte offset of `pcfg_v_deform_shift_bg` inside `parallax_config`, DERIVED from the
    struct declaration rather than typed. A field inserted ahead of it moves this read or
    stops the gate; it never slides silently."""
    import pathlib
    from left_col_mask_probe import struct_offsets
    layout = struct_offsets(pathlib.Path(REPO) / "engine" / "structs.emp", "parallax_config")
    return layout["pcfg_v_deform_shift_bg"][0]


def _decline_borrow_bit() -> int:
    """PCFG_VDS_DECLINE_BORROW out of the engine source. Loud when absent — a gate that
    guessed this bit would grade every scene against the wrong expectation."""
    import re as _re
    txt = open(os.path.join(REPO, "engine", "level", "parallax.emp"), encoding="utf-8").read()
    m = _re.search(r"^\s*pub\s+const\s+PCFG_VDS_DECLINE_BORROW\s*=\s*\$([0-9A-Fa-f]+)",
                   txt, _re.M)
    if not m:
        raise SystemExit("FAIL: cannot find `pub const PCFG_VDS_DECLINE_BORROW` in "
                         "engine/level/parallax.emp — the per-scene switch this gate reads "
                         "is not where it was, and a default would be a guess")
    return int(m.group(1), 16)


def _col_pairs() -> int:
    """VSCROLL_COL_PAIRS, re-derived the way the engine derives it: SCREEN_WIDTH / 16, out of
    engine/system/constants.emp. The gate used to type $4C for column-pair 19's plane-A word;
    that number is (pairs - 1) * 4 and it is an H40 fact, so it is computed here from the same
    constant the engine computes it from. Loud when absent — a guessed screen width would aim
    every VSRAM read in this file at the wrong column pair and still print numbers."""
    import re as _re
    txt = open(os.path.join(REPO, "engine", "system", "constants.emp"), encoding="utf-8").read()
    m = _re.search(r"^\s*pub\s+const\s+SCREEN_WIDTH\s*=\s*(\d+)", txt, _re.M)
    if not m:
        raise SystemExit("FAIL: cannot find `pub const SCREEN_WIDTH` in "
                         "engine/system/constants.emp — the column-pair count this gate aims "
                         "its VSRAM reads with is derived from it, and a default would be a guess")
    width = int(m.group(1))
    if width % 16:
        raise SystemExit(f"FAIL: SCREEN_WIDTH {width} is not a whole number of 16-px column "
                         f"pairs, so VSCROLL_COL_PAIRS is not an integer and this gate cannot "
                         f"say which VSRAM entry the leftmost partial column re-reads")
    return width // 16


def _signed11(word: int) -> int:
    """VSRAM words are 11 bits and the V-scroll they carry is SIGNED: a locked plane's small
    negative deform sample stores as $7FA, not as a large positive scroll. Every comparison in
    this file that asks 'is this value near zero' has to ask it on the signed axis, or $7FA
    reads as 2042 and lands nowhere near the 0..$1F it actually neighbours."""
    v = word & VSRAM_MASK
    return v - (VSRAM_MASK + 1) if v > (VSRAM_MASK >> 1) else v


def _planeb_family(vs: bytes, pairs: int):
    """The interval column-pair 19's plane-B word WOULD occupy if the borrow had not written it.

    MEASURED FROM THE SAME FRAME, not pinned. Step 5b's fill writes plane B's own base plus its
    deform sample into EVERY pair's second word; the borrow then overwrites exactly one of them,
    pair 19. So the other `pairs - 1` second words in this very VSRAM frame are a direct sample
    of the distribution pair 19's own word is drawn from — on whatever scene, at whatever camera
    Y, under whatever deform amplitude this run happens to be standing in. Nothing about the
    scene's authored amplitude is restated here, which is the point: a pinned bound (this file
    carried `expected <= 0x1F`) is a second copy of an engine fact and goes stale green.

    Returns (lo, hi, step) on the SIGNED axis, widened on each side by the largest
    column-to-column step observed. The widening is what makes this a bound on the TWENTIETH
    column rather than a description of the first nineteen: the deform is one wave sampled per
    column, so pair 19 sits one step from pair 18 and the largest step across the row bounds how
    far one step can carry. That is an assumption about the wave's slope and it is stated here
    rather than buried — a deform whose slope at column 19 exceeded every slope across columns
    0..18 could land outside this interval.
    """
    own = [_signed11((vs[i * 4 + 2] << 8) | vs[i * 4 + 3]) for i in range(pairs - 1)]
    if not own:
        raise SystemExit("FAIL: fewer than two column pairs — there is no plane-B sample to "
                         "bound column 19's own word against")
    step = max((abs(b - a) for a, b in zip(own, own[1:])), default=0)
    return min(own) - step, max(own) + step, step


def _trans_default() -> int:
    """PARALLAX_TRANS_DEFAULT out of the engine source. Used ONLY to bound the settle loop —
    the loop's condition is the machine's own `Parallax_Transition_Frames`, never a frame
    count typed here. Loud when absent: a guessed bound would turn "the engine never
    promoted" into "we gave up early", and the two deserve different verdicts."""
    import re as _re
    txt = open(os.path.join(REPO, "engine", "system", "constants.emp"), encoding="utf-8").read()
    m = _re.search(r"^\s*pub\s+const\s+PARALLAX_TRANS_DEFAULT\s*=\s*(\d+)", txt, _re.M)
    if not m:
        raise SystemExit("FAIL: cannot find `pub const PARALLAX_TRANS_DEFAULT` in "
                         "engine/system/constants.emp — the transition length this gate "
                         "bounds its settle against is not where it was")
    return int(m.group(1))

# The six scenes that attach SceneVDeform.Columns, i.e. the only ones that raise reg $0B
# bit 2 — Rocking_Slow/Rocking/Rocking_Fast and Perspective_Subtle/Perspective/_Dramatic.
# Indices into SCENES[]; the cycle order is the registry's own.
DEFAULT_SCENES = [10, 11, 12, 13, 14, 15]

# VSRAM is 11 bits wide on the write path (the VDP masks $07FF), so the comparison is over
# the bits the chip actually stores. Wider would fail on a value the hardware never kept;
# narrower would pass on a value it did.
VSRAM_MASK = 0x7FF

# VDP reg $0B (Mode Set 3), bit 2 = per-column V-scroll.
VDP_MODE3_OFF = 0x0B
VDP_MODE3_PERCOL = 0x04

# Corroborating pixel table only. Left edge = the fix; right edge = what it costs.
FG_COLS = [0, 8, 16, 24]
BG_COLS = [280, 288, 296, 304, 312]
ROW_RANGE = (96, 216, 8)


def _int(v):
    s = str(v)
    return int(s.removeprefix("0x"), 16) if s.lower().startswith("0x") else int(s, 16)


async def read_bus(client, *, symbol=None, addr=None, length=1):
    p = {"len": length}
    if symbol is not None:
        p["symbol"] = symbol
    else:
        p["addr"] = hex(addr)
    r = await client.call("emulator/read", p)
    return int(str(r["bytes"]).removeprefix("0x"), 16)


async def read_vsram(client, addr, length):
    r = await client.call("emulator/read", {"space": "vsram", "addr": hex(addr), "len": length})
    raw = str(r["bytes"]).removeprefix("0x")
    return bytes.fromhex(raw)


async def lookup(client, name):
    try:
        r = await client.call("emulator/lookup_symbol", {"name": name})
    except Exception as exc:  # noqa: BLE001 — an unresolvable symbol is unmeasurable, not zero
        raise SystemExit(f"UNMEASURABLE: symbol {name!r} did not resolve ({exc}). The gate cannot "
                         f"locate its subject; refusing to report a verdict") from exc
    return _int(r["addr"])


async def step_scene(client):
    """One forward step of the effects-lab cursor: START held, RIGHT pressed on one frame.

    The hotkey is edge-triggered on the direction and gated on START being HELD, so the
    step needs a frame with both and at least one frame with START alone for the next
    edge to exist. Held-only frames on either side keep the chord unambiguous.
    """
    await client.call("emulator/play_input", {
        "rows": [
            {"start": 0, "end": 2, "buttons": ["start"]},
            {"start": 2, "end": 3, "buttons": ["start", "right"]},
            {"start": 3, "end": 8, "buttons": ["start"]},
        ],
        "maxFrames": 8,
    })
    await client.call("emulator/release_all", {})
    await client.call("emulator/run_frames", {"frames": 4})


async def step_scene_back(client):
    """One BACKWARD step of the effects-lab cursor: START held, LEFT pressed on one frame.

    The mirror of `step_scene`, and load-bearing since the one-list consolidation — see
    the note at the head of this file. It used to live only in
    tools/left_edge_vsram_probe.py; it is here now because every caller needs it.
    """
    await client.call("emulator/play_input", {
        "rows": [
            {"start": 0, "end": 2, "buttons": ["start"]},
            {"start": 2, "end": 3, "buttons": ["start", "left"]},
            {"start": 3, "end": 8, "buttons": ["start"]},
        ],
        "maxFrames": 8,
    })
    await client.call("emulator/release_all", {})
    await client.call("emulator/run_frames", {"frames": 4})


async def drive_cursor(client, addr, index, limit=40):
    """Step the lab cursor to `index`, in the SHORTER direction, and return where it ended.

    Raises SystemExit rather than returning a wrong answer on either unmeasurable
    condition: a press that does not move the cursor (wrong shape, or replaying input),
    and a walk that runs out of steps.

    DIRECTIONAL BY CONSTRUCTION — see the note at the head of this file. Between two
    SCENE rows this never leaves the scene block, so it cannot install a raster program
    or a preset as a side effect of getting where it is going.
    """
    for _ in range(limit):
        at = await read_bus(client, addr=addr, length=1)
        if at == index:
            return at
        before = at
        if at < index:
            await step_scene(client)
        else:
            await step_scene_back(client)
        after = await read_bus(client, addr=addr, length=1)
        if after == before:
            raise SystemExit(
                f"UNMEASURABLE: the effects-lab cursor did not move from {before} "
                f"(START+{'RIGHT' if before < index else 'LEFT'} produced no step). The "
                f"hotkey needs a DEBUG shape and live input (Input_Source == 0); gating "
                f"on a shape that has no lab cycle would report green having tested "
                f"nothing")
    raise SystemExit(
        f"UNMEASURABLE: could not drive the effects-lab cursor to {index} in {limit} steps")


async def settle_transition(client, syms):
    """Run frames until the engine has PROMOTED the staged config, and say how long it took.

    `drive_cursor` returns the instant the cursor cell reads the wanted index, which is
    mid-transition: the lab's install stages Target + Transition_Frames and leaves Current
    alone (see the banner). Nothing downstream of here is allowed to read Current until the
    engine itself has promoted it, so this waits for the engine to say so.

    The condition is the machine's `Parallax_Transition_Frames`, read one frame at a time.
    The BOUND comes from PARALLAX_TRANS_DEFAULT, derived from the engine source: one staged
    transition can need at most that many frames, and the allowance below is two of them, so
    running out means the counter is not behaving like a transition at all. That is
    UNMEASURABLE, never a silent continue — grading the raw cell mid-transition is precisely
    the defect this function exists to end.
    """
    budget = 2 * _trans_default()
    for waited in range(budget + 1):
        frames = await read_bus(client, addr=syms["Parallax_Transition_Frames"], length=1)
        if frames == 0:
            return waited
        await client.call("emulator/run_frames", {"frames": 1})
    raise SystemExit(
        f"UNMEASURABLE: Parallax_Transition_Frames never reached 0 in {budget} frames "
        f"(2 x PARALLAX_TRANS_DEFAULT, derived from engine/system/constants.emp). The "
        f"transition staged by the lab install is not completing, so Parallax_Current_Config "
        f"is not the active config and every arm this run would pick is picked from the "
        f"wrong record")


async def sample_plane(client, layer, cols, rows):
    out = {}
    for y in rows:
        for x in cols:
            r = await client.call("emulator/pixel_attribution", {"x": x, "y": y})
            c = next((c for c in r["candidates"] if c["layer"] == layer), None)
            out[(x, y)] = None if c is None else bool(c["opaque"])
    return out


def render(title, grid, cols, rows):
    print(f"      {title}   (# opaque, . transparent, ? candidate absent)")
    print("        " + "".join(f"x={x:<5}" for x in cols))
    for y in rows:
        cells = "".join(
            f"{('#' if grid[(x, y)] is True else ('.' if grid[(x, y)] is False else '?')):<7}"
            for x in cols
        )
        print(f"        y={y:<4}" + cells)


async def check_scene(client, syms, index, want_pixels):
    """Return (ok, message). Every unmeasurable condition returns ok=False."""
    cursor = await read_bus(client, addr=syms["Debug_Lab_Index"], length=1)
    if cursor != index:
        return False, (f"UNMEASURABLE scene {index}: the effects-lab cursor reads {cursor} after "
                       f"being driven to {index}. The scene was never installed, so nothing here "
                       f"measures the subject")

    mode3 = await read_bus(client, addr=syms["VDP_Shadow_Table"] + VDP_MODE3_OFF, length=1)
    if not mode3 & VDP_MODE3_PERCOL:
        return False, (f"UNMEASURABLE scene {index}: VDP reg $0B reads ${mode3:02X} — bit 2 "
                       f"(per-column V-scroll) is CLEAR at the sample point, so the leftmost "
                       f"partial column quirk cannot occur and this run proves nothing. Never "
                       f"trust the scene cursor: the DEBUG warp clears bit 2 and travelling "
                       f"re-applies the section's own scene")

    # WHICH WORD IS WHOSE (2026-09-18, added with the direct assertion below). Step 5b aims
    # the borrow at VSCROLL_COL19_FG_OFF instead of _BG_OFF when `Parallax_Roles_Swapped` is
    # set, because the camera-tracked plane then presents through reg $02. This file's word
    # roles — a19 is the foreground's, b19 is the borrow's target — are the UNSWAPPED ones,
    # and they are the only ones either arm has ever been attested against. Under a swap both
    # arms would grade the wrong word and print confident numbers doing it, so the run says so
    # instead. It is read at the sample point for the same reason reg $0B is: nothing here may
    # be inferred from the cursor.
    swapped = await read_bus(client, addr=syms["Parallax_Roles_Swapped"], length=1)
    if swapped:
        return False, (f"UNMEASURABLE scene {index}: Parallax_Roles_Swapped reads ${swapped:02X} "
                       f"at the sample point, so Step 5b aims the column-19 borrow at the FIRST "
                       f"word of the pair (VSCROLL_COL19_FG_OFF) and the plane roles this gate "
                       f"asserts on are inverted. Neither arm is attested under a role swap; "
                       f"refusing to grade rather than grade the wrong word")

    cam_y_raw = await read_bus(client, addr=syms["Camera_Y"], length=4)
    cam_y = (cam_y_raw >> 16) & 0xFFFF            # Camera_Y is 16.16; the engine swaps for pixels
    expected = cam_y & VSRAM_MASK

    # THE WHOLE COLUMN-PAIR TABLE, not just pair 19, and the offset is DERIVED (2026-09-18).
    # $4C was typed here; it is (VSCROLL_COL_PAIRS - 1) * 4 and the engine derives it from
    # SCREEN_WIDTH, so this does too. The other pairs are read because they ARE the control:
    # see _planeb_family.
    pairs = _col_pairs()
    col19 = (pairs - 1) * 4                       # $4C on H40 — column-pair 19's first word
    vs = await read_vsram(client, 0x00, pairs * 4)
    if len(vs) != pairs * 4:
        return False, (f"UNMEASURABLE scene {index}: asked the machine for {pairs * 4} bytes of "
                       f"VSRAM and got {len(vs)}. The column-pair table this gate grades is not "
                       f"all there, so the words it would read are not the words it names")
    a19 = (vs[col19] << 8) | vs[col19 + 1]        # column-pair 19, plane A (reg $02's word)
    b19 = (vs[col19 + 2] << 8) | vs[col19 + 3]    # column-pair 19, plane B (reg $04's word)
    and_val = (a19 & b19) & VSRAM_MASK
    fam_lo, fam_hi, fam_step = _planeb_family(vs, pairs)
    # Can plane B's OWN word at pair 19 be mistaken for the foreground's V-scroll? If it can,
    # "the borrow stored camY here" and "this is plane B's own word" predict the SAME VSRAM and
    # neither arm's assertion discriminates. Both arms refuse on it, loudly, rather than take
    # the luck: the accept arm would green on a missing borrow, the declining arm on a store
    # that ran. Signed, because $7FA is -6 and neighbours zero.
    indistinguishable = fam_lo <= _signed11(expected) <= fam_hi

    # WHICH EXPECTATION THIS SCENE IS OWED (d-50, 2026-09-02). The borrow is per scene now,
    # so the gate reads the ACTIVE CONFIG rather than carrying a list of which scenes decline
    # — a list would go stale the first time an author changes one, and it would go stale
    # green. Both the field offset and the flag bit come from the engine source above.
    #
    # RE-READ AT THE SAMPLE POINT, never inferred from the settle (2026-09-18), for the same
    # reason reg $0B above is re-read and not trusted: `settle_transition` ran BEFORE this
    # sample, and a transition staged since would put the active config in Target while
    # `Parallax_Current_Config` still names the outgoing scene. Grading that frame is exactly
    # what made this gate red on the two scenes that were working. At Frames == 0 the raw
    # cell IS the active config — that is Parallax_Active_Config's own else-arm — so this is
    # a precondition check, not a restatement of the selector.
    trans = await read_bus(client, addr=syms["Parallax_Transition_Frames"], length=1)
    if trans:
        target = await read_bus(client, addr=syms["Parallax_Target_Config"], length=4)
        return False, (f"UNMEASURABLE scene {index}: a parallax transition is in flight at the "
                       f"sample point (Parallax_Transition_Frames={trans}, "
                       f"Target=${target:06X}), so Parallax_Current_Config still names the "
                       f"OUTGOING scene and both the borrow policy and the plane-B word would "
                       f"be read mid-crossfade. Refusing to grade a config the engine has not "
                       f"promoted")
    cfg = await read_bus(client, addr=syms["Parallax_Current_Config"], length=4)
    if not cfg:
        return False, (f"UNMEASURABLE scene {index}: Parallax_Current_Config is NULL at the "
                       f"sample point, so no scene is installed and the per-scene borrow "
                       f"policy cannot be read")
    vds = await read_bus(client, addr=cfg + _pcfg_vds_offset(), length=1)
    declined = bool(vds & _decline_borrow_bit())

    detail = (f"vsram4C=${a19:04X} vsram4E=${b19:04X} and=${and_val:03X} "
              f"expected=${expected:03X} (Camera_Y={cam_y}, reg$0B=${mode3:02X}, "
              f"cfg=${cfg:06X} vds=${vds:02X} borrow={'DECLINED' if declined else 'ON'}, "
              f"planeB own words over pairs 0..{pairs - 2} span [{fam_lo},{fam_hi}] signed "
              f"incl. a {fam_step} max step)")

    if declined:
        # THE DECLINING ARM. The store is skipped, so column-pair 19's plane-B word must still
        # be plane B's own — which on every per-column scene in this tree is a LOCKED plane
        # (v_factor 15, v_offset 0) plus a small signed deform sample, i.e. near zero, while
        # `expected` is the live camera Y. Asserting `b19 != expected` is therefore a real
        # discriminator: put the store back and b19 becomes camY exactly.
        #
        # LOUD ON UNMEASURABLE rather than lucky: when the camera happens to sit where camY
        # masks to a value the deform could also produce, the two hypotheses are
        # indistinguishable and this run proves nothing. It says so instead of passing.
        # The bound was `expected <= 0x1F`, typed. It is MEASURED now (_planeb_family), for
        # two reasons: a typed bound is a second copy of "plane B is locked plus a small
        # deform" and goes stale green the day a scene authors a bigger amplitude; and the
        # typed one was one-sided, blind to the fact that these words are SIGNED — plane B's
        # own word reads $07FA on scene 11, six below zero, and a camera at Y 2042 would have
        # masked to exactly that and sailed past a `<= 0x1F` test.
        if indistinguishable:
            return False, (f"UNMEASURABLE scene {index}: Camera_Y masks to ${expected:03X} "
                           f"({_signed11(expected)} signed), inside the interval plane B's own "
                           f"locked-plus-deform word occupies in this very frame, so 'the store "
                           f"was skipped' and 'the store happened' predict the same VSRAM. "
                           f"Re-run at a different camera Y. {detail}")
        if (b19 & VSRAM_MASK) == expected:
            return False, (f"FAIL scene {index}: this scene DECLINES the column-19 borrow "
                           f"(pcfg_v_deform_shift_bg=${vds:02X}), but column-pair 19's plane-B "
                           f"word is the foreground's V-scroll ${expected:03X} — the store ran "
                           f"anyway. {detail}")
        return True, (f"ok   scene {index}: borrow DECLINED and skipped; column-pair 19 keeps "
                      f"plane B's own word. {detail}")

    if (a19 & VSRAM_MASK) != expected:
        return False, (f"FAIL scene {index}: column-pair 19's PLANE-A word is not the foreground's "
                       f"V-scroll — the column buffer's FG words disagree with Camera_Y, so the "
                       f"borrow has nothing correct to borrow. {detail}")
    # TWO ASSERTIONS, AND THEY ARE DIFFERENT STATEMENTS (2026-09-18). The first is about the
    # SCREEN: the AND is the value the VDP actually consumes at the leftmost partial column, so
    # a tree that fails it renders wrong whatever the cause. The second is about OUR CODE: the
    # borrow's whole job is to put camY in pair 19's plane-B word, and that word carrying camY
    # is the thing the store either did or did not do.
    #
    # The screen statement alone was NOT ENOUGH, and that is why the second exists. Given plane
    # A's word already equals camY (checked above), `(a19 & b19) == expected` reduces to "b19's
    # bits are a SUPERSET of expected's" — which is not injective. Measured 2026-09-18: with the
    # store deleted, scene 11's plane B carried its own $07FA and $07FA & $0090 == $0090, so the
    # arm reported the borrow present on a tree that had none. Scenes 10/12/15 went red at the
    # same camera Y; scene 11 was laundered by one deform sample. `b19 == expected` is injective
    # where the AND is not, and it is what makes the poison red on EVERY accept scene.
    if and_val != expected:
        return False, (f"FAIL scene {index}: the leftmost partial column will render at V-scroll "
                       f"${and_val:03X}, not ${expected:03X}. VSRAM[$4C] & VSRAM[$4E] is what the "
                       f"VDP uses there (H40, hardware-tested), and it does not equal the "
                       f"foreground's V-scroll. {detail}")
    if (b19 & VSRAM_MASK) != expected:
        return False, (f"FAIL scene {index}: this scene ACCEPTS the column-19 borrow "
                       f"(pcfg_v_deform_shift_bg=${vds:02X}), but column-pair 19's plane-B word "
                       f"is ${b19 & VSRAM_MASK:03X}, not the foreground's V-scroll "
                       f"${expected:03X} — the borrow's store did not land. The AND above came "
                       f"out right anyway because ${b19 & VSRAM_MASK:03X}'s bits happen to cover "
                       f"${expected:03X}'s; that is laundering, not a borrow. {detail}")

    # REFUSED LAST HERE, FIRST IN THE DECLINING ARM, and the asymmetry is deliberate. Both
    # assertions above are definite findings when they fail — the screen IS wrong, the store did
    # NOT land — and a definite red beats "cannot tell", so ambiguity is only consulted on the
    # path that would otherwise return green. The declining arm's one assertion is the opposite
    # shape: `b19 == expected` there is a FAILURE, and under ambiguity it would convict a scene
    # for a coincidence, so it has to be refused before it is made.
    if indistinguishable:
        return False, (f"UNMEASURABLE scene {index}: everything here looks like a landed borrow, "
                       f"but Camera_Y masks to ${expected:03X} ({_signed11(expected)} signed), "
                       f"inside the interval plane B's own locked-plus-deform word occupies in "
                       f"this very frame — so a MISSING store would have left pair 19 carrying a "
                       f"word this run could not tell from the borrow. Proving nothing is not "
                       f"passing. Re-run at a different camera Y. {detail}")

    msg = f"ok   scene {index}: leftmost partial column renders the foreground's V-scroll. {detail}"
    if want_pixels:
        rows = list(range(ROW_RANGE[0], ROW_RANGE[1] + 1, ROW_RANGE[2]))
        fg = await sample_plane(client, "planeA", FG_COLS, rows)
        bg = await sample_plane(client, "planeB", BG_COLS, rows)
        print(f"  {msg}")
        print("      --- MEASUREMENT ONLY, not asserted (terrain makes edge occupancy noisy) ---")
        render("plane A, LEFT edge — what the borrow fixes", fg, FG_COLS, rows)
        render("plane B, RIGHT edge — what the borrow costs (col 19 now carries the FG's V-scroll)",
               bg, BG_COLS, rows)
        return True, None
    return True, msg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=os.path.join(REPO, "s4.debug.bin"))
    ap.add_argument("--symbols", default=None)
    ap.add_argument("--settle", type=int, default=240)
    ap.add_argument("--travel", type=int, default=0,
                    help="frames to hold RIGHT before sampling (moves the camera off the boot "
                         "position; only affects the pixel table, never the assertion)")
    ap.add_argument("--scenes", default=",".join(str(s) for s in DEFAULT_SCENES))
    ap.add_argument("--pixels", action="store_true",
                    help="also print the plane-A/plane-B edge occupancy tables")
    args = ap.parse_args()

    rom = os.path.abspath(args.rom)
    symbols = args.symbols or (rom[:-4] + ".lst")
    scenes = sorted(int(s) for s in args.scenes.split(",") if s.strip())

    with open(rom, "rb") as fh:
        blob = fh.read()
    print(f"ROM   {rom}")
    print(f"      {len(blob)} bytes, crc32 {zlib.crc32(blob) & 0xFFFFFFFF:08x}")
    print(f"      scenes {scenes}")

    inst = AetherInstance(rom, symbols=symbols)
    sock = inst.start()
    failures = []

    async def body():
        c = BusClient(sock)
        await c.connect()
        st = await c.call("emulator/status", {})
        if st["romBytes"] != len(blob):
            raise SystemExit(f"UNMEASURABLE: server serves {st['romBytes']} bytes, {rom} is "
                             f"{len(blob)} — refusing to gate a different ROM")
        print(f"      server romPath={st['romPath']} romBytes={st['romBytes']} (matches)")

        syms = {}
        # `Parallax_Current_Config` is read by check_scene() and was NOT in this tuple.
        # Chain 197's rewrite added the read and not the name, so every run died with
        # KeyError before reaching a single scene — which is why this gate's declining arm
        # had never executed once. The failure looked like "nobody ran it"; it was
        # "it could not run". Those two leave the same evidence: no result.
        # If you add a syms[...] read to check_scene(), add its name HERE in the same edit.
        for name in ("Debug_Lab_Index", "Camera_Y", "VDP_Shadow_Table",
                     "Parallax_Current_Config", "Parallax_Target_Config",
                     "Parallax_Transition_Frames", "Parallax_Roles_Swapped"):
            syms[name] = await lookup(c, name)

        await c.call("emulator/run_frames", {"frames": args.settle})
        if args.travel:
            await c.call("emulator/play_input",
                         {"rows": [{"start": 0, "end": args.travel, "buttons": ["right"]}],
                          "maxFrames": args.travel})
            await c.call("emulator/release_all", {})
            await c.call("emulator/run_frames", {"frames": 30})

        for index in scenes:
            at = await drive_cursor(c, syms["Debug_Lab_Index"], index)
            waited = await settle_transition(c, syms)
            print(f"      scene {index}: cursor at {at}, settled after {waited} frame(s) "
                  f"(Parallax_Transition_Frames == 0)")
            ok, msg = await check_scene(c, syms, index, args.pixels)
            if msg:
                print(f"  {msg}")
            if not ok:
                failures.append(index)

    try:
        asyncio.run(body())
    finally:
        inst.reap()

    print()
    if failures:
        print(f"RED   {len(failures)} of {len(scenes)} scenes failed: {failures}")
        return 1
    print(f"GREEN {len(scenes)} of {len(scenes)} scenes: the leftmost partial column renders the "
          f"foreground's V-scroll")
    return 0


if __name__ == "__main__":
    sys.exit(main())
