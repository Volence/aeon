# The plane-role swap, on screen — EFFECTS-W1 item 10b (2026-09-04)

Three captures, `s4.debug.bin` built at aeon `52be83a9`, headless, OJZ act 1, camera at
`Camera_X` 5824 with the scene frozen. Same machine, same frame budget between shots, nothing
reloaded — the only thing that changes between them is the `Parallax_Roles_Swapped` flag.

| file | flag | frame |
|---|---|---|
| `1-normal.png` | 0 | 828 |
| `2-roles-swapped.png` | 1 | 836 |
| `3-restored.png` | 0 again | 844 |

## What the machine says, and it is not in doubt

`tools/role_swap_witness.py`, same ROM: reg `$02` goes `$30 -> $38` and reg `$04` goes
`$07 -> $06` at the VDP shadow, and both come back on clear — every byte matching the value
folded from `VRAM_PLANE_A`/`VRAM_PLANE_B` through `vdp_base_shift`, derived rather than typed.
Of the 206 rows that are not animating on their own, **27 change** and **0 stay changed** after
the flag is cleared. Proven red by aiming the flag write at unrelated RAM: both arms fail.

So: the registers trade, the picture follows, and it goes back exactly.

## What a person has to decide, and why the pictures look so alike

**This scene is close to the worst place in the game to show this effect off.** Both planes are
carrying dense green foliage at similar scroll, so trading which one presents in front changes
very little that the eye can catch — the measured difference is a band around lines 64-91 (the
tree-trunk row, where the two planes' content genuinely differs) plus one row at the bottom.
The 27-of-206 figure and these images are the same fact seen two ways.

That is a statement about the scene, not about the mechanism. Nothing here suggests the swap is
broken; it suggests the demo wants somewhere the foreground and background do not look alike.

**The open question is taste and it needs a person:** does the swapped picture read as a clean
role trade — each layer keeping its own scroll feel, no seam and no snap — or does something
look wrong? No row-hash witness can answer that, and these are still frames, so they cannot show
scroll behaviour at all. If the answer is "I cannot tell from this", the useful next step is a
camera position where the two planes differ strongly, not a longer measurement.
