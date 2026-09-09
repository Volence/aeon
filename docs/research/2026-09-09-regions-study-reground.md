# Re-grounding the painted-regions study against master, 2026-09-09

**Subject:** the four-lens painted-regions design study of 2026-08-29 — synthesis
`empyrean origin/main:docs/superpowers/specs/2026-08-29-painted-regions-design.md`, four reports
under `empyrean origin/main:docs/research/2026-08-29-painted-regions-study/`, and the `REGIONS`
record in `empyrean origin/main:contract/projects.json`.

**How the peer tree was read.** Every empyrean file above was read with `git show origin/main:<path>`
after `git fetch origin`, at empyrean `f6ad6f5` ("bars: a claim about an artifact is not the
artifact"), fetched 2026-09-09. That SHA is reachable at empyrean's `origin`, not local-only.
Nothing was read through the sibling checkout's working tree.

**Baseline and subject.** The study's inputs were read-only exports at aeon `243c62ca` and aurora
`c5d79e74`. This document's subject is aeon `master` at `d3339973`. `git diff --stat 243c62ca...master`
(three dots): **615 files changed, 165,036 insertions, 9,682 deletions**, over **1,333 commits**.

**No emulator was used.** Anything that wants a running ROM is TAGGED rather than attempted, and
no ROM was built in this worktree — every ROM-size figure below is attributed to the in-tree
evidence row that recorded it, not to a build of mine.

**Aurora's half is not re-grounded here.** The study's §7 corrections were verified in aurora's
tree; this document does not re-check them, and says so rather than implying coverage.

---

## 0. Counts, and the headline

**Claims checked: 37. HOLDS 21 · MOVED 12 · UNCHECKABLE 4.**
(34 from the study itself, plus 3 put to this lane by the controller and verified in §4.2b.)

The study's **shape is intact**. Not one of its architectural conclusions is refuted by eleven
days of churn. What moved is almost entirely **coordinates** — and they moved in one direction,
which is the finding:

> **Every VRAM number the study used got smaller, and the study's §5 dismissal — "the 448-tile
> ceiling is untouched by regions" — was written when the background arena had 128 tiles of
> headroom. It has 56 today, all of them already claimed, and the shipped background occupies
> 100% of the static budget. The 448-slot run is now exactly and fully allocated, with live art
> on both sides of the arena. Parcel 2's central deliverable, "a different background on the
> other side of an edge", has nowhere to put the second background — and its gating experiment
> cannot change that answer.**

Section 4 develops that. It is the part nobody has looked at, and it is where the study's
conclusions would most plausibly come out differently.

---

## 1. Every factual claim, checked

### §1.1 — "The identity layer already exists, one scope too coarse"

| Claim | Verdict |
|---|---|
| Identity is `EffectsPreset`, reached by `Sec.sec_effects` | **HOLDS.** `engine/effects/preset.emp` `EffectsPreset`; `engine/structs.emp` `Sec.sec_effects`; installed at the crossing by `Parallax_CheckBoundary` → `Effects_InstallPreset` (`engine/level/parallax.emp`). |
| `EffectsPreset` is **38 B** | **MOVED → 46 B.** `pub struct EffectsPreset (size: 46)` at `engine/effects/preset.emp` today; `git show 243c62ca:engine/effects/preset.emp` reads `(size: 38)`. The growth is `ep_patch_motion: [u16; RASTER_MAX_PATCH]`, EFFECTS-W1 item 4 — one packed sweep word per patch channel. |
| Preset binding is **already many-to-one** — "act 1: 9 sections, 6 presets, one preset covering four sections" | **MOVED → one-to-one.** At `243c62ca` the nine `effects:` bindings were `Sec0, Sec1, Sec2, Sec3, Depth, Plain, Plain, Plain, Plain` — six distinct, exactly as the study says. Today they are `Sec0, Sec1, Sec2, Sec3, Depth, Sec5, Sec6, Sec7, Plain` — **nine distinct presets over nine sections**. Sections 5, 6 and 7 acquired their own records during EFFECTS-W1; the first is `99d70db4` (2026-08-30, "split(sec5): section 5 owns its preset"). **This cuts against B, not against the study**: B's "a 1 B per-section id is what `sec_effects` already does" rested on the many-to-one binding being real and used. It is no longer used. Every section now carries its own identity record, which is precisely the redundancy a region scope collapses. |
| Of the 66-byte section record, **32 bytes are read by nothing**; nine dead fields | **MOVED — the cleanup happened.** `sizeof(Sec)` is **34 (`$22`)** today, eight fields. All nine names (`sec_plc`, `sec_pal`, `sec_raster_table`, `sec_pal_cycle`, `sec_sound_bank`, `sec_anim_blocks`, `sec_flags`, `sec_music`, `sec_camera_lookahead`) plus the three reserved pads were deleted at `980bf788` (2026-09-04, "parcel(painted-regions): the three code rows"), merged at `6048f065`. A grep of `engine/ games/` for the nine returns **prose only** — `engine/structs.emp`'s own deletion note, `engine/effects/palette.emp`'s history comments, `engine/level/camera.emp`'s note, and three doc/comment sites. 288 ROM bytes recovered on act 1. |
| "Three of the six fields the hub called identity are dead" | **Moot** — the fields are gone. |

### §1.2 — "Crossing detection is one routine and is already camera-centre based"

| Claim | Verdict |
|---|---|
| `Parallax_CheckBoundary` compares the section under the camera centre with the previous one and, on change, calls `Effects_InstallPreset` then `Parallax_StartTransition` | **HOLDS, unchanged in mechanism.** Read at `engine/level/parallax.emp`: `Camera_X + SCREEN_WIDTH/2` and `Camera_Y + SCREEN_HEIGHT/2`, `asr` by `SECTION_SIZE_SHIFT`, compare against `Parallax_Prev_Sec_X/Y`, then `jbsr Effects_InstallPreset` / `jbra Parallax_StartTransition`. |
| A rectangle test costs ~154 vs ~176 nominal cycles/frame; ROM neutral; RAM ~24 B | **UNCHECKABLE.** These price a routine that does not exist. What can be said is that the subject of the comparison is unchanged, so the estimate has not been invalidated by anything — it has simply never been tested. Settled by writing the rectangle test and counting, not by reading. |
| The one caller site | **HOLDS in count, and note the second.** `games/sonic4/test/ojz_scroll_test.emp` calls it per-frame and again on the DEBUG warp — two call sites, one game; `games/demo` never reaches it. |

### §1.3 — "Plane B is never redrawn on a crossing"

| Claim | Verdict |
|---|---|
| Plane B is painted at boot and on the debug warp, by a synchronous IRQ-masked blit | **HOLDS.** `Section_Plane_Dirty` still has exactly two setters, `games/sonic4/test/ojz_scroll_test.emp` at level init and at the DEBUG warp; `engine/level/section.emp` says so in as many words and is still right. |
| `Draw_BG_TileColumn` has zero callers | **HOLDS.** Tree-wide references are its own definition (`engine/level/plane_buffer.emp`), two prose mentions in `engine/level/bg.emp`, and one comment in `tools/inject_editor_bg.py`. No `jbsr`/`jsr`. |
| All nine shipped sections use one background | **HOLDS.** Every `ojz_sec()` row passes `sec_bg_layout: default` (NULL = the act-wide `act_bg_layout: OJZ_Act1_BG_Layout`). |
| Therefore "redraw the background on a region change" is a wholly new mechanism and is the entire price of the feature | **HOLDS.** `Draw_BG_TileRow` still does not exist: `grep -rn "Draw_BG_TileRow" engine/ games/ tools/` returns nothing. |

### §1.4 — "The classics stream Plane B every frame"

| Claim | Verdict |
|---|---|
| S3K / S2 / FBZ stream Plane B; 128-256 words a frame, 8-16 frames | **UNCHECKABLE from this tree** — it is a claim about reference disassemblies, verified by the D lane against them, and nothing here bears on it. |
| The aeon half of the convergence: "8,448 B at 4 entries a frame = 16 frames" | **HOLDS.** 64 plane-B column entries × 132 B = 8,448 B of producer output for a whole plane; `PLANE_BUFFER_SIZE = 1536` (`engine/system/constants.emp`) still admits 4 × 132 B = 528 B per frame with room. See §3 experiment 1 for the measured occupancy. |

### §1.5 — "The palette is the cheap half, and the classics snap it"

| Claim | Verdict |
|---|---|
| 96 bytes, CRAM lines 1-3, line 0 is the character's | **HOLDS.** `engine/effects/palette.emp` and `games/sonic4/data/effects/ojz_effects.emp` both still state the 48-word / 96-byte lines-1-3 contract; `ep_pal` is `EffectsPreset`'s first field and is `required`. |
| S3K replaces all 48 level entries in one frame mid-act, AIZ1 at `$1308`; no classic fades mid-level | **UNCHECKABLE from this tree** (reference-disassembly claim). |
| "Edges must sit in doors" is about the tiles, never the colours | **HOLDS as reasoning**, and §4 sharpens it: the tiles are now the binding constraint in VRAM as well as in time. |

### §1.6 — "The block dictionary is not a vocabulary and should stay where it is"

| Claim | Verdict |
|---|---|
| It is a 768-byte compressor pre-seed reached by `Sec.sec_block_dict` | **HOLDS.** `sec_block_dict` and `sec_block_dict_len` survived the 66→34 cut precisely because they are read (`engine/level/tile_cache.emp`). |
| Recoverable ~21 KB by per-block dedup; act-wide single dictionary is 930 B *worse* | **HOLDS as a measurement** (`docs/DEFERRED_WORK.md`, "BLOCK-STREAM DEDUP IS ~21 KB"), **and is unbuilt.** `tools/ojz_block_gen.py` still does whole-blob dedup only. |
| The smaller rider — `OJZ_Sec4_LocalMap` does not dedup though `OJZ_Sec4_Blocks` does | **DONE 2026-09-04** (`980bf788`): `emit_section_local_maps` in `tools/ojz_strip_gen.py` now carries the sha256 content dedup, 202 ROM bytes. |
| **The ROM-budget rationale behind it** — "only 5,536 B is spendable; after dedup d-47 option B fits with 2,502 B above the reserve" (synthesis §8) | **MOVED, and superseded entirely.** `446a27d9` (2026-09-04, "relayout(rom)") moved `dac_banks` `0x90000 → 0xA8000` and `sound_bank → 0xB8000`, tripled `DATA_GROWTH_RESERVE` `0x4000 → 0xC000`, and added a `DATA_GROWTH_GRACE = 0x8000` term *inside* the `align_up` and outside the gate threshold. Its own applied figures: **room in the binding shape 114,658 B, 65,506 B of it above the reserve.** So the dedup is no longer a precondition for anything — the thin-margin ordering constraint ("the dedup must land FIRST", "the margin is 10% of option B's cost") has evaporated. **The `DEFERRED_WORK.md` entry still carries the old arithmetic** ("Binding-shape room today is 21,920 B with a 16,384 B `DATA_GROWTH_RESERVE` floor, so only 5,536 B is spendable") and is stale in the favourable-to-urgency direction. |

### §1.7 — "The ROM argument is a wash"

| Claim | Verdict |
|---|---|
| ~+116 B for a rectangle table; saves at most 1.6 KB in the largest legal act | **UNCHECKABLE** — prices an unbuilt table. Nothing invalidates it. |
| "in a **719 KB** ROM on a 4 MB cartridge" | **MOVED → ~820 KB.** The most recent in-tree four-shape evidence row (`docs/DEFERRED_WORK.md`, the LS-16 closure, built 2026-09-07) records `s4.bin` **820,229 B** and `s4.debug.bin` **846,529 B**. **I did not build these; I am citing the row that did.** The growth is consistent with the `446a27d9` anchor move. The *conclusion* — the ROM argument is a wash — **holds a fortiori**. |

### §1.8 — "Collision and objects do not care"

| Claim | Verdict |
|---|---|
| Collision is a tile attribute read from the cache; objects and rings are loaded by position from a 2×2 section window; neither reads identity | **HOLDS.** `engine/objects/entity_window.emp` + `engine/ram.emp` still carry `Entity_Window_Active` as a **4-bit** validity mask over four quadrants with `Entity_Window_Anchor`/`OriginX`/`OriginY`. No identity read. |
| Rider: up to four sections from four regions can be live at once, so object art must stay act-scoped (it is) | **HOLDS today** — and §4 records that the owner has since asked for exactly the opposite (per-region object art lists), which turns this rider from an observation into a constraint the VRAM item must break or work around. |

### §2 — the four disagreements

| Disagreement | Verdict on its factual underpinning |
|---|---|
| Rectangles vs a 1 B per-section id | **MOVED in the study's favour.** B's case rested on `sec_effects` already delivering section-granular many-to-one sharing. Act 1 is now **one preset per section** (see §1.1), so the sharing B pointed at is not in use, and "a per-section byte" would today buy nothing over what already ships. |
| Is a sub-section edge affordable | **The two facts both HOLD.** 64×64 planes are unchanged (`PLANE_H_CELLS = PLANE_V_CELLS = 64`), so D's 288 hidden plane px (512 − 224) stands; and `CAM_MAX_X_STEP = 16` (`engine/level/camera.emp`, declared file-local and byte-gate-covered) confirms "the camera moves at most 16 px a frame". B's ">= 320 px of full occlusion" remains untested. |
| Precedence rungs | **HOLDS.** Three rungs are still three: engine/act default < `EffectsPreset.ep_parallax` (0 = defer) < `Sec.sec_parallax_config` (non-zero outranks), resolved by `Effects_ResolveParallax`. Nothing has added a fourth. |
| Fade or snap the palette | **HOLDS, and the untested combination is still untested — for a reason worth naming.** All nine act-1 presets bind `pal: OJZ_Palette` — the *same* palette record. So today no crossing changes a single CRAM entry, and "a 48-entry snap over a half-repainted plane" has never been on screen. See §3 experiment 2. |

### §3 parcel descriptions, as factual claims

| Claim | Verdict |
|---|---|
| Parcel 0: "Delete the nine dead `Sec` fields and their constructor arguments (32 B a section, and the false enumeration in `ENGINE_ARCHITECTURE.md` §4.2 that lists a dead field as read)" | **DONE.** Fields at `980bf788`; ARCH §4.2 rewritten in the same parcel and at `bb4a6bc3` ("docs(arch): correct four stale/false claims found by the painted-regions audit"). §4.2 now documents the 34-byte struct and names the deletion. |
| Parcel 0: "Guard `sec_effects == 0` in release, not only in DEBUG" | **DONE, but not the way the study proposed — and the substitute is stronger.** The release-side runtime test was **not** added. Instead `Sec.sec_effects` and `ojz_sec()`'s `effects:` argument both **lost their `= 0` defaults**, making an omitted binding a compile error in every shape at zero ROM bytes. The `if DEBUG == 1` `raise_error` survives for a poked `Sec*` or a corrupted `Act.sec_grid_ptr`. |
| Parcel 0: the withdrawn boot-position item | **Still correctly withdrawn.** `Parallax_Init` still writes the `$FF` sentinel and sets `Snap_Pending` on every boot branch. |
| Parcel 0: "Fix `PAGE_FRAMES`'s stale 15 (it is 14; art pool is 896 tiles, act 1 uses 612)" | **MOVED on all three numbers, and the drift is separately fixed.** `POOL_TILE_CEILING` is **768** today (was 896), so `PAGE_FRAMES` is **12**, not 14 or 15. Moved by `77cf6a71` (2026-09-03, "vram: item 0 Option P — POOL_TILE_CEILING 896 -> 768, spare_nametable at $6000"), which also deleted the stale `// 15` comment and replaced it with **no number at all** plus the reason. **`act 1 uses 612` HOLDS** — `OJZ_ACT_POOL_TILES = 612`, `OJZ_ACT_POOL_PAGES = 10`, byte-identical to `243c62ca`. So the brief's framing is worth correcting: act 1's *10 pages* is not new, the *pool* shrank around it. Margin was 4 frames; it is 2. |
| Parcel 0: "act-wide block dedup in `ojz_block_gen.py`" — separate parcel, big ROM win | **Not done.** See §1.6: still worth ~21 KB, no longer load-bearing for anything. |
| Parcel 1 (regions v1) | **Entirely unbuilt.** `grep -rn "struct Region" engine/ games/ tools/` exits 1; `resolve_region` exits 1; `regions.json` exits 1 — against a positive control (`grep -rln "struct Sec" engine/`) that exits 0 with a hit, so the instrument speaks. |
| Parcel 1: "run the existing `parallax_crossing_gate` with rectangles equal to today's sections and require byte-identical behaviour" | **The gate still exists and its coupling to `Sec` got tighter.** `tools/parallax_crossing_gate.py` **parses field offsets out of `engine/structs.emp`'s trailing `// $HH` comments** — those comments are a gate, not decoration, and `980bf788` re-derived the tool's offsets when the struct shrank. Note for whoever takes parcel 1: `tools/boot_override_gate.py` and `tools/preset_lab_witness.py` **hardcode** `SEC_SIZE` and per-field offsets, so a region record that changes the struct owes an edit in both. |
| Parcel 2 (background belongs to the region) | **Entirely unbuilt**, and its VRAM premise has moved hard — §4. |

---

## 2. What this does to the three parcels

### Parcel 0 (cleanup) — **substantially DONE; one item survives, demoted**

| Item | State |
|---|---|
| Nine dead `Sec` fields + constructor args | **DONE** `980bf788` (merged `6048f065`) — 66 → 34 B, 288 ROM bytes |
| `sec_effects` guard | **DONE** — as a comptime pin, not the proposed release runtime test |
| ARCH §4.2 false enumeration | **DONE** `980bf788` + `bb4a6bc3` |
| `PAGE_FRAMES` stale comment | **DONE** `77cf6a71` — and the underlying values moved |
| `OJZ_Sec4_LocalMap` dedup rider | **DONE** `980bf788` — 202 B |
| Act-wide block dedup (~21 KB) | **OPEN, and demoted from urgent to nice-to-have.** It was scheduled ahead of d-47 option B because only 5,536 B was spendable. There are 65,506 B above the reserve now. |

**Verdict: parcel 0 is finished except for a ROM-saving parcel that is no longer blocking
anything.** A resumed REGIONS project should not re-plan it; it should re-scope the dedup as an
independent tools parcel and drop the ordering constraint.

### Parcel 1 (regions v1, identity by rectangle) — **shape intact, and the case for it got stronger**

Nothing in eleven days weakened it, and one thing strengthened it: **act 1's preset binding went
from six presets over nine sections to nine over nine.** The study's argument was "identity
already exists at one scope too coarse". It is now one record per section with no sharing at all —
which is the *fine*-grained failure mode as well: authors are cutting new preset records because
the section is the only scope they can bind to. Both directions of the argument now point the
same way.

Size: unchanged in aeon (S-M), with two additions the study did not price —
`tools/boot_override_gate.py` and `tools/preset_lab_witness.py` carry hardcoded `Sec` strides and
offsets, so a struct change owes an edit in each, and `tools/parallax_crossing_gate.py` parses the
`// $HH` comments.

Dependencies: **all satisfied or neutral.** EFFECTS-W1 (the pause reason) reads `done`;
EFFECTS-W2 reads `done`, which retires the study's "EFFECTS-W2's per-act binding shrinks to a key
change" note — the per-act binding of `inject_editor_bg.py` shipped. No new blocker appeared.

**Verdict: right shape, unbuilt, unblocked, slightly under-priced on tools.**

### Parcel 2 (the background belongs to the region) — **shape intact, premise broken**

The data move is still a data move; `Draw_BG_TileRow` still does not exist; the plane-buffer
transport is still there. What broke is the assumption underneath: the study priced parcel 2 as
an *engine* problem (build a row streamer) with VRAM left out of scope. **VRAM is now the binding
constraint, not the streamer** — see §4. Parcel 2 cannot deliver "a different background picture
on the other side of an edge" at any engine size, because there are no tiles for the second
picture.

What parcel 2 *can* still deliver unchanged is the **Flying Battery case the study itself named as
its cheapest win**: one tile set, two anchors, the Step-5 triple moved into the region record.
That costs zero new VRAM and is unaffected by everything in §4.

**Verdict: split it.** The anchors half (FBZ case, tall backgrounds, d-31 option 3) is intact and
cheap. The different-art half is now gated on a VRAM decision, not on the row streamer.

---

## 3. The three gating experiments

### Experiment 1 — plane-buffer headroom at a crossing: **partly answered, and the part that was answered is not the part asked**

`tools/plane_buffer_headroom_probe.py` landed at **`d2c3dff0`** (2026-09-08, "probe(plane-buffer):
the overflow is silent in every shape, and the sizing now has a number"). It was opened by an
unrelated TAG (LS-15b-resid, about the authority for the 1536-byte buffer), **not** by this study.

**What it measured**, from its own commit message and source: peak `Plane_Buffer_Ptr` sampled at
`VInt_DrawLevel`'s entry *before* the drain, on a private headless instance —
**0 B at rest, 272 B of 1536 holding left or right**, against a silent-drop threshold of 1398 B.
It also found the load-bearing thing: `Draw_TileColumn` **drops a column and returns** on
would-be overflow **in every shape, with no `raise_error`**, and the caller records the column as
written, so an overflow costs a visible gap and reports nothing.

**What it did not cover**, stated in its own commit message rather than inferred: *"only horizontal
motion was driven. Vertical and diagonal motion, BG column entries, section transitions and
teleports are unmeasured."*

So against the experiment as specified — *run the existing `parallax_crossing_gate` across the OJZ
(0,0)|(1,0) edge and latch the per-frame maximum* — **the crossing itself was never sampled, and a
crossing is the one frame where the section-transition producer runs.** What the probe does give
is a strong prior in the wanted direction: at 272 B used, **1,126 B remain to the drop threshold**,
comfortably above the study's ~600 B "16 frames" branch and nowhere near its ~300 B "32 frames"
branch. Treat that as an encouraging lower bound on a narrower question, not as the answer.

**TAGGED for the controller:** re-run `plane_buffer_headroom_probe.py` (or the crossing gate with
the same latch) across a section boundary, with vertical and diagonal motion, before sizing the
wipe. The probe already exists; only the input script changes.

### Experiment 2 — a 48-entry palette snap over old art: **unanswered, and now known to be unreachable in the shipped act**

Nothing has run it. More usefully, I can say why it will not happen by accident: **all nine act-1
presets bind `pal: OJZ_Palette`** (`games/sonic4/data/effects/ojz_effects.emp`), so no crossing in
the shipped act changes any CRAM entry. The experiment still needs its two-preset fixture and is
still zero engine code.

### Experiment 3 — does a second background fit VRAM at all: **never run, and it no longer needs running — the answer is already no**

The experiment as specified has not been run. A repo-wide `grep -rn "lilypad" . --exclude-dir=.git`
returns exactly one hit — `games/sonic4/data/editor_sources.stamp.json`, the content stamp — so
`games/sonic4/data/editor/bg_src/ojz_cave_lilypad.png` is **tracked** (`git ls-files` shows it) and
**has never been run through the injector's quantise-and-dedupe**. The grep is not vacuous: it
found the stamp.

**But the experiment's decision thresholds are obsolete, and its question is settled without it.**
The study wrote "≤224 ⇒ the half-window split is viable; ~320 like the forest ⇒ two tile sets
cannot coexist". 224 was half of the 448-slot physical run. §4.3a below establishes that the BG
arena is **376 tiles with 320 already spent and physically boxed in on both sides**, so there is
no 224/224 split available at any tile count the lilypad could turn out to have. **Running it
would refine a number that cannot change the answer.** Its remaining value is as an input to a
future art pass or paging spec, not as a gate on parcel 2.

---

## 4. The gap the study does not cover: VRAM pressure as a design constraint

The study says *"the 448-tile ceiling is untouched by regions"* and treats VRAM as out of scope.
The owner has since made VRAM the third leg of the project. His words, from the `REGIONS`
`shapeNotes` at empyrean `f6ad6f5`, 2026-09-08T17:10:25Z:

> *"can we add something to the region project to talk about and figure out vram space, and what
> we can do to get more of it for objects sincei t's all eaten by level pretty much"*

and the goal he stated when the hub offered "5 pages" as a target (2026-09-08T17:39:31Z):

> *"I'm just trying to think of how we can get massive dynamic levels still while having space for
> objects within our system"*

### 4.1 What the map actually is today

Read out of `games/sonic4/vram.toml` at `d3339973` (parsed, not quoted from memory — the file's own
rule). Full coverage of tiles 0..2047 is build-stopping via `tools/gen_vram_map.py`.

| Region | Tiles | Note |
|---|---|---|
| `fg_art_pool` | **768** | 37% of VRAM; the FG residency cache, `PAGE_FRAMES = 12` |
| `plane_a` + `plane_b` | **512** | two 64×64 nametables, no art |
| `bg_region` | **376** | `band_reserve = 56`; static importer budget `376 − 56 = 320` |
| `spare_nametable` | **128** | freed by `77cf6a71`; a legal `$2000`-aligned plane base; nothing points at it |
| `waterline_strips` | 48 | EFFECTS-W1 item 9d |
| objects + characters | **152** | dust ×2, sparkle, insta-shield, Sonic 32, ring art, test squares, **spring 24** |
| tables + debug tags | 99 | `sprite_table`, `hscroll_table`, `tails_appendage`, 13 tiles of debug tags |
| **FREE** | **1** | tile 959 |

(`window_plane` 128 declares `overlay_with = ["plane_b"]` and is not additional.)

### 4.2 The three numbers the study used, and where they are now

| Study's number | Today | Moved by |
|---|---|---|
| FG art pool **896** tiles, `PAGE_FRAMES` **14** | **768**, **12** | `77cf6a71` 2026-09-03 |
| BG ceiling **448** tiles, headroom **128** | **`BG_TILE_CAPACITY = 376`**, reserve **56** | `8a18c205` (448→400, waterline strips), `917569e9` and `67458e39` (400→388→376, the spring's two sheets) |
| ROM **719 KB** | **820,229 B** (`s4.bin`, 09-07 evidence row) | `446a27d9` 2026-09-04 |

### 4.2b The BG ceiling, verified rather than inherited

The controller put three measurements to this lane with the instruction to check them rather than
agree. **All three verify**, and the conclusion drawn from them is right — but it is right for a
stronger reason than the arithmetic, and one of the three needs a correction in the unfavourable
direction.

**Verified independently, at `d3339973`:**

| Controller's claim | Check |
|---|---|
| `bg_tiles.bin` is 10,242 B = 2 + 320×32 | **Confirmed.** `/usr/bin/ls -la` gives 10,242 B; `xxd -l 4` gives `2800 8888` — the header word is `0x2800` = 10,240 = 320 × 32, and `BG_Init` copies the **declared** length. |
| `tools/bganim_vprobe_gen.py` states the same | **Confirmed** — "320 tiles (bg_tiles.bin = 2 + 320*32)". |
| `docs/generated/vram-map-sonic4.md` gives `bg_region` 1024-1399 = 376, "band_reserve: 56 (static budget 320)" | **Confirmed, and cross-checked against a second source** — `games/sonic4/vram.toml` parsed directly gives `bg_region` base 1024 / tiles 376 / band_reserve 56, agreeing with the generated map. `BG_TILE_CAPACITY` resolves to **376** (`engine/system/constants.emp`). |

**1. Is 376 really the ceiling, or can it grow into a neighbour? It cannot — and the reason is
stronger than "376 is what is declared".** The physical run is `$8000..$B7FF` = slots
**1024..1471** = 448, bounded above by the relocated SAT (`VRAM_SPRITE_TABLE`). That run is now
**exactly and fully allocated**:

```
1024-1399  bg_region          376
1400-1447  waterline_strips    48   <- Waterline_Art_Update's single DMA (engine/level/bg_anim.emp)
1448-1471  spring              24   <- loaded at level init (games/sonic4/test/ojz_scroll_test.emp)
                              ----
                               448
```

**Both neighbours have live writers**, so `bg_region` cannot grow by one tile without evicting
shipped art. And there is no slack on the far side either: 1472..1535 is packed solid by
`sprite_table` / `tails_appendage` / `debug_bganim_tag` / `hscroll_table` / `debug_raster_tag` up
to `plane_a` at 1536, which is `$2000`-aligned and cannot slide. The arena is boxed in on both
sides. **So 376 is not a current declaration that a re-cut could nudge — it is the wall.**

**2. What moved it from 448 to 376, and when.** Three commits, all in five days, and **every carve
came out of `band_reserve` rather than out of the shipped background**, which is why the static
budget held at exactly 320 throughout and the drop is invisible in the blob:

| Commit | Date | `BG_TILE_CAPACITY` | `band_reserve` | Taken by |
|---|---|---|---|---|
| (`243c62ca`, the study's baseline) | 2026-08-29 | **448** | 128 | — |
| `8a18c205` | 2026-09-04 | 448 → **400** | 128 → 80 | `waterline_strips`, 48 tiles (EFFECTS-W1 item 9d) |
| `917569e9` | 2026-09-08 | 400 → **388** | 80 → 68 | the spring's first sheet, 12 tiles |
| `67458e39` | 2026-09-08 | 388 → **376** | 68 → 56 | the spring's second sheet, 12 tiles |

**3. Is `band_reserve` 56 available to a second tile set? Physically yes; usefully no — and this
is where the controller's reading is generous.** The 56 slots (1344..1399) are genuinely
unwritten: the blob occupies 1024..1343 and nothing else points above it. But calling them
available overstates it three times over:

- **They are not spare capacity, they are a cap on the same blob.** `vram.toml`'s own note:
  *"A band's tiles ARE the front of `tiles` (its phase-0 IS the static art there; see
  `inject_editor_bg.py validate_band_coherence`), so animated slots are a subset of the blob,
  never an addition to it."* The reserve exists so a **BgAnim band can be inserted into the
  shipped background**, not so a second background can sit beside it. Spending it on a second
  tile set spends the animation dial.
- **They are already the designated scavenging pool, and it is nearly spent.**
  `docs/DEFERRED_WORK.md`'s `VRAM-NEIGHBOURHOOD` booking: *"56 reserve tiles remain, and they are
  the cheapest source for the next object that needs tiles — which is exactly how the spring took
  its twelve, twice."* The reserve has lost **72 of its 128 tiles in five days** to two consumers
  that were not backgrounds.
- **56 tiles is not a background.** The one we ship is 320.

**So the free figure for a second background is not 56. It is effectively zero**, and the
controller's consequence holds a fortiori: experiment 3 is answered, parcel 2's art half is
decided (one tile set, two anchors), and BG tile paging moves onto the critical path for any
region that wants a genuinely different picture. The one thing worth stating that the
arithmetic alone does not: **because the arena is boxed in, "get more BG tiles" is not a
one-region edit to `vram.toml` — it is a re-cut that must displace `waterline_strips`, the spring,
or the SAT itself, each of which has a live consumer.** That is a VRAM-leg decision, not a
parcel-2 one.

**A prose-drift rider found while checking this, worth a one-line fix:** both
`engine/system/constants.emp` (above `BG_TILE_CAPACITY`) and `engine/level/bg.emp` (above
`BG_TILE_REGION_BYTES`) still say in prose *"the BG arena OWNS only `BG_TILE_CAPACITY` = **400**"*
while the constant three lines below reads **376**, and the `VRAM-NEIGHBOURHOOD` booking's own map
paragraph says `bg_region` **388** against its own "Current values" paragraph's 376. Same drift
class parcel 0 just cleaned out of `Sec`; the numbers moved twice in one day on 09-07/08 and the
prose kept one of the intermediate values each time.

### 4.3 The conclusions that were reached without VRAM pressure, and what changes

**(a) "The 448-tile ceiling is untouched by regions" (§5) — the sentence is now actively
misleading, in two different ways.**

*First:* 448 is the **physical** run `$8000..$B7FF` under the relocated SAT, and it is genuinely
untouched. But it has not been the **usable** ceiling since 2026-09-04. What the BG arena owns is
`BG_TILE_CAPACITY = 376`, of which 56 are `band_reserve`, leaving a static importer budget of
**320** — and **the shipped forest background blob is exactly 320 tiles**
(`tools/test_bg_tile_budget.py::TestBakedBlobOccupancy`, and `vram.toml`'s own region comment).
**The background arena is at 100% occupancy with zero slack.**

*Second, and this is the part that changes a design conclusion:* the ceiling is not untouched by
regions **in the other direction**. Regions are the mechanism that would *demand* a second
background, and there is no room for one. Experiment 3's "≤224 ⇒ the half-window split is viable"
branch **cannot be taken at any tile count**, because splitting 376 gives two arenas of 188 and
the one background we ship needs 320 — and, per §4.2b, the 448-slot run those numbers sit in is
**exactly and fully allocated with live art on both sides of the arena**, so the shortfall cannot
be closed by a declaration. The study's own fallback — *"Flying Battery's answer (one tile set,
two anchors) is the only option until paging lands"* — is not a fallback any more. **It is the
only reachable form of parcel 2.** That was a conditional in the study, resolved by an experiment
nobody had run; today it is unconditional and the experiment cannot change it, and it should be
written into the parcel rather than left as a branch.

**(b) The whole framing "regions consume the background rather than carry it" was priced as an
engine problem.** The study's parcel 2 size (aeon M, gated on three experiments) is a *streamer*
price. The streamer is not the blocker. A parcel that builds `Draw_BG_TileRow`, the tracker, the
16-frame wipe and the scroll clamp, and lands green, still cannot show a second background —
because the second background has nowhere to live. **The ordering the study proposed (streamer
first, paging in parcel 3) inverts under VRAM pressure**: BG tile paging, which the study parked
at "parcel 3, an open spec that cannot be taken before the streamer", is the thing that decides
whether the streamer has anything to stream. That claim of ordering deserves re-testing rather
than inheriting.

**(c) "Object art must stay act-scoped (it is)" (§1.8's rider) is the assumption the owner has
asked us to break.** From `shapeNotes` 2026-09-08T17:39:31Z, the hub's tier reading of the owner's
goal:

> *"OBJECT art, resident with no region concept, the missing tier: an object art list PER REGION
> (enter a cave, load its badniks and hazards into the object pool; leave, release), the
> originals' per-act PLC list extended to regions, so object variety costs ROM not VRAM."*

The study treated this as a *safety* observation — four sections from four regions can be live at
once, therefore act-scoped art is required for correctness. That reasoning is still sound **as a
constraint on the mechanism**, and it is exactly why a per-region object PLC is not free: the
entity window is 2×2, so a region-scoped art list must be resident for every region the window can
touch, not just the one the camera centre is in. **The study's rider is the design constraint on
the owner's ask, and neither document currently says so.** Whoever plans the VRAM leg should
start from it.

**(d) `sec_plc` was deleted eleven days ago, and it is the field the owner's ask wants back.**
`980bf788` removed `sec_plc` as dead — correctly, it had zero readers and was booked nowhere. But
a per-region object art list *is* a PLC list, and the study's own parcel 3 says "the art PLC list
[is a] region-record field the day something reads them". This is not a mistake in the deletion —
the deletion note and ARCH §4.2 both say a field can be re-added when a consumer wants one, rather
than reserved indefinitely — but it is worth naming plainly so nobody re-discovers it as a
regression: **the region record, not `Sec`, is where the PLC belongs, and that was already the
study's conclusion.**

**(e) Two levers the study never considered because it was not looking at VRAM, both now on the
table and both interacting with parcel 2.**

- **`fg_art_pool` = 768 tiles, 37% of VRAM, and the streaming path has never actually streamed.**
  `OJZ_ACT_POOL_PAGES = 10` against `PAGE_FRAMES = 12`, so `Level_LoadArt` latches
  `PageIn_Fully_Resident` and `PageCache_Direct_Map` (`engine/level/load_art.emp`) and nothing is
  ever evicted. The owner reframed the measurement precisely (2026-09-08T17:33:38Z): *"is it
  whether act 1 needs that many or is it 'does our view need that many loaded at onces to have
  seemless gameplay'?"* — i.e. the **working set**, not the act total. **This is the single
  highest-value measurement REGIONS could commission**, and it is a strict prerequisite for
  parcel 2's art half: whatever the FG pool returns is the only plausible source of a second
  background's tiles. It also means shrinking the frames below 10 would put the eviction path into
  service for the first time on a shipped act.
- **Plane size.** `PLANE_H_CELLS = PLANE_V_CELLS = 64` costs 512 tiles for the pair; 64×32 would
  return 256. The hardware fact recorded in `shapeNotes` (2026-09-08T17:41:54Z) is that **VDP
  register `$10` sets one size for both planes**, so the background cannot be 64×32 while the
  foreground stays 64×64. And ARCH's own "Why 64×64 scroll planes" table gives the two reasons —
  a 36-row vertical buffer for the mega-act's transitions, and **±288 px of VSRAM deformation
  range against ±32 px**, which the raster/parallax effects EFFECTS-W1 just shipped rely on.
  **Note the collision with §2 of this document:** D's "a 16-frame vertical wipe needs no cover"
  argument is built on 288 px of hidden plane margin. **Taking the 64×32 lever would delete the
  argument that makes parcel 2's vertical edges seamless.** Nobody has said that out loud yet, and
  it is the cleanest example of why the VRAM leg cannot be planned beside the region leg — it has
  to be planned inside it.

### 4.4 The short version

Of the study's eight established points, **six were reached without VRAM as a constraint and are
unaffected by it** (§1.1, §1.2, §1.5, §1.6, §1.7, §1.8 — identity, crossing detection, palette,
dictionary, ROM, collision). **Two were not, and both come out differently:**

- **§1.3/§1.4 → parcel 2.** The conclusion "a plane-B streamer is the entire price of the feature"
  is false under VRAM pressure. The streamer is the price of the *anchors* case (FBZ, tall
  backgrounds), which is genuinely reachable today. The *art* case is priced in tiles, and the
  tiles are at zero.
- **§5's "the 448-tile ceiling is untouched by regions".** The number is 376 with 320 spent, and
  the ceiling is what parcel 2 collides with head-on rather than something regions route around.

Everything else in the study stands.

---

## 5. What is TAGGED, and what is not claimed

**TAGGED for the controller (needs a running ROM; no emulator was used here):**
1. Experiment 1 proper — plane-buffer peak **at a crossing**, and under vertical/diagonal motion.
   The instrument exists (`tools/plane_buffer_headroom_probe.py`); only the driving script changes.
2. The FG working-set measurement the owner commissioned (peak distinct pages in the visible
   window; lookahead from ZX0 page-in latency against spindash speed; page re-entry frequency
   after eviction). This is the number parcel 2's art half depends on.
3. Block-stream aliasing confirmation on a built ROM, which the study's §8 already flagged as a
   fourth runtime question and which is still open.

**Not claimed:**
- No ROM was built in this worktree. Every ROM-size and CRC figure is attributed to the in-tree
  evidence row that produced it.
- Aurora's half of the study (§7's corrections) was not re-checked; it was verified in aurora's
  tree at authoring time and this document says nothing about its currency.
- The cycle estimates in §1.2 and the ROM estimates in §1.7 price routines and tables that do not
  exist. They are marked UNCHECKABLE rather than HOLDS, because nothing tested them then either.
- The `REGIONS` record at empyrean `origin/main:contract/projects.json` still reads
  `"state": "paused"` as of `f6ad6f5`. If the project was unpaused on 2026-09-09, that has not
  reached empyrean's `origin/main` yet. Stated as an observation about the record, not as a
  contradiction of the instruction.
