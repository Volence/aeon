# ROM re-layout #2 — "give extra room" — 2026-09-04

Owner ruling, verbatim: **"Yeah re-layout and give extra room."** The trigger was
`tools/bganim_room.py --gate` failing the `DEBUG=1` shape by **30 bytes**.

**Status: the aeon half is complete and the branch is RED on both sonic4 shapes until sigil
moves two frozen-table rows.** That is a placement *mechanism*, not the retired paired-freeze
ceremony; it was measured in both directions and is written out in full below. Nothing here
should be merged before the sigil hand-off lands.

Branch `parcel/rom-relayout-more-room`, worktree `/home/volence/sonic_hacks/.aeon-relayout2`,
from master `afd6f784`.

---

## 1. What fired

```
bganim_room [s4.debug.lst]:
  Art_Sonic 0x7355E + 101056 = 0x8C01E; anchor 0x90000
  ROM room 16354 B free + 8330 B the section already holds = 24684 B for ojz_bg_anim
bganim_room: FAIL — the bank placement rule is broken in this shape.
  `dac_banks` is declared at 0x90000 but packed data ends at 0x8C01E,
  leaving 16354 B < DATA_GROWTH_RESERVE 16384 B.
```

Release passed with 18,756 B. DEBUG binds, and DEBUG is the shape the owner tests on.

---

## 2. The structural defect the minimum move would not have fixed

The 08-26 rule was `dac_banks = align_up(packed_end + RESERVE, 0x8000)`, and the gate fails at
`room < RESERVE`. So the growth the tree can absorb before the gate re-fires is

```
align_up(end + R) - end - R
```

— the **align_up remainder**. That is a draw on `end mod 0x8000`, uniform on `[0, 0x8000)`, and
**raising RESERVE does not raise it**, because the demand and the anchor move together.

Measured at today's binding end `0x8C01E`:

| RESERVE | `dac_banks` | room | grace above the reserve |
|---|---|---|---|
| `0x4000` (today's) | `0x98000` | 32,738 B | 16,354 B |
| `0x6000` | `0x98000` | 32,738 B | 8,546 B |
| `0x8000` (double it) | `0x98000` | 32,738 B | **0 B** |
| `0xA000` | `0x98000` | 32,738 B | **−8,190 B — fails on landing** |

08-26 drew 6,368 B of grace; content ate it in 8.2 days. A pure anchor bump would have re-run
this parcel on the next draw.

**Fix:** a second term inside the `align_up` and outside the gate's threshold.

```
dac_banks  = align_up(max over sound-on shapes of packed_end
                      + DATA_GROWTH_RESERVE + DATA_GROWTH_GRACE, 0x8000)
sound_bank = dac_banks + 2 x 0x8000
gate FAILS when room < DATA_GROWTH_RESERVE
```

Room is then `>= RESERVE + GRACE` for every possible `packed_end`, so the recurrence period is
bounded below by GRACE rather than by the draw. `tools/test_bg_emit.py::
test_grace_makes_the_room_above_the_reserve_a_guarantee_not_a_draw` sweeps every residue of the
quantum and asserts both the floor and its tightness (the rule never buys a spare window).

---

## 3. Where the numbers come from — measured, not round

The 08-26..09-04 cycle is the only complete cycle this rule has had. Both ends are read from the
binding (DEBUG) shape's own sigil listing:

| | packed_data_end | source |
|---|---|---|
| 2026-08-26 | `0x8A720` | `docs/superpowers/2026-08-26-rom-relayout-report.md` |
| 2026-09-04 | `0x8C01E` | this build's `s4.debug.lst` |

**6,398 B in 8.2 days = 780 B/day**, and it splits:

* `+2,814 B` of data ahead of `Art_Sonic` (`Art_Sonic` 0x72A60 -> 0x7355E)
* `+3,584 B` of `art/optimized/characters/sonic.bin` itself (97,472 -> 101,056)

A finer series for the first component, from sigil's frozen tables across all 33 freezes since
the 08-26 re-layout (`HeightMaps` row of `golden/offcanonical_sizes/s4_debug.txt` at each
commit): `0x6E2A0` -> `0x6E76C`, ~40 B per chain, largest single step +416 B. So the drip is
small and the jumps are content drops — a re-cut art sheet moved 3.5 KB by itself.

**`DATA_GROWTH_RESERVE = 0xC000` (49,152 B).** The reserve must still hold the d-28 BG-animation
guarantee (16,384 B = two 8 KB bands per act) **and** a normal working cycle on top of it:

```
16,384 + 30 days x 780 B/day = 16,384 + 23,400 = 39,784
  -> rounded up to the reserve's own 0x4000 quantum = 0xC000 = 49,152 B
```

**`DATA_GROWTH_GRACE = 0x8000` (32,768 B).** One SetBank window — the natural quantum of the
thing being bought — and 42 days at the measured rate. It is the *guaranteed* minimum; today's
draw is better (below).

**That this room has already cost real content is on the record.** `games/sonic4/vram.toml`'s
perspective-floor note says a first cut spending 58 tiles was **backed out** because 1,856 B of
art pushed `Art_Sonic` past this reserve, with a margin of 252 B at the time. That note has been
corrected in place: the same 58 tiles now cost 2.8% of the room above the reserve.

---

## 4. Applied values, and the arithmetic

Binding shape: DEBUG (`config_a`'s `HeightMaps` row equals `s4_debug`'s; `s4` and `lean` are
smaller; `config_b` is sound-off).

```
packed_data_end   s4        0x72BFC + 101056 = 0x8B6BC
                  s4.debug  0x7355E + 101056 = 0x8C01E   <- binds

dac_banks   = align_up(0x8C01E + 0xC000 + 0x8000, 0x8000)
            = align_up(0xA001E, 0x8000)                  = 0xA8000
shared DAC bank (intra-section `align $8000`)            = 0xB0000
sound_bank  = dac_banks + 2 x 0x8000                     = 0xB8000
```

Room in the binding shape `0xA8000 - 0x8C01E` = **114,658 B**, of which **65,506 B** sits above
the reserve = **84 days** at the measured 780 B/day (the rule guarantees at least 42).

**Bank ids, `bankid(lma) = (lma & $7F8000) >> 15`, folded at link — nothing hand-typed:**

| bank | LMA | `& $7F8000` | `>> 15` | id |
|---|---|---|---|---|
| blip / `dac_banks` | `0xA8000` | `0xA8000` | 21 | **$15** |
| shared DAC | `0xB0000` | `0xB0000` | 22 | **$16** |
| `sound_bank` head | `0xB8000` | `0xB8000` | 23 | **$17** |

**Headroom under the hard ceiling.** Verified at source this run:
`engine/sound/z80_sound_driver.emp:1161` `SndDrv_SetBank` writes the bank LSB-first out of the
8-bit `a` register and then `xor a; ld (hl),a` for the 9th latch bit — *"All our banks are
< $100, so b8 = 0; write 0 explicitly."* So **bank id <= $FF**, and `bankid()`'s `$7F8000` mask
agrees.

* to the driver's `$FF` cap: `255 - 23 = 232` windows = **7,602,176 B** of headroom
* to the cartridge's `$7F` cap (address space ends `0x3FFFFF`): `127 - 23 = 104` windows =
  **3,407,872 B**, i.e. the banks could go to `0x3F8000`

We are three orders of magnitude inside the ceiling that matters.

---

## 5. THE BLOCK — sigil's frozen tables must move, and this is a mechanism

`map.toml`'s own header sentence, *"the frozen tables are the placement authority, these anchors
validate them"*, is literally true of the code. **A `[[anchor]]` places nothing.**

Read at source (`crates/sigil-harness/src/native.rs`):

* `true_bases_by_index` builds every ROM section's provisional base from
  `profile.frozen_sizes` — the label -> LMA rows of `golden/offcanonical_sizes/<shape>.txt`,
  read from sigil's **checkout at run time** (`load_frozen_table`, `CARGO_MANIFEST_DIR`), not
  compiled in.
* `map.toml`'s anchors reach the packing walk only as `anchor_addrs: HashSet<u32>`, tested by
  `is_anchor_gap(prov)`. Anchors are matched by **address**, never by name (the code says so at
  `native.rs:3314`). A declared anchor can therefore only *authorize* a section to stay at the
  address the frozen table already gives it.

Measured at the build, both directions, on this tree:

| experiment | result |
|---|---|
| anchors moved to `0xA8000`/`0xB8000`, tables unchanged | `error: native build (sonic4 debug): [map.undeclared-island] ROM section at 0x90000 is an ANCHOR_GAP-inferred island but no `[[anchor]] at = 0x90000` is declared` — the DAC bank did not move (same error, `sonic4 plain`) |
| **control**: keep `0x90000`/`0xA0000`, add a spare anchor at `0xA8000` | `error: [map.anchor-absent] declared anchor `control_probe_a8000` at 0xA8000 is not an inferred island in this build` — nothing landed at the declared address |

`sigil build` exposes no frozen-table override flag (`sigil build --help` -> usage line, no such
option). The control's map edit was reverted immediately (`git diff` clean).

### What sigil must do

Move these rows in every **sound-on** table —
`crates/sigil-harness/golden/offcanonical_sizes/{s4,s4_debug,config_a,lean}.txt`; `config_b` is
sound-off and unaffected — then re-derive with `golden/derive_offcanonical_sizes.sh` and re-pin
`src/pins.rs`. The 08-26 precedent hand-moved the island rows only and let the derive re-pack
everything downstream.

| row | from | to | delta |
|---|---|---|---|
| `Dac_Temp_Blip` (island) | `0x90000` | `0xA8000` | `+0x18000` |
| `SoundTablesZ80_Head` (phase bank, island) | `0xA0000` | `0xB8000` | `+0x18000` |
| `Song_MovingTrucks`, `Sfx_33`, `GameState_*`, `Replay_OJZ_Fixture`, `BusError`/`ReleaseFault`, `EndOfRom` | — | — | `+0x18000`, re-derived |

`pins.rs`'s `ASSEMBLED_LEN` / `DEBUG_ASSEMBLED_LEN` move by the same `+0x18000`.

### What the 09-02 cut did and did not change

The owner's **2026-09-02T18:20:19Z "CUT THE CEREMONY"** ruling (empyrean `docs/OVERSEER.md`,
read at the artifact for this parcel) ended the paired aeon+sigil **certification** freeze: aeon
freezes and certifies alone, and sigil's nightly drift observer is the safety net. That is real
and it is applied here — this parcel ran no sigil gates and waited on no sigil freeze for its
*evidence*. It did not, and could not, change the placement mechanism above. **The
"paired aeon+sigil landing" wording in `map.toml` was stale as to ceremony and correct as to
mechanism**; it has been rewritten to say exactly that, with the two measured errors quoted.

Closing `SIGIL-DECOUPLE` step 2 (the frozen tables stop being the placement authority) is what
would make a future anchor move an aeon-only change.

---

## 6. Four-shape verification

Assembler (pinned, unchanged across the whole run — hashed either side, per the freshness rule
that the banner's tree-state word is not a witness):

```
PRE-RUN  md5 6c2378ae8a657e26684d4019a7d976d7  sigil/target/release/sigil  (mtime 2026-09-02 17:46:28)
POST-RUN md5 6c2378ae8a657e26684d4019a7d976d7  (identical)
                emit_sound_blob  md5 b9d971d4a322f98c803bc479ad3e1d9f
```

| shape | baseline (master + re-bake) | after the parcel | delta |
|---|---|---|---|
| `s4.bin` | 720,821 B, cksum `3033548061` | **not produced** — `[map.undeclared-island]` | — |
| `s4.debug.bin` | 741,873 B, cksum `4182335998` | **not produced** — `[map.undeclared-island]` | — |
| `demo.bin` | 96,602 B, cksum `4157260963`, exit 0 | 96,602 B, cksum `4157260963`, exit 0 | **0 bytes** |
| `demo.debug.bin` | 102,818 B, cksum `1364289193`, exit 0 | 102,818 B, cksum `1364289193`, exit 0 | **0 bytes** |

The two demo rows are the **control**: both anchors carry `when = "sound_on"`, so a sound-off
shape must be byte-identical across this change, and it is. The two sonic4 rows are the block.

`bganim_room --gate`, both canonical sonic4 shapes: **still red, and for the original reason** —
the anchors have not actually moved, so the DEBUG room is still 16,354 B (now against a 49,152 B
reserve). The gate cannot go green until the frozen tables move. Its *message* is what changed,
and that is verified by the unit lane rather than by a build.

**Expected once sigil refreezes** (stated now so it can be checked rather than restated): both
sonic4 ROMs grow by `+0x18000 = 98,304 B` (`s4.bin` -> 819,125 B, `s4.debug.bin` -> 840,177 B);
every label below `0x8C01E` is unmoved; the Z80 resident blob changes exactly the
`SND_ENGINE_TABLE_BANK`/`SFX_BLOB_BANK` immediates from `$14` to `$17` (four bytes at the 08-26
sites `0x606`, `0x1121`, `0x1297`, `0x15EF`); 68k absolute references to the moved sound
sections take the same `+0x18000`.

**⚠ NOT CLAIMED: that placement is clean under a current assembler.** The pinned binary
(`0a58f2ec`, 2026-09-02) predates sigil master by 138 files in `crates/`, three of them in
`sigil-link`. Sigil measured on the record that the placement pass is identical between the two
(`final_size` untouched; the change is to `image_final_size`, whose only consumer is the
post-fixpoint `overlap_diag`) — so the arithmetic here stands. But the newer binary advances
over an internal `Reserve` instead of skipping it, so it is *strictly more likely* to name a
collision: **this binary's silence is not a clearance**, and a bank-anchor move is precisely the
operation that could put a pin inside a section's internal reservation gap. The overlap re-check
against `.sigil-sidetarget/release/sigil` (md5 `500990ecef7a5b0738696f75ad9a1939`, revision
`7bef76e6`) is **pending** — and it cannot be run meaningfully until the frozen tables move,
because until then no build reaches placement.

## 7. Fixture ritual — three stale, all decoded, none of them ours

The parcel produced no ROM byte change, so nothing of ours could stale a fixture. All three cuts
were nonetheless **red on master** in both shapes (the same re-stamp was sitting uncommitted in
the primary worktree). Checked before stamping, per the rule that a displacement following a
symbol move is benign and an opcode change is not:

| fixture | what differs | verdict |
|---|---|---|
| `sprite_tilt_cut.json` | no bytes at all; three recorded LMAs moved a **uniform +0x3F6** — `Ani_Sonic` `0x2AEB0`->`0x2B2A6`, `Ani_Tails` `0x2AFBA`->`0x2B3B0`, `Ani_Knuckles` `0x2B176`->`0x2B56C` | run shift, benign |
| `loop_crossover_cut.json` | 2 of 64 B at `+48/+49` of `Player_LoopCrossover`. Decoded from the ROM: `$01016A` is `lea $0007xxxx,a1` and the changed word is its low half, `0x0B24` -> `0x0F1A` = `CrossoverTable` `0x70B24` -> `0x70F1A`, **the same +0x3F6** | address operand, benign |
| `instashield_cut.json` | 2 of 62 B at `+58/+59` of `Ability_InstaShield`. `$0117AA` is `60 00 xx xx` = `bra.w`, changed word is its 16-bit displacement `0x9CB6` -> `0x9D3E` (+0x88); target `0xB462` -> `0xB4EA` = **`Sound_PlaySFX`**, which the fixture's own symbol map names | displacement, benign |

Stamped per the ritual — two invocations per fixture, one per shape, so each run preserves the
other shape's entry. All six gate runs green afterwards. The primary worktree's uncommitted
`instashield` re-stamp is itself one generation stale (still `0x9CB6` / `Sound_PlaySFX 0xB462`);
the other two match this one byte-for-byte.

## 8. Effects-gate ritual

`python3 tools/effects_gates.py --rom s4.debug.bin --lst s4.debug.lst`

```
15 segments: scene:mid_band 38.6s · scene:suppressed 43.6s · scene:above_screen 38.6s ·
scene:dense 41.4s · raster_off 0.6s · raster_source 1.7s · vsplit_landing 1.9s ·
palette_variant 1.7s · snapshot_poison 0.5s · warp_mailbox 6.6s · boot_override 1.6s ·
parallax_crossing 0.4s · tile_cache_fill 3.9s · cost_model 29.0s · listing 2.1s
        — all 15 PASS

effects_gates: OK — all 16 scheduled gate(s) produced a complete row set
  35 PASS rows, 0 FAIL rows
EXIT 0
```

⚠ **Run against master's artifacts, because this parcel produces no ROM.** It is a baseline
record, not a test of the move. The ritual must be re-run against the post-refreeze ROM before
this lands. (The lane spawns its own `oracle-aether`/`oracle_gui` on private `mkdtemp` sockets —
the owner's live socket was never touched.)

## 9. Pre-existing debt this parcel had to pick up

Master `afd6f784` **could not build**: `tools/level_staleness.py` stopped `DEBUG=1 ./build.sh`
with two editor sources added and never baked
(`games/sonic4/data/editor/effects/ojz_act1_floor.json`,
`games/sonic4/data/editor/ojz/act1/section_8.meta.json`). `tools/regenerate-level.sh` (9/9
sections, `verify_level_bin: OK`) changes four files and no byte counts. Committed separately as
`265bf6fa` so it is separable from the re-layout.

## 10. Files and commits

Branch `parcel/rom-relayout-more-room` (from master `afd6f784`):

| commit | what |
|---|---|
| `265bf6fa` | `rebake(level)` — master's stale level tree (pre-existing) |
| `446a27d9` | `relayout(rom)` — the rule, the constants, the anchors, tests, doc sync |
| `032b4cff` | `fixtures(restamp)` — the three cuts, with the decode of each |
| (this one) | this report + `docs/DEFERRED_WORK.md` entry + the mechanism correction |

Changed: `games/sonic4/map.toml`, `games/sonic4/vram.toml`, `tools/bganim_room.py`,
`tools/inject_editor_bg.py`, `tools/test_bg_emit.py`, `docs/ENGINE_ARCHITECTURE.md`,
`docs/DEFERRED_WORK.md`, `tools/fixtures/{sprite_tilt,loop_crossover,instashield}_cut.json`,
`games/sonic4/data/{editor_sources.stamp.json,generated/ojz/act1/*}`, and this report.

`tools/test_bg_emit.py`: **73 passed, 2 subtests**. Red-first for the new guarantee was applied
on disk (dropping `+ DATA_GROWTH_GRACE` from `rule_anchor`) and failed at the first residue —
`packed end 0x8000 -> anchor 0x18000 leaves 65536 B, under the RESERVE+GRACE floor of 81920 B` —
while the rest of the class stayed green, which is exactly why the defect survived 08-26. The
file was restored byte-identical (md5 `6ec7543f7fd9cfe7035f09e77c1f873c`).

Wall clock: builds ran 00:15-00:50 EDT on a 16-core box with load average 3.5-12.0 (other lanes
active); a canonical sonic4 build was ~2:07 each.
