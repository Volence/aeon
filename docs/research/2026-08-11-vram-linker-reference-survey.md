# Reference survey — VRAM organization in nine shipped-game disassemblies + requirements set

**Provenance:** research subagent output, 2026-08-11, dispatched for the
VRAM-linker design (see docs/research/2026-08-11-vram-allocation-brief.md).
Banked verbatim from the agent transcript.

---

All nine studies are done. Here is the full report.

# VRAM Organization in Shipped Genesis Games — Source Study

## 1. S.C.E. (`/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/`)

**Map expression.** Hybrid. A tiny global constants block of 13 `ArtTile_*` equates for universal objects (`Engine/Constants.asm:776-788` — SpikesSprings $484, Monitors $4AC, Sonic $680, Ring $6BC, HUD $6C8, Shield $79C, DashDust $7E0), plus VDP fixed regions as constants (`Engine/Constants.asm:830-838`: plane A/B, SAT $F800, hscroll $F000). Everything zone-specific is **raw literals**: `plreq $47E/$500/$580/$592` in per-act PLC lists (`Data/Pattern Load Cues.asm`, e.g. `PLC1_DEZ1_Before`, `PLC2_DEZ1_After`), and 18 distinct raw `make_art_tile($xxx,...)` literals across 64 call sites (`Objects/Main/Animals/Animals.asm:185-195`, `Spring/Spring.asm:45`, `Title Card/Title Card.asm:71`, `Egg Capsule/Egg Capsule.asm:653-655`). Helpers `make_art_tile`/`tiles_to_bytes` are AS `function`s (`Engine/Macros.asm:68,71`). Rough distinct hand-placed addresses: **~35**.

**Overlays.** Inherits S3K's dash-dust ↔ drowning-digits share: `AirCountdown_Load_Art` DMAs digit frames into `tiles_to_bytes(ArtTile_DashDust)` (`Objects/Main/Count Down/Count Down.asm:412-437`); guards are `cmpi.b #12,air_left / blo` before spawning dust (`Objects/Players/Spin Dust/Spin Dust.asm:77-82` and `:205-208`) and in `Player_ResetAirTimer` (`Count Down.asm:~447`). Second case: title card at `make_art_tile($500,...)` (`Title Card.asm:71`), results screen at $500 (`Results/Results.asm:116`), and the Spikebonker badnik PLC'd to $500 *after* the title card (`PLC2_DEZ*_After`) — a pure temporal handoff whose only "coordination" is PLC list ordering. No guard, no comment.

**Per-zone.** Per-act Before/After PLC lists with raw addresses; non-overlap guaranteed by nobody. **No build-time check.**

**Streamed.** Player DPLC window at $680 (`Sonic.asm:2974`); window size is implicit in the gap to `ArtTile_Ring` $6BC. Nothing verifies peak DPLC frame fits.

**Tooling.** The most assert-rich tree — but only for non-VRAM things: RAM overflow (`Engine/Variables.asm:456`), DMA source odd/zero/128kB-boundary (`Engine/Core/DMA Queue.asm:195-204`), buffer size (`Core/Load Level.asm:161`). **Zero VRAM-overlap checks.** `build.sh` is asl+p2bin+convsym+fixheader, no generation step.

## 2. skdisasm / S3K (`/home/volence/sonic_hacks/skdisasm/`)

**Map expression.** The worst symbolic coverage of the three Sonic trees: only **20** `ArtTile_*` constants (`sonic3k.constants.asm:1067-1097` — menus, monitors, players, ring, shield, dash dust). Against that: **1093** `make_art_tile` call sites of which **328 distinct raw tile literals** (e.g. `sonic3k.asm:5996` `make_art_tile($500,3,1)`, `:6085 ($4C0...)`, `:6145 ($680...)`), **119 distinct raw `plreq` destinations** (`PLC_0B` at `sonic3k.asm:199543`: `plreq $41B, ArtNem_AIZSwingVine` etc.), and **72 `zoneanimdecl` entries** whose third parameter is a raw VRAM tile (`AniPLC_AIZ1` at `sonic3k.asm:55573`; macro at `sonic3k.macros.asm:165-172`). Rough distinct hand-placed: **400+**. The PLC address and the object's `art_tile` literal must agree by hand across ~200k lines.

**Overlays.**
- *Dash dust ↔ drowning digits* (the canonical case): `AirCountdown_Load_Art` DMAs the digit frame to `tiles_to_bytes(ArtTile_DashDust)` or `_P2` (`sonic3k.asm:33463-33487`). Guards are **scattered at every dust-producing site**: skid-dust spawn checks `cmpi.b #12,air_left / blo` (`sonic3k.asm:22849`, `:22915`, `:28094`, `:28160`, `:32122`, `:32188` — six copies across Sonic/Tails/Knuckles code) plus inside the dust object itself (`:34237`). This is the cost profile of hand-sharing: N call sites each must remember the guard.
- *Equal-valued constants as state overlays*: `Competition_ModeSel = Competition_Results = $034A` (`sonic3k.constants.asm:1071-1072`), `Save_Misc = Competition_LevSel = $029F` (`:1070,1076`) — different menu states, same tiles, coordinated by full reload on state change.
- *Whole-map takeover*: menus decompress over the level-art region (`ArtTile_ArtKos_S3MenuBG = $0001`, used at `sonic3k.asm:13480`).
- Bugs: 71 `FixBugs` blocks exist but none I found documents a VRAM-sharing bug in this tree; the sharing design itself is what forces the air_left guards. Comments like `; Start at $A000` / `; Origin at $A000` (`sonic3k.asm:5996-6230`) are the only human-readable trace of the layout.

**Per-zone.** `Offs_PLC` per-act offset table (`sonic3k.asm:199357+`) → per-zone PLC lists; per-zone `AniPLC_*` lists; per-zone `levartptrs` MLLB (`sonic3k.macros.asm:175-179`). Non-overlap: by hand. Build check: **none** (only org-overflow and soundbank-size errors, `sonic3k.macrosetup.asm:13-37`, `sonic3k.macros.asm:288`).

**Streamed.** Player DMA windows `Player_1` $680 / `Player_2` $6A0 / `Player_2_Tail` $6B0 (`constants:1090-1092`, used `sonic3k.asm:25234-25545`). Peak-size fit is implicit in neighboring constants; **no comments, no checks**.

**Tooling.** None for VRAM.

## 3. s2disasm (`/home/volence/sonic_hacks/s2disasm/`)

**Map expression.** The gold standard retrofit: **299 `ArtTile_*` equates** in one file (`s2.constants.asm:2216-2650`), organized by *screen mode* (Sega/title/credits/menus/special stage/ending/continue) then *zone*, then *bosses*, then *universal*, with prose headers. Of 654 `make_art_tile` sites, **638 are symbolic; only 2 raw-literal sites remain** (`s2.asm:84199,84207`); 0 raw `plreq`. Per-screen-mode VDP region constants too (`s2.constants.asm:2211-2213`). This tree proves full symbolization of a shipped game's VRAM map is achievable — and it's the only tree where sharing is *visible by reading one file*.

**Overlays — declared as equal-valued constants, zero runtime guards:**
- `TitleCard = $0580 = Animal_1` (`s2.constants.asm:2562` vs `:2555`) — title card at act start, animals at act end.
- `Signpost = $0434 = Spikes` (`:2566` vs `:2318`) — end-of-act signpost over spike art.
- `Game_Over = $04DE = Invincible_stars` (`:2559` vs `:2589`).
- `Capsule = $0680 = Powerups` (monitors) (`:2572` vs `:2590`) — boss capsule over monitor art.
- `ContinueTails = ContinueText = $0500` (`:2284-2285`); `SpecialStart = SpecialBomb = $038A` (`:2261-2262`).
- `CNZBoss_Fudge = CNZBoss - $60 ; Badly reused mappings...` (`:2529`) — negative-offset aliasing hack to make reused mappings land right.

**Documented bug (the money citation):** `s2.asm:10326-10341` — Game Over in HTZ corrupts Tails on the Continue screen because `Dynamic_HTZ`'s cloud-art DMA was **queued** for the HTZ layout, the state changed, and the transfer landed on `ContinueTails` art. The `fixBugs` fix clears the DMA queue on Continue entry. Failure class: *asynchronous transfer outliving the state that owned the destination region*.

**Per-zone.** Dedicated constants sections per zone; level art always at $0000 with per-zone `NumTiles` constants, including partial-overwrite sharing: `NumTiles_HTZ_Sup = $0183 ; Overwrites several EHZ tiles` (`:2298-2300`), WFZ over SCZ (`:2305-2307`), `NumTiles_DEZ ; Skips several CPZ tiles` (`:2308`). Non-overlap: human review of the file. Build checks exist **for RAM only** (`fatal "Special stage variables exceed size of shared RAM."`, `s2.constants.asm:2045-2046,2061`) — never for VRAM.

**Streamed.** Sonic/Tails DPLC windows $0780/$07A0/$07B0 (`:2593-2595`); `Dynamic_HTZ` camera-position-driven background art streaming (`s2.asm:85503+`); signpost frame streaming (`PLCLoad_Signpost`, `s2.asm:34405`). Fit: implicit spacing. Notably, the **HUD chain comment** (`s2.constants.asm:2598-2603`) explicitly documents position-coupled allocation: HUD/powerup tiles are linked through mappings and "will probably have to edit the mappings (or move the power-ups and HUD as a single block unit)".

**Tooling.** None — the map is hand-curated; nothing generates or verifies it.

## 4. Batman & Robin (`.../The Adventures of Batman and Robin/disasm/`)

**Map expression.** No constants of any kind (machine-generated disasm). VDP destinations are raw command immediates scattered in code (`#$40000080`, `#$43000003`, `#$47600080` … ~16 distinct static ones across `code/**`) plus **runtime-computed** commands (`code/engine/interrupts.asm:236-241`: `lsl.l #2 / lsr.w #2 / ori / swap` — the classic address→command conversion from a RAM variable). Effects engine issues **zero direct VDP writes** — everything goes to RAM buffers (`EFFECTS_ENGINE.md:12-14`).

**Overlays.** Not observable as discrete cases; the architecture is frame-granularity multiplexing — procedurally generated effect tiles are re-streamed into fixed windows every frame (`ART_AND_COMPRESSION.md:25-37` — 3920-byte active-display bursts at `$00784A`; §3 software rasterizer). No guards visible; ownership is "whoever wrote the buffer this frame."

**Per-level.** Level nametables stored in **final VDP format** at $100000+ (`ART_AND_COMPRESSION.md:80-99`) — tile indices, palette, flip bits pre-baked. This means the original dev pipeline resolved VRAM layout **offline, at build time** — the closest 1990s analogue of a VRAM linker, though output-only and invisible in this tree.

**Tooling.** None in repo; inferred offline pipeline per above.

## 5. Gunstar Heroes (`.../gunstar_disasm/`)

**Map expression.** None symbolic. **13 distinct static VDP DMA command literals** in the whole ROM (`code/disasm.asm` — VBlank block lines 495-560 with `#$74000083`, CRAM `#$c0000000/#$c0000080`; enqueue subs at lines 988-1046 with `#$70000083` (SAT), `#$40000090` (VSRAM)). Everything else is runtime-built entries in a RAM DMA queue at $F400, drained as 14-byte blocks in VBlank (`loc_000DDA`, lines 536-551; matches `ANALYSIS.md:117-134`).

**Overlays.** Fixed VRAM/CRAM/SAT windows with **flag-selected prebuilt variants**: `btst #1/#2, $f7e7` chooses between two DMA parameter sets (lines 1006-1013, 1038-1044), `tst.b $f755` flips CRAM destination $0 vs $80 (lines 512-533) — page-flip/double-buffer coordination via RAM flags. Guards: the flags are the whole mechanism. Bugs: not found.

**Per-level.** Data-driven from level scripts in DATA regions (`MEMORY_MAP.md`); layout opaque in the raw disasm — **not found**.

**Streamed.** Sprite art pre-rendered then DMA'd from RAM buffers per frame (`ANALYSIS.md:130-134`); fit guaranteed by fixed buffer sizes, not checks.

**Tooling.** None.

## 6. Alien Soldier (`.../aliensoldier_disasm/`)

**Map expression.** Even more extreme: **4 static VDP command literals total** (`code/disasm.asm:326,342,740,768` — SAT `#$70000083`, VSRAM `#$40000090`). VDP command sequences are **pre-built into fixed RAM blocks** ($84A0, $8560 …) during the main loop; VBlank just blasts them (`code/disasm.asm:343-360`; `ANALYSIS.md:145-148`). The VRAM map exists only as data baked into those block builders.

**Overlays.** Same `$f7e7` variant-flag pattern as Gunstar (lines 312-335: `#$93029400` vs `#$93c09401` SAT transfer sizes). RLE sprite frames decompress to RAM and re-stream to fixed windows each frame (`ANALYSIS.md:151-156`) — frame-granularity ownership, no static owners at all.

**Per-level / tooling.** Data-driven; not found / none.

## 7. Thunder Force IV (`.../thunderforce4_disasm/`)

(Per the brief, I ignored ANALYSIS.md's claims and verified from code.)

**Map expression.** No symbolic map, and remarkably **zero static VDP DMA command immediates** matched anywhere in the 64k-line disasm. The VRAM destination is a **RAM cursor variable**: `sub_000866` seeds `$F118` with `#$8000`, `sub_00086E` with `#$F800` (`code/disasm.asm:157-162`), a loader consumes it, and it is bumped `addi.w #$20, $f118.w` after each load (line ~181) — a runtime **bump allocator** advancing one tile at a time as art is loaded sequentially. Two seed bases = two banks/contexts.

**Overlays / per-level.** The dual cursor bases are the only visible multiplexing; per-stage loaders re-seed the cursor. Details of per-stage layout: **not found** (implicit in load order and data sizes — fit is guaranteed by nothing but the data itself).

**Tooling.** None.

## 8. Ristar (`.../ristar_disasm/`)

**Map expression.** Raw disasm; **~77 distinct VDP command immediates** scattered through `code/disasm.asm` (30× `#$40000010` VSRAM, `#$70000003`, `#$6c000002`, etc.). No constants; SAT is a $EC00 RAM mirror DMA'd first each VBlank (`ANALYSIS.md:275`).

**Overlays.** Not concretely observable in the raw disasm — **not found**. Per-stage HInt scripts (RAM-patched handlers) imply per-stage raster/VRAM ownership conventions but no discrete two-owner case surfaced.

**Per-zone.** Per-stage art loads (Star/Nemesis compression) with inline destinations. Notable streaming detail: the decompressor is **interruptible/yieldable** with a busy flag at `$E5BC` (`ANALYSIS.md:79,185-190`) — decompression sliced across frames, the 1994 ancestor of Aeon's §9.7 bookmark decoder.

**Tooling.** None.

## 9. Vectorman (`.../vectorman_disasm/`)

The most architecturally interesting for an allocator design.

**Map expression.** No static map. Each object carries its **VRAM base as an object field**: `$20(a4)` = tile base, `$1A(a4)` = frame DPLC list pointer, dirty bit in `$1E(a4)` (`code/disasm.asm:7431-7476`). Slot values come from object init data — i.e. **authored offline into data tables**, not code.

**Streamed window with budget + rollback.** `sub_007826` (`code/disasm.asm:6288-6337`, matching `ANALYSIS.md:103-137`): streams the object's current frame into its window, bump-advancing the destination (`add.w d3,d0`), with hard per-frame budgets — max `$36` (54) queue entries and `$B40` (2880) bytes — and, critically, **transactional rollback**: on budget overflow (`loc_00788C`) it restores the saved queue pointer and entry count, discarding the whole object's batch, and returns failure so the caller keeps the dirty bit set (`:7437-7440` — the `beq` skips clearing it) and the object retries next frame. Double-buffered queue drained in VBlank (`ANALYSIS.md:140-175`).

**Overlays.** The entire sprite arena is time-multiplexed at frame granularity between whichever objects hold slots; slot non-overlap is guaranteed by the offline-authored slot data. Not found: the authoring-side table itself.

**Tooling.** None visible; the slot assignments are baked data (an offline allocation decision, like B&R's nametables).

---

# Synthesis

## Taxonomy of VRAM lifetimes actually observed

| Lifetime / pattern | Observed in | Mechanism |
|---|---|---|
| **Permanent (whole-game)** | S2/S3K/S.C.E. universal window $680-$7FF (players, ring, HUD, shield, dust); VDP tables (planes/SAT/hscroll) | Global equates; VDP-register-pinned |
| **Per-mode full-map takeover** | S2 screen-mode sections (title/menus/SS/continue/ending), S3K menus over level art | Full reload on state transition; constants files sectioned per mode |
| **Per-zone/per-act static pools** | S3K `Offs_PLC` per-act lists, S.C.E. Before/After act lists, S2 per-zone constant sections; partial cross-zone overwrites (HTZ over EHZ, WFZ over SCZ) | Hand-placed addresses in PLC lists that must match hand-placed literals in object code |
| **Per-state overlay within a mode** | Signpost/spikes, title-card/animals, capsule/monitors, game-over/invincibility-stars, boss-over-zone-pool (all S2, declared by equal constants); drowning-digits/dash-dust (S3K + S.C.E.) | Temporal sequencing; runtime guards ONLY where overlap can happen mid-state |
| **Streamed / DPLC window** | Player art windows (S2/S3K/S.C.E.), Dynamic_HTZ camera-driven, Vectorman per-object windows, TF4 bump cursor, Ristar yieldable decompressor, B&R per-frame procedural streams | Fixed base + implicit peak size; Vectorman adds per-frame budgets with transactional rollback |
| **Double-buffered / variant-flipped** | Gunstar/Alien Soldier `$f7e7` flag variants, CRAM $0/$80 flip, TF4 $8000/$F800 dual cursor, S3K DashDust vs DashDust_P2 | RAM flags select between prebuilt parameter sets; per-player window replication |
| **Position-coupled blocks** | S2 HUD/powerup chain ("move as a single block unit", `s2.constants.asm:2598-2603`); `CNZBoss_Fudge = CNZBoss-$60` aliasing | Mappings bake relative offsets; regions immovable independently |
| **Offline-baked layout** | B&R nametable-format level data; Vectorman slot fields in init data | The original studios' build pipelines WERE primitive VRAM linkers — output only, never verified in-ROM |

## Guards and bugs from hand-sharing

- The **only runtime guard pattern** found is the S3K `air_left >= 12` class — and it must be replicated at *every* producer site (six+ copies across three characters in S3K, two more in S.C.E.). Hand-sharing scales guards linearly with call sites.
- The **one fully documented bug** is exactly the failure a linker can't fix but must make visible: S2's HTZ-cloud-DMA-over-Continue-art (`s2.asm:10326-10341`) — a *queued* transfer crossing a state boundary into a region the new state owns. The fix (clear DMA queue on state entry) is an ownership-transition contract.
- Secondary evidence of pain: `CNZBoss_Fudge ... ; Badly reused mappings...`, the HUD "edit the mappings" warning, and S3K's 328 unlabeled literals that make sharing undiscoverable.
- **Build-time VRAM verification: zero, in all nine projects.** Every tree that asserts anything asserts RAM/bank sizes (s2 `fatal` at `s2.constants.asm:2045`, S.C.E. `Variables.asm:456`, skdisasm soundbank) and S.C.E. asserts DMA *source* validity (`DMA Queue.asm:195-204`) — never destination overlap. A declarative VRAM linker has no precedent in any reference; the culture of build-time `fatal` checks (S.C.E., s2) shows the toolchain could always have done it.

## Requirements a declarative build-time allocator must express (derived from observed usage)

1. **Named regions, symbolic-only references** — ban raw tile literals; the s2 retrofit (638/654 sites symbolic) proves shipped-game coverage is fully expressible symbolically.
2. **Lifetime scopes** (global / mode / zone / act / state) — overlap is an error only between regions whose lifetimes can coexist; regions in disjoint modes may alias freely (formalizing the s2 constants-file structure).
3. **Explicit overlay declarations** — two owners of one range must be declared as a pair (signpost/spikes class), turning today's silent equal-valued constants into checked intent, and enumerating the guard obligation where overlap is mid-state (drowning-digits class) so debug builds can assert ownership at DMA time.
4. **Streamed windows with declared peak size**, verified against the actual art at build time (max DPLC frame ≤ window) — no game checks this today; spacing is implicit and silent.
5. **Arena regions** the allocator reserves but does not subdivide, for runtime bump/budget allocators (Vectorman's 54-entry/$B40-byte transactional queue, TF4's cursor).
6. **Grouped/anchored blocks** — regions whose relative offsets are consumed by mappings move only as a unit (S2 HUD chain), including derived sub-regions via offset arithmetic (`Ring+4`, `HUD+$18`, even negative aliases like `CNZBoss-$60`).
7. **Pinned regions** — VDP-register-configured tables (planes/SAT/hscroll) and any window whose address is baked into data.
8. **Replicated instances** — per-player window pairs (DashDust/_P2), double-buffer pairs (TF4 $8000/$F800).
9. **Per-zone parameterization** — one logical region name resolving to different physical bases per (zone, act), so object code references the name and PLC/anim tables are generated, eliminating the S3K 328-literal hand-coupling.
10. **State-transition contracts as build output** — per-state ownership tables the engine can check (and DMA-queue flush points at ownership boundaries), directly addressing the S2 HTZ→Continue bug class of queued transfers outliving their owner.
