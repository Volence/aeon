# Aeon overseer handoff — 2026-08-22 (third rotation: the Aurora handshake day)

You are the aeon overseer. Boot: `docs/OVERSEER.md`, then read the shared protocol **at a
committed revision** (`git -C ../empyrean fetch -q origin && git -C ../empyrean show
origin/main:docs/OVERSEER-PROTOCOL.md`) — never through the sibling path, which is a peer's
live tree.

Supersedes `2026-08-22-aeon-overseer-handoff-2.md` where they disagree. That file remains the
authority for the earlier rulings and its own corrections, which are still accurate.

## ⚠ YOU ARE PROBABLY BOOTING INTO THE EMULATOR CUTOVER

The owner is flipping the MCP emulator binding from the legacy C++ server to the Rust core,
and relaunching every lane through a new console ("Dominion"). **A config change does not
touch running sessions**, so this rotation exists partly to make the flip take.

- **Rust core anchor: oracle `12cc17e`**, pushed and origin-reachable. It serves **41
  methods**; `write_vram` and `breakpoint_add` are **absent**. An unserved method returns
  **`-32601` naming it** — verified over the wire by the oracle lane, not grepped.
- **A gap is a REQUEST, not a workaround.** Owner's standing directive: *"tell it to make sure
  to tell the oracle agent to build out any tools these other suite items/agents might need,
  that's how we're getting robust."* And his framing of the cutover: *"this is really just to
  start building out the tooling"* — so a `-32601` is the mechanism **working**. Report it fast
  and cheap; do not engineer around it.
- **Breakpoints and `wait_for_break` do not exist there.** For an arm→wait→clear flow use
  `run_to{symbol}` — **`run_to` takes a symbol**, which is the piece nobody had noticed.
- **`status.romPath` comes back RELATIVE** (`"../aeon/s4.debug.bin"`), a known violation of
  oracle's own `protocol.md` SHOULD. Do not assume absolute.
- **We are already 8 tools deep into this cutover** — `boot_override_gate`, `effects_gates`,
  `hblank_window_sweep`, `sh_probe`, `staging_lifetime_timeline`, `tick_variance_probe`,
  `vsplit_landing_gate`, `warp_mailbox_gate` reference `oracle-aether`/`--no-pace`. It is
  **partial and in progress, not pending**.
- **HOLD: do not migrate the three cost probes** (`raster_cost_probe`,
  `engine_baseline_probe`, `streaming_choke_probe`) to oracle-next's profiler. Full reasoning
  in `docs/OVERSEER.md`'s Instruments section — `perFrame[].vintCycles` may displace a
  boundary-straddling handler's whole cost, **LOCATED NOT CONFIRMED**, and our sustained-
  streaming workloads make boundary-straddling the *normal* case.
- **Pixel capture is COMPOSABLE TODAY** on the Rust core (`play_input` + `scanlines{}` +
  `state_hash{includeFramebuffer}`). The old "three capture protocols failed their own
  controls" result is a **legacy-server** fact — stop carrying it. Still poison-test before
  adopting anything as a gate.

## What merged today — master `b1f8a230`-era → `74bdebf3`, all pushed, all verified from CLEAN checkouts

| SHA | What |
|---|---|
| `e0fe9499` | **P5 slice 5 — the binding seam. An Aurora-authored scene can reach a ROM for the first time.** Generated per-act module + unconditional `act_descriptor.emp` import + reachability gate + build wiring. |
| `93c436ec` | **`band_reserve` in `vram.toml`** — the importer refuses above `capacity - reserve` instead of treating 448 as pass/fail. |
| `880fcaf5` | **`band_reserve = 128`** set (one full-size animated band), plus three reserve tests reshaped from config-pins into derived checks. |
| `74bdebf3` | **Band coverage closed to 1..8**, gated on `MAX_PARALLAX_BANDS` by derivation rather than a list. |
| `9c6e5394` | **43-file triage** — they are the owner's work, not scrap; `.gitignore` for the export dump + save-states. |
| `c0d16788` | **README** rewritten against the tree (12 booked defects). |
| `4e6ad158` | **`map.toml`'s superseded fault-handler comment** retracted. |
| `f69c561e`, `2c746960`, `a3f17516`, `8ccef438`, `891b4a8b`, `f6d49db4`, `e5361e3b` | Rulings, measurements, hazard retractions. |

Four CRCs held at `2009211676` / `1171096707` / `957967962` / `64447604` (cksum) throughout —
**every parcel today was byte-neutral.** Suite 1262 → 1329, zero failures.

## Queue front — in the order I would cut them

**1. STAGE THE OWNER'S 38 STRANDED FILES. Byte-mover. Now UNBLOCKED — nothing else contends.**
Plan and full provenance: `docs/superpowers/notes/2026-08-22-dirty-tree-triage.md`. Two commits
that MUST land together (authoring, then bake — the collision tables are interned against the
strip indices), enumerated paths only. Carries the repin → refreeze ritual. **The owner
explicitly approved this**: *"Yes that sounds fine, aeon sort them in."*

**2. The `(align: N)` migration owed to sigil.** `6fae4d6a` on sigil master `5b2e50f8`, both at
origin. Two `Scene` fields take `(align: 2)`, two trailing `offsetof % 2` ensures delete. The
spelling is `(align: N)` and **NOT** `@align(N)`. **Binary-gated**: rebuild `SIGIL_BUILD` from
`6fae4d6a` first or it will not parse. Byte-neutrality is OURS to verify — sigil explicitly
declined to assert it.

**3. The `v_factor` contract defect — reported to empyrean, unowned until they rule.** The
schema types `v_factor` as a packed horizontal scroll factor (`$ref: #/$defs/factor`); the
engine uses it as a **vertical shift**, `u8`, `0..15`, `15` = lock sentinel
(`scene_dsl.emp:981`, `parallax.emp:1523`). Aurora's UI offers `FACTOR_*` values for it because
the schema says to, and they fold to nonsense (288). Same group: `v_offset` is schema-`integer`
but engine-`u16`, so negative offsets are schema-legal and engine-illegal — **that one may be
the ENGINE that is wrong**, and changing a shipped record's signedness is not a solo call.
**Do not harden the aeon side until empyrean rules**, or you may harden the wrong half.

## The day's biggest lesson: FIVE stale hazards, and every one failed PERMISSIVELY

Each told a reader to ignore something real, and none of them errored:

1. *"Every sigil SHA is local-only"* → refuse a valid anchor. sigil is pushed; `origin/master`
   moved.
2. *"Every fresh checkout trips level staleness"* → expect a failure that is not there. It is
   **nondeterministic** (git checkout near-ties the mtimes; the compare is a strict `>`).
3. *"~9-13 pytest failures are path artifacts"* → **write off up to thirteen real failures.**
   Measured zero, with no paired sigil worktree.
4. *"147 pytest functions run by nothing"* → build a runner that exists. `build.sh:414` has run
   `pytest tools` **build-fatally** since 2026-08-16. **This one cost a bad dispatch and a
   mid-flight agent correction.**
5. *"The editor tree is auto-commit-daemon territory — never touch it"* → **the daemon does not
   exist**, and 38 files of the owner's work sat unversioned for days.

**An ownership or hazard claim needs a LIVENESS CHECK, not a citation.** A permissive stale
hazard is worse than a strict one because nothing downstream ever contradicts it — the reader
dismisses the very evidence that would correct them. Expect more of these; assume the boot docs
are the highest-leverage place for them.

## Method notes worth keeping

- **Writer-ORIGINATED beats writer-CERTIFIED.** Aurora's fixture authored through their real UI
  (`07547231a860555ac79a681898b38713bbe7ef78`, aurora `c72a4270`) found **two** defects invisible
  to every test in both repos, because it enumerated over *the app's vocabulary* rather than over
  the schema. Their exhaustive hand-written shape-coverage fixture provably could not reach
  either. **Do not let anyone "tidy" that fixture to make it pass.**
- **The best agent results contradicted their briefs.** One on five points, one on two — and they
  were right every time I checked. Keep the contradict-me clause in every dispatch; it is what
  caught my own stale facts.
- **A wrong fact in a BRIEF is worse than in a message** — an agent has no standing to doubt its
  controller. Verify at dispatch time or mark it unverified.
- **Uncommitted files are invisible to a worktree agent.** Any triage-shaped dispatch must be
  read-only against the main tree, writes on a branch, staging by the controller.

## Peer state

- **aurora-86**: scene UI, re-point, BgAnim model all landed at their origin. They have handed
  cross-repo validation of `effects_gen` to us permanently. Holding for the `v_factor` ruling.
- **sigil-83**: `(align: N)` shipped; fixing a `pub equ` export gap (parser accepts `pub`,
  `item_pub_name()` drops it). They have registered a notify-before-change dependency on
  `pub equ` staying zero-byte and listing-visible — **our seam's reachability witness relies on
  exactly that**, and if it changed our gate would go quietly vacuous rather than loudly red.
- **empyrean-73**: owns the effects schema; holds the `v_factor` question and the oracle date.
- **oracle-next-f3**: cutover half done at `12cc17e`.

## Nothing is blocked on the owner

The reserve number was delegated and is set. Both BgAnim questions are closed. The triage is
approved. **A fresh boot can continue without asking him anything.**
