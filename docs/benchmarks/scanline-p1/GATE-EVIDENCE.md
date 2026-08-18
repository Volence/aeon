# Scanline Services P1 — gate evidence

Branch `feature/scanline-p1-scene-model`, paired with sigil branch of the same name.
Spec §8.1. Every number below was measured in this tree on 2026-08-18, not carried
forward from a report.

## 1. Image identity — the parcel's central claim

The reference is the TRUE pre-migration commit, `eeba0ae5` (the merge-base), built in
its own worktree `.worktrees/p1-refbase` with a paired sigil worktree. It predates BOTH
the migration and the raster-substrate parcel, so this one measurement tests both.

| shape | reference `eeba0ae5` | branch head | verdict |
|---|---|---|---|
| `DEBUG=1 ./build.sh` | `ab1055d4` / 712752 | `ab1055d4` / 712752 | EXACT |
| `./build.sh` | `7e4dc5de` / 697868 | `7e4dc5de` / 697868 | EXACT |
| `DEBUG=1 ./build.sh demo` | `10aad76c` / 100805 | `10aad76c` / 100805 | EXACT |
| `./build.sh demo` | `2ecd1031` / 96451 | `2ecd1031` / 96451 | EXACT |

**The demo shapes are the leak detector.** The demo authors no scenes and links no
parallax records; its image must not move AT ALL. It did not.

**Stronger than crc, measured during Task 9:** the 2766-byte record block at `$121C8`
is BYTE-EQUAL to the pre-migration block (extracted from the both-sets ROM before
editing, diffed after), and all 26 symbols sit at their original `.lst` addresses.

## 2. The freeze ritual was a NO-OP, and that is the result

The plan anticipated that placement would move (a module restructure) and budgeted a
repin + `refreeze --freeze --ab`. **Placement did not move — only the module NAME did.**

- `repin` → **"0 pin(s) changed"**. The regenerated `pins.rs` differs only in the
  renamed constant and its doc line; every number identical (`SCENE_REGISTRY`, debug
  base `$121C8`, len `$ACE`).
- `refreeze --check` → OK (tip `parcel-r1-restore-delay`, chain len 133).
- **`--check` is NOT the goldens** (it once passed with 16 golden ROM tests red), so the
  load-bearing evidence is the golden suite below, not this line.

So there was nothing to re-freeze and no `--ab` prose to write. A byte-changing parcel
would have needed both; this one is not that.

## 3. Golden suite — the real freeze gate

`cargo test --release --workspace --no-fail-fast`, `SIGIL_STRICT_GATE=1`,
`AEON_DIR` pointed at this worktree:

**3733 passed, 0 failed, cargo exit 0, ZERO skips.**

- `crates/sigil-harness/golden/provenance.toml` encodes all four crcs
  (`ab1055d4` / `7e4dc5de` / `10aad76c` / `2ecd1031`); `native_full_rom.rs` and
  `native_offcanonical_full.rs` actively compare against them, so the three
  off-canonical profiles (`config_a`, `config_b`, `lean`) are covered too.
- `scene_registry_port` (renamed from `parallax_configs_port`) — the region-level byte
  gate on the migrated block — **2/2**.
- Zero skips matters: these gates SKIP when the reference ROM is absent, and a skip
  reads like a pass in a summary line.

## 4. The equivalence witness (Task 7) — permanent, reachable, red-first

`games/sonic4/test/scene_equiv_proof.emp` proves, at comptime, that all **20 headers,
67 bands and 6 deform tables** lower to exactly the shipped values, against an oracle
transcribed independently from the (now deleted) `configs.emp`. **No mismatches.**

Reachability is the load-bearing part, because an unreached module has parse+scan
coverage and ZERO body elaboration — twenty proofs in a dark module assert nothing:
- Reached by a bare whole-path `use` from `ojz_scroll_test.emp`. `--extra-entry` would
  NOT have worked (it adds an edge to one invocation, leaving the witness dark on a
  normal build), and a registry row is impossible (that list carries emitting modules).
- **Red-first re-verified AFTER Task 9's rewiring** — the task that could have silently
  unwired it: `v_center 512 → 513` fails a plain `DEBUG=1 ./build.sh` with
  `scene equivalence: Scene_OJZ_Default's lowered HEADER differs from
  ParallaxConfig_OJZ_Default's at cfg field 4`. Reverted; green.
- `SIGIL_WARNINGS=full` `[module.unreachable]` lists 29 modules; `scene_equiv_proof`,
  `ojz_scenes` and `scene_registry` are all ABSENT from it.

**Scope, stated honestly:** the oracle is a TRANSCRIPTION, so this gate proves "the scene
model equals the shipped parameters as transcribed here". "As transcribed equals what
`configs.emp` held" is what §1's byte identity proves. Two gates, two different claims.

## 5. Poison lane (Task 8)

`tools/emp_expect_fail.py` → **OK, 15/15 cases**, including the four new scene poisons
(grid, capacity, mask A/B differential, proof).

Every poison was verified against a **CONTROL build with the planted defect removed**,
which is what separates "the intended guard fired" from "something failed". The mask
poison is the two-fixture differential form: fixture A PASSES and fixture B fails,
differing in exactly one authored field (`dsb 15 → 2`) and one capability bit. A's
passing was measured, not assumed — setting the declared word to `$0002` makes both of
A's ensures fire. A's declared word is a HAND-DERIVED literal, because `fold_caps([A])`
would make the subset test `(x & ~x) == 0` — true for every input and evidence of nothing.

The lane's sentinel fired correctly throughout, and earned its keep three times this
parcel by catching diagnostic-count drift: a register-token binding, a missing struct
default, and the dangling module id after the deletion.

## 6. Other build-time gates

Tool suite `990 passed, 2 skipped` · `s4lint: no issues` ·
`effects_budget_check: OK — 20 rows` · `verify_level_bin: OK`.

## 7. What this evidence does NOT cover

- **Runtime behaviour** beyond image identity — Task 11's spot-check. Identical images
  imply identical behaviour, so that check is a harness sanity test, not a second gate.
- **The 18 unbound configs.** Only `OJZ_Default` (act fallback) and `OJZ_Underwater`
  (section 0's preset) are referenced by anything, so no runtime check can exercise the
  other eighteen. They are verified by byte identity ALONE. A green Task 11 must not be
  read as "the parallax library is verified".
- **The parallax walker**, which the raster-substrate sweep explicitly excluded from its
  charter (P3 rewrites it). Unexamined, not cleared.
