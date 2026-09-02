# HOME-PATHS-OUTWARD — every place a sibling repo reaches INTO aeon, enumerated (2026-08-30)

**Queue row** `HOME-PATHS-OUTWARD` (`docs/lane-status.json`), the outward half of SUITE-HOME-PATHS in
`docs/DEFERRED_WORK.md`. The inward half converted 43 of this repo's own files to `tools/suite_paths.py`
and introduced `AEON_SUITE_ROOT`. This document is the consumer enumeration that entry said had not been
done: **which committed files in the six sibling checkouts name this tree, what each one does with the
path, whether a process would fail if aeon moved, and which environment variable (if any) already
overrides it.** Enumeration and recommendation only — nothing outside this worktree was modified, no
sibling test suite was run, no ROM byte moved.

## 0. The answer in one screen

| repo | HEAD | tree | files with a hit | sites | sites naming **aeon** | **load-bearing** aeon sites (files) |
|---|---|---|---:|---:|---:|---:|
| sigil | `036800fd` (master) | clean | 202 | 365 | 238 | **128** (108) |
| oracle | `7d57efa` (main) | DIRTY (1 path in `git status --porcelain`) | 65 | 133 | 44 | **4** (4) |
| aurora | `6fbfe9dd` (master) | clean | 272 | 566 | 203 | **76** (74) |
| seraph | `e149a22` (main) | DIRTY (2 paths) | 12 | 96 | 8 | **0** (0) |
| empyrean | `5dfd6c5` (main) | clean | 47 | 407 | 53 | **0** (0) |
| oracle-old | `58b6f81` (main) | clean | 21 | 80 | 12 | **10** (8) |
| **total** | | | **619** | **1647** | **558** | **218** (194) |

*(Load-bearing column corrected on review 2026-09-02: oracle 5 (5) → 4 (4), aurora 82 (79) → 76 (74),
total 225 (200) → 218 (194) — six rows had been ruled YES on lines that are comments, docstrings, a
`console.log` string, or a guard's refused value. The other five columns re-derived exactly. See the
review block at the end.)*

*files / sites* = the deduplicated union of the absolute-path grep and the relative-path grep (a file
hit by both is counted once per grep; §1 gives the two greps separately). *naming aeon* = the literal
resolves to `<suite>/aeon` itself (not `aeon-p25`, `.aeon-ref-drift`, or another sibling). *load-bearing*
= an executable line, not a comment or a record, that a process opens/imports/executes and that would
fail or silently skip if this checkout moved — see §2 for the verdict rules. Prose mentions are in the
tables but are never load-bearing.

**The three most load-bearing sites, by name:**

1. **`sigil/crates/sigil-harness/src/test_support.rs:601` — `LIVE_TREE_FALLBACK`.** The one constant
   `aeon_dir()` returns when `AEON_DIR` is unset; **261 call sites in 67 files** route through it (none of
   them carry the literal, so the grep alone under-counts sigil by that much). A write into the tree it
   names already refuses without `AEON_DIR` (d-17); a read still falls back and announces itself once per
   process. Beside it, 99 `sigil-cli/tests/*.rs` gate files carry their OWN copy of the same
   `env::var("AEON_DIR").unwrap_or_else(|_| "/home/volence/sonic_hacks/aeon")` line (86 executable, 13 in the
   header comment only).
2. **`sigil/scripts/nightly_source_gates.sh:31-34` — `AEON_MAIN=/home/volence/sonic_hacks/aeon` plus
   three sibling clones under the suite root, hard-coded, no override at all**, and it is the script an
   ENABLED systemd user timer runs nightly (`sigil-source-gates.timer`: enabled, last ran
   2026-08-30 05:17 EDT, next 2026-08-31 05:17). The twin `nightly_ref_drift.sh` + `drift-nightly.conf`
   have the same shape but their unit is not installed (`~/.config/systemd/user/sigil-ref-drift.*`
   absent; `is-enabled` → `not-found`).
3. **`sigil/scripts/landing-run.sh:207` — `AEON=$(abspath "${AEON_ARG:-${AEON_DIR:-/home/volence/sonic_hacks/aeon}}")`.**
   Every sigil landing run's default subject. It is the *good* shape — it refuses by name when the
   result is not an aeon checkout — but the default is still this machine's home directory.

Runner-up clusters: **oracle-old `linux-port/harness/*.py`** (8 files, 10 `ROM =`/`LST =` module
constants naming built aeon artifacts, no override of any kind — the legacy harness), **aurora's 72
committed scratchpad instruments** that default to the live tree (45 with an `AEON_DIR`/`LIVE_AEON`
fallback, 27 hard-coded), and **oracle `examples/common/rom_source.rs:44` `LIVE_AEON_DIR`** (three
hand-run examples default to it for the two artifacts oracle chose not to freeze).

**Env-var spellings peers already use to point at aeon** (§10): `AEON_DIR` (sigil: 100 files read it as an env var by command C, 145 name it anywhere outside prose — the
"124" this document first printed reproduced under no counting rule; aurora: 60 files; sigil CI pins it to
`/nonexistent/...` on purpose), `AEON_ARG` (sigil landing-run, CLI form),
`AEON_REPO` (sigil provision + ref-drift), `ORACLE_AEON_DIR` (oracle, 3 files, default = frozen
`fixtures/aeon/`), `AEON_ROOT` (aurora, 1 test), `AURORA_PEER_ROOT` + `AURORA_AEON_REPO` (aurora's
resolver: suite root + per-peer override), `LIVE_AEON` (2 aurora instruments), `TOOLS` (oracle
blastem-differential, aeon's `tools/`), `PROFILE_LST` (sigil A/B scripts, a listing path), and — found on
review — bare `AEON` (aurora `scratchpad/bg-roomy-regenerate.sh:16`, `AEON=${AEON:-$HERE/../aeon}`, 1 file).
**`AEON_SUITE_ROOT` appears in zero committed files outside aeon.** Nothing outside this repo knows it.

## 1. Method — the exact commands, and what each cannot see

Run 2026-08-30 from this worktree against the six sibling checkouts at the HEADs in §0, read-only
(`git -C <repo> grep` reads the index; no sibling file was written, no sibling test suite was run).

```sh
# A — absolute literals (the brief's command, verbatim), per repo
git -C /home/volence/sonic_hacks/<repo> grep -n -I -E 'sonic_hacks/aeon|/home/volence/sonic_hacks' \
    -- ':!*.lock' ':!target/*' ':!node_modules/*'
# B — relative reach through the sibling layout
git -C /home/volence/sonic_hacks/<repo> grep -n -I -E '(\.\./)+aeon(/|$|[^A-Za-z0-9_-])' \
    -- ':!*.lock' ':!target/*' ':!node_modules/*'
# C — env-var spellings containing AEON, in code contexts only
git -C /home/volence/sonic_hacks/<repo> grep -n -I -o -E '(env::var\("[A-Z0-9_]*AEON[A-Z0-9_]*"\)|process\.env\.[A-Z0-9_]*AEON[A-Z0-9_]*|environ(\.get)?\[?\(?"[A-Z0-9_]*AEON[A-Z0-9_]*"|\$\{[A-Z0-9_]*AEON[A-Z0-9_]*[:}-]|...)' \
    -- ':!*.md' ':!*.txt' ':!*.lock' ':!target/*' ':!node_modules/*' ':!*.jsonl'
# D — identifier-routed consumers that carry NO literal (per repo, see §9)
git -C .../sigil  grep -c -E '\baeon_dir\(\)' -- crates            # 261 sites / 67 files
git -C .../oracle grep -n -E 'LIVE_AEON_DIR|live_aeon\(' -- 'crates/*.rs' 'tools/*'
git -C .../aurora grep -n -E "(referenceFile|referenceTree|referencePath|siblingPath|peerRepo)\(\s*'aeon'" -- src test scripts
# E — committed CI / systemd / .claude surfaces
git -C <repo> ls-files .claude .github      # sigil: ci.yml; oracle: ci.yml + nightly-differential.yml; others: none
systemctl --user list-timers --all; [ -f ~/.config/systemd/user/sigil-*.{service,timer} ]
```

Every grep exited 0 with output except B and C on seraph and oracle-old (exit 1 = no match, and B on
empyrean matched only wiki links); no `2>/dev/null` anywhere. Grep A returns every line that names the
suite root, so hits naming *other* siblings (`s1disasm`, `empyrean/clients/python`, sigil's own
`.aeon-ref-drift` clones) are in the tables too, marked *not aeon* — they are consumers of the suite
LAYOUT and would move with it, which is the hub's question, but they are not counted as load-bearing
**for aeon**. No sibling has a committed `.claude/` directory; sigil and oracle have committed
`.github/workflows/` (read: sigil's CI sets `AEON_DIR: /nonexistent/aeon-not-checked-out-in-ci`, oracle's
names only its own frozen `fixtures/aeon` pin test).

**What this grep cannot see, stated rather than rendered as zero:**

* consumers that reach aeon through an identifier (`aeon_dir()`, `LIVE_AEON_DIR`, `peerRepo('aeon')`) —
  enumerated separately in §9 by command D;
* consumers that resolve `../aeon` at run time from a computed base (`$SIGIL_ROOT/../aeon`,
  `resolve(REPO, '..', 'aeon')`, an ancestor walk) — B catches the ones that spell `../aeon`; a walk that
  spells only `'aeon'` (aurora `screen.test.ts`, the injector-gate test) was found by reading the files
  named by C and by aurora's own review docs, not by a grep;
* uncommitted or gitignored state (aurora's `scratchpad/fixtures/aeon-build-pin/`, `aeon-console-fix/`
  copies; sigil's `.aeon-*` clones) — deliberately out of scope: the brief says committed files.

## 2. Verdict rules (mechanical; every row is re-derivable from its grep line)

| column | rule |
|---|---|
| *literal* | the `/home/volence/sonic_hacks/<first path component>` match, or the `../aeon` match |
| *PROSE* | the file is `.md`/`.txt`, or the line is a comment (`//`, `#`, `*`, `//!`, docstring), or the literal sits after a trailing `//`/`#` |
| *RECORD* | `.json`/`.toml`/`.log`/`.jsonl` data — a path written down as provenance, never opened by the file that holds it |
| *YES — fallback default* | executable line; the literal is the default of `env::var(..).unwrap_or_else`, `process.env.X ??`, `environ.get(X, ..)`, `${X:-..}` |
| *YES — hard-coded* | executable line naming aeon with no override construct on the line |
| *GUARD* | the literal is compared against (`startsWith`, `===`, `includes`) so the harness can REFUSE it — the value it must never open |
| *NO for aeon* | executable, but the literal names a different sibling (moves with the suite, not with aeon) |
| *env-override-aware?* | the variable(s) the line or its resolver honours; `none` means a move needs a source edit |

A file's verdict is the strongest of its lines (fallback > hard-coded > guard > record > prose).
`load-bearing sites` counts only executable, aeon-naming lines in files whose verdict is YES.

## 3. sigil — HEAD `036800fd` (master), tree clean

Absolute grep A: **197 files / 359 sites** (144 code files / 208 sites; 53 prose files / 151 sites); 232 sites in 150 files name aeon; **load-bearing: 126 sites in 106 files**. Relative grep B: 5 files / 6 sites; load-bearing 2 sites in 2 files.

**Shape.** Two mechanisms, both defaulting to the home literal. (a) Every `crates/sigil-cli/tests/*.rs`
gate file (and `sigil-frontend-emp/tests/cfg_blind_spots.rs`) opens with its own private
`std::env::var("AEON_DIR").unwrap_or_else(|_| "/home/volence/sonic_hacks/aeon".to_string())`; when the tree
is absent these gates **SKIP green** unless `SIGIL_STRICT_GATE=1` (their own headers say so). (b) The
harness crate centralises the same fallback as `test_support::LIVE_TREE_FALLBACK`, consumed by
`aeon_dir()` — 261 call sites / 67 files that carry no literal. The landing wrapper, the golden capture,
the off-canonical derivation and the two nightly lanes all default to the same path; the nightly lanes
do so **without any override**. `scripts/provision-aeon-ref.sh` is the one place with a relative default
(`$SIGIL_ROOT/../aeon`, overridable by `AEON_REPO`). The A/B evidence scripts under `golden/ab/` are
hand-run and reach TWO peers: `sys.path.insert` of `empyrean/clients/python` (18 files, no override) and
aeon's `s4.debug.lst` (8 files, `PROFILE_LST` in 6 of them). `provenance.toml`'s eleven `ab =` fields and the six
`profile_*.json` `rom` fields are records.

### sigil — absolute literals: code / data files (144 files, 208 sites)

| file | lines | literal(s) | use | load-bearing? | env-override-aware? |
|---|---|---|---|---|---|
| `crates/sigil-cli/tests/act_descriptor_port.rs` | 55,334 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/animate_port.rs` | 58,76 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/bg_anim_port.rs` | 52 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/bg_port.rs` | 47 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/boot_port.rs` | 33,55 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/buffers_port.rs` | 27,53 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/camera_port.rs` | 85 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/children_port.rs` | 39 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/collision_data_port.rs` | 24 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/collision_lookup_port.rs` | 60,87,360,402 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/collision_port.rs` | 63,81 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/compression_selftest_port.rs` | 41 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/contract_closure_corpus.rs` | 69,1243 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/controllers_port.rs` | 96,122,431,488 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/core_negative_probes.rs` | 33 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/core_port.rs` | 43,61 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/dac_bank_port.rs` | 30 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/dead_save_corpus.rs` | 45 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/diag_assert_vector.rs` | 39 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/dma_queue_port.rs` | 49 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/dplc_negative_probes.rs` | 36,49 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/dplc_port.rs` | 34,52 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/entity_window_port.rs` | 34 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/error_handler_port.rs` | 36 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/extra_entry.rs` | 83 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/game_debug_port.rs` | 34 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/game_loop_port.rs` | 60,94 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/hblank_negative_probes.rs` | 49 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/hblank_port.rs` | 42,63,296,319 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/header_port.rs` | 34 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/load_art_port.rs` | 50 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/load_object_port.rs` | 35 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/math_port.rs` | 75 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | PROSE (comment) | `AEON_DIR` |
| `crates/sigil-cli/tests/movem_restore_guard_corpus.rs` | 174 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/mt_bank_port.rs` | 22 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | PROSE (comment) | `AEON_DIR` |
| `crates/sigil-cli/tests/mt_negative_probes.rs` | 56 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/mt_port.rs` | 38 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | PROSE (comment) | `AEON_DIR` |
| `crates/sigil-cli/tests/native_declared_chain.rs` | 24 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/native_full_rom.rs` | 29 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/native_object_bank_budget.rs` | 29 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/native_rom.rs` | 30 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/objdef_port.rs` | 9 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | PROSE (comment) | `AEON_DIR` |
| `crates/sigil-cli/tests/ojz_run_a_port.rs` | 44 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/ojz_run_b_port.rs` | 34 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/out_verify_corpus.rs` | 38 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/p5_constants_flip.rs` | 16 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/parallax_port.rs` | 54 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/parcel_8b_stage_gen_touchers.rs` | 120 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/particle_anims_port.rs` | 49,77,225 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/plane_buffer_port.rs` | 59 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/preserves_corpus.rs` | 58 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/raster_negative_probes.rs` | 53 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/raster_port.rs` | 48,66 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/rings_port.rs` | 58,81 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/s4lz_port.rs` | 51 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/scene_registry_port.rs` | 45 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/seam1_native_link.rs` | 17 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | PROSE (comment) | `AEON_DIR` |
| `crates/sigil-cli/tests/seam2_colink_probe.rs` | 32 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/seam2_dac_emit.rs` | 28 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/seam2_dac_head_colink.rs` | 37 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/seam2_layout_derivation.rs` | 16 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/seam2_phased_head.rs` | 41 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/seam2_pitchtable.rs` | 28 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/seam2_seq_colink.rs` | 29 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/seam2_sfx_head_colink.rs` | 34 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/seam2_soundtables_colink.rs` | 28 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/section_port.rs` | 49,346 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/sfx_bank_port.rs` | 29 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/sfx_negative_probes.rs` | 68 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/sfx_port.rs` | 42 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | PROSE (comment) | `AEON_DIR` |
| `crates/sigil-cli/tests/slot_type_corpus.rs` | 37 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/sonic_anims_port.rs` | 47,148,243,320 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/sound_api_port.rs` | 39,57 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/soundbankhead_port.rs` | 31 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/sprites_port.rs` | 79 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/structs_module.rs` | 15 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | PROSE (comment) | `AEON_DIR` |
| `crates/sigil-cli/tests/test_g1_objects_port.rs` | 40 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/test_g2_objects_port.rs` | 26 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | PROSE (comment) | `AEON_DIR` |
| `crates/sigil-cli/tests/test_g3_objects_port.rs` | 26 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | PROSE (comment) | `AEON_DIR` |
| `crates/sigil-cli/tests/test_g4_final_objects_port.rs` | 38 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/test_mappings_port.rs` | 43,141 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/test_objects_port.rs` | 65,83 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/test_p1_player_port.rs` | 33 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | PROSE (comment) | `AEON_DIR` |
| `crates/sigil-cli/tests/test_p2_player_states_port.rs` | 12 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | PROSE (comment) | `AEON_DIR` |
| `crates/sigil-cli/tests/test_p4_player_sensors_port.rs` | 16 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | PROSE (comment) | `AEON_DIR` |
| `crates/sigil-cli/tests/tile_cache_port.rs` | 52,362,570 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/tranche24_spelling_probes.rs` | 363 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/tranche2_negative_probes.rs` | 46 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/tranche3_negative_probes.rs` | 48 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/tranche4_negative_probes.rs` | 25 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/tranche5_negative_probes.rs` | 31 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/tranche6_negative_probes.rs` | 34 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/tranche7_negative_probes.rs` | 30 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/vblank_port.rs` | 24,50 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/vdp_init_port.rs` | 84,105,443,469 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/vectors_port.rs` | 46 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/warn_tier_corpus.rs` | 240 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-cli/tests/z80_clobbers_incomplete.rs` | 17 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | PROSE (comment) | `AEON_DIR` |
| `crates/sigil-frontend-emp/tests/cfg_blind_spots.rs` | 311,440 | `/home/volence/sonic_hacks/aeon` | aeon SOURCE tree read by a source-compilation gate (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-harness/golden/ab/a3/ab_runner_codepoint.py` | 8 | `/home/volence/sonic_hacks/empyrean` | hand-run A/B evidence script: `sys.path.insert` of empyrean's Python Aether client (import) | NO for aeon (names another sibling) | none |
| `crates/sigil-harness/golden/ab/a3/ab_runner_quantum.py` | 16 | `/home/volence/sonic_hacks/empyrean` | hand-run A/B evidence script: `sys.path.insert` of empyrean's Python Aether client (import) | NO for aeon (names another sibling) | none |
| `crates/sigil-harness/golden/ab/g9/ab_g9_state.py` | 18,24 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/empyrean` | hand-run A/B evidence script: `sys.path.insert` of empyrean's Python Aether client (import); aeon `s4.debug.lst` listing as the profiler symbol source | YES — fallback default | `PROFILE_LST` |
| `crates/sigil-harness/golden/ab/g9/ab_g9_witness.py` | 15 | `/home/volence/sonic_hacks/empyrean` | hand-run A/B evidence script: `sys.path.insert` of empyrean's Python Aether client (import) | NO for aeon (names another sibling) | none |
| `crates/sigil-harness/golden/ab/waveb/ab_collision_state.py` | 18,24 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/empyrean` | hand-run A/B evidence script: `sys.path.insert` of empyrean's Python Aether client (import); aeon `s4.debug.lst` listing as the profiler symbol source | YES — fallback default | `PROFILE_LST` |
| `crates/sigil-harness/golden/ab/waveb/ab_pb4.py` | 13 | `/home/volence/sonic_hacks/empyrean` | hand-run A/B evidence script: `sys.path.insert` of empyrean's Python Aether client (import) | NO for aeon (names another sibling) | none |
| `crates/sigil-harness/golden/ab/waveb/ab_pb4_single.py` | 13 | `/home/volence/sonic_hacks/empyrean` | hand-run A/B evidence script: `sys.path.insert` of empyrean's Python Aether client (import) | NO for aeon (names another sibling) | none |
| `crates/sigil-harness/golden/ab/waveb/profile_BEFORE_churn.json` | 3 | `/home/volence/sonic_hacks/aeon` | recorded profile output — the `rom` field records which ROM was measured | RECORD | n/a |
| `crates/sigil-harness/golden/ab/waveb/profile_BEFORE_maxH.json` | 3 | `/home/volence/sonic_hacks/aeon` | recorded profile output — the `rom` field records which ROM was measured | RECORD | n/a |
| `crates/sigil-harness/golden/ab/waveb/profile_EW1_AFTER_FIXED_maxH.json` | 3 | `/home/volence/sonic_hacks/aeon` | recorded profile output — the `rom` field records which ROM was measured | RECORD | n/a |
| `crates/sigil-harness/golden/ab/waveb/profile_EW1_AFTER_maxH.json` | 3 | `/home/volence/sonic_hacks/aeon` | recorded profile output — the `rom` field records which ROM was measured | RECORD | n/a |
| `crates/sigil-harness/golden/ab/waveb/profile_EW1_BEFORE_maxH.json` | 3 | `/home/volence/sonic_hacks/sigil` | recorded profile output — the `rom` field records which ROM was measured | RECORD | n/a |
| `crates/sigil-harness/golden/ab/waveb/profile_TC2_AFTER_maxH.json` | 3 | `/home/volence/sonic_hacks/aeon` | recorded profile output — the `rom` field records which ROM was measured | RECORD | n/a |
| `crates/sigil-harness/golden/ab/waveb/profile_churn.py` | 12,18 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/empyrean` | hand-run A/B evidence script: `sys.path.insert` of empyrean's Python Aether client (import); aeon `s4.debug.lst` listing as the profiler symbol source | YES — hard-coded | none |
| `crates/sigil-harness/golden/ab/waveb/profile_collision.py` | 24,29 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/empyrean` | hand-run A/B evidence script: `sys.path.insert` of empyrean's Python Aether client (import); aeon `s4.debug.lst` listing as the profiler symbol source | YES — fallback default | `PROFILE_LST` |
| `crates/sigil-harness/golden/ab/waveb/profile_drive.py` | 12,18 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/empyrean` | hand-run A/B evidence script: `sys.path.insert` of empyrean's Python Aether client (import); aeon `s4.debug.lst` listing as the profiler symbol source | YES — hard-coded | none |
| `crates/sigil-harness/golden/ab/waveb/profile_drive2.py` | 12,18 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/empyrean` | hand-run A/B evidence script: `sys.path.insert` of empyrean's Python Aether client (import); aeon `s4.debug.lst` listing as the profiler symbol source | YES — fallback default | `PROFILE_LST` |
| `crates/sigil-harness/golden/ab/waveb/vram_dump.py` | 4 | `/home/volence/sonic_hacks/empyrean` | hand-run A/B evidence script: `sys.path.insert` of empyrean's Python Aether client (import) | NO for aeon (names another sibling) | none |
| `crates/sigil-harness/golden/ab/wavec/ab_wavec_ramdiff.py` | 8 | `/home/volence/sonic_hacks/empyrean` | hand-run A/B evidence script: `sys.path.insert` of empyrean's Python Aether client (import) | NO for aeon (names another sibling) | none |
| `crates/sigil-harness/golden/ab/wavec/ab_wavec_scroll.py` | 18,24 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/empyrean` | hand-run A/B evidence script: `sys.path.insert` of empyrean's Python Aether client (import); aeon `s4.debug.lst` listing as the profiler symbol source | YES — fallback default | `PROFILE_LST` |
| `crates/sigil-harness/golden/ab/wavec/ab_wavec_shot.py` | 5 | `/home/volence/sonic_hacks/empyrean` | hand-run A/B evidence script: `sys.path.insert` of empyrean's Python Aether client (import) | NO for aeon (names another sibling) | none |
| `crates/sigil-harness/golden/ab/wavec/ab_wavec_state.py` | 33,39 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/empyrean` | hand-run A/B evidence script: `sys.path.insert` of empyrean's Python Aether client (import); aeon `s4.debug.lst` listing as the profiler symbol source | YES — fallback default | `PROFILE_LST` |
| `crates/sigil-harness/golden/ab/wavec/ab_wavec_vcheck.py` | 6 | `/home/volence/sonic_hacks/empyrean` | hand-run A/B evidence script: `sys.path.insert` of empyrean's Python Aether client (import) | NO for aeon (names another sibling) | none |
| `crates/sigil-harness/golden/ab/wavec/ab_wavec_vshot.py` | 6 | `/home/volence/sonic_hacks/empyrean` | hand-run A/B evidence script: `sys.path.insert` of empyrean's Python Aether client (import) | NO for aeon (names another sibling) | none |
| `crates/sigil-harness/golden/capture_goldens.sh` | 75 | `/home/volence/sonic_hacks/aeon` | golden freeze capture: reads the built aeon shapes (`AEON_DIR` fallback) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-harness/golden/derive_offcanonical_sizes.sh` | 25 | `/home/volence/sonic_hacks/aeon` | off-canonical size derivation: reads the aeon tree (`AEON_DIR` fallback) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-harness/golden/provenance.toml` | 5952,6005,6058,6164,6217,6271,6325,6379,6433,6487,6541 | `/home/volence/sonic_hacks/aeon` | `ab =` evidence pointer in a freeze entry (a record of where the A/B evidence doc lived) | RECORD | n/a |
| `crates/sigil-harness/src/bin/cycle_fraction.rs` | 312 | `/home/volence/sonic_hacks/aeon` | aeon tree for a harness gate / bin (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-harness/src/bin/repin.rs` | 92 | `/home/volence/sonic_hacks/aeon` | aeon tree for a harness gate / bin (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-harness/src/test_support.rs` | 601 | `/home/volence/sonic_hacks/aeon` | `LIVE_TREE_FALLBACK` — THE central fallback `aeon_dir()` returns when `AEON_DIR` is unset (261 call sites in 67 files route through it) | YES — hard-coded | `AEON_DIR` |
| `crates/sigil-harness/tests/act_fixture_drift.rs` | 17 | `/home/volence/sonic_hacks/aeon` | aeon tree for a harness gate / bin (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-harness/tests/banked_carrier_drift.rs` | 23 | `/home/volence/sonic_hacks/aeon` | aeon tree for a harness gate / bin (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-harness/tests/m1b_gate.rs` | 36,51 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/oracle-old` | aeon source tree (`AEON_DIR` fallback) + oracle-old harness dir (`ORACLE_DIR` fallback) | YES — fallback default | `AEON_DIR`, `ORACLE_DIR` |
| `crates/sigil-harness/tests/m1c_vector_table.rs` | 25 | `/home/volence/sonic_hacks/aeon` | aeon tree for a harness gate / bin (`AEON_DIR` fallback default) | YES — fallback default | `AEON_DIR` |
| `crates/sigil-harness/tests/repin_pins.rs` | 7 | `/home/volence/sonic_hacks/aeon` | aeon tree for a harness gate / bin (`AEON_DIR` fallback default) | PROSE (comment) | `AEON_DIR` |
| `crates/sigil-isa/tests/encode_base_8bit.rs` | 4 | `/home/volence/sonic_hacks/aeon` | doc-comment naming aeon as ground truth for a vector | PROSE (comment) | n/a |
| `docs/lane-log.jsonl` | 86 | `/home/volence/sonic_hacks/.sigil-freeze-bin` | lane-log narrative | RECORD | n/a |
| `docs/superpowers/notes/phase2.5-apply_orgs.py` | 7 | `/home/volence/sonic_hacks/aeon-p25` | historical one-off script naming a retired `aeon-p25` scratch tree | NO for aeon (names another sibling) | none |
| `scripts/corpus_bytediff.sh` | 17 | `/home/volence/sonic_hacks/sigil` | sigil master checkout path (not aeon) | NO for aeon (names another sibling) | none |
| `scripts/drift-nightly.conf` | 34,47 | `/home/volence/sonic_hacks/.aeon-ref-drift` | drift job config: the drift record reader and the job's own aeon clone under the suite root | NO for aeon (names another sibling) | none (hard-coded) |
| `scripts/landing-run.sh` | 207 | `/home/volence/sonic_hacks/aeon` | landing wrapper: resolves the aeon checkout once (`AEON_ARG`/`AEON_DIR` fallback), refuses by name if not a checkout | YES — fallback default | `AEON_ARG`, `AEON_DIR` |
| `scripts/nightly_ref_drift.sh` | 37,38,41,47 | `/home/volence/sonic_hacks/.sigil-ref-drift`; `/home/volence/sonic_hacks/.sigil-ref-drift-target`; `/home/volence/sonic_hacks/aeon` … | nightly ref-drift lane: `AEON_MAIN` + its own clones under the suite root; unit NOT installed in ~/.config/systemd/user | YES — hard-coded | none for the paths (`AEON_REPO` is only forwarded to provision) |
| `scripts/nightly_source_gates.sh` | 31,32,33,34,41 | `/home/volence/sonic_hacks/.aeon-sigil-gates`; `/home/volence/sonic_hacks/.sigil-source-gates`; `/home/volence/sonic_hacks/.sigil-source-gates-target` … | nightly source-gate lane: `AEON_MAIN` (fetch source) + `AEON_GATES` (its own clone under the suite root); INSTALLED, timer enabled, last ran 2026-08-30 05:17 | YES — hard-coded | none (hard-coded) |
| `scripts/systemd/sigil-ref-drift.service` | 6 | `/home/volence/sonic_hacks/sigil` | systemd unit `ExecStart` naming sigil's OWN script path (suite-root-relative, not aeon) | NO for aeon (names another sibling) | none |
| `scripts/systemd/sigil-source-gates.service` | 6 | `/home/volence/sonic_hacks/sigil` | systemd unit `ExecStart` naming sigil's OWN script path (suite-root-relative, not aeon) | NO for aeon (names another sibling) | none |

### sigil — absolute literals: prose files (53 files, 151 sites) — PROSE, never load-bearing

| file | sites | naming aeon | lines |
|---|---:|---:|---|
| `crates/sigil-frontend-emp/tests/vectors/s4lz/README.md` | 3 | 2 | 21,36,37 |
| `docs/OVERSEER.md` | 12 | 5 | 845,1267,1321,2402,2775,4048,4065,4215,4649,5276,5534,5742 |
| `docs/superpowers/notes/2026-07-03-m1c-spike0-findings.md` | 2 | 2 | 3,57 |
| `docs/superpowers/notes/2026-07-08-item7-implementation-handoff.md` | 1 | 0 | 4 |
| `docs/superpowers/notes/2026-07-08-item7-implementation-notes.md` | 3 | 0 | 3,10,30 |
| `docs/superpowers/notes/2026-07-08-item9-implementation-handoff.md` | 1 | 0 | 4 |
| `docs/superpowers/notes/2026-07-12-object-pool-occupancy-build-packet.md` | 1 | 1 | 323 |
| `docs/superpowers/notes/2026-07-22-phase2.5-item9-design-gate.md` | 4 | 0 | 60,119,120,163 |
| `docs/superpowers/notes/2026-07-23-t18-step1-transcribe-plan.md` | 3 | 0 | 108,138,139 |
| `docs/superpowers/notes/2026-07-29-game-side-census.md` | 1 | 0 | 424 |
| `docs/superpowers/notes/2026-07-29-t27-close-packet.md` | 1 | 0 | 147 |
| `docs/superpowers/notes/2026-07-30-levelgen-design.md` | 1 | 0 | 150 |
| `docs/superpowers/notes/2026-08-19-m68k-roundtrip-packet.md` | 1 | 1 | 309 |
| `docs/superpowers/notes/2026-08-22-capstone-differential-packet.md` | 1 | 0 | 408 |
| `docs/superpowers/notes/2026-08-22-field-align-packet.md` | 3 | 0 | 362,368,372 |
| `docs/superpowers/notes/2026-08-22-pub-equ-export-packet.md` | 2 | 0 | 240,248 |
| `docs/superpowers/notes/2026-08-22-rom-sentinel-packet.md` | 12 | 0 | 134,165,171,172,173,174,175,197,198,210,277,280 |
| `docs/superpowers/notes/2026-08-22-version-provenance-packet.md` | 3 | 0 | 25,91,286 |
| `docs/superpowers/notes/2026-08-26-derived-layout-packet.md` | 3 | 0 | 46,151,152 |
| `docs/superpowers/notes/2026-08-26-five-reg-packet.md` | 1 | 0 | 102 |
| `docs/superpowers/notes/2026-08-26-nightly-gap-packet.md` | 1 | 0 | 138 |
| `docs/superpowers/notes/2026-08-26-pad-packet.md` | 4 | 0 | 142,147,179,191 |
| `docs/superpowers/notes/2026-08-26-repin-end-packet.md` | 1 | 0 | 137 |
| `docs/superpowers/notes/2026-08-26-rig-closure-packet.md` | 2 | 0 | 109,125 |
| `docs/superpowers/notes/2026-08-26-rings-contract-env-packet.md` | 1 | 0 | 8 |
| `docs/superpowers/notes/2026-08-27-constraint-recheck.md` | 2 | 0 | 163,451 |
| `docs/superpowers/notes/2026-08-27-cycle-fraction.md` | 4 | 0 | 5,236,242,245 |
| `docs/superpowers/notes/2026-08-27-embed-base-rule.md` | 4 | 0 | 48,79,83,248 |
| `docs/superpowers/notes/2026-08-27-hole-interior-reserved.md` | 1 | 0 | 71 |
| `docs/superpowers/notes/2026-08-27-prose-bounds-sweep.md` | 2 | 1 | 198,202 |
| `docs/superpowers/notes/2026-08-30-absolute-path-classify.md` | 7 | 4 | 18,22,182,185,202,206,304 |
| `docs/superpowers/notes/2026-08-30-aeon-dir-write-requires-naming.md` | 5 | 4 | 157,179,183,188,231 |
| `docs/superpowers/notes/2026-08-30-reference-tree-write-guard.md` | 2 | 1 | 52,133 |
| `docs/superpowers/notes/2026-08-30-source-gate-third-bucket.md` | 1 | 0 | 180 |
| `docs/superpowers/notes/campaign-gap-ledger.md` | 4 | 2 | 2023,2320,2334,2336 |
| `docs/superpowers/notes/porter-brief-boilerplate.md` | 1 | 1 | 16 |
| `docs/superpowers/plans/2026-07-03-sigil-m0.5-ea-spike.md` | 1 | 1 | 368 |
| `docs/superpowers/plans/2026-07-03-sigil-m1b-linker.md` | 1 | 1 | 1477 |
| `docs/superpowers/plans/2026-07-03-sigil-m1c-spike0-backend-mux.md` | 5 | 3 | 51,55,98,101,122 |
| `docs/superpowers/plans/2026-07-04-sigil-m1c-t6-directives.md` | 1 | 1 | 25 |
| `docs/superpowers/plans/2026-07-04-sigil-m1c-t7-struct-macro.md` | 1 | 1 | 40 |
| `docs/superpowers/plans/2026-07-04-sigil-m1d-t1-string-set.md` | 3 | 3 | 310,344,360 |
| `docs/superpowers/plans/2026-07-04-sigil-m1d-t2-abs-ea-end.md` | 3 | 3 | 319,338,345 |
| `docs/superpowers/plans/2026-07-04-sigil-m1d-t3-frontend-width.md` | 8 | 8 | 29,250,337,471,556,576,585,594 |
| `docs/superpowers/plans/2026-07-08-sound-migration-t0-t1.md` | 3 | 3 | 47,207,277 |
| `docs/superpowers/plans/2026-07-08-sound-migration-t2-mt-bank.md` | 8 | 8 | 154,159,352,388,403,422,467,469 |
| `docs/superpowers/plans/2026-07-08-spec2-plan7-item7pre-placement-fix.md` | 1 | 0 | 13 |
| `docs/superpowers/plans/2026-07-08-spec2-plan7-item9a-dispatch-inline-bodies.md` | 5 | 0 | 13,499,529,556,557 |
| `docs/superpowers/plans/2026-07-08-spec2-plan7-item9b-script-yield.md` | 3 | 0 | 13,663,665 |
| `docs/superpowers/plans/2026-07-09-emp-vscode-highlighter.md` | 4 | 0 | 11,118,362,364 |
| `docs/superpowers/plans/2026-07-09-sound-migration-t3-sfx.md` | 1 | 1 | 207 |
| `docs/superpowers/specs/2026-07-03-sigil-m0.5-ea-spike-design.md` | 1 | 1 | 115 |
| `editors/vscode/README.md` | 1 | 0 | 11 |

### sigil — relative `../aeon` reach: code / data files (2 files, 3 sites)

| file | lines | literal(s) | use | load-bearing? | env-override-aware? |
|---|---|---|---|---|---|
| `crates/sigil-cli/tests/subcommands.rs` | 13 | `../../../aeon` | `concat!(env!("CARGO_MANIFEST_DIR"), "/../../../aeon")` — the aeon SOURCE tree for an `#[ignore]`d subcommand test; relative to the crate, no `AEON_DIR` read at all (sub-verdict corrected on review: it was printed "fallback default") | YES — hard-coded | none |
| `scripts/provision-aeon-ref.sh` | 22,64 | `../aeon` | provisions the pinned reference worktree from `AEON_REPO` (default `../aeon` beside sigil) | YES — fallback default | `AEON_REPO` |

### sigil — relative `../aeon` reach: prose files (3 files, 3 sites) — PROSE, never load-bearing

| file | sites | naming aeon | lines |
|---|---:|---:|---|
| `docs/superpowers/notes/2026-08-01-waveb-b0b-ram-packing.md` | 1 | 1 | 89 |
| `docs/superpowers/plans/2026-07-03-sigil-m1b-linker.md` | 1 | 1 | 1632 |
| `docs/superpowers/plans/2026-07-08-sound-migration-t0-t1.md` | 1 | 1 | 270 |

## 4. oracle — HEAD `7d57efa` (main), tree DIRTY (1 path in `git status --porcelain`)

Absolute grep A: **51 files / 113 sites** (10 code files / 18 sites; 41 prose files / 95 sites); 24 sites in 16 files name aeon; **load-bearing: 1 sites in 1 files**. Relative grep B: 14 files / 20 sites; load-bearing 3 sites in 3 files (was printed 4 in 4: `tools/aether_smoke.py:14` is a docstring line, re-ruled PROSE on review).

**Shape.** The Rust core already did its own sweep (`oracle/docs/2026-08-30-live-tree-readers.md`,
read here at `7d57efa`): tests default to the frozen `fixtures/aeon/` with `ORACLE_AEON_DIR` as the
override, and the ONE remaining live-tree literal is `examples/common/rom_source.rs:44 LIVE_AEON_DIR`,
consumed through `live_aeon()` by three hand-run examples for the two artifacts that have no frozen copy
(`s4.soundtest.bin`, `demo.bin`); each announces the read at startup and takes a CLI path instead. The
other absolute hits are reference ROMs under the suite root, the oracle-old MCP script, and a sigil
fallback in `tools/aeon_pin_report.py` (`ORACLE_SIGIL_DIR` → `../sigil` → literal). The relative hits
that matter are `tools/blastem-differential/build_*.sh` — `TOOLS="${TOOLS:-$HERE/../../../aeon/tools}"`
— aeon's assembler tools for the differential ROM builds (their own doc left this class open by
choice).

### oracle — absolute literals: code / data files (10 files, 18 sites)

| file | lines | literal(s) | use | load-bearing? | env-override-aware? |
|---|---|---|---|---|---|
| `crates/oracle-aether/tests/mcp_tool_sweep.rs` | 39 | `/home/volence/sonic_hacks/oracle-old` | oracle-old legacy MCP script path (not aeon) | NO for aeon (names another sibling) | none |
| `crates/oracle-core/examples/common/rom_source.rs` | 4,44 | `/home/volence/sonic_hacks/aeon` | `LIVE_AEON_DIR` — the ONE live-tree constant; `live_aeon()` consumed by `diag_soundqueue.rs:97`, `synth_render.rs:38`, `k4_openbus_probe.rs:331-332` (zero-arg defaults for unfrozen `s4.soundtest.bin`/`demo.bin`, announced at startup) | YES — hard-coded | none (argv override in each example) |
| `crates/oracle-core/examples/k4_openbus_probe.rs` | 334,335,339,340,341,342,343,344 | `/home/volence/sonic_hacks/AP`; `/home/volence/sonic_hacks/The`; `/home/volence/sonic_hacks/skdisasm` | hand-run probe: reference ROMs under the suite root (S2/S3K/Treasure titles) — not aeon; aeon rows route through `rom_source` | NO for aeon (names another sibling) | none |
| `crates/oracle-core/examples/s3k_sram_probe.rs` | 13 | `/home/volence/sonic_hacks/Sonic` | hand-run probe: the S3K ROM under the suite root (not aeon) | NO for aeon (names another sibling) | none |
| `crates/oracle-core/examples/vgm_capture.rs` | 13 | `/home/volence/sonic_hacks/aeon` | doc-comment recording that the default USED to be the live tree (now `fixtures/aeon`) | PROSE (comment) | n/a |
| `crates/oracle-core/tests/symbols_as_dialect.rs` | 31 | `/home/volence/sonic_hacks/s1disasm` | s1disasm listing fallback (env override in file) — not aeon | NO for aeon (names another sibling) | none |
| `crates/oracle-core/tests/symbols_real_lst.rs` | 28 | `/home/volence/sonic_hacks/aeon` | doc-comment example value for `ORACLE_AEON_DIR`; the default is the frozen `fixtures/aeon/` | PROSE (comment) | n/a |
| `crates/oracle-replay/tests/replay_real_artifacts.rs` | 72 | `/home/volence/sonic_hacks/aeon` | doc-comment example value for `ORACLE_AEON_DIR`; the default is the frozen `fixtures/aeon/` | PROSE (comment) | n/a |
| `docs/2026-08-30-legacy-accept-table.json` | 4276 | `/home/volence/sonic_hacks/oracle-old` | acceptance record naming the oracle-old checkout | RECORD | n/a |
| `tools/aeon_pin_report.py` | 145 | `/home/volence/sonic_hacks/sigil` | sigil checkout fallback (`ORACLE_SIGIL_DIR`, then `../sigil`, then the literal) — not aeon | NO for aeon (names another sibling) | none |

### oracle — absolute literals: prose files (41 files, 95 sites) — PROSE, never load-bearing

| file | sites | naming aeon | lines |
|---|---:|---:|---|
| `README.md` | 1 | 0 | 13 |
| `crates/oracle-aether/tests/contract/PROVENANCE.md` | 6 | 0 | 546,551,552,559,560,565 |
| `docs/2026-07-22-fm-timer-design.md` | 1 | 1 | 18 |
| `docs/2026-07-23-timing-adjudication-oracle.md` | 2 | 2 | 32,139 |
| `docs/2026-08-03-a3-dma-fifo-design.md` | 1 | 0 | 35 |
| `docs/2026-08-03-decision2-premise-recheck.md` | 2 | 0 | 35,36 |
| `docs/2026-08-03-t16-slot-scheduling-recon.md` | 1 | 0 | 71 |
| `docs/2026-08-18-cr21-23-tier1-rows.md` | 2 | 0 | 161,361 |
| `docs/2026-08-18-cr24-scanlines.md` | 1 | 0 | 63 |
| `docs/2026-08-19-aeon-acceptance-results.md` | 1 | 1 | 17 |
| `docs/2026-08-19-aeon-streaming-demand.md` | 1 | 0 | 250 |
| `docs/2026-08-19-cram-serve-recon.md` | 1 | 1 | 624 |
| `docs/2026-08-19-profiler-recon.md` | 2 | 0 | 52,188 |
| `docs/2026-08-19-streaming-asks-recon.md` | 3 | 0 | 27,51,635 |
| `docs/2026-08-19-subline-recon.md` | 2 | 2 | 7,809 |
| `docs/2026-08-20-profiler-corpus-ab.md` | 1 | 0 | 91 |
| `docs/2026-08-22-aeon-instrument-asks.md` | 2 | 0 | 41,971 |
| `docs/2026-08-22-cycle-attribution-audit.md` | 1 | 0 | 5 |
| `docs/2026-08-22-peer-schema-defect-answers.md` | 5 | 0 | 37,91,93,330,784 |
| `docs/2026-08-22-shortrow-residual-measurement.md` | 1 | 0 | 124 |
| `docs/2026-08-26-cr-c-amendment-handoff.md` | 1 | 0 | 415 |
| `docs/2026-08-26-cr-d-object-decoders.md` | 1 | 0 | 529 |
| `docs/2026-08-26-ruling-cr-c.md` | 2 | 0 | 349,356 |
| `docs/2026-08-26-ruling-cr-d-delta.md` | 1 | 0 | 247 |
| `docs/2026-08-26-ruling-cr-d.md` | 1 | 0 | 413 |
| `docs/2026-08-27-cr-e-stop-precision.md` | 1 | 0 | 202 |
| `docs/2026-08-27-obj-join-recon.md` | 1 | 1 | 5 |
| `docs/2026-08-27-pin-audit.md` | 1 | 0 | 53 |
| `docs/2026-08-27-ruling-cr-a.md` | 1 | 0 | 35 |
| `docs/2026-08-27-write-vram.md` | 1 | 0 | 327 |
| `docs/2026-08-30-cr-i-serve.md` | 1 | 0 | 257 |
| `docs/2026-08-30-live-tree-readers.md` | 6 | 5 | 5,30,47,84,148,185 |
| `docs/2026-08-30-replay-net-unblind.md` | 4 | 1 | 48,78,100,466 |
| `docs/2026-08-30-restamp-ab-chain189.md` | 5 | 0 | 48,190,191,192,193 |
| `docs/OVERSEER.md` | 5 | 1 | 133,1184,1291,1768,2121 |
| `docs/plans/2026-07-21-s4-boot-milestone.md` | 1 | 1 | 15 |
| `docs/plans/2026-08-03-fifo-scanline-arcs.md` | 1 | 0 | 39 |
| `docs/proposed/2026-08-30-cr-i-symbolspath.md` | 1 | 0 | 21 |
| `docs/superpowers/plans/2026-08-17-player-s3-lenses.md` | 1 | 0 | 63 |
| `docs/superpowers/plans/2026-08-18-aeon-tier1-bus-methods.md` | 18 | 1 | 84,89,181,348,355,356,372,373,376,1107,1134,1135,1138,1150,1151,1165,1216,1225 |
| `fixtures/aeon/PROVENANCE.md` | 4 | 2 | 10,84,112,366 |

### oracle — relative `../aeon` reach: code / data files (7 files, 9 sites)

| file | lines | literal(s) | use | load-bearing? | env-override-aware? |
|---|---|---|---|---|---|
| `crates/oracle-replay/src/artifacts.rs` | 255 | `../aeon` | synthetic path string in a unit test (`/home/u/scratch/../aeon/p.txt`) — not a real consumer | NO (synthetic test string) | none |
| `docs/decisions.jsonl` | 6 | `../aeon` | lane-log / decisions narrative | RECORD | n/a |
| `docs/lane-log.jsonl` | 1,2,4 | `../aeon` | lane-log / decisions narrative | RECORD | n/a |
| `tools/aether_smoke.py` | 14 | `../aeon` | docstring recording the move from `../aeon` to `fixtures/aeon` (line 14 is inside the module `"""` docstring; the script's launch line names `fixtures/aeon/`) | PROSE (docstring) — corrected on review, was YES | n/a |
| `tools/blastem-differential/build_rom.sh` | 9 | `../../../aeon` | `TOOLS=${TOOLS:-$HERE/../../../aeon/tools}` — aeon's assembler tools for the differential ROM builds (env `TOOLS`) | YES — fallback default | `TOOLS` |
| `tools/blastem-differential/build_vdp_dma_fill.sh` | 6 | `../../../aeon` | `TOOLS=${TOOLS:-$HERE/../../../aeon/tools}` — aeon's assembler tools for the differential ROM builds (env `TOOLS`) | YES — fallback default | `TOOLS` |
| `tools/blastem-differential/build_vdp_pending.sh` | 6 | `../../../aeon` | `TOOLS=${TOOLS:-$HERE/../../../aeon/tools}` — aeon's assembler tools for the differential ROM builds (env `TOOLS`) | YES — fallback default | `TOOLS` |

### oracle — relative `../aeon` reach: prose files (7 files, 11 sites) — PROSE, never load-bearing

| file | sites | naming aeon | lines |
|---|---:|---:|---|
| `docs/2026-07-23-subframe-drift-triage.md` | 1 | 1 | 11 |
| `docs/2026-08-22-acceptance-21-survey.md` | 1 | 1 | 835 |
| `docs/2026-08-26-cr-d-object-decoders.md` | 3 | 3 | 142,165,211 |
| `docs/2026-08-28-rom-open.md` | 1 | 1 | 171 |
| `docs/2026-08-30-live-tree-readers.md` | 2 | 2 | 61,80 |
| `docs/OVERSEER.md` | 2 | 2 | 1593,1643 |
| `docs/superpowers/plans/2026-08-16-player-s1-palette-spine.md` | 1 | 1 | 1148 |

## 5. aurora — HEAD `6fbfe9dd` (master), tree clean

Absolute grep A: **227 files / 490 sites** (172 code files / 328 sites; 55 prose files / 162 sites); 127 sites in 112 files name aeon; **load-bearing: 74 sites in 72 files** (was printed 75 in 73: `crossover-paint-harness.mjs:43` is a guard's refused value, re-ruled GUARD). Relative grep B: 45 files / 76 sites; load-bearing 2 sites in 2 files (was printed 7 in 6: four rows were comments, docstrings, or `console.log` strings, re-ruled PROSE — see the rows).

**Shape.** `src/` and `test/` were converted on 2026-08-30 to a single resolver
(`test/support/sibling-root.mjs` → `AURORA_PEER_ROOT` for the suite root, `AURORA_<NAME>_REPO` per
peer; `test/support/peer-repo.ts` reads peers at a REVISION via `git -C <peer> show`, never the working
tree), and `scripts/check-peer-path-literals.mjs` now FORBIDS the literal under `src/ test/ scripts/`.
So every remaining `src`/`test` hit is a comment quoting the literal it replaced, a fixture provenance
record, or the resolver itself — with three exceptions that reach the live tree by a walk:
`src/core/model/__tests__/screen.test.ts` (ancestor walk for `aeon/engine/system/constants.emp`, no
override), `src/core/editing/__tests__/bg-override-art-injector-gate.test.ts` (ancestor walk for
`aeon/tools/inject_editor_bg.py`, `AEON_ROOT` overrides — a THIRD spelling for the same thing `AEON_DIR`
names elsewhere), and `test/formats/aeon-json-trailing-newline.test.ts` (through `referenceFile('aeon')`,
so the resolver's variables). The gate does not cover `scratchpad/`, which is committed on purpose
(instruments are tracked; `.gitignore` says so) and holds the whole live-tree population: **72 files
default to `/home/volence/sonic_hacks/aeon`** (45 via `process.env.AEON_DIR ??` / `LIVE_AEON` /
`environ.get`, 27 hard-coded `const`), plus 7 whose literal is the value a guard REFUSES, 19 `.log`/lens-sweep
records, 4 comment-only, and 58 files whose literals name other siblings (aurora's own `node_modules`, `.claude/worktrees`, `s1disasm`,
`oracle-next/target`). `src/core/project/__tests__/art-tiers.test.ts:15` `'../aeon/index'` is a false
positive (aurora's own adapter module).

### aurora — absolute literals: code / data files (172 files, 328 sites)

| file | lines | literal(s) | use | load-bearing? | env-override-aware? |
|---|---|---|---|---|---|
| `scratchpad/_select-key-probe.mjs` | 6,7 | `/home/volence/sonic_hacks/aurora` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/aeon-priority-lens-harness.mjs` | 107,108 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/aether-method-gate-proof.mjs` | 67,68 | `/home/volence/sonic_hacks/oracle`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/animated-art-harness.mjs` | 43 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/art-agent-harness.mjs` | 30 | `/home/volence/sonic_hacks/s1disasm.` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | PROSE (comment) | n/a |
| `scratchpad/band-art-foreground-harness.mjs` | 95,96 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `LIVE_AEON` |
| `scratchpad/band-preset-harness.mjs` | 80,83 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as a hard-coded subject | GUARD (refuses the live tree) | none |
| `scratchpad/band-trunk-demo.mjs` | 38 | `/home/volence/sonic_hacks/aeon` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/bg-dangling-ref-harness.mjs` | 50 | `/home/volence/sonic_hacks/aeon` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/bg-override-live-shape-refusal-probe.py` | 17 | `/home/volence/sonic_hacks/aeon` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/bg-override-paints-harness.mjs` | 43,65 | `/home/volence/sonic_hacks/aeon` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/bg-tile-picker-harness.mjs` | 51,72 | `/home/volence/sonic_hacks/aeon` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/bg-wrap-harness.mjs` | 68,69 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/bganim-band-harness.mjs` | 131,132 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/bganim-band-lens-harness.mjs` | 108,109 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/bganim-insert-roomy-harness.mjs` | 62 | `/home/volence/sonic_hacks/aurora` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/bganim-motion-harness.mjs` | 89 | `/home/volence/sonic_hacks/aurora` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/bganim-phase-shift-harness.mjs` | 47 | `/home/volence/sonic_hacks/aurora` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/bganim-preview-fixture.mjs` | 49 | `/home/volence/sonic_hacks/aeon` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/bganim-rate-shift-harness.mjs` | 75,76 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/bganim-strip-range-harness.mjs` | 87,88 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/bganim-tile-door-harness.mjs` | 103,104 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `LIVE_AEON` |
| `scratchpad/bganim-ui-authored-composition-harness.mjs` | 70,71 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/bganim-writer-vs-aeon-gate.emit.ts` | 3 | `/home/volence/sonic_hacks/aurora` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/bo-probe.mjs` | 12,13 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/oracle-next` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/bo-probe2.mjs` | 12,13 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/oracle-next` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/boot-override-harness.mjs` | 49,50,51,56,57 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/oracle-next`; `/home/volence/sonic_hacks/sigil` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — hard-coded | yes (see line) |
| `scratchpad/build-console-overlap-harness.mjs` | 80 | `/home/volence/sonic_hacks/aurora` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/camera-harness.mjs` | 19,20 | `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/camera-preview-harness.mjs` | 77 | `/home/volence/sonic_hacks/aeon` | committed instrument: the literal is the LIVE tree the harness REFUSES to open (guard) | GUARD (refuses the live tree) | none |
| `scratchpad/canvas-cdp-harness.mjs` | 41 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/capture-harness.mjs` | 31,32,33,34 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/chunk-links-harness.mjs` | 72 | `/home/volence/sonic_hacks/aeon` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/chunk-pool-check.mjs` | 3,8 | `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/chunkgrid-hint-harness.mjs` | 39,41,42 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/classic-emu-smoke.mjs` | 12,13,14 | `/home/volence/sonic_hacks/oracle-next`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/classic-playtest-harness.mjs` | 66,67 | `/home/volence/sonic_hacks/oracle-next`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/collision-after-capture.mjs` | 31,32 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/collision-agent-harness.mjs` | 70 | `/home/volence/sonic_hacks/s1disasm.` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | PROSE (comment) | n/a |
| `scratchpad/collision-before-capture.mjs` | 31,32 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/collision-edit-harness.mjs` | 27,29 | `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/collision-gesture-harness.mjs` | 45 | `/home/volence/sonic_hacks/s1disasm.` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | PROSE (comment) | n/a |
| `scratchpad/collision-ghost-capture.mjs` | 31,32 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/collision-legibility-harness.mjs` | 78,79 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/collision-lens-harness.mjs` | 22,24 | `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/collision-mark-normal-harness.mjs` | 74,75 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/collision-needle-harness.mjs` | 22,24 | `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/collision-preservation-harness.mjs` | 111,112 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/collision-read-harness.mjs` | 69,70 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/composer-fill-harness.mjs` | 27,28,29 | `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/composer-priority-harness.mjs` | 109 | `/home/volence/sonic_hacks/aeon` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/crash-harness.mjs` | 13,14 | `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/crossover-paint-harness.mjs` | 42,43 | `/home/volence/sonic_hacks/.aurora-crossover-paint`; `/home/volence/sonic_hacks/aeon` | committed instrument: the subject is the `.aurora-crossover-paint` worktree (42); `LIVE_AEON` (43) is used only at line 51, the compare that REFUSES the live tree | GUARD (refuses the live tree) — corrected on review, was YES | none |
| `scratchpad/curve-editor-harness.mjs` | 108,109 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/curve-option-disabled-harness.mjs` | 85,88 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as a hard-coded subject | GUARD (refuses the live tree) | none |
| `scratchpad/curve-vsplit-reachable-harness.mjs` | 196,199 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as a hard-coded subject | GUARD (refuses the live tree) | none |
| `scratchpad/dump-region.py` | 2 | `/home/volence/sonic_hacks/aeon` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/effects-bob-harness.mjs` | 77 | `/home/volence/sonic_hacks/aurora` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/effects-column-harness.mjs` | 220,221 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/effects-deform-harness.mjs` | 97,98 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/effects-guides-harness.mjs` | 111,112 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/effects-scene-harness.mjs` | 93,94 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/find-curved-slope.py` | 2 | `/home/volence/sonic_hacks/aeon` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/flip-match-real-data.mjs` | 15 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/fromtile-typing-probe.mjs` | 34 | `/home/volence/sonic_hacks/aeon` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/guard-surface-harness.mjs` | 21,55,61 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as a hard-coded subject | GUARD (refuses the live tree) | none |
| `scratchpad/guide-aim-probe.mjs` | 22,23 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/handover/aeon-banks-move.py` | 41 | `/home/volence/sonic_hacks/aeon` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/handover/aeon-section-fit.py` | 31 | `/home/volence/sonic_hacks/aeon` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/handover/handover-band-harness.mjs` | 62 | `/home/volence/sonic_hacks/aurora` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/handover/run-handover.sh` | 20,84 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | handover driver: `AEON_DIR` fallback + `git -C $AEON_DIR show <rev>:` reads; esbuild path under aurora | YES — fallback default | `AEON_DIR` |
| `scratchpad/import-cdp-harness.mjs` | 4 | `/home/volence/sonic_hacks/aurora` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/init-probe.mjs` | 5,6 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/oracle` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/label-measure-probe.mjs` | 20,21,22 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/layer-bound-harness.mjs` | 120,121 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/lens-sweep-2026-08-16/seat-ART.json` | 8,44,68 | `/home/volence/sonic_hacks/s1disasm` | recorded harness output / lens-sweep finding (record) | RECORD | n/a |
| `scratchpad/lens-sweep-2026-08-16/seat-CDP-A.json` | 20 | `/home/volence/sonic_hacks/s1disasm` | recorded harness output / lens-sweep finding (record) | RECORD | n/a |
| `scratchpad/lens-sweep-2026-08-16/seat-CDP-B.json` | 4,6,27,49 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/s1disasm` | recorded harness output / lens-sweep finding (record) | RECORD | n/a |
| `scratchpad/lens-sweep-2026-08-16/seat-DEAD.json` | 6 | `/home/volence/sonic_hacks/megaforge` | recorded harness output / lens-sweep finding (record) | RECORD | n/a |
| `scratchpad/lens-sweep-2026-08-16/seat-ERR.json` | 61 | `/home/volence/sonic_hacks/s1disasm` | recorded harness output / lens-sweep finding (record) | RECORD | n/a |
| `scratchpad/lens-sweep-2026-08-16/seat-FMT.json` | 4,6,15,48,60 | `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/programs`; `/home/volence/sonic_hacks/s1disasm` … | recorded harness output / lens-sweep finding (record) | RECORD | n/a |
| `scratchpad/lens-sweep-2026-08-16/seat-GUARD.json` | 34 | `/home/volence/sonic_hacks/s1disasm` | recorded harness output / lens-sweep finding (record) | RECORD | n/a |
| `scratchpad/lens-sweep-2026-08-16/seat-PERF.json` | 25,137 | `/home/volence/sonic_hacks/s1disasm` | recorded harness output / lens-sweep finding (record) | RECORD | n/a |
| `scratchpad/lens-sweep-2026-08-16/seat-SAVE.json` | 32 | `/home/volence/sonic_hacks/aurora` | recorded harness output / lens-sweep finding (record) | RECORD | n/a |
| `scratchpad/lens-sweep-2026-08-16/seat-SEAM.json` | 8,16,48,76 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm.` | recorded harness output / lens-sweep finding (record) | RECORD | n/a |
| `scratchpad/lens-sweep-2026-08-16/seat-STATE.json` | 34,63 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | recorded harness output / lens-sweep finding (record) | RECORD | n/a |
| `scratchpad/lib/harness-guard.mjs` | 51 | `/home/volence/sonic_hacks/aurora` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | PROSE (comment) | n/a |
| `scratchpad/live-palette-e2e-harness.mjs` | 33,35,36,37 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/oracle-next` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/loop-paint-harness.mjs` | 97,98 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/mapviewport-baseline-harness.mjs` | 218 | `/home/volence/sonic_hacks/aeon` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/marquee-flip-button-harness.mjs` | 76,77 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/marquee-flip-harness.mjs` | 75,76 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/marquee-harness.mjs` | 98,99 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/marquee-paste-probe.mjs` | 24,25 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/marquee-snap-modifier-harness.mjs` | 114,115 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/marquee-stamp-harness.mjs` | 51 | `/home/volence/sonic_hacks/aeon` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/micro-type-harness.mjs` | 22,24 | `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/numberfield-empty-harness.mjs` | 25 | `/home/volence/sonic_hacks/aeon` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/object-label-harness.mjs` | 74,75,76 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/paint-through-harness.mjs` | 36,37 | `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/palette-drag-harness.mjs` | 29,30,31 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/palette-grid-harness.mjs` | 29,30,31,32 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/palette-push-harness.mjs` | 32,33,34 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/oracle-next` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/paste-pan-harness.mjs` | 80,81 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/png-import-real-palette.mjs` | 14 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/pool-headroom.mjs` | 10,11 | `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | yes (see line) |
| `scratchpad/priority-lens-harness.mjs` | 38 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/probe-anim-coords.mts` | 26 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/probe-anim-hipri-cells.mts` | 11 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/probe-classic-hooks.mjs` | 11,12,13 | `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/probe-click-paint.mjs` | 10,11,12 | `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/probe-lens-coords.mts` | 15 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/probe-occlusion-cases.mts` | 22 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/probe-once.mjs` | 10,12 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/probe-sbz-pri-asym.mts` | 8 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/probe-sbz-pri.mts` | 8 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/probe-swatch.mjs` | 5,6,18 | `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/probe-zoom-default.mjs` | 5,6,33 | `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/probe-zoom.mjs` | 5,6,33 | `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/raster-timeline-harness.mjs` | 90,91 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/restore-harness.mjs` | 15,16 | `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/row8-probe.mjs` | 13 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/run-band-art-fg-1.log` | 2,6,82,84 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | recorded harness output / lens-sweep finding (record) | RECORD | n/a |
| `scratchpad/run-band-art-fg-2.log` | 2,6,82,84 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | recorded harness output / lens-sweep finding (record) | RECORD | n/a |
| `scratchpad/run-band-art-fg-3.log` | 2,6,82,84 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | recorded harness output / lens-sweep finding (record) | RECORD | n/a |
| `scratchpad/run-band-art-fg-scale135.log` | 2,6,82,84 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | recorded harness output / lens-sweep finding (record) | RECORD | n/a |
| `scratchpad/run-bound-FINAL-1.log` | 2,7 | `/home/volence/sonic_hacks/aurora` | recorded harness output / lens-sweep finding (record) | RECORD | n/a |
| `scratchpad/run-bound-RED.log` | 2,7 | `/home/volence/sonic_hacks/aurora` | recorded harness output / lens-sweep finding (record) | RECORD | n/a |
| `scratchpad/run-row57-1.log` | 2,6 | `/home/volence/sonic_hacks/aurora` | recorded harness output / lens-sweep finding (record) | RECORD | n/a |
| `scratchpad/run-row57-4-scale135.log` | 2,6 | `/home/volence/sonic_hacks/aurora` | recorded harness output / lens-sweep finding (record) | RECORD | n/a |
| `scratchpad/s1-anim-harness.mjs` | 47,106 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/s1-boss-sprites-harness.mjs` | 58,117 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/s1-layout-anim-harness.mjs` | 47 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/s1-library-presentation-harness.mjs` | 44 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/s1-nonlevel-families-harness.mjs` | 56 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/s1-priority-occlusion-harness.mjs` | 67 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/s1-saveback-cdp-harness.mjs` | 59 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/s1-sonic-preview-harness.mjs` | 53 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/s1-sonic-sprite-harness.mjs` | 37 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/screen-frame-harness.mjs` | 52 | `/home/volence/sonic_hacks/aeon` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/section-column-harness.mjs` | 206,264,266,267 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/section-header-action-harness.mjs` | 95,96 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/section-raster-select-harness.mjs` | 104,107 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as a hard-coded subject | GUARD (refuses the live tree) | none |
| `scratchpad/shell-flip-harness.mjs` | 27,28,29,33 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/slot-range-onscreen-harness.mjs` | 27 | `/home/volence/sonic_hacks/aeon` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/sonic-anim-study.mjs` | 16,17,18 | `/home/volence/sonic_hacks/oracle-next`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/sprite-restore-harness.mjs` | 46 | `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/storage-flush-probe.mjs` | 19 | `/home/volence/sonic_hacks/aurora` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/sweep-fix-harness.mjs` | 18,27,29 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/tile-attribute-harness.mjs` | 126,127 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/tile-editor-harness.mjs` | 25,26,27,28 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/timeline-edit-harness.mjs` | 63,64 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/toast-overflow-harness.mjs` | 62 | `/home/volence/sonic_hacks/aurora` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/tool-keys-harness.mjs` | 28,30 | `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/tool-split-harness.mjs` | 19,20 | `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/variant-families.mjs` | 24,25 | `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | yes (see line) |
| `scratchpad/vsplit-advisory-harness.mjs` | 101,102 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | `AEON_DIR` |
| `scratchpad/warp-tearing-harness.mjs` | 36,37,39 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/oracle-next` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/writer-originated-scene-harness.mjs` | 118 | `/home/volence/sonic_hacks/aurora` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scratchpad/zone-blocks-probe.mjs` | 28,30 | `/home/volence/sonic_hacks/aurora`; `/home/volence/sonic_hacks/s1disasm` | committed instrument: literal naming aurora itself / s1disasm / another sibling (not aeon) | NO for aeon (names another sibling) | none |
| `scripts/check-peer-path-literals.mjs` | 8,50 | `*     … scanned 918 file(s) … for literals naming /home/vole`; `/home/volence/sonic_hacks/s1disasm` | the resolver / gate itself: comments quoting the literal it replaced or forbids | PROSE (comment) | n/a |
| `scripts/verify-s1-roundtrip.mjs` | 9 | `/home/volence/sonic_hacks/` | comment (s1disasm, not aeon) | PROSE (comment) | n/a |
| `src/core/anim/__tests__/sonic-animate.test.ts` | 56 | `/home/volence/sonic_hacks/s1disasm` | comment quoting a historical s1disasm ENOENT (not aeon) | PROSE (comment) | n/a |
| `src/core/level-classic/model.ts` | 16 | `/home/volence/sonic_hacks/programs` | comment citing SonLVL source under `programs/` (not aeon) | PROSE (comment) | n/a |
| `src/core/level-classic/render.ts` | 22 | `/home/volence/sonic_hacks/programs` | comment citing SonLVL source under `programs/` (not aeon) | PROSE (comment) | n/a |
| `src/core/model/screen.ts` | 5 | `/home/volence/sonic_hacks/aeon` | comment citing the aeon constant's source file | PROSE (comment) | n/a |
| `src/renderer/components/classic/composer-shared.tsx` | 20 | `/home/volence/sonic_hacks/programs` | comment citing SonLVL source under `programs/` (not aeon) | PROSE (comment) | n/a |
| `test/fixtures/effects/ojz_act1_depth.provenance.json` | 3 | `/home/volence/sonic_hacks/aeon` | vendored-fixture provenance record: names the aeon path and the `git -C ../aeon show` command it was read with | RECORD | n/a |
| `test/formats/bg-override-binding.test.ts` | 65 | `/home/volence/sonic_hacks/aeon` | comment / doc citing `git -C ../aeon show <rev>:<path>` as the provenance of a vendored fixture | PROSE (comment) | n/a |
| `test/formats/effects-scene-curve-vsplit.test.ts` | 134 | `/home/volence/sonic_hacks/aeon` | comment / doc citing `git -C ../aeon show <rev>:<path>` as the provenance of a vendored fixture | PROSE (comment) | n/a |
| `test/support/fixture-tree.ts` | 54,89,93,256 | `/home/volence/sonic_hacks/`; `/home/volence/sonic_hacks/s1disasm` | the resolver / gate itself: comments quoting the literal it replaced or forbids | PROSE (comment) | n/a |
| `test/support/sibling-root.mjs` | 17,31,100 | `*     … scanned 918 file(s) … for literals naming /home/vole`; `/home/volence/sonic_hacks/s1disasm` | the resolver / gate itself: comments quoting the literal it replaced or forbids | PROSE (comment) | n/a |

### aurora — absolute literals: prose files (55 files, 162 sites) — PROSE, never load-bearing

| file | sites | naming aeon | lines |
|---|---:|---:|---|
| `BUILD-AND-PLAY.md` | 3 | 3 | 12,19,34 |
| `docs/OVERSEER.md` | 3 | 1 | 615,979,1104 |
| `docs/ROADMAP.md` | 1 | 1 | 823 |
| `docs/plans/2026-06-11-art-suite.md` | 1 | 0 | 13 |
| `docs/plans/2026-06-11-mcp-art-generation.md` | 2 | 0 | 11,15 |
| `docs/plans/2026-08-08-chunk-collision-and-map-clipboard.md` | 4 | 2 | 7,33,413,454 |
| `docs/plans/2026-08-09-disasm-project-abstraction.md` | 4 | 0 | 13,22,36,254 |
| `docs/reviews/2026-08-19-classic-playtest-links.md` | 2 | 1 | 9,103 |
| `docs/reviews/2026-08-20-p3-plan-audit.md` | 1 | 0 | 49 |
| `docs/reviews/2026-08-20-s1-animation-audit.md` | 1 | 0 | 15 |
| `docs/reviews/2026-08-20-s1-nonlevel-art-audit.md` | 1 | 0 | 5 |
| `docs/reviews/2026-08-22-non-facet-section-columns.md` | 1 | 0 | 325 |
| `docs/reviews/2026-08-26-effects-feedback-triage.md` | 1 | 1 | 6 |
| `docs/reviews/2026-08-26-effects-foreground-checks-2.md` | 1 | 1 | 17 |
| `docs/reviews/2026-08-26-effects-foreground-checks.md` | 1 | 1 | 5 |
| `docs/reviews/2026-08-27-camera-preview.md` | 1 | 1 | 325 |
| `docs/reviews/2026-08-27-fixture-build-drift.md` | 1 | 1 | 88 |
| `docs/reviews/2026-08-27-guard-surface-gaps.md` | 6 | 2 | 36,43,77,87,89,369 |
| `docs/reviews/2026-08-27-guard-transcription.md` | 4 | 2 | 33,37,65,135 |
| `docs/reviews/2026-08-27-screen-frame-guides.md` | 1 | 1 | 271 |
| `docs/reviews/2026-08-28-golden-live-tree.md` | 4 | 1 | 27,166,181,216 |
| `docs/reviews/2026-08-29-band-preset-panel.md` | 1 | 1 | 265 |
| `docs/reviews/2026-08-29-crossover-paint-loop.md` | 1 | 0 | 4 |
| `docs/reviews/2026-08-29-curve-option-disabled.md` | 1 | 1 | 247 |
| `docs/reviews/2026-08-29-fixture-absent-honesty.md` | 6 | 2 | 23,52,111,165,237,311 |
| `docs/reviews/2026-08-29-harness-hazards.md` | 1 | 0 | 49 |
| `docs/reviews/2026-08-30-incomplete-checkout-rows.md` | 1 | 0 | 8 |
| `docs/reviews/2026-08-30-o31-dangling-bg-refs.md` | 1 | 1 | 8 |
| `docs/reviews/2026-08-30-s1disasm-test-coupling.md` | 6 | 0 | 4,22,154,155,291,339 |
| `docs/reviews/2026-08-30-xvfb-display-leak.md` | 1 | 0 | 272 |
| `docs/specs/2026-08-08-chunk-collision-and-map-clipboard-design.md` | 1 | 0 | 5 |
| `docs/specs/2026-08-09-disasm-project-abstraction-design.md` | 1 | 0 | 51 |
| `docs/superpowers/plans/2026-08-12-ux-overhaul-stage1-foundations.md` | 2 | 0 | 11,22 |
| `docs/superpowers/plans/2026-08-12-ux-overhaul-stage2-shell.md` | 6 | 0 | 35,38,46,51,52,53 |
| `docs/superpowers/plans/2026-08-13-ux-overhaul-stage3-aeon-rehome.md` | 11 | 0 | 12,14,15,17,47,50,59,62,67,68,69 |
| `docs/superpowers/plans/2026-08-13-ux-overhaul-stage4-plan1-history.md` | 5 | 0 | 13,85,1607,1618,1621 |
| `docs/superpowers/plans/2026-08-13-ux-overhaul-stage4-plan2-foundations.md` | 4 | 0 | 13,57,661,665 |
| `docs/superpowers/plans/2026-08-13-ux-overhaul-stage4-plan3-slot-neutrality.md` | 3 | 0 | 13,62,416 |
| `docs/superpowers/plans/2026-08-13-ux-overhaul-stage4-plan5-slot-parity-and-classic-rehome.md` | 26 | 0 | 17,116,125,132,175,305,314,384,440,516,528,566,626,695,728,756,786,817,850,865,900,911,947,960,999,1010 |
| `docs/superpowers/plans/2026-08-14-plan6-handoff.md` | 1 | 0 | 85 |
| `docs/superpowers/plans/2026-08-14-ux-overhaul-stage4-plan6-art-convergence.md` | 2 | 0 | 130,528 |
| `docs/superpowers/plans/2026-08-15-canvas-cdp-report.md` | 1 | 0 | 356 |
| `docs/superpowers/plans/2026-08-17-classic-collision-editing.md` | 1 | 0 | 434 |
| `docs/superpowers/plans/2026-08-17-commit-collision-remediation.md` | 1 | 0 | 196 |
| `docs/superpowers/plans/2026-08-18-art-agent-surface.md` | 2 | 0 | 1136,1146 |
| `docs/superpowers/plans/2026-08-19-collision-paint-gesture.md` | 1 | 0 | 667 |
| `docs/superpowers/plans/2026-08-19-set-block-collision.md` | 2 | 0 | 1854,1956 |
| `scratchpad/2026-08-26-effects-foreground-checks-2.md` | 1 | 1 | 17 |
| `scratchpad/2026-08-26-effects-foreground-checks.md` | 1 | 1 | 5 |
| `scratchpad/_seam_exp.txt` | 9 | 0 | 1,2,3,4,5,6,7,8,9 |
| `scratchpad/_seam_sdk2.txt` | 4 | 0 | 1,2,3,4 |
| `scratchpad/_seam_sdk5.txt` | 3 | 0 | 2,3,4 |
| `scratchpad/_seam_vb2.txt` | 2 | 2 | 24,25 |
| `scratchpad/lens-sweep-2026-08-16/digest-crithigh.txt` | 7 | 2 | 36,191,247,308,325,417,441 |
| `scratchpad/lens-sweep-2026-08-16/digest-index.txt` | 2 | 0 | 162,172 |

### aurora — relative `../aeon` reach: code / data files (28 files, 44 sites)

| file | lines | literal(s) | use | load-bearing? | env-override-aware? |
|---|---|---|---|---|---|
| `.gitignore` | 29 | `../aeon` | comment explaining why a private aeon copy is ignored | PROSE (comment) | n/a |
| `docs/lane-log.jsonl` | 82,104 | `../../../../../../aeon`; `../aeon` | lane-log narrative | RECORD | n/a |
| `scratchpad/bg-roomy-regenerate.sh` | 13,16 | `../aeon` | committed instrument: aeon project/ROM as the default subject (env fallback) | YES — fallback default | yes (see line) |
| `scratchpad/bganim-insert-roomy-harness.mjs` | 46 | `../aeon` | committed instrument: comment naming the live tree | PROSE (comment) | n/a |
| `scratchpad/bganim-marquee-resolution-probe.mjs` | 324 | `../../../../aeon` | committed instrument: aeon project/ROM as a hard-coded subject | YES — hard-coded | none |
| `scratchpad/bganim-phase-shift-harness.mjs` | 31 | `../aeon` | committed instrument: comment naming the live tree | PROSE (comment) | n/a |
| `scratchpad/bganim-promoted-vs-aeon-injector.py` | 17,18 | `../aeon` | usage recipe inside the module docstring (`R=$(git -C ../aeon ls-remote …)`); the script itself takes its inputs as arguments | PROSE (docstring) — corrected on review, was YES | n/a |
| `scratchpad/bganim-promotion-vs-aeon-live.ts` | 15,16 | `../aeon` | committed instrument: comment naming the live tree | PROSE (comment) | n/a |
| `scratchpad/build-console-overlap-harness.mjs` | 55,61,81 | `../../aeon`; `../aeon` | committed instrument: comment naming the live tree | PROSE (comment) | n/a |
| `scratchpad/collision-preservation-harness.mjs` | 64,301 | `../aeon` | 64 is a comment; 301 is a `console.log` string printing a `git -C ../aeon show` hint (the instrument's live-tree default is its grep-A row, `AEON_DIR` fallback at 112) | PROSE (comment / printed string) — corrected on review, was YES | n/a |
| `scratchpad/effects-bob-harness.mjs` | 61,79 | `../aeon` | committed instrument: the literal is the LIVE tree the harness REFUSES to open (guard) | GUARD (refuses the live tree) | none |
| `scratchpad/item14-refusal-probe/probe.py` | 10 | `../aeon` | module docstring recording that the module beside the probe was extracted with `git -C ../aeon show` | PROSE (docstring) — corrected on review, was YES | n/a |
| `scratchpad/loop-paint-harness.mjs` | 11,339 | `../aeon` | 11 is a comment; 339 is a `console.log` string printing a `git -C ../aeon show` hint (the instrument's live-tree default is its grep-A row, `AEON_DIR` fallback at 98) | PROSE (comment / printed string) — corrected on review, was YES | n/a |
| `src/core/collision/crossover-audit.ts` | 4 | `../aeon` | comment / doc citing `git -C ../aeon show <rev>:<path>` as the provenance of a vendored fixture | PROSE (comment) | n/a |
| `src/core/collision/layer-transition.ts` | 7 | `../aeon` | comment / doc citing `git -C ../aeon show <rev>:<path>` as the provenance of a vendored fixture | PROSE (comment) | n/a |
| `src/core/editing/__tests__/bg-override-art-injector-gate.test.ts` | 6,37 | `../aeon` | runs aeon's `tools/inject_editor_bg.py` as the validator: ancestor walk for `../aeon`, `AEON_ROOT` overrides; skips with reason when absent | PROSE (comment) | `AEON_ROOT` |
| `src/core/editing/collision-word.ts` | 66,86 | `../aeon` | comment / doc citing `git -C ../aeon show <rev>:<path>` as the provenance of a vendored fixture | PROSE (comment) | n/a |
| `src/core/formats/bg-override/bganim-consumer-contract.json` | 22 | `../aeon` | vendored-fixture provenance record: names the aeon path and the `git -C ../aeon show` command it was read with | RECORD | n/a |
| `src/core/formats/raster-binding.ts` | 62,216,277,377,480 | `../aeon` | comment / doc citing `git -C ../aeon show <rev>:<path>` as the provenance of a vendored fixture | PROSE (comment) | n/a |
| `src/core/model/__tests__/screen.test.ts` | 20 | `../../aeon` | reads `engine/system/constants.emp` from a sibling `aeon/` found by ancestor walk (no env override); skips with message when absent | PROSE (comment) | none (walk only) |
| `src/core/project/__tests__/art-tiers.test.ts` | 15 | `../aeon` | FALSE POSITIVE: `'../aeon/index'` is aurora's own `src/core/project/aeon/` adapter module | NO (false positive) | none |
| `src/renderer/providers/effects-preset.ts` | 910 | `../aeon` | see line | PROSE (comment) | n/a |
| `test/fixtures/bg-override/editor_bg_override.handover-band.provenance.json` | 8 | `../aeon` | vendored-fixture provenance record: names the aeon path and the `git -C ../aeon show` command it was read with | RECORD | n/a |
| `test/fixtures/effects/ojz_act1_depth.provenance.json` | 11 | `../aeon` | vendored-fixture provenance record: names the aeon path and the `git -C ../aeon show` command it was read with | RECORD | n/a |
| `test/formats/aeon-json-trailing-newline.test.ts` | 238 | `../../../../../../aeon` | reads two aeon sidecars via `referenceFile('aeon', …)` → `AURORA_PEER_ROOT` / `AURORA_AEON_REPO`; the literal is the comment recording the old six-level hop | PROSE (comment) | `AURORA_PEER_ROOT` / `AURORA_AEON_REPO` |
| `test/formats/bg-override-contract-drift.test.ts` | 59 | `../aeon` | comment / doc citing `git -C ../aeon show <rev>:<path>` as the provenance of a vendored fixture | PROSE (comment) | n/a |
| `test/support/fixture-tree.ts` | 6,63 | `../../../../../../aeon`; `../aeon` | the resolver / gate itself: comments quoting the literal it replaced or forbids | PROSE (comment) | n/a |
| `test/support/peer-repo.ts` | 4 | `../aeon` | the resolver / gate itself: comments quoting the literal it replaced or forbids | PROSE (comment) | n/a |

### aurora — relative `../aeon` reach: prose files (17 files, 32 sites) — PROSE, never load-bearing

| file | sites | naming aeon | lines |
|---|---:|---:|---|
| `docs/OVERSEER.md` | 3 | 3 | 860,890,892 |
| `docs/ROADMAP.md` | 1 | 1 | 829 |
| `docs/reviews/2026-08-22-handoff-cutover.md` | 1 | 1 | 69 |
| `docs/reviews/2026-08-26-bg-capability-survey-s1-s2-s3k.md` | 1 | 1 | 49 |
| `docs/reviews/2026-08-27-build-console-overlap.md` | 1 | 1 | 116 |
| `docs/reviews/2026-08-27-curve-vsplit-reachable.md` | 3 | 3 | 85,98,547 |
| `docs/reviews/2026-08-27-guard-surface-gaps.md` | 3 | 3 | 87,100,447 |
| `docs/reviews/2026-08-27-guard-transcription.md` | 2 | 2 | 33,48 |
| `docs/reviews/2026-08-27-screen-frame-guides.md` | 1 | 1 | 250 |
| `docs/reviews/2026-08-28-collision-word-preservation.md` | 1 | 1 | 47 |
| `docs/reviews/2026-08-28-golden-live-tree.md` | 5 | 5 | 34,42,76,95,150 |
| `docs/reviews/2026-08-28-marquee-flip.md` | 1 | 1 | 150 |
| `docs/reviews/2026-08-29-drift-codec.md` | 1 | 1 | 350 |
| `docs/reviews/2026-08-29-fixture-absent-honesty.md` | 3 | 3 | 6,24,159 |
| `docs/reviews/2026-08-29-loop-paint.md` | 2 | 2 | 7,32 |
| `docs/reviews/2026-08-30-o21-bg-wrap-visibility.md` | 2 | 2 | 204,230 |
| `docs/superpowers/plans/2026-08-13-ux-overhaul-stage4-plan2-foundations.md` | 1 | 1 | 263 |

## 6. seraph — HEAD `e149a22` (main), tree DIRTY (2 paths)

Absolute grep A: **12 files / 96 sites** (4 code files / 4 sites; 8 prose files / 92 sites); 8 sites in 1 files name aeon; **load-bearing: 0 sites in 0 files**. Relative grep B: 0 files / 0 sites; load-bearing 0 sites in 0 files.

**Shape.** No committed seraph file names aeon in code. The four executable hits are suite-layout
consumers of OTHER siblings: `.mcp.json` runs the legacy Exodus MCP script under the suite root, and
three instrument-library `_game.json` files record their source ROM / disassembly under it. The eight
aeon mentions are all in one plan document.

### seraph — absolute literals: code / data files (4 files, 4 sites)

| file | lines | literal(s) | use | load-bearing? | env-override-aware? |
|---|---|---|---|---|---|
| `.mcp.json` | 5 | `/home/volence/sonic_hacks/Exodus` | MCP server command: the legacy Exodus MCP script under the suite root (not aeon) | RECORD | n/a |
| `library/batman-robin/_game.json` | 1 | `/home/volence/sonic_hacks/The` | instrument library `_game.json` source path: reference disassembly / ROM under the suite root (not aeon) | RECORD | n/a |
| `library/sonic2/_game.json` | 1 | `/home/volence/sonic_hacks/s2disasm` | instrument library `_game.json` source path: reference disassembly / ROM under the suite root (not aeon) | RECORD | n/a |
| `library/sonic3k/_game.json` | 1 | `/home/volence/sonic_hacks/skdisasm` | instrument library `_game.json` source path: reference disassembly / ROM under the suite root (not aeon) | RECORD | n/a |

### seraph — absolute literals: prose files (8 files, 92 sites) — PROSE, never load-bearing

| file | sites | naming aeon | lines |
|---|---:|---:|---|
| `docs/superpowers/2026-07-03-seraph-banking-queue.md` | 5 | 0 | 2112,2177,2757,2758,2767 |
| `docs/superpowers/plans/2026-05-01-megadaw-phase4-sequencer.md` | 26 | 0 | 200,612,618,647,1180,1186,1444,1796,1802,1991,1997,2356,2362,3114,3144,3150,3508,3514,4093,4099,4236,4242,4254,4259,4264,4288 |
| `docs/superpowers/plans/2026-05-02-megadaw-phase6-import.md` | 30 | 0 | 93,99,184,308,314,502,508,596,597,598,603,690,696,880,903,909,983,989,1067,1073,1122,1128,1166,1172,1309,1315,1392,1398,1405,1410 |
| `docs/superpowers/plans/2026-06-18-seraph-theme-adoption.md` | 1 | 0 | 11 |
| `docs/superpowers/plans/2026-07-03-s0-memra-contract.md` | 18 | 8 | 25,31,41,143,704,705,706,775,798,799,807,921,964,977,978,988,1004,1007 |
| `docs/superpowers/plans/2026-07-03-s1-native-model-compiler.md` | 1 | 0 | 3 |
| `docs/superpowers/plans/2026-07-16-instrument-library.md` | 10 | 0 | 11,18,40,1221,1324,1329,1330,1332,1345,1678 |
| `docs/superpowers/specs/2026-06-18-seraph-theme-adoption-design.md` | 1 | 0 | 9 |

### seraph — relative `../aeon` reach: no matches (grep exit 1)

## 7. empyrean — HEAD `5dfd6c5` (main), tree clean

Absolute grep A: **39 files / 396 sites** (0 code files / 0 sites; 39 prose files / 396 sites); 42 sites in 20 files name aeon; **load-bearing: 0 sites in 0 files**. Relative grep B: 8 files / 11 sites; load-bearing 0 sites in 0 files.

**Shape.** Prose only: 39 files / 396 sites, all `.md` (hub logs, plans, OVERSEER). 42 of those
sites name aeon. The 27 `AEON_DIR` spellings are the hub's own prose describing sigil's contract
(`contract/projects.json` carries it inside a note string, not as a field). The relative hits are the
wiki's own `<a href="../aeon/section-…html">` page links (5, false positives) and lane-log narrative.

### empyrean — absolute literals: prose files (39 files, 396 sites) — PROSE, never load-bearing

| file | sites | naming aeon | lines |
|---|---:|---:|---|
| `CLAUDE.md` | 8 | 1 | 35,37,38,39,40,41,44,240 |
| `contract/protocol.md` | 1 | 0 | 2171 |
| `docs/2026-08-22-empyrean-status-audit.md` | 6 | 1 | 41,73,75,82,86,143 |
| `docs/EMULATION_CORE_MODERNIZATION.md` | 2 | 0 | 18,272 |
| `docs/OVERSEER.md` | 7 | 1 | 2723,3481,5120,5790,6159,6422,6439 |
| `docs/ROADMAP.md` | 1 | 0 | 249 |
| `docs/SIGIL_CORE_SPEC.md` | 3 | 3 | 3,27,39 |
| `docs/SIGIL_M0_CATALOG.md` | 1 | 1 | 3 |
| `docs/SIGIL_ORACLE_ISA_SHARING.md` | 3 | 0 | 20,25,26 |
| `docs/handoffs/README.md` | 1 | 0 | 18 |
| `docs/handoffs/aeon.md` | 1 | 1 | 11 |
| `docs/handoffs/aurora.md` | 1 | 0 | 9 |
| `docs/handoffs/oracle.md` | 1 | 0 | 9 |
| `docs/handoffs/seraph.md` | 1 | 0 | 9 |
| `docs/plans/2026-07-01-sigil-core-foundation.md` | 115 | 0 | 26,59,60,61,62,63,64,65,66,67,68,69,70,74,81,84,86,100,106,117,133,144,158,170,184,198,212,230,251,259,267,275,276,277,278,282,293,300,352,449,452,484,532,542,543,547,681,798,806,807,808,810,812,824,852,926,931,958,977,982,1001,1137,1145,1146,1147,1153,1165,1199,1204,1269,1277,1280,1310,1315,1455,1463,1471,1472,1473,1477,1493,1563,1680,1737,1745,1746,1747,1751,1769,1777,1838,1925,1933,1934,1938,2228,2255,2276,2285,2294,2302,2320,2326,2334,2340,2341,2347,2353,2354,2362,2376,2377,2380,2391,2396 |
| `docs/plans/2026-07-01-sigil-m0-p2-z80-encoder.md` | 173 | 10 | 69,211,237,672,678,724,755,1069,1112,1128,1144,1145,1201,1217,1226,1291,1366,1367,1382,1433,1628,1629,1638,1662,1699,1783,1790,1791,1800,1910,2058,2059,2104,2163,2282,2288,2348,2389,2390,2476,2477,2566,2567,2721,2722,2830,2831,2906,2907,2944,2979,2980,3046,3109,3153,3184,3185,3245,3246,3305,3306,3359,3360,3414,3415,3473,3474,3529,3530,3577,3578,3631,3632,3684,3685,3749,3750,3788,3789,3815,3816,3847,3872,3945,4066,4067,4157,4158,4243,4244,4301,4302,4351,4426,4502,4548,4549,4654,4655,4721,4722,4796,4797,4871,4872,5001,5018,5051,5067,5140,5153,5154,5193,5214,5225,5226,5264,5284,5295,5296,5325,5345,5356,5357,5391,5415,5426,5427,5472,5500,5511,5512,5571,5620,5632,5633,5654,5678,5689,5690,5719,5741,5752,5753,5814,5826,5836,5837,5893,5908,5958,6095,6120,6162,6179,6194,6195,6204,6231,6253,6271,6286,6301,6302,6348,6394,6398,6415,6538,6584,6619,6635,6636 |
| `docs/plans/2026-07-02-sigil-spec2-p1-emp-parser.md` | 2 | 0 | 36,2644 |
| `docs/research/2026-08-29-painted-regions-study/A-engine-architect.md` | 1 | 1 | 3 |
| `docs/research/2026-08-29-painted-regions-study/B-adversary.md` | 1 | 1 | 6 |
| `docs/research/2026-08-29-painted-regions-study/D-precedent-backgrounds.md` | 2 | 0 | 8,9 |
| `docs/research/2026-08-29-painted-regions-study/E-effects-feature-audit.md` | 1 | 0 | 162 |
| `docs/superpowers/plans/2026-07-23-visual-identity-p1-contract-and-chrome.md` | 1 | 0 | 15 |
| `docs/superpowers/plans/2026-08-20-scribe-v1.md` | 23 | 8 | 20,21,200,726,748,756,757,819,902,952,982,990,992,993,995,1001,1512,1516,1526,1560,1563,1571,1576 |
| `wiki/EMP.md` | 1 | 1 | 42 |
| `wiki/REFERENCES.md` | 1 | 0 | 387 |
| `wiki/lenses/README.md` | 1 | 0 | 42 |
| `wiki/specs/2026-07-22-numbers-and-notation-plan.md` | 10 | 2 | 38,57,58,92,147,418,437,514,529,570 |
| `wiki/specs/2026-07-22-z80-programming-model-plan.md` | 6 | 2 | 46,62,63,70,148,366 |
| `wiki/specs/2026-07-25-base-pairing-plan.md` | 1 | 0 | 96 |
| `wiki/specs/2026-07-25-m68k-flow-plan.md` | 1 | 0 | 61 |
| `wiki/specs/2026-07-26-m68k-system.md` | 1 | 0 | 706 |
| `wiki/specs/2026-08-06-genesis-dma-frame-factsheet.md` | 2 | 1 | 38,39 |
| `wiki/specs/2026-08-06-genesis-system-factsheet.md` | 2 | 1 | 53,54 |
| `wiki/specs/2026-08-06-genesis-vdp-planes-factsheet.md` | 6 | 3 | 48,49,50,762,763,791 |
| `wiki/specs/2026-08-20-cold-read-plan.md` | 3 | 0 | 15,874,1081 |
| `wiki/specs/sweep-workpapers/triage-aeon-section-0-boot.md` | 1 | 1 | 34 |
| `wiki/specs/sweep-workpapers/triage-aeon-vdp-frame.md` | 1 | 1 | 23 |
| `wiki/specs/sweep-workpapers/triage-lens-a-timing.md` | 1 | 1 | 8 |
| `wiki/specs/sweep-workpapers/triage-vdp-frame-s9.md` | 2 | 1 | 6,152 |

### empyrean — relative `../aeon` reach: code / data files (5 files, 6 sites)

| file | lines | literal(s) | use | load-bearing? | env-override-aware? |
|---|---|---|---|---|---|
| `docs/lane-log.jsonl` | 41 | `../aeon` | lane-log narrative | RECORD | n/a |
| `wiki/basics/numbers-and-notation.html` | 860 | `../aeon` | FALSE POSITIVE: wiki-internal `<a href="../aeon/…html">` page link | NO (false positive) | none |
| `wiki/emp/reading-emp.html` | 857,858 | `../aeon` | FALSE POSITIVE: wiki-internal `<a href="../aeon/…html">` page link | NO (false positive) | none |
| `wiki/m68k/moving-data.html` | 1355 | `../aeon` | FALSE POSITIVE: wiki-internal `<a href="../aeon/…html">` page link | NO (false positive) | none |
| `wiki/m68k/programming-model.html` | 1390 | `../aeon` | FALSE POSITIVE: wiki-internal `<a href="../aeon/…html">` page link | NO (false positive) | none |

### empyrean — relative `../aeon` reach: prose files (3 files, 5 sites) — PROSE, never load-bearing

| file | sites | naming aeon | lines |
|---|---:|---:|---|
| `docs/OVERSEER.md` | 1 | 1 | 4245 |
| `docs/plans/2026-07-03-sigil-m0-p5-integration-harness-design.md` | 1 | 1 | 165 |
| `docs/plans/2026-07-03-sigil-m0-p5-integration-harness.md` | 3 | 3 | 335,634,835 |

## 8. oracle-old — HEAD `58b6f81` (main), tree clean

Absolute grep A: **21 files / 80 sites** (12 code files / 22 sites; 9 prose files / 58 sites); 12 sites in 10 files name aeon; **load-bearing: 10 sites in 8 files**. Relative grep B: 0 files / 0 sites; load-bearing 0 sites in 0 files.

**Shape.** The legacy harness (`linux-port/harness/`) is the one cluster with NO override of any
kind: eight test scripts set `ROM = "/home/volence/sonic_hacks/aeon/s4.bin"` (or `s4.debug.bin`) and two
also `LST = ".../s4.lst"` as module constants, two scene fixtures point `symbols` at `aeon/s4.lst`, and
every script `sys.path.insert`s `empyrean/clients/python`. `oracle-old` is reference-only per
`CLAUDE.md`, but sigil's `m1b_gate.rs:51` still resolves it (`ORACLE_DIR` → literal) and the memory
note "ab_runner IS the gate harness" names its `ab_runner.py`.

### oracle-old — absolute literals: code / data files (12 files, 22 sites)

| file | lines | literal(s) | use | load-bearing? | env-override-aware? |
|---|---|---|---|---|---|
| `linux-port/harness/ab_runner.py` | 88 | `/home/volence/sonic_hacks/empyrean` | `sys.path.insert` of empyrean's Python Aether client (import) | NO for aeon (names another sibling) | none |
| `linux-port/harness/breakpoint_regression_test.py` | 27,32 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/empyrean` | legacy harness test: `ROM =`/`LST =` module constants naming built aeon artifacts; empyrean client import | YES — hard-coded | none |
| `linux-port/harness/det_mode_note_test.py` | 21,26 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/empyrean` | legacy harness test: `ROM =`/`LST =` module constants naming built aeon artifacts; empyrean client import | YES — hard-coded | none |
| `linux-port/harness/determinism_gate.py` | 22,28 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/empyrean` | legacy harness test: `ROM =`/`LST =` module constants naming built aeon artifacts; empyrean client import | YES — hard-coded | none |
| `linux-port/harness/memory_hash_test.py` | 27,32,33 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/empyrean` | legacy harness test: `ROM =`/`LST =` module constants naming built aeon artifacts; empyrean client import | YES — hard-coded | none |
| `linux-port/harness/memory_read_test.py` | 37,42,43 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/empyrean` | legacy harness test: `ROM =`/`LST =` module constants naming built aeon artifacts; empyrean client import | YES — hard-coded | none |
| `linux-port/harness/press_determinism_test.py` | 19,24 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/empyrean` | legacy harness test: `ROM =`/`LST =` module constants naming built aeon artifacts; empyrean client import | YES — hard-coded | none |
| `linux-port/harness/reset_press_input_test.py` | 27,32 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/empyrean` | legacy harness test: `ROM =`/`LST =` module constants naming built aeon artifacts; empyrean client import | YES — hard-coded | none |
| `linux-port/harness/scenes/diff_probe.json` | 3 | `/home/volence/sonic_hacks/aeon` | scene fixture: `symbols` points at aeon `s4.lst` | RECORD | n/a |
| `linux-port/harness/scenes/example_ab.json` | 3 | `/home/volence/sonic_hacks/aeon` | scene fixture: `symbols` points at aeon `s4.lst` | RECORD | n/a |
| `linux-port/harness/screenshot_path_test.py` | 26,31 | `/home/volence/sonic_hacks/aeon`; `/home/volence/sonic_hacks/empyrean` | legacy harness test: `ROM =`/`LST =` module constants naming built aeon artifacts; empyrean client import | YES — hard-coded | none |
| `linux-port/mcp/mcp.json.sample` | 4 | `/home/volence/sonic_hacks/oracle` | sample MCP config naming the oracle checkout (not aeon) | NO for aeon (names another sibling) | none |

### oracle-old — absolute literals: prose files (9 files, 58 sites) — PROSE, never load-bearing

| file | sites | naming aeon | lines |
|---|---:|---:|---|
| `docs/superpowers/plans/2026-04-23-m68k-profiler.md` | 9 | 0 | 158,318,420,497,646,867,968,1017,1034 |
| `docs/superpowers/plans/2026-05-03-vgm-logging.md` | 7 | 0 | 258,351,420,486,677,741,819 |
| `docs/superpowers/plans/2026-06-18-regression-harness.md` | 9 | 0 | 120,141,145,260,368,369,390,510,602 |
| `docs/superpowers/plans/2026-06-19-audio-mixer-consolidation.md` | 7 | 0 | 15,21,101,201,269,329,447 |
| `docs/superpowers/plans/2026-06-19-audio-spectrum.md` | 8 | 0 | 15,21,38,154,318,437,449,639 |
| `docs/superpowers/plans/2026-06-19-channel-keyboard.md` | 7 | 0 | 15,21,38,135,231,370,471 |
| `docs/superpowers/plans/2026-06-19-spectrum-analyzer.md` | 3 | 0 | 15,21,250 |
| `docs/superpowers/plans/2026-06-20-agent-input-control.md` | 6 | 0 | 15,21,221,417,418,452 |
| `linux-port/mcp/README.md` | 2 | 0 | 50,109 |

### oracle-old — relative `../aeon` reach: no matches (grep exit 1)

## 9. Identifier-routed consumers the literal grep cannot see (command D)

| repo | mechanism | sites / files | what they read | override |
|---|---|---:|---|---|
| sigil | `sigil_harness::test_support::aeon_dir()` → `LIVE_TREE_FALLBACK` | 261 / 67 | aeon SOURCE (`.emp`, `map.toml`, generated sound) for every reference-dependent gate; writes refuse without `AEON_DIR` | `AEON_DIR` |
| sigil | `scripts/landing-run.sh` exports `AEON_DIR` to everything it spawns | 1 wrapper | the whole landing run | `--aeon` / `AEON_ARG` / `AEON_DIR` |
| oracle | `rom_source::live_aeon(..)` / `LIVE_AEON_DIR` | 4 / 3 (`diag_soundqueue.rs:97`, `synth_render.rs:38`, `k4_openbus_probe.rs:331,332`) | `s4.soundtest.bin`, `demo.bin` (unfrozen) | CLI path only |
| aurora | `peerRepo('aeon')` (git plumbing, at a revision) | 7 / 6 (`layer-transition.test.ts:201,247`, `collision-word.test.ts:113`, `aeon-fixture-currency.test.ts:78`, `bg-override-binding.test.ts:78`, `effects-preset-schema-drift.test.ts:203`, `vsplit-two-writer-currency.test.ts:77`) | committed blobs of aeon data/tools, never the working tree | `AURORA_PEER_ROOT` / `AURORA_AEON_REPO` |
| aurora | `referenceFile('aeon', …)` (filesystem, working tree) | 3 / 2 (`aeon-json-trailing-newline.test.ts:243,244`, `handover/ojz-sec5-showcase.test.ts:296`) | `section_4.meta.json`, `editor_bg_override.json`, the handover tree | same, plus `AURORA_AEON_REV` for the revision |
| aurora | ancestor walk for `aeon/` | 2 / 2 (`screen.test.ts`, `bg-override-art-injector-gate.test.ts`) | `engine/system/constants.emp`; `tools/inject_editor_bg.py` executed | none; `AEON_ROOT` |

## 10. Env-var spellings peers already use to point at aeon (command C, plus reading)

| spelling | repo(s) | files | meaning | default when unset |
|---|---|---:|---|---|
| `AEON_DIR` | sigil, aurora (scratchpad + 1 handover script), empyrean (prose) | sigil 100 by command C (145 naming it anywhere outside prose; the "124" first printed here reproduced under no rule) / aurora 60 (command C) | the aeon CHECKOUT | the home literal (sigil, aurora); sigil CI pins `/nonexistent/aeon-not-checked-out-in-ci` so its skips are honest |
| `AEON_ARG` | sigil `scripts/landing-run.sh` | 1 | `--aeon <path>` CLI form of `AEON_DIR` | falls through to `AEON_DIR` |
| `AEON_REPO` | sigil `scripts/provision-aeon-ref.sh`, `nightly_ref_drift.sh` | 2 | the aeon checkout to provision a pinned worktree FROM | `$SIGIL_ROOT/../aeon` (relative) |
| `ORACLE_AEON_DIR` | oracle (`symbols_real_lst.rs`, `replay_real_artifacts.rs`, `aeon_pin.rs`) | 3 | a directory of aeon BUILD ARTIFACTS | oracle's frozen `fixtures/aeon/` (never the live tree) |
| `AEON_ROOT` | aurora `bg-override-art-injector-gate.test.ts` | 1 | the aeon checkout | ancestor walk for `../aeon` |
| `AURORA_PEER_ROOT` | aurora resolver (`sibling-root.mjs`) | 1 (all `src`/`test`/`scripts` consumers) | the SUITE ROOT (parent of all checkouts) | `dirname(dirname(git --git-common-dir))` |
| `AURORA_AEON_REPO` | aurora resolver (`AURORA_<NAME>_REPO`) | 1 | the aeon checkout, per-peer override | `$AURORA_PEER_ROOT/aeon` |
| `AURORA_AEON_REV` | aurora `ojz-sec5-showcase.test.ts` | 1 | a REVISION of aeon, not a path | the handover base SHA |
| `LIVE_AEON` | aurora `band-art-foreground-harness.mjs`, `bganim-tile-door-harness.mjs` | 2 | the aeon checkout (read-only subject) | the home literal |
| `TOOLS` | oracle `tools/blastem-differential/build_*.sh` | 3 | aeon's `tools/` directory | `$HERE/../../../aeon/tools` (relative) |
| `PROFILE_LST` | sigil `golden/ab/**/*.py` | 6 of 8 | a listing FILE (`s4.debug.lst`) | the home literal |
| `ORACLE_DIR` | sigil `m1b_gate.rs` | 1 | the oracle-old checkout (not aeon, but the same class) | the home literal |
| `AEON` (bare) — added on review | aurora `scratchpad/bg-roomy-regenerate.sh:16` | 1 | the aeon checkout (`git archive`d at a SHA, never opened live) | `$HERE/../aeon` (relative) |
| `AEON_SUITE_ROOT` | **aeon only** (`tools/suite_paths.py`) | 0 outside aeon | the SUITE ROOT | marker walk from the file's own location |

Shell-local names that look like env vars but are not (`AEON_MAIN`, `AEON_GATES`, `DRIFT_AEON_TREE`,
`AEON_SHA`, `AEON_REV`, `AEON_TIP`) are assignments inside sigil's nightly scripts and aurora's harnesses;
they were read and excluded. `AEONDIR` (19 aurora sites) is a JS local, not an env name.

## 11. Recommendation for the hub (recommendation only — no edit was made anywhere)

**Two levels exist and they should stay two levels.** Every peer that names aeon means one of two
things: *the aeon checkout* (sigil `AEON_DIR`/`AEON_ARG`/`AEON_REPO`, aurora `AEON_DIR`/`AEON_ROOT`/`LIVE_AEON`/
`AURORA_AEON_REPO`/bare `AEON`) or *the suite root that all checkouts hang off* (aurora `AURORA_PEER_ROOT`, aeon
`AEON_SUITE_ROOT`). Collapsing them loses the case aurora's resolver already handles — a peer relocated
individually — and the case aeon's handles — a whole suite moved or a poison tree.

1. **Standardise the checkout-level spelling on `AEON_DIR`.** It is the de-facto contract already:
   100 sigil files (by command C), 60 aurora files, sigil's CI (which pins it to a nonexistent path so absence is
   honest), and the landing wrapper. The sites that would need to change to meet it are the ones that
   spell the same thing differently — aurora `AEON_ROOT` (1 test) and `LIVE_AEON` (2 instruments) — and
   aurora's resolver, which should treat `AEON_DIR` as an alias of `AURORA_AEON_REPO` (one line in
   `sibling-root.mjs`'s `siblingPath`). Oracle's `ORACLE_AEON_DIR` names a different thing (a directory
   of ARTIFACTS, defaulting to a frozen copy) and should keep its name.

2. **Standardise the suite-root spelling — one name, honoured by every resolver as the default
   `AEON_DIR` derives from.** Two candidates exist: aeon's `AEON_SUITE_ROOT` (implemented, gated by
   `tools/test_no_baked_home_paths.py`, a wrong value is a hard error) and aurora's `AURORA_PEER_ROOT`
   (implemented, a wrong value yields null rather than a fallback). Both are repo-branded names for a
   suite-level fact. The hub's call; the enumeration's only input is that **whichever name wins, the
   precedence every resolver should implement is: explicit checkout var > suite-root var > derived
   (git common-dir / marker walk) > REFUSE by name — never a home literal.** If the hub picks a neutral
   name (e.g. `EMPYREAN_ROOT`), aeon's `suite_paths.py` and aurora's `sibling-root.mjs` each need a
   one-line alias; if it picks `AEON_SUITE_ROOT`, only aurora does.

3. **The sites that need the suite-root variable to exist before their home literal can go**, in
   the order the load-bearing count ranks them:
   * sigil `test_support.rs:601 LIVE_TREE_FALLBACK` → derive from suite root, keep the announce;
   * the 99 `sigil-cli/tests/*.rs` private copies → route through `test_support::aeon_dir()` (one
     mechanism instead of two; sigil's own `reference_tree_named_write.rs` already treats the harness
     constant as the single source);
   * sigil `nightly_source_gates.sh:31-34`, `nightly_ref_drift.sh:37-47`, `drift-nightly.conf:34,47` →
     the ONLY sites with no override at all that a timer actually runs; derive the four paths from one
     `SUITE=` line;
   * sigil `landing-run.sh:207`, `capture_goldens.sh:75`, `derive_offcanonical_sizes.sh:25` → same
     one-line change, already refuse by name;
   * oracle `rom_source.rs:44 LIVE_AEON_DIR` → derive; the announce stays;
   * oracle `blastem-differential/build_*.sh` `TOOLS` default → derive;
   * oracle-old `linux-port/harness/*.py` (8 files) → only if that harness is still meant to run;
     otherwise record it as legacy and leave it;
   * aurora `scratchpad/` (72 instruments) → extend `check-peer-path-literals.mjs` to cover
     `scratchpad/` once the instruments read `AEON_DIR` through `sibling-root.mjs`; the 7 GUARD sites
     must keep a way to name the live tree they refuse (compare against the resolved default, not the
     literal);
   * aurora `screen.test.ts` walk → `referenceFile('aeon', …)` like its neighbours.

4. **The sigil A/B scripts' `sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")`
   (18 files) and oracle-old's (9 files) are the same defect pointed at empyrean**, and belong to the hub's
   list even though they are not aeon consumers.

**RULED 2026-09-02: `contract/SUITE_PATHS.md` (empyrean `4e8e865b`).** `AEON_DIR` for the checkout,
`EMPYREAN_SUITE_ROOT` (neither candidate) for the suite root, the precedence above verbatim, set-but-wrong a
hard error; aeon's one-line alias landed in `tools/suite_paths.py` (`AEON_SUITE_ROOT` transitional, announced).

**What this document does not claim.** It did not run any sibling's tests, so *load-bearing* is a
static reading of the line, not an observed failure. It did not enumerate uncommitted or gitignored
state. It counted what the greps returned at the HEADs named in §0; oracle and seraph were dirty at
enumeration time (1 and 2 paths), and the committed content is what was read.


## Reviewed 2026-09-02 (re-derived at the pinned revisions, read-only)

Clock at review: `date` → Tue 2026-09-01 23:40 EDT. Every command below ran as
`git -C /home/volence/sonic_hacks/<repo> grep … <sha> -- .` / `git show <sha>:<path>` against the §0
SHAs (all six reachable), never against a sibling working tree (sigil's HEAD is still `036800fd`;
oracle, aurora, empyrean and oracle-old have moved on — `2fd5bb0`, `4f125cfe`, `63c85ae`, `1eb09a9` — so
the pins are what was measured). Nothing was run inside a sibling.

**Grep totals, doc vs re-derived** (files / sites; the command is §1's, with the SHA inserted):

| repo | A doc | A re-derived | B doc | B re-derived | naming aeon doc | re-derived | `AEON_SUITE_ROOT` (`grep -n -I -F`) |
|---|---:|---:|---:|---:|---:|---:|---:|
| sigil | 197 / 359 | 197 / 359 | 5 / 6 | 5 / 6 | 238 | 238 (A 232 in 150 + B 6) | 0, exit 1 |
| oracle | 51 / 113 | 51 / 113 | 14 / 20 | 14 / 20 | 44 | 44 (A 24 in 16 + B 20) | 0, exit 1 |
| aurora | 227 / 490 | 227 / 490 | 45 / 76 | 45 / 76 | 203 | 203 (A 127 in 112 + B 76) | 0, exit 1 |
| seraph | 12 / 96 | 12 / 96 | 0 (exit 1) | 0 (exit 1) | 8 | 8 | 0, exit 1 |
| empyrean | 39 / 396 | 39 / 396 | 8 / 11 | 8 / 11 | 53 | 53 (A 42 in 20 + B 11) | 0, exit 1 |
| oracle-old | 21 / 80 | 21 / 80 | 0 (exit 1) | 0 (exit 1) | 12 | 12 | 0, exit 1 |
| **total** | 619 / 1647 | **619 / 1647** | | | 558 | **558** | **0** |

The code/prose splits in every §3–§8 header re-derived exactly (prose = `.md`/`.txt` path), and every
line number in every code-table row matched the pinned grep (zero mismatches across the six repos).

**Command C could not be re-run as written** — §1 prints it with a literal `|...)` in the alternation.
Re-run with the four printed alternatives and the tail dropped: sigil 135 sites (`AEON_DIR` 127 sites /
100 files), oracle 4 (`ORACLE_AEON_DIR`), aurora 126 (`AEON_DIR` 57 sites / 60 files), seraph, empyrean
and oracle-old exit 1. §1's "C exited 1 on seraph and oracle-old" is therefore under-stated by empyrean
for the reconstructed form; whether the elided tail changes that is unknowable from the text.

**Command D** re-derived exactly: sigil `\baeon_dir\(\)` in `crates` → 261 sites / 67 files; oracle
`LIVE_AEON_DIR|live_aeon\(` → the constant, the helper, and 4 consumer sites in 3 examples; aurora
resolver calls → 10 sites / 8 files (§9's 7/6 + 3/2).

**Headline claims.** (1) `sigil/crates/sigil-harness/src/test_support.rs:601` at `036800fd` is
`pub const LIVE_TREE_FALLBACK: &str = "/home/volence/sonic_hacks/aeon";` — holds. The "99
`sigil-cli/tests/*.rs` (86 executable, 13 header-comment only)" holds as grep A's 98 (85 + 13) plus
`subcommands.rs:13` from grep B. (2) `scripts/nightly_source_gates.sh:31-34` at `036800fd` assigns
`SIGIL_MAIN`, `AEON_MAIN=/home/volence/sonic_hacks/aeon`, `SIGIL_GATES`, `AEON_GATES` with no
`${…:-}` form anywhere; `AEON_MAIN` is consumed at 369/380/392 (`git -C "$AEON_MAIN" worktree add
--detach …`). `systemctl --user is-enabled sigil-source-gates.timer` → `enabled` (exit 0); `is-active` →
`active`; `list-timers --all`: last `Tue 2026-09-01 05:17:31 EDT`, next `Wed 2026-09-02 05:17 EDT`;
`ExecStart=/home/volence/sonic_hacks/sigil/scripts/nightly_source_gates.sh`. `is-enabled
sigil-ref-drift.timer` → `not-found` (exit 4). Holds. (3) `scripts/landing-run.sh:207` at `036800fd` is
`AEON=$(abspath "${AEON_ARG:-${AEON_DIR:-/home/volence/sonic_hacks/aeon}}")` followed by the
refuse-by-name checks at 208–210 — holds.

**Verdict sampling** (each site read at the pinned SHA and classified by what the line DOES): 22
load-bearing rows (sigil 8, aurora 9, oracle 3, oracle-old 2) and 9 non-load-bearing rows (sigil
`math_port.rs:75` PROSE, `provenance.toml` RECORD, `drift-nightly.conf:34,47` NO-for-aeon; oracle
`vgm_capture.rs:13` PROSE, `artifacts.rs:255` NO; aurora `screen.test.ts:20` PROSE,
`art-tiers.test.ts:15` false positive, `bg-override-art-injector-gate.test.ts:6,37` PROSE; seraph
`.mcp.json:5` RECORD). All 9 non-load-bearing verdicts hold. **6 of the 22 YES rows were wrong**, all
corrected in place above and each marked "corrected on review":

* aurora A `scratchpad/crossover-paint-harness.mjs:43` — `LIVE_AEON` is used only at line 51, a
  `===` compare that throws; the subject is `.aurora-crossover-paint`. YES → GUARD.
* aurora B `scratchpad/loop-paint-harness.mjs:11,339` — 11 comment, 339 `console.log` string. YES → PROSE.
* aurora B `scratchpad/collision-preservation-harness.mjs:64,301` — same shape. YES → PROSE.
* aurora B `scratchpad/bganim-promoted-vs-aeon-injector.py:17,18` — inside the module docstring. YES → PROSE.
* aurora B `scratchpad/item14-refusal-probe/probe.py:10` — inside the module docstring. YES → PROSE.
* oracle B `tools/aether_smoke.py:14` — inside the module docstring (the doc's own "use" column said
  so; the verdict column said YES). YES → PROSE.

Plus one sub-verdict: sigil B `crates/sigil-cli/tests/subcommands.rs:13` is
`concat!(env!("CARGO_MANIFEST_DIR"), "/../../../aeon")` — hard-coded relative to the crate, no
`AEON_DIR` read; it was printed "fallback default" with a copy-pasted use-text. Still load-bearing.

**Load-bearing totals, doc vs corrected** (re-derived by the doc's own rule — executable aeon-naming
lines in files ruled YES, files counted once per grep — over the corrected verdict tables):

| repo | doc sites (files) | corrected sites (files) |
|---|---:|---:|
| sigil | 128 (108) | 128 (108) — A 126 in 106, B 2 in 2 |
| oracle | 5 (5) | **4 (4)** — A 1 in 1, B 3 in 3 |
| aurora | 82 (79) | **76 (74)** — A 74 in 72, B 2 in 2 |
| seraph | 0 (0) | 0 (0) |
| empyrean | 0 (0) | 0 (0) |
| oracle-old | 10 (8) | 10 (8) |
| **total** | 225 (200) | **218 (194)** |

Aurora's §5 shape moves with it: 72 files default to the live tree (45 fallback, 27 hard-coded), 7
GUARD. None of the three headline sites, the ranking in §11, or the recommendation changes.

**§10 spellings.** Every row's file count re-derived by `git grep -l -I -w <spelling> <sha>` with
command C's exclusions except `AEON_DIR` on sigil: the "124 files" reproduced under no counting rule
tried (command C 100; `"AEON_DIR"` on a non-comment line 101; any non-comment line 117; any line 145;
`env::var("AEON_DIR")` 97). The row now carries the two derivable numbers. Aurora's 60 is command C's
figure exactly. `AEON_SUITE_ROOT` is 0 in all six (table above). One env spelling was missing from the
table and from the "nine spellings" summary: bare **`AEON`**, read as `${AEON:-$HERE/../aeon}` by aurora
`scratchpad/bg-roomy-regenerate.sh:16` (the other `$AEON`/`${AEON}` hits — sigil `landing-run.sh`,
`capture_goldens.sh`, `derive_offcanonical_sizes.sh`, aurora's harness template strings — are shell or
JS locals derived from `AEON_DIR`, as §10's last paragraph already says). Added as a row. aurora
`bganim-motion-harness.mjs:301` reads `process.env.AEON_LIVE`, a `'1'` boolean, not a path — not added.

**Not re-checked here:** no sibling test was run (the doc's "static reading" caveat stands); the
per-row prose of the 500-odd PROSE/RECORD rows beyond the 9 sampled; the dirty-tree paths of oracle
and seraph at enumeration time.
