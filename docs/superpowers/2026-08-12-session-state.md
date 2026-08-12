# Session state — 2026-08-12 (overnight run)

Supersedes the 2026-08-11 Knuckles cold-start brief for STATUS. That brief
(`2026-08-11-sfx-and-knuckles-handoff.md`) remains the reference for standing
operational facts — build env, the replay-gate recipe, oracle policy, the parcel
ritual, and its §6 corrections to the 2026-08-10 handoff. All still accurate.

## Repo state

| repo | branch | HEAD | pushed? |
|---|---|---|---|
| aeon | `master` | the Knuckles merge | **no** |
| sigil | `master` | `14049a9c` (chain 102) | **no** |

Nothing is pushed, as usual. Both masters moved together and are consistent —
sigil's registry names three modules that exist only on aeon master, so the two
must always be merged as a pair.

Work happened in dedicated worktrees (`aeon/.worktrees/knux`,
`sigil/.worktrees/knux`) because a second agent was live in the main trees on
the effects/parallax branch. **Leave the main trees alone while that is true.**
`sigil/.worktrees/knux` still exists on branch `knuckles`, fully merged — safe
to remove.

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
./build.sh              # plain  crc=77a68bbd len=692365
DEBUG=1 ./build.sh      # debug  crc=5f51e251 len=706778
DEBUG=1 ./build.sh demo # demo   crc=d9deebfa len=97728
```

## Landed this session

**1. `feat/character-dispatch` MERGED to master** (`9f59f5c7`) — 67 commits, the
hygiene boundary the previous session recommended taking before Knuckles.
CharacterDef dispatch, playable Tails with flight and the twin-tail appendage,
the VRAM registry (T0), and the dust effects. Gated before merging: all four
build shapes, aeon pytest 941, sigil workspace 3667/0, and both replay fixtures
(`Replay_Done=$FF`, clean frame). The merge is content-identical to the gated
branch tip, so those gates transfer exactly.

**2. Knuckles Task 9 COMPLETE and merged** (aeon `a4626d94`, sigil chain 102).
The parked WIP `357f4543` adapted and landed, plus the whole sigil half it was
missing. Knuckles is playable — his own art, mappings, animations, boxes,
physics row (jump force `$680 -> $600`, the only delta) and his own CRAM line 0.
`cd_ability` is still `Ability_None`, so today he plays as a Sonic with a weaker
jump.

Emulator-verified: the hotkey resolves `Character_ID=2` / `Player_Chardef=$11074`
and he renders in his own colours, running, mid-motion. **The palette round-trip
is the load-bearing check and it passes** — cycling back to Sonic restores blue,
which is exactly the case a `cd_palette` of 0 on the Sonic/Tails records would
have failed. Both replay fixtures still pass unchanged as Sonic.

The parked sigil WIP branch `wip/knuckles-task9` was NOT used — it predates the
dust parcels and would have reverted them. The sigil side was rebuilt from
current master.

**3. The C4 research banked, and the plan corrected.** See below — this is the
most valuable thing to read before touching Task 10.

## The frozen-table ruling, and the method worth reusing

Knuckles' art (`0x226C8`) took the same ROM-tail exile Tails' 132 KB took, and
overran the packer's `0x400` island margin in all five sonic4 shapes.

**The method:** do not hand-compute the shift. Every failure reports the MEASURED
packed base against the stale provisional, so a small loop — read the delta off
the error, shift that label and everything at or after it, rebuild, repeat —
converges in one round per shape. That mattered here: **config_b came out
+0x22890, not +0x226D0**, because the sound-OFF shape has no dac anchor to absorb
the run before the tail. Assuming uniformity would have shipped that shape wrong.

The audit is that the freeze re-derives it exactly, and it did: all seven tables
re-derived, and a second derive against a snapshot was a byte-for-byte no-op.
The two convergence scripts are in this session's scratchpad; they are ~90 lines
each and trivial to rewrite from the description above.

## NEXT — the immediate queue

**Task 10 (glide + slide) is the next thing, and it is bigger than the plan says.**
Read `2026-08-12-knuckles-c4-research.md` before writing any code. In order:

1. **The ability-box mechanism (§0 of the research) — a BLOCKER.** The 10x10
   ability box does not compose with `PHook_EnsureStanding`/`EnsureBall`. Land
   the fix as Task 10's opening step, WITH the glide as its first consumer (a
   `cd_ability_wh` nothing reads is the dormant scaffold the house style
   forbids). Sonic and Tails must come out behaviour-identical — gate on the
   replay fixtures.
2. **Glide + glide-fall + slide.** Note the third state, and note that the
   largest piece of work — glide's own terrain pass — is in none of the plan's
   four steps. Interim wall-contact behaviour should be S3K's own `.fail` path,
   so Task 11 replaces one branch instead of rewriting.
3. **Task 11 (climb + ledge).** Its Step 1, the one the plan calls "the hard
   part", is already done: no sensor work is needed. Hard-blocked on 2.

Then Task 12 (docs + the final C4 merge).

**Scope honestly.** The 2026-08-11 brief's judgement still holds and this session
confirmed it: task 9 was a solid overnight unit, and 10-11 are each comparable to
Tails' flight. Land one properly rather than half-landing both.

## Also open (unchanged, still valid)

- **ROM re-layout** ("banks late, data unbounded") — already approved, and now
  with a second data point: the character-art exile has happened twice, the plain
  ROM is 676 KB against 414 KB before Tails, and each exile costs a five-shape
  hand ruling. Still probably the highest-value engine parcel.
- **VRAM linker T1** (the packer in sigil's chainer), **C4-3 famine fix**,
  **sound packages 5 and 6**, the **S3K drum-kit content pass**, and the
  **`art_tile` hash normalization** rider.
- `Player_Chardef` is a single global, not per-slot — must be fixed before C3
  (the CPU follower), which is blocked on its own VRAM ruling anyway.
- The `mulu`/`divu` convention-vs-code discrepancy is still the user's call, and
  Task 10 will add a THIRD documented exception (`muls.w` for `cos * gsp`), so a
  ruling would be timely.

## One thing to watch

A second agent was working the effects/parallax branch in parallel, out of
`aeon/.worktrees/effects-p1`. Two hazards, neither hit but both real:

1. **The sigil repo is shared.** Registering a module in `native.rs` changes the
   module list for EVERY aeon tree, so a branch that lacks those `.emp` files
   stops building. This session kept its sigil work on a branch in a worktree
   until merge time for exactly that reason; do the same, and expect that
   branches cut before the character merge need a rebase before they build.
2. **Oracle is a single instance.** Only one session can drive it at a time.
