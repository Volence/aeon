# Engine Phase 3 — Cleanup, Comment Hygiene & Doc Reconciliation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A behavior-preserving cleanup that leaves the engine *verified* clean and makes `ENGINE_ARCHITECTURE.md` + code comments describe the shipped engine as the design — not as "old-thing-plus-patches."

**Architecture:** Two deterministic code edits (a debug scaffold + a stale capacity constant) and two deterministic doc edits, plus a hybrid **verified-clean audit** (mechanical symbol cross-reference → adversarial verify) that covers dead code, orphaned symbols, whole-engine comment hygiene, *and* a systematic `ENGINE_ARCHITECTURE.md`-vs-code contradiction sweep. The audit's findings drive the apply tasks. Everything lands on `cleanup/engine-phase3` and FF-merges to `master`.

**Tech Stack:** AS Macro Assembler (68000 + Z80), the `./build.sh` Wine pipeline, the Workflow tool for the audit, Exodus MCP (`oracle`) for render verification, Python build tools.

**Spec:** `docs/superpowers/specs/2026-06-23-engine-phase3-cleanup-design.md`

---

## Pre-flight context (read once before Task 1)

- **Branch:** all work happens on `cleanup/engine-phase3` (already created; the spec is committed there). FF-merge to `master` in the final task.
- **Build command (the only valid one for verification):** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe`. A plain `./build.sh` excludes sound and proves nothing about the full ROM. Exit 0 = pass. Lint warnings are **non-blocking**; the baseline is **184 warnings / 347 suggestions** — these counts must **not increase** (they may legitimately *drop* as dead code/comments are removed).
- **Baseline is green:** the pre-Phase-3 build exits 0 and produces `s4.bin` (~406 KB). Capture this as the regression oracle in Task 0.
- **Daemon caution:** `tools/ojz_strip_gen.py` is watched by an auto-commit daemon that commits edits to the *current* branch as the user ~60s after a change. The user authorized editing it on this branch while present. **Never `--amend`** on this branch.
- **Do NOT touch** the user's unrelated uncommitted work: `data/sprites/`, `tools/forest_bg_gen.py`, `data/editor_bg_override.json`, `data/editor/ojz/...`, `docs/research/reference_captures/br_mt_from_start.vgm`, `docs/research/s3k_art_style_demo.html`. When committing, `git add` exact paths only — never `git add -A`/`-u`.
- **Ground-truth facts established during planning (use these when rewriting docs):**
  - FG level art ships as a **globally-deduped, spatially-ordered, paged act pool** (`order_pool_spatially` + `split_pool_into_pages` in `tools/tile_dedupe.py`), loaded **once at init** by `Level_LoadArt` (`engine/level/load_art.asm`) and **fully resident** for the act. **There is no graph-coloring, no DSATUR, no per-section art swap, no `LoadSectionTiles`.**
  - Act pool pages are **ZX0**-wrapped (`act_pool_page*.zx0`); `Art_Decompress` dispatches version 1=S4LZ, version 2=ZX0.
  - The decompress staging buffer is **`Art_Staging_Buffer` = `ART_STAGING_BUFFER_SIZE` = 8192 bytes** (one 256-tile page), an init-only alias over tile-cache RAM — *not* a `~$1000` per-section buffer.

## File-structure map (what gets created or modified)

**Created:**
- `docs/research/2026-06-23-phase3-audit-findings.md` — the audit's structured output (dead-code list, comment-edit list, doc-contradiction list, ambiguous list). The input artifact for Tasks 4–6.

**Modified (deterministic, content known):**
- `test/ojz_scroll_test.asm` — remove the `SOUND_LOADTEST` scaffold (Task 1).
- `constants.asm` — `BG_TILE_CAPACITY` 512→448 + comment cleanup (Task 2).
- `tools/ojz_strip_gen.py` — `BG_TILE_CAPACITY_PY` 512→448 (Task 2; daemon-watched).
- `docs/ENGINE_ARCHITECTURE.md` — §2.5 art-loading flow, §2.7 cascade, §8.5 profiler note, graph-coloring/ZX0 de-staling (Task 6) + audit-confirmed fixes.
- `CLAUDE.md` (aeon) — pipeline description graph-color→paged-pool (Task 7; user-confirm).
- `docs/DEFERRED_WORK.md` — retire `BG_TILE_CAPACITY` deferral; mark Phase 3 done (Task 8).

**Deleted:**
- `docs/research/2026-06-22-HANDOFF-tile-budget.md`, `docs/research/2026-06-22-multipass-tile-streaming-scope.md` (Task 8).

**Modified (audit-driven, content produced by Task 3):**
- Various `engine/**/*.asm`, `test/*.asm`, `tools/*`, `ram.asm`, `structs.asm` — dead-code removals (Task 4) and comment edits (Task 5).

---

## Task 0: Capture the regression baseline

**Files:** none modified.

- [ ] **Step 1: Confirm branch and clean index of our scope**

Run: `git branch --show-current` → expect `cleanup/engine-phase3`.
Run: `git status --porcelain | grep -vE 'data/sprites|forest_bg_gen|editor_bg_override|data/editor/ojz|reference_captures|s3k_art_style_demo'` → expect no lines referencing files this plan will commit (only the user's untracked work should remain).

- [ ] **Step 2: Build the baseline ROM and record counts**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe 2>&1 | tail -20`
Expected: `Build complete: s4.bin` and the s4lint summary line. Record the warning/suggestion counts (baseline: 184 warnings / 347 suggestions) and the ROM byte size. These are the "must-not-regress" anchors for Task 9.

- [ ] **Step 3: Snapshot the baseline binary for later comparison**

Run: `cp s4.bin /tmp/s4_baseline_phase3.bin && ls -l /tmp/s4_baseline_phase3.bin`
Expected: a copy exists. (Used in Task 9 to reason about which bytes changed.)

- [ ] **Step 4: No commit** — this task only establishes anchors.

---

## Task 1: Remove the `SOUND_LOADTEST` debug scaffold

**Files:**
- Modify: `test/ojz_scroll_test.asm:155-162`

- [ ] **Step 1: Delete the scaffold block**

Remove exactly this block (the forced-scroll VGM/streaming stress test) from `GameState_OJZScroll_Update`:

```asm
    ifdef SOUND_LOADTEST
        ; DEBUG: force continuous rightward scroll to exercise the streaming-DMA
        ; load (Tile_Cache_Fill / Section_UpdateColumns) for sound-rate VGM
        ; measurement. +6px/frame in the x_pos integer (high) word.
        move.l  (Player_1+SST_x_pos).w, d0
        addi.l  #$00060000, d0
        move.l  d0, (Player_1+SST_x_pos).w
    endif

```

The surrounding code is unchanged: `jsr RunObjects` (line 153) is now directly followed by the `; -- camera follows Player_1 ...` comment and `jsr Camera_Update`.

- [ ] **Step 2: Build to verify green (the block was conditionally compiled out anyway, so the ROM is unchanged)**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe 2>&1 | tail -4`
Expected: `Build complete: s4.bin`, exit 0. Warning/suggestion counts must not increase.

- [ ] **Step 3: Confirm no other `SOUND_LOADTEST` references remain**

Run: `grep -rn 'SOUND_LOADTEST' . --include='*.asm' --include='*.sh' --include='*.md'`
Expected: zero hits in code/build (doc/spec/plan mentions are fine to leave; they are history, not live references).

- [ ] **Step 4: Commit**

```bash
git add test/ojz_scroll_test.asm
git commit -m "cleanup(phase3): remove SOUND_LOADTEST forced-scroll measurement scaffold

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Reconcile `BG_TILE_CAPACITY` 512 → 448

The shared BG tile region runs $8000..$B7FF (the SAT now sits at $B800), so usable capacity is **448** tiles, not 512. The engine doesn't read the constant; only the build tools gate on it. `tools/inject_editor_bg.py` already uses 448 — this task aligns `constants.asm` and `tools/ojz_strip_gen.py`.

**Files:**
- Modify: `constants.asm:60-77`
- Modify: `tools/ojz_strip_gen.py:248` (daemon-watched)

- [ ] **Step 1: Update the capacity constant and its comment in `constants.asm`**

Replace the existing rationale comment (lines 60-68) and the constant+stale-note (lines 71-77). Old constant line:

```asm
BG_TILE_CAPACITY        = 512           ; STALE pre-SAT nominal ($8000..$BFFF = 16 KB).
                                        ; The SAT now sits at $B800, so usable BG is only
                                        ; $8000..$B7FF = 448 tiles. Engine code doesn't read
                                        ; this; only build tools gate on it (ojz_strip_gen.py
                                        ; mirrors 512 — daemon-watched; inject_editor_bg.py
                                        ; already uses 448). Reconcile to 448 + add a BG_Init
                                        ; capacity guard — tracked in DEFERRED_WORK.
```

New (present-tense, describe-as-design — no "STALE/reconcile" narration):

```asm
BG_TILE_CAPACITY        = 448           ; Usable shared-BG tiles: $8000..$B7FF (the SAT
                                        ; sits at $B800). Build tools gate on this; engine
                                        ; code doesn't read it. Mirrored by ojz_strip_gen.py
                                        ; and inject_editor_bg.py.
```

Also update the rationale comment above `BG_TILE_BASE_VRAM` (lines 60-68): change "512 slots (16 KB)" framing to describe the 448-tile region ($8000..$B7FF, below the SAT at $B800). Keep the T1/T2/T3 union rationale; just correct the number and the region end.

- [ ] **Step 2: Update the mirror in `tools/ojz_strip_gen.py:248`**

```python
BG_TILE_CAPACITY_PY  = 448    # mirrors constants.asm BG_TILE_CAPACITY (usable $8000..$B7FF, SAT at $B800)
```

- [ ] **Step 3: Confirm `inject_editor_bg.py` is already 448 (no change expected)**

Run: `grep -n 'BG_TILE_CAPACITY' tools/inject_editor_bg.py`
Expected: `BG_TILE_CAPACITY = 448`.

- [ ] **Step 4: Full build — exercises the tightened gate against current OJZ data**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe 2>&1 | tail -6`
Expected: `Build complete: s4.bin`, exit 0. (OJZ BG usage is well under 448 — T1 uses ~218; the gate only tightens, so it can only *catch* a real overflow, never falsely fire here.) If the `ojz_strip_gen.py` BG-capacity assert fires, STOP — that means current data exceeds 448 and is a real finding to surface to the user.

- [ ] **Step 5: Commit**

```bash
git add constants.asm tools/ojz_strip_gen.py
git commit -m "cleanup(phase3): reconcile BG_TILE_CAPACITY 512->448 (SAT at \$B800)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

> Note: the daemon may also auto-commit `ojz_strip_gen.py` ~60s later if it fires first; that is acceptable on this branch. If it does, this step's commit will simply include only `constants.asm`. Do not `--amend` either way.

---

## Task 3: Verified-clean audit (Workflow) — dead code, orphans, comments, doc contradictions

Produces the findings artifact that drives Tasks 4–6. No source edits in this task.

**Files:**
- Create: `docs/research/2026-06-23-phase3-audit-findings.md`

- [ ] **Step 1: Build the mechanical symbol cross-reference (candidate orphans)**

Run this to list defined symbols with zero references outside their definition line (high-recall candidate list — the audit verifies each):

```bash
cd /home/volence/sonic_hacks/aeon
# Collect defined symbols: "Label:" and "NAME = ..." / "NAME equ ..." across engine asm.
grep -rhoE '^[A-Za-z_][A-Za-z0-9_]*(:| +=| +equ )' engine test ram.asm constants.asm structs.asm --include='*.asm' \
  | sed -E 's/[: ].*$//' | sort -u > /tmp/p3_syms.txt
wc -l /tmp/p3_syms.txt
: > /tmp/p3_orphans.txt
while read -r sym; do
  # count total references; a symbol with exactly 1 occurrence is defined-but-unreferenced
  n=$(grep -rcwF "$sym" engine test ram.asm constants.asm structs.asm --include='*.asm' | awk -F: '{s+=$2} END{print s+0}')
  if [ "$n" -le 1 ]; then echo "$sym" >> /tmp/p3_orphans.txt; fi
done < /tmp/p3_syms.txt
echo "candidate orphans:"; wc -l /tmp/p3_orphans.txt; cat /tmp/p3_orphans.txt
```

Expected: a (possibly empty) list of candidate orphaned symbols. Save the output — it is `candidateOrphans` for the workflow. (False positives are expected: macros, exported labels referenced from `.sh`/symbol files, struct fields used via offset macros. The audit's verify stage filters them.)

- [ ] **Step 2: Run the audit Workflow**

Invoke the Workflow tool with this script (pass `args` = `{ candidateOrphans: <the list from Step 1>, subsystems: <the list below>, archSections: <the list below> }`):

```javascript
export const meta = {
  name: 'phase3-verified-clean-audit',
  description: 'Audit aeon for dead code, orphaned symbols, stale/lying comments, and ENGINE_ARCHITECTURE.md-vs-code contradictions',
  phases: [{ title: 'Code+comment audit' }, { title: 'Verify finding' }, { title: 'Doc-vs-code' }],
}

const FINDINGS = {
  type: 'object', additionalProperties: false,
  properties: {
    items: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: {
          kind: { type: 'string', enum: ['dead_code', 'orphan_symbol', 'comment_noise', 'comment_lying', 'doc_contradiction'] },
          path: { type: 'string' }, line: { type: 'integer' },
          current: { type: 'string', description: 'the current code/comment/claim verbatim (short)' },
          proposed: { type: 'string', description: 'delete | rewrite-to: <text> | (for doc) corrected claim' },
          why: { type: 'string' },
          loadBearingRisk: { type: 'string', enum: ['none', 'low', 'ambiguous'] },
        },
        required: ['kind', 'path', 'current', 'proposed', 'why', 'loadBearingRisk'],
      },
    },
  },
  required: ['items'],
}
const VERDICT = {
  type: 'object', additionalProperties: false,
  properties: { safe: { type: 'boolean' }, reason: { type: 'string' } },
  required: ['safe', 'reason'],
}

const KEEP_RULE = `KEEP rule: load-bearing rationale — comments documenting a non-obvious constraint, hardware quirk, or "do not revert" warning — are KEPT (rephrase to present tense if they narrate history, but never drop the constraint). When unsure a comment is load-bearing, set loadBearingRisk:"ambiguous" and do NOT propose deletion. STRIP only: historical-diff narration ("changed X to Y to fix Z", "used to be...", references to deleted systems), stale temporaries ("for now"/"TODO after X" where X shipped), and LYING comments that describe behavior the code no longer has.`

// Phase 1+2: per-subsystem code+comment audit, each finding adversarially verified
const code = await pipeline(
  args.subsystems,
  s => agent(
    `Read-only audit of subsystem "${s.name}" (files: ${s.globs}) in /home/volence/sonic_hacks/aeon. Find: (a) dead_code (routines/data assembled but unreachable, incl. reachable only from other dead code), (b) orphan_symbol from this candidate list (verify each is truly unreferenced — exclude macros, struct-offset fields, labels referenced from build scripts/symbol files): ${JSON.stringify(args.candidateOrphans)}, (c) comment_noise / comment_lying per this rule. ${KEEP_RULE} Cite exact path:line and the verbatim current text. Do not edit anything.`,
    { phase: 'Code+comment audit', label: `audit:${s.name}`, schema: FINDINGS }),
  found => parallel(((found && found.items) || []).map(f => () =>
    agent(
      `Skeptically verify this proposed cleanup is SAFE to apply. Re-read the cited code in context. Default to safe:false if there is ANY chance the code is reachable or the comment encodes a real constraint. Finding: ${JSON.stringify(f)}`,
      { phase: 'Verify finding', label: `verify:${f.path}:${f.line || 0}`, schema: VERDICT })
      .then(v => ({ ...f, verified: v }))))
)

// Phase 3: ENGINE_ARCHITECTURE.md section-by-section vs shipped code (recon's sampling missed graph-coloring + ZX0 — verify EVERY section)
const KNOWN = `Known-stale to confirm and report: FG level art is globally-deduped + spatially-ordered + PAGED + fully resident, loaded once by Level_LoadArt — NOT graph-colored (DSATUR deleted from tile_dedupe.py), NO per-section art swap, NO LoadSectionTiles. Act pool pages are ZX0. Staging buffer is Art_Staging_Buffer=8192B, not a ~$1000 per-section buffer.`
const doc = await parallel(args.archSections.map(sec => () =>
  agent(
    `Read-only: verify ENGINE_ARCHITECTURE.md section "${sec}" against the SHIPPED code in /home/volence/sonic_hacks/aeon. Report every claim that contradicts reality as kind:"doc_contradiction" with path:"docs/ENGINE_ARCHITECTURE.md", the doc line, the current claim, and the corrected claim. ${KNOWN} Do not edit.`,
    { phase: 'Doc-vs-code', label: `doc:${sec}`, schema: FINDINGS })))

const codeItems = code.flat().filter(Boolean)
const docItems = doc.filter(Boolean).flatMap(d => (d && d.items) || [])
return {
  confirmedCode: codeItems.filter(f => f.verified && f.verified.safe && f.loadBearingRisk !== 'ambiguous'),
  ambiguous: codeItems.filter(f => !(f.verified && f.verified.safe) || f.loadBearingRisk === 'ambiguous'),
  docContradictions: docItems,
}
```

**`subsystems` value:**
```json
[
  {"name":"level-streaming","globs":"engine/level/*.asm"},
  {"name":"player","globs":"engine/player/*.asm"},
  {"name":"objects","globs":"engine/objects/**/*.asm"},
  {"name":"parallax-camera","globs":"engine/parallax.asm engine/*camera* engine/level/bg.asm"},
  {"name":"sound","globs":"engine/sound*.asm engine/**/*sound*"},
  {"name":"boot-vdp-dma","globs":"engine/boot.asm engine/vdp_init.asm engine/*dma* engine/*vint*"},
  {"name":"render-sprite","globs":"engine/*sprite* engine/*render*"},
  {"name":"test-harness","globs":"test/*.asm"},
  {"name":"top-level-asm","globs":"ram.asm constants.asm structs.asm main.asm"},
  {"name":"build-tools","globs":"tools/*.py build.sh"}
]
```
(Adjust globs to the real tree if a path differs — run `ls engine` first to confirm subdirectory names.)

**`archSections` value:** `["§0 Hardware Init","§1 Core VDP Pipeline","§2.1 Compression","§2.2 Dynamic VRAM Allocator","§2.3 VRAM Layout","§2.4 Per-Section BG","§2.5 Art Loading Flow","§2.6 Data Format Summary","§2.7 Cascade Effects","§3 Object System","§4 Section System","§5 Player System","§6 Audio","§7 Visual Effects","§8 Tooling & Build","§9 Cross-Cutting"]`

- [ ] **Step 3: Write the findings artifact**

Write the workflow's returned `confirmedCode`, `ambiguous`, and `docContradictions` into `docs/research/2026-06-23-phase3-audit-findings.md` as three markdown tables (kind · path:line · current · proposed · why · verdict). This file is the input for Tasks 4–6.

- [ ] **Step 4: Commit the findings artifact**

```bash
git add docs/research/2026-06-23-phase3-audit-findings.md
git commit -m "docs(phase3): verified-clean audit findings (dead code, comments, doc contradictions)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 5: Checkpoint — surface the `ambiguous` list to the user**

Present the `ambiguous` findings (load-bearing-risk or unverified). Get an explicit keep/cut decision for each before Tasks 4–5 touch them. Nothing ambiguous is changed without sign-off.

---

## Task 4: Apply confirmed dead-code / orphan removals

**Files:** as listed in `confirmedCode` (kind `dead_code` / `orphan_symbol`) from Task 3.

- [ ] **Step 1: If `confirmedCode` has zero dead-code/orphan items, record "engine verified clean — no dead code" and skip to Task 5.** (This is the expected outcome — recon found the leapfrog teardown already removed everything. The audit's job was to *prove* it.)

- [ ] **Step 2: For each confirmed dead-code/orphan finding, delete it**

Apply the `proposed: delete` exactly at `path:line`. Group related deletions (e.g. a routine + its now-unreferenced label) into one edit. Do NOT delete anything on the `ambiguous` list or anything the user vetoed in Task 3 Step 5.

- [ ] **Step 3: Build green after each grouped deletion**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe 2>&1 | tail -4`
Expected: `Build complete: s4.bin`, exit 0. A failed build means the symbol was *not* dead — revert that deletion and move it to the ambiguous list for the user.

- [ ] **Step 4: Commit (one commit per coherent group)**

```bash
git add <exact files>
git commit -m "cleanup(phase3): remove verified-dead <description>

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Whole-engine comment cleanup (per-subsystem, with user diff review)

**Files:** as listed in `confirmedCode` (kind `comment_noise` / `comment_lying`) from Task 3, grouped by subsystem.

- [ ] **Step 1: Apply confirmed comment edits for ONE subsystem**

For each `comment_noise`/`comment_lying` finding in the subsystem: apply its `proposed` (delete the narration, or rewrite to the present-tense text). Keep load-bearing rationale (rephrased present-tense). Example seed findings already known in `test/ojz_scroll_test.asm`: the "deleted in the leapfrog teardown" tail (lines 107-111 — keep the "no self-check because collision is editor-authored" rationale, drop the teardown history) and "(Section_Check + teleport machinery removed in a later task.)" (lines 170-173 — drop; the removal already happened).

- [ ] **Step 2: Build green (comment edits are build-neutral; this is a sanity check)**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe 2>&1 | tail -4`
Expected: `Build complete: s4.bin`, exit 0; warning/suggestion counts must not increase.

- [ ] **Step 3: Present the subsystem diff to the user for sign-off**

Run: `git diff --stat && git diff <subsystem files>`
Present it. For the FIRST subsystem, this doubles as the representative sample that validates the STRIP-vs-KEEP classification. If the user wants the rule tuned, adjust and re-apply before continuing to other subsystems.

- [ ] **Step 4: Commit the subsystem's comment cleanup**

```bash
git add <subsystem files>
git commit -m "cleanup(phase3): comment hygiene — <subsystem> (describe-as-design)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 5: Repeat Steps 1–4 for each remaining subsystem** until all `comment_noise`/`comment_lying` findings are applied.

---

## Task 6: ENGINE_ARCHITECTURE.md reconciliation

Apply the known rewrites (below) **and** every `docContradictions` finding from Task 3. No build needed (doc only); verify no broken internal section references.

**Files:**
- Modify: `docs/ENGINE_ARCHITECTURE.md`

- [ ] **Step 1: Rewrite §2.5 "Level load (blocking)" (current lines ~1330-1341)**

Replace the `LoadSectionTiles`/old-`LoadArt` pseudocode with the shipped paged-pool flow:

````markdown
**Level load (blocking, display OFF):**
```
Level_LoadArt(act descriptor)              ; engine/level/load_art.asm
  → For each page of the act's paged art pool (one page = ART_POOL_PAGE_TILES = 256 tiles):
      → Art_Decompress the wrapped ZX0/S4LZ page → Art_Staging_Buffer (8 KB, init-only)
      → QueueDMA_Critical: staging buffer → fixed VRAM slot (page_index << 13)
      → VSync_Wait so the Critical DMA drains during the blanked VBlank
  → BG_Init: blit the zone-wide BG to Plane B (T1; §2.4)
The whole act art pool is resident in VRAM for the life of the act. Section
streaming and teleport never reload tile art — there is no per-section art swap.
```
````

- [ ] **Step 2: Rewrite §2.5 "Per-section tile art — RAM footprint" (current lines ~1391-1398)**

````markdown
**Tile-art RAM footprint:**
```
Art_Staging_Buffer: 8,192 bytes (ART_STAGING_BUFFER_SIZE, one 256-tile page),
  an init-only alias over the tile-cache RAM — reused, not separately reserved.
No chunk tables, block tables, level layout arrays, or UFTC tile buffers in RAM.
FG tile art is decompressed once at init; sprite art DMAs directly from ROM.
```
````

- [ ] **Step 3: Rewrite the §2.7 "Per-Section Tile Art (2.5)" cascade (current lines ~1442-1451)**

````markdown
Paged Act Art Pool (2.5)
  → The whole act ships one globally-deduped, spatially-ordered, paged tile pool
    → ZX0/S4LZ pages (256 tiles each) decompressed once at init via
      Art_Staging_Buffer → Critical DMA to fixed VRAM slots
    → Resident for the life of the act — no per-section art swap, no preload
  → No chunk/block tables in RAM
    → Pre-computed block data from build tool, zero runtime conversion
      → Zero per-frame cost for level rendering (tile cache → plane buffer → VDP)
  → Tile overflow caught at build time
    → Pool deduped across the whole act; build asserts pool ≤ FG VRAM capacity
```
````

Also fix the §2.7 "Edge-Driven Allocation" line that says "graph-colored pool" (current ~line 1461) → "resident act art pool".

- [ ] **Step 4: De-stale graph-coloring everywhere the doc claims FG section art is graph-colored**

For every `docContradictions` finding about graph-coloring (expected in §2.3, §2.5, §2.7, §8/§8.1), replace "build-time graph coloring / DSATUR / graph-colored VRAM" with the shipped reality: "globally-deduped, spatially-ordered, paged act art pool, fully resident." Likewise correct any "Level art = S4LZ" claim that should read "ZX0 (act pool pages); S4LZ for <whatever the audit confirms still uses it>." Apply exactly what each verified `docContradictions` finding specifies.

- [ ] **Step 5: Add the §8.5 profiler deferred note (current heading ~line 3147)**

Directly under `### 8.5 Frame Profiler (...)`, add:

```markdown
> **Status (2026-06): deferred — not built.** The `Prof_*` RAM block exists but is
> never written; frame budget is measured today via `Lag_Frame_Count` (incremented
> in `VInt_Lag`). See DEFERRED_WORK.md §5.
```

- [ ] **Step 6: Strip residual leapfrog migration-narration**

For leapfrog-narration lines the audit flags (e.g. "the 2-slot leapfrog has been deleted", "replaces the deleted leapfrog"), rewrite to describe the current design in present tense without the "we deleted X" framing. Keep genuinely useful "why not the obvious alternative" rationale; drop pure migration history (it lives in git + the spec/plan docs).

- [ ] **Step 7: Verify no broken section cross-references**

Run: `grep -nE '§2\.5|§2\.7|§8\.5|graph.?col|LoadSectionTiles|DSATUR' docs/ENGINE_ARCHITECTURE.md`
Expected: no remaining `LoadSectionTiles`/`DSATUR`; any surviving "graph col" hit is only in a clearly-historical or object-allocator context the audit explicitly confirmed as still accurate.

- [ ] **Step 8: Commit**

```bash
git add docs/ENGINE_ARCHITECTURE.md
git commit -m "docs(phase3): reconcile ENGINE_ARCHITECTURE to shipped paged-pool reality

§2.5/§2.7 art-loading flow, graph-coloring→paged-pool de-staling, §8.5 profiler
deferred note, leapfrog narration stripped to describe-as-design.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Correct the stale pipeline description in `CLAUDE.md` (user-confirm)

The aeon `CLAUDE.md` describes the build as "deduplicate → graph-color → generate" and "Unified VRAM art pool with build-time graph coloring." That graph-coloring is gone. Because `CLAUDE.md` is project law, **confirm with the user before editing.**

**Files:**
- Modify: `CLAUDE.md` (the aeon one at `/home/volence/sonic_hacks/aeon/CLAUDE.md`)

- [ ] **Step 1: Locate the stale lines**

Run: `grep -nE 'graph.?col|graph coloring' CLAUDE.md`
Expected: the "What This Engine Is" bullet ("Unified VRAM art pool ($000-$5FF) with build-time graph coloring") and the "Build tool pipeline" bullet ("editor stamps → flatten → deduplicate → graph-color → generate").

- [ ] **Step 2: Confirm with the user, then rewrite**

Propose: "Unified VRAM art pool ($000-$5FF) — globally-deduped, spatially-ordered, paged act tileset (fully resident)" and "Build tool pipeline: editor stamps → flatten → deduplicate → spatial-order → page → generate." Apply on confirmation.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(phase3): CLAUDE.md — pipeline is paged dedup pool, not graph-coloring

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Delete stale scratch docs + update DEFERRED_WORK.md

**Files:**
- Delete: `docs/research/2026-06-22-HANDOFF-tile-budget.md`, `docs/research/2026-06-22-multipass-tile-streaming-scope.md`
- Modify: `docs/DEFERRED_WORK.md`

- [ ] **Step 1: Delete the two road-not-taken scratch docs**

```bash
git rm docs/research/2026-06-22-HANDOFF-tile-budget.md docs/research/2026-06-22-multipass-tile-streaming-scope.md
```
(These describe the multi-pass approach that the paged pool superseded; the resolved story lives in `DEFERRED_WORK.md` + git.)

- [ ] **Step 2: Update `DEFERRED_WORK.md`**

Find the `BG_TILE_CAPACITY` deferral entry (the "Reconcile to 448 + add a BG_Init capacity guard" note) and mark it RESOLVED (the guard shipped in commit 0aab611; the 448 reconciliation shipped in Task 2 of this plan). Add a short "Engine Phase 3 cleanup — RESOLVED 2026-06-23" entry summarizing the audit-verified-clean result + doc reconciliation.

Run: `grep -nE 'BG_TILE_CAPACITY|BG_Init capacity|448' docs/DEFERRED_WORK.md` to locate the entry.

- [ ] **Step 3: Commit**

```bash
git add docs/DEFERRED_WORK.md
git commit -m "docs(phase3): delete superseded tile-budget scratch docs; mark Phase 3 done

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: Final verification + FF-merge to master

**Files:** none modified.

- [ ] **Step 1: Clean full build**

Run: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe 2>&1 | tail -8`
Expected: `Build complete: s4.bin`, exit 0. Warning count ≤ 184, suggestion count ≤ 347 (must not increase vs baseline; a drop is good).

- [ ] **Step 2: Re-run the audit (Task 3 workflow) and confirm it comes back clean**

Re-invoke the Task 3 workflow. Expected: `confirmedCode` is empty (all dead code/noise comments already removed) and `docContradictions` is empty (doc reconciled). Any new finding → loop back to the relevant apply task.

- [ ] **Step 3: Boot in Exodus and confirm the OJZ scroll test renders identically**

With the user's `oracle` emulator: `emulator_reload_rom` (or have the user load `s4.bin`), `emulator_resume`, then `emulator_screenshot`. Confirm the OJZ scroll test renders as before. Since the only ROM-affecting change is verified-dead-code removal (behavior-unreachable) — and the `SOUND_LOADTEST` block was conditionally compiled out of this build anyway — the render must match the Task 0 baseline. Spot-check VRAM via `emulator_read_vram` at the FG pool base if any doubt.

- [ ] **Step 4: Confirm the working tree is clean of our scope**

Run: `git status --porcelain | grep -vE 'data/sprites|forest_bg_gen|editor_bg_override|data/editor/ojz|reference_captures|s3k_art_style_demo'`
Expected: empty (only the user's untracked work remains).

- [ ] **Step 5: FF-merge to master**

```bash
git checkout master
git merge --ff-only cleanup/engine-phase3
git log --oneline -8 | cat
```
Expected: fast-forward succeeds. If master advanced (e.g. a daemon commit) and FF is refused, STOP and surface to the user rather than forcing a merge commit.

- [ ] **Step 6: Report** the final state: build green, audit clean, render identical, branches merged, and the summary of what changed (dead code removed or "verified none", comment subsystems cleaned, doc sections reconciled).

---

## Self-review notes (planner)

- **Spec coverage:** WS1 audit → Task 3; WS2 code cleanup → Tasks 1, 4; WS3 comment cleanup → Task 5; WS4 constant → Task 2; WS5 doc reconciliation → Tasks 6, 8 (+ Task 7 CLAUDE.md, an expansion the planning ground-truth surfaced); WS6 verify+merge → Tasks 0, 9. All spec workstreams covered.
- **Expansion beyond spec:** Task 7 (CLAUDE.md) and the graph-coloring/ZX0 de-staling (Task 6 Steps 4) were discovered during planning (recon's sampling missed them). They are within the approved "make docs match shipped reality" goal; Task 7 is gated on user confirmation because CLAUDE.md is project law.
- **No invented content:** audit-derived deletions/comment-edits (Tasks 4–5) and extra doc fixes (Task 6 Step 4) are intentionally procedure-specified, not pre-enumerated — their exact content is produced by the Task 3 audit, which is itself fully specified (script + inputs + output format). All deterministic edits (Tasks 1, 2, 6 Steps 1–3/5, 7, 8) contain exact before/after text.
- **Consistency:** the build command, baseline counts (184/347), branch name, and "describe-as-design" rule are used identically across tasks.
