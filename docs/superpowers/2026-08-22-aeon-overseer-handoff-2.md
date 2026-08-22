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

## The one open question that is the OWNER'S

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

**Also cuttable cold: the `br_ext` lane row** (`DEFERRED_WORK.md`, "unlock 1"). Sequence is
satisfied and banked at `ba189b40` — binary current and enforcing, both arms verified against
the shared artifact, committed fixture to cite. **Read the local-only warning there first.**

## ⚠ Two standing hazards that will bite you

1. **Every sigil SHA is LOCAL-ONLY.** sigil `origin/master` is `40f862e2`; local master is 38+
   commits ahead and unpushed (the owner's gate). **The assembler aeon builds against was built
   from commits that exist nowhere but this disk.** Verify reachability before citing any sigil
   SHA; treat every Aurora SHA the same way unless they say "at origin".
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
