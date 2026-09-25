# Pricing (B): the S2 clip shape gets its own bank-anchor pair (aeon half)

2026-09-25. Branch `research/clip-own-anchor`, base `43e361a8`. **Pricing only: no code changed.**
Hub ruling e229e1a3 (booked in `docs/DEFERRED_WORK.md`, `## S2CLIP-DEBUG-ROOM`): (A), putting clip
shapes into the shared anchor max, is refused. (B), giving the clip shape its own anchor pair (the rule
applied to the clip shape itself, canonical untouched), is row 8's first job. This note prices the aeon
side of (B) and names what aeon would need sigil to accept. Sigil prices its own half.

**Verdict: (B) is feasible, and it can keep canonical ROMs byte-identical by construction on the aeon
side.** It cannot land on aeon alone. What sigil has to accept is larger than the brief suggests,
because the anchor is written in THREE places, not two (section 1, step 4).

## 0. Measured baseline (re-derived here, not inherited)

In this worktree, with the `export SIGIL_BUILD=... SIGIL_EMIT=...` pair, sigil `d7e6aa15`. The two donor
zones were converted first with `python3 tools/s2_zone_convert.py convert s2disasm@EHZ` and
`... s2disasm@CPZ` (a fresh worktree has no `games/sonic4/data/donors/`, which is gitignored, and the
bake refuses without them):

| shape | command | rc | Art_Sonic LMA + 101,536 = packed end | room under 0xA8000 | above reserve | ROM crc32 / size |
|---|---|---|---|---|---|---|
| plain | `S2CLIP=s2_ehz_cpz ./build.sh` | 0 | 0x81052 → **0x99CF2** | 58,126 B | **8,974 B** | `9a3533f1` / 822,334 B |
| DEBUG | `DEBUG=1 S2CLIP=s2_ehz_cpz ./build.sh` | 1 (bganim_room) | 0x87AAC → **0xA074C** | 30,900 B | −18,252 B | `441f1db0` / 848,912 B |

Both of the ruled figures reproduce: DEBUG end 0xA074C, crc `441f1db0` and 848,912 B are the same as the
row-7 agent's, and plain has 8,974 B above the reserve. The 28,062 B two-zone increment is
0xA074C − 0x999AE (the one-zone `s2_ehz_boot` DEBUG end in `2026-09-25-s2clip-bank-room-gate.md`). I
did not re-measure that one-zone end myself.

An observation that is outside this parcel: in the clip shapes, `Art_Sonic` sits **27,226 B** further
along in DEBUG than in plain (0x87AAC − 0x81052). The canonical shapes differed by 2,402 B at the 09-04
re-layout (0x8B6BC and 0x8C01E, map.toml:241-243). I did not investigate why. It is the reason DEBUG
binds by so much.

## 1. How the anchors flow today, end to end

1. **Declaration.** `games/sonic4/map.toml:352-361` has two `[[anchor]]` rows: `dac_banks` at 0xA8000
   and `sound_bank` at 0xB8000 (vma 0x8000), both with `when = "sound_on"`. The rule that derives them
   is at map.toml:189-255. The two-places warning is at :257-263, and the mechanism is at :278-293.
   Only two `when` predicates exist in the tree: `sound_on` and `sound_off`.
2. **Sigil placement.** `build.sh:1289` runs `sigil build --aeon . --native ${NATIVE_FLAGS}`. For the
   clip shape, `NATIVE_FLAGS` is `--game sonic4 [--debug]` (build.sh:1261-1262). **This is the same
   argv as the canonical shapes, so sigil cannot tell a clip build from a canonical one.** Nothing about
   S2CLIP reaches sigil except the re-baked level tree. From map.toml's own record (read by aeon at
   sigil 6884bfba, and not re-read here): an island is held at its FROZEN provisional base when that
   base equals a declared anchor. `Dac_Temp_Blip` (the head of `dac_banks.emp`) is such an island. The
   phase bank `SoundTablesZ80_Head` is held by its frozen row. `validate_placement` requires the
   inferred islands to equal the declared ones in both directions. The frozen rows live in
   `crates/sigil-harness/golden/offcanonical_sizes/<shape>.txt`, and the path is compiled into the
   binary (map.toml:306-311). **I could NOT see:** the current source for any of this (I did not read
   sigil's tree, per the brief); whether the map loader accepts any `when` predicate beyond `sound_on`
   and `sound_off`; and whether a non-island section's `[layout.provisional-drift]` warning can escalate.
   `sigil build --help` at d7e6aa15 lists no map, anchor or frozen-table override. Its only
   off-canonical selectors are `--config-a/-b`, `--lean`, `--stress-evict` and `--stress-art`.
3. **Link-time bank folds (68k side and the co-residency guards).** `games/sonic4/data/sound/dac_samples.emp:180-220`
   define `SND_*_BANK = bankid(Dac_*)` and `SND_*_PTR = winptr(Dac_*)`. `mt_bank.emp:257-265` and
   `sfx/sfx_bank.emp:176` ensure that every song/SFX shares `bankid(MovingTrucks_Bank_Start)`. At run
   time the 68k derives a song's bank from its address: `engine/sound/sound_api.emp:295`
   (`z80_bank(d1, a1)`, posted as `PARAM_BANK` at :309). All of these follow wherever the islands land.
4. **Emit-time bank folds: the THIRD place the anchor is written.** `build.sh:764` runs
   `emit_sound_blob --aeon . --out-dir engine/sound/generated` BEFORE the sigil build and BEFORE the
   S2CLIP re-bake (build.sh:1045-1070). It takes **no shape argument**, and the files it writes are
   gitignored. Measured in this worktree after the builds:
   - `engine/sound/generated/dac_sample_tab.bin` starts `15 00 00 00 80 40 ... 16 00 ...`. The `ds_bank`
     bytes are 0x15 = bankid(0xA8000) and 0x16 = bankid(0xB0000). They are folded into a binary that
     `soundbankhead.emp` embeds (`engine/sound/dac_sample_tab.emp:85ff` spells them as `SND_*_BANK`).
   - `engine/sound/generated/z80_sound_blob.bin` has `3E 17 CD 71 03` (`ld a,$17 ; call $0371`, i.e.
     SetBank(bankid(0xB8000))) at offsets 0x235, 0xD5E, 0xED4 and 0x122C, and `3E 15` at 0x41F. The
     debug blob is the same at shifted offsets. The site at `engine/sound/z80_sound_driver.emp:785`
     (`ld a, SND_ENGINE_TABLE_BANK`) is one of these. That equ is supplied on the emit side, and
     `mt_bank.emp:40` describes it as `MovingTrucks_Bank_Start >> 15`. The 08-26 re-layout report
     (`docs/superpowers/2026-08-26-rom-relayout-report.md`, the verification list) saw the same thing
     from the other direction: "the 4 bank-id bytes at 0x606.. differ from the golden blob".
   **I could NOT see** where `emit_sound_blob` gets the addresses it folds (the 08-26 report names
   sigil's `seam2::sound_layout`). I also could not see whether anything at link cross-checks the
   emitted immediates against the placed islands. If nothing does, then a clip build whose islands move
   but whose emit does not would build green, and its sequencer and DAC would bank the wrong $8000
   window, with no gate to say so.
5. **Gate.** `build.sh:1718-1720` runs `tools/bganim_room.py --lst --rom --built-after --fixture --gate`
   in every sonic4 shape, clip shapes included. It has no `--map` argument: `rom_room` hard-defaults to
   `games/sonic4/map.toml` (bganim_room.py:804). `anchor_addr` (:338-356) returns the FIRST `at` under a
   matching `name` and **ignores `when`**. `rule_anchor` (:253), RESERVE and GRACE (:247-248), and the
   pair check `sound_bank == dac_banks + 0x10000` (:1032) all read those rows. In a clip shape, the
   gate's remedy text (the DEBUG log above) tells you to move the map anchors and hand them to sigil,
   which is (A), the refused option.
6. **Z80 SetBank.** `engine/sound/z80_sound_driver.emp:1220` (`SndDrv_SetBank`) writes 8 bits plus a
   literal-0 ninth bit, so bank id ≤ $FF. The ids that reach it come from step 3 (68k → mailbox) and
   step 4 (emitted immediates and descriptor bytes). None is hand-typed in aeon source.

Other consumers: I grepped every `.py/.sh/.emp/.toml/.json` under `tools`, `engine` and `games` for
`dac_banks|0xA8000|[[anchor]]|sound_bank|0xB8000`. Outside prose, only `bganim_room.py` (and its
tests) read the anchor values.

## 2. Candidate mechanisms (aeon side)

Every candidate needs the same four things from sigil. **(i)** Some way for a clip invocation to be
told its anchors. **(ii)** Islands placed at those anchors with no frozen-row edit. **(iii)**
`emit_sound_blob` folding from the same anchors. **(iv)** No change when the input is absent. The
candidates differ in where the value lives on the aeon side, and in what canonical reads.

| # | mechanism | aeon files touched | size | canonical byte-identity |
|---|---|---|---|---|
| M1 | **Per-shape rows in `map.toml`**: a second `dac_banks`/`sound_bank` pair under a new predicate (`when = "s2clip"`, with canonical rows `sound_on && !s2clip`) | map.toml; build.sh (a selector flag to sigil + emit); bganim_room.py (`anchor_addr` made `when`-aware, because today it would return whichever row comes first); tests | M | **By measurement only.** Canonical reads the edited map.toml, and whether its bytes stay the same depends on sigil evaluating a new predicate as false. Sigil would need a predicate-language extension AND a shape selector. It also puts a test fixture's layout into the shipping placement contract, which is close to what (A) was refused for. |
| M2 | **An alternate map passed by build.sh** (a full `map.s2clip.toml`) | new map copy; build.sh; bganim_room.py (`--map`) | M | By construction (canonical argv and files unchanged). But the copy duplicates the 90-row `order` list and every region/hole/budget, so any drift in the canonical map silently diverges the clip shape. Needs a sigil `--map` flag. |
| M3 | **An anchor overlay committed per clip act** (recommended). `games/sonic4/data/clips/<id>/anchors.toml` holds only the two `[[anchor]]` rows, in map.toml's own syntax. build.sh passes it to `emit_sound_blob`, `sigil build` and `bganim_room.py`, and only when `S2CLIP` is set AND the file exists. | new `anchors.toml` per clip; build.sh (S2CLIP block ~:197-221 resolves the path; the emit call :764; `NATIVE_FLAGS` :1261; the bganim call :1718); bganim_room.py (an `--anchor-overlay` arg: overlay rows replace map rows by name, used in the room and pair checks and in `check_growth_path`'s pinned set; remedy text names the overlay file, not sigil); `tools/test_bg_emit.py` (red-first overlay tests: overlay read, pair check, remedy text, no-overlay equals today); docs (map.toml pointer, ENGINE_ARCHITECTURE ROM-layout line) | **S-M** (about 1 day with tests) | **By construction on the aeon side.** Without S2CLIP, no new branch runs. The argv to `emit_sound_blob`, `sigil build` and `bganim_room.py` is character-identical. No file a canonical build reads is edited (map.toml, .emp and generated trees are untouched). What remains is that a NEW sigil binary must be byte-identical on the no-flag path. That is sigil's claim, and its six goldens pin it. |
| M4 | **The clip bake emits its own anchor** (clip_rom_bake.py writes the overlay) | clip_rom_bake.py; build.sh reorder | M-L | By construction, same as M3. But the rule needs `packed_end`, which exists only in the post-link listing, and the bake runs after the emit (build.sh:764 vs :1069). Deriving it would take a two-pass build (and pass 1 can fail to link once the data overruns the canonical anchor), or a size predictor that is not the rule. If the bake only transports a committed value, it is M3 with an extra hop. |
| M5 | **Sigil applies the rule itself** for the clip shape (it places `dac_banks` at `align_up(end + R + G)`) | build.sh flag; bganim_room would check a value by construction, so the gate goes vacuous | S aeon / L sigil | By construction. But the emit-time folds (step 4) happen before the end is known, so bank-id folding would have to move to link, or the build would go two-pass. This is SIGIL-DECOUPLE-sized, not a row-8 first job. |

## 3. Recommendation: M3, the per-clip anchor overlay

The value belongs to aeon. It moves every time a clip act grows, and M3 is the only option where that
move is a one-file aeon commit, with no sigil frozen-row edit per row. It is also the only option that
leaves every file a canonical build reads untouched, which makes canonical byte-identity a property of
the construction rather than of a measurement.

Two details go with it. A clip with no `anchors.toml` builds exactly as today, so the one-zone clips
keep 0xA8000. And one file serves both of a clip's shapes (plain and DEBUG), with the value being the
rule's own "max over the sound-on shapes", so DEBUG binds.

### The interface aeon needs sigil to accept (names are sigil's call)

1. **`sigil build` takes an anchor overlay** (for example `--anchor-overlay <path>`): a TOML of
   `[[anchor]]` rows that replace same-named `map.toml` rows for that invocation. It should refuse a
   name the map does not declare, and a value off the 0x8000 grid.
2. **Islands follow the overlay without a frozen row.** When an overlay replaces an anchor,
   `Dac_Temp_Blip` and the phase bank `SoundTablesZ80_Head` take the overlay addresses as their bases,
   and `validate_placement` checks against the overlaid set. There is no per-clip frozen table, and no
   frozen-row edit when the value moves. Sections downstream of the banks (`Song_MovingTrucks`,
   `Sfx_33`, `GameState_*`, `Replay_OJZ_Fixture`, the fault island, `EndOfRom`) re-pack as usual. Sigil
   should say whether their `[layout.provisional-drift]` warnings stay warnings.
3. **`emit_sound_blob` takes the same overlay** and folds `SND_ENGINE_TABLE_BANK`, the blob's SetBank
   immediates and the `dac_sample_tab` `ds_bank` bytes from it. If a link-time check that the emitted
   bank ids equal `bankid()` of the placed islands does not already exist, please add one. Without it, a
   half-applied overlay builds green and plays audio from the wrong bank.
4. **No flag means no change**, so the six goldens are unchanged. The overlay file should be recorded as
   a build input in the listing's Source Digest, so `tools/artifact_provenance.py` can see which anchors
   a listing was built with.

Aeon would pass the overlay only together with `--game sonic4 [--debug]`, never with `--config-*`,
`--lean` or `--stress-*`.

## 4. Room figures for a row-8 act

The rule is `dac_banks = align_up(end + 0xC000 + 0x8000, 0x8000)`, with `sound_bank = dac_banks + 0x10000`.

| | plain (end 0x99CF2) | DEBUG (end 0xA074C) |
|---|---|---|
| rule anchor, this shape alone | 0xB0000 | **0xB8000** (bganim_room prints the same) |
| clip pair = max over both | **dac_banks 0xB8000, sound_bank 0xC8000** (bank ids $17 blip, $18 shared, $19 phase) | same |
| room at 0xB8000 today | 123,662 B (74,510 above reserve) | 96,436 B (**47,284 above reserve**) |

The next row can grow by 47,284 B before the gate fires, with DEBUG binding.

**Row 8, ESTIMATED, not measured.** The only data point is row 7's 28,062 B increment, and that
increment included more than one zone's worth: Emerald Hill's full width (+3,386 B), the corridor, and
CPZ's first 2,048 px (13,306 B of blocks + a 1,600 B fringe). Suppose a third zone adds about the same
28 KB:

- DEBUG end ≈ 0xA74EA. Room at 0xB8000 ≈ 68,374 B, which is ≈ 19,222 B above the reserve, so the gate
  passes. The rule applied at that end would ask for **0xC0000** (sound_bank 0xD0000). So row 8 should
  re-derive the overlay from its OWN measured end when it lands, not inherit 0xB8000.
- Plain end ≈ 0xA0A90. That is ≈ 46,448 B above the reserve at 0xB8000.
- A row-8 increment above **47,284 B** would fail DEBUG even at 0xB8000. A whole-zone clip is in that
  range: all of CPZ act 1 measured +123 KB of block stream (`clips/s2_ehz_cpz/clips.json`, note (1)).
  With the overlay that stops being a wall, because the anchor simply moves (the ROM is ~0.8 MB of a
  4 MB cartridge, and bank ids up to $7F are addressable). It becomes a rule-derived one-line edit.

## 5. What I could not determine

- Sigil's current placement and emit source (not read, per the brief). Specifically: where
  `emit_sound_blob` gets the bank addresses; whether an emitted-vs-placed bank-id cross-check exists;
  whether the map loader's `when` accepts anything beyond `sound_on` and `sound_off`; and how
  provisional-drift behaves for a whole re-packed tail.
- Why the clip DEBUG shape carries 27 KB more ahead of `Art_Sonic` than plain does.
- Whether flying a ROM with banks at 0xB8000 or 0xC0000 plays correctly. No emulator was used.

## Correction (appended 2026-09-25, from sigil, re-checked here at aeon master `c20d9b5e`)

Two errors in the "measured in this worktree" list above:

1. **`3E 15` at blob 0x41F is NOT a bank id.** The bytes there are `3E 15 32 01 40`: `ld a,$15 ; ld ($4001),a`,
   a YM2612 data write of `SND_TIMERA_CTRL_REARM` (= $15, `engine/sound/sound_constants.emp:159`, used at
   `engine/sound/z80_sound_driver.emp:1450`) to register $27. It equals bankid(0xA8000) only by coincidence.
   A consistency check or patcher keyed on "every `ld a,$15`" would corrupt the timer rearm.
2. **Offsets 0x235, 0xD5E, 0xED4, 0x122C are the `ld a,n` OPCODE bytes (`3E`).** The bank-id operand bytes
   are one later: **0x236, 0xD5F, 0xED5, 0x122D**. Re-checked: each of the four reads `3E 17 CD 71 03`.
   These offsets hold for the plain blob at this revision only; the debug blob differs, and any edit to the
   driver moves them, so derive them, never pin them.
