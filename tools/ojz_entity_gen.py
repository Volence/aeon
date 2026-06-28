#!/usr/bin/env python3
"""OJZ entity data generator — editor JSONs → engine entity_data.asm.

Reads per-section ring/object placement JSONs authored by the level editor
and emits the assembly entity tables consumed by the §4.9 camera-driven
entity window (act descriptor references the OJZ_Sec{N}_* labels).

Usage:
    python3 tools/ojz_entity_gen.py test      # run self-tests
    python3 tools/ojz_entity_gen.py generate  # generate entity_data.asm

Inputs (paths resolved via project.json):
    project.json                  zones[0].acts[0]: gridWidth/gridHeight/dataPath
    data/editor/objects.json      object library: [{id, name, codeLabel,
                                  defaultSubtype, properties}]
    {dataPath}/section_{N}.rings.json    [{x, y}] section-local pixels
    {dataPath}/section_{N}.objects.json  [{x, y, typeId, subtype} + optional
                                  booleans anyY, xflip, yflip]

Output: data/generated/ojz/act1/entity_data.asm
    For every section N in 0..gridW*gridH-1:
      OJZ_Sec{N}_TypeTable:  dc.b count, 0  then count × dc.l ObjDefLabel.
                             Minimized per section: only typeIds the section
                             uses, packed in first-use order after X-sorting.
      OJZ_Sec{N}_Objects:    objentry x, y, type [, sub] [, oflags] lines,
                             X-sorted ascending (stable; ties by Y then
                             authored order); objend terminator. type is the
                             index into the section's own type table.
      OJZ_Sec{N}_Rings:      dc.w X, Y pairs, X-sorted ascending (stable,
                             ties by Y); dc.l 0 terminator.
    Empty sections still emit all three labels (dc.b 0,0 / objend / dc.l 0).

Build-time validation (nonzero exit, all errors listed):
    - any coordinate outside [0, SECTION_SIZE)
    - > MAX_LIST_ENTRIES rings or objects per section (bitmask capacity)
    - > MAX_TYPES_PER_SECTION distinct types per section (5-bit type field)
    - unknown typeId (not in the object library); subtype outside 0-255
    - a ring at exactly (0,0) — would alias the dc.l 0 list terminator

Ring pressure analysis (stats, not failure): for every 2×2 block of adjacent
sections (degenerate 1-wide/1-tall blocks on the right/bottom edges), the
rings are combined in world coordinates and a Y band of PRESSURE_BAND_HEIGHT
pixels is swept over them; the max simultaneous ring count per block is
reported in the generated header. A global worst case above MAX_LIST_ENTRIES
prints a loud WARNING (conservative: the X ratchet rarely covers both columns
of a block fully).
"""

import json
import os
import sys

# Constants — must match constants.asm
SECTION_SIZE = 2048          # constants.asm SECTION_SIZE = $0800 (pixels per axis)
MAX_LIST_ENTRIES = 128       # constants.asm MAX_LIST_ENTRIES — collected/killed/loaded bitmask capacity
MAX_TYPES_PER_SECTION = 32   # constants.asm OEF_TYPE_MASK = $1F — 5-bit type field
MAX_SUBTYPE = 255            # constants.asm OEF_SUBTYPE_MASK = $FF

# Pressure-analysis Y band: visible rows + entity-window vertical margins.
SCREEN_HEIGHT = 224
BAND_Y_MARGIN = 256          # entity window extends ±256px beyond the screen
PRESSURE_BAND_HEIGHT = SCREEN_HEIGHT + 2 * BAND_Y_MARGIN  # 736

# Flag JSON key → OEF_* constant name (emitted as pre-shifted (1<<OEF_*) masks)
FLAG_KEYS = (
    ("anyY", "OEF_ANY_Y"),
    ("xflip", "OEF_XFLIP"),
    ("yflip", "OEF_YFLIP"),
)

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PROJECT_JSON = os.path.join(REPO_ROOT, "project.json")
OBJECT_LIBRARY_JSON = os.path.join(REPO_ROOT, "games", "sonic4", "data", "editor", "objects.json")
OUTPUT_PATH = os.path.join(REPO_ROOT, "games", "sonic4", "data", "generated", "ojz", "act1", "entity_data.asm")


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_act_config():
    """Read grid dimensions and data path from project.json (READ ONLY)."""
    with open(PROJECT_JSON, "r") as f:
        proj = json.load(f)
    act = proj["zones"][0]["acts"][0]
    return {
        "grid_w": act["gridWidth"],
        "grid_h": act["gridHeight"],
        "data_path": os.path.join(REPO_ROOT, act["dataPath"]),
    }


def load_object_library(path: str = OBJECT_LIBRARY_JSON) -> dict[str, str]:
    """Load the object library. Returns {typeId: codeLabel}."""
    with open(path, "r") as f:
        lib = json.load(f)
    return {entry["id"]: entry["codeLabel"] for entry in lib}


def load_section_json(data_path: str, sec_idx: int, kind: str) -> list[dict]:
    """Load section_{N}.{rings|objects}.json; missing file → empty list."""
    path = os.path.join(data_path, f"section_{sec_idx}.{kind}.json")
    if not os.path.isfile(path):
        return []
    with open(path, "r") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Validation + sorting
# ---------------------------------------------------------------------------

def validate_and_sort_rings(rings: list[dict], sec_idx: int, errors: list[str]):
    """Range-check rings; return [(x, y)] X-sorted ascending (stable, ties by Y)."""
    out = []
    for i, ring in enumerate(rings):
        x, y = ring["x"], ring["y"]
        where = f"section_{sec_idx}.rings.json[{i}]"
        if not (0 <= x < SECTION_SIZE) or not (0 <= y < SECTION_SIZE):
            errors.append(
                f"{where}: ring ({x},{y}) outside [0,{SECTION_SIZE}) — SECTION_SIZE"
            )
            continue
        if x == 0 and y == 0:
            errors.append(
                f"{where}: ring at exactly (0,0) would alias the dc.l 0 list "
                f"terminator — move it at least 1px"
            )
            continue
        out.append((x, y))
    if len(out) > MAX_LIST_ENTRIES:
        errors.append(
            f"section_{sec_idx}.rings.json: {len(out)} rings exceeds "
            f"MAX_LIST_ENTRIES ({MAX_LIST_ENTRIES} — collected-bitmask capacity)"
        )
    out.sort(key=lambda r: (r[0], r[1]))  # stable: ties keep authored order
    return out


def validate_and_sort_objects(objects: list[dict], sec_idx: int,
                              library: dict[str, str], errors: list[str]):
    """Range/type-check objects; return (sorted_objects, type_order).

    sorted_objects: [(x, y, type_index, subtype, [flag_names])] X-sorted
    ascending (stable; ties by Y then authored order).
    type_order: [typeId] in first-use order after sorting (per-section
    minimized type table).
    """
    checked = []
    for i, obj in enumerate(objects):
        x, y = obj["x"], obj["y"]
        type_id = obj.get("typeId")
        subtype = obj.get("subtype", 0)
        where = f"section_{sec_idx}.objects.json[{i}]"
        ok = True
        if not (0 <= x < SECTION_SIZE) or not (0 <= y < SECTION_SIZE):
            errors.append(
                f"{where}: object ({x},{y}) outside [0,{SECTION_SIZE}) — SECTION_SIZE"
            )
            ok = False
        if type_id not in library:
            errors.append(
                f"{where}: unknown typeId {type_id!r} — not in data/editor/objects.json"
            )
            ok = False
        if not (0 <= subtype <= MAX_SUBTYPE):
            errors.append(
                f"{where}: subtype {subtype} outside 0-{MAX_SUBTYPE}"
            )
            ok = False
        if not ok:
            continue
        flags = [name for key, name in FLAG_KEYS if obj.get(key)]
        checked.append((x, y, type_id, subtype, flags))

    if len(checked) > MAX_LIST_ENTRIES:
        errors.append(
            f"section_{sec_idx}.objects.json: {len(checked)} objects exceeds "
            f"MAX_LIST_ENTRIES ({MAX_LIST_ENTRIES} — killed-bitmask capacity)"
        )

    checked.sort(key=lambda o: (o[0], o[1]))  # stable: ties keep authored order

    # Per-section minimized type table, packed in first-use order
    type_order: list[str] = []
    for x, y, type_id, subtype, flags in checked:
        if type_id not in type_order:
            type_order.append(type_id)
    if len(type_order) > MAX_TYPES_PER_SECTION:
        errors.append(
            f"section_{sec_idx}.objects.json: {len(type_order)} distinct types "
            f"exceeds {MAX_TYPES_PER_SECTION} (OEF type field is 5 bits)"
        )

    type_index = {tid: i for i, tid in enumerate(type_order)}
    sorted_objects = [
        (x, y, type_index[tid], subtype, flags)
        for x, y, tid, subtype, flags in checked
    ]
    return sorted_objects, type_order


# ---------------------------------------------------------------------------
# Ring pressure analysis
# ---------------------------------------------------------------------------

def band_pressure(world_rings: list[tuple[int, int]]) -> int:
    """Max ring count inside any Y band of PRESSURE_BAND_HEIGHT pixels.

    Exact sweep: the maximal band can always be slid until its top edge
    touches a ring, so evaluating the band top at each distinct ring Y
    finds the true maximum.
    """
    if not world_rings:
        return 0
    ys = sorted(y for _, y in world_rings)
    worst = 0
    for top in sorted(set(ys)):
        count = sum(1 for y in ys if top <= y < top + PRESSURE_BAND_HEIGHT)
        worst = max(worst, count)
    return worst


def pressure_analysis(per_section_rings: list[list[tuple[int, int]]],
                      grid_w: int, grid_h: int):
    """Per-2×2-section-block worst-case ring band pressure.

    Blocks anchor at every (bx, by); right/bottom edges degenerate to
    1-wide/1-tall blocks. Rings are combined in world coordinates
    (section-local + section_origin × SECTION_SIZE).

    Returns ([(bx, by, worst_count)], global_worst).
    """
    results = []
    global_worst = 0
    for by in range(grid_h):
        for bx in range(grid_w):
            world = []
            # Edge blocks degenerate: the +1 neighbour clamps onto the anchor
            # and the set dedupes it away (1-wide/1-tall block).
            sections = {(sx, sy)
                        for sy in {by, min(by + 1, grid_h - 1)}
                        for sx in {bx, min(bx + 1, grid_w - 1)}}
            for sx, sy in sections:
                sec_idx = sy * grid_w + sx
                for x, y in per_section_rings[sec_idx]:
                    world.append((sx * SECTION_SIZE + x, sy * SECTION_SIZE + y))
            worst = band_pressure(world)
            results.append((bx, by, worst))
            global_worst = max(global_worst, worst)
    return results, global_worst


# ---------------------------------------------------------------------------
# Emission
# ---------------------------------------------------------------------------

def hexw(v: int) -> str:
    """Format a coordinate the way the hand-written file did: $-hex, 3+ digits."""
    return f"${v:03X}"


def emit_section(lines: list[str], sec_idx: int,
                 sorted_objects, type_order, library, sorted_rings) -> None:
    """Append one section's TypeTable/Objects/Rings blocks to lines."""
    sep = "; -----------------------------------------------"

    # Type table
    lines.append(sep)
    lines.append(f"; Sec{sec_idx} Type Table — {len(type_order)} type"
                 f"{'' if len(type_order) == 1 else 's'} (count prefix + longword array)")
    lines.append(sep)
    lines.append(f"OJZ_Sec{sec_idx}_TypeTable:")
    lines.append(f"        dc.b    {len(type_order)}, 0                    ; count, pad")
    for i, tid in enumerate(type_order):
        label = library[tid]
        pad = " " * max(1, 24 - len(label))
        lines.append(f"        dc.l    {label}{pad}; type {i} — {tid}")
    lines.append("")

    # Objects
    lines.append(sep)
    lines.append(f"; Sec{sec_idx} Object Layout — objentry (x, y, type [, sub] [, oflags]),")
    lines.append("; X-sorted ascending. objend emits the dc.w -1 terminator.")
    lines.append(sep)
    lines.append(f"OJZ_Sec{sec_idx}_Objects:")
    for x, y, type_idx, subtype, flags in sorted_objects:
        args = [hexw(x), hexw(y), str(type_idx)]
        if subtype != 0 or flags:
            args.append(str(subtype))
        if flags:
            args.append("|".join(f"(1<<{name})" for name in flags))
        lines.append(f"        objentry {', '.join(args)}")
    lines.append("        objend")
    lines.append("")

    # Rings
    lines.append(sep)
    lines.append(f"; Sec{sec_idx} Ring Layout — flat X-sorted (dc.w X, dc.w Y per ring)")
    lines.append(sep)
    lines.append(f"OJZ_Sec{sec_idx}_Rings:")
    for x, y in sorted_rings:
        lines.append(f"        dc.w    {hexw(x)}, {hexw(y)}")
    lines.append("        dc.l    0                       ; terminator")
    lines.append("")


def generate() -> None:
    """Generate entity_data.asm from the editor JSONs. Exits nonzero on errors."""
    cfg = load_act_config()
    grid_w, grid_h = cfg["grid_w"], cfg["grid_h"]
    num_sections = grid_w * grid_h
    library = load_object_library()

    errors: list[str] = []
    per_section_rings: list[list[tuple[int, int]]] = []
    per_section_objects = []
    per_section_types = []

    for sec_idx in range(num_sections):
        rings_raw = load_section_json(cfg["data_path"], sec_idx, "rings")
        objects_raw = load_section_json(cfg["data_path"], sec_idx, "objects")
        per_section_rings.append(
            validate_and_sort_rings(rings_raw, sec_idx, errors))
        sorted_objects, type_order = validate_and_sort_objects(
            objects_raw, sec_idx, library, errors)
        per_section_objects.append(sorted_objects)
        per_section_types.append(type_order)

    if errors:
        print("ojz_entity_gen: VALIDATION FAILED", file=sys.stderr)
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    blocks, global_worst = pressure_analysis(per_section_rings, grid_w, grid_h)

    total_rings = sum(len(r) for r in per_section_rings)
    total_objects = sum(len(o) for o in per_section_objects)

    lines: list[str] = []
    lines.append("; AUTO-GENERATED by tools/ojz_entity_gen.py — DO NOT EDIT;")
    lines.append("; edit data/editor/ojz/act1/section_N.{rings,objects}.json and")
    lines.append("; data/editor/objects.json instead, then rebuild.")
    lines.append(";")
    lines.append("; OJZ Act 1 entity data — flat X-sorted ring lists + object placements")
    lines.append("; + per-section minimized type tables (§4.9 camera-driven entity window)")
    lines.append(";")
    lines.append("; Stats:")
    lines.append(f";   grid: {grid_w}×{grid_h} ({num_sections} sections)")
    lines.append(f";   rings: {total_rings} total "
                 f"({', '.join(f'sec{i}={len(r)}' for i, r in enumerate(per_section_rings) if r)})")
    lines.append(f";   objects: {total_objects} total "
                 f"({', '.join(f'sec{i}={len(o)}' for i, o in enumerate(per_section_objects) if o)})")
    lines.append(f";   ring pressure ({PRESSURE_BAND_HEIGHT}px Y band over 2×2 section blocks):")
    for bx, by, worst in blocks:
        if worst:
            lines.append(f";     block ({bx},{by}): {worst}")
    lines.append(f";     global worst: {global_worst} "
                 f"(capacity {MAX_LIST_ENTRIES} per section ring buffer)")
    lines.append("")

    for sec_idx in range(num_sections):
        emit_section(lines, sec_idx, per_section_objects[sec_idx],
                     per_section_types[sec_idx], library,
                     per_section_rings[sec_idx])

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write("\n".join(lines))
        f.write("\n")

    print(f"ojz_entity_gen: {num_sections} sections, {total_rings} rings, "
          f"{total_objects} objects -> {os.path.normpath(OUTPUT_PATH)}")
    print(f"ojz_entity_gen: ring pressure global worst = {global_worst} "
          f"(band {PRESSURE_BAND_HEIGHT}px, capacity {MAX_LIST_ENTRIES})")
    if global_worst > MAX_LIST_ENTRIES:
        print("ojz_entity_gen: *** WARNING *** ring band pressure "
              f"{global_worst} exceeds MAX_LIST_ENTRIES ({MAX_LIST_ENTRIES}) — "
              "a fully-covered 2×2 block could overflow the ring window "
              "(conservative estimate; X ratchet rarely covers both columns)")


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def test_ring_sort_and_validation():
    errors = []
    rings = [{"x": 512, "y": 80}, {"x": 256, "y": 96}, {"x": 256, "y": 64}]
    out = validate_and_sort_rings(rings, 0, errors)
    assert out == [(256, 64), (256, 96), (512, 80)]
    assert errors == []

    errors = []
    validate_and_sort_rings([{"x": 0, "y": 0}], 0, errors)
    assert len(errors) == 1 and "terminator" in errors[0]

    errors = []
    validate_and_sort_rings([{"x": 2048, "y": 5}], 0, errors)
    assert len(errors) == 1 and "outside" in errors[0]

    errors = []
    validate_and_sort_rings([{"x": 1, "y": 1}] * 129, 0, errors)
    assert len(errors) == 1 and "MAX_LIST_ENTRIES" in errors[0]
    print("  test_ring_sort_and_validation OK")


def test_object_sort_types_flags():
    lib = {"solid": "ObjDef_Solid", "enemy": "ObjDef_Enemy"}
    errors = []
    objs = [
        {"x": 768, "y": 144, "typeId": "enemy", "subtype": 0},
        {"x": 512, "y": 176, "typeId": "solid", "subtype": 0, "anyY": True},
    ]
    sorted_objs, types = validate_and_sort_objects(objs, 0, lib, errors)
    assert errors == []
    assert types == ["solid", "enemy"]  # first-use order after X-sort
    assert sorted_objs == [
        (512, 176, 0, 0, ["OEF_ANY_Y"]),
        (768, 144, 1, 0, []),
    ]

    errors = []
    validate_and_sort_objects(
        [{"x": 1, "y": 1, "typeId": "nope", "subtype": 0}], 0, lib, errors)
    assert len(errors) == 1 and "unknown typeId" in errors[0]

    errors = []
    validate_and_sort_objects(
        [{"x": 1, "y": 1, "typeId": "solid", "subtype": 256}], 0, lib, errors)
    assert len(errors) == 1 and "subtype" in errors[0]
    print("  test_object_sort_types_flags OK")


def test_stable_tie_break():
    errors = []
    rings = [{"x": 100, "y": 50}, {"x": 100, "y": 50}, {"x": 100, "y": 40}]
    out = validate_and_sort_rings(rings, 0, errors)
    assert out == [(100, 40), (100, 50), (100, 50)]
    print("  test_stable_tie_break OK")


def test_band_pressure():
    # 3 rings inside one 736px band, 1 far below
    rings = [(0, 100), (0, 200), (0, 800), (0, 5000)]
    assert band_pressure(rings) == 3
    assert band_pressure([]) == 0
    # All in one tight cluster
    assert band_pressure([(0, 10)] * 5) == 5
    print("  test_band_pressure OK")


def test_pressure_blocks():
    # 2×2 grid, every section has 1 ring at the same local spot near y=0 —
    # vertically adjacent pairs land 2048px apart so a 736px band holds
    # only one row: worst per block = 2 (the two horizontal neighbours).
    per_sec = [[(100, 100)], [(200, 100)], [(100, 100)], [(200, 100)]]
    blocks, worst = pressure_analysis(per_sec, 2, 2)
    assert worst == 2, f"expected 2, got {worst}"
    print("  test_pressure_blocks OK")


def test_emit_section_shapes():
    lib = {"solid": "ObjDef_Solid"}
    lines = []
    emit_section(lines, 5, [], [], lib, [])
    text = "\n".join(lines)
    assert "OJZ_Sec5_TypeTable:" in text
    assert "dc.b    0, 0" in text
    assert "OJZ_Sec5_Objects:" in text
    assert "objend" in text
    assert "OJZ_Sec5_Rings:" in text
    assert "dc.l    0" in text

    lines = []
    emit_section(lines, 0, [(1024, 1792, 0, 0, ["OEF_ANY_Y"])], ["solid"],
                 lib, [(128, 96)])
    text = "\n".join(lines)
    assert "objentry $400, $700, 0, 0, (1<<OEF_ANY_Y)" in text
    assert "dc.w    $080, $060" in text
    print("  test_emit_section_shapes OK")


def run_tests():
    print("Running ojz_entity_gen tests...")
    test_ring_sort_and_validation()
    test_object_sort_types_flags()
    test_stable_tie_break()
    test_band_pressure()
    test_pressure_blocks()
    test_emit_section_shapes()
    print("All tests passed")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("test", "generate"):
        print(f"Usage: {sys.argv[0]} test|generate")
        sys.exit(1)

    if sys.argv[1] == "test":
        run_tests()
        return

    generate()


if __name__ == "__main__":
    main()
