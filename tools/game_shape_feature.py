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

Exit 0 with the value; 1 with the reason when the description, the row or the feature is
missing (never a default: a guessed sound axis decides whether a lane runs).
"""

import argparse
import pathlib
import sys
import tomllib

AEON = pathlib.Path(__file__).resolve().parent.parent


def feature(game, shape, name, aeon=AEON):
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
    value = None
    for row in reversed(chain):
        value = shapes[row].get("features", {}).get(name, value)
    if not isinstance(value, bool):
        raise ValueError("%s: [shapes.%s] states no boolean `%s` feature (chain %s)"
                         % (path, shape, name, " -> ".join(chain)))
    return value


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--game", required=True)
    ap.add_argument("--shape", required=True)
    ap.add_argument("--feature", required=True)
    a = ap.parse_args(argv)
    try:
        print(1 if feature(a.game, a.shape, a.feature) else 0)
    except ValueError as e:
        print("game_shape_feature: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
