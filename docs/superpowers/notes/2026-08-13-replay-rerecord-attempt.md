# Replay re-record — attempted 2026-08-13, STOPPED deliberately. Read before retrying.

**Status: master's replay net is still RED.** The re-record was attempted and abandoned
on purpose; nothing was half-applied (no repo file changed, the record buffers are scratch
RAM cleared on reset). The blocker is TOOLING, not the engine.

Attribution and the corrected premise are in
`2026-08-13-replay-net-attribution.md` — the desync is master's, inherited from Knuckles
C4 (`50d54512`), and it is behavioural, not layout-induced.

## The desync is now pinned to a cause

Dumping the standing fixture makes it exact:

```
@tick 1280  hash 0x1f420103      <- the trap reported d2=1F420103 at d1=0x502 (1282)
runs: ... tick 1212  byte 0x02  x25   <- DOWN held = spindash charge
```

Checkpoints at 1088/1152/1216 pass; 1280 fails. The input at that point is a spindash
charge, and Knuckles C4 changed spindash **dust** (priority band 5 =
`PLAYER_PRIORITY_BAND + 1`, plus the character line-0 palette permute and the generalised
`PHook_EnsureStanding`). Those are shared player code, not Knuckles-only — which is why a
Sonic fixture diverges. **Intended change; the fixture is simply stale.**

## Why interactive-MCP recording does NOT work — measured, not guessed

`Input_Source = INPUT_RECORD (2)` taps `Ctrl_1_Held` per tick into `Replay_Record_Buf`
and logs `(Logic_Tick, hash)` every 64 ticks into `Replay_Check_Log`. Sound mechanism.
Driving it from interactive tool calls is the problem:

| trap | detail |
|---|---|
| **`emulator_hold` fails ~50% of the time** | Every phase needed 1-3 retries. ALWAYS verify `Ctrl_1_Held` (`$FF802C`) after a hold. |
| **`hold` ADDS, it does not replace** | Holding `right` while `b` was down gave `0x18`, not `0x08`. Needs an explicit release between phases. |
| **`hold(down=false)` is also flaky** | Releasing `["a","right"]` left `0x4A` — both still held. `release_all` is more reliable. |
| **the `c` button never registers** | Three attempts, no effect, while `a`/`b`/directions worked in the same session. Possibly a name the tool ignores silently. Use `a`/`b` for jumps (same code paths). |
| **round-trip ≈ 60-120 emulated ticks** | The record ring is `REPLAY_RECORD_TICKS = 8192` (~2.3 min). The FIRST take filled the entire ring on button debugging alone, before reaching the spindash phase. |

Net effect: phases bleed into one another (the intended "run right" recorded as `0x18`
B+right; the jump as `0x58` A+B+right). The stream is *valid and deterministic*, but its
phases do not cleanly exercise the paths they are named for.

## Why that was a reason to STOP rather than ship it

1. **Both fixtures must be replaced together** for the net to go green. The slide fixture
   is the harder one — it exists to prove `EntityWindow_Slide` fires in all FOUR crossing
   directions, and a 50%-flaky driver will silently produce one that misses crossings.
2. A fixture that replays deterministically but does not exercise its named coverage is a
   **vacuous gate** — green, and testing nothing. That is precisely the failure class
   fixed in three other places this same day (see
   [[reference-gate-measures-the-placer]]). Trading a KNOWN-red net for a
   silently-vacuous green one is a bad trade.

## What the retry needs

**A scripted input driver, not interactive calls** — something that sets `Ctrl_1_Held`
at exact `Logic_Tick` boundaries so the timeline is reproducible and phase-accurate. The
old fixture's own run list is the spec to hit:

```
0:0x00 x1024 · 1024:0x10 x3 · 1027:0x08 x110 · 1137:0x28 x8 · 1145:0x08 x67
1212:0x02 x25 · 1237:0x22 x6 · 1243:0x02 x5 · 1248:0x22 x5 · 1253:0x08 x99
1352:0x04 x107 · 1459:0x44 x9 · 1468:0x04 x58 · 1526:0x01 x78 · 1604:0x08 x117
```

Note several runs are 3-9 ticks long — unreachable by hand at ~100 ticks per round trip.

**A cheaper alternative worth considering first:** the INPUT stream is unchanged and only
the HASHES are stale, so the stream does not need re-driving at all. Host the existing
fixture in RAM (`Replay_Record_Buf` at `$FFB81C` is free during playback), point
`Replay_Ptr` at it, and iterate: run -> trap -> read `d0` (actual hash) and `d1` (tick) ->
patch that checkpoint in the RAM copy -> re-run. Only 7 checkpoints (1280..1664) are
stale, so ~7 iterations of ~30 s, no rebuild and no scaffold, and the proven input
timeline is preserved byte-for-byte. **This is the recommended route.** (Oracle has no
register-write tool, so the expected value cannot simply be poked to match in-place.)

## Reference values

- Recording anchor: bp `GameState_OJZScroll_Init` (`$A1734`), poke `Input_Source` (`$FF803A`).
- `Replay_Record_Idx` `$FFB818` · `Replay_Check_Idx` `$FFB81A` ·
  `Replay_Record_Buf` `$FFB81C` (8192 B) · `Replay_Check_Log` `$FFD81C` (8 B/entry).
- `Replay_Ptr` `$FF8040` · `Replay_Done` `$FF803C` · `Logic_Tick` `$FF8004`.
- `core_hash` for the current master debug ROM = crc32 of `ROM[0, Replay_OJZ_Fixture)` =
  **`0x0C8A0CBA`** (`Replay_OJZ_Fixture` = `$A1DA0`).
- `tools/replay_pack.py --selftest` PASSES; `pack --raw <recbuf> --checks <checklog>
  --ticks N --core-hash H --out F`; both inputs are raw memory dumps.
- Sanity check that the recorder works: the first two logged hashes were `1D375066` @
  tick 2 and `0D37D06A` @ tick 66, matching the OLD fixture's tick-0/64 hashes exactly —
  at-rest state is unchanged, so only the post-spindash divergence is real.
