# Engine Phase 3 — Cleanup, Comment Hygiene & Doc Reconciliation

**Date:** 2026-06-23
**Status:** Design approved; implementation plan pending
**Branch:** `cleanup/engine-phase3` (FF-merge to `master` when verified)

---

## 1. Background

Continuous-scroll traversal shipped in two merged phases — Phase 1 (horizontal,
2026-06-22) and Phase 2 (vertical, 2026-06-23) — replacing the old "leapfrog"
2-slot VRAM/section-streaming system. The tile-budget blocker was resolved the
same week by a globally-deduped **paged act art pool** (`Level_LoadArt` + a page
loader), *not* by the alternative multi-pass-per-section approach that earlier
scratch docs explored.

"Phase 3" was tracked as "inline-delete pass-throughs + ARCH rewrite." A recon
pass (two read-only Explore agents over the code and `ENGINE_ARCHITECTURE.md`)
**reframed the work**:

- **The code-deletion is already done.** The continuous-scroll merge already
  removed the leapfrog infrastructure: no trampoline/pass-through wrappers, no
  orphaned slot-map/rebase constants, no `LoadSectionTiles`/per-section art path.
  Confirmed-gone: `sec_tile_blobs.asm` / `sec_vram_bases.asm`, the `Sec_tile_art`
  / `Sec_tile_art_vram` struct fields, the DSATUR color-graph Python functions,
  the `Decomp_Buffer` alias. The ~73 remaining "leapfrog" hits are all historical
  comments/docs.
- **The real remaining work is small, concentrated, and mostly about making the
  *description* of the engine match the *shipped* engine** — in both the
  architecture doc and the code comments.

This spec covers a **behavior-preserving cleanup**: the ROM must build green and
boot/render identically. Only dead code (if any survives an exhaustive audit),
one debug scaffold, one stale constant, stale scratch docs, and
historical-narration comments change.

## 2. Goal & Non-Goals

### Goal
When done, the engine is **verified clean** and both `ENGINE_ARCHITECTURE.md`
*and* the code comments describe the shipped engine **as the design** — present
tense, no "old-thing-plus-patches" narration, no descriptions of behavior the
engine no longer has.

### Non-Goals (explicitly out of scope)
- Any functional or performance change: Task 7 diagonal-scroll lag tuning,
  Phase 4 floating-origin rebase, multi-pass per-section streaming.
- The user's unrelated uncommitted work: `data/sprites/`, `tools/forest_bg_gen.py`,
  `data/editor_bg_override.json`, editor `data/editor/ojz/...` changes,
  `docs/research/reference_captures/br_mt_from_start.vgm`,
  `docs/research/s3k_art_style_demo.html`. These are left untouched.

## 3. Recon Findings (ground truth for the plan)

| Item | Location | Disposition |
|---|---|---|
| `SOUND_LOADTEST` debug scaffold (forces +6px/frame scroll for VGM/streaming stress) | `test/ojz_scroll_test.asm` (~155–162) | **DELETE** — confirmed temporary, marked for removal in the Phase 1 plan |
| Suspected `build.sh` measurement guard | `build.sh` (~86–97) | **VERIFY then DELETE only if confirmed dead** — current size-guards there look live |
| `BG_TILE_CAPACITY = 512` (stale; real usable post-SAT-relocation = 448) | `constants.asm` (~71) **and** `tools/ojz_strip_gen.py` (~248) | **RECONCILE 512→448** in both; `tools/inject_editor_bg.py` already uses 448 |
| `ENGINE_ARCHITECTURE.md` §2.5 "Art Loading Flow" | describes deleted per-section `LoadSectionTiles` | **REWRITE** to the paged-pool `Level_LoadArt` reality |
| `ENGINE_ARCHITECTURE.md` §2.7 "Per-Section Tile Art" cascade paragraph | contradicts the (correct) "no per-section art swap" text in the same section | **REWRITE/REMOVE** |
| `ENGINE_ARCHITECTURE.md` §8 profiler | §8.5 cycle profiler is not built (lag measured via `Lag_Frame_Count`) | **ADD deferred note** |
| Leftover leapfrog migration-narration | scattered in `ENGINE_ARCHITECTURE.md` (e.g. "the leapfrog has been deleted", "replaces the deleted leapfrog") | **STRIP to describe-as-design** (history lives in git + spec/plan docs) |
| Stale untracked scratch docs | `docs/research/2026-06-22-HANDOFF-tile-budget.md`, `docs/research/2026-06-22-multipass-tile-streaming-scope.md` | **DELETE** — describe the road not taken (multi-pass), superseded by the paged pool |

> The recon's "the engine code is otherwise clean" is a **negative claim from a
> sampling search** — it cannot prove absence. Workstream 1 exists to *verify* it.

## 4. Approach — Verified-Clean Audit (Approach C: Hybrid)

Three options were considered: (A) adversarial agent sweep only, (B) mechanical
symbol cross-reference only, (C) hybrid. **C is chosen.**

- **Mechanical pass** (deterministic, high recall on *unreferenced* symbols):
  cross-reference every defined label / `equ` / constant / struct field across all
  `*.asm` against its references → candidate orphan list.
- **Adversarial pass** (judgment, catches *semantic* dead code the mechanical pass
  can't — code reachable only from other dead code, stale scaffolds, contradictions):
  agents read each file **once** and classify, in the same pass, both dead code
  *and* comments (see §5). An independent skeptic verifies every proposed removal.
  **Bias toward KEEP** on anything possibly load-bearing.

The mechanical symbol data keeps the agents honest with ground truth; the agents
catch what pure symbol-counting misses.

**Output:** (1) confirmed-dead-code list, (2) confirmed comment edits, (3) an
**"ambiguous → ask the user"** list. Nothing on the ambiguous list is touched
without explicit sign-off.

## 5. Comment Cleanup Principle (whole engine)

A comment should describe the code **as it exists now**: present-tense behavior
plus any non-obvious rationale that protects it. Scope: all of `engine/`, `test/`,
`tools/`, `ram.asm`, `constants.asm`, `structs.asm`.

Classification used by the audit:

- **STRIP / REWRITE (noise):** historical-diff narration ("changed X to Y to fix
  bug Z", "used to be leapfrog", references to deleted systems), stale temporaries
  ("for now" / "TODO after X" where X already shipped), and **lying comments** that
  describe behavior the code no longer has (the most harmful — actively misleading).
- **KEEP (rephrase to present tense if needed):** **load-bearing rationale** — a
  comment documenting a non-obvious constraint, hardware quirk, or "do not revert"
  warning. These often *look* like "we did this to fix X" but protect against a real
  regression (e.g. the "per-line HScroll is load-bearing — per-cell tears the FG
  during scroll" comments). **When uncertain whether a comment is load-bearing, the
  verifier defaults to KEEP** and routes it to the ambiguous list.

**Verification:** comment edits don't change the binary, so the check is a
**reviewable diff, chunked by subsystem**. The user approves the classification on
a representative sample first, then reviews the full diff before it is committed.

## 6. Workstreams

1. **Verified-clean audit (Approach C).** Mechanical symbol xref → candidates;
   adversarial single-read-per-file classification of dead code + comments;
   skeptic verification; produce the three output lists.
2. **Code cleanup.** Delete the `SOUND_LOADTEST` scaffold + audit-confirmed dead
   code/orphans. Verify the `build.sh` guard; remove only if confirmed dead.
   **Build green after each change.**
3. **Comment cleanup (whole engine).** Apply confirmed comment edits per §5.
   Build-neutral; delivered as a subsystem-chunked diff for user sign-off
   (sample first, then full).
4. **Constant reconciliation.** `BG_TILE_CAPACITY` `512→448` in `constants.asm`
   *and* `tools/ojz_strip_gen.py`; confirm `inject_editor_bg.py` is already 448;
   re-check the build-tool gate is correct at 448.
   - *Note:* `tools/ojz_strip_gen.py` is watched by the auto-commit daemon, which
     commits edits to the current branch as the user ~60s later. The user has
     authorized editing it on this branch while present (no `--amend`).
5. **Doc reconciliation.** Rewrite `ENGINE_ARCHITECTURE.md` §2.5 + §2.7; add the
   §8 profiler-deferred note; strip leftover leapfrog migration-narration to
   describe-as-design. Delete the two stale untracked scratch docs. Update
   `DEFERRED_WORK.md` (retire the `BG_TILE_CAPACITY` deferral; mark Phase 3 done).
6. **Verification + merge.** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` exits 0;
   boot in Exodus and confirm the OJZ scroll test renders identically (only
   intended behavior delta = the removed forced-scroll scaffold); re-run the audit
   → comes back clean. FF-merge `cleanup/engine-phase3` to `master`.

## 7. Definition of Done

- `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` exits 0 (lint warnings are
  non-blocking, but the suggestion/warning counts should not *increase*).
- In Exodus: the OJZ scroll test boots and renders identically to the pre-Phase-3
  baseline, except the intended removal of the forced auto-scroll scaffold.
- The verified-clean audit, re-run after edits, reports no remaining dead
  code / orphaned symbols / historical-narration or lying comments (outside the
  user-accepted ambiguous list).
- `ENGINE_ARCHITECTURE.md` §2.5/§2.7/§8 match shipped reality; no
  migration-narration remains as load-bearing description.
- The two stale scratch docs are gone; `DEFERRED_WORK.md` is current.
- All work merged to `master` (FF).

## 8. Risks & Mitigations

- **Mis-stripping a load-bearing comment** (the main risk). *Mitigation:* default
  to KEEP when uncertain; skeptic verification of every removal; user reviews the
  full comment diff before commit; comment changes are build-neutral and fully
  reversible.
- **Deleting code that *looks* dead but is reachable from a niche path** (e.g.
  DEBUG-only or assert-time code). *Mitigation:* mechanical xref grounds the
  candidate list; adversarial verify checks reachability; build green after each
  deletion; anything ambiguous → ask the user.
- **`BG_TILE_CAPACITY` 448 gate breaks the build for the current OJZ data.**
  *Mitigation:* OJZ's BG usage is well under 448; re-run the full build after the
  change; the gate only tightens (512→448), so it can only *catch* an overflow
  that was previously silently waved through.
- **Auto-commit daemon commits `ojz_strip_gen.py` mid-edit.** *Mitigation:* user
  is present and authorized it on this branch; never `--amend`; the edit is a
  single-line constant change.

## 9. Open Items for the Plan

- Exact list of dead-code/orphan findings (produced by Workstream 1, not
  pre-enumerable here).
- The representative comment-edit sample for user sign-off (produced in
  Workstream 3).
