# Aeon overseer handoff — 2026-08-22 (second rotation, the cross-session verification day)

You are the aeon overseer. Boot: `docs/OVERSEER.md`, then `../empyrean/docs/OVERSEER-PROTOCOL.md`.
This supersedes `2026-08-22-aeon-overseer-handoff.md` for anything they disagree on; that file
remains the authority for the Aurora-arc rulings and the P3/streaming state it records.

## What merged (all verified on the merged tree from clean checkouts, all pushed)

Master moved `b1f8a230` → `ba189b40`. Four CRCs held at `060401e4` / `0dbaa80f` /
`c708b114` / `dec88cc1` throughout — every parcel today was zero-byte.

| SHA | What |
|---|---|
| `98100905` | **Ruling Q4**: `project.json`'s dangling `parallax` key → `"sceneRef": null`. Aurora's reader parcel was blocked on this. Reader enumeration verdict: **DEAD** (4 readers, all explicit, none generic; `regenerate-level.sh` re-baked byte-identical). |
| `bd31e133` | **TOOL-01**: all writers of `editor_bg_override.json` read before writing, refuse loudly on unowned keys, `--out` hatch, atomic write, `GEN_PALETTE`-asserted palette preservation, band-coherence gate. Suite 1191 → 1212. |
| `1a794ace` | **`layout.odd-field` closed**: the stale hand-computed pad in `Scene` became an `offsetof(...) % 2 == 0` invariant assertion. 2 → 0. |
| `efd8d666`, `551d1841`, `419194bb`, `a2750c3a`, `ba189b40` | Rulings + bookings (below). |

## ✅ THE OWNER'S OPEN QUESTION IS ANSWERED — 2026-08-22, in his own words

Relayed via the empyrean lane, transcribed from him rather than summarized:

> "No it wasn't meant to kill the animated background, it was my experiment with chat gpt's
> monkey art generator and having it make constrained art that could work with a genesis and
> work with the engine with an import. It made something pretty and was successful but used all
> the unique tiles as a side effect. It's just an experiment with that. I think I already told
> an agent we can take out some tiles or something to give more room for our experiments with
> parallax and animation using it specifically cause it does have trees and such for scrolls or
> whatever. Yeah, feel free to let us mold it to test, it's pretty but not final."

**Settled:** (1) the July loss was **NOT** intended to kill BgAnim — it was a side effect of a
*successful* generator experiment; (2) the colonnade bands are **not** to be restored, nobody
wants those specific bands back; (3) the art is explicitly **moldable** — "pretty but not
final", take tiles out, and he specifically wants room for parallax and animation experiments
**using this art**, because it has trees and similar content suited to scroll layers; (4) the
**reserve number is delegated** — "feel free to let us mold it to test" reads as *pick a reserve
that makes the experiments possible*, not *await my number*. Put a figure to him only if it
becomes a content-quality trade rather than experiment enablement. No content-destruction
caution binds: none of this is final art.

**Correction to this lane's own record, and the distinction matters.** I had booked the
restore-vs-keep framing as "OVERTAKEN — the answer no longer matters", inferred from his
saying the art is not permanent. **He has now actually answered it, and the answer is not the
same shape as my inference:** it was not moot, it was *unintended*. Same disposition, different
fact — and only the real one explains why the tile exhaustion happened at all (a generator with
no reason to reserve, which is precisely the importer defect the reserve parcel closes).

**He also believed he had already told an agent this** — the propagation gap, observed from his
side. Worth holding: an owner can consider a thing communicated while no lane has it.

**What this does NOT do: it does not free a single tile today.** The reserve governs *future*
imports; it cannot shrink the committed blob, because telling an importer "your budget is 256"
makes it **refuse**, not re-quantise. Freeing space in *this* art needs an art-side pass —
simplify or crop the source and re-import — which is exactly the loop he describes himself
being in, and is why loud-refusal-with-a-budget is the right mechanism and lossy tile-merging
remains correctly out of scope. Until such a pass, **Aurora stays on promotion-only**, which
works and which they built first.

## ~~The one open question that is the OWNER'S~~ (ANSWERED ABOVE — kept for provenance)

**Was the colonnade → Deep Forest art replacement (`dd93a840`) meant to take the BG animation
with it?** OJZ background animation has been dead in the ROM since 2026-07-21 — two authored
bands (32×4 `camera_x` slot 0, 16×4 `timer` slot 128, 8 phases each) were destroyed by the
first run of `png_to_bg_override.py`. **The bands are recoverable two ways**: from git
(`b0e5a661`, blob `33892d82`) or by re-running `forest_bg_gen.py`, which reproduces them
exactly (340 tiles, 192 animated) and passes the new coherence gate. They were fitted to the
*replaced* art, so restoring is not free. Full detail: `docs/BUGS.md` TOOL-01, memory
`project_bganim_silent_deletion.md`.

The per-key ownership fork that was parked alongside it is **CLOSED** — empyrean `8e55475`
(§5.2): Aurora is writer-of-record, `png_to_bg_override.py` is importer/seeder. Do not
re-open it as an owner question; it was answered by a universally-quantified rule three
sessions read as Aurora-scoped (protocol bar 12).

## Queue front

**`tools/effects_gen.py`** (scanline P5) — the aeon half of Aurora wave 1, and the reason
nothing an author produces can reach a ROM yet. Its normative read set is already written:
`tools/EFFECTS_CONSUMER_CONTRACT.md` §2. Design: `specs/2026-08-22-aurora-effects-wave1-design.md`
§7 enumerates the whole aeon lane. Both contract halves have landed (aeon + empyrean).

**QUEUED — `games/sonic4/map.toml`'s fault-handler header comment is STALE and says the
opposite of what ships.** Found by the README agent as an out-of-parcel observation it
correctly declined to touch; confirmed here.

`map.toml` lines 16-19 state: *"RELEASE targets (s4, config_b) place ReleaseFault … and NOT
the error_handler island"*, citing **review item 29 part 4**. `build.sh:11-12` says, in terms:
*"APPENDIX SHAPE SPLIT (crash-report axis, owner-ruled 2026-08-04 — **this SUPERSEDES the
review-item-29 release strip**)"*, and `build.sh:175-176` + `CLAUDE.md:40` both state that the
two canonical shapes **both** carry the MD Debugger island + deb2 symbols.

**It is stale PROSE, not a stale map** — which is the distinction that decides how urgent this
is, so it was worth separating. The `order` union at `map.toml:92` lists `"ReleaseFault",
"BusError", "EndOfRom"` and is agnostic about which target gets which. And the built artifacts
disagree with the comment: `s4.lst` (**release**) and `s4.debug.lst` carry **49 island symbol
hits each** — identical counts, i.e. release does carry it. *Freshness caveat, stated rather
than glossed: those `.lst` files are leftovers in a dirty tree and I did not rebuild to confirm,
so treat them as corroborating two maintained sources (`build.sh`, `CLAUDE.md`) rather than as
independent proof.*

**Why it is worth a parcel rather than a shrug:** this is precisely the failure the shared
protocol singles out — *"the worst place for a perishable claim is a code comment"*, because a
stale ruling in a comment outlives every doc that recorded its revision; nobody re-reads a
comment to check whether the rule it cites still holds. It just sits there being wrong and being
read. This one has a superseding ruling explicitly naming it, in a file most readers of
`map.toml` will not have open.

**Not fixed now only because `map.toml` is owned by the in-flight P5 seam parcel** (which adds a
section entry to it). Cut it after that lands — same window as the `(align: N)` migration below,
and both are `.emp`/placement-adjacent so they serialize naturally together.

**QUEUED, not dispatched — the `(align: N)` migration we owe sigil.** sigil shipped the
struct-field alignment attribute at **`6fae4d6a`** (on master `560d44da`, both reachable at
origin — verified here, not taken on their word). Our side of the standing obligation:

```
sc_mask_raw:           i16 (align: 2),
sc_v_deform_shift_raw: i16 (align: 2),
```

in `engine/level/scene_dsl.emp`, and the two trailing `ensure(offsetof(Scene, …) % 2 == 0, …)`
guards delete. Error tier, so it fails the build the way the `ensure` did.

**Deliberately NOT dispatched yet, and the reason is sequencing, not doubt.** (a) It edits
`.emp`, and the in-flight P5 seam parcel is the one thing that must not race on `.emp`;
(b) it needs `SIGIL_BUILD` rebuilt from `6fae4d6a` first, or the new spelling simply does not
parse — so it is binary-gated, not just code-gated, and the byte-changing ritual wants BOTH
sigil binaries rebuilt. Cut it after the P5 seam lands.

**Three cautions from sigil, the first being the one that bites:**
1. **The spelling is `(align: N)`, NOT `@align(N)`.** `@align(N)` already exists on `vars`
   region fields where it MOVES the allocation cursor; the split is deliberate (D2.29). A
   struct field written `@align(2)` is refused **by name with a teaching diagnostic**, so the
   failure is loud rather than silent — but knowing costs nothing.
2. **`sc_pad_5D`'s width stays hand-computed.** The attribute guards the constant; it does not
   derive it. **Keep the comment block above that field** — the authority for the pad width is
   still a guard firing, now a per-field attribute instead of a trailing ensure. The thing that
   would actually retire the hand-count is `pad_to(N)`, parked on the owner as new language
   surface.
3. Scene is comptime-only and nothing emits it, so this *should* be byte-neutral by
   construction — **sigil explicitly declined to assert that and left it to us. Verify with
   CRCs; do not inherit it.**

*Provenance worth keeping: sigil shipped this at ERROR tier rather than as another warning
because of the `sc_pad_5D` comment block from this lane — `[layout.odd-field]` did fire on the
08-18→08-22 drift and was swallowed by a warning baseline nobody re-read. A lint that fires
into a baseline is not a guard. They also re-pointed their `OVERSEER.md` cite of our ensures
from `scene_dsl.emp:1025,1027` to the symbol names, which is the coordinate-rot bar applied
without being asked.*

**Also cuttable cold: the `br_ext` lane row** (`DEFERRED_WORK.md`, "unlock 1"). Sequence is
satisfied and banked at `ba189b40` — binary current and enforcing, both arms verified against
the shared artifact, committed fixture to cite. **Read the local-only warning there first.**

## ⚠ Two standing hazards that will bite you

1. ~~**Every sigil SHA is LOCAL-ONLY.** sigil `origin/master` is `40f862e2`; local master is 38+
   commits ahead and unpushed (the owner's gate).~~ **STALE — CORRECTED 2026-08-22, later the
   same day.** sigil has pushed: `origin/master` is now **`560d44da`**, verified against the
   remote with `git ls-remote origin refs/heads/master` (not by reading the sibling working
   directory), and `merge-base --is-ancestor` confirms both `560d44da` and `6fae4d6a` are
   reachable there. So sigil SHAs are citable anchors again.
   **Keep the discipline, drop the blanket assumption:** still verify reachability before citing
   any sigil SHA, because "sigil is pushed" is itself a snapshot that ages exactly like the claim
   it replaces. And **treat every Aurora SHA as local-only unless they say "at origin"** — that
   half is unchanged and Aurora states the class explicitly in their messages.
   *Why this correction is worth the lines: a standing hazard in a boot doc is the highest-leverage
   place for a stale fact, because every fresh session reads it as current and nothing prompts a
   re-check. This one would have made a lane refuse to cite a perfectly good anchor — a false
   negative, so it fails silently and looks like caution. Same class empyrean and seraph both hit
   today from the other direction (a doc's self-description hardening into an owner approval).*
2. **As of `98100905`, every fresh checkout trips `level staleness` on mtime alone** (that
   parcel edited `project.json`). Remedy: `tools/regenerate-level.sh`, then revert the
   `DONOR_PROVENANCE.json` churn — unchanged level bytes mean the existing stamp still
   describes them. And a worktree named `X` needs a paired `sigil/.worktrees/X` or the
   emp-helper-closure locator silently falls through to sigil master.

## Rulings banked in `docs/OVERSEER.md` today — read them there, not here

- **CRC identity is blind to source-derived gates.** The refreeze-gated lint baseline could not
  see six consecutive zero-byte parcels. A zero-byte parcel touching `.emp` owes a source-drift
  check (`SIGIL_WARNINGS=full` before/after).
- **On a byte-neutral parcel, byte identity witnesses the SOURCE, never the BUILD.** Four CRCs
  matched their pins for a build that never ran. `rm -f` the ROMs first so existence proves
  freshness.
- **A citation has TWO SHAs** — the one you cite and the one you verified at. Never certify a
  LINE NUMBER with a SHA (`s4-types.ts:227` was `interface Palette` at my own pin, and had been
  two different types in one day). **Anchor to the symbol; let the SHA date the claim.**

**The family these belong to**, worth holding as one idea: the instrument in all three was
byte identity, and *byte identity is silent on every question about provenance* — did this come
from current source, did this build run, is this tool current. Excellent answer to "are the
bytes the same"; no answer at all to "should they be." The remedy is a provenance witness per
artifact, not more byte checks.

## Peer state

- **sigil-83**: quiet, master `dcadba70` (local-only). Owes: corpus-ungating SHA for the
  `OVERSEER.md` cross-reference. Queue: `game-defines` #1 (we owe the T8 three-context adoption
  check on their ship notice), ungating #2, provenance witness, Capstone differential,
  alignment attribute (when it lands, migrate our two `ensure`s and retire them).
- **aurora-86**: scene-authoring UI + re-point parcels in flight on their side. BgAnim is
  unblocked — `bd31e133` is their §6 gate for the first non-empty `anims` commit.
- **empyrean-73**: `origin/main` `3bbfeb1`. §5.1 cites our coherence gate with the vacuity
  caveat intact.

## Method note worth keeping

Not one of the day's findings was caught by the session that made it. **Mutual verification
cannot catch a shared frame — only a changed frame can.** Every error today was the same shape:
a competent lookup returning a clean answer about the wrong object. Verify peers firsthand, and
expect the favour back.
