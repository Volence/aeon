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
  * reserve    — band_reserve (see below) must be an int in 0..tiles, and may
                 only appear on bg_region: a field that is silently ignored on
                 13 of 14 regions is the same defect class this registry exists
                 to prevent, so a misplaced one is a build-stopping error
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
import re
import sys
import tomllib

TOTAL_TILES = 2048
# The one region whose `band_reserve` is honoured. The reserve is a GENERATOR
# budget, not a placement fact: it withholds tiles at the top of bg_region from
# the static BG importer (tools/png_to_bg_override.py) so a BgAnim band can be
# inserted later without the art having to be redrawn smaller first. Declaring
# it here rather than passing --max-tiles is deliberate — a flag is forgotten on
# the next import, which is exactly how the reserve reached zero (docs/BUGS.md
# TOOL-01). Nothing else consumes it yet, so anywhere else it would be a no-op.
RESERVE_REGION = "bg_region"
# strings interpolated into emitted .emp source, ensure messages, and markdown
# table cells must stay inside this charset (no quotes, no //, no |, no :)
SAFE_TEXT = re.compile(r"^[A-Za-z0-9_. -]+$")
# fields emitted as BARE .emp identifiers (const names, authority targets)
# must actually be identifiers — the loose charset would emit broken syntax
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MARK_BEGIN = "// >>> GENERATED: vram map (tools/gen_vram_map.py) — DO NOT HAND-EDIT <<<"
MARK_END = "// <<< GENERATED: vram map END >>>"


def fail(msg):
    print(f"gen_vram_map: {msg}", file=sys.stderr)
    sys.exit(1)


def load(toml_path):
    try:
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
    except OSError as e:
        fail(f"cannot read --toml file {toml_path}: {e.strerror or e} — "
             f"pass the game's vram.toml path (games/<game>/vram.toml)")
    except tomllib.TOMLDecodeError as e:
        fail(f"{toml_path}: TOML parse error — {e}")
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


def check_text(region_name, field, value):
    """Interpolated strings must be charset-safe — they land verbatim in
    emitted .emp source, ensure-message literals, and markdown table cells."""
    if not isinstance(value, str) or not SAFE_TEXT.match(value):
        fail(f"region {region_name!r}: field {field!r} value {value!r} has "
             f"characters outside [A-Za-z0-9_. -]")


def check_ident(region_name, field, value):
    """R3: fields emitted as bare .emp identifiers must BE identifiers —
    'VRAM WIN' or 'POOL TILES' would pass the loose charset yet emit
    broken syntax into the generated block."""
    if not isinstance(value, str) or not IDENT.match(value):
        fail(f"region {region_name!r}: field {field!r} value {value!r} is not "
             f"a valid identifier ([A-Za-z_][A-Za-z0-9_]*)")


def band_reserve(r):
    """The declared band reserve for a region, 0 when absent (the default:
    absent must mean 'behaves exactly as before this field existed')."""
    return int(r.get("band_reserve", 0))


def check_reserve(r):
    """band_reserve is an int in 0..tiles, on RESERVE_REGION only."""
    if r["name"] != RESERVE_REGION:
        fail(f"region {r['name']!r}: band_reserve is only honoured on "
             f"{RESERVE_REGION!r} (it withholds tiles from the static BG "
             f"importer); on {r['name']!r} it would be silently ignored")
    v = r["band_reserve"]
    # bool is an int subclass — `band_reserve = true` must not read as 1
    if not isinstance(v, int) or isinstance(v, bool):
        fail(f"region {r['name']!r}: band_reserve {v!r} is not an integer")
    if not (0 <= v <= r["tiles"]):
        fail(f"region {r['name']!r}: band_reserve {v} leaves 0..{r['tiles']} "
             f"(the region is {r['tiles']} tiles; a reserve cannot exceed it)")


def verify(regions, frees):
    for r in regions:
        for field in ("name", "owner", "lifetime"):
            check_text(r["name"], field, r[field])
        if r.get("const"):
            check_ident(r["name"], "const", r["const"])
        for auth in auth_list(r):
            auth_relation(r, auth)   # validates the form; result unused here
            check_ident(r["name"], "authority", auth.partition(":")[2])
        if not (0 <= r["base"] and r["base"] + r["tiles"] <= TOTAL_TILES):
            fail(f"region {r['name']!r} [{r['base']}..{r['base']+r['tiles']-1}] "
                 f"leaves 0..{TOTAL_TILES-1}")
        q = r.get("quantum")
        if q and r["tiles"] % q != 0:
            fail(f"region {r['name']!r}: tiles={r['tiles']} violates quantum {q}")
        if "band_reserve" in r:
            check_reserve(r)
    for fr in frees:
        if not (0 <= fr["base"] and fr["base"] + fr["tiles"] <= TOTAL_TILES):
            fail(f"[[free]] run [{fr['base']}..{fr['base']+fr['tiles']-1}] "
                 f"leaves 0..{TOTAL_TILES-1}")

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
    try:
        src = open(emp_path).read()
    except OSError as e:
        fail(f"cannot read --emp file {emp_path}: {e.strerror or e}")
    nb, ne = src.count(MARK_BEGIN), src.count(MARK_END)
    if nb == 0 and ne == 0:
        fail(f"{emp_path}: GENERATED markers not found — add the two marker "
             f"lines by hand once (see the plan, Task 3)")
    if nb != 1 or ne != 1:
        fail(f"{emp_path}: need exactly one GENERATED marker pair, found "
             f"{nb} BEGIN and {ne} END markers — fix the file by hand before "
             f"regenerating (a bad splice would duplicate content)")
    b, e = src.find(MARK_BEGIN), src.find(MARK_END)
    if e < b:
        fail(f"{emp_path}: the END marker appears before the BEGIN marker — "
             f"fix the marker order by hand before regenerating")
    # consume the remainder of the END-marker LINE (incl. its newline, if any)
    tail = src.find("\n", e)
    tail = len(src) if tail < 0 else tail + 1
    open(emp_path, "w").write(src[:b] + block + src[tail:])


def emit_map_doc(regions, frees, game, path):
    rows = []
    for r in regions:
        notes = []
        if r.get("overlay_with"):
            notes.append("overlay: " + ",".join(r["overlay_with"]))
        # a reserve invisible in the occupancy map is a reserve that gets
        # forgotten, which is the failure this field exists to prevent
        res = band_reserve(r)
        if res:
            notes.append(f"band_reserve: {res} (static budget {r['tiles'] - res})")
        rows.append((r["base"], r["base"] + r["tiles"] - 1, r["name"],
                     r["kind"], r["lifetime"], r["owner"],
                     r.get("const") or ", ".join(auth_list(r)),
                     "; ".join(notes)))
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
    by = {r["name"]: r for r in regions}
    for needed in ("fg_art_pool", "bg_region"):
        if needed not in by:
            fail(f"--py: region {needed!r} is not in the map — the Python "
                 f"mirror exists so build tools can import the budget "
                 f"constants (POOL_TILE_CEILING / BG_*) that derive from it; "
                 f"a mirror without them would be wrong, not empty")
    out = ["# GENERATED by tools/gen_vram_map.py from games/%s/vram.toml — do not edit." % game,
           "# Build tools import budget constants from HERE (one authority),",
           "# instead of restating them (the four-copies-of-448 incident).",
           "# GAME identifies the emitting contract: consumers that are sonic4-only",
           "# (the OJZ tools) assert it, so an accidental demo --py run cannot",
           "# silently poison their budget constants once the maps diverge.",
           "GAME = %r" % game,
           "REGIONS = {"]
    for r in sorted(regions, key=lambda r: (r["base"], r["name"])):
        out.append(f"    {r['name']!r}: {{'base': {r['base']}, 'tiles': {r['tiles']}, "
                   f"'lifetime': {r['lifetime']!r}}},")
    out.append("}")
    out.append(f"POOL_TILE_CEILING = {by['fg_art_pool']['base'] + by['fg_art_pool']['tiles']}")
    out.append(f"BG_TILE_BASE_SLOT = {by['bg_region']['base']}")
    out.append(f"BG_TILE_CAPACITY = {by['bg_region']['tiles']}")
    # BG_BAND_RESERVE / BG_STATIC_TILE_BUDGET: the reserve, and the subtraction
    # done ONCE here so no consumer restates it (the four-copies lesson applied
    # to the arithmetic, not just the literal). CAPACITY stays the hard VRAM
    # ceiling — tools/inject_editor_bg.py must keep gating the FINAL blob on it,
    # because a band's tiles live inside `tiles`, not beside it. The BUDGET is
    # for the static importer alone, which authors no bands and so must leave
    # room for one.
    res = band_reserve(by['bg_region'])
    out.append(f"BG_BAND_RESERVE = {res}")
    out.append(f"BG_STATIC_TILE_BUDGET = {by['bg_region']['tiles'] - res}")
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
