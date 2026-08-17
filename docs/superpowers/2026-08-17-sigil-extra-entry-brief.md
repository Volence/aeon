# BRIEF — `--extra-entry` on `sigil build`: retire the EFX-10 carrier

**For:** an agent working in the sigil repo with no prior context on Parcel R1.
**One small parcel.** A new CLI flag, its tests, and the aeon-side retirement of a
workaround. The workaround is live and well-guarded, so this is not urgent — but it is
scaffolding, and the removal condition written into its own header names this flag.

---

## The world you are working in

| repo | what it is | branch | push? |
|---|---|---|---|
| `/home/volence/sonic_hacks/sigil` | the from-scratch Rust assembler that builds aeon | `master` | yes |
| `/home/volence/sonic_hacks/aeon` | the Mega Drive engine it builds | `master` | yes |

The standing rituals bind: byte-changing sigil work rebuilds BOTH release binaries and runs
`repin` → `refreeze --freeze NAME --ab REF`; the full suite is `cargo test --release
--no-fail-fast` and green means the AGGREGATE across every binary (3721/0 as of chain 133 —
sum the `test result:` lines field-safely; a naive awk over them has already mis-hidden 2
failures once). New cross-seam symbol references break the `*_port` tests silently — check
them by name.

---

## The problem (EFX-10 in `aeon/docs/BUGS.md` — read that entry first)

aeon now has a **negative-build lane**: eleven poison `.emp` modules
(`aeon/games/sonic4/test/poison/*.emp`) that MUST fail the build, each asserting a specific
guard message and a specific diagnostic count (`aeon/tools/emp_expect_fail.py`). The
natural invocation — `sigil emp <module> --root <aeon>` — cannot run them:
`run_emp_program` (sigil-cli/src/main.rs, the `Manifest::scan` path around `:579`) does not
apply the two manifest rewrites `sigil build` applies (`publicize_helper_comptime`,
`normalize_helper_imports` — sigil-harness/src/native.rs, `build_emp`). Three failure
layers were measured (2026-08-17, recorded in EFX-10): the helper names aren't in scope;
raster_dsl's private helpers aren't importable; and the closure then demands the build's
`-D` interface values the lane doesn't have. No aeon-side spelling of a poison fixes this —
the fix is sigil-side.

**The interim (to be deleted by this parcel):** a zero-byte carrier module
(`aeon/games/sonic4/test/poison_carrier.emp`) inside the real build's `use` closure via a
named import in `ojz_effects.emp`; the lane REWRITES that tracked file per case, runs
`sigil build --native`, and restores it — sentinel-guarded, self-healing, Fable-ruled
2026-08-17 as interim-only.

---

## The feature

`sigil build ... --extra-entry <module-id-or-path>` (repeatable): evaluate the named
module **inside the real build profile** — same manifest rewrites, same helper
publication, same `-D` values, same synthetic-entry context — as if it carried a `use`
edge from the synthetic entry. Its module-level `ensure`s therefore RUN, and a failing
`ensure` fails the build with its message, exactly as any reachable module's would.

Design notes, learned the hard way this week — honor them:

1. **The extra entry's diagnostics must flow to the normal report** (`[Error] <message>`
   on the normal stream, nonzero exit). The lane's contract is: nonzero exit AND the
   expected message fragment present AND `count("[Error]") == expected` — do not change
   any of those surfaces.
2. **Do not let the PLUMBING mint new diagnostics.** The synthetic entry's own edge to the
   extra module must not trip `[import.no-names]` or any warn-tier lint — the warn-tier
   corpus tests (`sigil-cli/tests/warn_tier_corpus.rs`) assert the synthetic entry's own
   diagnostics never reach the build report, and a bare whole-module `use` already broke
   two of them once (fixed in aeon `008523ec` by a named import; your synthetic edge must
   use whatever form is diagnostic-silent — the corpus tests are your red-first check).
3. **The poisons are written in the ambient authoring spelling** (no imports, `module`
   line first) — deliberately, so they resolve names exactly as a real author's module
   would. The flag must accept that spelling unchanged; if it can't, the flag is wrong,
   not the poisons.
4. **A missing/unparseable extra-entry module is its own loud error**, never a silent
   skip — a lane whose subject vanished must fail, not pass (the vacuous-gate rule).
5. `--extra-entry` must have **zero effect on emitted bytes** for a module that only
   carries `ensure`s (the poison case). If a passed extra entry would emit `data`/code,
   pick a behavior and TEST it (refuse is fine; silent emission into the ROM is not).

## Definition of done — non-negotiable

1. Sigil-side: the flag exists with tests covering (a) a failing extra entry fails the
   build with its message, (b) a passing one changes no bytes (golden CRC unchanged),
   (c) two `--extra-entry` flags compose, (d) a missing module errors loudly, (e) the
   warn-tier corpus stays green. Full suite aggregate green; both release binaries
   rebuilt; `repin`/`refreeze` only if bytes moved (they should not).
2. aeon-side retirement, same parcel (the clean-not-bolted-on rule): `emp_expect_fail.py`
   swaps its backend to one `sigil build --native --extra-entry <poison>` per case —
   the CASES rows (paths, fragments, counts) carry over verbatim; the carrier file, its
   named import + consuming ensure in `ojz_effects.emp` (`ZZ_POISON_CARRIER_PRESENT`),
   and the lane's rewrite/restore/self-heal machinery are DELETED; the sentinel is
   replaced by its `--extra-entry` equivalent (an always-failing poison that proves the
   flag still evaluates — keep the anti-vacuity control, change its mechanism).
3. The lane runs green: 11/11 cases + sentinel, from `build.sh` and standalone. All
   four aeon shapes byte-identical before/after the retirement (the carrier was
   zero-byte; deleting it must be too — the `use` edge removal is the one thing to
   CRC-check).
4. `aeon/docs/BUGS.md` EFX-10 CLOSED (not re-scoped) naming this parcel;
   `poison/README.md` updated to describe the flag backend; the carrier's header
   removal-condition paragraph dies with the file.

## Traps

- The per-case cost was ~0.7 s under the carrier (a full native build per poison). The
  flag pays the same manifest scan; if you can evaluate N extra entries in ONE build
  invocation and report per-module, the lane drops from ~8 s to ~1 s — nice, not
  required; if you do it, the per-case message/count attribution must survive batching
  (the lane asserts counts PER CASE; a batched run that merges diagnostics breaks it —
  either keep one invocation per case or emit per-module sections the lane can split).
- aeon and sigil merge as a PAIR when coupled; the retirement commit and the flag commit
  land in their own repos but the aeon lane must never point at a flag the pinned sigil
  binaries don't have — land sigil first, rebuild the release binaries, then flip aeon.
- The expect-fail lane is invoked by `build.sh` — while iterating on the flag, remember
  every aeon build you run exercises the OLD backend until the flip; don't half-flip.

## Process expectations

Commit every step; exact `git add` paths; verify the branch at commit time; never leave
either master broken; the editor-data files under `aeon/games/sonic4/data/editor/**`
belong to an auto-commit daemon — never stage them. For a judgment call inside scope,
dispatch a Fable adviser with the evidence and your leaning; for anything that changes
direction or freezes a format, STOP and write the brief instead.
