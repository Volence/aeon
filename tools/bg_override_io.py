"""Shared read/refuse/write for games/sonic4/data/editor_bg_override.json.

TWO tools rewrite this file wholesale -- tools/png_to_bg_override.py (PNG ->
layout/tiles, optionally palette) and tools/forest_bg_gen.py (procedural forest
-> layout/tiles/anims) -- and BOTH used to build a fresh dict and `json.dump`
it without ever reading the file. Each therefore destroyed the other's keys.

That is not hypothetical. It fired on master: at b0e5a661 the file carried two
real BgAnim bands (32x4 camera_x @ slot 0, 16x4 timer @ slot 128, 8 phases
each -- 192 animated slots). At dd93a840, the commit that introduced
png_to_bg_override.py and ran it, the file has only layout/tiles. The bands
were gone, and OJZ background animation has been dead in the ROM since. The
JSON is minified, so in `git --stat` the loss rendered as a single changed
line.

WHY REFUSAL AND NOT MERGE -- this is the terminal answer for these tools, not a
placeholder pending a ruling:

  `anims`, `tiles` and `layout` are NOT separable keys. Bands pack contiguously
  from slot 0 (inject_editor_bg.py) and DMA over the FRONT of the static tile
  blob, so a band's phase-0 art IS those slots' rest state. Measured on the
  b0e5a661 data: phases[0] == tiles[slot_base:slot_base+cols*rows] for both
  bands, exactly.

  So a read-modify-write that retained `anims` while regenerating layout/tiles
  from new input would pass every assert in inject_editor_bg.py, bake cleanly,
  and ship a ROM where the retained bands DMA stale phase art over whatever the
  new dedup placed in slots 0..191. Silent visual corruption that clears every
  gate -- strictly worse than the deletion, which at least is recoverable from
  git.

Hence: a tool carries only keys IT owns, and stops on anything else. Callers
must offer an --out/BG_OUT escape so a refusal never tempts anyone to delete
the bands just to get past it.
"""

import json
import os
import sys


def read_existing_override(path, owned_keys, tool):
    """Return the current override dict ({} if absent), refusing unowned keys.

    Call BEFORE the expensive generation work so an authoring mistake stops in
    milliseconds rather than after a full quantisation pass.
    """
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        return {}                       # first-ever run: nothing to preserve
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR [{tool}]: {path} is not valid JSON ({e}). Refusing to "
                 "overwrite it -- it may be hand-authored content or a truncated "
                 "write. Repair or delete it deliberately, then re-run.")
    if not isinstance(data, dict):
        sys.exit(f"ERROR [{tool}]: {path} is not a JSON object. Refusing to overwrite it.")

    unowned = sorted(set(data) - set(owned_keys))
    if unowned:
        sys.exit(
            f"ERROR [{tool}]: {path} contains key(s) this tool does not author: "
            f"{', '.join(unowned)}.\n"
            f"  {tool} rewrites this file and WOULD DESTROY them. This is exactly how\n"
            "  OJZ's two BgAnim bands were lost at dd93a840 (see docs/BUGS.md TOOL-01).\n"
            f"  {tool} authors only: {', '.join(sorted(owned_keys))}.\n"
            "  These keys are NOT independently mergeable: bands DMA over the front of\n"
            "  the static tile blob, so regenerating layout/tiles while retaining anims\n"
            "  would bake cleanly and ship SILENTLY CORRUPT art. Refusing is correct.\n"
            "  To generate anyway without touching this file, redirect the output\n"
            "  (--out <path> / BG_OUT=<path>) and merge deliberately by hand.")
    return data


def atomic_write_json(path, obj):
    """Write via a tmp sibling + rename, so a crash cannot truncate the file.

    Same idiom as tools/ojz_block_gen.py:201-206; required of generators by
    tools/EFFECTS_CONSUMER_CONTRACT.md §3.
    """
    data = json.dumps(obj).encode()
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)
