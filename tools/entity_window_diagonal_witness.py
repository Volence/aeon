#!/usr/bin/env python3
"""entity_window_diagonal_witness — force a TWO-AXIS entity-window slide and check the window.

WHY IT EXISTS (SAH-3, STRESSART-ENTITY-AXIS, 2026-09-26). On the STRESS_ART DEBUG shape at
STRESS_ART_N 2200 and 1400 the fly-diagonal leg halted at camera (4608,4480) on the DEBUG
assert in EntityWindow_Slide that said "at most one anchor byte changes per slide (16px/f
camera clamp)". The clamp bounds each axis's STEP, not how many axes cross a section line on
one tick: (4608 - ENTITY_DESPAWN_BUFFER) and (4480 - ENTITY_DESPAWN_BUFFER_Y) are both
2 * SECTION_SIZE, so that tick moved both anchor bytes. Whether it happens depends on the x/y
phase of the flight, which is why it came and went with the stress art. Nobody had asked
whether only the assert was wrong or the window also mishandles the crossing. This tool asks
the WINDOW, on a crossing it forces deterministically instead of waiting for the phase.

HOW THE CROSSING IS FORCED. Boot the DEBUG shape (debug free flight), then for each arm:
  1. warp (the DEBUG warp mailbox, games/sonic4/test/ojz_scroll_test.emp Debug_Warp_Consume,
     which re-runs EntityWindow_Init) so the camera sits ONE pixel short of the anchor line on
     each axis the arm crosses (Camera_X = 2048k + ENTITY_DESPAWN_BUFFER - 1 going right, = the
     line itself going left, the same on Y with ENTITY_DESPAWN_BUFFER_Y);
  2. SETTLE_TICKS ticks at rest, checked every tick;
  3. move the leader by LEADER_KICK px on each crossing axis. That is past every deadzone
     (X: Camera_Deadzone_Base 16, Y: CAM_Y_DEADZONE 32), so the next Camera_Update steps the
     capped CAM_MAX_*_STEP = 16 px on each axis and the tick's EntityWindow_Scan sees both
     anchor bytes change. The crossing is MEASURED, not assumed: an arm whose kick tick did
     not move exactly the anchor bytes it names is UNMEASURABLE;
  4. FOLLOW_TICKS ticks of debug flight in the arm's direction (16 px per tick), checked
     every tick, long enough to carry the load band across a whole entered row/column.
A 16 px step on both axes is a legal camera motion, so the forced tick is one real play can
produce (docs/DEFERRED_WORK.md SAH-3 has the reachability argument).

WHAT IS CHECKED, EVERY TICK, at the entry of the Section_UpdateColumns call that follows
EntityWindow_Scan in the level update (nothing between them touches the camera or the window).
Every expectation is derived here from the camera and the ROM's own section lists, NOT read
back from the window:
  W  the window: Entity_Window_Anchor, the four entries' section ids, origins and the
     Entity_Window_Active mask equal what the camera envelope says they must be
     (sec0 = max(0, (Camera - DESPAWN_BUFFER) >> SECTION_SIZE_SHIFT), 2x2, void off-grid);
     and every valid entry's section owns a collected/killed slot (Ring_Collected_Window).
  M  loaded masks: an entry's ring bit is set exactly when that ring is in Ring_Buffer, its
     object bit exactly when that object is live (tagged, same section and list index).
  U  unloaded: no live window object belongs to an untracked section; no ring of an untracked
     section sits outside the X despawn window; nothing (ANY_Y objects excepted) sits outside
     the Y despawn band; no (section, index) is live twice.
  L  loaded: every ring and object of a tracked section that is not collected/killed, whose
     engine X is at or left of the right load edge, and whose engine Y is inside the band every
     offer since the current 128 px coarse row began has covered, [c - 129, c + 480] for
     c = Camera_Y & ENTITY_RESCAN_COARSE_MASK (ANY_Y objects: any Y), is live. Derivation in
     `guaranteed_band`. A full Ring_Buffer or a full dynamic list makes L unmeasurable that
     tick (said so), never a pass.
Non-vacuity, per arm: the kick tick moved exactly the anchor bytes the arm names; and at
least one entity of a section the crossing DROPPED was live before the kick (so U's "gone
after" had a subject) or at least one entity of a section it ENTERED was checked live by L
during the follow (so W/M/L watched a new section fill). Both counts are printed per arm.
The shipped act is 3x3 and sparse, so plan_arm picks each arm's line pair by those counts
rather than by a fixed position; void (off-grid) quadrants are allowed and checked (W).

A HALT (the loop stops: Section_UpdateColumns not reached within HALT_FRAMES frames) is a
FAIL, and the raise_error message is recovered and printed.

Exit: 0 every arm checked clean and met its non-vacuity preconditions; 1 an arm FAILED (a
check broke or the game halted); 2 UNMEASURABLE / COULD NOT RUN.

Usage (spawns its own headless emulator; nothing needs to be running):
  DEBUG=1 ./build.sh
  python3 tools/entity_window_diagonal_witness.py [--rom s4.debug.bin] [--lst s4.debug.lst]
Wired: tools/keepalive_manifest.toml (the nightly instrument keepalive lane), s4.debug.bin.
"""
import argparse
import asyncio
import re
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import add_client_path  # noqa: E402
add_client_path()  # the Aether client, resolved from the suite root; loud if absent
from aether import BusClient  # noqa: E402
from aether_instance import AetherInstance, SpawnError, read_bytes  # noqa: E402
from cart_identity import CartMismatch  # noqa: E402
from stressart_legs_witness import raise_message, listing_labels, nearest_label  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CONSTS = REPO / "engine" / "system" / "constants.emp"
EW = REPO / "engine" / "objects" / "entity_window.emp"
SST = REPO / "engine" / "objects" / "sst.emp"
CAMERA = REPO / "engine" / "level" / "camera.emp"
PLAYER = REPO / "games" / "sonic4" / "player" / "player_common.emp"


class Unmeasurable(Exception):
    pass


def const(name, src=CONSTS):
    """`[pub ]const NAME = <int>` (decimal or $hex) from engine source; loud if absent."""
    m = re.search(rf"^(?:pub )?const {name}\s*=\s*(\$[0-9A-Fa-f]+|\d+)\b", src.read_text(), re.M)
    if not m:
        raise Unmeasurable(f"`const {name} = <int>` not found in {src}")
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


def field(struct_src, name):
    """`name: type @ $XX` offset from an `@`-annotated struct (EntityScanState, Sst)."""
    m = re.search(rf"^\s*{name}:\s*[^@\n]+@\s*\$([0-9A-Fa-f]+)", struct_src.read_text(), re.M)
    if not m:
        raise Unmeasurable(f"field `{name}: ... @ $..` not found in {struct_src}")
    return int(m.group(1), 16)


# ---- derived constants (source is the authority; nothing restated) ----
SHIFT = const("SECTION_SIZE_SHIFT")
SECTION = const("SECTION_SIZE")
DESPAWN_X = const("ENTITY_DESPAWN_BUFFER")
DESPAWN_Y = const("ENTITY_DESPAWN_BUFFER_Y")
LOAD_X = const("ENTITY_LOAD_BUFFER")
LOAD_Y = const("ENTITY_LOAD_BUFFER_Y")
SCREEN_W = const("SCREEN_WIDTH")
SCREEN_H = const("SCREEN_HEIGHT")
HALF_W = const("CAM_SCREEN_HALF_W")
HALF_H = const("CAM_SCREEN_HALF_H")
COARSE_MASK = const("ENTITY_RESCAN_COARSE_MASK")
ROW = 0x10000 - COARSE_MASK
TRACKED = const("MAX_TRACKED_SECTIONS")
LOADED_SLOT = const("ENTITY_LOADED_SLOT_SIZE")
LOADED_OBJ = const("ENTITY_LOADED_OBJ_OFFSET")
COLL_OFF = const("COLLECTED_BITMASK_OFFSET")
KILL_OFF = const("KILLED_BITMASK_OFFSET")
EMPTY_TAG = const("COLLECTED_EMPTY_TAG")
SEC_VOID = const("SEC_VOID")
RING_ENTRY = 6            # RING_BUFFER_ENTRY_SIZE: derived in constants.emp, checked below
OBJ_ENTRY = const("OBJ_ENTRY_SIZE")
TAG_NONE = 0xFF           # TagRef.none, the carved niche (engine/system/types.emp)
SEC_SIZE = 22             # sizeof(Sec): engine/structs.emp pins it with an ensure
ESS_SIZE = 0x1A           # EntityScanState (size: $1A), declared in entity_window.emp
ESS_ID = field(EW, "ess_section_id")
ESS_OX = field(EW, "ess_origin_x")
ESS_OY = field(EW, "ess_origin_y")
SST_Y = field(SST, "y_pos")
SST_TAG = field(SST, "slot_tag")
SST_SEC = field(SST, "entity_section_id")
SST_IDX = field(SST, "entity_list_index")
CAM_X_STEP = const("CAM_MAX_X_STEP", CAMERA)
CAM_Y_STEP = const("CAM_MAX_Y_STEP")
DEAD_X = const("CAM_X_DEADZONE_INIT", CAMERA)
DEAD_Y = const("CAM_Y_DEADZONE", CAMERA)
FLY = const("PLAYER_DEBUG_FLY_SPEED", PLAYER)
# The kick: past the deadzone plus one full capped step on every axis, so the camera takes
# exactly CAM_MAX_*_STEP on the kick tick whichever side the deadzone sits on.
LEADER_KICK = max(DEAD_X, DEAD_Y) + max(CAM_X_STEP, CAM_Y_STEP)
if "RING_BUFFER_ENTRY_SIZE = RING_ENTRY_LIST_INDEX_OFFSET + 1" not in CONSTS.read_text() \
        or const("RING_ENTRY_SECTION_ID_OFFSET") != 4:
    raise SystemExit("COULD NOT RUN: the ring-buffer entry layout moved (dc.w x, y; dc.b "
                     "section, index); re-derive RING_ENTRY")

BOOT_FRAMES = 300         # the stress witness's settle: DEBUG boot is in free flight by then
SETTLE_TICKS = 4
# X: the right load edge must reach the corner column. Going right the kick lands the camera
# 15 px past the line, the corner column starts SECTION - DESPAWN_X further right, and the load
# edge leads the camera by SCREEN_W + LOAD_X. Y: the band's far edge (SCREEN_H + LOAD_Y below)
# must reach the corner row, SECTION - DESPAWN_Y below the line. The larger, over FLY px/tick,
# plus a coarse row of margin.
FOLLOW_TICKS = (max(SECTION - DESPAWN_X - SCREEN_W - LOAD_X,
                    SECTION - DESPAWN_Y - SCREEN_H - LOAD_Y) + ROW) // FLY + SETTLE_TICKS
HALT_FRAMES = 60


def guaranteed_band(cam_y):
    """The Y range every live-making offer has covered since the current coarse row began.

    RescanY fires on the first tick in coarse row c = cam_y & COARSE_MASK, at some camera
    y' in [c, c + ROW - 1], and offers everything under the X ratchet against the load band
    [y' - LOAD_Y, y' + SCREEN_H + LOAD_Y]. Every later offer in the row (the X scan, a slide's
    populate or fresh object walk) uses a camera in the same row. The intersection over
    y' in [c, c + ROW - 1] is [c + ROW - 1 - LOAD_Y, c + SCREEN_H + LOAD_Y], and the Y despawn
    band (DESPAWN_Y > LOAD_Y) never removes anything inside it while the camera stays in the
    row. So an entity in it that is under the ratchet and not collected/killed must be live."""
    c = cam_y & COARSE_MASK
    return c + ROW - 1 - LOAD_Y, c + SCREEN_H + LOAD_Y


class Act:
    """The act's section grid and every section's ring/object list, read from the ROM image."""

    def __init__(self, rom, act_ptr):
        self.rom = rom
        rd = lambda a, n: int.from_bytes(rom[a:a + n], "big")  # noqa: E731
        grid = rd(act_ptr, 4)
        self.w, self.h = rd(act_ptr + 4, 2), rd(act_ptr + 6, 2)
        self.live, self.rings, self.objs = {}, {}, {}
        for sid in range(self.w * self.h):
            sec = grid + sid * SEC_SIZE
            if rd(sec, 4) == 0:
                continue                           # void cell (Section_GetSecPtrXY's tst.l)
            self.live[sid] = True
            rp, op = rd(sec + 8, 4), rd(sec + 4, 4)
            rings = []
            while rp and rd(rp, 4) != 0:           # dc.l 0 terminator
                rings.append((rd(rp, 2), rd(rp + 2, 2)))
                rp += 4
            objs = []
            while op and not rd(op, 2) & 0x8000:   # dc.w -1 terminator (bmi)
                objs.append((rd(op, 2), rd(op + 2, 2), bool(rd(op + 4, 2) & 0x8000)))
                op += OBJ_ENTRY
            self.rings[sid], self.objs[sid] = rings, objs

    def sid(self, sx, sy):
        if 0 <= sx < self.w and 0 <= sy < self.h and (sy * self.w + sx) in self.live:
            return sy * self.w + sx
        return None

    def window(self, cam_x, cam_y):
        """(anchor, [(sid|None, origin_x, origin_y)] x TRACKED) the envelope demands."""
        ax = max(0, (cam_x - DESPAWN_X) >> SHIFT)
        ay = max(0, (cam_y - DESPAWN_Y) >> SHIFT)
        ents = []
        for e in range(TRACKED):
            sx, sy = ax + (e & 1), ay + (e >> 1)
            ents.append((self.sid(sx, sy), sx << SHIFT, sy << SHIFT))
        return (ax & 0xFF, ay & 0xFF), ents


class Machine:
    def __init__(self, b, s):
        self.b, self.s = b, s

    async def rd(self, addr, n):
        h = await read_bytes(self.b, addr & 0xFFFFFF, n)
        if len(h) != 2 * n:
            raise Unmeasurable(f"read_memory ${addr:06X} len {n} returned {len(h) // 2} byte(s)")
        return bytes.fromhex(h)

    async def u(self, name, n, off=0):
        return int.from_bytes(await self.rd(self.s[name] + off, n), "big")

    async def wr(self, addr, val, width):
        await self.b.call("emulator/write_memory", {"addr": hex(addr & 0xFFFFFF),
                                                    "value": val, "width": width})

    async def cam(self):
        return await self.u("Camera_X", 2), await self.u("Camera_Y", 2)

    async def tick(self):
        """Run to the next post-scan point. False = the loop halted (not reached)."""
        r = await self.b.call("emulator/run_to", {"addr": hex(self.s["Section_UpdateColumns"]),
                                                  "maxFrames": HALT_FRAMES})
        if not r.get("reached"):
            return False
        # step off the breakpoint address so the next run_to cannot return in place
        await self.b.call("emulator/step", {"count": 1})
        return True

    async def snapshot(self):
        s = self
        n_ring = await s.u("Ring_Count", 1)
        rb = await s.rd(s.s["Ring_Buffer"], n_ring * RING_ENTRY) if n_ring else b""
        rings = [(int.from_bytes(rb[i:i + 2], "big", signed=True),
                  int.from_bytes(rb[i + 2:i + 4], "big", signed=True), rb[i + 4], rb[i + 5])
                 for i in range(0, len(rb), RING_ENTRY)]
        n_live = await s.u("Dynamic_Live_Count", 2)
        lv = await s.rd(s.s["Dynamic_Live"], 2 * n_live) if n_live else b""
        objs = []
        for i in range(0, len(lv), 2):
            a = int.from_bytes(lv[i:i + 2], "big")
            if a == 0:
                continue
            sst = await s.rd(0xFF0000 | a, SST_IDX + 1)
            if int.from_bytes(sst[0:2], "big") == 0 or sst[SST_TAG] == TAG_NONE:
                continue                           # dead-uncompacted / not window-managed
            objs.append((int.from_bytes(sst[SST_Y:SST_Y + 2], "big", signed=True),
                         sst[SST_TAG], sst[SST_SEC], sst[SST_IDX]))
        ess = await s.rd(s.s["Entity_Scan_State"], TRACKED * ESS_SIZE)
        ents = [(ess[e * ESS_SIZE + ESS_ID],
                 int.from_bytes(ess[e * ESS_SIZE + ESS_OX:e * ESS_SIZE + ESS_OX + 2], "big",
                                signed=True),
                 int.from_bytes(ess[e * ESS_SIZE + ESS_OY:e * ESS_SIZE + ESS_OY + 2], "big",
                                signed=True)) for e in range(TRACKED)]
        coll = await s.rd(s.s["Ring_Collected_Window"], s.slots * s.slot_size)
        return {
            "cam": await s.cam(),
            "anchor": tuple(await s.rd(s.s["Entity_Window_Anchor"], 2)),
            "active": await s.u("Entity_Window_Active", 1),
            "ents": ents,
            "masks": await s.rd(s.s["Entity_Loaded_Masks"], TRACKED * LOADED_SLOT),
            "coll": {coll[k * s.slot_size]: coll[k * s.slot_size:(k + 1) * s.slot_size]
                     for k in range(s.slots) if coll[k * s.slot_size] != EMPTY_TAG},
            "rings": rings, "objs": objs, "n_live": n_live, "n_ring": n_ring,
        }


def bit(buf, base, idx):
    return bool(buf[base + (idx >> 3)] & (1 << (idx & 7)))


def check(act, snap, cap_ring, cap_live):
    """Violations of W/M/U/L for one tick, plus (live_keys, notes)."""
    bad, notes = [], []
    cx, cy = snap["cam"]
    anchor, want = act.window(cx, cy)
    # ---- W: the tracked set, derived from the camera ----
    if snap["anchor"] != anchor:
        bad.append(f"W anchor {snap['anchor']} != derived {anchor}")
    want_active = sum(1 << e for e, (sid, _, _) in enumerate(want) if sid is not None)
    if snap["active"] != want_active:
        bad.append(f"W Entity_Window_Active ${snap['active']:X} != derived ${want_active:X}")
    for e, ((sid, ox, oy), (gid, gox, goy)) in enumerate(zip(want, snap["ents"])):
        if sid is None:
            if gid != SEC_VOID:
                bad.append(f"W entry {e} holds section {gid}, derived void")
            continue
        if (gid, gox, goy) != (sid, ox, oy):
            bad.append(f"W entry {e} = (sec {gid}, {gox},{goy}), derived (sec {sid}, {ox},{oy})")
        if sid not in snap["coll"]:
            bad.append(f"W entry {e}: section {sid} owns no collected/killed slot")
    tracked = {sid: e for e, (sid, _, _) in enumerate(want) if sid is not None}
    # ---- U + M ----
    live_r, live_o = {}, {}
    for x, y, sec, idx in snap["rings"]:
        if (sec, idx) in live_r:
            bad.append(f"U ring (sec {sec}, #{idx}) live twice")
        live_r[(sec, idx)] = (x, y)
        if sec not in tracked and not (cx - DESPAWN_X <= x <= cx + SCREEN_W + DESPAWN_X):
            bad.append(f"U ring (sec {sec}, #{idx}) at x={x}: untracked section, outside the X window")
        if not (cy - DESPAWN_Y <= y <= cy + SCREEN_H + DESPAWN_Y):
            bad.append(f"U ring (sec {sec}, #{idx}) at y={y}: outside the Y despawn band")
    for y, tag, sec, idx in snap["objs"]:
        if (sec, idx) in live_o:
            bad.append(f"U object (sec {sec}, #{idx}) live twice")
        live_o[(sec, idx)] = tag
        if sec not in tracked:
            bad.append(f"U object (sec {sec}, #{idx}) live but its section is untracked")
        if not tag & 0x80 and not (cy - DESPAWN_Y <= y <= cy + SCREEN_H + DESPAWN_Y):
            bad.append(f"U object (sec {sec}, #{idx}) at y={y}: outside the Y despawn band")
    for sid, e in tracked.items():
        base = e * LOADED_SLOT
        for idx in range(len(act.rings[sid])):
            if bit(snap["masks"], base, idx) != ((sid, idx) in live_r):
                bad.append(f"M ring (sec {sid}, #{idx}): loaded bit {int(bit(snap['masks'], base, idx))}"
                           f" but {'live' if (sid, idx) in live_r else 'not live'}")
        for idx in range(len(act.objs[sid])):
            if bit(snap["masks"], base + LOADED_OBJ, idx) != ((sid, idx) in live_o):
                bad.append(f"M object (sec {sid}, #{idx}): loaded bit "
                           f"{int(bit(snap['masks'], base + LOADED_OBJ, idx))} but "
                           f"{'live' if (sid, idx) in live_o else 'not live'}")
    # ---- L ----
    lo, hi = guaranteed_band(cy)
    edge = cx + SCREEN_W + LOAD_X
    ring_full = snap["n_ring"] >= cap_ring
    live_full = snap["n_live"] >= cap_live
    if ring_full or live_full:
        notes.append(f"L unmeasurable this tick (ring buffer {snap['n_ring']}/{cap_ring}, "
                     f"dynamic {snap['n_live']}/{cap_live})")
    seen = set()
    for sid in tracked:
        _, ox, oy = want[tracked[sid]]
        slot = snap["coll"].get(sid)
        for idx, (lx, ly) in enumerate(act.rings[sid]):
            x, y = ox + lx, oy + ly
            if x > edge or not lo <= y <= hi:
                continue
            if slot is not None and bit(slot, COLL_OFF, idx):
                continue
            if (sid, idx) in live_r:
                seen.add(("r", sid, idx))
            elif not ring_full:
                bad.append(f"L ring (sec {sid}, #{idx}) at ({x},{y}) must be live and is not")
        for idx, (lx, ly, any_y) in enumerate(act.objs[sid]):
            x, y = ox + lx, oy + ly
            if x > edge or not (any_y or lo <= y <= hi):
                continue
            if slot is not None and bit(slot, KILL_OFF, idx):
                continue
            if (sid, idx) in live_o:
                seen.add(("o", sid, idx))
            elif not live_full:
                bad.append(f"L object (sec {sid}, #{idx}) at ({x},{y}) must be live and is not")
    live_keys = {("r",) + k for k in live_r} | {("o",) + k for k in live_o}
    return bad, notes, live_keys, seen


# Arms: (name, dx, dy, lines). dx/dy = the direction crossed (0 = that axis held
# mid-section); lines = (kx, ky) to pin the crossing, or None to let plan_arm pick it.
# The pinned arm replays the STRESS_ART halt: camera (4607,4479) -> (4623,4495) crosses
# kx = ky = 2 ((4608 - DESPAWN_X) and (4480 - DESPAWN_Y) are both 2 * SECTION_SIZE) into a
# window whose other three quadrants are off the grid (the shipped act is 3x3).
ARMS = (("diagonal right+down", 1, 1, None), ("diagonal left+down", -1, 1, None),
        ("diagonal right+up", 1, -1, None), ("diagonal left+up", -1, -1, None),
        ("diagonal right+down at the stress halt", 1, 1, (2, 2)),
        ("control right only", 1, 0, None), ("control down only", 0, 1, None))
BUTTONS = {1: "right", -1: "left"}, {1: "down", -1: "up"}


def live_able(act, sid, origin, cam):
    """Entities of section `sid` that L would demand live at camera `cam`, as a set (a static
    estimate, used only to choose a crossing that has something to check)."""
    (ox, oy), (cx, cy) = origin, cam
    lo, hi = guaranteed_band(cy)
    edge = cx + SCREEN_W + LOAD_X
    out = {("r", sid, i) for i, (lx, ly) in enumerate(act.rings[sid])
           if ox + lx <= edge and lo <= oy + ly <= hi}
    return out | {("o", sid, i) for i, (lx, ly, a) in enumerate(act.objs[sid])
                  if ox + lx <= edge and (a or lo <= oy + ly <= hi)}


def follow_path(q, dx, dy, xmax, ymax):
    """The follow's camera, sampled every tick (the camera keeps pace with the 16 px/tick
    flight once the kick has put the leader past the deadzone), clamped like the camera."""
    qx, qy = q
    return [(min(max(qx + dx * FLY * t, 0), xmax), min(max(qy + dy * FLY * t, 0), ymax))
            for t in range(FOLLOW_TICKS + 1)]


def neutral_camera(act, xmax, ymax):
    """A camera whose window tracks no section with a listed object, or None."""
    for cy in range(ymax, -1, -ROW):
        for cx in range(0, xmax + 1, ROW):
            _, win = act.window(cx, cy)
            if all(sid is None or not act.objs[sid] for sid, _, _ in win):
                return cx, cy
    return None


def plan_arm(act, dx, dy, xmax, ymax, lines=None):
    """Pick the crossing for an arm. Every line pair (kx, ky) whose pre- and post-kick cameras
    sit inside the camera clamp is a candidate; void (off-grid) quadrants are allowed, since
    the window must handle them too. Score: entities of the sections the crossing DROPS that
    are live-able before the kick (so U's "gone after" has a subject), and entities listed in
    the sections it ENTERS (so W/M/L watch new sections fill during the follow). Best minimum
    of the two wins, then best sum, ties to the smallest (kx, ky). `lines` pins the pair."""
    best = None
    # a held (0) axis is not a line: try its camera at every coarse row/column instead
    xs = [(k, None) for k in range(1, act.w + 1)] if dx else \
        [(0, v) for v in range(0, xmax + 1, ROW)]
    ys = [(k, None) for k in range(1, act.h + 1)] if dy else \
        [(0, v) for v in range(0, ymax + 1, ROW)]
    for kx, hx in xs:
        for ky, hy in ys:
            if lines and (kx, ky) != lines:
                continue
            # pre-kick camera: one px short of the line going +, on the line going -
            lx, ly = (kx << SHIFT) + DESPAWN_X, (ky << SHIFT) + DESPAWN_Y
            px = (lx - 1 if dx > 0 else lx) if dx else hx
            py = (ly - 1 if dy > 0 else ly) if dy else hy
            qx, qy = px + dx * CAM_X_STEP, py + dy * CAM_Y_STEP
            if not (0 <= px <= xmax and 0 <= py <= ymax and 0 <= qx <= xmax and 0 <= qy <= ymax):
                continue
            a0, pre = act.window(px, py)
            a1, post = act.window(qx, qy)
            pre_ids = {sid for sid, _, _ in pre if sid is not None}
            post_ids = {sid for sid, _, _ in post if sid is not None}
            dropped, entered = pre_ids - post_ids, post_ids - pre_ids
            org = {sid: (ox, oy) for sid, ox, oy in pre + post if sid is not None}
            d_n = sum(len(live_able(act, sid, org[sid], (px, py))) for sid in dropped)
            seen = set()
            for cam in follow_path((qx, qy), dx, dy, xmax, ymax):
                _, win = act.window(*cam)
                ids = {sid for sid, _, _ in win}
                for sid in entered & ids:
                    seen |= live_able(act, sid, org[sid], cam)
            e_n = len(seen)
            score = (min(d_n, e_n), d_n + e_n, -kx, -ky)
            if best is None or score > best[0]:
                best = (score, kx, ky, (px, py), (qx, qy), dropped, entered, a0, a1)
    return best


async def run_arm(m, act, name, dx, dy, lines, caps, labels, rom_image, verbose):
    s = m.s
    xmax, ymax = await m.u("Camera_X_Max", 2), await m.u("Camera_Y_Max", 2)
    plan = plan_arm(act, dx, dy, xmax, ymax, lines)
    if plan is None:
        raise Unmeasurable(f"{name}: no line pair {lines or ''} in the {act.w}x{act.h} grid "
                           f"puts both kick cameras inside the clamp ({xmax},{ymax})")
    _, kx, ky, (px, py), (qx, qy), dropped, entered, a0, a1 = plan
    print(f"  {name}: lines kx={kx} ky={ky}; camera ({px},{py}) -> ({qx},{qy}); anchor "
          f"{a0} -> {a1}; drops sections {sorted(dropped)}, enters {sorted(entered)}")
    # TWO HOPS, and the first is not optional. Debug_Warp_Consume re-runs EntityWindow_Init,
    # which clears every loaded bit but deletes no live object, so an object whose section
    # the destination window still tracks is spawned a second time (measured on d57002c5:
    # boot -> (2559,128) left section 0's objects #0-#5 live twice; docs/DEFERRED_WORK.md
    # SAH-3, the warp finding). That is the warp's defect, not the slide's, so the arm first
    # parks on a window with NO listed objects (every earlier object's section goes
    # untracked and despawns), then warps to the crossing.
    hop = neutral_camera(act, xmax, ymax)
    if hop is None:
        raise Unmeasurable(f"{name}: no camera in the act has a window with no listed objects "
                           f"to park on before the warp (see the TWO HOPS note)")
    for cam, what in ((hop, "park"), ((px, py), "warp")):
        # center_camera_on puts the camera at leader - HALF
        await m.wr(s["Warp_Req_X"], cam[0] + HALF_W, 2)
        await m.wr(s["Warp_Req_Y"], cam[1] + HALF_H, 2)
        await m.wr(s["Warp_Req_Flag"], 1, 1)
        for _ in range(8):
            if not await m.tick():
                return await halted(m, name, what, labels, rom_image)
            if await m.u("Warp_Req_Flag", 1) == 0:
                break
        else:
            raise Unmeasurable(f"{name}: the warp mailbox never acked ({what})")
        if what == "park":
            if not await m.tick():
                return await halted(m, name, what, labels, rom_image)
            left = (await m.snapshot())["objs"]
            if left:
                raise Unmeasurable(f"{name}: {len(left)} window object(s) still live after "
                                   f"parking at {hop}: {left[:4]}")
    fails, notes_all = [], []
    pre_live, entered_seen, ticks = set(), set(), 0

    async def one(phase):
        nonlocal ticks
        snap = await m.snapshot()
        bad, notes, live_keys, seen = check(act, snap, *caps)
        ticks += 1
        for n in notes:
            notes_all.append(f"{phase}: {n}")
        for v in bad:
            fails.append(f"{phase} cam {snap['cam']}: {v}")
        return snap, live_keys, seen

    for t in range(SETTLE_TICKS):
        if t and not await m.tick():
            return await halted(m, name, "settle", labels, rom_image)
        snap, live_keys, _ = await one(f"settle {t}")
    if snap["cam"] != (px, py):
        raise Unmeasurable(f"{name}: camera settled at {snap['cam']}, not ({px},{py}) (a warp "
                           f"clamp or a camera hold moved it)")
    pre_live = {k for k in live_keys if k[1] in dropped}
    anchor_pre = snap["anchor"]
    # the kick: move the leader past the deadzone on each crossing axis
    lead = await m.u("Camera_Target", 2)
    x_hi = int.from_bytes(await m.rd(0xFF0000 | (lead + 2), 2), "big")
    y_hi = int.from_bytes(await m.rd(0xFF0000 | (lead + 6), 2), "big")
    await m.wr(0xFF0000 | (lead + 2), (x_hi + dx * LEADER_KICK) & 0xFFFF, 2)
    await m.wr(0xFF0000 | (lead + 6), (y_hi + dy * LEADER_KICK) & 0xFFFF, 2)
    if not await m.tick():
        return await halted(m, name, "kick", labels, rom_image)
    snap, _, seen = await one("kick")
    moved = (snap["anchor"][0] != anchor_pre[0], snap["anchor"][1] != anchor_pre[1])
    if moved != (bool(dx), bool(dy)) or snap["cam"] != (qx, qy):
        raise Unmeasurable(f"{name}: the kick tick moved the camera to {snap['cam']} (planned "
                           f"({qx},{qy})) and the anchor {anchor_pre} -> {snap['anchor']}: "
                           f"not the crossing this arm names")
    gone = {k for k in pre_live}
    entered_seen |= {k for k in seen if k[1] in entered}
    # the follow: fly on in the arm's direction
    btn = [b for b in (BUTTONS[0].get(dx), BUTTONS[1].get(dy)) if b]
    await m.b.call("emulator/hold", {"buttons": btn, "down": True})
    for t in range(FOLLOW_TICKS):
        if not await m.tick():
            return await halted(m, name, f"follow {t}", labels, rom_image)
        snap, _, seen = await one(f"follow {t}")
        entered_seen |= {k for k in seen if k[1] in entered}
    await m.b.call("emulator/hold", {"buttons": btn, "down": False})
    print(f"    {ticks} ticks checked; {len(fails)} violation(s); camera ends {snap['cam']}; "
          f"dropped-section entities live before the kick: {len(gone)}; entered-section "
          f"entities checked live: {len(entered_seen)}")
    for n in sorted(set(notes_all))[:4]:
        print(f"    note: {n}")
    if fails:
        for f in fails[:12 if not verbose else len(fails)]:
            print(f"    FAIL {f}")
        if len(fails) > 12 and not verbose:
            print(f"    ... {len(fails) - 12} more (--verbose prints all)")
        return 1
    if not gone and not entered_seen:
        raise Unmeasurable(f"{name}: vacuous: nothing from a dropped section was live before "
                           f"the kick and nothing from an entered section was checked live")
    return 0


async def halted(m, name, where, labels, rom_image):
    st = await m.b.call("emulator/status", {})
    pc = int(str(st.get("pc", "0")), 16) & 0xFFFFFF
    print(f"    HALT: {name}, {where}: Section_UpdateColumns not reached in {HALT_FRAMES} "
          f"frames, camera {await m.cam()}, pc ${pc:06X} "
          f"({'in' if pc >= m.s['ErrorHandlerBlob'] else 'NOT in'} the fault island)")
    for site, msg in await raise_message(m.b, rom_image):
        print(f"      raise_error at ${site:06X} ({nearest_label(labels, site)}): {msg!r}")
    return 1


SYMS = ("Camera_X", "Camera_Y", "Camera_X_Max", "Camera_Y_Max", "Camera_Target",
        "Current_Act_Ptr", "Entity_Scan_State", "Entity_Window_Active", "Entity_Window_Anchor",
        "Entity_Loaded_Masks", "Ring_Buffer", "Ring_Count", "Ring_Collected_Window",
        "Ring_Collected_Park", "Dynamic_Live", "Dynamic_Live_Count", "Warp_Req_X",
        "Warp_Req_Y", "Warp_Req_Flag", "Section_UpdateColumns", "ErrorHandlerBlob")


async def sweep(sock, rom_image, labels, arms, verbose):
    b = BusClient(socket_path=sock, client_id="ewdiag", client_name="entity-window-diagonal")
    await b.connect()
    try:
        s = {}
        for n in SYMS:
            try:
                r = await b.call("emulator/lookup_symbol", {"name": n})
            except Exception as e:  # noqa: BLE001 - the bus raises its own error type
                raise Unmeasurable(f"symbol {n} not in the listing ({e})") from e
            s[n] = int(r["addr"], 16) & 0xFFFFFF
        m = Machine(b, s)
        # capacities from the RAM layout itself (engine/ram.emp: Ring_Count follows Ring_Buffer,
        # Dynamic_Live_Count follows Dynamic_Live; the park follows the window + 2 reserved)
        cap_ring = (s["Ring_Count"] - s["Ring_Buffer"]) // RING_ENTRY
        cap_live = (s["Dynamic_Live_Count"] - s["Dynamic_Live"]) // 2
        m.slot_size = KILL_OFF + (KILL_OFF - COLL_OFF)
        span = s["Ring_Collected_Park"] - s["Ring_Collected_Window"]
        m.slots = span // m.slot_size
        if span % m.slot_size not in (0, 2) or not 1 <= m.slots <= 9:
            raise Unmeasurable(f"Ring_Collected_Window spans {span} B: not N x {m.slot_size} "
                               f"(+2 reserved); the RAM layout moved")
        await b.call("emulator/run_frames", {"frames": BOOT_FRAMES})
        act = Act(rom_image, await m.u("Current_Act_Ptr", 4))
        print(f"  act grid {act.w}x{act.h}, {len(act.live)} real sections, "
              f"{sum(map(len, act.rings.values()))} rings, {sum(map(len, act.objs.values()))} "
              f"objects; ring buffer {cap_ring}, dynamic {cap_live}, collected slots {m.slots}; "
              f"kick {LEADER_KICK} px, follow {FOLLOW_TICKS} ticks")
        if not await m.tick():
            return await halted(m, "boot", "settle", labels, rom_image)
        cp = (await b.call("emulator/checkpoint", {}))["id"]
        worst = 0
        for name, dx, dy, lines in arms:
            await b.call("emulator/release_all", {})
            await b.call("emulator/restore", {"id": cp})
            try:
                rc = await run_arm(m, act, name, dx, dy, lines, (cap_ring, cap_live), labels,
                                   rom_image, verbose)
            except Unmeasurable as e:
                print(f"    UNMEASURABLE: {e}")
                rc = 2
            print(f"    -> {name}: {'PASS' if rc == 0 else 'FAIL' if rc == 1 else 'UNMEASURABLE'}")
            if rc == 1 or (rc == 2 and worst == 0):
                worst = rc
        return worst
    finally:
        await b.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--only", default="", help="comma-separated arm-name substrings")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    rom, lst = Path(a.rom), Path(a.lst)
    for q in (rom, lst):
        if not q.is_file():
            print(f"UNMEASURABLE: no {q}. Build it with `DEBUG=1 ./build.sh`.")
            return 2
    rom_image = rom.read_bytes()
    arms = [x for x in ARMS if not a.only or any(k in x[0] for k in a.only.split(","))]
    print(f"entity_window_diagonal_witness: {rom.name} crc32 {zlib.crc32(rom_image):08x}, "
          f"{len(arms)} arm(s)")
    inst = AetherInstance(str(rom), symbols=str(lst))
    try:
        sock = inst.start()
        rc = asyncio.run(sweep(sock, rom_image, listing_labels(lst), arms, a.verbose))
    except (Unmeasurable, SpawnError, CartMismatch) as e:
        print(f"  UNMEASURABLE: {e}")
        rc = 2
    finally:
        inst.reap()
    print({0: "PASS: every arm's window checked clean, non-vacuously",
           1: "FAIL: an arm's window broke a check, or the game halted",
           2: "UNMEASURABLE: an arm could not be measured"}[rc])
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
