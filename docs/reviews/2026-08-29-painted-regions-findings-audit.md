# Painted-regions study — firsthand audit of the fourteen findings against OUR tree

**Subject:** the fourteen cited defects in `aeon` returned by the aurora lane's four-lens
painted-regions design study, plus its one large ROM finding.
**Sources (read at the committed revision, not through the peer's working tree):**
`empyrean origin/main:docs/research/2026-08-29-painted-regions-study/B-adversary.md` §6 and
`.../A-engine-architect.md` §5.
**Peer's snapshot:** aeon `243c62ca`. **This audit:** aeon `bc552189` (master), branch
`audit/painted-regions-findings`. Every coordinate below was re-derived at `bc552189`; the
peer's snapshot-relative `path:line` are NOT reproduced.
**No emulator was used.** Runtime-wanting items stay TAGGED for the controller.

The study is good. Ten of the fourteen are real. Three are real facts wrapped in a wrong
causal story or a wrong novelty claim, and one is wrong on its central mechanism. The two
hypotheses the study deliberately held open are both settled below, and one of them turned
up a written work order that was never carried out.

---

## 1. Verdicts

### B §6 — the twelve-item table

| # | Finding | Verdict | Evidence at `bc552189` |
|---|---|---|---|
| 1 | ARCH claims `sec_pal` / `sec_raster_table` "have live consumers wired at the section-boundary crossing" | **CONFIRMED** | `docs/ENGINE_ARCHITECTURE.md:3699-3700` (peer cited `:3694-3696`; the line moved). Grep of `engine/ games/` for both names returns the `Sec` struct definition, the descriptor's field writes, and comments — **zero code readers**. Contradicted 73 lines later by `:3773-3776` in the same section ("`sec_pal` and `sec_pal_cycle` are no longer read directly on a crossing"), and by `engine/effects/palette.emp:240-243`. |
| 2 | ARCH names `sec_camera_lookahead` inside the list of fields engine code *does* read | **CONFIRMED** | `docs/ENGINE_ARCHITECTURE.md:2352` — "engine level code reads `sec_bg_layout`/`sec_parallax_config`/`sec_block_dict`/`sec_block_index`/`sec_camera_lookahead`, not `sec_pal`". `sec_camera_lookahead` has **zero** readers. Compounded by `:2394` in the present tense ("The camera reads the current section's value rather than a constant") against `engine/level/camera.emp:177-182` ("write-only until that ships"). The peer is right that this is the sharpest single false claim in §4.2, because the sentence's entire job is that enumeration. |
| 3 | Nine dead `Sec` fields, 32 of 66 bytes, three still populated | **CONFIRMED** | Grep over `engine/ games/` for all nine (`sec_plc`, `sec_pal`, `sec_raster_table`, `sec_pal_cycle`, `sec_sound_bank`, `sec_anim_blocks`, `sec_flags`, `sec_music`, `sec_camera_lookahead`) returns only `engine/structs.emp:109-134` (the definition), `act_descriptor.emp:203-217` (the writes), and comments. Byte arithmetic checks: 4+4+4+4+4+4+2+2+1 = 29, plus the three reserved pads (`$3C`, `$3E`, `$3F`) = **32 of 66 (48.5%)**, 288 B across act 1's nine rows. Three are still fed live values — `sec_pal: pal` (a **required** constructor argument), `sec_raster_table: raster`, `sec_pal_cycle: cycle` (`act_descriptor.emp:204,206,209`). `sec_plc` is booked nowhere: no `DEFERRED_WORK.md` entry, and ARCH §4.2's own audit note at `:2350` flags `SF_*` but not `sec_plc`. |
| 4 | `SF_*` is named in a comment and does not exist | **PARTLY** | The **fact is CONFIRMED**: `engine/structs.emp:126` says "`SF_* bitmask`" and no `SF_*` constant is defined anywhere in `engine/` or `games/`. The **novelty is REFUTED**: ARCH `:2350` already books it in terms — "the individual `SF_*` constants are not yet defined anywhere in `engine/`/`games/` (the `sec_pal` precedent — a field/name documented ahead of a consumer)". This is a known documented-ahead-of-code pin, not a discovery. |
| 5 | `Draw_BG_TileColumn` is dead, and ARCH lists it as a live producer *and* gets its width wrong | **CONFIRMED** | Zero callers: the only non-doc references are its own definition (`engine/level/plane_buffer.emp:410,424`), two prose mentions in `engine/level/bg.emp:23,29`, and a comment in `tools/inject_editor_bg.py:560`. The proc's own header says "ZERO CALLERS TODAY (2026-06-23 audit)". ARCH `:1290` and `:1299` list it among live producers, and `:1299` says "fixed 32-word strip" — the code emits **64 words** (`addi.w #4 + 64*2, d2`, header `$803F`). ARCH contradicts itself: `:1711` says all 64 rows in every writer including this one. |
| 6 | Camera-lookahead is four dead cells, acknowledged in code and booked nowhere | **PARTLY** | The **four dead cells are CONFIRMED**: `Camera_Lookahead` (`engine/ram.emp:712`) 0 readers / 0 writers; `Camera_Pan_Offset` (`:713`) one writer only, `move.w #0` at `engine/level/camera.emp:177`, no readers; `CAM_LOOKAHEAD_THRESHOLD` (`engine/system/constants.emp:818`) 0 readers; `Sec.sec_camera_lookahead` 0 readers. The code says so at `camera.emp:178-182`. **"Booked nowhere" is REFUTED**: `docs/DEFERRED_WORK.md:3205` lists `Camera_Lookahead` by name in "orphaned teleport-era RAM". The three *other* cells are genuinely unbooked, and the ARCH claims (#2) are the real defect. |
| 7 | Release has no `sec_effects == 0` guard | **CONFIRMED — see §2 for the reachability enumeration** | `engine/level/parallax.emp:723-728`: the `tst.l Sec.sec_effects(a0)` / `raise_error` pair is inside `if DEBUG == 1 { }`, so `jbsr Effects_InstallPreset` at `:729` runs unconditionally in release. **The asymmetry stated plainly: the shape that catches the bug is the one we develop in, and the shape that ships is the one that silently reads the 68000 vector table as an `EffectsPreset`.** Settled by the controller before this audit; the enumeration behind "unreachable today" is mine and is in §2. |
| 8 | The boot-position override installs only the parallax config and never sets `Snap_Pending` | **PARTLY — the headline half is REFUTED** | **REFUTED:** the boot path *does* set `Snap_Pending`, and it *does* carry the `$FF` sentinel. Both come from `Parallax_Init`, which every branch of the boot select calls (`games/sonic4/test/ojz_scroll_test.emp:578`): `engine/level/parallax.emp:650-651` writes `$FF` to `Parallax_Prev_Sec_X/Y` and `:655` does `st Parallax_Snap_Pending`. The peer read the comment at `ojz_scroll_test.emp:530-532` ("nothing here sets `Parallax_Snap_Pending` the way `Debug_Warp_Consume` does") as a statement about today's state. It is a **counterfactual** describing what happens *without* the override block: `Parallax_Init` sets the flag and its own `jbsr Parallax_Update` consumes it (`parallax.emp:1264`), so a later corrective crossing would lerp rather than snap. **CONFIRMED residue:** the boot path resolves *parallax only* — `jbsr Effects_ResolveParallax` (`:572`), never `Effects_InstallPreset` — so palette / cycle / variants / raster arrive one frame later from the first `Parallax_CheckBoundary`. That asymmetry with the warp path is real, but it is designed and documented (`:594`), not an accident, and the `$FF` sentinel — not "boot lands where identity is already right" — is why it is correct. The peer's conclusion "under regions it is a bug" does not follow from the mechanism they cited. |
| 9 | `inject_editor_bg.py`'s emitted section name keys on the zone, not the act | **PARTLY** | The **fact is CONFIRMED**: `tools/inject_editor_bg.py:326` — `self.section = f'{zone_id}_bg_anim'`, while `:325` gives the *module* an act suffix. Two acts of the same zone collide on `ojz_bg_anim` and on the same `pub` symbols. The **novelty is REFUTED**: the class docstring at `:302-315` says in capitals "THE SECTION NAME CARRIES NO ACT AND THAT IS DELIBERATE", names the collision explicitly, explains it is a ROM-placement change needing an owner ruling, and points at the booking — `docs/DEFERRED_WORK.md:496`, "A SECOND ACT'S BG ANIMATION HAS NOWHERE TO LIVE". Nothing here is unknown to the tree. |
| 10 | `OJZ_Sec4_Blocks` is a zero-byte alias but `OJZ_Sec4_LocalMap` is not | **CONFIRMED — and their UNVERIFIED half is settled** | `sec2_local_map.bin` and `sec4_local_map.bin` are byte-identical: both 202 B, both md5 `f51e8069c75be9a1aac8d376e30711fc`. So the ~202 B is genuinely recoverable. **Why one dedups and the other does not: two different generators.** `tools/ojz_block_gen.py` emits `sec_block_blobs.emp` with a sha256 whole-blob content dedup and writes the duplicate as a zero-byte `pub equ OJZ_Sec4_Blocks = extern("OJZ_Sec2_Blocks")`. `tools/ojz_strip_gen.py:842-853` emits `sec_local_maps.emp` from an unconditional `for sid in ...` loop of `pub data ... = embed(...)` with **no content comparison anywhere**. The dedup was built in one generator and never in its neighbour. |
| 11 | ARCH `:2386` and `:1715` stale | **CONFIRMED, all three parts** | (a) `:2386` "writes rows 0-31 of all 64 Plane B columns" — the code writes `moveq #32-1` **longwords** = 64 words = rows 0..63 (`engine/level/section.emp:429`, with the NEW-5 note at `:414-419` recording the fix). Contradicted by ARCH `:1711` in the same document. (b) `:2386` "set once at level init" — there are **two** setters, `games/sonic4/test/ojz_scroll_test.emp:515` (level init) and `:1284` (the DEBUG warp); `engine/level/section.emp:518` says "the only two `Section_Plane_Dirty` setters" in as many words. (c) `:1715` "one 4 KB nametable blit" — a Plane B layout is a raw 64×64 nametable = **8,192 B** (`engine/level/bg.emp:16-18`), so the byte-math and the "~0.6 ms" that hangs off it are both half-size. |
| 12 | The `.lst` listing is stale against the snapshot's blobs | **CONFIRMED for the artifact — REFUTED as a claim about the instrument. See §4.** | Measured both listings on disk against the committed blob. `s4.lst` (built 2026-08-27 09:51): `OJZ_Sec0_Blocks` `0x16A10` → `OJZ_Sec1_Blocks` `0x189EA` = **8,154 B**, against `sec0_blocks.bin` = **8,560 B** on disk — 406 B / 4.7% low, exactly the peer's figure. `s4.debug.lst` (built 2026-08-29 09:56): `0x173B0` → `0x19520` = **8,560 B — exact to the byte**. So a `.lst` is not a ~5%-wrong instrument; **a `.lst` from a revision that is not the subject is a wrong instrument, and one from the matching revision is byte-exact.** The correct generalisation is the one already in `tools/bganim_room.py`'s header: "A listing from a prior build is never a valid subject." |

### A §5 — the optimisations-to-fold-in list

| Item | Verdict | Evidence |
|---|---|---|
| Delete the ten dead `Sec` fields and the `pal:/raster:/cycle:` constructor arguments | **CONFIRMED** — and it is a work order that was written, scheduled, and skipped. See §3, hypothesis (i). | |
| `Section_Fwd_Neighbor_Data` / `Section_Bwd_Neighbor_Data` (8 B RAM) written by nothing, read only by the replay hash | **CONFIRMED** | Declared `engine/ram.emp:848-849`. The only other references tree-wide are `engine/system/replay.emp:375-376`, two `dc.l <name>, 1` rows in the hash ledger. No writer exists. Already booked at `docs/DEFERRED_WORK.md:3205` alongside `Camera_Lookahead` — so this is a confirmation, not a discovery, and note that deleting them **moves the replay hash ledger** and therefore owes the fixture ritual. |
| `PAGE_FRAMES` comment says 15, value is 14 | **CONFIRMED — and see §3, hypothesis (ii)** | `engine/system/constants.emp:272-274`: "`POOL_TILE_CEILING(960)` / `ART_POOL_PAGE_TILES(64)` = 15 frames", trailing `// 15`. `POOL_TILE_CEILING = 896` (`:668`), so `PAGE_FRAMES` = 14. The `ensure` at `:275` compares `PAGE_FRAMES * ART_POOL_PAGE_TILES == POOL_TILE_CEILING` — since `PAGE_FRAMES` is *defined* as that quotient, the check catches inexact division and can never catch the comment. Already booked at `docs/DEFERRED_WORK.md:4329-4331`; the peer says so itself. |
| `Section_RedrawPlanes` Plane B pass carries a now-false comment "BG layout is act-wide, not position-dependent" | **CONFIRMED** | `engine/level/section.emp:389`. The five lines directly beneath it derive the on-screen section from the camera and read `Sec.sec_bg_layout(a0)` with an `Act.act_bg_layout` fallback (`:393-406`). The comment is contradicted by the code it introduces. |
| Store the BG layout row-major and delete the injector transpose — "`Draw_BG_TileColumn` is the only consumer of column order and has no callers" | **REFUTED on its premise** | Column order has **three** consumers and two of them are live. `engine/level/bg.emp:20-24` enumerates them: "BG_Init and `Section_RedrawPlanes`' Plane B blit set the VDP address per column with autoinc `$80` (one `move.l` = two vertically-adjacent cells); `Draw_BG_TileColumn` gathers a column as a sequential `move.l` run." Both live consumers *require* column contiguity — the autoinc-`$80` excursion is the whole reason the blit is one `move.l` per two cells (`section.emp:410-435`, `bg.emp:136-150`). Making the blob row-major breaks them. The proposal as stated is not a free deletion. |
| Two anchors for one quantity (`pcfg_v_center_y`/`pcfg_v_offset` vs a region anchor) | **NOT A DEFECT IN OUR TREE** | `pcfg_v_center_y` / `pcfg_v_offset` (`engine/structs.emp:202-203`) are read at `engine/level/parallax.emp:1799-1801,1828` and are the single anchor today. The "two anchors" only exist if a region record adds a second one. This is a design constraint on unbuilt work, correctly stated, but there is nothing to book against the current tree. |

---

## 2. Finding 7 — is it genuinely unreachable today? The enumeration.

"All sections set `sec_effects`" is a reachability claim, so it was enumerated rather than
taken on trust. Three facts close it:

1. **There is exactly one `Sec` table in the whole tree.** Grep for `[Sec;` over
   `engine/ games/` returns `games/sonic4/data/levels/ojz/act1/act_descriptor.emp:224`,
   `pub data OJZ_Act1_Sections: [Sec; 9]`, and nothing else. `games/demo` has no `Sec` array.
2. **All nine of its rows pass a non-zero `effects:`.** `OJZ_Preset_Sec0`, `_Sec1`, `_Sec2`,
   `_Sec3`, `OJZ_Preset_Depth`, then `OJZ_Preset_Plain` for sections 5-8
   (`act_descriptor.emp:240,250,264,274,285,292,299,306,313`).
3. **The guard site has exactly one caller, in the one game that has sections.**
   `Parallax_CheckBoundary` is called from `games/sonic4/test/ojz_scroll_test.emp:843`
   (per-frame) and `:1300` (the DEBUG warp). Nothing in `games/demo` reaches it.

**Verdict: genuinely unreachable today.** The 68000-vector-table read cannot happen in any
shipped shape at `bc552189`.

**But the guard that matters is missing at the other end.** `ojz_sec()`'s signature is
`effects: Label = 0` (`act_descriptor.emp:198`) — the argument is **optional and defaults to
zero**. A tenth section, or a second act, authored without an `effects:` binding compiles
clean, ships, and takes the release path straight into `$1C`. Nothing at build time objects.
That is the shape of the risk: not "someone will delete a preset", but "the next author will
omit an optional argument". The cheap fix is not the release-side runtime guard the peer
implies — it is a build-time `ensure` over the table, or making `effects:` required the way
`pal:` already is. **Booking only; not fixed here.**

---

## 3. The two hypotheses the study held equal — both settled

### (i) Are the dead palette-family `Sec` fields deliberate transitional residue, or forgotten?

**SETTLED: forgotten. There is a written work order in the tree naming the task that was to
do it, that task ran, and it did not do it.**

The run the peer nominated was `git log -S sec_pal` around the effects-P3-C2 Task 13 commit.
Run: `git log --oneline -S"sec_pal" -- engine games` → the Task 13 commit is `e6b016e5`,
"refactor(effects-p3-c2): remove the dead legacy per-field installer path" (2026-08-15).

The instruction is at `act_descriptor.emp:186-193`, and it is explicit:

> "The legacy `pal:`/`raster:`/`cycle:` arguments are LEFT IN PLACE and still feed their
> fields — they become inert once `sec_effects != 0` … **but deleting them is Task 13's job,
> once reachability of the preset path is established.** Keeping them here keeps this task's
> diff a pure addition."

Both halves of that resolve against Task 13:

- **Its stated precondition was met, by Task 13 itself.** `e6b016e5`'s message: "Task 12
  converted the last OJZ act to the preset system, so … `OJZ_Act1_Sections` is the only
  `[Sec; N]` array, and its every section now sets `sec_effects`." That is precisely
  "reachability of the preset path is established".
- **Task 13 did not do the second half.** Its commit message enumerates every deletion —
  the `.legacy` branch, `Palette_LoadSection`, `Palette_InstallCycleSection`,
  `Raster_InstallSection`, `Raster_Clear`, two `map.toml` re-heads, one
  `Palette_SetVariant` call. **The constructor arguments and the fields are not mentioned
  anywhere in it**, and they are still there at `bc552189`: `sec_pal: pal` is not merely
  present, it is a **required** argument.

So this is not transitional residue held deliberately. It is a scheduled deletion whose
precondition was discharged in the same commit that was supposed to perform it. That is a
stronger result than the peer's framing allowed for: the tree contains its own instruction
to remove these, and the instruction has an owner and a date.

### (ii) Is `PAGE_FRAMES`'s stale comment pure drift, or evidence of an un-re-derived consumer?

**SETTLED: pure comment drift. Every consumer is symbolic; not one carries a literal.**

The run the peer nominated was a grep of every `PAGE_FRAMES` / `PAGE_FRAMES_MAX` consumer
against the 14/15 split. Run over `engine/ games/ tools/`:

- **Engine, count-sized (`PAGE_FRAMES`)** — `engine/level/page_cache.emp:74, 130, 145, 263,
  942, 999, 1007, 1027, 1090, 1132, 1184`. Every one is the symbol: `move.w #PAGE_FRAMES-1`,
  `cmpi.w #PAGE_FRAMES`, `#(PAGE_FRAMES-1)*sizeof(PageFrame)`, and an `ensure` at `:74` that
  is itself written in terms of `PAGE_FRAMES`. **No literal 14 or 15 appears in any of them.**
- **Engine, capacity-sized (`PAGE_FRAMES_MAX`)** — `engine/ram.emp:225` (`Page_Frames`) and
  `:628` (`Page_Audit_Scratch`). Both symbolic. This is the deliberate 2026-08-11
  capacity/count split, and the same comment block that carries the stale "15" states the
  split correctly two paragraphs later: "10 bytes at 14/15".
- **Derived** — `PAGE_FRAMES_CLAMP = PAGE_FRAMES - STRESS_EVICT * (...)`
  (`constants.emp:374`), symbolic, with its own bounds `ensure` at `:375`.
- **Tools** — the only two hits are *comments*: `tools/ojz_strip_gen.py:137` ("exceeds 15
  `PAGE_FRAMES` by ~4x") and `tools/streaming_choke_probe.py:41` ("10 pages against
  `PAGE_FRAMES=15`"). Neither is read by any code path; both are stale in the same way as
  `constants.emp:272-274`. `tools/evict_witness.py:51` hardcodes `PAGE_FRAMES_CLAMP = 9`,
  but that is the `STRESS_EVICT` fixture's own value, not a `PAGE_FRAMES` copy.

**No consumer would change behaviour at 14 vs 15, because no consumer names either number.**
The drift is confined to four comments — `constants.emp:272-274`, `ojz_strip_gen.py:137`,
`streaming_choke_probe.py:41`, and `DEFERRED_WORK.md:1050` ("10 pages against
`PAGE_FRAMES` = 15"). The peer also cited `DEFERRED_WORK.md:1655`; re-checked here, that
line names `PAGE_FRAMES_CLAMP` and carries no number, so it is **not** a fifth instance.
`constants.emp:665` has it right in the same file ("of the remaining 14").

---

## 4. Which instrument, and what it can and cannot price (finding 12, generalised)

Both listings on disk were checked against the tree before any number below was used.

| listing | built | `Sec0_Blocks` label delta | `sec0_blocks.bin` on disk | verdict |
|---|---|---:|---:|---|
| `s4.lst` | 2026-08-27 09:51 | 8,154 B | 8,560 B | **stale — 4.7% low** |
| `s4.debug.lst` | 2026-08-29 09:56 | 8,560 B | 8,560 B | exact on level data |

**Neither listing is current against master.** `839d600d` (2026-08-29 14:41) changed
`engine/level/plane_buffer.emp`, `engine/level/section.emp` and `engine/level/tile_cache.emp`
*after* the debug listing was produced. The debug listing's *data* offsets happen to still
match because that commit touched no level data, but `Art_Sonic`'s address rides downstream of
engine code and may have moved. **Any room figure quoted for an owner decision needs a fresh
`./build.sh` of both canonical shapes first.**

Instruments actually used in §5, in order of authority:

1. `tools/bganim_room.py` (reads the sigil `.lst` symbol listing plus `map.toml`'s hardware
   anchor, and nothing else) — for ROM room.
2. `games/sonic4/map.toml`'s `order` array — for *which* region a section lands in. This is
   an ordering fact, not an occupancy fact, and it does not depend on any listing being fresh.
3. On-disk `.bin` sizes under `games/sonic4/data/generated/ojz/act1/` — for blob content.

**Not used, deliberately:** any gap between two rows of sigil's frozen boundary tables. That
table lists a subset of labels; a gap in it is an allotment, never proven free space
(`tools/bganim_room.py` header; decisions d-8 / d-9).

---

## 5. The block-stream duplication finding — measured from the format, not estimated

A §2.4 claims **"491 stored streams for 74 distinct blocks; mean stream ~76 B; deduped
~74 x 76 = 5.6 KB + index + dict = ~15 KB vs 46.6 KB"**, i.e. ~31 KB recoverable. A second
reviewer claimed **"66% raw duplication across sections' dictionaries"**. Both were labelled
study estimates. Both were re-derived here from the on-disk blobs by parsing the format out
of `tools/ojz_block_gen.py` and `tools/s4lz.py`, not by trusting either figure.

### 5.1 The format, from the generator

A section blob is `[1024 B index][768*K raw dict blocks][concatenated S4LZ v3 streams]`.
An index entry is a big-endian `u32` offset from the **blob base**; `0` = empty; bit 31 set =
RAW-DIRECT, a pointer to a raw 768 B block inside the dict region. **Streams carry no length
field** — a stream's extent is implied by the next stored offset. Both readings were taken:
each token stream was re-walked for its exact consumed length *and* cross-checked against the
boundary-implied length. They agree on all 482 streams (total padding 0), and every decode was
verified against `s4lz.decompress`.

Every section reconstructs to its **exact** on-disk byte count. **Zero unaccounted bytes.**

### 5.2 Measured, per section (all K=1, dict 768 B)

| sec | file B | non-empty entries | raw-direct | compressed streams | index | dict | streams |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 8,560 | 82 | 1 | 81 | 1,024 | 768 | 6,768 |
| 1 | 4,988 | 54 | 1 | 53 | 1,024 | 768 | 3,196 |
| 2 | 6,040 | 48 | 1 | 47 | 1,024 | 768 | 4,248 |
| 3 | 4,428 | 52 | 1 | 51 | 1,024 | 768 | 2,636 |
| *4* | *(alias — **0 ROM bytes**)* | *48* | *1* | *47* | – | – | – |
| 5 | 3,622 | 48 | 1 | 47 | 1,024 | 768 | 1,830 |
| 6 | 7,168 | 53 | 1 | 52 | 1,024 | 768 | 5,376 |
| 7 | 4,724 | 52 | 1 | 51 | 1,024 | 768 | 2,932 |
| 8 | 7,072 | 54 | 1 | 53 | 1,024 | 768 | 5,280 |
| **shipped (8)** | **46,602** | **443** | **8** | **435** | **8,192** | **6,144** | **32,266** |
| all 9 (incl. alias) | 52,642 | 491 | 9 | 482 | 9,216 | 6,912 | 36,514 |

### 5.3 (a) Is "491 stored streams for 74 distinct blocks" right? **No — the two halves come from different populations.**

- **491 is not stored streams.** It is *non-empty index entries across all **nine** sections* —
  the number `ojz_block_gen.py` itself prints (`491/2304 total non-empty blocks`). Two things
  are folded in: it counts `sec4`, which is a zero-byte alias reaching the ROM as 0 bytes; and
  9 of those entries are RAW-DIRECT pointers into the dict region that store **no stream at
  all**. The ROM-reaching figure is **443 non-empty entries = 435 compressed streams + 8
  raw-direct**.
- **74 distinct is correct**, but at the *decoded raw 768 B block* granularity. At the
  granularity the sentence actually names — *stored* streams — there are **68** distinct
  byte-strings.
- **Their arithmetic does not close.** `(46,602 − 8,192 − 6,144) / 474 = 32,266/474 = 68.1`,
  not the 76 they wrote, and the divisor 474 matches no population in the data (435 streams /
  443 entries / 491 all-nine entries). The real mean stored stream is `32,266/435` = **74.2 B**.

### 5.4 (b) What it costs today

**46,602 B** = 8,192 index + 6,144 dict + 32,266 streams. The peer's 46.6 KB headline is right;
it is the sum of the eight shipped `.bin` files.

### 5.5 (c) What dedup costs back — and the shape of the duplication

The structure decides everything, and it is not what "act-wide dedup" implies:

- distinct raw blocks act-wide (8 shipped sections): **74**
- distinct raw blocks appearing in **more than one section**: **1** (73 blocks appear in
  exactly one section; one decorative block appears in all eight)

**So the recoverable duplication is ~99.2% *within*-section, not across sections.**

**Scenario A — within-section stream sharing.** Two index entries carry the same offset;
groups containing the dict block become RAW-DIRECT.

```
index    8,192  (unchanged)
dict     6,144  (unchanged)
streams 11,280  (73 distinct compressed streams, mean 154.5 B)
        ------
total   25,616
```

**Metadata cost: ZERO.** `engine/level/tile_cache.emp:461-468` does
`move.l (a2,d3.w), d0` then `lea (a2,d0.l), a0` — a 31-bit offset from *this section's* index
base, decoded with *this section's* `Sec.sec_block_dict`. Two entries holding the same offset
resolve identically. Nothing ever writes a ROM stream, and pointer aliasing is already the
established pattern in this routine (`.empty_block` aliases one shared zero page across every
slot; `.raw_direct` is zero-copy straight to ROM). No wider offsets, no new table, no
descriptor change, no `.emp` edit.

**Scenario B — true act-wide dedup with one shared dictionary.** The K-sweep was re-run on
the distinct set: K=0 → 28,630, K=1 → 27,914, K=2 → 27,230, K=3 → 26,546. Also zero new
metadata, but **930 B worse than Scenario A** — eight dictionaries tuned per section beat one
shared across the act. *Act-wide is the intuitive move and it is the wrong one.*

**Scenario C — A, plus sharing the one genuinely cross-section block.** Six of the seven
copies are byte-identical 28 B streams = 168 B. Not available: an offset from section X into
section Y's blob is a link-time distance the generator cannot bake into a standalone `.bin`,
and a backward reference sets bit 31 and is misread as RAW-DIRECT. 168 B does not buy a format
change.

### 5.6 (d) Realistic recoverable saving: **20,986 B**

```
32,266 (streams today) − 11,280 (distinct streams) = 20,986 B
46,602 → 25,616   (45.0% of the block data)
```

Confidence **high**, and it is a **lower bound**: re-running the K-sweep after dedup can only
choose a payload ≤ 25,616, since the current K choice stays available.

**Against the peer's ~31 KB: they are ~50% high.** The error is `74 × 76` — it prices the
distinct blocks at the *mean of all blocks*. Duplicates are the **simple** blocks; distinct
blocks skew large. Measured distinct-stream mean is **154.5 B**, 2x the 76 they assumed. The
deduped total is ~25.6 KB, not ~15 KB.

Assumptions that could move it:

1. **K-sweep re-optimisation** after dedup changes the objective — moves cost *down* only.
2. **Engine aliasing tolerance is read, not run.** `tile_cache.emp` is unambiguous (ROM
   streams are never written; staged pointers already alias) but this is source reading, not
   a runtime observation. **TAGGED** — see §8.
3. **Duplicate identity is exact 768 B, including the LOCAL per-section nametable indices.**
   Two visually identical blocks in sections with different local maps count as distinct. So
   the figure is conservative, never optimistic.
4. `sec4`'s zero-byte alias is taken from `sec_block_blobs.emp`, not confirmed against a
   listing.
5. All numbers are the committed `.bin` files at `bc552189`. A re-bake from a changed editor
   tree moves them.

**Adjacent lever, not counted:** after dedup the index tables are 8,192 B = 32% of the
remaining 25,616. The largest offset in any blob is 8,560, so `u16` entries fit (offsets are
word-even, leaving a flag bit free) — a further **4,096 B**. That one *does* need an engine
change and its cycle cost is unpriced.

### 5.7 (e) "66% raw duplication across sections' dictionaries" — **REFUTED, by a control**

The eight dictionaries are 768 B each (`OJZ_SEC{0..8}_BLOCK_DICT_LEN = 768` throughout).

- **Eight distinct dictionaries. Whole-dict duplication: 0.0%.**
- The only granularity that produces anything near 66% is 4-byte chunks, at 62.4% — **and the
  control kills it**: the identical measure applied *within a single dictionary alone* averages
  **61.2%**.

| chunk | cross-8-dict "duplication" | control: within ONE dict |
|---|---:|---:|
| 4 B | 62.4% | 61.2% |
| 16 B | 35.4% | 33.6% |
| 64 B | 32.3% | 25.0% |
| 256 B | 25.0% | 0.0% |
| 768 B | 0.0% | 0.0% |

Essentially all of the apparent "duplication" is the tileset's own self-similarity, present
inside one dictionary, not shared between them. The honest measure: `s4lz` each dict separately
= 3,012 B; all eight concatenated = 2,946 B. **Real cross-dictionary redundancy is 66 B of
6,144 = 1.1%.**

And it is unrecoverable regardless: the dictionaries are stored raw *by design*, because they
are simultaneously their own block storage and the LZ window the 68000 decoder indexes into.
Compressing them is not an available move.

---

## 6. THE BUDGET QUESTION — does the block saving land where the DPLC re-page needs it?

**Yes. Same region, one-for-one. They compete for exactly one budget, and it is the one
`d-47` option B is short of.**

### 6.1 The region, named

`games/sonic4/map.toml`'s `order` array is the placement contract. The relevant run, in order
(map.toml:130-136), with the addresses each label actually took in `s4.debug.lst`:

| label | LMA (debug shape) |
|---|---|
| `OJZ_Sec0_Blocks` | `0x173B0` |
| `OJZ_Sec8_Blocks` | `0x20E1A` |
| `OJZ_Sec0_LocalMap` | `0x229BC` |
| `BgAnim_Table` | `0x27F10` |
| `HeightMaps` | `0x6E5E0` |
| `Map_Sonic` | `0x707E0` |
| `DPLC_Sonic` | `0x72460` |
| **`Art_Sonic`** | **`0x72DA0`** |
| `Dac_Temp_Blip` (the `dac_banks` anchor) | `0x90000` |

`map.toml:132-133` states the invariant in as many words: collision_data is "the LAST data
section: its tail `Art_Sonic` is the packed-data end the bank rule measures."

**The block blobs sit upstream of `Art_Sonic` in the same packed data run, ~330 KB before it.**
Since sigil packs downstream sections from real sizes, **removing N bytes from the block blobs
slides `Art_Sonic` down by N and grows the room under `dac_banks` by N.** This is an ordering
fact from `map.toml` plus two label addresses; it does not depend on any listing being fresh.

### 6.2 The room, and the real constraint

Measured with `tools/bganim_room.py` (the instrument that reads the sigil `.lst` symbol
listing plus `map.toml`'s hardware anchor, and nothing else):

| shape | packed end | anchor | **ROM room** | binds? |
|---|---|---|---:|---|
| `s4.debug.lst` (2026-08-29) | `0x8AA60` | `0x90000` | **21,920 B** | **yes** — larger packed end |
| `s4.lst` (2026-08-27, **stale**) | `0x8A070` | `0x90000` | 24,464 B | no |

The debug figure reproduces `d-47`'s 21,920 exactly. **The debug shape is the binding one** —
one anchor serves every sound-on shape, so the shape with the largest packed end sets it, and
that shape also has the least room.

**The constraint is not "room > 0".** `bganim_room.py --gate` FAILS the moment a shape's room
drops below `DATA_GROWTH_RESERVE = 16,384 B` (`map.toml:198`, the d-28 acceptance). So:

```
spendable today (binding shape) = 21,920 − 16,384 = 5,536 B
```

**`d-47` option B needs +24,020 B.** Two separate failures at once:

- against the gate: short by `24,020 − 5,536` = **18,484 B**
- physically: `21,920 − 24,020` = **−2,100 B** — it overruns the `dac_banks` anchor and stops
  the build at `resolve_layout`

`d-47`'s card frames this as "24,020 against 24,160 available — it does NOT fit", which
compares against the *release* room and an implicit zero reserve. The truer statement is the
one above, and it explains the card's own next sentence ("it forces the sound banks to move
and crushes the background-animation ceiling"): the reserve *is* that ceiling's guarantee.

### 6.3 The answer

```
room after block dedup      21,920 + 20,986  = 42,906 B
after option B's +24,020    42,906 − 24,020  = 18,886 B
required reserve                               16,384 B
                                             ----------
                             MARGIN            2,502 B   FITS
```

**Recovering block-stream duplication changes the answer to `d-47`.** Option B goes from
overrunning a hardware anchor by 2,100 B to fitting with 2,502 B above the reserve — **without
moving `dac_banks`, without moving `sound_bank`, and without touching the 12,288 B BG-animation
ceiling the owner already ruled on.** The release shape is not binding and clears with more
room (`24,464 + 20,986 − 24,020 = 21,430`, margin 5,046).

**Four conditions on that answer, and none of them is optional:**

1. **Order of operations is load-bearing.** The dedup must land **first**. Option B applied to
   today's tree hard-overruns the anchor.
2. **The margin is thin.** 2,502 B is 10% of option B's cost. A 12% error in either number
   flips it. This makes option B *affordable*, not *comfortable*.
3. **Neither listing is current** (§4 — `839d600d` changed three `engine/level/*.emp` files
   after the debug listing was built). **Both numbers must be re-derived from a fresh
   `./build.sh` of both canonical shapes before the owner commits to option B on this basis.**
   The direction is robust — a docs-and-three-files delta cannot move an 18 KB shortfall — but
   a 2,502 B margin is exactly the size a stale listing can eat.
4. **The dedup is a byte-changing parcel.** It re-bakes level data, moves every downstream
   section, and owes the repin → refreeze `--ab` ritual; the base drift past sigil's frozen
   provisional table is a `[layout.provisional-drift]` WARNING, not a stop (sigil `b0363140`),
   but the refreeze is owed. A small alignment residue (bounded by the per-section alignment of
   the sections between the blobs and `Art_Sonic`) may cost back a few dozen bytes of the
   20,986.

**Side finding for `d-47`.** The card notes "a discrepancy I have not resolved" between its
24,160 / 21,920 room pair and the hub's 24,256 / 22,000. Partially resolved here: the **DEBUG**
number 21,920 reproduces exactly from `s4.debug.lst`; the **release** number does not — the
`s4.lst` on disk yields 24,464, a third value. Since the debug shape is the binding one, the
release discrepancy does not affect the decision.

---

## 7. What is booked, and what is deliberately not

**Nothing was fixed.** This parcel is docs-only and changes zero ROM bytes. Ready-to-make
one-line corrections, deliberately left for the owner:

| where | says | should say |
|---|---|---|
| `ENGINE_ARCHITECTURE.md:3699-3700` | `sec_raster_table` / `sec_pal` "have live consumers wired at the section-boundary crossing" | both have zero readers; the per-field path was deleted by effects-P3-C2 Task 13 |
| `ENGINE_ARCHITECTURE.md:2352` | engine level code reads "… `/sec_camera_lookahead`" | drop `sec_camera_lookahead` from the enumeration |
| `ENGINE_ARCHITECTURE.md:2394` | "The camera reads the current section's value" | scaffolding; write-only, no reader |
| `ENGINE_ARCHITECTURE.md:1299` | `Draw_BG_TileColumn` … "fixed 32-word strip" | 64-word strip, and the routine has zero callers |
| `ENGINE_ARCHITECTURE.md:2386` | "rows 0-31", "set once at level init" | rows 0-63 (NEW-5); two setters |
| `ENGINE_ARCHITECTURE.md:1715` | "4 KB nametable blit" | 8,192 B |
| `engine/system/constants.emp:272-274` | `POOL_TILE_CEILING(960)` → 15 frames, `// 15` | 896 → **14** |
| `engine/level/section.emp:389` | "BG layout is act-wide, not position-dependent" | the five lines below it read `Sec.sec_bg_layout` per section |
| `tools/ojz_strip_gen.py:137`, `tools/streaming_choke_probe.py:41` | `PAGE_FRAMES` = 15 | 14 |

Actionable items with real substance, in descending value:

1. **Per-block stream dedup in `ojz_block_gen.py`** — 20,986 B, zero engine change, zero new
   metadata (§5.6), and it lands in the budget `d-47` option B needs (§6).
2. **Local-map content dedup in `ojz_strip_gen.py`** — ~202 B, and the mechanism already exists
   in the neighbouring generator (§1, finding 10).
3. **Delete the nine dead `Sec` fields and the `pal:`/`raster:`/`cycle:` constructor
   arguments** — 288 B on this act, and the tree already contains the work order (§3).
4. **A build-time `ensure` that every `Sec` binds a preset**, or make `effects:` required the
   way `pal:` is — the real fix behind finding 7, better than any release-side runtime guard
   (§2).
5. `u16` block-index entries — a further 4,096 B, but needs an engine change and a cycle price.

---

## 8. TAGGED for the controller — wants runtime, not attempted

Carried forward from B's own tag list, unchanged and unattempted: (a) the real frame cost of
`Section_RedrawPlanes` with the display **on**; (b) the per-crossing cost of
`Effects_InstallPreset` including the ~19,332-cycle variant re-derive at speed; (c) whether a
16-frame `PAL_FADE_FRAMES` cross-fade is visually acceptable across a palette delta as large as
`OJZ_TestPal`.

Added by this audit:

(d) **Block-stream aliasing is verified by source reading only.** The claim that two index
entries may carry the same offset rests on `tile_cache.emp` never writing a ROM stream and on
`.empty_block` already aliasing a shared page. That reading is unambiguous, but a dedup parcel
should confirm it on a built ROM before landing — the replay fixtures plus a page-cache audit
pass would do it.
