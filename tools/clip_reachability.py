#!/usr/bin/env python3
"""clip_reachability.py — is the baked act PLAYABLE, not just internally consistent?

S2-COMPRESSED-ACT parcel 7. THE GAP THIS CLOSES, stated as the incident that opened it
(2026-09-17, owner's firsthand emulator run on `s4.s2clip.bin`):

  `verify_level_bin.py`'s ten lanes were GREEN. `clip_rom_bake.py ground` was GREEN.
  The ROM still looked like the world ended a third of the way through the clip.

Both of those gates answer "are the bytes self-consistent" — every block decodes to the
block its strips define, every .zx0 round-trips, the spawn has a floor under it. Neither
of them answers the question a player asks, which is "can I be everywhere in this act
without the act swallowing me". A single column with no floor is a bottomless pit, and
the acts this engine builds are 6,144 px tall while the painted band of a Sonic 2 clip is
1,024 — so a fall that does not terminate inside the painted band does not terminate at
all. Nothing measured that. This does.

WHAT IT CHECKS, per 8-px world column of the WHOLE ACT — not of the clip's destination
rectangle, which is the subject this gate started with and had to be corrected off. A
clip act is baked into a BIGGER act's slot, so the rectangle is complete while the act
around it is not, and the boundary that swallows the player is at the rectangle's EDGE.
See scan() for the measurement and check() for the two-sided declaration rule:

  1. ART. Some tile in that column is non-zero. An all-zero column is a column the
     player walks into and sees nothing.
  2. A FLOOR, ON EVERY REACHABLE COLLISION PLANE. A cell that is SOLID_TOP with a
     positive height in the sensor's own column of the 16-byte profile — the same
     arithmetic `probe_core` uses (games/sonic4/player/player_sensors.emp) and the same
     one clip_rom_bake.ground re-derives, applied to every column instead of one.
  3. THAT A FALL CAN END — whether there is air below the column's LAST landing surface.
     (2) is a claim about the TOP of a column and says nothing to a player already below
     it. This third check is the one the first version of this gate did not have, and its
     absence is what let the x = 4,096 edge be published as the whole story.

WHAT "REACHABLE" MEANS, AND WHY THE GATE IS SHAPED THIS WAY. The engine has two
collision planes and the querying object's `layer` byte selects between them
(engine/level/collision_lookup.emp: "0 = path A, 1 = path B"). `layer` is cleared at
player init (player_common.emp `clr.b layer(a0)`) and the ONLY thing that writes it is
Player_LoopCrossover, which fires off the interned CrossoverTable. So plane B is
reachable exactly when that table marks at least one attr byte. The table is read here,
never assumed — an act whose table is all zero is checked on plane A alone, and the SAME
run turns the plane-B holes from INFORMATIONAL into failures the moment a crossover is
marked. That is deliberate: it is the difference between a gate that would have caught
this act and a gate that refuses faithful donor data for a hazard it cannot reach.

WHY PLANE B MATTERS AT ALL, since it is unreachable today. Every act that has ever run
on this engine had plane B as a byte-for-byte COPY of plane A — `tools/ojz_block_gen.py`
says so in an assertion (`test_extract_block`: "OJZ: plane B must be a copy of plane A").
A Sonic 2 clip act is the FIRST content where the two planes differ, because Sonic 2's
chunk words carry two independent solidity nibbles and the converter splits them. So the
clip act is also the first content on which a wrong `layer` byte is fatal rather than a
no-op, and the plane-B holes this prints are the map of where it would be fatal.
Measured on s2_ehz_boot: plane A has a floor in all 512 columns; plane B has none at all
in x 1344..1407, which is EHZ's own jump-the-pit (Sonic 2 puts a row of five rings over it
at y 568, x 1392..1488) seen from the path the player is not on.

LOUD WHEN IT CANNOT MEASURE. A missing strip file, a strip of the wrong shape, a
constant that moved, an unreadable crossover table: exit 2, never a pass.

  python3 tools/clip_reachability.py check games/sonic4/data/clips/<id>/clips.json
"""

import argparse
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
GEN_DIR = os.path.join(REPO, "games", "sonic4", "data", "generated", "ojz", "act1")
COLL_DIR = os.path.join(REPO, "games", "sonic4", "data", "collision")
STRIP_GEN_SRC = os.path.join(REPO, "tools", "ojz_strip_gen.py")
CONSTANTS_EMP = os.path.join(REPO, "engine", "system", "constants.emp")

PLANE_NAMES = {0: "A", 1: "B"}


class Unmeasurable(Exception):
    """The gate could not ask its question. Exit 2 — never a pass."""


# ---------------------------------------------------------------------------
# Everything below is DERIVED. Nothing here restates a number another file owns.
# ---------------------------------------------------------------------------

def strip_gen_int(name, src=STRIP_GEN_SRC):
    """A plain-integer constant out of ojz_strip_gen.py's SOURCE.

    Parsed, not imported, for verify_level_bin's reason: ojz_strip_gen pulls in the
    donor-facing modules at import time and this gate must run on a checkout with no
    donor tree. A constant that moved or went non-literal is UNMEASURABLE.
    """
    if not os.path.isfile(src):
        raise Unmeasurable(f"{src} is missing — the strip layout is its to define and "
                           f"this gate cannot invent it")
    m = re.search(rf"^{name}\s*=\s*(\d+)\b", open(src).read(), re.M)
    if not m:
        raise Unmeasurable(f"ojz_strip_gen.py no longer defines {name} as a plain "
                           f"integer — the strip layout moved and this gate is reading "
                           f"a shape that no longer exists; re-derive it")
    return int(m.group(1))


def engine_const(name, path=CONSTANTS_EMP):
    from fg_working_set import ConstantSource
    src = ConstantSource()
    src.load_file(path)
    try:
        return int(src.get(name))
    except Exception as exc:                        # noqa: BLE001 — reported, not swallowed
        raise Unmeasurable(f"engine constant {name} could not be read from {path} "
                           f"({exc})") from exc


class StripGeometry:
    """The one place the 776-byte strip record is decomposed, derived from the generator."""

    def __init__(self, gen_dir, grid_w, section_px):
        self.gen_dir = gen_dir
        self.grid_w = grid_w
        self.section_px = section_px
        self.tile_rows = strip_gen_int("STRIP_TILE_HEIGHT")
        self.pad = strip_gen_int("STRIP_COLLISION_PAD")
        self.coll_rows = self.tile_rows // 2
        self.nt_bytes = self.tile_rows * 2
        self.stride = self.nt_bytes + 2 * self.coll_rows + self.pad
        self.section_tiles = self.section_px // 8
        if self.section_tiles != self.tile_rows:
            raise Unmeasurable(
                f"a section is {self.section_px} px = {self.section_tiles} tiles across "
                f"but a strip record holds {self.tile_rows} nametable rows; this gate "
                f"decomposes a strip file as one record per tile column of a SQUARE "
                f"section and cannot read a non-square one")
        self._cache = {}

    def _strip(self, n):
        if n not in self._cache:
            p = os.path.join(self.gen_dir, f"sec{n}_strips_a.bin")
            if not os.path.isfile(p):
                raise Unmeasurable(f"{p} is missing — there is no emitted strip for "
                                   f"section {n}, so its columns cannot be measured")
            d = open(p, "rb").read()
            want = self.tile_rows * self.stride
            if len(d) != want:
                raise Unmeasurable(f"{p} is {len(d)} B; a {self.tile_rows}-column "
                                   f"section at {self.stride} B per column is {want} B")
            self._cache[n] = d
        return self._cache[n]

    def _where(self, wx, wy):
        sx, lx = divmod(wx // 8, self.section_tiles)
        sy, ly = divmod(wy // 8, self.section_tiles)
        return sy * self.grid_w + sx, lx, ly

    def attr(self, wx, wy, plane):
        n, lx, ly = self._where(wx, wy)
        d = self._strip(n)
        off = self.stride * lx + self.nt_bytes + plane * self.coll_rows + (ly // 2)
        return d[off]

    def tile(self, wx, wy):
        n, lx, ly = self._where(wx, wy)
        d = self._strip(n)
        return struct.unpack_from(">H", d, self.stride * lx + ly * 2)[0] & 0x07FF


def reachable_planes(coll_dir):
    """(planes, why) — which collision planes a player can query in this act.

    Plane A always. Plane B exactly when the interned CrossoverTable marks something,
    because Player_LoopCrossover is the only writer of the player's `layer` byte and it
    fires off that table. READ, never assumed.
    """
    p = os.path.join(coll_dir, "crossover.bin")
    if not os.path.isfile(p):
        raise Unmeasurable(f"{p} is missing — plane B's reachability is decided by the "
                           f"interned CrossoverTable and this gate will not guess it")
    table = open(p, "rb").read()
    if not table:
        raise Unmeasurable(f"{p} is empty — it cannot say whether any attr byte is a "
                           f"crossover")
    marked = [i for i, b in enumerate(table) if b]
    if marked:
        return (0, 1), (f"CrossoverTable marks {len(marked)} attr byte(s) "
                        f"(first: {marked[0]}), so Player_LoopCrossover can move the "
                        f"player's layer onto plane B")
    return (0,), ("CrossoverTable marks no attr byte, so nothing writes the player's "
                  "layer and plane B is unreachable in this act")


# ---------------------------------------------------------------------------
# The measurement
# ---------------------------------------------------------------------------

def _runs(xs, step):
    out = []
    for x in xs:
        if out and x == out[-1][1] + step:
            out[-1][1] = x
        else:
            out.append([x, x])
    return [(a, b + step) for a, b in out]


def scan(manifest_path, donor_root=None, gen_dir=GEN_DIR, coll_dir=COLL_DIR, log=print):
    """Measure every 8-px column of the WHOLE ACT — not just the clip's rectangle.

    THE RECTANGLE IS THE WRONG SUBJECT, and finding that out is what this parcel cost.
    A clip act is baked into the SHIPPED act's slot at the SHIPPED act's grid (R21,
    clip_rom_bake.check_act_grid_matches_engine), because the descriptor's GRID_W/GRID_H
    are hand-written and shared with the canonical ROM. s2_ehz_boot therefore paints
    4,096 x 1,024 px of a 6,144 x 6,144 px act, and the remaining sections are baked as
    air — 0 of 256 non-empty blocks, content-deduped to one 1,024-byte blob. At x = 4,096
    the art and BOTH collision planes stop dead, top to bottom, and the camera's
    EDGE_CLAMP clamps the CAMERA to the act rather than the player to the clip. So the
    player walks off the end of the painted world into 2,048 px of void and falls 5,120
    px with nothing to land on.

    That boundary is REAL and it is in the bytes. Checking only the clip rectangle would
    certify it as perfect, which is exactly what every gate before this one did.
    """
    import act_grid
    import clip_manifest
    import clip_rom_bake

    act = clip_manifest.load(manifest_path, donor_root=clip_manifest._root(donor_root))
    # BEFORE anything is measured. A generated tree that is the shipped act, or a
    # different clip act, would answer this gate's questions with somebody else's bytes
    # and pass — which is the shape of the bug this whole parcel is about.
    try:
        clip_rom_bake.require_stamp(act.id, gen_dir, "clip_reachability")
    except clip_rom_bake.ClipRomError as exc:
        raise Unmeasurable(str(exc)) from exc
    grid_w, grid_h = act_grid.descriptor_grid()
    section_px = act.section_px
    geo = StripGeometry(gen_dir, grid_w, section_px)
    act_h = grid_h * section_px
    act_w = grid_w * section_px

    solid_top = engine_const("SOLID_TOP")
    cell_h = engine_const("COLL_CELL_H")
    cell_w = engine_const("COLL_CELL_W")
    try:
        solidity = open(os.path.join(coll_dir, "solidity.bin"), "rb").read()
        heights = open(os.path.join(coll_dir, "heightmaps.bin"), "rb").read()
    except OSError as exc:
        raise Unmeasurable(f"the emitted collision tables could not be read ({exc}) — "
                           f"a floor is a SOLID_TOP attr with a positive height and "
                           f"neither can be decided without them") from exc
    if len(solidity) < 256 or len(heights) < 256 * 16:
        raise Unmeasurable(f"solidity.bin is {len(solidity)} B and heightmaps.bin is "
                           f"{len(heights)} B; a 256-entry attr set needs 256 and 4096")

    planes, why = reachable_planes(coll_dir)
    if log:
        log(f"clip_reachability: reachable planes {[PLANE_NAMES[p] for p in planes]} — {why}")

    def floor_y(wx, plane):
        """The topmost landing surface in this column, the way probe_core finds one."""
        col = wx & (cell_h - 1)          # the sensor's column inside the 16-byte profile
        for y in range(0, act_h, cell_h):
            a = geo.attr(wx, y, plane)
            if a and (solidity[a] & solid_top):
                h = heights[a * cell_h + col]
                sh = h - 256 if h > 127 else h
                if sh > 0:
                    return y + cell_h - sh
        return None

    # THE SECOND MEASUREMENT, and the one the first version of this gate was missing
    # (added 2026-09-17 after the coordinator refused the first account — he was right).
    #
    # "Every column has a landing surface" is a claim about the TOP of a column, and a
    # player already BELOW a column's last landing surface is not helped by it. Sonic 2's
    # terrain interiors are LRB-only ($2000 — solid left/right/bottom and NOTHING to a
    # falling body), and Sonic 2 survives that with a LEVEL BOTTOM BOUNDARY that kills and
    # restarts a player who gets under the world. EHZ act 1 declares its own at y = 800
    # (s2_donor.level_size). A clip act declares none: it inherits a 6,144 px act with
    # nothing painted below 1,024. So a fall that is a death-and-restart in the donor game
    # is an ENDLESS fall here, and that — not the x = 4,096 edge — is what a walking
    # player meets first.
    def last_landing_row(wx, plane=0):
        col = wx & (cell_h - 1)
        last = -1
        for y in range(0, act_h, cell_h):
            a = geo.attr(wx, y, plane)
            if a and (solidity[a] & solid_top):
                h = heights[a * cell_h + col]
                sh = h - 256 if h > 127 else h
                if sh > 0:
                    last = y
        return last

    no_art, no_floor = [], {p: [] for p in (0, 1)}
    unbounded = []
    for wx in range(0, act_w, cell_w):
        if not any(geo.tile(wx, wy) for wy in range(0, act_h, 8)):
            no_art.append(wx)
        for plane in (0, 1):
            if floor_y(wx, plane) is None:
                no_floor[plane].append(wx)
        last = last_landing_row(wx)
        if last >= 0 and any(geo.attr(wx, y, 0) == 0
                             for y in range(last + cell_h, act_h, cell_h)):
            unbounded.append(wx)

    return {"act": act.id, "planes": planes, "why": why, "cell_w": cell_w,
            "unbounded": unbounded,
            "act_w": act_w, "act_h": act_h,
            "grid": [grid_w, grid_h], "section_px": section_px,
            "clip_rects": {c.id: list(c.dst) for c in act.clips},
            "declared": act.raw.get("unpainted_remainder"),
            "no_art": no_art, "no_floor": no_floor}


def _declared_bound(declared, key, act_extent, axis):
    """The declared first unpainted world coordinate on one axis, validated."""
    if key not in declared:
        raise Unmeasurable(
            f'manifest "unpainted_remainder" has no "{key}" — the declaration must name '
            f'the first unpainted world {axis} so the gate can check it against what the '
            f'bytes actually do. Write {key}: <int>, or {act_extent} to mean "nothing is '
            f'unpainted on this axis".')
    v = declared[key]
    if not isinstance(v, int) or isinstance(v, bool) or not (0 <= v <= act_extent):
        raise Unmeasurable(
            f'manifest "unpainted_remainder"."{key}" = {v!r} is not an integer in '
            f"0..{act_extent} (the act's {axis} extent)")
    return v


def check(manifest_path, donor_root=None, gen_dir=GEN_DIR, coll_dir=COLL_DIR, log=print):
    """0 = the act has no undeclared void, 1 = it has one. Unmeasurable -> exit 2.

    THE CHECK IS TWO-SIDED, deliberately. A clip act baked into a bigger act's slot HAS
    an unpainted remainder and cannot not have one; pretending otherwise would just make
    the gate un-passable. So the manifest DECLARES where the painted world ends and this
    measures whether the bytes agree — in BOTH directions:

      * a void that starts EARLIER than declared is the incident this gate exists for:
        content is missing and the world ends before its author thinks it does;
      * a void that starts LATER (or is absent) means the declaration went stale, which
        is how a gate quietly stops asking anything.

    A clip act with NO declaration at all and a real void FAILS, by name, with the
    numbers. That is the state s2_ehz_boot shipped in.
    """
    r = scan(manifest_path, donor_root=donor_root, gen_dir=gen_dir, coll_dir=coll_dir,
             log=log)
    step, act_w = r["cell_w"], r["act_w"]
    cols = act_w // step
    failures = []
    if log:
        gw, gh = r["grid"]
        log(f"clip_reachability: act {r['act']} — grid {gw}x{gh} at {r['section_px']} px "
            f"= {act_w}x{r['act_h']} px world, {cols} columns of {step} px")
        for cid, rect in r["clip_rects"].items():
            log(f"  clip {cid} paints dst (x={rect[0]}, y={rect[1]}, w={rect[2]}, "
                f"h={rect[3]})")
        # The VERTICAL remainder is reported, never checked: this gate measures columns,
        # so it can say where the painted world ENDS in x but not where each column's
        # band ends in y. Said out loud because a fall leaves through the bottom too, and
        # a number a gate prints but does not test must say so beside itself.
        band = max((rect[1] + rect[3]) for rect in r["clip_rects"].values())
        log(f"  vertical remainder (REPORTED, NOT CHECKED): the clips paint down to "
            f"y={band} of {r['act_h']} — {r['act_h'] - band} px of the act below that is "
            f"air that only a fall can reach")

    # The measured edge of the painted world: the first column with no art, if the
    # columns from there on are ALL artless (a trailing remainder). A hole in the middle
    # is not a remainder and is reported as a hole.
    no_art = set(r["no_art"])
    trailing_from = act_w
    for wx in range(act_w - step, -step, -step):
        if wx in no_art:
            trailing_from = wx
        else:
            break
    interior_no_art = sorted(x for x in no_art if x < trailing_from)

    declared = r["declared"]
    if declared is None:
        if interior_no_art or trailing_from < act_w:
            failures.append(
                f"the act has {len(no_art)} artless column(s) and the manifest declares "
                f"no `unpainted_remainder`. The painted world ends at x={trailing_from} "
                f"and the act runs to x={act_w}: past that edge there is no art and no "
                f"collision on either plane, top to bottom, so the player walks off the "
                f"end of the world and falls {r['act_h']} px with nothing to land on. "
                f"A clip act baked into a bigger act's slot ALWAYS has this remainder — "
                f"declare it: "
                f'"unpainted_remainder": {{"x_from": {trailing_from}, '
                f'"why": "<why this act does not paint it>"}}')
    elif not isinstance(declared, dict):
        raise Unmeasurable('manifest "unpainted_remainder" is not an object')
    else:
        want_x = _declared_bound(declared, "x_from", act_w, "x")
        if "why" not in declared or not str(declared.get("why", "")).strip():
            failures.append(
                'the `unpainted_remainder` declaration has no "why". A void the build '
                'accepts needs the reason written next to it, or the next reader cannot '
                'tell a deliberate edge from this parcel\'s bug')
        if trailing_from != want_x:
            failures.append(
                f"the painted world ends at x={trailing_from} but the manifest declares "
                f"x_from={want_x}. "
                + (f"CONTENT IS MISSING: {want_x - trailing_from} px of the act that the "
                   f"declaration says is painted carries no art and no collision."
                   if trailing_from < want_x else
                   f"THE DECLARATION IS STALE: it reserves {trailing_from - want_x} px "
                   f"that the act actually paints, so this gate has stopped asking about "
                   f"them."))
        elif log:
            log(f"  painted world ends at x={trailing_from}, exactly as declared "
                f"(why: {declared.get('why')})")

    if interior_no_art:
        failures.append(
            f"{len(interior_no_art)} column(s) INSIDE the painted world carry no art at "
            f"all — x runs {_runs(interior_no_art, step)}. That is a hole, not an edge")
    elif log:
        log(f"  art: all {trailing_from // step} painted columns carry at least one tile")

    for plane in (0, 1):
        name = PLANE_NAMES[plane]
        holes = [x for x in r["no_floor"][plane] if x < trailing_from]
        if plane in r["planes"]:
            if holes:
                failures.append(
                    f"plane {name} has NO landing surface in {len(holes)} column(s) of "
                    f"the painted world — x runs {_runs(holes, step)}. The act is "
                    f"{r['act_h']} px tall, so a fall in those columns does not "
                    f"terminate: the player leaves the world and never comes back")
            elif log:
                log(f"  plane {name}: a landing surface in every painted column "
                    f"(REACHABLE — checked)")
        elif log:
            if holes:
                log(f"  plane {name}: NO landing surface in {len(holes)} painted "
                    f"column(s) — x runs {_runs(holes, step)}. INFORMATIONAL, NOT A "
                    f"PASS: plane {name} is unreachable in this act ({r['why']}), so "
                    f"nothing can fall into them TODAY. Mark one crossover attr byte and "
                    f"this same run turns red.")
            else:
                log(f"  plane {name}: a landing surface in every painted column "
                    f"(unreachable in this act, reported anyway)")

    # -- THE UNBOUNDED FALL -------------------------------------------------------
    # Declared and two-sided, like the remainder above. The COUNT is the thing that moves:
    # add a floor, a death plane or a bottom boundary and it drops; lose one and it rises.
    # Either way this stops agreeing with the manifest and the build says so.
    # `donor_bottom_boundary` records the y at which the DONOR GAME kills a player who gets
    # under its world — the whole reason the same geometry is survivable there and fatal
    # here — and is derived (s2_donor.level_size), never typed into the tool.
    unbounded = [x for x in r["unbounded"] if x < trailing_from]
    decl = r["declared"] or {}
    want = decl.get("unbounded_fall") if isinstance(decl, dict) else None
    if unbounded and want is None:
        shown = _runs(unbounded, step)
        failures.append(
            f"{len(unbounded)} of {trailing_from // step} painted columns have AIR below "
            f"their LAST landing surface — x runs {shown[:6]}"
            + ("..." if len(shown) > 6 else "") + ". A body below that surface has no "
            f"floor anywhere in the {r['act_h']} px act and falls forever. Sonic 2's "
            f"terrain interiors are LRB-only and stop nothing falling; the donor game "
            f"survives that with a LEVEL BOTTOM BOUNDARY that kills and restarts, and this "
            f"act has none. Declare it inside `unpainted_remainder`: "
            f'"unbounded_fall": {{"columns": {len(unbounded)}, '
            f'"donor_bottom_boundary": <the donor level\'s own bottom y>, '
            f'"why": "<why this act ships without a bottom boundary>"}}')
    elif want is not None:
        if not isinstance(want, dict) or "columns" not in want:
            raise Unmeasurable('"unbounded_fall" must be an object with a "columns" count')
        if want["columns"] != len(unbounded):
            failures.append(
                f"the manifest declares {want['columns']} unbounded-fall column(s) and the "
                f"bytes have {len(unbounded)}. "
                + ("MORE of the act now swallows a falling body than was declared."
                   if len(unbounded) > want["columns"] else
                   "FEWER — something gained a floor, which is good news the declaration "
                   "has not caught up with. Re-derive it."))
        elif log:
            log(f"  unbounded fall: {len(unbounded)} column(s), exactly as declared "
                f"(the donor game's own bottom boundary: "
                f"y={want.get('donor_bottom_boundary')}; this act has none)")

    if failures:
        for f in failures:
            print(f"clip_reachability: FAIL — {f}", file=sys.stderr)
        return 1
    if log:
        log("clip_reachability: OK — the painted world ends where the manifest says it "
            "does, every column inside it carries art and a landing surface on every "
            "reachable plane, and the unbounded-fall volume is the declared one")
    return 0


# ---------------------------------------------------------------------------
# CLI — a MODES table dispatched before any handler runs (tools/test_cli_dispatch.py)
# ---------------------------------------------------------------------------

def _mode_check(rest):
    ap = argparse.ArgumentParser(prog="clip_reachability.py check")
    ap.add_argument("manifest")
    ap.add_argument("--donor-root", default=None)
    ap.add_argument("--gen-dir", default=GEN_DIR)
    ap.add_argument("--coll-dir", default=COLL_DIR)
    a = ap.parse_args(rest)
    return check(a.manifest, donor_root=a.donor_root, gen_dir=a.gen_dir,
                 coll_dir=a.coll_dir)


MODES = {"check": _mode_check}


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    handler = MODES.get(args[0] if args else None)
    if handler is None:
        print(f"usage: clip_reachability.py {{{'|'.join(MODES)}}} <clips.json> [options]")
        raise SystemExit(1)
    try:
        raise SystemExit(handler(args[1:]))
    except Unmeasurable as exc:
        print(f"clip_reachability: COULD NOT MEASURE — {exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
