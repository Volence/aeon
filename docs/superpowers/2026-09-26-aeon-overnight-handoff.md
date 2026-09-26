# aeon handoff, overnight 2026-09-26

Written by the aeon overseer at a boundary, with nothing running. Master is `2ccbce9b` plus
this commit. Check `git fetch origin` first; this file is not the clock.

## What landed (details in `docs/lane-log.jsonl`, all landing_build finished=0 on the merged tree)

| merge | what |
|---|---|
| 67a7a374 | S2 music: per-channel header volume kept (EHZ mix +9.5 dB -> +0.9 dB vs real S2) |
| a2e6e256 | PRINTED-NOT-GATED residue (tools only, byte-neutral) |
| f136c486 | slope landing: air landings use the S2/S3K landing rule (`Player_SensorLand`) |
| ef365c11 | DEBUG PageCache_Audit amortised into idle-slot slices (straight flight lag 0) |
| 0fec1b75 | resident plain copy (OJZ baked physical; DEBUG diagonal 43 -> 14) |
| e6a00773 | PSG envelope byte 0 on the note-on tick (needed sigil 4ce2509d's blob-length split) |
| 3f310a1d | GPL-2: demand-page frame leak fixed (hold + release after a clean fill pass) |
| 4a7f3443 | GPL-1: stress bake takes the canonical pin rule; over-budget stress bake refuses |
| 2ccbce9b | SAH-3: entity-window two-axis slide was always correct; assert fixed |
| 3f573f88, af8e7381 | research: S2 clip loops/planes; general patch loop design (A3) |

Owner ROMs in the main checkout are built from `2ccbce9b`: s4 80d58257, s4.debug 89f380e0,
s4.s2clip 85ec6e7a, s4.s2clip.debug be774dc5.

## Waiting on the owner (cards in `docs/decisions.jsonl`)

- **S2CLIP-PLANE-SWITCH**: branch `parcel/s2clip-plane-switch` tip `0a2dc632` (on bc72c85b),
  landing_build green there. Try-out ROMs are in `~/sonic_hacks/tryout/s2-loops/`. If he picks
  `line-table`, rebase it onto master (it predates 3f310a1d and later; `engine/structs.emp` Act
  and `player_common.emp` are the likely conflicts), re-run landing_build and the loop witness,
  and land it. Tell sigil about the new names (`LayerLine`, `Act.act_layer_lines`,
  `Player_LayerLines`) and send aurora a landing notice.
- **S2CLIP-DRUM-LEVEL**: his listen after the volume fix.
- **ROLL-FEEL**: S3K vs S2 roll rules.
- **GPL-A3-BUILD**: build the row/column-mask replacement for the general loop's refcounts
  (prototype `proto/gpl-rowlive3` 94cc63fa). The GPL-2 hold's release test ("refcount 0")
  becomes "in no mask" under A3.
- **SP6-MODULATION-DIVERGENCE**: the spring A/B, unchanged.

## Owner-free rows a successor can take

- **SAH-3a**: the DEBUG warp spawns window objects twice. It resets the loaded bits but doesn't
  delete live objects. This affects aurora's play-from-cursor. See DEFERRED_WORK under SAH-3.
- **SHARED-CONFIG-BARE**: prove or refute that `git bisect run` over build.sh flips
  `core.bare`. Until then, briefs should say not to bisect-run over build.sh, and never to
  write the shared config.
- GATE-PREDICATE-VS-PROMISE GPP rows, RPC-1..3, AA-2..6, SAH-5, the two new PRINTED-NOT-GATED
  cases, and HCZ2's import gaps vs S3K (from the PSG parcel). All are in DEFERRED_WORK.

## Traps met tonight (put them in every brief)

- `/tmp` is over the disk quota (EDQUOT). Use `TMPDIR=/home/volence/.cache/aeon-tmp`, and
  delete nothing in /tmp.
- Agents end their turn "waiting for a notification" and stall. Every brief says: poll your
  own log with a bounded loop.
- The shared sigil pair (1edd31eb / 3c3bd0ba) reads sigil's locked worktree
  `.worktrees/land-4ce2509d` at runtime. If demo or stress builds fail with "read frozen
  table ...", that worktree is gone: ask sigil.
- `test_check_does_not_perturb_generated_sound_artifacts` fails if the tree's previous build
  was a clip, stress or fresh demo build. Build canonical first.
- Aurora's currency rows go red on any landing touching the files it vendors. Send one notice
  per landing, listing the paths.
