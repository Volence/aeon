# NEXT-SESSION WORK ORDER — 2026-08-15

Written after Effects P3 Parcel C2 merged, for a clean restart.

---

## State at handoff

**Both repos on `master`, green, nothing in flight.**

- aeon `1c46848a` — Merge parcel/effects-p3-c2: one preset per section, total binding
- sigil `ccfc6226` — Merge parcel/effects-p3-c2: harness lockstep (chain 118)
- refreeze **chain 118** · sigil suite **3716 / 0** across 327 binaries · four shapes boot
- Verified pair. The `parcel/effects-p3-c2` branches are merged and deleted in both repos.

Working tree carries only the pre-existing editor JSON churn
(`games/sonic4/data/editor/…`, `games/sonic4/data/sprites/object-bindings.json`) —
auto-commit-daemon territory, not ours.

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
```

Current ROM CRCs: s4 `0fcdcbaa` · s4.debug `50f6ae69` · demo `6af0112d` · demo.debug `fdc82cc0`

**UNPUSHED:** aeon is **78 commits** ahead of `origin/master` (37 from this session),
sigil **14**. `origin/master` in both is 2026-08-14. Push was NOT done — it is the
owner's call.

---

## NEXT — Effects Parcel P, the patch generalisation

Roadmap: `docs/superpowers/2026-08-14-effects-crown-roadmap.md`. P is called **the crown
unlock**, and the roadmap says do it **before D**.

**What it is.** Let a fire be declared **patchable** at authoring time and have the DSL
emit its offset as a named constant. `raster_program` already computes the exact layout
and throws it away. That single move deletes:

- the magic `WATER_TEMPLATE_ARM0_OFF` offset,
- the `sh: 1` hack (a lava line currently has to write a no-op `set_reg($8C81,$8C81)`
  purely to manufacture an init word the offset needs),
- the one-moving-boundary-per-section limit.

Everything runtime-varying needs it: lava, rising flood, lightning, beat-driven pulses,
a gradient that survives vertical camera motion.

**Already partly unblocked.** The blanket-restore parcel killed the `init_count == 1`
trap — `WATER_TEMPLATE_ARM0_OFF` is now 2 and no longer depends on a frame-top init
word. Verify that before planning around it.

**Steal while there:** S3K's `H_int_counter = H_int_counter_command + 1` — the arm word
is a prebuilt VDP command whose LOW BYTE is the counter, so re-arming is a single byte
store with no OR or masking.

After P: **W** (world-anchor ownership — raster owns `Raster_Water_World_Y`, parallax
owns per-line HScroll wave, no shared seam, so "palette boundary + shimmer at the same
line" is inexpressible), **R** (mid-screen restore), **B** (budget honesty), **D**
(starter pack + content).

---

## Read these before planning P

1. **`docs/benchmarks/effects-p3-c2/GATE-EVIDENCE.md`** and **`DECLARED-DELTAS.md`** —
   what C2 proved, and its honest limits (sections 3-8 were not rendered individually).
2. **`docs/ENGINE_ARCHITECTURE.md` §7.12** — the preset binding, written this parcel.
3. **`docs/BUGS.md`** — the EFX-1…6 ledger. EFX-2 (cross-fade unreachable) and EFX-4's
   over-read half are OPEN **deliberately**; do not "fix" either without reading why.

**The 2026-08-13 P3 spec has drifted badly** — roughly ten of its concrete references
were wrong by the time C2 executed (file paths, line numbers, a superseded `sec_pal`
contract, and four guards it asked for that already existed). Treat it as a source of
INTENT and re-derive every concrete reference against the tree.

---

## Mechanics this parcel paid for — do not rediscover

**Guard reachability (the big one).** In a module outside the target's `use` closure,
`ensure`s do not fire **and declared struct layouts are not validated**. `EffectsPreset`
shipped `(size: 36)` with 32 bytes of fields for two tasks, and a task report asserted it
matched "exactly" — nothing had checked. Check with:

```bash
SIGIL_WARNINGS=full DEBUG=1 ./build.sh 2>&1 | grep module.unreachable
```

Do not over-read the count: ~14 unreachable for sonic4 and ~40 for demo are BY DESIGN
(each evaluates in the target that uses it; Z80 sound modules evaluate via seam-1/2). A
module unreachable in BOTH targets is the anomaly.

Related traps, all measured:
- **`map.toml` `order` placement is NOT reachability.** Only a real `use` lowers a module.
- **An unreferenced top-level `const` is comptime-inert** — a `const X = f(...)` probe
  proves nothing. A top-level `ensure` IS evaluated (in a reachable module).
- **A comptime fn's body evaluates at its CALL site**, so `preset()`-style guards work
  from anywhere reachable.
- **`ensure` comparing an imported DATA symbol to an int is unevaluable and always
  passes** — both `X != 0` and `X == 0` built clean. Vacuous-guard generator.
- The reliable proof is **inversion**: flip the predicate false, confirm the build FAILS,
  flip it back.

**Harness lockstep, both directions.**
- A NEW cross-seam ref fails to LINK in a `*_port` test's standalone scope (the known
  port-flip trap) — and **a DELETED symbol takes its pin with it**, so a scope still
  naming it fails to COMPILE. Same ritual, opposite failure.
- **A `repin.toml` region whose span contains a newly-carved section measures BOTH.**
  `parallax_configs` was loud (0xE9C pinned vs 0xA8A emitted); `palette` was silently
  wrong. Whenever you add a section, check the regions on either side of it.
- Only the **PinnedBaked bootstrap** reads region base/len, so a missing registry row
  surfaces through `soundbankhead_port` ALONE, as
  `section <name> has no region in the map`.
- **Fixing a repin.toml region changes `pins.rs`, and those pins feed PLACEMENT.** The
  ROM moved *after* the first refreeze this parcel — same lengths, reordered content. If
  you touch a region, re-verify captures and re-refreeze; a gate document citing a CRC it
  did not test is worse than one citing none.

**Emulator.** Oracle only, one instance (`pgrep -a oracle_gui`), binary
`/home/volence/sonic_hacks/oracle/linux-port/build/oracle_gui`. Subagents must NEVER
touch oracle MCP — it deadlocks; the controlling session does all runtime capture.
`emulator_read_cram` cannot see a mid-scanline CRAM write during active display —
measure the FRAMEBUFFER for `OP_CRAM`/`OP_PAL_REGION`/`OP_RUN_GRADIENT` (this bit the
gradient fixture, whose comment used to prescribe the opposite; corrected in
`ojz_effects.emp`).

**Replay net** is deterministic and headless — use it, do not hand-arm:

```bash
/home/volence/sonic_hacks/oracle-next/target/release/replay_runner \
  --rom s4.debug.bin --lst s4.debug.lst --fixture ojz_fixture
# also: --fixture ojz_slide_fixture, and --negative-control
```

---

## Also open, unrelated to effects

- Sound packages **5** and **6** (`project_open_work_inventory` memory).
- The `STRESS_EVICT` famine root-cause.
- `sigil`'s `deep_nesting_aborts` binary still aborts without printing a `test result`
  line, so suite totals remain a **lower bound**. Booked, user-ruled not to chase.
- The demo-shape `.lst` symbol skew (boot_head symbols report 4 bytes high) — booked in
  `docs/BUGS.md`, ROM is correct, only the listing lies.
