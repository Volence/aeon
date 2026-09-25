#!/usr/bin/env python3
"""A clip act's own sound-bank positions: derive `anchors.toml`, and say when it is STALE.

WHY THIS EXISTS (owner ruling d-35-revised = `clip-overlay-file`, 2026-09-25). A Sonic 2
clip build (`S2CLIP=<id> ./build.sh`) re-bakes the one act slot with far more level data
than the shipped act, and the two Z80 bank anchors (`dac_banks`, `sound_bank`) have to sit
above the packed data with the growth reserve free under them. Putting the clip shapes
into `games/sonic4/map.toml`'s anchor max was REFUSED (a test fixture must not move the
shipping layout). So each clip that needs its own positions carries ONE file,
`games/sonic4/data/clips/<id>/anchors.toml`, and build.sh hands it to `sigil build` as
`--anchor-overlay <path>` on that clip's builds only (never to the preflight
`emit_sound_blob`: `sigil build` re-emits the sound artifacts from its own switch). Sigil's
contract for the switch: sigil `docs/superpowers/notes/2026-09-25-clip-overlay-contract.md`
(the revision that says "sigil build only" is a1ff8796).

THE VALUE IS THE BANK PLACEMENT RULE, APPLIED TO THE CLIP ITSELF. For each of the clip's
two shapes (plain, DEBUG) the rule gives `dac_banks = align_up(packed_end + reserve +
grace, 0x8000)` (`bganim_room.rule_anchor`, the same function the room gate uses), and
the file takes the MAX over both shapes, exactly as map.toml takes the max over the
canonical sound-on shapes. Today DEBUG binds. `sound_bank = dac_banks + 0x10000`
(`bganim_room.SOUND_BANK_OFFSET`); `vma` and `when` are copied from map.toml's own rows,
because sigil refuses an overlay row that changes anything but the position.

WHY IT NEEDS BOTH SHAPES, AND HOW ONE BUILD STILL CHECKS IT. The max needs both shapes'
packed ends, and one build writes one shape. So:

  (check) runs INSIDE every S2CLIP build, after `sigil build`, on this invocation's own
          fresh (.bin, .lst) pair. It measures this shape's packed end (through
          `bganim_room.rom_room`, so the terminus and extent checks the room gate trusts
          are the ones this trusts), writes a MEASUREMENT RECORD beside the ROM
          (`<rom stem>.clip_anchors.json`, gitignored), and then, when the clip has an
          `anchors.toml`, compares this shape's rule value with the one the file was
          derived from (each derivation writes a `# measured:` line per shape). A
          different value is STALE.
  --derive reads the two measurement records, refuses unless each still describes the
          ROM and listing on disk (crc/size and sha256), and writes `anchors.toml`.

So the loop after a clip grows or shrinks across a bank boundary is: the build fails
naming this file; build the other shape too; `--derive`; commit; rebuild. The record is
written even on a STALE verdict, so the failing build itself supplies derive's input.

WHAT "STALE" MEANS HERE, and why the compare is the RULE VALUE and not the packed end.
The anchors move only when the rule's answer moves; the packed end moves on every byte.
Comparing packed ends would fail every clip build after every edit. Comparing the rule's
answer fails exactly when the positions the file holds are no longer the ones the rule
gives for this shape — in either direction, because a file that is higher than it needs
to be is still not the derivation of this tree.

WHAT IT ALSO CHECKS, on every S2CLIP build, because a positions file nobody applied is
the silent case: the islands sit where the effective anchors say (`Dac_Temp_Blip`'s LMA
is `dac_banks`, `SoundTablesZ80_Head`'s PHASE LMA is `sound_bank`), and the listing's
Source Digest carries a READ row for the overlay exactly when the clip has one. Either
failing means build.sh did not hand the file to sigil, or sigil did not apply it.

WHAT IT DOES NOT SEE: whether the other shape is still fresh. One build measures one
shape; the other shape's `# measured:` line is checked when that shape builds. Nor the
emit half: that the bank ids baked at emit time match the placed banks is sigil's
`[sound.bank-id-vs-placement]` check, inside `sigil build`.

EXIT CODES, the shape of tools/level_staleness.py: 0 fresh (or no overlay), 2 STALE
(the anchors, or the (.bin, .lst) pair per tools/artifact_provenance.py, whose stale code
every `--built-after` consumer shares), 1 the check could not measure or the tool broke. build.sh runs it `strict`: any non-zero
fails the build.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import tomllib
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artifact_provenance  # noqa: E402
import bganim_room  # noqa: E402

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIPS_REL = os.path.join("games", "sonic4", "data", "clips")
MAP_REL = os.path.join("games", "sonic4", "map.toml")
OVERLAY_NAME = "anchors.toml"
RECORD_SUFFIX = ".clip_anchors.json"

FRESH, BROKEN, STALE = 0, 1, 2

#: The two anchors a clip overlays, and the island label each one holds. The names are
#: map.toml's; the labels are the section heads map.toml's own comments name for them
#: (`dac_banks.emp section head (Dac_Temp_Blip)`, `SoundTablesZ80_Head`). The sound
#: bank's label carries its VMA in the listing's label column, so its LMA is read from
#: the listing's `PHASE <label> VMA $.. LMA $..` row instead.
ANCHORS = (bganim_room.ANCHOR_NAME, bganim_room.SOUND_ANCHOR_NAME)
ISLAND_LABEL = {bganim_room.ANCHOR_NAME: "Dac_Temp_Blip",
                bganim_room.SOUND_ANCHOR_NAME: "SoundTablesZ80_Head"}

_MEASURED = re.compile(
    r"^# measured: shape=(?P<shape>\S+) packed_end=0x(?P<end>[0-9A-Fa-f]+) "
    r"rule=0x(?P<rule>[0-9A-Fa-f]+)\b")
_PHASE = re.compile(r"^PHASE (\S+) VMA \$([0-9A-Fa-f]+) LMA \$([0-9A-Fa-f]+)\s*$")
_BUILD_ROM_NAME = re.compile(r'^\s*ROM_NAME="(s4\.s2clip[^"$]*)"\s*$')


class Unmeasurable(Exception):
    """The check could not reach its subject. Never converted to a pass."""


class Stale(Unmeasurable):
    """tools/artifact_provenance.py called the (.bin, .lst) pair NOT FRESH: exit 2, the
    stale code every provenance consumer shares (a stale PAIR, not stale anchors; both
    fail the build, and the message says which)."""


def overlay_path(clip, aeon=AEON):
    return os.path.join(aeon, CLIPS_REL, clip, OVERLAY_NAME)


def overlay_rel(clip):
    """The path build.sh passes, relative to the aeon root (sigil resolves it against
    the working directory, and build.sh runs from the root)."""
    return os.path.join(CLIPS_REL, clip, OVERLAY_NAME)


def clip_shapes(aeon=AEON):
    """The clip shapes' ROM stems, read off build.sh's S2CLIP block the way
    tools/gate_cut_shape.py reads off-canonical shapes: the standalone `ROM_NAME="..."`
    literals. Derived, not restated, so a third clip shape is not silently left out of
    the max."""
    path = os.path.join(aeon, "build.sh")
    with open(path, encoding="utf-8") as f:
        names = [m.group(1) for line in f for m in [_BUILD_ROM_NAME.match(line)] if m]
    if len(names) < 2 or len(set(names)) != len(names):
        raise Unmeasurable(
            f"build.sh spells {names!r} as the S2CLIP ROM names; expected the plain and "
            f"DEBUG shapes as two distinct `ROM_NAME=\"s4.s2clip...\"` literals. The max "
            f"over the clip's shapes cannot be taken over a shape list this cannot read.")
    return names


def map_anchor_rows(aeon=AEON):
    """name -> the map.toml `[[anchor]]` row (a dict), for the two overlaid anchors."""
    path = os.path.join(aeon, MAP_REL)
    with open(path, "rb") as f:
        doc = tomllib.load(f)
    out = {}
    for row in doc.get("anchor", []):
        if row.get("name") in ANCHORS:
            if row["name"] in out:
                raise Unmeasurable(f"{MAP_REL} declares `{row['name']}` twice; an overlay "
                                   f"row could not say which it replaces")
            out[row["name"]] = row
    missing = [n for n in ANCHORS if n not in out]
    if missing:
        raise Unmeasurable(f"{MAP_REL} declares no `[[anchor]]` named {missing}")
    return out


def parse_overlay(path):
    """(anchors {name: at}, measured {shape: (packed_end, rule)}, rows {name: row})
    from an `anchors.toml`. The rows are real TOML (sigil reads them); the `# measured:`
    lines are this tool's own derivation record, comments so sigil never sees them."""
    with open(path, "rb") as f:
        raw = f.read()
    try:
        doc = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
        raise Unmeasurable(f"{path}: not TOML ({e})")
    extra = set(doc) - {"anchor"}
    if extra:
        raise Unmeasurable(f"{path}: top-level key(s) {sorted(extra)}; an overlay holds only "
                           f"[[anchor]] rows (sigil refuses anything else)")
    rows = {}
    for row in doc.get("anchor", []):
        if row.get("name") in rows:
            raise Unmeasurable(f"{path}: two rows for `{row.get('name')}`")
        rows[row.get("name")] = row
    measured = {}
    for line in raw.decode("utf-8").splitlines():
        m = _MEASURED.match(line)
        if m:
            measured[m.group("shape")] = (int(m.group("end"), 16), int(m.group("rule"), 16))
    return {n: r.get("at") for n, r in rows.items()}, measured, rows


def render_overlay(clip, measurements, map_rows):
    """The `anchors.toml` text for `measurements` ({shape: record}). Pure."""
    rules = {s: bganim_room.rule_anchor(r["packed_end"]) for s, r in measurements.items()}
    dac = max(rules.values())
    binding = sorted(s for s, v in rules.items() if v == dac)
    values = {bganim_room.ANCHOR_NAME: dac,
              bganim_room.SOUND_ANCHOR_NAME: dac + bganim_room.SOUND_BANK_OFFSET}
    out = [
        f"# GENERATED by tools/clip_anchors.py --derive --clip {clip}. Do not hand-edit:",
        "# the build re-derives this shape's rule value and fails STALE when it differs",
        "# from the `# measured:` line below. Re-derive after building BOTH clip shapes:",
        f"#   S2CLIP={clip} ./build.sh; DEBUG=1 S2CLIP={clip} ./build.sh",
        f"#   python3 tools/clip_anchors.py --derive --clip {clip}",
        "#",
        "# This clip's own sound-bank positions (owner ruling d-35-revised,",
        "# clip-overlay-file), handed to `sigil build` as --anchor-overlay on S2CLIP",
        "# builds of this clip only; map.toml is untouched.",
        "# Rule (map.toml BANK PLACEMENT RULE, tools/bganim_room.py rule_anchor):",
        "#   dac_banks = align_up(packed_end + reserve + grace, 0x8000), max over the",
        "#   clip's shapes; sound_bank = dac_banks + 0x10000.",
    ]
    for shape in sorted(measurements):
        r = measurements[shape]
        out.append(f"# measured: shape={shape} packed_end=0x{r['packed_end']:X} "
                   f"rule=0x{rules[shape]:X} rom_crc={r['rom_crc']} rom_size={r['rom_size']}")
    out.append(f"# binding shape: {', '.join(binding)}")
    for name in ANCHORS:
        base = map_rows[name]
        out += ["", "[[anchor]]", f'name = "{name}"', f"at = 0x{values[name]:X}"]
        if "vma" in base:
            out.append(f"vma = 0x{base['vma']:X}")
        if "when" in base:
            out.append(f'when = "{base["when"]}"')
    return "\n".join(out) + "\n"


def verdict(overlay_text_path, shape, measured_rule, map_rows):
    """(code, lines) for one shape's measured rule value against an overlay file."""
    anchors, measured, rows = parse_overlay(overlay_text_path)
    problems = []
    if set(rows) != set(ANCHORS):
        problems.append(f"it holds rows {sorted(rows)}; a derived overlay holds exactly "
                        f"{list(ANCHORS)}")
    for name in ANCHORS:
        if name in rows:
            for key in ("vma", "when"):
                if rows[name].get(key) != map_rows[name].get(key):
                    problems.append(f"`{name}` {key} = {rows[name].get(key)!r} but "
                                    f"{MAP_REL} says {map_rows[name].get(key)!r}")
    if not measured:
        problems.append("it carries no `# measured:` line, so it was not written by "
                        "`derive` (hand-written, or the header was edited away)")
    else:
        want = max(rule for _end, rule in measured.values())
        if anchors.get(bganim_room.ANCHOR_NAME) != want:
            problems.append(f"`dac_banks` is {_hex(anchors.get(bganim_room.ANCHOR_NAME))} "
                            f"but the max of its own `# measured:` rules is 0x{want:X}")
        snd = anchors.get(bganim_room.SOUND_ANCHOR_NAME)
        dac = anchors.get(bganim_room.ANCHOR_NAME)
        if dac is not None and snd != dac + bganim_room.SOUND_BANK_OFFSET:
            problems.append(f"`sound_bank` is {_hex(snd)}, not dac_banks + "
                            f"0x{bganim_room.SOUND_BANK_OFFSET:X}")
    if shape not in measured:
        problems.append(f"it records no measurement for this shape ({shape}); it was "
                        f"derived over {sorted(measured)}")
    elif measured[shape][1] != measured_rule:
        problems.append(
            f"this shape's rule value is 0x{measured_rule:X} now, and the file was derived "
            f"when it was 0x{measured[shape][1]:X} (packed end then 0x{measured[shape][0]:X}). "
            f"The clip's data "
            f"{'GREW' if measured_rule > measured[shape][1] else 'SHRANK'} across a bank "
            f"boundary since the last derive.")
    return (STALE if problems else FRESH), problems


def _hex(v):
    return "(absent)" if v is None else f"0x{v:X}"


def record_path(rom):
    stem = rom[:-len(".bin")] if rom.endswith(".bin") else rom
    return stem + RECORD_SUFFIX


def _sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _crc_size(path):
    with open(path, "rb") as f:
        data = f.read()
    return f"{zlib.crc32(data) & 0xFFFFFFFF:08x}", len(data)


def placed_islands(lst):
    """name -> placed LMA of each overlaid anchor's island, from the listing."""
    labels = bganim_room.lst_labels(lst)
    phases = {}
    with open(lst, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = _PHASE.match(line.rstrip("\n"))
            if m:
                phases.setdefault(m.group(1), int(m.group(3), 16))
    out = {}
    dac_label = ISLAND_LABEL[bganim_room.ANCHOR_NAME]
    snd_label = ISLAND_LABEL[bganim_room.SOUND_ANCHOR_NAME]
    if dac_label not in labels:
        raise Unmeasurable(f"{lst} defines no {dac_label}; the dac_banks island is not "
                           f"where this check looks for it")
    if snd_label not in phases:
        raise Unmeasurable(f"{lst} has no `PHASE {snd_label} ...` row; the sound bank's "
                           f"LMA cannot be read (its label column holds the VMA)")
    out[bganim_room.ANCHOR_NAME] = labels[dac_label]
    out[bganim_room.SOUND_ANCHOR_NAME] = phases[snd_label]
    return out


def check(clip, lst, rom, built_after, aeon=AEON, out=sys.stdout):
    """The in-build check. Returns the exit code."""
    v = artifact_provenance.check_pair(rom, lst, built_after=float(built_after))
    if not v.fresh:
        raise Stale(v.render("clip_anchors"))
    print(f"  provenance FRESH — {os.path.basename(lst)} and {os.path.basename(rom)}: "
          f"written by this build and their Source Digest reproduces", file=out)
    shape = os.path.basename(lst)[:-len(".lst")]
    if shape not in clip_shapes(aeon):
        raise Unmeasurable(f"{lst} is not a clip shape's listing ({clip_shapes(aeon)})")
    map_rows = map_anchor_rows(aeon)
    ov_abs, ov_rel = overlay_path(clip, aeon), overlay_rel(clip)
    has_overlay = os.path.exists(ov_abs)
    overlay_anchors = parse_overlay(ov_abs)[0] if has_overlay else None

    # Was the overlay APPLIED? The digest row says sigil read it; the islands say it
    # placed by it. Both are needed: a read that did not move anything is the silent case.
    digest = artifact_provenance.read_digest(lst)
    read = [r for r in digest["reads"] if os.path.normpath(r["path"]) == os.path.normpath(ov_rel)]
    if has_overlay and not read:
        raise Unmeasurable(
            f"{ov_rel} exists but {os.path.basename(lst)}'s Source Digest has no READ row "
            f"for it: sigil was not handed --anchor-overlay (build.sh's S2CLIP wiring), so "
            f"this ROM sits on map.toml's canonical anchors")
    if not has_overlay and read:
        raise Unmeasurable(f"{ov_rel} does not exist but the listing says sigil read it")
    effective = {n: (overlay_anchors or {}).get(n, map_rows[n]["at"]) for n in ANCHORS}
    placed = placed_islands(lst)
    wrong = [n for n in ANCHORS if placed[n] != effective[n]]
    if wrong:
        raise Unmeasurable(
            "the islands are not where the effective anchors say: "
            + "; ".join(f"{ISLAND_LABEL[n]} at 0x{placed[n]:X}, `{n}` is 0x{effective[n]:X}"
                        for n in wrong)
            + f" ({'overlay ' + ov_rel if has_overlay else MAP_REL})")

    r = bganim_room.rom_room(lst, aeon, rom_path=rom,
                             anchor_overlay=ov_abs if has_overlay else None)
    packed_end, rule = r["packed_end"], bganim_room.rule_anchor(r["packed_end"])
    crc, size = _crc_size(rom)
    record = {"clip": clip, "shape": shape, "packed_end": packed_end, "rule": rule,
              "rom": os.path.basename(rom), "rom_crc": crc, "rom_size": size,
              "lst": os.path.basename(lst), "lst_sha256": _sha256(lst),
              "anchors_in_force": effective,
              "overlay": ov_rel if has_overlay else None}
    with open(record_path(rom), "w", encoding="utf-8") as f:
        json.dump(record, f, indent=1, sort_keys=True)
        f.write("\n")

    print(f"clip_anchors [{shape}] clip {clip}: packed end 0x{packed_end:X} -> rule "
          f"dac_banks 0x{rule:X}; placed at 0x{placed[bganim_room.ANCHOR_NAME]:X} / "
          f"0x{placed[bganim_room.SOUND_ANCHOR_NAME]:X} "
          f"({'from ' + ov_rel if has_overlay else 'map.toml canonical anchors, no overlay'})",
          file=out)
    print(f"  measurement recorded: {os.path.basename(record_path(rom))}", file=out)
    if not has_overlay:
        print(f"  no {ov_rel}: this clip builds on the canonical anchors. To give it its "
              f"own, build both clip shapes and run python3 tools/clip_anchors.py --derive "
              f"--clip {clip}", file=out)
        return FRESH
    code, problems = verdict(ov_abs, shape, rule, map_rows)
    if code == FRESH:
        print(f"  {ov_rel}: FRESH for this shape (its `# measured:` rule for {shape} is "
              f"0x{rule:X})", file=out)
        return FRESH
    print("#" * 78, file=out)
    print(f"## clip_anchors: STALE — {ov_rel}", file=out)
    for p in problems:
        print(f"##   {p}", file=out)
    print(f"## This ROM was built on positions that are not this tree's derivation. Remedy:",
          file=out)
    print(f"##   build BOTH clip shapes (this one's measurement is already recorded), then",
          file=out)
    print(f"##   python3 tools/clip_anchors.py --derive --clip {clip}   and commit the file.",
          file=out)
    print("#" * 78, file=out)
    return STALE


def derive(clip, aeon=AEON, out=sys.stdout, write=True):
    """Write `anchors.toml` from the two measurement records. Returns the exit code."""
    shapes = clip_shapes(aeon)
    measurements = {}
    for shape in shapes:
        rom = os.path.join(aeon, shape + ".bin")
        lst = os.path.join(aeon, shape + ".lst")
        rec = record_path(rom)
        if not os.path.exists(rec):
            raise Unmeasurable(f"no measurement for {shape} ({os.path.basename(rec)}): build "
                               f"it first with the S2CLIP={clip} shape that writes {shape}.bin")
        with open(rec, encoding="utf-8") as f:
            r = json.load(f)
        if r.get("clip") != clip:
            raise Unmeasurable(f"{os.path.basename(rec)} measured clip {r.get('clip')!r}, not "
                               f"{clip!r}: the last {shape} build was another clip. Rebuild it.")
        if not (os.path.exists(rom) and os.path.exists(lst)):
            raise Unmeasurable(f"{shape}.bin/.lst missing; the record describes nothing on disk")
        crc, size = _crc_size(rom)
        if (crc, size) != (r["rom_crc"], r["rom_size"]) or _sha256(lst) != r["lst_sha256"]:
            raise Unmeasurable(
                f"{os.path.basename(rec)} describes a {shape} build that is no longer the one "
                f"on disk (record crc {r['rom_crc']} / {r['rom_size']} B, disk {crc} / {size} B"
                f", or the listing changed). Rebuild {shape} with S2CLIP={clip}.")
        measurements[shape] = r
    text = render_overlay(clip, measurements, map_anchor_rows(aeon))
    path = overlay_path(clip, aeon)
    for shape in shapes:
        r = measurements[shape]
        print(f"clip_anchors derive: {shape} packed end 0x{r['packed_end']:X} -> rule "
              f"0x{bganim_room.rule_anchor(r['packed_end']):X} (rom {r['rom_crc']})", file=out)
    if write:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"clip_anchors derive: wrote {os.path.relpath(path, aeon)}", file=out)
    return FRESH


def main(argv=None):
    # Flat flags, no mode word: the build lane is `--lst/--rom/--built-after` exactly as
    # every other `--built-after` consumer (tools/test_provenance_consumers.py drives it
    # that way), and `--derive` is the one writing mode, which argparse cannot reach by
    # a typo because it is a flag, not a string compared against a table.
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--clip", required=True, help="clip act id (games/sonic4/data/clips/<id>)")
    ap.add_argument("--derive", action="store_true",
                    help="write anchors.toml from both clip shapes' measurement records")
    ap.add_argument("--lst", help="check: this build's listing")
    ap.add_argument("--rom", help="check: this build's ROM")
    ap.add_argument("--built-after", help="check: the epoch this build started sigil")
    args = ap.parse_args(argv)
    checking = (args.lst, args.rom, args.built_after)
    if args.derive and any(v is not None for v in checking):
        ap.error("--derive reads the measurement records; it takes no --lst/--rom/--built-after")
    if not args.derive and any(v is None for v in checking):
        ap.error("the check needs --lst, --rom and --built-after (or pass --derive)")
    try:
        if args.derive:
            return derive(args.clip)
        return check(args.clip, args.lst, args.rom, args.built_after)
    except Stale as e:
        print(str(e), file=sys.stderr)
        return artifact_provenance.UNMEASURABLE
    except (Unmeasurable, bganim_room.Unmeasurable, artifact_provenance.DigestError,
            OSError, KeyError, ValueError) as e:
        print(f"clip_anchors: FAIL (could not measure) — {e}", file=sys.stderr)
        return BROKEN


if __name__ == "__main__":
    sys.exit(main())
