#!/usr/bin/env python3
"""game_shape_feature — one `[shapes.<row>].features` value of a game description, for
build.sh (G0b Task 8).

WHY THIS EXISTS. build.sh decides lanes of its own from the shape's sound feature (the
`emit_sound_blob` preflight, the emitter-identity line). For a game sigil builds from its
description (`sigil build --project games/<g> --shape <row>`), that feature is the
description's fact (`games/<g>/game.toml`), not a shell default: demo's
`SOUND_DRIVER_ENABLED=0` lived in `games/demo/build.conf` until the cutover folded it into
`[shapes.*] features = { sound = false }`, which sigil already reads. build.sh asks here, so
the shell and the assembler read one fact.

The row's `extends` chain is followed (the root's features first, each shape down the chain
overriding what it states), with a cycle refused, as sigil's `resolve_shape` does.

    game_shape_feature.py --game demo --shape release --feature sound   -> prints 0 or 1
    game_shape_feature.py --game sonic4 --shape config-a --shell        -> build.sh's facts

`--shell` (G0b Task 10, the sonic4 cutover) prints every fact build.sh takes from the row,
one `DESC_<NAME>=<value>` assignment per line, for build.sh to `eval`: the three features
(`DESC_DEBUG`, `DESC_CRASH_REPORT`, `DESC_SOUND`, 0 or 1), the two sound dev opt-ins the
shape's defines turn on (`DESC_SOUND_DEBUG_HOTKEYS`, `DESC_SOUND_DBG_MIRROR`: the define's
value, 0 when the row and the game's `[defines]` do not set it, which is what sigil builds
then), `DESC_FIXTURE` (sticky down an `extends` chain, as sigil's `resolve_shape` has it) and
`DESC_STEM`, the row's `[outputs]` stem, empty when the description gives the row none (a
shape build.sh does not write).

Exit 0 with the value; 1 with the reason when the description, the row or the feature is
missing (never a default: a guessed sound axis decides whether a lane runs).
"""

import argparse
import pathlib
import re
import sys
import tomllib

AEON = pathlib.Path(__file__).resolve().parent.parent

#: The defines build.sh's environment knobs of the same name stand for.
SHELL_DEFINES = ("SOUND_DEBUG_HOTKEYS", "SOUND_DBG_MIRROR")
_STEM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _load(game, shape, aeon):
    path = pathlib.Path(aeon) / "games" / game / "game.toml"
    try:
        desc = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ValueError("cannot read %s: %s" % (path, e))
    shapes = desc.get("shapes", {})
    chain, row = [], shape
    while row is not None:
        if row in chain:
            raise ValueError("%s: [shapes.%s] extends cycle: %s" % (path, shape, " -> ".join(chain + [row])))
        if row not in shapes:
            raise ValueError("%s declares no [shapes.%s] row" % (path, row))
        chain.append(row)
        row = shapes[row].get("extends")
    return path, desc, shapes, chain


def feature(game, shape, name, aeon=AEON):
    path, _desc, shapes, chain = _load(game, shape, aeon)
    value = None
    for row in reversed(chain):
        value = shapes[row].get("features", {}).get(name, value)
    if not isinstance(value, bool):
        raise ValueError("%s: [shapes.%s] states no boolean `%s` feature (chain %s)"
                         % (path, shape, name, " -> ".join(chain)))
    return value


def shell_facts(game, shape, aeon=AEON):
    """The facts build.sh takes from `[shapes.<shape>]`, as an ordered list of (name, value)."""
    path, desc, shapes, chain = _load(game, shape, aeon)
    facts = [("DESC_DEBUG", feature(game, shape, "debug", aeon)),
             ("DESC_CRASH_REPORT", feature(game, shape, "crash_report", aeon)),
             ("DESC_SOUND", feature(game, shape, "sound", aeon))]
    defines = dict(desc.get("defines", {}))
    for row in reversed(chain):
        defines.update(shapes[row].get("defines", {}))
    for name in SHELL_DEFINES:
        v = defines.get(name, 0)
        if not isinstance(v, int) or isinstance(v, bool):
            raise ValueError("%s: define %s of [shapes.%s] is %r, not an integer" % (path, name, shape, v))
        facts.append(("DESC_" + name, v))
    facts.append(("DESC_FIXTURE", any(shapes[row].get("fixture", False) for row in chain)))
    stem = desc.get("outputs", {}).get(shape, "")
    if stem and not _STEM.match(stem):
        raise ValueError("%s: [outputs] %s = %r is not a plain file stem" % (path, shape, stem))
    facts.append(("DESC_STEM", stem))
    return [(k, int(v) if isinstance(v, bool) else v) for k, v in facts]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--game", required=True)
    ap.add_argument("--shape", required=True)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--feature")
    mode.add_argument("--shell", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.shell:
            for k, v in shell_facts(a.game, a.shape):
                print("%s=%s" % (k, v))
        else:
            print(1 if feature(a.game, a.shape, a.feature) else 0)
    except ValueError as e:
        print("game_shape_feature: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
