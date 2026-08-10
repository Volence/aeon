# A/B evidence — `characters` module split (class PS)

Parcel: move the `CharacterDef` roster + shared player asset/art loaders out of
the `player_common` section into a new `characters` section
(`games/sonic4/player/characters.emp`), enabled by registering the
`games.sonic4.characters` `ModuleSpec` in sigil.

- aeon `feat/character-dispatch` — `c3c12257` (OLD side: `b6034471`)
- sigil `feat/characters-modulespec` — `286ff460` (OLD side: `9f6b6209`)

Class **PS** (pure-size / value-identical): code moved between sections; no
instruction bytes and no data values were intended to change.

| shape | OLD | NEW |
|---|---|---|
| `s4.debug.bin` | `crc=a28d3c56 len=428171` | `crc=f1ad473a len=428171` |
| `s4.bin` | `crc=4331b05e len=414153` | `crc=11504636 len=414153` |

Both lengths unchanged; the layout blast radius is confined to the player run
(`player_common` shrank $40, `PState_Ground/Air/Spindash` slid back $40, the new
`characters` section fills it). `TestStatic_Main`, `DeformTable_Zero`,
`HeightMaps`, `SoundTablesZ80_Head`, `Replay_OJZ_Fixture`, `BusError` and
`EndOfRom` are all at unchanged addresses.

## Drive (identical for both ROMs, reset-deterministic, zero human input timing)

1. breakpoint `GameState_OJZScroll_Init` (`$5E03C`) **added before** `reset`
2. `reset`, `wait_for_break`
3. poke `Input_Source = INPUT_PLAYBACK` (`$FF803A` = 1),
   `Replay_Ptr = Replay_OJZ_Fixture + REPLAY_HEADER_LEN` (`$FF8040` = `$0005E5AE`)
4. clear breakpoints, **then** add a write-watchpoint on `Replay_Done` (`$FF803C`)
5. `resume` → breaks at the fixture's terminal tick

The `Replay_OJZ_Fixture` stream is 1721 ticks with embedded per-checkpoint
hashes of a curated ADDRESS-FREE span of `Player_1`.

## Anchor: the fixture's terminal instruction (deterministic)

The watchpoint breaks at **`Input_Tick+118` (`$2652`) on BOTH ROMs** — same
instruction, same tick.

| observation | OLD | NEW | verdict |
|---|---|---|---|
| break site | `Input_Tick+118` | `Input_Tick+118` | same |
| `Player_1` SST, 80 B | see below | see below | **identical but `code_addr`** |
| visible plane (PNG) | `OLD.anchor.png` | `NEW.anchor.png` | **byte-identical (`cmp`)** |
| `Replay_Done` | `$FF` | `$FF` | fixture completed, no desync |

```
OLD 011C 019FCB00 023D9A00 05B4 0000 81 00 00028BC0 03C0 1327 00 00 0002694A ...
NEW 0106 019FCB00 023D9A00 05B4 0000 81 00 00028BC0 03C0 1327 00 00 0002694A ...
     ^^^^ code_addr only
```
`code_addr` is a 16-bit offset from `ObjCodeBase` — definitionally an address,
and one of the fields `engine/system/replay.emp` EXCLUDES from its hash for
exactly this reason. Position, velocity, mappings, art_tile, box, anim state,
`mapping_frame`, `frame_off` and the whole `PlayerV` window are byte-identical.

Additional anchor: whole-WRAM hash at `GameState_OJZScroll_Init` **before** the
poke was `crc32=0x24EDCE23` on both ROMs.

Positive behavioural half: both ROMs ran the fixture to `Replay_Done=$FF` with no
`REPLAY DESYNC`. Since the checkpoint hash covers `anim_frame`/`anim_timer`/
`mapping_frame`/`prev_frame`/`sprite_piece_count` and the entire `PlayerV`
window, and a DEBUG mismatch is a hard `raise_exception`, both builds are proven
identical to the SAME recorded reference at every checkpoint across 1721 ticks.

## TWO METHODOLOGICAL TRAPS HIT — record these

**1. A wall-clock sleep is not an anchor, and a passing control can be a
collision.** The first attempt captured a screenshot after a fixed 33 s sleep,
i.e. AFTER the fixture ended and the game resumed free-running with the idle
animation advancing. OLD vs NEW differed by 60 bytes in a 10x7 box at Sonic's
foot. A control run (OLD vs a second OLD, same 33 s) came back **0 bytes
different**, which appeared to prove the metric deterministic and the difference
real. It was not: both OLD runs merely happened to land on the same idle frame.
The same SST read across runs showed `anim_frame` `$0C` vs `$0F` vs `$01`,
proving the post-fixture sample point drifts. At the true deterministic anchor
the screens are byte-identical. **A control that passes does not establish
determinism — it can be a collision. Anchor on an instruction, never on elapsed
time.**

**2. A whole-WRAM hash is NOT a validity metric when code moves sections.**
WRAM holds `code_addr` for every live object, so it necessarily changes.
OLD `0x5E810513` vs NEW `0x04221825` at the terminal anchor is expected and
correct. Compare address-free spans, or diff field-by-field.

**3. Watchpoint ordering wedges the emulator.** Adding the `$FF803C` write
watchpoint BEFORE `reset` makes it fire inside the boot RAM clear and leaves
oracle with `PC=SP=0xFFFFFFFF` and a frozen frame token; `breakpoint_clear` +
`reset` do NOT recover it (watchpoints survive `breakpoint_clear`). Recovery is
kill + relaunch. **Add the watchpoint AFTER the boot clear and after the poke.**

## Artifacts

`scratchpad/ab-characters/` — `OLD.debug.bin`, `NEW.debug.bin`,
`OLD.anchor.png`, `NEW.anchor.png` (byte-identical), plus the confounded
post-sleep captures `OLD.final.png` / `OLD2.final.png` / `NEW.final.png` kept as
the record of trap #1.
