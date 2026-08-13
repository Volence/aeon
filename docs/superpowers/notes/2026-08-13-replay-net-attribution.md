# Replay-net desync — attributed 2026-08-13

**Verdict: PRE-EXISTING ON MASTER. Effects P2 contributes ZERO delta to the replay net.**
The re-record is owed to the **Knuckles C4** parcel, which is already merged.

## What the handoff expected, and why it was wrong

The 2026-08-13 Effects P2 handoff listed the replay re-stamp as owed at merge, with the
expected disposition "layout-induced -> re-stamp, because `Palette_State` moved the RAM".

That expectation contradicts the net's own design. `engine/system/replay.emp` makes the
curated hash **address-free by contract**: every span base is symbol-relative
(`extern("Player_1") + offsetof(Sst, ...)`), pointer fields are explicitly excluded
(`code_addr`, `mappings`, `anim_table`, `parent_ptr`, `sibling_ptr`, `frame_off`), and
any cell whose VALUE is an address is NORMALIZED at fold time (the free-stack cursors
fold as occupancy, `interact` folds as an `Object_RAM` offset). The module even records
the incident that forced this — the 2026-08-11 pool-resize desync, caused by folding two
raw cursors. A pure RAM slide is therefore supposed to be invisible to the hash, and
"layout-induced drift" should not be the default expectation for one.

It was not layout-induced. It is behavioural, and it is not this lane's.

## The measurement

Same fixture (`Replay_OJZ_Fixture`), same recipe, same oracle instance, one ROM swapped:

```
break GameState_OJZScroll_Init -> poke Replay_Ptr = fixture + REPLAY_HEADER_LEN(20),
Input_Source = INPUT_PLAYBACK(1) -> resume
```

| | effects-p2 `s4.debug.bin` (`f9b3d140`) | master `s4.debug.bin` (`d8e0c6c2`) |
|---|---|---|
| desync tick (`d1`) | `0x00000502` = **1282** | `0x00000502` = **1282** |
| actual hash (`d0`) | `BBB93779` | `BBB93779` |
| expected hash (`d2`) | `1F420103` | `1F420103` |
| ticks clean before the trap | 1282 (~20 checkpoints) | 1282 (~20 checkpoints) |

**Byte-identical on both builds**, at the same tick, after an identical clean prefix.
Two things follow:

1. **Effects P2 is neutral to the net.** If the palette parcel had disturbed any cell the
   curated hash covers, the two actual hashes would differ. They do not. The
   `Palette_State` +0x1E4 RAM slide is genuinely layout-proof, which is the hash
   contract working as designed.
2. **Master's replay net is already red.** It has been since the Knuckles C4 merge
   (`50d54512`).

## Why the signature says "behavioural", not "layout"

A layout or RAM-shift break desyncs at the **FIRST** checkpoint, because every checkpoint
is equally wrong — that is exactly what the 2026-08-09 desync did (tick 2, the whole
region stale). This one runs clean through 1282 ticks and roughly twenty checkpoints and
only then diverges. State agreed for most of the run and then genuinely parted, which is
a behaviour change late in the input timeline, not a relocation.

That is consistent with the cause: **Knuckles C4 changed player behaviour in nine ruled
ways** (`PSTATE_SLIDE` gaining its missing `ObjectMove`, the 1-3px climb recess
divergence, the glide floor-probe fix, the ledge-clamber terminal fix, the box-restore
exemption, dust priority/palette). Its own handoff listed the replay re-stamp under "Also
owed before/at merge" and it was never performed, so master has been carrying fixtures
recorded against pre-Knuckles behaviour.

## Disposition

- **Effects P2 merges on this evidence.** Its merge is not gated on the net, because it
  is provably neutral to it.
- **The re-record is a separate, owed parcel** against master, and it is the deliberate
  kind: the behaviour change was intentional and user-ruled, so the fixtures should be
  re-recorded to the new correct behaviour via the full runbook in
  `2026-08-09-replay-net-rerecord-ab.md` (oracle recording legs, aether-bus dumps,
  `tools/replay_pack.py`), not silently re-stamped.
- **Process note:** "the RAM moved, so expect hash drift" is not a safe default for this
  net. Check the hash contract first — it is designed to be layout-proof, so drift after a
  pure relocation is evidence of a NEW un-normalized address-valued fold, not of a benign
  re-baseline. And attribute before re-recording: running the same fixture on the previous
  merge base costs one ROM swap and settles ownership outright.
