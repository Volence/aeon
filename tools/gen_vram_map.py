#!/usr/bin/env python3
"""gen_vram_map.py — the VRAM registry generator (linker T0, spec 2026-08-11).

Reads a game's vram.toml (the declared placement contract), VERIFIES it, and
EMITS:
  --emp      rewrite the GENERATED marker block inside the game's constants.emp
  --map-doc  the human-readable occupancy map (markdown)
  --py       the Python mirror (tools/vram_map.py) — sonic4 only; the build
             tools import their budget constants from it instead of restating
             them (this retires the four independent copies of the BG '448')

Checks (all build-stopping):
  * bounds     — every region/free run inside tiles 0..2047
  * coverage   — every tile is a region or a DECLARED [[free]] run; gaps are
                 errors naming the exact run, so free space is intentional
  * overlap    — two regions may not share tiles unless one names the other in
                 overlay_with (T0 accepts only statically-safe overlays; T2
                 adds lifetime checking)
  * quantum    — a region with quantum = N must have tiles % N == 0
  * authority  — typed cross-check forms (R1): engine-bytebase:NAME (NAME is a
                 VRAM byte address == base*32), engine-tiles:NAME (== tiles),
                 engine-endtiles:NAME (== base+tiles) each emit a comptime
                 ensure in the marker block; sigil-D:NAME is documented in the
                 map only (T1 closes it). String or list of strings. Unknown
                 form is a build-stopping error.

Deterministic: no timestamps, sorted iteration; two runs are byte-identical.
Region bases are REQUIRED at T0 (everything pinned); the T1 solver in sigil's
chainer introduces floating regions.
"""

import argparse
import sys
import tomllib

TOTAL_TILES = 2048
MARK_BEGIN = "// >>> GENERATED: vram map (tools/gen_vram_map.py) — DO NOT HAND-EDIT <<<"
MARK_END = "// <<< GENERATED: vram map END >>>"


def fail(msg):
    print(f"gen_vram_map: {msg}", file=sys.stderr)
    sys.exit(1)


def load(toml_path):
    with open(toml_path, "rb") as f:
        data = tomllib.load(f)
    regions = data.get("region", [])
    frees = data.get("free", [])
    for r in regions:
        for k in ("name", "owner", "kind", "base", "tiles", "lifetime"):
            if k not in r:
                fail(f"region {r.get('name','<unnamed>')!r} missing field {k!r}")
    for fr in frees:
        for k in ("base", "tiles"):
            if k not in fr:
                fail(f"[[free]] entry missing field {k!r}")
    return regions, frees


def auth_list(r):
    """Normalize the optional authority field: string -> one-element list."""
    a = r.get("authority")
    if a is None:
        return []
    return a if isinstance(a, list) else [a]


def auth_relation(r, auth):
    """The ensure relation for an engine-form authority; None for sigil-D
    (documented in the map, no ensure — T1 closes it). Unknown form is a
    build-stopping error naming the form and the region."""
    form, sep, name = auth.partition(":")
    if not sep or not name:
        fail(f"region {r['name']!r}: authority {auth!r} is not '<form>:<NAME>'")
    if form == "sigil-D":
        return None
    if form == "engine-bytebase":
        return f"{name} == ${r['base'] * 32:04X}"
    if form == "engine-tiles":
        return f"{name} == {r['tiles']}"
    if form == "engine-endtiles":
        return f"{name} == {r['base'] + r['tiles']}"
    fail(f"region {r['name']!r}: unknown authority form {form!r} in {auth!r}")


def verify(regions, frees):
    for r in regions:
        for auth in auth_list(r):
            auth_relation(r, auth)   # validates the form; result unused here
        if not (0 <= r["base"] and r["base"] + r["tiles"] <= TOTAL_TILES):
            fail(f"region {r['name']!r} [{r['base']}..{r['base']+r['tiles']-1}] "
                 f"leaves 0..{TOTAL_TILES-1}")
        q = r.get("quantum")
        if q and r["tiles"] % q != 0:
            fail(f"region {r['name']!r}: tiles={r['tiles']} violates quantum {q}")

    # overlap: pairwise interval check, exempting declared overlays (either way)
    def overlaid(a, b):
        return b["name"] in a.get("overlay_with", []) or \
               a["name"] in b.get("overlay_with", [])
    rs = sorted(regions, key=lambda r: (r["base"], r["name"]))
    for i, a in enumerate(rs):
        for b in rs[i + 1:]:
            if b["base"] >= a["base"] + a["tiles"]:
                break
            if not overlaid(a, b):
                fail(f"regions {a['name']!r} and {b['name']!r} overlap at "
                     f"tile {b['base']} and neither declares overlay_with the other")

    # coverage: non-overlay occupancy + declared frees must tile 0..2047 exactly
    owned = [False] * TOTAL_TILES
    for r in rs:
        for t in range(r["base"], r["base"] + r["tiles"]):
            owned[t] = True
    for fr in frees:
        for t in range(fr["base"], fr["base"] + fr["tiles"]):
            if owned[t]:
                fail(f"[[free]] run at {fr['base']} overlaps a region at tile {t}")
            owned[t] = True
    t = 0
    while t < TOTAL_TILES:
        if not owned[t]:
            start = t
            while t < TOTAL_TILES and not owned[t]:
                t += 1
            fail(f"tiles {start}..{t-1} are neither a region nor a declared "
                 f"[[free]] run — declare them (free space must be intentional)")
        t += 1


def emit_emp_block(regions, game):
    lines = [MARK_BEGIN,
             f"// Emitted from games/{game}/vram.toml — edit THAT, then run:",
             f"//   python3 tools/gen_vram_map.py --game {game}",
             "// The map doc: docs/generated/vram-map-" + game + ".md"]
    for r in sorted(regions, key=lambda r: (r["base"], r["name"])):
        c = r.get("const")
        if c:
            lines.append(
                f"pub const {c:<24}: VramTile = ${r['base']:04X}"
                f"   // {r['name']}: tiles {r['base']}..{r['base']+r['tiles']-1}"
                f" ({r['tiles']}), {r['lifetime']}, owner {r['owner']}")
    # authority cross-checks (R1): one ensure per engine-form authority, so a
    # vram.toml value drifting from its engine constant stops the build
    checks = []
    for r in sorted(regions, key=lambda r: (r["base"], r["name"])):
        for auth in auth_list(r):
            rel = auth_relation(r, auth)
            if rel is None:
                continue    # sigil-D: map-doc only
            name = auth.partition(":")[2]
            checks.append(
                f"ensure({rel}, \"vram.toml {r['name']} drifted from engine "
                f"{name} — edit games/{game}/vram.toml and regenerate\")")
    if checks:
        lines.append("// Authority cross-checks — the engine constant vs the declared map:")
        lines += checks
    # walls: each const-emitting region must end at or before its successor
    lines.append("// Walls — regeneration re-checks every adjacency:")
    rs = sorted((r for r in regions if not r.get("overlay_with")),
                key=lambda r: r["base"])
    for a, b in zip(rs, rs[1:]):
        ca = a.get("const")
        if ca:
            lines.append(
                f"ensure({ca} + {a['tiles']} <= ${b['base']:04X},"
                f" \"{a['name']} runs into {b['name']}\")")
    lines.append(MARK_END)
    return "\n".join(lines) + "\n"


def splice(emp_path, block):
    src = open(emp_path).read()
    b, e = src.find(MARK_BEGIN), src.find(MARK_END)
    if b < 0 or e < 0:
        fail(f"{emp_path}: GENERATED markers not found — add the two marker "
             f"lines by hand once (see the plan, Task 3)")
    open(emp_path, "w").write(src[:b] + block + src[e + len(MARK_END) + 1:])


def emit_map_doc(regions, frees, game, path):
    rows = []
    for r in regions:
        rows.append((r["base"], r["base"] + r["tiles"] - 1, r["name"],
                     r["kind"], r["lifetime"], r["owner"],
                     r.get("const") or ", ".join(auth_list(r)),
                     "overlay: " + ",".join(r["overlay_with"]) if r.get("overlay_with") else ""))
    for fr in frees:
        rows.append((fr["base"], fr["base"] + fr["tiles"] - 1, "FREE",
                     "", "", "", "", ""))
    rows.sort()
    out = [f"# VRAM map — {game}", "",
           f"GENERATED by tools/gen_vram_map.py from games/{game}/vram.toml.",
           "Do not edit; edit the TOML and regenerate.", "",
           "| tiles | name | kind | lifetime | owner | constant / authority | notes |",
           "|---|---|---|---|---|---|---|"]
    for (a, b, name, kind, life, owner, const, note) in rows:
        out.append(f"| {a}-{b} | {name} | {kind} | {life} | {owner} | {const} | {note} |")
    free_total = sum(fr["tiles"] for fr in frees)
    out += ["", f"Free: {free_total} tiles across {len(frees)} runs."]
    open(path, "w").write("\n".join(out) + "\n")


def emit_py(regions, frees, game, path):
    out = ["# GENERATED by tools/gen_vram_map.py from games/%s/vram.toml — do not edit." % game,
           "# Build tools import budget constants from HERE (one authority),",
           "# instead of restating them (the four-copies-of-448 incident).",
           "REGIONS = {"]
    for r in sorted(regions, key=lambda r: (r["base"], r["name"])):
        out.append(f"    {r['name']!r}: {{'base': {r['base']}, 'tiles': {r['tiles']}, "
                   f"'lifetime': {r['lifetime']!r}}},")
    out.append("}")
    by = {r["name"]: r for r in regions}
    out.append(f"POOL_TILE_CEILING = {by['fg_art_pool']['base'] + by['fg_art_pool']['tiles']}"
               if "fg_art_pool" in by else "")
    if "bg_region" in by:
        out.append(f"BG_TILE_BASE_SLOT = {by['bg_region']['base']}")
        out.append(f"BG_TILE_CAPACITY = {by['bg_region']['tiles']}")
    for r in regions:
        if r.get("const"):
            out.append(f"{r['const']} = {r['base']}")
    open(path, "w").write("\n".join(x for x in out if x) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--toml")
    ap.add_argument("--emp")
    ap.add_argument("--map-doc")
    ap.add_argument("--py")
    a = ap.parse_args()
    toml = a.toml or f"games/{a.game}/vram.toml"
    regions, frees = load(toml)
    verify(regions, frees)
    if a.emp:
        splice(a.emp, emit_emp_block(regions, a.game))
    if a.map_doc:
        emit_map_doc(regions, frees, a.game, a.map_doc)
    if a.py:
        emit_py(regions, frees, a.game, a.py)
    print(f"gen_vram_map: {a.game} OK — {len(regions)} regions, "
          f"{sum(f['tiles'] for f in frees)} free tiles")


if __name__ == "__main__":
    main()
